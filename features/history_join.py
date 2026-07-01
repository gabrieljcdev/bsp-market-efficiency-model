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
import re
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


_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")


def parse_distf(s):
    """Distance in furlongs from the object-typed dist_f column, which carries an
    'f' suffix ('16f', '21.5f') and may use the half symbol ('5½f' -> 5.5). Plain
    float() FAILS on these, so we strip to the leading numeric token (same idea as
    the bridge's _coerce_num). Returns None for blanks."""
    if s is None:
        return None
    m = _NUM_RE.search(str(s).replace("½", ".5"))
    return float(m.group()) if m else None


# Trailing Racing-Post country-of-breeding code: 'Atreides (IRE)', 'Gwash (GB)',
# 'Le Curieux (FR)'. Historical results carry it; LIVE racecards give the clean
# name -- so a live-card lookup misses the suffixed index key unless we canonicalise.
_COUNTRY_RE = re.compile(r"\s*\(([A-Z]{2,4})\)\s*$")


def canon_horse(name):
    """(base, country) for a horse name.

    Strips a trailing '(CC)' country code and normalises case + inner whitespace,
    so a live-card clean name ('Atreides') canonicalises to the same base as its
    historical key ('Atreides (IRE)'). `country` is None when no code is present.
    Used ONLY as a fallback when an exact-name lookup misses, and only when a base
    maps to a single country code (see HistoryIndex) -- so two genuinely different
    horses that share a name but differ in country ('X (IRE)' vs 'X (USA)') are
    never silently merged."""
    if name is None:
        return (None, None)
    s = str(name).strip()
    m = _COUNTRY_RE.search(s)
    cc = None
    if m:
        cc = m.group(1)
        s = s[:m.start()]
    return (" ".join(s.split()).lower(), cc)


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
        # Precompute parallel ord lists ONCE per entity (bisect needs them; never
        # rebuild per call -- that was O(runs^2) for big stables).
        self._ords = {
            "horse": {k: [x["ord"] for x in v] for k, v in self.horse.items()},
            "trainer": {k: [x["ord"] for x in v] for k, v in self.trainer.items()},
            "jockey": {k: [x["ord"] for x in v] for k, v in self.jockey.items()},
            "combo": {k: [x["ord"] for x in v] for k, v in self.combo.items()},
        }

        # Canonical horse fallback for LIVE-CARD names (which lack the historical
        # '(CC)' country suffix). Exact name is always tried FIRST in
        # prior_horse_runs, so the historical CSV path -- suffixed on both sides --
        # never reaches this and is byte-for-byte unaffected. This only rescues a
        # clean-name MISS. A base that maps to MORE THAN ONE distinct country code
        # is ambiguous (possibly different horses) and is REFUSED, never merged --
        # a silent wrong-merge would be worse than the miss.
        groups = {}                       # base -> list[original horse key]
        codes = {}                        # base -> set[country code]
        for key in self.horse:
            base, cc = canon_horse(key)
            groups.setdefault(base, []).append(key)
            s = codes.setdefault(base, set())
            if cc:
                s.add(cc)
        self._canon_horse = {}            # base -> (runs[], ords[])   (unambiguous)
        self._canon_ambiguous = set()     # bases with >1 country code -> refused
        for base, keys in groups.items():
            if len(codes[base]) > 1:
                self._canon_ambiguous.add(base)
            elif len(keys) == 1:          # reuse the existing sorted lists (no copy)
                k = keys[0]
                self._canon_horse[base] = (self.horse[k], self._ords["horse"][k])
            else:                         # merge case-variant keys, re-sort by ord
                merged = [run for k in keys for run in self.horse[k]]
                merged.sort(key=lambda r: r["ord"])
                self._canon_horse[base] = (merged, [r["ord"] for r in merged])

        # Strike-rate BUCKETS with prefix-win sums, so a strictly-prior SR is
        # O(log n) instead of rescanning a big stable's whole history per runner.
        # Bucket key -> (ords[], cumwins[]) where cumwins[i] = wins in runs[:i+1].
        # Buckets: trainer x {course,class,going} and the jockey-trainer combo.
        buckets = {}      # key -> list[(ord, won)]
        for r in src:
            trn, jky = r.get("trainer"), r.get("jockey")
            o = to_ord(r["date"])
            won = parse_pos(r.get("pos")) == 1
            if trn:
                buckets.setdefault(("tc", trn, r.get("course")), []).append((o, won))
                k = parse_class(r.get("class"))
                if k is not None:
                    buckets.setdefault(("tk", trn, k), []).append((o, won))
                g = r.get("going")
                if g:
                    buckets.setdefault(("tg", trn, g), []).append((o, won))
            if trn and jky:
                buckets.setdefault(("co", jky, trn), []).append((o, won))
        self._bkt = {}
        for key, pairs in buckets.items():
            pairs.sort(key=lambda p: p[0])          # by ord (src already date-sorted)
            ords, cum, run = [], [], 0
            for o, won in pairs:
                run += 1 if won else 0
                ords.append(o); cum.append(run)
            self._bkt[key] = (ords, cum)

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
            "dist_f": parse_distf(r.get("dist_f")),
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
    def _prior(self, kind, key, race_ord):
        """Runs for an entity with ord STRICTLY < race_ord (excludes same-day &
        the current run). [] for an unknown/empty key. O(log n) via precomputed
        ords."""
        runs = getattr(self, kind).get(key)
        if not runs:
            return []
        return runs[:bisect_left(self._ords[kind][key], race_ord)]

    def prior_horse_runs(self, horse, race_ord):
        """Strictly-prior runs for a horse. EXACT name is tried first (so the
        historical CSV path -- suffixed on both sides -- is unaffected); a MISS
        falls back to the country-code/case-canonical key, which rescues live-card
        clean names. An ambiguous canonical base (>1 country code) returns []."""
        runs = self.horse.get(horse)
        if runs is not None:
            return runs[:bisect_left(self._ords["horse"][horse], race_ord)]
        base, _ = canon_horse(horse)
        if base is None or base in self._canon_ambiguous:
            return []
        hit = self._canon_horse.get(base)
        if hit is None:
            return []
        runs, ords = hit
        return runs[:bisect_left(ords, race_ord)]

    def prior_trainer_runs(self, trainer, race_ord):
        return self._prior("trainer", trainer, race_ord)

    def prior_jockey_runs(self, jockey, race_ord):
        return self._prior("jockey", jockey, race_ord)

    def prior_combo_runs(self, jockey, trainer, race_ord):
        return self._prior("combo", (jockey, trainer), race_ord)

    # -- O(log n) strictly-prior strike rate via prefix-win buckets ----------- #
    def _sr_bucket(self, key, race_ord):
        """(strike_rate, n) over the bucket's runs with ord STRICTLY < race_ord.
        (None, 0) if the bucket is empty / no prior runs."""
        b = self._bkt.get(key)
        if not b:
            return (None, 0)
        ords, cum = b
        cut = bisect_left(ords, race_ord)          # count of prior runs
        if cut == 0:
            return (None, 0)
        wins = cum[cut - 1]                         # prefix wins in runs[:cut]
        return (wins / cut, cut)

    def trainer_srs(self, trainer, race_ord, course, klass, going):
        cs, cn = self._sr_bucket(("tc", trainer, course), race_ord)
        ks, kn = self._sr_bucket(("tk", trainer, klass), race_ord)
        gs, gn = self._sr_bucket(("tg", trainer, going), race_ord)
        return {"trainer_course_sr": cs, "trainer_course_sr_n": cn,
                "trainer_class_sr": ks, "trainer_class_sr_n": kn,
                "trainer_going_sr": gs, "trainer_going_sr_n": gn}

    def combo_sr(self, jockey, trainer, race_ord):
        s, n = self._sr_bucket(("co", jockey, trainer), race_ord)
        return {"jockey_trainer_combo_sr": s, "jockey_trainer_combo_sr_n": n}


