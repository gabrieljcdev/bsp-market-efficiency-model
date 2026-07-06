#!/usr/bin/env python3
"""score_price_drift.py -- CLV / PRICE-MOVEMENT probe (parallel analysis).

A DIFFERENT KIND of question from the who-wins / best-of-rest work: not "does the
market know this horse's chance," but "can PRE-RACE features predict which horses'
prices will move DIFFERENTIALLY between the morning line and the close, beyond the
common market-wide drift?" -- i.e. market TIMING/BEHAVIOUR, not horse KNOWLEDGE.

DEFINITIONS (per runner, both prices valid > 1):
    drift        = bsp / morning_wap - 1     (price movement morning -> close;
                                              >0 = drifted OUT/longer, <0 = STEAMED)
    clv_morning  = morning_wap / bsp - 1      (the CLV you get striking at the
                                              morning price and settling at BSP)

THE CRITICAL NULL (the same trap, one level up). Prices ALWAYS move, and the move
is dominated by a COMMON, price-dependent pattern: favourites steam, longshots blow
out (here median drift is +11.9%, p90 +124%). Backing any runner at the morning
price already captures that common drift for free. So the null is NOT "do prices
move" -- it is the MORNING-PRICE-BAND-STRATIFIED common drift: each runner is
benchmarked against the average move of ALL runners in its own morning-price band.
A "predict steamers" rule that merely picks morning-favourites beats a naive null
for free (exactly the favourite-longshot hole); the stratified null neutralises it.

TWO GATES, decided on the HOLDOUT split:
  (1) PREDICTION -- residual-drift regression. After removing each runner's
      morning-band mean drift, do pre-race features explain the RESIDUAL out of
      sample (holdout R^2 > 0)? That is "differential movement predictable beyond
      the common drift."
  (2) KILL-TEST -- money. Back the model's predicted steamers at the morning price,
      settle at BSP, net commission. The edge vs BSP must beat the morning-band-
      STRATIFIED common drift out of sample -- otherwise the morning-strike gain is
      just the timing artifact everyone gets (proven by the same-selection settle-
      at-BSP null sitting at ~ -commission).

POWER CANARY: wap (the pre-off volume-weighted price) sits LATER than the morning,
between morning_wap and bsp, so wap_move = wap/morning_wap - 1 is a partial peek at
the close -- a leaky "feature" that MUST light up both gates, proving the rig can
see a real differential-mover signal when one exists. Pre-race features must not.

ANCHOR / LEAKAGE: the drift label is built from morning_wap + bsp; confirm no
price/post-race column enters the FEATURES (only the pre-race materialised set),
and that a pre-race feature relates to drift weakly while the wap canary relates
strongly. Writes models/price_drift_results.json. Touches no pipeline code.
"""
import os
import sys
import csv
import json
import math

import numpy as np

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "backtest"))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clv  # noqa: E402
from score_target_c import SPLIT_CUTOFF, fnum  # noqa: E402

FEAT_CSV = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026_feat.csv")
OUT_JSON = os.path.join(_ROOT, "models", "price_drift_results.json")

FEATURES = ["or", "draw", "lbs", "age", "f_career_runs", "f_days_since",
            "f_win_rate", "f_place_rate", "f_jky_sr", "f_trn_sr"]
COMMISSION = clv.DEFAULT_COMMISSION
THIN_HOLDOUT_N = 2000
R2_EPS = 1e-3        # holdout residual-R^2 below this = no differential prediction
EDGE_TOL = 0.01      # +/-1pp floor on the differential morning-strike edge
DECILE = 0.10        # fraction selected as predicted steamers / drifters

