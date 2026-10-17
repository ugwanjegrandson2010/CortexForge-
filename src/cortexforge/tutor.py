"""Socratic tutor harness for CortexForge.

Implements the NPALS specification for a Socratic tutor:
- Dialogue state machine (opening -> diagnosing -> guiding -> confirming ->
  transferring -> reflecting -> closing)
- Socratic policy with 4-level hint ladder
- Answer-leak prevention (post-hoc classifier)
- Affect-adaptive branching

The tutor NEVER outputs final answers in practice/homework mode.
It uses graduated hints, Socratic questioning, and metacognitive prompts.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum, IntEnum
from typing import Optional, Protocol

from .questiongen import Question


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class DialogueState(Enum):
    """Dialogue states for the tutoring state machine."""

    OPENING = "opening"
    DIAGNOSING = "diagnosing"
    GUIDING = "guiding"
    CONFIRMING = "confirming"
    TRANSFERRING = "transferring"
    REFLECTING = "reflecting"
    CLOSING = "closing"


class HintLevel(IntEnum):
    """Hint ladder levels."""

    STRATEGIC_QUESTION = 1
    PROCEDURE_CUE = 2
    WORKED_ANALOGOUS_EXAMPLE = 3
    BOTTOM_OUT_STEP = 4


class AffectType(Enum):
    """Learner affect types."""

    NEUTRAL = "neutral"
    CONFUSED = "confused"
    CONFIDENT = "confident"
    FRUSTRATED = "frustrated"
    BORED = "bored"


class MoveType(Enum):
    """Types of tutor moves."""

    QUESTION = "question"
    HINT = "hint"
    FEEDBACK = "feedback"
    ENCOURAGEMENT = "encouragement"
    METACOGNITIVE = "metacognitive"
    TRANSITION = "transition"


class TutorMode(Enum):
    """Tutoring mode."""

    PRACTICE = "practice"
    EXPLORATION = "exploration"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LeakReport:
    """Report from answer leak detection."""

    is_leaked: bool
    matched_patterns: list[str]
    confidence: float
    details: str


@dataclass
class TutorResponse:
    """A response from the tutor."""

    text: str
    state: str
    move_type: str
    hint_level: int | None
    affect_detected: str | None
    leak_report: LeakReport
    metadata: dict = field(default_factory=dict)


@dataclass
class TutorSession:
    """State for a single tutoring session."""

    learner_id: str
    topic: str
    state: DialogueState
    current_question: Question | None
    hint_level: int
    max_hint_level: int
    dialogue_history: list[dict]
    affect_history: list[str]
    mode: TutorMode
    consecutive_struggles: int
    questions_asked: int
    hints_given: int


# ---------------------------------------------------------------------------
# TutorState - Dialogue state machine
# ---------------------------------------------------------------------------

class TutorState:
    """Manages dialogue state transitions.

    Valid transitions:
        OPENING -> DIAGNOSING
        DIAGNOSING -> GUIDING
        GUIDING -> CONFIRMING
        CONFIRMING -> GUIDING (remediation)
        CONFIRMING -> TRANSFERRING
        TRANSFERRING -> GUIDING (remediation)
        TRANSFERRING -> REFLECTING
        REFLECTING -> CLOSING
        REFLECTING -> GUIDING (continue)
        CLOSING -> OPENING (new session)
    """

    VALID_TRANSITIONS: dict[DialogueState, set[DialogueState]] = {
        DialogueState.OPENING: {DialogueState.DIAGNOSING},
        DialogueState.DIAGNOSING: {DialogueState.GUIDING},
        DialogueState.GUIDING: {DialogueState.CONFIRMING},
        DialogueState.CONFIRMING: {DialogueState.GUIDING, DialogueState.TRANSFERRING},
        DialogueState.TRANSFERRING: {DialogueState.GUIDING, DialogueState.REFLECTING},
        DialogueState.REFLECTING: {DialogueState.CLOSING, DialogueState.GUIDING},
        DialogueState.CLOSING: {DialogueState.OPENING},
    }

    def __init__(self, initial: DialogueState = DialogueState.OPENING):
        self._state = initial
        self._history: list[tuple[DialogueState, str]] = [(initial, "init")]

    @property
    def current(self) -> DialogueState:
        return self._state

    def can_transition_to(self, new_state: DialogueState) -> bool:
        return new_state in self.VALID_TRANSITIONS.get(self._state, set())

    def transition_to(self, new_state: DialogueState, reason: str = "") -> bool:
        if self.can_transition_to(new_state):
            self._state = new_state
            self._history.append((new_state, reason))
            return True
        return False

    def force_transition(self, new_state: DialogueState, reason: str = "") -> None:
        """Force a transition (use sparingly, for error recovery)."""
        self._state = new_state
        self._history.append((new_state, reason))

    @property
    def history(self) -> list[tuple[DialogueState, str]]:
        return list(self._history)

    def __str__(self) -> str:
        return self._state.value


# ---------------------------------------------------------------------------
# AnswerLeakDetector - Post-hoc classifier
# ---------------------------------------------------------------------------

class AnswerLeakDetector:
    """Detects whether tutor output contains answer leaks.

    Three detection strategies:
    1. Exact string matching (normalized)
    2. Substring matching (for partial leaks)
    3. Numeric matching (numbers from answer in output)
    """

    def __init__(
        self,
        string_threshold: float = 0.8,
        numeric_threshold: float = 0.6,
        min_match_length: int = 4,
    ):
        self.string_threshold = string_threshold
        self.numeric_threshold = numeric_threshold
        self.min_match_length = min_match_length

    def _normalize(self, text: str) -> str:
        """Normalize text for comparison."""
        return " ".join(text.lower().split())

    def _extract_numbers(self, text: str) -> list[str]:
        """Extract all numeric values from text."""
        return re.findall(r"\d+\.?\d*", text)

    def check(
        self, output: str, answer: str, mode: TutorMode = TutorMode.PRACTICE
    ) -> LeakReport:
        """Check if output contains answer leaks.

        In practice mode, the detector is strict: any leak is flagged.
        In exploration mode, the detector is lenient: only obvious leaks.
        """
        if not answer or not answer.strip():
            return LeakReport(
                is_leaked=False,
                matched_patterns=[],
                confidence=0.0,
                details="No answer to check against",
            )

        normalized_output = self._normalize(output)
        normalized_answer = self._normalize(answer)

        matched_patterns: list[str] = []

        # 1. Exact string match
        if normalized_answer in normalized_output:
            matched_patterns.append(f"exact_match: '{answer[:50]}...'")

        # 2. Substring match (for longer answers)
        if len(normalized_answer) > 20:
            chunks = [
                normalized_answer[i : i + 20]
                for i in range(0, len(normalized_answer), 20)
            ]
            for chunk in chunks:
                if len(chunk) >= self.min_match_length and chunk in normalized_output:
                    matched_patterns.append(f"chunk_match: '{chunk[:30]}...'")

        # 3. Numeric matching
        answer_numbers = self._extract_numbers(answer)
        output_numbers = self._extract_numbers(output)
        if answer_numbers and output_numbers:
            common_numbers = set(answer_numbers) & set(output_numbers)
            if common_numbers:
                significant = [
                    n for n in common_numbers if len(n) > 1 or float(n) > 10
                ]
                if significant:
                    matched_patterns.append(f"numeric_match: {significant}")

        # Determine if leaked
        is_leaked = len(matched_patterns) > 0

        # In exploration mode, be more lenient
        if mode == TutorMode.EXPLORATION:
            exact_or_multiple = any("exact_match" in p for p in matched_patterns) or (
                sum("chunk_match" in p for p in matched_patterns) >= 2
            )
            is_leaked = exact_or_multiple

        # Calculate confidence
        confidence = min(
            1.0, len(matched_patterns) * 0.3 + (0.5 if is_leaked else 0.0)
        )

        details = (
            f"Found {len(matched_patterns)} leak patterns"
            if is_leaked
            else "No leaks detected"
        )

        return LeakReport(
            is_leaked=is_leaked,
            matched_patterns=matched_patterns,
            confidence=round(confidence, 2),
            details=details,
        )


# ---------------------------------------------------------------------------
# SocraticPolicy - Hint ladder and move selection
# ---------------------------------------------------------------------------

class SocraticPolicy:
    """Implements the Socratic hint ladder.

    Four levels:
    1. Strategic question - prompts thinking without giving direction
    2. Procedure cue - hints at method or approach
    3. Worked analogous example - provides analogous problem + insight
    4. Bottom-out step - reveals first step (NOT the answer in practice mode)

    The policy NEVER outputs final answers in practice/homework mode.
    """

    HINT_TEMPLATES: dict[HintLevel, list[str]] = {
        HintLevel.STRATEGIC_QUESTION: [
            "What do you already know about {topic} that could help here?",
            "If you had to make an educated guess, what approach would you try?",
            "What's similar to this that you've encountered before?",
            "Before diving in, what do you think the key insight might be?",
        ],
        HintLevel.PROCEDURE_CUE: [
            "Try breaking this into smaller steps. What's the first thing you'd check?",
            "Is there a method or approach you've seen that fits this kind of problem?",
            "What would be a good first move here? Think about what you'd do before calculating.",
            "Consider: what information do you have, and what are you trying to find?",
        ],
        HintLevel.WORKED_ANALOGOUS_EXAMPLE: [
            "Here's a similar problem: Imagine you're dealing with a simpler case of {topic}. "
            "What's the core principle that applies?",
            "Think of it like a simpler version: if you had a basic {topic} problem, "
            "how would you solve it? Now apply that same logic here.",
        ],
        HintLevel.BOTTOM_OUT_STEP: [
            "Start with this: identify what you know and what you need to find. "
            "Then think about the relationship between them.",
            "The first step is to understand the structure of the problem. "
            "What are the key components here?",
        ],
    }

    METACOGNITIVE_PROMPTS = [
        "How did you arrive at that answer? Walk me through your reasoning.",
        "What was your strategy there? Would you use the same approach next time?",
        "How confident are you in that answer? What makes you uncertain?",
        "What would you do differently if you encountered a similar problem?",
        "What part of that was easiest for you? What was hardest?",
    ]

    def __init__(self, max_hint_level: int = HintLevel.BOTTOM_OUT_STEP):
        self.max_hint_level = max_hint_level

    def select_hint_level(self, session: TutorSession) -> HintLevel:
        """Select appropriate hint level based on session state.

        Escalates based on consecutive struggles.
        """
        if session.consecutive_struggles == 0:
            return HintLevel.STRATEGIC_QUESTION
        elif session.consecutive_struggles == 1:
            return HintLevel.PROCEDURE_CUE
        elif session.consecutive_struggles == 2:
            return HintLevel.WORKED_ANALOGOUS_EXAMPLE
        else:
            return HintLevel(self.max_hint_level)

    def generate_hint(self, session: TutorSession, question: Question) -> str:
        """Generate a hint at the current level.

        NEVER reveals the answer in practice mode.
        """
        hint_level = self.select_hint_level(session)
        templates = self.HINT_TEMPLATES[hint_level]
        import random

        template = random.choice(templates)

        topic = session.topic or "this topic"
        hint = template.format(topic=topic)

        if hint_level == HintLevel.BOTTOM_OUT_STEP:
            hint += self._get_first_step_hint(question)

        return hint

    def _get_first_step_hint(self, question: Question) -> str:
        """Generate a first-step hint that does NOT reveal the answer."""
        return (
            "\n\nAs a starting point: look at what the question is asking for, "
            "and identify the key concept involved. What principle applies here?"
        )

    def generate_strategic_question(self, topic: str) -> str:
        """Generate a Socratic strategic question."""
        import random

        template = random.choice(self.HINT_TEMPLATES[HintLevel.STRATEGIC_QUESTION])
        return template.format(topic=topic)

    def generate_metacognitive_prompt(self, context: str = "") -> str:
        """Generate a metacognitive prompt."""
        import random

        prompt = random.choice(self.METACOGNITIVE_PROMPTS)
        if context:
            prompt = f"{context}\n\n{prompt}"
        return prompt

    def should_escalate(
        self, session: TutorSession, learner_correct: bool | None
    ) -> bool:
        """Determine if hint level should escalate.

        Escalates if learner is struggling (incorrect or no answer).
        """
        if learner_correct is False:
            return True
        if learner_correct is None:
            return True
        return False

    def get_move_type(self, session: TutorSession) -> MoveType:
        """Determine the type of move to make."""
        state = session.state
        if state == DialogueState.OPENING:
            return MoveType.QUESTION
        elif state == DialogueState.DIAGNOSING:
            return MoveType.QUESTION
        elif state == DialogueState.GUIDING:
            return MoveType.HINT
        elif state == DialogueState.CONFIRMING:
            return MoveType.FEEDBACK
        elif state == DialogueState.TRANSFERRING:
            return MoveType.QUESTION
        elif state == DialogueState.REFLECTING:
            return MoveType.METACOGNITIVE
        else:
            return MoveType.TRANSITION


# ---------------------------------------------------------------------------
# AffectAdaptivePolicy - Affect-based branching
# ---------------------------------------------------------------------------

class AffectAdaptivePolicy:
    """Detects learner affect and adapts pedagogy accordingly.

    Branches:
    - confused -> scaffold up (more support, simpler steps)
    - confident -> challenge (harder problems, less hand-holding)
    - frustrated -> competence-restore (remind of past success, reduce difficulty)
    - bored -> relevance+novelty (connect to real world, add variety)
    """

    AFFECT_KEYWORDS: dict[AffectType, list[str]] = {
        AffectType.CONFUSED: [
            "confused",
            "don't understand",
            "lost",
            "stuck",
            "unclear",
            "what do you mean",
            "doesn't make sense",
            "where do i start",
        ],
        AffectType.CONFIDENT: [
            "easy",
            "obvious",
            "got it",
            "simple",
            "clear",
            "makes sense",
            "i know this",
            "straightforward",
        ],
        AffectType.FRUSTRATED: [
            "frustrated",
            "hate",
            "stupid",
            "can't do",
            "never get",
            "giving up",
            "too hard",
            "impossible",
            "annoying",
        ],
        AffectType.BORED: [
            "boring",
            "tired",
            "already know",
            "done this",
            "repetitive",
            "not interested",
            "why do i need",
            "pointless",
        ],
    }

    AFFECT_RESPONSES: dict[AffectType, dict] = {
        AffectType.CONFUSED: {
            "strategy": "scaffold_up",
            "action": "Break the problem into smaller, more manageable pieces.",
            "message": "Let's slow down and break this into smaller steps.",
        },
        AffectType.CONFIDENT: {
            "strategy": "challenge",
            "action": "Present a harder variant or ask for a deeper explanation.",
            "message": "Great, you've got the basics. Let's push deeper.",
        },
        AffectType.FRUSTRATED: {
            "strategy": "competence_restore",
            "action": "Remind of past success and reduce difficulty temporarily.",
            "message": "This one's tricky. Let's approach it differently — you've handled harder things before.",
        },
        AffectType.BORED: {
            "strategy": "relevance_novelty",
            "action": "Connect to real-world application or add novelty.",
            "message": "Let's look at why this matters in the real world.",
        },
    }

    def detect_affect(self, learner_input: str) -> AffectType:
        """Detect affect from learner input using keyword matching."""
        low = learner_input.lower()
        scores: dict[AffectType, int] = {}

        for affect, keywords in self.AFFECT_KEYWORDS.items():
            score = sum(1 for kw in keywords if kw in low)
            if score > 0:
                scores[affect] = score

        if not scores:
            return AffectType.NEUTRAL

        return max(scores, key=scores.get)  # type: ignore[arg-type]

    def get_adaptation(self, affect: AffectType) -> dict:
        """Get the adaptation strategy for a detected affect."""
        return self.AFFECT_RESPONSES.get(
            affect,
            {
                "strategy": "continue",
                "action": "Continue with current approach.",
                "message": "",
            },
        )

    def adapt_hint_level(
        self, affect: AffectType, current_level: HintLevel
    ) -> HintLevel:
        """Adapt hint level based on affect.

        - Confused: escalate hint level (more help)
        - Confident: de-escalate hint level (less help)
        - Frustrated: escalate hint level (more support)
        - Bored: keep hint level but add novelty
        """
        if affect in (AffectType.CONFUSED, AffectType.FRUSTRATED):
            return HintLevel(min(int(current_level) + 1, 4))
        elif affect == AffectType.CONFIDENT:
            return HintLevel(max(int(current_level) - 1, 1))
        else:
            return current_level


# ---------------------------------------------------------------------------
# RuleBasedRenderer - LLM fallback
# ---------------------------------------------------------------------------

class TutorRenderer(Protocol):
    """Protocol for tutor renderers."""

    def render(self, intent: str, context: dict) -> str: ...


class RuleBasedRenderer:
    """Rule-based renderer that implements the Socratic policy without an LLM.

    This is the fallback when no LLM API is available. It generates
    pedagogically sound responses using templates and rules.
    """

    OPENING_TEMPLATES = [
        "Welcome! Today we'll work on {topic}. Let's start by understanding what you already know.",
        "Hello! I'm here to help you learn {topic}. We'll work through this together.",
    ]

    DIAGNOSING_TEMPLATES = [
        "Before we dive in, let's figure out where you are. What do you know about {topic}?",
        "To help you best, I need to understand your starting point. Have you worked with {topic} before?",
    ]

    CONFIRMING_CORRECT = [
        "That's right. Your reasoning is sound.",
        "Correct. You've demonstrated understanding of the concept.",
    ]

    CONFIRMING_INCORRECT = [
        "Not quite. Let's think about this differently.",
        "That's not the answer, but let's work through why.",
    ]

    TRANSFERRING_TEMPLATES = [
        "Now let's try applying this to a new situation. How would you use {topic} in a different context?",
        "Let's see if you can transfer this. What if we changed the scenario?",
    ]

    REFLECTING_TEMPLATES = [
        "Let's take a moment to reflect. What did you learn from this?",
        "Think back to how you approached this. What would you do differently next time?",
    ]

    CLOSING_TEMPLATES = [
        "Great work today. You've made progress on {topic}. We'll continue next time.",
        "Well done. Keep practicing — we'll build on this in your next session.",
    ]

    def __init__(self):
        import random

        self.rng = random.Random(42)

    def render(self, intent: str, context: dict) -> str:
        """Render a response based on pedagogical intent.

        Args:
            intent: The pedagogical intent (e.g., "opening", "hint", "feedback")
            context: Context variables for template filling
        """
        topic = context.get("topic", "this topic")

        if intent == "opening":
            template = self.rng.choice(self.OPENING_TEMPLATES)
        elif intent == "diagnosing":
            template = self.rng.choice(self.DIAGNOSING_TEMPLATES)
        elif intent == "confirming_correct":
            template = self.rng.choice(self.CONFIRMING_CORRECT)
        elif intent == "confirming_incorrect":
            template = self.rng.choice(self.CONFIRMING_INCORRECT)
        elif intent == "transferring":
            template = self.rng.choice(self.TRANSFERRING_TEMPLATES)
        elif intent == "reflecting":
            template = self.rng.choice(self.REFLECTING_TEMPLATES)
        elif intent == "closing":
            template = self.rng.choice(self.CLOSING_TEMPLATES)
        else:
            template = "Let's continue working on {topic}."

        return template.format(topic=topic)


# ---------------------------------------------------------------------------
# TutorHarness - Main tutor interface
# ---------------------------------------------------------------------------

class TutorHarness:
    """Main tutor interface.

    Orchestrates the dialogue, manages state, and ensures pedagogical integrity.

    Key constraint: NEVER outputs final answers in practice/homework mode.
    """

    def __init__(
        self,
        policy: SocraticPolicy | None = None,
        leak_detector: AnswerLeakDetector | None = None,
        affect_policy: AffectAdaptivePolicy | None = None,
        renderer: RuleBasedRenderer | None = None,
    ):
        self.policy = policy or SocraticPolicy()
        self.leak_detector = leak_detector or AnswerLeakDetector()
        self.affect_policy = affect_policy or AffectAdaptivePolicy()
        self.renderer = renderer or RuleBasedRenderer()
        self.sessions: dict[str, TutorSession] = {}

    def begin_session(
        self,
        learner_id: str,
        topic: str,
        mode: TutorMode = TutorMode.PRACTICE,
        question: Question | None = None,
    ) -> TutorSession:
        """Begin a new tutoring session."""
        session = TutorSession(
            learner_id=learner_id,
            topic=topic,
            state=DialogueState.OPENING,
            current_question=question,
            hint_level=1,
            max_hint_level=4,
            dialogue_history=[],
            affect_history=[],
            mode=mode,
            consecutive_struggles=0,
            questions_asked=0,
            hints_given=0,
        )
        self.sessions[learner_id] = session
        return session

    def get_session(self, learner_id: str) -> TutorSession | None:
        """Get an existing session."""
        return self.sessions.get(learner_id)

    def set_question(self, learner_id: str, question: Question) -> None:
        """Set the current question for the session."""
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")
        session.current_question = question
        session.hint_level = 1  # Reset hint level for new question

    def respond(self, learner_id: str, learner_input: str) -> TutorResponse:
        """Process learner input and generate a response.

        This is the main entry point for the tutor.
        """
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        # 1. Detect affect
        affect = self.affect_policy.detect_affect(learner_input)
        session.affect_history.append(affect.value)

        # 2. Adapt hint level based on affect
        session.hint_level = self.affect_policy.adapt_hint_level(
            affect, HintLevel(session.hint_level)
        )

        # 3. Determine response based on current state
        response = self._generate_response(session, learner_input, affect)

        # 4. Check for answer leaks
        if session.current_question:
            leak_report = self.leak_detector.check(
                response.text, session.current_question.answer, session.mode
            )
            response.leak_report = leak_report

            # If leaked in practice mode, replace with safe fallback
            if leak_report.is_leaked and session.mode == TutorMode.PRACTICE:
                response.text = self._safe_fallback(session)
                response.leak_report = LeakReport(
                    is_leaked=False,
                    matched_patterns=[],
                    confidence=0.0,
                    details="Replaced due to leak detection",
                )

        # 5. Record in history
        session.dialogue_history.append(
            {
                "learner_input": learner_input,
                "tutor_response": response.text,
                "state": session.state.value,
                "affect": affect.value,
            }
        )

        return response

    def _is_likely_answer(self, question: Question, learner_input: str) -> bool:
        """Heuristic: is the learner providing an answer (not asking for help)?"""
        # If the input contains the answer, it's likely an answer
        if question.answer.lower() in learner_input.lower():
            return True
        # If the input contains help-seeking keywords, it's not an answer
        help_keywords = [
            "help", "stuck", "confused", "don't understand", "how", "what",
            "why", "?", "don't know", "lost", "where do i",
        ]
        if any(kw in learner_input.lower() for kw in help_keywords):
            return False
        # If the input is very short, it might be an answer
        if len(learner_input.split()) <= 3:
            return True
        return False

    def _generate_response(
        self, session: TutorSession, learner_input: str, affect: AffectType
    ) -> TutorResponse:
        """Generate a response based on current state and input."""
        # Auto-transition from GUIDING to CONFIRMING when learner provides an answer
        if (
            session.state == DialogueState.GUIDING
            and session.current_question
            and self._is_likely_answer(session.current_question, learner_input)
        ):
            session.state = DialogueState.CONFIRMING

        if session.state == DialogueState.OPENING:
            return self._handle_opening(session)
        elif session.state == DialogueState.DIAGNOSING:
            return self._handle_diagnosing(session, learner_input, affect)
        elif session.state == DialogueState.GUIDING:
            return self._handle_guiding(session, affect)
        elif session.state == DialogueState.CONFIRMING:
            return self._handle_confirming(session, learner_input)
        elif session.state == DialogueState.TRANSFERRING:
            return self._handle_transferring(session, learner_input)
        elif session.state == DialogueState.REFLECTING:
            return self._handle_reflecting(session)
        elif session.state == DialogueState.CLOSING:
            return self._handle_closing(session)
        else:
            return self._safe_fallback(session)

    def _handle_opening(self, session: TutorSession) -> TutorResponse:
        """Handle opening state."""
        text = self.renderer.render("opening", {"topic": session.topic})
        session.state = DialogueState.DIAGNOSING
        return TutorResponse(
            text=text,
            state=DialogueState.DIAGNOSING.value,
            move_type=MoveType.QUESTION.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def _handle_diagnosing(
        self, session: TutorSession, learner_input: str, affect: AffectType
    ) -> TutorResponse:
        """Handle diagnosing state."""
        session.state = DialogueState.GUIDING
        session.questions_asked += 1

        if session.current_question:
            text = f"Let's work on this: {session.current_question.prompt}"
        else:
            text = f"Let's start working on {session.topic}."

        return TutorResponse(
            text=text,
            state=DialogueState.GUIDING.value,
            move_type=MoveType.HINT.value,
            hint_level=None,
            affect_detected=affect.value,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def _handle_guiding(
        self, session: TutorSession, affect: AffectType
    ) -> TutorResponse:
        """Handle guiding state - provide hints."""
        session.hints_given += 1

        if session.current_question:
            text = self.policy.generate_hint(session, session.current_question)
        else:
            text = self.policy.generate_strategic_question(session.topic)

        adaptation = self.affect_policy.get_adaptation(affect)
        if adaptation["message"]:
            text = adaptation["message"] + "\n\n" + text

        return TutorResponse(
            text=text,
            state=DialogueState.GUIDING.value,
            move_type=MoveType.HINT.value,
            hint_level=session.hint_level,
            affect_detected=affect.value,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def _handle_confirming(
        self, session: TutorSession, learner_input: str
    ) -> TutorResponse:
        """Handle confirming state - check answer and provide feedback."""
        is_correct = self._check_answer(session, learner_input)

        if is_correct:
            session.consecutive_struggles = 0
            session.state = DialogueState.TRANSFERRING
            text = self.renderer.render("confirming_correct", {"topic": session.topic})
        else:
            session.consecutive_struggles += 1
            session.state = DialogueState.GUIDING
            text = self.renderer.render(
                "confirming_incorrect", {"topic": session.topic}
            )

        return TutorResponse(
            text=text,
            state=session.state.value,
            move_type=MoveType.FEEDBACK.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
            metadata={"consecutive_struggles": session.consecutive_struggles},
        )

    def _handle_transferring(
        self, session: TutorSession, learner_input: str
    ) -> TutorResponse:
        """Handle transferring state."""
        # In transfer mode, we present a new scenario and move to reflecting
        # (we don't re-check the original answer)
        session.state = DialogueState.REFLECTING

        text = self.renderer.render("transferring", {"topic": session.topic})
        return TutorResponse(
            text=text,
            state=DialogueState.REFLECTING.value,
            move_type=MoveType.QUESTION.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
            metadata={"consecutive_struggles": session.consecutive_struggles},
        )

    def _handle_reflecting(self, session: TutorSession) -> TutorResponse:
        """Handle reflecting state."""
        text = self.renderer.render("reflecting", {"topic": session.topic})
        text += "\n\n" + self.policy.generate_metacognitive_prompt()
        session.state = DialogueState.CLOSING
        return TutorResponse(
            text=text,
            state=DialogueState.CLOSING.value,
            move_type=MoveType.METACOGNITIVE.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
            metadata={"consecutive_struggles": session.consecutive_struggles},
        )

    def _handle_closing(self, session: TutorSession) -> TutorResponse:
        """Handle closing state."""
        text = self.renderer.render("closing", {"topic": session.topic})
        return TutorResponse(
            text=text,
            state=DialogueState.CLOSING.value,
            move_type=MoveType.TRANSITION.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def _check_answer(self, session: TutorSession, learner_input: str) -> bool:
        """Check if learner answer is correct (simplified)."""
        if not session.current_question:
            return False
        answer = session.current_question.answer.lower()
        input_lower = learner_input.lower()
        return answer in input_lower or input_lower in answer

    def _safe_fallback(self, session: TutorSession) -> str:
        """Generate a safe fallback response when a leak is detected."""
        return (
            "Let's approach this differently. "
            "What do you think the key concept here is?"
        )

    def provide_hint(self, learner_id: str) -> TutorResponse:
        """Provide a hint to the learner."""
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        session.hints_given += 1
        session.state = DialogueState.GUIDING

        if session.current_question:
            text = self.policy.generate_hint(session, session.current_question)
        else:
            text = self.policy.generate_strategic_question(session.topic)

        if session.current_question:
            leak_report = self.leak_detector.check(
                text, session.current_question.answer, session.mode
            )
            if leak_report.is_leaked and session.mode == TutorMode.PRACTICE:
                text = self._safe_fallback(session)
                leak_report = LeakReport(False, [], 0.0, "Safe fallback applied")
        else:
            leak_report = LeakReport(False, [], 0.0, "No question to check")

        return TutorResponse(
            text=text,
            state=DialogueState.GUIDING.value,
            move_type=MoveType.HINT.value,
            hint_level=session.hint_level,
            affect_detected=None,
            leak_report=leak_report,
        )

    def check_answer(self, learner_id: str, answer: str) -> TutorResponse:
        """Check a learner's answer and provide feedback."""
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        is_correct = self._check_answer(session, answer)

        if is_correct:
            session.consecutive_struggles = 0
            session.state = DialogueState.TRANSFERRING
            text = self.renderer.render("confirming_correct", {"topic": session.topic})
        else:
            session.consecutive_struggles += 1
            session.state = DialogueState.GUIDING
            text = self.renderer.render(
                "confirming_incorrect", {"topic": session.topic}
            )

        return TutorResponse(
            text=text,
            state=session.state.value,
            move_type=MoveType.FEEDBACK.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def reveal_answer(self, learner_id: str) -> TutorResponse:
        """Reveal the answer (only in exploration mode).

        In practice mode, this returns a refusal.
        """
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        if session.mode == TutorMode.PRACTICE:
            return TutorResponse(
                text="I can't reveal the answer in practice mode. Keep working on it!",
                state=session.state.value,
                move_type=MoveType.FEEDBACK.value,
                hint_level=None,
                affect_detected=None,
                leak_report=LeakReport(False, [], 0.0, ""),
            )

        if not session.current_question:
            return TutorResponse(
                text="No question to reveal.",
                state=session.state.value,
                move_type=MoveType.FEEDBACK.value,
                hint_level=None,
                affect_detected=None,
                leak_report=LeakReport(False, [], 0.0, ""),
            )

        return TutorResponse(
            text=f"The answer is: {session.current_question.answer}",
            state=session.state.value,
            move_type=MoveType.FEEDBACK.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(
                False, [], 0.0, "Exploration mode - answer revealed"
            ),
        )

    def get_metacognitive_prompt(self, learner_id: str) -> TutorResponse:
        """Get a metacognitive prompt."""
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        text = self.policy.generate_metacognitive_prompt()

        return TutorResponse(
            text=text,
            state=session.state.value,
            move_type=MoveType.METACOGNITIVE.value,
            hint_level=None,
            affect_detected=None,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def handle_question(self, learner_id: str, question: str) -> TutorResponse:
        """Handle a question from the learner.

        Responds with a Socratic counter-question or hint.
        """
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        affect = self.affect_policy.detect_affect(question)

        if affect == AffectType.CONFUSED:
            text = (
                "That's a good question. Let me help you think it through. "
                + self.policy.generate_strategic_question(session.topic)
            )
        else:
            text = (
                "Good question. What do you think the answer might be? "
                + self.policy.generate_strategic_question(session.topic)
            )

        return TutorResponse(
            text=text,
            state=session.state.value,
            move_type=MoveType.QUESTION.value,
            hint_level=session.hint_level,
            affect_detected=affect.value,
            leak_report=LeakReport(False, [], 0.0, ""),
        )

    def get_state(self, learner_id: str) -> dict:
        """Get the current state of a session."""
        session = self.sessions.get(learner_id)
        if session is None:
            raise ValueError(f"No active session for {learner_id}")

        return {
            "state": session.state.value,
            "hint_level": session.hint_level,
            "questions_asked": session.questions_asked,
            "hints_given": session.hints_given,
            "consecutive_struggles": session.consecutive_struggles,
            "affect_history": session.affect_history,
        }


__all__ = [
    "AffectAdaptivePolicy",
    "AffectType",
    "AnswerLeakDetector",
    "DialogueState",
    "HintLevel",
    "LeakReport",
    "MoveType",
    "RuleBasedRenderer",
    "SocraticPolicy",
    "TutorHarness",
    "TutorMode",
    "TutorRenderer",
    "TutorResponse",
    "TutorSession",
    "TutorState",
]
