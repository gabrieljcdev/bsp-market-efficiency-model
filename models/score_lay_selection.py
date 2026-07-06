#!/usr/bin/env python3
"""score_lay_selection.py -- Test 4: LAY-SIDE selection (Free Experiment Catalogue).

THE QUESTION (verbatim from the catalogue)
------------------------------------------
Stage-1's "value" picks drift OUT +31.66% vs a +14.12% baseline -- the WRONG side
for backing, exactly the RIGHT side for laying. Does laying those selections
produce positive lay-CLV, out of sample, AFTER the hardened verdict?

This scores EXISTING selections FLIPPED to the lay side. No new features, no
re-tuning Stage-1/2. It reads models/stage2_scored.csv (model_prob, market_prob,
blend_prob, score_struck=wap, score_bsp, score_pos -- all already computed) and
lays two selections:

  V1 (the live question) -- lay the model's BACK-VALUE picks: model_prob >
     market_prob (the model rates the horse higher than the pre-off market price
     implies). This is the +32% drift cohort; laying it is the captured-drift bet.
  V2 (classic lay-side control) -- lay the model's OVER-PRICED picks: model_prob <
     market_prob (the model rates the horse LOWER than the market). The symmetric
     mirror; expected priced, but it tells us whether V1 is drift-capture or noise.

market_prob is the PRE-OFF, per-race renormalised wap-implied probability written
by stage2_blend.py -- NEVER BSP. So the selection touches no post-race column
(leakage guard). struck = score_struck (wap); we lay at wap, settle at BSP.

THE HARDENED VERDICT (both gates required for RULED-IN)
------------------------------------------------------
1. PRICE-BAND-STRATIFIED LAY-ALL NULL. Longshots systematically drift WAP->BSP,
   so a longshot-heavy lay selection inherits positive lay-CLV as pure FLB/timing
   artifact (the exact mirror of the trainer_course_sr false positive). Each
   selected horse is benchmarked against the mean lay-CLV of ALL runners in its
   OWN BSP band; the selection must beat that band-matched lay-ALL on val AND
   holdout. This band-matched null is the whole test.
2. BRIER CORROBORATION. The blend must beat BSP on Brier over the selection's
   holdout horses. A lay-CLV number with no probability edge behind it is priced.

Split: discovery (date <= 2023-12-31) = the val partition | holdout (> cutoff).
Same split as every prior test; not re-split here. Commission 5% (net, not 2%).

Outputs models/lay_selection_results.json and prints a report. Verdicts:
  PRICED / RULED-IN / ARTIFACT-NAMED (raw lay-CLV positive but eaten by the null).
"""
import os
import sys
import csv
import json
import math
import statistics as st

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backtest"))
import clv          # noqa: E402  -- canonical parse/id/settle helpers
import lay_clv      # noqa: E402  -- the lay-side metric harness (pinned by test_lay_clv)

STAGE2 = os.path.join(_ROOT, "models", "stage2_scored.csv")
OUT_JSON = os.path.join(_ROOT, "models", "lay_selection_results.json")

SPLIT_CUTOFF = "2023-12-31"     # discovery (val) <= cutoff | holdout > cutoff
COMMISSION = lay_clv.DEFAULT_COMMISSION      # 0.05, net (not 2%)
THIN_HOLDOUT_N = 2000
EDGE_TOL = 0.01                 # +/-1pp floor around the band-matched lay-all null
MIN_BRIER_COVERAGE = 0.5

# Fine BSP bands for the STRATIFIED null -- identical edges to run_strategy's
# hardened back-side null, so the two sides neutralise composition the same way.
_PRICE_BAND_EDGES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
                     10.0, 15.0, 20.0, 30.0, 50.0, float("inf"))
_N_BANDS = len(_PRICE_BAND_EDGES) - 1
MIN_BAND_N = 50                 # thin band -> fall back to the global lay-all mean

# Coarse bands for the human-facing "where does any effect live" cut (brief).
_COARSE_EDGES = (1.0, 2.0, 3.0, 6.0, 12.0, float("inf"))
_COARSE_LABELS = ["1-2", "2-3", "3-6", "6-12", "12+"]
THIN_TAIL_BSP = 12.0            # liquidity flag: an "edge" living only in bsp>12


def _band(bsp, edges):
    if not bsp or bsp <= 1.0:
        return None
    for i in range(len(edges) - 1):
        if edges[i] <= bsp < edges[i + 1]:
            return i
    return len(edges) - 2


