#!/usr/bin/env python3
"""score_target_c.py -- ALTERNATIVE-TARGET analysis: best-of-rest (favourite excluded).

PARALLEL analysis, NOT a change to the main win-target pipeline. It reuses the
EXISTING materialised, leakage-clean rolling-form feature set (features/build_rolling.py
-> joined_gb_2018_2026_feat.csv) and the project's conditional-logit machinery, but
swaps the LABEL:

  POPULATION : each race is filtered to its NON-FAVOURITES -- the market favourite
               (single lowest-BSP priced runner) is excluded from the choice set.
  LABEL      : "best-of-rest" -- among the remaining runners, is this one the
               best-placed of the sub-group (lowest finishing pos among non-favs)?
               Exactly one positive per sub-race (dead-heat ties -> lowest BSP).

THE CRITICAL PART -- the null is the MARKET'S OWN RANKING of the sub-population,
never a uniform/blind 1/(field-1). Two honest benchmarks are computed:

  (A) SECOND-FAVOURITE null. The market's single best guess at best-of-rest is the
      2nd-favourite = the lowest-BSP runner AMONG the non-favourites. The model's
      top pick must identify best-of-rest MORE OFTEN than just taking the 2nd-fav.
      Also expressed probabilistically: q_i = (1/bsp_i) renormalised WITHIN the
      non-fav sub-group -- the market-implied P(best-of-rest). "Always pick the
      2nd-favourite" == argmax q.
  (B) PRICE-BAND-STRATIFIED null (the favourite-longshot hardening, same as the
      main verdict fix). Non-favourites still span a wide price range, so a rule
      that merely skews toward the shorter non-favs would beat a naive null for
      free. Each model-picked horse's actual back-@BSP return is benchmarked
      against the FULL non-fav field's back-all@BSP return IN ITS OWN BSP BAND.

VERDICT (same hardened bar as run_strategy.py, decided on the HOLDOUT split):
  ruled-in requires, on holdout, WITH discovery corroboration:
    * the model/blend pick beats the 2nd-favourite null (identifies best-of-rest
      more often), AND
    * a re-fitted blend beats the market ("always pick 2nd-fav" implied probs) on
      BRIER over the sub-population -- a genuine PROBABILITY edge.
  A CLV/ROI-style gap with NO Brier improvement does NOT rule in (the
  favourite-longshot artifact). Otherwise -> priced / thin / to-holdout.

ANCHOR TEST: the best-of-rest label is anchor-tested for leakage exactly like the
history-join features -- within-sub-race Spearman vs finish for `or` (pre-race
anchor ~ -0.1), `rpr` (post-race leaker ~ -0.8, proves the test still bites on
this population) and every rolling feature (must stay in the pre-race band).

This script writes NOTHING into the main pipeline; it only reads the derived CSV
and prints + dumps models/target_c_results.json.
"""
import os
import sys
import csv
import json
import math
from collections import defaultdict

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backtest"))
import clv  # noqa: E402  -- reuse settlement (back_bet_pnl) + commission default

FEAT_CSV = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_feat.csv")
OUT_JSON = os.path.join(_ROOT, "models", "target_c_results.json")

# The rolling-form baseline feature set: stage-1 base (or/draw/lbs/age) + the
# leakage-safe rolling batch. Same materialised columns, different target.
BASE_FEATURES = ["or", "draw", "lbs", "age"]
ROLL_FEATURES = ["f_career_runs", "f_days_since", "f_win_rate",
                 "f_place_rate", "f_jky_sr", "f_trn_sr"]
FEATURES = BASE_FEATURES + ROLL_FEATURES

SPLIT_CUTOFF = "2023-12-31"          # discovery <= cutoff | holdout > cutoff
COMMISSION = clv.DEFAULT_COMMISSION  # 0.05
THIN_HOLDOUT_N = 2000                # < this many holdout sub-races -> can't confirm
EDGE_TOL = 0.01                      # +/-1pp floor for the ROI edge
# A Brier delta below this on a ~0.10 base is not a probability edge -- it is the
# renormalisation/fit wobble of a blend that has collapsed onto the market.
BRIER_EPS = 1e-4

