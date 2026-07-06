"""Pre-off Gate 2 (edge) verdicts for Q2/Q3/Q6 from the extracted records.

Consumes ``models/gate_preoff_gate2_records.pkl`` (one row per qualifying GB-flat runner,
built by gate_preoff.extract_preoff_gate2). Applies, per the locked §12 amendment:
  * Q2 — logistic direction model on T-10min ladder features; verdict on holdout AND an
         odd/even-week split (disagreement = fail); bar = beat the band-stratified baseline
         drift by >= 2 ticks AND net-2%-commission > 0.
  * Q3 — frozen strike (3rd-best-back @ T-10min); CLV = struck/BSP - 1 vs a price-band x
         course-stratified null; holdout verdict.
  * Q6 — passive-quote P&L (entry vs T-10min hedge touch) net 2%; vs zero AND band null;
         + post-fill adverse-selection diagnostic (report only).
  * S1-S3 slices (sprints <=6f / small fields <=8 / handicaps), Benjamini-Hochberg as one
         family, reported for each surviving question.

Definitions are documented inline and echoed into the report; where the brief was terse the
choice is flagged. Verdict logic is unit-tested (test_gate_preoff_analysis.py) on synthetic
inputs before it is trusted on real records. numpy only (no sklearn dependency).
"""
from __future__ import annotations

import datetime as _dt
import math
from collections import defaultdict
from typing import List, Optional

import numpy as np

from backtest.pro_stream import _TICK_BANDS  # noqa: F401  (ladder source of truth)
from backtest.pro_stream import ticks_move

COMMISSION = 0.02
DISCOVERY_END = "2015-12-31"          # discovery <= this; holdout > this (within window)
BSP_BANDS = [(1.0, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 10.0), (10.0, 20.0), (20.0, 1000.0)]


# --------------------------------------------------------------------------- #
# small helpers                                                               #
# --------------------------------------------------------------------------- #
def price_band(p: Optional[float]) -> Optional[str]:
    if p is None:
        return None
    for lo, hi in BSP_BANDS:
        if lo <= p < hi:
            return f"{lo:g}-{hi:g}"
    return None


def week_parity(date_str: str) -> int:
    """0/1 by ISO week number — the odd/even-week robustness split."""
    y, m, d = (int(x) for x in date_str.split("-"))
    return _dt.date(y, m, d).isocalendar()[1] % 2


def ticks_between(p_from: Optional[float], p_to: Optional[float]) -> Optional[float]:
    """Signed Betfair ticks from p_from to p_to (positive = odds got BIGGER/drifted).

    Counts ladder steps; robust to the non-uniform tick grid.
    """
    if p_from is None or p_to is None or p_from <= 1.0 or p_to <= 1.0:
        return None
    lo, hi, sign = (p_from, p_to, 1.0) if p_to >= p_from else (p_to, p_from, -1.0)
    n = 0
    p = round(lo, 2)
    hi = round(hi, 2)
    while p < hi - 1e-9 and n < 5000:
        p = ticks_move(p, 1)
        n += 1
    return sign * n


def in_discovery(date_str: str) -> bool:
    return date_str <= DISCOVERY_END


def bh_reject(pvals, alpha=0.05):
    """Benjamini-Hochberg: return a boolean list of rejections at FDR alpha."""
    idx = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = len(pvals)
    reject = [False] * m
    kmax = -1
    for rank, i in enumerate(idx, start=1):
        if pvals[i] <= alpha * rank / m:
            kmax = rank
    for rank, i in enumerate(idx, start=1):
        if rank <= kmax:
            reject[i] = True
    return reject


def _mean_se(x):
    x = np.asarray([v for v in x if v is not None and not (isinstance(v, float) and math.isnan(v))], float)
    if len(x) == 0:
        return 0.0, 0.0, 0
    return float(x.mean()), float(x.std(ddof=1) / math.sqrt(len(x))) if len(x) > 1 else 0.0, len(x)


