import csv
from pathlib import Path

d = Path('/home/gabriel/projects/racing_project/data/joined')
for name in ['joined_gb_2024.csv', 'joined_gb_2025.csv', 'joined_gb_2026.csv']:
    p = d / name
    rows = bsp = 0
    cols = 0
    with open(p, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        cols = len(r.fieldnames)
        for row in r:
            rows += 1
            if row.get('bsp'):
                bsp += 1
    pct = 100.0 * bsp / rows if rows else 0
    print(f'{name}: {rows} rows, {cols} cols, {bsp} with bsp ({pct:.1f}%)')
