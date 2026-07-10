"""Tests pinning the Q1 CLV-validity harness itself (pre-reg §7.5).

Synthetic Betfair-stream fixtures — no tar, no form join — assert that:
  * a no-drift market yields ~zero CLV (the honest baseline; a metric that moves
    when the bets do not is broken);
  * the random control R5 is never awarded a positive CLV on zero-edge data;
  * a synthetic known-edge market (price shortens after a winning entry) is
    detected as positive CLV AND positive realised ROI;
  * the zero-match coverage guard raises (a silent 0-row join must fail loud);
  * Kendall tau is correct on identical / reversed rankings.
"""
import unittest

from backtest import q1_clv_validity as q1


def _md(inplay, status, runners, betDelay=1, venue="Ascot"):
    return {"eventTypeId": "7", "marketType": "WIN", "countryCode": "GB",
            "betDelay": betDelay, "inPlay": inplay, "status": status, "venue": venue,
            "name": "5f Hcap", "runners": runners}


def _active(*sids):
    return [{"id": s, "status": "ACTIVE"} for s in sids]


def no_drift_market(mid="1.ND"):
    """Runner 11 trades <=2.0 in running, price stays flat to the close, 11 wins.
    R1 fires; struck == close so every CLV must be 0."""
    return [
        {"pt": 0, "mc": [{"id": mid, "img": True,
            "marketDefinition": _md(False, "OPEN", _active(11, 12)),
            "rc": [{"id": 11, "atb": [[1.9, 1000], [2.0, 1000]], "atl": [[2.02, 1000]],
                    "trd": [[3.0, 50]], "ltp": 3.0},
                   {"id": 12, "atb": [[3.0, 1000]], "atl": [[3.05, 1000]],
                    "trd": [[3.0, 50]], "ltp": 3.0}]}]},
        {"pt": 1000, "mc": [{"id": mid, "marketDefinition": _md(True, "OPEN", _active(11, 12))}]},
        {"pt": 2000, "mc": [{"id": mid, "rc": [{"id": 11, "trd": [[2.0, 60]], "ltp": 2.0}]}]},
        {"pt": 3000, "mc": [{"id": mid, "rc": [{"id": 11, "ltp": 2.0}]}]},   # t+L fill instant
        {"pt": 33000, "mc": [{"id": mid, "rc": [{"id": 11, "ltp": 2.0}]}]},  # covers t+30s
        {"pt": 40000, "mc": [{"id": mid, "marketDefinition": _md(
            True, "CLOSED",
            [{"id": 11, "status": "WINNER", "bsp": 2.0},
             {"id": 12, "status": "LOSER", "bsp": 3.0}])}]},
    ]


def known_edge_market(mid="1.ED"):
    """Runner 11 enters at 2.0 (struck 2.0) then the price SHORTENS to 1.5 and 11 wins.
    Back CLV = 2.0/1.5 - 1 = +0.333 (positive) and realised ROI is positive too."""
    return [
        {"pt": 0, "mc": [{"id": mid, "img": True,
            "marketDefinition": _md(False, "OPEN", _active(11, 12)),
            "rc": [{"id": 11, "atb": [[1.9, 1000], [2.0, 1000]], "atl": [[2.02, 1000]],
                    "trd": [[3.0, 50]], "ltp": 3.0},
                   {"id": 12, "atb": [[3.0, 1000]], "atl": [[3.05, 1000]],
                    "trd": [[3.0, 50]], "ltp": 3.0}]}]},
        {"pt": 1000, "mc": [{"id": mid, "marketDefinition": _md(True, "OPEN", _active(11, 12))}]},
        {"pt": 2000, "mc": [{"id": mid, "rc": [{"id": 11, "trd": [[2.0, 60]], "ltp": 2.0}]}]},
        {"pt": 3000, "mc": [{"id": mid, "rc": [{"id": 11, "ltp": 2.0}]}]},
        {"pt": 10000, "mc": [{"id": mid, "rc": [{"id": 11, "trd": [[1.5, 80]], "ltp": 1.5}]}]},
        {"pt": 40000, "mc": [{"id": mid, "marketDefinition": _md(
            True, "CLOSED",
            [{"id": 11, "status": "WINNER", "bsp": 1.8},
             {"id": 12, "status": "LOSER", "bsp": 3.0}])}]},
    ]