# --------------------------------------------------------------------------- #
# 1. Single streaming pass: full-field band baselines + the two selections.    #
# --------------------------------------------------------------------------- #
def load_and_select():
    """Read stage2_scored once. Build, per partition:
      * full-field per-fine-band lay-CLV & fixed-liability sums -> the strat null,
      * full-field per-coarse-band the same -> the reporting lay-all,
      * the V1 / V2 selection bet lists (struck, bsp, won, band, blend/bsp probs).
    """
    parts = ("discovery", "holdout")
    # full-field accumulators
    ff = {p: {"clv_sum": [0.0] * _N_BANDS, "liab_sum": [0.0] * _N_BANDS,
              "n": [0] * _N_BANDS,
              "clv_all": 0.0, "liab_all": 0.0, "n_all": 0,
              "coarse_clv": [0.0] * len(_COARSE_LABELS),
              "coarse_liab": [0.0] * len(_COARSE_LABELS),
              "coarse_n": [0] * len(_COARSE_LABELS)}
          for p in parts}
    sel = {"V1": {p: [] for p in parts}, "V2": {p: [] for p in parts}}
    n_rows = skipped = 0

    with open(STAGE2, newline="") as f:
        for r in csv.DictReader(f):
            n_rows += 1
            d = (r.get("date") or "").strip()
            if not d:
                continue
            p = "discovery" if d <= SPLIT_CUTOFF else "holdout"
            struck = clv._fnum(r.get("score_struck"))
            bsp = clv._fnum(r.get("score_bsp"))
            if not struck or not bsp or struck <= 1.0 or bsp <= 1.0:
                skipped += 1
                continue
            won = (r.get("score_pos") or "").strip() == "1"    # laid horse won -> lay lost
            layclv = lay_clv.lay_closing_line_value(struck, bsp)
            liab = lay_clv.lay_bet_pnl_fixed_liability(struck, won, COMMISSION)

            # full-field baselines (lay EVERY runner) -- the null's raw material
            bi = _band(bsp, _PRICE_BAND_EDGES)
            a = ff[p]
            a["clv_all"] += layclv
            a["liab_all"] += liab
            a["n_all"] += 1
            if bi is not None:
                a["clv_sum"][bi] += layclv
                a["liab_sum"][bi] += liab
                a["n"][bi] += 1
            ci = _band(bsp, _COARSE_EDGES)
            if ci is not None:
                a["coarse_clv"][ci] += layclv
                a["coarse_liab"][ci] += liab
                a["coarse_n"][ci] += 1

            # the two selections (leakage-safe: model_prob vs pre-off market_prob)
            mp = clv._fnum(r.get("model_prob"))
            mkt = clv._fnum(r.get("market_prob"))
            if mp is None or mkt is None:
                continue
            bet = {
                "race_id": r.get("race_id"), "horse": r.get("horse"),
                "struck": struck, "bsp": bsp, "won": won, "band": bi,
                "blend_prob": clv._fnum(r.get("blend_prob")),
                "bsp_implied_prob": clv._fnum(r.get("bsp_implied_prob")),
            }
            if mp > mkt:
                sel["V1"][p].append(bet)
            elif mp < mkt:
                sel["V2"][p].append(bet)
    return ff, sel, n_rows, skipped


# --------------------------------------------------------------------------- #
# 2. Band-stratified lay-all null + the edge over it.                          #
# --------------------------------------------------------------------------- #
def strat_null(bets, ffp):
    """Mean band-matched lay-ALL lay-CLV and fixed-liability ROI for a selection.

    Each selected horse is scored against the FULL FIELD's mean in its OWN BSP
    band (same partition). A band with < MIN_BAND_N full-field runners falls back
    to the global lay-all mean, so a sparse bucket can't dominate the baseline.
    Returns (null_layclv, null_roi_liab, n) or (None, None, 0)."""
    clv_glob = (ffp["clv_all"] / ffp["n_all"]) if ffp["n_all"] else None
    liab_glob = (ffp["liab_all"] / ffp["n_all"]) if ffp["n_all"] else None
    s_clv = s_liab = 0.0
    n = 0
    for b in bets:
        bi = b["band"]
        if bi is not None and ffp["n"][bi] >= MIN_BAND_N:
            s_clv += ffp["clv_sum"][bi] / ffp["n"][bi]
            s_liab += ffp["liab_sum"][bi] / ffp["n"][bi]
        elif clv_glob is not None:
            s_clv += clv_glob
            s_liab += liab_glob
        else:
            continue
        n += 1
    if not n:
        return None, None, 0
    return s_clv / n, s_liab / n, n


