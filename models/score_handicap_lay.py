#!/usr/bin/env python3
"""score_handicap_lay.py -- SOLO handicap-features test on the LAY target.

Reads data/joined/joined_gb_2018_2026_hcap.csv, restricts to the FLAT-HANDICAP
subset (is_flat_hcap==1), and answers the Phase-3 question for the handicap
feature set ALONE (no rolling, no speedfig -- clean attribution):

  1. Does the handicap-features Stage-1 move the Benter blend weight off the
     baseline (~6.9% on this subset)?  Baseline = Stage-1 on the public set
     {or,draw,lbs,age}.  Solo = Stage-1 on the runner-VARYING handicap features.
  2. Blend Brier vs BSP (does the blend approach but not beat the market?).
  3. The LAY target (fully measurable): lay CLV@wap, lay drift, and -- the real
     question -- lay-SELECTED vs the back-all-lay baseline.

PROTOCOL (out-of-sample, the point of the whole exercise)
  TRAIN   = seasons <= 2023   (fit Stage-1 betas AND the Benter a,b here)
  VAL     = 2024              (reported separately)
  HOLDOUT = 2025-2026         (reported separately)
Stage-1 standardisation stats and the blend weights are LEARNED ON TRAIN ONLY
and applied frozen to val/holdout. No fitting touches val/holdout.

LEAKAGE: Stage-1 uses ONLY the runner-VARYING handicap features (race-CONSTANT
ones -- h_or_spread/std/field_or_mean/h_class -- cancel in a conditional logit
and are kept OUT; they live in the file for Stage-2 only). The market leg is the
pre-off WAP (struck price), NEVER BSP. BSP is the scorer.

LAY mechanics (struck = wap, close = bsp, 5% commission on layer winnings):
  lay value rule : lay where struck < 1/p  (market price shorter than fair -> overbet)
  lay CLV        : bsp/struck - 1           (>0 = price drifted out after we laid = good)
  drift          : bsp/wap - 1              (wap->close move; lay wants this positive)
  lay P&L (1u backer stake): horse loses -> +1*(1-comm) ; horse wins -> -(struck-1)
"""
import os
import csv
import math
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_hcap.csv")
COMMISSION = 0.05

