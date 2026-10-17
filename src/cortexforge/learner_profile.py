"""Learner profile — the 10-dimension model from the Mentat/NPALS specification.

Every field in this model follows the Open Learner Model (OLM) principle:
each estimate is visible to the learner, carries its provenance (the events
that produced it), and can be challenged. The learner is not a passive
subject of measurement but an active participant who can contest any claim
the system makes about them.

The ten dimensions:
  1. KnowledgeState        per-skill mastery, prerequisites, misconceptions
  2. CognitiveCapacities   WM proxy, processing speed, fluid reasoning
  3. PriorKnowledge        curriculum history, prerequisites, language
  4. MotivationProfile     SDT needs, goal orientation, expectancy-value
  5. AffectWellbeing       academic emotions, test anxiety, boredom thresholds
  6. GoalsValues           short/long-term goals, deadlines, exams
  7. SelfRegulation        SRL phase skills, planning quality, calibration
  8. ContextEnvironment    time budget, sleep, chronotype, devices
  9. Preferences           format, session length, feedback density
 10. InteractionHistory    all events, tutor dialogues

Security constraints inherited from the existing profile module:
  * No clinical language about the learner.
  * No praise without information.
  * No unfalsifiable character claims.
"""

from __future__ import annotations

import copy
import time
from dataclasses import dataclass, field, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Dimension definitions
# ---------------------------------------------------------------------------

DIMENSION_NAMES: tuple[str, ...] = (
    "knowledge_state",
    "cognitive_capacities",
    "prior_knowledge",
    "motivation_profile",
    "affect_wellbeing",
    "goals_values",
    "self_regulation",
    "context_environment",
    "preferences",
    "interaction_history",
)

# Fields each dimension tracks, with their types and default values.
# The keys here are the dot-addressable paths used by challenge() and
# provenance() (e.g. "knowledge_state.mastery").
DIMENSION_FIELDS: dict[str, dict[str, Any]] = {
    "knowledge_state": {
        "mastery": {},          # skill_id -> {p_known, opportunities, updated_at}
        "prerequisites": {},    # skill_id -> [prerequisite_skill_ids]
        "misconceptions": {},   # misconception_id -> {skill_id, statement, count}
        "skills_tracked": 0,    # number of skills with at least one attempt
    },
    "cognitive_capacities": {
        "wm_proxy": None,       # d' from n-back, or None
        "processing_speed": None,  # ms per decision, or None
        "fluid_reasoning": None,   # normalized score, or None
        "interference_cost_ms": None,  # flanker interference cost
        "n_instruments_run": 0,
    },
    "prior_knowledge": {
        "curriculum": "",       # self-reported or inferred curriculum
        "prerequisites_met": [],  # list of prerequisite skill IDs confirmed
        "language": "",         # primary learning language
        "domain_experience": "",  # self-reported domain background
    },
    "motivation_profile": {
        "goal_orientation": "",  # "mastery" | "performance" | "mixed" | ""
        "intrinsic_motivation": None,  # 0-1 self-report or inferred
        "extrinsic_motivation": None,  # 0-1 self-report or inferred
        "expectancy": None,     # 0-1 self-reported confidence of success
        "task_value": None,     # 0-1 self-reported perceived value
        "self_determination": {},  # {autonomy, competence, relatedness} -> 0-1
    },
    "affect_wellbeing": {
        "academic_emotions": {},  # emotion -> intensity (0-1)
        "test_anxiety": None,   # 0-1 self-report or inferred
        "boredom_threshold": None,  # minutes before disengagement, or None
        "frustration_tolerance": None,  # 0-1 inferred from practice
        "social_connectedness": None,  # UCLA score, or None
    },
    "goals_values": {
        "short_term_goals": [],   # list of {goal, deadline, done}
        "long_term_goals": [],    # list of {goal, deadline, done}
        "exams": [],            # list of {name, date, priority}
        "deadline_pressure": None,  # 0-1 inferred
    },
    "self_regulation": {
        "planning_quality": None,  # 0-1 inferred from schedule adherence
        "monitoring_accuracy": None,  # calibration bias (over/under-confidence)
        "control_strategy": "",  # "preventive" | "reactive" | "mixed" | ""
        "help_seeking": None,   # 0-1 frequency of help requests
        "procrastination_index": None,  # 0-1 inferred from timing patterns
    },
    "context_environment": {
        "session_minutes": 20,   # preferred session length
        "days_per_week": 4,      # preferred study days
        "best_time": "",         # "morning" | "afternoon" | "evening" | ""
        "chronotype": "",        # "lark" | "owl" | "intermediate" | ""
        "sleep_hours": None,     # self-reported average
        "devices": [],           # ["desktop", "tablet", "mobile"]
        "time_budget_weekly": None,  # hours per week available
    },
    "preferences": {
        "format": [],            # preferred content formats
        "feedback_density": "normal",  # "low" | "normal" | "high"
        "difficulty_setting": "evidence_band",  # "gentler" | "evidence_band" | "maximum"
        "target_success_rate": 0.85,
        "content_modalities": [],  # ["text", "interactive", "video"]
    },
    "interaction_history": {
        "total_attempts": 0,
        "total_sessions": 0,
        "total_reviews": 0,
        "first_seen": None,      # timestamp
        "last_seen": None,       # timestamp
        "tutor_dialogues": [],   # list of {timestamp, topic, summary}
        "session_log": [],       # list of {date, n_attempts, accuracy}
    },
}

