#!/usr/bin/env python3
"""build_handicap.py -- FLAT-HANDICAP feature set (own module, sibling of
build_rolling.py; NOT fused with it).

Reads data/joined/joined_gb_2018_2026.csv, appends handicap features, and writes
joined_gb_2018_2026_hcap.csv. Features are populated ONLY on the flat-handicap
subset (type=='Flat' AND race_name matches handicap/hcap, case-insensitive --
the 71% / ~340k-row subset confirmed in audit); all other rows get blanks and
is_flat_hcap=0.

SCOPE
-----
Handicaps are the documented soft spot: the official rating (OR) is the
handicapper's pre-race mark, published in advance, so it is CLEAN pre-race
information (confirmed in PROJECT_NOTES: top-rpr leaks, `or` does not). The
"well-in" / OR-trajectory angle -- a horse running off a lower mark than when it
last ran well -- is the angle we are probing. PRIOR HELD HONESTLY: handicap
structure is partly priced; expect modest signal at best, mostly priced.

CARDINAL LEAKAGE RULE (mirrors build_rolling.py / the rpr catch)
---------------------------------------------------------------
Every TRAJECTORY feature for a runner in a race on date D is computed ONLY from
that horse's prior flat-handicap runs on dates STRICTLY BEFORE D. We process
date-by-date and COMPUTE ALL of a date's features BEFORE updating histories with
that date's results. So the current race's outcome (pos/rpr/secs/bsp/...) can
never enter its own features, and same-day races are excluded too.

The RACE-RELATIVE features (rank/z within the race) use ONLY the current race's
OR values, every one of which is the handicapper's pre-race published mark -- no
outcome column is touched. They are leakage-safe by construction.

FEATURES (three dimensions: OFFICIAL RATING, WEIGHT, CLASS)
-----------------------------------------------------------
Runner-VARYING (a within-race conditional logit CAN identify these):
  -- OR dimension --
  h_or                : current official rating (level; pre-race mark)
  h_or_vs_lastwin     : cur_or - OR when horse last WON  (<0 = "well in")
  h_or_delta_last     : cur_or - OR at horse's last hcap run (recent mark move)
  h_or_delta_career   : cur_or - OR at horse's first hcap run (lifetime drift)
  h_or_vs_pb          : cur_or - horse's prior peak OR (<=0; distance below best)
  h_or_rank           : within-race rank of cur_or, in [0,1] (0 = top weight)
  h_or_z              : (cur_or - race_mean_or) / race_std_or
  h_hcap_runs         : log1p(prior flat-handicap starts)  (hcap experience)
  -- WEIGHT dimension (lbs; the handicapper's instrument, ~collinear with OR) --
  h_lbs               : weight carried, lbs (level; pre-race published)
  h_lbs_z             : (cur_lbs - race_mean_lbs) / race_std_lbs (top/bottomweight)
  h_lbs_delta_last    : cur_lbs - lbs at horse's last hcap run (weight move)
  -- CLASS dimension (Class 1 hardest .. 7 easiest; lower number = higher grade) --
  h_class_delta_last  : cur_class - class at last hcap run (<0 step up, >0 drop)
  h_class_drop_best   : cur_class - best (lowest-number) class horse has WON in
                        (>0 = running below its proven winning grade)

Race-CONSTANT (identical for every runner in a race -> a conditional logit
CANNOT use them; flagged explicitly in the proof so we never fool ourselves;
they stay in the FILE for Stage-2 use but are kept OUT of Stage-1):
  h_or_spread         : max_or - min_or in race (handicap compression)
  h_or_std            : std of OR across the race
  h_field_or_mean     : mean OR across the race (race-class proxy)
  h_class             : numeric class of the race (1..7)

Debut / no-prior-history cells are left blank ('') -> stage1's race-mean
imputation fills them, exactly as for missing or/draw today.
"""
import os
import re
import csv
import math
from datetime import date

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
OUT = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_hcap.csv")

HCAP_RE = re.compile(r"handicap|hcap", re.I)

VARYING = ["h_or", "h_or_vs_lastwin", "h_or_delta_last", "h_or_delta_career",
           "h_or_vs_pb", "h_or_rank", "h_or_z", "h_hcap_runs",
           "h_lbs", "h_lbs_z", "h_lbs_delta_last",
           "h_class_delta_last", "h_class_drop_best"]
