#!/usr/bin/env python3
"""build_geometry_join.py -- (re)paint the static course-geometry columns onto the
already-built history CSV, IN PLACE, without re-running the expensive history join.

build_history.py adds geometry during a full rebuild; this is the fast path for
when only the geometry reference changed (e.g. after verifying Tier-2 values):
it streams the existing joined_gb_2018_2026_hist.csv, DROPS any geometry columns
already present (idempotent), and appends fresh ones keyed on `course`. Nothing
else in the file is touched -- history/derived columns and row order are preserved.

Run:  python3 features/build_geometry_join.py
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import course_geometry as cg  # noqa: E402

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_hist.csv")


def main():
    if not os.path.exists(HIST):
        sys.exit(f"history CSV not found: {HIST}\n  build it first: python3 features/build_history.py")

    geo = cg.load_geometry()
    tmp = HIST + ".tmp"
    n = matched = 0
    with open(HIST, newline="") as f, open(tmp, "w", newline="") as g:
        reader = csv.reader(f)
        header = next(reader)
        # keep every non-geometry column, then append a fresh geometry block
        keep_idx = [i for i, c in enumerate(header) if c not in cg.GEOMETRY_COLS]
        if "course" not in header:
            sys.exit("history CSV has no `course` column -- cannot join geometry.")
        course_i = header.index("course")
        w = csv.writer(g)
        w.writerow([header[i] for i in keep_idx] + cg.GEOMETRY_COLS)
        for row in reader:
            n += 1
            course = row[course_i] if course_i < len(row) else ""
            geo_vals = cg.geometry_for(course, geo)
            if any(v != "" for v in geo_vals):
                matched += 1
            w.writerow([row[i] for i in keep_idx] + geo_vals)

    os.replace(tmp, HIST)
    print(f"repainted geometry on {HIST}")
    print(f"  rows={n}  matched_geometry={matched} ({matched / n:.1%})  "
          f"geometry_cols={len(cg.GEOMETRY_COLS)}")


if __name__ == "__main__":
    main()
