#!/usr/bin/env python3
"""build_history.py -- materialise the Layer-2 derived features (Phase 3).

Streams data/joined/joined_gb_2018_2026.csv through the SHARED history-join engine
(features/history_join.iter_row_features) and writes joined_gb_2018_2026_hist.csv
= every original column + the proven strictly-prior derived columns. This is the
file the rule-builder bridge reads, so a rule referencing a derived feature now
finds a REAL column (check_fields -> ok) and returns results instead of
"unsupported".

The SAME join/feature code (history_join) powers the runner view and the scanner
Tier 2 live -- one join, three surfaces. Output is gitignored (regenerable).

Each feature ships WITH its sample count `<name>_n` so thin stats stay visible.
"""
import csv
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import history_join as hj  # noqa: E402
import course_geometry as cg  # noqa: E402  -- static course-geometry reference join

SRC = hj.DEFAULT_CSV
OUT = os.path.join(hj._ROOT, "data", "joined", "joined_gb_2018_2026_hist.csv")

# (feature key in horse/trainer/combo dicts) -> (output column name). run_style is
# exposed under the manifest's name `run_style_proxy`.
DERIVED = [
    ("career_runs", "career_runs"),
    ("career_win_pct", "career_win_pct"), ("career_win_pct_n", "career_win_pct_n"),
    ("career_place_pct", "career_place_pct"), ("career_place_pct_n", "career_place_pct_n"),
    ("or_trajectory", "or_trajectory"), ("or_trajectory_n", "or_trajectory_n"),
    ("class_change", "class_change"), ("class_change_n", "class_change_n"),
    ("dslr", "dslr"), ("dslr_n", "dslr_n"),
    ("won_course_flag", "won_course_flag"), ("won_course_flag_n", "won_course_flag_n"),
    ("won_dist_flag", "won_dist_flag"), ("won_dist_flag_n", "won_dist_flag_n"),
    ("won_cd_flag", "won_cd_flag"), ("won_cd_flag_n", "won_cd_flag_n"),
    ("run_style", "run_style_proxy"), ("run_style_n", "run_style_proxy_n"),
    ("trainer_course_sr", "trainer_course_sr"), ("trainer_course_sr_n", "trainer_course_sr_n"),
    ("trainer_class_sr", "trainer_class_sr"), ("trainer_class_sr_n", "trainer_class_sr_n"),
    ("trainer_going_sr", "trainer_going_sr"), ("trainer_going_sr_n", "trainer_going_sr_n"),
    ("jockey_trainer_combo_sr", "jockey_trainer_combo_sr"),
    ("jockey_trainer_combo_sr_n", "jockey_trainer_combo_sr_n"),
]


def fmt(v):
    if v is None or v == "":
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def main():
    with open(SRC, newline="") as f:
        base_header = next(csv.reader(f))

    geo = cg.load_geometry()                 # static course -> geometry (Tier 1 + 2)
    n = 0
    with open(OUT, "w", newline="") as g:
        w = csv.writer(g)
        w.writerow(base_header + [out for _, out in DERIVED] + cg.GEOMETRY_COLS)
        for r, feats in hj.iter_row_features(SRC):
            n += 1
            base_vals = [r.get(c, "") for c in base_header]
            deriv_vals = [fmt(feats.get(key)) for key, _ in DERIVED]
            geo_vals = cg.geometry_for(r.get("course", ""), geo)
            w.writerow(base_vals + deriv_vals + geo_vals)

    print(f"wrote {OUT}")
    print(f"  rows={n}  base_cols={len(base_header)}  derived_cols={len(DERIVED)}"
          f"  geometry_cols={len(cg.GEOMETRY_COLS)}")


if __name__ == "__main__":
    main()
