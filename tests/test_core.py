"""Core engine tests: scheduler, tracing, question generation, store,
instruments, profile, onboarding, MCP."""

import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from cortexforge.instruments import (  # noqa: E402
    EVIDENCE_MODERATE, EVIDENCE_STRONG, LICENCE_CLINICAL, LICENCE_RESTRICTED,
    REGISTRY, divergence_signal, nih_toolbox_two_vector, penncnb_composite,
    score_task, servable_tasks, task_manifest, validate_registry,
)
from cortexforge.mcp import (  # noqa: E402
    AUTH_API_KEY, AUTH_LOCAL, AUTH_NONE, AUTH_OAUTH, CATALOGUE, CORE_EXCLUSIONS,
    CORE_KEYS, build_mcp_config, core_servers, oauth_servers, onboarding_plan,
    token_status, write_mcp_config,
)
from cortexforge.onboarding import (  # noqa: E402
    PROBES, PROBES_BY_ID, LearningContract, Onboarding,
)
from cortexforge.profile import (  # noqa: E402
    CLINICAL_PATTERNS, MIN_TRIALS_FOR_CLAIM, PAMPERING_PATTERNS,
    UNFALSIFIABLE_PATTERNS, StatementError, build_profile, grade_feedback,
    session_summary, validate_statement,
)
from cortexforge.questiongen import (  # noqa: E402
    ALL_STYLES, LLM_STYLES, NATIVE_GENERATORS, SourceError, generate_from_source,
    interleave, sentences,
)
from cortexforge.scheduler import (  # noqa: E402
    Card, DEFAULT_W, build_queue, fit_parameters, interval_for_retention,
    retention_forecast, retrievability, total_loss,
)
from cortexforge.store import Store  # noqa: E402
from cortexforge.tracing import (  # noqa: E402
    BKTParams, BKTSkill, Item, calibration_stats, select_next_item,
    update_theta_mle,
)

SAMPLE = """Photosynthesis is the process by which green plants convert light
energy into chemical energy stored in glucose. Chlorophyll absorbs light most
strongly in the blue and red parts of the spectrum. The light-dependent
reactions occur in the thylakoid membrane and produce ATP and NADPH. The Calvin
cycle occurs in the stroma and fixes carbon dioxide into a three-carbon sugar.
Because the Calvin cycle depends on ATP from the light reactions, photosynthesis
stops within minutes when light is removed. In contrast, respiration occurs in
the mitochondria and releases energy rather than storing it. The overall yield
is approximately 6 molecules of oxygen per molecule of glucose."""


# --------------------------------------------------------------- scheduler

class TestFSRS(unittest.TestCase):
    def test_retrievability_at_stability_is_ninety_percent(self):
        """By construction R(t=S) must equal the 0.9 target."""
        for s in (1.0, 5.0, 50.0, 500.0):
            self.assertAlmostEqual(retrievability(s, s), 0.9, places=6)

    def test_retrievability_decays(self):
        self.assertGreater(retrievability(1, 10), retrievability(10, 10))
        self.assertGreater(retrievability(10, 10), retrievability(100, 10))

    def test_retrievability_zero_stability(self):
        self.assertEqual(retrievability(5, 0), 0.0)

    def test_interval_inverts_retrievability(self):
        for s in (2.0, 20.0, 200.0):
            iv = interval_for_retention(s, 0.9)
            self.assertAlmostEqual(retrievability(iv, s), 0.9, places=1)

    def test_higher_retention_shorter_interval(self):
        self.assertLess(interval_for_retention(100, 0.97),
                        interval_for_retention(100, 0.85))

    def test_new_card_initialises(self):
        c = Card("q1")
        self.assertEqual(c.state, "new")
        out = c.review(3, 0.0)
        self.assertGreater(out["stability"], 0)
        self.assertEqual(c.reps, 1)

    def test_good_grades_increase_stability(self):
        c = Card("q1")
        c.review(3, 0.0)
        s1 = c.stability
        c.review(3, c.due_day)
        self.assertGreater(c.stability, s1)

    def test_easy_beats_good(self):
        a, b = Card("a"), Card("b")
        a.review(3, 0.0); a.review(3, a.due_day)
        b.review(4, 0.0); b.review(4, b.due_day)
        self.assertGreater(b.stability, a.stability)

    def test_lapse_reduces_stability(self):
        c = Card("q1")
        for _ in range(3):
            c.review(3, c.due_day)
        before = c.stability
        c.review(1, c.due_day)
        self.assertLess(c.stability, before)
        self.assertEqual(c.lapses, 1)
        self.assertEqual(c.state, "relearning")

    def test_difficulty_bounded(self):
        c = Card("q1")
        for i in range(60):
            c.review(1, c.due_day)
        self.assertGreaterEqual(c.difficulty, 1.0)
        self.assertLessEqual(c.difficulty, 10.0)

    def test_stability_never_zero(self):
        c = Card("q1")
        for i in range(40):
            c.review(1, c.due_day)
        self.assertGreater(c.stability, 0)

    def test_grade_clamped(self):
        c = Card("q1")
        c.review(99, 0.0)
        self.assertEqual(c.history[-1]["grade"], 4)
        c.review(-5, 1.0)
        self.assertEqual(c.history[-1]["grade"], 1)

    def test_roundtrip_serialisation(self):
        c = Card("q1")
        c.review(3, 0.0)
        c2 = Card.from_dict(c.to_dict())
        self.assertEqual(c2.stability, c.stability)
        self.assertEqual(c2.item_id, "q1")

    def test_queue_orders_due_first(self):
        cards = []
        for i in range(5):
            c = Card(f"q{i}")
            c.review(3, 0.0)
            cards.append(c)
        q = build_queue(cards, day=1000.0)
        self.assertTrue(all(c.due_day <= 1000.0 for c in q))

    def test_queue_respects_limit(self):
        cards = [Card(f"q{i}") for i in range(50)]
        for c in cards:
            c.review(3, 0.0)
        self.assertLessEqual(len(build_queue(cards, 1000.0, limit=7)), 7)

    def test_forecast_empty(self):
        f = retention_forecast([], 0.0)
        self.assertEqual(f["n"], 0)


