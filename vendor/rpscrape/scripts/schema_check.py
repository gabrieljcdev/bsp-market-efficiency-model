import csv
from pathlib import Path

INLINE = Path('/home/gabriel/projects/racing_project/vendor/rpscrape/data/region/gb/all/2023_01_01_2023_12_31.csv')
OFFLINE = Path('/home/gabriel/projects/racing_project/data/joined/joined_gb_2024.csv')


def header(p):
    with open(p, newline='', encoding='utf-8') as f:
        return next(csv.reader(f))


def first_data_rows(p, n=3):
    with open(p, newline='', encoding='utf-8') as f:
        r = csv.DictReader(f)
        out = []
        for i, row in enumerate(r):
            out.append(row)
            if i + 1 >= n:
                break
        return out


hi = header(INLINE)
ho = header(OFFLINE)

print(f'INLINE  ({INLINE.name}): {len(hi)} cols')
print(f'OFFLINE ({OFFLINE.name}): {len(ho)} cols')
print()

# Exact ordered comparison
if hi == ho:
    print('HEADERS: IDENTICAL (same names, same order)')
else:
    print('HEADERS: DIFFER')
    print(' positional diffs:')
    for i in range(max(len(hi), len(ho))):
        a = hi[i] if i < len(hi) else '<none>'
        b = ho[i] if i < len(ho) else '<none>'
        if a != b:
            print(f'  col {i}: inline={a!r}  offline={b!r}')
    si, so = set(hi), set(ho)
    if si - so:
        print(f' only in inline: {si - so}')
    if so - si:
        print(f' only in offline: {so - si}')

print()
print('=== spot-check shared columns (first 3 rows each) ===')
ri = first_data_rows(INLINE)
ro = first_data_rows(OFFLINE)
for col in ['date', 'off', 'horse', 'bsp', 'pre_min', 'ip_vol', 'dec', 'or', 'rpr']:
    print(f'-- {col} --')
    print('   inline :', [r.get(col) for r in ri])
    print('   offline:', [r.get(col) for r in ro])
