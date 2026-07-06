"""Q7 — Non-runner repricing latency (pre-registration §12 Amendment 2).

Detects pre-off NON-RUNNER removals (status ACTIVE->REMOVED, adjustmentFactor >= 2.5%)
in GB-flat WIN markets and measures whether the stale-quote pickoff the mechanism
predicts actually survives Betfair's suspend-and-cancel-unmatched behaviour.

Frozen definition (Amendment 2, locked before first Q7 data contact):
  * Event    : ACTIVE->REMOVED, GB-flat WIN, pre-off, adjustmentFactor >= 2.5%.
  * t        : publishTime of the message carrying the REMOVED transition.
  * Pre      : book snapshot at t-1s.  Post: 1s snapshots t+1s .. t+300s.
  * Benchmark: P_fair,i = P_pre,i * (1 - A),  A = sum(adjustmentFactor/100) removed.
               (probability-renormalisation; Betfair matched-bet 1+(P-1)(1-A) reported
               as a cross-check.)  Win-market RF applies to the price.
  * Opportunity: available size at t+k (k=1..30s) at a price STALE vs the benchmark by
               >= 2 Betfair ticks, either side; entry @1s latency, £50/runner cap; exit
               at touch t+300s; net 2% commission.

GATE 1 (this module, Part B): count events + rate/raceday; fillability bar = a >=£50
stale-quote opportunity in >= 10% of NR events, else FAIL (mechanically deleted). Plus
the mandatory diagnostics: suspend fraction, suspension-duration dist, book-wipe
fraction (depth t+1s vs t-1s), time-to-repopulation (depth back to 80% of pre level).

Reconstruction, tick ladder and matchable-£ come from pro_stream (bflw-validated,
unit-tested). Gate 2 (edge, survivors only) is a separate pass, run only on a PASS.
"""
from __future__ import annotations

import bz2
import io
import json
import tarfile
from collections import Counter
from typing import Dict, List, Optional, Tuple

from backtest.pro_stream import (Market, RunnerBook, load_gb_courses,
                                 market_verdict, peek_market_definition, ticks_move)
from backtest.gate_preoff import off_epoch_ms, dist_furlongs

STAKE_CAP = 50.0          # £ cap per runner (frozen)
MIN_AF = 2.5              # adjustmentFactor >= 2.5% (sub-2.5% RFs not applied by Betfair)
STALE_TICKS = 2           # "stale vs benchmark by >= 2 Betfair ticks"
POST_MAX_S = 300          # post window t+1s .. t+300s
OPP_MAX_K = 30            # opportunity window k = 1..30s
FILL_BAR = 50.0           # >= £50 available -> a fillable opportunity
REPOP_FRAC = 0.80         # depth back to 80% of pre level = repopulated


# --------------------------------------------------------------------------- #
# Pure metric helpers (unit-tested directly)                                   #
# --------------------------------------------------------------------------- #
def fair_price(p_pre: float, A: float) -> float:
    """Probability-renormalisation fair price: P_pre * (1 - A). WIN-market RF on price."""
    return p_pre * (1.0 - A)


def fair_price_matched(p_pre: float, A: float) -> float:
    """Betfair mechanical matched-bet reduction 1 + (P-1)(1-A) (reported cross-check)."""
    return 1.0 + (p_pre - 1.0) * (1.0 - A)


def stale_back_size(back: Dict[float, float], p_fair: float, min_ticks: int = STALE_TICKS) -> float:
    """£ available to BACK a survivor at odds >= min_ticks ticks LONGER than fair.

    A too-long back price is the pickoff: the removed runner made survivors more likely,
    so fair odds shorten; size still resting to back at >= P_fair + 2 ticks is stale value.
    (available-to-back = the runner's ``back`` ladder in pro_stream.)
    """
    threshold = ticks_move(p_fair, min_ticks)
    return round(sum(s for p, s in back.items() if p >= threshold - 1e-9), 2)


def stale_lay_size(lay: Dict[float, float], p_fair: float, min_ticks: int = STALE_TICKS) -> float:
    """£ available to LAY a survivor at odds <= min_ticks ticks SHORTER than fair."""
    threshold = ticks_move(p_fair, -min_ticks)
    return round(sum(s for p, s in lay.items() if p <= threshold + 1e-9), 2)


def _depth(back: Dict[float, float], lay: Dict[float, float]) -> float:
    return round(sum(back.values()) + sum(lay.values()), 2)