class TestFSRSParameterFitting(unittest.TestCase):
    """v1.1 — fit FSRS weights from the learner's own review history."""

    def _make_history(self, grades, start_day=0.0, interval=1.0):
        """Build a review sequence [(day, grade), ...] from a grade list."""
        return [(start_day + i * interval, g) for i, g in enumerate(grades)]

    def test_returns_defaults_with_too_few_reviews(self):
        """Fitting on <10 reviews returns defaults, not noise."""
        seqs = [self._make_history([3, 3, 3]), self._make_history([1, 2])]
        w = fit_parameters(seqs)
        self.assertEqual(w, DEFAULT_W)

    def test_output_shape_and_types(self):
        seqs = [self._make_history([3, 3, 1, 3, 4, 3, 1, 3, 3, 2, 3, 4])
                for _ in range(5)]
        w = fit_parameters(seqs, max_iter=20)
        self.assertEqual(len(w), 19)
        self.assertTrue(all(isinstance(x, float) for x in w))
        self.assertTrue(all(x > 0 for x in w))

    def test_loss_non_negative(self):
        seqs = [self._make_history([3, 3, 3, 1, 3, 4, 2, 3, 3, 1, 3, 4])]
        loss = total_loss(DEFAULT_W, seqs)
        self.assertGreater(loss, 0.0)

    def test_fitting_reduces_loss(self):
        """Coordinate descent must not increase the loss."""
        seqs = [
            self._make_history([3, 3, 1, 3, 4, 3, 1, 3, 3, 2, 3, 4]),
            self._make_history([4, 4, 3, 4, 3, 4, 4, 3, 4, 4, 3, 4]),
            self._make_history([1, 1, 2, 1, 3, 1, 2, 1, 1, 3, 1, 2]),
            self._make_history([3, 2, 3, 4, 3, 3, 2, 3, 4, 3, 2, 3]),
            self._make_history([2, 3, 2, 1, 3, 2, 3, 2, 1, 3, 2, 3]),
        ]
        before = total_loss(DEFAULT_W, seqs)
        w = fit_parameters(seqs, max_iter=100)
        after = total_loss(w, seqs)
        self.assertLessEqual(after, before)

    def test_empty_history_returns_defaults(self):
        w = fit_parameters([])
        self.assertEqual(w, DEFAULT_W)

    def test_custom_initial_weights(self):
        """Passing initial weights seeds the optimiser."""
        seqs = [self._make_history([3, 3, 3, 1, 3, 4, 2, 3, 3, 1, 3, 4])]
        w0 = list(DEFAULT_W)
        w = fit_parameters(seqs, initial=w0, max_iter=10)
        self.assertEqual(len(w), 19)
        self.assertTrue(all(x > 0 for x in w))

    def test_grades_are_clamped_in_loss(self):
        """Grades outside 1-4 are clamped before scoring."""
        seqs = [self._make_history([99, -5, 99, -5, 3, 3, 3, 3, 3, 3, 3, 3])]
        loss = total_loss(DEFAULT_W, seqs)
        self.assertGreater(loss, 0.0)
        self.assertFalse(math.isnan(loss))


# ----------------------------------------------------------------- tracing

class TestBKT(unittest.TestCase):
    def test_prior_initialises(self):
        s = BKTSkill("x", BKTParams(p_L0=0.3))
        self.assertAlmostEqual(s.p_known, 0.3)

    def test_correct_increases_knowledge(self):
        s = BKTSkill("x")
        before = s.p_known
        s.update(True)
        self.assertGreater(s.p_known, before)

    def test_incorrect_decreases_knowledge(self):
        s = BKTSkill("x", BKTParams(p_L0=0.8))
        before = s.p_known
        s.update(False)
        self.assertLess(s.p_known, before)

    def test_mastery_reached_with_repeated_success(self):
        s = BKTSkill("x")
        for _ in range(12):
            s.update(True)
        self.assertTrue(s.mastered)

    def test_probability_bounded(self):
        s = BKTSkill("x")
        for _ in range(200):
            s.update(True)
        self.assertLess(s.p_known, 1.0)
        for _ in range(200):
            s.update(False)
        self.assertGreater(s.p_known, 0.0)

    def test_counters(self):
        s = BKTSkill("x")
        s.update(True); s.update(False); s.update(True)
        self.assertEqual(s.opportunities, 3)
        self.assertEqual(s.correct, 2)

    def test_predicted_correct_in_range(self):
        s = BKTSkill("x")
        for _ in range(5):
            s.update(True)
        p = s.predicted_correct()
        self.assertGreaterEqual(p, 0.0)
        self.assertLessEqual(p, 1.0)


class TestIRT(unittest.TestCase):
    def test_icc_monotonic(self):
        it = Item("q", a=1.5, b=0.0)
        self.assertLess(it.p_correct(-2), it.p_correct(0))
        self.assertLess(it.p_correct(0), it.p_correct(2))

    def test_icc_at_difficulty_is_half(self):
        it = Item("q", a=1.0, b=0.5, c=0.0)
        self.assertAlmostEqual(it.p_correct(0.5), 0.5, places=6)

    def test_guessing_floor(self):
        it = Item("q", a=1.0, b=0.0, c=0.25)
        self.assertGreaterEqual(it.p_correct(-10), 0.25)

    def test_information_peaks_near_difficulty(self):
        it = Item("q", a=1.0, b=0.0, c=0.0)
        self.assertGreater(it.information(0.0), it.information(3.0))
        self.assertGreater(it.information(0.0), it.information(-3.0))

    def test_elo_update_direction(self):
        it = Item("q")
        before = it.elo
        it.update_elo(True)
        self.assertGreater(it.elo, before)
        it2 = Item("q2")
        b2 = it2.elo
        it2.update_elo(False)
        self.assertLess(it2.elo, b2)

    def test_theta_update_rises_on_success(self):
        items = [Item(f"q{i}", b=0.0) for i in range(5)]
        theta = update_theta_mle(0.0, [(i, True) for i in items])
        self.assertGreater(theta, 0.0)

    def test_theta_update_falls_on_failure(self):
        items = [Item(f"q{i}", b=0.0) for i in range(5)]
        theta = update_theta_mle(0.0, [(i, False) for i in items])
        self.assertLess(theta, 0.0)

    def test_theta_bounded(self):
        items = [Item(f"q{i}", b=0.0) for i in range(20)]
        self.assertLessEqual(update_theta_mle(0.0, [(i, True) for i in items]), 4.0)

    def test_item_selection_targets_eighty_five_percent(self):
        """The anti-pampering control: selection must aim below certainty."""
        pool = [Item(f"q{i}", b=(i - 10) / 2.0) for i in range(21)]
        chosen = select_next_item(pool, theta=0.0, target_p=0.85)
        self.assertIsNotNone(chosen)
        assert chosen is not None
        self.assertAlmostEqual(chosen.p_correct(0.0), 0.85, delta=0.15)

    def test_item_selection_never_picks_certainty(self):
        pool = [Item(f"q{i}", b=(i - 10) / 2.0) for i in range(21)]
        chosen = select_next_item(pool, theta=0.0, target_p=0.85)
        assert chosen is not None
        self.assertLess(chosen.p_correct(0.0), 0.99)

    def test_item_selection_excludes(self):
        pool = [Item(f"q{i}", b=0.0) for i in range(3)]
        chosen = select_next_item(pool, 0.0, exclude={"q0", "q1"})
        assert chosen is not None
        self.assertEqual(chosen.item_id, "q2")

    def test_item_selection_empty(self):
        self.assertIsNone(select_next_item([], 0.0))


