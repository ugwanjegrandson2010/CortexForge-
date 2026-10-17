"""Session architecture tests: SessionRunner, ZullCycle, SessionTemplate,
ReflectionPrompt, ForethoughtPrompt."""

import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.session import (  # noqa: E402
    FORETHOUGHT_PROMPTS,
    REFLECTION_PROMPTS,
    STAGE_SPECS,
    STAGE_SPECS_BY_NAME,
    ForethoughtPrompt,
    ReflectionPrompt,
    SessionAttempt,
    SessionConfig,
    SessionEvent,
    SessionRunner,
    SessionTemplate,
    SessionType,
    StageName,
    StageSpec,
    ZullCycle,
    ZullPhase,
    get_forethought_prompts,
    get_reflection_prompts,
)
from cortexforge.scheduler import Card, build_queue, retention_forecast  # noqa: E402
from cortexforge.tracing import BKTSkill, BKTParams, Item, calibration_stats  # noqa: E402
from cortexforge.questiongen import Question  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_card(qid: str, state: str = "review", stability: float = 5.0,
               difficulty: float = 5.0, due_day: float = 0.0) -> Card:
    """Create a card with specific state for testing."""
    c = Card(qid)
    c.state = state
    c.stability = stability
    c.difficulty = difficulty
    c.due_day = due_day
    c.last_review_day = 0.0
    return c


def _make_question(qid: str, style: str = "cloze", bloom: str = "remember",
                   skill_id: str = "test_skill", difficulty_hint: float = 0.0,
                   source_span: str = "A test source span that is long enough.") -> Question:
    """Create a question for testing."""
    return Question(
        qid=qid, style=style, prompt=f"Test prompt for {qid}",
        answer="test answer", source_span=source_span,
        skill_id=skill_id, grading="fuzzy", bloom=bloom,
        difficulty_hint=difficulty_hint,
    )


# ---------------------------------------------------------------------------
# ZullCycle tests
# ---------------------------------------------------------------------------

class TestZullCycle(unittest.TestCase):
    def setUp(self):
        self.cycle = ZullCycle()

    def test_four_phases_in_order(self):
        phases = self.cycle.phases()
        self.assertEqual(len(phases), 4)
        self.assertEqual(phases[0], ZullPhase.EXPERIENCE)
        self.assertEqual(phases[1], ZullPhase.REFLECT)
        self.assertEqual(phases[2], ZullPhase.CREATE)
        self.assertEqual(phases[3], ZullPhase.ACT)

    def test_next_phase_wraps(self):
        self.assertEqual(self.cycle.next_phase(ZullPhase.ACT),
                         ZullPhase.EXPERIENCE)

    def test_next_phase_sequential(self):
        self.assertEqual(self.cycle.next_phase(ZullPhase.EXPERIENCE),
                         ZullPhase.REFLECT)
        self.assertEqual(self.cycle.next_phase(ZullPhase.REFLECT),
                         ZullPhase.CREATE)
        self.assertEqual(self.cycle.next_phase(ZullPhase.CREATE),
                         ZullPhase.ACT)

    def test_descriptions_present(self):
        for phase in self.cycle.phases():
            desc = self.cycle.description(phase)
            self.assertTrue(desc)
            self.assertGreater(len(desc), 20)

    def test_strategies_present(self):
        for phase in self.cycle.phases():
            strategies = self.cycle.strategies(phase)
            self.assertGreater(len(strategies), 0)
            for s in strategies:
                self.assertGreater(len(s), 10)

    def test_stages_for_phase(self):
        """Each Zull phase maps to at least one session stage."""
        for phase in self.cycle.phases():
            stages = self.cycle.stages_for_phase(phase)
            self.assertGreater(len(stages), 0,
                               f"Phase {phase} has no stages")

    def test_experience_maps_to_launch_and_hook(self):
        stages = self.cycle.stages_for_phase(ZullPhase.EXPERIENCE)
        self.assertIn(StageName.LAUNCH, stages)
        self.assertIn(StageName.EPISODIC_HOOK, stages)

    def test_reflect_maps_to_retrieval_and_close(self):
        stages = self.cycle.stages_for_phase(ZullPhase.REFLECT)
        self.assertIn(StageName.DAILY_RETRIEVAL, stages)
        self.assertIn(StageName.CONFIDENCE_RATED_CLOSE, stages)

    def test_create_maps_to_guided_construction(self):
        stages = self.cycle.stages_for_phase(ZullPhase.CREATE)
        self.assertIn(StageName.GUIDED_CONSTRUCTION, stages)

    def test_act_maps_to_active_testing(self):
        stages = self.cycle.stages_for_phase(ZullPhase.ACT)
        self.assertIn(StageName.ACTIVE_TESTING, stages)

    def test_to_dict(self):
        d = self.cycle.to_dict()
        self.assertIn("phases", d)
        self.assertIn("descriptions", d)
        self.assertIn("strategies", d)
        self.assertEqual(len(d["phases"]), 4)

    def test_all_phase_values_are_valid(self):
        """Phase values match the stage zull_phase strings."""
        for spec in STAGE_SPECS:
            self.assertIn(spec.zull_phase, [p.value for p in ZullPhase])


