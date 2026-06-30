"""
test_verdict.py -- regression tests for the HARDENED verdict baseline.

Two holes used to let a no-skill, favourite-skewed selection read RULED-IN:

  1. The composition-fair null de-overrounds the field by a single per-race
     factor (p_i = (1/bsp_i)/Z). That strips the overround LEVEL but not the
     favourite-longshot price composition: short prices return MORE @BSP than
     their de-overrounded implied prob, so a rule that merely skews toward
     favourites beats the fair null for free. The fix benchmarks each selected
     horse against the full field's actual back-all@BSP return IN ITS OWN BSP
     BAND (run_strategy._price_band) -- price composition matched, edge -> ~0.

  2. Even a positive edge_bsp can be a CLV-relative artifact with no forecasting
     skill behind it. The Brier-corroboration gate requires the blend to beat
     BSP on Brier over the selection's own horses before anything reads ruled-in.

Test A drives the FULL pipeline on a synthetic, FLB-biased fixture where the
market is efficient (no harvestable skill): the OLD fair-null edge is large and
positive (the hole), the NEW price-band-stratified edge collapses to ~0, and the
verdict is PRICED -- even though the blend (monkeypatched) WOULD pass the Brier
gate, proving the composition fix alone blocks the false rule-in.

Test B unit-tests run_strategy._verdict: with the edge clearing the floor and
discovery corroborating, the Brier gate alone decides ruled-in vs priced.

Stdlib unittest only. Discovered by run_tests.py (which scans backtest/).
    python3 run_tests.py
    python3 -m unittest backtest.test_verdict
"""
import csv
import os
import sys
import tempfile
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "racing_rulebuilder"))
import run_strategy as rs          # noqa: E402


# --------------------------------------------------------------------------- #
# Synthetic fixture: an EFFICIENT market with a favourite-longshot bias.       #
#                                                                             #
# Each race = 1 favourite @ BSP 2.0 + 4 longshots @ BSP 6.0 (overround                                                                         #
# Z = 1/2 + 4/6 = 1.167). The favourite wins at EXACTLY its raw implied rate   #
# 1/2; the four longshots split the rest, so each wins 1/8 < raw implied 1/6   #
# (the FLB). Backing the favourite returns only -commission (-2.5%) -- no edge #
# -- yet the de-overrounded fair-null assigns it prob 0.4286 < 0.5, so it      #
# UNDER-prices the favourite and a favourites-only rule "beats" it by ~+14%.   #
# --------------------------------------------------------------------------- #
FAV_BSP = 2.0
LONG_BSP = 6.0
N_LONGSHOTS = 4
RACES_PER_PART = 3000          # holdout favourites = 3000 >= THIN_HOLDOUT_N