class TestCalibration(unittest.TestCase):
    def test_empty(self):
        self.assertEqual(calibration_stats([])["n"], 0)

    def test_perfect_calibration(self):
        j = [(1.0, True)] * 10 + [(0.0, False)] * 10
        out = calibration_stats(j)
        self.assertAlmostEqual(out["bias"], 0.0, places=6)
        self.assertEqual(out["interpretation"], "well_calibrated")

    def test_overconfidence_detected(self):
        j = [(0.9, False)] * 10
        out = calibration_stats(j)
        self.assertGreater(out["bias"], 0.15)
        self.assertEqual(out["interpretation"], "overconfident")

    def test_underconfidence_detected(self):
        j = [(0.1, True)] * 10
        out = calibration_stats(j)
        self.assertLess(out["bias"], -0.15)
        self.assertEqual(out["interpretation"], "underconfident")

    def test_brier_bounded(self):
        j = [(0.5, True), (0.5, False), (1.0, True), (0.0, False)]
        out = calibration_stats(j)
        self.assertGreaterEqual(out["brier"], 0.0)
        self.assertLessEqual(out["brier"], 1.0)

    def test_gamma_computed(self):
        j = [(0.9, True), (0.8, True), (0.2, False), (0.1, False)]
        out = calibration_stats(j)
        self.assertIsNotNone(out["gamma"])
        self.assertGreater(out["gamma"], 0.0)


# ----------------------------------------------------------- question gen

class TestQuestionGeneration(unittest.TestCase):
    def setUp(self):
        self.qs = generate_from_source(SAMPLE, max_per_style=2)

    def test_produces_questions(self):
        real = [q for q in self.qs if q.style != "provenance"]
        self.assertGreater(len(real), 20)

    def test_all_native_styles_attempted(self):
        styles = {q.style for q in self.qs}
        for s in NATIVE_GENERATORS:
            self.assertIn(s, styles, f"style {s} produced nothing")

    def test_every_question_has_provenance(self):
        for q in self.qs:
            if q.style == "provenance":
                continue
            self.assertTrue(q.source_span, f"{q.qid} has no source span")

    def test_every_question_has_answer(self):
        for q in self.qs:
            if q.style == "provenance":
                continue
            self.assertTrue(q.answer, f"{q.qid} has no answer")

    def test_llm_styles_flagged(self):
        for q in self.qs:
            if q.style in LLM_STYLES:
                self.assertTrue(q.requires_llm)

    def test_native_styles_not_flagged(self):
        for q in self.qs:
            if q.style in NATIVE_GENERATORS:
                self.assertFalse(q.requires_llm)

    def test_cloze_has_blank(self):
        cloze = [q for q in self.qs if q.style == "cloze"]
        self.assertTrue(cloze)
        for q in cloze:
            self.assertIn("______", q.prompt)

    def test_true_false_requires_justification(self):
        tf = [q for q in self.qs if q.style == "true_false_justify"]
        self.assertTrue(tf)
        for q in tf:
            self.assertIn("justify", q.prompt.lower())

    def test_no_pampering_in_prompts(self):
        for q in self.qs:
            low = q.prompt.lower()
            for pat in PAMPERING_PATTERNS:
                self.assertNotIn(pat, low, f"pampering in {q.qid}")

    def test_specific_styles(self):
        qs = generate_from_source(SAMPLE, styles=["cloze", "definition"])
        styles = {q.style for q in qs}
        self.assertIn("cloze", styles)
        self.assertIn("definition", styles)
        self.assertNotIn("steelman", styles)

    def test_unknown_style_rejected(self):
        with self.assertRaises(KeyError):
            generate_from_source(SAMPLE, styles=["nonexistent_style"])

    def test_empty_source_rejected(self):
        with self.assertRaises(SourceError):
            generate_from_source("")

    def test_short_source_handled(self):
        qs = generate_from_source("Water boils at 100 degrees Celsius at sea level.")
        self.assertTrue(any(q.style != "provenance" for q in qs))

    def test_provenance_reports_skips(self):
        qs = generate_from_source("Water boils at 100 degrees.")
        prov = [q for q in qs if q.style == "provenance"]
        if prov:
            self.assertIn("skipped", prov[0].meta)

    def test_bloom_ordering(self):
        real = [q for q in self.qs if q.style != "provenance"]
        order = {"remember": 0, "understand": 1, "apply": 2, "analyse": 3,
                 "evaluate": 4, "create": 5}
        levels = [order[q.bloom] for q in real]
        self.assertEqual(levels, sorted(levels))

    def test_difficulty_hints_present(self):
        for q in self.qs:
            if q.style != "provenance":
                self.assertIsInstance(q.difficulty_hint, float)

    def test_interleave_separates_skills(self):
        real = [q for q in self.qs if q.style != "provenance"]
        out = interleave(real)
        self.assertEqual(len(out), len(real))
        runs = 0
        for a, b in zip(out, out[1:]):
            if a.skill_id == b.skill_id:
                runs += 1
        self.assertLess(runs, len(out) / 2)

    def test_sentence_splitter(self):
        s = sentences("One sentence here that is long enough to keep. "
                      "Another one follows and is also long enough! "
                      "And a third one that passes the filter too?")
        self.assertEqual(len(s), 3)

    def test_sentence_splitter_drops_fragments(self):
        """Fragments under 25 chars are dropped as unusable."""
        self.assertEqual(sentences("Too short. Also short."), [])

    def test_all_styles_listed(self):
        self.assertGreaterEqual(len(ALL_STYLES), 21)

    def test_ordering_answer_format(self):
        qs = generate_from_source(SAMPLE, styles=["ordering"])
        real = [q for q in qs if q.style == "ordering"]
        self.assertTrue(real)
        for q in real:
            self.assertIn("->", q.answer)


# ------------------------------------------------------------------- store

