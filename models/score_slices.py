#!/usr/bin/env python3
"""score_slices.py -- NARROW-SUBPOPULATION probe: four mechanism-first slices.

Tests whether the ALREADY-BUILT, leakage-clean rolling-form feature set finds an
edge inside four narrow subpopulations, each chosen for a MECHANISM -- a plausible
reason the market could be softer there. Parallel analysis; touches no pipeline.

NOTE ON THE SLICES: the brief titled this "four mechanism-first slices" but the
specific four were truncated in transmission. These four are defensible stand-ins,
each with its market-softness mechanism; the harness is generic (SLICES below), so
swapping in different predicates is a one-line change.

  1. lowclass   Class 6-7 flat            -- least professional money in the lowest
                                             grades; public model may find edge.
  2. bigfield   >=16-runner flat handicap -- maximal pricing complexity; hardest
                                             races for the market to price per-runner.
  3. staying    >=12f flat                -- stamina/form over raw speed; market may
                                             lean on speed the trip discounts.
  4. sellers    sellers/claimers flat     -- softest money, connections-driven, the
                                             lowest grade of all.

THE DISCIPLINE (same as tonight's tests):
  * WITHIN-SLICE null, never the whole-field null -- the market's own within-race
    ranking IN the slice (BSP-implied prob) + a price-band-stratified back-all@BSP
    null computed INSIDE the slice. A false edge hides in a whole-field null.
  * CANARY power check per slice: an rpr-augmented model (rpr is POST-RACE) MUST beat
    the market on the slice's holdout Brier. If even rpr can't -- the slice is too
    small to detect an edge and a PRICED verdict would be underpowered noise, so the
    verdict is INCONCLUSIVE, not priced. Small slices need this most.
  * Brier corroboration is the probability gate; the @BSP stratified edge is money.
  * Discovery/holdout split; verdict on holdout, corroborated on discovery.

PRE-REGISTERED BAR (printed up front, applied per slice, all on HOLDOUT):
  POWER : canary(rpr) Brier < market Brier by > 1e-4      (else INCONCLUSIVE)
  PROB  : blend Brier < market Brier by > 1e-4            (a real probability edge)
  MONEY : blend top-pick ROI@BSP beats the within-slice price-band-stratified
          back-all@BSP null by > +1.0% net commission
  CORROB: PROB and MONEY hold with the same sign on discovery
  RULED-IN needs POWER + PROB + MONEY + CORROB; otherwise PRICED (if powered).
"""
import os
import sys
import csv
import json
import re
import math
from collections import defaultdict

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backtest"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clv  # noqa: E402
from score_target_c import (  # noqa: E402  -- reuse the group-softmax cond-logit rig
    fnum, parse_pos, SPLIT_CUTOFF, BRIER_EPS,
    _group_starts, _softmax_groups, fit_condlogit, _brier, _price_band, _N_BANDS,
    MIN_BAND_N,
)

FEAT_CSV = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_feat.csv")
OUT_JSON = os.path.join(_ROOT, "models", "slices_results.json")

FEATURES = ["or", "draw", "lbs", "age", "f_career_runs", "f_days_since",
            "f_win_rate", "f_place_rate", "f_jky_sr", "f_trn_sr"]
COMMISSION = clv.DEFAULT_COMMISSION
EDGE_TOL = 0.01
MIN_HOLDOUT_BETS = 500          # fewer one-per-race @BSP bets -> ROI SE too large to read

_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def dist_num(x):
    v = fnum(x)
    if v is not None:
        return v
    mo = _NUM_RE.search("" if x is None else str(x))
    return float(mo.group()) if mo else None


def field_size(rr):
    fs = fnum(rr.get("ran"))
    return int(fs) if fs else 0


# race-level slice predicates (evaluated on any runner row of the race) ------- #
def _name(rr):
    return (rr.get("race_name") or "").lower()


SLICES = {
    "lowclass":  ("Class 6-7 flat (soft/low-grade money)",
                  lambda rr: rr.get("class") in ("Class 6", "Class 7")),
    "bigfield":  (">=16-runner flat handicap (pricing complexity)",
                  lambda rr: "handicap" in _name(rr) and field_size(rr) >= 16),
    "staying":   (">=12f flat (stamina/form over speed)",
                  lambda rr: (dist_num(rr.get("dist_f")) or 0) >= 12),
    "sellers":   ("sellers/claimers flat (softest money)",
                  lambda rr: any(k in _name(rr) for k in ("seller", "selling", "claim"))),
}


