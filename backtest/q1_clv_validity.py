"""Q1 — Does CLV transfer to in-play?  Metric-validity harness.

Pre-registration: ``prompts/Q1_INP.MD`` (committed 694ae7b, registered 2026-07-09).

Question (sport-agnostic arithmetic): does ``struck / pseudo_close - 1`` — a CLV
metric built against a *pseudo-close* reconstructed from in-running prices — rank
five pre-specified in-play rules the same way absolute realised ROI does? If not,
``backtest/clv.py`` ports to football as plumbing only.

Data: real Betfair PRO historical stream tars in ``data/historical/betfair_pro/``
(GB flat WIN, ~2015-16), reconstructed to a 1-second in-running order book +
last-traded-price series by ``backtest.pro_stream``. No data is bought here; no
holdout is touched (this era is entirely pre-2018, i.e. discovery only).

Guardrails honoured (pre-reg §1):
  * commission HARDCODED 0.02 here — ``DEFAULT_COMMISSION`` (0.05) is never read;
  * no live endpoint, no purchase;
  * INCONCLUSIVE is a respected verdict;
  * every G2 differential is reported next to its G1 absolute;
  * joins assert non-zero match counts (a silent zero-match yields a beautiful,
    meaningless Kendall tau — pre-reg §6).

``measure_market`` is pure (messages + is_led callback + seed) so it is unit-tested
on synthetic fixtures with no tar and no form join. ``run_q1`` is the tar driver.
"""
from __future__ import annotations

import bz2
import io
import json
import random
import tarfile
from collections import Counter, defaultdict
from typing import Callable, Dict, List, Optional, Tuple

from backtest.pro_stream import (Market, load_gb_courses, market_verdict,
                                 peek_market_definition, ticks_move)

# --------------------------------------------------------------------------- #
# Pre-registered constants (fixed BEFORE any result was seen)                  #
# --------------------------------------------------------------------------- #
COMMISSION = 0.02          # pre-reg §1 — hardcoded; DEFAULT_COMMISSION deliberately NOT read
STAKE_UNIT = 1.0           # ROI reported per unit backer-stake
SLIP_TICKS = 1             # 1-tick slippage cap (pre-reg §3)
MIN_LATENCY_MS = 1000      # 1.0 s latency floor; else market betDelay*1000 if larger
MIN_MATCH = 1.0            # £ matchable within slip for a modelled fill to count (unit stake)
P2_OFFSET_MS = 30_000      # P2 pseudo-close: in-running LTP at entry + 30 s
RNG_SEED = 20260709        # R5 random control seed (reproducible)

R1_BACK_TRIGGER = 2.0
R2_LAY_TRIGGER = 1.5
R3_DRIFT_MULT = 2.0        # back if in-running price first trades >= 2x its BSP

# 14 price bands, favourite-fine — identical to run_strategy._PRICE_BAND_EDGES.
_PRICE_BAND_EDGES = (1.0, 1.5, 2.0, 2.5, 3.0, 4.0, 5.0, 6.0, 8.0,
                     10.0, 15.0, 20.0, 30.0, 50.0, float("inf"))
_N_BANDS = len(_PRICE_BAND_EDGES) - 1
MIN_BAND_N = 50            # thin band -> global (same-side) fallback


def price_band(price: float) -> Optional[int]:
    if price is None or price <= 1.0:
        return None
    for i in range(_N_BANDS):
        if _PRICE_BAND_EDGES[i] <= price < _PRICE_BAND_EDGES[i + 1]:
            return i
    return _N_BANDS - 1


# --------------------------------------------------------------------------- #
# P&L (inlined so the 0.05 DEFAULT_COMMISSION constant is never imported)      #
# --------------------------------------------------------------------------- #
def back_pnl(struck: float, won: bool, comm: float = COMMISSION) -> float:
    """1-unit BACK: win -> (struck-1)*(1-comm); lose -> -1."""
    return (struck - 1.0) * (1.0 - comm) if won else -1.0


