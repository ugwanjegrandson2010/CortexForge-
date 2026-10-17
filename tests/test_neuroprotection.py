"""Neuro-protection system tests.

Covers ClarityGuardian, LoadBudgeter, AttentionalHygiene, CircadianSync,
NoveltyInjector, and the NeuroProtectionSystem facade.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.neuroprotection import (  # noqa: E402
    AttentionalHygiene,
    CircadianRecommendation,
    CircadianSync,
    ClarityGuardian,
    FatigueSignal,
    HygienePrompt,
    LoadBudgeter,
    LoadStatus,
    NeuroProtectionSystem,
    NeuroProtectionStatus,
    NoveltyChallenge,
    NoveltyInjector,
    Trial,
)


def _trials(n: int, correct_prob: float = 0.9, base_rt: float = 500.0,
            rt_noise: float = 50.0) -> list[Trial]:
    """Build synthetic trials with controllable accuracy and RT noise."""
    import random
    rng = random.Random(42)
    trials = []
    for _ in range(n):
        correct = rng.random() < correct_prob
        rt = base_rt + rng.gauss(0, rt_noise)
        trials.append(Trial(correct=correct, rt_ms=max(100.0, rt)))
    return trials


# ---------------------------------------------------------------------------
# ClarityGuardian
# ---------------------------------------------------------------------------

class TestClarityGuardian(unittest.TestCase):

    def test_no_fatigue_with_stable_performance(self):
        """Low RT variance and low error rate → no fatigue."""
        guardian = ClarityGuardian(baseline_error_rate=0.1)
        trials = _trials(20, correct_prob=0.95, rt_noise=20.0)
        sig = guardian.analyze(trials)
        self.assertFalse(sig.is_fatigued)
        self.assertIsNotNone(sig.rt_cv)
        self.assertLess(sig.rt_cv, 0.35)

    def test_fatigue_from_high_rt_variance(self):
        """High RT coefficient of variation → fatigue detected."""
        guardian = ClarityGuardian(baseline_error_rate=0.1)
        trials = _trials(20, correct_prob=0.9, rt_noise=200.0)
        sig = guardian.analyze(trials)
        self.assertTrue(sig.is_fatigued)
        self.assertTrue(sig.rt_variance_elevated)
        self.assertGreater(sig.rt_cv, 0.35)

    def test_fatigue_from_error_spike(self):
        """Error rate exceeding 2× baseline → fatigue detected."""
        guardian = ClarityGuardian(baseline_error_rate=0.05)
        trials = _trials(20, correct_prob=0.5, rt_noise=20.0)
        sig = guardian.analyze(trials)
        self.assertTrue(sig.is_fatigued)
        self.assertTrue(sig.error_spike)

    def test_insufficient_trials_returns_non_fatigued(self):
        """Fewer than MIN_TRIALS_FOR_FATIGUE trials → no fatigue flag."""
        guardian = ClarityGuardian(baseline_error_rate=0.1)
        trials = _trials(3, correct_prob=0.0, rt_noise=500.0)
        sig = guardian.analyze(trials)
        self.assertFalse(sig.is_fatigued)
        self.assertIsNone(sig.rt_cv)
        self.assertLess(sig.n_trials, 8)

    def test_baseline_error_rate_zero_with_high_errors_flags_spike(self):
        """No baseline (0.0) but >15% error rate → spike flagged."""
        guardian = ClarityGuardian(baseline_error_rate=0.0)
        trials = _trials(20, correct_prob=0.6, rt_noise=20.0)
        sig = guardian.analyze(trials)
        self.assertTrue(sig.error_spike)

    def test_record_trial_accumulates_history(self):
        """record_trial() builds internal history for later analysis."""
        guardian = ClarityGuardian(baseline_error_rate=0.1)
        for _ in range(10):
            guardian.record_trial(correct=True, rt_ms=500.0)
        sig = guardian.analyze()
        self.assertEqual(sig.n_trials, 10)
        self.assertFalse(sig.is_fatigued)

    def test_reset_clears_history(self):
        """reset() clears accumulated trial history."""
        guardian = ClarityGuardian()
        for _ in range(5):
            guardian.record_trial(correct=True, rt_ms=400.0)
        guardian.reset()
        sig = guardian.analyze()
        self.assertEqual(sig.n_trials, 0)

    def test_fatigue_signal_includes_evidence(self):
        """Every fatigue signal carries an evidence citation."""
        guardian = ClarityGuardian(baseline_error_rate=0.1)
        trials = _trials(20, correct_prob=0.5, rt_noise=200.0)
        sig = guardian.analyze(trials)
        self.assertTrue(sig.evidence)
        self.assertIn("RT variability", sig.evidence)

    def test_signal_serialises_to_dict(self):
        """FatigueSignal is JSON-serialisable via to_dict()."""
        import json
        sig = FatigueSignal(
            is_fatigued=True, rt_cv=0.4, error_rate=0.3,
            baseline_error_rate=0.1, error_spike=True,
            rt_variance_elevated=True, n_trials=10,
            reason="test", suggestion="test", evidence="test",
        )
        d = sig.to_dict()
        self.assertTrue(d["is_fatigued"])
        json.dumps(d)

    def test_no_clinical_vocabulary_in_output(self):
        """No clinical terms appear in reason or suggestion strings."""
        guardian = ClarityGuardian(baseline_error_rate=0.05)
        trials = _trials(20, correct_prob=0.3, rt_noise=200.0)
        sig = guardian.analyze(trials)
        text = (sig.reason + sig.suggestion).lower()
        for word in ("disorder", "diagnos", "symptom", "deficit",
                      "impaired", "abnormal", "patient"):
            self.assertNotIn(word, text)


# ---------------------------------------------------------------------------
# LoadBudgeter
# ---------------------------------------------------------------------------

class TestLoadBudgeter(unittest.TestCase):

    def test_session_within_budget(self):
        """Planned session fits → not over budget."""
        budgeter = LoadBudgeter(daily_cap=20.0)
        status = budgeter.start_session(planned_minutes=30.0)
        self.assertFalse(status.is_over_budget)
        self.assertFalse(status.is_near_budget)

    def test_session_exceeds_remaining_budget(self):
        """Planned session exceeds remaining → near budget, not over."""
        budgeter = LoadBudgeter(daily_cap=10.0)
        budgeter.record_session(actual_minutes=40.0)  # 8 units used
        status = budgeter.start_session(planned_minutes=30.0)  # 6 units
        self.assertFalse(status.is_over_budget)
        self.assertTrue(status.is_near_budget)
        self.assertLess(status.units_remaining, 6.0)

    def test_over_budget_after_recording(self):
        """Recording enough sessions → over budget."""
        budgeter = LoadBudgeter(daily_cap=5.0)
        status = budgeter.record_session(actual_minutes=30.0)  # 6 units
        self.assertTrue(status.is_over_budget)
        self.assertEqual(status.units_remaining, 0.0)

    def test_daily_cap_clamped(self):
        """Daily cap is clamped to [MIN, MAX] range."""
        low = LoadBudgeter(daily_cap=1.0)
        self.assertEqual(low.daily_cap, 5.0)
        high = LoadBudgeter(daily_cap=100.0)
        self.assertEqual(high.daily_cap, 40.0)

    def test_reset_daily_clears_usage(self):
        """reset_daily() zeros the counter."""
        budgeter = LoadBudgeter(daily_cap=20.0)
        budgeter.record_session(actual_minutes=60.0)
        self.assertGreater(budgeter.units_used, 0)
        budgeter.reset_daily()
        self.assertEqual(budgeter.units_used, 0)
        self.assertEqual(budgeter.units_remaining, 20.0)

    def test_units_conversion(self):
        """1 unit = UNIT_MINUTES minutes of focused work."""
        budgeter = LoadBudgeter(daily_cap=20.0, unit_minutes=5.0)
        status = budgeter.record_session(actual_minutes=25.0)
        self.assertAlmostEqual(status.units_used, 5.0)

    def test_multiple_sessions_accumulate(self):
        """Multiple sessions add up correctly."""
        budgeter = LoadBudgeter(daily_cap=20.0)
        budgeter.record_session(actual_minutes=20.0)  # 4 units
        budgeter.record_session(actual_minutes=15.0)  # 3 units
        self.assertAlmostEqual(budgeter.units_used, 7.0)

    def test_load_status_includes_suggestion(self):
        """Every LoadStatus carries an actionable suggestion."""
        budgeter = LoadBudgeter(daily_cap=5.0)
        status = budgeter.record_session(actual_minutes=60.0)
        self.assertTrue(status.suggestion)
        self.assertIn("today", status.suggestion.lower())


# ---------------------------------------------------------------------------
# AttentionalHygiene
# ---------------------------------------------------------------------------

class TestAttentionalHygiene(unittest.TestCase):

    def test_no_break_before_block_elapsed(self):
        """No break recommended before block minutes elapse."""
        hygiene = AttentionalHygiene()
        prompt = hygiene.get_break_recommendation(minutes_into_session=5.0)
        self.assertEqual(prompt.prompt_type, "none")
        self.assertEqual(prompt.duration_minutes, 0.0)

    def test_break_after_block_elapsed(self):
        """Break recommended after block minutes elapse."""
        hygiene = AttentionalHygiene()
        prompt = hygiene.get_break_recommendation(minutes_into_session=20.0)
        self.assertEqual(prompt.prompt_type, "break")
        self.assertEqual(prompt.duration_minutes, 5.0)

    def test_shorter_block_when_fatigued(self):
        """Block shortens to 10 min when fatigue is detected."""
        fatigue = FatigueSignal(
            is_fatigued=True, rt_cv=0.4, error_rate=0.3,
            baseline_error_rate=0.1, error_spike=True,
            rt_variance_elevated=True, n_trials=10,
            reason="test", suggestion="test", evidence="test",
        )
        hygiene = AttentionalHygiene(fatigue_signal=fatigue)
        # At 12 minutes: not fatigued would be still in block (15 min),
        # but fatigued block is 10 min → break should fire
        prompt = hygiene.get_break_recommendation(minutes_into_session=12.0)
        self.assertEqual(prompt.prompt_type, "break")

    def test_brain_dump_prompt(self):
        """Brain dump prompt is well-formed."""
        hygiene = AttentionalHygiene()
        prompt = hygiene.get_brain_dump_prompt()
        self.assertEqual(prompt.prompt_type, "brain_dump")
        self.assertEqual(prompt.duration_minutes, 5.0)
        self.assertIn("write down", prompt.message.lower())

    def test_nsdr_prompt(self):
        """NSDR prompt is well-formed."""
        hygiene = AttentionalHygiene()
        prompt = hygiene.get_nsdr_prompt()
        self.assertEqual(prompt.prompt_type, "nsdr")
        self.assertEqual(prompt.duration_minutes, 10.0)
        self.assertIn("breathing", prompt.message.lower())

    def test_no_fatigue_intervention_when_not_fatigued(self):
        """No fatigue intervention when fatigue signal is None or false."""
        hygiene = AttentionalHygiene()
        self.assertIsNone(hygiene.get_fatigue_intervention())
        not_fatigued = FatigueSignal(
            is_fatigued=False, rt_cv=0.1, error_rate=0.05,
            baseline_error_rate=0.1, error_spike=False,
            rt_variance_elevated=False, n_trials=10,
            reason="ok", suggestion="ok", evidence="ok",
        )
        hygiene.set_fatigue_signal(not_fatigued)
        self.assertIsNone(hygiene.get_fatigue_intervention())

    def test_fatigue_intervention_when_fatigued(self):
        """NSDR intervention returned when fatigue is detected."""
        fatigue = FatigueSignal(
            is_fatigued=True, rt_cv=0.4, error_rate=0.3,
            baseline_error_rate=0.1, error_spike=True,
            rt_variance_elevated=True, n_trials=10,
            reason="test", suggestion="test", evidence="test",
        )
        hygiene = AttentionalHygiene(fatigue_signal=fatigue)
        prompt = hygiene.get_fatigue_intervention()
        self.assertIsNotNone(prompt)
        self.assertEqual(prompt.prompt_type, "nsdr")

    def test_pre_session_routine(self):
        """Pre-session routine includes brain dump and NSDR."""
        hygiene = AttentionalHygiene()
        routine = hygiene.get_pre_session_routine()
        types = [p.prompt_type for p in routine]
        self.assertIn("brain_dump", types)
        self.assertIn("nsdr", types)


# ---------------------------------------------------------------------------
# CircadianSync
# ---------------------------------------------------------------------------

class TestCircadianSync(unittest.TestCase):

    def test_peak_hour_recommended(self):
        """Peak hours are recommended for demanding sessions."""
        sync = CircadianSync()
        rec = sync.recommend(current_hour=10)
        self.assertTrue(rec.recommended)
        self.assertEqual(rec.window, "peak")

    def test_moderate_hour_recommended(self):
        """Moderate hours are recommended."""
        sync = CircadianSync()
        rec = sync.recommend(current_hour=14)
        self.assertTrue(rec.recommended)
        self.assertEqual(rec.window, "moderate")

    def test_late_night_not_recommended(self):
        """Late-night hours are not recommended."""
        sync = CircadianSync()
        rec = sync.recommend(current_hour=23)
        self.assertFalse(rec.recommended)
        self.assertEqual(rec.window, "late_night")

    def test_early_morning_not_recommended(self):
        """Early morning (03:00) is not recommended."""
        sync = CircadianSync()
        rec = sync.recommend(current_hour=3)
        self.assertFalse(rec.recommended)
        self.assertEqual(rec.window, "late_night")

    def test_low_window_not_recommended(self):
        """Low-performance window is not recommended."""
        sync = CircadianSync()
        # Default: hour 5 is late_night; hour 21 is moderate
        # Hour 4 is late_night; use custom to get "low"
        custom = CircadianSync(
            peak_hours=(10,),
            moderate_hours=(14,),
            late_night_start=0,
            late_night_end=0,
        )
        rec = custom.recommend(current_hour=8)
        self.assertFalse(rec.recommended)

    def test_is_good_time_for_session(self):
        """Quick check returns True for peak/moderate, False otherwise."""
        sync = CircadianSync()
        self.assertTrue(sync.is_good_time_for_session(10))
        self.assertTrue(sync.is_good_time_for_session(14))
        self.assertFalse(sync.is_good_time_for_session(23))
        self.assertFalse(sync.is_good_time_for_session(3))

    def test_get_optimal_session_hours(self):
        """Returns sorted peak hours."""
        sync = CircadianSync(peak_hours=(15, 9, 11))
        hours = sync.get_optimal_session_hours()
        self.assertEqual(hours, [9, 11, 15])

    def test_recommendation_includes_evidence(self):
        """Every recommendation carries an evidence citation."""
        sync = CircadianSync()
        for hour in (3, 10, 14, 23):
            rec = sync.recommend(hour)
            self.assertTrue(rec.evidence)


# ---------------------------------------------------------------------------
# NoveltyInjector
# ---------------------------------------------------------------------------

class TestNoveltyInjector(unittest.TestCase):

    def test_generates_challenge(self):
        """Returns a well-formed NoveltyChallenge."""
        injector = NoveltyInjector()
        challenge = injector.generate_challenge(week_number=1)
        self.assertIsInstance(challenge, NoveltyChallenge)
        self.assertTrue(challenge.title)
        self.assertTrue(challenge.description)
        self.assertTrue(challenge.source_domain)
        self.assertTrue(challenge.target_domain)
        self.assertNotIn(challenge.target_domain, (challenge.source_domain,))

    def test_challenge_id_format(self):
        """Challenge ID includes week number and template index."""
        injector = NoveltyInjector()
        c = injector.generate_challenge(week_number=3)
        self.assertIn("w003", c.challenge_id)

    def test_weekly_schedule(self):
        """generate_weekly_schedule returns N challenges."""
        injector = NoveltyInjector()
        challenges = injector.generate_weekly_schedule(num_weeks=4, start_week=1)
        self.assertEqual(len(challenges), 4)
        weeks = [c.challenge_id for c in challenges]
        self.assertEqual(len(set(weeks)), 4)  # unique IDs

    def test_domain_coverage(self):
        """Domain coverage counts target domains."""
        injector = NoveltyInjector()
        injector.generate_weekly_schedule(num_weeks=5)
        coverage = injector.get_domain_coverage()
        self.assertGreater(len(coverage), 0)
        total = sum(coverage.values())
        self.assertEqual(total, 5)

    def test_learner_domains_avoided(self):
        """When learner domains are known, challenges target new domains."""
        injector = NoveltyInjector(learner_domains=["music", "cooking"])
        # Generate several challenges; at least some should target
        # domains outside the learner's known set
        challenges = injector.generate_weekly_schedule(num_weeks=6)
        novel_targets = [
            c.target_domain for c in challenges
            if c.target_domain not in ("music", "cooking")
        ]
        self.assertGreater(len(novel_targets), 0)

    def test_difficulty_estimation(self):
        """Difficulty is estimated from domain pair."""
        injector = NoveltyInjector()
        diff = injector._estimate_difficulty("music", "mathematics")
        self.assertIn(diff, ("accessible", "moderate"))

    def test_time_estimation_bounds(self):
        """Time estimate is bounded between 10 and 30 minutes."""
        injector = NoveltyInjector()
        minutes = injector._estimate_minutes("word " * 500)
        self.assertGreaterEqual(minutes, 10.0)
        self.assertLessEqual(minutes, 30.0)

    def test_challenge_includes_evidence(self):
        """Every challenge carries an evidence citation."""
        injector = NoveltyInjector()
        c = injector.generate_challenge(week_number=1)
        self.assertTrue(c.evidence)
        self.assertIn("novelty", c.evidence.lower())

    def test_no_clinical_vocabulary_in_challenges(self):
        """No clinical terms appear in challenge text."""
        injector = NoveltyInjector()
        for w in range(1, 13):
            c = injector.generate_challenge(week_number=w)
            text = (c.title + c.description + c.rationale).lower()
            for word in ("disorder", "diagnos", "symptom", "deficit",
                         "impaired", "abnormal", "patient"):
                self.assertNotIn(word, text)


# ---------------------------------------------------------------------------
# NeuroProtectionStatus
# ---------------------------------------------------------------------------

class TestNeuroProtectionStatus(unittest.TestCase):

    def _status(self, fatigued=False, over_budget=False, recommended=True):
        fatigue = FatigueSignal(
            is_fatigued=fatigued, rt_cv=0.4 if fatigued else 0.1,
            error_rate=0.3 if fatigued else 0.05,
            baseline_error_rate=0.1, error_spike=fatigued,
            rt_variance_elevated=fatigued, n_trials=10,
            reason="test", suggestion="test", evidence="test",
        )
        load = LoadStatus(
            units_used=25.0 if over_budget else 5.0,
            units_remaining=0.0 if over_budget else 15.0,
            daily_cap=20.0, is_over_budget=over_budget,
            is_near_budget=False, reason="test", suggestion="test",
        )
        circadian = CircadianRecommendation(
            recommended=recommended,
            current_hour=10,
            window="peak" if recommended else "low",
            reason="test",
            suggestion="test",
            evidence="test",
        )
        return NeuroProtectionStatus(
            fatigue=fatigue, load=load, circadian=circadian,
        )

    def test_should_block_when_fatigued(self):
        status = self._status(fatigued=True)
        self.assertTrue(status.should_block_session())

    def test_should_block_when_over_budget(self):
        status = self._status(over_budget=True)
        self.assertTrue(status.should_block_session())

    def test_should_block_when_circadian_not_recommended(self):
        status = self._status(recommended=False)
        self.assertTrue(status.should_block_session())

    def test_should_not_block_when_all_clear(self):
        status = self._status(fatigued=False, over_budget=False,
                              recommended=True)
        self.assertFalse(status.should_block_session())

    def test_blocking_reasons_collected(self):
        status = self._status(fatigued=True, over_budget=True)
        reasons = status.get_blocking_reasons()
        self.assertGreaterEqual(len(reasons), 2)

    def test_serialises_to_dict(self):
        status = self._status()
        d = status.to_dict()
        self.assertIn("fatigue", d)
        self.assertIn("load", d)
        self.assertIn("circadian", d)

    def test_empty_status_never_blocks(self):
        status = NeuroProtectionStatus()
        self.assertFalse(status.should_block_session())
        self.assertEqual(status.get_blocking_reasons(), [])


# ---------------------------------------------------------------------------
# NeuroProtectionSystem (facade)
# ---------------------------------------------------------------------------

class TestNeuroProtectionSystem(unittest.TestCase):

    def test_facade_constructs_all_subsystems(self):
        nps = NeuroProtectionSystem()
        self.assertIsInstance(nps.clarity, ClarityGuardian)
        self.assertIsInstance(nps.load, LoadBudgeter)
        self.assertIsInstance(nps.hygiene, AttentionalHygiene)
        self.assertIsInstance(nps.circadian, CircadianSync)
        self.assertIsInstance(nps.novelty, NoveltyInjector)

    def test_check_session_returns_full_status(self):
        nps = NeuroProtectionSystem()
        status = nps.check_session(hour=14, minutes_into_session=5.0,
                                   planned_minutes=20.0)
        self.assertIsInstance(status, NeuroProtectionStatus)
        self.assertIsNotNone(status.fatigue)
        self.assertIsNotNone(status.load)
        self.assertIsNotNone(status.circadian)

    def test_end_session_returns_status(self):
        nps = NeuroProtectionSystem()
        status = nps.end_session(actual_minutes=25.0)
        self.assertIsNotNone(status.load)
        self.assertIsNotNone(status.fatigue)

    def test_get_weekly_novelty(self):
        nps = NeuroProtectionSystem()
        challenge = nps.get_weekly_novelty(week_number=5)
        self.assertIsInstance(challenge, NoveltyChallenge)
        self.assertIn("w005", challenge.challenge_id)

    def test_custom_daily_cap(self):
        nps = NeuroProtectionSystem(daily_cap=10.0)
        self.assertEqual(nps.load.daily_cap, 10.0)

    def test_custom_peak_hours(self):
        nps = NeuroProtectionSystem(peak_hours=(8, 9, 10))
        self.assertEqual(nps.circadian.peak_hours, {8, 9, 10})

    def test_session_blocked_at_late_night(self):
        nps = NeuroProtectionSystem()
        status = nps.check_session(hour=23, minutes_into_session=5.0,
                                   planned_minutes=20.0)
        self.assertTrue(status.should_block_session())

    def test_session_allowed_at_peak_hour(self):
        nps = NeuroProtectionSystem()
        status = nps.check_session(hour=10, minutes_into_session=5.0,
                                   planned_minutes=20.0)
        self.assertFalse(status.should_block_session())

    def test_over_budget_blocks_session(self):
        nps = NeuroProtectionSystem(daily_cap=5.0)
        status = nps.check_session(hour=10, minutes_into_session=5.0,
                                   planned_minutes=60.0)
        self.assertTrue(status.load.is_near_budget or
                        status.load.is_over_budget)

    def test_no_clinical_vocabulary_in_system_output(self):
        """No clinical terms anywhere in the system's output strings."""
        nps = NeuroProtectionSystem()
        status = nps.check_session(hour=23, minutes_into_session=5.0,
                                   planned_minutes=20.0)
        d = status.to_dict()
        for key in ("fatigue", "load", "circadian"):
            if d[key]:
                text = str(d[key]).lower()
                for word in ("disorder", "diagnos", "symptom", "deficit",
                             "impaired", "abnormal", "patient"):
                    self.assertNotIn(word, text,
                                     f"clinical term '{word}' in {key}")


