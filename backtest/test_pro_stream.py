"""Unit tests for the PRO stream reader + order-book reconstruction (Gate 1).

Synthetic fixtures only — no real archive touched. Run via ``python run_tests.py``.
"""
import bz2
import io
import json
import os
import tarfile
import tempfile
import unittest

from backtest import pro_stream as ps


# --------------------------------------------------------------------------- #
# Order-book delta reconstruction                                             #
# --------------------------------------------------------------------------- #
class TestRunnerBook(unittest.TestCase):
    def test_atb_add_update_remove_and_best(self):
        b = ps.RunnerBook()
        b.apply_rc({"atb": [[3.0, 100], [3.5, 50], [2.9, 200], [4.0, 10]]})
        # best back = highest prices first, top 3
        self.assertEqual(b.best_back(3), [(4.0, 10), (3.5, 50), (3.0, 100)])
        # update a level, remove another (size 0)
        b.apply_rc({"atb": [[3.5, 25], [4.0, 0]]})
        self.assertEqual(b.best_back(3), [(3.5, 25), (3.0, 100), (2.9, 200)])
        self.assertNotIn(4.0, b.back)

    def test_atl_best_is_lowest(self):
        b = ps.RunnerBook()
        b.apply_rc({"atl": [[4.5, 30], [5.0, 20], [4.2, 40], [6.0, 5]]})
        self.assertEqual(b.best_lay(3), [(4.2, 40), (4.5, 30), (5.0, 20)])

    def test_trd_replace_remove_total(self):
        b = ps.RunnerBook()
        b.apply_rc({"trd": [[3.0, 100], [3.1, 50]]})
        self.assertEqual(b.traded_total(), 150.0)
        b.apply_rc({"trd": [[3.0, 150]]})           # absolute replace, not additive
        self.assertEqual(b.traded_total(), 200.0)
        b.apply_rc({"trd": [[3.1, 0]]})             # remove level
        self.assertEqual(b.traded_total(), 150.0)

    def test_best_back_empty(self):
        self.assertEqual(ps.RunnerBook().best_back(3), [])


# --------------------------------------------------------------------------- #
# Market reconstruction (mcm / img / definition)                              #
# --------------------------------------------------------------------------- #
class TestMarket(unittest.TestCase):
    def test_definition_and_runner_apply(self):
        m = ps.Market()
        m.apply_mcm({"pt": 1000, "mc": [{
            "id": "1.1", "img": True,
            "marketDefinition": {"status": "OPEN", "inPlay": False, "betDelay": 1,
                                 "marketType": "WIN", "eventTypeId": "7"},
            "rc": [{"id": 111, "atb": [[2.0, 500]]}],
        }]})
        self.assertEqual(m.market_id, "1.1")
        self.assertEqual(m.status, "OPEN")
        self.assertFalse(m.inplay)
        self.assertEqual(m.bet_delay, 1)
        self.assertEqual(m.books[111].best_back(1), [(2.0, 500)])

    def test_img_resets_books(self):
        m = ps.Market()
        m.apply_mcm({"pt": 1000, "mc": [{"id": "1.1", "img": True,
                    "rc": [{"id": 111, "atb": [[2.0, 500], [2.1, 100]]}]}]})
        # a later full image with only one level should replace, not merge
        m.apply_mcm({"pt": 2000, "mc": [{"id": "1.1", "img": True,
                    "rc": [{"id": 111, "atb": [[3.0, 10]]}]}]})
        self.assertEqual(m.books[111].best_back(3), [(3.0, 10)])

    def test_inplay_and_status_transition_tracked(self):
        m = ps.Market()
        m.apply_mcm({"pt": 1000, "mc": [{"id": "1.1",
                    "marketDefinition": {"status": "OPEN", "inPlay": False}}]})
        m.apply_mcm({"pt": 1500, "mc": [{"id": "1.1",
                    "marketDefinition": {"status": "SUSPENDED", "inPlay": True}}]})
        self.assertTrue(m.inplay)
        self.assertEqual(m.status, "SUSPENDED")


