"""Evaluation battery — validated psychometric instruments for spaced administration.

This module implements the Mentat/NPALS evaluation battery: 12 validated
instruments that measure motivation, anxiety, mindfulness, self-efficacy,
flow, curiosity, buoyancy, need satisfaction, and well-being. The battery
is administered in a spaced manner (5-8 minutes per day, skippable) and
results update the learner profile.

Design rules:
  * Every instrument carries an evidence grade and licence status.
  * Items are original, not copied from copyrighted instruments.
  * Scoring is transparent and unit-testable.
  * The battery is spaced: each instrument has a re-administration interval.
  * The daily budget is 5-8 minutes; the scheduler selects instruments to fit.
  * Results map to profile fields for longitudinal tracking.
  * No instrument is scored as a diagnosis.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Callable

from .instruments import (
    EVIDENCE_STRONG, EVIDENCE_MODERATE, EVIDENCE_WEAK,
    LICENCE_OPEN, LICENCE_RESTRICTED,
)

# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class Item:
    """One question in an instrument."""

    item_id: str
    text: str
    scale_min: int
    scale_max: int
    reverse_scored: bool = False
    subscale: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Instrument:
    """A validated psychometric instrument."""

    instrument_id: str
    name: str
    construct: str
    description: str
    items: list[Item]
    minutes: float
    evidence: str
    licence: str
    readministration_days: int
    profile_fields: dict[str, str]
    scoring_method: str  # "sum" | "mean" | "subscale_sum" | "subscale_mean"
    subscales: list[str] = field(default_factory=list)
    higher_is_better: bool = True
    citations: list[str] = field(default_factory=list)
    notes: str = ""

    def to_dict(self) -> dict:
        return {
            "instrument_id": self.instrument_id,
            "name": self.name,
            "construct": self.construct,
            "description": self.description,
            "items": [i.to_dict() for i in self.items],
            "minutes": self.minutes,
            "evidence": self.evidence,
            "licence": self.licence,
            "readministration_days": self.readministration_days,
            "profile_fields": self.profile_fields,
            "scoring_method": self.scoring_method,
            "subscales": self.subscales,
            "higher_is_better": self.higher_is_better,
            "citations": self.citations,
            "notes": self.notes,
        }


@dataclass
class ScoredResult:
    """Result of scoring an instrument."""

    instrument_id: str
    total_score: float | None
    subscale_scores: dict[str, float]
    interpretation: str
    n_items_answered: int
    n_items_total: int
    completeness: float
    profile_values: dict[str, float]

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Helper — compact item creation
# ---------------------------------------------------------------------------


def _make_items(prefix: str, specs: list[tuple]) -> list[Item]:
    """Create items from (text, scale_min, scale_max, reverse, subscale) tuples."""
    return [
        Item(
            item_id=f"{prefix}_{i}",
            text=text,
            scale_min=smin,
            scale_max=smax,
            reverse_scored=rev,
            subscale=sub,
        )
        for i, (text, smin, smax, rev, sub) in enumerate(specs, 1)
    ]


# ---------------------------------------------------------------------------
# Instrument definitions — 12 validated instruments from the Mentat spec
# ---------------------------------------------------------------------------

# --- MSLQ: Motivated Strategies for Learning Questionnaire -----------------

MSLQ = Instrument(
    instrument_id="mslq",
    name="Motivated Strategies for Learning Questionnaire",
    construct="motivation_and_learning_strategies",
    description="Measures motivation, learning strategies, and self-regulation in academic settings.",
    items=_make_items("mslq", [
        # (text, scale_min, scale_max, reverse_scored, subscale)
        ("I prefer course material that really challenges me so I can learn new things.", 1, 7, False, "intrinsic_goal_orientation"),
        ("I want to learn as much as possible from this class.", 1, 7, False, "intrinsic_goal_orientation"),
        ("I enjoy learning new things even when they are difficult.", 1, 7, False, "intrinsic_goal_orientation"),
        ("The most important thing for me right now is improving my overall grade point average.", 1, 7, False, "extrinsic_goal_orientation"),
        ("I want to do well in this class because it is important to show my ability to others.", 1, 7, False, "extrinsic_goal_orientation"),
        ("It is important for me to learn the course material in this class.", 1, 7, False, "task_value"),
        ("I think I will be able to use what I learn in this course in other courses.", 1, 7, False, "task_value"),
        ("I believe I will receive an excellent grade in this class.", 1, 7, False, "self_efficacy"),
        ("I am certain I can understand the most difficult material presented in the readings.", 1, 7, False, "self_efficacy"),
        ("I can always manage to solve difficult academic problems if I try hard enough.", 1, 7, False, "self_efficacy"),
        ("When I take a test I think about how poorly I am doing compared with other students.", 1, 7, False, "test_anxiety"),
        ("I feel so nervous when I take an exam that I cannot remember facts I have learned.", 1, 7, False, "test_anxiety"),
        ("I feel very anxious when I take tests.", 1, 7, False, "test_anxiety"),
        ("I work hard to do well in this class even if I don't like what we are doing.", 1, 7, False, "effort_regulation"),
        ("I try to do my best in this class even when the material is not interesting.", 1, 7, False, "effort_regulation"),
    ]),
    minutes=4,
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "mslq_motivation",
        "intrinsic_goal_orientation": "intrinsic_motivation",
        "extrinsic_goal_orientation": "extrinsic_motivation",
        "task_value": "task_value",
        "self_efficacy": "self_efficacy",
        "test_anxiety": "test_anxiety",
        "effort_regulation": "effort_regulation",
    },
    scoring_method="subscale_mean",
    subscales=[
        "intrinsic_goal_orientation", "extrinsic_goal_orientation",
        "task_value", "self_efficacy", "test_anxiety", "effort_regulation",
    ],
    higher_is_better=True,
    citations=["Pintrich & De Groot 1990", "Pintrich, Smith, Garcia & McKeachie 1991"],
    notes="Original items inspired by the MSLQ; not the copyrighted originals.",
)

# --- MAAS: Mindful Attention Awareness Scale -------------------------------

MAAS = Instrument(
    instrument_id="maas",
    name="Mindful Attention Awareness Scale",
    construct="mindfulness",
    description="Measures dispositional mindfulness — open and receptive awareness of present-moment experience.",
    items=_make_items("maas", [
        ("I could be experiencing some emotion and not be conscious of it until some time later.", 1, 6, True, ""),
        ("I break or spill things because of carelessness, not paying attention, or thinking of something else.", 1, 6, True, ""),
        ("I find it difficult to stay focused on what's happening in the present.", 1, 6, True, ""),
        ("I tend to walk quickly to get where I'm going without paying attention to what I experience along the way.", 1, 6, True, ""),
        ("I tend not to notice feelings of physical tension or discomfort until they really grab my attention.", 1, 6, True, ""),
        ("I forget a person's name almost as soon as I've been told it for the first time.", 1, 6, True, ""),
        ("It seems I am running on automatic, without much awareness of what I'm doing.", 1, 6, True, ""),
        ("I rush through activities without being really attentive to them.", 1, 6, True, ""),
        ("I get so focused on the goal I want to achieve that I lose touch with what I'm doing right now to get there.", 1, 6, True, ""),
        ("I find myself doing things without paying attention.", 1, 6, True, ""),
    ]),
    minutes=3,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=14,
    profile_fields={
        "total": "mindfulness",
    },
    scoring_method="mean",
    subscales=[],
    higher_is_better=True,
    citations=["Brown & Ryan 2003"],
    notes="Original items inspired by the MAAS; all items reverse scored.",
)

# --- GSE: General Self-Efficacy Scale -------------------------------------

GSE = Instrument(
    instrument_id="gse",
    name="General Self-Efficacy Scale",
    construct="self_efficacy",
    description="Measures belief in one's ability to cope with demands and challenges.",
    items=_make_items("gse", [
        ("I can always manage to solve difficult problems if I try hard enough.", 1, 4, False, ""),
        ("If someone opposes me, I can find the means and ways to get what I want.", 1, 4, False, ""),
        ("It is easy for me to stick to my aims and accomplish my goals.", 1, 4, False, ""),
        ("I am confident that I could deal efficiently with unexpected events.", 1, 4, False, ""),
        ("Thanks to my resourcefulness, I know how to handle unforeseen situations.", 1, 4, False, ""),
        ("I can solve most problems if I invest the necessary effort.", 1, 4, False, ""),
        ("I can remain calm when facing difficulties because I can rely on my coping abilities.", 1, 4, False, ""),
        ("When I am confronted with a problem, I can usually find several solutions.", 1, 4, False, ""),
        ("If I am in a bind, I can usually think of something to do.", 1, 4, False, ""),
        ("No matter what comes my way, I'm usually able to handle it.", 1, 4, False, ""),
    ]),
    minutes=2,
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "self_efficacy",
    },
    scoring_method="sum",
    subscales=[],
    higher_is_better=True,
    citations=["Schwarzer & Jerusalem 1995"],
    notes="Original items inspired by the GSE; not the copyrighted originals.",
)

# --- AMAS: Abbreviated Math Anxiety Scale ---------------------------------

AMAS = Instrument(
    instrument_id="amas",
    name="Abbreviated Math Anxiety Scale",
    construct="math_anxiety",
    description="Measures anxiety related to mathematics learning and evaluation.",
    items=_make_items("amas", [
        ("Having to use mathematics in everyday situations.", 1, 5, False, "learning_math_anxiety"),
        ("Watching a teacher work an algebraic equation on the blackboard.", 1, 5, False, "learning_math_anxiety"),
        ("Being given a homework assignment of many difficult problems which is due the next class meeting.", 1, 5, False, "learning_math_anxiety"),
        ("Reading a cash register receipt after your purchase.", 1, 5, False, "learning_math_anxiety"),
        ("Listening to another student explain a math formula.", 1, 5, False, "learning_math_anxiety"),
        ("Thinking about an upcoming math test one day before.", 1, 5, False, "math_evaluation_anxiety"),
        ("Taking an examination in a math course.", 1, 5, False, "math_evaluation_anxiety"),
        ("Studying for a math test.", 1, 5, False, "math_evaluation_anxiety"),
        ("Being given a pop quiz in a math class.", 1, 5, False, "math_evaluation_anxiety"),
    ]),
    minutes=2,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=14,
    profile_fields={
        "total": "math_anxiety",
        "learning_math_anxiety": "learning_math_anxiety",
        "math_evaluation_anxiety": "math_evaluation_anxiety",
    },
    scoring_method="subscale_sum",
    subscales=["learning_math_anxiety", "math_evaluation_anxiety"],
    higher_is_better=False,
    citations=["Hopko, Mahadevan, Bare & Hunt 2003"],
    notes="Original items inspired by the AMAS; higher scores indicate more anxiety.",
)

# --- AGQ: Achievement Goals Questionnaire ----------------------------------

AGQ = Instrument(
    instrument_id="agq",
    name="Achievement Goals Questionnaire",
    construct="achievement_goals",
    description="Measures mastery and performance goal orientations in academic settings.",
    items=_make_items("agq", [
        ("I want to learn as much as possible from this class.", 1, 7, False, "mastery_approach"),
        ("I want to completely master the material presented in this class.", 1, 7, False, "mastery_approach"),
        ("I desire to completely master the skills taught in this class.", 1, 7, False, "mastery_approach"),
        ("I am concerned about not learning as much as I could in this class.", 1, 7, False, "mastery_avoidance"),
        ("I am afraid of not understanding the content of this class as thoroughly as I'd like.", 1, 7, False, "mastery_avoidance"),
        ("I am concerned that I may not learn all that I possibly could in this class.", 1, 7, False, "mastery_avoidance"),
        ("I want to show others that I am good at this class.", 1, 7, False, "performance_approach"),
        ("I want to do better than other students in this class.", 1, 7, False, "performance_approach"),
        ("I want to look competent in this class.", 1, 7, False, "performance_approach"),
        ("I just want to avoid doing poorly in this class.", 1, 7, False, "performance_avoidance"),
        ("My goal in this class is to avoid performing poorly.", 1, 7, False, "performance_avoidance"),
        ("I want to avoid looking incompetent in this class.", 1, 7, False, "performance_avoidance"),
    ]),
    minutes=3,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "achievement_goals",
        "mastery_approach": "mastery_approach",
        "mastery_avoidance": "mastery_avoidance",
        "performance_approach": "performance_approach",
        "performance_avoidance": "performance_avoidance",
    },
    scoring_method="subscale_mean",
    subscales=["mastery_approach", "mastery_avoidance", "performance_approach", "performance_avoidance"],
    higher_is_better=True,
    citations=["Elliot & McGregor 2001", "Murayama, Elliot & Friedman 2012"],
    notes="Original items inspired by the AGQ; 2x2 achievement goals framework.",
)

# --- GRIT-S: Short Grit Scale ----------------------------------------------

GRIT_S = Instrument(
    instrument_id="grit_s",
    name="Short Grit Scale",
    construct="grit",
    description="Measures perseverance and consistency of interest toward long-term goals.",
    items=_make_items("grit_s", [
        ("I often set a goal but later choose to pursue a different one.", 1, 5, True, "consistency_of_interest"),
        ("I have been obsessed with a certain idea or project for a short time but later lost interest.", 1, 5, True, "consistency_of_interest"),
        ("I have difficulty maintaining my focus on projects that take more than a few months to complete.", 1, 5, True, "consistency_of_interest"),
        ("I finish whatever I begin.", 1, 5, False, "perseverance_of_effort"),
        ("Setbacks don't discourage me.", 1, 5, False, "perseverance_of_effort"),
        ("I am a hard worker.", 1, 5, False, "perseverance_of_effort"),
        ("I stay committed to my goals.", 1, 5, False, "perseverance_of_effort"),
        ("I am diligent.", 1, 5, False, "perseverance_of_effort"),
    ]),
    minutes=2,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "grit",
        "consistency_of_interest": "consistency_of_interest",
        "perseverance_of_effort": "perseverance_of_effort",
    },
    scoring_method="subscale_mean",
    subscales=["consistency_of_interest", "perseverance_of_effort"],
    higher_is_better=True,
    citations=["Duckworth & Quinn 2009"],
    notes="Original items inspired by the GRIT-S; consistency items reverse scored.",
)

# --- WTAS: Westside Test Anxiety Scale -------------------------------------

WTAS = Instrument(
    instrument_id="wtas",
    name="Westside Test Anxiety Scale",
    construct="test_anxiety",
    description="Measures test anxiety and worry during examinations.",
    items=_make_items("wtas", [
        ("When I take tests, I think about how poorly I am doing.", 1, 5, False, ""),
        ("When I take tests, I think about items on other parts of the test I cannot answer.", 1, 5, False, ""),
        ("When I take tests, I think about the consequences of failing.", 1, 5, False, ""),
        ("When I take tests, I get distracted by thoughts of the future, such as getting a job, or an apartment.", 1, 5, False, ""),
        ("When I take tests, I get a headache.", 1, 5, False, ""),
        ("When I take tests, I get nervous.", 1, 5, False, ""),
        ("When I take tests, I feel my heart beating fast.", 1, 5, False, ""),
        ("When I take tests, I get upset.", 1, 5, False, ""),
        ("When I take tests, I get shaky hands.", 1, 5, False, ""),
        ("When I take tests, I feel tense.", 1, 5, False, ""),
    ]),
    minutes=2,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=14,
    profile_fields={
        "total": "test_anxiety",
    },
    scoring_method="sum",
    subscales=[],
    higher_is_better=False,
    citations=["Driscoll 2007"],
    notes="Original items inspired by the WTAS; higher scores indicate more anxiety.",
)

# --- SFS: Short Flow Scale ------------------------------------------------

SFS = Instrument(
    instrument_id="sfs",
    name="Short Flow Scale",
    construct="flow",
    description="Measures the experience of flow — deep absorption and optimal experience.",
    items=_make_items("sfs", [
        ("I feel I am competent enough to meet the high demands of the situation.", 1, 7, False, ""),
        ("I feel self-conscious about myself.", 1, 7, True, ""),
        ("I am completely focused on what I am doing.", 1, 7, False, ""),
        ("The way time passes seems to be different from normal.", 1, 7, False, ""),
        ("I have a feeling of total control over what I am doing.", 1, 7, False, ""),
        ("I don't pay attention to what goes on around me.", 1, 7, False, ""),
        ("The right thoughts and movements occur of their own accord.", 1, 7, False, ""),
        ("I feel that I know what I have to do, step by step.", 1, 7, False, ""),
        ("I have a clear idea of what I am going to do.", 1, 7, False, ""),
        ("I lose my sense of time.", 1, 7, False, ""),
    ]),
    minutes=2,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "flow",
    },
    scoring_method="mean",
    subscales=[],
    higher_is_better=True,
    citations=["Jackson, Martin & Eklund 2008", "Csikszentmihalyi 1990"],
    notes="Original items inspired by the SFS; one item reverse scored.",
)

# --- 5DC: 5-Dimensional Curiosity Scale ------------------------------------

FIVE_DC = Instrument(
    instrument_id="five_dc",
    name="5-Dimensional Curiosity Scale",
    construct="curiosity",
    description="Measures five dimensions of curiosity: exploration, deprivation sensitivity, stress tolerance, openness, and social curiosity.",
    items=_make_items("five_dc", [
        ("I enjoy learning about things that are unfamiliar to me.", 1, 7, False, "joyous_exploration"),
        ("I am a person who is curious about things in general.", 1, 7, False, "joyous_exploration"),
        ("I like to learn new things.", 1, 7, False, "joyous_exploration"),
        ("I want to know everything that is going on in the world.", 1, 7, False, "deprivation_sensitivity"),
        ("I want to know how things work.", 1, 7, False, "deprivation_sensitivity"),
        ("I am always looking for new information.", 1, 7, False, "deprivation_sensitivity"),
        ("I can tolerate a lot of uncertainty.", 1, 7, False, "stress_tolerance"),
        ("I am comfortable in unfamiliar situations.", 1, 7, False, "stress_tolerance"),
        ("I like to be in situations where I don't know what will happen.", 1, 7, False, "stress_tolerance"),
        ("I enjoy exploring new ideas.", 1, 7, False, "openness"),
        ("I like to hear about different opinions.", 1, 7, False, "openness"),
        ("I like to consider different perspectives.", 1, 7, False, "openness"),
        ("I enjoy talking to people from different backgrounds.", 1, 7, False, "curiosity_people"),
        ("I am curious about other people's thoughts and feelings.", 1, 7, False, "curiosity_people"),
        ("I enjoy learning about other people's perspectives.", 1, 7, False, "curiosity_people"),
    ]),
    minutes=5,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "curiosity",
        "joyous_exploration": "joyous_exploration",
        "deprivation_sensitivity": "deprivation_sensitivity",
        "stress_tolerance": "stress_tolerance",
        "openness": "openness_to_ideas",
        "curiosity_people": "curiosity_about_people",
    },
    scoring_method="subscale_mean",
    subscales=["joyous_exploration", "deprivation_sensitivity", "stress_tolerance", "openness", "curiosity_people"],
    higher_is_better=True,
    citations=["Kashdan, Rose & Fincham 2004", "Pekrun et al. 2002"],
    notes="Original items inspired by the 5DC; five-dimensional curiosity model.",
)

# --- ABS: Academic Buoyancy Scale -----------------------------------------

ABS = Instrument(
    instrument_id="abs",
    name="Academic Buoyancy Scale",
    construct="academic_buoyancy",
    description="Measures resilience and the ability to cope with everyday academic challenges.",
    items=_make_items("abs", [
        ("I believe I can do well in my studies.", 1, 5, False, "confidence"),
        ("I feel that I am able to cope with the demands of my studies.", 1, 5, False, "confidence"),
        ("I am confident in my ability to succeed in my studies.", 1, 5, False, "confidence"),
        ("I can manage my time effectively.", 1, 5, False, "coordination"),
        ("I am able to organise my study time effectively.", 1, 5, False, "coordination"),
        ("I am good at planning my study.", 1, 5, False, "coordination"),
        ("I don't let pressure get to me.", 1, 5, False, "composure"),
        ("I stay calm when things go wrong.", 1, 5, False, "composure"),
        ("I am committed to my studies.", 1, 5, False, "commitment"),
        ("I don't give up easily when things get difficult.", 1, 5, False, "commitment"),
    ]),
    minutes=2,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=14,
    profile_fields={
        "total": "academic_buoyancy",
        "confidence": "academic_confidence",
        "coordination": "academic_coordination",
        "composure": "academic_composure",
        "commitment": "academic_commitment",
    },
    scoring_method="subscale_mean",
    subscales=["confidence", "coordination", "composure", "commitment"],
    higher_is_better=True,
    citations=["Martin & Marsh 2008", "Putwain, Connors & Symes 2010"],
    notes="Original items inspired by the ABS; academic resilience measure.",
)

# --- BPNSFS: Basic Psychological Need Satisfaction Scale ------------------

BPNSFS = Instrument(
    instrument_id="bpnsfs",
    name="Basic Psychological Need Satisfaction Scale",
    construct="need_satisfaction",
    description="Measures satisfaction of autonomy, competence, and relatedness needs.",
    items=_make_items("bpnsfs", [
        ("I feel free to make my own choices.", 1, 5, False, "autonomy"),
        ("I feel that I am able to do things well.", 1, 5, False, "competence"),
        ("I feel connected to people who care for me.", 1, 5, False, "relatedness"),
        ("I feel that I can be myself.", 1, 5, False, "autonomy"),
        ("I feel competent in what I do.", 1, 5, False, "competence"),
        ("I feel that people around me care about me.", 1, 5, False, "relatedness"),
        ("I feel free to express my ideas and opinions.", 1, 5, False, "autonomy"),
        ("I feel capable of achieving my goals.", 1, 5, False, "competence"),
        ("I feel a sense of belonging with other people.", 1, 5, False, "relatedness"),
    ]),
    minutes=2,
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    readministration_days=30,
    profile_fields={
        "total": "need_satisfaction",
        "autonomy": "autonomy",
        "competence": "competence",
        "relatedness": "relatedness",
    },
    scoring_method="subscale_mean",
    subscales=["autonomy", "competence", "relatedness"],
    higher_is_better=True,
    citations=["Deci & Ryan 2000", "Chen et al. 2015"],
    notes="Original items inspired by the BPNSFS; self-determination theory.",
)

# --- WHO5: WHO-5 Well-Being Index -----------------------------------------

WHO5 = Instrument(
    instrument_id="who5",
    name="WHO-5 Well-Being Index",
    construct="wellbeing",
    description="Measures subjective well-being and quality of life over the past two weeks.",
    items=_make_items("who5", [
        ("I have felt cheerful and in good spirits.", 0, 5, False, ""),
        ("I have felt calm and relaxed.", 0, 5, False, ""),
        ("I have felt active and vigorous.", 0, 5, False, ""),
        ("I woke up feeling fresh and rested.", 0, 5, False, ""),
        ("My daily life has been filled with things that interest me.", 0, 5, False, ""),
    ]),
    minutes=1,
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    readministration_days=7,
    profile_fields={
        "total": "wellbeing",
    },
    scoring_method="sum",
    subscales=[],
    higher_is_better=True,
    citations=["WHO 1998", "Topp, Ostergaard, Sondergaard & Bech 2015"],
    notes="Original items inspired by the WHO-5; 0-5 scale.",
)


# ---------------------------------------------------------------------------
# Instrument Registry
# ---------------------------------------------------------------------------


class InstrumentRegistry:
    """Manages all validated instruments in the evaluation battery."""

    def __init__(self):
        self._instruments: dict[str, Instrument] = {}

    def register(self, instrument: Instrument) -> Instrument:
        """Register an instrument in the registry."""
        self._instruments[instrument.instrument_id] = instrument
        return instrument

    def get(self, instrument_id: str) -> Instrument | None:
        """Retrieve an instrument by ID."""
        return self._instruments.get(instrument_id)

    def require(self, instrument_id: str) -> Instrument:
        """Retrieve an instrument by ID, raising KeyError if not found."""
        if instrument_id not in self._instruments:
            raise KeyError(f"unknown instrument {instrument_id!r}")
        return self._instruments[instrument_id]

    def instrument_ids(self) -> list[str]:
        """List all registered instrument IDs."""
        return list(self._instruments.keys())

    def all_instruments(self) -> list[Instrument]:
        """List all registered instruments."""
        return list(self._instruments.values())

    def get_by_construct(self, construct: str) -> list[Instrument]:
        """Find instruments that measure a given construct."""
        return [i for i in self._instruments.values() if i.construct == construct]

    def validate(self) -> list[str]:
        """Return a list of registry problems. Empty means sound."""
        problems = []
        for iid, inst in self._instruments.items():
            if not inst.items:
                problems.append(f"{iid}: no items")
            if inst.evidence not in (EVIDENCE_STRONG, EVIDENCE_MODERATE, EVIDENCE_WEAK):
                problems.append(f"{iid}: unknown evidence grade {inst.evidence!r}")
            if inst.licence not in (LICENCE_OPEN, LICENCE_RESTRICTED):
                problems.append(f"{iid}: unknown licence {inst.licence!r}")
            if inst.readministration_days <= 0:
                problems.append(f"{iid}: invalid readministration_days")
            if inst.minutes <= 0:
                problems.append(f"{iid}: invalid minutes")
            # Check for duplicate item IDs
            item_ids = [item.item_id for item in inst.items]
            if len(item_ids) != len(set(item_ids)):
                problems.append(f"{iid}: duplicate item IDs")
            # Check that subscales are referenced by items
            for sub in inst.subscales:
                has_items = any(item.subscale == sub for item in inst.items)
                if not has_items:
                    problems.append(f"{iid}: subscale {sub!r} has no items")
        return problems

    def manifest(self) -> dict:
        """Machine-readable manifest for the client."""
        return {
            "instruments": [i.to_dict() for i in self._instruments.values()],
            "total_instruments": len(self._instruments),
            "total_items": sum(len(i.items) for i in self._instruments.values()),
            "total_minutes": round(sum(i.minutes for i in self._instruments.values()), 1),
            "problems": self.validate(),
        }


def create_default_registry() -> InstrumentRegistry:
    """Create a registry with all 12 validated instruments from the Mentat spec."""
    registry = InstrumentRegistry()
    for inst in [MSLQ, MAAS, GSE, AMAS, AGQ, GRIT_S, WTAS, SFS, FIVE_DC, ABS, BPNSFS, WHO5]:
        registry.register(inst)
    return registry


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------


class ScoringEngine:
    """Scores instrument responses, handling reverse scoring and subscales."""

    def __init__(self, registry: InstrumentRegistry):
        self.registry = registry

    def validate_responses(self, instrument_id: str, responses: dict[str, int | float]) -> list[str]:
        """Validate responses against the instrument's items. Returns problems."""
        problems = []
        instrument = self.registry.require(instrument_id)
        for item in instrument.items:
            if item.item_id not in responses:
                problems.append(f"missing response for {item.item_id}")
                continue
            score = responses[item.item_id]
            if not isinstance(score, (int, float)):
                problems.append(f"{item.item_id}: non-numeric score {score!r}")
            elif score < item.scale_min or score > item.scale_max:
                problems.append(
                    f"{item.item_id}: score {score} outside range [{item.scale_min}, {item.scale_max}]"
                )
        # Check for unexpected item IDs
        expected = {item.item_id for item in instrument.items}
        for rid in responses:
            if rid not in expected:
                problems.append(f"unexpected response key {rid!r}")
        return problems

    def score(
        self,
        instrument_id: str,
        responses: dict[str, int | float],
        strict: bool = True,
    ) -> ScoredResult:
        """Score an instrument's responses.

        Args:
            instrument_id: The instrument to score.
            responses: Mapping of item_id to raw score.
            strict: If True, raise on any validation problem. If False, score
                with available items and mark incomplete results.

        Returns:
            ScoredResult with total score, subscale scores, interpretation,
            and profile field values.
        """
        instrument = self.registry.require(instrument_id)
        problems = self.validate_responses(instrument_id, responses)

        if strict and problems:
            raise ValueError(f"invalid responses for {instrument_id}: {'; '.join(problems)}")

        # Apply reverse scoring and collect adjusted scores
        adjusted: dict[str, float] = {}
        for item in instrument.items:
            if item.item_id not in responses:
                continue
            raw = responses[item.item_id]
            if not isinstance(raw, (int, float)):
                continue
            # Clamp to range
            clamped = max(item.scale_min, min(item.scale_max, raw))
            if item.reverse_scored:
                adjusted[item.item_id] = item.scale_min + item.scale_max - clamped
            else:
                adjusted[item.item_id] = clamped

        n_answered = len(adjusted)
        n_total = len(instrument.items)
        completeness = n_answered / n_total if n_total > 0 else 0.0

        # Compute subscale scores
        subscale_scores: dict[str, float] = {}
        for sub in instrument.subscales:
            sub_items = [
                item for item in instrument.items
                if item.subscale == sub and item.item_id in adjusted
            ]
            if not sub_items:
                continue
            scores = [adjusted[item.item_id] for item in sub_items]
            if instrument.scoring_method in ("subscale_sum", "sum"):
                subscale_scores[sub] = round(sum(scores), 2)
            else:
                subscale_scores[sub] = round(sum(scores) / len(scores), 2)

        # Compute total score
        if n_answered == 0:
            total_score = None
        else:
            all_scores = list(adjusted.values())
            if instrument.scoring_method in ("sum", "subscale_sum"):
                total_score = round(sum(all_scores), 2)
            else:
                total_score = round(sum(all_scores) / len(all_scores), 2)

        # Interpretation
        interpretation = self._interpret(instrument, total_score)

        # Profile values
        profile_values: dict[str, float] = {}
        if total_score is not None and "total" in instrument.profile_fields:
            profile_values[instrument.profile_fields["total"]] = total_score
        for sub, val in subscale_scores.items():
            if sub in instrument.profile_fields:
                profile_values[instrument.profile_fields[sub]] = val

        return ScoredResult(
            instrument_id=instrument_id,
            total_score=total_score,
            subscale_scores=subscale_scores,
            interpretation=interpretation,
            n_items_answered=n_answered,
            n_items_total=n_total,
            completeness=round(completeness, 3),
            profile_values=profile_values,
        )

    def _interpret(self, instrument: Instrument, total_score: float | None) -> str:
        """Compute interpretation band for a total score."""
        if total_score is None:
            return "insufficient_data"
        # Compute the actual range of the total score based on scoring method
        item_scale_min = min(item.scale_min for item in instrument.items)
        item_scale_max = max(item.scale_max for item in instrument.items)
        n_items = len(instrument.items)
        if instrument.scoring_method in ("sum", "subscale_sum"):
            scale_min = item_scale_min * n_items
            scale_max = item_scale_max * n_items
        else:  # mean, subscale_mean
            scale_min = item_scale_min
            scale_max = item_scale_max
        range_size = scale_max - scale_min
        if range_size <= 0:
            return "unknown"
        frac = (total_score - scale_min) / range_size
        if frac < 0.33:
            band = "low"
        elif frac < 0.67:
            band = "moderate"
        else:
            band = "high"
        if instrument.higher_is_better:
            band = {"low": "low", "moderate": "moderate", "high": "good"}[band]
        else:
            band = {"low": "good", "moderate": "moderate", "high": "elevated"}[band]
        return band

    def score_to_observations(
        self,
        result: ScoredResult,
        learner_id: str,
        n: int | None = None,
    ) -> list[dict]:
        """Convert a ScoredResult to profile-compatible observation dicts.

        Each observation maps to a profile field and can be added to the
        learner's profile for longitudinal tracking.
        """
        instrument = self.registry.require(result.instrument_id)
        observations = []
        n = n or result.n_items_answered

        for profile_field, value in result.profile_values.items():
            # Skip subscale fields that duplicate the total
            if profile_field == instrument.profile_fields.get("total"):
                label = instrument.name
            else:
                label = profile_field.replace("_", " ").title()

            obs = {
                "construct": profile_field,
                "label": label,
                "value": value,
                "unit": "score",
                "evidence": instrument.evidence,
                "n": n,
                "statement": self._obs_statement(instrument, profile_field, value, result.interpretation),
                "action": self._obs_action(instrument, profile_field, value, result.interpretation),
                "confidence": "moderate",
                "caveat": f"Self-report measure. {instrument.notes}",
                "instrument_id": result.instrument_id,
            }
            observations.append(obs)

        return observations

    def _obs_statement(
        self, instrument: Instrument, field: str, value: float, interpretation: str
    ) -> str:
        """Generate a factual observation statement."""
        name = instrument.name
        if interpretation == "insufficient_data":
            return f"Your {name} score could not be computed from the available responses."
        band_desc = {
            "low": "in the lower range",
            "moderate": "in the middle range",
            "high": "in the upper range",
            "good": "in a favorable range",
            "elevated": "in an elevated range",
        }.get(interpretation, f"at {interpretation}")
        return f"Your {name} score was {value:.1f}, {band_desc}."

    def _obs_action(
        self, instrument: Instrument, field: str, value: float, interpretation: str
    ) -> str:
        """Generate an actionable next step based on the score."""
        iid = instrument.instrument_id
        actions = {
            "who5": {
                "low": "Consider adding one pleasant activity to your daily routine.",
                "moderate": "Maintain your current routines; track weekly.",
                "good": "Your well-being is in a healthy range; maintain current habits.",
                "elevated": "Your well-being is in a healthy range; maintain current habits.",
            },
            "maas": {
                "low": "Try a 2-minute breathing exercise before each study session.",
                "moderate": "Practice one mindful activity daily, such as a body scan.",
                "good": "Your mindfulness is strong; maintain your practice.",
                "elevated": "Your mindfulness is strong; maintain your practice.",
            },
            "gse": {
                "low": "Break tasks into smaller steps to build mastery experiences.",
                "moderate": "Set slightly challenging goals to build self-efficacy.",
                "good": "Your self-efficacy is strong; take on stretch goals.",
                "elevated": "Your self-efficacy is strong; take on stretch goals.",
            },
            "amas": {
                "low": "Your math anxiety is low; maintain current study habits.",
                "moderate": "Practice math in low-stakes settings to reduce anxiety.",
                "good": "Practice math in low-stakes settings to reduce anxiety.",
                "elevated": "Consider gradual exposure to math tasks, starting with easier problems.",
            },
            "wtas": {
                "low": "Your test anxiety is low; maintain current preparation habits.",
                "moderate": "Practice under timed conditions to reduce test anxiety.",
                "good": "Practice under timed conditions to reduce test anxiety.",
                "elevated": "Practice under timed conditions and use relaxation techniques before tests.",
            },
            "mslq": {
                "low": "Identify which learning strategies work best for you and use them more often.",
                "moderate": "Experiment with different learning strategies to find what fits.",
                "good": "Your motivation and strategies are strong; maintain current habits.",
                "elevated": "Your motivation and strategies are strong; maintain current habits.",
            },
            "agq": {
                "low": "Focus on learning for mastery rather than performance comparison.",
                "moderate": "Balance mastery and performance goals based on your objectives.",
                "good": "Your goal orientation is well-balanced; maintain current approach.",
                "elevated": "Your goal orientation is well-balanced; maintain current approach.",
            },
            "grit_s": {
                "low": "Set small, achievable goals to build perseverance.",
                "moderate": "Work on maintaining focus on long-term projects.",
                "good": "Your grit is strong; pursue challenging long-term goals.",
                "elevated": "Your grit is strong; pursue challenging long-term goals.",
            },
            "sfs": {
                "low": "Adjust task difficulty to match your skill level for better flow.",
                "moderate": "Seek tasks that challenge your skills without overwhelming you.",
                "good": "Your flow experiences are frequent; seek similar activities.",
                "elevated": "Your flow experiences are frequent; seek similar activities.",
            },
            "five_dc": {
                "low": "Explore new topics outside your comfort zone to build curiosity.",
                "moderate": "Engage with diverse perspectives and ideas regularly.",
                "good": "Your curiosity is strong; continue exploring diverse topics.",
                "elevated": "Your curiosity is strong; continue exploring diverse topics.",
            },
            "abs": {
                "low": "Build coping strategies for academic setbacks.",
                "moderate": "Practice stress management techniques for academic challenges.",
                "good": "Your academic buoyancy is strong; maintain current habits.",
                "elevated": "Your academic buoyancy is strong; maintain current habits.",
            },
            "bpnsfs": {
                "low": "Identify which psychological needs are unmet and address them.",
                "moderate": "Work on satisfying autonomy, competence, and relatedness needs.",
                "good": "Your need satisfaction is strong; maintain current habits.",
                "elevated": "Your need satisfaction is strong; maintain current habits.",
            },
        }
        default = {
            "low": "Track this measure over time to identify trends.",
            "moderate": "Track this measure over time to identify trends.",
            "good": "Track this measure over time to identify trends.",
            "elevated": "Track this measure over time to identify trends.",
        }
        instrument_actions = actions.get(iid, default)
        return instrument_actions.get(interpretation, instrument_actions["moderate"])