def brier_gate(bets):
    """Blend-vs-BSP Brier over the selection's OWN horses (read-only, stage-2).

    A real probability edge means the blend separates winners better than the
    market on these exact horses -> blend Brier < BSP Brier. Returns None if no
    covered horse; else the two Briers, coverage and whether the blend beats BSP.
    """
    bl = bs = 0.0
    n = 0
    for b in bets:
        blp, bip = b.get("blend_prob"), b.get("bsp_implied_prob")
        if blp is None or bip is None:
            continue
        y = 1.0 if b["won"] else 0.0
        bl += (blp - y) ** 2
        bs += (bip - y) ** 2
        n += 1
    if not n:
        return None
    return {"n": n, "coverage": n / len(bets),
            "blend_brier": bl / n, "bsp_brier": bs / n,
            "blend_beats_bsp": (bl / n) < (bs / n),
            "sufficient": (n / len(bets)) >= MIN_BRIER_COVERAGE}


def coarse_cut(bets, ffp):
    """Per coarse BSP band: selection lay-CLV vs the lay-ALL band mean + edge.
    Shows where any effect lives and whether it's monotone-in-price (the artifact
    signature: longshot bands carry all the positive lay-CLV)."""
    rows = []
    by = {i: [] for i in range(len(_COARSE_LABELS))}
    for b in bets:
        ci = _band(b["bsp"], _COARSE_EDGES)
        if ci is not None:
            by[ci].append(b)
    for i, lab in enumerate(_COARSE_LABELS):
        bs = by[i]
        if not bs:
            rows.append({"band": lab, "n": 0})
            continue
        sel_clv = st.mean(lay_clv.lay_closing_line_value(b["struck"], b["bsp"]) for b in bs)
        sel_roi = st.mean(lay_clv.lay_bet_pnl_fixed_liability(b["struck"], b["won"], COMMISSION)
                          for b in bs)
        all_clv = (ffp["coarse_clv"][i] / ffp["coarse_n"][i]) if ffp["coarse_n"][i] else None
        rows.append({
            "band": lab, "n": len(bs),
            "sel_lay_clv": sel_clv, "layall_lay_clv": all_clv,
            "edge_lay_clv": (sel_clv - all_clv) if all_clv is not None else None,
            "sel_roi_liab": sel_roi,
        })
    return rows


def liquidity_flag(bets, headline_edge):
    """Does any lay edge live entirely in the illiquid bsp>12 tail? Split the
    selection at bsp=12 and report each half's lay-CLV + share. morning_vol is not
    carried in stage2_scored, so band concentration is the liquidity proxy here."""
    thin = [b for b in bets if b["bsp"] > THIN_TAIL_BSP]
    thick = [b for b in bets if b["bsp"] <= THIN_TAIL_BSP]
    f = lambda bs: (st.mean(lay_clv.lay_closing_line_value(b["struck"], b["bsp"]) for b in bs)
                    if bs else None)
    return {
        "thin_tail_bsp_gt": THIN_TAIL_BSP,
        "n_thin": len(thin), "share_thin": len(thin) / len(bets) if bets else 0.0,
        "lay_clv_thin_bsp_gt12": f(thin),
        "lay_clv_thick_bsp_le12": f(thick),
        "note": "morning_vol not carried in stage2_scored; band concentration used "
                "as the liquidity proxy. Laying 12+ shots at size is not matchable "
                "in thin markets.",
    }


