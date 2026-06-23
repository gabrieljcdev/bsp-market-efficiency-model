#!/usr/bin/env python3
"""build_speedfig.py -- race-relative SPEED FIGURES from finish times (FLAT only).
Own module, sibling of build_rolling.py / build_handicap.py; NOT fused with them.

A speed figure is a DIFFERENT information source from the handicapper's ratings:
it comes from the CLOCK (race time), not from `or`/`rpr`. That orthogonality is
the whole reason to try it -- the remaining best free shot at market-orthogonal
signal (PROJECT_NOTES, 2026-06-22).

WHAT THIS BUILDS
----------------
`secs` is a per-runner finish time, 99.7% populated on flat, lengths-derived
(winner clock + beaten-lengths). We express each run as a deviation from a PAR
time for its conditions, producing a self-standardised figure:

    speedfig_raw = (par_adj - secs) / par_adj          (faster => higher)

where par_adj is the par time for the run's (course, distance, surface) cell,
shifted by a coarse GOING-band correction (soft/heavy ground is slower).

HONEST LIMIT (do not overclaim): `secs` is lengths-derived and the figure is
self-standardised -- there is NO authoritative par/going/weight-for-age scale
behind it. Good for RANKING runs within comparable conditions; weaker as an
absolute cross-race figure. Fine as a proxy.

  *** ANTI-LEAKAGE NOTE FOR THE BUILD ITSELF (Stage 1) ***
  speedfig_raw is a POST-RACE figure: it DESCRIBES a completed run. It is NOT a
  predictive feature -- the Stage-2 features (built later) window it over a
  horse's PRIOR runs only.
  Par is a property of (course, distance, surface, going) across MANY races, so
  a horse's OWN race outcome never defines its baseline. We do NOT z-score the
  figure WITHIN its own race (that would rank by finishing order = an rpr-style
  leak in disguise). Because `secs` is itself lengths-derived, speedfig_raw is
  necessarily monotonic with finishing position WITHIN a race -- but the LEVEL
  differs across races (a fast race lifts every runner's figure vs par). That
  cross-race level is the absolute-vs-par information; it is NOT a within-race
  ranking. Confirmed explicitly in the report.

STAGE 1 (this file): build the figure + report construction. STOP before
windowing. Stage 2 (predictive sf_* + going-interaction features) is added only
after review.
"""
import os
import csv
import math
from collections import defaultdict
from statistics import median

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
OUT = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_sf.csv")

MIN_CELL = 30        # >=30 timed runs => usable cell par (per the audit: 311 cells)
MIN_BAND = 5         # min runs in (cell, going-band) to contribute a going shift
TRAIN_MAX_YEAR = 2023  # par + going shift estimated on TRAIN ONLY (<=2023), then
#                        frozen and applied to all years. This keeps the 2024 val
#                        and 2025-26 holdout figures normalised against a baseline
#                        that NEVER saw those years (no in-sample contamination).

# Stage-1 columns appended to every row (blank on non-flat / invalid-secs rows)
NEW = ["sf_is_flat", "sf_cell", "sf_cell_level", "sf_low_conf",
       "sf_going_band", "sf_par_base", "sf_par_adj", "speedfig_raw"]

# Stage-2 windowed predictive columns (all strictly prior-date; null on
# debut / insufficient history). speedfig_raw of the CURRENT run never enters
# its OWN features -- we compute date-grouped and update histories only AFTER.
TREND_WIN = 5        # trailing prior figures used to fit the improving/declining slope
SF_BASE = ["sf_last", "sf_best3", "sf_avg3", "sf_trend", "sf_vs_classpar"]
SF_GOING = ["sf_on_todays_going", "sf_going_delta", "going_switch_flag"]
NEW2 = SF_BASE + SF_GOING


# --------------------------------------------------------------------------- #
# Going-band mapping: COARSE, surface-aware. Turf and AW use different scales. #
# --------------------------------------------------------------------------- #
def going_band(going, surface):
    g = (going or "").strip().lower()
    s = (surface or "").strip().lower()
    if s == "aw":
        if "fast" in g:
            return "aw_std_fast"
        if "slow" in g:
            return "aw_std_slow"
        if "standard" in g:
            return "aw_standard"
        return "aw_other"
    # turf
    if g == "heavy":
        return "heavy"
    if g == "soft":
        return "soft"
    if g == "good to soft":
        return "good_soft"
    if g == "good":
        return "good"
    if g in ("good to firm", "firm"):
        return "firm"
    return "turf_other"


def parse_dist_f(s):
    s = (s or "").strip().lower().rstrip("f")
    try:
        return float(s)
    except ValueError:
        return None