# --------------------------------------------------------------------------- #
# 1-second sampling                                                            #
# --------------------------------------------------------------------------- #
class TestSampling(unittest.TestCase):
    def _def(self, pt, inplay=False, status="OPEN"):
        return {"pt": pt, "mc": [{"id": "1.1",
                "marketDefinition": {"status": status, "inPlay": inplay},
                "rc": [{"id": 1, "atb": [[2.0, 100]]}]}]}

    def test_cadence_one_hz(self):
        msgs = [self._def(0), self._def(300), self._def(600), self._def(1000),
                self._def(1300), self._def(2000)]
        snaps = list(ps.iter_snapshots(msgs, step_ms=1000))
        pts = [s["pt"] for s in snaps]
        # first (0), then >=1000 since last: 1000, 2000
        self.assertEqual(pts, [0, 1000, 2000])

    def test_inplay_transition_forces_emit(self):
        msgs = [self._def(0, inplay=False),
                self._def(200, inplay=True),      # <1s later but transition
                self._def(400, inplay=True)]
        snaps = list(ps.iter_snapshots(msgs, step_ms=1000))
        pts = [s["pt"] for s in snaps]
        self.assertIn(200, pts)                   # transition captured off-grid
        self.assertTrue(snaps[[s["pt"] for s in snaps].index(200)]["inplay"])

    def test_status_transition_forces_emit(self):
        msgs = [self._def(0, status="OPEN"),
                self._def(100, status="SUSPENDED")]
        pts = [s["pt"] for s in ps.iter_snapshots(msgs, step_ms=1000)]
        self.assertEqual(pts, [0, 100])


# --------------------------------------------------------------------------- #
# Flat / jumps classification + market verdict                                #
# --------------------------------------------------------------------------- #
class TestClassifier(unittest.TestCase):
    def test_flat_names(self):
        for n in ["5f Mdn Stks", "1m App Hcap", "6f Hcap", "7f Cond Stks",
                  "5f Nov Stks", "1m2f Hcap", "2m Hcap", "6f Sell Stks",
                  "1m4f Listed", "7f Grp 3"]:
            self.assertEqual(ps.classify_flat_jumps(n), "flat", n)

    def test_jumps_names(self):
        for n in ["2m Hrd", "2m4f Ch", "2m Nov Ch", "3m1f Hcap Chase",
                  "2m Nov Hrd", "2m NHF", "NH Flat", "2m4f Hunt Ch",
                  "2m Bumper", "2m Hurdle"]:
            self.assertEqual(ps.classify_flat_jumps(n), "jumps", n)

    def test_unclassifiable(self):
        self.assertIsNone(ps.classify_flat_jumps(""))
        self.assertIsNone(ps.classify_flat_jumps(None))

    def test_market_verdict(self):
        courses = {"lingfield", "wolverhampton", "newmarket"}
        base = {"eventTypeId": "7", "marketType": "WIN", "countryCode": "GB",
                "venue": "Lingfield", "name": "5f Mdn Stks"}
        self.assertEqual(ps.market_verdict(base, courses), ("flat", "flat"))
        # AW venue variant still matches the normalised reference
        self.assertEqual(ps.market_verdict({**base, "venue": "Wolverhampton"}, courses),
                         ("flat", "flat"))
        self.assertEqual(ps.market_verdict({**base, "marketType": "SPECIAL"}, courses)[1],
                         "not_win")
        self.assertEqual(ps.market_verdict({**base, "countryCode": "IE"}, courses)[1],
                         "not_gb")
        self.assertEqual(ps.market_verdict({**base, "venue": "Curragh"}, courses)[1],
                         "venue_not_in_gb_ref")
        self.assertEqual(ps.market_verdict({**base, "name": "2m4f Ch"}, courses)[1],
                         "jumps")
        self.assertEqual(ps.market_verdict({**base, "eventTypeId": "4339"}, courses)[1],
                         "not_horse_racing")

    def test_norm_course_strips_qualifier(self):
        self.assertEqual(ps._norm_course("Newmarket (July)"), "newmarket")
        self.assertEqual(ps._norm_course("Wolverhampton (AW)"), "wolverhampton")