# --------------------------------------------------------------------------- #
# Pass A: find qualifying removal events (reads marketDefinition only, cheap)   #
# --------------------------------------------------------------------------- #
def find_removal_events(messages: List[dict], md0: dict) -> List[dict]:
    """Scan the message list for ACTIVE->REMOVED transitions, grouped by publishTime.

    Returns one event dict per (t) at which >=1 runner with AF>=2.5% is removed pre-off:
      {t, off, removed:{sid:af}, A, inplay_at_t, active_sids:set}
    """
    off = off_epoch_ms(md0.get("marketTime"))
    status: Dict[int, str] = {}
    af_seen: Dict[int, float] = {}
    prev_inplay = False
    by_t: Dict[int, dict] = {}
    for msg in messages:
        pt = msg.get("pt")
        for mc in msg.get("mc", []):
            md = mc.get("marketDefinition")
            if not md:
                continue
            inplay = md.get("inPlay", prev_inplay)
            for rd in md.get("runners", []):
                sid = rd.get("id")
                st = rd.get("status")
                af = rd.get("adjustmentFactor")
                if af is not None:
                    af_seen[sid] = af
                prev = status.get(sid)
                if st == "REMOVED" and prev is not None and prev != "REMOVED":
                    # first observation of this runner's removal
                    afx = af if af is not None else af_seen.get(sid)
                    if afx is not None and afx >= MIN_AF and not inplay and pt is not None:
                        ev = by_t.setdefault(pt, {"t": pt, "off": off, "removed": {},
                                                  "inplay_at_t": inplay})
                        ev["removed"][sid] = afx
                if st is not None:
                    status[sid] = st
            prev_inplay = inplay
    events = []
    # active runner set at market definition (for survivor identification)
    for pt in sorted(by_t):
        ev = by_t[pt]
        ev["A"] = round(sum(v for v in ev["removed"].values()) / 100.0, 6)
        events.append(ev)
    return events


# --------------------------------------------------------------------------- #
# Pass B: snapshot the book at t-1s and t+1..300s for each event; compute      #
# --------------------------------------------------------------------------- #
def _snapshot_state(m: Market) -> dict:
    """Compact deep-copied book state for all runners + market status."""
    return {
        "status": m.status,
        "inplay": m.inplay,
        "books": {sid: (dict(b.back), dict(b.lay)) for sid, b in m.books.items()},
    }


def _replay_targets(messages: List[dict], targets: List[int]) -> Dict[int, dict]:
    """State of the market AS OF each target time = after all messages with pt <= target."""
    tsorted = sorted(set(targets))
    out: Dict[int, dict] = {}
    ti = 0
    m = Market()
    for msg in messages:
        pt = msg.get("pt")
        if pt is not None:
            while ti < len(tsorted) and tsorted[ti] < pt:
                out[tsorted[ti]] = _snapshot_state(m)
                ti += 1
        m.apply_mcm(msg)
    while ti < len(tsorted):                     # targets past the last message
        out[tsorted[ti]] = _snapshot_state(m)
        ti += 1
    return out