# --------------------------------------------------------------------------- #
# run-style classifier: map a PRIOR-run closeup comment -> early-race style.   #
# RP comments are " - " separated and chronological; the EARLIEST positional   #
# phrase is the running style, so we pick the category whose keyword appears    #
# first in the string.                                                         #
# --------------------------------------------------------------------------- #
_RUNSTYLE_KEYS = {
    "led": ("made all", "made virtually all", "soon led", "led", "set off in front",
            "disputed lead", "every yard", "dictated", "in front"),
    "prominent": ("chased leaders", "chased leader", "tracked leaders",
                  "tracked leader", "pressed leader", "close up", "prominent",
                  "handy", "front rank", "raced keenly", "prom "),
    "midfield": ("mid-division", "mid division", "midfield", "in touch",
                 "centre of"),
    "held_up": ("held up", "in rear", "towards rear", "in last", "behind",
                "settled rear", "raced in rear", "patiently", "last early",
                "dropped rear", "in touch in rear"),
}


_RUNSTYLE_ORDER = {"led": 0, "prominent": 1, "midfield": 2, "held_up": 3}


def classify_runstyle(comment):
    """Return led/prominent/midfield/held_up from a single PRIOR-run comment, or
    None. Whichever category's keyword appears EARLIEST wins (early-race position).
    """
    if not comment:
        return None
    s = comment.lower()
    best, best_pos = None, len(s) + 1
    for style, keys in _RUNSTYLE_KEYS.items():
        for kw in keys:
            i = s.find(kw)
            if 0 <= i < best_pos:
                best, best_pos = style, i
    return best