class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = Path(self.tmp.name) / "t.db"
        self.store = Store(self.db)
        self.store.upsert_learner("L1", "Tester")

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_learner_roundtrip(self):
        got = self.store.get_learner("L1")
        self.assertEqual(got["display"], "Tester")

    def test_missing_learner(self):
        self.assertIsNone(self.store.get_learner("nope"))

    def test_add_and_count_questions(self):
        qs = generate_from_source(SAMPLE, max_per_style=1)
        n = self.store.add_questions("L1", qs)
        self.assertEqual(n, self.store.count_questions("L1"))

    def test_provenance_not_stored(self):
        qs = generate_from_source("Water boils at 100 degrees.")
        self.store.add_questions("L1", qs)
        stored = self.store.list_questions("L1")
        self.assertFalse(any(q["style"] == "provenance" for q in stored))

    def test_source_roundtrip(self):
        self.store.add_source("s1", "L1", "T", "/p", "abc", "hello world")
        self.assertEqual(self.store.get_source_text("s1"), "hello world")
        self.assertEqual(len(self.store.list_sources("L1")), 1)

    def test_attempt_recorded(self):
        self.store.add_attempt("L1", "q1", "sk", True, 1.0, 500, 0.8, "ans", 0.0)
        a = self.store.attempts("L1")
        self.assertEqual(len(a), 1)
        self.assertEqual(a[0]["correct"], 1)

    def test_skill_upsert(self):
        self.store.upsert_skill("L1", "sk", 0.7, {"p_L0": .2, "p_T": .15,
                                                  "p_S": .1, "p_G": .2}, 5, 4)
        s = self.store.skill_states("L1")
        self.assertEqual(len(s), 1)
        self.assertAlmostEqual(s[0]["p_known"], 0.7)

    def test_card_upsert(self):
        c = Card("q1")
        c.review(3, 0.0)
        self.store.upsert_card("L1", c)
        self.assertEqual(len(self.store.cards("L1")), 1)

    def test_profile_save_and_load(self):
        self.store.save_profile("L1", "kind", {"a": 1})
        self.assertEqual(self.store.latest_profile("L1", "kind"), {"a": 1})

    def test_events(self):
        self.store.log_event("test", "detail", "L1")
        self.assertEqual(len(self.store.events()), 1)

    def test_export_contains_all_tables(self):
        exp = self.store.export_learner("L1")
        for k in ("learner", "sources", "questions", "attempts", "skills",
                  "cards", "events"):
            self.assertIn(k, exp)

    def test_erase_removes_everything(self):
        self.store.add_source("s1", "L1", "T", "/p", "abc", "text")
        self.store.add_attempt("L1", "q1", "sk", True, 1.0, 1, None, "", 0.0)
        self.store.erase_learner("L1")
        self.assertIsNone(self.store.get_learner("L1"))
        self.assertEqual(self.store.count_questions("L1"), 0)
        self.assertEqual(self.store.attempts("L1"), [])
        self.assertEqual(self.store.list_sources("L1"), [])

    def test_sql_injection_attempt_is_parameterised(self):
        """A hostile learner_id must be stored as data, never executed."""
        evil = "x'; DROP TABLE learner; --"
        self.store.upsert_learner(evil)
        self.assertIsNotNone(self.store.get_learner(evil))
        self.assertIsNotNone(self.store.get_learner("L1"))

    def test_transaction_rollback(self):
        with self.assertRaises(RuntimeError):
            with self.store.transaction():
                self.store.upsert_learner("L2")
                raise RuntimeError("boom")
        self.assertIsNone(self.store.get_learner("L2"))

    def test_concurrent_writes_from_multiple_threads(self):
        """Regression: sqlite3 connections are thread-bound.

        ThreadingHTTPServer serves each request on its own thread, so the
        store must hand out a per-thread connection. Without that, every
        request after the first raises ProgrammingError.
        """
        import threading
        errors: list[Exception] = []

        def worker(n: int):
            try:
                for i in range(5):
                    lid = f"T{n}_{i}"
                    self.store.upsert_learner(lid, f"worker{n}")
                    self.store.log_event("concurrent", f"t{n}i{i}", lid)
                    self.store.add_attempt(lid, f"q{i}", "sk", True, 1.0, 10,
                                           None, "", 0.0)
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30)

        self.assertEqual(errors, [], f"thread errors: {errors[:3]}")
        self.assertIsNotNone(self.store.get_learner("T0_0"))
        self.assertIsNotNone(self.store.get_learner("T7_4"))

    def test_concurrent_reads_and_writes(self):
        import threading
        errors: list[Exception] = []
        stop = threading.Event()

        def writer():
            try:
                for i in range(50):
                    self.store.upsert_learner(f"W{i}")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)
            finally:
                stop.set()

        def reader():
            try:
                while not stop.is_set():
                    self.store.list_sources("L1")
                    self.store.count_questions("L1")
            except Exception as exc:  # noqa: BLE001
                errors.append(exc)

        ts = [threading.Thread(target=writer)] + \
             [threading.Thread(target=reader) for _ in range(4)]
        for t in ts:
            t.start()
        for t in ts:
            t.join(timeout=30)
        self.assertEqual(errors, [], f"errors: {errors[:3]}")


# -------------------------------------------------------------- instruments

