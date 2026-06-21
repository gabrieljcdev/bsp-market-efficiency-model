import csv
from pathlib import Path

ALL = Path('/home/gabriel/projects/racing_project/vendor/rpscrape/data/region/gb/all')
JOINED = Path('/home/gabriel/projects/racing_project/data/joined')

sources = []
for y in range(2018, 2024):
    sources.append(('inline', y, ALL / f'{y}_01_01_{y}_12_31.csv'))
sources.append(('offline', 2024, JOINED / 'joined_gb_2024.csv'))
sources.append(('offline', 2025, JOINED / 'joined_gb_2025.csv'))
sources.append(('offline', 2026, JOINED / 'joined_gb_2026.csv'))

ref_hdr = None
for kind, y, p in sources:
    if not p.exists():
        print(f'{y} [{kind}] MISSING: {p}')
        continue
    with open(p, newline='', encoding='utf-8') as f:
        r = csv.reader(f)
        hdr = next(r)
        rows = sum(1 for _ in r)
    if ref_hdr is None:
        ref_hdr = hdr
        hdr_ok = 'REF'
    else:
        hdr_ok = 'OK' if hdr == ref_hdr else 'HEADER DIFFERS!'
    print(f'{y} [{kind}]: {rows:>6} rows, {len(hdr)} cols  {hdr_ok}  ({p.name})')