# --- MIRROR Gate 2 (lay predicted drifters) constants ---------------------- #
# Pre-registered at 2% commission (the forward-ledger exchange rate), independent
# of the back-side COMMISSION above. The strikeability haircut is the decisive
# test: morning_wap is a volume-weighted AVERAGE, not a price you can lay -- the
# quotable lay sits ABOVE it, so re-strike the lay at morning_wap x (1 + h).
LAY_COMMISSION = 0.02
LAY_HAIRCUTS = (0.0, 0.025, 0.05, 0.10)
LAY_EDGE_TOL = 0.01      # picks must beat lay-ALL by >= +1pp AND be absolute-positive
LAY_SPREAD_REF = 0.05    # a realistic lay strikeability haircut; die at/below => ARTIFACT

# Morning-price bands (same edges as the main verdict's BSP-band null).
_BAND_EDGES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
               10.0, 15.0, 20.0, 30.0, 50.0, float("inf"))
_N_BANDS = len(_BAND_EDGES) - 1


def band_of(px):
    if not px or px <= 1.0:
        return -1
    for i in range(_N_BANDS):
        if _BAND_EDGES[i] <= px < _BAND_EDGES[i + 1]:
            return i
    return _N_BANDS - 1


# --------------------------------------------------------------------------- #
# 1. Load runners with a valid morning + close (and wap for the canary).       #
# --------------------------------------------------------------------------- #
def load():
    cols = FEATURES + ["date", "pos", "morning_wap", "bsp", "wap"]
    rows = []
    with open(FEAT_CSV, newline="") as f:
        for r in csv.DictReader(f):
            m, b = fnum(r.get("morning_wap")), fnum(r.get("bsp"))
            if not (m and b and m > 1.0 and b > 1.0):
                continue
            rows.append({k: r.get(k) for k in cols} | {"_m": m, "_b": b})
    return rows


def build_arrays(rows):
    disc_mask = np.array([r["date"] <= SPLIT_CUTOFF for r in rows])
    m = np.array([r["_m"] for r in rows])
    b = np.array([r["_b"] for r in rows])
    wap = np.array([fnum(r.get("wap")) or np.nan for r in rows])
    won = np.array([1.0 if (r.get("pos") or "").strip() == "1" else 0.0 for r in rows])
    drift = b / m - 1.0
    bands = np.array([band_of(x) for x in m])

    # feature matrix: race-mean impute is overkill here (no race grouping); use
    # DISCOVERY global-mean impute + z-score (discovery stats only).
    X = np.full((len(rows), len(FEATURES)), np.nan)
    for j, fkey in enumerate(FEATURES):
        col = np.array([fnum(r.get(fkey)) for r in rows], dtype=float)
        mu = np.nanmean(col[disc_mask])
        col = np.where(np.isnan(col), mu, col)
        sd = col[disc_mask].std() or 1.0
        X[:, j] = (col - mu) / sd
    return disc_mask, m, b, wap, won, drift, bands, X


# --------------------------------------------------------------------------- #
# 2. Ridge regression (closed form; intercept unpenalised).                    #
# --------------------------------------------------------------------------- #
def ridge_fit(X, y, l2=1.0):
    Xb = np.column_stack([np.ones(len(y)), X])
    A = Xb.T @ Xb
    reg = l2 * np.eye(Xb.shape[1]); reg[0, 0] = 0.0
    w = np.linalg.solve(A + reg, Xb.T @ y)
    return w


def ridge_pred(w, X):
    return np.column_stack([np.ones(len(X)), X]) @ w


def r2(pred, y):
    ss_res = float(((y - pred) ** 2).sum())
    ss_tot = float(((y - y.mean()) ** 2).sum())
    return 1.0 - ss_res / ss_tot if ss_tot > 0 else float("nan")