class TestInstruments(unittest.TestCase):
    def test_registry_valid(self):
        self.assertEqual(validate_registry(), [])

    def test_servable_excludes_clinical(self):
        for s in servable_tasks():
            self.assertFalse(s.clinical_only)
            self.assertNotIn(s.licence, (LICENCE_RESTRICTED, LICENCE_CLINICAL))

    def test_restricted_declared_not_served(self):
        manifest = task_manifest()
        served = {t["task_id"] for t in manifest["tasks"]}
        declined = {t["task_id"] for t in manifest["declined"]}
        self.assertIn("rmet_original", declined)
        self.assertNotIn("rmet_original", served)
        self.assertIn("asrs", declined)

    def test_notion_and_obsidian_present(self):
        ids = {s.task_id for s in servable_tasks()}
        self.assertTrue(ids)

    def test_flanker_scorer(self):
        trials = ([{"congruent": True, "correct": True, "rt_ms": 500}] * 10 +
                  [{"congruent": False, "correct": True, "rt_ms": 700}] * 10)
        out = score_task("flanker", trials)
        self.assertAlmostEqual(out["interference_cost_ms"], 200.0)
        self.assertEqual(out["accuracy"], 1.0)

    def test_dccs_scorer(self):
        trials = ([{"switched": True, "correct": True, "rt_ms": 600}] * 5 +
                  [{"switched": False, "correct": True, "rt_ms": 400}] * 5)
        out = score_task("dccs", trials)
        self.assertAlmostEqual(out["switch_cost_ms"], 200.0)

    def test_nback_dprime(self):
        trials = ([{"n": 3, "hit": True}] * 8 + [{"n": 3, "miss": True}] * 2 +
                  [{"n": 3, "false_alarm": True}] * 2 +
                  [{"n": 3, "correct_rejection": True}] * 8)
        out = score_task("dual_nback", trials)
        self.assertEqual(out["max_n"], 3)
        self.assertGreater(out["d_prime"], 0)
        self.assertIn("transfer", out["transfer_claim"])

    def test_bart_scorer(self):
        trials = [{"pumps": 30, "burst": False}] * 5 + [{"pumps": 50, "burst": True}]
        out = score_task("bart", trials)
        self.assertAlmostEqual(out["adjusted_pumps"], 30.0)

    def test_discounting_scorer(self):
        trials = [{"delay_days": 7, "immediate": 50, "delayed": 60,
                   "chose_immediate": True}]
        out = score_task("delay_discounting", trials)
        self.assertIsNotNone(out["log_k"])

    def test_ultimatum_scorer(self):
        trials = [{"role": "responder", "offer": 0.2, "accepted": False},
                  {"role": "responder", "offer": 0.5, "accepted": True}]
        out = score_task("ultimatum", trials)
        self.assertIsNotNone(out["min_acceptable_offer"])
        self.assertEqual(out["rejection_rate"], 0.5)

    def test_dictator_scorer(self):
        out = score_task("dictator", [{"share": 0.0}, {"share": 0.5}])
        self.assertAlmostEqual(out["mean_share_given"], 0.25)
        self.assertAlmostEqual(out["zero_give_rate"], 0.5)

    def test_svo_categories(self):
        """Ring categories on the deviation frame (Liebrand & McClintock 1988).

        Equal split sits at +45 (prosocial); favouring self sits below -22.5
        (competitive); giving the other more than self sits above +67.5
        (altruist).
        """
        prosocial = score_task("social_value_orientation",
                               [{"self": 60, "other": 60}] * 5)
        self.assertEqual(prosocial["svo_category"], "prosocial")
        comp = score_task("social_value_orientation",
                          [{"self": 80, "other": 20}] * 5)
        self.assertEqual(comp["svo_category"], "competitive")
        alt = score_task("social_value_orientation",
                         [{"self": 30, "other": 70}] * 5)
        self.assertEqual(alt["svo_category"], "altruist")
        # Self-favouring but not maximally: still competitive on the ring,
        # because the ring measures deviation from the equal split.
        mild = score_task("social_value_orientation",
                          [{"self": 90, "other": 60}] * 5)
        self.assertEqual(mild["svo_category"], "competitive")

    def test_svo_angle_matches_documented_frame(self):
        equal = score_task("social_value_orientation",
                           [{"self": 50, "other": 50}] * 5)
        self.assertAlmostEqual(equal["svo_angle"], 45.0, places=1)
        self_only = score_task("social_value_orientation",
                               [{"self": 100, "other": 0}] * 5)
        self.assertAlmostEqual(self_only["svo_angle"], -45.0, places=1)

    def test_svo_empty(self):
        out = score_task("social_value_orientation", [])
        self.assertIsNone(out["svo_category"])

    def test_public_goods_decay(self):
        trials = [{"round": i, "contribution": 10 - i, "others_mean": 5}
                  for i in range(5)]
        out = score_task("public_goods", trials)
        self.assertLess(out["decay_slope"], 0)

    def test_pd_scorer(self):
        trials = ([{"partner": "tft", "cooperated": True}] * 5 +
                  [{"partner": "random", "cooperated": False}] * 5)
        out = score_task("prisoners_dilemma", trials)
        self.assertEqual(out["coop_vs_tft"], 1.0)
        self.assertEqual(out["coop_vs_random"], 0.0)

    def test_ucla_bands(self):
        self.assertEqual(score_task("loneliness_ucla", [1] * 20)["band"], "low")
        self.assertEqual(score_task("loneliness_ucla", [4] * 20)["band"], "high")

    def test_pattern_comparison_scorer(self):
        trials = [{"correct": True}] * 70 + [{"correct": False}] * 20
        out = score_task("pattern_comparison", trials)
        self.assertEqual(out["correct_in_window"], 70)
        self.assertAlmostEqual(out["accuracy"], 0.778, places=2)
        self.assertEqual(out["n"], 90)

    def test_pattern_comparison_empty(self):
        out = score_task("pattern_comparison", [])
        self.assertEqual(out["correct_in_window"], 0)
        self.assertIsNone(out["accuracy"])

    def test_false_belief_scorer(self):
        trials = ([{"correct": True, "order": "second"}] * 6 +
                  [{"correct": False, "order": "second"}] * 2 +
                  [{"correct": True, "order": "first"}] * 2)
        out = score_task("false_belief", trials)
        self.assertAlmostEqual(out["second_order_accuracy"], 0.75, places=2)
        self.assertEqual(out["n"], 8)

    def test_false_belief_empty(self):
        out = score_task("false_belief", [])
        self.assertIsNone(out["second_order_accuracy"])

    def test_ucla_trials_format(self):
        """score_ucla accepts the trials format [{score: int}, ...]."""
        trials = [{"score": 1}] * 20
        out = score_task("loneliness_ucla", trials)
        self.assertEqual(out["ucla_total"], 20)
        self.assertEqual(out["band"], "low")

    def test_ucla_list_format_still_works(self):
        """score_ucla still accepts the original list[int] format."""
        out = score_task("loneliness_ucla", [4] * 20)
        self.assertEqual(out["ucla_total"], 80)
        self.assertEqual(out["band"], "high")

    def test_unknown_task_rejected(self):
        with self.assertRaises(KeyError):
            score_task("nope", [])

    def test_empty_trials_handled(self):
        out = score_task("flanker", [])
        self.assertIsNone(out["interference_cost_ms"])


