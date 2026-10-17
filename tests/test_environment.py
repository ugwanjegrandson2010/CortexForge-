"""Tests for the environment audit and prescription system."""
import sys
import time
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.environment import (  # noqa: E402
    EVIDENCE_LIBRARY,
    EVIDENCE_MODERATE,
    EVIDENCE_STRONG,
    EVIDENCE_WEAK,
    AdherenceRecord,
    AdherenceTracker,
    DigitalEnvironment,
    EnvironmentAudit,
    EvidenceEntry,
    MaterialsEnvironment,
    PhysicalEnvironment,
    Prescription,
    PrescriptionGenerator,
    SocialEnvironment,
    TemporalEnvironment,
    evidence_manifest,
    get_evidence,
    should_reaudit,
)


def _make_audit(**overrides) -> EnvironmentAudit:
    """Build a fully-populated audit with sensible defaults, allowing overrides."""
    audit = EnvironmentAudit(learner_id="L1")
    audit.physical = PhysicalEnvironment(
        lighting="dim",
        noise_sources=["speech", "music_with_lyrics"],
        temperature_c=26.0,
        green_view=False,
        has_indoor_plants=False,
        ergonomic_setup="poor",
        phone_location="on_desk",
        desk_clutter="heavy",
    )
    audit.digital = DigitalEnvironment(
        notification_load="high",
        blocker_available=False,
        blocker_active=False,
        distraction_sources=["social_media", "news"],
        phone_in_reach=True,
        social_media_apps_installed=True,
        website_blocker_installed=False,
    )
    audit.social = SocialEnvironment(
        study_partners=[],
        household_support="disruptive",
        quiet_hours_feasible=False,
        quiet_hours="",
        social_commitment_device=False,
    )
    audit.temporal = TemporalEnvironment(
        sleep_schedule="irregular",
        typical_bedtime="01:00",
        typical_wake_time="09:00",
        anchors=[],
        deadline_map_visible=False,
        intermediate_checkpoints=False,
        exam_date_known=True,
        exam_date="2026-11-15",
    )
    audit.materials = MaterialsEnvironment(
        textbook_access="partial",
        calculator_available=False,
        stationery_ready=False,
        materials_visible=False,
        digital_notes_organised=False,
    )
    # Apply overrides
    for key, val in overrides.items():
        if hasattr(audit, key):
            setattr(audit, key, val)
    return audit


def _make_clean_audit() -> EnvironmentAudit:
    """Build an audit with no issues — should produce few or no prescriptions."""
    audit = EnvironmentAudit(learner_id="L2")
    audit.physical = PhysicalEnvironment(
        lighting="bright",
        noise_sources=[],
        temperature_c=21.0,
        green_view=True,
        has_indoor_plants=True,
        ergonomic_setup="good",
        phone_location="another_room",
        desk_clutter="minimal",
    )
    audit.digital = DigitalEnvironment(
        notification_load="low",
        blocker_available=True,
        blocker_active=True,
        distraction_sources=[],
        phone_in_reach=False,
        social_media_apps_installed=False,
        website_blocker_installed=True,
    )
    audit.social = SocialEnvironment(
        study_partners=["Alice"],
        household_support="supportive",
        quiet_hours_feasible=True,
        quiet_hours="22:00-07:00",
        social_commitment_device=True,
    )
    audit.temporal = TemporalEnvironment(
        sleep_schedule="consistent",
        typical_bedtime="23:00",
        typical_wake_time="07:00",
        anchors=["morning coffee"],
        deadline_map_visible=True,
        intermediate_checkpoints=True,
        exam_date_known=True,
        exam_date="2026-12-01",
    )
    audit.materials = MaterialsEnvironment(
        textbook_access="full",
        calculator_available=True,
        stationery_ready=True,
        materials_visible=True,
        digital_notes_organised=True,
    )
    return audit


# --------------------------------------------------------------- evidence