def extract_q7(messages: List[dict], md0: dict) -> List[dict]:
    """One record per qualifying pre-off NR removal event with Gate-1 metrics."""
    events = find_removal_events(messages, md0)
    if not events:
        return []
    # gather all snapshot target times
    targets: List[int] = []
    for ev in events:
        t = ev["t"]
        targets.append(t - 1000)
        targets.extend(t + k * 1000 for k in range(1, POST_MAX_S + 1))
    states = _replay_targets(messages, targets)

    name = md0.get("name") or ""
    field = md0.get("numberOfActiveRunners")
    is_hcap = "hcap" in name.lower() or "handicap" in name.lower()
    dist = dist_furlongs(name)
    market_id = md0.get("marketId") or md0.get("id")
    recs = []
    for ev in events:
        t, A, off = ev["t"], ev["A"], ev["off"]
        removed = set(ev["removed"])
        pre = states.get(t - 1000, {})
        pre_books = pre.get("books", {})
        survivors = [sid for sid in pre_books if sid not in removed]

        # per-survivor pre price + fair benchmark (best-back at t-1s)
        pfair: Dict[int, float] = {}
        pfair_matched: Dict[int, float] = {}
        p_pre: Dict[int, float] = {}
        for sid in survivors:
            back = pre_books[sid][0]
            if not back:
                continue
            bb = max(back)                        # best back = highest price offered
            p_pre[sid] = bb
            pfair[sid] = fair_price(bb, A)
            pfair_matched[sid] = fair_price_matched(bb, A)

        pre_depth = sum(_depth(pre_books[sid][0], pre_books[sid][1]) for sid in survivors)

        # diagnostics + fillability over the post window
        suspended = False
        susp_start: Optional[int] = None
        susp_end: Optional[int] = None
        depth_t1: Optional[float] = None
        repop_k: Optional[int] = None
        # fillability scan k=1..30 at post-latency book t+(k+1)s
        best_opp = 0.0
        best_opp_side = None
        best_opp_k = None
        best_opp_matched = 0.0        # same, but staleness measured vs the matched-bet benchmark

        for k in range(1, POST_MAX_S + 1):
            st = states.get(t + k * 1000)
            if st is None:
                continue
            books = st["books"]
            status = st["status"]
            if status == "SUSPENDED":
                suspended = True
                if susp_start is None:
                    susp_start = k
                susp_end = None
            elif status == "OPEN" and susp_start is not None and susp_end is None:
                susp_end = k
            d = sum(_depth(books.get(sid, ({}, {}))[0], books.get(sid, ({}, {}))[1])
                    for sid in survivors)
            if k == 1:
                depth_t1 = d
            if repop_k is None and pre_depth > 0 and d >= REPOP_FRAC * pre_depth:
                repop_k = k

            # opportunity window: detect at t+k (k<=30), FILL at post-latency book t+(k+1)
            if k <= OPP_MAX_K:
                fill_st = states.get(t + (k + 1) * 1000)
                fbooks = fill_st["books"] if fill_st else books
                for sid in survivors:
                    if sid not in pfair:
                        continue
                    fb = fbooks.get(sid, ({}, {}))
                    back_stale = stale_back_size(fb[0], pfair[sid])
                    lay_stale = stale_lay_size(fb[1], pfair[sid])
                    sz = min(STAKE_CAP, max(back_stale, lay_stale))
                    if max(back_stale, lay_stale) > best_opp:
                        best_opp = round(max(back_stale, lay_stale), 2)
                        best_opp_side = "back" if back_stale >= lay_stale else "lay"
                        best_opp_k = k
                    # matched-bet-benchmark sensitivity
                    bm = min(STAKE_CAP, max(stale_back_size(fb[0], pfair_matched[sid]),
                                            stale_lay_size(fb[1], pfair_matched[sid])))
                    best_opp_matched = max(best_opp_matched, bm)

        susp_dur = None
        if susp_start is not None:
            end = susp_end if susp_end is not None else POST_MAX_S + 1   # censored
            susp_dur = end - susp_start
        wipe_ratio = (depth_t1 / pre_depth) if (pre_depth and depth_t1 is not None) else None

        recs.append({
            "market_id": market_id, "t": t, "off": off,
            "time_to_off_s": round((off - t) / 1000.0, 1) if off else None,
            "date": (md0.get("marketTime") or "")[:10], "venue": md0.get("venue"),
            "field": field, "dist_f": dist, "is_hcap": is_hcap,
            "n_removed": len(removed), "A": A, "af_pct": round(A * 100, 3),
            "n_survivors_priced": len(pfair),
            "pre_depth_gbp": round(pre_depth, 2),
            "depth_t1_gbp": round(depth_t1, 2) if depth_t1 is not None else None,
            "wipe_ratio": round(wipe_ratio, 4) if wipe_ratio is not None else None,
            "suspended": suspended,
            "susp_start_s": susp_start, "susp_dur_s": susp_dur,
            "susp_censored": bool(susp_start is not None and susp_end is None),
            "repop_k_s": repop_k,
            "best_opp_gbp": best_opp, "best_opp_side": best_opp_side, "best_opp_k": best_opp_k,
            "best_opp_matched_gbp": round(best_opp_matched, 2),
            "fillable": best_opp >= FILL_BAR,
            "fillable_matched": best_opp_matched >= FILL_BAR,
        })
    return recs


# --------------------------------------------------------------------------- #
# Summary (Gate 1)                                                             #
# --------------------------------------------------------------------------- #
def _pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    i = min(len(s) - 1, max(0, int(round(q * (len(s) - 1)))))
    return s[i]


