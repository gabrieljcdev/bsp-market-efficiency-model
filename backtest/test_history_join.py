"""Unit tests for the shared Layer-2 history-join engine (features/history_join.py).

Focus = the leakage-critical guarantees:
  * strictly-prior (date < race date); current & same-day runs excluded
  * delete-future-runs invariance (a past stat can't move when later runs vanish)
  * date-sort robustness (the joined CSV is not globally sorted)
  * no backfill on debut
  * the dist_f-suffix parsing regression ('16f' must not collapse to None)
  * fast prefix-win trainer SR == brute-force pure scan
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "features"))
import history_join as hj  # noqa: E402


def run(date, horse, pos, course="Ascot", dist_f="8f", trainer="T", jockey="J",
        klass="Class 3", going="Good", oratng="80", comment=""):
    """A minimal joined-row dict (only the columns the engine reads)."""
    return {"date": date, "off": "14:00", "horse": horse, "pos": pos,
            "course": course, "dist_f": dist_f, "trainer": trainer,
            "jockey": jockey, "class": klass, "going": going, "or": oratng,
            "surface": "Turf", "type": "Flat", "hg": "", "comment": comment}


def ctx(date, course="Ascot", dist_f="8f", klass="Class 3", going="Good",
        oratng="80", horse="H", jockey="J", trainer="T"):
    return {"race_ord": hj.to_ord(date), "course": course,
            "dist_f": hj.parse_distf(dist_f), "cur_or": hj.fnum(oratng),
            "klass": hj.parse_class(klass), "going": going,
            "horse": horse, "jockey": jockey, "trainer": trainer}


class TestStrictlyPrior(unittest.TestCase):
    def test_excludes_current_and_future(self):
        rows = [run("2020-01-01", "H", "1"), run("2020-02-01", "H", "1"),
                run("2020-03-01", "H", "5")]
        idx = hj.HistoryIndex(rows=rows)
        # at the 2nd run, only the 1st (a win) is prior -> win% = 1.0 over n=1
        prior = idx.prior_horse_runs("H", hj.to_ord("2020-02-01"))
        self.assertEqual(len(prior), 1)
        f = hj.horse_features(prior, ctx("2020-02-01", horse="H"))
        self.assertEqual(f["career_runs"], 1)
        self.assertEqual(f["career_win_pct"], 1.0)

    def test_same_day_excluded(self):
        rows = [run("2020-01-01", "H", "1"), run("2020-02-01", "H", "1"),
                run("2020-02-01", "H", "2")]  # two runs same day
        idx = hj.HistoryIndex(rows=rows)
        prior = idx.prior_horse_runs("H", hj.to_ord("2020-02-01"))
        self.assertEqual(len(prior), 1)  # only 2020-01-01, NOT the same-day run

    def test_debut_no_backfill(self):
        idx = hj.HistoryIndex(rows=[run("2020-01-01", "H", "1")])
        f = hj.horse_features(idx.prior_horse_runs("H", hj.to_ord("2020-01-01")),
                              ctx("2020-01-01"))
        self.assertEqual(f["career_runs"], 0)
        self.assertIsNone(f["career_win_pct"])
        self.assertIsNone(f["dslr"])


class TestDateSortRobustness(unittest.TestCase):
    def test_unsorted_rows_give_correct_prior(self):
        # rows fed out of date order (mirrors the line-452718 inversion)
        rows = [run("2020-03-01", "H", "5"), run("2020-01-01", "H", "1"),
                run("2020-02-01", "H", "1")]
        idx = hj.HistoryIndex(rows=rows)
        prior = idx.prior_horse_runs("H", hj.to_ord("2020-03-01"))
        self.assertEqual([p["date"] for p in prior],
                         ["2020-01-01", "2020-02-01"])  # sorted, both prior


class TestDeleteFutureInvariance(unittest.TestCase):
    def test_features_unchanged_when_future_deleted(self):
        full = [run("2020-01-01", "H", "1"), run("2020-02-01", "H", "3"),
                run("2020-03-01", "H", "1"), run("2020-04-01", "H", "1")]
        c = ctx("2020-02-01", horse="H")
        f_full = hj.horse_features(
            hj.HistoryIndex(rows=full).prior_horse_runs("H", hj.to_ord("2020-02-01")), c)
        truncated = [r for r in full if r["date"] < "2020-03-01"]
        f_tr = hj.horse_features(
            hj.HistoryIndex(rows=truncated).prior_horse_runs("H", hj.to_ord("2020-02-01")), c)
        self.assertEqual(f_full, f_tr)


class TestDistfParsing(unittest.TestCase):
    def test_suffix_and_half(self):
        self.assertEqual(hj.parse_distf("16f"), 16.0)
        self.assertEqual(hj.parse_distf("21.5f"), 21.5)
        self.assertEqual(hj.parse_distf("5½f"), 5.5)
        self.assertIsNone(hj.parse_distf(""))

    def test_won_course_superset_of_cd(self):
        # won at Ascot over 6f; today's race is Ascot over 8f
        rows = [run("2020-01-01", "H", "1", course="Ascot", dist_f="6f"),
                run("2020-06-01", "H", "4", course="Ascot", dist_f="8f")]
        idx = hj.HistoryIndex(rows=rows)
        f = hj.horse_features(idx.prior_horse_runs("H", hj.to_ord("2020-06-01")),
                              ctx("2020-06-01", course="Ascot", dist_f="8f"))
        # one prior Ascot run (6f, won); the 2020-06-01 run is current -> excluded
        self.assertEqual(f["won_course_flag"], 1)   # won at the course (any dist)
        self.assertEqual(f["won_course_flag_n"], 1)
        # no prior run at today's 8f -> None (no basis, no backfill), NOT 0. If the
        # dist_f 'f' suffix had collapsed to None, every dist would match and these
        # would wrongly equal won_course (the bug this guards against):
        self.assertIsNone(f["won_dist_flag"])
        self.assertEqual(f["won_dist_flag_n"], 0)
        self.assertIsNone(f["won_cd_flag"])
        self.assertEqual(f["won_cd_flag_n"], 0)


class TestRunStyle(unittest.TestCase):
    def test_classifier(self):
        self.assertEqual(hj.classify_runstyle("Led - ridden 2f out"), "led")
        self.assertEqual(hj.classify_runstyle("Held up in rear - headway"), "held_up")
        self.assertEqual(hj.classify_runstyle("Chased leaders - kept on"), "prominent")
        self.assertIsNone(hj.classify_runstyle(""))

    def test_dominant_is_deterministic_majority(self):
        rows = [run("2020-01-01", "H", "2", comment="Led - ran on"),
                run("2020-02-01", "H", "2", comment="Made all"),
                run("2020-03-01", "H", "4", comment="Held up in rear")]
        idx = hj.HistoryIndex(rows=rows)
        f = hj.horse_features(idx.prior_horse_runs("H", hj.to_ord("2020-06-01")),
                              ctx("2020-06-01"))
        self.assertEqual(f["run_style"], "led")   # 2 led vs 1 held_up
        self.assertEqual(f["run_style_n"], 3)


class TestTrainerSrEquivalence(unittest.TestCase):
    def test_fast_bucket_matches_pure_scan(self):
        rows = [run("2020-01-01", "A", "1", trainer="T", course="Ascot"),
                run("2020-02-01", "B", "3", trainer="T", course="Ascot"),
                run("2020-03-01", "C", "1", trainer="T", course="York"),
                run("2020-04-01", "D", "2", trainer="T", course="Ascot")]
        idx = hj.HistoryIndex(rows=rows)
        ro = hj.to_ord("2020-06-01")
        c = ctx("2020-06-01", course="Ascot", trainer="T")
        fast = idx.trainer_srs("T", ro, "Ascot", c["klass"], "Good")
        pure = hj.trainer_features(idx.prior_trainer_runs("T", ro), c)
        self.assertEqual(fast["trainer_course_sr"], pure["trainer_course_sr"])
        self.assertEqual(fast["trainer_course_sr_n"], pure["trainer_course_sr_n"])
        # 3 prior Ascot runs (A win, B no, D no) -> 1/3
        self.assertAlmostEqual(fast["trainer_course_sr"], 1 / 3)
        self.assertEqual(fast["trainer_course_sr_n"], 3)

    def test_trainer_sr_strictly_prior(self):
        rows = [run("2020-01-01", "A", "1", trainer="T", course="Ascot"),
                run("2020-06-01", "B", "1", trainer="T", course="Ascot")]
        idx = hj.HistoryIndex(rows=rows)
        # at 2020-06-01 only the first Ascot run counts (1/1); the current excluded
        srs = idx.trainer_srs("T", hj.to_ord("2020-06-01"), "Ascot",
                              hj.parse_class("Class 3"), "Good")
        self.assertEqual(srs["trainer_course_sr_n"], 1)
        self.assertEqual(srs["trainer_course_sr"], 1.0)


class TestCountrySuffixLookup(unittest.TestCase):
    """LIVE-CARD clean names must find COUNTRY-suffixed historical horses.

    Regression for a silent zero-match (worse than a loud error): the historical
    CSV carries 'Atreides (IRE)'; a live racecard gives the clean 'Atreides', so
    the runner view / scanner showed 'no history' for horses with plenty. Same
    class of bug as the course-name byte-match issue. The fix is exact-match-FIRST
    (historical path untouched) with a country/case-canonical fallback that refuses
    to merge genuinely different horses (same name, different country)."""

    def test_clean_name_finds_suffixed_history(self):
        rows = [run("2020-01-01", "Atreides (IRE)", "1"),
                run("2020-02-01", "Atreides (IRE)", "3"),
                run("2020-03-01", "Atreides (IRE)", "2")]
        idx = hj.HistoryIndex(rows=rows)
        # clean live-card name -> all 3 prior runs found (was 0 before the fix)
        prior = idx.prior_horse_runs("Atreides", hj.to_ord("2020-06-01"))
        self.assertEqual(len(prior), 3)
        f = hj.named_features(idx, ctx("2020-06-01", horse="Atreides"))
        self.assertEqual(f["career_runs"], 3)
        self.assertAlmostEqual(f["career_win_pct"], 1 / 3)

    def test_exact_suffixed_lookup_unaffected(self):
        # the HISTORICAL bridge path (suffixed name on BOTH sides) hits the exact
        # branch and never touches the canonical fallback -> unchanged behaviour.
        rows = [run("2020-01-01", "Atreides (IRE)", "1"),
                run("2020-02-01", "Atreides (IRE)", "3")]
        idx = hj.HistoryIndex(rows=rows)
        self.assertEqual(
            len(idx.prior_horse_runs("Atreides (IRE)", hj.to_ord("2020-06-01"))), 2)

    def test_case_variants_same_country_merge(self):
        # a source casing inconsistency ('Gwash (IRE)' vs 'gwash (IRE)') is ONE
        # horse -> its runs merge under the clean name.
        rows = [run("2020-01-01", "Gwash (IRE)", "1"),
                run("2020-02-01", "gwash (IRE)", "2")]
        idx = hj.HistoryIndex(rows=rows)
        self.assertEqual(
            len(idx.prior_horse_runs("Gwash", hj.to_ord("2020-06-01"))), 2)

    def test_different_country_is_ambiguous_and_refused(self):
        # two DIFFERENT horses sharing a name but bred in different countries must
        # NOT be silently merged on a clean-name lookup.
        rows = [run("2020-01-01", "Kingsman (IRE)", "1"),
                run("2020-02-01", "Kingsman (USA)", "1")]
        idx = hj.HistoryIndex(rows=rows)
        self.assertEqual(
            idx.prior_horse_runs("Kingsman", hj.to_ord("2020-06-01")), [])
        # ...but each exact suffixed name still resolves to its own history.
        self.assertEqual(
            len(idx.prior_horse_runs("Kingsman (IRE)", hj.to_ord("2020-06-01"))), 1)
        self.assertEqual(
            len(idx.prior_horse_runs("Kingsman (USA)", hj.to_ord("2020-06-01"))), 1)

    def test_canon_horse_parser(self):
        self.assertEqual(hj.canon_horse("Atreides (IRE)"), ("atreides", "IRE"))
        self.assertEqual(hj.canon_horse("Bettys Tiara (GB)"), ("bettys tiara", "GB"))
        self.assertEqual(hj.canon_horse("No Suffix"), ("no suffix", None))
        self.assertEqual(hj.canon_horse(None), (None, None))


if __name__ == "__main__":
    unittest.main(verbosity=2)