# --------------------------------------------------------------------------- #
# Load flat races once.                                                        #
# --------------------------------------------------------------------------- #
def load_races():
    keep = FEATURES + ["date", "course", "off", "pos", "bsp", "rpr",
                       "type", "class", "ran", "dist_f", "race_name"]
    races = defaultdict(list)
    with open(FEAT_CSV, newline="") as f:
        for r in csv.DictReader(f):
            if r.get("type") != "Flat":
                continue
            races[f"{r['date']}|{r['course']}|{r['off']}"].append(
                {k: r.get(k) for k in keep})
    return races


# --------------------------------------------------------------------------- #
# Build contiguous discovery-first arrays for one set of races.                #
# --------------------------------------------------------------------------- #
def build(races):
    # keep only races with >=2 priced runners and a valid winner
    valid = []
    for rid, rs in races.items():
        priced = [r for r in rs if (fnum(r["bsp"]) or 0) > 1.0]
        if len(priced) < 2:
            continue
        if not any(parse_pos(r["pos"]) == 1 for r in priced):
            continue
        valid.append((rid, priced))
    valid.sort(key=lambda kv: (0 if kv[1][0]["date"] <= SPLIT_CUTOFF else 1, kv[0]))

    disc_rows = 0
    n_disc = 0
    # discovery stats for impute + z
    def col(rlist, key):
        return [fnum(r.get(key)) for r in rlist]

    disc_flat = [r for rid, rs in valid if rs[0]["date"] <= SPLIT_CUTOFF for r in rs]
    gstats = {}
    for f in FEATURES + ["rpr"]:
        xs = [v for v in (fnum(r.get(f)) for r in disc_flat) if v is not None]
        mu = sum(xs) / len(xs) if xs else 0.0
        sd = (sum((x - mu) ** 2 for x in xs) / len(xs)) ** 0.5 if xs else 1.0
        gstats[f] = (mu, sd or 1.0)

    X, rpr, y, bsp, sizes = [], [], [], [], []
    for rid, rs in valid:
        is_d = rs[0]["date"] <= SPLIT_CUTOFF
        sizes.append(len(rs))
        if is_d:
            n_disc += 1
            disc_rows += len(rs)
        for r in rs:
            row = []
            for f in FEATURES:
                v = fnum(r.get(f))
                if v is None:
                    vals = [fnum(x.get(f)) for x in rs]
                    present = [t for t in vals if t is not None]
                    v = (sum(present) / len(present)) if present else gstats[f][0]
                mu, sd = gstats[f]
                row.append((v - mu) / sd)
            X.append(row)
            rv = fnum(r.get("rpr"))
            if rv is None:
                vals = [fnum(x.get("rpr")) for x in rs]
                present = [t for t in vals if t is not None]
                rv = (sum(present) / len(present)) if present else gstats["rpr"][0]
            mu, sd = gstats["rpr"]
            rpr.append((rv - mu) / sd)
            y.append(1.0 if parse_pos(r["pos"]) == 1 else 0.0)
            bsp.append(fnum(r["bsp"]))
    return (np.array(X), np.array(rpr).reshape(-1, 1), np.array(y),
            np.array(bsp), np.array(sizes), n_disc, disc_rows)


# --------------------------------------------------------------------------- #
# Betting: back argmax(prob) per race @BSP, within-slice price-band-strat null. #
# --------------------------------------------------------------------------- #
def betting(prob, bsp, y, part_sizes, row0):
    n_rows = int(part_sizes.sum())
    sl = slice(row0, row0 + n_rows)
    b, yy, pp = bsp[sl], y[sl], prob[sl]
    starts = _group_starts(part_sizes)

    band_pnl = np.zeros(_N_BANDS); band_n = np.zeros(_N_BANDS)
    ff = 0.0
    for i in range(n_rows):
        pnl = clv.back_bet_pnl(b[i], bool(yy[i]), COMMISSION)
        ff += pnl
        bi = _price_band(b[i])
        if bi is not None:
            band_pnl[bi] += pnl; band_n[bi] += 1
    ff_roi = ff / n_rows if n_rows else None
    band_roi = np.where(band_n >= MIN_BAND_N, band_pnl / np.maximum(band_n, 1), np.nan)

    pnls, strat = [], 0.0
    for st, sz in zip(starts, part_sizes):
        k = st + int(np.argmax(pp[st:st + sz]))
        pnls.append(clv.back_bet_pnl(b[k], bool(yy[k]), COMMISSION))
        bi = _price_band(b[k])
        strat += band_roi[bi] if (bi is not None and not np.isnan(band_roi[bi])) else (ff_roi or 0.0)
    pnls = np.array(pnls); n = len(pnls)
    roi = float(pnls.mean())
    return {
        "n_bets": n,
        "roi_bsp": roi,
        "roi_se": float(pnls.std(ddof=1) / math.sqrt(n)) if n > 1 else None,
        "strat_null_bsp": strat / n,
        "edge_vs_strat": roi - strat / n,
    }


