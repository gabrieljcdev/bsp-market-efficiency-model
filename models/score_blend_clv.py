"""
score_blend_clv.py -- Block D3: calibrate & CLV the blend, THREE-WAY.

Compares Stage-1-alone vs the Stage-2 Blend vs BSP, reusing the existing
harnesses (models/calibrate.py for proper scores, backtest/clv.py for CLV).

Two questions:
  1. Does the blend beat Stage-1-alone? (Adding the market should help: expect
     the blend's Brier/log-loss to land BETWEEN Stage-1 and BSP.)
  2. Does the blend approach -- but NOT beat -- BSP? The market input is the
     pre-off LTP, already a near-BSP price, so the blend can at best get close
     to the scorer. Beating BSP would be a RED FLAG (suspect the LTP<->BSP
     timing gap leaking, per PROJECT_NOTES), not a triumph.

CLV selection rule is identical to Block C: back where prob > 1/struck, struck =
pre-off LTP stand-in (NEVER BSP), net 5% commission.
"""
import os
import csv
import sys
import subprocess
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STAGE2 = os.path.join(_ROOT, "models", "stage2_scored.csv")
SEL = os.path.join(_ROOT, "models", "stage2_selections.csv")
CLV = os.path.join(_ROOT, "backtest", "clv.py")
STRUCK_COL = "struck"   # = sqrt(pre_min*pre_max), pre-off mid (was bf_last_preoff_ltp)
COMMISSION = 0.05

sys.path.insert(0, os.path.join(_ROOT, "backtest"))
sys.path.insert(0, os.path.join(_ROOT, "models"))
import clv          # pure CLV metric functions
import calibrate    # proper_scores reuse


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def make_bets(rows, prob_col):
    """Value selections for a prob column: back where offered price > fair price."""
    bets, sel_rows = [], []
    for r in rows:
        p = fnum(r[prob_col])
        struck = fnum(r["score_struck"])
        bsp = fnum(r["score_bsp"])
        if not p or p <= 0 or not struck or struck <= 1.0 or not bsp or bsp <= 1.0:
            continue
        if struck > 1.0 / p:                       # model/blend sees value
            won = (r.get("score_pos") or "").strip() == "1"
            bets.append({"struck": struck, "bsp": bsp, "won": won})
            sel_rows.append({
                "race_id": r["race_id"], "horse": r["horse"],
                STRUCK_COL: struck, "bsp": bsp,
                "won": 1 if won else 0,
            })
    return bets, sel_rows


def main():
    rows = list(csv.DictReader(open(STAGE2, newline="")))
    print(f"Loaded {len(rows)} runners from stage2_scored.csv\n")

    # ---- 1. THREE-WAY proper scores -----------------------------------------
    print("=== PROPER SCORES three-way (lower = better) ===")
    print(f"{'':>14}{'Brier':>12}{'race log-loss':>16}")
    scores = {}
    for name, col in (("Stage-1 model", "model_prob"),
                      ("Blend", "blend_prob"),
                      ("BSP", "bsp_implied_prob")):
        b, ll = calibrate.proper_scores(rows, col)
        scores[name] = (b, ll)
        print(f"{name:>14}{b:>12.5f}{ll:>16.4f}")
    print("Expectation: Stage-1 (worst) -> Blend (between) -> BSP (best).")

    # ---- 2. CLV three-way (Stage-1 vs Blend; both scored vs BSP) -------------
    print("\n=== CLV: Stage-1 selections vs Blend selections ===")
    print(f"{'strategy':<16}{'n_sel':>7}{'mean CLV':>10}{'beat close':>12}"
          f"{'ROI@struck':>12}{'ROI@BSP':>10}")
    for name, col in (("Stage-1 model", "model_prob"), ("Blend", "blend_prob")):
        bets, sel_rows = make_bets(rows, col)
        s = clv.summarise(bets, COMMISSION)
        print(f"{name:<16}{s['n_bets']:>7}{s['mean_clv']:>9.2%}"
              f"{s['pct_beating_bsp']:>12.1%}{s['roi_struck']:>11.2%}"
              f"{s['roi_bsp']:>10.2%}")
        if name == "Blend":      # persist the blend selections + run the harness
            with open(SEL, "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=["race_id", "horse",
                                   STRUCK_COL, "bsp", "won"])
                w.writeheader()
                w.writerows(sel_rows)

    # canonical harness run on the blend selections (literal clv.py reuse)
    print("\n--- backtest/clv.py on the BLEND selections ---")
    res = subprocess.run([sys.executable, CLV, "--joined", SEL,
                          "--struck-col", STRUCK_COL,
                          "--commission", str(COMMISSION)],
                         capture_output=True, text=True)
    print(res.stdout.strip())
    if res.returncode != 0:
        print("clv.py stderr:", res.stderr)

    # ---- verdict ------------------------------------------------------------
    print("\n=== VERDICT ===")
    s1, bl, bsp = scores["Stage-1 model"], scores["Blend"], scores["BSP"]
    beat_s1 = bl[0] < s1[0] and bl[1] < s1[1]
    approach_bsp = bl[0] > bsp[0] and bl[1] > bsp[1]
    print(f"Blend beats Stage-1-alone? {'YES' if beat_s1 else 'NO'} "
          f"(Brier {bl[0]:.5f} vs {s1[0]:.5f}; log-loss {bl[1]:.4f} vs {s1[1]:.4f})")
    print(f"Blend approaches but stays >= BSP? {'YES' if approach_bsp else 'NO'} "
          f"(Brier {bl[0]:.5f} vs BSP {bsp[0]:.5f})")
    print("Red flag only if the blend BEATS BSP -> suspect LTP<->BSP timing leak.")


if __name__ == "__main__":
    main()
