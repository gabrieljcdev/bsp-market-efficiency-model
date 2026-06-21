"""
test_clv.py -- quick unit tests for the CLV harness metric functions.

Stdlib unittest only (no pytest needed). Run either of:
    python3 backtest/test_clv.py
    python3 -m unittest backtest.test_clv
"""
import os
import sys
import unittest

# Make `import clv` work regardless of the working directory.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import clv


class TestClosingLineValue(unittest.TestCase):
    def test_beat_the_close(self):
        # Struck 6.0, market closed at 5.0 -> we took 20% bigger odds.
        self.assertAlmostEqual(clv.closing_line_value(6.0, 5.0), 0.20)

    def test_exactly_the_close(self):
        self.assertAlmostEqual(clv.closing_line_value(5.0, 5.0), 0.0)

    def test_worse_than_close(self):
        # Struck 4.0 against a 5.0 close -> negative CLV.
        self.assertAlmostEqual(clv.closing_line_value(4.0, 5.0), -0.20)


class TestBackBetPnl(unittest.TestCase):
    def test_win_nets_commission_on_winnings(self):
        # 1u back at 5.0 wins -> 4u profit, less 5% commission = 3.8u.
        self.assertAlmostEqual(clv.back_bet_pnl(5.0, True, 0.05), 3.8)

    def test_win_zero_commission(self):
        # No commission -> full (odds - 1) profit.
        self.assertAlmostEqual(clv.back_bet_pnl(5.0, True, 0.0), 4.0)

    def test_loss_forfeits_stake_no_commission(self):
        # A loser always costs exactly the 1u stake, commission irrelevant.
        self.assertAlmostEqual(clv.back_bet_pnl(5.0, False, 0.05), -1.0)
        self.assertAlmostEqual(clv.back_bet_pnl(99.0, False, 0.20), -1.0)


class TestSummarise(unittest.TestCase):
    def setUp(self):
        # Two bets, hand-computable:
        #   bet1: struck 6.0, bsp 5.0, WON  -> CLV +0.20
        #         pnl@struck = (6-1)*0.95 = 4.75 ; pnl@bsp = (5-1)*0.95 = 3.80
        #   bet2: struck 3.0, bsp 4.0, LOST -> CLV -0.25
        #         pnl@struck = -1.0 ; pnl@bsp = -1.0
        self.bets = [
            {"struck": 6.0, "bsp": 5.0, "won": True},
            {"struck": 3.0, "bsp": 4.0, "won": False},
        ]
        self.s = clv.summarise(self.bets, commission=0.05)

    def test_counts(self):
        self.assertEqual(self.s["n_bets"], 2)
        self.assertEqual(self.s["n_winners"], 1)

    def test_clv_metrics(self):
        # mean/median of [+0.20, -0.25] = -0.025
        self.assertAlmostEqual(self.s["mean_clv"], -0.025)
        self.assertAlmostEqual(self.s["median_clv"], -0.025)
        # Only bet1 was struck above its close.
        self.assertAlmostEqual(self.s["pct_beating_bsp"], 0.5)

    def test_realised_pnl_and_roi(self):
        # struck: 4.75 - 1.0 = 3.75 ; bsp: 3.80 - 1.0 = 2.80
        self.assertAlmostEqual(self.s["pnl_struck"], 3.75)
        self.assertAlmostEqual(self.s["pnl_bsp"], 2.80)
        self.assertAlmostEqual(self.s["roi_struck"], 3.75 / 2)
        self.assertAlmostEqual(self.s["roi_bsp"], 2.80 / 2)

    def test_commission_does_not_move_clv(self):
        # CLV is a pure price metric: changing commission must not change it.
        s2 = clv.summarise(self.bets, commission=0.02)
        self.assertAlmostEqual(self.s["mean_clv"], s2["mean_clv"])
        self.assertNotAlmostEqual(self.s["pnl_struck"], s2["pnl_struck"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