# Same BSP odds bands as run_strategy.py's price-band-stratified null.
_PRICE_BAND_EDGES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
                     10.0, 15.0, 20.0, 30.0, 50.0, float("inf"))
_N_BANDS = len(_PRICE_BAND_EDGES) - 1
MIN_BAND_N = 50


def _price_band(bsp):
    if not bsp or bsp <= 1.0:
        return None
    for i in range(_N_BANDS):
        if _PRICE_BAND_EDGES[i] <= bsp < _PRICE_BAND_EDGES[i + 1]:
            return i
    return _N_BANDS - 1


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_pos(x):
    """Numeric finishing position, or None for non-finishers (PU/F/UR/...)."""
    s = ("" if x is None else str(x)).strip()
    return int(s) if s.isdigit() else None


# --------------------------------------------------------------------------- #
# 1. Load rows and build the NON-FAVOURITE sub-races + best-of-rest label.     #
# --------------------------------------------------------------------------- #
def build_subraces():
    """Return a list of sub-race dicts. Each carries the aligned per-runner arrays
    the analysis needs (features raw, bsp, won_race, best_of_rest label, or, rpr)."""
    keep = (["date", "course", "off", "horse", "pos", "bsp", "rpr"] + FEATURES)
    races = defaultdict(list)
    with open(FEAT_CSV, newline="") as f:
        for r in csv.DictReader(f):
            races[f"{r['date']}|{r['course']}|{r['off']}"].append(
                {k: r.get(k) for k in keep})

    subs = []
    n_races = 0
    dropped = {"few_priced": 0, "few_nonfav": 0, "no_label": 0}
    for rid, rs in races.items():
        n_races += 1
        priced = [r for r in rs if (fnum(r["bsp"]) or 0) > 1.0]
        if len(priced) < 3:                       # need fav + >=2 non-favs
            dropped["few_priced"] += 1
            continue
        fav = min(priced, key=lambda r: fnum(r["bsp"]))
        nonfav = [r for r in priced if r is not fav]
        if len(nonfav) < 2:
            dropped["few_nonfav"] += 1
            continue
        # best-of-rest = lowest finishing pos among non-favs (dead-heat -> min BSP)
        finishers = [r for r in nonfav if parse_pos(r["pos"]) is not None]
        if not finishers:
            dropped["no_label"] += 1
            continue
        best = min(finishers, key=lambda r: (parse_pos(r["pos"]), fnum(r["bsp"])))
        subs.append({
            "rid": rid, "date": rs[0]["date"], "runners": nonfav, "best": best,
        })
    return subs, n_races, dropped


# --------------------------------------------------------------------------- #
# 2. Feature matrix: within-sub-race mean-impute, then z-score (stats from the #
#    DISCOVERY partition only -- no holdout distribution leaks into scaling).  #
# --------------------------------------------------------------------------- #
def build_matrix(subs):
    # within-sub-race mean impute (per feature), tracking presence for global mean
    disc_present = {f: [] for f in FEATURES}
    for s in subs:
        rs = s["runners"]
        for f in FEATURES:
            vals = [fnum(r[f]) for r in rs]
            present = [v for v in vals if v is not None]
            rmean = (sum(present) / len(present)) if present else None
            s.setdefault("_raw", {})[f] = [(v if v is not None else rmean) for v in vals]
            if s["date"] <= SPLIT_CUTOFF:
                disc_present[f].extend(present)

    gmean = {f: (sum(v) / len(v) if v else 0.0) for f, v in disc_present.items()}
    # fill still-missing (a sub-race with zero present for a feature) with global
    for s in subs:
        for f in FEATURES:
            s["_raw"][f] = [(gmean[f] if v is None else v) for v in s["_raw"][f]]

    # z-score stats on discovery runners
    stats = {}
    for f in FEATURES:
        xs = np.array([v for s in subs if s["date"] <= SPLIT_CUTOFF
                       for v in s["_raw"][f]], dtype=float)
        mu, sd = float(xs.mean()), float(xs.std() or 1.0)
        stats[f] = (mu, sd or 1.0)

    # assemble flat contiguous arrays (sub-races kept contiguous, discovery first)
    subs.sort(key=lambda s: (0 if s["date"] <= SPLIT_CUTOFF else 1, s["rid"]))
    X, y_best, y_win, bsp, is_disc, sizes, meta = [], [], [], [], [], [], []
    or_arr, rpr_arr, pos_arr = [], [], []
    for s in subs:
        rs = s["runners"]
        sizes.append(len(rs))
        is_disc.append(s["date"] <= SPLIT_CUTOFF)
        meta.append(s)
        for j, r in enumerate(rs):
            X.append([(s["_raw"][f][j] - stats[f][0]) / stats[f][1] for f in FEATURES])
            y_best.append(1.0 if r is s["best"] else 0.0)
            y_win.append(1.0 if parse_pos(r["pos"]) == 1 else 0.0)
            bsp.append(fnum(r["bsp"]))
            or_arr.append(fnum(r["or"]))
            rpr_arr.append(fnum(r["rpr"]))
            pos_arr.append(parse_pos(r["pos"]))
    return (np.array(X), np.array(y_best), np.array(y_win), np.array(bsp),
            np.array(is_disc, dtype=bool), np.array(sizes),
            or_arr, rpr_arr, pos_arr, stats)


