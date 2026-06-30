"""
test_course_geometry.py -- invariant guards for the static course-geometry join.

Guards the things that quietly break a course-keyed join + the Tier-2 gate, NOT
the geometry values themselves (those are reviewed/edited by hand):

  1. Every course the join key can take is covered. The geometry reference must
     byte-match the manifest's `course` enum exactly -- a near-miss spelling joins
     to nothing. Zero missing, zero extra.
  2. Tier-2 verification is PER FIELD, PER COURSE. course_character / undulation
     are unverified everywhere -> selectable=false + engine-refused. uphill_finish
     is verified for a confirmed subset of courses -> selectable, but materialised
     ONLY for verified courses (unverified courses blank), so an unconfirmed value
     can never feed analysis.

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
sys.path.insert(0, os.path.join(_ROOT, "features"))
import run_strategy as rs          # noqa: E402
import course_geometry as cg       # noqa: E402

GEO_CSV = os.path.join(_ROOT, "data", "reference", "course_geometry.csv")
MANIFEST = os.path.join(_ROOT, "racing_rulebuilder", "field_manifest.json")
TIER1 = {"handedness", "course_shape", "circumference_f", "run_in_y"}
GATED_TIER2 = {"course_character", "undulation"}           # unverified everywhere
PERCOURSE_TIER2 = {"uphill_finish"}                        # verified per course
EXPECTED_UPHILL_VERIFIED = {
    "Sandown", "Towcester", "Ascot", "Pontefract", "Chepstow", "Hereford",
    "Fakenham", "Epsom", "Goodwood", "Newbury", "Uttoxeter",
}


def _geo_rows():
    with open(GEO_CSV, newline="") as f:
        return list(csv.DictReader(f))


def _manifest():
    with open(MANIFEST, encoding="utf-8") as fh:
        return json.load(fh)


class TestCourseNameMatch(unittest.TestCase):
    def test_geometry_covers_every_manifest_course_exactly(self):
        m = _manifest()
        enum_courses = set(next(f for f in m["fields"] if f["name"] == "course")["values"])
        geo_courses = {r["course"] for r in _geo_rows()}
        self.assertEqual(geo_courses - enum_courses, set(),
                         "geometry rows whose name byte-matches no dataset course")
        self.assertEqual(enum_courses - geo_courses, set(),
                         "dataset courses with no geometry row (would join to blank)")
        self.assertEqual(len(geo_courses), 65)


class TestTierFlags(unittest.TestCase):
    def test_gated_tier2_unverified_everywhere(self):
        for r in _geo_rows():
            self.assertEqual(r["course_character_verified"], "false")
            self.assertEqual(r["undulation_verified"], "false")

    def test_uphill_verified_exactly_the_confirmed_set(self):
        verified = {r["course"] for r in _geo_rows()
                    if r["uphill_finish_verified"] == "true"}
        self.assertEqual(verified, EXPECTED_UPHILL_VERIFIED)

    def test_manifest_marks_tiers_correctly(self):
        by_name = {f["name"]: f for f in _manifest()["course_geometry"]}
        for n in TIER1 | PERCOURSE_TIER2:                  # selectable: Tier 1 + uphill
            self.assertTrue(by_name[n]["selectable"], f"{n} should be selectable")
        for n in GATED_TIER2:
            self.assertFalse(by_name[n]["selectable"], f"{n} must NOT be selectable")
            self.assertIs(by_name[n]["verified"], False)
        self.assertIs(by_name["uphill_finish"]["verified"], True)


class TestMaterialisedMasking(unittest.TestCase):
    """The loader blanks uphill_finish for unverified courses, keeps it for
    verified ones, and still carries the gated Tier-2 fields raw."""

    def setUp(self):
        cg._CACHE = None                                   # force a fresh read
        self.geo = cg.load_geometry()

    def tearDown(self):
        cg._CACHE = None

    def test_uphill_present_only_for_verified_courses(self):
        present = {c for c, v in self.geo.items() if v["uphill_finish"]}
        self.assertEqual(present, EXPECTED_UPHILL_VERIFIED)

    def test_verified_uphill_values_are_yes_no(self):
        self.assertEqual(self.geo["Sandown"]["uphill_finish"], "Yes")
        self.assertEqual(self.geo["Epsom"]["uphill_finish"], "No")
        self.assertEqual(self.geo["Bath"]["uphill_finish"], "")     # unverified -> blank

    def test_gated_tier2_still_carried_raw(self):
        # course_character / undulation are gated but NOT blanked (carried for display)
        self.assertTrue(self.geo["Bath"]["course_character"])
        self.assertTrue(self.geo["York"]["undulation"])


class TestEngineGate(unittest.TestCase):
    """check_fields refuses still-gated Tier-2 fields but accepts verified ones."""

    def setUp(self):
        self.post, self.derived, self.unverified = rs.load_manifest_sets()
        self.columns = TIER1 | GATED_TIER2 | PERCOURSE_TIER2 | {"course", "or"}

    def test_unverified_set_is_only_the_gated_tier2(self):
        self.assertEqual(self.unverified, GATED_TIER2)

    def test_gated_tier2_field_is_refused(self):
        fc = rs.check_fields({"course_character"}, self.columns,
                             self.post, self.derived, self.unverified)
        self.assertIn("course_character", fc["unverified"])
        self.assertNotIn("course_character", fc["ok"])

    def test_uphill_finish_is_now_ok(self):
        fc = rs.check_fields({"uphill_finish"}, self.columns,
                             self.post, self.derived, self.unverified)
        self.assertIn("uphill_finish", fc["ok"])
        self.assertEqual(fc["unverified"], [])

    def test_tier1_field_is_ok(self):
        fc = rs.check_fields({"circumference_f"}, self.columns,
                             self.post, self.derived, self.unverified)
        self.assertIn("circumference_f", fc["ok"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