def parse_class(s):
    """'Class 4' -> 4 ; blank/other -> None. Lower number = higher grade.
    Class is the race's PUBLISHED grade (pre-race), so leakage-safe to use."""
    import re
    m = re.search(r"(\d+)", s or "")
    return int(m.group(1)) if m else None


def fmt(v):
    if v == "" or v is None:
        return ""
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


# --------------------------------------------------------------------------- #
# Load flat, valid-secs runs                                                   #
# --------------------------------------------------------------------------- #
def load():
    """Return (n_total, runs) where runs is a list of dicts for flat valid-secs
    rows, each carrying its original row index `i`."""
    runs = []
    n_total = 0
    with open(SRC, newline="") as f:
        r = csv.DictReader(f)
        for i, row in enumerate(r):
            n_total += 1
            if row["type"].strip().lower() != "flat":
                continue
            s = (row["secs"] or "").strip()
            try:
                secs = float(s)
            except ValueError:
                continue
            if secs <= 0:
                continue
            df = parse_dist_f(row["dist_f"])
            surf = (row["surface"] or "").strip()
            if df is None or not surf:
                continue
            runs.append({
                "i": i,
                "date": row["date"],
                "year": int(row["date"][:4]),
                "rid": (row["date"], row["course"], row["off"]),
                "course": row["course"],
                "dist_f": row["dist_f"].strip(),
                "df": df,
                "surface": surf,
                "band": going_band(row["going"], surf),
                "cls": parse_class(row["class"]),
                "secs": secs,
                "pos": (row["pos"] or "").strip(),
                "horse": row["horse"],
            })
    return n_total, runs


# --------------------------------------------------------------------------- #
# Par times: tiered cells. level0 (course,dist_f,surface); fall back to        #
# level1 (dist_f,surface); else level2 (surface) marked low-confidence.        #
# Par = MEDIAN secs (robust central measure, NOT raw mean).                    #
# --------------------------------------------------------------------------- #
def build_pars(runs):
    by0 = defaultdict(list)   # (course,dist_f,surface) -> [secs]
    by1 = defaultdict(list)   # (dist_f,surface)        -> [secs]
    by2 = defaultdict(list)   # (surface,)              -> [secs]
    for r in runs:
        if r["year"] > TRAIN_MAX_YEAR:        # TRAIN-ONLY par estimation
            continue
        by0[(r["course"], r["dist_f"], r["surface"])].append(r["secs"])
        by1[(r["dist_f"], r["surface"])].append(r["secs"])
        by2[(r["surface"],)].append(r["secs"])
    par0 = {k: median(v) for k, v in by0.items() if len(v) >= MIN_CELL}
    par1 = {k: median(v) for k, v in by1.items() if len(v) >= MIN_CELL}
    par2 = {k: median(v) for k, v in by2.items()}
    return by0, par0, par1, par2


def resolve_par(r, par0, par1, par2):
    """Return (par_base, level, low_conf) for a run via tiered fallback."""
    k0 = (r["course"], r["dist_f"], r["surface"])
    if k0 in par0:
        return par0[k0], "course_dist_surf", 0
    k1 = (r["dist_f"], r["surface"])
    if k1 in par1:
        return par1[k1], "dist_surf", 1
    return par2[(r["surface"],)], "surface", 1


# --------------------------------------------------------------------------- #
# Going correction: per-cell-then-pool, so the going effect is not confounded  #
# with which courses are run more often on which ground.                       #
#   rdev = (secs - par_base) / par_base   (relative slowness vs cell par)      #
#   shift[band] = median over level0 cells of (median rdev within cell+band)   #
# par_adj = par_base * (1 + shift[band]); heavy band => shift > 0 (slower).     #
# --------------------------------------------------------------------------- #
def build_going_shift(runs, par0, par1, par2):
    # relative deviation of each run from its cell base par
    for r in runs:
        pb, lvl, lc = resolve_par(r, par0, par1, par2)
        r["par_base"] = pb
        r["level"] = lvl
        r["low_conf"] = lc
        r["rdev"] = (r["secs"] - pb) / pb

    # per-cell, per-band median rdev (only well-populated level0 cells, TRAIN only)
    cell_band = defaultdict(lambda: defaultdict(list))  # cell -> band -> [rdev]
    for r in runs:
        if r["year"] > TRAIN_MAX_YEAR:        # TRAIN-ONLY going-shift estimation
            continue
        if r["level"] == "course_dist_surf":
            cell = (r["course"], r["dist_f"], r["surface"])
            cell_band[cell][r["band"]].append(r["rdev"])

    band_cellmeds = defaultdict(list)   # band -> [per-cell median rdev]
    band_ncells = defaultdict(int)
    for cell, bands in cell_band.items():
        for band, devs in bands.items():
            if len(devs) >= MIN_BAND:
                band_cellmeds[band].append(median(devs))
                band_ncells[band] += 1

    shift = {b: median(v) for b, v in band_cellmeds.items()}
    return shift, band_ncells