class NoDriftBaseline(unittest.TestCase):
    def setUp(self):
        self.recs = q1.measure_market(no_drift_market(), is_led=lambda sid: False)
        self.by_rule = {r["rule"]: r for r in self.recs}

    def test_r1_fires_and_fills(self):
        self.assertIn("R1", self.by_rule)
        self.assertTrue(self.by_rule["R1"]["filled"])
        self.assertAlmostEqual(self.by_rule["R1"]["struck"], 2.0, places=6)

    def test_no_drift_gives_zero_clv(self):
        r1 = self.by_rule["R1"]
        for k in ("clv_p1", "clv_p2", "clv_p3"):     # struck==close==2.0 everywhere
            self.assertIsNotNone(r1[k])
            self.assertAlmostEqual(r1[k], 0.0, places=6,
                                   msg=f"{k} moved with no price drift — metric broken")

    def test_r5_control_not_positive_on_zero_edge(self):
        agg = q1.aggregate(self.recs)
        if agg["R5"]["n_filled"]:
            for k in ("P1_clv", "P2_clv"):
                self.assertLessEqual(abs(agg["R5"][k] or 0.0), 1e-6,
                                     msg="R5 awarded non-zero CLV on no-drift data")


class KnownEdgeDetected(unittest.TestCase):
    def test_edge_shows_positive_clv_and_roi(self):
        recs = q1.measure_market(known_edge_market(), is_led=lambda sid: False)
        r1 = next(r for r in recs if r["rule"] == "R1")
        self.assertTrue(r1["filled"])
        self.assertGreater(r1["clv_p1"], 0.2)                 # 2.0/1.5 - 1 = +0.333
        self.assertGreater(r1["g1_pnl"], 0.0)                 # winner backed at 2.0
        self.assertGreater(r1["c1_pnl"], 0.0)                 # hindsight also positive


class CoverageGuard(unittest.TestCase):
    def test_zero_flat_markets_raises(self):
        with self.assertRaises(AssertionError):
            q1.assert_coverage({"flat_markets": 0, "opportunities": 0})

    def test_zero_opportunities_raises(self):
        with self.assertRaises(AssertionError):
            q1.assert_coverage({"flat_markets": 5, "opportunities": 0})

    def test_nonzero_coverage_ok(self):
        q1.assert_coverage({"flat_markets": 5, "opportunities": 20})   # no raise


class KendallTau(unittest.TestCase):
    def test_identical_ranking_tau_one(self):
        order = ["R1", "R2", "R3", "R4", "R5"]
        a = {"R1": 5, "R2": 4, "R3": 3, "R4": 2, "R5": 1}
        self.assertAlmostEqual(q1.kendall_tau(order, a, dict(a)), 1.0, places=6)

    def test_reversed_ranking_tau_minus_one(self):
        order = ["R1", "R2", "R3", "R4", "R5"]
        a = {"R1": 5, "R2": 4, "R3": 3, "R4": 2, "R5": 1}
        b = {"R1": 1, "R2": 2, "R3": 3, "R4": 4, "R5": 5}
        self.assertAlmostEqual(q1.kendall_tau(order, a, b), -1.0, places=6)


class SettlementAndBands(unittest.TestCase):
    def test_settlement_reads_winner_and_bsp(self):
        w, removed, bsp, bd = q1.settlement(no_drift_market())
        self.assertIn(11, w)
        self.assertNotIn(12, w)
        self.assertEqual(bsp[11], 2.0)
        self.assertEqual(bd, 1)

    def test_price_band_edges(self):
        self.assertEqual(q1.price_band(1.4), 0)      # [1.0,1.5)
        self.assertEqual(q1.price_band(2.0), 2)      # [2.0,2.5)
        self.assertIsNone(q1.price_band(1.0))        # unpriced


if __name__ == "__main__":
    unittest.main()