# --------------------------------------------------------------------------- #
# 3. Group-softmax conditional logit (numpy, contiguous groups).              #
# --------------------------------------------------------------------------- #
def _group_starts(sizes):
    return np.concatenate([[0], np.cumsum(sizes)[:-1]]).astype(int)


def _softmax_groups(u, starts, sizes):
    gmax = np.maximum.reduceat(u, starts)
    e = np.exp(u - np.repeat(gmax, sizes))
    gsum = np.add.reduceat(e, starts)
    return e / np.repeat(gsum, sizes)


def fit_condlogit(X, y, sizes, l2=1.0, iters=800):
    starts = _group_starts(sizes)
    beta = np.zeros(X.shape[1])

    def nll_grad(b):
        p = _softmax_groups(X @ b, starts, sizes)
        nll = -float((y * np.log(np.clip(p, 1e-12, 1))).sum()) + l2 * float(b @ b)
        grad = X.T @ (p - y) + 2 * l2 * b
        return nll, grad

    nll, grad = nll_grad(beta)
    lr = 0.5
    for _ in range(iters):
        trial = beta - lr * grad
        n2, g2 = nll_grad(trial)
        if n2 < nll:
            beta, nll, grad, lr = trial, n2, g2, lr * 1.05
        else:
            lr *= 0.5
            if lr < 1e-9:
                break
    return beta


# --------------------------------------------------------------------------- #
# 4. Metrics over a partition mask: hit-rate, Brier, and the two nulls.        #
# --------------------------------------------------------------------------- #
def _group_argmax_hits(vals, y, starts, sizes):
    """Fraction of groups whose argmax(vals) runner is the labelled winner (y=1)."""
    hits = 0
    for st, sz in zip(starts, sizes):
        seg = vals[st:st + sz]
        k = int(np.argmax(seg))
        hits += int(y[st + k] == 1.0)
    return hits / len(sizes)


def _brier(p, y):
    """Mean per-runner squared error (within-group renormalised probs vs one-hot)."""
    return float(((p - y) ** 2).mean())


