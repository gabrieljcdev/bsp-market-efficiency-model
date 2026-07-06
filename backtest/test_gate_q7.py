"""Unit tests for Q7 (non-runner repricing latency), Gate 1, on synthetic fixtures."""
import unittest

from backtest import gate_q7_nonrunner as q7
from backtest.gate_preoff import off_epoch_ms


class TestBenchmarkMaths(unittest.TestCase):
    def test_fair_price_probability_renorm(self):
        # remove a 20% runner -> survivors' prices scale down by (1-0.20)
        self.assertAlmostEqual(q7.fair_price(4.0, 0.20), 3.2)
        self.assertAlmostEqual(q7.fair_price(10.0, 0.10), 9.0)

    def test_fair_price_matched_crosscheck(self):
        # Betfair matched-bet reduction 1 + (P-1)(1-A); diverges from renorm at short prices
        self.assertAlmostEqual(q7.fair_price_matched(4.0, 0.20), 3.4)   # vs 3.2 renorm
        self.assertAlmostEqual(q7.fair_price_matched(2.0, 0.10), 1.9)   # vs 1.8 renorm

    def test_stale_back_size_two_ticks_out(self):
        # fair 3.2; 2 ticks longer = 3.30 (band 3-4 -> 0.05 inc). Back offers at >=3.30 count.
        back = {4.0: 100.0, 3.9: 80.0, 3.25: 40.0}     # 3.25 is < 3.30 -> excluded
        self.assertAlmostEqual(q7.stale_back_size(back, 3.2), 180.0)

    def test_stale_lay_size_two_ticks_in(self):
        # fair 3.2; 2 ticks shorter = 3.10. Lay offers at <=3.10 count (too-short lay).
        lay = {3.1: 100.0, 3.15: 50.0}                 # 3.15 > 3.10 -> excluded
        self.assertAlmostEqual(q7.stale_lay_size(lay, 3.2), 100.0)