def lay_pnl(struck: float, won: bool, comm: float = COMMISSION) -> float:
    """1-unit-backer-stake LAY: horse loses -> +(1-comm); horse wins -> -(struck-1)."""
    return -(struck - 1.0) if won else (1.0 - comm)


def side_clv(side: str, struck: float, close: float) -> Optional[float]:
    """Side-aware CLV. back: struck/close-1; lay: close/struck-1 (project convention,
    HANDOVER glossary Lay-CLV=BSP/struck-1). Locked before results were seen: applying
    the back-only formula to a lay manufactures a sign flip unrelated to proxy
    robustness, which is the pathology under test."""
    if struck is None or close is None or struck <= 0 or close <= 0:
        return None
    return (struck / close - 1.0) if side == "back" else (close / struck - 1.0)


# --------------------------------------------------------------------------- #
# Settlement extraction                                                        #
# --------------------------------------------------------------------------- #
def _final_definition(messages: List[dict]) -> dict:
    md = {}
    for msg in messages:
        for mc in msg.get("mc", []):
            d = mc.get("marketDefinition")
            if d:
                md = d
    return md


def settlement(messages: List[dict]) -> Tuple[set, set, Dict[int, float], Optional[int]]:
    """(winner_sids, removed_sids, bsp_by_sid, bet_delay) from the final marketDefinition."""
    fd = _final_definition(messages)
    winners, removed, bsp = set(), set(), {}
    for r in fd.get("runners", []):
        sid = r.get("id")
        st = r.get("status")
        if st == "WINNER":
            winners.add(sid)
        if st == "REMOVED":
            removed.add(sid)
        b = r.get("bsp")
        if b not in (None, 0):
            bsp[sid] = float(b)
    return winners, removed, bsp, fd.get("betDelay")


# --------------------------------------------------------------------------- #
# Pass 1 — per-runner in-running LTP series + entry detection                  #
# --------------------------------------------------------------------------- #
def _ltp_series(messages: List[dict]) -> Tuple[Dict[int, List[Tuple[int, float]]], Optional[int]]:
    """Per-runner [(pt, ltp)] while the market is IN RUNNING, and the inplay-start pt.

    Reconstruction of inPlay/pt uses ``Market``; ltp is read straight from the raw
    ``rc`` deltas (RunnerBook does not retain it). A new point is appended only when
    ltp changes, so the series is a step function keyed by publish-time.
    """
    m = Market()
    series: Dict[int, List[Tuple[int, float]]] = defaultdict(list)
    inplay_start = None
    for msg in messages:
        m.apply_mcm(msg)
        pt = m.publish_time
        if pt is None:
            continue
        if m.inplay and inplay_start is None:
            inplay_start = pt
        if not m.inplay:
            continue
        for mc in msg.get("mc", []):
            for rc in mc.get("rc", []):
                if "ltp" in rc:
                    sid = rc.get("id")
                    ltp = rc["ltp"]
                    s = series[sid]
                    if not s or s[-1][1] != ltp:
                        s.append((pt, ltp))
    return series, inplay_start


def _ltp_at(series: List[Tuple[int, float]], t: int) -> Optional[float]:
    """Step-function lookup: last ltp at or before time ``t`` (None if t precedes series)."""
    val = None
    for pt, ltp in series:
        if pt <= t:
            val = ltp
        else:
            break
    return val