def partition_metrics(mask_sizes_idx, X, y_best, y_win, bsp, sizes,
                      model_p, q, blend_p):
    """Compute all metrics for a contiguous block of groups given by group indices.

    mask_sizes_idx = (group_start_row, group_sizes) already sliced for the part.
    """
    row0, part_sizes = mask_sizes_idx
    n_rows = int(part_sizes.sum())
    sl = slice(row0, row0 + n_rows)
    starts = _group_starts(part_sizes)  # local starts within the slice

    yb = y_best[sl]
    yw = y_win[sl]
    b = bsp[sl]
    mp, qq, bp = model_p[sl], q[sl], blend_p[sl]

    # --- best-of-rest identification: hit rates vs the 2nd-favourite null ---
    hit_2ndfav = _group_argmax_hits(-b, yb, starts, part_sizes)   # min bsp = argmax(-b)
    hit_model = _group_argmax_hits(mp, yb, starts, part_sizes)
    hit_blend = _group_argmax_hits(bp, yb, starts, part_sizes)

    # --- Brier over the sub-population (probability edge, the decider) ---
    brier_mkt = _brier(qq, yb)
    brier_model = _brier(mp, yb)
    brier_blend = _brier(bp, yb)

    # --- betting @BSP (actual race win), price-band-stratified null over non-favs ---
    # full non-fav field back-all@BSP, bucketed by BSP band -> the stratified null
    band_pnl = np.zeros(_N_BANDS)
    band_n = np.zeros(_N_BANDS)
    ff_pnl = 0.0
    for i in range(n_rows):
        pnl = clv.back_bet_pnl(b[i], bool(yw[i]), COMMISSION)
        ff_pnl += pnl
        bi = _price_band(b[i])
        if bi is not None:
            band_pnl[bi] += pnl
            band_n[bi] += 1
    ff_roi = ff_pnl / n_rows if n_rows else None
    band_roi = np.where(band_n >= MIN_BAND_N, band_pnl / np.maximum(band_n, 1), np.nan)

    def pick_block(vals):
        """Back the argmax-vals non-fav in each group; ROI@BSP + stratified edge.

        Also returns the per-bet ROI standard error and the picks' mean BSP so a
        big-looking @BSP number can be read against its noise and price mix (a
        longshot-skewed pick set produces a high-variance ROI that a coarse
        stratified null cannot fully tame -- exactly the artifact the Brier gate
        is there to catch)."""
        pnls, strat, wins, bsps = [], 0.0, 0, []
        for st, sz in zip(starts, part_sizes):
            seg = vals[st:st + sz]
            k = st + int(np.argmax(seg))
            pnls.append(clv.back_bet_pnl(b[k], bool(yw[k]), COMMISSION))
            wins += int(yw[k] == 1.0)
            bsps.append(b[k])
            bi = _price_band(b[k])
            if bi is not None and not np.isnan(band_roi[bi]):
                strat += band_roi[bi]
            elif ff_roi is not None:
                strat += ff_roi
        pnls = np.array(pnls)
        n = len(pnls)
        roi = float(pnls.mean())
        roi_se = float(pnls.std(ddof=1) / math.sqrt(n)) if n > 1 else None
        strat_roi = strat / n
        return {"n": n, "win_rate": wins / n, "roi_bsp": roi, "roi_se": roi_se,
                "mean_bsp": float(np.mean(bsps)),
                "strat_null_bsp": strat_roi, "edge_strat": roi - strat_roi}

    return {
        "n_subraces": len(part_sizes),
        "n_runners": n_rows,
        "hit_rate": {"second_fav": hit_2ndfav, "model": hit_model, "blend": hit_blend,
                     "model_minus_2ndfav": hit_model - hit_2ndfav,
                     "blend_minus_2ndfav": hit_blend - hit_2ndfav},
        "brier": {"market": brier_mkt, "model": brier_model, "blend": brier_blend,
                  "blend_minus_market": brier_blend - brier_mkt,
                  "blend_beats_market": brier_blend < brier_mkt},
        "betting_bsp": {
            "fullfield_nonfav_roi": ff_roi,
            "second_fav": pick_block(-b),
            "model": pick_block(mp),
            "blend": pick_block(bp),
        },
    }


# --------------------------------------------------------------------------- #
# 5. Anchor test on the best-of-rest label (within-sub-race Spearman vs pos).  #
# --------------------------------------------------------------------------- #
def _spearman(a, b):
    n = len(a)
    if n < 3:
        return None
    ra = np.argsort(np.argsort(a)).astype(float)
    rb = np.argsort(np.argsort(b)).astype(float)
    ra -= ra.mean(); rb -= rb.mean()
    d = math.sqrt((ra * ra).sum() * (rb * rb).sum())
    return float((ra * rb).sum() / d) if d > 0 else None


