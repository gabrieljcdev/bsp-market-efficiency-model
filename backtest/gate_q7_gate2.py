"""Q7 — Gate 2 (edge, survivors only). Runs only because Gate 1 PASSED the fillability
bar (>=£50 stale quote in 12.8% of NR events > 10% bar; §12 Amendment 2, Part C).

THE TRADE (frozen, Amendment 2). On a qualifying pre-off NR removal, for each survivor
with a >=2-tick-stale quote vs the RF benchmark P_fair = P_pre*(1-A) in t+1..t+30s:
  * ENTER at 1 s latency (act on the t+(k+1) book), £50 backer-stake cap per runner,
    on the stale side (BACK a too-long price / LAY a too-short one).
  * EXIT at the touch at t+300s (close the position: a back is closed by laying the
    best-lay, a lay by backing the best-back).
  * P&L net 2% commission on booked profit.

THE NULL (frozen). The identical entry/exit at **matched random non-NR moments**,
band-matched by price and time-to-off. Implemented as control moments sampled in the
SAME markets (>=120 s away from any removal), anchored to their own t_c-1s best-back
with A=0 (no RF shift) — so the control measures the AMBIENT return of the same
mechanical "fade a >=2-tick-stale quote, hold 5 min" trade absent a removal. The
removal edge is (NR P&L - null P&L) within each price-band × time-to-off cell.

VERDICT (decided before any money narrative, on holdout; §7 + Amendment 1 parity):
  edge = band×tto-matched (NR mean - null mean) net-2% P&L per trade must be **> 0 AND
  hold same-sign on discovery AND on both odd/even ISO-week parities** — any
  disagreement = FAIL. A positive raw NR P&L that does not beat the ambient null, or
  that flips across a split, is not a harvestable removal edge.

Reuses the Gate-1 event finder + snapshot replay from gate_q7_nonrunner (unit-tested).
"""
from __future__ import annotations

import bz2
import io
import json
import random
import tarfile
from collections import Counter, defaultdict
from datetime import date as _date
from typing import Dict, List, Optional, Tuple

from backtest.pro_stream import (Market, load_gb_courses, market_verdict,
                                 peek_market_definition, ticks_move)
from backtest.gate_preoff import off_epoch_ms, dist_furlongs
from backtest.gate_q7_nonrunner import (find_removal_events, _replay_targets,
                                        POST_MAX_S, OPP_MAX_K, STAKE_CAP, STALE_TICKS)

COMMISSION = 0.02
FILL_MIN = 50.0                 # a trade needs >=£50 matched to be taken (Gate-1 unit)
N_CTRL = 2                      # control moments sampled per NR market
CTRL_GAP_S = 120               # control moments kept >=120s from any removal
PRICE_BANDS = (1.0, 2.0, 3.0, 4.0, 6.0, 10.0, 20.0, 50.0, float("inf"))
TTO_BUCKETS = ((0, 120), (120, 300), (300, 600), (600, 1800), (1800, 10 ** 9))


# --------------------------------------------------------------------------- #
# Trade P&L (pinned + unit-tested; convention-safe green-up round trip)        #
# --------------------------------------------------------------------------- #
def trade_pnl(side: str, p_in: float, p_out: float, stake: float,
              commission: float = COMMISSION) -> float:
    """Booked profit of opening ``stake`` (backer-stake £) at ``p_in`` and closing at the
    ``p_out`` touch, net commission on positive profit.

    BACK opened, closed by LAY:  profit = stake*(p_in - p_out)/p_out  (profit if price shortened)
    LAY  opened, closed by BACK:  profit = stake*(p_out - p_in)/p_out  (= -back; profit if drifted)
    e.g. back £50 @4.0 close @2.0 -> 50*(4-2)/2 = +£50; commission trims the +£50 by 2%.
    """
    if p_out is None or p_in is None or p_out <= 1.0:
        return 0.0
    gross = stake * (p_in - p_out) / p_out
    if side == "lay":
        gross = -gross
    return gross * (1.0 - commission) if gross > 0 else gross


def _price_band(p: float) -> int:
    for i in range(len(PRICE_BANDS) - 1):
        if PRICE_BANDS[i] <= p < PRICE_BANDS[i + 1]:
            return i
    return len(PRICE_BANDS) - 2


def _tto_bucket(tto_s: float) -> int:
    for i, (lo, hi) in enumerate(TTO_BUCKETS):
        if lo <= tto_s < hi:
            return i
    return len(TTO_BUCKETS) - 1


