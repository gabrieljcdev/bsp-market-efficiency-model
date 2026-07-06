"""
lay_clv.py -- the LAY-side CLV scoring harness (mirror of backtest/clv.py).

WHY A LAY HARNESS?
------------------
The back harness (clv.py) scores BACK bets: struck / bsp - 1, profit when the
market shortens after you back. Some selections are the WRONG side for backing
(the model's "value" picks drift OUT +31.66% vs a +14.12% baseline) but the RIGHT
side for LAYING. Laying a horse is betting it LOSES: you offer the price, a backer
takes it, and you keep their stake if the horse loses / pay the liability if it
wins. This module pins the lay-side metric maths so a lay experiment is scored on
exactly the same footing as the back side -- struck = wap, close = bsp, net 5%.

LAY CLV (the sign flips vs the back side)
-----------------------------------------
For a LAY struck at decimal odds `struck`, against a close of `bsp`:

        lay_clv = bsp / struck - 1

  * lay_clv > 0  -> the price DRIFTED after our lay (bsp > struck): we laid at a
                    SHORTER (better-for-a-layer) price than the close. Good.
  * lay_clv = 0  -> we laid at exactly the closing price.
  * lay_clv < 0  -> the price STEAMED in (bsp < struck): we laid too short, the
                    close was a better lay price. Bad.

This is the exact reciprocal-shaped mirror of back CLV (struck / bsp - 1): the
layer wants the price to go OUT after striking, the backer wants it to come IN.
Like back CLV it's commission-independent -- a pure price comparison.

LAY P&L -- TWO RISK FRAMINGS
----------------------------
A lay's downside is the LIABILITY (odds - 1) x stake, not the stake. Two framings:

  * FIXED LIABILITY (preferred, the honest risk unit): hold the money-at-risk
    constant at L = 1 unit. To risk L you stake s = L / (odds - 1). If the horse
    LOSES you win the backer's stake s, net commission: +s * (1 - comm). If it
    WINS you pay the fixed liability: -L = -1. ROI is per unit of LIABILITY, so
    a 40/1 lay and a 2/1 lay are compared at the same risk.

  * FIXED STAKE (for comparability with the back-side 1u runs): stake 1 unit of
    backer-money each time. Horse LOSES -> +1 * (1 - comm); horse WINS -> pay the
    variable liability -(odds - 1). Same shape as score_price_drift._lay_pnl.

Commission (Betfair 5% default) is charged ONLY on a winning lay (the horse
loses and you collect) -- never on the liability you pay out.
"""
import os
import csv
import argparse
import statistics as st
from collections import defaultdict

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_JOINED = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")
DEFAULT_COMMISSION = 0.05   # Betfair's standard exchange commission on winnings


# --------------------------------------------------------------------------- #
# Core metric functions -- deliberately tiny and pure so they're easy to test. #
# `won` throughout means THE LAID HORSE WON (i.e. the lay LOST).               #
# --------------------------------------------------------------------------- #

def lay_closing_line_value(struck, bsp):
    """Lay CLV for a single LAY bet: how much the price drifted after we laid.

    bsp / struck - 1.  e.g. lay struck at 4.0 against a BSP of 5.0 -> +0.25 (+25%):
    the price drifted OUT from 4.0 to 5.0, so we laid at a shorter (better) price
    than the close. The mirror of back CLV (struck / bsp - 1).
    """
    return bsp / struck - 1.0


def lay_bet_pnl_fixed_liability(struck, won, commission):
    """P&L of a LAY carrying 1 unit of LIABILITY, net of exchange commission.

    Stake to risk 1 unit of liability at odds `struck` is s = 1 / (struck - 1).
      * horse LOSES (lay wins) -> collect the backer's stake, less commission:
        +s * (1 - commission) = (1 - commission) / (struck - 1).
      * horse WINS  (lay loses) -> pay the fixed 1-unit liability: -1.0.
    ROI from this is per unit of LIABILITY -- the honest risk-normalised framing.
    """
    if won:
        return -1.0
    return (1.0 - commission) / (struck - 1.0)


