"""Unit tests for Gate-1 liquidity measurement (synthetic fixtures)."""
import unittest

from backtest import gate1_liquidity as g


def _open(pt, betDelay=1, inplay=False, runners=(1,)):
    return {"pt": pt, "mc": [{"id": "1.1", "img": (pt == 0), "marketDefinition": {
        "status": "OPEN", "inPlay": inplay, "betDelay": betDelay,
        "runners": [{"id": r, "status": "ACTIVE"} for r in runners]}}]}


def _rc(pt, sid, atb=None, atl=None, trd=None):
    rc = {"id": sid}
    if atb is not None: rc["atb"] = atb
    if atl is not None: rc["atl"] = atl
    if trd is not None: rc["trd"] = trd
    return {"pt": pt, "mc": [{"id": "1.1", "rc": [rc]}]}


LED_1 = lambda mid, sid: sid == 1


class TestMeasureMarket(unittest.TestCase):
    def test_lay_side_filled_at_t_plus_1s(self):
        msgs = [
            _open(0, betDelay=1, inplay=False),
            _rc(500, 1, trd=[[2.5, 200]]),               # pre-race trade (ignored)
            _open(1000, betDelay=1, inplay=True),         # inplay onset -> baseline
            _rc(1200, 1, atl=[[1.9, 150]]),               # lay liquidity resting
            _rc(1500, 1, trd=[[1.9, 260]]),               # NEW in-running trade <=2.0 -> signal
            _rc(2600, 1, atl=[[1.9, 150]]),               # t >= 1500+1000 -> fulfil here
        ]
        recs = g.measure_market(msgs, LED_1)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertEqual(r["entry_price"], 1.9)
        self.assertEqual(r["signal_pt"], 1500)
        self.assertTrue(r["filled_lay"])              # 150 >= 100
        self.assertFalse(r["filled_back"])            # no back liquidity
        self.assertFalse(r["truncated"])

    def test_bet_delay_2s_moves_fill_window(self):
        msgs = [
            _open(0, betDelay=2, inplay=False),
            _open(1000, betDelay=2, inplay=True),
            _rc(1500, 1, trd=[[1.95, 300]]),          # signal at 1500, deadline 1500+2000=3500
            _rc(3000, 1, atl=[[1.95, 500]]),          # before deadline
            _rc(3600, 1, atl=[[1.95, 40]]),           # >=3500 -> fulfil; lay now only 40
        ]
        recs = g.measure_market(msgs, LED_1)
        self.assertEqual(recs[0]["bet_delay"], 2)
        self.assertFalse(recs[0]["filled_lay"])       # 40 < 100 at t+2s
        self.assertFalse(recs[0]["truncated"])

    def test_non_led_ignored(self):
        msgs = [
            _open(0, inplay=False, runners=(1, 2)),
            _open(1000, inplay=True, runners=(1, 2)),
            _rc(1500, 2, trd=[[1.8, 100]]),           # runner 2 touches <=2.0 but not led
            _rc(2600, 2, atl=[[1.8, 500]]),
        ]
        self.assertEqual(g.measure_market(msgs, LED_1), [])

    def test_preplay_touch_not_a_signal(self):
        msgs = [
            _open(0, inplay=False),
            _rc(500, 1, trd=[[1.9, 400]]),            # traded <=2.0 BEFORE inplay
            _open(1000, inplay=True),                 # baseline captures the 1.9 volume
            _rc(2600, 1, atl=[[1.9, 999]]),           # no NEW <=2.0 trade in running
        ]
        self.assertEqual(g.measure_market(msgs, LED_1), [])

    def test_truncated_when_market_ends_before_fill(self):
        msgs = [
            _open(0, inplay=False),
            _open(1000, inplay=True),
            _rc(1500, 1, trd=[[1.9, 50]]),            # signal, deadline 2500
            _rc(1900, 1, atl=[[1.9, 500]]),           # market ends before 2500
        ]
        recs = g.measure_market(msgs, LED_1)
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["truncated"])
        self.assertFalse(recs[0]["filled_lay"])


class TestSummarise(unittest.TestCase):
    def _rec(self, back, lay):
        return {"filled_back": back, "filled_lay": lay}

    def test_insufficient_n(self):
        s = g.summarise([self._rec(True, True)] * 10)
        self.assertEqual(s["verdict_lay"], "INSUFFICIENT_N")

    def test_pass_fail_threshold(self):
        recs = [self._rec(False, True)] * 1200 + [self._rec(False, False)] * 900
        s = g.summarise(recs)                          # n=2100 >= N_MIN; lay frac ~0.571
        self.assertEqual(s["n_opportunities"], 2100)
        self.assertEqual(s["verdict_lay"], "PASS")     # 0.571 > 0.50
        self.assertEqual(s["verdict_back"], "FAIL")    # 0.0


if __name__ == "__main__":
    unittest.main(verbosity=2)