CONSTANT = ["h_or_spread", "h_or_std", "h_field_or_mean", "h_class"]
NEW = ["is_flat_hcap"] + VARYING + CONSTANT


def parse_class(s):
    """'Class 4' -> 4.0 ; blank/other -> None. Lower number = higher grade."""
    m = re.search(r"(\d+)", s or "")
    return float(m.group(1)) if m else None


def to_ord(d):
    y, m, dd = d.split("-")
    return date(int(y), int(m), int(dd)).toordinal()


def parse_or(s):
    s = (s or "").strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def fmt(v):
    if v == "" or v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


def build():
    # ---- pass 1: extract the minimal columns we need ----------------------
    # row -> (date, racekey, horse, is_fh, or_val, lbs_val, class_val, pos_str)
    rows = []
    with open(SRC, newline="") as f:
        r = csv.reader(f)
        hdr = next(r)
        ci = {c: i for i, c in enumerate(hdr)}
        di, ci_co, ci_off = ci["date"], ci["course"], ci["off"]
        ni, ti, hi, oi, li, cli, pi = (ci["race_name"], ci["type"], ci["horse"],
                                       ci["or"], ci["lbs"], ci["class"], ci["pos"])
        for row in r:
            is_fh = (row[ti].strip().lower() == "flat"
                     and bool(HCAP_RE.search(row[ni] or "")))
            racekey = (row[di], row[ci_co], row[ci_off])
            rows.append((row[di], racekey, row[hi], is_fh,
                         parse_or(row[oi]) if is_fh else None,
                         parse_or(row[li]) if is_fh else None,
                         parse_class(row[cli]) if is_fh else None,
                         row[pi]))
    n = len(rows)

    feat = [None] * n  # each -> dict of feature_name -> value ('' if N/A)

    # ---- race-RELATIVE features (current-race OR/lbs only; no temporal order)
    # group flat-handicap rows by race; ranks/z/spread use only pre-race marks
    race_idx = {}
    for k in range(n):
        if rows[k][3]:
            race_idx.setdefault(rows[k][1], []).append(k)

    def mean_std(vals):
        mu = sum(vals) / len(vals)
        sd = math.sqrt(sum((v - mu) ** 2 for v in vals) / len(vals))
        return mu, sd

    for rk, idxs in race_idx.items():
        ors = [(k, rows[k][4]) for k in idxs if rows[k][4] is not None]
        lbss = {k: rows[k][5] for k in idxs if rows[k][5] is not None}
        cls = next((rows[k][6] for k in idxs if rows[k][6] is not None), None)
        if ors:
            vals = [o for _, o in ors]
            mean, std = mean_std(vals)
            spread = max(vals) - min(vals)
            lmu = lsd = None
            if lbss:
                lmu, lsd = mean_std(list(lbss.values()))
            # dense rank of OR: 0 = highest OR (top weight), 1 = lowest
            srt = sorted(vals, reverse=True)
            m = len(srt)
            for k, o in ors:
                lo = srt.index(o)
                hi = m - 1 - srt[::-1].index(o)
                rank01 = ((lo + hi) / 2.0) / (m - 1) if m > 1 else 0.5
                d = feat[k] = {c: "" for c in NEW}
                d["is_flat_hcap"] = 1
                d["h_or"] = o
                d["h_or_rank"] = rank01
                d["h_or_z"] = (o - mean) / std if std > 0 else 0.0
                d["h_or_spread"] = spread
                d["h_or_std"] = std
                d["h_field_or_mean"] = mean
                if cls is not None:
                    d["h_class"] = cls
                lv = lbss.get(k)
                if lv is not None:
                    d["h_lbs"] = lv
                    d["h_lbs_z"] = (lv - lmu) / lsd if lsd else 0.0

    # rows with no valid OR but still flat-handicap: mark flag, leave blanks
    for idxs in race_idx.values():
        for k in idxs:
            if feat[k] is None:
                feat[k] = {c: "" for c in NEW}
                feat[k]["is_flat_hcap"] = 1
    # everything else: not a flat handicap
    for k in range(n):
        if feat[k] is None:
            feat[k] = {c: "" for c in NEW}
            feat[k]["is_flat_hcap"] = 0

    # ---- TRAJECTORY features (strictly-prior flat-hcap runs) ---------------
    # chronological, compute-before-update, same-day excluded -- as build_rolling
    fh = [k for k in range(n) if rows[k][3] and rows[k][4] is not None]
    fh.sort(key=lambda k: rows[k][0])  # stable: file order within a date

    # horse -> dict of rolling prior-run state (all strictly earlier dates)
    H = {}
    i = 0
    while i < len(fh):
        cur_date = rows[fh[i]][0]
        j = i
        while j < len(fh) and rows[fh[j]][0] == cur_date:
            j += 1
        block = fh[i:j]

        # COMPUTE (history strictly earlier than cur_date)
        for k in block:
            _, _, horse, _, cur_or, cur_lbs, cur_cls, _ = rows[k]
            h = H.get(horse)
            d = feat[k]
            if h and h["n"] > 0:
                d["h_hcap_runs"] = math.log1p(h["n"])
                d["h_or_delta_last"] = cur_or - h["last_or"]
                d["h_or_delta_career"] = cur_or - h["first_or"]
                d["h_or_vs_pb"] = cur_or - h["max_or"]
                d["h_or_vs_lastwin"] = ((cur_or - h["last_win_or"])
                                        if h["last_win_or"] is not None else "")
                if cur_lbs is not None and h["last_lbs"] is not None:
                    d["h_lbs_delta_last"] = cur_lbs - h["last_lbs"]
                if cur_cls is not None and h["last_cls"] is not None:
                    d["h_class_delta_last"] = cur_cls - h["last_cls"]
                if cur_cls is not None and h["best_win_cls"] is not None:
                    d["h_class_drop_best"] = cur_cls - h["best_win_cls"]
            else:
                d["h_hcap_runs"] = 0.0  # first hcap start: experience = 0

        # UPDATE histories with this date's results (after computing)
        for k in block:
            _, _, horse, _, cur_or, cur_lbs, cur_cls, pos = rows[k]
            won = pos.strip() == "1"
            h = H.get(horse)
            if h is None:
                H[horse] = {"n": 1, "first_or": cur_or, "last_or": cur_or,
                            "max_or": cur_or,
                            "last_win_or": (cur_or if won else None),
                            "last_lbs": cur_lbs, "last_cls": cur_cls,
                            "best_win_cls": (cur_cls if won else None)}
            else:
                h["n"] += 1
                h["last_or"] = cur_or
                if cur_or > h["max_or"]:
                    h["max_or"] = cur_or
                if won:
                    h["last_win_or"] = cur_or
                if cur_lbs is not None:
                    h["last_lbs"] = cur_lbs
                if cur_cls is not None:
                    h["last_cls"] = cur_cls
                if won and cur_cls is not None and (
                        h["best_win_cls"] is None or cur_cls < h["best_win_cls"]):
                    h["best_win_cls"] = cur_cls
        i = j

    return rows, feat, n, len(race_idx), len(H)


