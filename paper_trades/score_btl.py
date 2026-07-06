#!/usr/bin/env python3
"""score_btl.py -- grade the btl_3jul.json paper-trade ledger against actual BSPs.

For each pick (back £20 at the EX2 strike, greened exit = lay at BSP, 2% comm):
    realised_clv      = strike / bsp - 1          (>0 => struck a bigger price than
                                                   the close; good for the backer)
    realised_net_pnl  = 20 * (strike/bsp - 1),  x0.98 when positive
                        (greened back-to-lay locks this profit regardless of result;
                         commission bites only a winning book)
and compares realised vs the logged band-median PREDICTION.

BSP INPUT (pick either):
  --bsp FILE.json    {"Horse Name": 7.4, ...}  or  {"market_id": {"Horse": 7.4}}
                     horse names matched via canon_horse (country-suffix safe).
  --results FILE     an rpscrape results JSON/CSV pull; BSP read per runner and
                     matched to each pick by (market_id if present) else canon_horse.

Writes the realised fields back into the ledger (in place, unless --dry-run) and
prints the ledger table. 6 picks is ANECDOTE, not evidence -- printed on the header.
"""
import os, sys, json, csv, argparse
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "features"))
try:
    from history_join import canon_horse
except Exception:                       # keep the scorer runnable in isolation
    def canon_horse(n):
        return ((" ".join(str(n).split()).lower() if n else None), None)

STAKE, COMM = 20.0, 0.02
LEDGER = os.path.join(_ROOT, "paper_trades", "btl_3jul.json")


def realised(strike, bsp):
    clv = strike / bsp - 1.0
    raw = STAKE * clv
    return clv, (raw * (1 - COMM) if raw > 0 else raw)


def fnum(x):
    try:
        v = float(x); return v if v == v else None
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- #
# BSP sources.                                                                 #
# --------------------------------------------------------------------------- #
def bsp_from_json(path):
    """Flat {horse: bsp} or nested {market_id: {horse: bsp}} -> lookups."""
    raw = json.load(open(path))
    by_horse, by_mkt = {}, {}
    def add_horse(h, v):
        v = fnum(v)
        if v: by_horse[canon_horse(h)[0]] = v
    if all(isinstance(v, dict) for v in raw.values()):
        for mkt, runners in raw.items():
            by_mkt[str(mkt)] = {canon_horse(h)[0]: fnum(v) for h, v in runners.items()}
            for h, v in runners.items():
                add_horse(h, v)
    else:
        for h, v in raw.items():
            add_horse(h, v)
    return by_horse, by_mkt


def bsp_from_results(path):
    """Best-effort BSP extraction from an rpscrape results pull (JSON or CSV).
    Matches by canon_horse; market_id used when the source carries one."""
    by_horse, by_mkt = {}, {}
    if path.endswith(".json"):
        data = json.load(open(path))
        def walk(o):
            if isinstance(o, dict):
                name = o.get("horse") or o.get("name")
                bsp = o.get("bsp") or o.get("BSP") or o.get("bfsp")
                if name and fnum(bsp):
                    by_horse[canon_horse(name)[0]] = fnum(bsp)
                for v in o.values():
                    walk(v)
            elif isinstance(o, list):
                for v in o: walk(v)
        walk(data)
    else:
        for row in csv.DictReader(open(path, newline="")):
            name = row.get("horse") or row.get("name")
            bsp = row.get("bsp") or row.get("BSP") or row.get("bfsp")
            if name and fnum(bsp):
                by_horse[canon_horse(name)[0]] = fnum(bsp)
    return by_horse, by_mkt


def lookup(pick, by_horse, by_mkt):
    ch = canon_horse(pick["horse"])[0]
    m = by_mkt.get(str(pick.get("market_id")))
    if m and ch in m and m[ch]:
        return m[ch]
    return by_horse.get(ch)


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description="Grade the BTL paper-trade ledger vs actual BSPs.")
    ap.add_argument("--bsp", help="JSON of {horse: bsp} or {market_id: {horse: bsp}}")
    ap.add_argument("--results", help="rpscrape results pull (JSON/CSV) to read BSP from")
    ap.add_argument("--ledger", default=LEDGER)
    ap.add_argument("--dry-run", action="store_true", help="print only; do not write back")
    args = ap.parse_args()

    led = json.load(open(args.ledger))
    by_horse, by_mkt = {}, {}
    if args.bsp:
        by_horse, by_mkt = bsp_from_json(args.bsp)
    elif args.results:
        by_horse, by_mkt = bsp_from_results(args.results)

    print("BTL PAPER-TRADE LEDGER -- realised vs predicted")
    print("*** 6 picks is ANECDOTE, NOT evidence. Forward CLV ledger seed, not a verdict. ***\n")
    hdr = ("{:<30}{:<16}{:>7}{:>8}{:>8}{:>9}{:>9}{:>9}".format(
        "race", "pick", "strike", "predBSP", "actBSP", "realCLV", "realP&L", "vsPred"))
    print(hdr)
    n_graded = 0
    sum_pred = sum_real = 0.0
    for p in led["picks"]:
        bsp = lookup(p, by_horse, by_mkt) if (by_horse or by_mkt) else None
        pred = p["predicted_net_pnl_median"]
        if bsp:
            clv, pnl = realised(p["strike_ex2"], bsp)
            p["realised"] = {"bsp": bsp, "clv": round(clv, 4),
                             "net_pnl": round(pnl, 4),
                             "vs_pred": round(pnl - pred, 4)}
            n_graded += 1
            sum_pred += pred; sum_real += pnl
            print("{:<30}{:<16}{:>7.2f}{:>8.2f}{:>8.2f}{:>+9.2%}{:>+9.2f}{:>+9.2f}".format(
                p["race"][:30], p["horse"][:16], p["strike_ex2"],
                p["predicted_bsp_median"], bsp, clv, pnl, pnl - pred))
        else:
            print("{:<30}{:<16}{:>7.2f}{:>8.2f}{:>8}{:>9}{:>9}{:>9}".format(
                p["race"][:30], p["horse"][:16], p["strike_ex2"],
                p["predicted_bsp_median"], "  --", "  --", "  --", "  --"))
    if n_graded:
        print(f"\ngraded {n_graded}/{len(led['picks'])} picks | "
              f"predicted net £{sum_pred:+.2f} | realised net £{sum_real:+.2f} | "
              f"realised-minus-predicted £{sum_real - sum_pred:+.2f}")
        led["realised_summary"] = {
            "n_graded": n_graded, "predicted_net_gbp": round(sum_pred, 4),
            "realised_net_gbp": round(sum_real, 4),
            "realised_minus_predicted_gbp": round(sum_real - sum_pred, 4)}
    else:
        print("\nNo BSPs supplied yet -- pass --bsp or --results to grade. Predictions stand:")
        print(f"  predicted portfolio net @ median £"
              f"{sum(p['predicted_net_pnl_median'] for p in led['picks']):+.2f}")

    if not args.dry_run and n_graded:
        json.dump(led, open(args.ledger, "w"), indent=2)
        print(f"\nwrote realised fields back to {os.path.relpath(args.ledger, _ROOT)}")


if __name__ == "__main__":
    main()