# ---------------------------------------------------------------------------
# Dimension and audit data structures
# ---------------------------------------------------------------------------


@dataclass
class Dimension:
    """One dimension of the learner profile.

    Tracks the data, confidence in that data, provenance (event IDs that
    support the estimate), and when it was last updated.
    """

    name: str
    confidence: float = 0.0
    provenance: list[str] = field(default_factory=list)
    data: dict = field(default_factory=dict)
    last_updated: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "confidence": round(self.confidence, 4),
            "provenance": list(self.provenance),
            "data": dict(self.data),
            "last_updated": self.last_updated,
        }


@dataclass
class AuditEntry:
    """One audit trail entry — every change is recorded.

    The audit trail is append-only. It records what changed, when, from
    what source, and which events support the new value.
    """

    version: int
    timestamp: float
    dimension: str
    field: str
    old_value: Any
    new_value: Any
    source: str             # "practice" | "instrument" | "override" | "system"
    provenance: list[str] = field(default_factory=list)
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# LearnerProfile
# ---------------------------------------------------------------------------


class LearnerProfile:
    """The 10-dimension learner profile.

    Every update increments the version and appends to the audit log.
    The learner can challenge any field, which reduces its confidence and
    records the dispute without destroying the underlying evidence.
    """

    def __init__(self, learner_id: str):
        self.learner_id = learner_id
        self.version: int = 1
        self.created_at: float = time.time()
        self.dimensions: dict[str, Dimension] = {}
        self.audit_log: list[AuditEntry] = []
        self._challenges: dict[str, list[dict]] = {}

        for name in DIMENSION_NAMES:
            defaults = DIMENSION_FIELDS.get(name, {})
            self.dimensions[name] = Dimension(
                name=name,
                confidence=0.0,
                provenance=[],
                data=copy.deepcopy(defaults),
                last_updated=0.0,
            )

    # ------------------------------------------------------------------
    # Core update mechanism
    # ------------------------------------------------------------------

    def _apply_update(
        self,
        dimension_name: str,
        field: str,
        new_value: Any,
        source: str,
        event_id: str,
        confidence: float | None = None,
        note: str = "",
    ) -> None:
        """Apply a single field update, audit it, and bump the version."""
        if dimension_name not in self.dimensions:
            raise KeyError(f"unknown dimension: {dimension_name!r}")

        dim = self.dimensions[dimension_name]
        old_value = copy.deepcopy(dim.data.get(field))
        dim.data[field] = copy.deepcopy(new_value)

        if event_id and event_id not in dim.provenance:
            dim.provenance.append(event_id)

        if confidence is not None:
            dim.confidence = max(0.0, min(1.0, confidence))
        elif source == "instrument":
            # Instruments start with moderate-high confidence
            dim.confidence = max(dim.confidence, 0.6)
        elif source == "override":
            # Learner self-knowledge is high confidence but self-reported
            dim.confidence = max(dim.confidence, 0.8)
        elif source == "practice":
            # Practice events build confidence gradually
            n = len(dim.provenance)
            dim.confidence = max(dim.confidence, min(0.3 + n * 0.05, 0.9))

        dim.last_updated = time.time()

        entry = AuditEntry(
            version=self.version,
            timestamp=dim.last_updated,
            dimension=dimension_name,
            field=field,
            old_value=old_value,
            new_value=new_value,
            source=source,
            provenance=list(dim.provenance),
            note=note,
        )
        self.audit_log.append(entry)
        self.version += 1

    def update_dimension(
        self,
        dimension_name: str,
        updates: dict[str, Any],
        source: str,
        event_id: str = "",
        confidence: float | None = None,
        note: str = "",
    ) -> int:
        """Apply multiple field updates to one dimension.

        Returns the new version number.
        """
        for field_name, value in updates.items():
            self._apply_update(
                dimension_name, field_name, value,
                source, event_id, confidence, note,
            )
        return self.version

    # ------------------------------------------------------------------
    # Source-specific update methods
    # ------------------------------------------------------------------

    def update_from_practice(
        self,
        dimension_name: str,
        event_id: str,
        updates: dict[str, Any],
        confidence: float | None = None,
    ) -> int:
        """Update a dimension from a practice event (attempt, review, session).

        Practice events build confidence gradually — a single attempt is
        weak evidence, a pattern across many attempts is strong evidence.
        """
        return self.update_dimension(
            dimension_name, updates, "practice", event_id, confidence,
        )

    def update_from_instrument(
        self,
        dimension_name: str,
        event_id: str,
        updates: dict[str, Any],
        confidence: float | None = None,
    ) -> int:
        """Update a dimension from an instrument result (task, probe, scale).

        Instruments carry higher initial confidence because they are
        standardized measures, but their confidence still decays if
        contradicted by practice evidence.
        """
        return self.update_dimension(
            dimension_name, updates, "instrument", event_id, confidence,
        )

    def update_from_override(
        self,
        dimension_name: str,
        updates: dict[str, Any],
        reason: str = "",
    ) -> int:
        """Update a dimension from a learner override.

        The learner can set any value directly. The system records the
        override with high confidence but notes that it is self-reported.
        The original measured value is preserved in the audit trail.
        """
        return self.update_dimension(
            dimension_name, updates, "override", event_id="",
            confidence=0.9, note=reason,
        )

    # ------------------------------------------------------------------
    # Convenience methods for common dimensions
    # ------------------------------------------------------------------

    def record_attempt(
        self,
        skill_id: str,
        correct: bool,
        event_id: str,
        confidence: float | None = None,
    ) -> int:
        """Record a practice attempt and update knowledge_state + interaction_history."""
        dim = self.dimensions["knowledge_state"]
        mastery = dim.data["mastery"]

        if skill_id not in mastery:
            mastery[skill_id] = {
                "p_known": 0.2, "opportunities": 0, "correct": 0,
            }
        entry = mastery[skill_id]
        entry["opportunities"] += 1
        entry["correct"] += 1 if correct else 0
        # Simple BKT-like update
        k = entry["p_known"]
        if correct:
            entry["p_known"] = min(0.95, k + 0.15 * (1 - k))
        else:
            entry["p_known"] = max(0.05, k - 0.10 * k)

        dim.data["skills_tracked"] = len(mastery)

        # Also update interaction history
        ih = self.dimensions["interaction_history"]
        ih.data["total_attempts"] += 1

        return self.update_from_practice(
            "knowledge_state", event_id,
            {"mastery": mastery, "skills_tracked": len(mastery)},
            confidence,
        )

    def record_instrument_score(
        self,
        dimension_name: str,
        event_id: str,
        updates: dict[str, Any],
    ) -> int:
        """Record instrument results (flanker, n-back, etc.)."""
        # Also update interaction history
        self.dimensions["interaction_history"].data["total_sessions"] += 1
        return self.update_from_instrument(
            dimension_name, event_id, updates,
        )

    def record_session(
        self,
        event_id: str,
        date: float,
        n_attempts: int,
        accuracy: float,
    ) -> int:
        """Record a completed session and update relevant dimensions."""
        ih = self.dimensions["interaction_history"]
        ih.data["total_sessions"] += 1
        ih.data["last_seen"] = date
        ih.data["first_seen"] = ih.data["first_seen"] or date

        session_entry = {
            "date": date,
            "n_attempts": n_attempts,
            "accuracy": round(accuracy, 4),
        }
        ih.data["session_log"].append(session_entry)
        # Keep only last 100 sessions
        if len(ih.data["session_log"]) > 100:
            ih.data["session_log"] = ih.data["session_log"][-100:]

        return self.update_from_practice(
            "interaction_history", event_id,
            {
                "total_sessions": ih.data["total_sessions"],
                "last_seen": date,
                "session_log": ih.data["session_log"],
            },
        )

    # ------------------------------------------------------------------
    # Challenge and provenance
    # ------------------------------------------------------------------

    def challenge(self, field: str, claim: str) -> dict:
        """Allow the learner to contest a profile estimate.

        The challenge is recorded, the field's confidence is reduced (it
        is now disputed), and the challenge text is stored. The underlying
        data is NOT removed — the evidence still exists, but the system
        now marks it as contested.

        `field` can be a dimension name ("knowledge_state") or a
        dotted path ("knowledge_state.mastery").

        Returns the challenge record.
        """
        parts = field.split(".", 1)
        dimension_name = parts[0]
        sub_field = parts[1] if len(parts) > 1 else None

        if dimension_name not in self.dimensions:
            raise KeyError(f"unknown dimension: {dimension_name!r}")

        dim = self.dimensions[dimension_name]

        # Reduce confidence — the estimate is now disputed
        old_confidence = dim.confidence
        dim.confidence = max(0.0, old_confidence * 0.5)

        challenge_record = {
            "field": field,
            "sub_field": sub_field,
            "claim": claim,
            "timestamp": time.time(),
            "version": self.version,
            "confidence_before": round(old_confidence, 4),
            "confidence_after": round(dim.confidence, 4),
            "status": "disputed",
        }

        if field not in self._challenges:
            self._challenges[field] = []
        self._challenges[field].append(challenge_record)

        # Audit the challenge
        entry = AuditEntry(
            version=self.version,
            timestamp=challenge_record["timestamp"],
            dimension=dimension_name,
            field=sub_field or "*",
            old_value=old_confidence,
            new_value=dim.confidence,
            source="system",
            provenance=list(dim.provenance),
            note=f"learner challenge: {claim}",
        )
        self.audit_log.append(entry)
        self.version += 1

        return challenge_record

    def provenance(self, field: str) -> list[str]:
        """Return the events behind an estimate.

        `field` can be a dimension name or a dotted path. Returns the
        list of event IDs that support the current estimate.
        """
        parts = field.split(".", 1)
        dimension_name = parts[0]

        if dimension_name not in self.dimensions:
            raise KeyError(f"unknown dimension: {dimension_name!r}")

        dim = self.dimensions[dimension_name]
        return list(dim.provenance)

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self) -> dict:
        """Return the full profile as a JSON-serializable dict."""
        return {
            "learner_id": self.learner_id,
            "version": self.version,
            "created_at": self.created_at,
            "dimensions": {
                name: dim.to_dict() for name, dim in self.dimensions.items()
            },
            "challenges": {
                field: challenges
                for field, challenges in self._challenges.items()
            },
            "audit_log": [entry.to_dict() for entry in self.audit_log],
        }

    # ------------------------------------------------------------------
    # Security-conscious statement generation
    # ------------------------------------------------------------------

    def describe(self, field: str, require_actionable: bool = True) -> str:
        """Generate a plain-language, falsifiable description of a field.

        Follows the security constraints:
          * No clinical language.
          * No praise without information.
          * No unfalsifiable character claims.
        """
        parts = field.split(".", 1)
        dim_name = parts[0]
        sub_field = parts[1] if len(parts) > 1 else None

        if dim_name not in self.dimensions:
            raise KeyError(f"unknown dimension: {dim_name!r}")

        dim = self.dimensions[dim_name]
        value = dim.data.get(sub_field) if sub_field else None
        conf = dim.confidence
        n_events = len(dim.provenance)

        if conf < 0.3 or n_events < 2:
            return (
                f"Insufficient evidence to make a claim about {field}. "
                f"Currently based on {n_events} event(s)."
            )

        # Build an honest, falsifiable statement
        if isinstance(value, bool):
            state = "yes" if value else "no"
            return (
                f"Based on {n_events} event(s), the current estimate for "
                f"{field} is {state}. Confidence: {conf:.0%}. "
                f"This estimate is open to challenge."
            )
        elif isinstance(value, (int, float)):
            return (
                f"Based on {n_events} event(s), the current estimate for "
                f"{field} is {value}. Confidence: {conf:.0%}. "
                f"This estimate is open to challenge."
            )
        elif isinstance(value, str) and value:
            return (
                f"Based on {n_events} event(s), {field} is recorded as "
                f"\"{value}\". Confidence: {conf:.0%}. "
                f"This estimate is open to challenge."
            )
        else:
            return (
                f"Based on {n_events} event(s), {field} is recorded. "
                f"Confidence: {conf:.0%}. This estimate is open to challenge."
            )

    # ------------------------------------------------------------------
    # Batch operations
    # ------------------------------------------------------------------

    def apply_onboarding(self, contract: dict) -> int:
        """Populate the profile from a LearningContract.

        This is the bridge from the onboarding module's 13 probes to the
        10-dimension profile.
        """
        # Goals & values
        goals_updates = {}
        if contract.get("goal_type"):
            goals_updates["short_term_goals"] = [
                {"goal": contract["goal_type"], "deadline": None, "done": False}
            ]

        # Preferences
        pref_updates = {
            "session_minutes": contract.get("session_minutes", 20),
            "days_per_week": contract.get("days_per_week", 4),
            "best_time": contract.get("best_time", ""),
            "difficulty_setting": contract.get("difficulty_setting", "evidence_band"),
            "target_success_rate": contract.get("target_success_rate", 0.85),
        }

        # Context & environment
        ctx_updates = {
            "session_minutes": contract.get("session_minutes", 20),
            "days_per_week": contract.get("days_per_week", 4),
            "best_time": contract.get("best_time", ""),
        }

        # Prior knowledge
        prior_updates = {
            "curriculum": contract.get("domain", ""),
            "domain_experience": contract.get("domain_shape", ""),
        }

        # Self-regulation (from calibration probe)
        srl_updates = {}
        if contract.get("fog_baseline") is not None:
            srl_updates["planning_quality"] = max(
                0.0, 1.0 - contract["fog_baseline"] / 4.0
            )

        version = self.version
        if goals_updates:
            version = self.update_from_instrument(
                "goals_values", "onboarding", goals_updates
            )
        version = self.update_from_instrument(
            "preferences", "onboarding", pref_updates
        )
        version = self.update_from_instrument(
            "context_environment", "onboarding", ctx_updates
        )
        version = self.update_from_instrument(
            "prior_knowledge", "onboarding", prior_updates
        )
        if srl_updates:
            version = self.update_from_instrument(
                "self_regulation", "onboarding", srl_updates
            )

        return version

    # ------------------------------------------------------------------
    # Properties for quick access
    # ------------------------------------------------------------------

    @property
    def confidence_summary(self) -> dict[str, float]:
        """Return confidence for all dimensions."""
        return {
            name: round(dim.confidence, 4)
            for name, dim in self.dimensions.items()
        }

    @property
    def provenance_summary(self) -> dict[str, list[str]]:
        """Return provenance event IDs for all dimensions."""
        return {
            name: list(dim.provenance)
            for name, dim in self.dimensions.items()
        }