# --------------------------------------------------------------------------- #
# Evaluate one slice.                                                          #
# --------------------------------------------------------------------------- #
def eval_slice(races):
    X, rpr, y, bsp, sizes, n_disc, disc_rows = build(races)
    if len(sizes) == 0 or n_disc == 0 or n_disc == len(sizes):
        return None
    starts = _group_starts(sizes)
    dsz = sizes[:n_disc]

    beta = fit_condlogit(X[:disc_rows], y[:disc_rows], dsz)
    model_p = _softmax_groups(X @ beta, starts, sizes)
    q = _softmax_groups(np.log(1.0 / bsp), starts, sizes)

    Xb = np.column_stack([np.log(np.clip(model_p, 1e-12, 1)),
                          np.log(np.clip(q, 1e-12, 1))])
    beta_b = fit_condlogit(Xb[:disc_rows], y[:disc_rows], dsz, l2=0.5)
    blend_p = _softmax_groups(Xb @ beta_b, starts, sizes)

    Xc = np.column_stack([X, rpr])                    # canary: features + rpr (post-race)
    beta_c = fit_condlogit(Xc[:disc_rows], y[:disc_rows], dsz)
    canary_p = _softmax_groups(Xc @ beta_c, starts, sizes)

    def part(dstart, psz, r0):
        sl = slice(r0, r0 + int(psz.sum()))
        yy = y[sl]
        out = {
            "n_races": len(psz), "n_runners": int(psz.sum()),
            "brier_market": _brier(q[sl], yy),
            "brier_model": _brier(model_p[sl], yy),
            "brier_blend": _brier(blend_p[sl], yy),
            "brier_canary": _brier(canary_p[sl], yy),
        }
        out["blend_bet"] = betting(blend_p, bsp, y, psz, r0)
        return out

    disc = part(0, dsz, 0)
    hold = part(n_disc, sizes[n_disc:], disc_rows)
    return {"discovery": disc, "holdout": hold,
            "market_share_blend": float(beta_b[1] / (abs(beta_b[0]) + abs(beta_b[1])))}


def verdict(res):
    d, h = res["discovery"], res["holdout"]
    power = (h["brier_market"] - h["brier_canary"]) > BRIER_EPS
    prob_h = (h["brier_market"] - h["brier_blend"]) > BRIER_EPS
    prob_d = (d["brier_market"] - d["brier_blend"]) > BRIER_EPS
    money_h = h["blend_bet"]["edge_vs_strat"] > EDGE_TOL
    money_d = d["blend_bet"]["edge_vs_strat"] > EDGE_TOL
    can_margin = h["brier_market"] - h["brier_canary"]
    # The canary validates the BRIER channel's power; the betting channel has its own
    # small-sample limit -- below MIN_HOLDOUT_RUNNERS its ROI SE is large, so any @BSP
    # number there is uninterpretable and the decision rests on the powered Brier gate.
    thin_bet = h["blend_bet"]["n_bets"] < MIN_HOLDOUT_BETS
    bet_note = (f" [betting channel underpowered: {h['blend_bet']['n_bets']:,} bets, "
                f"ROI SE +/-{h['blend_bet']['roi_se']:.1%} -- its @BSP figure is noise; "
                f"the verdict rests on the canary-powered Brier gate]") if thin_bet else ""

    if not power:
        return "inconclusive", (
            f"UNDERPOWERED: the rpr canary does NOT beat the market on holdout Brier "
            f"(margin {can_margin:+.5f} <= {BRIER_EPS:g}) on n={h['n_runners']:,} "
            f"runners / {h['n_races']:,} races -- the slice is too small to detect an "
            f"edge, so a PRICED verdict here would be underpowered noise.")
    # A small-sample betting fluke cannot rule in without the (powered) Brier gate;
    # when the betting channel is thin, require the probability edge to carry it.
    if prob_h and prob_d and money_h and money_d and not (thin_bet and not (prob_h and prob_d)):
        return "ruled-in", (
            f"blend beats market on holdout Brier "
            f"({h['brier_market'] - h['brier_blend']:+.5f}) AND the top-pick @BSP edge "
            f"beats the within-slice stratified null by "
            f"{h['blend_bet']['edge_vs_strat']:+.2%}, both corroborated on discovery "
            f"-- a real within-slice edge (canary powered, margin {can_margin:+.5f}).")
    reasons = []
    reasons.append(f"blend Brier vs market {h['brier_market'] - h['brier_blend']:+.5f} "
                   f"(need >{BRIER_EPS:g}{'' if prob_h else ', FAILS'})")
    reasons.append(f"@BSP edge vs within-slice null {h['blend_bet']['edge_vs_strat']:+.2%} "
                   f"+/-{h['blend_bet']['roi_se']:.2%} (need >{EDGE_TOL:.0%}"
                   f"{'' if money_h else ', FAILS'})")
    return "priced", (
        f"canary powered (Brier margin {can_margin:+.5f}) so the test can see an edge, "
        f"but none survives: " + "; ".join(reasons) + ". Within-slice, the market is "
        f"efficient -- no probability edge (the decisive gate)." + bet_note)


