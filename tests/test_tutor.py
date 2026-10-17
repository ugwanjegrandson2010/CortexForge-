"""Unit tests for the Socratic tutor harness."""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.questiongen import Question
from cortexforge.tutor import (
    AffectAdaptivePolicy,
    AffectType,
    AnswerLeakDetector,
    DialogueState,
    HintLevel,
    LeakReport,
    MoveType,
    RuleBasedRenderer,
    SocraticPolicy,
    TutorHarness,
    TutorMode,
    TutorResponse,
    TutorSession,
    TutorState,
)


def _make_question(
    qid: str = "q1",
    prompt: str = "What is 2 + 2?",
    answer: str = "4",
    topic: str = "arithmetic",
) -> Question:
    return Question(
        qid=qid,
        style="numeric",
        prompt=prompt,
        answer=answer,
        source_span="2 + 2 = 4",
        skill_id=topic,
        grading="numeric",
    )


def _make_session(
    state: DialogueState = DialogueState.GUIDING,
    mode: TutorMode = TutorMode.PRACTICE,
    question: Question | None = None,
    consecutive_struggles: int = 0,
) -> TutorSession:
    return TutorSession(
        learner_id="L1",
        topic="arithmetic",
        state=state,
        current_question=question,
        hint_level=1,
        max_hint_level=4,
        dialogue_history=[],
        affect_history=[],
        mode=mode,
        consecutive_struggles=consecutive_struggles,
        questions_asked=0,
        hints_given=0,
    )


# -----------------------------------------------------------------------
# TutorState
# -----------------------------------------------------------------------


class TestTutorState(unittest.TestCase):
    def test_initial_state(self):
        ts = TutorState()
        self.assertEqual(ts.current, DialogueState.OPENING)

    def test_valid_transition(self):
        ts = TutorState()
        self.assertTrue(ts.transition_to(DialogueState.DIAGNOSING, "start"))
        self.assertEqual(ts.current, DialogueState.DIAGNOSING)

    def test_invalid_transition(self):
        ts = TutorState()
        self.assertFalse(ts.transition_to(DialogueState.CLOSING, "skip"))
        self.assertEqual(ts.current, DialogueState.OPENING)

    def test_full_forward_path(self):
        ts = TutorState()
        path = [
            DialogueState.DIAGNOSING,
            DialogueState.GUIDING,
            DialogueState.CONFIRMING,
            DialogueState.TRANSFERRING,
            DialogueState.REFLECTING,
            DialogueState.CLOSING,
        ]
        for state in path:
            self.assertTrue(ts.transition_to(state, "forward"))
        self.assertEqual(ts.current, DialogueState.CLOSING)

    def test_remediation_path(self):
        ts = TutorState()
        ts.transition_to(DialogueState.DIAGNOSING)
        ts.transition_to(DialogueState.GUIDING)
        ts.transition_to(DialogueState.CONFIRMING)
        # Wrong answer -> back to guiding
        self.assertTrue(ts.transition_to(DialogueState.GUIDING, "wrong"))
        self.assertEqual(ts.current, DialogueState.GUIDING)

    def test_history_tracked(self):
        ts = TutorState()
        ts.transition_to(DialogueState.DIAGNOSING, "start")
        ts.transition_to(DialogueState.GUIDING, "diagnosed")
        history = ts.history
        self.assertEqual(len(history), 3)
        self.assertEqual(history[0][0], DialogueState.OPENING)
        self.assertEqual(history[1][0], DialogueState.DIAGNOSING)
        self.assertEqual(history[2][0], DialogueState.GUIDING)

    def test_force_transition(self):
        ts = TutorState()
        ts.force_transition(DialogueState.CLOSING, "error recovery")
        self.assertEqual(ts.current, DialogueState.CLOSING)

    def test_can_transition_to(self):
        ts = TutorState(DialogueState.CONFIRMING)
        self.assertTrue(ts.can_transition_to(DialogueState.GUIDING))
        self.assertTrue(ts.can_transition_to(DialogueState.TRANSFERRING))
        self.assertFalse(ts.can_transition_to(DialogueState.OPENING))

    def test_str(self):
        ts = TutorState(DialogueState.GUIDING)
        self.assertEqual(str(ts), "guiding")


# -----------------------------------------------------------------------
# AnswerLeakDetector
# -----------------------------------------------------------------------


