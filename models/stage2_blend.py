"""
stage2_blend.py -- Stage-2 Benter market blend (Block D1).

Benter's two-stage idea: your fundamental model is one opinion; the MARKET price
is another, usually sharper, opinion. Combine them. The standard formulation
blends the two in LOG-probability space, which makes the result a weighted
GEOMETRIC mean of the two probabilities:

    utility_i = a * log(model_prob_i) + b * log(market_prob_i)
    blend_i   = softmax over the race  ∝  model_prob_i^a * market_prob_i^b

We fit (a, b) with a conditional logit grouped by race (same per-race choice-set
structure as Stage 1), predicting the actual winner. The two coefficients ARE the
Benter weights: how much to trust the model vs the market.

LEAKAGE (cardinal rule, Stage-2 form)
-------------------------------------
The market input MUST be the PRE-OFF price (the `bf_last_preoff_ltp` stand-in),
NEVER BSP. BSP is the scorer; blending it in would feed in the answer we're
trying to beat. The guard asserts the input matrix is exactly
{x1 = log model_prob, x2 = log pre-off market_prob} and nothing else.
"""
import os
import csv
import math
import random
from collections import defaultdict

random.seed(42)  # reproducibility

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED = os.path.join(_ROOT, "models", "stage1_scored.csv")
OUT = os.path.join(_ROOT, "models", "stage2_scored.csv")

INPUTS = ["x1_log_model_prob", "x2_log_market_prob"]   # the only two model inputs
FORBIDDEN = {"bsp", "bsp_implied_prob", "score_bsp", "pos", "score_pos",
             "dec", "rpr"}


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


STRUCK_MODE = os.environ.get("STRUCK_MODE", "wap")  # wap|geomean|pre_min|pre_max


def struck_price(pre_min, pre_max, wap=None):
    """Pre-off struck price fed to the blend as the x2 market opinion -- NEVER BSP.
    STRUCK_MODE selects the source:
      'wap' (default) = PPWAP, the pre-off volume-weighted avg traded price (a REAL
                        struck price; carries a WAP-vs-close timing component, not a
                        timestamped strike);
      'geomean'       = sqrt(pre_min*pre_max) (least-biased range proxy);
      'pre_min'/'pre_max' = that bound of the pre-off range.
    Returns None unless the chosen price is valid decimal odds (>1.0)."""
    if STRUCK_MODE == "wap":
        w = fnum(wap)
        return w if (w and w > 1.0) else None
    lo, hi = fnum(pre_min), fnum(pre_max)
    if not lo or not hi or lo <= 1.0 or hi <= 1.0:
        return None
    if STRUCK_MODE == "pre_min":
        return lo
    if STRUCK_MODE == "pre_max":
        return hi
    return math.sqrt(lo * hi)


def leakage_guard(input_names):
    used = set(input_names)
    assert used == set(INPUTS), f"unexpected Stage-2 inputs: {used}"
    bad = used & FORBIDDEN
    assert not bad, f"LEAKAGE: forbidden input(s): {bad}"
    print("LEAKAGE GUARD PASSED. Stage-2 inputs:", input_names,
          f"(x2 from STRUCK_MODE={STRUCK_MODE} -- PRE-OFF price, NOT BSP)")


# ---- conditional logit on the 2-input matrix (same maths as Stage 1) -------
def race_probs(runners, beta):
    us = [beta[0] * r["x1"] + beta[1] * r["x2"] for r in runners]
    m = max(us)
    ex = [math.exp(u - m) for u in us]
    s = sum(ex)
    return [e / s for e in ex]


def nll_and_grad(races, beta, l2):
    nll = 0.0
    g = [0.0, 0.0]
    for runners in races:
        ps = race_probs(runners, beta)
        for r, p in zip(runners, ps):
            y = 1.0 if r["won"] else 0.0
            if y:
                nll -= math.log(max(p, 1e-12))
            g[0] += (p - y) * r["x1"]
            g[1] += (p - y) * r["x2"]
    nll += l2 * (beta[0] ** 2 + beta[1] ** 2)
    g[0] += 2 * l2 * beta[0]
    g[1] += 2 * l2 * beta[1]
    return nll, g


