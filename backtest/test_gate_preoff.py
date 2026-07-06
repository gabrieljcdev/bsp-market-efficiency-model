"""Unit tests for pre-off Gate 1 (Q2/Q3/Q6) on synthetic fixtures."""
import unittest

from backtest import gate_preoff as gp


class TestHelpers(unittest.TestCase):
    def test_off_epoch(self):
        a = gp.off_epoch_ms("2015-06-01T13:00:00.000Z")
        b = gp.off_epoch_ms("2015-06-01T13:00:00Z")
        self.assertEqual(a, b)
        self.assertIsNone(gp.off_epoch_ms(None))

    def test_dist_furlongs(self):
        self.assertEqual(gp.dist_furlongs("5f Mdn Stks"), 5)
        self.assertEqual(gp.dist_furlongs("1m2f Hcap"), 10)
        self.assertEqual(gp.dist_furlongs("1m Hcap"), 8)
        self.assertEqual(gp.dist_furlongs("2m4f Ch"), 20)
        self.assertEqual(gp.dist_furlongs("7f Hcap"), 7)
        self.assertIsNone(gp.dist_furlongs("Irish Derby Winner"))


class TestExtractGate1(unittest.TestCase):
    def _market(self, q6_traded_at_3=1700):
        off = gp.off_epoch_ms("2015-06-01T13:00:00.000Z")
        t30m, t10m = off - 1_800_000, off - 600_000
        md = {"marketTime": "2015-06-01T13:00:00.000Z", "eventTypeId": "7",
              "marketType": "WIN", "countryCode": "GB", "venue": "Bath",
              "name": "5f Hcap", "numberOfActiveRunners": 8,
              "runners": [{"id": 1, "status": "ACTIVE"}]}
        return off, [
            {"pt": t30m, "mc": [{"id": "1.1", "img": True, "marketDefinition": md,
                "rc": [{"id": 1, "atb": [[3.0, 500], [2.9, 200], [2.8, 150]],
                        "atl": [[3.1, 300]], "trd": [[3.0, 1000]]}]}]},
            {"pt": t10m, "mc": [{"id": "1.1",
                "rc": [{"id": 1, "atb": [[3.0, 600]], "trd": [[3.0, q6_traded_at_3]]}]}]},
            {"pt": off, "mc": [{"id": "1.1", "marketDefinition": {**md, "inPlay": True}}]},
        ], md

    def test_q2_q3_fill_and_q6_fill(self):
        off, msgs, md = self._market(q6_traded_at_3=1700)   # traded 700 > queue 500 + 100
        recs = gp.extract_preoff_gate1(msgs, md)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertTrue(r["q2_fill"])              # 600 available at best-back 3.0
        self.assertTrue(r["q3_fill"])              # 3rd-best-back 2.8 present, depth ok
        self.assertEqual(r["third_back_t10"], 2.8)
        self.assertTrue(r["q6_posted"])
        self.assertTrue(r["q6_back_fill"])         # 700 traded > 500 queue + 100
        self.assertEqual(r["dist_f"], 5)
        self.assertTrue(r["is_hcap"])

    def test_q6_not_filled_when_thin_trading(self):
        off, msgs, md = self._market(q6_traded_at_3=1400)   # traded 400 < queue 500 + 100
        r = gp.extract_preoff_gate1(msgs, md)[0]
        self.assertTrue(r["q6_posted"])
        self.assertFalse(r["q6_back_fill"])

    def test_no_records_if_no_t10min(self):
        off = gp.off_epoch_ms("2015-06-01T13:00:00.000Z")
        md = {"marketTime": "2015-06-01T13:00:00.000Z", "venue": "Bath", "name": "5f Hcap",
              "runners": [{"id": 1, "status": "ACTIVE"}]}
        # only a snapshot 5s before off -> never reaches T-10min pre-off
        msgs = [{"pt": off - 5000, "mc": [{"id": "1.1", "img": True, "marketDefinition": md,
                 "rc": [{"id": 1, "atb": [[3.0, 100]]}]}]},
                {"pt": off, "mc": [{"id": "1.1", "marketDefinition": {**md, "inPlay": True}}]}]
        self.assertEqual(gp.extract_preoff_gate1(msgs, md), [])

    def test_summarise_verdicts(self):
        recs = ([{"q2_fill": True, "q3_fill": True, "q6_posted": True,
                  "q6_back_fill": False, "q6_lay_fill": False}] * 900 +
                [{"q2_fill": False, "q3_fill": False, "q6_posted": True,
                  "q6_back_fill": True, "q6_lay_fill": False}] * 100)
        s = gp.summarise_gate1(recs)
        self.assertEqual(s["Q2_liquidity"]["verdict"], "PASS")   # 0.90 > 0.50
        self.assertEqual(s["Q6_fill_rate"]["rate"], 0.10)        # 100/1000
        self.assertEqual(s["Q6_fill_rate"]["verdict"], "PASS")   # 0.10 >= 0.10


if __name__ == "__main__":
    unittest.main(verbosity=2)
