#!/usr/bin/env python3
"""test_target_c_verdict.py -- lock the Target-C (best-of-rest) verdict logic.

Proves the verdict can BOTH rule out and rule in, so the observed PRICED result is
a genuine judgment, not a function that always returns priced. Mirrors the hardened
bar: a big @BSP ROI with no MEANINGFUL Brier margin over the market is the
favourite-longshot artifact -> priced; only a real probability edge that also
out-picks the 2nd-favourite, corroborated on discovery, rules in.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_target_c as tc  # noqa: E402


def _part(n, hit_edge, brier_market, brier_blend, model_roi, model_se, strat_edge):
    """Minimal partition dict shaped like partition_metrics()' output."""
    return {
        "n_subraces": n,
        "hit_rate": {"blend_minus_2ndfav": hit_edge},
        "brier": {"market": brier_market, "blend": brier_blend},
        "betting_bsp": {
            "model": {"roi_bsp": model_roi, "roi_se": model_se},
            "blend": {"edge_strat": strat_edge},
        },
    }


class TestTargetCVerdict(unittest.TestCase):
    def test_artifact_shape_is_priced(self):
        """The actual observed shape: negligible Brier margin + fat longshot ROI +
        loses to the 2nd-fav -> priced (the FLB artifact the brief warned about)."""
        disc = _part(57000, -0.0026, 0.09801, 0.09790, +0.0725, 0.03, +0.1185)
        hold = _part(24000, -0.0024, 0.10014, 0.10006, +0.0314, 0.0511, +0.0798)
        v, reason = tc.verdict(disc, hold)
        self.assertEqual(v, "priced")
        self.assertIn("collapses onto the market", reason)

    def test_brier_edge_but_loses_2ndfav_is_priced(self):
        """A real Brier margin that still can't out-pick the 2nd-favourite -> priced
        (the probability edge doesn't translate into beating the market's best guess)."""
        disc = _part(57000, -0.004, 0.100, 0.0990, -0.02, 0.03, -0.01)
        hold = _part(24000, -0.004, 0.100, 0.0990, -0.02, 0.02, -0.01)
        v, reason = tc.verdict(disc, hold)
        self.assertEqual(v, "priced")
        self.assertIn("does NOT beat the", reason)

    def test_thin_holdout(self):
        disc = _part(57000, +0.01, 0.100, 0.0990, +0.01, 0.02, +0.01)
        hold = _part(500, +0.01, 0.100, 0.0990, +0.01, 0.05, +0.01)
        v, _ = tc.verdict(disc, hold)
        self.assertEqual(v, "to-holdout")

    def test_real_edge_rules_in(self):
        """A meaningful Brier margin AND out-picks the 2nd-fav, corroborated on
        discovery -> ruled-in. Proves the gate is not stuck on priced."""
        disc = _part(57000, +0.012, 0.100, 0.0985, +0.03, 0.01, +0.02)
        hold = _part(24000, +0.010, 0.100, 0.0985, +0.03, 0.01, +0.02)
        v, reason = tc.verdict(disc, hold)
        self.assertEqual(v, "ruled-in")
        self.assertIn("real probability edge", reason)

    def test_uncorroborated_is_priced(self):
        """Holdout looks good but discovery doesn't back it -> priced."""
        disc = _part(57000, -0.005, 0.100, 0.1001, +0.0, 0.02, -0.01)  # no disc edge
        hold = _part(24000, +0.010, 0.100, 0.0985, +0.03, 0.01, +0.02)
        v, reason = tc.verdict(disc, hold)
        self.assertEqual(v, "priced")
        self.assertIn("NOT corroborated", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