# --------------------------------------------------------------------------- #
# PURE feature aggregation over a strictly-prior slice.                        #
# --------------------------------------------------------------------------- #
def horse_features(prior, ctx):
    """Derive the horse features from a STRICTLY-PRIOR run slice.

    `prior` : list[run] already filtered to ord < race_ord (date-ascending).
    `ctx`   : {race_ord, course, dist_f, cur_or, klass}.
    Returns a flat dict: each feature value plus its sample count `<name>_n`.
    None where there is no prior basis (no backfill).
    """
    n = len(prior)
    out = {
        "career_runs": n,
        "career_win_pct": None, "career_win_pct_n": n,
        "career_place_pct": None, "career_place_pct_n": n,
        "or_trajectory": None, "or_trajectory_n": 0,
        "class_change": None, "class_change_n": 0,
        "dslr": None, "dslr_n": 0,
        "won_course_flag": None, "won_course_flag_n": 0,
        "won_dist_flag": None, "won_dist_flag_n": 0,
        "won_cd_flag": None, "won_cd_flag_n": 0,
        "run_style": None, "run_style_n": 0,
    }
    if n == 0:
        return out

    out["career_win_pct"] = sum(1 for r in prior if r["won"]) / n
    out["career_place_pct"] = sum(1 for r in prior if r["placed"]) / n

    # OR-trajectory: current OR minus the mean OR of the last up-to-3 prior runs
    # that carried an OR. Positive => rated higher than recent form. cur_or and
    # prior OR are PRE-RACE published ratings (clean).
    cur_or = ctx.get("cur_or")
    if cur_or is not None:
        recent_or = [r["or"] for r in reversed(prior) if r["or"] is not None][:3]
        if recent_or:
            out["or_trajectory"] = cur_or - sum(recent_or) / len(recent_or)
            out["or_trajectory_n"] = len(recent_or)

    # class_change vs last run: lower class number = higher class. cur < last
    # => stepping UP in class; cur > last => DOWN; equal => SAME.
    cur_k = ctx.get("klass")
    last_k = next((r["klass"] for r in reversed(prior) if r["klass"] is not None), None)
    if cur_k is not None and last_k is not None:
        out["class_change"] = ("up" if cur_k < last_k
                               else "down" if cur_k > last_k else "same")
        out["class_change_n"] = 1

    # DSLR: days since the most recent prior run.
    out["dslr"] = ctx["race_ord"] - prior[-1]["ord"]
    out["dslr_n"] = 1

    # course / distance / course+distance prior-win flags. n = prior runs in that
    # condition so a thin "1 from 1" is visible, not hidden behind the flag.
    course, dist_f = ctx.get("course"), ctx.get("dist_f")
    at_course = [r for r in prior if r["course"] == course]
    at_dist = [r for r in prior if r["dist_f"] == dist_f]
    at_cd = [r for r in at_course if r["dist_f"] == dist_f]
    out["won_course_flag_n"] = len(at_course)
    out["won_dist_flag_n"] = len(at_dist)
    out["won_cd_flag_n"] = len(at_cd)
    if at_course:
        out["won_course_flag"] = 1 if any(r["won"] for r in at_course) else 0
    if at_dist:
        out["won_dist_flag"] = 1 if any(r["won"] for r in at_dist) else 0
    if at_cd:
        out["won_cd_flag"] = 1 if any(r["won"] for r in at_cd) else 0

    # dominant run-style across the horse's PRIOR-run comments (run-style proxy).
    # Tie-break by a FIXED priority (led>prominent>midfield>held_up) so the
    # feature is deterministic/reproducible -- max(set(...)) would break ties via
    # hash-randomised set order, making the materialised column non-reproducible.
    styles = [s for s in (classify_runstyle(r["comment"]) for r in prior) if s]
    if styles:
        out["run_style_n"] = len(styles)
        out["run_style"] = max(_RUNSTYLE_ORDER,
                               key=lambda s: (styles.count(s), -_RUNSTYLE_ORDER[s]))
    return out


