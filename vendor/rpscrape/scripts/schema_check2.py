import csv
from collections import Counter
from pathlib import Path

INLINE = Path('/home/gabriel/projects/racing_project/vendor/rpscrape/data/region/gb/all/2023_01_01_2023_12_31.csv')
OFFLINE = Path('/home/gabriel/projects/racing_project/data/joined/joined_gb_2024.csv')
FORM2024 = Path('/home/gabriel/projects/racing_project/vendor/rpscrape/data/region/gb/all/2024_01_01_2024_12_31.csv')

BF = ['bsp', 'pre_min', 'pre_max', 'ip_min', 'ip_max', 'pre_vol', 'ip_vol']


def rows(p):
    with open(p, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def fmt_profile(vals):
    """Classify each non-empty value's numeric format."""
    c = Counter()
    for v in vals:
        if v == '' or v is None:
            c['empty'] += 1
        elif v == '–' or v == '-':
            c['dash'] += 1
        elif '.' in v:
            dec = len(v.split('.')[1])
            c[f'{dec}dp'] += 1
        else:
            c['int'] += 1
    return c


print('=== 1. missing-OR sentinel: does INLINE 2023 also use en-dash? ===')
ri = rows(INLINE)
ro = rows(OFFLINE)
print('inline 2023  or:', fmt_profile(r['or'] for r in ri))
print('offline 2024 or:', fmt_profile(r['or'] for r in ro))
print('inline 2023  rpr:', fmt_profile(r['rpr'] for r in ri))
print('offline 2024 rpr:', fmt_profile(r['rpr'] for r in ro))

print()
print('=== 2. BSP price-format profiles (inline 2023 vs offline 2024) ===')
for col in BF:
    print(f'{col:8} inline :', dict(fmt_profile(r[col] for r in ri)))
    print(f'{col:8} offline:', dict(fmt_profile(r[col] for r in ro)))

print()
print('=== 3. offline join must leave the 41 form cols byte-identical to source form 2024 ===')
form_hdr = None
with open(FORM2024, newline='', encoding='utf-8') as f:
    form_hdr = next(csv.reader(f))
src = rows(FORM2024)
print(f'source form 2024: {len(src)} rows, {len(form_hdr)} cols')
print(f'offline joined  : {len(ro)} rows')
mismatch = 0
checked = 0
for a, b in zip(src, ro):
    checked += 1
    for col in form_hdr:
        if a.get(col, '') != b.get(col, ''):
            mismatch += 1
            if mismatch <= 5:
                print(f'  MISMATCH row {checked} col {col!r}: form={a.get(col)!r} joined={b.get(col)!r}')
print(f'form-column mismatches across {checked} rows x {len(form_hdr)} cols: {mismatch}')
