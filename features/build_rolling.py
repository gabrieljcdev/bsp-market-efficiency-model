#!/usr/bin/env python3
"""build_rolling.py -- first batch of LEAKAGE-SAFE rolling form features.

Reads data/joined/joined_gb_2018_2026.csv, appends 6 runner-varying, strictly
pre-race features, and writes joined_gb_2018_2026_feat.csv.

CARDINAL LEAKAGE RULE (mirrors the rpr catch in PROJECT_NOTES)
-------------------------------------------------------------
Every feature for a runner in a race on date D is computed ONLY from that
horse's / jockey's / trainer's runs on dates STRICTLY BEFORE D. We process the
data date-by-date and COMPUTE ALL of a date's features BEFORE updating the
histories with that date's results. So:
  * the current race's outcome (pos) can never enter its own features;
  * same-day races are excluded too (no intra-day off-time ambiguity);
  * no post-race column (pos/rpr/bsp/secs/...) of the current row is used --
    features derive purely from PRIOR rows.
This batch deliberately AVOIDS rpr entirely (even past rpr) to stay in clearly
Tier-2/3, mostly-priced territory and keep the leakage question unambiguous.

FEATURES (all leakage-safe, runner-varying, so identified by the conditional logit)
  f_career_runs : log1p(prior GB runs in-set)        -- experience
  f_days_since  : days since this horse's last run    -- recency/freshness
  f_win_rate    : prior wins / prior runs             -- horse class/form
  f_place_rate  : prior places (pos<=3) / prior runs  -- horse consistency
  f_jky_sr      : jockey prior win strike rate        -- connections
  f_trn_sr      : trainer prior win strike rate       -- connections
Debut / no-history cells are left blank ('') -> stage1's race-mean imputation
fills them, exactly as for missing or/draw today.
"""
import os
import csv
import math
from collections import defaultdict
from datetime import date

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
OUT = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_feat.csv")
NEW = ["f_career_runs", "f_days_since", "f_win_rate", "f_place_rate",
       "f_jky_sr", "f_trn_sr"]


def to_ord(d):
    y, m, dd = d.split("-")
    return date(int(y), int(m), int(dd)).toordinal()


def fmt(v):
    if v == "" or v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def main():
    # ---- pass 1: lightweight extract (idx, date, horse, jockey, trainer, pos)
    meta = []
    with open(SRC, newline="") as f:
        r = csv.reader(f)
        hdr = next(r)
        ci = {c: i for i, c in enumerate(hdr)}
        di, hi, ji, ti, pi = (ci["date"], ci["horse"], ci["jockey"],
                              ci["trainer"], ci["pos"])
        for row in r:
            meta.append((row[di], row[hi], row[ji], row[ti], row[pi]))
    n = len(meta)

    # chronological order; stable sort keeps file order within a date
    order = sorted(range(n), key=lambda k: meta[k][0])

    H = {}   # horse   -> [runs, wins, places, last_ord]
    J = {}   # jockey  -> [rides, wins]
    T = {}   # trainer -> [runs, wins]
    feat = [None] * n

    i = 0
    while i < n:
        cur_date = meta[order[i]][0]
        j = i
        while j < n and meta[order[j]][0] == cur_date:
            j += 1
        block = order[i:j]
        cur_ord = to_ord(cur_date)

        # COMPUTE (uses only history from strictly-earlier dates)
        for k in block:
            _, horse, jky, trn, pos = meta[k]
            h = H.get(horse)
            if h and h[0] > 0:
                runs = h[0]
                f_runs = math.log1p(runs)
                f_win = h[1] / runs
                f_place = h[2] / runs
                f_days = (cur_ord - h[3]) if h[3] is not None else ""
            else:
                f_runs, f_win, f_place, f_days = 0.0, "", "", ""
            jj = J.get(jky)
            f_jsr = (jj[1] / jj[0]) if (jj and jj[0] > 0) else ""
            tt = T.get(trn)
            f_tsr = (tt[1] / tt[0]) if (tt and tt[0] > 0) else ""
            feat[k] = (f_runs, f_days, f_win, f_place, f_jsr, f_tsr)

        # UPDATE histories with this date's results (after computing)
        for k in block:
            _, horse, jky, trn, pos = meta[k]
            ps = pos.strip()
            win = 1 if ps == "1" else 0
            place = 1 if (ps.isdigit() and int(ps) <= 3) else 0
            h = H.setdefault(horse, [0, 0, 0, None])
            h[0] += 1; h[1] += win; h[2] += place; h[3] = cur_ord
            jj = J.setdefault(jky, [0, 0]); jj[0] += 1; jj[1] += win
            tt = T.setdefault(trn, [0, 0]); tt[0] += 1; tt[1] += win
        i = j

    # ---- pass 2: stream original again, append features in original row order
    with open(SRC, newline="") as fin, open(OUT, "w", newline="") as fout:
        r = csv.reader(fin); w = csv.writer(fout)
        hdr = next(r)
        w.writerow(hdr + NEW)
        for idx, row in enumerate(r):
            w.writerow(row + [fmt(v) for v in feat[idx]])

    # ---- leakage self-check + coverage report
    debut = sum(1 for f in feat if f[0] == 0.0)            # 0 prior runs
    filled = {c: 0 for c in NEW}
    for f in feat:
        for c, v in zip(NEW, f):
            if v != "":
                filled[c] += 1
    print(f"rows={n}  wrote {OUT}")
    print(f"distinct horses={len(H)} jockeys={len(J)} trainers={len(T)}")
    print(f"debut rows (0 prior runs, f_career_runs=0): {debut} ({100*debut/n:.1f}%)")
    print("feature non-empty fill rates:")
    for c in NEW:
        print(f"  {c:14s} {100*filled[c]/n:5.1f}%")
    print("LEAKAGE-SAFE: features computed date-grouped, strictly before each "
          "race date; no current/same-day outcome used.")


if __name__ == "__main__":
    main()
