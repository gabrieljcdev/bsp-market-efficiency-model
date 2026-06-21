import csv
import time
import curl_cffi

from pathlib import Path
from datetime import date, timedelta, datetime

from models.betfair import BSP, BSPMap


class Betfair:
    def __init__(self, race_urls: list[str]):
        self.urls: list[tuple[str, str]] = create_urls(race_urls)
        self.data: BSPMap = {}
        self.rows: list[BSP] = []

        for url, region in self.urls:
            rows = get_data(url, region)

            if not rows:
                continue

            self.rows.extend(rows)

            for row in rows:
                key = (row.region, row.date, row.off)
                self.data.setdefault(key, []).append(row)

    @classmethod
    def from_csv(cls, path: Path) -> 'Betfair':
        self = cls.__new__(cls)

        self.urls = []
        self.data = {}
        self.rows = []

        with open(path, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            for record in reader:
                bsp = BSP.from_csv(record)
                if not bsp:
                    continue

                self.rows.append(bsp)

                key = (bsp.region, bsp.date, bsp.off)
                self.data.setdefault(key, []).append(bsp)

        return self


def create_date_range(date_start: str, date_end: str) -> list[date]:
    start = datetime.strptime(date_start, '%Y-%m-%d').date() - timedelta(days=1)
    end = datetime.strptime(date_end, '%Y-%m-%d').date() + timedelta(days=1)

    dates: list[date] = []
    current = start
    while current <= end:
        dates.append(current)
        current += timedelta(days=1)

    return dates


def create_urls(race_urls: list[str]) -> list[tuple[str, str]]:
    url_base = 'https://promo.betfair.com/betfairsp/prices/dwbfprices'
    regions = ['uk', 'ire', 'usa', 'aus', 'fr', 'uae']

    dates = {x.split('/')[6] for x in race_urls}
    date_start, date_end = min(dates), max(dates)
    dates = create_date_range(date_start, date_end)

    urls: list[tuple[str, str]] = []

    for d in dates:
        formatted = d.strftime('%d%m%Y')
        for region in regions:
            urls.append((f'{url_base}{region}win{formatted}.csv', region.upper()))

    return urls


# Betfair's promo endpoint rate-limits (HTTP 429) under sustained sequential
# load and sends NO Retry-After header. Empirically ~1 req/s is throttle-free,
# ~0.6s is near-clean; firing flat-out gets ~70% of requests 429'd. A small
# polite delay before every request keeps us under the limit and is FAR faster
# overall than hammering and eating fixed 10s backoffs on each 429.
_THROTTLE_DELAY = 0.7


def _bf_get(url: str, attempts: int = 6, base: float = 2.0, cap: float = 60.0):
    """curl_cffi.get with a timeout and retry/backoff on transient network
    errors, so a single timed-out SP-file download can't crash the run."""
    for i in range(1, attempts + 1):
        try:
            return curl_cffi.get(url, timeout=20)
        except Exception:
            if i >= attempts:
                raise
            time.sleep(min(base * (2 ** (i - 1)), cap))


def get_data(url: str, region: str) -> list[BSP] | None:
    # Politeness delay to stay under Betfair's rate limit (see _THROTTLE_DELAY).
    time.sleep(_THROTTLE_DELAY)

    resp = _bf_get(url)

    # Up to 8 retries for throttle/transient server errors, with exponential
    # backoff (no Retry-After header is sent, so we self-pace).
    for attempt in range(8):
        if resp.status_code == 404:
            return None
        if resp.status_code == 200:
            break
        if resp.status_code in (429, 520):
            time.sleep(min(2.0 * (2 ** attempt), 60.0))
            resp = _bf_get(url)
            continue
        raise RuntimeError(f'HTTP error {resp.status_code} for URL {url}')

    if resp.status_code != 200:
        raise RuntimeError(f'HTTP error {resp.status_code} for URL {url}')

    reader = csv.DictReader(resp.content.decode().splitlines())
    rows: list[BSP] = []

    for record in reader:
        # Betfair's dwbf SP files use UPPERCASE headers for older dates and
        # lowercase for newer ones; normalise so both formats parse.
        record = {k.lower(): v for k, v in record.items() if k is not None}
        bsp = BSP.from_record(record, region)
        if bsp:
            rows.append(bsp)

    return rows