# --------------------------------------------------------------------------- #
# Class par: mean (clipped) speedfig_raw per race class, TRAIN ONLY. Because    #
# par is the per-cell median across ALL classes, better-class horses beat par   #
# by more -> class_par[1] > class_par[7]. sf_vs_classpar expresses a horse's     #
# prior speed RELATIVE to what today's class typically runs.                     #
# --------------------------------------------------------------------------- #
def build_class_par(runs, clip_floor):
    by_cls = defaultdict(list)
    for r in runs:
        if r["year"] > TRAIN_MAX_YEAR or r["cls"] is None:
            continue
        by_cls[r["cls"]].append(max(r["speedfig_raw"], clip_floor))
    return {c: sum(v) / len(v) for c, v in by_cls.items()}


def _slope(ys):
    """OLS slope of ys vs index 0..m-1 (m>=2). >0 = improving (faster over time)."""
    m = len(ys)
    xs = list(range(m))
    mx = (m - 1) / 2.0
    my = sum(ys) / m
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(m))
    den = sum((xs[i] - mx) ** 2 for i in range(m))
    return num / den if den else 0.0


# --------------------------------------------------------------------------- #
# Windowed predictive features. Date-grouped, compute-before-update, same-day   #
# excluded -- mirrors build_rolling.py / build_handicap.py exactly. Every value  #
# for a run on date D derives ONLY from that horse's flat figures on dates       #
# STRICTLY BEFORE D. Each prior figure is CLIPPED at clip_floor before use.       #
# --------------------------------------------------------------------------- #
def build_features(runs, clip_floor, class_par):
    feat = {}                       # run-index i -> {col: val or ''}
    order = sorted(range(len(runs)), key=lambda k: runs[k]["date"])  # stable in-date
    H = {}                          # horse -> rolling prior state

    i = 0
    while i < len(order):
        cur_date = runs[order[i]]["date"]
        j = i
        while j < len(order) and runs[order[j]]["date"] == cur_date:
            j += 1
        block = order[i:j]

        # COMPUTE (history strictly earlier than cur_date)
        for k in block:
            r = runs[k]
            d = {c: "" for c in NEW2}
            h = H.get(r["horse"])
            if h and h["figs"]:
                figs = h["figs"]                     # all prior, clipped, chrono
                last3 = figs[-3:]
                d["sf_last"] = figs[-1]
                d["sf_best3"] = max(last3)
                d["sf_avg3"] = sum(last3) / len(last3)
                if len(figs) >= 2:
                    d["sf_trend"] = _slope(figs[-TREND_WIN:])
                # vs class par for TODAY's class (published, pre-race)
                if r["cls"] in class_par:
                    d["sf_vs_classpar"] = d["sf_avg3"] - class_par[r["cls"]]
                # going x horse interaction
                overall = sum(figs) / len(figs)
                bf = h["band_figs"].get(r["band"])
                if bf:
                    on_going = sum(bf) / len(bf)
                    d["sf_on_todays_going"] = on_going
                    d["sf_going_delta"] = on_going - overall
                # last band exists (figs nonempty) -> switch flag well-defined
                d["going_switch_flag"] = 0 if r["band"] == h["last_band"] else 1
            feat[k] = d

        # UPDATE histories with this date's figures (AFTER computing)
        for k in block:
            r = runs[k]
            cf = max(r["speedfig_raw"], clip_floor)   # clip before storing as prior
            h = H.get(r["horse"])
            if h is None:
                H[r["horse"]] = {"figs": [cf], "last_band": r["band"],
                                 "band_figs": {r["band"]: [cf]}}
            else:
                h["figs"].append(cf)
                h["last_band"] = r["band"]
                h["band_figs"].setdefault(r["band"], []).append(cf)
        i = j

    return feat