class TestCompositeScoring(unittest.TestCase):
    """PennCNB efficiency and NIH Toolbox two-vector scoring."""

    def test_penncnb_efficiency_is_mean_of_z_scores(self):
        out = penncnb_composite(accuracy=0.9, median_rt_ms=500.0,
                                ref_acc_mean=0.8, ref_acc_sd=0.1,
                                ref_rt_mean=600.0, ref_rt_sd=100.0)
        # z_acc = (0.9-0.8)/0.1 = 1.0 ; z_speed = -((500-600)/100) = 1.0
        self.assertAlmostEqual(out["z_accuracy"], 1.0, places=3)
        self.assertAlmostEqual(out["z_speed"], 1.0, places=3)
        self.assertAlmostEqual(out["efficiency"], 1.0, places=3)

    def test_penncnb_faster_is_better(self):
        fast = penncnb_composite(0.8, 400.0, 0.8, 0.1, 600.0, 100.0)
        slow = penncnb_composite(0.8, 800.0, 0.8, 0.1, 600.0, 100.0)
        self.assertGreater(fast["z_speed"], slow["z_speed"])
        self.assertGreater(fast["efficiency"], slow["efficiency"])

    def test_penncnb_rejects_bad_sd(self):
        with self.assertRaises(ValueError):
            penncnb_composite(0.8, 500.0, 0.8, 0.0, 600.0, 100.0)

    def test_penncnb_flags_within_person_use(self):
        out = penncnb_composite(0.8, 500.0, 0.8, 0.1, 600.0, 100.0)
        self.assertIn("within-person", out["note"])

    def test_nih_accuracy_vector_formula(self):
        out = nih_toolbox_two_vector(correct=20, total=20, median_rt_ms=500.0)
        # 0.125 * 20 = 2.5
        self.assertAlmostEqual(out["accuracy_vector"], 2.5, places=3)

    def test_nih_accuracy_vector_saturates(self):
        out = nih_toolbox_two_vector(correct=100, total=100, median_rt_ms=500.0)
        self.assertAlmostEqual(out["accuracy_vector"], 5.0, places=3)

    def test_nih_low_accuracy_uses_accuracy_only(self):
        """The load-bearing rule: below 80% accuracy, speed is not scored."""
        out = nih_toolbox_two_vector(correct=10, total=20, median_rt_ms=300.0)
        self.assertAlmostEqual(out["total_0_10"], out["accuracy_vector"], places=3)
        self.assertIn("<= 80%", out["rule_applied"])

    def test_nih_high_accuracy_adds_rt_vector(self):
        out = nih_toolbox_two_vector(correct=18, total=20, median_rt_ms=300.0)
        self.assertAlmostEqual(out["total_0_10"],
                               out["accuracy_vector"] + out["rt_vector"], places=3)
        self.assertIn("> 80%", out["rule_applied"])

    def test_nih_rt_vector_bounds(self):
        fast = nih_toolbox_two_vector(18, 20, median_rt_ms=100.0)
        slow = nih_toolbox_two_vector(18, 20, median_rt_ms=5000.0)
        self.assertAlmostEqual(fast["rt_vector"], 5.0, places=3)
        self.assertAlmostEqual(slow["rt_vector"], 0.0, places=3)

    def test_nih_rejects_zero_total(self):
        with self.assertRaises(ValueError):
            nih_toolbox_two_vector(0, 0)


class TestDivergenceSignal(unittest.TestCase):
    """Subjective vs objective cognition must never be composited."""

    def test_insufficient_data(self):
        self.assertEqual(divergence_signal(None, 0.8)["state"], "insufficient_data")
        self.assertEqual(divergence_signal(2.0, None)["state"], "insufficient_data")

    def test_concordant_impairment(self):
        out = divergence_signal(subjective=3.5, objective=0.3)
        self.assertEqual(out["state"], "concordant_impairment")

    def test_subjective_only(self):
        """The common post-viral pattern: feels worse than they perform."""
        out = divergence_signal(subjective=3.5, objective=0.9)
        self.assertEqual(out["state"], "subjective_only")
        self.assertIn("not evidence", out["interpretation"])

    def test_objective_only(self):
        """The dangerous case: performance dropped without the learner noticing."""
        out = divergence_signal(subjective=0.5, objective=0.3)
        self.assertEqual(out["state"], "objective_only")
        self.assertIn("will not prompt you", out["interpretation"])

    def test_concordant_healthy(self):
        out = divergence_signal(subjective=0.5, objective=0.9)
        self.assertEqual(out["state"], "concordant_healthy")

    def test_never_returns_a_merged_score(self):
        out = divergence_signal(2.0, 0.8)
        self.assertNotIn("composite", out)
        self.assertNotIn("score", out)
        self.assertIn("never averaged", out["note"])

    def test_no_clinical_language(self):
        for s, o in [(3.5, 0.3), (3.5, 0.9), (0.5, 0.3), (0.5, 0.9)]:
            text = divergence_signal(s, o)["interpretation"].lower()
            for pat in ("disorder", "diagnos", "symptom", "deficit", "patient"):
                self.assertNotIn(pat, text)


# ----------------------------------------------------------------- profile

class TestProfile(unittest.TestCase):
    def _scores(self):
        return {
            "flanker": score_task("flanker",
                                  [{"congruent": True, "correct": True, "rt_ms": 500}] * 10 +
                                  [{"congruent": False, "correct": True, "rt_ms": 700}] * 10),
            "public_goods": score_task("public_goods",
                                       [{"round": i, "contribution": 8, "others_mean": 7}
                                        for i in range(10)]),
            "prisoners_dilemma": score_task("prisoners_dilemma",
                                            [{"partner": "tft", "cooperated": True}] * 10 +
                                            [{"partner": "random", "cooperated": False}] * 10),
            "ultimatum": score_task("ultimatum",
                                    [{"role": "responder", "offer": 0.2, "accepted": False}] * 10 +
                                    [{"role": "responder", "offer": 0.5, "accepted": True}] * 10),
        }

    def test_builds_profile(self):
        p = build_profile("L1", self._scores())
        self.assertGreater(len(p.observations), 0)

    def test_role_inferred(self):
        p = build_profile("L1", self._scores())
        self.assertIn(p.social_role, ("Sustainer", "Enforcer", "Competitor",
                                      "Giver", "Withholder", "Reciprocator",
                                      "Unclassified"))

    def test_limits_always_present(self):
        p = build_profile("L1", {})
        self.assertGreater(len(p.limits), 0)

    def test_no_diagnosis_passes(self):
        p = build_profile("L1", self._scores())
        p.assert_no_diagnosis()

    def test_clinical_task_refused(self):
        with self.assertRaises(StatementError):
            build_profile("L1", {"asrs": {"n": 20}})

    def test_low_trials_flagged(self):
        scores = {"flanker": score_task("flanker",
                                        [{"congruent": True, "correct": True, "rt_ms": 500}])}
        p = build_profile("L1", scores)
        if p.observations:
            self.assertIn("provisional", p.observations[0].statement)

    def test_unmeasured_reported(self):
        p = build_profile("L1", {})
        self.assertGreater(len(p.unmeasured), 0)

    def test_serialises(self):
        p = build_profile("L1", self._scores())
        json.dumps(p.to_dict())


