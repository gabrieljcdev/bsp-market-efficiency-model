#!/usr/bin/env python3
"""anchor_test_history.py -- LEAKAGE PROOF for the shared history-join engine.

Run this BEFORE trusting any Layer-2 derived feature. Two independent checks:

(1) or/rpr WITHIN-RACE ANCHOR TEST
    For each derived feature, the within-race Spearman correlation vs finishing
    position, averaged over races. Benchmarks (the project's standing anchors):
        or  ~ -0.13   (genuinely PRE-RACE -> the safe band)
        rpr ~ -0.89   (assigned POST-RACE -> the leakage signature)
    A leakage-safe feature lands near the PRE-RACE anchor (a touch stronger is
    fine for genuine past form -- place-rate-like). ANY feature near -0.89 means
    the current result leaked into its own feature -> STOP and fix the join.
    (sign: higher feature -> better -> lower pos number -> negative correlation.)

(2) DELETE-FUTURE-RUNS INVARIANCE
    A horse's features for an EARLY race must not change if its LATER runs are
    deleted from the dataset. If they do, the join is reading the future. This is
    the structural proof that complements the statistical anchor.
"""
import os
import sys
from collections import defaultdict

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import history_join as hj  # noqa: E402

FEATURES = ["career_win_pct", "career_place_pct", "or_trajectory", "dslr",
            "won_cd_flag"]


def _spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    rx = np.argsort(np.argsort(xs)).astype(float)
    ry = np.argsort(np.argsort(ys)).astype(float)
    rx -= rx.mean(); ry -= ry.mean()
    d = np.sqrt((rx * rx).sum() * (ry * ry).sum())
    return float((rx * ry).sum() / d) if d > 0 else None


def anchor_test(csv_path=hj.DEFAULT_CSV):
    # collect per-race (pos, feature-values, or) for finishers only
    by_race = defaultdict(list)
    for r, feats in hj.iter_row_features(csv_path):
        pos = hj.parse_pos(r.get("pos"))
        if pos is None:
            continue  # within-race rank needs a finishing position
        rid = f"{r['date']}|{r.get('course')}|{r.get('off')}"
        rec = {"pos": pos, "or": hj.fnum(r.get("or"))}
        for f in FEATURES:
            rec[f] = feats.get(f)
        by_race[rid].append(rec)

    cols = ["or"] + FEATURES
    sums = {c: [] for c in cols}
    for rid, recs in by_race.items():
        if len(recs) < 3:
            continue
        pos = [x["pos"] for x in recs]
        for c in cols:
            vals = [x[c] for x in recs]
            if any(v is None for v in vals):
                continue  # need full coverage within the race to rank it
            if len(set(vals)) < 2:
                continue  # constant within race -> undefined rank correlation
            s = _spearman(pos, vals)
            if s is not None:
                sums[c].append(s)

    print("=" * 70)
    print("(1) WITHIN-RACE SPEARMAN vs FINISH  (anchors: or ~ -0.13 | rpr ~ -0.89)")
    print(f"  {'feature':<20}{'mean rho':>10}{'races':>9}   verdict")
    for c in cols:
        arr = sums[c]
        if not arr:
            print(f"  {c:<20}{'n/a':>10}{0:>9}")
            continue
        m = float(np.mean(arr))
        if c == "or":
            verdict = "<- PRE-RACE anchor"
        elif abs(m) > 0.6:
            verdict = "*** NEAR rpr -- LEAK, STOP ***"
        elif abs(m) > 0.35:
            verdict = "!! stronger than expected -- inspect"
        else:
            verdict = "ok (pre-race band)"
        print(f"  {c:<20}{m:>+10.4f}{len(arr):>9}   {verdict}")
    return sums


def invariance_test(csv_path=hj.DEFAULT_CSV, n_check=300):
    """Pick horses with >=3 runs; recompute the 2nd run's features after deleting
    every run on or after the 3rd run's date. Features must be identical -- if
    they change, the join is reading the future.

    Efficient: raw rows are bucketed by horse once, so each truncated rebuild uses
    only that horse's handful of rows (no 726k re-scan per horse)."""
    rows = hj.HistoryIndex._read(csv_path)
    full = hj.HistoryIndex(rows=rows)

    raw_by_horse = defaultdict(list)        # bucket raw rows once
    for r in rows:
        raw_by_horse[r["horse"]].append(r)

    candidates = sorted(h for h, runs in full.horse.items() if len(runs) >= 3)
    candidates = candidates[:n_check]       # deterministic sample (no RNG)

    mismatches = checked = 0
    for h in candidates:
        runs = full.horse[h]                # date-ascending
        target = runs[1]                    # the horse's 2nd run
        third_ord = runs[2]["ord"]
        ctx = {"race_ord": target["ord"], "course": target["course"],
               "dist_f": target["dist_f"], "cur_or": target["or"]}
        feat_full = hj.horse_features(full.prior_horse_runs(h, target["ord"]), ctx)
        # rebuild from ONLY this horse's rows, with the 3rd run onward DELETED
        kept = [r for r in raw_by_horse[h] if hj.to_ord(r["date"]) < third_ord]
        truncated = hj.HistoryIndex(rows=kept)
        feat_tr = hj.horse_features(truncated.prior_horse_runs(h, target["ord"]), ctx)
        checked += 1
        if feat_full != feat_tr:
            mismatches += 1
            if mismatches <= 3:
                print(f"  MISMATCH horse={h!r}: full={feat_full} trunc={feat_tr}")

    print("\n" + "=" * 70)
    print("(2) DELETE-FUTURE-RUNS INVARIANCE")
    print(f"  horses checked: {checked}   mismatches: {mismatches}")
    print("  PASS -- deleting a horse's future runs does not change its past "
          "features." if mismatches == 0 else "  *** FAIL -- join reads the future ***")
    return mismatches == 0


if __name__ == "__main__":
    anchor_test()
    invariance_test()