# --------------------------------------------------------------------------- #
# trainer / jockey-trainer-combo strike rates over strictly-prior slices.      #
# Each SR is "wins / runs among the entity's prior runs matching the condition" #
# returned WITH its n so thin stats are visible.                               #
# --------------------------------------------------------------------------- #
def _sr(runs):
    """(strike_rate, n) over a run list; (None, 0) if empty."""
    n = len(runs)
    return ((sum(1 for r in runs if r["won"]) / n), n) if n else (None, 0)


# PURE reference implementations (used by the equivalence unit test). The live /
# batch path uses the index's O(log n) prefix-win buckets, which must AGREE with
# these brute-force scans over the same strictly-prior slice.
def trainer_features(prior, ctx):
    """trainer_course_sr / trainer_class_sr / trainer_going_sr from the trainer's
    STRICTLY-PRIOR runs matching today's course / class / going."""
    course, klass, going = ctx.get("course"), ctx.get("klass"), ctx.get("going")
    cs, cn = _sr([r for r in prior if r["course"] == course])
    ks, kn = _sr([r for r in prior if r["klass"] == klass]) if klass is not None else (None, 0)
    gs, gn = _sr([r for r in prior if r["going"] == going]) if going else (None, 0)
    return {
        "trainer_course_sr": cs, "trainer_course_sr_n": cn,
        "trainer_class_sr": ks, "trainer_class_sr_n": kn,
        "trainer_going_sr": gs, "trainer_going_sr_n": gn,
    }


def combo_features(prior, ctx):
    """jockey_trainer_combo_sr over the pairing's STRICTLY-PRIOR runs together."""
    s, n = _sr(prior)
    return {"jockey_trainer_combo_sr": s, "jockey_trainer_combo_sr_n": n}


