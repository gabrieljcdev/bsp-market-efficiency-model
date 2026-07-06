"""Pre-off gates for Q2/Q3/Q6 (pre-registration §12 Amendment 1).

Gate 1 (liquidity / fill feasibility) in ONE pre-off parse pass per market:
  * Q2  — is £100 matchable within 1 tick at the T-10min entry? (book-depth gate)
  * Q3  — entry = 3rd-best-back at T-10min; is £100 matchable within 1 tick there?
  * Q6  — passive quote joining the touch queue at T-30min (both sides, £100/side);
          FILLED iff traded volume at that price T-30min→T-10min > prior_queue + £100.
          Gate = fill RATE (< 10% of posted quotes ever fill ⇒ Q6 fails).

Reconstruction, tick ladder and matchable-£ come from pro_stream (already bflw-validated
and unit-tested). Records are one row per qualifying GB-flat WIN runner and also carry the
Gate-2 raw material (entry/exit/off prices, T-10min ladder, slice tags) so the edge gate
needs no second parse. Gate-2 verdict logic is applied later, on survivors only.
"""
from __future__ import annotations

import bz2
import io
import json
import re
import tarfile
from collections import Counter
from datetime import datetime, timezone
from typing import List, Optional

from backtest.pro_stream import (Market, RunnerBook, load_gb_courses,
                                 market_verdict, peek_market_definition, ticks_move)

STAKE = 100.0
SLIP_TICKS = 1