def lay_bet_pnl_fixed_stake(struck, won, commission):
    """P&L of a LAY of 1 unit of BACKER-STAKE, net of exchange commission.

      * horse LOSES (lay wins) -> keep the 1-unit stake, less commission:
        +1 * (1 - commission).
      * horse WINS  (lay loses) -> pay the variable liability: -(struck - 1).
    Same shape as score_price_drift._lay_pnl; use for like-for-like comparison
    with the back-side 1u flat runs (where stake is also the unit).
    """
    if won:
        return -(struck - 1.0)
    return 1.0 - commission


# --------------------------------------------------------------------------- #
# Loading bets from the joined dataset.  (Reuses clv's parse/id/settle logic   #
# if clv is importable, else falls back to local copies -- keeps this module   #
# runnable standalone.)                                                        #
# --------------------------------------------------------------------------- #
try:                                    # prefer the canonical helpers
    import clv as _clv                  # noqa: E402
    _fnum, _race_id, _won = _clv._fnum, _clv._race_id, _clv._won
except Exception:                       # standalone fallback (identical semantics)
    def _fnum(x):
        try:
            return float(x)
        except (TypeError, ValueError):
            return None

    def _race_id(r):
        rid = r.get("race_id")
        if rid:
            return rid
        if r.get("date"):
            return f"{r.get('date')}|{r.get('course')}|{r.get('off')}"
        return None

    def _won(r):
        w = r.get("won")
        if w not in (None, ""):
            return str(w).strip() in ("1", "True", "true", "WINNER")
        return (r.get("pos") or "").strip() == "1"


def load_runners(path, struck_col):
    """Read a runner table into lay-bet-ready dicts (struck, bsp, won, race_id).

    Rows missing a usable struck price or BSP are skipped -- and a struck of
    exactly 1.0 is unusable for a lay besides (stake = 1/(struck-1) blows up),
    so we require struck > 1.0 just like the back harness.
    """
    runners = []
    skipped = 0
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            struck = _fnum(r.get(struck_col))
            bsp = _fnum(r.get("bsp"))
            if not struck or not bsp or struck <= 1.0 or bsp <= 1.0:
                skipped += 1
                continue
            runners.append({
                "race_id": _race_id(r),
                "horse": r.get("horse"),
                "struck": struck,
                "bsp": bsp,
                "won": _won(r),          # the LAID horse won -> the lay LOST
            })
    return runners, skipped


def select_bets(runners, strategy):
    """Turn the runner pool into the lay bets a strategy would place.

    * "all"        -> lay every runner.
    * "favourites" -> lay each race's shortest-BSP runner (rarely sane, but the
      mirror of clv.select_bets so the harnesses stay symmetric).
    """
    if strategy == "all":
        return runners
    if strategy == "favourites":
        by_race = defaultdict(list)
        for r in runners:
            by_race[r["race_id"]].append(r)
        return [min(rs, key=lambda r: r["bsp"]) for rs in by_race.values()]
    raise ValueError(f"unknown strategy: {strategy}")


# --------------------------------------------------------------------------- #
# Aggregation.                                                                 #
# --------------------------------------------------------------------------- #