# --------------------------------------------------------------------------- #
# Streaming bz2-in-tar (end-to-end round trip, never extracts)                #
# --------------------------------------------------------------------------- #
class TestTarStreaming(unittest.TestCase):
    def _add_bz2(self, tar, arcname, text):
        raw = bz2.compress(text.encode("utf-8"))
        info = tarfile.TarInfo(name=arcname)
        info.size = len(raw)
        tar.addfile(info, io.BytesIO(raw))

    def test_streams_only_market_files(self):
        lines = [
            json.dumps({"pt": 1000, "mc": [{"id": "1.999", "img": True,
                "marketDefinition": {"eventTypeId": "7", "marketType": "WIN",
                                     "countryCode": "GB", "venue": "Lingfield",
                                     "name": "5f Mdn Stks", "status": "OPEN"},
                "rc": [{"id": 5, "atb": [[2.0, 100]]}]}]}),
            json.dumps({"pt": 2100, "mc": [{"id": "1.999",
                "rc": [{"id": 5, "atb": [[2.5, 40]]}]}]}),
        ]
        with tempfile.TemporaryDirectory() as d:
            tp = os.path.join(d, "t.tar")
            with tarfile.open(tp, "w") as tar:
                self._add_bz2(tar, "PRO/2015/Jun/1/27/27.bz2", '{"eventmeta":1}')  # skipped
                self._add_bz2(tar, "PRO/2015/Jun/1/27/1.999.bz2", "\n".join(lines))
            got = list(ps.iter_tar_market_streams([tp]))
        self.assertEqual(len(got), 1)                      # event-meta skipped
        _tp, market_id, msgs = got[0]
        self.assertEqual(market_id, "1.999")
        self.assertEqual(len(msgs), 2)
        md = ps.first_market_definition(msgs)
        self.assertEqual(ps.market_verdict(md, {"lingfield"}), ("flat", "flat"))
        # reconstruct across both messages
        snaps = list(ps.iter_snapshots(iter(msgs), step_ms=1000))
        last = snaps[-1]
        self.assertEqual(last["runners"][5]["back"][0], (2.5, 40))


class TestFillPrimitives(unittest.TestCase):
    def test_ticks_move(self):
        self.assertEqual(ps.ticks_move(2.0, 1), 2.02)     # 2.00 band = 0.02
        self.assertEqual(ps.ticks_move(2.0, -1), 1.99)    # below 2.00 = 0.01
        self.assertEqual(ps.ticks_move(1.99, 1), 2.0)     # cross the band boundary
        self.assertEqual(ps.ticks_move(3.0, 1), 3.05)     # 3.00 band = 0.05
        self.assertEqual(ps.ticks_move(2.0, 0), 2.0)

    def test_matchable_back(self):
        b = ps.RunnerBook()
        b.apply_rc({"atb": [[2.0, 100], [2.02, 50], [1.99, 30]]})
        self.assertEqual(b.matchable_back(2.0, slip_ticks=0), 150.0)   # p>=2.00
        self.assertEqual(b.matchable_back(2.0, slip_ticks=1), 180.0)   # p>=1.99

    def test_matchable_lay(self):
        b = ps.RunnerBook()
        b.apply_rc({"atl": [[2.0, 100], [1.98, 40], [2.02, 20]]})
        self.assertEqual(b.matchable_lay(2.0, slip_ticks=0), 140.0)    # p<=2.00
        self.assertEqual(b.matchable_lay(2.0, slip_ticks=1), 160.0)    # p<=2.02

    def test_traded_at_or_below(self):
        b = ps.RunnerBook()
        b.apply_rc({"trd": [[1.95, 100], [2.0, 50], [2.5, 25]]})
        self.assertEqual(b.traded_at_or_below(2.0), 150.0)

    def test_runner_seeding_from_definition(self):
        m = ps.Market()
        m.apply_mcm({"pt": 1, "mc": [{"id": "1.1", "marketDefinition": {
            "runners": [{"id": 11, "status": "ACTIVE"}, {"id": 22, "status": "ACTIVE"},
                        {"id": 33, "status": "REMOVED"}]}}]})
        self.assertIn(11, m.books)
        self.assertIn(22, m.books)
        self.assertNotIn(33, m.books)          # removed runner not seeded

    def test_peek_market_definition_partial(self):
        lines = [
            json.dumps({"pt": 1, "mc": [{"id": "1.7", "marketDefinition": {
                "eventTypeId": "7", "marketType": "WIN", "countryCode": "GB",
                "venue": "Ascot", "name": "1m Hcap"}}]}),
            json.dumps({"pt": 2, "mc": [{"id": "1.7", "rc": [{"id": 1, "atb": [[2, 5]]}]}]}),
        ]
        raw = bz2.compress(("\n".join(lines)).encode("utf-8"))
        md = ps.peek_market_definition(io.BytesIO(raw))
        self.assertEqual(md["venue"], "Ascot")
        self.assertEqual(ps.market_verdict(md, {"ascot"}), ("flat", "flat"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
