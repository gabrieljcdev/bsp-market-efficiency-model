"""Gate 1 — LIQUIDITY feasibility on the PRO ladder (pre-reg §4 + fill model §6).

Locked pre-registration: `analysis/preregistration_inrunning.md`.

Qualifying opportunity (§4): a GB flat runner with run_style_proxy=='led', entered when
its in-running price FIRST trades <= P_trigger (2.0). Fill model (§6): act at t + L where
L = the market's betDelay (>=1.0s; verified per market, not assumed), cross the spread,
matched £ = size available at/through the entry price within 1-tick slippage. An
opportunity is FILLED iff >= £X (100) is matchable.

PASS (§4): >= £X matchable in > Y% (50) of >= N (2,000) qualifying opportunities.
Liquidity is a market property → measured over the FULL qualifying set, no split.

`measure_market` is pure (takes a run_style callback) so it is unit-tested on synthetic
fixtures independent of the form join. The tar-iterating runner is `run_gate1`.
"""
from __future__ import annotations

import bz2
import io
import json
import tarfile
from collections import Counter
from typing import Callable, Dict, List, Optional

from backtest.pro_stream import (Market, load_gb_courses, market_verdict,
                                 peek_market_definition)
from backtest.pro_form_join import (build_runstyle_index, market_date,
                                    runstyle_lookup)

P_TRIGGER = 2.0
X_STAKE = 100.0
Y_FRACTION = 0.50
N_MIN = 2000
SLIP_TICKS = 1
MIN_LATENCY_MS = 1000


def measure_market(messages, is_led: Callable[[Optional[str], int], bool],
                   threshold: float = P_TRIGGER, stake: float = X_STAKE,
                   slip_ticks: int = SLIP_TICKS) -> List[dict]:
    """One pass over a market's messages → a liquidity record per qualifying opportunity.

    A 'led' runner qualifies the first time it TRADES at <= ``threshold`` in running; the
    book is then re-measured at t + betDelay (>= MIN_LATENCY_MS) and the matchable £ on
    both sides recorded. `is_led(market_id, selection_id) -> bool` supplies the pre-race
    run-style filter (from the form join).
    """
    m = Market()
    inplay_started = False
    baseline: Dict[int, dict] = {}
    signals: Dict[int, tuple] = {}      # sid -> (signal_pt, entry_price)
    pending: Dict[int, int] = {}        # sid -> deadline_pt awaiting the t+L snapshot
    done = set()
    out: List[dict] = []

    def latency_ms() -> int:
        bd = m.bet_delay or 1
        return max(MIN_LATENCY_MS, int(bd * 1000))

    for msg in messages:
        m.apply_mcm(msg)
        pt = m.publish_time
        if pt is None:
            continue
        if m.inplay and not inplay_started:
            inplay_started = True
            baseline = {sid: dict(b.trd) for sid, b in m.books.items()}
        if not inplay_started:
            continue

        # (1) detect new <=threshold in-running trades on led runners
        for sid, b in m.books.items():
            if sid in signals or sid in done:
                continue
            if not is_led(m.market_id, sid):
                continue
            base = baseline.get(sid, {})
            touch = None
            for price, size in b.trd.items():
                if price <= threshold + 1e-9 and size > base.get(price, 0) + 1e-9:
                    touch = price if touch is None else min(touch, price)
            if touch is not None:
                signals[sid] = (pt, touch)
                pending[sid] = pt + latency_ms()

        # (2) fulfil any fill whose t+L deadline has now elapsed
        for sid in list(pending):
            if pt >= pending[sid]:
                sig_pt, entry = signals[sid]
                b = m.books.get(sid)
                mb = b.matchable_back(entry, slip_ticks) if b else 0.0
                ml = b.matchable_lay(entry, slip_ticks) if b else 0.0
                out.append({
                    "market_id": m.market_id, "selection_id": sid,
                    "signal_pt": sig_pt, "entry_price": entry, "bet_delay": m.bet_delay,
                    "matchable_back": mb, "matchable_lay": ml,
                    "filled_back": mb >= stake, "filled_lay": ml >= stake,
                    "truncated": False,
                })
                del pending[sid]
                done.add(sid)

    # opportunities that signalled but the market ended before t+L: conservatively unfilled
    for sid, deadline in pending.items():
        sig_pt, entry = signals[sid]
        out.append({
            "market_id": m.market_id, "selection_id": sid,
            "signal_pt": sig_pt, "entry_price": entry, "bet_delay": m.bet_delay,
            "matchable_back": 0.0, "matchable_lay": 0.0,
            "filled_back": False, "filled_lay": False, "truncated": True,
        })
    return out