def summarise_lay(bets, commission):
    """Compute lay-CLV and realised lay-return metrics over a list of lay bets.

    Lay-CLV metrics (pure price comparison, commission-independent):
      * mean_lay_clv / median_lay_clv -- average drift captured vs the close.
      * pct_drifted  -- share of lays whose price drifted OUT after striking
        (lay_clv > 0); the lay-side mirror of pct_beating_bsp.

    Realised metrics (commission applied):
      * FIXED LIABILITY  -- pnl_liab / roi_liab: ROI per unit of LIABILITY (the
        preferred risk unit). staked_liab = n (1 unit of liability per bet).
      * FIXED STAKE      -- pnl_stake / roi_stake: ROI per unit of backer-STAKE,
        for like-for-like comparison with the back-side 1u flat runs.
    Both are settled at the STRUCK price. A parallel *_bsp pair settles the SAME
    lays at BSP -- the honest close -- so (roi_struck - roi_bsp) is the lay-CLV
    edge turned into money.
    """
    n = len(bets)
    clvs = [lay_closing_line_value(b["struck"], b["bsp"]) for b in bets]

    pnl_liab = sum(lay_bet_pnl_fixed_liability(b["struck"], b["won"], commission)
                   for b in bets)
    pnl_stake = sum(lay_bet_pnl_fixed_stake(b["struck"], b["won"], commission)
                    for b in bets)
    # the SAME lays settled at the close (BSP) -- the benchmark price.
    pnl_liab_bsp = sum(lay_bet_pnl_fixed_liability(b["bsp"], b["won"], commission)
                       for b in bets)
    pnl_stake_bsp = sum(lay_bet_pnl_fixed_stake(b["bsp"], b["won"], commission)
                        for b in bets)

    return {
        "n_bets": n,
        "n_lay_wins": sum(1 for b in bets if not b["won"]),   # horse lost -> lay won
        "mean_lay_clv": st.mean(clvs),
        "median_lay_clv": st.median(clvs),
        "pct_drifted": sum(1 for c in clvs if c > 0) / n,
        "commission": commission,
        # fixed-liability framing (preferred): 1 unit liability per bet
        "staked_liab": float(n),
        "pnl_liab": pnl_liab,
        "roi_liab": pnl_liab / n,
        "pnl_liab_bsp": pnl_liab_bsp,
        "roi_liab_bsp": pnl_liab_bsp / n,
        # fixed-stake framing: 1 unit backer-stake per bet
        "staked_stake": float(n),
        "pnl_stake": pnl_stake,
        "roi_stake": pnl_stake / n,
        "pnl_stake_bsp": pnl_stake_bsp,
        "roi_stake_bsp": pnl_stake_bsp / n,
    }


def print_report(strategy, struck_col, s, skipped):
    """Render a lay summary dict as a readable block."""
    print(f"\n=== LAY-CLV report: strategy='{strategy}', "
          f"struck price='{struck_col}' ===")
    print(f"lays                 : {s['n_bets']}  "
          f"(lay wins {s['n_lay_wins']}, skipped {skipped} for missing prices)")
    print(f"commission           : {s['commission']:.0%}")
    print("\n-- Lay closing line value (bsp vs struck) --")
    print(f"mean lay-CLV         : {s['mean_lay_clv']:+.2%}")
    print(f"median lay-CLV       : {s['median_lay_clv']:+.2%}")
    print(f"price drifted (>0)   : {s['pct_drifted']:.1%}")
    print("\n-- Realised lay return, net of commission --")
    print(f"[fixed liability] staked {s['staked_liab']:.0f}u liability")
    print(f"  P&L @ struck       : {s['pnl_liab']:+.1f}u  (ROI {s['roi_liab']:+.2%})")
    print(f"  P&L @ BSP (bench)  : {s['pnl_liab_bsp']:+.1f}u  (ROI {s['roi_liab_bsp']:+.2%})")
    print(f"[fixed stake] staked {s['staked_stake']:.0f}u stake")
    print(f"  P&L @ struck       : {s['pnl_stake']:+.1f}u  (ROI {s['roi_stake']:+.2%})")
    print(f"  P&L @ BSP (bench)  : {s['pnl_stake_bsp']:+.1f}u  (ROI {s['roi_stake_bsp']:+.2%})")
    edge = s["roi_liab"] - s["roi_liab_bsp"]
    print(f"lay edge vs BSP (liab): {edge:+.2%}  "
          f"(positive => our lay price beat the close on average)")


def main():
    ap = argparse.ArgumentParser(description="Lay-CLV scoring harness (bsp vs struck).")
    ap.add_argument("--joined", default=DEFAULT_JOINED,
                    help="runner table (form + BSP)")
    ap.add_argument("--struck-col", default="struck",
                    help="column to use as the lay struck price (convention: wap)")
    ap.add_argument("--strategy", default="all", choices=["all", "favourites"],
                    help="which runners to lay")
    ap.add_argument("--commission", type=float, default=DEFAULT_COMMISSION,
                    help="exchange commission on winning lays (default 0.05)")
    args = ap.parse_args()

    runners, skipped = load_runners(args.joined, args.struck_col)
    bets = select_bets(runners, args.strategy)
    summary = summarise_lay(bets, args.commission)
    print_report(args.strategy, args.struck_col, summary, skipped)


if __name__ == "__main__":
    main()