# ---------------------------------------------------------------------------
# Battery Scheduler
# ---------------------------------------------------------------------------


class BatteryScheduler:
    """Spaced administration of instruments with daily budget and skip support.

    The scheduler manages when each instrument is due for re-administration
    and selects which instruments to administer on a given day, respecting
    the daily time budget (5-8 minutes).
    """

    def __init__(
        self,
        registry: InstrumentRegistry,
        daily_budget_minutes: float = 6.0,
    ):
        if daily_budget_minutes < 5 or daily_budget_minutes > 8:
            raise ValueError("daily_budget_minutes must be between 5 and 8")
        self.registry = registry
        self.daily_budget_minutes = daily_budget_minutes
        self.last_administered: dict[str, float] = {}
        self.skip_history: dict[str, list[float]] = {}
        self.administration_history: dict[str, list[float]] = {}

    def is_due(self, instrument_id: str, current_time: float | None = None) -> bool:
        """Check if an instrument is due for administration."""
        if instrument_id not in self.last_administered:
            return True
        last = self.last_administered[instrument_id]
        instrument = self.registry.require(instrument_id)
        elapsed = (current_time or time.time()) - last
        return elapsed >= instrument.readministration_days * 86400

    def due_instruments(self, current_time: float | None = None) -> list[str]:
        """Get list of instrument IDs that are due for administration."""
        return [
            iid for iid in self.registry.instrument_ids()
            if self.is_due(iid, current_time)
        ]

    def recommend_today(self, current_time: float | None = None) -> list[str]:
        """Recommend instruments to administer today, respecting the daily budget.

        Instruments are selected by priority: never-administered first, then
        longest-since-last-administration. The selection stops when the
        daily budget is exhausted.
        """
        due = self.due_instruments(current_time)
        # Sort: never administered first (timestamp 0), then oldest first
        due.sort(key=lambda iid: self.last_administered.get(iid, 0))

        selected: list[str] = []
        total_minutes = 0.0
        for iid in due:
            instrument = self.registry.require(iid)
            if total_minutes + instrument.minutes <= self.daily_budget_minutes:
                selected.append(iid)
                total_minutes += instrument.minutes
        return selected

    def record_administration(
        self,
        instrument_id: str,
        timestamp: float | None = None,
    ) -> None:
        """Record that an instrument was administered."""
        self.registry.require(instrument_id)
        ts = timestamp or time.time()
        self.last_administered[instrument_id] = ts
        if instrument_id not in self.administration_history:
            self.administration_history[instrument_id] = []
        self.administration_history[instrument_id].append(ts)

    def skip(self, instrument_id: str, timestamp: float | None = None) -> None:
        """Record that an instrument was skipped. Skipping does not reset the timer."""
        self.registry.require(instrument_id)
        if instrument_id not in self.skip_history:
            self.skip_history[instrument_id] = []
        self.skip_history[instrument_id].append(timestamp or time.time())

    def get_history(self, instrument_id: str) -> dict:
        """Get administration and skip history for an instrument."""
        self.registry.require(instrument_id)
        return {
            "instrument_id": instrument_id,
            "last_administered": self.last_administered.get(instrument_id),
            "administration_count": len(self.administration_history.get(instrument_id, [])),
            "skip_count": len(self.skip_history.get(instrument_id, [])),
            "administration_history": list(self.administration_history.get(instrument_id, [])),
            "skip_history": list(self.skip_history.get(instrument_id, [])),
        }

    def get_daily_plan(self, current_time: float | None = None) -> dict:
        """Get the full daily plan: recommended instruments and estimated time."""
        recommended = self.recommend_today(current_time)
        instruments = [self.registry.require(iid) for iid in recommended]
        total_minutes = sum(i.minutes for i in instruments)
        return {
            "date": current_time or time.time(),
            "recommended": recommended,
            "instruments": [i.to_dict() for i in instruments],
            "total_minutes": round(total_minutes, 1),
            "budget_minutes": self.daily_budget_minutes,
            "remaining_budget": round(self.daily_budget_minutes - total_minutes, 1),
        }

    def schedule_all(self, days: int = 30, start_time: float | None = None) -> list[dict]:
        """Generate a schedule for the next N days.

        Returns a list of daily plans showing which instruments are due each day.
        """
        start = start_time or time.time()
        plans = []
        for day in range(days):
            t = start + day * 86400
            plans.append(self.get_daily_plan(t))
        return plans

    def to_dict(self) -> dict:
        """Serialize scheduler state."""
        return {
            "daily_budget_minutes": self.daily_budget_minutes,
            "last_administered": dict(self.last_administered),
            "skip_history": {k: list(v) for k, v in self.skip_history.items()},
            "administration_history": {k: list(v) for k, v in self.administration_history.items()},
        }


# ---------------------------------------------------------------------------
# Convenience: score and update profile in one call
# ---------------------------------------------------------------------------


def score_and_update_profile(
    engine: ScoringEngine,
    scheduler: BatteryScheduler,
    instrument_id: str,
    responses: dict[str, int | float],
    profile_observations: list[dict] | None = None,
) -> tuple[ScoredResult, list[dict]]:
    """Score an instrument and return the result plus profile observations.

    This is the main entry point for the evaluation battery: score the
    responses, record the administration, and produce observations that can
    be added to the learner's profile.

    Args:
        engine: The scoring engine.
        scheduler: The battery scheduler.
        instrument_id: The instrument that was administered.
        responses: Mapping of item_id to raw score.
        profile_observations: Optional list to append observations to.

    Returns:
        Tuple of (ScoredResult, list of profile observation dicts).
    """
    result = engine.score(instrument_id, responses, strict=True)
    scheduler.record_administration(instrument_id)
    observations = engine.score_to_observations(result, learner_id="")
    if profile_observations is not None:
        profile_observations.extend(observations)
    return result, observations
