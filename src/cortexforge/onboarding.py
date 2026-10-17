"""First-run onboarding — extract the learner's actual shape before teaching.

The requirement: on first open, the system engages the learner in a range of
activities to work out what kind of learning system can be built for them.
This module defines that sequence as data, drives it as a state machine, and
produces a `LearningContract` — the explicit, falsifiable agreement about
what the system will do for this person.

Design rules:
  * Every probe has a purpose the learner can read. No dark patterns, no
    engagement-farming, no "just one more".
  * The sequence adapts: a probe is skipped when an earlier probe already
    answers its question, and the reason for the skip is recorded.
  * The learner can leave at any point; partial onboarding yields a valid
    contract with a smaller evidence base and says so.
  * The contract is falsifiable: it names what would prove it wrong.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Callable

# ---------------------------------------------------------------------------
# Probe definitions
# ---------------------------------------------------------------------------

@dataclass
class Probe:
    probe_id: str
    name: str
    purpose: str            # shown to the learner, in plain language
    minutes: float
    yields: list[str]       # contract fields this probe populates
    task_id: str = ""       # instruments.py task, if it is a behavioural task
    kind: str = "task"      # task | interview | calibration | source
    question: str = ""
    options: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    skip_if: str = ""       # expression key evaluated against answers

    def to_dict(self) -> dict:
        return asdict(self)


PROBES: list[Probe] = [
    Probe(
        probe_id="goal",
        name="What you are actually trying to do",
        purpose=("Everything downstream depends on this. A system built for "
                 "passing an exam is not the system built for understanding a "
                 "field for its own sake."),
        minutes=2, kind="interview", yields=["goal_type", "deadline_pressure"],
        question="Which of these is closest to why you are here?",
        options=[
            "Pass a specific exam or certification, with a date attached",
            "Understand a subject deeply, with no deadline",
            "Build a practical skill I will use at work",
            "Recover or rebuild ability I feel I have lost",
            "I am not sure yet — help me find out",
        ],
    ),
    Probe(
        probe_id="domain",
        name="What you are learning",
        purpose=("The subject determines which question styles are even "
                 "possible. Some subjects have no numeric content; some have "
                 "no causal chains; some are almost entirely procedural."),
        minutes=2, kind="interview", yields=["domain", "domain_shape"],
        question="Name the subject or subjects, and say whether it is mostly "
                 "facts, mostly procedures, mostly arguments, or a mix.",
    ),
    Probe(
        probe_id="source",
        name="What you already have to work from",
        purpose=("Your own material is the best source, because the questions "
                 "will be in your vocabulary and about your syllabus. If you "
                 "have nothing yet, the system will find sources instead."),
        minutes=3, kind="source", yields=["source_available", "source_kind"],
        question="Paste text, give a file path, or connect a note system "
                 "(Notion, Obsidian). Or say 'none' and the system will fetch "
                 "material for you.",
    ),
    Probe(
        probe_id="baseline_cognition",
        name="Baseline: attention and working memory",
        purpose=("Sets the starting difficulty so the first real session is not "
                 "wasted. Two short tasks, about seven minutes total."),
        minutes=7, kind="task", yields=["baseline_difficulty", "inhibitory_control",
                                        "working_memory_updating"],
        task_id="flanker",
    ),
    Probe(
        probe_id="baseline_speed",
        name="Baseline: processing speed",
        purpose="How fast you can handle simple decisions, so pacing is set correctly.",
        minutes=2, kind="task", yields=["processing_speed"], task_id="pattern_comparison",
    ),
    Probe(
        probe_id="calibration_probe",
        name="How well you know what you know",
        purpose=("Most learners study the wrong things because their confidence "
                 "is miscalibrated. This measures the gap directly, in about "
                 "twelve questions."),
        minutes=4, kind="calibration", yields=["calibration_bias", "calibration_brier"],
        depends_on=["source"],
        skip_if="no_source",
    ),
    Probe(
        probe_id="social_baseline",
        name="How you behave in a group",
        purpose=("Learning is social: study groups, asking questions, admitting "
                 "confusion. These four short games show how you actually "
                 "behave when something is at stake, which is not always how "
                 "people describe themselves."),
        minutes=17, kind="task",
        yields=["fairness_norm_enforcement", "altruism", "cooperation",
                "strategic_reasoning"],
        task_id="ultimatum",
    ),
    Probe(
        probe_id="social_preference",
        name="How you weigh your outcome against someone else's",
        purpose="Four minutes of allocation choices; sets whether you need guardrails against being exploited.",
        minutes=4, kind="task", yields=["social_preference_orientation"],
        task_id="social_value_orientation",
    ),
    Probe(
        probe_id="mind_reading",
        name="Modelling what other people think",
        purpose=("Predicts how well you will handle material that requires "
                 "taking another's perspective — history, literature, "
                 "negotiation, debugging someone else's code."),
        minutes=5, kind="task", yields=["theory_of_mind"], task_id="false_belief",
    ),
    Probe(
        probe_id="connectedness",
        name="Your current social base",
        purpose=("Social contact is a cognitive intervention, not a separate "
                 "concern. This sets whether the system should build in "
                 "contact, and it is tracked over time."),
        minutes=3, kind="task", yields=["social_connectedness"],
        task_id="loneliness_ucla",
    ),
    Probe(
        probe_id="fog_baseline",
        name="Current mental clarity",
        purpose=("A baseline for the thing you may be trying to fix. Measured "
                 "the same way every time so the trend is real rather than "
                 "remembered."),
        minutes=3, kind="interview", yields=["fog_baseline", "fog_domains"],
        question="Over the last two weeks, how often have you had trouble with "
                 "each of: holding a thought, finding a word, following a "
                 "conversation, remembering why you walked into a room, "
                 "reading the same paragraph twice? Answer 0 (never) to 4 "
                 "(daily) for each.",
    ),
    Probe(
        probe_id="constraints",
        name="What you can realistically commit",
        purpose=("A plan you cannot follow is worse than no plan. This sets "
                 "session length and frequency to something that will actually "
                 "happen, and the system will hold you to it."),
        minutes=2, kind="interview", yields=["session_minutes", "days_per_week",
                                             "best_time"],
        question="How many minutes per session, how many days per week, and at "
                 "what time of day? Be honest rather than ambitious — the "
                 "schedule adapts to what you actually do, not what you intend.",
    ),
    Probe(
        probe_id="difficulty_preference",
        name="How hard you want it",
        purpose=("The system defaults to the difficulty band where learning is "
                 "fastest, which feels uncomfortable. This is where you decide "
                 "whether to accept that, knowing it will not feel good."),
        minutes=1, kind="interview", yields=["difficulty_setting"],
        question="The evidence says learning is fastest when you get about 85% "
                 "right — which means failing roughly one in seven items on "
                 "purpose. Do you want that (recommended), a gentler 70%, or "
                 "the hardest setting the system will allow?",
        options=["85% — the evidence-based band (recommended)",
                 "70% — gentler, slower, less frustrating",
                 "As hard as possible — I want to be pushed"],
    ),
]

PROBES_BY_ID = {p.probe_id: p for p in PROBES}


# ---------------------------------------------------------------------------
# Learning contract
# ---------------------------------------------------------------------------

@dataclass
class LearningContract:
    learner_id: str
    created_at: float = field(default_factory=time.time)
    goal_type: str = ""
    domain: str = ""
    domain_shape: str = ""
    source_available: bool = False
    source_kind: str = ""
    session_minutes: int = 20
    days_per_week: int = 4
    best_time: str = "unspecified"
    target_success_rate: float = 0.85
    difficulty_setting: str = "evidence_band"
    baseline_difficulty: float = 0.0
    fog_baseline: float | None = None
    fog_domains: dict = field(default_factory=dict)
    question_styles: list[str] = field(default_factory=list)
    intervention_plan: list[str] = field(default_factory=list)
    evidence_base: list[str] = field(default_factory=list)
    falsifiers: list[str] = field(default_factory=list)
    gaps: list[str] = field(default_factory=list)
    probes_completed: list[str] = field(default_factory=list)
    probes_skipped: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def summary(self) -> str:
        """Plain-language contract the learner can read and challenge."""
        lines = [
            f"WHAT THIS SYSTEM WILL DO FOR YOU",
            f"",
            f"Goal: {self.goal_type or 'not established'}",
            f"Subject: {self.domain or 'not established'} ({self.domain_shape or 'shape unknown'})",
            f"Source material: {'yes — ' + self.source_kind if self.source_available else 'none yet; the system will fetch material'}",
            f"",
            f"Sessions: {self.session_minutes} minutes, {self.days_per_week} days per week, {self.best_time}",
            f"Target success rate: {self.target_success_rate:.0%} — you will fail about "
            f"{1 - self.target_success_rate:.0%} of items by design.",
            f"",
            f"Question styles that fit your material: {', '.join(self.question_styles) or 'to be determined'}",
            f"",
            f"WHAT IT WILL DO ABOUT COGNITIVE LOAD",
        ]
        lines += [f"  - {x}" for x in self.intervention_plan] or ["  - (pending baseline)"]
        lines += ["", "WHAT WOULD PROVE THIS CONTRACT WRONG"]
        lines += [f"  - {x}" for x in self.falsifiers] or ["  - (none stated)"]
        if self.gaps:
            lines += ["", "WHAT IS STILL UNKNOWN"]
            lines += [f"  - {x}" for x in self.gaps]
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Onboarding state machine
# ---------------------------------------------------------------------------

class Onboarding:
    """Drives the probe sequence, adapting to what has already been learned."""

    def __init__(self, learner_id: str):
        self.learner_id = learner_id
        self.answers: dict[str, object] = {}
        self.completed: list[str] = []
        self.skipped: dict[str, str] = {}
        self.started_at = time.time()

    def next_probe(self) -> Probe | None:
        """Return the next probe to run, or None when onboarding is complete."""
        for probe in PROBES:
            if probe.probe_id in self.completed or probe.probe_id in self.skipped:
                continue
            if not all(d in self.completed for d in probe.depends_on):
                continue
            if probe.skip_if and self._should_skip(probe):
                self.skipped[probe.probe_id] = probe.skip_if
                continue
            return probe
        return None

    def _should_skip(self, probe: Probe) -> bool:
        if probe.skip_if == "no_source":
            return not self._source_present()
        return False

    def _source_present(self) -> bool:
        """A source exists if the source probe returned usable material.

        The source probe stores its raw answer under 'source'. Treat empty,
        whitespace, and the explicit words 'none'/'no'/'skip' as absent, and
        an explicit dict with source_available as authoritative.
        """
        raw = self.answers.get("source")
        if isinstance(raw, dict):
            return bool(raw.get("source_available"))
        if raw is None:
            return False
        text = str(raw).strip().lower()
        if not text or text in ("none", "no", "skip", "n/a", "na"):
            return False
        return True

    def record(self, probe_id: str, answer) -> None:
        """Record a probe result and mark it complete."""
        if probe_id not in PROBES_BY_ID:
            raise KeyError(f"unknown probe {probe_id!r}")
        self.answers[probe_id] = answer
        if probe_id not in self.completed:
            self.completed.append(probe_id)

    def skip(self, probe_id: str, reason: str) -> None:
        self.skipped[probe_id] = reason

    def progress(self) -> dict:
        total = len(PROBES)
        done = len(self.completed)
        remaining = [p.probe_id for p in PROBES
                     if p.probe_id not in self.completed
                     and p.probe_id not in self.skipped]
        minutes_left = sum(PROBES_BY_ID[p].minutes for p in remaining)
        return {
            "completed": done, "total": total,
            "fraction": round(done / total, 3),
            "remaining": remaining,
            "minutes_remaining": round(minutes_left, 1),
            "skipped": dict(self.skipped),
        }

    def build_contract(self) -> LearningContract:
        """Turn the collected answers into an explicit, falsifiable contract."""
        c = LearningContract(learner_id=self.learner_id)
        a = self.answers

        c.probes_completed = list(self.completed)
        c.probes_skipped = dict(self.skipped)
        c.evidence_base = [f"{pid}: {_evidence_note(pid)}" for pid in self.completed]

        goal = str(a.get("goal", "")).lower()
        if "exam" in goal or "certification" in goal:
            c.goal_type = "exam_with_deadline"
        elif "deeply" in goal or "understand" in goal:
            c.goal_type = "mastery_no_deadline"
        elif "work" in goal or "practical" in goal:
            c.goal_type = "applied_skill"
        elif "recover" in goal or "lost" in goal:
            c.goal_type = "remediation"
        else:
            c.goal_type = "exploratory"

        c.domain = str(a.get("domain", ""))
        c.domain_shape = _classify_domain_shape(c.domain)

        c.source_available = self._source_present()
        raw_src = a.get("source")
        if c.source_available:
            text = str(raw_src)
            c.source_kind = ("pasted text" if len(text) > 200
                             else "short note or reference")
        else:
            c.source_kind = ""

        cons = a.get("constraints")
        if isinstance(cons, dict):
            c.session_minutes = int(cons.get("session_minutes", 20) or 20)
            c.days_per_week = int(cons.get("days_per_week", 4) or 4)
            c.best_time = str(cons.get("best_time", "unspecified"))
        c.session_minutes = max(5, min(90, c.session_minutes))
        c.days_per_week = max(1, min(7, c.days_per_week))

        pref = str(a.get("difficulty_preference", "")).lower()
        if "70" in pref:
            c.target_success_rate, c.difficulty_setting = 0.70, "gentler"
        elif "hard" in pref:
            c.target_success_rate, c.difficulty_setting = 0.60, "maximum"
        else:
            c.target_success_rate, c.difficulty_setting = 0.85, "evidence_band"

        fog = a.get("fog_baseline")
        if isinstance(fog, dict):
            vals = [v for v in fog.values() if isinstance(v, (int, float))]
            c.fog_baseline = round(sum(vals) / len(vals), 2) if vals else None
            c.fog_domains = fog
        elif isinstance(fog, (int, float)):
            c.fog_baseline = float(fog)

        c.question_styles = _styles_for(c.domain_shape, c.source_available)
        c.intervention_plan = _intervention_plan(c)
        c.falsifiers = _falsifiers(c)
        c.gaps = _gaps(self)
        return c


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _evidence_note(probe_id: str) -> str:
    notes = {
        "goal": "self-report of intent",
        "domain": "self-report of subject",
        "source": "presence and kind of source material",
        "baseline_cognition": "behavioural task, 40 trials",
        "baseline_speed": "behavioural task, fixed window",
        "calibration_probe": "confidence-accuracy pairs",
        "social_baseline": "behavioural economic games",
        "social_preference": "SVO ring measure",
        "mind_reading": "second-order false belief vignettes",
        "connectedness": "self-report scale",
        "fog_baseline": "self-report over two weeks",
        "constraints": "self-report of availability",
        "difficulty_preference": "explicit learner choice",
    }
    return notes.get(probe_id, "recorded")


def _classify_domain_shape(domain: str) -> str:
    low = domain.lower()
    if any(k in low for k in ("math", "physics", "chemistry", "engineering",
                              "accounting", "statistics")):
        return "procedural_numeric"
    if any(k in low for k in ("history", "law", "philosophy", "politics",
                              "literature", "ethics")):
        return "argumentative_textual"
    if any(k in low for k in ("language", "vocabulary", "anatomy", "biology",
                              "medicine", "pharmacology")):
        return "factual_high_volume"
    if any(k in low for k in ("code", "programming", "software", "data")):
        return "procedural_symbolic"
    if any(k in low for k in ("art", "music", "design", "writing")):
        return "generative_performative"
    return "mixed"


def _styles_for(domain_shape: str, has_source: bool) -> list[str]:
    base = ["cloze", "definition", "wh_question", "true_false_justify",
            "feynman", "socratic", "prediction_verify"]
    by_shape = {
        "procedural_numeric": ["numeric", "worked_example_completion",
                               "error_spotting", "counterexample",
                               "proof_derivation", "transfer"],
        "argumentative_textual": ["steelman", "compare_contrast", "causal_chain",
                                  "counterexample", "essay", "socratic"],
        "factual_high_volume": ["cloze", "list_recall", "ordering",
                                "true_false_justify", "analogy"],
        "procedural_symbolic": ["error_spotting", "worked_example_completion",
                                "transfer", "counterexample", "proof_derivation"],
        "generative_performative": ["analogy", "feynman", "steelman",
                                    "compare_contrast", "essay"],
        "mixed": ["analogy", "causal_chain", "compare_contrast", "transfer"],
    }
    styles = list(dict.fromkeys(base + by_shape.get(domain_shape, [])))
    if not has_source:
        styles = [s for s in styles if s not in ("cloze", "definition",
                                                 "wh_question", "list_recall")]
    return styles


def _intervention_plan(c: LearningContract) -> list[str]:
    plan = [
        (f"Adaptive difficulty held near {c.target_success_rate:.0%} success — "
         "the band where error-driven learning is fastest (Wilson et al. 2019)."),
        ("Spaced review on the FSRS schedule, so each item returns just before "
         "you would forget it rather than on a fixed calendar."),
        ("Interleaved practice across skills within a session, which produces "
         "worse in-session performance and better retention."),
        ("Retrieval before review: you answer from memory first, then see the "
         "source. Rereading is not offered as a study method."),
        ("Confidence rating on every item, so miscalibration is measured and "
         "corrected rather than left to accumulate."),
    ]
    if c.session_minutes >= 20:
        plan.append("Sessions split into two blocks with a short break, because "
                    "sustained attention decays within a single long block.")
    if c.fog_baseline is not None and c.fog_baseline >= 2.0:
        plan.append("Shorter blocks with more frequent breaks, given the "
                    "elevated mental-fatigue baseline you reported.")
        plan.append("Cognitive load is capped per session; the system will end "
                    "a session early rather than push through fatigue.")
    plan.append("Physical activity and sleep timing are logged as covariates, "
                "because both have larger effects on cognition than any "
                "cognitive training does.")
    return plan


def _falsifiers(c: LearningContract) -> list[str]:
    f = [
        ("If your measured success rate sits outside "
         f"{c.target_success_rate - 0.1:.0%}-{c.target_success_rate + 0.1:.0%} "
         "for three consecutive sessions, the difficulty model is wrong."),
        ("If predicted recall (FSRS) diverges from your actual recall by more "
         "than 10 points over 100 reviews, the scheduler is miscalibrated."),
        ("If your confidence-accuracy bias does not shrink over four weeks, "
         "the calibration feedback is not working."),
        ("If your self-reported mental clarity does not improve while your "
         "task performance does, the system is training the task and not you."),
    ]
    if c.goal_type == "exam_with_deadline":
        f.append("If you fail a practice exam at the level you need, the "
                 "question coverage is wrong regardless of your accuracy here.")
    return f


def _gaps(ob: Onboarding) -> list[str]:
    gaps = []
    for probe in PROBES:
        if probe.probe_id in ob.skipped:
            gaps.append(f"{probe.name}: skipped ({ob.skipped[probe.probe_id]})")
        elif probe.probe_id not in ob.completed:
            gaps.append(f"{probe.name}: not yet run")
    return gaps
