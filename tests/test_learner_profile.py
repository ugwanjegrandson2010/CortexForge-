"""Tests for the 10-dimension LearnerProfile system."""
import json
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.instruments import (  # noqa: E402
    REGISTRY, score_task, servable_tasks,
)
from cortexforge.learner_profile import (  # noqa: E402
    DIMENSION_FIELDS, DIMENSION_NAMES, AuditEntry, Dimension,
    LearnerProfile,
)
from cortexforge.profile import (  # noqa: E402
    Profile, StatementError, build_learner_profile, build_profile,
    profile_to_learner_profile,
)
from cortexforge.onboarding import LearningContract, Onboarding  # noqa: E402
from cortexforge.profile import CLINICAL_PATTERNS  # noqa: E402


class TestDimensionStructure(unittest.TestCase):
    """The 10 dimensions from the Mentat specification."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_all_10_dimensions_present(self):
        expected = {
            "knowledge_state", "cognitive_capacities", "prior_knowledge",
            "motivation_profile", "affect_wellbeing", "goals_values",
            "self_regulation", "context_environment", "preferences",
            "interaction_history",
        }
        self.assertEqual(set(self.lp.dimensions.keys()), expected)

    def test_dimension_names_constant(self):
        self.assertEqual(len(DIMENSION_NAMES), 10)
        self.assertIn("knowledge_state", DIMENSION_NAMES)
        self.assertIn("cognitive_capacities", DIMENSION_NAMES)
        self.assertIn("prior_knowledge", DIMENSION_NAMES)
        self.assertIn("motivation_profile", DIMENSION_NAMES)
        self.assertIn("affect_wellbeing", DIMENSION_NAMES)
        self.assertIn("goals_values", DIMENSION_NAMES)
        self.assertIn("self_regulation", DIMENSION_NAMES)
        self.assertIn("context_environment", DIMENSION_NAMES)
        self.assertIn("preferences", DIMENSION_NAMES)
        self.assertIn("interaction_history", DIMENSION_NAMES)

    def test_initial_confidence_is_zero(self):
        for name in DIMENSION_NAMES:
            self.assertEqual(self.lp.dimensions[name].confidence, 0.0)

    def test_initial_provenance_is_empty(self):
        for name in DIMENSION_NAMES:
            self.assertEqual(self.lp.dimensions[name].provenance, [])

    def test_initial_version_is_one(self):
        self.assertEqual(self.lp.version, 1)

    def test_dimension_fields_populated(self):
        """Each dimension should have its default fields from DIMENSION_FIELDS."""
        for name in DIMENSION_NAMES:
            dim = self.lp.dimensions[name]
            expected_fields = DIMENSION_FIELDS.get(name, {})
            for field in expected_fields:
                self.assertIn(field, dim.data,
                              f"{name} missing field {field}")


class TestUpdateMethods(unittest.TestCase):
    """Updates from practice, instruments, and overrides."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_update_from_practice(self):
        v = self.lp.update_from_practice(
            "knowledge_state", "evt1",
            {"skills_tracked": 5},
        )
        self.assertGreater(v, 1)
        self.assertEqual(self.lp.dimensions["knowledge_state"].data["skills_tracked"], 5)
        self.assertIn("evt1", self.lp.dimensions["knowledge_state"].provenance)

    def test_update_from_instrument(self):
        v = self.lp.update_from_instrument(
            "cognitive_capacities", "flanker:run1",
            {"interference_cost_ms": 150.0},
        )
        self.assertGreater(v, 1)
        dim = self.lp.dimensions["cognitive_capacities"]
        self.assertEqual(dim.data["interference_cost_ms"], 150.0)
        self.assertIn("flanker:run1", dim.provenance)
        # Instruments get higher initial confidence
        self.assertGreaterEqual(dim.confidence, 0.6)

    def test_update_from_override(self):
        v = self.lp.update_from_override(
            "context_environment",
            {"session_minutes": 45, "best_time": "evening"},
            reason="I prefer longer evening sessions",
        )
        self.assertGreater(v, 1)
        dim = self.lp.dimensions["context_environment"]
        self.assertEqual(dim.data["session_minutes"], 45)
        self.assertEqual(dim.data["best_time"], "evening")

    def test_practice_builds_confidence_gradually(self):
        """Practice events build confidence gradually, not instantly."""
        dim = self.lp.dimensions["knowledge_state"]
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        c1 = dim.confidence
        self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 2})
        c2 = dim.confidence
        self.assertGreater(c2, c1)
        self.assertLess(c2, 0.9)  # Still not maxed out

    def test_instrument_confidence_higher_than_single_practice(self):
        """An instrument result carries more confidence than one practice event."""
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.lp.update_from_instrument(
            "cognitive_capacities", "nback:run1", {"wm_proxy": 1.5}
        )
        self.assertGreater(
            self.lp.dimensions["cognitive_capacities"].confidence,
            self.lp.dimensions["knowledge_state"].confidence,
        )

    def test_override_confidence_high_but_self_reported(self):
        """Overrides get high confidence but are noted as self-reported."""
        self.lp.update_from_override(
            "motivation_profile", {"intrinsic_motivation": 0.8}
        )
        dim = self.lp.dimensions["motivation_profile"]
        self.assertGreaterEqual(dim.confidence, 0.8)

    def test_unknown_dimension_rejected(self):
        with self.assertRaises(KeyError):
            self.lp.update_from_practice("nonexistent", "e1", {"x": 1})

    def test_update_dimension_batch(self):
        """Batch update applies multiple fields."""
        v = self.lp.update_dimension(
            "context_environment",
            {"session_minutes": 30, "days_per_week": 5, "best_time": "morning"},
            "practice", "evt1",
        )
        dim = self.lp.dimensions["context_environment"]
        self.assertEqual(dim.data["session_minutes"], 30)
        self.assertEqual(dim.data["days_per_week"], 5)
        self.assertEqual(dim.data["best_time"], "morning")

    def test_provenance_accumulates(self):
        """Multiple events accumulate in provenance."""
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 2})
        self.lp.update_from_instrument("knowledge_state", "e3", {"skills_tracked": 3})
        prov = self.lp.dimensions["knowledge_state"].provenance
        self.assertIn("e1", prov)
        self.assertIn("e2", prov)
        self.assertIn("e3", prov)