def main():
    print("Loading flat races ...")
    races = load_races()
    print(f"  flat races loaded: {len(races):,}\n")
    print(__doc__.split("PRE-REGISTERED BAR")[1].join(["PRE-REGISTERED BAR", ""]).strip())

    results = {}
    for key, (desc, pred) in SLICES.items():
        sub = {rid: rs for rid, rs in races.items() if rs and pred(rs[0])}
        print("\n" + "=" * 78)
        print(f"SLICE '{key}': {desc}")
        print(f"  races in slice: {len(sub):,}")
        res = eval_slice(sub)
        if res is None:
            print("  -- too few races / no split coverage; skipped.")
            results[key] = {"desc": desc, "skipped": True}
            continue
        vd, reason = verdict(res)
        res.update(desc=desc, verdict=vd, verdict_reason=reason)
        results[key] = res
        _report_slice(res)

    with open(OUT_JSON, "w") as f:
        json.dump(results, f, indent=2, default=float)
    print("\n" + "=" * 78)
    print("SUMMARY")
    for key, r in results.items():
        if r.get("skipped"):
            print(f"  {key:<10} skipped"); continue
        h = r["holdout"]
        print(f"  {key:<10} {r['verdict'].upper():<12} "
              f"holdout {h['n_races']:>5,} races | blendBrier-mkt "
              f"{h['brier_market'] - h['brier_blend']:+.5f} | @BSP edge "
              f"{h['blend_bet']['edge_vs_strat']:+.2%} | canary "
              f"{h['brier_market'] - h['brier_canary']:+.5f}")
    print(f"\nwrote {os.path.relpath(OUT_JSON, _ROOT)}")


def _report_slice(r):
    d, h = r["discovery"], r["holdout"]
    p5 = lambda x: f"{x:.5f}"
    pc = lambda x: f"{x:+.2%}"
    print(f"  blend market-share: {r['market_share_blend']:.1%}")
    print(f"  {'':<26}{'discovery':>14}{'holdout':>14}")
    print(f"  {'races':<26}{d['n_races']:>14,}{h['n_races']:>14,}")
    print(f"  {'runners':<26}{d['n_runners']:>14,}{h['n_runners']:>14,}")
    print(f"  {'Brier market':<26}{p5(d['brier_market']):>14}{p5(h['brier_market']):>14}")
    print(f"  {'Brier blend':<26}{p5(d['brier_blend']):>14}{p5(h['brier_blend']):>14}")
    print(f"  {'Brier canary (rpr)':<26}{p5(d['brier_canary']):>14}{p5(h['brier_canary']):>14}")
    print(f"  {'blend-mkt margin':<26}"
          f"{d['brier_market'] - d['brier_blend']:>+14.5f}"
          f"{h['brier_market'] - h['brier_blend']:>+14.5f}")
    print(f"  {'canary-mkt margin (power)':<26}"
          f"{d['brier_market'] - d['brier_canary']:>+14.5f}"
          f"{h['brier_market'] - h['brier_canary']:>+14.5f}")
    db, hb = d["blend_bet"], h["blend_bet"]
    print(f"  {'@BSP pick ROI':<26}{pc(db['roi_bsp']):>14}{pc(hb['roi_bsp']):>14}")
    print(f"  {'within-slice strat null':<26}"
          f"{pc(db['strat_null_bsp']):>14}{pc(hb['strat_null_bsp']):>14}")
    hedge = pc(hb['edge_vs_strat']) + (f" +/-{hb['roi_se']:.2%}" if hb['roi_se'] else "")
    print(f"  {'@BSP edge vs null':<26}{pc(db['edge_vs_strat']):>14}{hedge:>20}")
    print(f"  VERDICT: {r['verdict'].upper()} -- {r['verdict_reason']}")


if __name__ == "__main__":
    main()