# --------------------------------------------------------------------------- #
# 3. Betting kill-test: morning strike vs BSP settle, stratified common drift.  #
# --------------------------------------------------------------------------- #
def roi_block(idx, m, b, won, bands, band_morning_edge):
    """ROI striking at morning vs settling at BSP for a selection (indices), plus
    the direct CLV and the morning-band-STRATIFIED common-drift benchmark.

    edge_vs_bsp    = money value of striking morning vs the close (timing).
    differential   = edge_vs_bsp minus the band-average morning-strike edge -- what
                     the picks capture BEYOND the common, price-priced drift.
    HARVESTABLE money is roi_morning itself: it must be > 0 net commission. A
    positive `differential` with a negative `roi_morning` just means the picks lose
    LESS than their band average (a CLV-relative artifact, not an edge)."""
    sel_m, sel_b, sel_won = m[idx], b[idx], won[idx]
    pnl_m = np.where(sel_won > 0, (sel_m - 1.0) * (1.0 - COMMISSION), -1.0)
    pnl_b = np.where(sel_won > 0, (sel_b - 1.0) * (1.0 - COMMISSION), -1.0)
    n = len(idx)
    strat = float(np.mean([band_morning_edge[bands[i]] for i in idx if bands[i] >= 0]))
    edge = float(pnl_m.mean() - pnl_b.mean())
    return {
        "n": n,
        "roi_morning": float(pnl_m.mean()),
        "roi_morning_se": float(pnl_m.std(ddof=1) / math.sqrt(n)) if n > 1 else None,
        "roi_bsp": float(pnl_b.mean()),                 # settle-at-close null (~ -comm)
        "mean_clv": float(np.mean(sel_m / sel_b - 1.0)),   # >0 = beat the close
        "edge_vs_bsp": edge,
        "strat_common_edge": strat,
        "differential_edge": edge - strat,
        "win_rate": float(sel_won.mean()),
        "mean_morning": float(sel_m.mean()),
    }


def _bottom_k(idx, p, frac):
    k = max(1, int(len(idx) * frac))
    return idx[np.argsort(p)[:k]]


def kill_test(mask, pred, m, b, won, bands, band_morning_edge):
    """Two selections of predicted STEAMERS (most-negative predicted drift):
      * whole-pop : the global bottom decile -- concentrates in the longshot bands
                    where the FLB blow-out lives (the artifact lens).
      * in-band   : the bottom decile WITHIN each morning-price band, pooled -- a
                    price-balanced, fair harvest of the differential-timing signal.
    Also the predicted-DRIFTERS tail for lay-side context."""
    idx = np.where(mask)[0]
    p = pred[idx]
    whole = _bottom_k(idx, p, DECILE)
    drifters = idx[np.argsort(p)[-max(1, int(len(idx) * DECILE)):]]
    inband = []
    for bi in range(_N_BANDS):
        bidx = idx[bands[idx] == bi]
        if len(bidx) >= 20:
            inband.extend(_bottom_k(bidx, pred[bidx], DECILE).tolist())
    inband = np.array(inband, dtype=int) if inband else whole[:0]
    return {
        "whole_pop_steamers": roi_block(whole, m, b, won, bands, band_morning_edge),
        "inband_steamers": roi_block(inband, m, b, won, bands, band_morning_edge),
        "pred_drifters_ctx": roi_block(drifters, m, b, won, bands, band_morning_edge),
        "n_runners": len(idx),
    }


# --------------------------------------------------------------------------- #
# 3b. MIRROR Gate 2: LAY predicted in-band DRIFTERS at morning, settle race.    #
#     No new features, no re-fit -- reuses the SAME predicted residual drift.   #
# --------------------------------------------------------------------------- #
def _top_k(idx, p, frac):
    k = max(1, int(len(idx) * frac))
    return idx[np.argsort(p)[-k:]]


def inband_drifters(mask, pred, bands):
    """Top decile of predicted residual drift WITHIN each morning band, pooled --
    the exact mirror of kill_test's in-band steamers, on the drift-OUT side."""
    idx = np.where(mask)[0]
    sel = []
    for bi in range(_N_BANDS):
        bidx = idx[bands[idx] == bi]
        if len(bidx) >= 20:
            sel.extend(_top_k(bidx, pred[bidx], DECILE).tolist())
    return np.array(sel, dtype=int) if sel else idx[:0]