# --------------------------------------------------------------------------- #
# the ONE call the live surfaces use: assemble every Layer-2 feature for a     #
# runner from the index, all strictly-prior.                                   #
# --------------------------------------------------------------------------- #
def runner_features(index, ctx):
    """Full Layer-2 feature dict for one runner.

    `ctx` must carry: race_ord, course, dist_f, cur_or, klass, going,
                      horse, jockey, trainer.
    Pulls strictly-prior slices from `index` then runs the pure aggregators.
    """
    ro = ctx["race_ord"]
    feats = horse_features(index.prior_horse_runs(ctx["horse"], ro), ctx)
    feats.update(index.trainer_srs(ctx["trainer"], ro, ctx.get("course"),
                                   ctx.get("klass"), ctx.get("going")))
    feats.update(index.combo_sr(ctx["jockey"], ctx["trainer"], ro))
    return feats


# Output naming shared by ALL consumers (materialiser, runner view, scanner) so
# the column names agree everywhere. run_style is exposed as the manifest's
# run_style_proxy. The ordered list is the materialised column order.
_OUTPUT_RENAME = {"run_style": "run_style_proxy", "run_style_n": "run_style_proxy_n"}
LAYER2_FIELDS = [
    "career_runs",
    "career_win_pct", "career_win_pct_n",
    "career_place_pct", "career_place_pct_n",
    "or_trajectory", "or_trajectory_n",
    "class_change", "class_change_n",
    "dslr", "dslr_n",
    "won_course_flag", "won_course_flag_n",
    "won_dist_flag", "won_dist_flag_n",
    "won_cd_flag", "won_cd_flag_n",
    "run_style_proxy", "run_style_proxy_n",
    "trainer_course_sr", "trainer_course_sr_n",
    "trainer_class_sr", "trainer_class_sr_n",
    "trainer_going_sr", "trainer_going_sr_n",
    "jockey_trainer_combo_sr", "jockey_trainer_combo_sr_n",
]
# Selectable Layer-2 fields a rule may reference (the value columns, not the _n).
LAYER2_SELECTABLE = [f for f in LAYER2_FIELDS if not f.endswith("_n")]


def named_features(index, ctx):
    """runner_features with output names (run_style -> run_style_proxy). The single
    feature dict every surface uses."""
    f = runner_features(index, ctx)
    for src, dst in _OUTPUT_RENAME.items():
        f[dst] = f.pop(src)
    return f


_INDEX_CACHE = {}


def get_index(csv_path=DEFAULT_CSV):
    """Process-cached HistoryIndex. The live surfaces (runner view, scanner Tier 2)
    call this so the date-sorted index is built once per process and shared, not
    rebuilt per request. ALWAYS built from the BASE joined CSV (raw history)."""
    key = os.path.abspath(csv_path)
    if key not in _INDEX_CACHE:
        _INDEX_CACHE[key] = HistoryIndex(csv_path)
    return _INDEX_CACHE[key]


def ctx_from_row(r):
    """Build a runner_features ctx from a raw joined/card row dict."""
    return {
        "race_ord": to_ord(r["date"]),
        "course": r.get("course"), "dist_f": parse_distf(r.get("dist_f")),
        "cur_or": fnum(r.get("or")), "klass": parse_class(r.get("class")),
        "going": r.get("going"), "horse": r.get("horse"),
        "jockey": r.get("jockey"), "trainer": r.get("trainer"),
    }


# --------------------------------------------------------------------------- #
# row iterator: (raw_row, horse_features) over the WHOLE file, strictly-prior. #
# Shared by the anchor test (Phase 1) and the materialiser (Phase 3).         #
# --------------------------------------------------------------------------- #
def iter_row_features(csv_path=DEFAULT_CSV):
    """(raw_row, full Layer-2 feature dict) for every row, strictly-prior.
    Shared by the anchor test (proof) and the materialiser (Phase 3)."""
    rows = HistoryIndex._read(csv_path)
    index = HistoryIndex(rows=rows)
    for r in rows:
        yield r, runner_features(index, ctx_from_row(r))


if __name__ == "__main__":
    # tiny smoke test
    idx = HistoryIndex()
    print(f"indexed horses={len(idx.horse)} trainers={len(idx.trainer)} "
          f"jockeys={len(idx.jockey)} combos={len(idx.combo)}")
