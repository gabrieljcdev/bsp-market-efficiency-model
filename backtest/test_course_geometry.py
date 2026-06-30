"""
test_course_geometry.py -- invariant guards for the static course-geometry join.

Guards the things that quietly break a course-keyed join, NOT the geometry values
themselves (those are reviewed/edited by hand):

  1. Every course the join key can take is covered. The geometry reference must
     byte-match the manifest's `course` enum exactly (the manifest enum is sourced
     from the joined CSV's distinct courses) -- a near-miss spelling joins to
     nothing. Zero missing, zero extra.
  2. Tier-2 fields stay gated. Every Tier-2 value is tier2_verified=false in the
     reference, and the engine REFUSES a selection rule referencing one (so an
     unverified descriptor can't feed analysis), while a Tier-1 field is accepted.

Stdlib unittest only. Discovered by run_tests.py.
    python3 -m unittest backtest.test_course_geometry
"""
import csv
import json
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "racing_rulebuilder"))
import run_strategy as rs          # noqa: E402

GEO_CSV = os.path.join(_ROOT, "data", "reference", "course_geometry.csv")
MANIFEST = os.path.join(_ROOT, "racing_rulebuilder", "field_manifest.json")
TIER2 = {"course_character", "undulation", "uphill_finish"}
TIER1 = {"handedness", "course_shape", "circumference_f", "run_in_y"}


def _geo_rows():
    with open(GEO_CSV, newline="") as f:
        return list(csv.DictReader(f))


class TestCourseNameMatch(unittest.TestCase):
    def test_geometry_covers_every_manifest_course_exactly(self):
        with open(MANIFEST, encoding="utf-8") as fh:
            m = json.load(fh)
        course_field = next(f for f in m["fields"] if f["name"] == "course")
        enum_courses = set(course_field["values"])          # sourced from the joined CSV
        geo_courses = {r["course"] for r in _geo_rows()}
        self.assertEqual(geo_courses - enum_courses, set(),
                         "geometry rows whose name byte-matches no dataset course")
        self.assertEqual(enum_courses - geo_courses, set(),
                         "dataset courses with no geometry row (would join to blank)")
        self.assertEqual(len(geo_courses), 65)


class TestTierFlags(unittest.TestCase):
    def test_every_tier2_value_is_unverified(self):
        for r in _geo_rows():
            self.assertEqual(r["tier2_verified"], "false",
                             f"{r['course']} Tier-2 not flagged unverified")

    def test_manifest_marks_tiers_correctly(self):
        with open(MANIFEST, encoding="utf-8") as fh:
            m = json.load(fh)
        by_name = {f["name"]: f for f in m["course_geometry"]}
        for n in TIER1:
            self.assertTrue(by_name[n]["selectable"], f"{n} should be selectable")
        for n in TIER2:
            self.assertFalse(by_name[n]["selectable"], f"{n} must NOT be selectable")
            self.assertIs(by_name[n]["verified"], False)


class TestEngineGate(unittest.TestCase):
    """check_fields must refuse unverified Tier-2 fields but accept Tier-1."""

    def setUp(self):
        self.post, self.derived, self.unverified = rs.load_manifest_sets()
        # the materialised columns the rule could legitimately reference
        self.columns = TIER1 | TIER2 | {"course", "or"}

    def test_unverified_set_is_the_tier2_block(self):
        self.assertEqual(self.unverified, TIER2)

    def test_tier2_field_is_refused(self):
        fc = rs.check_fields({"course_character"}, self.columns,
                             self.post, self.derived, self.unverified)
        self.assertIn("course_character", fc["unverified"])
        self.assertNotIn("course_character", fc["ok"])

    def test_tier1_field_is_ok(self):
        fc = rs.check_fields({"circumference_f"}, self.columns,
                             self.post, self.derived, self.unverified)
        self.assertIn("circumference_f", fc["ok"])
        self.assertEqual(fc["unverified"], [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