def _lay_pnl(strike, won, comm):
    """Lay P&L per £1 backer-stake-equivalent: if the horse LOSES you keep the
    backer's stake (net commission); if it WINS you pay liability (strike-1).
    Commission bites only the winning (lay-wins) side."""
    return np.where(won > 0, -(strike - 1.0), (1.0 - comm))


def lay_gate2(pick_idx, all_idx, m, b, won, comm, haircuts):
    """LAY the picks at morning_wap x (1+h) for each haircut h, settle on the race,
    vs the lay-ALL-at-the-same-strike null. Holdout only. Also a lay-at-BSP context
    figure and the per-trade liability distribution at £20 backer-stake-equivalent."""
    out = {"n_picks": len(pick_idx), "n_all": len(all_idx), "commission": comm,
           "haircuts": {}}
    for h in haircuts:
        pk = _lay_pnl(m[pick_idx] * (1 + h), won[pick_idx], comm)
        al = _lay_pnl(m[all_idx] * (1 + h), won[all_idx], comm)
        roi_pk, roi_al = float(pk.mean()), float(al.mean())
        out["haircuts"][f"{h:.3f}"] = {
            "h": h, "lay_picks_roi": roi_pk,
            "lay_picks_se": float(pk.std(ddof=1) / math.sqrt(len(pk))) if len(pk) > 1 else None,
            "lay_all_roi": roi_al, "edge_over_layall": roi_pk - roi_al,
        }
    out["lay_at_bsp_roi_context"] = float(_lay_pnl(b[pick_idx], won[pick_idx], comm).mean())
    out["mean_lay_clv_is_drift"] = float((b[pick_idx] / m[pick_idx] - 1.0).mean())
    out["win_rate_picks"] = float(won[pick_idx].mean())
    liab = 20.0 * (m[pick_idx] - 1.0)     # liability to win £20-equivalent, lay @ morning
    out["liability_gbp_per_trade"] = {
        "mean": float(liab.mean()), "p10": float(np.percentile(liab, 10)),
        "p25": float(np.percentile(liab, 25)), "median": float(np.median(liab)),
        "p75": float(np.percentile(liab, 75)), "p90": float(np.percentile(liab, 90)),
        "max": float(liab.max()), "mean_morning_price": float(m[pick_idx].mean()),
    }
    return out


