#!/usr/bin/env python3
"""score_weather_lay.py -- SOLO weather/visibility probe on the LAY rig.

Block 5 (reduced, visibility-only). The Block-4 gate showed true fog (<1km) is
far too rare (4 val / 7 holdout races) to test as a race-level flag, AND a
race-CONSTANT flag cancels in a conditional logit anyway. So this scores the only
identifiable, powered weather signal:

  (A) Stage-1 blend-weight test -- does a visibility x draw INTERACTION move the
      Benter blend weight off the baseline {or,draw,lbs,age}? (flat/AW only, where
      draw exists). vis x draw VARIES within race so it is identifiable.
        neg_log_vis      = -ln(visibility)   (higher = foggier; race-constant)
        vis_x_draw       = z(neg_log_vis) * (draw_norm-0.5)
        fog5k_x_draw     = 1[vis<5000m] * (draw_norm-0.5)
  (B) Market-efficiency SEGMENTATION -- bucket races by visibility band and ask:
      is the market (BSP) less efficient, or does the blend beat it, when it is
      foggier? This catches a RACE-LEVEL effect the interaction cannot.

PROTOCOL (identical to score_speedfig_lay): TRAIN<=2023 (here effectively the
covered 2022-23 subset) fits Stage-1 betas AND the Benter a,b; VAL 2024 and
HOLDOUT 2025-26 reported separately; stats frozen from train. Covered window only
(rows with a visibility reading). LAY kill-test: lay-ALL@BSP is the NULL
(~ -commission); any large lay ROI/CLV at wap is the WAP-vs-close timing artifact.
BSP is the scorer, never a model input.
"""
import os
import csv
import math
import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_wx.csv")
COMMISSION = 0.05