def _week_parity(d: str) -> Optional[int]:
    try:
        return _date.fromisoformat(d).isocalendar()[1] % 2
    except Exception:
        return None


# --------------------------------------------------------------------------- #
# Entry / exit primitives                                                      #
# --------------------------------------------------------------------------- #
def _take_back(back: Dict[float, float], p_fair: float, cap: float,
               min_ticks: int = STALE_TICKS) -> Tuple[float, Optional[float]]:
    """Fill up to ``cap`` BACKING the too-long stale rungs (>= p_fair + min_ticks ticks),
    best (highest) odds first. Returns (matched £, size-weighted entry price)."""
    thr = ticks_move(p_fair, min_ticks)
    rungs = sorted(((p, s) for p, s in back.items() if p >= thr - 1e-9), key=lambda x: -x[0])
    return _fill(rungs, cap)


def _take_lay(lay: Dict[float, float], p_fair: float, cap: float,
              min_ticks: int = STALE_TICKS) -> Tuple[float, Optional[float]]:
    """Fill up to ``cap`` LAYING the too-short stale rungs (<= p_fair - min_ticks ticks),
    best (lowest) odds first."""
    thr = ticks_move(p_fair, -min_ticks)
    rungs = sorted(((p, s) for p, s in lay.items() if p <= thr + 1e-9), key=lambda x: x[0])
    return _fill(rungs, cap)


def _fill(rungs, cap) -> Tuple[float, Optional[float]]:
    got = 0.0
    cost = 0.0
    for p, s in rungs:
        take = min(s, cap - got)
        if take <= 0:
            break
        got += take
        cost += take * p
    if got <= 0:
        return 0.0, None
    return round(got, 2), cost / got


def _best_back(back: Dict[float, float]) -> Optional[float]:
    return max(back) if back else None


def _best_lay(lay: Dict[float, float]) -> Optional[float]:
    return min(lay) if lay else None


def _one_trade(states, t, p_fair_of: Dict[int, float], survivors, off) -> List[dict]:
    """For one anchored moment (NR event or control), return the taken trades (>=FILL_MIN).

    ``p_fair_of``: sid -> benchmark fair price (P_pre*(1-A) for NR; P_anchor for control).
    First k in 1..OPP_MAX_K with a >=FILL_MIN stale side, filled at t+(k+1), closed at
    the t+300s touch.
    """
    trades = []
    exit_st = states.get(t + POST_MAX_S * 1000)
    exit_books = exit_st["books"] if exit_st else {}
    for sid in survivors:
        pf = p_fair_of.get(sid)
        if pf is None or pf <= 1.0:
            continue
        for k in range(1, OPP_MAX_K + 1):
            fill_st = states.get(t + (k + 1) * 1000)
            if fill_st is None:
                continue
            fb = fill_st["books"].get(sid, ({}, {}))
            m_back, px_back = _take_back(fb[0], pf, STAKE_CAP)
            m_lay, px_lay = _take_lay(fb[1], pf, STAKE_CAP)
            if max(m_back, m_lay) < FILL_MIN:
                continue
            if m_back >= m_lay:
                side, p_in, matched = "back", px_back, m_back
            else:
                side, p_in, matched = "lay", px_lay, m_lay
            eb = exit_books.get(sid, ({}, {}))
            p_out = _best_lay(eb[1]) if side == "back" else _best_back(eb[0])
            if p_out is None:
                break                          # no exit touch -> unclosable, drop
            pnl = trade_pnl(side, p_in, p_out, matched, COMMISSION)
            d = None
            trades.append({
                "side": side, "p_in": round(p_in, 3), "p_out": round(p_out, 3),
                "matched": matched, "pnl_net": round(pnl, 4),
                "pnl_per_pound": round(pnl / matched, 5) if matched else 0.0,
                "entry_band": _price_band(p_in),
                "tto_s": round((off - t) / 1000.0, 1) if off else None,
            })
            break                              # one trade per survivor per moment
    return trades


