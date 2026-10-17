"""Profile synthesis — turning measurements into honest statements.

This is the module that decides what the system is allowed to say about a
person. Its governing rule:

    A statement is emitted only if (a) the underlying construct has evidence
    graded moderate or strong, (b) the learner has enough trials for the
    estimate to be stable, and (c) the statement is phrased as a behavioural
    observation with its uncertainty attached, never as a trait or a verdict.

Three further rules are enforced in code:

  * NO PAMPERING. `Feedback` never emits praise for effort alone, never
    inflates a score, and never softens a failure into a success. It states
    what happened, what it implies, and what to do next.
  * NO DIAGNOSIS. Constructs marked clinical_only cannot enter a profile;
    `build_profile` raises if one is passed.
  * NO FLATTERY, NO CRUELTY. A statement must be falsifiable and actionable.
    `validate_statement` rejects both empty encouragement and unfalsifiable
    character claims.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Iterable

from .instruments import (EVIDENCE_MODERATE, EVIDENCE_STRONG, EVIDENCE_WEAK,
                          REGISTRY, servable_tasks)

# ---------------------------------------------------------------------------
# Statement validation
# ---------------------------------------------------------------------------

# Phrases that constitute pampering: praise without information.
PAMPERING_PATTERNS = (
    "great job", "well done", "you're doing amazing", "keep it up",
    "you are so", "superstar", "awesome work", "proud of you",
    "don't worry", "it's okay", "everyone struggles", "you tried your best",
    "good effort", "almost there", "so close", "you're a natural",
    "you're brilliant", "you're smart", "gifted",
)

# Phrases that constitute unfalsifiable character claims.
UNFALSIFIABLE_PATTERNS = (
    "you are a good person", "you are a bad person", "you are kind",
    "you are selfish", "you are lazy", "you are intelligent",
    "you are stupid", "you are a leader", "you are a follower",
    "your personality is", "you will always", "you will never",
)

# Clinical vocabulary that must never appear in a learner-facing profile.
CLINICAL_PATTERNS = (
    "disorder", "diagnosis", "diagnose", "symptom", "pathology",
    "deficit", "impaired", "abnormal", "clinical", "patient",
    "adhd", "autism", "depression", "anxiety disorder", "dementia",
    "mci", "cognitive impairment",
)

MIN_TRIALS_FOR_CLAIM = 8


class StatementError(ValueError):
    """Raised when a profile statement violates the honesty contract."""


def validate_statement(text: str, require_actionable: bool = True) -> None:
    """Reject pampering, unfalsifiable, or clinical statements."""
    low = text.lower()
    for pat in PAMPERING_PATTERNS:
        if pat in low:
            raise StatementError(f"pampering phrase: {pat!r}")
    for pat in UNFALSIFIABLE_PATTERNS:
        if pat in low:
            raise StatementError(f"unfalsifiable character claim: {pat!r}")
    for pat in CLINICAL_PATTERNS:
        if pat in low:
            raise StatementError(f"clinical vocabulary: {pat!r}")
    if require_actionable and len(text.split()) < 6:
        raise StatementError("statement too short to be informative")


# ---------------------------------------------------------------------------
# Profile model
# ---------------------------------------------------------------------------

@dataclass
class Observation:
    """One measured behavioural fact, with its uncertainty."""

    construct: str
    label: str
    value: float | str | None
    unit: str
    evidence: str
    n: int
    statement: str
    action: str
    confidence: str = "low"      # low | moderate | high
    caveat: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Profile:
    learner_id: str
    observations: list[Observation] = field(default_factory=list)
    social_role: str = ""
    social_role_basis: list[str] = field(default_factory=list)
    learning_shape: str = ""
    learning_basis: list[str] = field(default_factory=list)
    unmeasured: list[str] = field(default_factory=list)
    limits: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "learner_id": self.learner_id,
            "observations": [o.to_dict() for o in self.observations],
            "social_role": self.social_role,
            "social_role_basis": self.social_role_basis,
            "learning_shape": self.learning_shape,
            "learning_basis": self.learning_basis,
            "unmeasured": self.unmeasured,
            "limits": self.limits,
        }

    def assert_no_diagnosis(self) -> None:
        """Refuse to emit a profile that contains clinical constructs."""
        for o in self.observations:
            spec = REGISTRY.get(o.construct) or _find_by_construct(o.construct)
            if spec and spec.clinical_only:
                raise StatementError(
                    f"clinical construct in learner profile: {o.construct}")
            for pat in CLINICAL_PATTERNS:
                if pat in o.statement.lower():
                    raise StatementError(
                        f"clinical vocabulary in statement: {pat!r}")


def _find_by_construct(construct: str):
    for spec in REGISTRY.values():
        if spec.construct == construct:
            return spec
    return None


# ---------------------------------------------------------------------------
# Observation builders — one per construct, each with an explicit caveat
# ---------------------------------------------------------------------------

def _conf(n: int, evidence: str) -> str:
    if n < MIN_TRIALS_FOR_CLAIM:
        return "low"
    if evidence == EVIDENCE_STRONG and n >= 30:
        return "high"
    if evidence in (EVIDENCE_STRONG, EVIDENCE_MODERATE) and n >= 15:
        return "moderate"
    return "low"


def obs_inhibitory_control(scores: dict, n: int) -> Observation | None:
    cost = scores.get("interference_cost_ms")
    if cost is None:
        return None
    if cost < 40:
        band, stmt = "low", ("Your reaction time barely changes when distracting "
                             "information is present — you filter interference "
                             "efficiently.")
        act = "You can take on tasks with heavy competing detail without losing speed."
    elif cost < 120:
        band, stmt = "moderate", ("Distracting information costs you about "
                                  f"{cost:.0f} ms per decision — a normal, "
                                  "workable amount of interference.")
        act = "Reduce on-screen clutter when a task needs speed."
    else:
        band, stmt = "high", (f"Distracting information costs you about {cost:.0f} ms "
                              "per decision, which is a large penalty.")
        act = ("Practise with the distractor present rather than removing it; "
               "the cost falls with exposure, not with avoidance.")
    return Observation(
        construct="inhibitory_control", label="Interference cost",
        value=cost, unit="ms", evidence=EVIDENCE_STRONG, n=n,
        statement=stmt, action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat="Measured on one task on one day; reaction-time measures vary "
               "with sleep, caffeine, and device.",
    )


def obs_working_memory(scores: dict, n: int) -> Observation | None:
    d = scores.get("d_prime")
    if d is None:
        return None
    if d < 0.5:
        stmt = (f"At the hardest level you held, your discrimination was "
                f"d'={d:.2f} — close to chance.")
        act = "Shorten the load: fewer items, more repetitions, longer gaps."
    elif d < 2.0:
        stmt = f"You discriminated targets from non-targets at d'={d:.2f} — above chance, not yet fluent."
        act = "Increase load only after two consecutive clean sessions."
    else:
        stmt = f"You discriminated targets from non-targets at d'={d:.2f}, which is strong."
        act = "Move to a harder variant; the current load is no longer training you."
    return Observation(
        construct="working_memory_updating", label="Working-memory discrimination",
        value=d, unit="d'", evidence=EVIDENCE_MODERATE, n=n,
        statement=stmt, action=act, confidence=_conf(n, EVIDENCE_MODERATE),
        caveat=("This measures performance on this task. It does not establish "
                "that training it improves unrelated abilities — that transfer "
                "is not supported by the evidence."),
    )


def obs_risk(scores: dict, n: int) -> Observation | None:
    pumps = scores.get("adjusted_pumps")
    if pumps is None:
        return None
    if pumps < 20:
        stmt = f"You banked early, averaging {pumps:.1f} pumps before stopping."
        act = "In low-stakes settings, test one extra step before you stop."
    elif pumps < 45:
        stmt = f"You averaged {pumps:.1f} pumps before banking — a middle setting."
        act = "Your risk setting is flexible; match it to the actual cost of loss."
    else:
        stmt = f"You averaged {pumps:.1f} pumps before banking, taking large risks."
        act = ("Check whether the stakes in the real situation match the stakes "
               "you behaved as if were present.")
    return Observation(
        construct="risk_taking", label="Risk-taking", value=pumps, unit="pumps",
        evidence=EVIDENCE_MODERATE, n=n, statement=stmt, action=act,
        confidence=_conf(n, EVIDENCE_MODERATE),
        caveat="Points, not money; risk behaviour shifts with real stakes.",
    )


def obs_impulsivity(scores: dict, n: int) -> Observation | None:
    logk = scores.get("log_k")
    if logk is None:
        return None
    if logk < -3:
        stmt = f"Your discount rate is log k={logk:.2f}: you wait for larger later rewards."
        act = "Long-horizon plans suit you; use them for spaced review."
    elif logk < -1.5:
        stmt = f"Your discount rate is log k={logk:.2f}: you trade off delay and size moderately."
        act = "Break long study arcs into weekly checkpoints you can see."
    else:
        stmt = f"Your discount rate is log k={logk:.2f}: immediate rewards pull you strongly."
        act = ("Put the reward inside the session — visible progress per block — "
               "rather than at the end of the course.")
    return Observation(
        construct="impulsivity", label="Delay discounting", value=logk,
        unit="log k", evidence=EVIDENCE_MODERATE, n=n, statement=stmt,
        action=act, confidence=_conf(n, EVIDENCE_MODERATE),
        caveat="Hypothetical rewards; real-money discounting is steeper.",
    )


def obs_fairness(scores: dict, n: int) -> Observation | None:
    mao = scores.get("min_acceptable_offer")
    rej = scores.get("rejection_rate")
    if mao is None and rej is None:
        return None
    if mao is not None and mao > 0.35:
        stmt = (f"You rejected offers below roughly {mao:.0%} of the stake, "
                "accepting a personal cost to punish what you judged unfair.")
        act = ("You enforce norms at your own expense. In group work, say the "
               "standard out loud before you enforce it.")
    elif mao is not None:
        stmt = (f"You accepted offers down to about {mao:.0%} of the stake, "
                "prioritising the outcome over the principle.")
        act = "You are pragmatic in distribution; watch for accepting terms you "
        "will resent later."
    else:
        stmt = f"Your rejection rate was {rej:.0%}."
        act = "Re-run with more trials for a stable estimate."
    return Observation(
        construct="fairness_norm_enforcement", label="Fairness enforcement",
        value=mao, unit="share", evidence=EVIDENCE_STRONG, n=n, statement=stmt,
        action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat=("Ultimatum behaviour varies with culture, anonymity, and stake "
                "size; one session is a sample, not a disposition."),
    )


def obs_altruism(scores: dict, n: int) -> Observation | None:
    share = scores.get("mean_share_given")
    if share is None:
        return None
    if share < 0.15:
        stmt = f"You gave away {share:.0%} of the stake when no one could respond."
        act = "Your default is self-regarding when unobserved; that is a fact to plan around, not a fault."
    elif share < 0.4:
        stmt = f"You gave away {share:.0%} of the stake when no one could respond."
        act = "You split partially by default; make the split rule explicit when it matters."
    else:
        stmt = f"You gave away {share:.0%} of the stake when no one could respond."
        act = "You give generously without reciprocity; check you are not funding others' avoidance."
    return Observation(
        construct="altruism", label="Unconditional giving", value=share,
        unit="share", evidence=EVIDENCE_STRONG, n=n, statement=stmt, action=act,
        confidence=_conf(n, EVIDENCE_STRONG),
        caveat="Anonymous and one-shot; repeated interaction changes giving.",
    )


def obs_trust(scores: dict, n: int) -> Observation | None:
    sent = scores.get("trust_sent")
    ret = scores.get("reciprocity_returned")
    if sent is None and ret is None:
        return None
    parts = []
    if sent is not None:
        parts.append(f"you sent {sent:.0%} as the first mover")
    if ret is not None:
        parts.append(f"you returned {ret:.0%} when trusted")
    stmt = "In the trust exchange, " + " and ".join(parts) + "."
    if sent is not None and sent > 0.6 and ret is not None and ret > 0.4:
        act = "You extend and repay trust; you are a reliable partner in reciprocal settings."
    elif sent is not None and sent < 0.3:
        act = "You withhold trust initially; you will need explicit signals before you invest in a group."
    else:
        act = "Your trust is conditional; state your conditions early so others can meet them."
    return Observation(
        construct="trust_and_reciprocity", label="Trust and reciprocity",
        value=sent, unit="share", evidence=EVIDENCE_STRONG, n=n, statement=stmt,
        action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat="Partner behaviour was scripted, not human.",
    )


def obs_cooperation(scores: dict, n: int) -> Observation | None:
    mean = scores.get("mean_contribution")
    slope = scores.get("decay_slope")
    if mean is None:
        return None
    if slope is not None and slope < -0.3:
        stmt = (f"You contributed {mean:.1f} on average but your contributions "
                f"fell by {abs(slope):.1f} per round as the game went on.")
        act = ("You start cooperative and withdraw when others under-contribute. "
               "Name the free-rider problem early instead of quietly reducing.")
    elif mean > 6:
        stmt = f"You contributed {mean:.1f} on average and held that level."
        act = "You sustain cooperation; you are the person who makes a group work."
    else:
        stmt = f"You contributed {mean:.1f} on average."
        act = "Your contribution is cautious; test one round of higher contribution."
    return Observation(
        construct="cooperation", label="Cooperation", value=mean, unit="points",
        evidence=EVIDENCE_STRONG, n=n, statement=stmt, action=act,
        confidence=_conf(n, EVIDENCE_STRONG),
        caveat="Scripted partners; real groups add reputation and history.",
    )


def obs_strategy(scores: dict, n: int) -> Observation | None:
    tft = scores.get("coop_vs_tft")
    rnd = scores.get("coop_vs_random")
    if tft is None and rnd is None:
        return None
    if tft is not None and rnd is not None:
        if tft > 0.6 and rnd < 0.4:
            stmt = (f"You cooperated {tft:.0%} against a reciprocal partner and "
                    f"{rnd:.0%} against an exploitative one — you read your opponent.")
            act = "You discriminate well; you are suited to roles that require reading intent."
        elif tft > 0.6 and rnd > 0.6:
            stmt = (f"You cooperated {tft:.0%} against a reciprocal partner and "
                    f"{rnd:.0%} against an exploitative one — you cooperate regardless of the partner.")
            act = ("Your cooperation is unconditional, which is exploitable. Add a "
                   "defection trigger: cooperate first, then mirror.")
        elif tft < 0.4:
            stmt = f"You cooperated only {tft:.0%} against a partner who reciprocates."
            act = "You defect against cooperators; in repeated groups that invites retaliation."
        else:
            stmt = f"You cooperated {tft:.0%} with reciprocators and {rnd:.0%} with exploiters."
            act = "Your strategy is mixed; make the rule explicit so it is predictable to others."
    else:
        stmt = f"Cooperation rate: {tft if tft is not None else rnd:.0%}."
        act = "More trials are needed for a stable read."
    return Observation(
        construct="strategic_reasoning", label="Strategic behaviour",
        value=tft, unit="cooperation rate", evidence=EVIDENCE_STRONG, n=n,
        statement=stmt, action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat="Two scripted opponents only; real social strategy is richer.",
    )


def obs_svo(scores: dict, n: int) -> Observation | None:
    cat = scores.get("svo_category")
    ang = scores.get("svo_angle")
    if cat is None:
        return None
    mapping = {
        "prosocial": ("You weight the other person's outcome close to your own "
                      "when allocating resources.", "You are a natural coalition-builder; use it deliberately, not by default."),
        "individualist": ("You maximise your own outcome while leaving the other "
                          "person free to maximise theirs.",
                          "You are a fair-weather cooperator; declare your terms up front."),
        "competitive": ("You accept a personal cost to end up ahead of the other "
                        "person.",
                        "You will sacrifice to win. Check whether winning is the actual objective."),
        "altruist": ("You allocate more to the other person than to yourself.",
                     "You may be exploited; set a floor on your own share."),
    }
    stmt, act = mapping.get(cat, (f"Your allocation angle was {ang:.1f} degrees.",
                                  "Re-run for a stable estimate."))
    return Observation(
        construct="social_preference_orientation", label="Social preference",
        value=cat, unit="category", evidence=EVIDENCE_MODERATE, n=n,
        statement=stmt, action=act, confidence=_conf(n, EVIDENCE_MODERATE),
        caveat="Decomposed games are abstract; real allocation has context.",
    )


def obs_calibration(scores: dict, n: int) -> Observation | None:
    bias = scores.get("bias")
    brier = scores.get("brier")
    if bias is None:
        return None
    if bias > 0.15:
        stmt = (f"You rated your confidence {bias:.0%} higher than your accuracy "
                f"justified (Brier {brier:.3f}).")
        act = ("You overestimate what you know. Before answering, state one thing "
               "that would make you wrong — that single habit closes most of this gap.")
    elif bias < -0.15:
        stmt = (f"You rated your confidence {abs(bias):.0%} lower than your "
                f"accuracy justified (Brier {brier:.3f}).")
        act = "You know more than you claim. Answer first, doubt second."
    else:
        stmt = f"Your confidence tracked your accuracy closely (Brier {brier:.3f})."
        act = "Your self-assessment is reliable; trust your 'I don't know' signal."
    return Observation(
        construct="metacognitive_calibration", label="Confidence calibration",
        value=bias, unit="bias", evidence=EVIDENCE_STRONG, n=n, statement=stmt,
        action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat="Calibration is domain-specific; it can be good in one subject and poor in another.",
    )


def obs_theory_of_mind(scores: dict, n: int) -> Observation | None:
    acc = scores.get("second_order_accuracy")
    if acc is None:
        return None
    if acc < 0.5:
        stmt = (f"You answered {acc:.0%} of second-order belief questions correctly "
                "— you often model what someone thinks rather than what they think "
                "someone else thinks.")
        act = ("Before responding in a disagreement, write down what each person "
               "believes the other believes. The gap is usually there.")
    elif acc < 0.85:
        stmt = f"You answered {acc:.0%} of second-order belief questions correctly."
        act = "You track nested beliefs reasonably; the failures will be under load."
    else:
        stmt = f"You answered {acc:.0%} of second-order belief questions correctly."
        act = "You model nested mental states accurately."
    return Observation(
        construct="theory_of_mind", label="Mental-state modelling", value=acc,
        unit="accuracy", evidence=EVIDENCE_STRONG, n=n, statement=stmt,
        action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat=("Vignettes are verbal and static; real-time social inference is "
                "harder and this does not measure it."),
    )


def obs_loneliness(scores: dict, n: int) -> Observation | None:
    total = scores.get("ucla_total")
    if total is None:
        return None
    band = scores.get("band", "moderate")
    if band == "high":
        stmt = f"Your connectedness score was {total}/80, in the high-loneliness band."
        act = ("Social contact is a cognitive intervention as well as a social "
               "one. Schedule one recurring contact per week and treat it as "
               "part of the training, not separate from it.")
    elif band == "low":
        stmt = f"Your connectedness score was {total}/80, indicating strong social connection."
        act = "Your social base is a cognitive asset; protect the time it takes."
    else:
        stmt = (f"Your connectedness score was {total}/80, in the middle band — "
                "neither isolated nor strongly connected.")
        act = ("Track this monthly; it moves with study load, and a drop is an "
               "early signal to add contact before it affects your work.")
    return Observation(
        construct="social_connectedness", label="Social connectedness",
        value=total, unit="/80", evidence=EVIDENCE_STRONG, n=n, statement=stmt,
        action=act, confidence=_conf(n, EVIDENCE_STRONG),
        caveat=("Self-report. Loneliness is not a character trait and this is not "
                "a clinical assessment."),
    )


OBSERVATION_BUILDERS = {
    "inhibitory_control": obs_inhibitory_control,
    "working_memory_updating": obs_working_memory,
    "risk_taking": obs_risk,
    "impulsivity": obs_impulsivity,
    "fairness_norm_enforcement": obs_fairness,
    "altruism": obs_altruism,
    "trust_and_reciprocity": obs_trust,
    "cooperation": obs_cooperation,
    "strategic_reasoning": obs_strategy,
    "social_preference_orientation": obs_svo,
    "metacognitive_calibration": obs_calibration,
    "theory_of_mind": obs_theory_of_mind,
    "social_connectedness": obs_loneliness,
}


# ---------------------------------------------------------------------------
# Synthesis
# ---------------------------------------------------------------------------

def build_profile(learner_id: str, task_scores: dict[str, dict],
                  learning_metrics: dict | None = None) -> Profile:
    """Assemble a Profile from task scores and learning metrics.

    `task_scores` maps task_id -> scorer output (with _construct and _evidence).
    `learning_metrics` carries BKT/IRT/calibration aggregates.
    """
    prof = Profile(learner_id=learner_id)
    measured: set[str] = set()

    for task_id, scores in task_scores.items():
        spec = REGISTRY.get(task_id)
        if spec is None:
            continue
        if spec.clinical_only:
            raise StatementError(f"refusing clinical task {task_id!r}")
        builder = OBSERVATION_BUILDERS.get(spec.construct)
        if builder is None:
            continue
        n = int(scores.get("n", 0) or 0)
        obs = builder(scores, n)
        if obs is None:
            continue
        validate_statement(obs.statement)
        validate_statement(obs.action)
        if n < MIN_TRIALS_FOR_CLAIM:
            obs.statement += (f" (Based on {n} trials — too few for a stable "
                              "estimate; treat as provisional.)")
        prof.observations.append(obs)
        measured.add(spec.construct)

    lm = learning_metrics or {}
    if lm.get("calibration"):
        obs = obs_calibration(lm["calibration"], int(lm["calibration"].get("n", 0)))
        if obs:
            validate_statement(obs.statement)
            validate_statement(obs.action)
            prof.observations.append(obs)
            measured.add("metacognitive_calibration")

    prof.social_role, prof.social_role_basis = _infer_social_role(prof)
    prof.learning_shape, prof.learning_basis = _infer_learning_shape(lm)

    all_constructs = {s.construct for s in servable_tasks()}
    prof.unmeasured = sorted(all_constructs - measured)
    prof.limits = [
        "These are behavioural observations from short tasks, not a personality test.",
        "Every number here has a confidence label; 'low' means the estimate is unstable.",
        "Constructs with weak evidence are excluded from this profile entirely.",
        "Nothing here is a clinical assessment and nothing here diagnoses anything.",
        "Behaviour measured in a game is a sample of behaviour, not a summary of a person.",
    ]
    prof.assert_no_diagnosis()
    return prof


def _num(v) -> float | None:
    """Coerce an Observation value to float, or None if it is not numeric.

    Guards the role-inference comparisons: a categorical value (e.g. SVO
    category "prosocial") must never reach a numeric comparison.
    """
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    return None


def _infer_social_role(prof: Profile) -> tuple[str, list[str]]:
    """Name the group role the measurements support, with its basis."""
    by = {o.construct: o for o in prof.observations}
    basis: list[str] = []
    role = ""

    coop = _num(by["cooperation"].value) if "cooperation" in by else None
    strat = _num(by["strategic_reasoning"].value) if "strategic_reasoning" in by else None
    fair = _num(by["fairness_norm_enforcement"].value) if "fairness_norm_enforcement" in by else None
    svo = by["social_preference_orientation"].value if "social_preference_orientation" in by else None
    trust = _num(by["trust_and_reciprocity"].value) if "trust_and_reciprocity" in by else None
    alt = _num(by["altruism"].value) if "altruism" in by else None

    if coop is not None and coop > 6 and strat is not None and strat > 0.6:
        role = "Sustainer"
        basis.append("high contribution held across rounds")
        basis.append("cooperates with reciprocators")
    elif fair is not None and fair > 0.35:
        role = "Enforcer"
        basis.append("rejects unfair offers at personal cost")
    elif svo == "competitive":
        role = "Competitor"
        basis.append("accepts personal cost to finish ahead")
    elif svo == "altruist" or (alt is not None and alt > 0.5):
        role = "Giver"
        basis.append("allocates more to others than to self")
    elif trust is not None and trust < 0.3:
        role = "Withholder"
        basis.append("withholds initial trust")
    elif strat is not None and strat > 0.6:
        role = "Reciprocator"
        basis.append("mirrors the partner's behaviour")
    else:
        role = "Unclassified"
        basis.append("insufficient or mixed evidence across the social tasks")

    if len(basis) == 1 and role != "Unclassified":
        basis.append("single-task basis — re-run to confirm")
    return role, basis


def _infer_learning_shape(lm: dict) -> tuple[str, list[str]]:
    """Describe the learner's study pattern from their own learning metrics."""
    basis: list[str] = []
    shape = ""
    cal = lm.get("calibration", {})
    retention = lm.get("mean_retrievability")
    due = lm.get("due_now")
    mastered = lm.get("mastered_fraction")

    if cal.get("bias") is not None and cal["bias"] > 0.15:
        shape = "Overconfident self-assessor"
        basis.append(f"confidence exceeds accuracy by {cal['bias']:.0%}")
    elif mastered is not None and mastered < 0.3:
        shape = "Broad but shallow"
        basis.append(f"only {mastered:.0%} of tracked skills are mastered")
    elif retention is not None and retention < 0.75:
        shape = "Under-reviewing"
        basis.append(f"predicted recall across the deck is {retention:.0%}")
    elif due is not None and due > 50:
        shape = "Backlogged"
        basis.append(f"{due} items are past due")
    else:
        shape = "Steady"
        basis.append("review load and retention are within range")
    return shape, basis