def _detect_entries(series, is_led, bsp_by_sid, removed, rng):
    """List of (rule, side, sid, signal_pt, entry_price) from the in-running LTP series."""
    entries = []
    r5_pool = []
    for sid, s in series.items():
        if sid in removed or not s:
            continue
        led = bool(is_led(sid))
        bsp = bsp_by_sid.get(sid)
        first_le2 = next(((pt, l) for pt, l in s if l <= R1_BACK_TRIGGER + 1e-9), None)
        first_le15 = next(((pt, l) for pt, l in s if l <= R2_LAY_TRIGGER + 1e-9), None)
        first_drift = None
        if bsp and bsp > 1.0:
            first_drift = next(((pt, l) for pt, l in s if l >= R3_DRIFT_MULT * bsp - 1e-9), None)
        if first_le2:
            entries.append(("R1", "back", sid, first_le2[0], first_le2[1]))
            if led:
                entries.append(("R4", "back", sid, first_le2[0], first_le2[1]))
        if first_le15:
            entries.append(("R2", "lay", sid, first_le15[0], first_le15[1]))
        if first_drift:
            entries.append(("R3", "back", sid, first_drift[0], first_drift[1]))
        # R5 candidate: one uniformly-random in-running instant for this runner
        pt, l = rng.choice(s)
        r5_pool.append(("R5", "back", sid, pt, l))
    # R5 ~matched count: subsample to the largest of R1-R4 counts (seeded)
    target = max((sum(1 for e in entries if e[0] == r) for r in ("R1", "R2", "R3", "R4")),
                 default=0)
    if r5_pool and target and len(r5_pool) > target:
        r5_pool = rng.sample(r5_pool, target)
    entries.extend(r5_pool)
    return entries


# --------------------------------------------------------------------------- #
# Pass 2 — realistic fill at t+L, plus the hindsight canary window             #
# --------------------------------------------------------------------------- #
def _fill_entries(messages, entries) -> Dict[Tuple, dict]:
    """For each entry, replay the book and capture the struck price + matched £ at t+L
    (crossing the spread within 1-tick slip), and the best in-window traded price (C1).

    Returns { (rule, sid): fill_dict }. Only one entry per (rule, sid) is possible by
    construction (each rule fires at most once per runner).
    """
    # schedule: sid -> list of (rule, side, signal_pt, entry_price, deadline)
    m0 = Market()  # first pass to learn per-market bet_delay for the latency
    # We need bet_delay before scheduling; grab it from settlement/def cheaply.
    _, _, _, bet_delay = settlement(messages)
    latency = max(MIN_LATENCY_MS, int((bet_delay or 1) * 1000))

    pending: Dict[Tuple, dict] = {}
    window_best: Dict[Tuple, float] = {}
    for rule, side, sid, sig_pt, entry in entries:
        key = (rule, sid)
        pending[key] = {"rule": rule, "side": side, "sid": sid, "signal_pt": sig_pt,
                        "entry_price": entry, "deadline": sig_pt + latency,
                        "struck": None, "matched": 0.0, "filled": False,
                        "c1_struck": entry, "bet_delay": bet_delay}
        window_best[key] = entry

    m = Market()
    remaining = set(pending)
    for msg in messages:
        m.apply_mcm(msg)
        pt = m.publish_time
        if pt is None:
            continue
        # accumulate in-window best traded price for the canary
        for mc in msg.get("mc", []):
            for rc in mc.get("rc", []):
                if "ltp" not in rc:
                    continue
                sid = rc.get("id")
                ltp = rc["ltp"]
                for rule in ("R1", "R2", "R3", "R4", "R5"):
                    key = (rule, sid)
                    p = pending.get(key)
                    if p is None or pt < p["signal_pt"] or pt > p["deadline"]:
                        continue
                    if p["side"] == "back":
                        window_best[key] = max(window_best[key], ltp)   # best odds to back = highest
                    else:
                        window_best[key] = min(window_best[key], ltp)   # best odds to lay = lowest
        # fulfil fills whose t+L deadline elapsed
        for key in list(remaining):
            p = pending[key]
            if pt < p["deadline"]:
                continue
            sid = p["sid"]
            entry = p["entry_price"]
            book = m.books.get(sid)
            struck = matched = None
            if book is not None:
                if p["side"] == "back":
                    limit = ticks_move(entry, -SLIP_TICKS)          # accept down to entry-1tick
                    offers = [(pr, sz) for pr, sz in book.back.items() if pr >= limit - 1e-9]
                    if offers:
                        struck = max(pr for pr, _ in offers)        # cross to best available back
                        matched = round(sum(sz for _, sz in offers), 2)
                else:
                    limit = ticks_move(entry, SLIP_TICKS)           # accept up to entry+1tick
                    offers = [(pr, sz) for pr, sz in book.lay.items() if pr <= limit + 1e-9]
                    if offers:
                        struck = min(pr for pr, _ in offers)
                        matched = round(sum(sz for _, sz in offers), 2)
            p["struck"] = struck
            p["matched"] = matched or 0.0
            p["filled"] = struck is not None and (matched or 0.0) >= MIN_MATCH
            p["c1_struck"] = window_best[key]
            remaining.discard(key)
        if not remaining:
            break
    # entries whose deadline never arrived (market ended): unfilled, canary still valid
    for key in remaining:
        pending[key]["filled"] = False
        pending[key]["c1_struck"] = window_best[key]
    return pending