# --------------------------------------------------------------------------- #
def build():
    n_total, runs = load()
    by0, par0, par1, par2 = build_pars(runs)
    shift, band_ncells = build_going_shift(runs, par0, par1, par2)

    # final figure per run
    for r in runs:
        sh = shift.get(r["band"], 0.0)
        par_adj = r["par_base"] * (1.0 + sh)
        r["par_adj"] = par_adj
        r["speedfig_raw"] = (par_adj - r["secs"]) / par_adj
        r["shift"] = sh

    # CLIP FLOOR for Stage-2 features (sf_last et al.): a tail-off / pulled-up run
    # must not carry a ~-1.4 figure into its NEXT-run feature. Floor = 1st pct of
    # speedfig_raw over TRAIN ONLY (threshold itself leakage-free). The descriptive
    # speedfig_raw column is left UNCLIPPED (it honestly describes the run); the
    # clip is applied only when a prior figure feeds a feature (Stage 2).
    train_sf = sorted(r["speedfig_raw"] for r in runs if r["year"] <= TRAIN_MAX_YEAR)
    clip_floor = quantiles(train_sf, [0.01])[0]

    # Stage-2 windowed features (strictly prior-date, clip applied)
    class_par = build_class_par(runs, clip_floor)
    feat = build_features(runs, clip_floor, class_par)

    return (n_total, runs, by0, par0, par1, par2, shift, band_ncells,
            clip_floor, class_par, feat)


def write_out(n_total, runs, feat):
    by_i = {r["i"]: k for k, r in enumerate(runs)}  # row index -> runs position
    with open(SRC, newline="") as fin, open(OUT, "w", newline="") as fout:
        rd = csv.reader(fin)
        w = csv.writer(fout)
        hdr = next(rd)
        w.writerow(hdr + NEW + NEW2)
        for idx, row in enumerate(rd):
            k = by_i.get(idx)
            if k is None:
                w.writerow(row + [""] * (len(NEW) + len(NEW2)))
            else:
                r = runs[k]
                cell = f'{r["course"]}|{r["dist_f"]}|{r["surface"]}'
                d = feat[k]
                w.writerow(row + [
                    1, cell, r["level"], r["low_conf"], r["band"],
                    fmt(r["par_base"]), fmt(r["par_adj"]),
                    fmt(r["speedfig_raw"]),
                ] + [fmt(d[c]) for c in NEW2])


# --------------------------------------------------------------------------- #
# Report                                                                        #
# --------------------------------------------------------------------------- #
def quantiles(vals, qs):
    s = sorted(vals)
    n = len(s)
    out = []
    for q in qs:
        if n == 1:
            out.append(s[0]); continue
        pos = q * (n - 1)
        lo = int(math.floor(pos)); hi = int(math.ceil(pos))
        out.append(s[lo] if lo == hi else s[lo] + (s[hi] - s[lo]) * (pos - lo))
    return out