def anchor_test(subs, stats):
    """Within-sub-race Spearman of each column vs finishing pos, over the NON-FAV
    sub-group (finishers only). or ~ pre-race anchor; rpr ~ post-race leak sanity;
    rolling features must land in the pre-race band."""
    cols = ["or", "rpr"] + [f for f in FEATURES if f not in ("or",)]
    acc = {c: [] for c in cols}
    for s in subs:
        rs = s["runners"]
        pos = [parse_pos(r["pos"]) for r in rs]
        idx = [i for i, p in enumerate(pos) if p is not None]
        if len(idx) < 3:
            continue
        pv = [pos[i] for i in idx]
        for c in cols:
            vals = [fnum(r[c]) for r in rs]
            xs = [vals[i] for i in idx]
            if any(x is None for x in xs) or len(set(xs)) < 2:
                continue
            rho = _spearman(pv, xs)
            if rho is not None:
                acc[c].append(rho)
    out = {}
    for c in cols:
        arr = acc[c]
        out[c] = {"mean_rho": (float(np.mean(arr)) if arr else None),
                  "n_subraces": len(arr)}
    return out


# --------------------------------------------------------------------------- #
# 6. Verdict (holdout-decided, same hardened bar).                            #
# --------------------------------------------------------------------------- #
def _brier_edge(part):
    """market Brier - blend Brier; positive AND above BRIER_EPS = a real prob edge
    (not the fit wobble of a blend that has collapsed onto the market)."""
    return part["brier"]["market"] - part["brier"]["blend"]


def verdict(disc, hold):
    hn = hold["n_subraces"]
    h_hit = hold["hit_rate"]["blend_minus_2ndfav"]
    d_hit = disc["hit_rate"]["blend_minus_2ndfav"]
    h_be, d_be = _brier_edge(hold), _brier_edge(disc)
    h_brier_ok = h_be > BRIER_EPS
    d_brier_ok = d_be > BRIER_EPS
    h_edge = hold["betting_bsp"]["blend"]["edge_strat"]

    if hn < THIN_HOLDOUT_N:
        if d_hit > 0 and d_brier_ok:
            return "to-holdout", (
                f"discovery blend beats the 2nd-fav null (+{d_hit:.2%} hit) with a "
                f"Brier edge, but holdout n={hn:,} < {THIN_HOLDOUT_N:,} -- too thin.")
        return "thin", (f"holdout n={hn:,} < {THIN_HOLDOUT_N:,}; not enough to judge.")

    # decisive gate: a MEANINGFUL probability edge. A hit-rate/ROI gap without it is
    # the favourite-longshot / CLV-relative artifact -> priced (as the brief requires).
    if not h_brier_ok:
        return "priced", (
            f"the blend collapses onto the market (blend Brier {hold['brier']['blend']:.5f} "
            f"vs market {hold['brier']['market']:.5f}, margin {h_be:+.5f} <= {BRIER_EPS:g}); "
            f"the model adds no probability edge over the market's OWN ranking of the "
            f"sub-population, so it also fails to out-pick the 2nd-favourite (hit "
            f"{h_hit:+.2%}). Any @BSP ROI on longshot picks (holdout "
            f"{hold['betting_bsp']['model']['roi_bsp']:+.2%} "
            f"+/-{hold['betting_bsp']['model']['roi_se']:.2%}) is the "
            f"favourite-longshot artifact, not harvestable edge.")

    if h_hit <= 0:
        return "priced", (
            f"holdout blend clears the Brier floor ({h_be:+.5f}) but does NOT beat the "
            f"2nd-favourite on best-of-rest identification (hit {h_hit:+.2%}) -- the edge "
            f"does not translate into out-picking the market's single best guess.")

    if not (d_hit > 0 and d_brier_ok):
        return "priced", (
            f"holdout edge (hit {h_hit:+.2%}, Brier {h_be:+.5f}) is NOT corroborated "
            f"by discovery (hit {d_hit:+.2%}, Brier {d_be:+.5f}).")

    return "ruled-in", (
        f"holdout blend beats the 2nd-favourite null on best-of-rest identification "
        f"(hit {h_hit:+.2%}) AND beats the market on Brier by {h_be:+.5f} "
        f"(> {BRIER_EPS:g}) on n={hn:,}, corroborated on discovery (hit {d_hit:+.2%}) "
        f"-- a real probability edge over the market's ranking of the sub-population "
        f"(betting @BSP price-band-stratified edge {h_edge:+.2%}).")