# --------------------------------------------------------------------------- #
# measure_market — pure, testable                                             #
# --------------------------------------------------------------------------- #
def measure_market(messages: List[dict], is_led: Callable[[int], bool],
                   seed: int = RNG_SEED) -> List[dict]:
    """One market's messages -> a scored opportunity record per (rule, runner-entry)."""
    winners, removed, bsp_by_sid, _bd = settlement(messages)
    series, inplay_start = _ltp_series(messages)
    if inplay_start is None:
        return []                                   # never went in running
    rng = random.Random(seed ^ (hash(messages[0].get("mc", [{}])[0].get("id", "")) & 0xFFFFFFFF)
                         if messages else seed)
    entries = _detect_entries(series, is_led, bsp_by_sid, removed, rng)
    fills = _fill_entries(messages, entries)

    out: List[dict] = []
    for (rule, side, sid, sig_pt, entry) in entries:
        f = fills[(rule, sid)]
        won = sid in winners
        s = series.get(sid, [])
        p1 = _ltp_at(s, s[-1][0]) if s else None                 # final in-running LTP
        p2 = _ltp_at(s, sig_pt + P2_OFFSET_MS)                    # LTP at entry + 30 s
        p2_trunc = (s and sig_pt + P2_OFFSET_MS > s[-1][0])
        p3 = bsp_by_sid.get(sid)                                 # BSP (known-invalid control)
        struck = f["struck"] if f["filled"] else None
        rec = {
            "rule": rule, "side": side, "market_id": f.get("market_id"),
            "selection_id": sid, "signal_pt": sig_pt, "entry_price": entry,
            "band": price_band(entry), "won": won, "bsp": p3,
            "filled": f["filled"], "struck": struck, "matched": f["matched"],
            "p1_final_ltp": p1, "p2_ltp_t30": p2, "p2_truncated": bool(p2_trunc),
            "c1_struck": f["c1_struck"],
            # realised G1 (filled only) and the hindsight canary C1
            "g1_pnl": (back_pnl(struck, won) if side == "back" else lay_pnl(struck, won))
                      if struck is not None else None,
            "c1_pnl": (back_pnl(f["c1_struck"], won) if side == "back"
                       else lay_pnl(f["c1_struck"], won)) if f["c1_struck"] else None,
            # CLV under three pseudo-closes (filled only)
            "clv_p1": side_clv(side, struck, p1) if struck is not None else None,
            "clv_p2": side_clv(side, struck, p2) if struck is not None else None,
            "clv_p3": side_clv(side, struck, p3) if struck is not None else None,
        }
        out.append(rec)
    return out