def report(n_total, runs, by0, par0, par1, par2, shift, band_ncells, clip_floor):
    n = len(runs)
    n_tr = sum(1 for r in runs if r["year"] <= TRAIN_MAX_YEAR)
    print(f"rows total={n_total}  flat valid-secs runs={n} ({100*n/n_total:.1f}%)")
    print(f"wrote {OUT}")
    print(f"par + going shift estimated on TRAIN ONLY (year<={TRAIN_MAX_YEAR}): "
          f"{n_tr} train runs ({100*n_tr/n:.1f}% of figured runs)")

    # ---- cell coverage ----------------------------------------------------- #
    all0 = defaultdict(int)
    for r in runs:
        all0[(r["course"], r["dist_f"], r["surface"])] += 1
    usable = sum(1 for k, v in all0.items() if v >= MIN_CELL)
    sparse = len(all0) - usable
    runs_in_usable = sum(v for k, v in all0.items() if v >= MIN_CELL)
    print()
    print("CELL COVERAGE -- par = MEDIAN secs per (course, dist_f, surface)")
    print(f"  distinct level0 cells        : {len(all0)}")
    print(f"  usable (>={MIN_CELL} runs)          : {usable}  "
          f"({100*runs_in_usable/n:.1f}% of runs)")
    print(f"  sparse (<{MIN_CELL} runs)           : {sparse}  "
          f"(pooled to dist_surf / surface, low_conf=1)")
    lvl_count = defaultdict(int)
    for r in runs:
        lvl_count[r["level"]] += 1
    print("  par resolution level used:")
    for lvl in ("course_dist_surf", "dist_surf", "surface"):
        c = lvl_count.get(lvl, 0)
        print(f"    {lvl:18s} {c:>8d}  ({100*c/n:.2f}%)")

    # ---- going-band shifts (the sanity check) ------------------------------ #
    print()
    print("GOING-BAND CORRECTION -- per-cell-then-pooled relative time shift")
    print("  shift>0 => slower ground (par lengthened).  RAW = pooled mean rdev")
    print("  of all runs in band (pre-correction sanity); SHIFT = applied value.")
    raw_band = defaultdict(list)
    for r in runs:
        raw_band[r["band"]].append(r["rdev"])
    med_df = median([r["df"] for r in runs])
    # approximate seconds-at-median-distance using a representative par
    rep_par = median([r["par_base"] for r in runs])
    print(f"  (seconds column = shift * representative par {rep_par:.1f}s)")
    print(f"  {'band':14s}{'n_runs':>9}{'raw mean rdev':>15}"
          f"{'SHIFT(med)':>12}{'~secs':>8}{'cells':>7}")
    order = ["firm", "good", "good_soft", "soft", "heavy", "turf_other",
             "aw_std_fast", "aw_standard", "aw_std_slow", "aw_other"]
    for b in order:
        if b not in raw_band:
            continue
        vals = raw_band[b]
        sh = shift.get(b, 0.0)
        print(f"  {b:14s}{len(vals):>9d}{sum(vals)/len(vals):>15.4%}"
              f"{sh:>12.4%}{sh*rep_par:>8.2f}{band_ncells.get(b,0):>7d}")
    # turf ground-softness ordering sanity
    t_order = [b for b in ("firm", "good", "good_soft", "soft", "heavy")
               if b in shift]
    shifts_seq = [shift[b] for b in t_order]
    mono = all(shifts_seq[i] <= shifts_seq[i + 1] + 1e-9
               for i in range(len(shifts_seq) - 1))
    print(f"  SANITY: turf firm->heavy shift sequence "
          f"{[f'{shift[b]:+.3%}' for b in t_order]}")
    print(f"          monotonic slower as ground softens? {mono}  "
          f"(heavy markedly > good: "
          f"{shift.get('heavy',0)-shift.get('good',0):+.3%})")

    # ---- speedfig_raw distribution ---------------------------------------- #
    sf = [r["speedfig_raw"] for r in runs]
    qs = quantiles(sf, [0.01, 0.05, 0.25, 0.5, 0.75, 0.95, 0.99])
    mu = sum(sf) / len(sf)
    sd = (sum((x - mu) ** 2 for x in sf) / len(sf)) ** 0.5
    print()
    print("speedfig_raw DISTRIBUTION (faster run => higher; 0 = exactly at par)")
    print(f"  mean={mu:+.4f}  sd={sd:.4f}  min={min(sf):+.4f}  max={max(sf):+.4f}")
    print(f"  p01={qs[0]:+.4f} p05={qs[1]:+.4f} p25={qs[2]:+.4f} "
          f"p50={qs[3]:+.4f} p75={qs[4]:+.4f} p95={qs[5]:+.4f} p99={qs[6]:+.4f}")

    # ---- par table for a handful of cells ---------------------------------- #
    print()
    print("PAR-TIME TABLE -- sample usable cells (median secs, n runs)")
    sample = sorted(((k, len(v)) for k, v in by0.items() if len(v) >= MIN_CELL),
                    key=lambda x: -x[1])[:8]
    print(f"  {'course':28s}{'dist':>6}{'surf':>6}{'n':>7}{'par(med s)':>12}")
    for (course, df, surf), cnt in sample:
        print(f"  {course[:27]:28s}{df:>6}{surf:>6}{cnt:>7d}{par0[(course,df,surf)]:>12.2f}")

    # ---- worked example: a known-fast run scores high ---------------------- #
    print()
    print("WORKED EXAMPLE -- top-5 speedfig_raw runs (should be exceptional clockings)")
    top = sorted(runs, key=lambda r: -r["speedfig_raw"])[:5]
    print(f"  {'horse':22s}{'cell':>30}{'band':>12}{'secs':>8}"
          f"{'par_adj':>9}{'sf_raw':>9}")
    for r in top:
        cell = f'{r["course"][:12]}|{r["dist_f"]}|{r["surface"]}'
        print(f"  {r['horse'][:21]:22s}{cell:>30}{r['band']:>12}"
              f"{r['secs']:>8.1f}{r['par_adj']:>9.1f}{r['speedfig_raw']:>9.4f}")

    # ---- CONFIRM: absolute-vs-par, NOT within-race z-score ----------------- #
    # Pick a cell with both a fast and a slow race; show winners' figures differ
    # across races (the absolute level), while within a race figures track pos.
    print()
    print("ANTI-LEAKAGE CONFIRMATION -- speedfig_raw is ABSOLUTE vs par, not a")
    print("within-race rank. Two races, SAME cell: the faster race lifts EVERY")
    print("runner's figure (incl. the winner). A within-race z-score could not")
    print("show this -- every race's winner would score identically.")
    # find busiest usable cell, take its two races with most-different winner secs
    cell_runs = defaultdict(list)
    for r in runs:
        if r["level"] == "course_dist_surf":
            cell_runs[(r["course"], r["dist_f"], r["surface"])].append(r)
    best_cell = max(cell_runs, key=lambda k: len(cell_runs[k]))
    races = defaultdict(list)
    for r in cell_runs[best_cell]:
        races[r["rid"]].append(r)
    winners = []
    for rid, recs in races.items():
        w = [x for x in recs if x["pos"] == "1"]
        if w:
            winners.append((rid, w[0]))
    winners.sort(key=lambda x: x[1]["secs"])
    if len(winners) >= 2:
        fast_rid, fast_w = winners[0]
        slow_rid, slow_w = winners[-1]
        print(f"  cell = {best_cell[0]} | {best_cell[1]} | {best_cell[2]}  "
              f"(par_base={par0[best_cell]:.2f}s)")
        for tag, rid, w in (("FAST race", fast_rid, fast_w),
                            ("SLOW race", slow_rid, slow_w)):
            print(f"   {tag} {rid[0]} {rid[2]}: winner secs={w['secs']:.2f} "
                  f"sf_raw={w['speedfig_raw']:+.4f}")
        print(f"   => same cell, winner figures differ by "
              f"{fast_w['speedfig_raw']-slow_w['speedfig_raw']:+.4f}: the figure "
              f"carries cross-race PACE, not just finishing order.")

    # ---- Stage-2 clip floor (computed now, applied in Stage 2) ------------- #
    n_clip = sum(1 for r in runs if r["speedfig_raw"] < clip_floor)
    print()
    print("STAGE-2 CLIP FLOOR (for sf_last et al.; descriptive column left unclipped)")
    print(f"  floor = train p01 of speedfig_raw = {clip_floor:+.4f}")
    print(f"  runs below floor (would be clipped as a prior figure): {n_clip} "
          f"({100*n_clip/n:.3f}%) -- tail-off / pulled-up far back")

    print()
    print("STAGE 1 (construction) COMPLETE.")


