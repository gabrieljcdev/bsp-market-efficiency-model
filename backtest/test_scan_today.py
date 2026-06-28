"""
test_scan_today.py -- regression test for native int/bool coercion in selection
rules. This is the divergence found on first contact with live rpscrape cards.

Live racecard JSON carries NATIVE ints (race_class = 3) and NATIVE bools
(non_runner = True) where the historical CSV is all strings. A categorical rule
on `class` used to crash on `(3).strip()`; the fix coerces non-string cells to
`str` in run_strategy._eval_rule (the categorical and flag branches).

These tests FAIL against the pre-fix code -- they raise AttributeError on the
int/bool cell -- and PASS after. They exercise the coercion path itself, not a
stringified stand-in: the fixture race carries a real `int` class and real
`bool` flags, mirroring rpscrape's asdict() output.

Stdlib unittest only. Discovered by run_tests.py (which scans backtest/).
    python3 run_tests.py
    python3 -m unittest backtest.test_scan_today
"""
import os
import sys
import unittest

# scan_today + run_strategy live in racing_rulebuilder/; make them importable
# regardless of the working directory (run_strategy itself wires in backtest/).
_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "racing_rulebuilder"))
import run_strategy as rs          # noqa: E402
import scan_today                  # noqa: E402


def _card(race_class, going, runners):
    """A minimal racecard with only the fields scan_today reads. `race_class`
    type (int vs str) is the variable under test."""
    return {
        "date": "2026-06-28", "region": "GB", "course": "Ascot",
        "off_time": "13:00", "race_name": "Test Race", "race_type": "Flat",
        "race_class": race_class, "going": going, "surface": "Turf",
        "distance": "1m", "distance_f": 8.0, "distance_y": 1760,
        "field_size": len(runners), "rating_band": "0-105", "age_band": "3yo",
        "pattern": None, "prize": "10000", "course_detail": "R",
        "runners": runners,
    }


def _runner(name, ofr, num, non_runner=False, reserve=False):
    return {
        "name": name, "number": num, "draw": num, "age": 4,
        "sex_code": "G", "sex": None, "lbs": 130, "ofr": ofr,
        "headgear": None, "form": "1-2", "jockey": "J", "trainer": "T",
        "sire": "S", "dam": "D", "damsire": "DS", "owner": "O",
        "non_runner": non_runner, "reserve": reserve,
    }


class TestNativeIntClassEndToEnd(unittest.TestCase):
    """The exact shape that crashed: a categorical rule on an int race_class,
    scanned through scan_today.scan() just as the live card flows through it."""

    def setUp(self):
        # Race A: class as a NATIVE INT (3) like live rpscrape; 2 active + 1 NR.
        # Race B: class as a STRING ("3") like the historical CSV; 1 runner.
        self.cards = {"GB": {"Ascot": {
            "13:00": _card(3, "Good", [
                _runner("Int Horse A", 90, 1),
                _runner("Int Horse B", 85, 2),
                _runner("Gone NR", 99, 3, non_runner=True),
            ]),
            "13:30": _card("3", "Good", [
                _runner("Str Horse", 95, 1),
            ]),
        }}}
        # The fixture must really carry a native int + native bool (asdict shape),
        # not a stringified stand-in -- otherwise it would not exercise the bug.
        a = self.cards["GB"]["Ascot"]["13:00"]
        self.assertIsInstance(a["race_class"], int)
        self.assertIsInstance(a["runners"][2]["non_runner"], bool)
        self.assertIsInstance(self.cards["GB"]["Ascot"]["13:30"]["race_class"], str)

    def _strategy(self, op, value):
        return {"selection_rules": {"combinator": "all", "children": [
            {"field": "class", "type": "categorical", "op": op, "value": value}]}}

    def test_is_matches_both_int_and_string_class(self):
        # 'class is "3"' must match BOTH the int-3 race and the string-"3" race.
        res = scan_today.scan(self._strategy("is", "3"), self.cards)
        self.assertTrue(res["ok"], msg=res.get("errors"))
        self.assertEqual(res["n_races_with_qualifier"], 2)   # both races qualify
        self.assertEqual(res["n_qualifiers"], 3)             # 2 (race A) + 1 (race B)
        self.assertEqual(res["n_nonrunners_excluded"], 1)    # the NR still excluded

    def test_is_non_matching_class_excluded(self):
        # 'class is "5"' matches neither race -> zero qualifiers, still clean.
        res = scan_today.scan(self._strategy("is", "5"), self.cards)
        self.assertTrue(res["ok"], msg=res.get("errors"))
        self.assertEqual(res["n_qualifiers"], 0)

    def test_in_operator_over_int_cell(self):
        # 'class in ["3","4"]' exercises the categorical 'in' branch on an int cell.
        res = scan_today.scan(self._strategy("in", ["3", "4"]), self.cards)
        self.assertTrue(res["ok"], msg=res.get("errors"))
        self.assertEqual(res["n_qualifiers"], 3)


class TestEvalRuleCoercion(unittest.TestCase):
    """Direct _eval_rule tests on native int/bool cells -- the coercion lines."""

    def test_categorical_int_cell_is(self):
        # raw is int 3 -> pre-fix this raised AttributeError on (3).strip()
        rule = {"field": "class", "type": "categorical", "op": "is", "value": "3"}
        self.assertTrue(rs._eval_rule(rule, {"class": 3}))
        self.assertFalse(rs._eval_rule(rule, {"class": 4}))

    def test_categorical_int_cell_in(self):
        rule = {"field": "class", "type": "categorical", "op": "in", "value": ["3", "4"]}
        self.assertTrue(rs._eval_rule(rule, {"class": 4}))
        self.assertFalse(rs._eval_rule(rule, {"class": 5}))

    def test_flag_native_bool_true(self):
        # raw is bool True -> pre-fix this raised AttributeError on (True).strip()
        rule = {"field": "f", "type": "flag", "op": "true", "value": True}
        self.assertTrue(rs._eval_rule(rule, {"f": True}))
        self.assertFalse(rs._eval_rule(rule, {"f": False}))

    def test_flag_native_bool_false_value(self):
        rule = {"field": "f", "type": "flag", "op": "false", "value": False}
        self.assertTrue(rs._eval_rule(rule, {"f": False}))
        self.assertFalse(rs._eval_rule(rule, {"f": True}))


if __name__ == "__main__":
    unittest.main(verbosity=2)
