"""
calibrate.py -- calibration check for the Stage-1 model vs BSP.

CALIBRATION asks a different question from "does it pick winners":
    "Of all the runners the model gave ~20%, did ~20% of them actually win?"
A model is well-calibrated if predicted probability == observed win rate in
every probability band. We bucket runners by predicted prob, then compare the
mean predicted prob against the ACTUAL win rate (pos == 1) in each bucket.

We run the IDENTICAL bucketing on the BSP-implied probability (1/BSP, already
renormalised per race in the scored file) so the model and the market sit on one
table. Expectation (and a healthy result): the model is roughly calibrated but
WORSE than BSP -- it has only a few public features, the market has everything.

Uses `pos` only to SCORE (the one legitimate use of the result), never as input.
Reads models/stage1_scored.csv; writes a text reliability chart to models/.
"""
import os
import csv

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED = os.path.join(_ROOT, "models", "stage1_scored.csv")
CHART = os.path.join(_ROOT, "models", "reliability.txt")

# Probability bands (lower inclusive, upper exclusive); last one catches >=50%.
BANDS = [(0.00, 0.02), (0.02, 0.05), (0.05, 0.10), (0.10, 0.20),
         (0.20, 0.35), (0.35, 0.50), (0.50, 1.0001)]


def band_label(lo, hi):
    hi = min(hi, 1.0)
    return f"{lo*100:.0f}-{hi*100:.0f}%"


def won(row):
    return (row.get("score_pos") or "").strip() == "1"


def calibrate(rows, prob_col):
    """Per band: n, mean predicted prob, actual win rate, diff (actual-pred)."""
    buckets = [[] for _ in BANDS]
    for r in rows:
        p = float(r[prob_col])
        for i, (lo, hi) in enumerate(BANDS):
            if lo <= p < hi:
                buckets[i].append(r)
                break
    table = []
    ece = 0.0                      # expected calibration error (n-weighted |diff|)
    n_total = len(rows)
    for (lo, hi), b in zip(BANDS, buckets):
        if not b:
            table.append((band_label(lo, hi), 0, None, None, None))
            continue
        pred = sum(float(r[prob_col]) for r in b) / len(b)
        actual = sum(1 for r in b if won(r)) / len(b)
        table.append((band_label(lo, hi), len(b), pred, actual, actual - pred))
        ece += (len(b) / n_total) * abs(actual - pred)
    return table, ece


def print_combined(model_tab, bsp_tab, model_ece, bsp_ece):
    print("\n=== CALIBRATION: model vs BSP (actual win rate by predicted band) ===")
    print(f"{'band':>8} | {'MODEL n':>7} {'pred':>7} {'actual':>7} {'diff':>7} "
          f"| {'BSP n':>6} {'pred':>7} {'actual':>7} {'diff':>7}")
    print("-" * 78)
    for m, b in zip(model_tab, bsp_tab):
        def fmt(t):
            _, n, pred, act, diff = t
            if not n:
                return f"{n:>7} {'-':>7} {'-':>7} {'-':>7}"
            return f"{n:>7} {pred:>6.1%} {act:>6.1%} {diff:>+6.1%}"
        print(f"{m[0]:>8} | {fmt(m)} | {fmt(b)[1:]}")
    print("-" * 78)
    print(f"Expected Calibration Error (n-weighted |actual-pred|): "
          f"model {model_ece:.3%}  |  BSP {bsp_ece:.3%}")
    print("Lower ECE = better calibrated. Expect BSP < model (market knows more).")


def write_chart(model_tab, bsp_tab):
    """Tiny ASCII reliability chart: predicted (x) vs actual (o) per band."""
    lines = ["Reliability (per band): p=predicted  a=actual  | each cell ~2%",
             "perfect calibration => p and a land in the same column", ""]
    for tab, name in ((model_tab, "MODEL"), (bsp_tab, "BSP  ")):
        lines.append(name)
        for label, n, pred, act, _ in tab:
            if not n:
                lines.append(f"  {label:>7} (n=0)")
                continue
            row = ["."] * 50                       # 0..100% in 2% cells
            row[min(int(pred * 50), 49)] = "p"
            ai = min(int(act * 50), 49)
            row[ai] = "P" if row[ai] == "p" else "a"   # overlap shows as P
            lines.append(f"  {label:>7} n={n:<4} |{''.join(row)}|")
        lines.append("")
    with open(CHART, "w") as f:
        f.write("\n".join(lines))
    print(f"\nWrote text reliability chart -> {CHART}")


def proper_scores(rows, prob_col):
    """Proper scores that reward calibration AND resolution (lower = better):
      * Brier   = mean over runners of (prob - won)^2.
      * log-loss = mean over races of -ln(prob assigned to the actual winner)
                   -- the conditional-logit's own multiclass loss.
    ECE can be fooled by an under-confident model that always predicts the base
    rate; these cannot -- they punish a model that fails to separate runners.
    """
    import math
    from collections import defaultdict
    brier = sum((float(r[prob_col]) - (1.0 if won(r) else 0.0)) ** 2
                for r in rows) / len(rows)
    races = defaultdict(list)
    for r in rows:
        races[r["race_id"]].append(r)   # was bf_market_id (gone in 2018-2026 schema)
    ll = 0.0
    for rs in races.values():
        for r in rs:
            if won(r):
                ll -= math.log(max(float(r[prob_col]), 1e-12))
    return brier, ll / len(races)


def main():
    rows = list(csv.DictReader(open(SCORED, newline="")))
    print(f"Loaded {len(rows)} scored runners; "
          f"{sum(1 for r in rows if won(r))} winners.")
    model_tab, model_ece = calibrate(rows, "model_prob")
    bsp_tab, bsp_ece = calibrate(rows, "bsp_implied_prob")
    print_combined(model_tab, bsp_tab, model_ece, bsp_ece)

    # Proper scores -- the honest model-vs-market comparison.
    mb, mll = proper_scores(rows, "model_prob")
    bb, bll = proper_scores(rows, "bsp_implied_prob")
    print("\n=== PROPER SCORES (reward calibration + resolution; lower=better) ===")
    print(f"{'':>12}{'Brier':>12}{'race log-loss':>16}")
    print(f"{'MODEL':>12}{mb:>12.5f}{mll:>16.4f}")
    print(f"{'BSP':>12}{bb:>12.5f}{bll:>16.4f}")
    print("ECE says model looks calibrated, but these show BSP's resolution edge:")
    print("the model bunches predictions near the base rate (poor separation).")

    write_chart(model_tab, bsp_tab)


if __name__ == "__main__":
    main()