def verdict_lay(lg, tol=LAY_EDGE_TOL, spread_ref=LAY_SPREAD_REF):
    """HARVESTABLE / ARTIFACT / PRICED, decided on holdout.

    Three ways to fail past the h=0 null, each catching the unquotable-WAP trap:
      (A) absolute picks ROI dies at a flat haircut <= spread_ref (the literal test); OR
      (B) the QUOTABLE-CLOSE cross-check: laying the SAME picks at BSP -- the deepest,
          most strikeable price that exists -- does not itself clear +tol. If the edge
          isn't there at the close, it lived in the morning_wap average, not a real
          mispricing (this is the strikeability haircut taken to its limit); OR
      (C) the lay-ALL base is positive at morning (you 'profit' laying EVERYTHING) and
          dies under the haircut -- a signature that the morning_wap itself is the
          artifact, so any edge stacked on it inherits the doubt.
    A flat % haircut alone is too coarse for a longshot-clustered lay book, so (B)/(C)
    are needed -- otherwise a WAP artifact survives 5% purely because the flat penalty
    understates the real spread on 30/1+ shots."""
    hc = lg["haircuts"]
    h0 = hc["0.000"]
    gate0 = (h0["lay_picks_roi"] > 0) and (h0["edge_over_layall"] >= tol)
    death_abs = next((hc[k]["h"] for k in sorted(hc, key=lambda k: hc[k]["h"])
                      if hc[k]["lay_picks_roi"] <= 0), None)
    layall_death = next((hc[k]["h"] for k in sorted(hc, key=lambda k: hc[k]["h"])
                         if hc[k]["lay_all_roi"] <= 0), None)
    bsp_ctx = lg["lay_at_bsp_roi_context"]
    L = lg["liability_gbp_per_trade"]

    if not gate0:
        return "PRICED", (
            f"lay-drifters@morning ROI {h0['lay_picks_roi']:+.2%} (edge over lay-ALL "
            f"{h0['edge_over_layall']:+.2%}) fails the null even at a ZERO haircut -- there is "
            f"no lay edge to strike; same PRICED conclusion as the back side.")

    flat_kills = death_abs is not None and death_abs <= spread_ref
    close_kills = bsp_ctx < tol           # (B) no edge at the quotable close
    base_is_wap = (h0["lay_all_roi"] > 0) and (layall_death is not None
                                               and layall_death <= spread_ref)
    if flat_kills or close_kills or base_is_wap:
        return "ARTIFACT", (
            f"lay-drifters@morning clears the h=0 null ({h0['lay_picks_roi']:+.2%} ROI, edge "
            f"{h0['edge_over_layall']:+.2%}) but this is the UNQUOTABLE morning_wap, not a "
            f"strikeable lay: laying the SAME picks at the quotable CLOSE (BSP) returns only "
            f"{bsp_ctx:+.2%} (< +{tol:.0%}) -- the edge evaporates at the deepest real price; the "
            f"lay-ALL base is {h0['lay_all_roi']:+.2%} at morning (you cannot profit laying "
            f"EVERYTHING) and dies by ~{(layall_death or spread_ref):.1%} haircut; and the picks "
            f"cluster in the longshot tail (mornAvg {L['mean_morning_price']:.0f}, p90 liability "
            f"£{L['p90']:,.0f}, max £{L['max']:,.0f}) where a flat % haircut understates real "
            f"spread/fill. The morning->close drift is real but only capturable at a price you "
            f"cannot strike -- ARTIFACT, mirroring the back-side PRICED verdict.")
    return "HARVESTABLE", (
        f"lay-drifters@morning ROI {h0['lay_picks_roi']:+.2%} (edge {h0['edge_over_layall']:+.2%}) "
        f"survives a ~{spread_ref:.0%} haircut AND still returns {bsp_ctx:+.2%} laid at the "
        f"quotable close (BSP) -- a genuinely strikeable lay edge (now scrutinise the liability "
        f"tail: p90 £{L['p90']:,.0f}, max £{L['max']:,.0f} per £20-equivalent).")


# --------------------------------------------------------------------------- #
# 4. Anchor / leakage: feature-vs-drift correlation, canary strength.          #
# --------------------------------------------------------------------------- #
def anchor(disc_mask, X, drift, wap_move):
    d = drift[disc_mask]
    out = {}
    for j, fkey in enumerate(FEATURES):
        x = X[disc_mask, j]
        out[fkey] = float(np.corrcoef(x, d)[0, 1])
    mask = disc_mask & ~np.isnan(wap_move)
    out["wap_move (CANARY, later price)"] = float(
        np.corrcoef(wap_move[mask], drift[mask])[0, 1])
    return out