def write_out(feat, n):
    with open(SRC, newline="") as fin, open(OUT, "w", newline="") as fout:
        r = csv.reader(fin)
        w = csv.writer(fout)
        hdr = next(r)
        w.writerow(hdr + NEW)
        for idx, row in enumerate(r):
            w.writerow(row + [fmt(feat[idx][c]) for c in NEW])


# ---- LEAKAGE PROOF --------------------------------------------------------
# Within-race Spearman of each feature vs finishing pos, on the flat-handicap
# subset, benchmarked against `or` (clean pre-race) and `rpr` (post-race leak).
# A clean pre-race feature lands in or's mild range; anything near rpr's
# magnitude is a leakage red flag. Race-constant features have ~zero within-race
# variance -> undefined/NaN within-race correlation -> a conditional logit can't
# use them, which the table makes explicit.
def within_race_spearman(rows, feat, src_extra):
    import numpy as np

    # gather per-race runner records with finishing pos and feature values
    races = {}  # racekey -> list of (pos_int, {feat: val})
    for k in range(n_global):
        if not feat[k]["is_flat_hcap"]:
            continue
        ps = rows[k][7].strip()   # pos is the last field of the row tuple
        if not ps.isdigit():
            continue
        rec = {c: feat[k][c] for c in VARYING + CONSTANT}
        rec["or"] = src_extra[k][0]
        rec["rpr"] = src_extra[k][1]
        races.setdefault(rows[k][1], []).append((int(ps), rec))

    cols = VARYING + CONSTANT + ["or", "rpr"]
    # pooled within-race Spearman = Pearson of within-race ranks, pooled
    pooled = {c: ([], []) for c in cols}      # (feature_ranks, pos_ranks)
    const_races = {c: 0 for c in cols}        # races where feature has no spread
    used_races = {c: 0 for c in cols}

    def rankdata(a):
        order = np.argsort(a, kind="mergesort")
        ranks = np.empty(len(a), float)
        ranks[order] = np.arange(len(a), dtype=float)
        # average ties
        a_sorted = a[order]
        i = 0
        while i < len(a):
            j = i
            while j + 1 < len(a) and a_sorted[j + 1] == a_sorted[i]:
                j += 1
            if j > i:
                ranks[order[i:j + 1]] = (i + j) / 2.0
            i = j + 1
        return ranks

    for rk, recs in races.items():
        if len(recs) < 3:
            continue
        pos_arr = np.array([p for p, _ in recs], float)
        pos_rank = rankdata(pos_arr)
        for c in cols:
            vals = [r.get(c) for _, r in recs]
            mask = [v != "" and v is not None for v in vals]
            if sum(mask) < 3:
                continue
            fv = np.array([float(vals[t]) for t in range(len(vals)) if mask[t]])
            pr = np.array([pos_rank[t] for t in range(len(vals)) if mask[t]])
            if fv.max() == fv.min():     # no within-race variance (race-constant)
                const_races[c] += 1
                continue
            used_races[c] += 1
            fr = rankdata(fv)
            pooled[c][0].extend((fr - fr.mean()).tolist())
            pooled[c][1].extend((pr - pr.mean()).tolist())

    out = {}
    for c in cols:
        xs = np.array(pooled[c][0])
        ys = np.array(pooled[c][1])
        if len(xs) > 1 and xs.std() > 0 and ys.std() > 0:
            rho = float(np.corrcoef(xs, ys)[0, 1])
        else:
            rho = float("nan")
        out[c] = (rho, used_races[c], const_races[c])
    return out