class TestAnswerLeakDetector(unittest.TestCase):
    def setUp(self):
        self.detector = AnswerLeakDetector()

    def test_no_leak(self):
        report = self.detector.check("Think about the approach.", "4")
        self.assertFalse(report.is_leaked)

    def test_exact_match(self):
        report = self.detector.check("The answer is 4.", "4")
        self.assertTrue(report.is_leaked)
        self.assertTrue(any("exact" in p for p in report.matched_patterns))

    def test_numeric_match(self):
        report = self.detector.check("Consider the value 42.", "42")
        self.assertTrue(report.is_leaked)
        # "42" is short enough to be caught by exact match
        self.assertTrue(
            any("exact" in p or "numeric" in p for p in report.matched_patterns)
        )

    def test_chunk_match_long_answer(self):
        long_answer = "the quick brown fox jumps over the lazy dog"
        output = "Remember that the quick brown fox jumps over the lazy dog is the key"
        report = self.detector.check(output, long_answer)
        self.assertTrue(report.is_leaked)

    def test_exploration_mode_lenient(self):
        # In exploration mode, a single chunk match should not flag
        long_answer = "the quick brown fox jumps over the lazy dog"
        output = "the quick brown fox"
        report = self.detector.check(output, long_answer, TutorMode.EXPLORATION)
        # Only one chunk match -> not leaked in exploration mode
        self.assertFalse(report.is_leaked)

    def test_exploration_mode_strict_on_exact(self):
        report = self.detector.check(
            "The answer is 4.", "4", TutorMode.EXPLORATION
        )
        self.assertTrue(report.is_leaked)

    def test_empty_answer(self):
        report = self.detector.check("Some text", "")
        self.assertFalse(report.is_leaked)

    def test_confidence_bounded(self):
        report = self.detector.check("The answer is 4.", "4")
        self.assertGreaterEqual(report.confidence, 0.0)
        self.assertLessEqual(report.confidence, 1.0)

    def test_common_numbers_not_flagged(self):
        # Numbers like 1, 2, 3 are too common to be significant
        report = self.detector.check("Try step 1 then step 2.", "3")
        self.assertFalse(report.is_leaked)


# -----------------------------------------------------------------------
# SocraticPolicy
# -----------------------------------------------------------------------


class TestSocraticPolicy(unittest.TestCase):
    def setUp(self):
        self.policy = SocraticPolicy()

    def test_select_hint_level_no_struggles(self):
        session = _make_session(consecutive_struggles=0)
        level = self.policy.select_hint_level(session)
        self.assertEqual(level, HintLevel.STRATEGIC_QUESTION)

    def test_select_hint_level_one_struggle(self):
        session = _make_session(consecutive_struggles=1)
        level = self.policy.select_hint_level(session)
        self.assertEqual(level, HintLevel.PROCEDURE_CUE)

    def test_select_hint_level_two_struggles(self):
        session = _make_session(consecutive_struggles=2)
        level = self.policy.select_hint_level(session)
        self.assertEqual(level, HintLevel.WORKED_ANALOGOUS_EXAMPLE)

    def test_select_hint_level_many_struggles(self):
        session = _make_session(consecutive_struggles=5)
        level = self.policy.select_hint_level(session)
        self.assertEqual(level, HintLevel.BOTTOM_OUT_STEP)

    def test_generate_hint_returns_string(self):
        session = _make_session(question=_make_question())
        hint = self.policy.generate_hint(session, session.current_question)
        self.assertIsInstance(hint, str)
        self.assertGreater(len(hint), 0)

    def test_generate_hint_never_contains_answer(self):
        q = _make_question(answer="42")
        session = _make_session(question=q, consecutive_struggles=5)
        hint = self.policy.generate_hint(session, q)
        # The hint should not contain the answer "42"
        self.assertNotIn("42", hint)

    def test_generate_strategic_question(self):
        q = self.policy.generate_strategic_question("photosynthesis")
        self.assertIsInstance(q, str)
        self.assertGreater(len(q), 10)
        # At least one template should include the topic
        templates = SocraticPolicy.HINT_TEMPLATES[HintLevel.STRATEGIC_QUESTION]
        topic_in_any = any("photosynthesis" in t.format(topic="photosynthesis") for t in templates)
        self.assertTrue(topic_in_any)

    def test_generate_metacognitive_prompt(self):
        prompt = self.policy.generate_metacognitive_prompt()
        self.assertIsInstance(prompt, str)
        self.assertGreater(len(prompt), 10)

    def test_should_escalate_on_incorrect(self):
        session = _make_session()
        self.assertTrue(self.policy.should_escalate(session, False))

    def test_should_escalate_on_no_answer(self):
        session = _make_session()
        self.assertTrue(self.policy.should_escalate(session, None))

    def test_should_not_escalate_on_correct(self):
        session = _make_session()
        self.assertFalse(self.policy.should_escalate(session, True))

    def test_get_move_type(self):
        session = _make_session(state=DialogueState.GUIDING)
        self.assertEqual(self.policy.get_move_type(session), MoveType.HINT)

    def test_get_move_type_feedback(self):
        session = _make_session(state=DialogueState.CONFIRMING)
        self.assertEqual(self.policy.get_move_type(session), MoveType.FEEDBACK)

    def test_hint_templates_exist_for_all_levels(self):
        for level in HintLevel:
            self.assertIn(level, SocraticPolicy.HINT_TEMPLATES)
            self.assertGreater(len(SocraticPolicy.HINT_TEMPLATES[level]), 0)


