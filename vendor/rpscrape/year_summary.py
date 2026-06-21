"""Print a one-line sanity summary for a scraped CSV.
Usage: year_summary.py <YEAR> <CSV_PATH>  (run from vendor/rpscrape/scripts)
"""
import csv
import os
import sys

year = sys.argv[1]
f = sys.argv[2]

if not os.path.exists(f):
    print(f'SUMMARY {year}: NO OUTPUT FILE ({os.path.basename(f)})')
    sys.exit(0)

rows = list(csv.DictReader(open(f, encoding='utf-8')))
n = len(rows)
if n == 0:
    print(f'SUMMARY {year}: 0 rows ({os.path.basename(f)})')
    sys.exit(0)


def pct(col: str) -> int:
    return 100 * sum(1 for r in rows if (r.get(col) or '').strip()) // n


cols = list(rows[0].keys())
parts = [
    f'rows={n}',
    f'cols={len(cols)}',
    f'or={pct("or")}%',
    f'rpr={pct("rpr")}%',
    f'comment={pct("comment")}%',
    (f'bsp={pct("bsp")}%' if 'bsp' in cols else 'bsp=MISSING'),
]
print(f'SUMMARY {year}: ' + ' '.join(parts) + f'  [{os.path.basename(f)}]')