# --------------------------------------------------------------------------- #
# Main.                                                                        #
# --------------------------------------------------------------------------- #
def main():
    print("Building non-favourite sub-races + best-of-rest label ...")
    subs, n_races, dropped = build_subraces()
    print(f"  races scanned      : {n_races:,}")
    print(f"  dropped few_priced : {dropped['few_priced']:,}  "
          f"few_nonfav {dropped['few_nonfav']:,}  no_label {dropped['no_label']:,}")
    print(f"  usable sub-races   : {len(subs):,}")

    (X, y_best, y_win, bsp, is_disc, sizes,
     or_arr, rpr_arr, pos_arr, stats) = build_matrix(subs)

    n_disc = int(is_disc.sum())      # sub-races are sorted discovery-first
    starts = _group_starts(sizes)
    disc_rows = int(sizes[:n_disc].sum())

    print(f"\nsplit @ {SPLIT_CUTOFF}: discovery {n_disc:,} sub-races "
          f"| holdout {len(sizes) - n_disc:,} sub-races")

    # --- fit conditional logit on DISCOVERY sub-races only ---
    dsizes = sizes[:n_disc]
    beta = fit_condlogit(X[:disc_rows], y_best[:disc_rows], dsizes)
    print("\nfitted conditional logit (best-of-rest | non-favourites), z-coeffs:")
    for f, bb in zip(FEATURES, beta):
        print(f"  {f:14s}{bb:+.4f}")

    # score ALL sub-races
    model_p = _softmax_groups(X @ beta, starts, sizes)
    # market-implied within the non-fav sub-group
    q = _softmax_groups(np.log(1.0 / bsp), starts, sizes)   # softmax(log 1/bsp)=renorm

    # --- fit the BLEND (Benter): a*log(model) + b*log(q), on DISCOVERY ---
    Xb = np.column_stack([np.log(np.clip(model_p, 1e-12, 1)),
                          np.log(np.clip(q, 1e-12, 1))])
    beta_b = fit_condlogit(Xb[:disc_rows], y_best[:disc_rows], dsizes, l2=0.5)
    blend_p = _softmax_groups(Xb @ beta_b, starts, sizes)
    print(f"\nblend weights (log-model, log-market): "
          f"{beta_b[0]:+.4f}, {beta_b[1]:+.4f}  "
          f"(market share {beta_b[1] / (abs(beta_b[0]) + abs(beta_b[1])):.1%})")

    # --- partition metrics ---
    disc_idx = (0, sizes[:n_disc])
    hold_idx = (disc_rows, sizes[n_disc:])
    disc_m = partition_metrics(disc_idx, X, y_best, y_win, bsp, sizes, model_p, q, blend_p)
    hold_m = partition_metrics(hold_idx, X, y_best, y_win, bsp, sizes, model_p, q, blend_p)

    # --- anchor test on the label ---
    anchor = anchor_test(subs, stats)

    vd, reason = verdict(disc_m, hold_m)

    results = {
        "target": "C_best_of_rest_favourite_excluded",
        "feature_set": FEATURES,
        "split_cutoff": SPLIT_CUTOFF,
        "commission": COMMISSION,
        "n_races_scanned": n_races,
        "n_subraces_usable": len(subs),
        "condlogit_beta": dict(zip(FEATURES, [float(b) for b in beta])),
        "blend_beta": {"log_model": float(beta_b[0]), "log_market": float(beta_b[1])},
        "discovery": disc_m,
        "holdout": hold_m,
        "anchor_test": anchor,
        "verdict": vd,
        "verdict_reason": reason,
    }
    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=float)

    _print_report(disc_m, hold_m, anchor, vd, reason)
    print(f"\nwrote {os.path.relpath(OUT_JSON, _ROOT)}")