class TestAntiPampering(unittest.TestCase):
    def test_blocks_all_pampering_phrases(self):
        for pat in PAMPERING_PATTERNS:
            with self.assertRaises(StatementError, msg=f"leaked: {pat}"):
                validate_statement(f"You should know that {pat} for this attempt")

    def test_blocks_all_unfalsifiable_claims(self):
        for pat in UNFALSIFIABLE_PATTERNS:
            with self.assertRaises(StatementError, msg=f"leaked: {pat}"):
                validate_statement(f"Based on the data, {pat} in every setting")

    def test_blocks_all_clinical_vocabulary(self):
        for pat in CLINICAL_PATTERNS:
            with self.assertRaises(StatementError, msg=f"leaked: {pat}"):
                validate_statement(f"The measurement indicates {pat} present here")

    def test_blocks_too_short(self):
        with self.assertRaises(StatementError):
            validate_statement("Correct.")

    def test_allows_honest_statement(self):
        validate_statement("You answered 6 of 10 correctly, which is below the "
                           "band where learning is fastest.")

    def test_feedback_never_praises(self):
        for verdict in ("correct", "partial", "incorrect"):
            fb = grade_feedback(verdict, 1.0, "answer", "response")
            self.assertFalse(fb.is_praise)
            low = (fb.what_happened + fb.what_it_means + fb.next_action).lower()
            for pat in PAMPERING_PATTERNS:
                self.assertNotIn(pat, low)

    def test_lucky_correct_named(self):
        fb = grade_feedback("correct", 1.0, "a", "a", expected_p=0.95)
        self.assertIn("already likely", fb.what_happened)

    def test_incorrect_gives_answer(self):
        fb = grade_feedback("incorrect", 0.0, "the right answer", "wrong")
        self.assertIn("the right answer", fb.what_happened)

    def test_blank_answer_diagnosed(self):
        fb = grade_feedback("incorrect", 0.0, "x", "   ")
        self.assertIn("blank", fb.what_it_means.lower())

    def test_session_summary_flags_easy_set(self):
        s = session_summary([{"correct": True, "latency_ms": 500}] * 10)
        self.assertEqual(s["verdict"], "under-challenged")

    def test_session_summary_flags_overload(self):
        s = session_summary([{"correct": False, "latency_ms": 500}] * 10)
        self.assertEqual(s["verdict"], "over-loaded")

    def test_session_summary_productive_band(self):
        attempts = ([{"correct": True, "latency_ms": 500}] * 8 +
                    [{"correct": False, "latency_ms": 500}] * 2)
        s = session_summary(attempts)
        self.assertEqual(s["verdict"], "in the productive band")

    def test_session_summary_empty(self):
        self.assertEqual(session_summary([])["n"], 0)


# -------------------------------------------------------------- onboarding