# ---------------------------------------------------------------------------
# SessionTemplate tests
# ---------------------------------------------------------------------------

class TestSessionTemplate(unittest.TestCase):
    def test_default_template_has_6_stages(self):
        t = SessionTemplate()
        self.assertEqual(len(t.stages), 6)

    def test_stage_order_canonical(self):
        t = SessionTemplate()
        names = t.stage_names()
        self.assertEqual(names, [
            StageName.LAUNCH,
            StageName.DAILY_RETRIEVAL,
            StageName.EPISODIC_HOOK,
            StageName.GUIDED_CONSTRUCTION,
            StageName.ACTIVE_TESTING,
            StageName.CONFIDENCE_RATED_CLOSE,
        ])

    def test_total_duration_computed(self):
        t = SessionTemplate()
        expected = sum(s.duration_max for s in STAGE_SPECS)
        self.assertEqual(t.total_duration_min, expected)

    def test_each_session_type_builds(self):
        for st in SessionType:
            t = SessionTemplate.for_type(st)
            self.assertEqual(len(t.stages), 6)
            self.assertEqual(t.session_type, st)

    def test_review_reorders_stages(self):
        t = SessionTemplate.for_type(SessionType.REVIEW)
        names = t.stage_names()
        # Review should emphasise retrieval: Daily Retrieval before Active Testing
        self.assertLess(names.index(StageName.DAILY_RETRIEVAL),
                        names.index(StageName.ACTIVE_TESTING))

    def test_checkup_emphasises_testing_and_close(self):
        t = SessionTemplate.for_type(SessionType.CHECKUP)
        names = t.stage_names()
        # Checkup should have Active Testing and Confidence-Rated Close early
        self.assertLess(names.index(StageName.ACTIVE_TESTING),
                        names.index(StageName.GUIDED_CONSTRUCTION))

    def test_reflection_reorders_stages(self):
        t = SessionTemplate.for_type(SessionType.REFLECTION)
        names = t.stage_names()
        # Reflection should emphasise close and hook
        self.assertIn(StageName.CONFIDENCE_RATED_CLOSE, names)
        self.assertIn(StageName.EPISODIC_HOOK, names)

    def test_stage_lookup(self):
        t = SessionTemplate()
        spec = t.stage(StageName.LAUNCH)
        self.assertEqual(spec.name, StageName.LAUNCH)
        self.assertEqual(spec.label, "Launch")

    def test_stage_specs_immutable(self):
        """Stage specs are frozen dataclasses — cannot be mutated."""
        spec = STAGE_SPECS_BY_NAME[StageName.LAUNCH]
        with self.assertRaises(AttributeError):
            spec.duration_min = 99

    def test_all_stages_have_zull_phase(self):
        for spec in STAGE_SPECS:
            self.assertIn(spec.zull_phase,
                          [p.value for p in ZullPhase],
                          f"Stage {spec.name} has invalid zull_phase")

    def test_to_dict(self):
        t = SessionTemplate()
        d = t.to_dict()
        self.assertIn("session_type", d)
        self.assertIn("stages", d)
        self.assertIn("total_duration_min", d)
        self.assertEqual(len(d["stages"]), 6)

    def test_each_template_has_all_stage_names(self):
        """Every template (regardless of type) must contain all 6 stages."""
        for st in SessionType:
            t = SessionTemplate.for_type(st)
            self.assertEqual(set(t.stage_names()), set(StageName),
                             f"{st.value} template missing stages")


# ---------------------------------------------------------------------------
# StageSpec tests
# ---------------------------------------------------------------------------

class TestStageSpec(unittest.TestCase):
    def test_stage_spec_fields(self):
        spec = StageSpec(
            name=StageName.LAUNCH,
            label="Launch",
            duration_min=2, duration_max=2,
            purpose="Test purpose",
            zull_phase="Experience",
        )
        self.assertEqual(spec.name, StageName.LAUNCH)
        self.assertEqual(spec.label, "Launch")
        self.assertEqual(spec.duration_min, 2)
        self.assertEqual(spec.duration_max, 2)

    def test_stage_spec_to_dict(self):
        spec = STAGE_SPECS_BY_NAME[StageName.LAUNCH]
        d = spec.to_dict()
        self.assertIn("name", d)
        self.assertIn("label", d)
        self.assertIn("duration_min", d)
        self.assertIn("duration_max", d)
        self.assertIn("purpose", d)
        self.assertIn("zull_phase", d)

    def test_all_stage_specs_have_purpose(self):
        for spec in STAGE_SPECS:
            self.assertTrue(spec.purpose,
                            f"Stage {spec.name} has no purpose")

    def test_all_stage_specs_have_valid_durations(self):
        for spec in STAGE_SPECS:
            self.assertGreaterEqual(spec.duration_min, 1,
                                    f"Stage {spec.name} duration_min too small")
            self.assertGreaterEqual(spec.duration_max, spec.duration_min,
                                    f"Stage {spec.name} duration_max < duration_min")