def _write_fixture(path):
    """Favourites carry sel=1 (the selection), longshots sel=0. The favourite
    wins exactly half the races in each partition; the rest go round-robin to the
    longshots. Discovery dates <= cutoff, holdout dates > cutoff."""
    cols = ["race_id", "date", "course", "off", "horse", "type",
            "bsp", "wap", "won", "sel"]
    with open(path, "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for part, date in (("d", "2024-01-01"), ("h", "2025-01-01")):
            for i in range(RACES_PER_PART):
                rid = f"{part}{i}"
                fav_wins = (i % 2 == 0)                 # favourite wins exactly half
                long_winner = (i // 2) % N_LONGSHOTS    # round-robin the rest
                w.writerow({"race_id": rid, "date": date, "course": "Synth",
                            "off": "13:00", "horse": f"{rid}_fav", "type": "Flat",
                            "bsp": FAV_BSP, "wap": FAV_BSP,
                            "won": 1 if fav_wins else 0, "sel": 1})
                for k in range(N_LONGSHOTS):
                    win = (not fav_wins) and (k == long_winner)
                    w.writerow({"race_id": rid, "date": date,
                                "course": "Synth", "off": "13:00",
                                "horse": f"{rid}_l{k}", "type": "Flat",
                                "bsp": LONG_BSP, "wap": LONG_BSP,
                                "won": 1 if win else 0, "sel": 0})


def _perfect_blend_map(path):
    """A blend that forecasts PERFECTLY (Brier 0) -> always beats BSP. Used so
    Test A's PRICED verdict can only come from the stratified null, never the
    Brier gate. Keyed (race_id, horse) -> (blend_prob, bsp_implied_prob, won)."""
    m = {}
    with open(path, newline="") as fh:
        for r in csv.DictReader(fh):
            won = 1.0 if r["won"] == "1" else 0.0
            bsp = float(r["bsp"])
            m[(r["race_id"], r["horse"])] = (won, 1.0 / bsp, won)
    return m


class TestStratifiedNullClosesFLBHole(unittest.TestCase):
    """Test A -- the favourite-longshot composition hole is closed."""

    def setUp(self):
        # Keep the fixture on the SAME mount as the repo: run_strategy calls
        # os.path.relpath(src, _ROOT), which raises across drives on Windows.
        self.tmp = tempfile.mkdtemp(dir=_ROOT)
        self.csv = os.path.join(self.tmp, "synth.csv")
        _write_fixture(self.csv)
        # Monkeypatch the blend map to a PERFECT forecaster so the Brier gate
        # would PASS -- isolating the stratified null as the only thing that can
        # block ruled-in. Save/restore the memo so other tests are unaffected.
        self._saved = (rs._BLEND_MAP, rs._BLEND_MAP_LOADED)
        rs._BLEND_MAP = _perfect_blend_map(self.csv)
        rs._BLEND_MAP_LOADED = True

    def tearDown(self):
        rs._BLEND_MAP, rs._BLEND_MAP_LOADED = self._saved
        for f in os.listdir(self.tmp):
            os.remove(os.path.join(self.tmp, f))
        os.rmdir(self.tmp)

    def _run(self):
        return rs.run_strategy({
            "source_csv": self.csv,
            "split": {"mode": "date", "date_cutoff": "2024-06-30"},
            "selection_rules": {"combinator": "all", "children": [
                {"field": "sel", "op": "==", "value": 1,
                 "type": "numeric", "coerce": True}]},
        }, mode="backtest")

    def test_favourite_skew_does_not_rule_in(self):
        res = self._run()
        self.assertTrue(res["ok"], res.get("errors"))
        hold = res["holdout"]

        # The selection is genuinely no-skill: backing favourites @BSP just pays
        # the commission drag (~ -2.5%), it does not profit.
        self.assertLess(hold["clv"]["roi_bsp"], 0.0)

        # THE HOLE: the old composition-fair null would have shown a large
        # positive edge purely from the favourite skew (would falsely rule in).
        self.assertGreater(hold["edge_bsp_fair"], 0.05)

        # THE FIX: the price-band-stratified null matches the selection to the
        # full field's @BSP return in its own price band -> edge collapses to ~0.
        self.assertLessEqual(hold["edge_bsp_strat"], rs.EDGE_TOL)
        self.assertAlmostEqual(hold["edge_bsp_strat"], 0.0, places=4)

        # The blend (monkeypatched) DOES beat BSP here, so the Brier gate is NOT
        # what blocks the rule-in -- the stratified null is.
        self.assertTrue(hold["brier"]["blend_beats_bsp"])

        # End to end: a favourite-skewed no-skill selection must NOT rule in.
        self.assertNotEqual(res["verdict"], "ruled-in")
        self.assertEqual(res["verdict"], "priced")


class TestBrierGate(unittest.TestCase):
    """Test B -- with the edge clearing the floor AND discovery corroborating,
    the Brier-corroboration gate alone decides ruled-in vs priced."""

    def _verdict(self, blend_brier=None, bsp_brier=None, coverage=1.0,
                 brier=True, he=0.03, de=0.03, hn=5000):
        br = None
        if brier:
            bb = 0.080 if blend_brier is None else blend_brier
            sb = 0.085 if bsp_brier is None else bsp_brier
            br = {"n": int(hn * coverage), "coverage": coverage,
                  "blend_brier": bb, "bsp_brier": sb,
                  "blend_beats_bsp": bb < sb,
                  "sufficient": coverage >= rs.MIN_BRIER_COVERAGE}
        hold = {"edge_bsp": he, "scored_bets": hn, "brier": br}
        disc = {"edge_bsp": de}
        return rs._verdict(disc, hold)

    def test_ruled_in_when_blend_beats_bsp(self):
        v, _ = self._verdict(blend_brier=0.080, bsp_brier=0.085)
        self.assertEqual(v, "ruled-in")

    def test_priced_when_blend_does_not_beat_bsp(self):
        # The trainer_course_sr case: edge holds, but blend Brier >= BSP Brier.
        v, reason = self._verdict(blend_brier=0.122, bsp_brier=0.121)
        self.assertEqual(v, "priced")
        self.assertIn("probability edge", reason)

    def test_priced_when_blend_coverage_too_thin(self):
        v, reason = self._verdict(blend_brier=0.080, bsp_brier=0.085,
                                  coverage=0.10)
        self.assertEqual(v, "priced")

    def test_priced_when_no_blend_file(self):
        v, _ = self._verdict(brier=False)
        self.assertEqual(v, "priced")

    def test_edge_below_floor_is_priced_regardless(self):
        v, _ = self._verdict(blend_brier=0.080, bsp_brier=0.085, he=0.005)
        self.assertEqual(v, "priced")

    def test_thin_holdout_not_ruled_in(self):
        v, _ = self._verdict(blend_brier=0.080, bsp_brier=0.085, hn=100)
        self.assertIn(v, ("thin", "to-holdout"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