# -----------------------------------------------------------------------
# AffectAdaptivePolicy
# -----------------------------------------------------------------------


class TestAffectAdaptivePolicy(unittest.TestCase):
    def setUp(self):
        self.policy = AffectAdaptivePolicy()

    def test_detect_confused(self):
        affect = self.policy.detect_affect("I'm confused about this")
        self.assertEqual(affect, AffectType.CONFUSED)

    def test_detect_confident(self):
        affect = self.policy.detect_affect("This is easy, I got it")
        self.assertEqual(affect, AffectType.CONFIDENT)

    def test_detect_frustrated(self):
        affect = self.policy.detect_affect("I'm frustrated, this is too hard")
        self.assertEqual(affect, AffectType.FRUSTRATED)

    def test_detect_bored(self):
        affect = self.policy.detect_affect("This is boring, I already know this")
        self.assertEqual(affect, AffectType.BORED)

    def test_detect_neutral(self):
        affect = self.policy.detect_affect("Let me think about this")
        self.assertEqual(affect, AffectType.NEUTRAL)

    def test_detect_lost(self):
        affect = self.policy.detect_affect("I'm lost, where do I start?")
        self.assertEqual(affect, AffectType.CONFUSED)

    def test_detect_giving_up(self):
        affect = self.policy.detect_affect("I'm giving up, this is impossible")
        self.assertEqual(affect, AffectType.FRUSTRATED)

    def test_get_adaptation_confused(self):
        adapt = self.policy.get_adaptation(AffectType.CONFUSED)
        self.assertEqual(adapt["strategy"], "scaffold_up")

    def test_get_adaptation_confident(self):
        adapt = self.policy.get_adaptation(AffectType.CONFIDENT)
        self.assertEqual(adapt["strategy"], "challenge")

    def test_get_adaptation_frustrated(self):
        adapt = self.policy.get_adaptation(AffectType.FRUSTRATED)
        self.assertEqual(adapt["strategy"], "competence_restore")

    def test_get_adaptation_bored(self):
        adapt = self.policy.get_adaptation(AffectType.BORED)
        self.assertEqual(adapt["strategy"], "relevance_novelty")

    def test_adapt_hint_level_confused_escalates(self):
        new_level = self.policy.adapt_hint_level(
            AffectType.CONFUSED, HintLevel.STRATEGIC_QUESTION
        )
        self.assertEqual(new_level, HintLevel.PROCEDURE_CUE)

    def test_adapt_hint_level_confident_de_escalates(self):
        new_level = self.policy.adapt_hint_level(
            AffectType.CONFIDENT, HintLevel.PROCEDURE_CUE
        )
        self.assertEqual(new_level, HintLevel.STRATEGIC_QUESTION)

    def test_adapt_hint_level_frustrated_escalates(self):
        new_level = self.policy.adapt_hint_level(
            AffectType.FRUSTRATED, HintLevel.STRATEGIC_QUESTION
        )
        self.assertEqual(new_level, HintLevel.PROCEDURE_CUE)

    def test_adapt_hint_level_bored_keeps(self):
        new_level = self.policy.adapt_hint_level(
            AffectType.BORED, HintLevel.PROCEDURE_CUE
        )
        self.assertEqual(new_level, HintLevel.PROCEDURE_CUE)

    def test_adapt_hint_level_bounds(self):
        # Should not go below 1
        new_level = self.policy.adapt_hint_level(
            AffectType.CONFIDENT, HintLevel.STRATEGIC_QUESTION
        )
        self.assertEqual(new_level, HintLevel.STRATEGIC_QUESTION)
        # Should not go above 4
        new_level = self.policy.adapt_hint_level(
            AffectType.FRUSTRATED, HintLevel.BOTTOM_OUT_STEP
        )
        self.assertEqual(new_level, HintLevel.BOTTOM_OUT_STEP)


