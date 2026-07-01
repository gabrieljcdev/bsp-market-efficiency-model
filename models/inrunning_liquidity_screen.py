#!/usr/bin/env python3
"""inrunning_liquidity_screen.py -- Stage 1 LIQUIDITY GATE, free first-pass screen.

Pre-registration: Strategy_Direction_InRunning.md (confirmed 2026-07-01).
  Signal (liquidity gate): front-runner (run_style_proxy == 'led') entered when the
  in-running price first trades <= 2.0.
  Gate: >= £X matched in > Y% of qualifying opportunities.   X=£100, Y=50%, N>=2,000.

WHAT THIS SCREEN IS (and is NOT):
  The joined dataset already carries the Betfair BSP-file IN-PLAY aggregates:
      ip_min = lowest price traded in running   (ip_min <= 2.0 == the trigger fired)
      ip_vol = TOTAL £ matched in running on that runner (whole in-play period,
               ALL prices, BOTH sides).
  So `ip_vol >= £X` is a NECESSARY-BUT-NOT-SUFFICIENT condition for matching £X at
  <= 2.0 at the entry instant (t + 1s latency): the true point-in-time matched size
  is <= ip_vol. Therefore the fraction with ip_vol >= £X is an UPPER BOUND on the
  real fill rate. This screen can DECISIVELY FAIL the gate for free (if even the
  upper bound < Y%), but it CANNOT pass it -- a definitive pass needs the PRO-tier
  full-ladder+volume time series (historicdata.betfair.com), which is a paid
  purchase and is NOT run here. No data bought; no edge gate; read-only.
"""
import os
import csv
import statistics as st

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_hist.csv")
SPLIT_CUTOFF = "2023-12-31"

X = 100.0          # £ target matched stake
Y = 0.50           # required fraction of opportunities
N_MIN = 2000       # min qualifying opportunities
TRIGGER = 2.0      # in-running price trigger (ip_min <= TRIGGER)
CONTEXT_X = [10.0, 100.0, 500.0, 1000.0]   # upper-bound fractions at several stakes


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    qual_vols = []          # ip_vol for each qualifying opportunity
    qual_disc, qual_hold = [], []
    n_led = n_led_priced = 0
    total = 0
    with open(HIST, newline="") as f:
        for r in csv.DictReader(f):
            total += 1
            if r.get("run_style_proxy") != "led":
                continue
            n_led += 1
            ipmin = fnum(r.get("ip_min"))
            ipvol = fnum(r.get("ip_vol"))
            if ipmin is None or ipvol is None:
                continue
            n_led_priced += 1
            if ipmin <= TRIGGER:                    # the <=2.0 trigger fired in-running
                qual_vols.append(ipvol)
                (qual_disc if (r.get("date") or "") <= SPLIT_CUTOFF
                 else qual_hold).append(ipvol)

    nq = len(qual_vols)
    print("=" * 74)
    print("IN-RUNNING LIQUIDITY GATE -- free first-pass UPPER-BOUND screen")
    print("=" * 74)
    print(f"rows scanned                    : {total:,}")
    print(f"front-runners (run_style=led)   : {n_led:,}  (with ip data {n_led_priced:,})")
    print(f"QUALIFYING (led & ip_min<=2.0)  : {nq:,}   [N_MIN={N_MIN:,}]")
    if nq == 0:
        print("no qualifying opportunities -- cannot screen.")
        return

    frac_ge_X = sum(1 for v in qual_vols if v >= X) / nq
    print(f"\nip_vol (TOTAL in-play matched, GBP) over qualifying set:")
    qv = sorted(qual_vols)
    q = lambda p: qv[min(int(p * nq), nq - 1)]
    print(f"  median £{st.median(qv):,.0f}   p10 £{q(.10):,.0f}   p25 £{q(.25):,.0f}   "
          f"p50 £{q(.50):,.0f}   p90 £{q(.90):,.0f}")
    print(f"\nUPPER-BOUND fraction with ip_vol >= stake (>= true fill rate):")
    for cx in CONTEXT_X:
        fr = sum(1 for v in qual_vols if v >= cx) / nq
        mark = "  <- X" if cx == X else ""
        print(f"  >= £{cx:>7,.0f}: {fr:6.1%}{mark}")

    # discovery/holdout stability of the upper bound (sanity; gate uses full set)
    fd = (sum(1 for v in qual_disc if v >= X) / len(qual_disc)) if qual_disc else float("nan")
    fh = (sum(1 for v in qual_hold if v >= X) / len(qual_hold)) if qual_hold else float("nan")
    print(f"\nupper-bound fraction >= £{X:,.0f}: full {frac_ge_X:.1%} | "
          f"disc {fd:.1%} (n{len(qual_disc):,}) | hold {fh:.1%} (n{len(qual_hold):,})")

    print("\n" + "-" * 74)
    print(f"PRE-REGISTERED BAR: >= £{X:,.0f} matched in > {Y:.0%} of qualifying opps")
    print(f"UPPER-BOUND (total in-play vol >= £{X:,.0f}): {frac_ge_X:.1%}")
    if nq < N_MIN:
        print(f"NOTE: only {nq:,} qualifying opps (< N_MIN {N_MIN:,}) -- widen window if used.")
    if frac_ge_X <= Y:
        print(f"VERDICT: DECISIVE FAIL -- even the UPPER BOUND ({frac_ge_X:.1%}) is <= "
              f"Y={Y:.0%}; the true point-in-time fill rate can only be lower. "
              f"No purchase needed; the gate is failed on data in hand.")
    else:
        print(f"VERDICT: NOT KILLED by the free screen -- the upper bound ({frac_ge_X:.1%}) "
              f"clears Y={Y:.0%}, but this is NECESSARY-NOT-SUFFICIENT (total in-play "
              f"volume, not size available at <=2.0 at t+1s). A DEFINITIVE pass/fail "
              f"needs the PRO full-ladder+volume data (paid; NOT run here). "
              f"INCONCLUSIVE at zero cost -- decide whether to buy the ladder.")
    print("=" * 74)


if __name__ == "__main__":
    main()