n_global = 0


def main():
    global n_global
    rows, feat, n, n_races, n_horses = build()
    n_global = n
    write_out(feat, n)

    # pull or/rpr straight from source for the benchmark columns
    src_extra = [None] * n
    with open(SRC, newline="") as f:
        r = csv.reader(f)
        hdr = next(r)
        ci = {c: i for i, c in enumerate(hdr)}
        oi, ri = ci["or"], ci["rpr"]
        for idx, row in enumerate(r):
            ov, rv = parse_or(row[oi]), parse_or(row[ri])
            src_extra[idx] = ("" if ov is None else ov,
                              "" if rv is None else rv)

    n_fh = sum(1 for d in feat if d["is_flat_hcap"])
    print(f"rows={n}  wrote {OUT}")
    print(f"flat-handicap rows: {n_fh} ({100*n_fh/n:.1f}% of all)")
    print(f"distinct flat-hcap races={n_races}  horses with hcap history={n_horses}")
    print()
    print("feature non-empty fill rate (over flat-handicap subset):")
    for c in VARYING + CONSTANT:
        filled = sum(1 for d in feat if d["is_flat_hcap"] and d[c] != "")
        tag = "varying " if c in VARYING else "CONSTANT"
        print(f"  [{tag}] {c:18s} {100*filled/n_fh:5.1f}%")
    print()
    print("=" * 72)
    print("LEAKAGE PROOF -- within-race Spearman(feature, finishing pos)")
    print("  benchmark:  or  = clean pre-race mark   |   rpr = post-race leak")
    print("  red flag:   |rho| anywhere near rpr's magnitude")
    print("=" * 72)
    res = within_race_spearman(rows, feat, src_extra)
    order = ["or", "rpr"] + VARYING + CONSTANT
    print(f"  {'feature':18s} {'rho':>8s}  {'races_used':>10s}  {'races_const':>11s}")
    for c in order:
        rho, used, const = res[c]
        rs = "   nan " if rho != rho else f"{rho:+.3f}"
        flag = ""
        if c in CONSTANT:
            flag = "  <- race-CONSTANT (cond.logit cannot use)"
        elif c in ("or", "rpr"):
            flag = "  <- benchmark"
        print(f"  {c:18s} {rs:>8s}  {used:>10d}  {const:>11d}{flag}")
    print("=" * 72)


if __name__ == "__main__":
    main()