# --------------------------------------------------------------------------- #
# Aggregation, Kendall tau, verdict                                            #
# --------------------------------------------------------------------------- #
def _mean(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def _band_common(records, side):
    """Per-band pooled mean G1 pnl over all filled `side` opportunities = the zero-skill
    band-common return. <MIN_BAND_N obs -> global (same-side) fallback."""
    by_band = defaultdict(list)
    allpnl = []
    for r in records:
        if r["side"] != side or r["g1_pnl"] is None or r["band"] is None:
            continue
        by_band[r["band"]].append(r["g1_pnl"])
        allpnl.append(r["g1_pnl"])
    glob = _mean(allpnl)
    common = {}
    for b, xs in by_band.items():
        common[b] = _mean(xs) if len(xs) >= MIN_BAND_N else glob
    return common, glob


def aggregate(records: List[dict]) -> dict:
    """Per-rule G1/G2/C1 + the three pseudo-close CLVs, and n."""
    rules = ["R1", "R2", "R3", "R4", "R5"]
    common_back, glob_back = _band_common(records, "back")
    common_lay, glob_lay = _band_common(records, "lay")

    per_rule = {}
    for rule in rules:
        rr = [r for r in records if r["rule"] == rule]
        filled = [r for r in rr if r["filled"]]
        side = rr[0]["side"] if rr else "back"
        common = common_back if side == "back" else common_lay
        glob = glob_back if side == "back" else glob_lay
        g2 = []
        for r in filled:
            if r["g1_pnl"] is None:
                continue
            base = common.get(r["band"], glob) if r["band"] is not None else glob
            if base is not None:
                g2.append(r["g1_pnl"] - base)
        per_rule[rule] = {
            "side": side,
            "n_entries": len(rr),
            "n_filled": len(filled),
            "fill_rate": round(len(filled) / len(rr), 4) if rr else None,
            "G1_abs_roi": _mean([r["g1_pnl"] for r in filled]),
            "G2_strat_diff": _mean(g2),
            "C1_hindsight_roi": _mean([r["c1_pnl"] for r in rr]),
            "P1_clv": _mean([r["clv_p1"] for r in filled]),
            "P2_clv": _mean([r["clv_p2"] for r in filled]),
            "P3_clv": _mean([r["clv_p3"] for r in filled]),
            "p2_truncated_frac": round(_mean([1.0 if r["p2_truncated"] else 0.0
                                              for r in filled]) or 0.0, 4),
        }
    return per_rule


def kendall_tau(order_a: List[str], vals_a: Dict[str, float],
                vals_b: Dict[str, float]) -> Optional[float]:
    """Kendall tau-b between two rankings of the same items by their metric values."""
    items = [k for k in order_a if vals_a.get(k) is not None and vals_b.get(k) is not None]
    n = len(items)
    if n < 2:
        return None
    conc = disc = 0
    for i in range(n):
        for j in range(i + 1, n):
            a = vals_a[items[i]] - vals_a[items[j]]
            b = vals_b[items[i]] - vals_b[items[j]]
            s = a * b
            if s > 0:
                conc += 1
            elif s < 0:
                disc += 1
            # ties contribute to neither (tau-b denominator handles them)
    # tau-b
    import math
    n0 = n * (n - 1) / 2

    def ties(vals):
        c = Counter(round(vals[k], 12) for k in items)
        return sum(v * (v - 1) / 2 for v in c.values())
    t_a, t_b = ties(vals_a), ties(vals_b)
    denom = math.sqrt((n0 - t_a) * (n0 - t_b))
    return (conc - disc) / denom if denom > 0 else None


def verdict(per_rule: dict) -> dict:
    """Apply the pre-registered decision rule (pre-reg §5). Returns dict with the
    verdict string and the components that drove it."""
    rules_core = ["R1", "R2", "R3", "R4"]                 # R5 is the control, not gated on sign
    all_rules = ["R1", "R2", "R3", "R4", "R5"]
    g1 = {r: per_rule[r]["G1_abs_roi"] for r in all_rules}
    g2 = {r: per_rule[r]["G2_strat_diff"] for r in all_rules}
    p1 = {r: per_rule[r]["P1_clv"] for r in all_rules}
    p2 = {r: per_rule[r]["P2_clv"] for r in all_rules}
    p3 = {r: per_rule[r]["P3_clv"] for r in all_rules}

    def sgn(x):
        return 0 if x is None or abs(x) < 1e-9 else (1 if x > 0 else -1)

    sign_break = []
    for r in rules_core:
        for pname, pv in (("P1", p1), ("P2", p2), ("P3", p3)):
            if g1[r] is not None and pv[r] is not None and sgn(pv[r]) != sgn(g1[r]):
                sign_break.append(f"{pname}/{r}")
    spread = {}
    for r in all_rules:
        vals = [v for v in (p1[r], p2[r], p3[r]) if v is not None]
        spread[r] = (max(vals) - min(vals)) if len(vals) >= 2 else None
    spread12 = {}
    for r in all_rules:
        vals = [v for v in (p1[r], p2[r]) if v is not None]
        spread12[r] = (max(vals) - min(vals)) if len(vals) == 2 else None
    big_spread = [r for r, s in spread.items() if s is not None and s > 0.10]
    r5_positive = [p for p, pv in (("P1", p1), ("P2", p2), ("P3", p3))
                   if pv["R5"] is not None and pv["R5"] > 0.01]

    tau_g1 = {p: kendall_tau(all_rules, d, g1) for p, d in (("P1", p1), ("P2", p2), ("P3", p3))}
    tau_g2 = {p: kendall_tau(all_rules, d, g2) for p, d in (("P1", p1), ("P2", p2), ("P3", p3))}

    not_safe = bool(sign_break) or bool(big_spread) or bool(r5_positive)

    # PROXY-ROBUST (hard to earn): all of sign-agree P1&P2 on R1-R4, tau>=0.8 P1&P2 vs G1,
    # spread P1/P2 <=3pp every rule, R5 ~zero P1&P2, P3 visibly misbehaves.
    sign_ok_p12 = all(
        g1[r] is not None and p1[r] is not None and p2[r] is not None
        and sgn(p1[r]) == sgn(g1[r]) and sgn(p2[r]) == sgn(g1[r]) for r in rules_core)
    tau_ok = (tau_g1["P1"] is not None and tau_g1["P1"] >= 0.8 and
              tau_g1["P2"] is not None and tau_g1["P2"] >= 0.8)
    spread12_ok = all(s is not None and s <= 0.03 for s in spread12.values())
    r5_zero_p12 = (abs(p1["R5"] or 0) <= 0.01 and abs(p2["R5"] or 0) <= 0.01)
    p3_misbehaves = bool([1 for r in rules_core
                          if p3[r] is not None and g1[r] is not None
                          and (sgn(p3[r]) != sgn(g1[r]) or (spread[r] or 0) > 0.10)])
    proxy_robust = (not not_safe and sign_ok_p12 and tau_ok and spread12_ok
                    and r5_zero_p12 and p3_misbehaves)

    if not_safe:
        v = "NOT SAFE"
    elif proxy_robust:
        v = "PROXY-ROBUST"
    else:
        v = "INCONCLUSIVE"
    return {
        "verdict": v,
        "sign_disagreements_R1_R4": sign_break,
        "proxy_spread_P1P2P3": {r: (round(s, 4) if s is not None else None)
                                for r, s in spread.items()},
        "proxy_spread_P1P2": {r: (round(s, 4) if s is not None else None)
                              for r, s in spread12.items()},
        "spread_over_10pp": big_spread,
        "R5_positive_under": r5_positive,
        "kendall_tau_vs_G1": tau_g1,
        "kendall_tau_vs_G2": tau_g2,
    }


# --------------------------------------------------------------------------- #
# Tar driver (parallel; forked workers share the run-style index COW)         #
# --------------------------------------------------------------------------- #
_G_INDEX = None
_G_COURSES = None


def process_tar(tar_path: str):
    from backtest.pro_form_join import market_date, runstyle_lookup
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
            md = peek_market_definition(io.BytesIO(comp))
            v, reason = market_verdict(md, courses) if md else (None, "no_md")
            c["reason_" + reason] += 1
            if v != "flat":
                continue
            c["flat_markets"] += 1
            try:
                raw = bz2.decompress(comp)
                messages = [json.loads(l) for l in raw.decode("utf-8", "replace").splitlines()
                            if l.strip()]
            except Exception:
                c["decompress_error"] += 1
                continue
            date = market_date(md.get("marketTime"))
            venue = md.get("venue")
            name_by_sid = {rd["id"]: rd.get("name") for rd in md.get("runners", [])
                           if rd.get("status") == "ACTIVE"}

            def is_led(sid, _d=date, _v=venue, _n=name_by_sid, _i=idx):
                if _i is None:
                    return False
                style, _k = runstyle_lookup(_i, _d, _v, _n.get(sid))
                return style == "led"

            market_recs = measure_market(messages, is_led)
            for r in market_recs:
                r["market_id"] = md.get("marketId") or r.get("market_id")
            recs.extend(market_recs)
            c["scored_markets"] += 1
            c["opportunities"] += len(market_recs)
    return recs, dict(c)


def assert_coverage(cov: dict) -> None:
    """Pre-reg §6: assume a silent zero-match join exists. A join that matched 0 rows
    produces a beautiful, meaningless Kendall tau — so fail loudly here instead."""
    if cov.get("flat_markets", 0) <= 0:
        raise AssertionError("zero GB-flat markets classified — tar/course join is empty")
    if cov.get("opportunities", 0) <= 0:
        raise AssertionError("zero opportunities scored — run-style / LTP join is empty")


def run_q1(tar_paths, form_csvs, courses_path, workers: int = 8):
    from backtest.pro_form_join import build_runstyle_index
    global _G_INDEX, _G_COURSES
    _G_INDEX = build_runstyle_index(form_csvs) if form_csvs else None
    _G_COURSES = load_gb_courses(courses_path)
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    with ctx.Pool(workers) as pool:
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
    import sys
    import time

    ROOT = "/home/gabriel/projects/racing_project"
    tars = sorted(glob.glob(os.path.join(ROOT, "data/historical/betfair_pro/*.tar")))
    if "--tars" in sys.argv:
        k = int(sys.argv[sys.argv.index("--tars") + 1])
        tars = tars[:k]
    forms = [p for p in [
        os.path.join(ROOT, "vendor/rpscrape/data/region/gb/all/2014_05_01_2015_04_30.csv"),
        os.path.join(ROOT, "vendor/rpscrape/data/region/gb/all/2015_05_01_2016_04_30.csv"),
    ] if os.path.exists(p)]
    workers = int(os.environ.get("Q1_WORKERS", "8"))
    print("tars=%d forms=%d workers=%d" % (len(tars), len(forms), workers))
    t0 = time.time()
    recs, cov = run_q1(tars, forms, os.path.join(ROOT, "data/reference/course_geometry.csv"), workers)
    dt = time.time() - t0
    per_rule = aggregate(recs)
    vd = verdict(per_rule)
    assert_coverage(cov)
    out = {"verdict": vd, "per_rule": per_rule, "coverage": cov,
           "n_records": len(recs), "wall_clock_s": round(dt, 1),
           "n_tars": len(tars), "forms": [os.path.basename(f) for f in forms]}
    dest = os.path.join(ROOT, "models/q1_clv_validity_results.json")
    with open(dest, "w") as fh:
        json.dump(out, fh, indent=2, default=str)
    print("wall clock: %.0fs  records=%d" % (dt, len(recs)))
    print("coverage:", json.dumps(cov, indent=2))
    print("VERDICT:", vd["verdict"])
    print("per_rule:", json.dumps(per_rule, indent=2, default=str))
    print("verdict detail:", json.dumps(vd, indent=2, default=str))
    print("wrote", dest)
