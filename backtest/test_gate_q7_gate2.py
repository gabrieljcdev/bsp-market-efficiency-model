"""Unit tests for Q7 Gate 2: the trade P&L money model, entry/exit fills, and the
band×tto-matched null verdict on discovery/holdout + odd/even-week parity splits."""
import unittest

from backtest import gate_q7_gate2 as g2


class TestTradePnl(unittest.TestCase):
    def test_back_profits_when_price_shortens(self):
        # back £50 @4.0, close (lay) @2.0 -> gross 50*(4-2)/2 = +50, net 2% -> 49.0
        self.assertAlmostEqual(g2.trade_pnl("back", 4.0, 2.0, 50.0), 49.0)

    def test_back_loses_when_price_drifts(self):
        # back £50 @2.0 close @4.0 -> gross -25, no commission on a loss
        self.assertAlmostEqual(g2.trade_pnl("back", 2.0, 4.0, 50.0), -25.0)

    def test_lay_profits_when_price_drifts(self):
        # lay £50 @2.0 close (back) @4.0 -> +25 gross, net 2% -> 24.5
        self.assertAlmostEqual(g2.trade_pnl("lay", 2.0, 4.0, 50.0), 24.5)

    def test_lay_loses_when_price_shortens(self):
        self.assertAlmostEqual(g2.trade_pnl("lay", 4.0, 2.0, 50.0), -50.0)

    def test_no_exit_is_flat(self):
        self.assertEqual(g2.trade_pnl("back", 4.0, None, 50.0), 0.0)


class TestFills(unittest.TestCase):
    def test_take_back_only_stale_rungs(self):
        # fair 3.2 -> stale-back threshold 3.30; only >=3.30 rungs are takeable, best first
        matched, px = g2._take_back({4.0: 100, 3.9: 30, 3.25: 200}, 3.2, 50.0)
        self.assertEqual(matched, 50.0)
        self.assertAlmostEqual(px, 4.0)         # filled from the £100 @4.0 rung

    def test_take_lay_only_stale_rungs(self):
        # fair 3.2 -> stale-lay threshold 3.10; only <=3.10 counts
        matched, px = g2._take_lay({3.1: 100, 3.15: 200}, 3.2, 50.0)
        self.assertEqual(matched, 50.0)
        self.assertAlmostEqual(px, 3.1)

    def test_no_stale_liquidity(self):
        self.assertEqual(g2._take_back({3.2: 500}, 3.2, 50.0), (0.0, None))


class TestVerdict(unittest.TestCase):
    def _t(self, date, parity, roi, kind):
        return {"date": date, "parity": parity, "entry_band": 2, "tto_s": 100.0,
                "pnl_per_pound": roi, "kind": kind, "matched": 50.0}

    def _book(self, nr_roi, ctrl_roi):
        nr, ctrl = [], []
        for date in ("2016-02-01", "2015-08-01"):        # holdout, discovery
            for parity in (0, 1):
                for _ in range(15):
                    nr.append(self._t(date, parity, nr_roi, "nr"))
                    ctrl.append(self._t(date, parity, ctrl_roi, "ctrl"))
        return nr, ctrl

    def test_ruled_in_when_nr_beats_null_on_all_splits(self):
        nr, ctrl = self._book(nr_roi=0.10, ctrl_roi=0.0)
        v = g2.verdict_gate2(nr, ctrl)
        self.assertEqual(v["verdict"], "RULED-IN")
        self.assertGreater(v["holdout"]["matched_edge_per_pound"], 0)

    def test_priced_when_nr_equals_null(self):
        nr, ctrl = self._book(nr_roi=0.05, ctrl_roi=0.05)
        v = g2.verdict_gate2(nr, ctrl)
        self.assertEqual(v["verdict"], "PRICED")

    def test_priced_when_null_beats_nr(self):
        nr, ctrl = self._book(nr_roi=0.0, ctrl_roi=0.05)
        v = g2.verdict_gate2(nr, ctrl)
        self.assertEqual(v["verdict"], "PRICED")

    def test_thin_when_few_holdout_trades(self):
        nr = [self._t("2016-02-01", 0, 0.1, "nr") for _ in range(10)]
        ctrl = [self._t("2016-02-01", 0, 0.0, "ctrl") for _ in range(10)]
        self.assertEqual(g2.verdict_gate2(nr, ctrl)["verdict"], "THIN")

    def test_helpers(self):
        self.assertEqual(g2._price_band(3.5), 2)          # [3,4)
        self.assertEqual(g2._tto_bucket(100), 0)          # [0,120)
        self.assertEqual(g2._tto_bucket(400), 2)          # [300,600)
        self.assertIn(g2._week_parity("2016-02-01"), (0, 1))


if __name__ == "__main__":
    unittest.main(verbosity=2)