# --------------------------------------------------------------------------- #
# Per-market extraction: NR trades + control trades                            #
# --------------------------------------------------------------------------- #
def extract_q7_gate2(messages: List[dict], md0: dict) -> Tuple[List[dict], List[dict]]:
    events = find_removal_events(messages, md0)
    if not events:
        return [], []
    off = off_epoch_ms(md0.get("marketTime"))
    date = (md0.get("marketTime") or "")[:10]
    parity = _week_parity(date)
    market_id = md0.get("marketId") or md0.get("id")

    # control moments: same market, >=120s from any removal, in [off-1800s, off-120s]
    ctrl_ts: List[int] = []
    if off is not None:
        rng = random.Random(int(str(market_id).split(".")[-1]) if str(market_id).split(".")[-1].isdigit() else hash(market_id) & 0xffffffff)
        rem_ts = [ev["t"] for ev in events]
        lo, hi = off - 1_800_000, off - 120_000
        tries = 0
        while len(ctrl_ts) < N_CTRL and tries < 40:
            tries += 1
            cand = rng.randint(lo, hi) if hi > lo else None
            if cand is None:
                break
            if all(abs(cand - rt) >= CTRL_GAP_S * 1000 for rt in rem_ts):
                ctrl_ts.append(cand)

    # one replay covering all NR + control windows
    targets: List[int] = []
    for ev in events:
        t = ev["t"]
        targets.append(t - 1000)
        targets.extend(t + k * 1000 for k in range(1, POST_MAX_S + 1))
    for tc in ctrl_ts:
        targets.append(tc - 1000)
        targets.extend(tc + k * 1000 for k in range(1, POST_MAX_S + 1))
    states = _replay_targets(messages, targets)

    def survivors_and_fair(t, A, removed):
        pre = states.get(t - 1000, {}).get("books", {})
        surv = [sid for sid in pre if sid not in removed]
        pfair = {}
        for sid in surv:
            bb = _best_back(pre[sid][0])
            if bb:
                pfair[sid] = bb * (1.0 - A)
        return surv, pfair

    nr_trades, ctrl_trades = [], []
    for ev in events:
        surv, pfair = survivors_and_fair(ev["t"], ev["A"], set(ev["removed"]))
        for tr in _one_trade(states, ev["t"], pfair, surv, off):
            tr.update({"kind": "nr", "date": date, "parity": parity,
                       "market_id": market_id, "A": ev["A"]})
            nr_trades.append(tr)
    for tc in ctrl_ts:
        surv, pfair = survivors_and_fair(tc, 0.0, set())   # A=0: no RF shift
        for tr in _one_trade(states, tc, pfair, surv, off):
            tr.update({"kind": "ctrl", "date": date, "parity": parity,
                       "market_id": market_id, "A": 0.0})
            ctrl_trades.append(tr)
    return nr_trades, ctrl_trades


# --------------------------------------------------------------------------- #
# Verdict: band×tto-matched null on discovery/holdout + odd/even parity        #
# --------------------------------------------------------------------------- #
HOLDOUT_FROM = "2016-01-01"


def _matched_edge(nr: List[dict], ctrl: List[dict]) -> Optional[dict]:
    """Mean NR net P&L per trade minus the band×tto-matched control mean. None if empty."""
    if not nr:
        return None
    cbucket: Dict[Tuple[int, int], List[float]] = defaultdict(list)
    for c in ctrl:
        cbucket[(c["entry_band"], _tto_bucket(c["tto_s"] or 0))].append(c["pnl_per_pound"])
    cmean = {k: sum(v) / len(v) for k, v in cbucket.items()}
    glob = (sum(c["pnl_per_pound"] for c in ctrl) / len(ctrl)) if ctrl else 0.0
    nr_r = sum(t["pnl_per_pound"] for t in nr) / len(nr)
    edges = []
    for t in nr:
        b = cmean.get((t["entry_band"], _tto_bucket(t["tto_s"] or 0)), glob)
        edges.append(t["pnl_per_pound"] - b)
    return {
        "n_nr": len(nr), "n_ctrl": len(ctrl),
        "nr_roi_per_pound": round(nr_r, 5),
        "ctrl_roi_per_pound": round(glob, 5),
        "matched_edge_per_pound": round(sum(edges) / len(edges), 5),
    }