BASELINE_FEATS = ["or", "draw", "lbs", "age"]
WX_FEATS = ["or", "draw", "lbs", "age", "vis_x_draw", "fog5k_x_draw"]


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
def load():
    """Covered-window, flat/AW rows (draw_norm present) with a visibility reading.
    Precompute interaction features into each row's raw dict."""
    rows = []
    with open(SRC, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("wx_in_window") != "1":
                continue
            vis = fnum(r.get("wx_visibility"))
            dn = fnum(r.get("draw_norm"))
            nlv = fnum(r.get("neg_log_vis"))
            if vis is None or dn is None or nlv is None:
                continue  # interaction test needs draw (flat/AW) + visibility
            # interaction building blocks (z-scoring of neg_log_vis done in build_X
            # via the 'neg_log_vis' stat; here store raw products, standardised later)
            r["neg_log_vis"] = nlv
            r["vis_x_draw"] = nlv * (dn - 0.5)
            r["fog5k_x_draw"] = (1.0 if vis < 5000 else 0.0) * (dn - 0.5)
            rid = f"{r['date']}|{r['course']}|{r['off']}"
            rows.append({
                "rid": rid,
                "year": int(r["date"][:4]),
                "won": 1.0 if (r.get("pos") or "").strip() == "1" else 0.0,
                "bsp": fnum(r.get("bsp")),
                "wap": fnum(r.get("wap")),
                "vis": vis,
                "raw": r,
            })
    return rows


def split(rows):
    tr = [r for r in rows if r["year"] <= 2023]
    va = [r for r in rows if r["year"] == 2024]
    ho = [r for r in rows if r["year"] >= 2025]
    return tr, va, ho


# ---- feature matrix: race-mean impute -> z (stats frozen from train) -------- #
def fit_stats(rows, feats):
    by_race = {}
    for i, r in enumerate(rows):
        by_race.setdefault(r["rid"], []).append(i)
    stats = {}
    for f in feats:
        vals = [fnum(rows[i]["raw"].get(f)) for i in range(len(rows))]
        present = [v for v in vals if v is not None]
        gmean = sum(present) / len(present) if present else 0.0
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


# ---- conditional logit (vectorised) ---------------------------------------- #
def _segments(rows):
    perm = np.array(sorted(range(len(rows)), key=lambda i: rows[i]["rid"]))
    rids = [rows[i]["rid"] for i in perm]
    seg_starts, seg_lens, i = [], [], 0
    while i < len(rids):
        j = i
        while j < len(rids) and rids[j] == rids[i]:
            j += 1
        seg_starts.append(i)
        seg_lens.append(j - i)
        i = j
    return perm, np.array(seg_starts), np.array(seg_lens)


def _race_softmax(u, ss, sl):
    mx = np.maximum.reduceat(u, ss)
    e = np.exp(u - np.repeat(mx, sl))
    denom = np.add.reduceat(e, ss)
    return e / np.repeat(denom, sl)


def cond_logit_fit(X, y, rows, l2=1.0, iters=800):
    perm, ss, sl = _segments(rows)
    Xs, ys = X[perm], y[perm]
    beta = np.zeros(X.shape[1])

    def nll_grad(b):
        p = _race_softmax(Xs @ b, ss, sl)
        nll = -np.sum(ys * np.log(np.clip(p, 1e-12, None))) + l2 * np.sum(b * b)
        return nll, Xs.T @ (p - ys) + 2 * l2 * b

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
    p = _race_softmax((X[perm]) @ beta, ss, sl)
    return p[inv]


def market_prob(rows, key):
    by_race = {}
    for i, r in enumerate(rows):
        by_race.setdefault(r["rid"], []).append(i)
    mp = [None] * len(rows)
    for idxs in by_race.values():
        inv = [(1.0 / rows[i][key]) if (rows[i][key] and rows[i][key] > 1.0)
               else None for i in idxs]
        z = sum(v for v in inv if v is not None)
        if z <= 0:
            continue
        for i, v in zip(idxs, inv):
            mp[i] = (v / z) if v is not None else None
    return mp


def blend_fit(rows, mp_model, mp_mkt, l2=1.0):
    keep = [i for i in range(len(rows))
            if mp_mkt[i] and mp_mkt[i] > 0 and mp_model[i] and mp_model[i] > 0]
    sub = [rows[i] for i in keep]
    X = np.column_stack([np.log([mp_model[i] for i in keep]),
                         np.log([mp_mkt[i] for i in keep])])
    y = np.array([rows[i]["won"] for i in keep])
    return cond_logit_fit(X, y, sub, l2=l2, iters=2000)


def blend_prob(rows, mp_model, mp_mkt, beta):
    keep = [i for i in range(len(rows))
            if mp_mkt[i] and mp_mkt[i] > 0 and mp_model[i] and mp_model[i] > 0]
    sub = [rows[i] for i in keep]
    X = np.column_stack([np.log([mp_model[i] for i in keep]),
                         np.log([mp_mkt[i] for i in keep])])
    p = cond_logit_prob(X, beta, sub)
    out = [None] * len(rows)
    for i, pi in zip(keep, p):
        out[i] = float(pi)
    return out


# ---- scoring --------------------------------------------------------------- #
def brier(rows, prob, mask=None):
    se, n = 0.0, 0
    for i, r in enumerate(rows):
        if prob[i] is None or (mask is not None and not mask[i]):
            continue
        se += (prob[i] - r["won"]) ** 2
        n += 1
    return (se / n) if n else float("nan"), n


def lay_select(rows, prob, key="wap"):
    sel = [False] * len(rows)
    for i, r in enumerate(rows):
        p, s = prob[i], r[key]
        if p and p > 0 and s and s > 1.0 and s < 1.0 / p:
            sel[i] = True
    return sel


def lay_metrics(rows, selected, key="wap"):
    clvs, pnl, beat, n, nwin = [], 0.0, 0, 0, 0
    for i, r in enumerate(rows):
        if not selected[i]:
            continue
        s, bsp = r[key], r["bsp"]
        if not s or s <= 1.0 or not bsp or bsp <= 1.0:
            continue
        n += 1
        clvs.append(bsp / s - 1.0)
        if s < bsp:
            beat += 1
        pnl += (-(s - 1.0)) if r["won"] else (1.0 - COMMISSION)
    if not n:
        return None
    return {"n": n, "mean_clv": float(np.mean(clvs)),
            "median_clv": float(np.median(clvs)), "pct_beat": beat / n,
            "roi": pnl / n}


def print_lay_block(title, rows, blend_p, s1_p):
    print(f"\n--- LAY target: {title} ---")
    print(f"  {'strategy':<24}{'struck':>7}{'n':>7}{'mean CLV':>10}{'med CLV':>9}"
          f"{'beat':>7}{'lay ROI':>9}")
    valid = [bool(r["wap"] and r["wap"] > 1.0 and r["bsp"] and r["bsp"] > 1.0)
             for r in rows]
    rep = [("lay-ALL @BSP (NULL)", valid, "bsp"),
           ("lay-ALL @wap (baseline)", valid, "wap"),
           ("blend lay-selected", lay_select(rows, blend_p, "wap"), "wap"),
           ("stage1 lay-selected", lay_select(rows, s1_p, "wap"), "wap")]
    for name, sel, sk in rep:
        m = lay_metrics(rows, sel, key=sk)
        if m is None:
            print(f"  {name:<24}{sk:>7}{'--':>7}")
            continue
        print(f"  {name:<24}{sk:>7}{m['n']:>7}{m['mean_clv']:>9.2%}"
              f"{m['median_clv']:>8.2%}{m['pct_beat']:>7.1%}{m['roi']:>9.2%}")


def run_stage1(feats, tr, va, ho):
    stats = fit_stats(tr, feats)
    Xtr, Xva, Xho = (build_X(tr, feats, stats), build_X(va, feats, stats),
                     build_X(ho, feats, stats))
    beta = cond_logit_fit(Xtr, np.array([r["won"] for r in tr]), tr)
    return (beta,
            list(cond_logit_prob(Xtr, beta, tr)),
            list(cond_logit_prob(Xva, beta, va)),
            list(cond_logit_prob(Xho, beta, ho)))


# ---- (B) market-efficiency segmentation by visibility band ----------------- #
VIS_BANDS = [(0, 2000, "<2km (fog/thick)"), (2000, 5000, "2-5km (mist)"),
             (5000, 10000, "5-10km (hazy)"), (10000, 1e9, ">10km (clear)")]


def segment_by_visibility(title, rows, blend_p, bsp_mp):
    print(f"\n--- (B) MARKET-EFFICIENCY by visibility band: {title} ---")
    print(f"  {'band':<20}{'races':>7}{'runners':>9}{'BSP Brier':>11}"
          f"{'blend Brier':>13}{'blend-BSP':>11}")
    for lo, hi, name in VIS_BANDS:
        idx = [i for i, r in enumerate(rows) if lo <= r["vis"] < hi]
        if not idx:
            print(f"  {name:<20}{0:>7}")
            continue
        races = len(set(rows[i]["rid"] for i in idx))
        mask = [False] * len(rows)
        for i in idx:
            mask[i] = True
        bsp_b, n1 = brier(rows, bsp_mp, mask)
        bl_b, n2 = brier(rows, blend_p, mask)
        diff = bl_b - bsp_b
        flag = "  <-- blend beats BSP" if diff < 0 else ""
        print(f"  {name:<20}{races:>7}{len(idx):>9}{bsp_b:>11.5f}"
              f"{bl_b:>13.5f}{diff:>+11.5f}{flag}")


# --------------------------------------------------------------------------- #
def main():
    rows = load()
    tr, va, ho = split(rows)
    print(f"Covered-window flat/AW rows with visibility: {len(rows)}")
    print(f"  train<=2023(covered 2022-23) {len(tr)} | val2024 {len(va)} "
          f"| holdout2025-26 {len(ho)}")

    wap_tr, wap_va, wap_ho = (market_prob(tr, "wap"), market_prob(va, "wap"),
                              market_prob(ho, "wap"))
    bsp_va, bsp_ho = market_prob(va, "bsp"), market_prob(ho, "bsp")

    results = {}
    for name, feats in (("baseline {or,draw,lbs,age}", BASELINE_FEATS),
                        ("weather (+vis x draw)", WX_FEATS)):
        beta, p_tr, p_va, p_ho = run_stage1(feats, tr, va, ho)
        bb = blend_fit(tr, p_tr, wap_tr)
        a, b = bb
        weight = a / (a + b) if (a + b) != 0 else float("nan")
        results[name] = {"beta": beta, "weight": weight, "feats": feats,
                         "p_va": p_va, "p_ho": p_ho,
                         "bl_va": blend_prob(va, p_va, wap_va, bb),
                         "bl_ho": blend_prob(ho, p_ho, wap_ho, bb)}
        print(f"\n=== Stage-1 = {name} ===")
        print(f"  Benter weights (TRAIN): a(model)={a:+.4f} b(market)={b:+.4f}"
              f"  -> MODEL WEIGHT {weight:6.2%}")
        if "weather" in name:
            print("  Stage-1 betas (z; interaction = does fog change draw edge):")
            for fn, bv in zip(feats, beta):
                print(f"      {fn:16s} {bv:+.4f}")

    base_w = results["baseline {or,draw,lbs,age}"]["weight"]
    wx_w = results["weather (+vis x draw)"]["weight"]
    print("\n" + "=" * 72)
    print("(A) THE ONE NUMBER -- Stage-1 model weight in the Benter blend")
    print(f"  baseline {{or,draw,lbs,age}}        : {base_w:6.2%}")
    print(f"  weather (+ vis x draw interaction) : {wx_w:6.2%}   "
          f"(vs baseline {wx_w - base_w:+.2%})")
    print(f"  -> {'RISE -- recheck leak' if wx_w > base_w else 'no rise / fall'}"
          " (prior: no mechanism at testable thresholds => expect ~0 / priced)")
    print("=" * 72)

    wx = results["weather (+vis x draw)"]
    for split_name, srows, blp, s1p, bspmp in (
            ("VALIDATION 2024", va, wx["bl_va"], wx["p_va"], bsp_va),
            ("HOLDOUT 2025-26", ho, wx["bl_ho"], wx["p_ho"], bsp_ho)):
        print(f"\n################  {split_name}  ################")
        bmask = [bl is not None for bl in blp]
        bl_b, _ = brier(srows, blp, bmask)
        bsp_b, _ = brier(srows, bspmp, bmask)
        print(f"\n--- Proper score (Brier; market-valid runners) ---")
        print(f"  blend Brier : {bl_b:.5f}   BSP Brier : {bsp_b:.5f}   "
              f"-> blend {'BEATS' if bl_b < bsp_b else 'does NOT beat'} BSP")
        print_lay_block(split_name, srows, blp, s1p)
        segment_by_visibility(split_name, srows, blp, bspmp)

    print("\nNULL reminder: lay-ALL@BSP ~ -commission; large lay ROI/CLV at wap is "
          "the WAP-vs-close timing artifact, NOT skill. (A) tests within-race fog x "
          "draw; (B) tests whether foggier races are mispriced at race level.")


if __name__ == "__main__":
    main()