class TestEvidenceLibrary(unittest.TestCase):
    def test_all_entries_have_citations(self):
        for key, entry in EVIDENCE_LIBRARY.items():
            self.assertTrue(entry.citation, f"{key} has no citation")
            self.assertTrue(entry.finding, f"{key} has no finding")

    def test_all_entries_have_valid_evidence_grade(self):
        valid = {EVIDENCE_STRONG, EVIDENCE_MODERATE, EVIDENCE_WEAK}
        for key, entry in EVIDENCE_LIBRARY.items():
            self.assertIn(entry.evidence, valid,
                          f"{key} has invalid evidence grade {entry.evidence!r}")

    def test_get_evidence_returns_entry(self):
        ev = get_evidence("phone_in_another_room")
        self.assertIsNotNone(ev)
        self.assertEqual(ev.citation, "Ward et al. 2017")

    def test_get_evidence_returns_none_for_unknown(self):
        self.assertIsNone(get_evidence("nonexistent_key"))

    def test_evidence_manifest_serialises(self):
        manifest = evidence_manifest()
        self.assertIn("phone_in_another_room", manifest)
        self.assertIn("steady_ambient_noise", manifest)
        self.assertIn("movement_breaks", manifest)
        for key, entry in manifest.items():
            self.assertIn("citation", entry)
            self.assertIn("finding", entry)
            self.assertIn("evidence", entry)

    def test_all_prescription_keys_have_evidence(self):
        """Every prescription key used in the generator must have evidence."""
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for p in prescriptions:
            self.assertIn(p.key, EVIDENCE_LIBRARY,
                          f"prescription {p.key} has no evidence entry")

    def test_ward_citation_present(self):
        ev = get_evidence("phone_in_another_room")
        self.assertIn("Ward", ev.citation)
        self.assertIn("2017", ev.citation)

    def test_sorqvist_citation_present(self):
        ev = get_evidence("steady_ambient_noise")
        self.assertIn("Sörqvist", ev.citation)

    def test_kaplan_citation_present(self):
        ev = get_evidence("green_view")
        self.assertIn("Kaplan", ev.citation)

    def test_evidence_entry_to_dict(self):
        ev = EvidenceEntry(
            citation="Test 2020", finding="test finding",
            evidence=EVIDENCE_STRONG)
        d = ev.to_dict()
        self.assertEqual(d["citation"], "Test 2020")
        self.assertEqual(d["evidence"], EVIDENCE_STRONG)


# ------------------------------------------------------------------- audit


class TestEnvironmentAudit(unittest.TestCase):
    def test_audit_to_dict(self):
        audit = _make_audit()
        d = audit.to_dict()
        self.assertEqual(d["learner_id"], "L1")
        self.assertIn("physical", d)
        self.assertIn("digital", d)
        self.assertIn("social", d)
        self.assertIn("temporal", d)
        self.assertIn("materials", d)

    def test_dimension_summary_detects_issues(self):
        audit = _make_audit()
        summary = audit.dimension_summary()
        self.assertGreater(summary["physical"]["count"], 0)
        self.assertGreater(summary["digital"]["count"], 0)
        self.assertGreater(summary["social"]["count"], 0)
        self.assertGreater(summary["temporal"]["count"], 0)
        self.assertGreater(summary["materials"]["count"], 0)

    def test_clean_audit_has_few_issues(self):
        audit = _make_clean_audit()
        summary = audit.dimension_summary()
        # A clean audit should have zero or near-zero issues per dimension
        for dim in ("physical", "digital", "social", "temporal", "materials"):
            self.assertEqual(summary[dim]["count"], 0,
                             f"{dim} should have no issues in a clean audit")

    def test_physical_issues_content(self):
        audit = _make_audit()
        issues = audit._physical_issues()
        self.assertIn("lighting too dim for alert tasks", issues["issues"])
        self.assertIn("phone within reach (on_desk)", issues["issues"])
        self.assertIn("temperature 26.0C too warm for alertness", issues["issues"])

    def test_digital_issues_content(self):
        audit = _make_audit()
        issues = audit._digital_issues()
        self.assertIn("high notification load", issues["issues"])
        self.assertIn("no website blocker available", issues["issues"])

    def test_social_issues_content(self):
        audit = _make_audit()
        issues = audit._social_issues()
        self.assertIn("no study partners", issues["issues"])
        self.assertIn("disruptive household environment", issues["issues"])

    def test_temporal_issues_content(self):
        audit = _make_audit()
        issues = audit._temporal_issues()
        self.assertIn("irregular sleep schedule", issues["issues"])
        self.assertIn("deadline map not visible", issues["issues"])

    def test_materials_issues_content(self):
        audit = _make_audit()
        issues = audit._materials_issues()
        self.assertIn("partial textbook access", issues["issues"])
        self.assertIn("materials not visible from desk", issues["issues"])

    def test_audit_has_created_at(self):
        audit = _make_audit()
        self.assertGreater(audit.created_at, 0)

    def test_physical_environment_to_dict(self):
        p = PhysicalEnvironment(lighting="bright", temperature_c=21.0)
        d = p.to_dict()
        self.assertEqual(d["lighting"], "bright")
        self.assertEqual(d["temperature_c"], 21.0)

    def test_digital_environment_to_dict(self):
        d_env = DigitalEnvironment(notification_load="low", blocker_active=True)
        d = d_env.to_dict()
        self.assertEqual(d["notification_load"], "low")
        self.assertTrue(d["blocker_active"])

    def test_social_environment_to_dict(self):
        s = SocialEnvironment(study_partners=["Alice"], quiet_hours_feasible=True)
        d = s.to_dict()
        self.assertEqual(d["study_partners"], ["Alice"])
        self.assertTrue(d["quiet_hours_feasible"])

    def test_temporal_environment_to_dict(self):
        t = TemporalEnvironment(sleep_schedule="consistent", exam_date="2026-12-01")
        d = t.to_dict()
        self.assertEqual(d["sleep_schedule"], "consistent")
        self.assertEqual(d["exam_date"], "2026-12-01")

    def test_materials_environment_to_dict(self):
        m = MaterialsEnvironment(textbook_access="full", calculator_available=True)
        d = m.to_dict()
        self.assertEqual(d["textbook_access"], "full")
        self.assertTrue(d["calculator_available"])