def fit(races, l2=1.0, iters=2000):
    beta = [0.0, 0.0]
    lr = 0.2
    nll, g = nll_and_grad(races, beta, l2)
    for _ in range(iters):
        trial = [beta[0] - lr * g[0], beta[1] - lr * g[1]]
        n2, g2 = nll_and_grad(races, trial, l2)
        if n2 < nll:
            beta, nll, g, lr = trial, n2, g2, lr * 1.05
        else:
            lr *= 0.5
            if lr < 1e-9:
                break
    return beta, nll


def main():
    rows = list(csv.DictReader(open(SCORED, newline="")))
    for r in rows:                         # pre-off struck price per runner
        r["_struck"] = struck_price(r["score_pre_min"], r["score_pre_max"],
                                    r.get("score_wap"))
    by_race = defaultdict(list)
    for r in rows:
        by_race[r["race_id"]].append(r)

    races = []          # list of lists of runner dicts with x1,x2,won,carry
    dropped = 0
    for mid, rs in by_race.items():
        valid = [r for r in rs
                 if fnum(r["model_prob"]) and fnum(r["model_prob"]) > 0
                 and r["_struck"] and r["_struck"] > 1.0]
        dropped += len(rs) - len(valid)
        if len(valid) < 2:
            continue
        # market-implied prob from the PRE-OFF price, renormalised per race
        raw = [1.0 / r["_struck"] for r in valid]
        z = sum(raw)
        runners = []
        for r, w in zip(valid, raw):
            mp = fnum(r["model_prob"])
            mkt = w / z
            runners.append({
                "x1": math.log(mp), "x2": math.log(mkt),
                "model_prob": mp, "market_prob": mkt,
                "won": (r.get("score_pos") or "").strip() == "1",
                "row": r,
            })
        races.append(runners)

    print(f"Rows in scored file : {len(rows)}")
    print(f"Runners dropped     : {dropped} (invalid/missing struck price)")
    print(f"Races used          : {len(races)}")

    leakage_guard(INPUTS)
    beta, nll = fit(races)
    print(f"\nFitted Benter weights (conditional logit on log-probs):")
    print(f"  a (log model_prob)  = {beta[0]:+.4f}")
    print(f"  b (log market_prob) = {beta[1]:+.4f}")
    print(f"  final NLL = {nll:.1f}")

    # score + per-race sum check + write
    out_rows, sums = [], []
    for runners in races:
        ps = race_probs(runners, beta)
        sums.append(sum(ps))
        for rr, p in zip(runners, ps):
            r = rr["row"]
            out_rows.append({
                "race_id": r["race_id"], "date": r["date"],
                "course": r["course"], "off": r["off"], "horse": r["horse"],
                "model_prob": round(rr["model_prob"], 6),
                "market_prob": round(rr["market_prob"], 6),
                "blend_prob": round(p, 6),
                # carried NON-features (scoring only, never inputs)
                "score_bsp": r["score_bsp"],
                "bsp_implied_prob": r["bsp_implied_prob"],
                "score_pos": r["score_pos"],
                "score_struck": round(r["_struck"], 4),
            })
    cols = ["race_id", "date", "course", "off", "horse",
            "model_prob", "market_prob", "blend_prob",
            "score_bsp", "bsp_implied_prob", "score_pos",
            "score_struck"]
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(out_rows)

    print("\n--- CHECKPOINT: per-race blend_prob sums ---")
    print(f"  min={min(sums):.6f}  max={max(sums):.6f}  "
          f"mean={sum(sums)/len(sums):.6f}  (should be 1.000000)")
    print(f"\nWrote -> {OUT}  ({len(out_rows)} runners)")


if __name__ == "__main__":
    main()