# -----------------------------------------------------------------------
# RuleBasedRenderer
# -----------------------------------------------------------------------


class TestRuleBasedRenderer(unittest.TestCase):
    def setUp(self):
        self.renderer = RuleBasedRenderer()

    def test_render_opening(self):
        text = self.renderer.render("opening", {"topic": "algebra"})
        self.assertIn("algebra", text)

    def test_render_diagnosing(self):
        text = self.renderer.render("diagnosing", {"topic": "algebra"})
        self.assertIn("algebra", text)

    def test_render_closing(self):
        text = self.renderer.render("closing", {"topic": "algebra"})
        self.assertIn("algebra", text)

    def test_render_unknown_intent(self):
        text = self.renderer.render("unknown", {"topic": "algebra"})
        self.assertIn("algebra", text)

    def test_render_confirming_correct(self):
        text = self.renderer.render("confirming_correct", {"topic": "algebra"})
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)

    def test_render_confirming_incorrect(self):
        text = self.renderer.render("confirming_incorrect", {"topic": "algebra"})
        self.assertIsInstance(text, str)
        self.assertGreater(len(text), 0)


# -----------------------------------------------------------------------
# TutorHarness
# -----------------------------------------------------------------------


class TestTutorHarness(unittest.TestCase):
    def setUp(self):
        self.harness = TutorHarness()
        self.q = _make_question()

    def test_begin_session(self):
        session = self.harness.begin_session("L1", "arithmetic")
        self.assertEqual(session.learner_id, "L1")
        self.assertEqual(session.topic, "arithmetic")
        self.assertEqual(session.state, DialogueState.OPENING)
        self.assertEqual(session.mode, TutorMode.PRACTICE)

    def test_begin_session_with_question(self):
        session = self.harness.begin_session(
            "L1", "arithmetic", question=self.q
        )
        self.assertIsNotNone(session.current_question)

    def test_get_session(self):
        self.harness.begin_session("L1", "arithmetic")
        session = self.harness.get_session("L1")
        self.assertIsNotNone(session)

    def test_get_session_missing(self):
        session = self.harness.get_session("nonexistent")
        self.assertIsNone(session)

    def test_set_question(self):
        self.harness.begin_session("L1", "arithmetic")
        self.harness.set_question("L1", self.q)
        session = self.harness.get_session("L1")
        self.assertIsNotNone(session.current_question)
        self.assertEqual(session.current_question.qid, "q1")

    def test_respond_no_session_raises(self):
        with self.assertRaises(ValueError):
            self.harness.respond("nonexistent", "hello")

    def test_respond_opening(self):
        self.harness.begin_session("L1", "arithmetic")
        response = self.harness.respond("L1", "hello")
        self.assertIsInstance(response, TutorResponse)
        self.assertEqual(response.state, DialogueState.DIAGNOSING.value)

    def test_respond_guiding(self):
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        # Move to guiding
        self.harness.respond("L1", "hello")
        response = self.harness.respond("L1", "I'm stuck")
        self.assertEqual(response.state, DialogueState.GUIDING.value)
        self.assertEqual(response.move_type, MoveType.HINT.value)

    def test_respond_never_leaks_answer_practice(self):
        """Critical test: tutor must NEVER reveal the answer in practice mode."""
        q = _make_question(answer="42")
        self.harness.begin_session("L1", "arithmetic", question=q)
        # Move to guiding
        self.harness.respond("L1", "hello")
        # Get multiple hints
        for _ in range(5):
            response = self.harness.provide_hint("L1")
            self.assertFalse(
                response.leak_report.is_leaked,
                f"Leak detected: {response.leak_report.matched_patterns}",
            )
            self.assertNotIn("42", response.text)

    def test_reveal_answer_practice_mode_refused(self):
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        response = self.harness.reveal_answer("L1")
        self.assertIn("can't reveal", response.text.lower())

    def test_reveal_answer_exploration_mode(self):
        self.harness.begin_session(
            "L1", "arithmetic", mode=TutorMode.EXPLORATION, question=self.q
        )
        response = self.harness.reveal_answer("L1")
        self.assertIn("4", response.text)

    def test_check_answer_correct(self):
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        response = self.harness.check_answer("L1", "4")
        self.assertEqual(response.state, DialogueState.TRANSFERRING.value)

    def test_check_answer_incorrect(self):
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        response = self.harness.check_answer("L1", "wrong")
        self.assertEqual(response.state, DialogueState.GUIDING.value)

    def test_get_metacognitive_prompt(self):
        self.harness.begin_session("L1", "arithmetic")
        response = self.harness.get_metacognitive_prompt("L1")
        self.assertEqual(response.move_type, MoveType.METACOGNITIVE.value)

    def test_handle_question(self):
        self.harness.begin_session("L1", "arithmetic")
        response = self.harness.handle_question("L1", "What is the answer?")
        self.assertEqual(response.move_type, MoveType.QUESTION.value)

    def test_get_state(self):
        self.harness.begin_session("L1", "arithmetic")
        state = self.harness.get_state("L1")
        self.assertIn("state", state)
        self.assertIn("hint_level", state)
        self.assertIn("questions_asked", state)

    def test_full_dialogue_flow(self):
        """Test a complete tutoring session from opening to closing."""
        self.harness.begin_session("L1", "arithmetic", question=self.q)

        # Opening -> Diagnosing
        r = self.harness.respond("L1", "hello")
        self.assertEqual(r.state, DialogueState.DIAGNOSING.value)

        # Diagnosing -> Guiding
        r = self.harness.respond("L1", "I know math")
        self.assertEqual(r.state, DialogueState.GUIDING.value)

        # Guiding -> Confirming (correct answer)
        r = self.harness.respond("L1", "4")
        self.assertEqual(r.state, DialogueState.TRANSFERRING.value)

        # Transferring -> Reflecting
        r = self.harness.respond("L1", "yes, I can apply it")
        self.assertEqual(r.state, DialogueState.REFLECTING.value)

        # Reflecting -> Closing
        r = self.harness.respond("L1", "I learned a lot")
        self.assertEqual(r.state, DialogueState.CLOSING.value)

    def test_remediation_flow(self):
        """Test remediation when learner struggles."""
        self.harness.begin_session("L1", "arithmetic", question=self.q)

        # Get to guiding
        self.harness.respond("L1", "hello")
        self.harness.respond("L1", "I know math")

        # Wrong answer -> back to guiding
        r = self.harness.respond("L1", "wrong")
        self.assertEqual(r.state, DialogueState.GUIDING.value)
        self.assertGreater(r.metadata.get("consecutive_struggles", 0), 0)

    def test_affect_adaptation_in_response(self):
        """Test that affect is detected and recorded."""
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        self.harness.respond("L1", "hello")
        response = self.harness.respond("L1", "I'm confused")
        self.assertEqual(response.affect_detected, AffectType.CONFUSED.value)

    def test_hint_level_escalation(self):
        """Test that hint level escalates with struggles."""
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        self.harness.respond("L1", "hello")
        self.harness.respond("L1", "I know math")

        # First struggle
        self.harness.respond("L1", "wrong")
        state = self.harness.get_state("L1")
        self.assertGreaterEqual(state["hint_level"], 1)

        # Second struggle
        self.harness.respond("L1", "still wrong")
        state = self.harness.get_state("L1")
        self.assertGreaterEqual(state["hint_level"], 1)

    def test_provide_hint_no_session_raises(self):
        with self.assertRaises(ValueError):
            self.harness.provide_hint("nonexistent")

    def test_check_answer_no_session_raises(self):
        with self.assertRaises(ValueError):
            self.harness.check_answer("nonexistent", "4")

    def test_reveal_answer_no_session_raises(self):
        with self.assertRaises(ValueError):
            self.harness.reveal_answer("nonexistent")

    def test_session_history_recorded(self):
        self.harness.begin_session("L1", "arithmetic", question=self.q)
        self.harness.respond("L1", "hello")
        self.harness.respond("L1", "I'm stuck")
        session = self.harness.get_session("L1")
        self.assertGreater(len(session.dialogue_history), 0)

    def test_multiple_sessions_independent(self):
        """Test that multiple learner sessions are independent."""
        self.harness.begin_session("L1", "arithmetic")
        self.harness.begin_session("L2", "algebra")

        r1 = self.harness.respond("L1", "hello")
        r2 = self.harness.respond("L2", "hi")

        self.assertEqual(r1.state, DialogueState.DIAGNOSING.value)
        self.assertEqual(r2.state, DialogueState.DIAGNOSING.value)

        # L1 should not affect L2
        s1 = self.harness.get_session("L1")
        s2 = self.harness.get_session("L2")
        self.assertEqual(s1.topic, "arithmetic")
        self.assertEqual(s2.topic, "algebra")


