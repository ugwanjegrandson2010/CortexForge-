"""Unit tests for the evaluation battery system.

Tests cover:
  * Instrument registration and retrieval
  * Scoring accuracy (including reverse scoring)
  * Subscale computation
  * Validation (missing responses, out-of-range, unexpected keys)
  * Interpretation bands
  * Profile field mapping
  * Scheduler due-ness logic
  * Daily budget constraints
  * Skip handling
  * Profile integration
"""

from __future__ import annotations

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.evaluation import (  # noqa: E402
    AMAS,
    FIVE_DC,
    ABS,
    BPNSFS,
    GSE,
    GRIT_S,
    MAAS,
    MSLQ,
    SFS,
    AGQ,
    WHO5,
    WTAS,
    BatteryScheduler,
    Instrument,
    InstrumentRegistry,
    Item,
    ScoringEngine,
    ScoredResult,
    create_default_registry,
    score_and_update_profile,
)


# ---------------------------------------------------------------------------
# Instrument registration tests
# ---------------------------------------------------------------------------


class TestInstrumentRegistry(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()

    def test_default_registry_has_12_instruments(self):
        self.assertEqual(len(self.registry.instrument_ids()), 12)

    def test_all_instruments_present(self):
        expected = {"mslq", "maas", "gse", "amas", "agq", "grit_s",
                     "wtas", "sfs", "five_dc", "abs", "bpnsfs", "who5"}
        self.assertEqual(set(self.registry.instrument_ids()), expected)

    def test_get_instrument(self):
        mslq = self.registry.get("mslq")
        self.assertIsNotNone(mslq)
        self.assertEqual(mslq.instrument_id, "mslq")
        self.assertEqual(mslq.name, "Motivated Strategies for Learning Questionnaire")

    def test_get_unknown_instrument_returns_none(self):
        self.assertIsNone(self.registry.get("nonexistent"))

    def test_require_unknown_instrument_raises(self):
        with self.assertRaises(KeyError):
            self.registry.require("nonexistent")

    def test_get_by_construct(self):
        results = self.registry.get_by_construct("self_efficacy")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].instrument_id, "gse")

    def test_validate_empty_registry(self):
        reg = InstrumentRegistry()
        self.assertEqual(reg.validate(), [])

    def test_validate_sound_registry(self):
        problems = self.registry.validate()
        self.assertEqual(problems, [])

    def test_manifest(self):
        manifest = self.registry.manifest()
        self.assertEqual(manifest["total_instruments"], 12)
        self.assertGreater(manifest["total_items"], 0)
        self.assertGreater(manifest["total_minutes"], 0)
        self.assertEqual(manifest["problems"], [])

    def test_instrument_to_dict(self):
        who5 = self.registry.get("who5")
        self.assertIsNotNone(who5)
        d = who5.to_dict()
        self.assertEqual(d["instrument_id"], "who5")
        self.assertEqual(d["evidence"], "strong")
        self.assertEqual(d["licence"], "open")
        self.assertEqual(len(d["items"]), 5)

    def test_all_instruments_have_items(self):
        for inst in self.registry.all_instruments():
            self.assertGreater(len(inst.items), 0, f"{inst.instrument_id} has no items")

    def test_all_instruments_have_profile_fields(self):
        for inst in self.registry.all_instruments():
            self.assertIn("total", inst.profile_fields,
                          f"{inst.instrument_id} missing total profile field")

    def test_all_instruments_have_valid_evidence(self):
        valid = {"strong", "moderate", "weak", "none"}
        for inst in self.registry.all_instruments():
            self.assertIn(inst.evidence, valid,
                          f"{inst.instrument_id} has invalid evidence {inst.evidence}")

    def test_all_instruments_have_valid_licence(self):
        valid = {"open", "restricted", "clinical_only"}
        for inst in self.registry.all_instruments():
            self.assertIn(inst.licence, valid,
                          f"{inst.instrument_id} has invalid licence {inst.licence}")

    def test_all_instruments_have_positive_readministration(self):
        for inst in self.registry.all_instruments():
            self.assertGreater(inst.readministration_days, 0)

    def test_all_instruments_have_positive_minutes(self):
        for inst in self.registry.all_instruments():
            self.assertGreater(inst.minutes, 0)

    def test_subscale_items_exist(self):
        for inst in self.registry.all_instruments():
            for sub in inst.subscales:
                has_items = any(item.subscale == sub for item in inst.items)
                self.assertTrue(has_items,
                                f"{inst.instrument_id}: subscale {sub!r} has no items")


