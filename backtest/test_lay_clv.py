"""
test_lay_clv.py -- unit tests pinning the LAY-side CLV harness maths.

Mirror of test_clv.py, for backtest/lay_clv.py. Metric maths are pinned FIRST
(same discipline as day 1) so the Test-4 lay experiment can only ever be as right
as these hand-computed numbers. `won` throughout means THE LAID HORSE WON (the
lay LOST). Stdlib unittest only. Run either of:
    python3 backtest/test_lay_clv.py
    python3 -m unittest backtest.test_lay_clv
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import lay_clv


class TestLayClosingLineValue(unittest.TestCase):
    def test_price_drifted_out(self):
        # Laid at 4.0, market closed at 5.0 -> price drifted +25%: we laid short.
        self.assertAlmostEqual(lay_clv.lay_closing_line_value(4.0, 5.0), 0.25)

    def test_exactly_the_close(self):
        self.assertAlmostEqual(lay_clv.lay_closing_line_value(5.0, 5.0), 0.0)

    def test_price_steamed_in(self):
        # Laid at 5.0 against a 4.0 close -> negative lay-CLV (laid too short).
        self.assertAlmostEqual(lay_clv.lay_closing_line_value(5.0, 4.0), -0.20)

    def test_is_mirror_of_back_clv(self):
        # lay_clv(a,b) and back clv(b,a) [struck/bsp-1] are the same number.
        self.assertAlmostEqual(lay_clv.lay_closing_line_value(4.0, 5.0),
                               5.0 / 4.0 - 1.0)


class TestLayPnlFixedLiability(unittest.TestCase):
    def test_lay_wins_collects_stake_net_commission(self):
        # Horse LOSES -> lay wins the backer's stake s = 1/(5-1) = 0.25, less 5%.
        # payout = 0.25 * 0.95 = 0.2375 per 1 unit of liability.
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_liability(5.0, False, 0.05), 0.2375)

    def test_lay_wins_zero_commission(self):
        # No commission -> full stake s = 1/(5-1) = 0.25.
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_liability(5.0, False, 0.0), 0.25)

    def test_lay_loses_forfeits_fixed_liability(self):
        # Horse WINS -> pay exactly the 1-unit liability, commission irrelevant,
        # and INDEPENDENT of the odds (that's the whole point of fixed liability).
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_liability(5.0, True, 0.05), -1.0)
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_liability(99.0, True, 0.20), -1.0)


class TestLayPnlFixedStake(unittest.TestCase):
    def test_lay_wins_keeps_stake_net_commission(self):
        # Horse LOSES -> keep the 1u stake less 5% = 0.95, independent of odds.
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_stake(5.0, False, 0.05), 0.95)
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_stake(21.0, False, 0.05), 0.95)

    def test_lay_loses_pays_variable_liability(self):
        # Horse WINS -> pay the liability (odds - 1), no commission on a loss.
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_stake(5.0, True, 0.05), -4.0)
        self.assertAlmostEqual(
            lay_clv.lay_bet_pnl_fixed_stake(3.0, True, 0.20), -2.0)


class TestSummariseLay(unittest.TestCase):
    def setUp(self):
        # Two lays, hand-computable:
        #   bet1: struck 4.0, bsp 5.0, horse LOST (won=False -> lay won)
        #         lay-CLV = 5/4 - 1 = +0.25
        #         liab@struck = 0.95/(4-1) = 0.316667 ; liab@bsp = 0.95/(5-1) = 0.2375
        #         stake@struck = +0.95           ; stake@bsp = +0.95
        #   bet2: struck 3.0, bsp 2.0, horse WON (won=True -> lay lost)
        #         lay-CLV = 2/3 - 1 = -0.333333
        #         liab@struck = -1.0             ; liab@bsp = -1.0
        #         stake@struck = -(3-1) = -2.0   ; stake@bsp = -(2-1) = -1.0
        self.bets = [
            {"struck": 4.0, "bsp": 5.0, "won": False},
            {"struck": 3.0, "bsp": 2.0, "won": True},
        ]
        self.s = lay_clv.summarise_lay(self.bets, commission=0.05)

    def test_counts(self):
        self.assertEqual(self.s["n_bets"], 2)
        self.assertEqual(self.s["n_lay_wins"], 1)     # only bet1's horse lost

    def test_lay_clv_metrics(self):
        # mean/median of [+0.25, -0.333333] = -0.041667
        self.assertAlmostEqual(self.s["mean_lay_clv"], -1.0 / 24.0)
        self.assertAlmostEqual(self.s["median_lay_clv"], -1.0 / 24.0)
        # Only bet1's price drifted out.
        self.assertAlmostEqual(self.s["pct_drifted"], 0.5)

    def test_fixed_liability_pnl_and_roi(self):
        pnl = 0.95 / 3.0 - 1.0                        # 0.316667 - 1.0
        self.assertAlmostEqual(self.s["pnl_liab"], pnl)
        self.assertAlmostEqual(self.s["roi_liab"], pnl / 2)
        pnl_bsp = 0.2375 - 1.0
        self.assertAlmostEqual(self.s["pnl_liab_bsp"], pnl_bsp)
        self.assertAlmostEqual(self.s["roi_liab_bsp"], pnl_bsp / 2)

    def test_fixed_stake_pnl_and_roi(self):
        pnl = 0.95 - 2.0
        self.assertAlmostEqual(self.s["pnl_stake"], pnl)
        self.assertAlmostEqual(self.s["roi_stake"], pnl / 2)
        pnl_bsp = 0.95 - 1.0
        self.assertAlmostEqual(self.s["pnl_stake_bsp"], pnl_bsp)
        self.assertAlmostEqual(self.s["roi_stake_bsp"], pnl_bsp / 2)

    def test_commission_does_not_move_lay_clv(self):
        # lay-CLV is a pure price metric: commission must not change it.
        s2 = lay_clv.summarise_lay(self.bets, commission=0.02)
        self.assertAlmostEqual(self.s["mean_lay_clv"], s2["mean_lay_clv"])
        self.assertNotAlmostEqual(self.s["pnl_liab"], s2["pnl_liab"])


class TestLayVsBackDuality(unittest.TestCase):
    """A lay and a back struck at the SAME price on the SAME horse are exact
    P&L opposites BEFORE commission -- the sanity check that the sides mirror."""

    def test_fixed_stake_lay_is_back_negated_ex_commission(self):
        import clv
        # SAME horse, SAME outcome `won`: the backer's P&L is the exact negative
        # of the layer's, before commission. won=True -> back +(o-1), lay -(o-1).
        for struck, won in ((5.0, True), (5.0, False), (12.0, False)):
            back = clv.back_bet_pnl(struck, won, 0.0)
            lay = lay_clv.lay_bet_pnl_fixed_stake(struck, won, 0.0)
            self.assertAlmostEqual(back, -lay)


if __name__ == "__main__":
    unittest.main(verbosity=2)