def _print_report(d, h, anchor, vd, reason):
    pct = lambda x: (f"{x:+.2%}" if x is not None else "   --")
    p5 = lambda x: (f"{x:.5f}" if x is not None else "   --")
    print("\n" + "=" * 72)
    print("TARGET C -- best-of-rest (favourite excluded)   discovery | holdout")
    print("=" * 72)
    print(f"{'sub-races':<32}{d['n_subraces']:>18,}{h['n_subraces']:>18,}")
    print(f"{'non-fav runners':<32}{d['n_runners']:>18,}{h['n_runners']:>18,}")
    print("\n-- best-of-rest IDENTIFICATION (hit rate; null = pick 2nd-favourite) --")
    for k, lab in [("second_fav", "2nd-fav (market null)"),
                   ("model", "model pick"), ("blend", "blend pick")]:
        print(f"  {lab:<30}{d['hit_rate'][k]:>18.2%}{h['hit_rate'][k]:>18.2%}")
    print(f"  {'blend - 2nd-fav (edge)':<30}"
          f"{d['hit_rate']['blend_minus_2ndfav']:>18.2%}"
          f"{h['hit_rate']['blend_minus_2ndfav']:>18.2%}")
    print("\n-- BRIER over the sub-population (probability edge; gate) --")
    for k, lab in [("market", "market (2nd-fav implied)"),
                   ("model", "model"), ("blend", "blend")]:
        print(f"  {lab:<30}{p5(d['brier'][k]):>18}{p5(h['brier'][k]):>18}")
    dbe = d['brier']['market'] - d['brier']['blend']
    hbe = h['brier']['market'] - h['brier']['blend']
    mflag = lambda x: ("edge" if x > BRIER_EPS else "~market")
    print(f"  {'market - blend (margin)':<30}{dbe:>+18.5f}{hbe:>+18.5f}")
    print(f"  {'meaningful edge (>1e-4)?':<30}{mflag(dbe):>18}{mflag(hbe):>18}")
    print("\n-- betting @BSP (actual win), price-band-stratified null over non-favs --")
    for k, lab in [("second_fav", "back 2nd-fav"),
                   ("model", "back model pick"), ("blend", "back blend pick")]:
        db, hb = d["betting_bsp"][k], h["betting_bsp"][k]
        hse = f" +/-{hb['roi_se']:.2%}" if hb.get("roi_se") is not None else ""
        print(f"  {lab:<20} ROI@BSP     {pct(db['roi_bsp']):>12}"
              f"{pct(hb['roi_bsp']) + hse:>24}")
        print(f"  {'':<20} strat-edge  {pct(db['edge_strat']):>12}{pct(hb['edge_strat']):>18}")
        print(f"  {'':<20} mean BSP    {db['mean_bsp']:>12.2f}{hb['mean_bsp']:>18.2f}")
    print("\n-- ANCHOR TEST on the best-of-rest label (within-sub-race Spearman vs finish) --")
    print("   anchors: or ~ pre-race (mild) | rpr ~ post-race leak (strong -ve)")
    for c in ["or", "rpr"] + [f for f in FEATURES if f not in ("or",)]:
        a = anchor[c]
        m = a["mean_rho"]
        tag = ""
        if c == "or":
            tag = "<- PRE-RACE anchor"
        elif c == "rpr":
            tag = "<- POST-RACE leak sanity (test still bites)"
        elif m is not None and abs(m) > 0.6:
            tag = "*** NEAR rpr -- LEAK ***"
        else:
            tag = "ok (pre-race band)"
        ms = f"{m:+.4f}" if m is not None else "  n/a"
        print(f"  {c:<16}{ms:>10}   ({a['n_subraces']:,} sub-races)  {tag}")
    print("\n" + "=" * 72)
    print(f"VERDICT: {vd.upper()}")
    print(reason)
    print("=" * 72)


if __name__ == "__main__":
    main()