def summarise(records: List[dict]) -> dict:
    """Liquidity verdict over the full qualifying set (both entry sides)."""
    n = len(records)
    fb = sum(1 for r in records if r["filled_back"])
    fl = sum(1 for r in records if r["filled_lay"])
    trunc = sum(1 for r in records if r.get("truncated"))
    frac_back = fb / n if n else 0.0
    frac_lay = fl / n if n else 0.0

    def verdict(frac):
        if n < N_MIN:
            return "INSUFFICIENT_N"
        return "PASS" if frac > Y_FRACTION else "FAIL"

    return {
        "n_opportunities": n, "n_min": N_MIN,
        "filled_back": fb, "frac_back": round(frac_back, 4), "verdict_back": verdict(frac_back),
        "filled_lay": fl, "frac_lay": round(frac_lay, 4), "verdict_lay": verdict(frac_lay),
        "truncated": trunc, "X_stake": X_STAKE, "Y_fraction": Y_FRACTION,
    }


# --------------------------------------------------------------------------- #
# Full-dataset driver (parallel over tars; forked workers share the index COW) #
# --------------------------------------------------------------------------- #
_G_INDEX = None
_G_COURSES = None


def process_tar(tar_path: str):
    """Worker: classify each market (partial decompress), measure only GB-flat WIN ones.

    Returns (opportunity_records, coverage_counters). Uses forked-inherited globals
    ``_G_INDEX`` / ``_G_COURSES`` so the 88k-key run-style index is shared copy-on-write,
    not re-pickled per worker.
    """
    idx, courses = _G_INDEX, _G_COURSES
    recs: List[dict] = []
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
            md = peek_market_definition(io.BytesIO(comp))     # cheap classify
            verdict, reason = market_verdict(md, courses) if md else (None, "no_md")
            c["reason_" + reason] += 1
            if verdict != "flat":
                continue
            c["flat_markets"] += 1
            try:
                raw = bz2.decompress(comp)
                messages = [json.loads(l) for l in raw.decode("utf-8", "replace").splitlines() if l.strip()]
            except Exception:
                c["decompress_error"] += 1
                continue
            date = market_date(md.get("marketTime"))
            venue = md.get("venue")
            name_by_sid = {rd["id"]: rd.get("name") for rd in md.get("runners", [])
                           if rd.get("status") == "ACTIVE"}
            for sid, name in name_by_sid.items():
                c["active_runners"] += 1
                style, _n = runstyle_lookup(idx, date, venue, name)
                c["runstyle_covered" if style is not None else "runstyle_uncovered"] += 1
                if style == "led":
                    c["led_runners"] += 1

            def is_led(_mid, sid, _d=date, _v=venue, _n=name_by_sid, _i=idx):
                return runstyle_lookup(_i, _d, _v, _n.get(sid))[0] == "led"

            recs.extend(measure_market(messages, is_led))
    return recs, dict(c)


def run_gate1(tar_paths, form_csvs, courses_path, workers: int = 8):
    """Build the run-style index, then measure liquidity across all tars in parallel."""
    global _G_INDEX, _G_COURSES
    _G_INDEX = build_runstyle_index(form_csvs)
    _G_COURSES = load_gb_courses(courses_path)
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:                 # workers fork -> inherit globals
        results = pool.map(process_tar, tar_paths)
    all_recs: List[dict] = []
    total: Counter = Counter()
    for recs, c in results:
        all_recs.extend(recs)
        total.update(c)
    return all_recs, dict(total)


if __name__ == "__main__":
    import glob
    import os
    import time

    ROOT = "/home/gabriel/projects/racing_project"
    tars = sorted(glob.glob(os.path.join(ROOT, "data/historical/betfair_pro/*.tar")))
    forms = [p for p in [
        os.path.join(ROOT, "vendor/rpscrape/data/region/gb/all/2014_05_01_2015_04_30.csv"),
        os.path.join(ROOT, "vendor/rpscrape/data/region/gb/all/2015_05_01_2016_04_30.csv"),
    ] if os.path.exists(p)]
    workers = int(os.environ.get("GATE1_WORKERS", "8"))
    print("tars=%d forms=%s workers=%d" % (len(tars), [os.path.basename(f) for f in forms], workers))
    t0 = time.time()
    recs, cov = run_gate1(tars, forms, os.path.join(ROOT, "data/reference/course_geometry.csv"), workers)
    dt = time.time() - t0
    s = summarise(recs)
    out = {"summary": s, "coverage": cov, "wall_clock_s": round(dt, 1),
           "forms": [os.path.basename(f) for f in forms]}
    dest = os.path.join(ROOT, "models/gate1_liquidity_results.json")
    with open(dest, "w") as fh:
        json.dump({**out, "records_head": recs[:50]}, fh, indent=2)
    print("wall clock: %.0fs" % dt)
    print("coverage:", json.dumps(cov, indent=2))
    print("SUMMARY:", json.dumps(s, indent=2))
    print("wrote", dest)