def summarise_q7_gate1(records: List[dict], n_racedays: Optional[int] = None) -> dict:
    n = len(records)
    if n == 0:
        return {"n_events": 0, "verdict": "NO_EVENTS"}
    dates = {r["date"] for r in records if r.get("date")}
    susp = [r for r in records if r["suspended"]]
    wipes = [r["wipe_ratio"] for r in records if r["wipe_ratio"] is not None]
    durs = [r["susp_dur_s"] for r in records if r["susp_dur_s"] is not None]
    repops = [r["repop_k_s"] for r in records if r["repop_k_s"] is not None]
    fillable = sum(1 for r in records if r["fillable"])
    fillable_m = sum(1 for r in records if r["fillable_matched"])
    wiped = sum(1 for r in records if r["wipe_ratio"] is not None and r["wipe_ratio"] <= 0.10)
    frac = lambda a, b: round(a / b, 4) if b else 0.0
    rd = n_racedays or len(dates)
    fill_frac = frac(fillable, n)
    return {
        "n_events": n,
        "n_racedays_with_events": len(dates),
        "events_per_raceday": round(n / rd, 3) if rd else None,
        "af_pct": {"min": min(r["af_pct"] for r in records),
                   "median": _pct([r["af_pct"] for r in records], 0.5),
                   "max": max(r["af_pct"] for r in records)},
        "suspend_fraction": frac(len(susp), n),
        "suspension_duration_s": {"n": len(durs), "median": _pct(durs, 0.5),
                                  "p90": _pct(durs, 0.9), "max": max(durs) if durs else None,
                                  "n_censored": sum(1 for r in records if r["susp_censored"])},
        "book_wipe": {"wiped_frac_le10pct": frac(wiped, n),
                      "wipe_ratio_median": _pct(wipes, 0.5),
                      "wipe_ratio_p10": _pct(wipes, 0.10)},
        "repopulation_to_80pct_s": {"n_repopulated": len(repops),
                                    "frac_repopulated": frac(len(repops), n),
                                    "median": _pct(repops, 0.5), "p90": _pct(repops, 0.9)},
        "fillability": {
            "fillable_events": fillable, "fill_fraction": fill_frac, "bar": 0.10,
            "verdict": "PASS" if fill_frac >= 0.10 else "FAIL",
            "fillable_matched_benchmark": fillable_m,
            "fill_fraction_matched": frac(fillable_m, n),
            "best_opp_gbp_median": _pct([r["best_opp_gbp"] for r in records], 0.5),
            "best_opp_gbp_p90": _pct([r["best_opp_gbp"] for r in records], 0.90),
        },
        "verdict": "PASS" if fill_frac >= 0.10 else "FAIL",
    }


# --------------------------------------------------------------------------- #
# Parallel tar driver (mirror of gate_preoff)                                  #
# --------------------------------------------------------------------------- #
_G_COURSES = None


def process_tar_q7(tar_path: str):
    courses = _G_COURSES
    recs: List[dict] = []
    c: Counter = Counter()
    racedays: set = set()
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
            c["reason_" + reason] += 1
            if verdict != "flat":
                continue
            c["flat_markets"] += 1
            if md.get("marketTime"):
                racedays.add(md["marketTime"][:10])
            try:
                raw = bz2.decompress(comp)
                messages = [json.loads(l) for l in raw.decode("utf-8", "replace").splitlines() if l.strip()]
            except Exception:
                c["decompress_error"] += 1
                continue
            md0 = dict(md)
            md0.setdefault("marketId", base[:-4])
            r = extract_q7(messages, md0)
            if r:
                c["markets_with_events"] += 1
                c["events"] += len(r)
            recs.extend(r)
    return recs, dict(c), sorted(racedays)


def run_gate1_q7(tar_paths, courses_path, workers: int = 12):
    global _G_COURSES
    _G_COURSES = load_gb_courses(courses_path)
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        results = pool.map(process_tar_q7, tar_paths)
    all_recs: List[dict] = []
    total: Counter = Counter()
    racedays: set = set()
    for recs, c, rd in results:
        all_recs.extend(recs)
        total.update(c)
        racedays.update(rd)
    return all_recs, dict(total), racedays


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
    recs, cov, racedays = run_gate1_q7(
        tars, os.path.join(ROOT, "data/reference/course_geometry.csv"), workers)
    dt = time.time() - t0
    s = summarise_q7_gate1(recs, n_racedays=len(racedays))
    with open(os.path.join(ROOT, "models/gate_q7_gate1_records.pkl"), "wb") as fh:
        pickle.dump(recs, fh)
    with open(os.path.join(ROOT, "models/gate_q7_gate1_results.json"), "w") as fh:
        json.dump({"summary": s, "coverage": cov, "wall_clock_s": round(dt, 1),
                   "n_tars": len(tars), "n_racedays_total": len(racedays)}, fh, indent=2)
    print("wall clock: %.0fs  (%d tars, %d racedays)" % (dt, len(tars), len(racedays)))
    print("Q7 GATE 1 SUMMARY:", json.dumps(s, indent=2))