# ---------------------------------------------------------------------------
# ForethoughtPrompt tests
# ---------------------------------------------------------------------------

class TestForethoughtPrompt(unittest.TestCase):
    def test_forethought_prompt_fields(self):
        p = ForethoughtPrompt("id1", "task_analysis", "Test prompt text")
        self.assertEqual(p.prompt_id, "id1")
        self.assertEqual(p.category, "task_analysis")
        self.assertEqual(p.text, "Test prompt text")

    def test_forethought_prompt_to_dict(self):
        p = ForethoughtPrompt("id1", "task_analysis", "Test prompt text")
        d = p.to_dict()
        self.assertIn("prompt_id", d)
        self.assertIn("category", d)
        self.assertIn("text", d)

    def test_get_forethought_prompts_all_types(self):
        """Every session type must have forethought prompts."""
        for st in SessionType:
            prompts = get_forethought_prompts(st)
            self.assertGreater(len(prompts), 0,
                               f"No forethought prompts for {st.value}")

    def test_get_forethought_prompts_by_category(self):
        prompts = get_forethought_prompts(SessionType.PRACTICE,
                                          category="task_analysis")
        self.assertGreater(len(prompts), 0)
        for p in prompts:
            self.assertEqual(p.category, "task_analysis")

    def test_get_forethought_prompts_self_motivation(self):
        prompts = get_forethought_prompts(SessionType.PRACTICE,
                                          category="self_motivation")
        self.assertGreater(len(prompts), 0)
        for p in prompts:
            self.assertEqual(p.category, "self_motivation")

    def test_forethought_prompts_have_unique_ids(self):
        all_prompts = []
        for st in SessionType:
            all_prompts.extend(get_forethought_prompts(st))
        ids = [p.prompt_id for p in all_prompts]
        self.assertEqual(len(ids), len(set(ids)),
                         "Duplicate forethought prompt IDs")

    def test_forethought_prompts_meaningful_text(self):
        """Prompts must be substantive, not placeholders."""
        for st in SessionType:
            for p in get_forethought_prompts(st):
                self.assertGreater(len(p.text), 20,
                                   f"Prompt {p.prompt_id} too short")

    def test_forethought_prompt_stage_default(self):
        p = ForethoughtPrompt("id", "task_analysis", "text")
        self.assertEqual(p.stage, StageName.LAUNCH)

    def test_forethought_prompt_bank_complete(self):
        """Both categories must have prompts for all session types."""
        for st in SessionType:
            for cat in ("task_analysis", "self_motivation"):
                self.assertIn((cat, st), FORETHOUGHT_PROMPTS,
                              f"Missing forethought prompts for {cat}/{st.value}")


# ---------------------------------------------------------------------------
# ReflectionPrompt tests
# ---------------------------------------------------------------------------

class TestReflectionPrompt(unittest.TestCase):
    def test_reflection_prompt_fields(self):
        p = ReflectionPrompt("id1", "self_evaluation", "Test prompt text")
        self.assertEqual(p.prompt_id, "id1")
        self.assertEqual(p.category, "self_evaluation")
        self.assertEqual(p.text, "Test prompt text")

    def test_reflection_prompt_to_dict(self):
        p = ReflectionPrompt("id1", "self_evaluation", "Test prompt text")
        d = p.to_dict()
        self.assertIn("prompt_id", d)
        self.assertIn("category", d)
        self.assertIn("text", d)

    def test_get_reflection_prompts_all_types(self):
        """Every session type must have reflection prompts."""
        for st in SessionType:
            prompts = get_reflection_prompts(st)
            self.assertGreater(len(prompts), 0,
                               f"No reflection prompts for {st.value}")

    def test_get_reflection_prompts_by_category(self):
        prompts = get_reflection_prompts(SessionType.PRACTICE,
                                         category="self_evaluation")
        self.assertGreater(len(prompts), 0)
        for p in prompts:
            self.assertEqual(p.category, "self_evaluation")

    def test_get_reflection_prompts_all_categories(self):
        """All three SRL reflection categories must be covered."""
        for cat in ("self_evaluation", "attribution", "adaptivity"):
            prompts = get_reflection_prompts(SessionType.PRACTICE,
                                             category=cat)
            self.assertGreater(len(prompts), 0,
                               f"No prompts for category {cat}")

    def test_reflection_prompts_have_unique_ids(self):
        all_prompts = []
        for st in SessionType:
            all_prompts.extend(get_reflection_prompts(st))
        ids = [p.prompt_id for p in all_prompts]
        self.assertEqual(len(ids), len(set(ids)),
                         "Duplicate reflection prompt IDs")

    def test_reflection_prompts_meaningful_text(self):
        for st in SessionType:
            for p in get_reflection_prompts(st):
                self.assertGreater(len(p.text), 20,
                                   f"Prompt {p.prompt_id} too short")

    def test_reflection_prompt_stage_default(self):
        p = ReflectionPrompt("id", "self_evaluation", "text")
        self.assertEqual(p.stage, StageName.CONFIDENCE_RATED_CLOSE)

    def test_reflection_prompt_bank_complete(self):
        """All three categories must have prompts for all session types."""
        for st in SessionType:
            for cat in ("self_evaluation", "attribution", "adaptivity"):
                self.assertIn((cat, st), REFLECTION_PROMPTS,
                              f"Missing reflection prompts for {cat}/{st.value}")


