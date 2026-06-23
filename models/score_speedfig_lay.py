#!/usr/bin/env python3
"""score_speedfig_lay.py -- SOLO speed-figure-features test on the LAY target.

Reads data/joined/joined_gb_2018_2026_sf.csv, restricts to the FLAT FIGURED
subset (sf_is_flat==1: flat runs with a valid lengths-derived finish time), and
answers the Phase-3 question for the speed-figure feature set ALONE (no rolling,
no handicap -- clean attribution, to be combined with other families later):

  1. Does the speedfig-features Stage-1 move the Benter blend weight off the
     baseline (~6.9% reference)?  Baseline = Stage-1 on {or,draw,lbs,age}.
     Solo = Stage-1 on the runner-VARYING speed-figure features.
  2. Blend Brier vs BSP (does the blend approach but not beat the market?).
  3. The LAY target via the ESTABLISHED kill-test rig:
       lay-ALL@BSP    = the correct NULL (strike=settle=close) ~= -commission
       lay-ALL@wap    = baseline carrying the WAP-vs-close timing artifact
       blend lay-selected / stage1 lay-selected = the actual signal test
     VALIDATION (2024) and HOLDOUT (2025-26) reported separately.

PROTOCOL (out-of-sample)
  TRAIN   = seasons <= 2023   (fit Stage-1 betas AND the Benter a,b here)
  VAL     = 2024              (reported separately)
  HOLDOUT = 2025-2026         (reported separately)
Standardisation stats and blend weights are LEARNED ON TRAIN ONLY and applied
frozen to val/holdout. Speed-figure pars were ALSO train-only (see build_speedfig).

LEAKAGE: Stage-1 uses only runner-VARYING speed-figure features (all are
strictly-prior-run windowed; proven within-race Spearman -0.03..-0.20, nowhere
near rpr -0.91). The market leg is the pre-off WAP (struck), NEVER BSP. BSP is
the scorer.

LAY mechanics (5% commission on layer winnings):
  lay value rule : lay where struck < 1/p  (market price shorter than fair)
  lay CLV        : bsp/struck - 1           (>0 = drifted out after we laid = good)
  lay P&L (1u)   : horse loses -> +1*(1-comm) ; horse wins -> -(struck-1)
  NULL           : lay-ALL@BSP (struck=bsp) => CLV identically 0, ROI = -commission
                   drag. ANY large lay ROI/CLV is the WAP-vs-close timing artifact
                   common to the lay-ALL@wap baseline, NOT skill.
"""
import os
import csv
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_sf.csv")
COMMISSION = 0.05

# Stage-1 feature sets ------------------------------------------------------
BASELINE_FEATS = ["or", "draw", "lbs", "age"]              # public baseline
SF_BASE_FEATS = ["sf_last", "sf_best3", "sf_avg3", "sf_trend", "sf_vs_classpar"]
SF_GOING_FEATS = ["sf_on_todays_going", "sf_going_delta", "going_switch_flag"]
SF_FEATS = SF_BASE_FEATS + SF_GOING_FEATS                  # full set (base + going)


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
            if r.get("sf_is_flat") != "1":
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
    return p[inv]


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
    keep = [i for i in range(len(rows))
            if mkt_prob[i] and mkt_prob[i] > 0 and model_prob[i] > 0]
    sub = [rows[i] for i in keep]
    X = np.column_stack([np.log([model_prob[i] for i in keep]),
                         np.log([mkt_prob[i] for i in keep])])
    y = np.array([rows[i]["won"] for i in keep])
    return cond_logit_fit(X, y, sub, l2=l2, iters=2000)


def blend_prob(rows, model_prob, mkt_prob, beta):
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


def lay_metrics(rows, selected, struck_key="wap"):
    """Lay metrics over runners where selected[i] is True.
    struck = rows[i][struck_key]; close = bsp. For the @BSP null use struck_key='bsp'."""
    clvs, drifts, pnl, beat, nwin = [], [], 0.0, 0, 0
    n = 0
    for i, r in enumerate(rows):
        if not selected[i]:
            continue
        struck, bsp = r[struck_key], r["bsp"]
        if not struck or struck <= 1.0 or not bsp or bsp <= 1.0:
            continue
        n += 1
        clv = bsp / struck - 1.0
        clvs.append(clv)
        drifts.append(bsp / struck - 1.0)
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


def lay_select(rows, prob, struck_key="wap"):
    """Lay-value rule: lay where struck < 1/p (market price shorter than fair)."""
    sel = [False] * len(rows)
    for i, r in enumerate(rows):
        p, struck = prob[i], r[struck_key]
        if p and p > 0 and struck and struck > 1.0 and struck < 1.0 / p:
            sel[i] = True
    return sel


