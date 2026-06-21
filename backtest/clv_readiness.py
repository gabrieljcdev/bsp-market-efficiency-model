"""
clv_readiness.py -- sanity pass: is the joined dataset ready for a CLV harness?

NOT the CLV harness itself (that's the next phase, backtest/clv.py). This only
checks the joined table has the pieces CLV needs and that the BSP benchmark
behaves like a real, well-calibrated market:

  1. Completeness  -- BSP, a struck-price proxy, and a result on every runner.
  2. Benchmark soundness -- favourite strike rate + BSP-implied-prob calibration.
  3. CLV plumbing demo  -- CLV = struck/bsp - 1 using last_preoff_ltp as the
     struck-price stand-in, % beating the close, and a flat-stakes ROI at BSP
     net of commission (proves the result+price+commission math runs end-to-end).

CLV (close = BSP) is the project's scoring metric. Real CLV needs genuine struck
prices with timestamps; until then last_preoff_ltp is the documented stand-in.
"""
import os, csv, statistics as st
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
JOINED = os.path.join(_ROOT, "data", "joined", "joined_gb_2025_09.csv")
COMMISSION = 0.05   # Betfair default; applied to net winnings


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def load():
    rows = list(csv.DictReader(open(JOINED, newline="")))
    for r in rows:
        r["_bsp"] = fnum(r.get("bsp"))
        r["_ltp"] = fnum(r.get("bf_last_preoff_ltp"))
        r["_win"] = (r.get("pos", "").strip() == "1")
    return rows


def section(t):
    print("\n" + t + "\n" + "-" * len(t))


def main():
    rows = load()
    races = defaultdict(list)
    for r in rows:
        races[r["bf_market_id"]].append(r)

    # ---- 1. completeness ----------------------------------------------------
    section("1. COMPLETENESS")
    n = len(rows)
    good_bsp = [r for r in rows if r["_bsp"] and r["_bsp"] > 1.0]
    bad_bsp = [r for r in rows if not r["_bsp"] or r["_bsp"] <= 1.0]
    ltp = [r for r in rows if r["_ltp"] and r["_ltp"] > 1.0]
    print(f"runners                  : {n}")
    print(f"races (bf_market_id)     : {len(races)}")
    print(f"valid BSP (>1.0)         : {len(good_bsp)} ({100*len(good_bsp)/n:.1f}%)"
          f"  | invalid/missing: {len(bad_bsp)}")
    print(f"struck proxy (last LTP)  : {len(ltp)} ({100*len(ltp)/n:.1f}%)")
    winners = [r for r in rows if r["_win"]]
    one_winner = sum(1 for rr in races.values()
                     if sum(1 for r in rr if r["_win"]) == 1)
    print(f"winners (pos==1)         : {len(winners)}")
    print(f"races with exactly 1 win : {one_winner}/{len(races)}")

    # ---- 2. benchmark soundness --------------------------------------------
    section("2. BSP BENCHMARK SOUNDNESS")
    # favourite (shortest BSP) strike rate
    fav_wins = fav_n = 0
    for rr in races.values():
        cand = [r for r in rr if r["_bsp"]]
        if not cand:
            continue
        fav = min(cand, key=lambda r: r["_bsp"])
        fav_n += 1
        fav_wins += int(fav["_win"])
    print(f"favourite strike rate    : {fav_wins}/{fav_n} "
          f"({100*fav_wins/fav_n:.1f}%)   [GB norm ~33%]")

    # calibration: BSP-implied prob (1/BSP) vs actual win rate, by band
    bands = [(1.0, 2.0), (2.0, 3.0), (3.0, 5.0), (5.0, 10.0),
             (10.0, 20.0), (20.0, 1e9)]
    print(f"\n  {'BSP band':<14}{'n':>7}{'implied':>9}{'actual':>9}")
    for lo, hi in bands:
        grp = [r for r in good_bsp if lo <= r["_bsp"] < hi]
        if not grp:
            continue
        implied = st.mean(1.0 / r["_bsp"] for r in grp)
        actual = st.mean(1.0 if r["_win"] else 0.0 for r in grp)
        label = f"{lo:g}-{hi:g}" if hi < 1e9 else f"{lo:g}+"
        print(f"  {label:<14}{len(grp):>7}{implied:>8.1%}{actual:>9.1%}")

    # ---- 3. CLV plumbing demo ----------------------------------------------
    section("3. CLV PLUMBING (last_preoff_ltp as struck-price stand-in)")
    pair = [r for r in rows if r["_ltp"] and r["_bsp"]]
    clv = [r["_ltp"] / r["_bsp"] - 1.0 for r in pair]
    beat = sum(1 for c in clv if c > 0)
    print(f"runners with both prices : {len(pair)}")
    print(f"mean CLV (ltp/bsp - 1)   : {100*st.mean(clv):+.2f}%")
    print(f"median CLV               : {100*st.median(clv):+.2f}%")
    print(f"beat the close (ltp>bsp) : {beat}/{len(pair)} ({100*beat/len(pair):.1f}%)")
    print("  NOTE: last LTP sits ~on the close, so proxy CLV ~0 by construction.")
    print("  True CLV needs real struck prices+timestamps (not in this dataset yet).")

    # flat-stakes ROI: back every favourite at BSP, 1u, net commission
    pnl = 0.0
    for rr in races.values():
        cand = [r for r in rr if r["_bsp"]]
        if not cand:
            continue
        fav = min(cand, key=lambda r: r["_bsp"])
        if fav["_win"]:
            pnl += (fav["_bsp"] - 1.0) * (1 - COMMISSION)
        else:
            pnl -= 1.0
    print(f"\n  demo backtest: back the favourite at BSP, flat 1u, "
          f"{int(COMMISSION*100)}% comm")
    print(f"  staked {fav_n}u -> P&L {pnl:+.1f}u  (ROI {100*pnl/fav_n:+.1f}%)")
    print("  (negative ROI at BSP is expected market efficiency; this just shows"
          " the result+price+commission math runs.)")

    # ---- verdict ------------------------------------------------------------
    section("READINESS VERDICT")
    ok = (len(bad_bsp) == 0 and len(ltp) == n
          and one_winner >= 0.98 * len(races))
    print("PRESENT : valid BSP benchmark, result (pos), struck-price proxy (LTP),"
          " RP SP (dec), race id (bf_market_id), commission knob.")
    print("MISSING : real struck prices with timestamps -> needed for true CLV.")
    print(f"\n==> Dataset is {'READY' if ok else 'NOT ready'} to drive "
          f"backtest/clv.py (with LTP as the interim struck price).")


if __name__ == "__main__":
    main()
