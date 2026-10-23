"""CortexForge HTTP server — stdlib only, hardened.

Endpoints
    GET  /                       the app shell
    GET  /static/*               static assets (containment-checked)
    GET  /api/health             liveness
    GET  /api/manifest           task + MCP + style manifest
    POST /api/onboarding/start   begin first-run
    GET  /api/onboarding/next    next probe
    POST /api/onboarding/record  record a probe result
    POST /api/onboarding/finish  build the learning contract
    POST /api/source             ingest a source document
    POST /api/generate           generate questions from a source
    GET  /api/session            build today's session
    POST /api/attempt            record an answer
    GET  /api/profile            current behavioural profile
    GET  /api/export             export all learner data
    POST /api/erase              erase all learner data
    GET  /api/mcp/plan           onboarding plan for MCP
    POST /api/mcp/config         write mcp.json
    GET  /api/scheduler/weights  FSRS weights in effect for a learner
    POST /api/scheduler/fit      fit FSRS weights from the learner's history

Security posture (see security.py for the CVE mapping):
  * Bound to 127.0.0.1 by default; never 0.0.0.0 without an explicit flag.
  * Every response carries the CSP and hardening headers.
  * A per-run bearer token is required for all mutating endpoints, so a
    malicious page in the learner's browser cannot drive the local API
    (the classic localhost-CSRF / DNS-rebinding class).
  * Host header is validated against an allowlist (DNS rebinding).
  * Request bodies are size-capped and JSON-parsed with the strict loader.
  * Static file serving goes through safe_join.
"""

from __future__ import annotations

import json
import mimetypes
import os
import re
import threading
import time
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .accounts import AccountManager, SmtpConfig, RateLimiter
from .environment import (EnvironmentAudit, PrescriptionGenerator,
                         PhysicalEnvironment, DigitalEnvironment,
                         SocialEnvironment, TemporalEnvironment,
                         MaterialsEnvironment)
from .evaluation import (create_default_registry, ScoringEngine,
                         BatteryScheduler, score_and_update_profile,
                         InstrumentRegistry)
from .instruments import task_manifest, score_task, REGISTRY
from .learner_profile import LearnerProfile
from .mcp import (CATALOGUE, build_mcp_config, core_servers, onboarding_plan,
                  write_mcp_config)
from .neuroprotection import NeuroProtectionSystem, Trial
from .onboarding import Onboarding, PROBES, PROBES_BY_ID
from .profile import build_profile, grade_feedback, session_summary
from .questiongen import ALL_STYLES, Question, generate_from_source, interleave
from .scheduler import (DEFAULT_W, MIN_LOSS_FOR_FIT, MIN_REVIEWS_FOR_FIT,
                        Card, build_queue, fit_parameters,
                        retention_forecast, total_loss)
from .security import (MAX_DOCUMENT_BYTES, SecurityError, escape_html,
                       load_json_only, safe_join, sanitise_text,
                       security_headers, secure_token)
from .session import SessionRunner, SessionConfig, SessionType, StageName
from .store import Store
from .tracing import BKTSkill, BKTParams, Item, calibration_stats, select_next_item
from .tutor import TutorHarness, TutorMode

MAX_BODY_BYTES = 8 * 1024 * 1024
ALLOWED_HOSTS = {"127.0.0.1", "localhost", "[::1]", "::1"}