class TestExtractQ7(unittest.TestCase):
    OFF = "2015-06-01T13:00:00.000Z"

    def _md(self, **kw):
        base = {"marketTime": self.OFF, "eventTypeId": "7", "marketType": "WIN",
                "countryCode": "GB", "venue": "Bath", "name": "5f Hcap",
                "numberOfActiveRunners": 3, "marketId": "1.99"}
        base.update(kw)
        return base

    def _seed(self):
        off = off_epoch_ms(self.OFF)
        t = off - 300_000                    # removal 5 min before off (pre-off)
        md_open = self._md(runners=[{"id": 1, "status": "ACTIVE"},
                                    {"id": 2, "status": "ACTIVE"},
                                    {"id": 3, "status": "ACTIVE"}])
        seed = {"pt": off - 600_000, "mc": [{"id": "1.99", "img": True,
                "marketDefinition": md_open,
                "rc": [{"id": 1, "atb": [[4.0, 100], [3.9, 80]], "atl": [[4.1, 90]]},
                       {"id": 2, "atb": [[3.0, 100]], "atl": [[3.1, 100]]},
                       {"id": 3, "atb": [[6.0, 100]], "atl": [[6.2, 100]]}]}]}
        return off, t, md_open, seed

    def test_fillable_when_ladder_does_not_repopulate(self):
        off, t, md_open, seed = self._seed()
        # removal of runner 3 (AF 20%), market stays OPEN, survivors' stale offers left intact
        md_rm = self._md(runners=[{"id": 1, "status": "ACTIVE"},
                                  {"id": 2, "status": "ACTIVE"},
                                  {"id": 3, "status": "REMOVED", "adjustmentFactor": 20.0}],
                         status="OPEN")
        msgs = [seed,
                {"pt": t, "mc": [{"id": "1.99", "marketDefinition": md_rm,
                                  "rc": [{"id": 3, "atb": [[6.0, 0]], "atl": [[6.2, 0]]}]}]},
                {"pt": off, "mc": [{"id": "1.99",
                                    "marketDefinition": self._md(inPlay=True)}]}]
        recs = q7.extract_q7(msgs, md_open)
        self.assertEqual(len(recs), 1)
        r = recs[0]
        self.assertAlmostEqual(r["A"], 0.20)
        self.assertEqual(r["n_removed"], 1)
        self.assertFalse(r["suspended"])
        self.assertTrue(r["fillable"])              # 180 available to back @>=3.30 (fair 3.2)
        self.assertEqual(r["best_opp_side"], "back")
        self.assertGreaterEqual(r["best_opp_gbp"], 50.0)

    def test_suspend_and_wipe_kills_the_opportunity(self):
        off, t, md_open, seed = self._seed()
        md_rm = self._md(runners=[{"id": 1, "status": "ACTIVE"},
                                  {"id": 2, "status": "ACTIVE"},
                                  {"id": 3, "status": "REMOVED", "adjustmentFactor": 20.0}],
                         status="SUSPENDED")
        # on removal: suspend + wipe ALL unmatched (sizes -> 0); reopen thin at fair much later
        wipe = [{"id": 1, "atb": [[4.0, 0], [3.9, 0]], "atl": [[4.1, 0]]},
                {"id": 2, "atb": [[3.0, 0]], "atl": [[3.1, 0]]},
                {"id": 3, "atb": [[6.0, 0]], "atl": [[6.2, 0]]}]
        md_reopen = self._md(runners=[{"id": 1, "status": "ACTIVE"},
                                      {"id": 2, "status": "ACTIVE"},
                                      {"id": 3, "status": "REMOVED", "adjustmentFactor": 20.0}],
                             status="OPEN")
        msgs = [seed,
                {"pt": t, "mc": [{"id": "1.99", "marketDefinition": md_rm, "rc": wipe}]},
                {"pt": t + 120_000, "mc": [{"id": "1.99", "marketDefinition": md_reopen,
                    "rc": [{"id": 1, "atb": [[3.2, 20]]}, {"id": 2, "atb": [[2.4, 20]]}]}]},
                {"pt": off, "mc": [{"id": "1.99",
                                    "marketDefinition": self._md(inPlay=True)}]}]
        r = q7.extract_q7(msgs, md_open)[0]
        self.assertTrue(r["suspended"])
        self.assertLessEqual(r["wipe_ratio"], 0.10)     # book gone at t+1s
        self.assertFalse(r["fillable"])                 # nothing >= £50 to hit
        self.assertEqual(r["best_opp_gbp"], 0.0)

    def test_sub_threshold_af_is_ignored(self):
        off, t, md_open, seed = self._seed()
        md_rm = self._md(runners=[{"id": 1, "status": "ACTIVE"},
                                  {"id": 2, "status": "ACTIVE"},
                                  {"id": 3, "status": "REMOVED", "adjustmentFactor": 1.0}],
                         status="OPEN")   # AF 1% < 2.5% -> not applied, no event
        msgs = [seed,
                {"pt": t, "mc": [{"id": "1.99", "marketDefinition": md_rm,
                                  "rc": [{"id": 3, "atb": [[6.0, 0]]}]}]},
                {"pt": off, "mc": [{"id": "1.99",
                                    "marketDefinition": self._md(inPlay=True)}]}]
        self.assertEqual(q7.extract_q7(msgs, md_open), [])

    def test_inplay_removal_excluded(self):
        off, t, md_open, seed = self._seed()
        md_rm = self._md(runners=[{"id": 3, "status": "REMOVED", "adjustmentFactor": 20.0}],
                         inPlay=True, status="OPEN")
        msgs = [seed,
                {"pt": off + 60_000, "mc": [{"id": "1.99", "marketDefinition": md_rm}]}]
        self.assertEqual(q7.extract_q7(msgs, md_open), [])


class TestSummary(unittest.TestCase):
    def _rec(self, fillable, suspended=True, wipe=0.0, dur=2, repop=None):
        return {"date": "2015-06-01", "af_pct": 5.0, "suspended": suspended,
                "susp_dur_s": dur, "susp_censored": False, "wipe_ratio": wipe,
                "repop_k_s": repop, "fillable": fillable, "fillable_matched": fillable,
                "best_opp_gbp": 60.0 if fillable else 0.0}

    def test_fail_below_10pct(self):
        recs = [self._rec(False)] * 95 + [self._rec(True)] * 5     # 5% fillable
        s = q7.summarise_q7_gate1(recs, n_racedays=50)
        self.assertEqual(s["fillability"]["verdict"], "FAIL")
        self.assertEqual(s["verdict"], "FAIL")
        self.assertEqual(s["suspend_fraction"], 1.0)

    def test_pass_at_or_above_10pct(self):
        recs = [self._rec(False)] * 88 + [self._rec(True)] * 12    # 12% fillable
        s = q7.summarise_q7_gate1(recs, n_racedays=50)
        self.assertEqual(s["fillability"]["verdict"], "PASS")
        self.assertEqual(s["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main(verbosity=2)