def verdict_gate2(nr_trades: List[dict], ctrl_trades: List[dict]) -> dict:
    def split(rows, pred):
        return [r for r in rows if pred(r)]
    disc = lambda r: r["date"] < HOLDOUT_FROM
    hold = lambda r: r["date"] >= HOLDOUT_FROM
    res = {
        "overall": _matched_edge(nr_trades, ctrl_trades),
        "discovery": _matched_edge(split(nr_trades, disc), split(ctrl_trades, disc)),
        "holdout": _matched_edge(split(nr_trades, hold), split(ctrl_trades, hold)),
        "parity_even": _matched_edge(split(nr_trades, lambda r: r["parity"] == 0),
                                     split(ctrl_trades, lambda r: r["parity"] == 0)),
        "parity_odd": _matched_edge(split(nr_trades, lambda r: r["parity"] == 1),
                                    split(ctrl_trades, lambda r: r["parity"] == 1)),
    }
    legs = [res["holdout"], res["discovery"], res["parity_even"], res["parity_odd"]]
    have = [x for x in legs if x is not None]
    hold_edge = res["holdout"]["matched_edge_per_pound"] if res["holdout"] else None
    all_pos = all(x["matched_edge_per_pound"] > 0 for x in have) and len(have) == 4
    if res["holdout"] is None or res["holdout"]["n_nr"] < 30:
        verdict = "THIN"
        reason = "too few holdout NR trades to judge the edge."
    elif hold_edge is not None and hold_edge > 0 and all_pos:
        verdict = "RULED-IN"
        reason = (f"holdout band×tto-matched edge {hold_edge:+.4f}/£ > 0 AND same-sign on "
                  f"discovery + both week parities — a removal-driven stale-quote edge.")
    else:
        verdict = "PRICED"
        signs = {k: (round(v["matched_edge_per_pound"], 4) if v else None)
                 for k, v in res.items()}
        reason = (f"holdout matched edge {hold_edge}/£ does not clear the ambient null "
                  f"on all splits (edges {signs}) — the stale-quote return is the ambient "
                  f"spread/churn base rate, not a removal edge.")
    res["verdict"] = verdict
    res["verdict_reason"] = reason
    return res


# --------------------------------------------------------------------------- #
# Parallel tar driver                                                          #
# --------------------------------------------------------------------------- #
_G_COURSES = None


def process_tar_g2(tar_path: str):
    courses = _G_COURSES
    nr_all: List[dict] = []
    ctrl_all: List[dict] = []
    c: Counter = Counter()
    with tarfile.open(tar_path) as tar:
        for member in tar:
            base = member.name.rsplit("/", 1)[-1]
            if not (member.name.endswith(".bz2") and base.startswith("1.")):
                continue
            fh = tar.extractfile(member)
            if fh is None:
                continue
            comp = fh.read()
            md = peek_market_definition(io.BytesIO(comp))
            verdict, reason = market_verdict(md, courses) if md else (None, "no_md")
            if verdict != "flat":
                continue
            try:
                raw = bz2.decompress(comp)
                messages = [json.loads(l) for l in raw.decode("utf-8", "replace").splitlines() if l.strip()]
            except Exception:
                c["decompress_error"] += 1
                continue
            md0 = dict(md)
            md0.setdefault("marketId", base[:-4])
            nr, ctrl = extract_q7_gate2(messages, md0)
            nr_all.extend(nr)
            ctrl_all.extend(ctrl)
    c["nr_trades"] += len(nr_all)
    c["ctrl_trades"] += len(ctrl_all)
    return nr_all, ctrl_all, dict(c)


def run_gate2_q7(tar_paths, courses_path, workers: int = 12):
    global _G_COURSES
    _G_COURSES = load_gb_courses(courses_path)
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        results = pool.map(process_tar_g2, tar_paths)
    nr_all, ctrl_all, total = [], [], Counter()
    for nr, ctrl, c in results:
        nr_all.extend(nr)
        ctrl_all.extend(ctrl)
        total.update(c)
    return nr_all, ctrl_all, dict(total)


if __name__ == "__main__":
    import glob
    import os
    import pickle
    import time

    ROOT = "/home/gabriel/projects/racing_project"
    tars = sorted(glob.glob(os.path.join(ROOT, "data/historical/betfair_pro/*.tar")))
    only = os.environ.get("GATE_TARS")
    if only:
        tars = tars[:int(only)]
    workers = int(os.environ.get("GATE_WORKERS", "12"))
    t0 = time.time()
    nr, ctrl, cov = run_gate2_q7(
        tars, os.path.join(ROOT, "data/reference/course_geometry.csv"), workers)
    dt = time.time() - t0
    v = verdict_gate2(nr, ctrl)
    with open(os.path.join(ROOT, "models/gate_q7_gate2_trades.pkl"), "wb") as fh:
        pickle.dump({"nr": nr, "ctrl": ctrl}, fh)
    with open(os.path.join(ROOT, "models/gate_q7_gate2_results.json"), "w") as fh:
        json.dump({"verdict": v, "coverage": cov, "wall_clock_s": round(dt, 1),
                   "n_tars": len(tars)}, fh, indent=2, default=float)
    print("wall clock: %.0fs  (%d tars)" % (dt, len(tars)))
    print("Q7 GATE 2 VERDICT:", json.dumps(v, indent=2, default=float))
