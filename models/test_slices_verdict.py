#!/usr/bin/env python3
"""test_slices_verdict.py -- lock the narrow-slice verdict gate.

Proves: (a) PRICED when powered but no probability edge (the observed shape);
(b) INCONCLUSIVE when the rpr canary can't beat the market (underpowered slice);
(c) RULED-IN only with BOTH a Brier edge and an @BSP edge, corroborated; (d) a
small-sample @BSP fluke cannot rule in without the (powered) Brier gate.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import score_slices as ss  # noqa: E402


def _side(nrun, nbets, mkt, blend, canary, roi_edge, roi_se):
    return {"n_races": nbets, "n_runners": nrun,
            "brier_market": mkt, "brier_blend": blend, "brier_canary": canary,
            "blend_bet": {"n_bets": nbets, "edge_vs_strat": roi_edge, "roi_se": roi_se,
                          "roi_bsp": roi_edge, "strat_null_bsp": 0.0}}


def _res(mkt, blend, canary, roi_edge, roi_se, nrun=40000, nbets=4000):
    return {"holdout": _side(nrun, nbets, mkt, blend, canary, roi_edge, roi_se),
            "discovery": _side(nrun * 2, nbets * 2, mkt, blend, canary, roi_edge, roi_se)}


class TestSlicesVerdict(unittest.TestCase):
    def test_observed_priced(self):
        # powered canary, no Brier edge, tiny/negative @BSP edge -> priced
        r = _res(0.08666, 0.08667, 0.01980, roi_edge=0.0048, roi_se=0.0225)
        v, reason = ss.verdict(r)
        self.assertEqual(v, "priced")
        self.assertIn("no probability edge", reason)

    def test_underpowered_inconclusive(self):
        # canary cannot beat market on Brier (margin < 1e-4) -> slice too small to judge
        r = _res(0.097, 0.09703, 0.09695, roi_edge=0.3, roi_se=0.15, nrun=590, nbets=76)
        v, reason = ss.verdict(r)
        self.assertEqual(v, "inconclusive")
        self.assertIn("UNDERPOWERED", reason)

    def test_bigfield_fluke_not_ruled_in(self):
        # huge @BSP edge but NO Brier edge + thin betting -> priced, not ruled-in
        r = _res(0.04717, 0.04720, 0.01474, roi_edge=0.3038, roi_se=0.145,
                 nrun=5328, nbets=280)
        v, reason = ss.verdict(r)
        self.assertEqual(v, "priced")
        self.assertIn("betting channel underpowered", reason)

    def test_real_edge_rules_in(self):
        # Brier edge AND @BSP edge, both on a well-powered slice -> ruled-in
        r = _res(0.0866, 0.0855, 0.0198, roi_edge=0.03, roi_se=0.01)
        v, reason = ss.verdict(r)
        self.assertEqual(v, "ruled-in")
        self.assertIn("real within-slice edge", reason)


if __name__ == "__main__":
    unittest.main(verbosity=2)
