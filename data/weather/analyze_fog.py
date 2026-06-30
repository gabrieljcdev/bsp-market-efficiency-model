"""Block 4 gate: quantify visibility/fog event frequency in weather_by_race.csv.

A race-level fog flag can only carry signal if fog actually OCCURS often enough
in the covered window (2022-03 -> 2026-06) to test. This script reports, per
split (train2022-23 / val2024 / holdout2025-26):
  - coverage (runner rows + distinct races with a visibility reading)
  - the visibility distribution (percentiles, in metres)
  - low-visibility RACE counts at several fog thresholds (<1000/1500/2000/5000 m)

If fog races are tiny (<~50), the probe is under-powered and that is the verdict.
"""
import csv
from collections import defaultdict

SRC = "data/weather/weather_by_race.csv"
THRESHOLDS = [500, 1000, 1500, 2000, 5000]


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def split_of(date):
    y = int(date[:4])
    if y <= 2023:
        return "train(2022-23)"
    if y == 2024:
        return "val(2024)"
    return "holdout(2025-26)"


def pctl(sorted_vals, q):
    if not sorted_vals:
        return None
    i = min(len(sorted_vals) - 1, int(q * len(sorted_vals)))
    return sorted_vals[i]


def main():
    # per race: take one visibility value (race-level)
    race_vis = {}          # rid -> (split, visibility)
    rows_total = defaultdict(int)
    rows_withvis = defaultdict(int)
    with open(SRC, newline="") as f:
        for r in csv.DictReader(f):
            date = r["date"]
            sp = split_of(date)
            rows_total[sp] += 1
            v = fnum(r.get("wx_visibility"))
            if v is not None:
                rows_withvis[sp] += 1
                rid = f"{date}|{r['course']}|{r['off']}"
                race_vis[rid] = (sp, v)

    print("=" * 64)
    print("COVERAGE (runner rows with a visibility reading, by split)")
    for sp in ["train(2022-23)", "val(2024)", "holdout(2025-26)"]:
        t, w = rows_total[sp], rows_withvis[sp]
        print(f"  {sp:18s} rows={t:7d}  with_vis={w:7d}  ({(w/t if t else 0):5.1%})")

    # distinct races by split
    races_by_split = defaultdict(list)
    for rid, (sp, v) in race_vis.items():
        races_by_split[sp].append(v)

    print("\n" + "=" * 64)
    print("VISIBILITY DISTRIBUTION (metres; per distinct race)")
    for sp in ["train(2022-23)", "val(2024)", "holdout(2025-26)"]:
        vals = sorted(races_by_split[sp])
        if not vals:
            print(f"  {sp:18s} (no races)")
            continue
        print(f"  {sp:18s} n_races={len(vals):5d}  "
              f"p01={pctl(vals,.01):.0f} p05={pctl(vals,.05):.0f} "
              f"p25={pctl(vals,.25):.0f} p50={pctl(vals,.50):.0f} "
              f"max={vals[-1]:.0f}")

    print("\n" + "=" * 64)
    print("LOW-VISIBILITY RACE COUNTS (distinct races below threshold)")
    hdr = "  " + "thresh(m)".ljust(12) + "".join(s.rjust(18) for s in
          ["train(2022-23)", "val(2024)", "holdout(2025-26)"])
    print(hdr)
    for th in THRESHOLDS:
        line = f"  <{th:<11d}"
        for sp in ["train(2022-23)", "val(2024)", "holdout(2025-26)"]:
            n = sum(1 for v in races_by_split[sp] if v < th)
            tot = len(races_by_split[sp])
            line += f"{n:>10d}/{tot:<7d}"
        print(line)

    print("\nGATE: if <1000m race counts are tiny in val/holdout, the fog flag is")
    print("under-powered as a race-level feature -> report as the verdict.")


if __name__ == "__main__":
    main()
