"""Unit tests for pre-off Gate-2 verdict mechanics (synthetic)."""
import unittest

from backtest import gate_preoff_analysis as a


class TestHelpers(unittest.TestCase):
    def test_ticks_between(self):
        self.assertEqual(a.ticks_between(2.0, 2.02), 1)      # one tick bigger
        self.assertEqual(a.ticks_between(2.0, 1.99), -1)     # one tick shorter
        self.assertEqual(a.ticks_between(3.0, 3.05), 1)
        self.assertEqual(a.ticks_between(2.02, 2.0), -1)
        self.assertIsNone(a.ticks_between(None, 2.0))

    def test_price_band_and_parity(self):
        self.assertEqual(a.price_band(1.5), "1-2")
        self.assertEqual(a.price_band(4.0), "3-5")
        self.assertIn(a.week_parity("2015-06-01"), (0, 1))

    def test_bh_reject(self):
        # classic BH: p=[0.001,0.01,0.2,0.5], alpha .05 -> first two reject
        rej = a.bh_reject([0.001, 0.01, 0.2, 0.5], alpha=0.05)
        self.assertEqual(rej, [True, True, False, False])

    def test_q6_pnl_back(self):
        # back @3.0 hedged by lay @2.9: gross (3.0-2.9)/2.9 ~ 0.03448, minus 2% of it
        pnl = a._q6_pnl(3.0, 2.9, "back")
        self.assertAlmostEqual(pnl, (0.1 / 2.9) * (1 - 0.02), places=5)
        self.assertLess(a._q6_pnl(2.9, 3.0, "back"), 0)      # backed short, hedged long -> loss


class TestQ3CLV(unittest.TestCase):
    def test_clv_and_band_null(self):
        # struck consistently longer than bsp in one band+course -> positive raw CLV,
        # but the band-course null removes the common component -> edge ~ 0.
        recs = []
        for i in range(400):
            d = "2015-07-01" if i % 2 else "2016-02-01"
            recs.append({"date": d, "venue": "Bath", "q3_entry": 3.1, "bsp": 3.0,
                         "field": 8, "dist_f": 5, "is_hcap": False})
        res = a.analyse_q3(recs)
        self.assertGreater(res["holdout"]["raw_clv_mean"], 0)     # struck 3.1 vs bsp 3.0
        self.assertAlmostEqual(res["holdout"]["edge_vs_band_course_null"], 0.0, places=6)
        self.assertEqual(res["verdict"], "FAIL")                 # no edge beyond the null


class TestLogistic(unittest.TestCase):
    def test_separable(self):
        X = [[x, 0, 0] for x in range(-20, 0)] + [[x, 0, 0] for x in range(1, 21)]
        y = [0] * 20 + [1] * 20
        m = a.fit_logistic(X, y, iters=500, lr=0.3)
        p = a.predict_logistic(m, [[-10, 0, 0], [10, 0, 0]])
        self.assertLess(p[0], 0.5)
        self.assertGreater(p[1], 0.5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