# =========================================================================== #
# STAGE 2 -- LEAKAGE PROOF                                                      #
# Within-race Spearman(feature, finishing pos) on the flat figured subset,      #
# anchored by `or` (clean pre-race, ~-0.12) and `rpr` (post-race leak, ~-0.89). #
# A clean windowed speed feature should land pre-race-like: a touch stronger    #
# than `or` is fine (genuine past speed predicts current finish a little);      #
# anything approaching rpr (|rho|>=~0.3) is the CURRENT figure leaking in.       #
# =========================================================================== #
def _rankdata(a):
    import numpy as np
    order = np.argsort(a, kind="mergesort")
    ranks = np.empty(len(a), float)
    ranks[order] = np.arange(len(a), dtype=float)
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


def within_race_spearman(records, cols):
    """records: list of (racekey, pos_int, {col: val_or_''}). Returns
    {col: (pooled_rho, used_races, const_races, n_runners)} -- pooled within-race
    Spearman = Pearson of within-race centred ranks across all races."""
    import numpy as np
    races = defaultdict(list)
    for rk, pos, rec in records:
        races[rk].append((pos, rec))

    pooled = {c: ([], []) for c in cols}
    used = {c: 0 for c in cols}
    const = {c: 0 for c in cols}
    nrun = {c: 0 for c in cols}

    for rk, recs in races.items():
        if len(recs) < 3:
            continue
        pos_rank = _rankdata(np.array([p for p, _ in recs], float))
        for c in cols:
            vals = [r.get(c, "") for _, r in recs]
            mask = [v != "" and v is not None for v in vals]
            if sum(mask) < 3:
                continue
            fv = np.array([float(vals[t]) for t in range(len(vals)) if mask[t]])
            pr = np.array([pos_rank[t] for t in range(len(vals)) if mask[t]])
            nrun[c] += len(fv)
            if fv.max() == fv.min():
                const[c] += 1
                continue
            used[c] += 1
            fr = _rankdata(fv)
            pooled[c][0].extend((fr - fr.mean()).tolist())
            pooled[c][1].extend((pr - pr.mean()).tolist())

    out = {}
    for c in cols:
        xs, ys = np.array(pooled[c][0]), np.array(pooled[c][1])
        if len(xs) > 1 and xs.std() > 0 and ys.std() > 0:
            rho = float(np.corrcoef(xs, ys)[0, 1])
        else:
            rho = float("nan")
        out[c] = (rho, used[c], const[c], nrun[c])
    return out


