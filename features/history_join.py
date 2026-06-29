#!/usr/bin/env python3
"""history_join.py -- the SHARED Layer-2 history-join engine.

ONE join, used by all three Layer-2 surfaces (rule-builder backtest materialiser,
runner view, scanner Tier 2). Build it once; do not fork per feature or per
surface. This is the most leakage-sensitive component in the project, so the
join discipline is enforced HERE, in one place, and proven before any feature is
trusted (see anchor_test_history.py).

THE CARDINAL LEAKAGE RULE (mirrors features/build_rolling.py and the rpr catch)
------------------------------------------------------------------------------
For a runner in a race on date D, every derived feature is computed ONLY from
that horse's / trainer's / jockey's runs on dates STRICTLY BEFORE D.
  * The joined CSV is NOT globally date-sorted (one inversion at line 452718:
    2023-05-12 then 2023-05-11) -> we SORT BY DATE when building the index, never
    trust file order.
  * Strictly-prior is enforced by ordinal: prior = runs with run.ord < race.ord.
    Same-day runs share an ord, so bisect_left(ords, race_ord) excludes them too
    (no intra-day off-time ambiguity) -- identical guarantee to build_rolling's
    "compute all of a date's features BEFORE updating histories".
  * These features touch pos and comment (POST-RACE columns). They are
    leakage-safe ONLY because they read those columns from STRICTLY-PRIOR runs,
    never the current row. The current row's pos/comment never enter its own
    features.
Debut / no-prior-run -> the feature is None (no backfill), matching existing
discipline. Every feature is returned WITH its sample count n so thin stats are
always visible (no hidden threshold).

ARCHITECTURE
------------
  HistoryIndex(csv_path)          -- one date-sorted pass; per-entity run lists.
  index.prior_horse_runs(h, ord)  -- strictly-prior slice (bisect; O(log n)).
  horse_features(prior, ctx)      -- PURE aggregation over a strictly-prior slice.
The live surfaces call index.prior_*_runs(...) then the pure *_features(...).
The batch materialiser streams the CSV and calls the SAME pure functions. So the
leakage guarantee lives entirely in "which runs are in `prior`", computed one way.

PHASE 1 implements the horse features that touch pos/or (the most leakage-
sensitive sample) so the anchor proof bites. Trainer / jockey-combo / run-style
features are layered on in Phase 2 onto this same index.
"""
import csv
import os
from bisect import bisect_left
from datetime import date as _date

csv.field_size_limit(1 << 24)

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CSV = os.path.join(_ROOT, "data", "joined", "joined_gb_2018_2026.csv")


# --------------------------------------------------------------------------- #
# small parsers                                                               #
# --------------------------------------------------------------------------- #
def to_ord(d):
    """'YYYY-MM-DD' -> proleptic ordinal int (sortable, day-diffable)."""
    y, m, dd = d.split("-")
    return _date(int(y), int(m), int(dd)).toordinal()


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def parse_class(s):
    """'Class 4' -> 4 ; 'Class 1' -> 1 ; blank/other -> None.
    Lower integer = higher class (Class 1 is the top)."""
    if not s:
        return None
    t = str(s).strip().lower().replace("class", "").strip()
    try:
        return int(t)
    except ValueError:
        return None


def parse_pos(s):
    """Finishing position as int, or None for non-finishers (PU/F/UR/'-'/...)."""
    t = ("" if s is None else str(s)).strip()
    return int(t) if t.isdigit() else None


