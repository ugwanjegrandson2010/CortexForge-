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
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from . import __version__
from .instruments import task_manifest, score_task, REGISTRY
from .mcp import (CATALOGUE, build_mcp_config, core_servers, onboarding_plan,
                  write_mcp_config)
from .onboarding import Onboarding, PROBES, PROBES_BY_ID
from .profile import build_profile, grade_feedback, session_summary
from .questiongen import ALL_STYLES, generate_from_source, interleave
from .scheduler import Card, build_queue, retention_forecast
from .security import (MAX_DOCUMENT_BYTES, SecurityError, escape_html,
                       load_json_only, safe_join, sanitise_text,
                       security_headers, secure_token)
from .store import Store
from .tracing import BKTSkill, BKTParams, Item, calibration_stats, select_next_item

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
        self.day_zero: dict[str, float] = {}

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
        bucket = self.cards.setdefault(learner_id, {})
        if qid not in bucket:
            bucket[qid] = Card(qid)
        return bucket[qid]


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
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(length))
        for k, v in security_headers().items():
            self.send_header(k, v)
        self.end_headers()

    def _json(self, obj: Any, status: int = 200) -> None:
        body = json.dumps(obj, default=str).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body))
        self.wfile.write(body)

    def _error(self, status: int, message: str) -> None:
        self._json({"error": message, "status": status}, status)

    def _check_host(self) -> bool:
        host = (self.headers.get("Host") or "").split(":")[0]
        if host and host not in ALLOWED_HOSTS:
            self._error(403, "host not allowed")
            return False
        return True

    def _check_auth(self) -> bool:
        """Bearer token required for mutating calls (localhost CSRF guard)."""
        supplied = self.headers.get("X-CortexForge-Token", "")
        from .security import constant_time_compare
        if not supplied or not constant_time_compare(supplied, self.state.token):
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
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
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
            return self._error(404, "not found")
        except SecurityError as exc:
            return self._error(400, str(exc))
        except Exception as exc:  # never leak a traceback to the client
            self.state.store.log_event("error", f"{type(exc).__name__}: {exc}")
            return self._error(500, "internal error")

    def do_POST(self) -> None:
        if not self._check_host():
            return
        if not self._check_auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
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
            return self._error(404, "not found")
        except SecurityError as exc:
            return self._error(400, str(exc))
        except Exception as exc:
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
        self.wfile.write(data)

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
            sched = card.review(grade, day)
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
    print(f"API token (required for writes): {app.token}")
    print(f"Database: {args.db}")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nshutting down")
    finally:
        app.store.close()
        httpd.server_close()


if __name__ == "__main__":
    main()
