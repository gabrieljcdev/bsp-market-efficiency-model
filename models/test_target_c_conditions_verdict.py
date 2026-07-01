#!/usr/bin/env python3
"""test_target_c_conditions_verdict.py -- lock the Target-C-EXT verdict gate.

The gate must: (a) return PRICED for the observed shape (conditions add nothing
beyond the recalibrated market prob, but the post-race rpr canary DOES -> the test
is powered and the null is informative); (b) return RULED-IN when conditions really
do beat the market; (c) return INCONCLUSIVE when even the rpr canary can't beat the
market (test unpowered -> a null is uninformative). Proves the gate is not stuck.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_target_c_conditions as tcc  # noqa: E402


def _res(n, b1c_d, m2_d, b1c_h, m2_h, rpr_h):
    return {
        "holdout": {"n": n, "brier_market_recal": b1c_h,
                    "brier_market_cond": m2_h, "brier_market_rpr": rpr_h},
        "discovery": {"n": 57000, "brier_market_recal": b1c_d,
                      "brier_market_cond": m2_d, "brier_market_rpr": rpr_h - 0.013},
    }


class TestConditionsVerdict(unittest.TestCase):
    def test_observed_priced(self):
        # market+cond ~ market recal on holdout (slightly worse), canary beats -> priced
        r = _res(24553, 0.20216, 0.20200, 0.20340, 0.20364, 0.18991)
        v, reason = tcc.verdict(r)
        self.assertEqual(v, "priced")
        self.assertIn("ALREADY in the price", reason)

    def test_real_conditioning_rules_in(self):
        # conditions beat recal market by > eps on BOTH splits, canary powered
        r = _res(24553, 0.2020, 0.1990, 0.2034, 0.2004, 0.1899)
        v, reason = tcc.verdict(r)
        self.assertEqual(v, "ruled-in")
        self.assertIn("beyond what the price", reason)

    def test_unpowered_is_inconclusive(self):
        # even the rpr canary cannot beat the recalibrated market -> test unpowered
        r = _res(24553, 0.2034, 0.2034, 0.2034, 0.2035, 0.20335)
        v, reason = tcc.verdict(r)
        self.assertEqual(v, "inconclusive")
        self.assertIn("POWER CHECK FAILED", reason)

    def test_thin_holdout(self):
        r = _res(500, 0.2020, 0.1990, 0.2034, 0.2004, 0.1899)
        v, _ = tcc.verdict(r)
        self.assertEqual(v, "thin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
