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


def _lay(h_rows, bsp_ctx, morn=37.0, p90=1270.0, mx=19980.0):
    """h_rows: list of (h, picks_roi, layall_roi). Builds a lay_gate2-shaped dict."""
    hc = {}
    for h, pr, al in h_rows:
        hc[f"{h:.3f}"] = {"h": h, "lay_picks_roi": pr, "lay_all_roi": al,
                          "edge_over_layall": pr - al, "lay_picks_se": 0.031}
    return {"haircuts": hc, "lay_at_bsp_roi_context": bsp_ctx,
            "liability_gbp_per_trade": {"p90": p90, "max": mx, "mean_morning_price": morn}}


class TestLayGate2Verdict(unittest.TestCase):
    # observed shape: clears the h=0 null and survives a flat 5% haircut, BUT the
    # quotable-close (BSP) edge is ~0 -> the morning edge is the unquotable WAP.
    OBS = [(0.0, 0.0939, 0.0444), (0.025, 0.0717, 0.0209),
           (0.05, 0.0495, -0.0025), (0.10, 0.0051, -0.0494)]

    def test_observed_is_artifact_via_close(self):
        v, reason = pd.verdict_lay(_lay(self.OBS, bsp_ctx=0.0082))
        self.assertEqual(v, "ARTIFACT")
        self.assertIn("quotable CLOSE", reason)

    def test_no_edge_at_zero_is_priced(self):
        rows = [(0.0, -0.01, 0.02), (0.025, -0.02, 0.0), (0.05, -0.03, -0.02),
                (0.10, -0.05, -0.05)]
        self.assertEqual(pd.verdict_lay(_lay(rows, bsp_ctx=-0.01))[0], "PRICED")

    def test_flat_haircut_kill_is_artifact(self):
        # absolute picks ROI dies by 5% even though the close looks ok
        rows = [(0.0, 0.03, 0.005), (0.025, 0.01, -0.01), (0.05, -0.01, -0.03),
                (0.10, -0.05, -0.07)]
        self.assertEqual(pd.verdict_lay(_lay(rows, bsp_ctx=0.03))[0], "ARTIFACT")

    def test_genuine_edge_is_harvestable(self):
        # survives 5% on absolute ROI, close (BSP) still pays, lay-ALL base not a
        # positive-then-dying WAP signature -> the only HARVESTABLE path.
        rows = [(0.0, 0.06, -0.02), (0.025, 0.055, -0.02), (0.05, 0.05, -0.02),
                (0.10, 0.045, -0.02)]
        v, reason = pd.verdict_lay(_lay(rows, bsp_ctx=0.04))
        self.assertEqual(v, "HARVESTABLE")


if __name__ == "__main__":
    unittest.main(verbosity=2)