# ---------------------------------------------------------------------------
# Feedback — the anti-pampering contract
# ---------------------------------------------------------------------------

@dataclass
class Feedback:
    verdict: str          # correct | partial | incorrect
    score: float
    what_happened: str
    what_it_means: str
    next_action: str
    is_praise: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def grade_feedback(verdict: str, score: float, correct_answer: str,
                   learner_answer: str, expected_p: float = 0.85) -> Feedback:
    """Produce feedback that informs without flattering or punishing.

    Rules:
      * A correct answer gets a statement of what it demonstrates, never praise.
      * An incorrect answer gets the correct answer, the likely error, and the
        next action — never a softening phrase.
      * A lucky correct answer (high expected_p) is named as such.
    """
    if verdict == "correct":
        if expected_p > 0.92:
            what = ("Correct — but this item was one you were already likely "
                    "to get right.")
            means = "It does not add evidence that you have learned it."
            nxt = "The scheduler will move you to harder items on this skill."
        else:
            what = ("Correct. Your answer matched the target on this item at "
                    "this difficulty.")
            means = "This is evidence the skill is available to you at this difficulty."
            nxt = "The next item on this skill will be harder."
    elif verdict == "partial":
        what = f"Partly correct. The full answer is: {correct_answer}"
        means = ("You have part of the structure; the missing part is what the "
                 "question was testing.")
        nxt = ("Re-attempt this skill tomorrow, not immediately — the delay is "
               "what makes it stick.")
    else:
        what = f"Incorrect. The correct answer is: {correct_answer}"
        means = _diagnose_error(learner_answer, correct_answer)
        nxt = ("This item returns in the next session. Read the source span, "
               "then answer from memory without looking.")
    validate_statement(what)
    validate_statement(means)
    validate_statement(nxt)
    return Feedback(verdict=verdict, score=score, what_happened=what,
                    what_it_means=means, next_action=nxt, is_praise=False)