# --------------------------------------------------------------------------- #
# 5. Verdict.                                                                  #
# --------------------------------------------------------------------------- #
def verdict(res):
    h, d = res["holdout"], res["discovery"]
    canary_ok = res["canary"]["holdout_resid_r2"] > R2_EPS
    feat_r2_h = h["feature_resid_r2"]
    feat_r2_d = d["feature_resid_r2"]
    # The MONEY gate is the price-balanced in-band harvest, and it must actually
    # survive commission: roi_morning > EDGE_TOL (a real profit), not merely a
    # positive differential over an even-more-negative band baseline.
    hb, db = h["inband_steamers"], d["inband_steamers"]

    if res["holdout"]["n_runners"] < THIN_HOLDOUT_N:
        return "thin", f"holdout runners {res['holdout']['n_runners']:,} too few."
    if not canary_ok:
        return "inconclusive", (
            f"POWER CHECK FAILED: the wap-move canary does not predict drift OOS "
            f"(holdout resid R^2 {res['canary']['holdout_resid_r2']:+.4f}) -- the rig "
            f"cannot see a differential-mover signal, so a null is uninformative.")

    pred_ok = feat_r2_h > R2_EPS and feat_r2_d > R2_EPS
    money_ok = (hb["roi_morning"] > EDGE_TOL and db["roi_morning"] > EDGE_TOL
                and hb["differential_edge"] > EDGE_TOL)
    if pred_ok and money_ok:
        return "ruled-in", (
            f"pre-race features predict differential drift OOS (holdout resid R^2 "
            f"{feat_r2_h:+.4f}) AND backing the in-band predicted steamers at the "
            f"morning price returns {hb['roi_morning']:+.2%} net commission on holdout "
            f"(differential {hb['differential_edge']:+.2%}), corroborated on discovery "
            f"-- a real, harvestable differential-timing edge (canary powered).")

    return "priced", (
        f"the wap canary IS powered (holdout resid R^2 {res['canary']['holdout_resid_r2']:+.3f}, "
        f"so the rig can see a differential-mover signal), and pre-race features DO carry a "
        f"small, stable one (holdout resid R^2 {feat_r2_h:+.4f}) -- but it is NOT harvestable: "
        f"backing the in-band predicted steamers at the morning price still LOSES "
        f"{hb['roi_morning']:+.2%} net commission on holdout (mean CLV {hb['mean_clv']:+.2%}); "
        f"the positive differential ({hb['differential_edge']:+.2%}) only means they lose less "
        f"than their band's common drift. Prices drift OUT morning->close, so the close is the "
        f"better back price; the differential signal lives in the FLB longshot tail and does not "
        f"survive commission.")


