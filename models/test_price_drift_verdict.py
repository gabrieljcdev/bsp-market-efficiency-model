#!/usr/bin/env python3
"""test_price_drift_verdict.py -- lock the CLV/price-movement verdict gate.

The money gate is the price-balanced in-band harvest and it must SURVIVE COMMISSION
(roi_morning > 0), not merely post a positive differential over an even-more-negative
band baseline. Proves the gate: (a) PRICED on the observed shape (real but
un-harvestable differential -- negative roi_morning); (b) RULED-IN only when the
in-band harvest actually profits net commission; (c) INCONCLUSIVE if the canary is
unpowered; (d) THIN on a tiny holdout.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_price_drift as pd  # noqa: E402


def _res(nrun, feat_r2, canary_r2, inband_roi, inband_diff, inband_clv):
    def side(roi, diff, clv, r2):
        return {"n_runners": nrun, "feature_resid_r2": r2,
                "inband_steamers": {"n": 20000, "roi_morning": roi,
                                    "differential_edge": diff, "mean_clv": clv}}
    return {
        "holdout": side(inband_roi, inband_diff, inband_clv, feat_r2),
        "discovery": side(inband_roi, inband_diff, inband_clv, feat_r2),
        "canary": {"holdout_resid_r2": canary_r2},
    }


class TestPriceDriftVerdict(unittest.TestCase):
    def test_observed_priced(self):
        # real differential (+2.9%) but roi_morning LOSES and CLV negative -> priced
        r = _res(213103, 0.0119, 0.712, -0.0303, 0.0292, -0.0196)
        v, reason = pd.verdict(r)
        self.assertEqual(v, "priced")
        self.assertIn("NOT harvestable", reason)

    def test_harvestable_rules_in(self):
        # in-band harvest actually profits net commission AND differential clears floor
        r = _res(213103, 0.0119, 0.712, +0.03, 0.03, +0.04)
        v, reason = pd.verdict(r)
        self.assertEqual(v, "ruled-in")
        self.assertIn("harvestable", reason)

    def test_positive_diff_but_still_losing_is_priced(self):
        # differential positive, roi_morning just below zero -> still priced
        r = _res(213103, 0.0119, 0.712, -0.001, 0.02, -0.005)
        self.assertEqual(pd.verdict(r)[0], "priced")

    def test_unpowered_canary_inconclusive(self):
        r = _res(213103, 0.0000, 0.0002, +0.03, 0.03, +0.04)
        v, reason = pd.verdict(r)
        self.assertEqual(v, "inconclusive")
        self.assertIn("POWER CHECK FAILED", reason)

    def test_thin_holdout(self):
        r = _res(500, 0.0119, 0.712, +0.03, 0.03, +0.04)
        self.assertEqual(pd.verdict(r)[0], "thin")


if __name__ == "__main__":
    unittest.main(verbosity=2)
