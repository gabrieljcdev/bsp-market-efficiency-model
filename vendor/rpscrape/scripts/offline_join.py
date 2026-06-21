#!/usr/bin/env python3
"""Offline form+BSP join — attaches Betfair SP data to an already-scraped RP
form CSV WITHOUT re-hitting Racing Post.

Replicates rpscrape's inline ``Race.join_betfair_data`` (utils/race.py) exactly:
  - match key  = (region, date, off)  [exact]
  - horse norm = horse.split('(')[0].strip().lower()   (drops '(IRE)' etc.)
  - matched if jarowinkler_similarity(name, bsp.horse) >= 0.77  (first hit wins)
  - copies bsp, pre_min, pre_max, ip_min, ip_max, pre_vol, ip_vol,
           wap, morning_wap, morning_vol  (wap == Betfair PPWAP, the pre-off
           volume-weighted avg traded price -- the interim REAL struck price;
           morning_wap is an earlier same-day comparison point)
  - derives wap_valid: 1 iff wap parses to decimal odds > 1.0 (a usable struck
           price). Carries a WAP-vs-close timing component; NOT a timestamped
           strike, but good enough for a real CLV distribution.

Appending the three new BSP cols after ip_vol keeps the cross-era 48-col schema
identical (2018-2023 inline + 2024-2026 offline) -> still combinable by
combine_years.py, now at 52 cols.

Reuses rpscrape's own primitives (Betfair.from_csv builds the BSPMap, the same
jarowinkler match) so the output is byte-for-byte consistent with the 2018-2023
inline-join files. BSP rows are region-keyed, so GB form only matches GB BSP.

Usage (from scripts/):
    python offline_join.py <form_csv> <betfair_cache_csv> <out_csv>
e.g.
    python offline_join.py \
        ../data/region/gb/all/2024_01_01_2024_12_31.csv \
        ../.cache/betfair/2024_01_01_2024_12_31.csv \
        ../../../data/joined/joined_gb_2024.csv
"""
import csv
import sys
from pathlib import Path

from jarowinkler import jarowinkler_similarity

from utils.betfair import Betfair

BF_COLS = ['bsp', 'pre_min', 'pre_max', 'ip_min', 'ip_max', 'pre_vol', 'ip_vol',
           'wap', 'morning_wap', 'morning_vol']
DERIVED = ['wap_valid']   # 1 iff wap is a usable struck price (decimal odds > 1)
THRESHOLD = 0.77


def _wap_valid(wap) -> str:
    """1 iff wap is a real, usable struck price (parses to decimal odds > 1.0)."""
    try:
        return '1' if float(wap) > 1.0 else '0'
    except (TypeError, ValueError):
        return '0'


def main() -> None:
    if len(sys.argv) != 4:
        print(__doc__)
        sys.exit(2)

    form_path = Path(sys.argv[1])
    cache_path = Path(sys.argv[2])
    out_path = Path(sys.argv[3])
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # BSPMap: (region, date, off) -> [BSP, ...], horse names already lowercased.
    bf = Betfair.from_csv(cache_path)
    bsp_map = bf.data
    print(f'Loaded {len(bf.rows)} BSP rows, {len(bsp_map)} race keys from {cache_path.name}')

    matched = 0
    total = 0
    with open(form_path, newline='', encoding='utf-8') as fin, \
         open(out_path, 'w', newline='', encoding='utf-8') as fout:
        reader = csv.DictReader(fin)
        fieldnames = list(reader.fieldnames or [])
        # Append BSP + derived columns if not already present (idempotent).
        out_fields = (fieldnames
                      + [c for c in BF_COLS if c not in fieldnames]
                      + [c for c in DERIVED if c not in fieldnames])
        writer = csv.DictWriter(fout, fieldnames=out_fields)
        writer.writeheader()

        for row in reader:
            total += 1
            for c in BF_COLS:
                row.setdefault(c, '')
                row[c] = ''
            row['wap_valid'] = '0'

            key = (row.get('region', ''), row.get('date', ''), row.get('off', ''))
            candidates = bsp_map.get(key)
            if candidates:
                name = row.get('horse', '').split('(')[0].strip().lower()
                for bsp in candidates:
                    if jarowinkler_similarity(name, bsp.horse) >= THRESHOLD:
                        row['bsp'] = bsp.bsp or ''
                        row['pre_min'] = bsp.pre_min or ''
                        row['pre_max'] = bsp.pre_max or ''
                        row['ip_min'] = bsp.ip_min or ''
                        row['ip_max'] = bsp.ip_max or ''
                        row['pre_vol'] = bsp.pre_vol or ''
                        row['ip_vol'] = bsp.ip_vol or ''
                        row['wap'] = bsp.wap or ''
                        row['morning_wap'] = bsp.morning_wap or ''
                        row['morning_vol'] = bsp.morning_vol or ''
                        row['wap_valid'] = _wap_valid(bsp.wap)
                        matched += 1
                        break

            writer.writerow(row)

    pct = 100.0 * matched / total if total else 0.0
    print(f'DONE {out_path.name}: {matched}/{total} runners matched to BSP ({pct:.1f}%)')


if __name__ == '__main__':
    main()
