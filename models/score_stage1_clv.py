"""
score_stage1_clv.py -- score the Stage-1 model with CLV (Block C).

This is the moment the project points at: turn the model's probabilities into
fair prices and ask whether the model found value the market (BSP) didn't.

STEPS
-----
1. Read models/stage1_scored.csv (model_prob per runner + carried non-features).
2. Fair price from the model:           fair_price = 1 / model_prob.
3. SELECTION RULE (value betting): back a runner when the price the market
   OFFERED is bigger than the model's fair price -- i.e. you're being offered
   better-than-fair odds because the model thinks the runner is likelier than
   that price implies:
                       struck_price > fair_price   <=>   model_prob > 1/struck.
   NB the brief's literal wording ("fair price BIGGER than the offered price")
   is inverted relative to its own rationale ("model thinks it's likelier");
   we follow the rationale, which is the correct value condition.
   The "price the market offered" is the pre-off struck price `clv.py` expects
   -- `bf_last_preoff_ltp` -- NOT BSP (BSP is the scorer). Per PROJECT_NOTES the
   free-tier struck price is an LTP stand-in, so a positive CLV here may be a
   timing artifact, not genuine edge.
4. Write the selections in the column layout backtest/clv.py consumes and run
   that existing harness on them (reuse; --struck-col is configurable). CLV is
   scored against BSP, net of commission (default 5%).
5. Report: #selections, mean CLV, % beating BSP, realised P&L, by race type.
"""
import os
import csv
import sys
import math
import subprocess
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCORED = os.path.join(_ROOT, "models", "stage1_scored.csv")
JOINED = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
SELECTIONS = os.path.join(_ROOT, "models", "stage1_selections.csv")
CLV = os.path.join(_ROOT, "backtest", "clv.py")
STRUCK_COL = "struck"   # interim struck price = sqrt(pre_min*pre_max), pre-off mid
COMMISSION = 0.05

sys.path.insert(0, os.path.join(_ROOT, "backtest"))
import clv   # reuse the harness's pure metric functions for the per-type table


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def race_key(r):
    """(date, course, off) -> canonical race id (replaces gone bf_market_id)."""
    return f"{r['date']}|{r['course']}|{r['off']}"


STRUCK_MODE = os.environ.get("STRUCK_MODE", "wap")  # wap|geomean|pre_min|pre_max


def struck_price(pre_min, pre_max, wap=None):
    """Interim struck price for CLV. STRUCK_MODE selects the source:
    'wap' (default) = PPWAP, the pre-off volume-weighted avg traded price (a REAL
    struck price; carries a WAP-vs-close timing component, not a timestamped
    strike); 'geomean' = sqrt(pre_min*pre_max); 'pre_min'/'pre_max' = that bound.
    None unless the chosen price is valid decimal odds (>1.0).
    """
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


def main():
    # race-type lookup (Flat / Chase / Hurdle / NH Flat) keyed by race id
    rtype = {}
    for r in csv.DictReader(open(JOINED, newline="")):
        rtype[race_key(r)] = r["type"]

    rows = list(csv.DictReader(open(SCORED, newline="")))
    selections = []
    for r in rows:
        prob = fnum(r["model_prob"])
        struck = struck_price(r["score_pre_min"], r["score_pre_max"],
                              r.get("score_wap"))
        bsp = fnum(r["score_bsp"])
        if not prob or not struck or not bsp or struck <= 1.0 or bsp <= 1.0:
            continue
        fair = 1.0 / prob
        # VALUE: market offers a bigger price than the model's fair price.
        if struck > fair:
            selections.append({
                "race_id": r["race_id"],
                "horse": r["horse"],
                "type": rtype.get(r["race_id"], "?"),
                "model_prob": prob,
                "fair_price": round(fair, 3),
                STRUCK_COL: round(struck, 4),
                "bsp": bsp,
                "won": 1 if (r.get("score_pos") or "").strip() == "1" else 0,
            })

    # write selections in the exact layout clv.py reads
    cols = ["race_id", "horse", "type", "model_prob", "fair_price",
            STRUCK_COL, "bsp", "won"]
    with open(SELECTIONS, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        w.writerows(selections)

    total = sum(1 for _ in rows)
    print(f"Runners scored      : {total}")
    print(f"Selections (value)  : {len(selections)} "
          f"({100*len(selections)/total:.1f}% of runners)")
    print(f"Struck price        : STRUCK_MODE={STRUCK_MODE} -> col '{STRUCK_COL}'  "
          f"({'PPWAP, real pre-off traded price' if STRUCK_MODE=='wap' else 'pre-off range proxy'})")
    print(f"Wrote selections    -> {SELECTIONS}")

    # --- feed the selections into the EXISTING harness (literal reuse) -------
    print("\n" + "=" * 60)
    print("Running backtest/clv.py on the model's selections:")
    print("=" * 60)
    res = subprocess.run(
        [sys.executable, CLV, "--joined", SELECTIONS,
         "--struck-col", STRUCK_COL, "--commission", str(COMMISSION)],
        capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print("clv.py stderr:", res.stderr)

    # --- breakdown by race type (reuse clv's pure metric functions) ---------
    print("\n=== CLV by race type ===")
    print(f"{'type':<10}{'n':>6}{'mean CLV':>10}{'beat BSP':>10}"
          f"{'ROI@struck':>12}{'ROI@BSP':>10}")
    by_type = defaultdict(list)
    for s in selections:
        by_type[s["type"]].append(
            {"struck": s[STRUCK_COL], "bsp": s["bsp"],
             "won": s["won"] == 1})
    for t, bets in sorted(by_type.items(), key=lambda kv: -len(kv[1])):
        s = clv.summarise(bets, COMMISSION)
        print(f"{t:<10}{s['n_bets']:>6}{s['mean_clv']:>9.2%}"
              f"{s['pct_beating_bsp']:>10.1%}{s['roi_struck']:>11.2%}"
              f"{s['roi_bsp']:>10.2%}")


if __name__ == "__main__":
    main()