class TestOnboarding(unittest.TestCase):
    def _run_all(self, ob, source="none"):
        while True:
            p = ob.next_probe()
            if p is None:
                break
            if p.probe_id == "source":
                ob.record(p.probe_id, source)
            elif p.probe_id == "goal":
                ob.record(p.probe_id, "Pass a specific exam or certification, with a date attached")
            elif p.probe_id == "domain":
                ob.record(p.probe_id, "Statistics and probability")
            elif p.probe_id == "constraints":
                ob.record(p.probe_id, {"session_minutes": 25, "days_per_week": 5,
                                       "best_time": "morning"})
            elif p.probe_id == "difficulty_preference":
                ob.record(p.probe_id, "85% — the evidence-based band (recommended)")
            elif p.probe_id == "fog_baseline":
                ob.record(p.probe_id, {"a": 3, "b": 2, "c": 2, "d": 3, "e": 3})
            else:
                ob.record(p.probe_id, {"ok": True})

    def test_probe_sequence_completes(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        self.assertIsNone(ob.next_probe())

    def test_calibration_skipped_without_source(self):
        ob = Onboarding("L1")
        self._run_all(ob, source="none")
        self.assertIn("calibration_probe", ob.skipped)

    def test_calibration_runs_with_source(self):
        ob = Onboarding("L1")
        self._run_all(ob, source="my notes on statistics")
        self.assertNotIn("calibration_probe", ob.skipped)

    def test_progress_tracking(self):
        ob = Onboarding("L1")
        p = ob.progress()
        self.assertEqual(p["completed"], 0)
        self.assertGreater(p["minutes_remaining"], 0)

    def test_contract_goal_classified(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        c = ob.build_contract()
        self.assertEqual(c.goal_type, "exam_with_deadline")

    def test_contract_domain_shape(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        c = ob.build_contract()
        self.assertEqual(c.domain_shape, "procedural_numeric")

    def test_contract_styles_match_shape(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        c = ob.build_contract()
        self.assertIn("numeric", c.question_styles)

    def test_contract_constraints_clamped(self):
        ob = Onboarding("L1")
        ob.record("constraints", {"session_minutes": 9999, "days_per_week": 99})
        c = ob.build_contract()
        self.assertLessEqual(c.session_minutes, 90)
        self.assertLessEqual(c.days_per_week, 7)

    def test_contract_target_rate(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        c = ob.build_contract()
        self.assertAlmostEqual(c.target_success_rate, 0.85)

    def test_gentler_setting_respected(self):
        ob = Onboarding("L1")
        ob.record("difficulty_preference", "70% — gentler")
        c = ob.build_contract()
        self.assertAlmostEqual(c.target_success_rate, 0.70)

    def test_falsifiers_present(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        c = ob.build_contract()
        self.assertGreaterEqual(len(c.falsifiers), 4)

    def test_fog_baseline_computed(self):
        ob = Onboarding("L1")
        ob.record("fog_baseline", {"a": 4, "b": 4})
        c = ob.build_contract()
        self.assertAlmostEqual(c.fog_baseline, 4.0)

    def test_high_fog_changes_plan(self):
        ob = Onboarding("L1")
        ob.record("fog_baseline", {"a": 4, "b": 4, "c": 3})
        c = ob.build_contract()
        self.assertTrue(any("fatigue" in x.lower() or "breaks" in x.lower()
                            for x in c.intervention_plan))

    def test_gaps_reported(self):
        ob = Onboarding("L1")
        c = ob.build_contract()
        self.assertGreater(len(c.gaps), 0)

    def test_summary_is_readable(self):
        ob = Onboarding("L1")
        self._run_all(ob)
        s = ob.build_contract().summary()
        self.assertIn("WHAT THIS SYSTEM WILL DO", s)
        self.assertIn("PROVE THIS CONTRACT WRONG", s)

    def test_unknown_probe_rejected(self):
        with self.assertRaises(KeyError):
            Onboarding("L1").record("nonexistent", 1)

    def test_all_probes_have_purpose(self):
        for p in PROBES:
            self.assertTrue(p.purpose, f"{p.probe_id} has no stated purpose")
            self.assertTrue(p.yields, f"{p.probe_id} yields nothing")


# --------------------------------------------------------------------- MCP

class TestMCP(unittest.TestCase):
    def test_catalogue_has_notion_and_obsidian(self):
        keys = {s.key for s in CATALOGUE}
        self.assertIn("notion", keys)
        self.assertIn("obsidian", keys)

    def test_notion_is_oauth(self):
        notion = next(s for s in CATALOGUE if s.key == "notion")
        self.assertEqual(notion.auth, AUTH_OAUTH)
        self.assertEqual(notion.target, "https://mcp.notion.com/mcp")

    def test_core_set_size(self):
        self.assertGreaterEqual(len(core_servers()), 10)

    def test_core_includes_notion_and_obsidian(self):
        keys = {s.key for s in core_servers()}
        self.assertIn("notion", keys)
        self.assertIn("obsidian", keys)

    def test_oauth_list_nonempty(self):
        self.assertGreater(len(oauth_servers()), 0)

    def test_config_generates_all_core(self):
        cfg = build_mcp_config()
        self.assertEqual(len(cfg["mcpServers"]), len(core_servers()))

    def test_config_never_inlines_secrets(self):
        cfg = build_mcp_config()
        blob = json.dumps(cfg)
        for key in ("sk-", "api_key=", "password", "secret"):
            self.assertNotIn(key, blob.lower())

    def test_oauth_entry_has_no_token(self):
        cfg = build_mcp_config(["notion"])
        entry = cfg["mcpServers"]["notion"]
        self.assertEqual(entry["auth"], "oauth")
        self.assertNotIn("access_token", entry)
        self.assertIn("token_cache", entry)

    def test_stdio_entry_uses_env_reference(self):
        cfg = build_mcp_config(["obsidian"])
        entry = cfg["mcpServers"]["obsidian"]
        self.assertEqual(entry["command"], "npx")
        self.assertEqual(entry["env"]["OBSIDIAN_VAULT_PATH"],
                         "${OBSIDIAN_VAULT_PATH}")

    def test_api_key_entry_uses_env_reference(self):
        cfg = build_mcp_config(["brave_search"])
        entry = cfg["mcpServers"]["brave_search"]
        self.assertEqual(entry["env"]["BRAVE_API_KEY"], "${BRAVE_API_KEY}")

    def test_unknown_key_skipped(self):
        cfg = build_mcp_config(["notion", "does_not_exist"])
        self.assertEqual(list(cfg["mcpServers"]), ["notion"])

    def test_write_config_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p = write_mcp_config(Path(d) / "mcp.json", ["notion"])
            self.assertTrue(p.is_file())
            mode = oct(os.stat(p).st_mode & 0o777)
            self.assertEqual(mode, "0o600")

    def test_onboarding_plan_shape(self):
        plan = onboarding_plan()
        for k in ("already_configured", "oauth_required", "api_key_required",
                  "steps", "core_without_any_auth"):
            self.assertIn(k, plan)

    def test_plan_separates_oauth_from_local(self):
        plan = onboarding_plan()
        oauth_keys = {o["key"] for o in plan["oauth_required"]}
        self.assertIn("notion", oauth_keys)
        self.assertNotIn("obsidian", oauth_keys)

    def test_token_status_unauthorised(self):
        with tempfile.TemporaryDirectory() as d:
            st = token_status(d, "notion")
            self.assertFalse(st["authorised"])

    def test_all_servers_have_learning_role(self):
        for s in CATALOGUE:
            self.assertTrue(s.learning_role, f"{s.key} has no learning role")

    def test_all_servers_have_valid_transport(self):
        for s in CATALOGUE:
            self.assertIn(s.transport, ("stdio", "streamable-http", "sse"))

    def test_all_servers_have_valid_auth(self):
        for s in CATALOGUE:
            self.assertIn(s.auth, (AUTH_NONE, AUTH_OAUTH, AUTH_API_KEY, AUTH_LOCAL))

    def test_http_servers_have_url(self):
        for s in CATALOGUE:
            if s.transport != "stdio":
                self.assertTrue(s.target.startswith("http"), s.key)

    def test_stdio_servers_have_command(self):
        for s in CATALOGUE:
            if s.transport == "stdio":
                self.assertTrue(s.target, s.key)
                self.assertIsInstance(s.args, list)

    def test_obsidian_default_needs_no_plugin(self):
        """The default Obsidian server must work on raw Markdown."""
        obs = next(s for s in CATALOGUE if s.key == "obsidian")
        self.assertEqual(obs.transport, "stdio")
        self.assertIn("obsidian-mcp", " ".join(obs.args))
        self.assertNotIn("OBSIDIAN_API_KEY", obs.env_keys)
        self.assertIn("no", obs.notes.lower())

    def test_obsidian_rest_variant_documented_as_plugin_requiring(self):
        rest = next(s for s in CATALOGUE if s.key == "obsidian_rest")
        self.assertIn("plugin", rest.notes.lower())

    def test_anki_is_sse_on_localhost(self):
        anki = next(s for s in CATALOGUE if s.key == "anki")
        self.assertEqual(anki.transport, "sse")
        self.assertIn("localhost", anki.target)

    def test_wolfram_excluded_from_oauth_only_core(self):
        from cortexforge.mcp import CORE_EXCLUSIONS
        self.assertIn("wolfram", CORE_EXCLUSIONS)
        self.assertNotIn("wolfram", CORE_KEYS)

    def test_core_exclusions_document_missing_servers(self):
        from cortexforge.mcp import CORE_EXCLUSIONS
        for key in ("coursera", "khan_academy", "duolingo"):
            self.assertIn(key, CORE_EXCLUSIONS)

    def test_every_core_server_is_oauth_or_no_auth(self):
        """The user's constraint: only OAuth should remain for the learner."""
        for s in core_servers():
            self.assertIn(s.auth, (AUTH_NONE, AUTH_LOCAL, AUTH_OAUTH),
                          f"{s.key} needs an API key and cannot be OAuth-only")

    def test_notes_present_on_servers_with_caveats(self):
        for key in ("obsidian", "obsidian_rest", "anki", "wolfram"):
            spec = next(s for s in CATALOGUE if s.key == key)
            self.assertTrue(spec.notes, f"{key} should document its caveat")


if __name__ == "__main__":
    unittest.main(verbosity=2)
