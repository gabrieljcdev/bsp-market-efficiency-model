#!/usr/bin/env python3
"""Combine the per-year GB form+BSP joined files (2018-2026) into one master
CSV. All years are now offline-joined (data/joined/joined_gb_{year}.csv) via
offline_join.py against the Betfair caches, sharing an identical 52-col schema:
the prior 48 + wap (PPWAP), morning_wap, morning_vol, wap_valid. Re-joining the
2018-2023 inline files reproduces their bsp/pre_min/... numerically (verified:
0 mismatches), and adds the WAP struck-price columns. Strings preserved as-is.
"""
import csv
from pathlib import Path

ALL = Path('/home/gabriel/projects/racing_project/vendor/rpscrape/data/region/gb/all')
JOINED = Path('/home/gabriel/projects/racing_project/data/joined')
OUT = JOINED / 'joined_gb_2018_2026.csv'

sources = [JOINED / f'joined_gb_{y}.csv' for y in range(2018, 2027)]

ref_hdr = None
total = 0
bsp_filled = 0
with open(OUT, 'w', newline='', encoding='utf-8') as fout:
    writer = None
    for p in sources:
        with open(p, newline='', encoding='utf-8') as fin:
            reader = csv.reader(fin)
            hdr = next(reader)
            if ref_hdr is None:
                ref_hdr = hdr
                writer = csv.writer(fout)
                writer.writerow(hdr)
                bsp_idx = hdr.index('bsp')
            elif hdr != ref_hdr:
                raise SystemExit(f'HEADER MISMATCH in {p.name}; aborting combine.')
            n = 0
            for row in reader:
                writer.writerow(row)
                n += 1
                if row[bsp_idx]:
                    bsp_filled += 1
            total += n
            print(f'  + {p.name}: {n} rows')

print(f'\nDONE {OUT.name}: {total} rows, {len(ref_hdr)} cols, '
      f'{bsp_filled} with bsp ({100.0*bsp_filled/total:.1f}%)')