# --------------------------------------------------------------------------- #
# the index                                                                   #
# --------------------------------------------------------------------------- #
class HistoryIndex:
    """Per-entity, date-sorted run lists built from the joined CSV in one pass.

    A 'run' is a light dict with exactly the prior-run facts the Layer-2 features
    need. Horse runs are the Phase-1 surface; trainer/jockey/combo/sire lists are
    populated too (cheap) so Phase 2 needs no rebuild.
    """

    def __init__(self, csv_path=DEFAULT_CSV, rows=None):
        self.horse = {}        # horse -> list[run]  (date-ascending)
        self._horse_ords = {}  # horse -> list[int]  (parallel ords for bisect)
        # Phase-2 entities (populated now, used later):
        self.trainer = {}
        self.jockey = {}
        self.combo = {}        # (jockey, trainer) -> list[run]

        src = rows if rows is not None else self._read(csv_path)
        # SORT BY DATE FIRST (file is not globally sorted). Stable -> preserves
        # within-date file order, matching build_rolling.
        src.sort(key=lambda r: r["date"])
        for r in src:
            run = self._mk_run(r)
            self._append(self.horse, r["horse"], run)
            self._append(self.trainer, r.get("trainer"), run)
            self._append(self.jockey, r.get("jockey"), run)
            self._append(self.combo, (r.get("jockey"), r.get("trainer")), run)
        for h, runs in self.horse.items():
            self._horse_ords[h] = [x["ord"] for x in runs]

    @staticmethod
    def _read(csv_path):
        out = []
        with open(csv_path, newline="") as f:
            for r in csv.DictReader(f):
                out.append(r)
        return out

    @staticmethod
    def _mk_run(r):
        pos = parse_pos(r.get("pos"))
        return {
            "ord": to_ord(r["date"]),
            "date": r["date"],
            "pos": pos,
            "won": pos == 1,
            "placed": pos is not None and pos <= 3,
            "or": fnum(r.get("or")),
            "course": r.get("course"),
            "dist_f": fnum(r.get("dist_f")),
            "surface": r.get("surface"),
            "going": r.get("going"),
            "klass": parse_class(r.get("class")),
            "type": r.get("type"),
            "hg": (r.get("hg") or "").strip(),
            "comment": r.get("comment") or "",
        }

    @staticmethod
    def _append(d, key, run):
        if key in (None, ""):
            return
        d.setdefault(key, []).append(run)

    # -- strictly-prior slices ------------------------------------------------ #
    def prior_horse_runs(self, horse, race_ord):
        """Runs for `horse` with ord STRICTLY < race_ord (excludes same-day &
        the current run). Returns [] for a debut / unknown horse."""
        runs = self.horse.get(horse)
        if not runs:
            return []
        cut = bisect_left(self._horse_ords[horse], race_ord)
        return runs[:cut]

    def _prior_generic(self, d, key, race_ord):
        runs = d.get(key)
        if not runs:
            return []
        # entity lists are date-ascending; linear-scan cut (these are small per key
        # except for big stables -- still fine; a bisect cache can be added if hot).
        cut = bisect_left([x["ord"] for x in runs], race_ord)
        return runs[:cut]

    def prior_trainer_runs(self, trainer, race_ord):
        return self._prior_generic(self.trainer, trainer, race_ord)

    def prior_jockey_runs(self, jockey, race_ord):
        return self._prior_generic(self.jockey, jockey, race_ord)

    def prior_combo_runs(self, jockey, trainer, race_ord):
        return self._prior_generic(self.combo, (jockey, trainer), race_ord)


# --------------------------------------------------------------------------- #
# PURE feature aggregation over a strictly-prior slice (Phase 1 = horse)      #
# --------------------------------------------------------------------------- #
def horse_features(prior, ctx):
    """Derive the Phase-1 horse features from a STRICTLY-PRIOR run slice.

    `prior` : list[run] already filtered to ord < race_ord (date-ascending).
    `ctx`   : {race_ord, course, dist_f, cur_or}.
    Returns a flat dict: each feature value plus its sample count `<name>_n`.
    None where there is no prior basis (no backfill).
    """
    n = len(prior)
    out = {
        "career_runs": n,
        "career_win_pct": None, "career_win_pct_n": n,
        "career_place_pct": None, "career_place_pct_n": n,
        "or_trajectory": None, "or_trajectory_n": 0,
        "dslr": None, "dslr_n": 0,
        "won_cd_flag": None, "won_cd_flag_n": 0,
    }
    if n == 0:
        return out

    wins = sum(1 for r in prior if r["won"])
    places = sum(1 for r in prior if r["placed"])
    out["career_win_pct"] = wins / n
    out["career_place_pct"] = places / n

    # OR-trajectory: current OR minus the mean OR of the last up-to-3 prior runs
    # that carried an OR. Positive => rated higher than recent form. cur_or and
    # prior OR are PRE-RACE published ratings (clean).
    cur_or = ctx.get("cur_or")
    if cur_or is not None:
        recent_or = [r["or"] for r in reversed(prior) if r["or"] is not None][:3]
        if recent_or:
            out["or_trajectory"] = cur_or - sum(recent_or) / len(recent_or)
            out["or_trajectory_n"] = len(recent_or)

    # DSLR: days since the most recent prior run.
    out["dslr"] = ctx["race_ord"] - prior[-1]["ord"]
    out["dslr_n"] = 1

    # won at today's course AND distance before? n = prior runs at this C/D so a
    # thin "1 from 1" is visible, not hidden behind the flag.
    course, dist_f = ctx.get("course"), ctx.get("dist_f")
    cd = [r for r in prior if r["course"] == course and r["dist_f"] == dist_f]
    out["won_cd_flag_n"] = len(cd)
    if cd:
        out["won_cd_flag"] = 1 if any(r["won"] for r in cd) else 0
    return out


# --------------------------------------------------------------------------- #
# row iterator: (raw_row, horse_features) over the WHOLE file, strictly-prior. #
# Shared by the anchor test (Phase 1) and the materialiser (Phase 3).         #
# --------------------------------------------------------------------------- #
def iter_row_features(csv_path=DEFAULT_CSV):
    rows = HistoryIndex._read(csv_path)
    index = HistoryIndex(rows=rows)
    for r in rows:
        race_ord = to_ord(r["date"])
        prior = index.prior_horse_runs(r["horse"], race_ord)
        ctx = {"race_ord": race_ord, "course": r.get("course"),
               "dist_f": fnum(r.get("dist_f")), "cur_or": fnum(r.get("or"))}
        yield r, horse_features(prior, ctx)


if __name__ == "__main__":
    # tiny smoke test
    idx = HistoryIndex()
    print(f"indexed horses={len(idx.horse)} trainers={len(idx.trainer)} "
          f"jockeys={len(idx.jockey)} combos={len(idx.combo)}")
