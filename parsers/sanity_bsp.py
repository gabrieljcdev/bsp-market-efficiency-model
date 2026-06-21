"""
sanity_bsp.py -- quick sanity report over output/bsp_table.csv (Block 2).

Checks the BSP table looks like a real set of horse-racing WIN markets:
  * favourites carry short BSP, longshots long (per-race min/max sample)
  * sum(1/BSP) per race lands near 1.0-1.05 (a near-fair book); far above
    that flags missing/!ACTIVE runners or a parse problem
  * row counts and runners-per-race distribution

Operates only on ACTIVE runners with a reconciled BSP. BSP is the scoring
benchmark, never a model input -- this script only inspects it.
"""
import os, csv, statistics as st
from collections import defaultdict

_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CSV = os.path.join(_root, "output", "bsp_table.csv")


def load(path):
    by_market = defaultdict(list)
    rows = 0
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows += 1
            by_market[r["market_id"]].append(r)
    return by_market, rows


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def main():
    by_market, rows = load(CSV)
    print(f"total rows: {rows} | markets: {len(by_market)}\n")

    # market_type split
    mtypes = defaultdict(int)
    for runners in by_market.values():
        mtypes[runners[0].get("market_type")] += 1
    print("markets by type:", dict(mtypes), "\n")

    # WIN-market race counts per country (a runner that ran == WINNER/LOSER).
    country_races = defaultdict(int)
    for runners in by_market.values():
        if runners[0].get("market_type") != "WIN":
            continue
        country_races[runners[0].get("country")] += 1
    print("WIN markets by country:", dict(country_races), "\n")

    # Fair-book check on GB WIN markets. Post-race a runner that took part has
    # status WINNER or LOSER (never ACTIVE) and a reconciled BSP; REMOVED
    # (withdrawn) runners are excluded from the book.
    COUNTRY = "GB"
    overrounds, runners_per_race, win_markets = [], [], 0
    examples = []
    for mid, runners in by_market.items():
        if runners[0].get("market_type") != "WIN":
            continue
        if runners[0].get("country") != COUNTRY:
            continue
        ran = [r for r in runners
               if r.get("runner_status") in ("WINNER", "LOSER")
               and fnum(r.get("bsp"))]
        if len(ran) < 2:
            continue
        win_markets += 1
        runners_per_race.append(len(ran))
        bsps = sorted((fnum(r["bsp"]) for r in ran))
        overrounds.append(sum(1.0 / b for b in bsps))
        if len(examples) < 5:
            fav = min(ran, key=lambda r: fnum(r["bsp"]))
            dog = max(ran, key=lambda r: fnum(r["bsp"]))
            examples.append((runners[0].get("venue"), runners[0].get("market_time"),
                             len(ran), fnum(fav["bsp"]), fnum(dog["bsp"]),
                             sum(1.0 / b for b in bsps)))

    print(f"{COUNTRY} WIN races with >=2 runners that ran (reconciled BSP): "
          f"{win_markets}\n")

    print("sample races (venue, off, n_active, fav_bsp, longshot_bsp, sum(1/BSP)):")
    for v, t, n, fav, dog, ov in examples:
        print(f"  {str(v):<12} {str(t):<22} n={n:<3} fav={fav:<6} long={dog:<8} book={ov:.3f}")

    if overrounds:
        ov = sorted(overrounds)
        print("\nfair-book sum(1/BSP) across WIN races:")
        print(f"  min={ov[0]:.3f}  median={st.median(ov):.3f}  "
              f"mean={st.mean(ov):.3f}  max={ov[-1]:.3f}")
        in_band = sum(1 for x in ov if 1.0 <= x <= 1.05)
        print(f"  in 1.00-1.05 band: {in_band}/{len(ov)} "
              f"({100*in_band/len(ov):.1f}%)")
    if runners_per_race:
        rp = sorted(runners_per_race)
        print("\nrunners per WIN race:")
        print(f"  min={rp[0]}  median={st.median(rp)}  "
              f"mean={st.mean(rp):.1f}  max={rp[-1]}")


if __name__ == "__main__":
    main()