class TestVersioning(unittest.TestCase):
    """Version increments on every update."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_version_starts_at_one(self):
        self.assertEqual(self.lp.version, 1)

    def test_version_increments_on_practice(self):
        v1 = self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.assertEqual(v1, 2)
        v2 = self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 2})
        self.assertEqual(v2, 3)

    def test_version_increments_on_instrument(self):
        v = self.lp.update_from_instrument(
            "cognitive_capacities", "e1", {"wm_proxy": 1.0}
        )
        self.assertEqual(v, 2)

    def test_version_increments_on_override(self):
        v = self.lp.update_from_override("preferences", {"format": ["text"]})
        self.assertEqual(v, 2)

    def test_version_increments_per_field_in_batch(self):
        """Each field in a batch update increments the version."""
        v = self.lp.update_dimension(
            "context_environment",
            {"session_minutes": 30, "days_per_week": 5, "best_time": "morning"},
            "practice", "evt1",
        )
        # 3 fields -> version goes from 1 to 4
        self.assertEqual(v, 4)


class TestAuditTrail(unittest.TestCase):
    """Every change is auditable."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_audit_entry_created(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 5})
        self.assertEqual(len(self.lp.audit_log), 1)
        entry = self.lp.audit_log[0]
        self.assertEqual(entry.dimension, "knowledge_state")
        self.assertEqual(entry.field, "skills_tracked")
        self.assertEqual(entry.source, "practice")
        self.assertIn("e1", entry.provenance)

    def test_audit_entry_has_old_and_new_value(self):
        self.lp.update_from_instrument(
            "cognitive_capacities", "e1", {"wm_proxy": 1.5}
        )
        entry = self.lp.audit_log[0]
        self.assertIsNone(entry.old_value)
        self.assertEqual(entry.new_value, 1.5)

    def test_audit_captures_previous_value(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 5})
        self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 10})
        entry = self.lp.audit_log[1]
        self.assertEqual(entry.old_value, 5)
        self.assertEqual(entry.new_value, 10)

    def test_audit_entry_has_version(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 5})
        self.assertEqual(self.lp.audit_log[0].version, 1)
        self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 10})
        self.assertEqual(self.lp.audit_log[1].version, 2)

    def test_audit_entry_has_timestamp(self):
        before = time.time()
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 5})
        after = time.time()
        ts = self.lp.audit_log[0].timestamp
        self.assertGreaterEqual(ts, before)
        self.assertLessEqual(ts, after)

    def test_audit_not_dimension_specific(self):
        """Audit captures the full old/new value, not just the changed field."""
        self.lp.update_from_practice(
            "knowledge_state", "e1",
            {"mastery": {"skill1": {"p_known": 0.5}}},
        )
        entry = self.lp.audit_log[0]
        self.assertIn("skill1", str(entry.new_value))