# --------------------------------------------------------------------------- #
# 3. Verdict -- decided on holdout, corroborated on val, both gates required.  #
# --------------------------------------------------------------------------- #
def verdict(disc, hold):
    """PRICED / RULED-IN / ARTIFACT-NAMED / thin.

    ARTIFACT-NAMED is the specific answer the brief asks us to name: the raw
    selection lay-CLV is positive (looks like a lay edge) but collapses onto the
    band-matched lay-ALL null -- the +32% drift was the BAND COMPOSITION talking,
    not the model. RULED-IN needs the band-null edge to hold on val AND holdout
    beyond the floor AND the blend to beat BSP on Brier."""
    hn = hold["n"]
    he, de = hold["edge_lay_clv"], disc["edge_lay_clv"]
    raw_h = hold["mean_lay_clv"]
    br = hold["brier"]

    if hn < THIN_HOLDOUT_N or he is None:
        return "thin", (f"holdout selection n={hn:,} < {THIN_HOLDOUT_N:,} -- too "
                        "thin to judge the lay-CLV null.")

    if he <= EDGE_TOL:
        if raw_h is not None and raw_h > EDGE_TOL:
            return "ARTIFACT-NAMED", (
                f"raw holdout lay-CLV {raw_h:+.2%} looks like a lay edge, but against "
                f"the price-band-matched lay-ALL null it is only {he:+.2%} (<= +{EDGE_TOL:.0%}) "
                f"-- the drift was the BSP-BAND COMPOSITION talking, not the model. "
                f"Longshots drift WAP->BSP and the selection merely inherits that FLB/timing "
                f"artifact; there is no model lay-CLV once composition is matched.")
        return "PRICED", (
            f"holdout lay-CLV vs the band-matched lay-ALL null is {he:+.2%} "
            f"(<= +{EDGE_TOL:.0%}) and the raw lay-CLV ({raw_h:+.2%}) offers nothing "
            f"either -- no harvestable lay edge, the close is the better lay price.")

    if de is None or de <= EDGE_TOL:
        d_txt = f"{de:+.2%}" if de is not None else "n/a"
        return "PRICED", (
            f"holdout lay-CLV edge over the band-null {he:+.2%} is NOT corroborated on "
            f"val ({d_txt} <= +{EDGE_TOL:.0%}) -- not stable out of sample.")

    if br is None or not br.get("sufficient"):
        cov = f"{br['coverage']:.0%}" if br else "n/a"
        return "PRICED", (
            f"holdout lay-CLV edge {he:+.2%} holds val ({de:+.2%}) but the blend covers "
            f"only {cov} of the selection (< {MIN_BRIER_COVERAGE:.0%}) -- no probability "
            f"edge to corroborate it, so not harvestable.")
    if not br.get("blend_beats_bsp"):
        return "PRICED", (
            f"holdout lay-CLV edge {he:+.2%} holds val ({de:+.2%}) but is NOT backed by a "
            f"probability edge (blend Brier {br['blend_brier']:.5f} >= BSP {br['bsp_brier']:.5f}) "
            f"-- CLV-relative only, the favourite-longshot artifact, not harvestable lay edge.")

    return "RULED-IN", (
        f"holdout lay-CLV edge over the band-matched lay-ALL null {he:+.2%} holds val "
        f"({de:+.2%}) beyond the +{EDGE_TOL:.0%} floor on n={hn:,} AND the blend beats BSP on "
        f"Brier over the selection ({br['blend_brier']:.5f} < {br['bsp_brier']:.5f}) -- a real, "
        f"probability-backed lay edge out of sample.")


# --------------------------------------------------------------------------- #
# 4. Score one variant across both partitions.                                 #
# --------------------------------------------------------------------------- #
def score_variant(name, sel, ff):
    out = {"variant": name}
    blocks = {}
    for p in ("discovery", "holdout"):
        bets = sel[p]
        if not bets:
            blocks[p] = {"n": 0}
            continue
        s = lay_clv.summarise_lay(bets, COMMISSION)
        null_clv, null_roi, nn = strat_null(bets, ff[p])
        blk = {
            "n": s["n_bets"],
            "mean_lay_clv": s["mean_lay_clv"],
            "median_lay_clv": s["median_lay_clv"],
            "pct_drifted": s["pct_drifted"],
            "roi_liab": s["roi_liab"], "roi_liab_bsp": s["roi_liab_bsp"],
            "roi_stake": s["roi_stake"], "roi_stake_bsp": s["roi_stake_bsp"],
            "layall_null_lay_clv": null_clv,
            "layall_null_roi_liab": null_roi,
            "edge_lay_clv": (s["mean_lay_clv"] - null_clv) if null_clv is not None else None,
            "edge_roi_liab": (s["roi_liab"] - null_roi) if null_roi is not None else None,
            "brier": brier_gate(bets),
            "coarse_cut": coarse_cut(bets, ff[p]),
            "liquidity": liquidity_flag(bets, None),
        }
        blocks[p] = blk
    out["discovery"], out["holdout"] = blocks["discovery"], blocks["holdout"]
    if blocks["holdout"].get("n", 0) and blocks["discovery"].get("n", 0):
        out["verdict"], out["verdict_reason"] = verdict(blocks["discovery"], blocks["holdout"])
    else:
        out["verdict"], out["verdict_reason"] = "thin", "empty partition."
    return out