def off_epoch_ms(market_time: Optional[str]) -> Optional[int]:
    """Betfair marketTime ('2015-06-01T13:00:00.000Z') → epoch ms (the off)."""
    if not market_time:
        return None
    try:
        dt = datetime.strptime(market_time, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=timezone.utc)
    except ValueError:
        try:
            dt = datetime.strptime(market_time, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return int(dt.timestamp() * 1000)


def dist_furlongs(name: Optional[str]) -> Optional[float]:
    """Furlongs from a Betfair race name ('5f Mdn Stks'→5, '1m2f Hcap'→10, '1m'→8)."""
    if not name:
        return None
    m = re.match(r"\s*(?:(\d+)m)?(?:(\d+)f)?", name)
    if not m or (m.group(1) is None and m.group(2) is None):
        return None
    miles = int(m.group(1)) if m.group(1) else 0
    fur = int(m.group(2)) if m.group(2) else 0
    return miles * 8 + fur


def _book(tup) -> RunnerBook:
    b = RunnerBook()
    b.back, b.lay, b.trd = dict(tup[0]), dict(tup[1]), dict(tup[2])
    return b


def extract_preoff_gate1(messages, md, stake: float = STAKE, slip: int = SLIP_TICKS) -> List[dict]:
    off = off_epoch_ms(md.get("marketTime"))
    if off is None:
        return []
    t30m, t10m, t30s = off - 1_800_000, off - 600_000, off - 30_000
    TOL_MS = 120_000                             # a target is "met" only if a message
    m = Market()                                 # lands within 2 min after it (else a gap)
    snap = {}
    done = set()
    for msg in messages:
        m.apply_mcm(msg)
        if m.inplay:
            break
        pt = m.publish_time
        if pt is None:
            continue
        for label, tt in (("T30m", t30m), ("T10m", t10m), ("T30s", t30s)):
            if label in done or pt < tt:
                continue
            done.add(label)
            if pt <= tt + TOL_MS:                # fresh enough to represent the target
                snap[label] = {sid: (dict(b.back), dict(b.lay), dict(b.trd))
                               for sid, b in m.books.items()}
    if "T10m" not in snap:                       # no book near T-10min (late open / gap)
        return []

    name = md.get("name") or ""
    field = md.get("numberOfActiveRunners")
    is_hcap = "hcap" in name.lower() or "handicap" in name.lower()
    dist = dist_furlongs(name)
    recs = []
    for rd in md.get("runners", []):
        if rd.get("status") != "ACTIVE":
            continue
        sid = rd["id"]
        b10 = _book(snap["T10m"].get(sid, ({}, {}, {})))
        bb = b10.best_back(3)
        bl = b10.best_lay(1)
        best_back = bb[0][0] if bb else None
        best_lay = bl[0][0] if bl else None
        third_back = bb[2][0] if len(bb) >= 3 else None

        # Q2 Gate 1: £100 matchable within 1 tick at the T-10min touch (entry side = back)
        q2_fill = best_back is not None and b10.matchable_back(best_back, slip) >= stake

        # Q3 Gate 1: entry quote at 3rd-best-back rung; £100 matchable within 1 tick there
        q3_fill = third_back is not None and b10.matchable_back(third_back, slip) >= stake

        # Q6 Gate 1: passive quote joins the touch queue at T-30min (both sides)
        q6_back_fill = q6_lay_fill = False
        q6_posted = False
        if "T30m" in snap:
            b30 = _book(snap["T30m"].get(sid, ({}, {}, {})))
            bb30 = b30.best_back(1)
            bl30 = b30.best_lay(1)
            if bb30 and bl30:                     # need a two-sided book to post
                q6_posted = True
                pb, pl = bb30[0][0], bl30[0][0]
                qback = bb30[0][1]                # queue ahead of us at best-back
                qlay = bl30[0][1]
                traded_pb = b10.trd.get(pb, 0) - b30.trd.get(pb, 0)   # traded AT pb, 30m→10m
                traded_pl = b10.trd.get(pl, 0) - b30.trd.get(pl, 0)
                q6_back_fill = traded_pb > qback + stake
                q6_lay_fill = traded_pl > qlay + stake

        recs.append({
            "market_id": m.market_id, "selection_id": sid,
            "date": (md.get("marketTime") or "")[:10], "venue": md.get("venue"),
            "field": field, "dist_f": dist, "is_hcap": is_hcap,
            "best_back_t10": best_back, "best_lay_t10": best_lay, "third_back_t10": third_back,
            "q2_fill": q2_fill, "q3_fill": q3_fill,
            "q6_posted": q6_posted, "q6_back_fill": q6_back_fill, "q6_lay_fill": q6_lay_fill,
        })
    return recs


def summarise_gate1(records: List[dict]) -> dict:
    n = len(records)
    q2 = sum(1 for r in records if r["q2_fill"])
    q3 = sum(1 for r in records if r["q3_fill"])
    posted = sum(1 for r in records if r["q6_posted"])
    q6f = sum(1 for r in records if r["q6_back_fill"] or r["q6_lay_fill"])

    def frac(a, b):
        return round(a / b, 4) if b else 0.0

    q2_frac, q3_frac = frac(q2, n), frac(q3, n)
    q6_rate = frac(q6f, posted)
    return {
        "n_runner_moments": n,
        "Q2_liquidity": {"fill": q2, "frac": q2_frac, "bar": 0.50,
                         "verdict": "PASS" if q2_frac > 0.50 else "FAIL"},
        "Q3_liquidity": {"fill": q3, "frac": q3_frac, "bar": 0.50,
                         "verdict": "PASS" if q3_frac > 0.50 else "FAIL"},
        "Q6_fill_rate": {"posted": posted, "filled": q6f, "rate": q6_rate, "bar": 0.10,
                         "verdict": "PASS" if q6_rate >= 0.10 else "FAIL"},
    }


# --------------------------------------------------------------------------- #
# Parallel tar driver (GB-flat markets only; no run-style / form join needed)  #
# --------------------------------------------------------------------------- #
_G_COURSES = None


def process_tar_preoff(tar_path: str):
    courses = _G_COURSES
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
            md = peek_market_definition(io.BytesIO(comp))
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
            r = extract_preoff_gate1(messages, md)
            if not r:
                c["no_t10min_markets"] += 1
            recs.extend(r)
    return recs, dict(c)


def run_gate1_preoff(tar_paths, courses_path, workers: int = 12):
    global _G_COURSES
    _G_COURSES = load_gb_courses(courses_path)
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
        results = pool.map(process_tar_preoff, tar_paths)
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
    only = os.environ.get("GATE_TARS")
    if only:
        tars = tars[:int(only)]
    workers = int(os.environ.get("GATE1_WORKERS", "12"))
    t0 = time.time()
    recs, cov = run_gate1_preoff(tars, os.path.join(ROOT, "data/reference/course_geometry.csv"), workers)
    dt = time.time() - t0
    s = summarise_gate1(recs)
    out = {"summary": s, "coverage": cov, "wall_clock_s": round(dt, 1), "n_tars": len(tars)}
    dest = os.path.join(ROOT, "models/gate_preoff_gate1_results.json")
    # keep records for Gate-2 reuse (survivors)
    import pickle
    with open(os.path.join(ROOT, "models/gate_preoff_gate1_records.pkl"), "wb") as fh:
        pickle.dump(recs, fh)
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2)
    print("wall clock: %.0fs  (%d tars)" % (dt, len(tars)))
    print("coverage:", json.dumps(cov, indent=2))
    print("GATE 1 (pre-off) SUMMARY:", json.dumps(s, indent=2))
    print("wrote", dest)
