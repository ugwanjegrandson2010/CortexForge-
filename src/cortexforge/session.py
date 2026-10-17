"""Session architecture — the Zull cycle and 6-stage session structure.

Design references:
  * Zull, J.E. (2002, 2011) — The Art of Changing the Brain.
    The four-stage learning cycle: Experience → Reflect → Create → Act.
  * Zimmerman, B.J. (2002) — Becoming a Self-Regulated Learner.
    Forethought phase (task analysis, goal-setting, self-efficacy beliefs)
    and self-reflection phase (self-evaluation, attribution, adaptivity).
  * FSRS-4.5 scheduler (see scheduler.py) — due-queue drives Daily Retrieval.
  * BKT/IRT (see tracing.py) — mastery and difficulty estimates.

The 6-stage session structure:
  1. Launch              (2 min)  — attention, autonomy, forethought prompts
  2. Daily Retrieval     (5-8 min) — FSRS due-queue first, spaced retrieval
  3. Episodic Hook       (2-3 min) — concrete case or story, episodic encoding
  4. Guided Construction(10-15 min)— small steps, worked examples, scaffolding
  5. Active Testing      (5-8 min) — apply in varied contexts, transfer probes
  6. Confidence-Rated Close (2 min)— calibration, reflection prompts, SRL close

Session types: practice, review, checkup, homework, explore, reflection.
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable, Iterable, Sequence

from .scheduler import Card, build_queue, retention_forecast
from .tracing import BKTSkill, BKTParams, Item, calibration_stats, select_next_item
from .questiongen import Question, interleave


# ---------------------------------------------------------------------------
# Session types
# ---------------------------------------------------------------------------

class SessionType(str, Enum):
    """The six session types defined by the Mentat/NPALS specification."""

    PRACTICE = "practice"
    REVIEW = "review"
    CHECKUP = "checkup"
    HOMEWORK = "homework"
    EXPLORE = "explore"
    REFLECTION = "reflection"


# ---------------------------------------------------------------------------
# Stage definitions
# ---------------------------------------------------------------------------

class StageName(str, Enum):
    """The six stages of a session."""

    LAUNCH = "launch"
    DAILY_RETRIEVAL = "daily_retrieval"
    EPISODIC_HOOK = "episodic_hook"
    GUIDED_CONSTRUCTION = "guided_construction"
    ACTIVE_TESTING = "active_testing"
    CONFIDENCE_RATED_CLOSE = "confidence_rated_close"


@dataclass(frozen=True)
class StageSpec:
    """Specification for one session stage."""

    name: StageName
    label: str
    duration_min: int
    duration_max: int
    purpose: str
    zull_phase: str  # which Zull cycle phase this stage primarily serves

    def to_dict(self) -> dict:
        return asdict(self)


# The canonical 6-stage template.
STAGE_SPECS: tuple[StageSpec, ...] = (
    StageSpec(
        name=StageName.LAUNCH,
        label="Launch",
        duration_min=2, duration_max=2,
        purpose="Attention and autonomy — forethought prompts, goal-setting",
        zull_phase="Experience",
    ),
    StageSpec(
        name=StageName.DAILY_RETRIEVAL,
        label="Daily Retrieval Open",
        duration_min=5, duration_max=8,
        purpose="FSRS due-queue first — spaced retrieval practice",
        zull_phase="Reflect",
    ),
    StageSpec(
        name=StageName.EPISODIC_HOOK,
        label="Episodic Hook",
        duration_min=2, duration_max=3,
        purpose="Concrete case or story — episodic encoding anchor",
        zull_phase="Experience",
    ),
    StageSpec(
        name=StageName.GUIDED_CONSTRUCTION,
        label="Guided Construction",
        duration_min=10, duration_max=15,
        purpose="Small steps, worked examples — scaffolded skill building",
        zull_phase="Create",
    ),
    StageSpec(
        name=StageName.ACTIVE_TESTING,
        label="Active Testing",
        duration_min=5, duration_max=8,
        purpose="Apply in varied contexts — transfer and generalisation",
        zull_phase="Act",
    ),
    StageSpec(
        name=StageName.CONFIDENCE_RATED_CLOSE,
        label="Confidence-Rated Close",
        duration_min=2, duration_max=2,
        purpose="Calibration and reflection — SRL close, self-evaluation",
        zull_phase="Reflect",
    ),
)

STAGE_SPECS_BY_NAME: dict[StageName, StageSpec] = {s.name: s for s in STAGE_SPECS}


# ---------------------------------------------------------------------------
# Zull cycle
# ---------------------------------------------------------------------------

class ZullPhase(str, Enum):
    """The four phases of the Zull learning cycle."""

    EXPERIENCE = "Experience"
    REFLECT = "Reflect"
    CREATE = "Create"
    ACT = "Act"


@dataclass
class ZullCycle:
    """Implements the 4-stage Zull learning cycle.

    The cycle is iterative: Act produces new Experience, which re-enters
    Reflect. Each phase has a name, a cognitive process, and a set of
    facilitation strategies.

    Zull's key insight: learning is not information transfer but the
    physical rewiring of the brain through a cycle of experience,
    reflection, creation of new connections, and active testing.
    """

    phase_descriptions: dict[ZullPhase, str] = field(default_factory=lambda: {
        ZullPhase.EXPERIENCE: (
            "Concrete sensory and emotional experience — the raw material "
            "of learning. The brain encodes what is attended to."
        ),
        ZullPhase.REFLECT: (
            "Deliberate reflection on the experience — consolidating, "
            "finding patterns, connecting to prior knowledge. This is "
            "where the brain reorganises."
        ),
        ZullPhase.CREATE: (
            "Active creation of new mental models — generating hypotheses, "
            "building schemas, constructing understanding. The brain "
            "forms new connections."
        ),
        ZullPhase.ACT: (
            "Active testing of the new model — applying it in practice, "
            "getting feedback, refining. The brain strengthens what is used."
        ),
    })

    phase_strategies: dict[ZullPhase, list[str]] = field(default_factory=lambda: {
        ZullPhase.EXPERIENCE: [
            "Present concrete, sensory-rich material",
            "Engage attention through novelty or relevance",
            "Connect to the learner's existing knowledge",
            "Use stories, cases, or demonstrations",
        ],
        ZullPhase.REFLECT: [
            "Ask the learner to summarise in their own words",
            "Prompt comparison with prior examples",
            "Encourage identification of patterns",
            "Allow incubation time — do not rush",
        ],
        ZullPhase.CREATE: [
            "Guide construction of a worked example",
            "Ask the learner to generate a new example",
            "Scaffold with partial solutions",
            "Encourage hypothesis formation",
        ],
        ZullPhase.ACT: [
            "Provide varied practice contexts",
            "Give immediate, specific feedback",
            "Ask the learner to teach the concept back",
            "Test in conditions different from study",
        ],
    })

    def phases(self) -> list[ZullPhase]:
        """Return the four phases in cycle order."""
        return [ZullPhase.EXPERIENCE, ZullPhase.REFLECT,
                ZullPhase.CREATE, ZullPhase.ACT]

    def description(self, phase: ZullPhase) -> str:
        return self.phase_descriptions[phase]

    def strategies(self, phase: ZullPhase) -> list[str]:
        return list(self.phase_strategies[phase])

    def next_phase(self, phase: ZullPhase) -> ZullPhase:
        """Advance to the next phase in the cycle (wraps around)."""
        phases = self.phases()
        idx = phases.index(phase)
        return phases[(idx + 1) % len(phases)]

    def stages_for_phase(self, phase: ZullPhase) -> list[StageName]:
        """Return the session stages that primarily serve this Zull phase."""
        return [s.name for s in STAGE_SPECS if s.zull_phase == phase.value]

    def to_dict(self) -> dict:
        return {
            "phases": [p.value for p in self.phases()],
            "descriptions": {p.value: self.phase_descriptions[p]
                             for p in self.phases()},
            "strategies": {p.value: self.phase_strategies[p]
                           for p in self.phases()},
        }


# ---------------------------------------------------------------------------
# Session template
# ---------------------------------------------------------------------------

@dataclass
class SessionTemplate:
    """The 6-stage session structure.

    Defines the canonical session flow: Launch → Daily Retrieval →
    Episodic Hook → Guided Construction → Active Testing →
    Confidence-Rated Close.

    Each stage has a time budget, a purpose, and a mapping to the Zull
    cycle. The template can be customised per session type (e.g. a
    reflection session reorders stages to emphasise Reflect).
    """

    stages: list[StageSpec] = field(default_factory=lambda: list(STAGE_SPECS))
    session_type: SessionType = SessionType.PRACTICE
    total_duration_min: int = 0  # computed on init

    def __post_init__(self):
        self.total_duration_min = sum(s.duration_max for s in self.stages)

    @classmethod
    def for_type(cls, session_type: SessionType) -> "SessionTemplate":
        """Build a template adapted to the given session type.

        Different session types reorder or reweight stages:
          - practice: standard 6-stage flow
          - review: emphasises Daily Retrieval and Active Testing
          - checkup: emphasises Active Testing and Confidence-Rated Close
          - homework: emphasises Guided Construction and Active Testing
          - explore: emphasises Episodic Hook and Guided Construction
          - reflection: emphasises Confidence-Rated Close and Episodic Hook
        """
        base = list(STAGE_SPECS)
        if session_type == SessionType.PRACTICE:
            pass  # canonical order
        elif session_type == SessionType.REVIEW:
            # Retrieval-heavy: move Daily Retrieval earlier emphasis
            base = _reorder_stages(base, [
                StageName.LAUNCH,
                StageName.DAILY_RETRIEVAL,
                StageName.ACTIVE_TESTING,
                StageName.EPISODIC_HOOK,
                StageName.GUIDED_CONSTRUCTION,
                StageName.CONFIDENCE_RATED_CLOSE,
            ])
        elif session_type == SessionType.CHECKUP:
            # Assessment-heavy: testing and calibration
            base = _reorder_stages(base, [
                StageName.LAUNCH,
                StageName.DAILY_RETRIEVAL,
                StageName.ACTIVE_TESTING,
                StageName.CONFIDENCE_RATED_CLOSE,
                StageName.EPISODIC_HOOK,
                StageName.GUIDED_CONSTRUCTION,
            ])
        elif session_type == SessionType.HOMEWORK:
            # Construction-heavy: guided practice and application
            base = _reorder_stages(base, [
                StageName.LAUNCH,
                StageName.EPISODIC_HOOK,
                StageName.GUIDED_CONSTRUCTION,
                StageName.ACTIVE_TESTING,
                StageName.DAILY_RETRIEVAL,
                StageName.CONFIDENCE_RATED_CLOSE,
            ])
        elif session_type == SessionType.EXPLORE:
            # Discovery-heavy: hook and construction
            base = _reorder_stages(base, [
                StageName.LAUNCH,
                StageName.EPISODIC_HOOK,
                StageName.GUIDED_CONSTRUCTION,
                StageName.DAILY_RETRIEVAL,
                StageName.ACTIVE_TESTING,
                StageName.CONFIDENCE_RATED_CLOSE,
            ])
        elif session_type == SessionType.REFLECTION:
            # Reflection-heavy: close and hook
            base = _reorder_stages(base, [
                StageName.LAUNCH,
                StageName.DAILY_RETRIEVAL,
                StageName.EPISODIC_HOOK,
                StageName.CONFIDENCE_RATED_CLOSE,
                StageName.GUIDED_CONSTRUCTION,
                StageName.ACTIVE_TESTING,
            ])
        return cls(stages=base, session_type=session_type)

    def stage(self, name: StageName) -> StageSpec:
        return STAGE_SPECS_BY_NAME[name]

    def stage_names(self) -> list[StageName]:
        return [s.name for s in self.stages]

    def to_dict(self) -> dict:
        return {
            "session_type": self.session_type.value,
            "stages": [s.to_dict() for s in self.stages],
            "total_duration_min": self.total_duration_min,
        }


def _reorder_stages(base: list[StageSpec],
                    order: list[StageName]) -> list[StageSpec]:
    """Reorder stages according to the given StageName sequence."""
    by_name = {s.name: s for s in base}
    return [by_name[n] for n in order]


# ---------------------------------------------------------------------------
# Forethought prompts (Zimmerman SRL — forethought phase)
# ---------------------------------------------------------------------------

@dataclass
class ForethoughtPrompt:
    """Zimmerman's Self-Regulated Learning forethought phase prompts.

    The forethought phase encompasses:
      * Task analysis (goal-setting, strategic planning)
      * Self-motivation beliefs (self-efficacy, outcome expectations,
        intrinsic interest, learning goal orientation)

    These prompts are delivered at the Launch stage to prime the learner
    for the session ahead.
    """

    prompt_id: str
    category: str  # task_analysis | self_motivation
    text: str
    stage: StageName = StageName.LAUNCH

    def to_dict(self) -> dict:
        return asdict(self)


# Prompt bank — keyed by (category, session_type)
FORETHOUGHT_PROMPTS: dict[tuple[str, SessionType], list[ForethoughtPrompt]] = {
    ("task_analysis", SessionType.PRACTICE): [
        ForethoughtPrompt(
            "ta_practice_1", "task_analysis",
            "Before we begin: what is the single skill you most want to "
            "strengthen in this session? Name it specifically.",
        ),
        ForethoughtPrompt(
            "ta_practice_2", "task_analysis",
            "Look at the session plan. Which stage do you expect to find "
            "hardest, and what will you do when you hit that difficulty?",
        ),
    ],
    ("task_analysis", SessionType.REVIEW): [
        ForethoughtPrompt(
            "ta_review_1", "task_analysis",
            "You have items due for retrieval. Before starting: how many "
            "do you expect to recall easily, and which ones do you expect "
            "to struggle with?",
        ),
        ForethoughtPrompt(
            "ta_review_2", "task_analysis",
            "Set a retrieval goal: what percentage of due items do you "
            "aim to recall correctly? Write it down.",
        ),
    ],
    ("task_analysis", SessionType.CHECKUP): [
        ForethoughtPrompt(
            "ta_checkup_1", "task_analysis",
            "This is a checkup session. Before testing: what do you "
            "believe you have mastered, and what do you believe you "
            "have not? Be specific.",
        ),
        ForethoughtPrompt(
            "ta_checkup_2", "task_analysis",
            "Rate your confidence in each skill area from 0 to 10. "
            "These ratings will be compared with your actual performance.",
        ),
    ],
    ("task_analysis", SessionType.HOMEWORK): [
        ForethoughtPrompt(
            "ta_homework_1", "task_analysis",
            "Before we start the construction work: what is the "
            "learning objective for this session? State it in one "
            "sentence.",
        ),
        ForethoughtPrompt(
            "ta_homework_2", "task_analysis",
            "What prerequisite knowledge will you need? Identify any "
            "gaps before we begin the guided steps.",
        ),
    ],
    ("task_analysis", SessionType.EXPLORE): [
        ForethoughtPrompt(
            "ta_explore_1", "task_analysis",
            "We are exploring new material. What do you already know "
            "about this topic? List three things.",
        ),
        ForethoughtPrompt(
            "ta_explore_2", "task_analysis",
            "What question do you most want answered by the end of "
            "this session? Write it down — we will return to it.",
        ),
    ],
    ("task_analysis", SessionType.REFLECTION): [
        ForethoughtPrompt(
            "ta_reflection_1", "task_analysis",
            "Before we reflect: what happened in your last session that "
            "is still on your mind? Name the moment.",
        ),
        ForethoughtPrompt(
            "ta_reflection_2", "task_analysis",
            "What would you like to understand better about your own "
            "learning process today?",
        ),
    ],
    ("self_motivation", SessionType.PRACTICE): [
        ForethoughtPrompt(
            "sm_practice_1", "self_motivation",
            "Rate your confidence that you will improve in this "
            "session, from 0 to 10. What would move it up by one point?",
        ),
        ForethoughtPrompt(
            "sm_practice_2", "self_motivation",
            "What is one thing you learned recently that surprised you? "
            "Hold that curiosity — we will build on it.",
        ),
    ],
    ("self_motivation", SessionType.REVIEW): [
        ForethoughtPrompt(
            "sm_review_1", "self_motivation",
            "Retrieval practice feels effortful. That effort is the "
            "point — it is what strengthens memory. Remind yourself: "
            "struggle now means easier recall later.",
        ),
        ForethoughtPrompt(
            "sm_review_2", "self_motivation",
            "You have been consistent with your reviews. That "
            "consistency is a skill in itself. Acknowledge it.",
        ),
    ],
    ("self_motivation", SessionType.CHECKUP): [
        ForethoughtPrompt(
            "sm_checkup_1", "self_motivation",
            "A checkup is not a judgement — it is a measurement. "
            "Your only goal is an honest reading of where you are.",
        ),
        ForethoughtPrompt(
            "sm_checkup_2", "self_motivation",
            "Whatever the results, they are information, not a "
            "verdict. What matters is what you do next.",
        ),
    ],
    ("self_motivation", SessionType.HOMEWORK): [
        ForethoughtPrompt(
            "sm_homework_1", "self_motivation",
            "Building new understanding takes patience. You will "
            "not get every step right the first time — that is "
            "expected and it is how learning works.",
        ),
        ForethoughtPrompt(
            "sm_homework_2", "self_motivation",
            "Think of a time you understood something that once "
            "seemed impossible. You did it then; you can do it now.",
        ),
    ],
    ("self_motivation", SessionType.EXPLORE): [
        ForethoughtPrompt(
            "sm_explore_1", "self_motivation",
            "Exploration rewards curiosity, not correctness. Give "
            "permission yourself to not know — that is the starting "
            "point of discovery.",
        ),
        ForethoughtPrompt(
            "sm_explore_2", "self_motivation",
            "What is something you have always wanted to understand? "
            "If it is related to today's material, hold that "
            "question — it will make the session more meaningful.",
        ),
    ],
    ("self_motivation", SessionType.REFLECTION): [
        ForethoughtPrompt(
            "sm_reflection_1", "self_motivation",
            "Reflection is not about judging yourself — it is about "
            "understanding your own process. Approach it with "
            "curiosity, not criticism.",
        ),
        ForethoughtPrompt(
            "sm_reflection_2", "self_motivation",
            "You are building the skill of self-awareness. Every "
            "reflection makes the next one easier and more accurate.",
        ),
    ],
}


def get_forethought_prompts(session_type: SessionType,
                            category: str | None = None) -> list[ForethoughtPrompt]:
    """Return forethought prompts for the given session type.

    If category is None, returns all prompts (task_analysis + self_motivation).
    """
    if category is not None:
        return list(FORETHOUGHT_PROMPTS.get((category, session_type), []))
    out: list[ForethoughtPrompt] = []
    for cat in ("task_analysis", "self_motivation"):
        out.extend(FORETHOUGHT_PROMPTS.get((cat, session_type), []))
    return out


# ---------------------------------------------------------------------------
# Reflection prompts (Zimmerman SRL — self-reflection phase)
# ---------------------------------------------------------------------------

@dataclass
class ReflectionPrompt:
    """Zimmerman's Self-Regulated Learning self-reflection phase prompts.

    The self-reflection phase encompasses:
      * Self-evaluation (comparing performance against a standard)
      * Attribution (causal explanations for success or failure)
      * Adaptivity (adjusting strategies for future learning)

    These prompts are delivered at the Confidence-Rated Close stage.
    """

    prompt_id: str
    category: str  # self_evaluation | attribution | adaptivity
    text: str
    stage: StageName = StageName.CONFIDENCE_RATED_CLOSE

    def to_dict(self) -> dict:
        return asdict(self)


REFLECTION_PROMPTS: dict[tuple[str, SessionType], list[ReflectionPrompt]] = {
    ("self_evaluation", SessionType.PRACTICE): [
        ReflectionPrompt(
            "se_practice_1", "self_evaluation",
            "Rate your performance in this session from 0 to 10. "
            "What evidence supports that rating?",
        ),
        ReflectionPrompt(
            "se_practice_2", "self_evaluation",
            "Which item was hardest? What made it hard — was it "
            "the concept, the application, or the transfer?",
        ),
    ],
    ("self_evaluation", SessionType.REVIEW): [
        ReflectionPrompt(
            "se_review_1", "self_evaluation",
            "How many due items did you recall? How does that "
            "compare to your pre-session prediction?",
        ),
        ReflectionPrompt(
            "se_review_2", "self_evaluation",
            "Which items did you forget? What do they have in "
            "common — recency, difficulty, or similarity?",
        ),
    ],
    ("self_evaluation", SessionType.CHECKUP): [
        ReflectionPrompt(
            "se_checkup_1", "self_evaluation",
            "Compare your pre-session confidence ratings with your "
            "actual performance. Where were you accurate? Where "
            "were you off?",
        ),
        ReflectionPrompt(
            "se_checkup_2", "self_evaluation",
            "What is the single most important thing this checkup "
            "revealed about your current state?",
        ),
    ],
    ("self_evaluation", SessionType.HOMEWORK): [
        ReflectionPrompt(
            "se_homework_1", "self_evaluation",
            "Did you meet the learning objective you set at the "
            "start? What evidence do you have?",
        ),
        ReflectionPrompt(
            "se_homework_2", "self_evaluation",
            "Which guided step was most valuable? Which was "
            "least helpful? Why?",
        ),
    ],
    ("self_evaluation", SessionType.EXPLORE): [
        ReflectionPrompt(
            "se_explore_1", "self_evaluation",
            "Did the session answer the question you wrote down "
            "at the start? If not, what would you need to "
            "explore next?",
        ),
        ReflectionPrompt(
            "se_explore_2", "self_evaluation",
            "What surprised you most in this session? What does "
            "that tell you about your existing mental models?",
        ),
    ],
    ("self_evaluation", SessionType.REFLECTION): [
        ReflectionPrompt(
            "se_reflection_1", "self_evaluation",
            "Looking back at the session you reflected on: what "
            "would you do differently if you could repeat it?",
        ),
        ReflectionPrompt(
            "se_reflection_2", "self_evaluation",
            "What have you learned about your own learning "
            "process that you did not know before?",
        ),
    ],
    ("attribution", SessionType.PRACTICE): [
        ReflectionPrompt(
            "at_practice_1", "attribution",
            "If you succeeded today, what caused that success — "
            "effort, strategy, prior knowledge, or task ease? "
            "Be honest about which.",
        ),
        ReflectionPrompt(
            "at_practice_2", "attribution",
            "If you struggled today, what caused the difficulty — "
            "was it the material, your preparation, your approach, "
            "or something else?",
        ),
    ],
    ("attribution", SessionType.REVIEW): [
        ReflectionPrompt(
            "at_review_1", "attribution",
            "When you recalled an item easily, what made it easy? "
            "When you forgot one, what caused the forgetting?",
        ),
        ReflectionPrompt(
            "at_review_2", "attribution",
            "Is there a pattern in what you remember and what you "
            "forget? What does that pattern suggest about your "
            "study approach?",
        ),
    ],
    ("attribution", SessionType.CHECKUP): [
        ReflectionPrompt(
            "at_checkup_1", "attribution",
            "Your confidence ratings and your performance have "
            "been compared. Where you were overconfident, what "
            "explains the gap? Where underconfident, what "
            "explains that?",
        ),
        ReflectionPrompt(
            "at_checkup_2", "attribution",
            "What is the most useful thing you can learn from "
            "the gap between what you expected and what happened?",
        ),
    ],
    ("attribution", SessionType.HOMEWORK): [
        ReflectionPrompt(
            "at_homework_1", "attribution",
            "When a guided step worked, what made it work? "
            "When you got stuck, what was the cause?",
        ),
        ReflectionPrompt(
            "at_homework_2", "attribution",
            "Did your approach change during the session? If so, "
            "what triggered the change?",
        ),
    ],
    ("attribution", SessionType.EXPLORE): [
        ReflectionPrompt(
            "at_explore_1", "attribution",
            "What helped you engage with the new material — "
            "curiosity, relevance, novelty, or something else?",
        ),
        ReflectionPrompt(
            "at_explore_2", "attribution",
            "When you felt lost, what brought you back? That "
            "strategy is worth remembering.",
        ),
    ],
    ("attribution", SessionType.REFLECTION): [
        ReflectionPrompt(
            "at_reflection_1", "attribution",
            "What caused you to learn from this reflection "
            "session? What made it different from just "
            "reviewing the material?",
        ),
        ReflectionPrompt(
            "at_reflection_2", "attribution",
            "If you could attribute your growth in "
            "self-awareness to one thing, what would it be?",
        ),
    ],
    ("adaptivity", SessionType.PRACTICE): [
        ReflectionPrompt(
            "ad_practice_1", "adaptivity",
            "Based on today's session, what will you do "
            "differently in your next practice session? Be "
            "specific.",
        ),
        ReflectionPrompt(
            "ad_practice_2", "adaptivity",
            "What is one strategy you used today that you "
            "should use more often? What is one you should "
            "use less?",
        ),
    ],
    ("adaptivity", SessionType.REVIEW): [
        ReflectionPrompt(
            "ad_review_1", "adaptivity",
            "Given today's retrieval results, should you "
            "adjust your review frequency? How?",
        ),
        ReflectionPrompt(
            "ad_review_2", "adaptivity",
            "What is one change you will make to your "
            "study schedule based on what you learned today?",
        ),
    ],
    ("adaptivity", SessionType.CHECKUP): [
        ReflectionPrompt(
            "ad_checkup_1", "adaptivity",
            "This checkup gives you a snapshot. What is the "
            "one adjustment you will make to your learning "
            "plan based on it?",
        ),
        ReflectionPrompt(
            "ad_checkup_2", "adaptivity",
            "If you could redesign your next month of "
            "study based on today's results, what would "
            "you change?",
        ),
    ],
    ("adaptivity", SessionType.HOMEWORK): [
        ReflectionPrompt(
            "ad_homework_1", "adaptivity",
            "What did you learn about how you construct "
            "understanding that you can apply to the next "
            "topic?",
        ),
        ReflectionPrompt(
            "ad_homework_2", "adaptivity",
            "Should you revisit any of the guided steps "
            "before the next session? Which ones and why?",
        ),
    ],
    ("adaptivity", SessionType.EXPLORE): [
        ReflectionPrompt(
            "ad_explore_1", "adaptivity",
            "What new question emerged from this exploration "
            "that you want to pursue next?",
        ),
        ReflectionPrompt(
            "ad_explore_2", "adaptivity",
            "How will you follow up on what you discovered "
            "today? What is the next step?",
        ),
    ],
    ("adaptivity", SessionType.REFLECTION): [
        ReflectionPrompt(
            "ad_reflection_1", "adaptivity",
            "What have you learned about reflecting that "
            "will make your next reflection more useful?",
        ),
        ReflectionPrompt(
            "ad_reflection_2", "adaptivity",
            "How will you use what you discovered about "
            "yourself in future sessions?",
        ),
    ],
}


def get_reflection_prompts(session_type: SessionType,
                           category: str | None = None) -> list[ReflectionPrompt]:
    """Return reflection prompts for the given session type.

    If category is None, returns all prompts (self_evaluation + attribution
    + adaptivity).
    """
    if category is not None:
        return list(REFLECTION_PROMPTS.get((category, session_type), []))
    out: list[ReflectionPrompt] = []
    for cat in ("self_evaluation", "attribution", "adaptivity"):
        out.extend(REFLECTION_PROMPTS.get((cat, session_type), []))
    return out


# ---------------------------------------------------------------------------
# Session events and attempts
# ---------------------------------------------------------------------------

@dataclass
class SessionEvent:
    """A timestamped event during a session."""

    event_type: str  # stage_enter | stage_exit | attempt | prompt_shown | prompt_answered
    stage: StageName | None
    timestamp: float
    data: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SessionAttempt:
    """A single question attempt within a session."""

    qid: str
    skill_id: str
    correct: bool
    grade: int  # 1-4 (FSRS scale)
    confidence: float | None  # 0-1
    latency_ms: int
    response: str
    stage: StageName
    timestamp: float

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Session runner
# ---------------------------------------------------------------------------

@dataclass
class SessionConfig:
    """Configuration for a session run."""

    learner_id: str
    session_type: SessionType = SessionType.PRACTICE
    day: float = 0.0  # days since learner epoch
    limit: int = 20  # max items in retrieval queue
    target_success_rate: float = 0.85  # anti-pampering target
    enable_forethought: bool = True
    enable_reflection: bool = True
    rng_seed: int = 42


class SessionRunner:
    """Manages the flow of a learning session through the 6-stage structure.

    The runner:
      1. Builds a SessionTemplate for the session type
      2. Generates forethought prompts at Launch
      3. Drives the FSRS due-queue at Daily Retrieval
      4. Presents an Episodic Hook
      5. Guides Construction with scaffolded steps
      6. Tests actively in varied contexts
      7. Closes with confidence rating and reflection prompts

    It integrates with the existing scheduler (FSRS), tracing (BKT/IRT),
    and questiongen modules.
    """

    def __init__(self, config: SessionConfig):
        self.config = config
        self.template = SessionTemplate.for_type(config.session_type)
        self.zull = ZullCycle()
        self.events: list[SessionEvent] = []
        self.attempts: list[SessionAttempt] = []
        self.current_stage: StageName | None = None
        self.stage_start_time: float = 0.0
        self._rng = random.Random(config.rng_seed)
        self._forethought_prompts: list[ForethoughtPrompt] = []
        self._reflection_prompts: list[ReflectionPrompt] = []
        self._queue: list[Card] = []
        self._queue_index: int = 0
        self._skill_states: dict[str, BKTSkill] = {}
        self._theta: float = 0.0  # learner ability estimate

    # -- public API ---------------------------------------------------------

    def start(self) -> dict:
        """Start the session: generate forethought prompts, build queue."""
        self._log_event("session_start", None, {
            "session_type": self.config.session_type.value,
            "learner_id": self.config.learner_id,
        })
        if self.config.enable_forethought:
            self._forethought_prompts = get_forethought_prompts(
                self.config.session_type)
        self._reflection_prompts = get_reflection_prompts(
            self.config.session_type)
        return {
            "session_type": self.config.session_type.value,
            "template": self.template.to_dict(),
            "forethought_prompts": [p.to_dict() for p in self._forethought_prompts],
            "total_stages": len(self.template.stages),
        }

    def enter_stage(self, stage: StageName) -> dict:
        """Enter a session stage: log the transition, return stage info."""
        spec = self.template.stage(stage)
        self.current_stage = stage
        self.stage_start_time = time.time()
        self._log_event("stage_enter", stage, {
            "label": spec.label,
            "duration_min": spec.duration_min,
            "duration_max": spec.duration_max,
            "purpose": spec.purpose,
            "zull_phase": spec.zull_phase,
        })
        result = {
            "stage": stage.value,
            "label": spec.label,
            "purpose": spec.purpose,
            "zull_phase": spec.zull_phase,
            "zull_strategies": self.zull.strategies(
                ZullPhase(spec.zull_phase)),
        }
        if stage == StageName.LAUNCH and self._forethought_prompts:
            result["forethought_prompts"] = [
                p.to_dict() for p in self._forethought_prompts]
        if stage == StageName.CONFIDENCE_RATED_CLOSE and self._reflection_prompts:
            result["reflection_prompts"] = [
                p.to_dict() for p in self._reflection_prompts]
        return result

    def exit_stage(self, stage: StageName) -> dict:
        """Exit a session stage: log the transition, return summary."""
        elapsed = time.time() - self.stage_start_time
        self._log_event("stage_exit", stage, {
            "elapsed_seconds": round(elapsed, 2),
        })
        stage_attempts = [a for a in self.attempts if a.stage == stage]
        return {
            "stage": stage.value,
            "elapsed_seconds": round(elapsed, 2),
            "n_attempts": len(stage_attempts),
            "n_correct": sum(1 for a in stage_attempts if a.correct),
        }

    def build_retrieval_queue(self, cards: list[Card]) -> list[Card]:
        """Build the FSRS due-queue for the Daily Retrieval stage."""
        self._queue = build_queue(cards, self.config.day, limit=self.config.limit)
        self._queue_index = 0
        self._log_event("queue_built", StageName.DAILY_RETRIEVAL, {
            "n_due": len(self._queue),
            "limit": self.config.limit,
        })
        return self._queue

    def next_retrieval_item(self) -> Card | None:
        """Get the next item from the retrieval queue."""
        if self._queue_index >= len(self._queue):
            return None
        card = self._queue[self._queue_index]
        self._queue_index += 1
        return card

    def record_attempt(self, qid: str, skill_id: str, correct: bool,
                       grade: int, confidence: float | None,
                       latency_ms: int, response: str) -> SessionAttempt:
        """Record a question attempt during the session."""
        attempt = SessionAttempt(
            qid=qid, skill_id=skill_id, correct=correct,
            grade=grade, confidence=confidence,
            latency_ms=latency_ms, response=response,
            stage=self.current_stage or StageName.DAILY_RETRIEVAL,
            timestamp=time.time(),
        )
        self.attempts.append(attempt)
        self._log_event("attempt", attempt.stage, {
            "qid": qid, "skill_id": skill_id, "correct": correct,
            "grade": grade, "confidence": confidence,
        })
        return attempt

    def get_calibration(self) -> dict:
        """Compute calibration statistics for the session's attempts."""
        pairs = [(a.confidence, a.correct) for a in self.attempts
                 if a.confidence is not None]
        return calibration_stats(pairs)

    def get_session_summary(self) -> dict:
        """Produce an honest session summary."""
        n = len(self.attempts)
        if n == 0:
            return {
                "n": 0,
                "verdict": "no data",
                "statement": "No attempts recorded in this session.",
            }
        correct = sum(1 for a in self.attempts if a.correct)
        acc = correct / n
        lat = [a.latency_ms for a in self.attempts if a.latency_ms > 0]
        med_lat = sorted(lat)[len(lat) // 2] if lat else None
        cal = self.get_calibration()
        if acc >= 0.9:
            verdict = "under-challenged"
            stmt = (f"{correct}/{n} correct ({acc:.0%}). This set was too "
                    "easy to produce learning; difficulty will increase.")
        elif acc >= 0.75:
            verdict = "in the productive band"
            stmt = (f"{correct}/{n} correct ({acc:.0%}). This is the band "
                    "where learning is fastest.")
        elif acc >= 0.5:
            verdict = "struggling productively"
            stmt = (f"{correct}/{n} correct ({acc:.0%}). Below the optimal "
                    "band; the system will reduce load on weakest skills.")
        else:
            verdict = "over-loaded"
            stmt = (f"{correct}/{n} correct ({acc:.0%}). The material is "
                    "currently beyond reach at this granularity.")
        return {
            "n": n,
            "correct": correct,
            "accuracy": round(acc, 3),
            "median_latency_ms": med_lat,
            "verdict": verdict,
            "statement": stmt,
            "calibration": cal,
            "session_type": self.config.session_type.value,
        }

    def close(self) -> dict:
        """Close the session: return final summary and reflection prompts."""
        self._log_event("session_close", None, {
            "n_attempts": len(self.attempts),
            "n_stages_completed": len(set(
                e.stage for e in self.events
                if e.event_type == "stage_enter" and e.stage is not None)),
        })
        summary = self.get_session_summary()
        if self.config.enable_reflection:
            summary["reflection_prompts"] = [
                p.to_dict() for p in self._reflection_prompts]
        return summary

    # -- stage-specific helpers ---------------------------------------------

    def get_episodic_hook(self, questions: list[Question]) -> dict | None:
        """Select an episodic hook from available questions.

        Prefers questions with rich source spans (stories, cases) that
        can serve as concrete anchors for the session.
        """
        if not questions:
            return None
        # Prefer questions with longer source spans (more contextual richness)
        candidates = [q for q in questions if len(q.source_span) > 80]
        if not candidates:
            candidates = questions
        chosen = self._rng.choice(candidates)
        return {
            "question": chosen.to_dict(),
            "hook_type": "concrete_case",
            "purpose": "Episodic encoding anchor — a concrete example to "
                       "which the session's abstract concepts can attach.",
        }

    def get_guided_steps(self, questions: list[Question],
                         skill_id: str | None = None) -> list[dict]:
        """Generate guided construction steps from questions.

        Orders questions by Bloom level (remember → understand → apply)
        and wraps each in a scaffolding frame.
        """
        pool = [q for q in questions if not skill_id or q.skill_id == skill_id]
        if not pool:
            pool = questions
        bloom_order = {"remember": 0, "understand": 1, "apply": 2,
                       "analyse": 3, "evaluate": 4, "create": 5}
        pool.sort(key=lambda q: bloom_order.get(q.bloom, 9))
        steps = []
        for i, q in enumerate(pool[:5]):
            steps.append({
                "step_number": i + 1,
                "question": q.to_dict(),
                "scaffold": self._scaffold_for(q),
                "bloom_level": q.bloom,
            })
        return steps

    def get_active_tests(self, questions: list[Question],
                         exclude_qids: set[str] | None = None) -> list[dict]:
        """Select active testing items in varied contexts.

        Uses IRT-based selection to target the configured success rate,
        excluding items already used in the session.
        """
        exclude = exclude_qids or set(a.qid for a in self.attempts)
        pool = [q for q in questions if q.qid not in exclude]
        if not pool:
            return []
        # Convert questions to IRT items for selection
        items = []
        for q in pool:
            item = Item(
                item_id=q.qid,
                a=1.0,
                b=q.difficulty_hint,
                c=0.0,
                skill_id=q.skill_id,
            )
            items.append(item)
        selected = []
        used: set[str] = set()
        for _ in range(min(5, len(items))):
            chosen = select_next_item(items, self._theta,
                                      target_p=self.config.target_success_rate,
                                      exclude=used)
            if chosen is None:
                break
            used.add(chosen.item_id)
            q = next(q for q in pool if q.qid == chosen.item_id)
            selected.append({
                "question": q.to_dict(),
                "target_p": self.config.target_success_rate,
                "context": "varied" if len(selected) % 2 == 0 else "familiar",
            })
        return selected

    def update_skill(self, skill_id: str, correct: bool) -> float:
        """Update BKT skill state and return new mastery probability."""
        if skill_id not in self._skill_states:
            self._skill_states[skill_id] = BKTSkill(skill_id)
        skill = self._skill_states[skill_id]
        p_known = skill.update(correct)
        return p_known

    def update_theta(self, responses: list[tuple[Item, bool]]) -> float:
        """Update learner ability estimate via IRT MLE."""
        from .tracing import update_theta_mle
        self._theta = update_theta_mle(self._theta, responses)
        return self._theta

    # -- internal helpers ---------------------------------------------------

    def _log_event(self, event_type: str, stage: StageName | None,
                   data: dict) -> None:
        self.events.append(SessionEvent(
            event_type=event_type,
            stage=stage,
            timestamp=time.time(),
            data=data,
        ))

    def _scaffold_for(self, question: Question) -> str:
        """Generate a scaffolding hint based on question type."""
        scaffolds = {
            "cloze": "Recall the term from memory. If stuck, think about "
                     "the context and what word would fit grammatically.",
            "definition": "Start with the term, then explain it in your "
                          "own words. Use an example if possible.",
            "wh_question": "Read the gap, predict the answer, then "
                           "verify against the source.",
            "true_false_justify": "State your verdict first, then justify "
                                  "it with specific evidence.",
            "ordering": "Identify the logical sequence, then check for "
                        "cause-effect relationships.",
            "error_spotting": "Compare each part of the statement with "
                              "the source. The error will be a detail.",
            "worked_example_completion": "Follow the steps shown, then "
                                         "compute the final result.",
            "analogy": "Identify the relationship in the first pair, "
                       "then find a parallel relationship.",
            "list_recall": "Recall the items from memory. Do not look "
                           "at the source until you have listed them all.",
            "numeric": "Identify the quantities, their units, and the "
                        "relationship between them.",
            "causal_chain": "Identify the cause and effect, then explain "
                            "the mechanism connecting them.",
            "compare_contrast": "Identify both sides, then find the "
                                "single most important difference.",
            "counterexample": "Think of a case where the claim would "
                              "fail. Be specific.",
            "transfer": "Identify the principle, then find a new domain "
                        "where it applies.",
            "socratic": "Identify the assumption that must hold for the "
                        "statement to be true.",
            "feynman": "Explain simply, then identify what you could "
                       "not simplify.",
            "prediction_verify": "Commit to your prediction, then "
                                 "compare with the source.",
            "steelman": "Build the strongest opposing case. Do not "
                        "strawman.",
        }
        return scaffolds.get(
            question.style,
            "Approach this step by step. If stuck, try a simpler version "
            "first.",
        )

    # -- serialisation ------------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "config": {
                "learner_id": self.config.learner_id,
                "session_type": self.config.session_type.value,
                "day": self.config.day,
                "limit": self.config.limit,
                "target_success_rate": self.config.target_success_rate,
            },
            "template": self.template.to_dict(),
            "current_stage": self.current_stage.value if self.current_stage else None,
            "n_events": len(self.events),
            "n_attempts": len(self.attempts),
            "forethought_prompts": [p.to_dict() for p in self._forethought_prompts],
            "reflection_prompts": [p.to_dict() for p in self._reflection_prompts],
        }