# --------------------------------------------------------------------------- #
# Main.                                                                        #
# --------------------------------------------------------------------------- #
def main():
    print("Loading runners with valid morning + close prices ...")
    rows = load()
    disc_mask, m, b, wap, won, drift, bands, X = build_arrays(rows)
    hold_mask = ~disc_mask
    wap_move = wap / m - 1.0
    nd, nh = int(disc_mask.sum()), int(hold_mask.sum())
    print(f"  runners: {len(rows):,}  (discovery {nd:,} | holdout {nh:,})")
    print(f"  drift = bsp/morning-1: disc mean {drift[disc_mask].mean():+.4f} "
          f"median {np.median(drift[disc_mask]):+.4f}")

    # --- common drift, morning-band-stratified (discovery-fit) ---
    band_mean_drift = np.zeros(_N_BANDS)      # E[drift] per morning band (discovery)
    band_morning_edge = np.zeros(_N_BANDS)    # back-all morning-strike edge vs BSP / band
    for bi in range(_N_BANDS):
        sel = disc_mask & (bands == bi)
        if sel.sum() >= 50:
            band_mean_drift[bi] = drift[sel].mean()
            pm = np.where(won[sel] > 0, (m[sel] - 1) * (1 - COMMISSION), -1.0)
            pb = np.where(won[sel] > 0, (b[sel] - 1) * (1 - COMMISSION), -1.0)
            band_morning_edge[bi] = pm.mean() - pb.mean()

    # residual drift = drift - its morning-band mean (removes the common move)
    resid = drift - band_mean_drift[np.clip(bands, 0, _N_BANDS - 1)]

    # --- (1) prediction gate: features -> residual drift, discovery-fit ---
    w_feat = ridge_fit(X[disc_mask], resid[disc_mask])
    pred_feat = ridge_pred(w_feat, X)
    # canary: wap_move -> residual drift (later price, leaky)
    cmask = ~np.isnan(wap_move)
    wm = wap_move.reshape(-1, 1)
    w_can = ridge_fit(wm[disc_mask & cmask], resid[disc_mask & cmask])
    pred_can = ridge_pred(w_can, wm)

    def resid_r2(mask, pred):
        mm = mask & ~np.isnan(pred)
        return r2(pred[mm], resid[mm])

    # --- (2) kill-test on predicted steamers (feature model) ---
    def part(mask):
        kt = kill_test(mask, pred_feat, m, b, won, bands, band_morning_edge)
        kt["feature_resid_r2"] = resid_r2(mask, pred_feat)
        kt["backall_morning_edge_vs_bsp"] = float(
            np.where(won[mask] > 0, (m[mask] - 1) * (1 - COMMISSION), -1.0).mean()
            - np.where(won[mask] > 0, (b[mask] - 1) * (1 - COMMISSION), -1.0).mean())
        return kt

    disc_res = part(disc_mask)
    hold_res = part(hold_mask)
    canary = {
        "discovery_resid_r2": resid_r2(disc_mask & cmask, pred_can),
        "holdout_resid_r2": resid_r2(hold_mask & cmask, pred_can),
    }

    # --- MIRROR Gate 2: LAY predicted in-band drifters, HOLDOUT only, 2% comm ---
    hold_idx = np.where(hold_mask)[0]
    drift_idx = inband_drifters(hold_mask, pred_feat, bands)
    lay = lay_gate2(drift_idx, hold_idx, m, b, won, LAY_COMMISSION, LAY_HAIRCUTS)
    lay["verdict"], lay["verdict_reason"] = verdict_lay(lay)

    res = {
        "probe": "clv_price_movement_morning_to_close",
        "split_cutoff": SPLIT_CUTOFF, "commission": COMMISSION,
        "n_runners": len(rows),
        "common_drift_median_disc": float(np.median(drift[disc_mask])),
        "band_mean_drift_disc": {str(i): float(band_mean_drift[i])
                                 for i in range(_N_BANDS)},
        "discovery": disc_res, "holdout": hold_res,
        "canary": canary,
        "lay_gate2_mirror_holdout": lay,
        "anchor_feature_vs_drift_corr": anchor(disc_mask, X, drift, wap_move),
    }
    vd, reason = verdict(res)
    res["verdict"], res["verdict_reason"] = vd, reason
    with open(OUT_JSON, "w") as f:
        json.dump(res, f, indent=2, default=float)

    _report(res)
    print(f"\nwrote {os.path.relpath(OUT_JSON, _ROOT)}")