# Stage-1 feature sets ------------------------------------------------------
BASELINE_FEATS = ["or", "draw", "lbs", "age"]              # public baseline
HCAP_FEATS = ["h_or", "h_or_vs_lastwin", "h_or_delta_last", "h_or_delta_career",
              "h_or_vs_pb", "h_or_rank", "h_or_z", "h_hcap_runs",
              "h_lbs", "h_lbs_z", "h_lbs_delta_last",
              "h_class_delta_last", "h_class_drop_best"]     # runner-VARYING only


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# Load + split                                                                #
# --------------------------------------------------------------------------- #
def load():
    rows = []
    with open(SRC, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("is_flat_hcap") != "1":
                continue
            rid = f"{r['date']}|{r['course']}|{r['off']}"
            rows.append({
                "rid": rid,
                "year": int(r["date"][:4]),
                "won": 1.0 if (r.get("pos") or "").strip() == "1" else 0.0,
                "bsp": fnum(r.get("bsp")),
                "wap": fnum(r.get("wap")),
                "raw": r,
            })
    return rows


def split(rows):
    tr = [r for r in rows if r["year"] <= 2023]
    va = [r for r in rows if r["year"] == 2024]
    ho = [r for r in rows if r["year"] >= 2025]
    return tr, va, ho


# --------------------------------------------------------------------------- #
# Feature matrix: race-mean impute -> z-standardise (stats frozen from train) #
# --------------------------------------------------------------------------- #
def build_X(rows, feats, stats):
    """Impute (race-mean, then train global mean) and z-standardise with `stats`
    = {feat: (global_mean, mu, sd)}. Returns X (N,K) float array."""
    # group by race for race-mean imputation
    by_race = {}
    for i, r in enumerate(rows):
        by_race.setdefault(r["rid"], []).append(i)
    N, K = len(rows), len(feats)
    X = np.empty((N, K))
    for k, f in enumerate(feats):
        gmean, mu, sd = stats[f]
        vals = [fnum(rows[i]["raw"].get(f)) for i in range(N)]
        for idxs in by_race.values():
            present = [vals[i] for i in idxs if vals[i] is not None]
            rm = sum(present) / len(present) if present else gmean
            for i in idxs:
                v = vals[i] if vals[i] is not None else rm
                X[i, k] = (v - mu) / sd
    return X


def fit_stats(rows, feats):
    """Train-only standardisation stats. global mean (impute fallback), and the
    mu/sd of the race-mean-imputed values (so z is well-scaled)."""
    by_race = {}
    for i, r in enumerate(rows):
        by_race.setdefault(r["rid"], []).append(i)
    stats = {}
    for f in feats:
        vals = [fnum(rows[i]["raw"].get(f)) for i in range(len(rows))]
        present = [v for v in vals if v is not None]
        gmean = sum(present) / len(present)
        imp = []
        for idxs in by_race.values():
            pr = [vals[i] for i in idxs if vals[i] is not None]
            rm = sum(pr) / len(pr) if pr else gmean
            for i in idxs:
                imp.append(vals[i] if vals[i] is not None else rm)
        mu = sum(imp) / len(imp)
        sd = (sum((x - mu) ** 2 for x in imp) / len(imp)) ** 0.5 or 1.0
        stats[f] = (gmean, mu, sd)
    return stats


# --------------------------------------------------------------------------- #
# Conditional logit (vectorised; races as contiguous segments)                #
# --------------------------------------------------------------------------- #
def _segments(rows):
    """Sort indices by race; return (perm, seg_starts, seg_lens)."""
    perm = np.array(sorted(range(len(rows)), key=lambda i: rows[i]["rid"]))
    rids = [rows[i]["rid"] for i in perm]
    seg_starts, seg_lens = [], []
    i = 0
    while i < len(rids):
        j = i
        while j < len(rids) and rids[j] == rids[i]:
            j += 1
        seg_starts.append(i)
        seg_lens.append(j - i)
        i = j
    return perm, np.array(seg_starts), np.array(seg_lens)


def _race_softmax(u, seg_starts, seg_lens):
    """Per-race softmax of utilities u (already sorted by race)."""
    mx = np.maximum.reduceat(u, seg_starts)
    mx_exp = np.repeat(mx, seg_lens)
    e = np.exp(u - mx_exp)
    denom = np.add.reduceat(e, seg_starts)
    return e / np.repeat(denom, seg_lens)


def cond_logit_fit(X, y, rows, l2=1.0, iters=800):
    perm, ss, sl = _segments(rows)
    Xs, ys = X[perm], y[perm]
    beta = np.zeros(X.shape[1])

    def nll_grad(b):
        u = Xs @ b
        p = _race_softmax(u, ss, sl)
        # nll = -sum log p(winner)
        nll = -np.sum(ys * np.log(np.clip(p, 1e-12, None))) + l2 * np.sum(b * b)
        grad = Xs.T @ (p - ys) + 2 * l2 * b
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


def cond_logit_prob(X, beta, rows):
    perm, ss, sl = _segments(rows)
    inv = np.empty(len(rows), dtype=int)
    inv[perm] = np.arange(len(rows))
    u = (X[perm]) @ beta
    p = _race_softmax(u, ss, sl)
    return p[inv]   # back to original row order


# --------------------------------------------------------------------------- #
# Market-implied prob (renormalised per race) from a price column             #
# --------------------------------------------------------------------------- #
def market_prob(rows, price_key):
    by_race = {}
    for i, r in enumerate(rows):
        by_race.setdefault(r["rid"], []).append(i)
    mp = [None] * len(rows)
    for idxs in by_race.values():
        inv = []
        for i in idxs:
            pr = rows[i][price_key]
            inv.append(1.0 / pr if (pr and pr > 1.0) else None)
        z = sum(v for v in inv if v is not None)
        if z <= 0:
            continue
        for i, v in zip(idxs, inv):
            mp[i] = (v / z) if v is not None else None
    return mp


# --------------------------------------------------------------------------- #
# Stage-2 Benter blend: fit (a,b) on train, apply frozen                       #
# --------------------------------------------------------------------------- #
def blend_fit(rows, model_prob, mkt_prob, l2=1.0):
    """Fit conditional logit on [log model_prob, log market_prob] over runners
    with valid market prob (>0). Returns beta=(a,b)."""
    keep = [i for i in range(len(rows))
            if mkt_prob[i] and mkt_prob[i] > 0 and model_prob[i] > 0]
    sub = [rows[i] for i in keep]
    X = np.column_stack([np.log([model_prob[i] for i in keep]),
                         np.log([mkt_prob[i] for i in keep])])
    y = np.array([rows[i]["won"] for i in keep])
    return cond_logit_fit(X, y, sub, l2=l2, iters=2000)


def blend_prob(rows, model_prob, mkt_prob, beta):
    """Apply blend weights; blend_prob only where market prob valid (else None)."""
    keep = [i for i in range(len(rows))
            if mkt_prob[i] and mkt_prob[i] > 0 and model_prob[i] > 0]
    sub = [rows[i] for i in keep]
    X = np.column_stack([np.log([model_prob[i] for i in keep]),
                         np.log([mkt_prob[i] for i in keep])])
    p = cond_logit_prob(X, beta, sub)
    out = [None] * len(rows)
    for i, pi in zip(keep, p):
        out[i] = float(pi)
    return out


# --------------------------------------------------------------------------- #
# Scoring                                                                      #
# --------------------------------------------------------------------------- #
def brier(rows, prob, mask=None):
    se, n = 0.0, 0
    for i, r in enumerate(rows):
        if prob[i] is None:
            continue
        if mask is not None and not mask[i]:
            continue
        se += (prob[i] - r["won"]) ** 2
        n += 1
    return se / n if n else float("nan")


def lay_metrics(rows, prob, selected):
    """Lay metrics over the runners where selected[i] is True. struck=wap, close=bsp."""
    clvs, drifts, pnl, beat, nwin = [], [], 0.0, 0, 0
    n = 0
    for i, r in enumerate(rows):
        if not selected[i]:
            continue
        struck, bsp = r["wap"], r["bsp"]
        if not struck or struck <= 1.0 or not bsp or bsp <= 1.0:
            continue
        n += 1
        clv = bsp / struck - 1.0           # lay CLV (drift after we laid)
        clvs.append(clv)
        drifts.append(bsp / struck - 1.0)  # wap->close move (struck==wap)
        if struck < bsp:
            beat += 1
        if r["won"]:
            pnl += -(struck - 1.0)
            nwin += 1
        else:
            pnl += 1.0 * (1.0 - COMMISSION)
    if n == 0:
        return None
    return {
        "n": n, "nwin": nwin,
        "mean_clv": float(np.mean(clvs)),
        "median_clv": float(np.median(clvs)),
        "pct_beat": beat / n,
        "median_drift": float(np.median(drifts)),
        "roi": pnl / n,
    }


def lay_select(rows, prob):
    """Lay-value rule: lay where struck < 1/p (market price shorter than fair)."""
    sel = [False] * len(rows)
    for i, r in enumerate(rows):
        p, struck = prob[i], r["wap"]
        if p and p > 0 and struck and struck > 1.0 and struck < 1.0 / p:
            sel[i] = True
    return sel


def print_lay_block(title, rows, blend_p, s1_p):
    print(f"\n--- LAY target: {title} ---")
    hdr = (f"  {'strategy':<22}{'n':>7}{'mean CLV':>10}{'med CLV':>9}"
           f"{'beat':>7}{'med drift':>10}{'lay ROI':>9}")
    print(hdr)
    # back-all-lay baseline: lay EVERY runner with a valid price
    base_sel = [bool(r["wap"] and r["wap"] > 1.0 and r["bsp"] and r["bsp"] > 1.0)
                for r in rows]
    rep = [("lay-ALL (baseline)", base_sel),
           ("blend lay-selected", lay_select(rows, blend_p)),
           ("stage1 lay-selected", lay_select(rows, s1_p))]
    for name, sel in rep:
        m = lay_metrics(rows, [1.0] * len(rows), sel) if name.startswith("lay-ALL") \
            else lay_metrics(rows, blend_p, sel)
        if m is None:
            print(f"  {name:<22}{'--':>7}")
            continue
        print(f"  {name:<22}{m['n']:>7}{m['mean_clv']:>9.2%}{m['median_clv']:>8.2%}"
              f"{m['pct_beat']:>7.1%}{m['median_drift']:>9.2%}{m['roi']:>9.2%}")


# --------------------------------------------------------------------------- #
def run_stage1(name, feats, tr, va, ho):
    stats = fit_stats(tr, feats)
    Xtr, Xva, Xho = (build_X(tr, feats, stats), build_X(va, feats, stats),
                     build_X(ho, feats, stats))
    ytr = np.array([r["won"] for r in tr])
    beta = cond_logit_fit(Xtr, ytr, tr)
    p_tr = list(cond_logit_prob(Xtr, beta, tr))
    p_va = list(cond_logit_prob(Xva, beta, va))
    p_ho = list(cond_logit_prob(Xho, beta, ho))
    return beta, p_tr, p_va, p_ho


def main():
    rows = load()
    tr, va, ho = split(rows)
    print(f"FLAT-HANDICAP rows: {len(rows)}  "
          f"(train<=2023 {len(tr)} | val2024 {len(va)} | holdout2025-26 {len(ho)})")

    # market-implied prob from WAP (struck), per split, per race
    wap_tr, wap_va, wap_ho = (market_prob(tr, "wap"), market_prob(va, "wap"),
                              market_prob(ho, "wap"))
    bsp_tr, bsp_va, bsp_ho = (market_prob(tr, "bsp"), market_prob(va, "bsp"),
                              market_prob(ho, "bsp"))

    results = {}
    for name, feats in (("baseline {or,draw,lbs,age}", BASELINE_FEATS),
                        ("handicap-solo (varying)", HCAP_FEATS)):
        beta, p_tr, p_va, p_ho = run_stage1(name, feats, tr, va, ho)
        # Stage-2 blend fitted on TRAIN, applied frozen to val/holdout
        bb = blend_fit(tr, p_tr, wap_tr)
        a, b = bb
        weight = a / (a + b) if (a + b) != 0 else float("nan")
        bl_va = blend_prob(va, p_va, wap_va, bb)
        bl_ho = blend_prob(ho, p_ho, wap_ho, bb)
        results[name] = {
            "beta": beta, "a": a, "b": b, "weight": weight,
            "p_va": p_va, "p_ho": p_ho, "bl_va": bl_va, "bl_ho": bl_ho,
        }
        print(f"\n=== Stage-1 = {name} ===")
        print(f"  Benter blend weights (fitted on TRAIN): a(model)={a:+.4f}  "
              f"b(market)={b:+.4f}")
        print(f"  -> MODEL WEIGHT a/(a+b) = {weight:6.2%}   "
              f"(baseline reference ~6.9%)")

    # ---- blend weight comparison (the ONE number) --------------------------
    base_w = results["baseline {or,draw,lbs,age}"]["weight"]
    hc_w = results["handicap-solo (varying)"]["weight"]
    print("\n" + "=" * 72)
    print("THE ONE NUMBER -- Stage-1 model weight in the Benter blend (TRAIN-fit)")
    print(f"  baseline {{or,draw,lbs,age}} : {base_w:6.2%}")
    print(f"  handicap-solo (varying)    : {hc_w:6.2%}")
    print(f"  movement                   : {hc_w - base_w:+.2%}")
    print("=" * 72)

    # ---- Brier vs BSP + LAY target, per split, for handicap-solo blend -----
    hc = results["handicap-solo (varying)"]
    for split_name, srows, blp, s1p, bspmp in (
            ("VALIDATION 2024", va, hc["bl_va"], hc["p_va"], bsp_va),
            ("HOLDOUT 2025-26", ho, hc["bl_ho"], hc["p_ho"], bsp_ho)):
        print(f"\n################  {split_name}  ################")
        # Brier on runners where blend prob exists (market-valid)
        bmask = [bl is not None for bl in blp]
        bl_brier = brier(srows, blp, bmask)
        bsp_brier = brier(srows, bspmp, bmask)
        print(f"\n--- Proper score (Brier, lower=better; market-valid runners) ---")
        print(f"  blend Brier : {bl_brier:.5f}")
        print(f"  BSP   Brier : {bsp_brier:.5f}")
        print(f"  -> blend {'BEATS' if bl_brier < bsp_brier else 'does NOT beat'}"
              f" BSP (expect: approaches, does not beat).")
        print_lay_block(split_name, srows, blp, s1p)

    print("\nNOTE: lay CLV>0 means selections drifted OUT after we laid (good for a "
          "layer). The real test is blend/stage1 lay-selected vs lay-ALL baseline.\n"
          "PRIOR: modest at best; a LARGE jump => re-check leakage, do not celebrate.")


if __name__ == "__main__":
    main()
