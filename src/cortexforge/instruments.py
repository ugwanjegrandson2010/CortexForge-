"""Behavioural profiling — the instruments and their scoring.

This module implements game-like tasks that measure HOW a person behaves and
what role they occupy in a group. It is deliberately split into two halves:

  1. TASK DEFINITIONS — pure data. Each task declares its stimuli, its
     scoring rule, the construct it measures, and the evidence behind it.
     A task with no evidence entry is refused by `validate_registry()`.

  2. SCORERS — pure functions from a response record to a score. They are
     unit-testable without a browser, which is the only way to trust them.

HARD RULES enforced in code, not in prose:

  * No instrument is scored as a diagnosis. `Profile.assert_no_diagnosis()`
    rejects any construct tagged `clinical_only` from appearing in a
    learner-facing profile.
  * Every construct carries an `evidence` grade. Constructs graded `weak`
    are reported with an explicit uncertainty statement and are never used
    to make a claim about the person's character.
  * Copyrighted instruments (RMET, MSCEIT, ASRS, AQ, MACH-IV) are declared
    but marked `licence: restricted`; the registry refuses to serve their
    items and the system uses original analogues instead.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Callable

# ---------------------------------------------------------------------------
# Evidence grading
# ---------------------------------------------------------------------------

EVIDENCE_STRONG = "strong"      # multiple independent replications, meta-analytic
EVIDENCE_MODERATE = "moderate"  # replicated but with caveats
EVIDENCE_WEAK = "weak"          # single study, contested, or poor psychometrics
EVIDENCE_NONE = "none"          # no validation; exploratory only

LICENCE_OPEN = "open"
LICENCE_RESTRICTED = "restricted"
LICENCE_CLINICAL = "clinical_only"


@dataclass
class TaskSpec:
    """Declarative definition of one behavioural task."""

    task_id: str
    name: str
    construct: str
    evidence: str
    licence: str
    minutes: float
    trials: int
    mechanics: str
    scoring: str
    measures: list[str] = field(default_factory=list)
    citations: list[str] = field(default_factory=list)
    clinical_only: bool = False
    notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# Registry of tasks
# ---------------------------------------------------------------------------

REGISTRY: dict[str, TaskSpec] = {}


def _register(spec: TaskSpec) -> TaskSpec:
    REGISTRY[spec.task_id] = spec
    return spec


# --- Cognitive (see docs/research/01) --------------------------------------

_register(TaskSpec(
    task_id="flanker",
    name="Flanker interference",
    construct="inhibitory_control",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=3, trials=40,
    mechanics=("A central arrow points left or right, flanked by congruent or "
               "incongruent arrows. Learner reports the centre direction. "
               "Congruent and incongruent trials are interleaved 50/50."),
    scoring=("interference_cost = median_RT(incongruent) - median_RT(congruent); "
             "accuracy is tracked separately. Score = -interference_cost "
             "z-scored against the learner's own baseline."),
    measures=["interference_cost_ms", "accuracy", "post_error_slowing_ms"],
    citations=["Eriksen & Eriksen 1974", "NIH Toolbox Flanker (Zelazo 2013)"],
))

_register(TaskSpec(
    task_id="dccs",
    name="Dimensional change card sort",
    construct="cognitive_flexibility",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=4, trials=40,
    mechanics=("Stimuli vary on two dimensions (colour, shape). The sorting "
               "rule switches without warning at fixed points; the learner "
               "must follow the current rule."),
    scoring=("switch_cost = median_RT(switch trials) - median_RT(repeat trials); "
             "mixed-block accuracy is the primary index."),
    measures=["switch_cost_ms", "mixed_accuracy"],
    citations=["Zelazo 2006", "NIH Toolbox DCCS"],
))

_register(TaskSpec(
    task_id="list_sorting",
    name="List sorting working memory",
    construct="working_memory",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=4, trials=14,
    mechanics=("Items from one or two categories are presented; the learner "
               "must recall them sorted by size within category. Two-category "
               "trials load executive demand."),
    scoring="total correct across 1-list and 2-list trials, capped at 28.",
    measures=["total_correct", "two_list_correct"],
    citations=["NIH Toolbox List Sorting (Tulsky 2013)"],
))

_register(TaskSpec(
    task_id="pattern_comparison",
    name="Pattern comparison processing speed",
    construct="processing_speed",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=2, trials=90,
    mechanics=("Two side-by-side patterns; learner judges same or different "
               "as fast as possible within a fixed 90-second window."),
    scoring="number of correct responses in the fixed window.",
    measures=["correct_in_window"],
    citations=["NIH Toolbox Pattern Comparison (Carlozzi 2013)"],
))

_register(TaskSpec(
    task_id="dual_nback",
    name="Dual n-back",
    construct="working_memory_updating",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=6, trials=60,
    mechanics=("A square moves position and a letter is spoken/shown each "
               "trial. Learner reports matches at lag n on either stream. "
               "n adapts: 2 up after 3 consecutive correct, 1 down after 2 wrong."),
    scoring=("n_level reached and d-prime on the highest stable block. "
             "Reported with the explicit caveat that far transfer is not "
             "established (Melby-Lervag & Hulme 2013/2016)."),
    measures=["max_n", "d_prime"],
    citations=["Jaeggi 2008", "Melby-Lervag & Hulme 2013",
               "Nguyen 2022 (null transfer)"],
    notes="Transfer claims are NOT made from this task.",
))

_register(TaskSpec(
    task_id="bart",
    name="Balloon analogue risk task",
    construct="risk_taking",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=4, trials=30,
    mechanics=("Learner pumps a balloon for points; each pump adds value and "
               "raises burst probability. They may bank at any point. Burst "
               "loses the trial's points."),
    scoring=("adjusted average pumps on non-burst trials (Lejuez 2002); "
             "also bank rate and post-burst adjustment."),
    measures=["adjusted_pumps", "post_burst_adjustment"],
    citations=["Lejuez 2002"],
))

_register(TaskSpec(
    task_id="delay_discounting",
    name="Delay discounting (monetary choice)",
    construct="impulsivity",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=3, trials=27,
    mechanics=("27 fixed choices between a smaller immediate reward and a "
               "larger delayed reward at 7/30/90/180/365 days."),
    scoring=("log k from the hyperbolic model V = A / (1 + kD), fitted by "
             "least squares over the indifference points."),
    measures=["log_k"],
    citations=["Kirby, Petry & Bickel 1999"],
))

# --- Social-cognitive (see docs/research/02) -------------------------------

_register(TaskSpec(
    task_id="false_belief",
    name="Second-order false belief",
    construct="theory_of_mind",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=3, trials=8,
    mechanics=("Short vignettes in which a character forms a belief about "
               "another character's belief. Learner answers what the first "
               "character thinks the second believes."),
    scoring="proportion correct on second-order items; first-order items are "
            "screening only.",
    measures=["second_order_accuracy"],
    citations=["Wimmer & Perner 1983", "Perner & Wimmer 1985",
               "Hacettepe-CBToM 2025"],
))

_register(TaskSpec(
    task_id="strange_stories",
    name="Strange stories (original analogues)",
    construct="mental_state_inference",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=5, trials=8,
    mechanics=("Short social vignettes requiring inference of pretence, "
               "joke, lie, misunderstanding, persuasion, or white lie. "
               "Items are written for this system, not copied from Happe."),
    scoring="2 points for a correct mental-state inference, 1 for a partial "
            "or over-literal answer, 0 for a physical/non-mental answer.",
    measures=["inference_score", "over_literal_rate"],
    citations=["Happe 1994 (construct)", "White 2009 (review)"],
    notes="Items are original; Happe's originals are not reproduced.",
))

_register(TaskSpec(
    task_id="rmet_analogue",
    name="Mind-in-the-eyes analogue (text-described)",
    construct="emotion_recognition",
    evidence=EVIDENCE_WEAK,
    licence=LICENCE_OPEN,
    minutes=4, trials=20,
    mechanics=("Because the RMET's stimulus set is copyrighted and its "
               "psychometrics are contested, this system uses text-described "
               "social scenes with four emotion labels instead of eye photos."),
    scoring="proportion correct, with a valence-confusion matrix.",
    measures=["accuracy", "valence_confusions"],
    citations=["Baron-Cohen 2001 (original)", "Oakley 2016 (critique)",
               "Kittel 2022 (psychometric critique)"],
    notes=("Reported as WEAK evidence and never used to characterise the "
           "person. Presented as a practice task only."),
))

_register(TaskSpec(
    task_id="ultimatum",
    name="Ultimatum game",
    construct="fairness_norm_enforcement",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=5, trials=20,
    mechanics=("Learner splits a stake as proposer, then responds to offers "
               "as responder. Rejections are costly to both sides."),
    scoring=("minimum acceptable offer (MAO); rejection rate by offer size; "
             "proposer generosity. MAO is the primary fairness index."),
    measures=["min_acceptable_offer", "rejection_rate", "proposer_offer"],
    citations=["Guth, Schmittberger & Schwarze 1982", "Camerer 2003"],
))

_register(TaskSpec(
    task_id="dictator",
    name="Dictator game",
    construct="altruism",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=2, trials=6,
    mechanics="Learner divides a stake with an anonymous partner who cannot respond.",
    scoring="mean share given; proportion of zero-giving and equal-split choices.",
    measures=["mean_share_given", "zero_give_rate"],
    citations=["Forsythe 1994", "Engel 2011 (meta-analysis)"],
))

_register(TaskSpec(
    task_id="trust_game",
    name="Trust game",
    construct="trust_and_reciprocity",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=4, trials=10,
    mechanics=("Investor sends an amount that is tripled; trustee decides how "
               "much to return. Learner plays both roles."),
    scoring="mean sent as investor (trust); mean returned as trustee "
            "(reciprocity); conditional return curve.",
    measures=["trust_sent", "reciprocity_returned"],
    citations=["Berg, Dickhaut & McCabe 1995", "Johnson & Mislin 2011"],
))

_register(TaskSpec(
    task_id="public_goods",
    name="Public goods game",
    construct="cooperation",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=6, trials=10,
    mechanics=("Four players contribute to a common pool that is multiplied "
               "and shared equally. Learner plays against scripted strategies "
               "including a free-rider and a conditional cooperator."),
    scoring="mean contribution; decay slope across rounds; response to "
            "punishment and to others' contributions.",
    measures=["mean_contribution", "decay_slope", "conditional_cooperation"],
    citations=["Fehr & Gachter 2000", "Fischbacher, Gachter & Fehr 2001"],
))

_register(TaskSpec(
    task_id="prisoners_dilemma",
    name="Iterated prisoner's dilemma",
    construct="strategic_reasoning",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=5, trials=30,
    mechanics=("Repeated two-choice game against a tit-for-tat partner, then "
               "against a random partner. Learner may defect or cooperate."),
    scoring=("cooperation rate against tit-for-tat (reciprocity), against "
             "random (exploitation), and forgiveness after a partner defect."),
    measures=["coop_vs_tft", "coop_vs_random", "forgiveness"],
    citations=["Axelrod 1984", "Fudenberg, Rand & Dreber 2012"],
))

_register(TaskSpec(
    task_id="social_value_orientation",
    name="Social value orientation (ring measure)",
    construct="social_preference_orientation",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=4, trials=24,
    mechanics=("24 decomposed games: choose between allocations to self and "
               "an anonymous other. Choices are plotted on the SVO ring."),
    scoring=("mean angle on the SVO ring: prosocial -45..45 deg, individualist "
             "-45..-90, competitive < -90, altruist > 45."),
    measures=["svo_angle", "svo_category"],
    citations=["Liebrand 1984", "Murphy, Ackermann & Handgraaf 2011"],
))

_register(TaskSpec(
    task_id="loneliness_ucla",
    name="Loneliness and social connectedness",
    construct="social_connectedness",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=3, trials=20,
    mechanics="20 self-report items on felt social connection, 1-4 scale.",
    scoring="sum 20-80; higher is lonelier. Tracked longitudinally, never "
            "used as a character judgement.",
    measures=["ucla_total"],
    citations=["Russell 1996 (UCLA Loneliness Scale v3)"],
))

_register(TaskSpec(
    task_id="need_for_cognition",
    name="Need for cognition",
    construct="epistemic_motivation",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=3, trials=18,
    mechanics="18 self-report items on enjoyment of effortful thinking.",
    scoring="sum; predicts how much the learner will tolerate desirable difficulty.",
    measures=["nfc_total"],
    citations=["Cacioppo & Petty 1982", "Cacioppo, Petty & Kao 1984"],
))

_register(TaskSpec(
    task_id="decision_style",
    name="General decision-making style",
    construct="decision_style",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_OPEN,
    minutes=4, trials=25,
    mechanics="25 items across rational, intuitive, dependent, avoidant, spontaneous.",
    scoring="five subscale means; the profile is a shape, not a single number.",
    measures=["rational", "intuitive", "dependent", "avoidant", "spontaneous"],
    citations=["Scott & Bruce 1995"],
))

_register(TaskSpec(
    task_id="calibration",
    name="Confidence calibration",
    construct="metacognitive_calibration",
    evidence=EVIDENCE_STRONG,
    licence=LICENCE_OPEN,
    minutes=0, trials=0,
    mechanics=("Not a separate task: every question asks for a confidence "
               "rating before the answer is revealed."),
    scoring=("Brier score, over/under-confidence bias, and Goodman-Kruskal "
             "gamma between confidence and accuracy (see tracing.py)."),
    measures=["brier", "bias", "gamma"],
    citations=["Nelson 1984", "Dunlosky & Metcalfe 2009"],
))

# --- Declared but NOT served (licence-restricted) --------------------------

_register(TaskSpec(
    task_id="rmet_original",
    name="Reading the Mind in the Eyes (original)",
    construct="emotion_recognition",
    evidence=EVIDENCE_WEAK,
    licence=LICENCE_RESTRICTED,
    minutes=4, trials=36,
    mechanics="Not served: stimulus set is copyrighted and psychometrics contested.",
    scoring="n/a",
    citations=["Baron-Cohen 2001", "Oakley 2016"],
    clinical_only=True,
    notes="Declared for completeness; the registry refuses to serve these items.",
))

_register(TaskSpec(
    task_id="asrs",
    name="Adult ADHD Self-Report Scale",
    construct="attention_regulation",
    evidence=EVIDENCE_MODERATE,
    licence=LICENCE_CLINICAL,
    minutes=3, trials=18,
    mechanics="Not served: a screening instrument, not a learning-system task.",
    scoring="n/a",
    citations=["Kessler 2005"],
    clinical_only=True,
    notes="Never administered or scored by this system.",
))


def validate_registry() -> list[str]:
    """Return a list of registry problems. Empty list means the registry is sound."""
    problems = []
    for tid, spec in REGISTRY.items():
        if spec.evidence not in (EVIDENCE_STRONG, EVIDENCE_MODERATE,
                                 EVIDENCE_WEAK, EVIDENCE_NONE):
            problems.append(f"{tid}: unknown evidence grade {spec.evidence!r}")
        if spec.licence not in (LICENCE_OPEN, LICENCE_RESTRICTED,
                                LICENCE_CLINICAL):
            problems.append(f"{tid}: unknown licence {spec.licence!r}")
        if spec.licence == LICENCE_OPEN and not spec.citations:
            problems.append(f"{tid}: open task with no citations")
        if spec.clinical_only and spec.licence == LICENCE_OPEN:
            problems.append(f"{tid}: clinical_only but marked open")
    return problems


def servable_tasks() -> list[TaskSpec]:
    """Tasks the system may actually administer."""
    return [s for s in REGISTRY.values()
            if s.licence == LICENCE_OPEN and not s.clinical_only]


def task_manifest() -> dict:
    """Machine-readable manifest for the client."""
    return {
        "tasks": [s.to_dict() for s in servable_tasks()],
        "declined": [s.to_dict() for s in REGISTRY.values()
                     if s.licence != LICENCE_OPEN or s.clinical_only],
        "total_minutes": round(sum(s.minutes for s in servable_tasks()), 1),
        "problems": validate_registry(),
    }


# ---------------------------------------------------------------------------
# Scorers — pure functions, unit-testable without a browser
# ---------------------------------------------------------------------------

def score_flanker(trials: list[dict]) -> dict:
    """trials: [{'congruent': bool, 'correct': bool, 'rt_ms': int, 'prev_error': bool}]"""
    ok = [t for t in trials if t.get("correct")]
    cong = [t["rt_ms"] for t in ok if t.get("congruent")]
    incong = [t["rt_ms"] for t in ok if not t.get("congruent")]
    cost = (statistics.median(incong) - statistics.median(cong)
            if cong and incong else None)
    post_err = [t["rt_ms"] for t in ok if t.get("prev_error")]
    post_ok = [t["rt_ms"] for t in ok if not t.get("prev_error")]
    pes = (statistics.median(post_err) - statistics.median(post_ok)
           if post_err and post_ok else None)
    return {
        "interference_cost_ms": round(cost, 1) if cost is not None else None,
        "accuracy": round(len(ok) / len(trials), 3) if trials else None,
        "post_error_slowing_ms": round(pes, 1) if pes is not None else None,
        "n": len(trials),
    }


def score_dccs(trials: list[dict]) -> dict:
    ok = [t for t in trials if t.get("correct")]
    sw = [t["rt_ms"] for t in ok if t.get("switched")]
    rp = [t["rt_ms"] for t in ok if not t.get("switched")]
    cost = (statistics.median(sw) - statistics.median(rp) if sw and rp else None)
    mixed = [t for t in trials if t.get("mixed_block")]
    return {
        "switch_cost_ms": round(cost, 1) if cost is not None else None,
        "mixed_accuracy": (round(sum(1 for t in mixed if t.get("correct"))
                                 / len(mixed), 3) if mixed else None),
        "n": len(trials),
    }


def score_dual_nback(trials: list[dict]) -> dict:
    """trials: [{'n': int, 'hit': bool, 'false_alarm': bool, 'miss': bool,
                 'correct_rejection': bool}]"""
    hits = sum(1 for t in trials if t.get("hit"))
    misses = sum(1 for t in trials if t.get("miss"))
    fas = sum(1 for t in trials if t.get("false_alarm"))
    crs = sum(1 for t in trials if t.get("correct_rejection"))
    hr = hits / (hits + misses) if (hits + misses) else 0.0
    fr = fas / (fas + crs) if (fas + crs) else 0.0
    hr_c = min(max(hr, 1e-4), 1 - 1e-4)
    fr_c = min(max(fr, 1e-4), 1 - 1e-4)
    dprime = _norm_ppf(hr_c) - _norm_ppf(fr_c)
    return {
        "max_n": max((t.get("n", 0) for t in trials), default=0),
        "d_prime": round(dprime, 3),
        "hit_rate": round(hr, 3),
        "false_alarm_rate": round(fr, 3),
        "transfer_claim": "none — far transfer is not established",
    }


# ---------------------------------------------------------------------------
# PennCNB-style composite scoring (accuracy / speed / efficiency)
# ---------------------------------------------------------------------------

def penncnb_composite(accuracy: float, median_rt_ms: float,
                      ref_acc_mean: float, ref_acc_sd: float,
                      ref_rt_mean: float, ref_rt_sd: float) -> dict:
    """Penn Computerized Neurocognitive Battery composite scoring.

    The PennCNB architecture is the most reusable scoring model in the
    literature: raw accuracy and speed are each converted to z-scores, the
    speed z is sign-flipped so that faster is better, and efficiency is the
    mean of the two. This yields three comparable indices per task, which
    lets a system compare a learner across tasks with different natural
    scales.

    Reference means and SDs must be supplied by the caller (the dossier
    tabulates them for the ten PennCNB tests); passing the learner's own
    baseline is acceptable for within-person tracking but must not be
    presented as a norm.
    """
    if ref_acc_sd <= 0 or ref_rt_sd <= 0:
        raise ValueError("reference SDs must be positive")
    z_acc = (accuracy - ref_acc_mean) / ref_acc_sd
    z_speed = -((median_rt_ms - ref_rt_mean) / ref_rt_sd)
    return {
        "z_accuracy": round(z_acc, 3),
        "z_speed": round(z_speed, 3),
        "efficiency": round((z_acc + z_speed) / 2.0, 3),
        "note": ("Efficiency is the mean of the accuracy z and the sign-flipped "
                 "speed z. Reference values are supplied by the caller; if they "
                 "are the learner's own baseline this is a within-person index, "
                 "not a norm-referenced score."),
    }


def nih_toolbox_two_vector(correct: int, total: int,
                           median_rt_ms: float | None = None,
                           rt_floor_ms: float = 200.0,
                           rt_ceiling_ms: float = 3000.0) -> dict:
    """NIH Toolbox two-vector scoring for accuracy-and-speed tasks.

    The Toolbox scores accuracy and reaction time on separate 0-5 vectors and
    sums them to a 0-10 total, with one important rule: if accuracy is at or
    below 80%, the total is the accuracy vector alone, because speed is not
    interpretable when the learner is not getting the items right. This is a
    direct implementation of that rule.

    The accuracy vector is 0.125 x number correct, capped at 5 (so 40 correct
    responses saturate it). The RT vector is a linear rescale of median RT
    from the ceiling (0 points) to the floor (5 points).
    """
    if total <= 0:
        raise ValueError("total must be positive")
    accuracy = correct / total
    acc_vector = min(5.0, 0.125 * correct)
    if median_rt_ms is None:
        rt_vector = 0.0
    else:
        span = max(rt_ceiling_ms - rt_floor_ms, 1.0)
        frac = (rt_ceiling_ms - median_rt_ms) / span
        rt_vector = max(0.0, min(5.0, 5.0 * frac))
    if accuracy <= 0.80:
        total_score = acc_vector
        rule = ("accuracy <= 80%: total is the accuracy vector alone, because "
                "speed is not interpretable below this accuracy")
    else:
        total_score = acc_vector + rt_vector
        rule = "accuracy > 80%: total is accuracy vector + RT vector"
    return {
        "accuracy": round(accuracy, 3),
        "accuracy_vector": round(acc_vector, 3),
        "rt_vector": round(rt_vector, 3),
        "total_0_10": round(total_score, 3),
        "rule_applied": rule,
    }


def score_bart(trials: list[dict]) -> dict:
    """trials: [{'pumps': int, 'burst': bool, 'banked': bool, 'points': int}]"""
    adj = [t["pumps"] for t in trials if not t.get("burst")]
    burst = [t for t in trials if t.get("burst")]
    post = []
    for i, t in enumerate(trials):
        if t.get("burst") and i + 1 < len(trials):
            post.append(trials[i + 1]["pumps"] - t["pumps"])
    return {
        "adjusted_pumps": round(statistics.mean(adj), 2) if adj else None,
        "burst_rate": round(len(burst) / len(trials), 3) if trials else None,
        "post_burst_adjustment": round(statistics.mean(post), 2) if post else None,
        "n": len(trials),
    }


def score_delay_discounting(trials: list[dict]) -> dict:
    """trials: [{'delay_days': float, 'immediate': float, 'delayed': float,
                 'chose_immediate': bool}] -> log k via grid search on hyperbolic."""
    best_k, best_err = None, float("inf")
    for i in range(-500, 101):  # log10 k from -5.00 to 1.00
        k = 10 ** (i / 100.0)
        err = 0.0
        for t in trials:
            d = max(t.get("delay_days", 1.0), 1e-6)
            v = t["delayed"] / (1.0 + k * d)
            pred_imm = 1.0 if t["immediate"] >= v else 0.0
            err += (pred_imm - (1.0 if t.get("chose_immediate") else 0.0)) ** 2
        if err < best_err:
            best_err, best_k = err, k
    return {
        "log_k": round(math.log10(best_k), 3) if best_k else None,
        "k": best_k,
        "fit_error": round(best_err, 3),
        "n": len(trials),
    }


def score_ultimatum(trials: list[dict]) -> dict:
    """trials: [{'role': 'proposer'|'responder', 'offer': float, 'accepted': bool}]"""
    resp = [t for t in trials if t.get("role") == "responder"]
    prop = [t for t in trials if t.get("role") == "proposer"]
    rejected = [t["offer"] for t in resp if not t.get("accepted")]
    accepted = [t["offer"] for t in resp if t.get("accepted")]
    mao = None
    if rejected:
        mao = max(rejected)
        if accepted:
            mao = (max(rejected) + min(accepted)) / 2.0
    return {
        "min_acceptable_offer": round(mao, 3) if mao is not None else None,
        "rejection_rate": (round(len(rejected) / len(resp), 3) if resp else None),
        "proposer_offer": (round(statistics.mean([t["offer"] for t in prop]), 3)
                           if prop else None),
        "n": len(trials),
    }


def score_dictator(trials: list[dict]) -> dict:
    shares = [t["share"] for t in trials]
    if not shares:
        return {"mean_share_given": None, "zero_give_rate": None, "n": 0}
    return {
        "mean_share_given": round(statistics.mean(shares), 3),
        "zero_give_rate": round(sum(1 for s in shares if s <= 0) / len(shares), 3),
        "equal_split_rate": round(sum(1 for s in shares if abs(s - 0.5) < 0.01)
                                  / len(shares), 3),
        "n": len(shares),
    }


def score_trust(trials: list[dict]) -> dict:
    inv = [t["sent"] for t in trials if t.get("role") == "investor"]
    tru = [t["returned"] for t in trials if t.get("role") == "trustee"]
    return {
        "trust_sent": round(statistics.mean(inv), 3) if inv else None,
        "reciprocity_returned": round(statistics.mean(tru), 3) if tru else None,
        "n": len(trials),
    }


def score_public_goods(trials: list[dict]) -> dict:
    """trials: [{'round': int, 'contribution': float, 'others_mean': float}]"""
    contribs = [t["contribution"] for t in trials]
    if not contribs:
        return {"mean_contribution": None, "decay_slope": None, "n": 0}
    rounds = [t["round"] for t in trials]
    slope = _ols_slope(rounds, contribs)
    pairs = [(t["others_mean"], t["contribution"]) for t in trials
             if "others_mean" in t]
    cond = _ols_slope([p[0] for p in pairs], [p[1] for p in pairs]) if len(pairs) > 2 else None
    return {
        "mean_contribution": round(statistics.mean(contribs), 3),
        "decay_slope": round(slope, 4) if slope is not None else None,
        "conditional_cooperation": round(cond, 3) if cond is not None else None,
        "n": len(contribs),
    }


def score_pd(trials: list[dict]) -> dict:
    """trials: [{'partner': 'tft'|'random', 'cooperated': bool,
                 'partner_cooperated': bool}]"""
    tft = [t for t in trials if t.get("partner") == "tft"]
    rnd = [t for t in trials if t.get("partner") == "random"]
    forg = [t for t in trials if t.get("partner_defected_prev")]
    return {
        "coop_vs_tft": (round(sum(1 for t in tft if t["cooperated"]) / len(tft), 3)
                        if tft else None),
        "coop_vs_random": (round(sum(1 for t in rnd if t["cooperated"]) / len(rnd), 3)
                           if rnd else None),
        "forgiveness": (round(sum(1 for t in forg if t["cooperated"]) / len(forg), 3)
                        if forg else None),
        "n": len(trials),
    }


def score_svo(trials: list[dict]) -> dict:
    """trials: [{'self': float, 'other': float}] -> mean ring angle in degrees.

    Implements the SVO ring measure (Liebrand 1984; Liebrand & McClintock 1988;
    Murphy, Ackermann & Handgraaf 2011).

    Each trial is a point in the (own payoff, other payoff) plane. The ring
    measure takes the angle of that point measured from the origin, where the
    horizontal axis is own payoff and the vertical axis is other payoff, and
    then reports the mean angle across trials. The canonical orientations are:

          0 deg  individualist  (maximise own payoff)
         45 deg  prosocial      (maximise joint payoff)
         90 deg  altruist       (maximise the other's payoff)
        -45 deg  competitive    (maximise own minus other)

    A raw atan2(other, self) spans only 0..90 degrees, so the competitive
    region is unreachable from a single allocation. The ring resolves this by
    centring each allocation on the *equal-split* reference point (the midpoint
    of the payoff range) and measuring the deviation from it: an allocation
    that gives the other person less than an equal split has a negative
    deviation and therefore a negative angle. That centring is what makes the
    four canonical orientations reachable, and it is why the ring is defined
    over the plane rather than over the raw payoffs.
    """
    if not trials:
        return {"svo_angle": None, "svo_category": None, "n": 0}

    # Reference: the equal-split point of the payoff range actually used.
    all_vals = [float(t["self"]) for t in trials] + [float(t["other"]) for t in trials]
    ref = (min(all_vals) + max(all_vals)) / 2.0
    if ref == 0:
        ref = 1.0

    angles = []
    for t in trials:
        s = float(t["self"]) - ref
        o = float(t["other"]) - ref
        if s == 0 and o == 0:
            angles.append(45.0)   # an equal split is the prosocial midpoint
            continue
        angles.append(math.degrees(math.atan2(o, s)))
    angle = statistics.mean(angles)

    # Ring boundaries (Liebrand & McClintock 1988), expressed on the
    # deviation frame: an equal split sits at +45, pure self-interest at 0,
    # pure other-interest at +90, and self-minus-other at -45.
    if angle >= 67.5:
        cat = "altruist"
    elif angle >= 22.5:
        cat = "prosocial"
    elif angle >= -22.5:
        cat = "individualist"
    else:
        cat = "competitive"
    return {
        "svo_angle": round(angle, 2),
        "svo_category": cat,
        "mean_self": round(statistics.mean(t["self"] for t in trials), 2),
        "mean_other": round(statistics.mean(t["other"] for t in trials), 2),
        "reference": round(ref, 2),
        "n": len(trials),
    }


def score_ucla(items: list[int]) -> dict:
    total = sum(items)
    return {"ucla_total": total, "n": len(items),
            "band": ("low" if total < 28 else "moderate" if total < 44
                     else "high")}


def score_nfc(items: list[int]) -> dict:
    return {"nfc_total": sum(items), "n": len(items)}


def score_decision_style(items: dict[str, list[int]]) -> dict:
    return {k: round(statistics.mean(v), 2) for k, v in items.items() if v}


def divergence_signal(subjective: float | None, objective: float | None,
                      subjective_scale_max: float = 4.0) -> dict:
    """Compare self-reported fog against measured performance.

    Self-reported brain fog correlates only weakly with objective
    neuropsychological performance (roughly 0.1 SD across 25,796 participants;
    Jennings et al. 2023). The two must therefore never be composited into a
    single "cognitive health" number. But the *divergence* between them is
    itself informative, and there are three distinct states a learner can be
    in, each calling for a different response:

        both impaired   -> the problem is real and measurable; reduce load
        subjective only -> the learner feels worse than they perform; this is
                           the most common post-viral pattern, and the honest
                           response is to show them the objective data rather
                           than to treat a perception as a deficit
        objective only  -> performance has dropped without the learner noticing;
                           this is the dangerous case, because they will not
                           self-refer

    Returns a state label plus the interpretation, and never a merged score.
    """
    if subjective is None or objective is None:
        return {
            "state": "insufficient_data",
            "interpretation": ("Both a subjective clarity rating and an objective "
                               "performance measure are needed to compare them."),
        }

    subj_norm = max(0.0, min(1.0, subjective / max(subjective_scale_max, 1e-9)))
    obj_norm = max(0.0, min(1.0, objective))

    # Thresholds: subjective >= 0.5 on the normalised scale is "reported fog";
    # objective below 0.6 of the learner's own baseline band is "measured drop".
    subj_bad = subj_norm >= 0.5
    obj_bad = obj_norm < 0.6

    if subj_bad and obj_bad:
        state = "concordant_impairment"
        interp = ("You report difficulty and your measured performance is also "
                  "below your baseline. Both signals agree, so the load in this "
                  "system will be reduced until the trend reverses.")
    elif subj_bad and not obj_bad:
        state = "subjective_only"
        interp = ("You report more difficulty than your measured performance "
                  "shows. This pattern is common after viral illness and is not "
                  "evidence that your ability has dropped. The objective trend "
                  "is the one to watch; the feeling is real but it is not a "
                  "measurement of capacity.")
    elif not subj_bad and obj_bad:
        state = "objective_only"
        interp = ("Your measured performance is below your baseline but you are "
                  "not reporting difficulty. This is the pattern worth acting on "
                  "first, because it will not prompt you to seek help on its own.")
    else:
        state = "concordant_healthy"
        interp = ("Your reported clarity and your measured performance agree, "
                  "and both are within your normal range.")

    return {
        "state": state,
        "subjective_normalised": round(subj_norm, 3),
        "objective_normalised": round(obj_norm, 3),
        "divergence": round(subj_norm - obj_norm, 3),
        "interpretation": interp,
        "note": ("These are reported separately and are never averaged into a "
                 "single score. Subjective and objective measures of cognition "
                 "diverge, and the divergence is the useful signal."),
    }


def _ols_slope(xs: list[float], ys: list[float]) -> float | None:
    n = len(xs)
    if n < 2:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    den = sum((x - mx) ** 2 for x in xs)
    return num / den if den else None


def _norm_ppf(p: float) -> float:
    """Inverse standard normal CDF (Acklam's rational approximation)."""
    a = (-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
         1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00)
    b = (-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
         6.680131188771972e+01, -1.328068155288572e+01)
    c = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
         -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00)
    d = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
         3.754408661907416e+00)
    plow, phigh = 0.02425, 1 - 0.02425
    if p < plow:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    if p > phigh:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
               ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
           (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1)


SCORERS: dict[str, Callable] = {
    "flanker": score_flanker,
    "dccs": score_dccs,
    "dual_nback": score_dual_nback,
    "bart": score_bart,
    "delay_discounting": score_delay_discounting,
    "ultimatum": score_ultimatum,
    "dictator": score_dictator,
    "trust_game": score_trust,
    "public_goods": score_public_goods,
    "prisoners_dilemma": score_pd,
    "social_value_orientation": score_svo,
    "loneliness_ucla": score_ucla,
    "need_for_cognition": score_nfc,
    "decision_style": score_decision_style,
}


def score_task(task_id: str, data) -> dict:
    if task_id not in SCORERS:
        raise KeyError(f"no scorer for task {task_id!r}")
    spec = REGISTRY.get(task_id)
    out = SCORERS[task_id](data)
    out["_task"] = task_id
    out["_construct"] = spec.construct if spec else ""
    out["_evidence"] = spec.evidence if spec else EVIDENCE_NONE
    return out
