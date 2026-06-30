#!/usr/bin/env python3
"""course_geometry.py -- shared loader for the static course-geometry reference.

Loads data/reference/course_geometry.csv (built by
data/reference/build_course_geometry.py) into a course-name -> values map and
exposes the column order, so the materialiser (build_history / the geometry join)
and any live surface paint identical columns from ONE source.

Join key is the exact course-name string -- byte-match with the joined dataset is
guaranteed by the builder's validation step. A course missing from the reference
yields blanks (never a guess); callers can detect that via geometry_for() == [""]*N.

TIER 2 fields (course_character / undulation / uphill_finish) are PROPOSED and
UNVERIFIED in the reference (tier2_verified=false). They are materialised for
display/join, but must NOT be treated as selectable analysis inputs until a human
verifies them -- that gate is enforced in the manifest (selectable=false), not here.
"""
import csv
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
REFERENCE_CSV = os.path.join(_ROOT, "data", "reference", "course_geometry.csv")

# Geometry value columns materialised per runner, in order. Tier 1 first, then
# the Tier 2 block. Excludes the bookkeeping cols (<field>_verified, notes) and
# the join key (course) itself.
TIER1_COLS = ["handedness", "course_shape", "circumference_f", "run_in_y"]
TIER2_COLS = ["course_character", "undulation", "uphill_finish"]
GEOMETRY_COLS = TIER1_COLS + TIER2_COLS

# Tier-2 fields PROMOTED to per-course verification: their value is materialised
# ONLY for courses whose <field>_verified == true (others blank), so an unverified
# course's draft value can never feed analysis even though the field is selectable.
# Still-fully-gated Tier-2 fields (course_character / undulation) are NOT here:
# they are carried raw for display but kept selectable=false + engine-refused via
# the manifest. Add a field here when it becomes per-course-verified + selectable.
PER_COURSE_VERIFIED = {"uphill_finish"}

_CACHE = None


def load_geometry(path=REFERENCE_CSV):
    """course-name -> {col: value} for the GEOMETRY_COLS. Memoised.

    A PER_COURSE_VERIFIED Tier-2 field is blanked for any course where its
    <field>_verified flag is not "true" (unverified -> unknown)."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE
    m = {}
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            vals = {}
            for c in GEOMETRY_COLS:
                v = r.get(c) or ""
                if c in PER_COURSE_VERIFIED:
                    verified = (r.get(c + "_verified") or "").strip().lower() == "true"
                    v = v if verified else ""
                vals[c] = v
            m[r["course"]] = vals
    _CACHE = m
    return m


def geometry_for(course, geo=None):
    """Ordered geometry values for `course` (GEOMETRY_COLS order); blanks if the
    course has no reference row."""
    geo = geo if geo is not None else load_geometry()
    row = geo.get(course)
    if row is None:
        return ["" for _ in GEOMETRY_COLS]
    return [row[c] for c in GEOMETRY_COLS]