class TestChallenge(unittest.TestCase):
    """Learners can contest profile estimates."""

    def setUp(self):
        self.lp = LearnerProfile("L1")
        # Build up some evidence first
        for i in range(5):
            self.lp.update_from_practice(
                "knowledge_state", f"e{i}",
                {"skills_tracked": i + 1},
            )

    def test_challenge_reduces_confidence(self):
        dim = self.lp.dimensions["knowledge_state"]
        before_conf = dim.confidence
        result = self.lp.challenge("knowledge_state", "I think this is wrong")
        self.assertLess(dim.confidence, before_conf)
        self.assertEqual(result["status"], "disputed")

    def test_challenge_does_not_remove_data(self):
        """Challenging a field does not destroy the underlying evidence."""
        dim = self.lp.dimensions["knowledge_state"]
        before_data = dict(dim.data)
        self.lp.challenge("knowledge_state", "I disagree")
        self.assertEqual(dim.data, before_data)

    def test_challenge_recorded(self):
        result = self.lp.challenge("knowledge_state", "I disagree")
        self.assertIn("knowledge_state", self.lp._challenges)
        self.assertEqual(len(self.lp._challenges["knowledge_state"]), 1)
        self.assertEqual(
            self.lp._challenges["knowledge_state"][0]["claim"],
            "I disagree",
        )

    def test_challenge_audited(self):
        n_before = len(self.lp.audit_log)
        self.lp.challenge("knowledge_state", "I disagree")
        self.assertGreater(len(self.lp.audit_log), n_before)
        entry = self.lp.audit_log[-1]
        self.assertIn("challenge", entry.note.lower())

    def test_challenge_sub_field(self):
        """Can challenge a specific sub-field."""
        self.lp.update_from_instrument(
            "cognitive_capacities", "nback:1", {"wm_proxy": 1.5}
        )
        result = self.lp.challenge(
            "cognitive_capacities.wm_proxy", "That test was noisy"
        )
        self.assertEqual(result["sub_field"], "wm_proxy")

    def test_challenge_unknown_dimension_rejected(self):
        with self.assertRaises(KeyError):
            self.lp.challenge("nonexistent", "nope")

    def test_multiple_challenges_accumulate(self):
        self.lp.challenge("knowledge_state", "first challenge")
        self.lp.challenge("knowledge_state", "second challenge")
        self.assertEqual(len(self.lp._challenges["knowledge_state"]), 2)