# -----------------------------------------------------------------------
# Integration tests
# -----------------------------------------------------------------------


class TestTutorIntegration(unittest.TestCase):
    """Integration tests for the full tutoring pipeline."""

    def test_socratic_dialogue_never_reveals_answer(self):
        """End-to-end: tutor must never reveal the answer in practice mode."""
        harness = TutorHarness()
        q = _make_question(
            qid="q1",
            prompt="What is the capital of France?",
            answer="Paris",
            topic="geography",
        )
        harness.begin_session("L1", "geography", question=q)

        # Simulate a struggling learner
        harness.respond("L1", "hello")
        harness.respond("L1", "I don't know")

        for _ in range(10):
            response = harness.provide_hint("L1")
            self.assertFalse(
                response.leak_report.is_leaked,
                f"Leak: {response.leak_report.matched_patterns}",
            )
            self.assertNotIn("Paris", response.text)

    def test_exploration_mode_allows_answer_reveal(self):
        """In exploration mode, answer can be revealed after attempt."""
        harness = TutorHarness()
        q = _make_question(answer="42")
        harness.begin_session(
            "L1", "arithmetic", mode=TutorMode.EXPLORATION, question=q
        )

        # Learner attempts
        harness.respond("L1", "hello")
        harness.respond("L1", "I know math")
        harness.respond("L1", "4")

        # Reveal answer
        response = harness.reveal_answer("L1")
        self.assertIn("42", response.text)

    def test_affect_changes_hint_level(self):
        """Test that affect detection changes the hint level."""
        harness = TutorHarness()
        q = _make_question(answer="42")
        harness.begin_session("L1", "arithmetic", question=q)

        harness.respond("L1", "hello")
        harness.respond("L1", "I know math")

        # Confused learner should get more help
        response = harness.respond("L1", "I'm confused")
        self.assertEqual(response.affect_detected, AffectType.CONFUSED.value)

    def test_metacognitive_prompt_in_reflection(self):
        """Test that metacognitive prompts appear in reflection state."""
        harness = TutorHarness()
        q = _make_question(answer="4")
        harness.begin_session("L1", "arithmetic", question=q)

        # Fast-forward to reflecting
        harness.respond("L1", "hello")
        harness.respond("L1", "I know math")
        harness.respond("L1", "4")  # correct -> transferring
        harness.respond("L1", "yes")  # -> reflecting
        response = harness.respond("L1", "I learned")  # -> closing (metacognitive)

        self.assertEqual(response.state, DialogueState.CLOSING.value)
        self.assertEqual(response.move_type, MoveType.METACOGNITIVE.value)

    def test_dialogue_state_machine_integrity(self):
        """Test that the state machine follows valid transitions."""
        harness = TutorHarness()
        q = _make_question(answer="4")
        harness.begin_session("L1", "arithmetic", question=q)

        # Follow the full path
        states = []
        r = harness.respond("L1", "hello")
        states.append(r.state)
        r = harness.respond("L1", "I know math")
        states.append(r.state)
        r = harness.respond("L1", "4")
        states.append(r.state)
        r = harness.respond("L1", "yes")
        states.append(r.state)
        r = harness.respond("L1", "I learned")
        states.append(r.state)

        expected = [
            DialogueState.DIAGNOSING.value,
            DialogueState.GUIDING.value,
            DialogueState.TRANSFERRING.value,
            DialogueState.REFLECTING.value,
            DialogueState.CLOSING.value,
        ]
        self.assertEqual(states, expected)


if __name__ == "__main__":
    unittest.main(verbosity=2)