def stage2_proof(runs, feat, class_par, clip_floor):
    n = len(runs)
    print()
    print("=" * 74)
    print("STAGE 2 -- WINDOWED FEATURES + LEAKAGE PROOF")
    print("=" * 74)

    # ---- class par sanity (higher grade -> beats cell par by more) --------- #
    print("\nclass_par (mean clipped speedfig_raw by race class, TRAIN only):")
    print("  expect higher grade (lower class number) => larger figure")
    for c in sorted(class_par):
        print(f"    class {c}: {class_par[c]:+.4f}")

    # ---- null rates -------------------------------------------------------- #
    print("\nfeature non-empty fill rate (over flat figured runs):")
    for c in NEW2:
        filled = sum(1 for k in range(n) if feat[k][c] != "")
        print(f"  {c:20s} {100*filled/n:5.1f}%")

    # ---- pull or/rpr anchors straight from source -------------------------- #
    or_by_i, rpr_by_i = {}, {}
    want = {r["i"] for r in runs}
    with open(SRC, newline="") as f:
        rd = csv.reader(f)
        hdr = next(rd)
        ci = {c: t for t, c in enumerate(hdr)}
        oi, ri = ci["or"], ci["rpr"]
        for idx, row in enumerate(rd):
            if idx in want:
                def _f(x):
                    try:
                        return float(x)
                    except (TypeError, ValueError):
                        return ""
                or_by_i[idx] = _f(row[oi])
                rpr_by_i[idx] = _f(row[ri])

    # ---- build per-runner records for the within-race Spearman ------------- #
    cols = ["or", "rpr"] + NEW2
    records = []
    for k in range(n):
        r = runs[k]
        ps = r["pos"]
        if not ps.isdigit():
            continue
        rec = dict(feat[k])
        rec["or"] = or_by_i.get(r["i"], "")
        rec["rpr"] = rpr_by_i.get(r["i"], "")
        records.append((r["rid"], int(ps), rec))

    res = within_race_spearman(records, cols)

    print()
    print("WITHIN-RACE SPEARMAN(feature, finishing pos)  [pooled over races>=3 runners]")
    print("  anchors:  or = clean pre-race (~-0.12)   |   rpr = post-race leak (~-0.89)")
    print("  read:     speed features should be pre-race-like; |rho|>=0.30 => FLAG")
    print(f"  {'feature':20s}{'rho':>9}{'races':>8}{'const':>7}{'runners':>9}   flag")
    for c in cols:
        rho, u, cst, nr = res[c]
        rs = "  nan" if rho != rho else f"{rho:+.3f}"
        if c == "or":
            tag = "<- anchor (clean)"
        elif c == "rpr":
            tag = "<- anchor (LEAK)"
        elif rho == rho and abs(rho) >= 0.30:
            tag = "*** FLAG: approaching rpr -- recheck windowing"
        elif rho == rho and abs(rho) >= 0.20:
            tag = "(stronger than or -- real past-speed signal, still pre-race-like)"
        else:
            tag = ""
        print(f"  {c:20s}{rs:>9}{u:>8}{cst:>7}{nr:>9}   {tag}")

    # ---- KEY DIAGNOSTIC: does going_delta add signal BEYOND sf_avg3? -------- #
    print()
    print("KEY DIAGNOSTIC -- ground-interaction beyond the plain figure")
    print("  sf_avg3            : base speed (mean of last 3 prior, clipped)")
    print("  sf_on_todays_going : same but ONLY prior runs on today's going band")
    print("  sf_going_delta     : on-going minus overall avg (the suitability term)")
    for c in ("sf_avg3", "sf_on_todays_going", "sf_going_delta"):
        rho, u, cst, nr = res[c]
        rs = "nan" if rho != rho else f"{rho:+.3f}"
        print(f"    {c:20s} rho={rs:>8}  (runners={nr})")
    # partial: within-race correlation of going_delta with pos, controlling avg3,
    # via residualising both on sf_avg3 across the runners that have BOTH.
    _partial_going_delta(records)

    # ---- 5-horse run-by-run trace ------------------------------------------ #
    print()
    print("5-HORSE TRACE -- features use ONLY prior runs; debut null; no backfill")
    horse_runs = defaultdict(list)
    for k in range(n):
        horse_runs[runs[k]["horse"]].append(k)
    # pick 5 horses with a healthy run count and some going variety
    cands = sorted(horse_runs.items(), key=lambda kv: -len(kv[1]))
    picks = [h for h, ks in cands if 5 <= len(ks) <= 12][:5]
    for h in picks:
        ks = sorted(horse_runs[h], key=lambda k: runs[k]["date"])
        print(f"\n  {h}")
        print(f"    {'date':11s}{'band':>11}{'secs':>8}{'sf_raw':>9}"
              f"{'sf_last':>9}{'sf_avg3':>9}{'on_going':>9}{'switch':>7}")
        for k in ks:
            r, d = runs[k], feat[k]
            def g(c):
                v = d[c]
                return "  --  " if v == "" else f"{float(v):+.4f}"
            sw = "" if d["going_switch_flag"] == "" else str(d["going_switch_flag"])
            print(f"    {r['date']:11s}{r['band']:>11}{r['secs']:>8.1f}"
                  f"{r['speedfig_raw']:>+9.4f}{g('sf_last'):>9}{g('sf_avg3'):>9}"
                  f"{g('sf_on_todays_going'):>9}{sw:>7}")

    # ---- variation within race (identifiability in a conditional logit) ----- #
    print()
    print("WITHIN-RACE VARIATION (a conditional logit can only use VARYING features)")
    by_race_present = defaultdict(lambda: defaultdict(list))
    for k in range(n):
        r = runs[k]
        for c in NEW2:
            v = feat[k][c]
            if v != "":
                by_race_present[r["rid"]][c].append(float(v))
    for c in NEW2:
        races_ge2 = 0
        varying = 0
        for rid, cm in by_race_present.items():
            vals = cm.get(c, [])
            if len(vals) >= 2:
                races_ge2 += 1
                if max(vals) != min(vals):
                    varying += 1
        pct = 100 * varying / races_ge2 if races_ge2 else float("nan")
        print(f"  {c:20s} varies in {pct:5.1f}% of races with >=2 present "
              f"({races_ge2} such races)")

    print()
    print("STAGE 2 PROOF COMPLETE -- STOP. No fit, no commit until reviewed.")