def _p_two_sided(mean, se):
    if se == 0:
        return 1.0
    z = abs(mean / se)
    return math.erfc(z / math.sqrt(2))       # normal two-sided


# --------------------------------------------------------------------------- #
# logistic regression (numpy, L2, IRLS-ish gradient descent)                  #
# --------------------------------------------------------------------------- #
def fit_logistic(X, y, l2=1.0, iters=300, lr=0.1):
    X = np.asarray(X, float)
    y = np.asarray(y, float)
    mu = X.mean(0)
    sd = X.std(0)
    sd[sd == 0] = 1.0
    Xs = (X - mu) / sd
    Xs = np.hstack([np.ones((len(Xs), 1)), Xs])
    w = np.zeros(Xs.shape[1])
    for _ in range(iters):
        p = 1.0 / (1.0 + np.exp(-Xs @ w))
        g = Xs.T @ (p - y) / len(y) + l2 * np.r_[0, w[1:]] / len(y)
        w -= lr * g
    return {"w": w, "mu": mu, "sd": sd}


def predict_logistic(model, X):
    X = np.asarray(X, float)
    Xs = (X - model["mu"]) / model["sd"]
    Xs = np.hstack([np.ones((len(Xs), 1)), Xs])
    return 1.0 / (1.0 + np.exp(-Xs @ model["w"]))


# --------------------------------------------------------------------------- #
# Q2 — pre-off ladder momentum -> final-10-min direction                      #
# --------------------------------------------------------------------------- #
def _q2_rows(records):
    rows = []
    for r in records:
        mom = ticks_between(r.get("best_back_t11"), r.get("best_back_t10"))
        mid10, midoff = r.get("mid_t10"), r.get("mid_off")
        imb, t10, t11 = r.get("imbalance_t10"), r.get("trd_t10"), r.get("trd_t11")
        if None in (mom, mid10, midoff, imb, t10, t11) or mid10 <= 1 or midoff <= 1:
            continue
        rows.append({
            "date": r["date"], "venue": r.get("venue"), "band": price_band(mid10),
            "field": r.get("field"), "dist_f": r.get("dist_f"), "is_hcap": r.get("is_hcap"),
            "f_mom": mom, "f_imb": math.log(imb) if imb > 0 else 0.0, "f_acc": (t10 - t11),
            "shorten": 1.0 if midoff < mid10 else 0.0,
            "drift_ticks": ticks_between(mid10, midoff), "mid10": mid10, "midoff": midoff,
        })
    return rows


def analyse_q2(records):
    rows = _q2_rows(records)
    disc = [r for r in rows if in_discovery(r["date"])]
    if len(disc) < 200:
        return {"error": "insufficient discovery", "n": len(rows)}
    model = fit_logistic([[r["f_mom"], r["f_imb"], r["f_acc"]] for r in disc],
                         [r["shorten"] for r in disc])
    band_drift = defaultdict(list)
    for r in disc:
        band_drift[r["band"]].append(r["drift_ticks"])
    band_side = {b: (1 if np.mean(v) > 0 else -1) for b, v in band_drift.items()}

    def evaluate(test):
        if not test:
            return {"n": 0, "edge_ticks_vs_baseline": 0.0, "net_return_mean": 0.0}
        p = predict_logistic(model, [[r["f_mom"], r["f_imb"], r["f_acc"]] for r in test])
        model_ticks, base_ticks, net = [], [], []
        for r, pi in zip(test, p):
            if pi > 0.5:
                mt = ticks_between(r["midoff"], r["mid10"])
                ret = (r["mid10"] - r["midoff"]) / r["midoff"]
            else:
                mt = ticks_between(r["mid10"], r["midoff"])
                ret = (r["midoff"] - r["mid10"]) / r["mid10"]
            side = band_side.get(r["band"], 1)
            bt = (ticks_between(r["mid10"], r["midoff"]) if side > 0
                  else ticks_between(r["midoff"], r["mid10"]))
            model_ticks.append(mt); base_ticks.append(bt)
            net.append(ret - COMMISSION * max(ret, 0))
        edge = np.mean(model_ticks) - np.mean(base_ticks)
        m_net, se_net, n = _mean_se(net)
        return {"n": n, "edge_ticks_vs_baseline": round(float(edge), 3),
                "net_return_mean": round(m_net, 5), "net_return_se": round(se_net, 5),
                "mean_model_ticks": round(float(np.mean(model_ticks)), 3),
                "mean_baseline_ticks": round(float(np.mean(base_ticks)), 3)}

    hold = [r for r in rows if not in_discovery(r["date"])]
    even = [r for r in rows if week_parity(r["date"]) == 0]
    odd = [r for r in rows if week_parity(r["date"]) == 1]
    res = {"n_total": len(rows), "discovery": evaluate(disc), "holdout": evaluate(hold),
           "week_even": evaluate(even), "week_odd": evaluate(odd)}

    def ok(e):
        return e["n"] > 0 and e["edge_ticks_vs_baseline"] >= 2.0 and e["net_return_mean"] > 0
    res["verdict"] = ("PASS" if (ok(res["holdout"]) and ok(res["week_even"])
                                 and ok(res["week_odd"])) else "FAIL")
    return res