class AppState:
    """Holds the store and per-learner runtime state."""

    def __init__(self, db_path: str, static_dir: str):
        self.store = Store(db_path)
        self.static_dir = Path(static_dir).resolve()
        self.token = secure_token(24)
        self.lock = threading.Lock()
        self.onboardings: dict[str, Onboarding] = {}
        self.skills: dict[str, dict[str, BKTSkill]] = {}
        self.items: dict[str, list[Item]] = {}
        self.theta: dict[str, float] = {}
        self.cards: dict[str, dict[str, Card]] = {}
        self.weights: dict[str, list] = {}
        self.day_zero: dict[str, float] = {}
        self.tutors: dict[str, TutorHarness] = {}
        self.session_runners: dict[str, SessionRunner] = {}
        self.neuroprotection: dict[str, NeuroProtectionSystem] = {}
        self.learner_profiles: dict[str, LearnerProfile] = {}
        self.eval_registries: dict[str, InstrumentRegistry] = {}
        self.eval_schedulers: dict[str, BatteryScheduler] = {}
        self.eval_engines: dict[str, ScoringEngine] = {}
        self.accounts = AccountManager(self.store)
        self.auth_rate_limiter = RateLimiter(window=60, max_attempts=5)

    def day(self, learner_id: str) -> float:
        if learner_id not in self.day_zero:
            self.day_zero[learner_id] = time.time()
        return (time.time() - self.day_zero[learner_id]) / 86400.0

    def skill_for(self, learner_id: str, skill_id: str) -> BKTSkill:
        bucket = self.skills.setdefault(learner_id, {})
        if skill_id not in bucket:
            bucket[skill_id] = BKTSkill(skill_id)
        return bucket[skill_id]

    def card_for(self, learner_id: str, qid: str) -> Card:
        """Return the live card for `qid`, hydrating it from the store on
        first touch.

        Without hydration every process restart reset each card to `new`, so
        due-day, stability and difficulty were silently discarded and the
        whole deck re-appeared as never-reviewed.
        """
        bucket = self.cards.setdefault(learner_id, {})
        if qid not in bucket:
            row = self.state_card_row(learner_id, qid)
            if row is not None:
                bucket[qid] = Card(
                    qid,
                    stability=float(row["stability"] or 0.0),
                    difficulty=float(row["difficulty"] or 0.0),
                    reps=int(row["reps"] or 0),
                    lapses=int(row["lapses"] or 0),
                    last_review_day=float(row["last_day"] or 0.0),
                    due_day=float(row["due_day"] or 0.0),
                    state=str(row["state"] or "new"),
                )
            else:
                bucket[qid] = Card(qid)
        return bucket[qid]

    def state_card_row(self, learner_id: str, qid: str) -> dict | None:
        rows = self.store.card_rows(learner_id, [qid])
        return rows[0] if rows else None

    def hydrate_cards(self, learner_id: str) -> int:
        """Load every persisted card for a learner into memory.

        Called before queue/forecast work so a restarted process still knows
        which items are due. Returns the number of cards loaded.
        """
        bucket = self.cards.setdefault(learner_id, {})
        n = 0
        for row in self.store.all_cards(learner_id):
            if row["qid"] in bucket:
                continue
            bucket[row["qid"]] = Card(
                row["qid"],
                stability=float(row["stability"] or 0.0),
                difficulty=float(row["difficulty"] or 0.0),
                reps=int(row["reps"] or 0),
                lapses=int(row["lapses"] or 0),
                last_review_day=float(row["last_day"] or 0.0),
                due_day=float(row["due_day"] or 0.0),
                state=str(row["state"] or "new"),
            )
            n += 1
        return n

    def weights_for(self, learner_id: str) -> list:
        """FSRS weights for a learner: fitted, else the published defaults."""
        if learner_id not in self.weights:
            fitted = self.store.get_fitted_weights(learner_id)
            self.weights[learner_id] = list(fitted) if fitted else list(DEFAULT_W)
        return self.weights[learner_id]

    def invalidate_weights(self, learner_id: str) -> None:
        self.weights.pop(learner_id, None)