def _partial_going_delta(records):
    """Within-race partial: correlation of sf_going_delta with finishing pos AFTER
    removing sf_avg3 (both residualised on sf_avg3 within each race, pooled). If
    ~0 => going_delta adds nothing beyond the base figure; if it stays negative
    => the ground-suitability term carries INDEPENDENT within-race signal."""
    import numpy as np
    xs_res, ys_res = [], []           # residual going_delta, residual pos-rank
    raw_dx, raw_dy = [], []           # for the simple pooled corr too
    races = defaultdict(list)
    for rk, pos, rec in records:
        gd, a3 = rec.get("sf_going_delta", ""), rec.get("sf_avg3", "")
        if gd != "" and gd is not None and a3 != "" and a3 is not None:
            races[rk].append((pos, float(gd), float(a3)))
    for rk, recs in races.items():
        if len(recs) < 3:
            continue
        pos = np.array([p for p, _, _ in recs], float)
        gd = np.array([g for _, g, _ in recs], float)
        a3 = np.array([a for _, _, a in recs], float)
        if a3.max() == a3.min() or gd.max() == gd.min():
            continue
        pr = _rankdata(pos)
        # residualise gd and pos-rank on a3 (within race, OLS with intercept)
        A = np.column_stack([np.ones(len(a3)), a3])
        bx, *_ = np.linalg.lstsq(A, gd, rcond=None)
        by, *_ = np.linalg.lstsq(A, pr, rcond=None)
        rx = gd - A @ bx
        ry = pr - A @ by
        xs_res.extend((rx).tolist()); ys_res.extend((ry).tolist())
        raw_dx.extend((gd - gd.mean()).tolist())
        raw_dy.extend((pr - pr.mean()).tolist())
    def corr(a, b):
        a, b = np.array(a), np.array(b)
        if len(a) > 1 and a.std() > 0 and b.std() > 0:
            return float(np.corrcoef(a, b)[0, 1])
        return float("nan")
    print(f"    -> going_delta vs pos, RAW within-race corr  = {corr(raw_dx,raw_dy):+.3f}")
    print(f"    -> going_delta vs pos, PARTIAL on sf_avg3     = {corr(xs_res,ys_res):+.3f}")
    print("       (partial ~0 => no signal beyond base figure; stays negative =>")
    print("        ground-suitability carries INDEPENDENT within-race information)")


def main():
    (n_total, runs, by0, par0, par1, par2, shift, band_ncells,
     clip_floor, class_par, feat) = build()
    write_out(n_total, runs, feat)
    report(n_total, runs, by0, par0, par1, par2, shift, band_ncells, clip_floor)
    stage2_proof(runs, feat, class_par, clip_floor)


if __name__ == "__main__":
    main()