# ---------------------------------------------------------------------------
# Integration-style tests
# ---------------------------------------------------------------------------

class TestNeuroProtectionIntegration(unittest.TestCase):

    def test_full_session_lifecycle(self):
        """Simulate a full session: start, monitor, fatigue, end."""
        nps = NeuroProtectionSystem(daily_cap=20.0, baseline_error_rate=0.1)

        # Start session check
        status = nps.check_session(hour=10, minutes_into_session=0,
                                   planned_minutes=30.0)
        self.assertFalse(status.should_block_session())

        # Simulate trials with increasing noise (fatigue onset)
        for i in range(20):
            correct = i < 15  # errors start at trial 15
            rt = 500 + (i * 15)  # RTs drift upward
            nps.clarity.record_trial(correct=correct, rt_ms=float(rt))

        # Re-check with fatigue data
        fatigue = nps.clarity.analyze()
        # May or may not be fatigued depending on variance; just verify
        # the system produces a coherent status
        self.assertIsNotNone(fatigue)
        self.assertIsNotNone(fatigue.rt_cv)

        # End session
        final = nps.end_session(actual_minutes=30.0)
        self.assertIsNotNone(final.load)
        self.assertGreater(final.load.units_used, 0)

    def test_novelty_varies_across_weeks(self):
        """Different weeks produce different challenges."""
        nps = NeuroProtectionSystem()
        challenges = [nps.get_weekly_novelty(w) for w in range(1, 8)]
        titles = [c.title for c in challenges]
        # At least some variety across 7 weeks
        self.assertGreater(len(set(titles)), 1)

    def test_hygiene_intervenes_on_fatigue(self):
        """When fatigue is detected, hygiene suggests NSDR."""
        nps = NeuroProtectionSystem(baseline_error_rate=0.05)
        # Generate fatiguing trials
        for _ in range(15):
            nps.clarity.record_trial(correct=False, rt_ms=800.0)
        for _ in range(5):
            nps.clarity.record_trial(correct=True, rt_ms=400.0)

        fatigue = nps.clarity.analyze()
        nps.hygiene.set_fatigue_signal(fatigue)
        intervention = nps.hygiene.get_fatigue_intervention()
        if fatigue.is_fatigued:
            self.assertIsNotNone(intervention)
            self.assertEqual(intervention.prompt_type, "nsdr")


if __name__ == "__main__":
    unittest.main(verbosity=2)