def print_lay_block(title, rows, blend_p, s1_p):
    print(f"\n--- LAY target: {title} ---")
    hdr = (f"  {'strategy':<24}{'struck':>7}{'n':>7}{'mean CLV':>10}{'med CLV':>9}"
           f"{'beat':>7}{'med drift':>10}{'lay ROI':>9}")
    print(hdr)
    valid = [bool(r["wap"] and r["wap"] > 1.0 and r["bsp"] and r["bsp"] > 1.0)
             for r in rows]
    rep = [
        ("lay-ALL @BSP (NULL)", valid, "bsp"),       # strike=settle=close => -comm
        ("lay-ALL @wap (baseline)", valid, "wap"),   # carries WAP-vs-close artifact
        ("blend lay-selected", lay_select(rows, blend_p, "wap"), "wap"),
        ("stage1 lay-selected", lay_select(rows, s1_p, "wap"), "wap"),
    ]
    for name, sel, sk in rep:
        m = lay_metrics(rows, sel, struck_key=sk)
        if m is None:
            print(f"  {name:<24}{sk:>7}{'--':>7}")
            continue
        print(f"  {name:<24}{sk:>7}{m['n']:>7}{m['mean_clv']:>9.2%}"
              f"{m['median_clv']:>8.2%}{m['pct_beat']:>7.1%}"
              f"{m['median_drift']:>9.2%}{m['roi']:>9.2%}")


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
    print(f"FLAT FIGURED rows: {len(rows)}  "
          f"(train<=2023 {len(tr)} | val2024 {len(va)} | holdout2025-26 {len(ho)})")

    wap_tr, wap_va, wap_ho = (market_prob(tr, "wap"), market_prob(va, "wap"),
                              market_prob(ho, "wap"))
    bsp_va, bsp_ho = market_prob(va, "bsp"), market_prob(ho, "bsp")

    results = {}
    for name, feats in (("baseline {or,draw,lbs,age}", BASELINE_FEATS),
                        ("speedfig-base (no going)", SF_BASE_FEATS),
                        ("speedfig-solo (varying)", SF_FEATS)):
        beta, p_tr, p_va, p_ho = run_stage1(name, feats, tr, va, ho)
        bb = blend_fit(tr, p_tr, wap_tr)
        a, b = bb
        weight = a / (a + b) if (a + b) != 0 else float("nan")
        bl_va = blend_prob(va, p_va, wap_va, bb)
        bl_ho = blend_prob(ho, p_ho, wap_ho, bb)
        results[name] = {
            "beta": beta, "a": a, "b": b, "weight": weight,
            "p_va": p_va, "p_ho": p_ho, "bl_va": bl_va, "bl_ho": bl_ho,
            "feats": feats,
        }
        print(f"\n=== Stage-1 = {name} ===")
        print(f"  Benter blend weights (fitted on TRAIN): a(model)={a:+.4f}  "
              f"b(market)={b:+.4f}")
        print(f"  -> MODEL WEIGHT a/(a+b) = {weight:6.2%}   "
              f"(baseline reference ~6.9%)")
        if name.startswith("speedfig"):
            print("  Stage-1 betas (z-standardised; sign: higher util => more likely win):")
            for fn, bv in zip(feats, beta):
                print(f"      {fn:20s} {bv:+.4f}")

    base_w = results["baseline {or,draw,lbs,age}"]["weight"]
    sfb_w = results["speedfig-base (no going)"]["weight"]
    sf_w = results["speedfig-solo (varying)"]["weight"]
    print("\n" + "=" * 72)
    print("THE ONE NUMBER -- Stage-1 model weight in the Benter blend (TRAIN-fit)")
    print(f"  baseline {{or,draw,lbs,age}}    : {base_w:6.2%}")
    print(f"  speedfig-base (no going)      : {sfb_w:6.2%}   "
          f"(vs baseline {sfb_w - base_w:+.2%})")
    print(f"  speedfig-full (base + going)  : {sf_w:6.2%}   "
          f"(vs baseline {sf_w - base_w:+.2%})")
    print(f"  movement vs baseline          : {sf_w - base_w:+.2%}  "
          f"({'RISE -- first positive signal, RE-CHECK leakage' if sf_w > base_w else 'fall'})")
    print("-" * 72)
    print("GOING-INTERACTION CONTRIBUTION (the betting-level test of the whisper)")
    print(f"  base-only -> full (adding going feats) : {sf_w - sfb_w:+.2%}")
    print("  (leakage proof: sf_going_delta partial on sf_avg3 = -0.033 -- orthogonal")
    print("   but tiny. Does that whisper survive into the blend weight, or vanish?)")
    print("=" * 72)

    sf = results["speedfig-solo (varying)"]
    for split_name, srows, blp, s1p, bspmp in (
            ("VALIDATION 2024", va, sf["bl_va"], sf["p_va"], bsp_va),
            ("HOLDOUT 2025-26", ho, sf["bl_ho"], sf["p_ho"], bsp_ho)):
        print(f"\n################  {split_name}  ################")
        bmask = [bl is not None for bl in blp]
        bl_brier = brier(srows, blp, bmask)
        bsp_brier = brier(srows, bspmp, bmask)
        print(f"\n--- Proper score (Brier, lower=better; market-valid runners) ---")
        print(f"  blend Brier : {bl_brier:.5f}")
        print(f"  BSP   Brier : {bsp_brier:.5f}")
        print(f"  -> blend {'BEATS' if bl_brier < bsp_brier else 'does NOT beat'}"
              f" BSP (expect: approaches, does not beat).")
        print_lay_block(split_name, srows, blp, s1p)

    print("\nNOTE: the NULL is lay-ALL@BSP (~ -commission). Any large lay ROI/CLV at "
          "wap is the WAP-vs-close timing artifact, COMMON to the lay-ALL@wap baseline,\n"
          "NOT skill. Real signal = blend/stage1 lay-selected beating the lay-ALL@wap "
          "baseline by more than the selection is just a market filter.\n"
          "PRIOR: a blend-weight RISE off ~6.9% would be the first positive signal -- "
          "treat as exciting BUT re-check construction for within-race-ranking leak.")


if __name__ == "__main__":
    main()