# --------------------------------------------------------------------------- #
# 5. Main + report.                                                            #
# --------------------------------------------------------------------------- #
def main():
    print(f"Reading {os.path.relpath(STAGE2, _ROOT)} ...")
    ff, sel, n_rows, skipped = load_and_select()
    print(f"  rows {n_rows:,}  (skipped {skipped:,} for missing struck/bsp)")
    for p in ("discovery", "holdout"):
        print(f"  full-field lay-able @ {p:<9}: {ff[p]['n_all']:,}")

    res = {
        "test": "test_4_lay_side_selection",
        "source": os.path.relpath(STAGE2, _ROOT),
        "split_cutoff": SPLIT_CUTOFF, "commission": COMMISSION,
        "thresholds": {"thin_holdout_n": THIN_HOLDOUT_N, "edge_tol": EDGE_TOL},
        "selection_defs": {
            "V1": "lay model_prob > market_prob (back-value picks; captured drift)",
            "V2": "lay model_prob < market_prob (over-priced; symmetric control)",
        },
        "variants": {},
    }
    for name in ("V1", "V2"):
        res["variants"][name] = score_variant(name, sel[name], ff)

    with open(OUT_JSON, "w") as f:
        json.dump(res, f, indent=2, default=float)
    _report(res)
    print(f"\nwrote {os.path.relpath(OUT_JSON, _ROOT)}")


def _report(res):
    pc = lambda x: f"{x:+.2%}" if x is not None else "    --"
    print("\n" + "=" * 78)
    print("TEST 4 -- LAY-SIDE SELECTION   (struck=wap, settle=bsp, comm 5%, net)")
    print("=" * 78)
    for name in ("V1", "V2"):
        v = res["variants"][name]
        print(f"\n--- {name}: {res['selection_defs'][name]} ---")
        print(f"{'':<30}{'val (disc)':>14}{'holdout':>14}")
        d, h = v["discovery"], v["holdout"]
        print(f"{'lays':<30}{d.get('n',0):>14,}{h.get('n',0):>14,}")
        if not (d.get("n") and h.get("n")):
            print("  (empty partition)"); continue
        print(f"{'mean lay-CLV':<30}{pc(d['mean_lay_clv']):>14}{pc(h['mean_lay_clv']):>14}")
        print(f"{'median lay-CLV':<30}{pc(d['median_lay_clv']):>14}{pc(h['median_lay_clv']):>14}")
        print(f"{'price drifted (>0)':<30}{d['pct_drifted']:>13.1%}{h['pct_drifted']:>14.1%}")
        print("  -- band-matched lay-ALL null (favourite-longshot-neutral) --")
        print(f"{'  lay-ALL null lay-CLV':<30}"
              f"{pc(d['layall_null_lay_clv']):>14}{pc(h['layall_null_lay_clv']):>14}")
        print(f"{'  EDGE vs null (HEADLINE)':<30}"
              f"{pc(d['edge_lay_clv']):>14}{pc(h['edge_lay_clv']):>14}")
        print("  -- realised lay ROI (net comm) --")
        print(f"{'  ROI fixed-liability':<30}{pc(d['roi_liab']):>14}{pc(h['roi_liab']):>14}")
        print(f"{'  ROI fixed-liab @BSP':<30}{pc(d['roi_liab_bsp']):>14}{pc(h['roi_liab_bsp']):>14}")
        print(f"{'  ROI fixed-stake':<30}{pc(d['roi_stake']):>14}{pc(h['roi_stake']):>14}")
        br = h.get("brier")
        if br:
            verb = "<" if br["blend_beats_bsp"] else ">="
            print(f"  -- Brier gate (holdout selection, {br['coverage']:.0%} covered) --")
            print(f"    blend {br['blend_brier']:.5f} {verb} BSP {br['bsp_brier']:.5f}"
                  f"  -> blend beats BSP: {'YES' if br['blend_beats_bsp'] else 'NO'}")
        print("  -- lay-CLV by BSP band (holdout): sel vs lay-ALL, edge --")
        print(f"    {'band':>6}{'n':>8}{'sel CLV':>11}{'layALL':>11}{'edge':>11}{'ROIliab':>11}")
        for row in h["coarse_cut"]:
            if not row.get("n"):
                print(f"    {row['band']:>6}{0:>8}"); continue
            print(f"    {row['band']:>6}{row['n']:>8,}{pc(row['sel_lay_clv']):>11}"
                  f"{pc(row['layall_lay_clv']):>11}{pc(row['edge_lay_clv']):>11}"
                  f"{pc(row['sel_roi_liab']):>11}")
        lq = h["liquidity"]
        print(f"  -- liquidity: {lq['share_thin']:.1%} of lays in bsp>12 "
              f"(lay-CLV there {pc(lq['lay_clv_thin_bsp_gt12'])} vs "
              f"{pc(lq['lay_clv_thick_bsp_le12'])} in bsp<=12) --")
        print(f"\n  VERDICT [{name}]: {v['verdict']}")
        print(f"  {v['verdict_reason']}")
    print("\n" + "=" * 78)


if __name__ == "__main__":
    main()