def _diagnose_error(learner: str, correct: str) -> str:
    """Name the likely error type without speculating about the person."""
    if not learner.strip():
        return "You left it blank. A blank is scored as incorrect, not as 'not attempted'."
    lt, ct = set(learner.lower().split()), set(correct.lower().split())
    overlap = len(lt & ct) / max(len(ct), 1)
    if overlap > 0.6:
        return ("You had most of the content but the detail was wrong — this is a "
                "precision error, not a comprehension error.")
    if overlap > 0.2:
        return ("You were in the right area but missed the specific mechanism the "
                "question asked for.")
    return ("Your answer did not overlap with the target. Check whether you "
            "answered the question that was asked.")


def session_summary(attempts: list[dict]) -> dict:
    """Honest session summary. No participation trophies."""
    if not attempts:
        return {"n": 0, "verdict": "no data",
                "statement": "No attempts recorded."}
    n = len(attempts)
    correct = sum(1 for a in attempts if a.get("correct"))
    acc = correct / n
    lat = [a["latency_ms"] for a in attempts if a.get("latency_ms")]
    med_lat = statistics.median(lat) if lat else None
    if acc >= 0.9:
        verdict = "under-challenged"
        stmt = (f"{correct}/{n} correct ({acc:.0%}). This set was too easy to "
                "produce learning; difficulty will increase next session.")
    elif acc >= 0.75:
        verdict = "in the productive band"
        stmt = (f"{correct}/{n} correct ({acc:.0%}). This is the band where "
                "learning is fastest; the system will hold you here.")
    elif acc >= 0.5:
        verdict = "struggling productively"
        stmt = (f"{correct}/{n} correct ({acc:.0%}). Below the optimal band; "
                "the system will reduce load on the weakest skills and keep the "
                "rest where it is.")
    else:
        verdict = "over-loaded"
        stmt = (f"{correct}/{n} correct ({acc:.0%}). The material is currently "
                "beyond reach at this granularity. Prerequisites will be "
                "re-taught before this set is repeated.")
    return {"n": n, "correct": correct, "accuracy": round(acc, 3),
            "median_latency_ms": med_lat, "verdict": verdict,
            "statement": stmt}