# ---------------------------------------------------------------------------
# SessionRunner tests
# ---------------------------------------------------------------------------

class TestSessionRunner(unittest.TestCase):
    def _make_runner(self, session_type=SessionType.PRACTICE, **kwargs):
        config = SessionConfig(
            learner_id="test_learner",
            session_type=session_type,
            day=0.0,
            limit=10,
            target_success_rate=0.85,
            rng_seed=42,
            **kwargs,
        )
        return SessionRunner(config)

    def test_start_returns_session_info(self):
        runner = self._make_runner()
        info = runner.start()
        self.assertEqual(info["session_type"], "practice")
        self.assertIn("template", info)
        self.assertIn("forethought_prompts", info)
        self.assertEqual(info["total_stages"], 6)

    def test_start_generates_forethought_prompts(self):
        runner = self._make_runner()
        info = runner.start()
        self.assertGreater(len(info["forethought_prompts"]), 0)

    def test_start_without_forethought(self):
        runner = self._make_runner(enable_forethought=False)
        info = runner.start()
        self.assertEqual(len(info["forethought_prompts"]), 0)

    def test_enter_stage(self):
        runner = self._make_runner()
        runner.start()
        result = runner.enter_stage(StageName.LAUNCH)
        self.assertEqual(result["stage"], "launch")
        self.assertEqual(result["label"], "Launch")
        self.assertIn("zull_phase", result)
        self.assertIn("zull_strategies", result)
        self.assertGreater(len(result["zull_strategies"]), 0)

    def test_enter_launch_shows_forethought_prompts(self):
        runner = self._make_runner()
        runner.start()
        result = runner.enter_stage(StageName.LAUNCH)
        self.assertIn("forethought_prompts", result)
        self.assertGreater(len(result["forethought_prompts"]), 0)

    def test_enter_close_shows_reflection_prompts(self):
        runner = self._make_runner()
        runner.start()
        result = runner.enter_stage(StageName.CONFIDENCE_RATED_CLOSE)
        self.assertIn("reflection_prompts", result)
        self.assertGreater(len(result["reflection_prompts"]), 0)

    def test_exit_stage(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.LAUNCH)
        time.sleep(0.01)  # ensure measurable elapsed time
        result = runner.exit_stage(StageName.LAUNCH)
        self.assertEqual(result["stage"], "launch")
        self.assertIn("elapsed_seconds", result)
        self.assertGreater(result["elapsed_seconds"], 0)

    def test_build_retrieval_queue(self):
        runner = self._make_runner()
        runner.start()
        cards = [
            _make_card("q1", state="review", stability=5.0, due_day=0.0),
            _make_card("q2", state="review", stability=3.0, due_day=1.0),
            _make_card("q3", state="new"),
        ]
        queue = runner.build_retrieval_queue(cards)
        self.assertGreater(len(queue), 0)
        # Due items should come first
        self.assertEqual(queue[0].item_id, "q1")

    def test_next_retrieval_item(self):
        runner = self._make_runner()
        runner.start()
        cards = [
            _make_card("q1", state="review", stability=5.0, due_day=0.0),
            _make_card("q2", state="review", stability=3.0, due_day=0.0),
        ]
        runner.build_retrieval_queue(cards)
        item1 = runner.next_retrieval_item()
        self.assertIsNotNone(item1)
        self.assertEqual(item1.item_id, "q1")
        item2 = runner.next_retrieval_item()
        self.assertIsNotNone(item2)
        self.assertEqual(item2.item_id, "q2")
        item3 = runner.next_retrieval_item()
        self.assertIsNone(item3)

    def test_record_attempt(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        attempt = runner.record_attempt(
            qid="q1", skill_id="sk1", correct=True,
            grade=3, confidence=0.8, latency_ms=5000,
            response="my answer",
        )
        self.assertEqual(attempt.qid, "q1")
        self.assertTrue(attempt.correct)
        self.assertEqual(attempt.grade, 3)
        self.assertEqual(attempt.confidence, 0.8)
        self.assertEqual(attempt.stage, StageName.DAILY_RETRIEVAL)
        self.assertEqual(len(runner.attempts), 1)

    def test_get_calibration_empty(self):
        runner = self._make_runner()
        cal = runner.get_calibration()
        self.assertEqual(cal["n"], 0)

    def test_get_calibration_with_attempts(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        runner.record_attempt("q1", "sk1", True, 3, 0.9, 3000, "a")
        runner.record_attempt("q2", "sk1", False, 1, 0.2, 5000, "b")
        cal = runner.get_calibration()
        self.assertEqual(cal["n"], 2)
        self.assertIn("brier", cal)
        self.assertIn("bias", cal)

    def test_get_session_summary_empty(self):
        runner = self._make_runner()
        summary = runner.get_session_summary()
        self.assertEqual(summary["n"], 0)
        self.assertEqual(summary["verdict"], "no data")

    def test_get_session_summary_productive(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        # 8 correct out of 10 = 80% = productive band
        for i in range(8):
            runner.record_attempt(f"q{i}", "sk1", True, 3, 0.8, 3000, "a")
        for i in range(2):
            runner.record_attempt(f"q{i+8}", "sk1", False, 1, 0.3, 5000, "b")
        summary = runner.get_session_summary()
        self.assertEqual(summary["n"], 10)
        self.assertEqual(summary["verdict"], "in the productive band")

    def test_get_session_summary_under_challenged(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        for i in range(10):
            runner.record_attempt(f"q{i}", "sk1", True, 3, 0.9, 2000, "a")
        summary = runner.get_session_summary()
        self.assertEqual(summary["verdict"], "under-challenged")

    def test_get_session_summary_over_loaded(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        for i in range(10):
            runner.record_attempt(f"q{i}", "sk1", False, 1, 0.2, 8000, "b")
        summary = runner.get_session_summary()
        self.assertEqual(summary["verdict"], "over-loaded")

    def test_close_returns_summary(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.LAUNCH)
        runner.exit_stage(StageName.LAUNCH)
        result = runner.close()
        self.assertIn("statement", result)
        self.assertIn("reflection_prompts", result)
        self.assertGreater(len(result["reflection_prompts"]), 0)

    def test_close_without_reflection(self):
        runner = self._make_runner(enable_reflection=False)
        runner.start()
        result = runner.close()
        self.assertNotIn("reflection_prompts", result)

    def test_get_episodic_hook(self):
        runner = self._make_runner()
        questions = [
            _make_question("q1", source_span="Short."),
            _make_question("q2", source_span="A much longer source span that "
                           "provides rich contextual detail for the learner "
                           "to engage with as a concrete case study."),
        ]
        hook = runner.get_episodic_hook(questions)
        self.assertIsNotNone(hook)
        self.assertIn("question", hook)
        self.assertEqual(hook["hook_type"], "concrete_case")

    def test_get_episodic_hook_empty(self):
        runner = self._make_runner()
        hook = runner.get_episodic_hook([])
        self.assertIsNone(hook)

    def test_get_guided_steps(self):
        runner = self._make_runner()
        questions = [
            _make_question("q1", bloom="apply"),
            _make_question("q2", bloom="remember"),
            _make_question("q3", bloom="understand"),
        ]
        steps = runner.get_guided_steps(questions)
        self.assertGreater(len(steps), 0)
        # Steps should be ordered by Bloom level
        bloom_order = {"remember": 0, "understand": 1, "apply": 2,
                       "analyse": 3, "evaluate": 4, "create": 5}
        for i in range(len(steps) - 1):
            self.assertLessEqual(
                bloom_order.get(steps[i]["bloom_level"], 9),
                bloom_order.get(steps[i + 1]["bloom_level"], 9),
            )
        # Each step should have a scaffold
        for step in steps:
            self.assertIn("scaffold", step)
            self.assertTrue(step["scaffold"])

    def test_get_guided_steps_with_skill_filter(self):
        runner = self._make_runner()
        questions = [
            _make_question("q1", skill_id="math", bloom="remember"),
            _make_question("q2", skill_id="history", bloom="remember"),
            _make_question("q3", skill_id="math", bloom="apply"),
        ]
        steps = runner.get_guided_steps(questions, skill_id="math")
        self.assertEqual(len(steps), 2)
        for step in steps:
            self.assertEqual(step["question"]["skill_id"], "math")

    def test_get_active_tests(self):
        runner = self._make_runner()
        questions = [
            _make_question(f"q{i}", difficulty_hint=(i - 5) * 0.5)
            for i in range(10)
        ]
        tests = runner.get_active_tests(questions)
        self.assertGreater(len(tests), 0)
        self.assertLessEqual(len(tests), 5)
        for t in tests:
            self.assertIn("question", t)
            self.assertIn("target_p", t)
            self.assertIn("context", t)

    def test_get_active_tests_excludes_used(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        questions = [_make_question(f"q{i}") for i in range(5)]
        # Record attempts for some questions
        runner.record_attempt("q0", "sk1", True, 3, 0.8, 3000, "a")
        runner.record_attempt("q1", "sk1", True, 3, 0.8, 3000, "a")
        tests = runner.get_active_tests(questions)
        used_qids = {t["question"]["qid"] for t in tests}
        self.assertNotIn("q0", used_qids)
        self.assertNotIn("q1", used_qids)

    def test_update_skill(self):
        runner = self._make_runner()
        p1 = runner.update_skill("sk1", True)
        p2 = runner.update_skill("sk1", True)
        self.assertGreater(p2, p1)
        self.assertIn("sk1", runner._skill_states)

    def test_update_skill_multiple(self):
        runner = self._make_runner()
        skill = runner.update_skill("sk1", False)
        self.assertIn("sk1", runner._skill_states)
        self.assertGreaterEqual(skill, 0.0)
        self.assertLessEqual(skill, 1.0)

    def test_update_theta(self):
        runner = self._make_runner()
        items = [Item(f"q{i}", b=0.0) for i in range(5)]
        theta = runner.update_theta([(i, True) for i in items])
        self.assertGreater(theta, 0.0)
        self.assertEqual(runner._theta, theta)

    def test_events_logged(self):
        runner = self._make_runner()
        runner.start()
        runner.enter_stage(StageName.LAUNCH)
        runner.exit_stage(StageName.LAUNCH)
        runner.close()
        self.assertGreater(len(runner.events), 0)
        event_types = {e.event_type for e in runner.events}
        self.assertIn("session_start", event_types)
        self.assertIn("stage_enter", event_types)
        self.assertIn("stage_exit", event_types)
        self.assertIn("session_close", event_types)

    def test_to_dict(self):
        runner = self._make_runner()
        runner.start()
        d = runner.to_dict()
        self.assertIn("config", d)
        self.assertIn("template", d)
        self.assertIn("forethought_prompts", d)
        self.assertIn("reflection_prompts", d)
        self.assertEqual(d["config"]["learner_id"], "test_learner")

    def test_full_session_flow(self):
        """Integration test: run through all 6 stages."""
        runner = self._make_runner()
        info = runner.start()
        self.assertEqual(info["total_stages"], 6)

        # Stage 1: Launch
        result = runner.enter_stage(StageName.LAUNCH)
        self.assertIn("forethought_prompts", result)
        runner.exit_stage(StageName.LAUNCH)

        # Stage 2: Daily Retrieval
        result = runner.enter_stage(StageName.DAILY_RETRIEVAL)
        cards = [
            _make_card("q1", state="review", stability=5.0, due_day=0.0),
            _make_card("q2", state="review", stability=3.0, due_day=0.0),
        ]
        runner.build_retrieval_queue(cards)
        item = runner.next_retrieval_item()
        self.assertIsNotNone(item)
        runner.record_attempt("q1", "sk1", True, 3, 0.8, 3000, "a")
        runner.exit_stage(StageName.DAILY_RETRIEVAL)

        # Stage 3: Episodic Hook
        result = runner.enter_stage(StageName.EPISODIC_HOOK)
        questions = [_make_question(f"hq{i}") for i in range(3)]
        hook = runner.get_episodic_hook(questions)
        self.assertIsNotNone(hook)
        runner.exit_stage(StageName.EPISODIC_HOOK)

        # Stage 4: Guided Construction
        result = runner.enter_stage(StageName.GUIDED_CONSTRUCTION)
        steps = runner.get_guided_steps(questions)
        self.assertGreater(len(steps), 0)
        runner.exit_stage(StageName.GUIDED_CONSTRUCTION)

        # Stage 5: Active Testing
        result = runner.enter_stage(StageName.ACTIVE_TESTING)
        tests = runner.get_active_tests(questions)
        self.assertGreater(len(tests), 0)
        runner.exit_stage(StageName.ACTIVE_TESTING)

        # Stage 6: Confidence-Rated Close
        result = runner.enter_stage(StageName.CONFIDENCE_RATED_CLOSE)
        self.assertIn("reflection_prompts", result)
        summary = runner.close()
        self.assertIn("statement", summary)
        self.assertIn("reflection_prompts", summary)

    def test_session_type_review_flow(self):
        """Review session type produces correct template."""
        runner = self._make_runner(session_type=SessionType.REVIEW)
        info = runner.start()
        self.assertEqual(info["session_type"], "review")
        template = info["template"]
        self.assertEqual(template["session_type"], "review")

    def test_session_type_reflection_flow(self):
        """Reflection session type produces correct template."""
        runner = self._make_runner(session_type=SessionType.REFLECTION)
        info = runner.start()
        self.assertEqual(info["session_type"], "reflection")


# ---------------------------------------------------------------------------
# SessionEvent and SessionAttempt tests
# ---------------------------------------------------------------------------

class TestSessionEvent(unittest.TestCase):
    def test_event_creation(self):
        e = SessionEvent(
            event_type="test",
            stage=StageName.LAUNCH,
            timestamp=time.time(),
            data={"key": "value"},
        )
        self.assertEqual(e.event_type, "test")
        self.assertEqual(e.stage, StageName.LAUNCH)
        self.assertEqual(e.data["key"], "value")

    def test_event_to_dict(self):
        e = SessionEvent(
            event_type="test",
            stage=StageName.LAUNCH,
            timestamp=time.time(),
            data={"key": "value"},
        )
        d = e.to_dict()
        self.assertIn("event_type", d)
        self.assertIn("stage", d)
        self.assertIn("timestamp", d)
        self.assertIn("data", d)

    def test_event_no_stage(self):
        e = SessionEvent(
            event_type="session_start",
            stage=None,
            timestamp=time.time(),
        )
        self.assertIsNone(e.stage)


class TestSessionAttempt(unittest.TestCase):
    def test_attempt_creation(self):
        a = SessionAttempt(
            qid="q1", skill_id="sk1", correct=True,
            grade=3, confidence=0.8, latency_ms=5000,
            response="answer", stage=StageName.DAILY_RETRIEVAL,
            timestamp=time.time(),
        )
        self.assertEqual(a.qid, "q1")
        self.assertTrue(a.correct)
        self.assertEqual(a.grade, 3)

    def test_attempt_to_dict(self):
        a = SessionAttempt(
            qid="q1", skill_id="sk1", correct=True,
            grade=3, confidence=0.8, latency_ms=5000,
            response="answer", stage=StageName.DAILY_RETRIEVAL,
            timestamp=time.time(),
        )
        d = a.to_dict()
        self.assertIn("qid", d)
        self.assertIn("skill_id", d)
        self.assertIn("correct", d)
        self.assertIn("grade", d)
        self.assertIn("confidence", d)
        self.assertIn("stage", d)

    def test_attempt_no_confidence(self):
        a = SessionAttempt(
            qid="q1", skill_id="sk1", correct=False,
            grade=1, confidence=None, latency_ms=3000,
            response="answer", stage=StageName.DAILY_RETRIEVAL,
            timestamp=time.time(),
        )
        self.assertIsNone(a.confidence)


# ---------------------------------------------------------------------------
# Integration with existing modules
# ---------------------------------------------------------------------------

class TestSessionIntegration(unittest.TestCase):
    """Test that session.py integrates correctly with scheduler, tracing,
    and questiongen."""

    def test_runner_uses_fsrs_queue(self):
        """SessionRunner.build_retrieval_queue should use scheduler.build_queue."""
        config = SessionConfig("test", SessionType.PRACTICE, day=10.0)
        runner = SessionRunner(config)
        cards = []
        for i in range(5):
            c = Card(f"q{i}")
            c.review(3, 0.0)
            cards.append(c)
        queue = runner.build_retrieval_queue(cards)
        # All cards reviewed at day 0 should be due by day 10
        self.assertTrue(all(c.due_day <= 10.0 for c in queue))

    def test_runner_uses_bkt(self):
        """SessionRunner.update_skill should use BKT."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        p1 = runner.update_skill("sk1", True)
        skill = runner._skill_states["sk1"]
        self.assertIsInstance(skill, BKTSkill)
        self.assertEqual(skill.opportunities, 1)
        p2 = runner.update_skill("sk1", True)
        self.assertEqual(skill.opportunities, 2)

    def test_runner_uses_irt_selection(self):
        """SessionRunner.get_active_tests should use IRT item selection."""
        config = SessionConfig("test", target_success_rate=0.85)
        runner = SessionRunner(config)
        questions = []
        for i in range(10):
            q = Question(
                qid=f"q{i}", style="cloze", prompt="p", answer="a",
                source_span="s", difficulty_hint=(i - 5) * 0.5,
            )
            questions.append(q)
        tests = runner.get_active_tests(questions)
        self.assertGreater(len(tests), 0)
        # Selected items should be near the target success rate
        for t in tests:
            item = Item(t["question"]["qid"],
                        b=t["question"]["difficulty_hint"])
            p = item.p_correct(0.0)
            self.assertLess(p, 0.99)

    def test_runner_calibration_matches_tracing(self):
        """SessionRunner.get_calibration should match calibration_stats."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        runner.record_attempt("q1", "sk1", True, 3, 0.9, 3000, "a")
        runner.record_attempt("q2", "sk1", False, 1, 0.2, 5000, "b")
        cal = runner.get_calibration()
        # Verify against direct calibration_stats call
        direct = calibration_stats([(0.9, True), (0.2, False)])
        self.assertEqual(cal["n"], direct["n"])
        self.assertAlmostEqual(cal["brier"], direct["brier"])
        self.assertAlmostEqual(cal["bias"], direct["bias"])

    def test_guided_steps_use_question_styles(self):
        """Guided steps should generate scaffolds based on question styles."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        questions = [
            _make_question("q1", style="cloze"),
            _make_question("q2", style="definition"),
            _make_question("q3", style="true_false_justify"),
        ]
        steps = runner.get_guided_steps(questions)
        self.assertEqual(len(steps), 3)
        scaffolds = [s["scaffold"] for s in steps]
        # Each scaffold should be non-empty
        for s in scaffolds:
            self.assertTrue(s)


# ---------------------------------------------------------------------------
# SessionConfig tests
# ---------------------------------------------------------------------------

class TestSessionConfig(unittest.TestCase):
    def test_default_config(self):
        config = SessionConfig("test_learner")
        self.assertEqual(config.learner_id, "test_learner")
        self.assertEqual(config.session_type, SessionType.PRACTICE)
        self.assertEqual(config.day, 0.0)
        self.assertEqual(config.limit, 20)
        self.assertEqual(config.target_success_rate, 0.85)
        self.assertTrue(config.enable_forethought)
        self.assertTrue(config.enable_reflection)

    def test_custom_config(self):
        config = SessionConfig(
            "learner2",
            session_type=SessionType.REVIEW,
            day=5.0,
            limit=30,
            target_success_rate=0.75,
            enable_forethought=False,
            enable_reflection=False,
            rng_seed=99,
        )
        self.assertEqual(config.learner_id, "learner2")
        self.assertEqual(config.session_type, SessionType.REVIEW)
        self.assertEqual(config.day, 5.0)
        self.assertEqual(config.limit, 30)
        self.assertEqual(config.target_success_rate, 0.75)
        self.assertFalse(config.enable_forethought)
        self.assertFalse(config.enable_reflection)
        self.assertEqual(config.rng_seed, 99)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):
    def test_runner_with_no_cards(self):
        """Runner should handle empty card list gracefully."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        runner.start()
        queue = runner.build_retrieval_queue([])
        self.assertEqual(len(queue), 0)
        item = runner.next_retrieval_item()
        self.assertIsNone(item)

    def test_runner_with_empty_questions(self):
        """Runner should handle empty question list gracefully."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        hook = runner.get_episodic_hook([])
        self.assertIsNone(hook)
        steps = runner.get_guided_steps([])
        self.assertEqual(len(steps), 0)
        tests = runner.get_active_tests([])
        self.assertEqual(len(tests), 0)

    def test_runner_with_all_excluded(self):
        """get_active_tests with all questions excluded."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        questions = [_make_question("q1"), _make_question("q2")]
        runner.record_attempt("q1", "sk1", True, 3, 0.8, 3000, "a")
        runner.record_attempt("q2", "sk1", True, 3, 0.8, 3000, "a")
        tests = runner.get_active_tests(questions)
        self.assertEqual(len(tests), 0)

    def test_guided_steps_max_5(self):
        """get_guided_steps should return at most 5 steps."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        questions = [_make_question(f"q{i}") for i in range(10)]
        steps = runner.get_guided_steps(questions)
        self.assertLessEqual(len(steps), 5)

    def test_active_tests_max_5(self):
        """get_active_tests should return at most 5 tests."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        questions = [_make_question(f"q{i}") for i in range(10)]
        tests = runner.get_active_tests(questions)
        self.assertLessEqual(len(tests), 5)

    def test_session_summary_extreme_accuracy(self):
        """Session summary should handle 0% and 100% accuracy."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        # 0% accuracy
        for i in range(5):
            runner.record_attempt(f"q{i}", "sk1", False, 1, 0.1, 5000, "b")
        summary = runner.get_session_summary()
        self.assertEqual(summary["verdict"], "over-loaded")

    def test_calibration_extreme_confidence(self):
        """Calibration should handle extreme confidence values."""
        config = SessionConfig("test")
        runner = SessionRunner(config)
        runner.start()
        runner.enter_stage(StageName.DAILY_RETRIEVAL)
        runner.record_attempt("q1", "sk1", True, 3, 1.0, 1000, "a")
        runner.record_attempt("q2", "sk1", False, 1, 0.0, 1000, "b")
        cal = runner.get_calibration()
        self.assertEqual(cal["n"], 2)
        self.assertGreaterEqual(cal["brier"], 0.0)
        self.assertLessEqual(cal["brier"], 1.0)


# ---------------------------------------------------------------------------
# Session type enum tests
# ---------------------------------------------------------------------------

class TestSessionType(unittest.TestCase):
    def test_all_types_present(self):
        """All six session types from the spec must be present."""
        expected = {"practice", "review", "checkup", "homework",
                    "explore", "reflection"}
        actual = {st.value for st in SessionType}
        self.assertEqual(actual, expected)

    def test_session_type_values(self):
        self.assertEqual(SessionType.PRACTICE.value, "practice")
        self.assertEqual(SessionType.REVIEW.value, "review")
        self.assertEqual(SessionType.CHECKUP.value, "checkup")
        self.assertEqual(SessionType.HOMEWORK.value, "homework")
        self.assertEqual(SessionType.EXPLORE.value, "explore")
        self.assertEqual(SessionType.REFLECTION.value, "reflection")


if __name__ == "__main__":
    unittest.main(verbosity=2)