# --------------------------------------------------------------------------- #
# Q3 — frozen timestamped-strike CLV vs band x course null                    #
# --------------------------------------------------------------------------- #
def analyse_q3(records):
    rows = []
    for r in records:
        struck, bsp = r.get("q3_entry"), r.get("bsp")
        if struck is None or bsp is None or bsp <= 1 or struck <= 1:
            continue
        rows.append({"date": r["date"], "venue": r.get("venue"), "band": price_band(bsp),
                     "clv": struck / bsp - 1.0, "field": r.get("field"),
                     "dist_f": r.get("dist_f"), "is_hcap": r.get("is_hcap")})
    disc = [r for r in rows if in_discovery(r["date"])]
    hold = [r for r in rows if not in_discovery(r["date"])]

    def edges(subset):
        cell = defaultdict(list)
        for r in subset:
            cell[(r["band"], r["venue"])].append(r["clv"])
        cmean = {k: np.mean(v) for k, v in cell.items()}
        return [r["clv"] - cmean[(r["band"], r["venue"])] for r in subset]

    def summ(subset):
        raw = _mean_se([r["clv"] for r in subset])
        edg = _mean_se(edges(subset))
        return {"n": raw[2], "raw_clv_mean": round(raw[0], 5),
                "edge_vs_band_course_null": round(edg[0], 6), "edge_se": round(edg[1], 6),
                "p": round(_p_two_sided(edg[0], edg[1]), 4)}

    res = {"n_total": len(rows), "discovery": summ(disc), "holdout": summ(hold)}
    h, d = res["holdout"], res["discovery"]
    res["verdict"] = ("PASS" if (h["edge_vs_band_course_null"] > 0 and h["p"] < 0.05
                                 and d["edge_vs_band_course_null"] > 0) else "FAIL")
    res["note"] = "CLV vs band-course null (price-only); Brier needs win/loss (not extracted)."
    return res


# --------------------------------------------------------------------------- #
# Q6 — passive-quote P&L (entry vs T-10min hedge), net 2%, vs zero + band null #
# --------------------------------------------------------------------------- #
def _q6_pnl(entry, hedge, side):
    if not entry or not hedge or entry <= 1 or hedge <= 1:
        return None
    gross = (entry - hedge) / hedge if side == "back" else (hedge - entry) / entry
    return gross - COMMISSION * max(gross, 0)