class Handler(BaseHTTPRequestHandler):
    server_version = f"CortexForge/{__version__}"
    protocol_version = "HTTP/1.1"

    # -- plumbing --------------------------------------------------------
    @property
    def state(self) -> AppState:
        return self.server.app  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args) -> None:
        # Log method/path/status only; never log bodies or headers.
        try:
            self.state.store.log_event("http", f"{self.command} {self.path}")
        except Exception:
            pass

    def _headers(self, status: int, ctype: str, length: int) -> None:
        self.send_response(status)
        # CVE-2019-9740/CVE-2019-9947: sanitize CRLF in headers
        safe_ctype = ctype.replace('\r', ' ').replace('\n', ' ').replace('\x00', '')
        self.send_header("Content-Type", safe_ctype)
        self.send_header("Content-Length", str(length))
        for k, v in security_headers().items():
            safe_k = k.replace('\r', ' ').replace('\n', ' ').replace('\x00', '')
            safe_v = v.replace('\r', ' ').replace('\n', ' ').replace('\x00', '')
            self.send_header(safe_k, safe_v)
        self.end_headers()

    def _safe_write(self, data: bytes) -> None:
        """Write response data, handling BrokenPipeError gracefully."""
        try:
            self.wfile.write(data)
        except (BrokenPipeError, ConnectionResetError):
            self.close_connection = True

    def _json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, default=str).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self._safe_write(body)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message, "status": status}, status)

    def _check_host(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        # CVE-2015-20107: hostname length limit (RFC 1035)
        if len(host) > 253:
            self._error(400, "hostname too long")
            return False
        # Reject control characters in hostname
        if any(ord(c) < 32 or ord(c) == 127 for c in host):
            self._error(400, "invalid hostname")
            return False
        if host and host not in ALLOWED_HOSTS:
            self._error(403, "host not allowed")
            return False
        return True

    def _check_auth(self) -> bool:
        """Per-user API token required for mutating calls (localhost CSRF guard)."""
        supplied = self.headers.get("X-CortexForge-Token", "")
        if not supplied:
            self._error(401, "missing or invalid token")
            return False
        # Check against per-user tokens in the account table
        row = self.state.store._one(
            "SELECT account_id FROM account WHERE api_token = ?",
            (supplied,)
        )
        if row is None:
            self._error(401, "missing or invalid token")
            return False
        return True

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise SecurityError(f"body too large: {length}")
        raw = self.rfile.read(length) if length else b"{}"
        return load_json_only(raw.decode("utf-8", "replace"))

    # -- routes ----------------------------------------------------------
    def do_GET(self) -> None:
        if not self._check_host():
            return
        # CVE-2021-28861: collapse leading slashes to prevent open redirect
        raw_path = self.path
        while raw_path.startswith('//'):
            raw_path = '/' + raw_path.lstrip('/')
        parsed = urllib.parse.urlparse(raw_path)
        path = parsed.path
        # CVE-2021-23336: strict query parsing
        query = urllib.parse.parse_qs(parsed.query, strict_parsing=False,
                                       max_num_fields=100)
        try:
            if path == "/":
                return self._serve_static("index.html")
            if path.startswith("/static/"):
                return self._serve_static(path[len("/static/"):])
            if path == "/api/health":
                return self._json({"ok": True, "version": __version__,
                                   "time": time.time()})
            if path == "/api/manifest":
                return self._json({
                    "tasks": task_manifest(),
                    "styles": ALL_STYLES,
                    "mcp": {"catalogue": len(CATALOGUE),
                            "core": [s.key for s in core_servers()]},
                    "probes": [p.to_dict() for p in PROBES],
                })
            if path == "/api/onboarding/next":
                return self._onboarding_next(query)
            if path == "/api/session":
                return self._session(query)
            if path == "/api/profile":
                return self._profile(query)
            if path == "/api/export":
                return self._export(query)
            if path == "/api/mcp/plan":
                return self._json(onboarding_plan())
            if path == "/api/mcp/config":
                return self._json(build_mcp_config())
            if path == "/api/learner-profile":
                return self._learner_profile_get(query)
            if path == "/api/session/summary":
                return self._session_summary_get(query)
            if path == "/api/environment/audit":
                return self._environment_audit_get(query)
            if path == "/api/neuroprotection/status":
                return self._neuroprotection_status_get(query)
            if path == "/api/evaluation/battery":
                return self._evaluation_battery_get(query)
            if path == "/api/scheduler/weights":
                return self._scheduler_weights_get(query)
            if path == "/api/account/verify":
                return self._account_verify_get(query)
            return self._error(404, "not found")
        except SecurityError as exc:
            return self._error(400, str(exc))
        except Exception as exc:  # never leak a traceback to the client
            self.state.store.log_event("error", f"{type(exc).__name__}: {exc}")
            return self._error(500, "internal error")

    def do_POST(self) -> None:
        if not self._check_host():
            return
        # CVE-2021-28861: collapse leading slashes
        raw_path = self.path
        while raw_path.startswith('//'):
            raw_path = '/' + raw_path.lstrip('/')
        parsed = urllib.parse.urlparse(raw_path)
        path = parsed.path
        # Auth endpoints must not require a token (chicken-and-egg)
        AUTH_ENDPOINTS = {'/api/account/create', '/api/account/login',
                          '/api/account/reset-request', '/api/account/reset'}
        if path not in AUTH_ENDPOINTS:
            if not self._check_auth():
                return
        try:
            body = self._read_body()
            if path == "/api/onboarding/start":
                return self._onboarding_start(body)
            if path == "/api/onboarding/record":
                return self._onboarding_record(body)
            if path == "/api/onboarding/finish":
                return self._onboarding_finish(body)
            if path == "/api/source":
                return self._add_source(body)
            if path == "/api/generate":
                return self._generate(body)
            if path == "/api/attempt":
                return self._attempt(body)
            if path == "/api/erase":
                return self._erase(body)
            if path == "/api/mcp/config":
                return self._write_mcp(body)
            if path == "/api/session/start":
                return self._session_start(body)
            if path == "/api/session/stage":
                return self._session_stage(body)
            if path == "/api/session/close":
                return self._session_close(body)
            if path == "/api/tutor/begin":
                return self._tutor_begin(body)
            if path == "/api/tutor/respond":
                return self._tutor_respond(body)
            if path == "/api/tutor/hint":
                return self._tutor_hint(body)
            if path == "/api/tutor/answer":
                return self._tutor_answer(body)
            if path == "/api/tutor/question":
                return self._tutor_question(body)
            if path == "/api/environment/submit":
                return self._environment_submit(body)
            if path == "/api/neuroprotection/trial":
                return self._neuroprotection_trial(body)
            if path == "/api/evaluation/respond":
                return self._evaluation_respond(body)
            if path == "/api/learner-profile/update":
                return self._learner_profile_update(body)
            if path == "/api/scheduler/fit":
                return self._scheduler_fit(body)
            if path == "/api/account/create":
                return self._account_create(body)
            if path == "/api/account/login":
                return self._account_login(body)
            if path == "/api/account/logout":
                return self._account_logout(body)
            if path == "/api/account/session":
                return self._account_session(body)
            if path == "/api/account/reset-request":
                return self._account_reset_request(body)
            if path == "/api/account/reset":
                return self._account_reset(body)
            return self._error(404, "not found")
        except SecurityError as exc:
            return self._error(400, str(exc))
        except Exception as exc:
            # Log the traceback to stderr for diagnosis, but never to the
            # client: it can leak paths and internal structure.
            traceback.print_exc()
            self.state.store.log_event("error", f"{type(exc).__name__}: {exc}")
            return self._error(500, "internal error")

    # -- static ----------------------------------------------------------
    def _serve_static(self, rel: str) -> None:
        try:
            target = safe_join(self.state.static_dir, rel)
        except SecurityError:
            return self._error(403, "forbidden")
        if not target.is_file():
            return self._error(404, "not found")
        ctype = mimetypes.guess_type(str(target))[0] or "application/octet-stream"
        data = target.read_bytes()
        self._headers(200, ctype, len(data))
        self._safe_write(data)

    # -- handlers --------------------------------------------------------
    def _learner_id(self, body: dict) -> str:
        lid = str(body.get("learner_id") or "").strip()
        if not lid or len(lid) > 128 or not re.fullmatch(r"[A-Za-z0-9_\-]+", lid):
            raise SecurityError("invalid learner_id")
        return lid

    def _onboarding_start(self, body: dict) -> None:
        lid = self._learner_id(body)
        with self.state.lock:
            self.state.onboardings[lid] = Onboarding(lid)
        self.state.store.upsert_learner(lid)
        self.state.store.log_event("onboarding_start", "", lid)
        self._json({"learner_id": lid, "probes": [p.to_dict() for p in PROBES],
                    "progress": self.state.onboardings[lid].progress()})

    def _onboarding_next(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        ob = self.state.onboardings.get(lid)
        if ob is None:
            return self._error(404, "no onboarding in progress")
        probe = ob.next_probe()
        self._json({"probe": probe.to_dict() if probe else None,
                    "progress": ob.progress()})

    def _onboarding_record(self, body: dict) -> None:
        lid = self._learner_id(body)
        ob = self.state.onboardings.get(lid)
        if ob is None:
            return self._error(404, "no onboarding in progress")
        probe_id = str(body.get("probe_id") or "")
        if probe_id not in PROBES_BY_ID:
            return self._error(400, "unknown probe_id")
        answer = body.get("answer")
        if isinstance(answer, str):
            answer = sanitise_text(answer, 20000)
        with self.state.lock:
            ob.record(probe_id, answer)
            # If this probe was a behavioural task, score it and store the result.
            probe = PROBES_BY_ID[probe_id]
            if probe.task_id and isinstance(answer, dict) and "trials" in answer:
                try:
                    scored = score_task(probe.task_id, answer["trials"])
                    self.state.store.save_profile(lid, f"task:{probe.task_id}", scored)
                except (KeyError, TypeError, ValueError):
                    pass
        self._json({"recorded": probe_id, "progress": ob.progress()})

    def _onboarding_finish(self, body: dict) -> None:
        lid = self._learner_id(body)
        ob = self.state.onboardings.get(lid)
        if ob is None:
            return self._error(404, "no onboarding in progress")
        contract = ob.build_contract()
        self.state.store.save_profile(lid, "contract", contract.to_dict())
        self.state.store.log_event("onboarding_finish", "", lid)
        self._json({"contract": contract.to_dict(),
                    "summary": contract.summary()})

    def _add_source(self, body: dict) -> None:
        import hashlib
        lid = self._learner_id(body)
        text = body.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._error(400, "text is required")
        if len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
            return self._error(413, "source too large")
        text = sanitise_text(text, 4_000_000)
        sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
        sid = "src-" + sha[:16]
        self.state.store.add_source(
            sid, lid, sanitise_text(str(body.get("title", "")), 500),
            sanitise_text(str(body.get("origin_path", "")), 1000), sha, text)
        self._json({"source_id": sid, "sha256": sha, "n_chars": len(text)})

    def _generate(self, body: dict) -> None:
        lid = self._learner_id(body)
        sid = str(body.get("source_id") or "")
        text = self.state.store.get_source_text(sid) if sid else body.get("text")
        if not isinstance(text, str) or not text.strip():
            return self._error(400, "source_id or text is required")
        styles = body.get("styles")
        if styles is not None and not isinstance(styles, list):
            return self._error(400, "styles must be a list")
        if styles:
            unknown = [s for s in styles if s not in ALL_STYLES]
            if unknown:
                return self._error(400, f"unknown styles: {unknown}")
        try:
            questions = generate_from_source(
                text, styles=styles,
                max_per_style=int(body.get("max_per_style", 3) or 3),
                skill_id=sanitise_text(str(body.get("skill_id", "")), 100))
        except ValueError as exc:
            return self._error(400, str(exc))
        stored = self.state.store.add_questions(lid, questions)
        self.state.store.log_event("generate", f"{stored} questions", lid)
        payload = [q.to_dict() for q in questions if q.style != "provenance"]
        prov = next((q.meta for q in questions if q.style == "provenance"), {})
        self._json({"generated": stored, "questions": payload,
                    "provenance": prov})

    def _session(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        day = self.state.day(lid)
        with self.state.lock:
            self.state.hydrate_cards(lid)
            cards = list(self.state.cards.get(lid, {}).values())
        queue = build_queue(cards, day, limit=int((query.get("limit") or ["20"])[0]))
        qmap = {q["qid"]: q for q in self.state.store.list_questions(lid, limit=5000)}
        items = [qmap[c.item_id] for c in queue if c.item_id in qmap]
        forecast = retention_forecast(cards, day)
        self._json({"day": round(day, 3), "n_due": len(items),
                    "items": items, "forecast": forecast})

    def _attempt(self, body: dict) -> None:
        lid = self._learner_id(body)
        qid = str(body.get("qid") or "")
        if not qid:
            return self._error(400, "qid required")
        correct = bool(body.get("correct"))
        grade = int(body.get("grade") or (3 if correct else 1))
        grade = max(1, min(4, grade))
        confidence = body.get("confidence")
        if confidence is not None:
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (TypeError, ValueError):
                confidence = None
        day = self.state.day(lid)
        with self.state.lock:
            card = self.state.card_for(lid, qid)
            sched = card.review(grade, day, self.state.weights_for(lid))
            skill_id = sanitise_text(str(body.get("skill_id", "general")), 100)
            skill = self.state.skill_for(lid, skill_id)
            p_known = skill.update(correct)
            self.state.store.add_attempt(
                lid, qid, skill_id, correct, 1.0 if correct else 0.0,
                int(body.get("latency_ms") or 0), confidence,
                str(body.get("response", "")), day)
            self.state.store.upsert_card(lid, card)
            self.state.store.upsert_skill(lid, skill_id, p_known,
                                          skill.p.to_dict(),
                                          skill.opportunities, skill.correct)
        self._json({"p_known": round(p_known, 4), "mastered": skill.mastered,
                    "schedule": sched,
                    "next_due_day": round(sched["due_day"], 3)})

    def _profile(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        task_scores: dict[str, dict] = {}
        for spec in REGISTRY.values():
            saved = self.state.store.latest_profile(lid, f"task:{spec.task_id}")
            if saved:
                task_scores[spec.task_id] = saved
        attempts = self.state.store.attempts(lid, limit=10000)
        pairs = [(a["confidence"], bool(a["correct"])) for a in attempts
                 if a["confidence"] is not None]
        with self.state.lock:
            self.state.hydrate_cards(lid)
            cards = list(self.state.cards.get(lid, {}).values())
        day = self.state.day(lid)
        forecast = retention_forecast(cards, day)
        skills = self.state.store.skill_states(lid)
        mastered = (sum(1 for s in skills if s["p_known"] >= 0.95) / len(skills)
                    if skills else 0.0)
        lm = {
            "calibration": calibration_stats(pairs) if pairs else {},
            "mean_retrievability": forecast["mean_retrievability"],
            "due_now": forecast["due_now"],
            "mastered_fraction": mastered,
        }
        try:
            prof = build_profile(lid, task_scores, lm)
        except Exception as exc:
            return self._error(500, f"profile build failed: {exc}")
        self._json({"profile": prof.to_dict(),
                    "session": session_summary(attempts)})

    def _export(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        self._json(self.state.store.export_learner(lid))

    def _erase(self, body: dict) -> None:
        lid = self._learner_id(body)
        if body.get("confirm") != "ERASE":
            return self._error(400, "confirm must be the string ERASE")
        self.state.store.erase_learner(lid)
        self.state.onboardings.pop(lid, None)
        self.state.skills.pop(lid, None)
        self.state.cards.pop(lid, None)
        self._json({"erased": lid})

    def _write_mcp(self, body: dict) -> None:
        keys = body.get("keys")
        if keys is not None and not isinstance(keys, list):
            return self._error(400, "keys must be a list")
        out = Path(body.get("path") or (Path.home() / ".cortexforge" / "mcp.json"))
        p = write_mcp_config(out, keys)
        self._json({"written": str(p), "servers": list(build_mcp_config(keys)["mcpServers"])})


    # -- learner profile -------------------------------------------------

    def _learner_profile_get(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        prof = self.state.learner_profiles.get(lid)
        if prof is None:
            prof = self.state.learner_profiles.setdefault(lid, LearnerProfile(lid))
        self._json(prof.to_dict())

    def _learner_profile_update(self, body: dict) -> None:
        lid = self._learner_id(body)
        prof = self.state.learner_profiles.setdefault(lid, LearnerProfile(lid))
        event_type = str(body.get("event_type") or "")
        if event_type == "attempt":
            prof.record_attempt(
                skill_id=str(body.get("skill_id") or "general"),
                correct=bool(body.get("correct")),
                confidence=body.get("confidence"),
                latency_ms=int(body.get("latency_ms") or 0),
            )
        elif event_type == "session":
            prof.record_session(
                session_type=str(body.get("session_type") or "practice"),
                duration_min=float(body.get("duration_min") or 0),
                success_rate=body.get("success_rate"),
            )
        elif event_type == "instrument":
            prof.record_instrument_score(
                instrument_id=str(body.get("instrument_id") or ""),
                score=body.get("score"),
                subscale=body.get("subscale"),
            )
        elif event_type == "override":
            prof.update_from_override(
                dimension=str(body.get("dimension") or ""),
                field=str(body.get("field") or ""),
                value=body.get("value"),
                reason=str(body.get("reason") or ""),
            )
        else:
            return self._error(400, "event_type must be attempt, session, instrument, or override")
        self._json(prof.to_dict())

    # -- session ----------------------------------------------------------

    def _session_start(self, body: dict) -> None:
        lid = self._learner_id(body)
        stype = str(body.get("session_type") or "practice")
        try:
            session_type = SessionType(stype)
        except ValueError:
            return self._error(400, f"unknown session_type: {stype}")
        cfg = SessionConfig(
            session_type=session_type,
            day=self.state.day(lid),
            limit=int(body.get("limit") or 20),
            target_success_rate=float(body.get("target_success_rate") or 0.80),
            enable_forethought=bool(body.get("enable_forethought", True)),
            enable_reflection=bool(body.get("enable_reflection", True)),
        )
        runner = SessionRunner(cfg)
        with self.state.lock:
            self.state.session_runners[lid] = runner
        self._json(runner.start())

    def _session_stage(self, body: dict) -> None:
        lid = self._learner_id(body)
        runner = self.state.session_runners.get(lid)
        if runner is None:
            return self._error(404, "no active session")
        stage = str(body.get("stage") or "")
        try:
            stage_name = StageName(stage)
        except ValueError:
            return self._error(400, f"unknown stage: {stage}")
        action = str(body.get("action") or "enter")
        if action == "enter":
            result = runner.enter_stage(stage_name)
        elif action == "exit":
            result = runner.exit_stage(stage_name)
        else:
            return self._error(400, "action must be enter or exit")
        self._json(result)

    def _session_close(self, body: dict) -> None:
        lid = self._learner_id(body)
        runner = self.state.session_runners.pop(lid, None)
        if runner is None:
            return self._error(404, "no active session")
        result = runner.close()
        self._json(result)

    def _session_summary_get(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        runner = self.state.session_runners.get(lid)
        if runner is None:
            return self._error(404, "no active session")
        self._json(runner.get_session_summary())

    # -- tutor ------------------------------------------------------------

    def _tutor_begin(self, body: dict) -> None:
        lid = self._learner_id(body)
        topic = sanitise_text(str(body.get("topic") or ""), 500)
        mode_str = str(body.get("mode") or "practice")
        try:
            mode = TutorMode(mode_str)
        except ValueError:
            return self._error(400, f"unknown mode: {mode_str}")
        tutor = self.state.tutors.setdefault(lid, TutorHarness())
        question = None
        q_data = body.get("question")
        if isinstance(q_data, dict):
            question = Question(
                qid=str(q_data.get("qid") or ""),
                style=str(q_data.get("style") or ""),
                prompt=str(q_data.get("prompt") or ""),
                answer=str(q_data.get("answer") or ""),
                source_span=str(q_data.get("source_span") or ""),
                skill_id=str(q_data.get("skill_id") or ""),
                meta=q_data.get("meta") or {},
            )
        session = tutor.begin_session(lid, topic, mode, question)
        self._json({"learner_id": lid, "state": session.state.value})

    def _tutor_respond(self, body: dict) -> None:
        lid = self._learner_id(body)
        tutor = self.state.tutors.get(lid)
        if tutor is None:
            return self._error(404, "no tutor session")
        msg = sanitise_text(str(body.get("message") or ""), 5000)
        resp = tutor.respond(lid, msg)
        self._json(resp.to_dict())

    def _tutor_hint(self, body: dict) -> None:
        lid = self._learner_id(body)
        tutor = self.state.tutors.get(lid)
        if tutor is None:
            return self._error(404, "no tutor session")
        resp = tutor.provide_hint(lid)
        self._json(resp.to_dict())

    def _tutor_answer(self, body: dict) -> None:
        lid = self._learner_id(body)
        tutor = self.state.tutors.get(lid)
        if tutor is None:
            return self._error(404, "no tutor session")
        answer = str(body.get("answer") or "")
        resp = tutor.check_answer(lid, answer)
        self._json(resp.to_dict())

    def _tutor_question(self, body: dict) -> None:
        lid = self._learner_id(body)
        tutor = self.state.tutors.get(lid)
        if tutor is None:
            return self._error(404, "no tutor session")
        q = sanitise_text(str(body.get("question") or ""), 5000)
        resp = tutor.handle_question(lid, q)
        self._json(resp.to_dict())

    # -- environment ------------------------------------------------------

    def _environment_audit_get(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        audit = self.state.store.get_environment_audit(lid)
        if audit is None:
            return self._json({"learner_id": lid, "audit": None,
                                "prescriptions": []})
        self._json({"learner_id": lid, "audit": audit.to_dict()})

    def _environment_submit(self, body: dict) -> None:
        lid = self._learner_id(body)
        p_data = body.get("physical") or {}
        d_data = body.get("digital") or {}
        s_data = body.get("social") or {}
        t_data = body.get("temporal") or {}
        m_data = body.get("materials") or {}
        audit = EnvironmentAudit(
            learner_id=lid,
            physical=PhysicalEnvironment(
                lighting=str(p_data.get("lighting") or ""),
                noise_sources=list(p_data.get("noise_sources") or []),
                temperature_c=p_data.get("temperature_c"),
                green_view=bool(p_data.get("green_view", False)),
                has_indoor_plants=bool(p_data.get("has_indoor_plants", False)),
                ergonomic_setup=str(p_data.get("ergonomic_setup") or ""),
                phone_location=str(p_data.get("phone_location") or ""),
                desk_clutter=str(p_data.get("desk_clutter") or ""),
            ),
            digital=DigitalEnvironment(
                notification_load=str(d_data.get("notification_load") or ""),
                blocker_available=bool(d_data.get("blocker_available", False)),
                blocker_active=bool(d_data.get("blocker_active", False)),
                distraction_sources=list(d_data.get("distraction_sources") or []),
                phone_in_reach=bool(d_data.get("phone_in_reach", True)),
                social_media_apps_installed=bool(d_data.get("social_media_apps_installed", True)),
                website_blocker_installed=bool(d_data.get("website_blocker_installed", False)),
            ),
            social=SocialEnvironment(
                study_partners=list(s_data.get("study_partners") or []),
                household_support=str(s_data.get("household_support") or ""),
                quiet_hours_feasible=bool(s_data.get("quiet_hours_feasible", False)),
                quiet_hours=str(s_data.get("quiet_hours") or ""),
                social_commitment_device=bool(s_data.get("social_commitment_device", False)),
            ),
            temporal=TemporalEnvironment(
                sleep_schedule=str(t_data.get("sleep_schedule") or ""),
                typical_bedtime=str(t_data.get("typical_bedtime") or ""),
                typical_wake_time=str(t_data.get("typical_wake_time") or ""),
                anchors=list(t_data.get("anchors") or []),
                deadline_map_visible=bool(t_data.get("deadline_map_visible", False)),
                intermediate_checkpoints=bool(t_data.get("intermediate_checkpoints", False)),
                exam_date_known=bool(t_data.get("exam_date_known", False)),
                exam_date=str(t_data.get("exam_date") or ""),
            ),
            materials=MaterialsEnvironment(
                textbook_access=str(m_data.get("textbook_access") or ""),
                calculator_available=bool(m_data.get("calculator_available", False)),
                stationery_ready=bool(m_data.get("stationery_ready", False)),
                materials_visible=bool(m_data.get("materials_visible", False)),
                digital_notes_organised=bool(m_data.get("digital_notes_organised", False)),
            ),
        )
        self.state.store.save_environment_audit(lid, audit.to_dict())
        gen = PrescriptionGenerator(audit)
        prescriptions = gen.generate(max_prescriptions=int(body.get("max_prescriptions") or 5))
        self._json({"learner_id": lid, "audit": audit.to_dict(),
                    "prescriptions": [p.to_dict() for p in prescriptions]})

    # -- neuroprotection --------------------------------------------------

    def _neuroprotection_status_get(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        nps = self.state.neuroprotection.get(lid)
        if nps is None:
            nps = self.state.neuroprotection.setdefault(lid, NeuroProtectionSystem())
        try:
            hour = int((query.get("hour") or ["12"])[0])
        except (ValueError, TypeError):
            hour = 12
        status = nps.check_session(hour=hour)
        self._json(status.to_dict())

    def _neuroprotection_trial(self, body: dict) -> None:
        lid = self._learner_id(body)
        nps = self.state.neuroprotection.setdefault(lid, NeuroProtectionSystem())
        correct = bool(body.get("correct"))
        rt_ms = float(body.get("rt_ms") or 0)
        nps.clarity_guardian.record_trial(correct, rt_ms)
        self._json({"learner_id": lid, "recorded": True})

    # -- evaluation -------------------------------------------------------

    def _evaluation_battery_get(self, query: dict) -> None:
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        registry = self.state.eval_registries.setdefault(lid, create_default_registry())
        scheduler = self.state.eval_schedulers.setdefault(lid, BatteryScheduler(registry))
        engine = self.state.eval_engines.setdefault(lid, ScoringEngine(registry))
        due = scheduler.recommend_today()
        instruments = []
        for inst_id in due:
            inst = registry.get(inst_id)
            if inst:
                instruments.append(inst.to_dict())
        self._json({"learner_id": lid, "due_instruments": instruments,
                    "daily_plan": scheduler.get_daily_plan()})

    def _evaluation_respond(self, body: dict) -> None:
        lid = self._learner_id(body)
        registry = self.state.eval_registries.setdefault(lid, create_default_registry())
        scheduler = self.state.eval_schedulers.setdefault(lid, BatteryScheduler(registry))
        engine = self.state.eval_engines.setdefault(lid, ScoringEngine(registry))
        instrument_id = str(body.get("instrument_id") or "")
        responses = body.get("responses") or {}
        if not isinstance(responses, dict):
            return self._error(400, "responses must be an object")
        try:
            result = engine.score(instrument_id, responses)
        except (KeyError, ValueError) as exc:
            return self._error(400, str(exc))
        scheduler.record_administration(instrument_id)
        observations = engine.score_to_observations(result)
        self._json({"learner_id": lid, "result": result.to_dict(),
                    "observations": observations})

    # -- scheduler / FSRS weights ----------------------------------------

    MIN_REVIEWS_FOR_FIT = MIN_REVIEWS_FOR_FIT

    def _scheduler_weights_get(self, query: dict) -> None:
        """Report the FSRS weights in effect for a learner."""
        lid = (query.get("learner_id") or [""])[0]
        if not lid:
            return self._error(400, "learner_id required")
        row = self.state.store._one(
            "SELECT weights, n_reviews, loss, fitted_at FROM fsrs_weights "
            "WHERE learner_id = ?", (lid,))
        weights = self.state.weights_for(lid)
        fitted = row is not None
        self._json({
            "learner_id": lid,
            "weights": [round(float(w), 6) for w in weights],
            "fitted": fitted,
            "n_reviews": int(row["n_reviews"]) if fitted else 0,
            "loss": round(float(row["loss"]), 6) if fitted and row["loss"] is not None else None,
            "using_defaults": not fitted,
            "n_reviews_available": self.state.store._query(
                "SELECT COUNT(*) AS n FROM attempt WHERE learner_id = ?",
                (lid,))[0]["n"],
            "min_reviews_for_fit": self.MIN_REVIEWS_FOR_FIT,
        })

    def _scheduler_fit(self, body: dict) -> None:
        """Fit FSRS-4.5 weights from the learner's own review history.

        Fitting is deliberately conservative: with fewer than ten recorded
        reviews the defaults are returned untouched, because fitting on too
        little data produces noise rather than signal. ``max_iter`` is
        validated before the history is read so a malformed request is a 400
        rather than a misleading 409.
        """
        lid = self._learner_id(body)
        try:
            max_iter = int(body.get("max_iter") or 200)
        except (TypeError, ValueError):
            return self._error(400, "max_iter must be an integer")
        max_iter = max(1, min(2000, max_iter))
        history = self.state.store.review_history(lid)
        sequences = [seq for seq in history.values() if seq]
        n_reviews = sum(len(s) for s in sequences)
        if n_reviews < self.MIN_REVIEWS_FOR_FIT:
            return self._error(409, (
                f"need at least {self.MIN_REVIEWS_FOR_FIT} reviews to fit; "
                f"found {n_reviews}"))
        with self.state.lock:
            w = fit_parameters(sequences, max_iter=max_iter)
            loss = total_loss(w, sequences)
            # A zero (or near-zero) loss means the reviews carry no signal —
            # typically every review landed on the same day, so predicted
            # retrievability was 1.0 for all of them. Persisting weights from
            # that would be storing noise as if it were a fit.
            if loss <= MIN_LOSS_FOR_FIT:
                return self._json({
                    "learner_id": lid,
                    "fitted": False,
                    "reason": ("reviews carry no scheduling signal: predicted "
                               "retrievability was 1.0 for every review, so "
                               "there is nothing to fit against"),
                    "n_reviews": n_reviews,
                    "n_cards": len(sequences),
                    "loss": round(loss, 6),
                    "weights": [round(float(x), 6) for x in self.state.weights_for(lid)],
                })
            self.state.store.save_fitted_weights(lid, w, n_reviews, loss)
            self.state.invalidate_weights(lid)
            self.state.store.log_event(
                "fsrs_fit", f"{n_reviews} reviews, loss {loss:.4f}", lid)
        self._json({
            "learner_id": lid,
            "fitted": True,
            "n_reviews": n_reviews,
            "n_cards": len(sequences),
            "loss": round(loss, 6),
            "weights": [round(float(x), 6) for x in w],
            "max_iter": max_iter,
        })

    # -- account ---------------------------------------------------------

    def _account_verify_get(self, query: dict) -> None:
        token = (query.get("token") or [""])[0]
        if not token:
            return self._error(400, "token required")
        try:
            result = self.state.accounts.verify_email(token)
            self._json(result)
        except SecurityError as exc:
            self._error(400, str(exc))

    def _account_create(self, body: dict) -> None:
        # Rate limit account creation
        if not self.state.auth_rate_limiter.check("create"):
            return self._error(429, "too many account creation attempts")
        email = str(body.get("email") or "")
        password = str(body.get("password") or "")
        display_name = str(body.get("display_name") or "")
        try:
            account = self.state.accounts.create_account(
                email, password, display_name
            )
            self.state.store.log_event("account_create", "", account["learner_id"])
            self._json(account, 201)
        except SecurityError as exc:
            self._error(400, str(exc))

    def _account_login(self, body: dict) -> None:
        # Rate limit login attempts
        if not self.state.auth_rate_limiter.check("login"):
            return self._error(429, "too many login attempts")
        email = str(body.get("email") or "")
        password = str(body.get("password") or "")
        try:
            session = self.state.accounts.login(email, password)
            self.state.store.log_event("account_login", "", session["learner_id"])
            self._json(session)
        except SecurityError as exc:
            self._error(401, str(exc))

    def _account_logout(self, body: dict) -> None:
        token = str(body.get("session_token") or "")
        if token:
            self.state.accounts.logout(token)
        self._json({"logged_out": True})

    def _account_session(self, body: dict) -> None:
        token = str(body.get("session_token") or "")
        session = self.state.accounts.validate_session(token)
        if session is None:
            return self._error(401, "invalid or expired session")
        self._json(session)

    def _account_reset_request(self, body: dict) -> None:
        # Rate limit reset requests
        if not self.state.auth_rate_limiter.check("reset"):
            return self._error(429, "too many reset requests")
        email = str(body.get("email") or "")
        result = self.state.accounts.request_password_reset(email)
        self._json(result)

    def _account_reset(self, body: dict) -> None:
        token = str(body.get("token") or "")
        new_password = str(body.get("new_password") or "")
        try:
            result = self.state.accounts.reset_password(token, new_password)
            self._json(result)
        except SecurityError as exc:
            self._error(400, str(exc))


def make_server(db_path: str, static_dir: str, host: str = "127.0.0.1",
                port: int = 8731) -> ThreadingHTTPServer:
    if host not in ALLOWED_HOSTS:
        raise SecurityError(
            f"refusing to bind {host}; CortexForge is local-only by default")
    httpd = ThreadingHTTPServer((host, port), Handler)
    httpd.app = AppState(db_path, static_dir)  # type: ignore[attr-defined]
    return httpd


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser(prog="cortexforge")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8731)
    ap.add_argument("--db", default=str(Path.home() / ".cortexforge" / "cortexforge.db"))
    ap.add_argument("--static", default=str(Path(__file__).resolve().parent.parent.parent / "web"))
    args = ap.parse_args()

    httpd = make_server(args.db, args.static, args.host, args.port)
    app: AppState = httpd.app  # type: ignore[attr-defined]
    print(f"CortexForge {__version__} listening on http://{args.host}:{args.port}")
    print(f"Database: {args.db}")
    print("Authentication is per-account. Create one to get a token:")
    print("  curl -X POST http://%s:%d/api/account/create \\"
          % (args.host, args.port))
    print("    -H 'Content-Type: application/json' \\")
    print('    -d \'{"email":"you@example.com","password":"Str0ngPass!","display_name":"Me"}\'')
    print("The response includes api_token — send it as X-CortexForge-Token.")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        app.store.close()
        httpd.server_close()


if __name__ == "__main__":
    main()
