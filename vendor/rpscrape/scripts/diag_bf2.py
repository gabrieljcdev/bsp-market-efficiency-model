"""Find a non-throttled request rate, and inspect 429 Retry-After."""
import time
import curl_cffi
from datetime import date, timedelta

base = 'https://promo.betfair.com/betfairsp/prices/dwbfprices'
regions = ['uk', 'ire', 'usa', 'aus', 'fr', 'uae']
start = date(2024, 3, 10)

for delay in (0.3, 0.6, 1.0):
    codes = {}
    n = 0
    t0 = time.time()
    retry_after_seen = set()
    for i in range(6):
        d = start + timedelta(days=i)
        f = d.strftime('%d%m%Y')
        for r in regions:
            url = f'{base}{r}win{f}.csv'
            n += 1
            try:
                resp = curl_cffi.get(url, timeout=20)
                codes[resp.status_code] = codes.get(resp.status_code, 0) + 1
                if resp.status_code == 429:
                    ra = resp.headers.get('Retry-After')
                    retry_after_seen.add(ra)
            except Exception as e:
                codes[type(e).__name__] = codes.get(type(e).__name__, 0) + 1
            time.sleep(delay)
    el = time.time() - t0
    print(f'delay={delay}s: {n} reqs in {el:.1f}s codes={codes} retry_after={retry_after_seen}')