def analyse_q6(records):
    rows = []
    for r in records:
        for side, ent, hed, filled in (
                ("back", r.get("q6_back_entry"), r.get("q6_hedge_lay"), r.get("q6_back_fill")),
                ("lay", r.get("q6_lay_entry"), r.get("q6_hedge_back"), r.get("q6_lay_fill"))):
            if not filled:
                continue
            pnl = _q6_pnl(ent, hed, side)
            if pnl is None:
                continue
            rows.append({"date": r["date"], "venue": r.get("venue"), "band": price_band(ent),
                         "pnl": pnl, "side": side, "field": r.get("field"),
                         "dist_f": r.get("dist_f"), "is_hcap": r.get("is_hcap")})
    disc = [r for r in rows if in_discovery(r["date"])]
    hold = [r for r in rows if not in_discovery(r["date"])]

    def band_edge(subset):
        cell = defaultdict(list)
        for r in subset:
            cell[(r["band"], r["venue"])].append(r["pnl"])
        cmean = {k: np.mean(v) for k, v in cell.items()}
        return _mean_se([r["pnl"] - cmean[(r["band"], r["venue"])] for r in subset])

    def summ(subset):
        raw = _mean_se([r["pnl"] for r in subset])
        edg = band_edge(subset)
        return {"n": raw[2], "pnl_vs_zero_mean": round(raw[0], 6), "pnl_se": round(raw[1], 6),
                "p_vs_zero": round(_p_two_sided(raw[0], raw[1]), 4),
                "edge_vs_band_null": round(edg[0], 6), "edge_p": round(_p_two_sided(edg[0], edg[1]), 4)}

    res = {"n_filled": len(rows), "discovery": summ(disc), "holdout": summ(hold)}
    h = res["holdout"]
    res["verdict"] = ("PASS" if (h["pnl_vs_zero_mean"] > 0 and h["p_vs_zero"] < 0.05
                                 and h["edge_vs_band_null"] > 0) else "FAIL")

    def drift(recs_):
        segs = {"t30_25": [], "t30_15": [], "t30_10": []}
        for r in recs_:
            e = r.get("q6_back_entry")
            if e is None or not r.get("q6_back_fill"):
                continue
            for k, lbl in (("t30_25", "best_back_t25m"), ("t30_15", "best_back_t15m"),
                           ("t30_10", "best_back_t10")):
                segs[k].append(ticks_between(e, r.get(lbl)))
        return {k: round(_mean_se(v)[0], 3) for k, v in segs.items()}

    res["adverse_selection_filled_back"] = drift(records)
    return res


# --------------------------------------------------------------------------- #
# S1-S3 slices                                                                #
# --------------------------------------------------------------------------- #
def slice_records(records, which):
    if which == "S1_sprint":
        return [r for r in records if (r.get("dist_f") or 99) <= 6]
    if which == "S2_smallfield":
        return [r for r in records if (r.get("field") or 99) <= 8]
    if which == "S3_handicap":
        return [r for r in records if r.get("is_hcap")]
    return records


if __name__ == "__main__":
    import json
    import os
    import pickle

    ROOT = "/home/gabriel/projects/racing_project"
    recs = pickle.load(open(os.path.join(ROOT, "models/gate_preoff_gate2_records.pkl"), "rb"))
    print("records: %d" % len(recs))
    out = {"n_records": len(recs), "Q2": analyse_q2(recs), "Q3": analyse_q3(recs),
           "Q6": analyse_q6(recs)}
    slices, fam_p, fam_key = {}, [], []
    for q, fn in (("Q2", analyse_q2), ("Q3", analyse_q3), ("Q6", analyse_q6)):
        if out[q].get("verdict") != "PASS":
            continue
        for sl in ("S1_sprint", "S2_smallfield", "S3_handicap"):
            r = fn(slice_records(recs, sl))
            slices["%s:%s" % (q, sl)] = r
            hp = (r.get("holdout") or {})
            pv = hp.get("p") or hp.get("p_vs_zero")
            if isinstance(pv, (int, float)):
                fam_p.append(pv); fam_key.append("%s:%s" % (q, sl))
    if fam_p:
        for k, rj in zip(fam_key, bh_reject(fam_p)):
            slices[k]["bh_reject_at_0.05"] = bool(rj)
    out["slices"] = slices
    dest = os.path.join(ROOT, "models/gate_preoff_gate2_results.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print(json.dumps({k: out[k].get("verdict") for k in ("Q2", "Q3", "Q6")}, indent=2))
    print("wrote", dest)