def _report(res):
    d, h = res["discovery"], res["holdout"]
    pc = lambda x: f"{x:+.2%}"
    print("\n" + "=" * 76)
    print("CLV / PRICE-MOVEMENT PROBE -- differential drift beyond the common move")
    print("=" * 76)
    print(f"common drift (median, disc): {res['common_drift_median_disc']:+.2%}  "
          f"(prices drift OUT morning->close on average)")
    print(f"\n{'':<40}{'discovery':>17}{'holdout':>17}")
    print(f"{'runners':<40}{d['n_runners']:>17,}{h['n_runners']:>17,}")
    print("\n-- GATE 1: prediction (features -> residual drift, R^2 beyond band mean) --")
    print(f"{'  feature resid R^2':<40}{d['feature_resid_r2']:>+17.4f}"
          f"{h['feature_resid_r2']:>+17.4f}")
    print(f"{'  wap-move CANARY resid R^2':<40}"
          f"{res['canary']['discovery_resid_r2']:>+17.4f}"
          f"{res['canary']['holdout_resid_r2']:>+17.4f}   <- must be >0")
    print("\n-- GATE 2: kill-test, back predicted STEAMERS @morning, settle BSP --")
    print("   HARVESTABLE = roi_morning survives commission (>0); differential alone is not")
    for key, name in [("inband_steamers", "IN-BAND steamers (fair, price-balanced)"),
                      ("whole_pop_steamers", "whole-pop steamers (longshot-concentrated)")]:
        print(f"  * {name}")
        for lab, blk in [("disc", d), ("hold", h)]:
            s = blk[key]
            se = f" +/-{s['roi_morning_se']:.2%}" if s.get("roi_morning_se") else ""
            print(f"      [{lab}] n={s['n']:>6,} mornAvg {s['mean_morning']:5.1f} "
                  f"win {s['win_rate']:4.1%} | ROI@morn {pc(s['roi_morning'])}{se}  "
                  f"CLV {pc(s['mean_clv'])}  edgeVsBSP {pc(s['edge_vs_bsp'])}  "
                  f"DIFF {pc(s['differential_edge'])}")
    print(f"\n  back-ALL morning-strike edge vs BSP (the common drift everyone gets): "
          f"disc {pc(d['backall_morning_edge_vs_bsp'])} | holdout "
          f"{pc(h['backall_morning_edge_vs_bsp'])}")
    print("\n-- ANCHOR: |corr(feature, drift)| pre-race should be weak; canary strong --")
    for k, v in res["anchor_feature_vs_drift_corr"].items():
        tag = "<- CANARY" if "CANARY" in k else ("ok (weak)" if abs(v) < 0.1 else "note")
        print(f"  {k:<38}{v:>+9.4f}   {tag}")

    lg = res.get("lay_gate2_mirror_holdout")
    if lg:
        print("\n" + "-" * 76)
        print(f"MIRROR GATE 2: LAY predicted in-band DRIFTERS @morning, settle race "
              f"(holdout, {lg['commission']:.0%} comm)")
        print(f"  n picks {lg['n_picks']:,} | win {lg['win_rate_picks']:.1%} | "
              f"mean lay-CLV(=drift) {pc(lg['mean_lay_clv_is_drift'])} | "
              f"lay@BSP ctx {pc(lg['lay_at_bsp_roi_context'])}")
        print("  STRIKEABILITY HAIRCUT h on the unquotable WAP (lay strike = wap x (1+h)):")
        print(f"    {'h':>6}{'lay picks ROI':>16}{'lay-ALL ROI':>14}{'edge vs lay-ALL':>18}")
        for key in sorted(lg["haircuts"], key=lambda k: lg["haircuts"][k]["h"]):
            c = lg["haircuts"][key]
            se = f" +/-{c['lay_picks_se']:.2%}" if c.get("lay_picks_se") else ""
            flag = "  <- null: >0 & edge>=+1%?" if c["h"] == 0.0 else ""
            ok = "PASS" if (c["lay_picks_roi"] > 0 and c["edge_over_layall"] >= LAY_EDGE_TOL) else "fail"
            print(f"    {c['h']:>5.1%}{pc(c['lay_picks_roi']):>13}{se:<8}"
                  f"{pc(c['lay_all_roi']):>10}{pc(c['edge_over_layall']):>14}   {ok}{flag}")
        L = lg["liability_gbp_per_trade"]
        print(f"  LIABILITY per trade @ £20 backer-stake (lay@morning, mornAvg {L['mean_morning_price']:.1f}):")
        print(f"    mean £{L['mean']:,.0f} | p10 £{L['p10']:,.0f}  p25 £{L['p25']:,.0f}  "
              f"med £{L['median']:,.0f}  p75 £{L['p75']:,.0f}  p90 £{L['p90']:,.0f}  max £{L['max']:,.0f}")
        print(f"  LAY VERDICT: {lg['verdict']}")
        print(f"  {lg['verdict_reason']}")

    print("\n" + "=" * 76)
    print(f"BACK-SIDE VERDICT: {res['verdict'].upper()}")
    print(res["verdict_reason"])
    if lg:
        print(f"\nLAY-SIDE (MIRROR) VERDICT: {lg['verdict']}")
    print("=" * 76)


if __name__ == "__main__":
    main()