# ---------------------------------------------------------------------------
# Scoring engine tests
# ---------------------------------------------------------------------------


class TestScoringEngine(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()
        self.engine = ScoringEngine(self.registry)

    def test_score_who5_perfect(self):
        """WHO5 with all max scores should give total = 25."""
        responses = {"who5_1": 5, "who5_2": 5, "who5_3": 5, "who5_4": 5, "who5_5": 5}
        result = self.engine.score("who5", responses)
        self.assertEqual(result.total_score, 25)
        self.assertEqual(result.interpretation, "good")
        self.assertEqual(result.completeness, 1.0)
        self.assertEqual(result.n_items_answered, 5)

    def test_score_who5_zero(self):
        """WHO5 with all zero scores should give total = 0."""
        responses = {"who5_1": 0, "who5_2": 0, "who5_3": 0, "who5_4": 0, "who5_5": 0}
        result = self.engine.score("who5", responses)
        self.assertEqual(result.total_score, 0)
        self.assertEqual(result.interpretation, "low")

    def test_score_who5_mixed(self):
        responses = {"who5_1": 3, "who5_2": 4, "who5_3": 2, "who5_4": 3, "who5_5": 4}
        result = self.engine.score("who5", responses)
        self.assertEqual(result.total_score, 16)
        self.assertEqual(result.completeness, 1.0)

    def test_reverse_scoring_maas(self):
        """MAAS items are reverse scored. Raw 1 should become 6, raw 6 should become 1."""
        responses = {f"maas_{i}": 1 for i in range(1, 11)}
        result = self.engine.score("maas", responses)
        # All raw 1s become 6s after reverse scoring
        self.assertEqual(result.total_score, 6.0)

    def test_reverse_scoring_maas_high(self):
        """MAAS with all raw 6s should become all 1s after reverse scoring."""
        responses = {f"maas_{i}": 6 for i in range(1, 11)}
        result = self.engine.score("maas", responses)
        self.assertEqual(result.total_score, 1.0)

    def test_reverse_scoring_grit_s(self):
        """GRIT-S consistency items are reverse scored."""
        responses = {}
        for i in range(1, 4):
            responses[f"grit_s_{i}"] = 1  # consistency -> reverse -> 5
        for i in range(4, 9):
            responses[f"grit_s_{i}"] = 5  # perseverance -> 5
        result = self.engine.score("grit_s", responses)
        self.assertEqual(result.total_score, 5.0)
        self.assertEqual(result.subscale_scores["consistency_of_interest"], 5.0)
        self.assertEqual(result.subscale_scores["perseverance_of_effort"], 5.0)

    def test_subscale_computation_amq(self):
        """AMAS has learning and evaluation subscales."""
        responses = {}
        for i in range(1, 6):
            responses[f"amas_{i}"] = 3  # learning items
        for i in range(6, 10):
            responses[f"amas_{i}"] = 4  # evaluation items
        result = self.engine.score("amas", responses)
        self.assertEqual(result.subscale_scores["learning_math_anxiety"], 15)
        self.assertEqual(result.subscale_scores["math_evaluation_anxiety"], 16)
        self.assertEqual(result.total_score, 31)

    def test_subscale_computation_agq(self):
        """AGQ has 4 subscales with mean scoring."""
        responses = {}
        for i in range(1, 4):
            responses[f"agq_{i}"] = 5  # mastery_approach
        for i in range(4, 7):
            responses[f"agq_{i}"] = 3  # mastery_avoidance
        for i in range(7, 10):
            responses[f"agq_{i}"] = 6  # performance_approach
        for i in range(10, 13):
            responses[f"agq_{i}"] = 2  # performance_avoidance
        result = self.engine.score("agq", responses)
        self.assertEqual(result.subscale_scores["mastery_approach"], 5.0)
        self.assertEqual(result.subscale_scores["mastery_avoidance"], 3.0)
        self.assertEqual(result.subscale_scores["performance_approach"], 6.0)
        self.assertEqual(result.subscale_scores["performance_avoidance"], 2.0)

    def test_profile_values_mapping(self):
        """Scores should map to profile field names."""
        responses = {"who5_1": 4, "who5_2": 4, "who5_3": 4, "who5_4": 4, "who5_5": 4}
        result = self.engine.score("who5", responses)
        self.assertIn("wellbeing", result.profile_values)
        self.assertEqual(result.profile_values["wellbeing"], 20)

    def test_profile_values_subscales(self):
        """Subscale scores should map to their profile fields."""
        responses = {}
        for i in range(1, 16):
            responses[f"five_dc_{i}"] = 5
        result = self.engine.score("five_dc", responses)
        self.assertIn("joyous_exploration", result.profile_values)
        self.assertIn("curiosity_about_people", result.profile_values)
        self.assertEqual(result.profile_values["joyous_exploration"], 5.0)

    def test_missing_responses_strict(self):
        """Strict mode should raise on missing responses."""
        responses = {"who5_1": 5}
        with self.assertRaises(ValueError, msg="missing response"):
            self.engine.score("who5", responses, strict=True)

    def test_missing_responses_lenient(self):
        """Lenient mode should score with available items."""
        responses = {"who5_1": 5, "who5_2": 4, "who5_3": 3}
        result = self.engine.score("who5", responses, strict=False)
        self.assertEqual(result.total_score, 12)
        self.assertEqual(result.n_items_answered, 3)
        self.assertEqual(result.completeness, 0.6)

    def test_out_of_range_high(self):
        """Scores above scale max should be rejected in strict mode."""
        responses = {"who5_1": 6, "who5_2": 5, "who5_3": 5, "who5_4": 5, "who5_5": 5}
        with self.assertRaises(ValueError, msg="outside range"):
            self.engine.score("who5", responses, strict=True)

    def test_out_of_range_low(self):
        """Scores below scale min should be rejected in strict mode."""
        responses = {"who5_1": -1, "who5_2": 5, "who5_3": 5, "who5_4": 5, "who5_5": 5}
        with self.assertRaises(ValueError, msg="outside range"):
            self.engine.score("who5", responses, strict=True)

    def test_unexpected_keys(self):
        """Unexpected response keys should be rejected in strict mode."""
        responses = {"who5_1": 5, "who5_2": 5, "who5_3": 5, "who5_4": 5, "who5_5": 5,
                      "who5_6": 3}
        with self.assertRaises(ValueError, msg="unexpected"):
            self.engine.score("who5", responses, strict=True)

    def test_non_numeric_score(self):
        """Non-numeric scores should be rejected."""
        responses = {"who5_1": "five", "who5_2": 5, "who5_3": 5, "who5_4": 5, "who5_5": 5}
        with self.assertRaises(ValueError, msg="non-numeric"):
            self.engine.score("who5", responses, strict=True)

    def test_empty_responses(self):
        """Empty responses in lenient mode should give None total."""
        result = self.engine.score("who5", {}, strict=False)
        self.assertIsNone(result.total_score)
        self.assertEqual(result.interpretation, "insufficient_data")
        self.assertEqual(result.completeness, 0.0)

    def test_interpretation_bands(self):
        """Test interpretation band boundaries."""
        # WHO5: scale 0-5, sum of 5 items -> range 0-25
        # low: 0-8.33, moderate: 8.33-16.67, high: 16.67-25
        low = self.engine.score("who5", {f"who5_{i}": 1 for i in range(1, 6)})
        self.assertEqual(low.interpretation, "low")

        moderate = self.engine.score("who5", {f"who5_{i}": 3 for i in range(1, 6)})
        self.assertEqual(moderate.interpretation, "moderate")

        high = self.engine.score("who5", {f"who5_{i}": 5 for i in range(1, 6)})
        self.assertEqual(high.interpretation, "good")

    def test_interpretation_higher_is_worse(self):
        """AMAS has higher_is_better=False, so high scores map to 'elevated'."""
        # AMAS: scale 1-5, sum of 9 items -> range 9-45
        # low: 9-21, moderate: 21-33, high: 33-45
        low = self.engine.score("amas", {f"amas_{i}": 1 for i in range(1, 10)})
        self.assertEqual(low.interpretation, "good")

        high = self.engine.score("amas", {f"amas_{i}": 5 for i in range(1, 10)})
        self.assertEqual(high.interpretation, "elevated")

    def test_validate_responses_problems(self):
        """validate_responses should report all problems."""
        responses = {"who5_1": 10}
        problems = self.engine.validate_responses("who5", responses)
        self.assertGreater(len(problems), 0)
        self.assertTrue(any("missing" in p for p in problems))
        self.assertTrue(any("outside range" in p for p in problems))

    def test_validate_responses_clean(self):
        """validate_responses should return empty list for valid responses."""
        responses = {"who5_1": 3, "who5_2": 4, "who5_3": 3, "who5_4": 4, "who5_5": 3}
        problems = self.engine.validate_responses("who5", responses)
        self.assertEqual(problems, [])

    def test_score_to_observations(self):
        """ScoredResult should convert to profile observations."""
        responses = {"who5_1": 4, "who5_2": 4, "who5_3": 4, "who5_4": 4, "who5_5": 4}
        result = self.engine.score("who5", responses)
        observations = self.engine.score_to_observations(result, "learner_1")
        self.assertGreater(len(observations), 0)
        obs = observations[0]
        self.assertIn("construct", obs)
        self.assertIn("value", obs)
        self.assertIn("statement", obs)
        self.assertIn("action", obs)
        self.assertEqual(obs["construct"], "wellbeing")

    def test_score_to_observations_subscales(self):
        """Subscale results should produce observations for each subscale."""
        responses = {}
        for i in range(1, 16):
            responses[f"five_dc_{i}"] = 5
        result = self.engine.score("five_dc", responses)
        observations = self.engine.score_to_observations(result, "learner_1")
        constructs = [o["construct"] for o in observations]
        self.assertIn("joyous_exploration", constructs)
        self.assertIn("curiosity_about_people", constructs)


# ---------------------------------------------------------------------------
# Battery scheduler tests
# ---------------------------------------------------------------------------


class TestBatteryScheduler(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()
        self.scheduler = BatteryScheduler(self.registry)

    def test_default_budget(self):
        self.assertEqual(self.scheduler.daily_budget_minutes, 6.0)

    def test_budget_bounds(self):
        with self.assertRaises(ValueError):
            BatteryScheduler(self.registry, daily_budget_minutes=4)
        with self.assertRaises(ValueError):
            BatteryScheduler(self.registry, daily_budget_minutes=9)

    def test_budget_bounds_valid(self):
        s = BatteryScheduler(self.registry, daily_budget_minutes=5)
        self.assertEqual(s.daily_budget_minutes, 5)
        s = BatteryScheduler(self.registry, daily_budget_minutes=8)
        self.assertEqual(s.daily_budget_minutes, 8)

    def test_is_due_never_administered(self):
        """Instruments never administered should always be due."""
        self.assertTrue(self.scheduler.is_due("who5"))

    def test_is_due_after_administration(self):
        """Instruments just administered should not be due."""
        self.scheduler.record_administration("who5")
        self.assertFalse(self.scheduler.is_due("who5"))

    def test_is_due_after_interval(self):
        """Instruments should be due after their readministration interval."""
        past = time.time() - 8 * 86400
        self.scheduler.record_administration("who5", timestamp=past)
        self.assertTrue(self.scheduler.is_due("who5"))

    def test_is_not_due_within_interval(self):
        """Instruments should not be due within their readministration interval."""
        past = time.time() - 3 * 86400
        self.scheduler.record_administration("who5", timestamp=past)
        self.assertFalse(self.scheduler.is_due("who5"))

    def test_due_instruments(self):
        """All instruments should be due when nothing has been administered."""
        due = self.scheduler.due_instruments()
        self.assertEqual(len(due), 12)

    def test_due_instruments_partial(self):
        """Only non-administered instruments should be due."""
        self.scheduler.record_administration("who5")
        self.scheduler.record_administration("maas")
        due = self.scheduler.due_instruments()
        self.assertNotIn("who5", due)
        self.assertNotIn("maas", due)
        self.assertEqual(len(due), 10)

    def test_recommend_today_respects_budget(self):
        """Recommended instruments should fit within the daily budget."""
        recommended = self.scheduler.recommend_today()
        instruments = [self.scheduler.registry.require(iid) for iid in recommended]
        total = sum(i.minutes for i in instruments)
        self.assertLessEqual(total, self.scheduler.daily_budget_minutes)

    def test_recommend_today_priority(self):
        """Never-administered instruments should be prioritized."""
        recommended = self.scheduler.recommend_today()
        self.assertGreaterEqual(len(recommended), 1)

    def test_recommend_today_all_administered(self):
        """When all instruments are administered recently, nothing should be due."""
        s = BatteryScheduler(self.registry)
        now = time.time()
        for iid in s.registry.instrument_ids():
            s.record_administration(iid, timestamp=now)
        due = s.due_instruments(current_time=now)
        self.assertEqual(len(due), 0)

    def test_record_administration(self):
        self.scheduler.record_administration("who5")
        history = self.scheduler.get_history("who5")
        self.assertEqual(history["administration_count"], 1)
        self.assertIsNotNone(history["last_administered"])

    def test_skip(self):
        self.scheduler.record_administration("who5")
        self.scheduler.skip("who5")
        history = self.scheduler.get_history("who5")
        self.assertEqual(history["skip_count"], 1)
        # Skipping should not reset the timer
        self.assertFalse(self.scheduler.is_due("who5"))

    def test_skip_multiple(self):
        self.scheduler.skip("who5")
        self.scheduler.skip("who5")
        history = self.scheduler.get_history("who5")
        self.assertEqual(history["skip_count"], 2)

    def test_get_daily_plan(self):
        plan = self.scheduler.get_daily_plan()
        self.assertIn("recommended", plan)
        self.assertIn("total_minutes", plan)
        self.assertIn("budget_minutes", plan)
        self.assertLessEqual(plan["total_minutes"], plan["budget_minutes"])

    def test_schedule_all(self):
        plans = self.scheduler.schedule_all(days=7)
        self.assertEqual(len(plans), 7)
        for plan in plans:
            self.assertIn("recommended", plan)
            self.assertIn("total_minutes", plan)

    def test_to_dict(self):
        self.scheduler.record_administration("who5")
        self.scheduler.skip("maas")
        state = self.scheduler.to_dict()
        self.assertEqual(state["daily_budget_minutes"], 6.0)
        self.assertIn("who5", state["last_administered"])
        self.assertIn("maas", state["skip_history"])

    def test_unknown_instrument_raises(self):
        with self.assertRaises(KeyError):
            self.scheduler.record_administration("nonexistent")
        with self.assertRaises(KeyError):
            self.scheduler.skip("nonexistent")
        with self.assertRaises(KeyError):
            self.scheduler.get_history("nonexistent")


# ---------------------------------------------------------------------------
# Integration: score and update profile
# ---------------------------------------------------------------------------


class TestScoreAndUpdate(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()
        self.engine = ScoringEngine(self.registry)
        self.scheduler = BatteryScheduler(self.registry)

    def test_score_and_update(self):
        responses = {"who5_1": 4, "who5_2": 4, "who5_3": 4, "who5_4": 4, "who5_5": 4}
        result, observations = score_and_update_profile(
            self.engine, self.scheduler, "who5", responses)
        self.assertEqual(result.total_score, 20)
        self.assertGreater(len(observations), 0)
        self.assertFalse(self.scheduler.is_due("who5"))

    def test_score_and_update_appends(self):
        responses = {"who5_1": 4, "who5_2": 4, "who5_3": 4, "who5_4": 4, "who5_5": 4}
        profile_obs = []
        _, obs1 = score_and_update_profile(
            self.engine, self.scheduler, "who5", responses, profile_obs)
        _, obs2 = score_and_update_profile(
            self.engine, self.scheduler, "gse",
            {f"gse_{i}": 3 for i in range(1, 11)}, profile_obs)
        self.assertEqual(len(profile_obs), len(obs1) + len(obs2))


# ---------------------------------------------------------------------------
# Instrument-specific tests
# ---------------------------------------------------------------------------


class TestInstrumentSpecifics(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()

    def test_mslq_15_items(self):
        mslq = self.registry.get("mslq")
        self.assertIsNotNone(mslq)
        self.assertEqual(len(mslq.items), 15)

    def test_maas_10_items_all_reverse(self):
        maas = self.registry.get("maas")
        self.assertIsNotNone(maas)
        self.assertEqual(len(maas.items), 10)
        self.assertTrue(all(item.reverse_scored for item in maas.items))

    def test_gse_10_items(self):
        gse = self.registry.get("gse")
        self.assertIsNotNone(gse)
        self.assertEqual(len(gse.items), 10)

    def test_amas_9_items_2_subscales(self):
        amas = self.registry.get("amas")
        self.assertIsNotNone(amas)
        self.assertEqual(len(amas.items), 9)
        self.assertEqual(len(amas.subscales), 2)

    def test_agq_12_items_4_subscales(self):
        agq = self.registry.get("agq")
        self.assertIsNotNone(agq)
        self.assertEqual(len(agq.items), 12)
        self.assertEqual(len(agq.subscales), 4)

    def test_grit_s_8_items_mixed_reverse(self):
        grit = self.registry.get("grit_s")
        self.assertIsNotNone(grit)
        self.assertEqual(len(grit.items), 8)
        reverse_count = sum(1 for item in grit.items if item.reverse_scored)
        forward_count = sum(1 for item in grit.items if not item.reverse_scored)
        self.assertGreater(reverse_count, 0)
        self.assertGreater(forward_count, 0)

    def test_wtas_10_items_no_subscales(self):
        wtas = self.registry.get("wtas")
        self.assertIsNotNone(wtas)
        self.assertEqual(len(wtas.items), 10)
        self.assertEqual(len(wtas.subscales), 0)

    def test_sfs_10_items_one_reverse(self):
        sfs = self.registry.get("sfs")
        self.assertIsNotNone(sfs)
        self.assertEqual(len(sfs.items), 10)
        reverse_count = sum(1 for item in sfs.items if item.reverse_scored)
        self.assertEqual(reverse_count, 1)

    def test_five_dc_15_items_5_subscales(self):
        fdc = self.registry.get("five_dc")
        self.assertIsNotNone(fdc)
        self.assertEqual(len(fdc.items), 15)
        self.assertEqual(len(fdc.subscales), 5)

    def test_abs_10_items_4_subscales(self):
        abs_inst = self.registry.get("abs")
        self.assertIsNotNone(abs_inst)
        self.assertEqual(len(abs_inst.items), 10)
        self.assertEqual(len(abs_inst.subscales), 4)

    def test_bpnsfs_9_items_3_subscales(self):
        bpnsfs = self.registry.get("bpnsfs")
        self.assertIsNotNone(bpnsfs)
        self.assertEqual(len(bpnsfs.items), 9)
        self.assertEqual(len(bpnsfs.subscales), 3)

    def test_who5_5_items_0_to_5_scale(self):
        who5 = self.registry.get("who5")
        self.assertIsNotNone(who5)
        self.assertEqual(len(who5.items), 5)
        self.assertEqual(who5.items[0].scale_min, 0)
        self.assertEqual(who5.items[0].scale_max, 5)

    def test_readministration_intervals(self):
        """Check that readministration intervals are reasonable."""
        for inst in self.registry.all_instruments():
            self.assertGreaterEqual(inst.readministration_days, 1)
            self.assertLessEqual(inst.readministration_days, 30)

    def test_total_battery_minutes(self):
        """Total battery should be completable in a reasonable number of days."""
        total = sum(inst.minutes for inst in self.registry.all_instruments())
        self.assertGreaterEqual(total, 25)
        self.assertLessEqual(total, 60)

    def test_higher_is_better_flags(self):
        """Anxiety measures should have higher_is_better=False."""
        amas = self.registry.get("amas")
        self.assertIsNotNone(amas)
        self.assertFalse(amas.higher_is_better)
        wtas = self.registry.get("wtas")
        self.assertIsNotNone(wtas)
        self.assertFalse(wtas.higher_is_better)

    def test_positive_measures_higher_is_better(self):
        """Well-being and self-efficacy measures should have higher_is_better=True."""
        who5 = self.registry.get("who5")
        self.assertIsNotNone(who5)
        self.assertTrue(who5.higher_is_better)
        gse = self.registry.get("gse")
        self.assertIsNotNone(gse)
        self.assertTrue(gse.higher_is_better)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases(unittest.TestCase):
    def setUp(self):
        self.registry = create_default_registry()
        self.engine = ScoringEngine(self.registry)
        self.scheduler = BatteryScheduler(self.registry)

    def test_score_with_float_responses(self):
        """Float responses should be handled correctly."""
        responses = {"who5_1": 3.5, "who5_2": 4.0, "who5_3": 3.0,
                     "who5_4": 4.5, "who5_5": 3.5}
        result = self.engine.score("who5", responses)
        self.assertEqual(result.total_score, 18.5)

    def test_score_with_integer_responses(self):
        """Integer responses should work fine."""
        responses = {"who5_1": 3, "who5_2": 4, "who5_3": 3, "who5_4": 4, "who5_5": 3}
        result = self.engine.score("who5", responses)
        self.assertEqual(result.total_score, 17)

    def test_completeness_partial(self):
        """Completeness should reflect fraction of items answered."""
        responses = {"who5_1": 3, "who5_2": 4}
        result = self.engine.score("who5", responses, strict=False)
        self.assertEqual(result.completeness, 0.4)
        self.assertEqual(result.n_items_answered, 2)
        self.assertEqual(result.n_items_total, 5)

    def test_scheduler_with_custom_budget(self):
        """Scheduler with larger budget should fit more instruments."""
        s = BatteryScheduler(self.registry, daily_budget_minutes=8.0)
        recommended = s.recommend_today()
        instruments = [s.registry.require(iid) for iid in recommended]
        total = sum(i.minutes for i in instruments)
        self.assertLessEqual(total, 8.0)
        self.assertGreater(total, 6.0)

    def test_instrument_item_ids_unique(self):
        """All item IDs within an instrument should be unique."""
        for inst in self.registry.all_instruments():
            ids = [item.item_id for item in inst.items]
            self.assertEqual(len(ids), len(set(ids)),
                             f"{inst.instrument_id} has duplicate item IDs")

    def test_item_ids_prefixed(self):
        """Item IDs should be prefixed with the instrument ID."""
        for inst in self.registry.all_instruments():
            for item in inst.items:
                self.assertTrue(
                    item.item_id.startswith(inst.instrument_id),
                    f"{item.item_id} does not start with {inst.instrument_id}"
                )

    def test_scored_result_to_dict(self):
        """ScoredResult should serialize to dict."""
        responses = {"who5_1": 3, "who5_2": 4, "who5_3": 3, "who5_4": 4, "who5_5": 3}
        result = self.engine.score("who5", responses)
        d = result.to_dict()
        self.assertEqual(d["instrument_id"], "who5")
        self.assertEqual(d["total_score"], 17)
        self.assertEqual(d["n_items_answered"], 5)

    def test_scheduler_skip_does_not_affect_due(self):
        """Skipping should not reset the administration timer."""
        self.scheduler.record_administration("who5")
        self.scheduler.skip("who5")
        self.assertFalse(self.scheduler.is_due("who5"))

    def test_multiple_instruments_scoring(self):
        """Score multiple instruments and verify independence."""
        who5_result = self.engine.score(
            "who5", {f"who5_{i}": 4 for i in range(1, 6)})
        gse_result = self.engine.score(
            "gse", {f"gse_{i}": 3 for i in range(1, 11)})
        self.assertEqual(who5_result.total_score, 20)
        self.assertEqual(gse_result.total_score, 30)
        self.assertEqual(who5_result.instrument_id, "who5")
        self.assertEqual(gse_result.instrument_id, "gse")


if __name__ == "__main__":
    unittest.main()
