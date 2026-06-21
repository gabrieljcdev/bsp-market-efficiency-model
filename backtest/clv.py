"""
clv.py -- the CLV (Closing Line Value) scoring harness.

WHAT IS CLV?
------------
"Closing line value" measures how good a price you got compared with where the
market finally settled. On the Betfair Exchange the canonical "close" is the
Betfair Starting Price (BSP) -- the reconciled price at the off. For a BACK bet
struck at decimal odds `struck`, against a close of `bsp`:

        CLV = struck / bsp - 1

  * CLV > 0  -> you backed at BIGGER odds than the close (you beat the market).
  * CLV = 0  -> you got exactly the closing price.
  * CLV < 0  -> you took a worse price than the close.

Why we score on CLV: the closing line is the market's most efficient estimate of
each runner's chance. Consistently beating it out of sample is the strongest
evidence of genuine edge -- far more reliable on small samples than raw P&L,
because it doesn't need a bet to actually win to tell you the price was good.
This is the project's core metric: beat BSP out of sample, net of commission.

INTERIM STRUCK PRICE
--------------------
A real run needs the price you actually struck (with a timestamp). We don't have
that yet. In the 2018-2026 schema the Betfair stream's `bf_last_preoff_ltp` is
gone; the join kept only the BSP-CSV pre-off fields, so the interim struck price
is `struck = sqrt(pre_min * pre_max)` -- the geometric midpoint of the pre-off
traded range -- computed upstream by the scorers and passed in via `--struck-col`.
It sits ~on the close, so the *level* of CLV here is near zero by construction;
the value of this harness right now is the plumbing and the distribution, not the
headline edge.

USAGE
-----
    python3 backtest/clv.py                         # back every runner
    python3 backtest/clv.py --strategy favourites   # back each race's favourite
    python3 backtest/clv.py --commission 0.02       # 2% commission
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
# --------------------------------------------------------------------------- #

def closing_line_value(struck, bsp):
    """CLV for a single BACK bet: how much bigger our odds were than the close.

    struck / bsp - 1.  e.g. struck 6.0 against a BSP of 5.0 -> +0.20 (+20%):
    we took 6.0 when the market closed at 5.0, so we beat the line by 20%.
    """
    return struck / bsp - 1.0


def back_bet_pnl(struck, won, commission):
    """Profit (in units) of a 1-unit BACK bet, net of exchange commission.

    On a win you receive your net winnings (stake * (odds - 1)); the exchange
    takes `commission` of those winnings, so net = (struck - 1) * (1 - comm).
    On a loss you forfeit the 1-unit stake (no commission is charged on losses).
    """
    if won:
        return (struck - 1.0) * (1.0 - commission)
    return -1.0


# --------------------------------------------------------------------------- #
# Loading bets from the joined dataset.                                        #
# --------------------------------------------------------------------------- #

def _fnum(x):
    """Parse a float, returning None for blanks / non-numeric cells."""
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _race_id(r):
    """Race id from an explicit `race_id` column, else (date, course, off).

    Selections files written by the scorers carry `race_id` directly; a raw
    joined table (no race_id column) falls back to the canonical key. Replaces
    the gone `bf_market_id`.
    """
    rid = r.get("race_id")
    if rid:
        return rid
    if r.get("date"):
        return f"{r.get('date')}|{r.get('course')}|{r.get('off')}"
    return None


def _won(r):
    """Settlement flag. Prefer an explicit `won` column (1/True/WINNER); else
    fall back to finishing position `pos == '1'`. Replaces the gone
    `bf_runner_status == 'WINNER'`."""
    w = r.get("won")
    if w not in (None, ""):
        return str(w).strip() in ("1", "True", "true", "WINNER")
    return (r.get("pos") or "").strip() == "1"


def load_runners(path, struck_col):
    """Read the joined table into a list of bet-ready runner dicts.

    Each runner keeps only what the harness needs: the struck price (our chosen
    column), the closing BSP, whether it won, and its race id (for strategies
    that pick one runner per race). Rows missing a usable struck price or BSP
    are skipped -- you can't score a bet without both prices.
    """
    runners = []
    skipped = 0
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            struck = _fnum(r.get(struck_col))
            bsp = _fnum(r.get("bsp"))
            # Need two valid (>1.0) decimal prices to form a bet.
            if not struck or not bsp or struck <= 1.0 or bsp <= 1.0:
                skipped += 1
                continue
            runners.append({
                "race_id": _race_id(r),
                "horse": r.get("horse"),
                "struck": struck,
                "bsp": bsp,
                # Settlement consistent with BSP (Betfair side / finishing pos).
                "won": _won(r),
            })
    return runners, skipped


def select_bets(runners, strategy):
    """Turn the pool of runners into the set of bets a strategy would place.

    * "all"        -> back every runner (one bet per runner).
    * "favourites" -> back only the shortest-BSP runner in each race.
    Add new strategies here as the project grows.
    """
    if strategy == "all":
        return runners
    if strategy == "favourites":
        by_race = defaultdict(list)
        for r in runners:
            by_race[r["race_id"]].append(r)
        # The favourite is the runner the market rates highest = lowest BSP.
        return [min(rs, key=lambda r: r["bsp"]) for rs in by_race.values()]
    raise ValueError(f"unknown strategy: {strategy}")


# --------------------------------------------------------------------------- #
# Aggregation.                                                                 #
# --------------------------------------------------------------------------- #

def summarise(bets, commission):
    """Compute the CLV and realised-return metrics over a list of bets.

    CLV metrics (pure price comparison, commission-independent):
      * mean_clv / median_clv -- average value taken vs the close.
      * pct_beating_bsp       -- share of bets struck above the close (CLV > 0).

    Realised metrics (what the bets actually returned, commission applied):
      * pnl_struck / roi_struck -- P&L backing at our struck price.
      * pnl_bsp / roi_bsp       -- same bets settled at BSP, the benchmark.
        The gap between roi_struck and roi_bsp is the CLV edge turned into money:
        if we reliably beat the close, backing at our price out-returns the close.
    """
    n = len(bets)
    clvs = [closing_line_value(b["struck"], b["bsp"]) for b in bets]

    pnl_struck = sum(back_bet_pnl(b["struck"], b["won"], commission) for b in bets)
    pnl_bsp = sum(back_bet_pnl(b["bsp"], b["won"], commission) for b in bets)

    return {
        "n_bets": n,
        "n_winners": sum(1 for b in bets if b["won"]),
        "mean_clv": st.mean(clvs),
        "median_clv": st.median(clvs),
        "pct_beating_bsp": sum(1 for c in clvs if c > 0) / n,
        "commission": commission,
        "staked": float(n),                 # 1 unit per bet
        "pnl_struck": pnl_struck,
        "roi_struck": pnl_struck / n,
        "pnl_bsp": pnl_bsp,
        "roi_bsp": pnl_bsp / n,
    }


def print_report(strategy, struck_col, s, skipped):
    """Render a summary dict as a readable block."""
    print(f"\n=== CLV report: strategy='{strategy}', "
          f"struck price='{struck_col}' ===")
    print(f"bets                 : {s['n_bets']}  "
          f"(winners {s['n_winners']}, skipped {skipped} for missing prices)")
    print(f"commission           : {s['commission']:.0%}")
    print("\n-- Closing line value (struck vs BSP) --")
    print(f"mean CLV             : {s['mean_clv']:+.2%}")
    print(f"median CLV           : {s['median_clv']:+.2%}")
    print(f"beat the close (>BSP): {s['pct_beating_bsp']:.1%}")
    print("\n-- Realised return, net of commission (1u flat back bets) --")
    print(f"staked               : {s['staked']:.0f}u")
    print(f"P&L @ struck price   : {s['pnl_struck']:+.1f}u  "
          f"(ROI {s['roi_struck']:+.2%})")
    print(f"P&L @ BSP (benchmark): {s['pnl_bsp']:+.1f}u  "
          f"(ROI {s['roi_bsp']:+.2%})")
    edge = s["roi_struck"] - s["roi_bsp"]
    print(f"edge vs BSP          : {edge:+.2%}  "
          f"(positive => our price beat the close on average)")


def main():
    ap = argparse.ArgumentParser(description="CLV scoring harness (struck vs BSP).")
    ap.add_argument("--joined", default=DEFAULT_JOINED,
                    help="joined runner table (form + BSP)")
    ap.add_argument("--struck-col", default="struck",
                    help="column to use as the struck price "
                         "(interim: sqrt(pre_min*pre_max), the pre-off mid)")
    ap.add_argument("--strategy", default="all", choices=["all", "favourites"],
                    help="which bets to place")
    ap.add_argument("--commission", type=float, default=DEFAULT_COMMISSION,
                    help="exchange commission on winnings (default 0.05)")
    args = ap.parse_args()

    runners, skipped = load_runners(args.joined, args.struck_col)
    bets = select_bets(runners, args.strategy)
    summary = summarise(bets, args.commission)
    print_report(args.strategy, args.struck_col, summary, skipped)


if __name__ == "__main__":
    main()