# ---------------------------------------------------------- prescriptions


class TestPrescriptionGenerator(unittest.TestCase):
    def test_generates_3_to_5_prescriptions(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        self.assertGreaterEqual(len(prescriptions), 3)
        self.assertLessEqual(len(prescriptions), 5)

    def test_prescriptions_are_ranked(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for i, p in enumerate(prescriptions):
            self.assertEqual(p.rank, i + 1)

    def test_prescriptions_sorted_by_impact(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        scores = [p.impact_score for p in prescriptions]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_every_prescription_has_evidence(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for p in prescriptions:
            self.assertTrue(p.evidence_citation,
                            f"prescription {p.key} has no citation")
            self.assertTrue(p.evidence_finding,
                            f"prescription {p.key} has no finding")
            self.assertIn(p.evidence_strength,
                          (EVIDENCE_STRONG, EVIDENCE_MODERATE, EVIDENCE_WEAK))

    def test_every_prescription_has_if_then(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for p in prescriptions:
            self.assertIn("If", p.if_condition,
                          f"prescription {p.key} if_condition lacks 'If'")
            self.assertIn("then", p.then_action,
                          f"prescription {p.key} then_action lacks 'then'")

    def test_every_prescription_has_dimension(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        valid_dims = ("physical", "digital", "social", "temporal", "materials")
        for p in prescriptions:
            self.assertIn(p.dimension, valid_dims,
                          f"prescription {p.key} has invalid dimension {p.dimension}")

    def test_clean_audit_produces_few_prescriptions(self):
        audit = _make_clean_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        # A clean audit should produce at most 1 prescription (movement breaks
        # is always emitted as a universal recommendation)
        self.assertLessEqual(len(prescriptions), 1)

    def test_phone_prescription_when_phone_on_desk(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertIn("phone_in_another_room", keys)

    def test_no_phone_prescription_when_phone_in_another_room(self):
        audit = _make_clean_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertNotIn("phone_in_another_room", keys)

    def test_movement_breaks_always_emitted(self):
        """Movement breaks is a universal recommendation."""
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertIn("movement_breaks", keys)

    def test_notification_block_emitted_when_high_load(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertIn("notification_block", keys)

    def test_no_notification_block_when_low_load(self):
        audit = _make_clean_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertNotIn("notification_block", keys)

    def test_sleep_prescription_when_irregular(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("consistent_sleep", keys)

    def test_no_sleep_prescription_when_consistent(self):
        audit = _make_clean_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertNotIn("consistent_sleep", keys)

    def test_deadline_map_prescription_when_not_visible(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("deadline_map", keys)

    def test_materials_visible_prescription_when_not_visible(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("materials_visible", keys)

    def test_prescription_to_dict(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for p in prescriptions:
            d = p.to_dict()
            self.assertIn("rank", d)
            self.assertIn("key", d)
            self.assertIn("title", d)
            self.assertIn("if_condition", d)
            self.assertIn("then_action", d)
            self.assertIn("evidence_citation", d)
            self.assertIn("impact_score", d)
            self.assertIn("dimension", d)

    def test_impact_score_is_evidence_times_feasibility(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for p in prescriptions:
            strength_map = {EVIDENCE_STRONG: 1.0, EVIDENCE_MODERATE: 0.7,
                            EVIDENCE_WEAK: 0.4}
            expected = round(strength_map[p.evidence_strength] * p.feasibility, 3)
            self.assertAlmostEqual(p.impact_score, expected, places=3)

    def test_lyrics_prescription_when_lyrics_present(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("no_lyrics", keys)

    def test_no_lyrics_prescription_when_no_lyrics(self):
        audit = _make_clean_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertNotIn("no_lyrics", keys)

    def test_green_view_prescription_when_no_green(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("green_view", keys)

    def test_cool_temperature_prescription_when_warm(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("cool_temperature", keys)

    def test_ergonomic_prescription_when_poor(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("ergonomic_setup", keys)

    def test_social_accountability_prescription_when_no_partner(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("social_accountability", keys)

    def test_quiet_hours_prescription_when_not_feasible(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=15)
        keys = [p.key for p in prescriptions]
        self.assertIn("quiet_hours_negotiation", keys)

    def test_max_respected(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=3)
        self.assertEqual(len(prescriptions), 3)

    def test_prescription_keys_are_unique(self):
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        keys = [p.key for p in prescriptions]
        self.assertEqual(len(keys), len(set(keys)),
                         "prescription keys must be unique")


# -------------------------------------------------------------- adherence


class TestAdherenceTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = AdherenceTracker()

    def test_record_and_rate(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-03", False)
        rate = self.tracker.adherence_rate("phone_in_another_room", "L1")
        self.assertAlmostEqual(rate, 0.667, places=2)

    def test_rate_none_when_no_records(self):
        rate = self.tracker.adherence_rate("nonexistent", "L1")
        self.assertIsNone(rate)

    def test_rate_per_learner(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", True)
        self.tracker.record("phone_in_another_room", "L2", "2026-10-01", False)
        rate_l1 = self.tracker.adherence_rate("phone_in_another_room", "L1")
        rate_l2 = self.tracker.adherence_rate("phone_in_another_room", "L2")
        self.assertAlmostEqual(rate_l1, 1.0)
        self.assertAlmostEqual(rate_l2, 0.0)

    def test_adherence_trend(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", False)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-03", True)
        trend = self.tracker.adherence_trend("phone_in_another_room", "L1")
        self.assertEqual(len(trend), 3)
        self.assertEqual(trend[0]["date"], "2026-10-01")
        self.assertEqual(trend[0]["rate"], 1.0)
        self.assertEqual(trend[1]["rate"], 0.0)
        self.assertEqual(trend[2]["rate"], 1.0)

    def test_overall_adherence(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", False)
        self.tracker.record("movement_breaks", "L1", "2026-10-01", True)
        self.tracker.record("movement_breaks", "L1", "2026-10-02", True)
        overall = self.tracker.overall_adherence("L1")
        self.assertAlmostEqual(overall, 0.75)

    def test_overall_adherence_none_when_empty(self):
        self.assertIsNone(self.tracker.overall_adherence("L1"))

    def test_struggling_prescriptions(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", True)
        self.tracker.record("movement_breaks", "L1", "2026-10-01", False)
        self.tracker.record("movement_breaks", "L1", "2026-10-02", False)
        struggling = self.tracker.struggling_prescriptions("L1", threshold=0.5)
        self.assertEqual(len(struggling), 1)
        self.assertEqual(struggling[0]["prescription_key"], "movement_breaks")
        self.assertEqual(struggling[0]["rate"], 0.0)

    def test_struggling_empty_when_all_good(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", True)
        struggling = self.tracker.struggling_prescriptions("L1", threshold=0.5)
        self.assertEqual(struggling, [])

    def test_records_for_learner(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L2", "2026-10-01", False)
        records = self.tracker.records_for_learner("L1")
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].learner_id, "L1")

    def test_summary(self):
        self.tracker.record("phone_in_another_room", "L1", "2026-10-01", True)
        self.tracker.record("phone_in_another_room", "L1", "2026-10-02", False)
        self.tracker.record("movement_breaks", "L1", "2026-10-01", True)
        summary = self.tracker.summary("L1")
        self.assertEqual(summary["n"], 3)
        self.assertAlmostEqual(summary["overall_rate"], 0.667, places=2)
        self.assertIn("phone_in_another_room", summary["prescriptions"])
        self.assertIn("movement_breaks", summary["prescriptions"])

    def test_summary_empty(self):
        summary = self.tracker.summary("L1")
        self.assertEqual(summary["n"], 0)
        self.assertIsNone(summary["overall_rate"])

    def test_adherence_record_to_dict(self):
        rec = AdherenceRecord(
            prescription_key="test", learner_id="L1",
            date="2026-10-01", followed=True, notes="test note")
        d = rec.to_dict()
        self.assertEqual(d["prescription_key"], "test")
        self.assertEqual(d["learner_id"], "L1")
        self.assertEqual(d["date"], "2026-10-01")
        self.assertTrue(d["followed"])
        self.assertEqual(d["notes"], "test note")

    def test_multiple_prescriptions_tracked(self):
        """Track adherence for multiple prescriptions simultaneously."""
        keys = ["phone_in_another_room", "movement_breaks",
                "steady_ambient_noise", "notification_block"]
        for i, key in enumerate(keys):
            self.tracker.record(key, "L1", "2026-10-01", i % 2 == 0)
        summary = self.tracker.summary("L1")
        self.assertEqual(len(summary["prescriptions"]), 4)


# ------------------------------------------------------------- re-audit


class TestReauditScheduler(unittest.TestCase):
    def test_monthly_reaudit_due(self):
        now = time.time()
        last = now - (31 * 86400)  # 31 days ago
        result = should_reaudit(last, now)
        self.assertTrue(result["due"])
        self.assertIn("monthly", result["reason"])

    def test_monthly_reaudit_not_due(self):
        now = time.time()
        last = now - (15 * 86400)  # 15 days ago
        result = should_reaudit(last, now)
        self.assertFalse(result["due"])

    def test_pre_exam_audit_due(self):
        import datetime
        now = datetime.datetime(2026, 10, 17)
        now_ts = now.timestamp()
        last = now_ts - (10 * 86400)  # 10 days ago
        exam = "2026-10-28"  # 11 days away
        result = should_reaudit(last, now_ts, exam_date=exam)
        self.assertTrue(result["due"])
        self.assertIn("exam", result["reason"])

    def test_pre_exam_audit_not_due_far(self):
        import datetime
        now = datetime.datetime(2026, 10, 17)
        now_ts = now.timestamp()
        last = now_ts - (10 * 86400)
        exam = "2026-12-01"  # 45 days away
        result = should_reaudit(last, now_ts, exam_date=exam)
        self.assertFalse(result["due"])

    def test_pre_exam_audit_not_due_past(self):
        import datetime
        now = datetime.datetime(2026, 10, 17)
        now_ts = now.timestamp()
        last = now_ts - (10 * 86400)
        exam = "2026-10-10"  # 7 days ago (past)
        result = should_reaudit(last, now_ts, exam_date=exam)
        # Past exam should not trigger pre-exam audit
        self.assertFalse(result["due"])

    def test_days_since_last_reported(self):
        now = time.time()
        last = now - (20 * 86400)
        result = should_reaudit(last, now)
        self.assertEqual(result["days_since_last"], 20)

    def test_invalid_exam_date_ignored(self):
        now = time.time()
        last = now - (10 * 86400)
        result = should_reaudit(last, now, exam_date="not-a-date")
        self.assertFalse(result["due"])


# --------------------------------------------------------- integration


class TestIntegration(unittest.TestCase):
    def test_full_pipeline(self):
        """Audit -> Prescriptions -> Adherence tracking."""
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()

        # Verify we got prescriptions
        self.assertGreaterEqual(len(prescriptions), 3)

        # Track adherence for each
        tracker = AdherenceTracker()
        for p in prescriptions:
            tracker.record(p.key, "L1", "2026-10-01", True)
            tracker.record(p.key, "L1", "2026-10-02", True)
            tracker.record(p.key, "L1", "2026-10-03", False)

        # Check overall adherence
        overall = tracker.overall_adherence("L1")
        self.assertAlmostEqual(overall, 0.667, places=2)

        # Check per-prescription
        for p in prescriptions:
            rate = tracker.adherence_rate(p.key, "L1")
            self.assertAlmostEqual(rate, 0.667, places=2)

    def test_audit_to_prescriptions_to_dict(self):
        """Full serialisation path."""
        audit = _make_audit()
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate()
        for p in prescriptions:
            d = p.to_dict()
            # Must be JSON-serialisable
            import json
            json.dumps(d)

    def test_evidence_manifest_json_serialisable(self):
        import json
        manifest = evidence_manifest()
        json.dumps(manifest)

    def test_audit_dimension_summary_json_serialisable(self):
        import json
        audit = _make_audit()
        summary = audit.dimension_summary()
        json.dumps(summary)


if __name__ == "__main__":
    unittest.main(verbosity=2)
