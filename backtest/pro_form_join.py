"""Join PRO markets to scraped 2015-16 GB form → run_style_proxy per runner (Gate 1).

The locked signal (pre-reg §4) needs each runner's PRE-RACE dominant run-style. There is
no race-metadata for 2015-16, so we scrape the window's form and compute run_style_proxy
the same way the 2018-26 pipeline does: the dominant `classify_runstyle` over a horse's
STRICTLY-PRIOR run comments (features/history_join.py). Reuses the project's name/course
normalisers so the cross-source key matches the BSP join.

Key = (race_date, normalised course, normalised horse) — a horse runs at most once per
course per day, so this is effectively unique (same key the BSP join uses).
"""
from __future__ import annotations

import csv
from collections import defaultdict
from typing import Dict, Optional, Tuple

from features.history_join import classify_runstyle, _RUNSTYLE_ORDER
from parsers.join_form_bsp import norm_course, norm_name


def _dominant(styles) -> Optional[str]:
    if not styles:
        return None
    return max(_RUNSTYLE_ORDER, key=lambda s: (styles.count(s), -_RUNSTYLE_ORDER[s]))


def build_runstyle_index(form_csv) -> Dict[Tuple[str, str, str], Tuple[Optional[str], int]]:
    """{(date, norm_course, norm_horse): (run_style_proxy, n_prior)} over strictly-prior form.

    run_style_proxy for a race is the dominant style across the horse's runs BEFORE that
    race (never the race itself), matching the leakage discipline of the pre-off pipeline.
    ``form_csv`` may be one path or a list of paths (e.g. a 2014 lead-in + the window) —
    all rows are pooled so early-window races see their pre-window priors (no cold start).
    """
    paths = [form_csv] if isinstance(form_csv, str) else list(form_csv)
    by_horse = defaultdict(list)
    for p in paths:
        with open(p, newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                h = norm_name(row.get("horse"))
                if h:
                    by_horse[h].append(row)

    index: Dict[Tuple[str, str, str], Tuple[Optional[str], int]] = {}
    for h, runs in by_horse.items():
        runs.sort(key=lambda x: (x.get("date", ""), x.get("off", "")))
        prior = []
        for row in runs:
            key = (row.get("date", ""), norm_course(row.get("course", "")), h)
            index[key] = (_dominant(prior), len(prior))   # strictly-prior: current excluded
            st = classify_runstyle(row.get("comment"))
            if st:
                prior.append(st)
    return index


def market_date(market_time_utc: Optional[str]) -> str:
    """YYYY-MM-DD from a Betfair marketTime (e.g. '2015-06-01T13:00:00.000Z').

    GB racing is daytime, so the UTC calendar date equals the UK local race date (BST or
    GMT) in every case in this window.
    """
    return (market_time_utc or "")[:10]


def runstyle_lookup(index, date: str, venue: Optional[str], horse: Optional[str]):
    """(run_style_proxy, n_prior) for a PRO runner, or (None, 0) if unjoined."""
    return index.get((date, norm_course(venue or ""), norm_name(horse or "")), (None, 0))