class TestProvenance(unittest.TestCase):
    """Provenance returns the events behind an estimate."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_provenance_empty_initially(self):
        prov = self.lp.provenance("knowledge_state")
        self.assertEqual(prov, [])

    def test_provenance_returns_event_ids(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 2})
        prov = self.lp.provenance("knowledge_state")
        self.assertIn("e1", prov)
        self.assertIn("e2", prov)

    def test_provenance_distinguishes_dimensions(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.lp.update_from_instrument("cognitive_capacities", "e2", {"wm_proxy": 1.0})
        ks_prov = self.lp.provenance("knowledge_state")
        cc_prov = self.lp.provenance("cognitive_capacities")
        self.assertIn("e1", ks_prov)
        self.assertNotIn("e2", ks_prov)
        self.assertIn("e2", cc_prov)
        self.assertNotIn("e1", cc_prov)

    def test_provenance_sub_field(self):
        self.lp.update_from_instrument(
            "cognitive_capacities", "nback:1", {"wm_proxy": 1.5}
        )
        prov = self.lp.provenance("cognitive_capacities.wm_proxy")
        self.assertIn("nback:1", prov)

    def test_provenance_unknown_dimension_rejected(self):
        with self.assertRaises(KeyError):
            self.lp.provenance("nonexistent")


class TestToDict(unittest.TestCase):
    """JSON-serializable output."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_to_dict_returns_dict(self):
        d = self.lp.to_dict()
        self.assertIsInstance(d, dict)

    def test_to_dict_has_learner_id(self):
        d = self.lp.to_dict()
        self.assertEqual(d["learner_id"], "L1")

    def test_to_dict_has_version(self):
        d = self.lp.to_dict()
        self.assertEqual(d["version"], 1)

    def test_to_dict_has_all_dimensions(self):
        d = self.lp.to_dict()
        self.assertIn("dimensions", d)
        for name in DIMENSION_NAMES:
            self.assertIn(name, d["dimensions"])

    def test_to_dict_dimension_has_confidence_and_provenance(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        d = self.lp.to_dict()
        ks = d["dimensions"]["knowledge_state"]
        self.assertIn("confidence", ks)
        self.assertIn("provenance", ks)
        self.assertIn("e1", ks["provenance"])

    def test_to_dict_has_audit_log(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        d = self.lp.to_dict()
        self.assertIn("audit_log", d)
        self.assertEqual(len(d["audit_log"]), 1)

    def test_to_dict_json_serializable(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.lp.update_from_instrument(
            "cognitive_capacities", "e2", {"wm_proxy": 1.5}
        )
        self.lp.challenge("knowledge_state", "I disagree")
        json_str = json.dumps(self.lp.to_dict())
        self.assertIsInstance(json_str, str)

    def test_to_dict_challenges_included(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        self.lp.challenge("knowledge_state", "I disagree")
        d = self.lp.to_dict()
        self.assertIn("challenges", d)
        self.assertIn("knowledge_state", d["challenges"])

    def test_audit_entry_in_to_dict(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 5})
        d = self.lp.to_dict()
        entry = d["audit_log"][0]
        self.assertIn("version", entry)
        self.assertIn("dimension", entry)
        self.assertIn("field", entry)
        self.assertIn("old_value", entry)
        self.assertIn("new_value", entry)
        self.assertIn("source", entry)
        self.assertIn("provenance", entry)


class TestRecordAttempt(unittest.TestCase):
    """Convenience method for recording practice attempts."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_record_attempt_updates_knowledge_state(self):
        self.lp.record_attempt("skill1", True, "attempt:1")
        dim = self.lp.dimensions["knowledge_state"]
        self.assertIn("skill1", dim.data["mastery"])
        self.assertEqual(dim.data["mastery"]["skill1"]["opportunities"], 1)
        self.assertEqual(dim.data["mastery"]["skill1"]["correct"], 1)

    def test_record_attempt_updates_interaction_history(self):
        self.lp.record_attempt("skill1", True, "attempt:1")
        ih = self.lp.dimensions["interaction_history"]
        self.assertEqual(ih.data["total_attempts"], 1)

    def test_multiple_attempts_accumulate(self):
        for i in range(5):
            self.lp.record_attempt("skill1", i < 3, f"attempt:{i}")
        dim = self.lp.dimensions["knowledge_state"]
        self.assertEqual(dim.data["mastery"]["skill1"]["opportunities"], 5)
        self.assertEqual(dim.data["mastery"]["skill1"]["correct"], 3)

    def test_correct_attempt_increases_mastery(self):
        self.lp.record_attempt("skill1", True, "a1")
        p1 = self.lp.dimensions["knowledge_state"].data["mastery"]["skill1"]["p_known"]
        self.lp.record_attempt("skill1", True, "a2")
        p2 = self.lp.dimensions["knowledge_state"].data["mastery"]["skill1"]["p_known"]
        self.assertGreater(p2, p1)

    def test_incorrect_attempt_decreases_mastery(self):
        # First build up mastery
        for _ in range(5):
            self.lp.record_attempt("skill1", True, "a")
        p1 = self.lp.dimensions["knowledge_state"].data["mastery"]["skill1"]["p_known"]
        self.lp.record_attempt("skill1", False, "a_bad")
        p2 = self.lp.dimensions["knowledge_state"].data["mastery"]["skill1"]["p_known"]
        self.assertLess(p2, p1)


class TestRecordInstrumentScore(unittest.TestCase):
    """Convenience method for recording instrument results."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_record_flanker(self):
        trials = (
            [{"congruent": True, "correct": True, "rt_ms": 500}] * 10
            + [{"congruent": False, "correct": True, "rt_ms": 700}] * 10
        )
        scores = score_task("flanker", trials)
        self.lp.record_instrument_score(
            "cognitive_capacities", "flanker:1",
            {"interference_cost_ms": scores["interference_cost_ms"]},
        )
        dim = self.lp.dimensions["cognitive_capacities"]
        self.assertEqual(dim.data["interference_cost_ms"], 200.0)
        self.assertIn("flanker:1", dim.provenance)

    def test_record_nback(self):
        trials = (
            [{"n": 3, "hit": True}] * 8
            + [{"n": 3, "miss": True}] * 2
            + [{"n": 3, "false_alarm": True}] * 2
            + [{"n": 3, "correct_rejection": True}] * 8
        )
        scores = score_task("dual_nback", trials)
        self.lp.record_instrument_score(
            "cognitive_capacities", "nback:1",
            {"wm_proxy": scores["d_prime"]},
        )
        dim = self.lp.dimensions["cognitive_capacities"]
        self.assertIsNotNone(dim.data["wm_proxy"])


class TestRecordSession(unittest.TestCase):
    """Convenience method for recording completed sessions."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_record_session(self):
        self.lp.record_session("session:1", time.time(), 20, 0.85)
        ih = self.lp.dimensions["interaction_history"]
        self.assertEqual(ih.data["total_sessions"], 1)
        self.assertIsNotNone(ih.data["last_seen"])
        self.assertIsNotNone(ih.data["first_seen"])

    def test_session_log_appended(self):
        self.lp.record_session("s1", time.time(), 20, 0.85)
        self.lp.record_session("s2", time.time() + 3600, 15, 0.90)
        ih = self.lp.dimensions["interaction_history"]
        self.assertEqual(len(ih.data["session_log"]), 2)

    def test_session_log_capped(self):
        """Session log keeps only the last 100 entries."""
        for i in range(110):
            self.lp.record_session(f"s{i}", time.time() + i, 10, 0.8)
        ih = self.lp.dimensions["interaction_history"]
        self.assertEqual(len(ih.data["session_log"]), 100)


class TestApplyOnboarding(unittest.TestCase):
    """Bridge from onboarding LearningContract to LearnerProfile."""

    def _make_contract(self):
        c = LearningContract(learner_id="L1")
        c.goal_type = "exam_with_deadline"
        c.domain = "Statistics and probability"
        c.domain_shape = "procedural_numeric"
        c.session_minutes = 25
        c.days_per_week = 5
        c.best_time = "morning"
        c.target_success_rate = 0.85
        c.difficulty_setting = "evidence_band"
        c.fog_baseline = 1.5
        return c

    def test_apply_onboarding_populates_dimensions(self):
        lp = LearnerProfile("L1")
        c = self._make_contract()
        lp.apply_onboarding(c.to_dict())

        # Preferences should be populated
        pref = lp.dimensions["preferences"]
        self.assertEqual(pref.data["session_minutes"], 25)
        self.assertEqual(pref.data["days_per_week"], 5)
        self.assertEqual(pref.data["best_time"], "morning")

        # Context should be populated
        ctx = lp.dimensions["context_environment"]
        self.assertEqual(ctx.data["session_minutes"], 25)
        self.assertEqual(ctx.data["days_per_week"], 5)

        # Prior knowledge should be populated
        prior = lp.dimensions["prior_knowledge"]
        self.assertEqual(prior.data["curriculum"], "Statistics and probability")
        self.assertEqual(prior.data["domain_experience"], "procedural_numeric")

    def test_apply_onboarding_creates_provenance(self):
        lp = LearnerProfile("L1")
        c = self._make_contract()
        lp.apply_onboarding(c.to_dict())
        for name in ("preferences", "context_environment", "prior_knowledge"):
            self.assertIn("onboarding", lp.dimensions[name].provenance)

    def test_apply_onboarding_increments_version(self):
        lp = LearnerProfile("L1")
        v_before = lp.version
        c = self._make_contract()
        lp.apply_onboarding(c.to_dict())
        self.assertGreater(lp.version, v_before)


class TestBridgeFunctions(unittest.TestCase):
    """build_learner_profile and profile_to_learner_profile."""

    def _scores(self):
        return {
            "flanker": score_task(
                "flanker",
                [{"congruent": True, "correct": True, "rt_ms": 500}] * 10
                + [{"congruent": False, "correct": True, "rt_ms": 700}] * 10,
            ),
            "public_goods": score_task(
                "public_goods",
                [{"round": i, "contribution": 8, "others_mean": 7}
                 for i in range(10)],
            ),
        }

    def test_build_learner_profile(self):
        lp = build_learner_profile("L1", self._scores())
        self.assertIsInstance(lp, LearnerProfile)
        self.assertEqual(lp.learner_id, "L1")
        # Should have populated cognitive_capacities from flanker
        self.assertGreater(
            lp.dimensions["cognitive_capacities"].confidence, 0.0
        )

    def test_build_learner_profile_serializable(self):
        lp = build_learner_profile("L1", self._scores())
        json.dumps(lp.to_dict())

    def test_profile_to_learner_profile(self):
        p = build_profile("L1", self._scores())
        lp = profile_to_learner_profile(p)
        self.assertIsInstance(lp, LearnerProfile)
        self.assertEqual(lp.learner_id, "L1")
        # Should have mapped flanker observation to cognitive_capacities
        self.assertGreater(
            lp.dimensions["cognitive_capacities"].confidence, 0.0
        )

    def test_profile_to_learner_profile_serializable(self):
        p = build_profile("L1", self._scores())
        lp = profile_to_learner_profile(p)
        json.dumps(lp.to_dict())

    def test_build_learner_profile_clinical_task_rejected(self):
        with self.assertRaises(StatementError):
            build_learner_profile("L1", {"asrs": {"n": 20}})

    def test_build_learner_profile_with_metrics(self):
        lm = {
            "calibration": {"bias": 0.2, "brier": 0.15, "n": 50},
            "mean_retrievability": 0.85,
        }
        lp = build_learner_profile("L1", self._scores(), lm)
        # Should have updated self_regulation from calibration
        self.assertGreater(
            lp.dimensions["self_regulation"].confidence, 0.0
        )


class TestDescribe(unittest.TestCase):
    """Plain-language descriptions are honest and non-clinical."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_describe_low_confidence(self):
        desc = self.lp.describe("knowledge_state.mastery")
        self.assertIn("Insufficient evidence", desc)

    def test_describe_with_evidence(self):
        for i in range(5):
            self.lp.update_from_practice(
                "knowledge_state", f"e{i}",
                {"skills_tracked": i + 1},
            )
        desc = self.lp.describe("knowledge_state.skills_tracked")
        self.assertIn("5", desc)  # The value
        self.assertIn("Confidence", desc)
        self.assertIn("challenge", desc.lower())

    def test_describe_no_clinical_language(self):
        for i in range(5):
            self.lp.update_from_practice(
                "affect_wellbeing", f"e{i}",
                {"test_anxiety": 0.6},
            )
        desc = self.lp.describe("affect_wellbeing.test_anxiety")
        low = desc.lower()
        for pat in CLINICAL_PATTERNS:
            self.assertNotIn(pat, low)

    def test_describe_no_praise(self):
        for i in range(5):
            self.lp.update_from_practice(
                "knowledge_state", f"e{i}",
                {"skills_tracked": i + 1},
            )
        desc = self.lp.describe("knowledge_state.skills_tracked")
        low = desc.lower()
        for pat in ("great job", "well done", "awesome", "proud", "amazing"):
            self.assertNotIn(pat, low)


class TestConfidenceSummary(unittest.TestCase):
    """Quick access to confidence across dimensions."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_summary_covers_all_dimensions(self):
        summary = self.lp.confidence_summary
        for name in DIMENSION_NAMES:
            self.assertIn(name, summary)

    def test_summary_updates(self):
        self.lp.update_from_instrument(
            "cognitive_capacities", "e1", {"wm_proxy": 1.5}
        )
        summary = self.lp.confidence_summary
        self.assertGreater(summary["cognitive_capacities"], 0.0)


class TestProvenanceSummary(unittest.TestCase):
    """Quick access to provenance across dimensions."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_summary_covers_all_dimensions(self):
        summary = self.lp.provenance_summary
        for name in DIMENSION_NAMES:
            self.assertIn(name, summary)

    def test_summary_shows_events(self):
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        summary = self.lp.provenance_summary
        self.assertIn("e1", summary["knowledge_state"])


class TestIntegrationWithExistingCode(unittest.TestCase):
    """The new system works alongside the existing profile.py code."""

    def test_profile_class_still_works(self):
        """The existing Profile class is unchanged."""
        scores = {
            "flanker": score_task(
                "flanker",
                [{"congruent": True, "correct": True, "rt_ms": 500}] * 10
                + [{"congruent": False, "correct": True, "rt_ms": 700}] * 10,
            ),
        }
        p = build_profile("L1", scores)
        self.assertIsInstance(p, Profile)
        self.assertGreater(len(p.observations), 0)

    def test_learner_profile_coexists_with_profile(self):
        """Both can be created from the same data."""
        scores = {
            "flanker": score_task(
                "flanker",
                [{"congruent": True, "correct": True, "rt_ms": 500}] * 10
                + [{"congruent": False, "correct": True, "rt_ms": 700}] * 10,
            ),
        }
        p = build_profile("L1", scores)
        lp = build_learner_profile("L1", scores)
        self.assertIsInstance(p, Profile)
        self.assertIsInstance(lp, LearnerProfile)

    def test_onboarding_to_learner_profile(self):
        """Full pipeline: onboarding -> contract -> learner profile."""
        ob = Onboarding("L1")
        # Run all probes
        while True:
            probe = ob.next_probe()
            if probe is None:
                break
            if probe.probe_id == "source":
                ob.record(probe.probe_id, "my notes on statistics")
            elif probe.probe_id == "goal":
                ob.record(probe.probe_id,
                          "Pass a specific exam or certification")
            elif probe.probe_id == "domain":
                ob.record(probe.probe_id, "Statistics and probability")
            elif probe.probe_id == "constraints":
                ob.record(probe.probe_id, {
                    "session_minutes": 25, "days_per_week": 5,
                    "best_time": "morning",
                })
            elif probe.probe_id == "difficulty_preference":
                ob.record(probe.probe_id, "85% — the evidence-based band")
            elif probe.probe_id == "fog_baseline":
                ob.record(probe.probe_id, {"a": 2, "b": 2, "c": 1, "d": 2, "e": 3})
            else:
                ob.record(probe.probe_id, {"ok": True})

        contract = ob.build_contract()
        lp = LearnerProfile("L1")
        lp.apply_onboarding(contract.to_dict())

        # Verify key dimensions were populated
        self.assertEqual(
            lp.dimensions["preferences"].data["session_minutes"], 25
        )
        self.assertEqual(
            lp.dimensions["preferences"].data["days_per_week"], 5
        )
        self.assertEqual(
            lp.dimensions["prior_knowledge"].data["curriculum"],
            "Statistics and probability",
        )

    def test_full_pipeline_serializable(self):
        """The entire pipeline produces JSON-serializable output."""
        ob = Onboarding("L1")
        while True:
            probe = ob.next_probe()
            if probe is None:
                break
            if probe.probe_id == "source":
                ob.record(probe.probe_id, "statistics notes")
            elif probe.probe_id == "goal":
                ob.record(probe.probe_id, "Pass an exam")
            elif probe.probe_id == "domain":
                ob.record(probe.probe_id, "Statistics")
            elif probe.probe_id == "constraints":
                ob.record(probe.probe_id, {
                    "session_minutes": 30, "days_per_week": 4,
                    "best_time": "evening",
                })
            elif probe.probe_id == "difficulty_preference":
                ob.record(probe.probe_id, "85%")
            elif probe.probe_id == "fog_baseline":
                ob.record(probe.probe_id, {"a": 1, "b": 2})
            else:
                ob.record(probe.probe_id, {"ok": True})

        contract = ob.build_contract()
        lp = LearnerProfile("L1")
        lp.apply_onboarding(contract.to_dict())

        # Add some practice
        for i in range(10):
            lp.record_attempt("stats_bayes", i < 7, f"attempt:{i}")

        # Add an instrument
        lp.record_instrument_score(
            "cognitive_capacities", "flanker:1",
            {"interference_cost_ms": 120.0},
        )

        # Challenge something
        lp.challenge("knowledge_state", "I already know this material")

        # Serialize
        json_str = json.dumps(lp.to_dict())
        self.assertIsInstance(json_str, str)
        self.assertGreater(len(json_str), 100)


class TestSecurityConstraints(unittest.TestCase):
    """The learner profile maintains all existing security constraints."""

    def setUp(self):
        self.lp = LearnerProfile("L1")

    def test_no_clinical_vocabulary_in_describe(self):
        """No clinical language in generated descriptions."""
        for i in range(5):
            self.lp.update_from_practice(
                "affect_wellbeing", f"e{i}",
                {"test_anxiety": 0.5},
            )
        desc = self.lp.describe("affect_wellbeing.test_anxiety")
        low = desc.lower()
        for pat in CLINICAL_PATTERNS:
            self.assertNotIn(pat, low,
                             f"clinical pattern {pat!r} in description")

    def test_no_praise_in_describe(self):
        """No pampering phrases in descriptions."""
        for i in range(5):
            self.lp.update_from_practice(
                "knowledge_state", f"e{i}",
                {"skills_tracked": i + 1},
            )
        desc = self.lp.describe("knowledge_state.skills_tracked")
        low = desc.lower()
        pampering = ("great job", "well done", "awesome", "proud",
                     "amazing", "keep it up", "good effort")
        for pat in pampering:
            self.assertNotIn(pat, low)

    def test_no_unfalsifiable_claims(self):
        """Descriptions are falsifiable and uncertainty-bearing."""
        for i in range(5):
            self.lp.update_from_practice(
                "cognitive_capacities", f"e{i}",
                {"wm_proxy": 1.5 + i * 0.1},
            )
        desc = self.lp.describe("cognitive_capacities.wm_proxy")
        # Must contain uncertainty marker
        self.assertIn("Confidence", desc)
        # Must be open to challenge
        self.assertIn("challenge", desc.lower())

    def test_challenge_preserves_evidence(self):
        """Challenging does not destroy evidence — it marks it as disputed."""
        for i in range(5):
            self.lp.update_from_practice(
                "knowledge_state", f"e{i}",
                {"skills_tracked": i + 1},
            )
        before_data = dict(self.lp.dimensions["knowledge_state"].data)
        before_prov = list(self.lp.dimensions["knowledge_state"].provenance)

        self.lp.challenge("knowledge_state", "I disagree with this")

        after_data = self.lp.dimensions["knowledge_state"].data
        after_prov = self.lp.dimensions["knowledge_state"].provenance

        self.assertEqual(before_data, after_data)
        self.assertEqual(before_prov, after_prov)

    def test_audit_trail_append_only(self):
        """Audit entries are recorded at update time and reflect that moment."""
        self.lp.update_from_practice("knowledge_state", "e1", {"skills_tracked": 1})
        entry = self.lp.audit_log[0]
        # The entry captures the value at the time of the update
        self.assertEqual(entry.new_value, 1)
        self.assertEqual(entry.source, "practice")
        self.assertIn("e1", entry.provenance)
        # A subsequent update creates a new entry, doesn't modify the old one
        self.lp.update_from_practice("knowledge_state", "e2", {"skills_tracked": 5})
        self.assertEqual(len(self.lp.audit_log), 2)
        self.assertEqual(self.lp.audit_log[0].new_value, 1)
        self.assertEqual(self.lp.audit_log[1].new_value, 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
