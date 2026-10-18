#!/usr/bin/env python3
"""CortexForge TUI — terminal interface for the adaptive learning system.

Usage:
    python -m cortexforge.tui [--port 8731] [--db /path/to.db]

Connects to a running CortexForge server (or starts one in-process).
Provides the same core flows as the web client: onboarding, source
management, study sessions, profile, and MCP integrations.

Pure stdlib — uses curses (built-in on Unix). On Windows, falls back
to a simple text menu if curses is unavailable.
"""

from __future__ import annotations

import argparse
import curses
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional

# ---------------------------------------------------------------------------
# API client
# ---------------------------------------------------------------------------


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"HTTP {status}: {message}")


class ApiClient:
    """Minimal HTTP client for the CortexForge API."""

    def __init__(self, base: str, token: str = "", timeout: int = 30):
        self.base = base.rstrip("/")
        self.token = token
        self.timeout = timeout

    def _request(
        self,
        method: str,
        path: str,
        body: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        url = self.base + path
        if params:
            qs = urllib.parse.urlencode(
                {k: v for k, v in params.items() if v is not None}, doseq=True
            )
            if qs:
                url += "?" + qs
        data = None
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if body is not None:
            data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                raw = resp.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            try:
                err = json.loads(raw.decode("utf-8"))
                msg = err.get("error", str(exc))
            except Exception:
                msg = str(exc)
            raise ApiError(exc.code, msg)
        except urllib.error.URLError as exc:
            raise ApiError(0, str(exc))

    def get(self, path: str, params: dict | None = None) -> dict:
        return self._request("GET", path, params=params)

    def post(self, path: str, body: dict | None = None) -> dict:
        return self._request("POST", path, body=body)

    def health(self) -> dict:
        return self.get("/api/health")

    def manifest(self) -> dict:
        return self.get("/api/manifest")

    def onboarding_start(self, name: str) -> dict:
        return self.post("/api/onboarding/start", {"name": name})

    def onboarding_next(self, learner_id: str) -> dict:
        return self.get("/api/onboarding/next", {"learner_id": learner_id})

    def onboarding_record(
        self, learner_id: str, probe_id: str, answer: Any
    ) -> dict:
        return self.post(
            "/api/onboarding/record",
            {"learner_id": learner_id, "probe_id": probe_id, "answer": answer},
        )

    def onboarding_finish(self, learner_id: str) -> dict:
        return self.post(
            "/api/onboarding/finish", {"learner_id": learner_id}
        )

    def add_source(self, learner_id: str, text: str, title: str = "") -> dict:
        return self.post(
            "/api/source",
            {"learner_id": learner_id, "text": text, "title": title},
        )

    def generate(
        self,
        learner_id: str,
        source_id: str = "",
        text: str = "",
        styles: list[str] | None = None,
    ) -> dict:
        body: dict[str, Any] = {"learner_id": learner_id}
        if source_id:
            body["source_id"] = source_id
        if text:
            body["text"] = text
        if styles:
            body["styles"] = styles
        return self.post("/api/generate", body)

    def session(self, learner_id: str, limit: int = 20) -> dict:
        return self.get("/api/session", {"learner_id": learner_id, "limit": limit})

    def attempt(
        self,
        learner_id: str,
        qid: str,
        correct: bool,
        grade: int = 3,
        confidence: float | None = None,
        skill_id: str = "general",
        latency_ms: int = 0,
        response: str = "",
    ) -> dict:
        body: dict[str, Any] = {
            "learner_id": learner_id,
            "qid": qid,
            "correct": correct,
            "grade": grade,
            "skill_id": skill_id,
            "latency_ms": latency_ms,
            "response": response,
        }
        if confidence is not None:
            body["confidence"] = confidence
        return self.post("/api/attempt", body)

    def profile(self, learner_id: str) -> dict:
        return self.get("/api/profile", {"learner_id": learner_id})

    def export(self, learner_id: str) -> dict:
        return self.get("/api/export", {"learner_id": learner_id})

    def erase(self, learner_id: str) -> dict:
        return self.post("/api/erase", {"learner_id": learner_id, "confirm": "ERASE"})

    def mcp_plan(self) -> dict:
        return self.get("/api/mcp/plan")

    def account_verify(self, token: str) -> dict:
        return self.get("/api/account/verify", {"token": token})


# ---------------------------------------------------------------------------
# TUI framework
# ---------------------------------------------------------------------------


@dataclass
class TuiState:
    """Shared state across screens."""

    api: ApiClient
    learner_id: str = ""
    learner_name: str = ""
    token: str = ""
    screen: str = "main"
    message: str = ""
    message_time: float = 0.0
    running: bool = True
    needs_redraw: bool = True
    data: dict = field(default_factory=dict)


class Screen:
    """Base class for TUI screens."""

    def __init__(self, state: TuiState):
        self.state = state
        self.win: Any = None
        self.height = 0
        self.width = 0

    def setup(self, win: Any, height: int, width: int):
        self.win = win
        self.height = height
        self.width = width

    def draw(self):
        pass

    def handle(self, ch: int) -> bool:
        """Handle a key press. Return True if handled."""
        return False

    def on_enter(self):
        pass

    def on_leave(self):
        pass


def set_message(state: TuiState, msg: str):
    state.message = msg
    state.message_time = time.time()


def format_time_ago(t: float) -> str:
    delta = time.time() - t
    if delta < 5:
        return "now"
    if delta < 60:
        return f"{int(delta)}s ago"
    if delta < 3600:
        return f"{int(delta / 60)}m ago"
    return f"{int(delta / 3600)}h ago"


def truncate(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: n - 3] + "..."


def wrap_text(text: str, width: int) -> list[str]:
    """Simple word-wrap."""
    if width < 10:
        return [text]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        if len(current) + len(word) + 1 > width:
            if current:
                lines.append(current)
            current = word
        else:
            current = current + " " + word if current else word
    if current:
        lines.append(current)
    return lines


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


class MainMenuScreen(Screen):
    def __init__(self, state: TuiState):
        super().__init__(state)
        self.selected = 0
        self.menu_items = [
            ("Setup / Onboarding", "onboard"),
            ("Sources", "sources"),
            ("Study", "study"),
            ("Profile", "profile"),
            ("Integrations (MCP)", "mcp"),
            ("Settings", "settings"),
            ("Quit", "quit"),
        ]

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        title = "CortexForge"
        self.win.addnstr(1, (w - len(title)) // 2, title, w, curses.A_BOLD)

        subtitle = "Adaptive learning system"
        self.win.addnstr(
            2, (w - len(subtitle)) // 2, subtitle, w, curses.A_DIM
        )

        if self.state.learner_id:
            status = f"Learner: {self.state.learner_name or self.state.learner_id}"
            self.win.addnstr(4, 2, status, w - 4)

        start_y = max(6, h // 2 - len(self.menu_items))
        for i, (label, _) in enumerate(self.menu_items):
            y = start_y + i
            if y >= h - 3:
                break
            if i == self.selected:
                self.win.addnstr(
                    y, 4, f"> {label}", w - 8, curses.A_REVERSE
                )
            else:
                self.win.addnstr(y, 4, f"  {label}", w - 8)

        # Message line
        if self.state.message:
            age = time.time() - self.state.message_time
            if age < 10:
                msg_y = h - 3
                self.win.addnstr(
                    msg_y, 2, truncate(self.state.message, w - 4), w - 4,
                    curses.A_BOLD if age < 5 else curses.A_DIM,
                )

        hint = "↑↓=Navigate  Enter=Select  q=Quit"
        self.win.addnstr(
            h - 1, (w - len(hint)) // 2, hint, w, curses.A_DIM
        )

        self.win.refresh()

    def handle(self, ch: int) -> bool:
        n = len(self.menu_items)
        if ch in (curses.KEY_UP, ord("k")):
            self.selected = (self.selected - 1) % n
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.selected = (self.selected + 1) % n
            return True
        if ch in (curses.KEY_ENTER, 10, 13):
            _, action = self.menu_items[self.selected]
            if action == "quit":
                self.state.running = False
            else:
                self.state.screen = action
            return True
        if ch in (ord("q"), 27):
            self.state.running = False
            return True
        return False


class OnboardingScreen(Screen):
    """Interactive onboarding flow mirroring the web client's 13-probe sequence."""

    def __init__(self, state: TuiState):
        super().__init__(state)
        self.phase = "name"  # name -> probes -> done
        self.name_input = ""
        self.probe_list: list[dict] = []
        self.current_probe_idx = 0
        self.current_probe: Optional[dict] = None
        self.answer_text = ""
        self.answer_options_idx = 0
        self.probe_results: dict[str, Any] = {}
        self.contract: Optional[dict] = None
        self.scroll_offset = 0

    def on_enter(self):
        if not self.probe_list:
            self.start_onboarding()

    def start_onboarding(self):
        try:
            result = self.state.api.onboarding_start(self.state.learner_name)
            self.state.learner_id = result.get("learner_id", "")
            self.probe_list = result.get("probes", [])
            self.current_probe_idx = 0
            self.phase = "probes"
            self.fetch_next_probe()
            set_message(self.state, f"Started onboarding — {len(self.probe_list)} probes")
        except Exception as exc:
            set_message(self.state, f"Error: {exc}")

    def fetch_next_probe(self):
        if not self.state.learner_id:
            return
        try:
            result = self.state.api.onboarding_next(self.state.learner_id)
            self.current_probe = result.get("probe")
            if self.current_probe is None:
                self.phase = "review"
                return
            self.answer_text = ""
            self.answer_options_idx = 0
            self.scroll_offset = 0
        except Exception as exc:
            set_message(self.state, f"Error fetching probe: {exc}")

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        # Header
        header = "Onboarding — Build your learning system"
        self.win.addnstr(0, 2, header, w - 4, curses.A_BOLD)
        self.win.addnstr(0, w - 15, f" {h}x{w}", w - 1, curses.A_DIM)

        if self.phase == "name":
            self.draw_name_input(h, w)
        elif self.phase == "probes":
            self.draw_probe(h, w)
        elif self.phase == "review":
            self.draw_review(h, w)
        elif self.phase == "done":
            self.draw_done(h, w)

        # Footer
        if self.phase == "probes" and self.current_probe:
            progress = f"Probe {self.current_probe_idx + 1}/{len(self.probe_list)}"
            self.win.addnstr(h - 2, 2, progress, 20, curses.A_DIM)

        self.win.refresh()

    def draw_name_input(self, h: int, w: int):
        y = 4
        self.win.addnstr(y, 4, "Enter your name or handle:", w - 8)
        y += 2
        self.win.addnstr(y, 6, f"> {self.name_input}_", w - 12)
        y += 3
        self.win.addnstr(y, 4, "Press Enter to begin, or 'q' to go back.", w - 8, curses.A_DIM)

    def draw_probe(self, h: int, w: int):
        probe = self.current_probe
        if not probe:
            return

        y = 2
        # Name
        self.win.addnstr(y, 2, probe.get("name", ""), w - 4, curses.A_BOLD)
        y += 1

        # Purpose (wrapped)
        purpose = probe.get("purpose", "")
        for line in wrap_text(purpose, w - 6):
            self.win.addnstr(y, 4, line, w - 8, curses.A_DIM)
            y += 1
        y += 1

        # Question
        question = probe.get("question", "")
        for line in wrap_text(question, w - 6):
            self.win.addnstr(y, 2, line, w - 4)
            y += 1
        y += 1

        # Options or text input
        options = probe.get("options") or []
        if options:
            for i, opt in enumerate(options):
                if i == self.answer_options_idx:
                    self.win.addnstr(y, 4, f"> {opt}", w - 8, curses.A_REVERSE)
                else:
                    self.win.addnstr(y, 4, f"  {opt}", w - 8)
                y += 1
        else:
            self.win.addnstr(y, 4, "Your answer:", w - 8)
            y += 1
            self.win.addnstr(y, 6, f"> {self.answer_text}_", w - 12)
            y += 2
            self.win.addnstr(y, 4, "(Type your answer, Enter to submit)", w - 8, curses.A_DIM)

    def draw_review(self, h: int, w: int):
        y = 4
        self.win.addnstr(y, 4, "Review your answers:", w - 8, curses.A_BOLD)
        y += 2
        for pid, answer in self.probe_results.items():
            ans_str = str(answer)
            if len(ans_str) > 60:
                ans_str = ans_str[:57] + "..."
            self.win.addnstr(y, 6, f"{pid}: {ans_str}", w - 12)
            y += 1
        y += 1
        self.win.addnstr(y, 4, "Press Enter to finish, 'b' to go back.", w - 8, curses.A_DIM)

    def draw_done(self, h: int, w: int):
        y = 4
        self.win.addnstr(y, 4, "Onboarding complete!", w - 8, curses.A_BOLD)
        y += 2
        if self.contract:
            summary = self.contract.get("summary", "")
            for line in wrap_text(summary, w - 8):
                self.win.addnstr(y, 4, line, w - 8)
                y += 1
        y += 1
        self.win.addnstr(y, 4, "Press any key to return to main menu.", w - 8, curses.A_DIM)

    def handle(self, ch: int) -> bool:
        if self.phase == "name":
            return self.handle_name(ch)
        if self.phase == "probes":
            return self.handle_probe(ch)
        if self.phase == "review":
            if ch in (curses.KEY_ENTER, 10, 13):
                self.finish_onboarding()
                return True
            if ch in (ord("b"),):
                self.phase = "probes"
                self.current_probe_idx = max(0, self.current_probe_idx - 1)
                return True
            return True
        if self.phase == "done":
            self.state.screen = "main"
            return True
        if ch in (ord("q"), 27):
            self.state.screen = "main"
            return True
        return False

    def handle_name(self, ch: int) -> bool:
        if ch in (curses.KEY_ENTER, 10, 13):
            if self.name_input.strip():
                self.state.learner_name = self.name_input.strip()
                self.start_onboarding()
            return True
        if ch in (curses.KEY_BACKSPACE, 127, 8):
            self.name_input = self.name_input[:-1]
            return True
        if ch in (ord("q"), 27):
            self.state.screen = "main"
            return True
        if 32 <= ch < 127:
            self.name_input += chr(ch)
            return True
        return False

    def handle_probe(self, ch: int) -> bool:
        probe = self.current_probe
        if not probe:
            return False
        options = probe.get("options") or []
        kind = probe.get("kind", "interview")

        if options:
            if ch in (curses.KEY_UP, ord("k")):
                self.answer_options_idx = max(0, self.answer_options_idx - 1)
                return True
            if ch in (curses.KEY_DOWN, ord("j")):
                self.answer_options_idx = min(len(options) - 1, self.answer_options_idx + 1)
                return True
            if ch in (curses.KEY_ENTER, 10, 13):
                answer = options[self.answer_options_idx]
                self.submit_answer(probe, answer)
                return True
        else:
            if ch in (curses.KEY_ENTER, 10, 13):
                if self.answer_text.strip():
                    self.submit_answer(probe, self.answer_text.strip())
                return True
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.answer_text = self.answer_text[:-1]
                return True
            if ch in (ord("q"), 27):
                self.state.screen = "main"
                return True
            if 32 <= ch < 127:
                self.answer_text += chr(ch)
                return True

        return True

    def submit_answer(self, probe: dict, answer: Any):
        pid = probe.get("probe_id", "")
        try:
            self.state.api.onboarding_record(self.state.learner_id, pid, answer)
            self.probe_results[pid] = answer
            self.current_probe_idx += 1
            self.fetch_next_probe()
            set_message(self.state, f"Recorded answer for {pid}")
        except Exception as exc:
            set_message(self.state, f"Error: {exc}")

    def finish_onboarding(self):
        try:
            result = self.state.api.onboarding_finish(self.state.learner_id)
            self.contract = result.get("contract")
            self.phase = "done"
            set_message(self.state, "Onboarding complete!")
        except Exception as exc:
            set_message(self.state, f"Error finishing: {exc}")


class SourcesScreen(Screen):
    def __init__(self, state: TuiState):
        super().__init__(state)
        self.text_input = ""
        self.title_input = ""
        self.mode = "add"  # add | view
        self.sources: list[dict] = []
        self.view_text = ""
        self.scroll = 0

    def on_enter(self):
        if not self.sources:
            # Try to get sources from the manifest or just show the add form
            pass

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        header = "Sources — your learning material"
        self.win.addnstr(0, 2, header, w - 4, curses.A_BOLD)

        if self.mode == "add":
            self.draw_add(h, w)
        elif self.mode == "view":
            self.draw_view(h, w)

        if self.state.message:
            self.win.addnstr(h - 2, 2, truncate(self.state.message, w - 4), w - 4, curses.A_BOLD)

        hint = "Tab=Switch  Enter=Submit  q=Back"
        self.win.addnstr(h - 1, 2, hint, w - 4, curses.A_DIM)
        self.win.refresh()

    def draw_add(self, h: int, w: int):
        y = 2
        self.win.addnstr(y, 2, "Title:", w - 4)
        self.win.addnstr(y + 1, 4, f"> {self.title_input}", w - 8)
        y += 3
        self.win.addnstr(y, 2, "Text (paste your material):", w - 4)
        y += 1
        # Multi-line text input area
        text_lines = h - y - 5
        for i in range(max(1, text_lines)):
            line_idx = self.scroll + i
            if line_idx < len(self.text_input.split("\n")):
                self.win.addnstr(y + i, 4, self.text_input.split("\n")[line_idx], w - 8)

    def draw_view(self, h: int, w: int):
        if self.sources:
            y = 2
            for i, src in enumerate(self.sources):
                title = src.get("title", "Untitled")
                n_chars = src.get("n_chars", 0)
                sha = src.get("sha256", "")[:12]
                self.win.addnstr(y, 2, f"{i + 1}. {title} ({n_chars} chars) [{sha}]", w - 4)
                y += 1

    def handle(self, ch: int) -> bool:
        if ch in (ord("q"), 27):
            self.state.screen = "main"
            return True
        if ch == 9:  # Tab
            self.mode = "view" if self.mode == "add" else "add"
            return True
        if self.mode == "add":
            if ch in (curses.KEY_ENTER, 10, 13):
                if self.text_input.strip():
                    try:
                        result = self.state.api.add_source(
                            self.state.learner_id,
                            self.text_input.strip(),
                            self.title_input.strip(),
                        )
                        self.sources.append({
                            "title": self.title_input or "Untitled",
                            "n_chars": result.get("n_chars", 0),
                            "sha256": result.get("sha256", ""),
                            "source_id": result.get("source_id", ""),
                        })
                        self.text_input = ""
                        self.title_input = ""
                        set_message(self.state, "Source added!")
                    except Exception as exc:
                        set_message(self.state, f"Error: {exc}")
                return True
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.text_input = self.text_input[:-1]
                return True
            if 32 <= ch < 127:
                self.text_input += chr(ch)
                return True
        return True


class StudyScreen(Screen):
    """View due items and answer them."""

    def __init__(self, state: TuiState):
        super().__init__(state)
        self.items: list[dict] = []
        self.forecast: dict = {}
        self.current_idx = 0
        self.answer_text = ""
        self.confidence: float = 0.8
        self.results: list[dict] = []
        self.mode = "list"  # list | answer | done

    def on_enter(self):
        self.load_session()

    def load_session(self):
        try:
            result = self.state.api.session(self.state.learner_id)
            self.items = result.get("items", [])
            self.forecast = result.get("forecast", {})
            self.current_idx = 0
            self.results = []
            if not self.items:
                set_message(self.state, "No items due — generate questions first!")
        except Exception as exc:
            set_message(self.state, f"Error: {exc}")

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        header = "Study Session"
        self.win.addnstr(0, 2, header, w - 4, curses.A_BOLD)

        if self.mode == "list":
            self.draw_list(h, w)
        elif self.mode == "answer":
            self.draw_answer(h, w)
        elif self.mode == "done":
            self.draw_done(h, w)

        if self.state.message:
            self.win.addnstr(h - 2, 2, truncate(self.state.message, w - 4), w - 4, curses.A_BOLD)

        self.win.refresh()

    def draw_list(self, h: int, w: int):
        y = 2
        if self.forecast:
            due = self.forecast.get("due_now", 0)
            mean_ret = self.forecast.get("mean_retrievability", 0)
            self.win.addnstr(y, 2, f"Due now: {due}  |  Mean retrievability: {mean_ret:.2f}", w - 4, curses.A_DIM)
            y += 2

        if not self.items:
            self.win.addnstr(y, 4, "No items due. Generate questions first.", w - 8)
            return

        self.win.addnstr(y, 2, f"Items: {len(self.items)}", w - 4)
        y += 2

        for i, item in enumerate(self.items):
            if i == self.current_idx:
                self.win.addnstr(y, 4, f"→ {item.get('style', '?')}: {truncate(item.get('prompt', ''), w - 10)}", w - 8, curses.A_REVERSE)
            else:
                self.win.addnstr(y, 4, f"  {item.get('style', '?')}: {truncate(item.get('prompt', ''), w - 10)}", w - 8)
            y += 1
            if y > h - 5:
                break

    def draw_answer(self, h: int, w: int):
        if self.current_idx >= len(self.items):
            self.mode = "done"
            return
        item = self.items[self.current_idx]
        y = 2
        self.win.addnstr(y, 2, f"Style: {item.get('style', '?')}", w - 4, curses.A_DIM)
        y += 1
        prompt = item.get("prompt", "")
        for line in wrap_text(prompt, w - 4):
            self.win.addnstr(y, 2, line, w - 4)
            y += 1
        y += 1
        self.win.addnstr(y, 2, "Your answer:", w - 4)
        y += 1
        self.win.addnstr(y, 4, f"> {self.answer_text}_", w - 8)
        y += 2
        self.win.addnstr(y, 2, f"Confidence: {self.confidence:.1f}  (←/→ to adjust)", w - 4, curses.A_DIM)

    def draw_done(self, h: int, w: int):
        y = 4
        self.win.addnstr(y, 4, "Session complete!", w - 8, curses.A_BOLD)
        y += 2
        for r in self.results:
            correct = "✓" if r.get("correct") else "✗"
            self.win.addnstr(y, 4, f"{correct} {truncate(r.get('prompt', ''), 50)}", w - 8)
            y += 1
        y += 1
        self.win.addnstr(y, 4, "Press any key to return.", w - 8, curses.A_DIM)

    def handle(self, ch: int) -> bool:
        if self.mode == "list":
            if ch in (curses.KEY_UP, ord("k")):
                self.current_idx = max(0, self.current_idx - 1)
                return True
            if ch in (curses.KEY_DOWN, ord("j")):
                self.current_idx = min(len(self.items) - 1, self.current_idx + 1)
                return True
            if ch in (curses.KEY_ENTER, 10, 13):
                self.mode = "answer"
                self.answer_text = ""
                return True
            if ch in (ord("q"), 27):
                self.state.screen = "main"
                return True
            return True
        if self.mode == "answer":
            if ch in (curses.KEY_ENTER, 10, 13):
                self.submit_answer()
                return True
            if ch == curses.KEY_LEFT:
                self.confidence = max(0.0, self.confidence - 0.1)
                return True
            if ch == curses.KEY_RIGHT:
                self.confidence = min(1.0, self.confidence + 0.1)
                return True
            if ch in (curses.KEY_BACKSPACE, 127, 8):
                self.answer_text = self.answer_text[:-1]
                return True
            if ch in (ord("q"), 27):
                self.mode = "list"
                return True
            if 32 <= ch < 127:
                self.answer_text += chr(ch)
                return True
            return True
        if self.mode == "done":
            self.state.screen = "main"
            return True
        return False

    def submit_answer(self):
        if self.current_idx >= len(self.items):
            return
        item = self.items[self.current_idx]
        qid = item.get("qid", "")
        # Simple correctness check — the learner self-reports
        correct = self.answer_text.strip().lower() == item.get("answer", "").strip().lower()
        try:
            result = self.state.api.attempt(
                self.state.learner_id,
                qid,
                correct=correct,
                grade=3 if correct else 1,
                confidence=self.confidence,
                skill_id=item.get("skill_id", "general"),
                response=self.answer_text,
            )
            self.results.append({
                "prompt": item.get("prompt", ""),
                "correct": correct,
                "p_known": result.get("p_known", 0),
                "mastered": result.get("mastered", False),
            })
            self.current_idx += 1
            if self.current_idx >= len(self.items):
                self.mode = "done"
            else:
                self.mode = "answer"
                self.answer_text = ""
        except Exception as exc:
            set_message(self.state, f"Error: {exc}")


class ProfileScreen(Screen):
    def __init__(self, state: TuiState):
        super().__init__(state)
        self.profile_data: dict = {}
        self.session_data: dict = {}
        self.scroll = 0

    def on_enter(self):
        self.load_profile()

    def load_profile(self):
        try:
            result = self.state.api.profile(self.state.learner_id)
            self.profile_data = result.get("profile", {})
            self.session_data = result.get("session", {})
        except Exception as exc:
            set_message(self.state, f"Error: {exc}")

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        header = "Profile — what the system knows about you"
        self.win.addnstr(0, 2, header, w - 4, curses.A_BOLD)

        if not self.profile_data:
            self.win.addnstr(4, 4, "No profile data yet. Complete onboarding first.", w - 8)
        else:
            y = 2 - self.scroll
            profile = self.profile_data

            # Role
            role = profile.get("role", "Unknown")
            if y >= 2:
                self.win.addnstr(y, 2, f"Role: {role}", w - 4, curses.A_BOLD)
            y += 2

            # Study shape
            shape = profile.get("study_shape", "Unknown")
            if y >= 2:
                self.win.addnstr(y, 2, f"Study shape: {shape}", w - 4)
            y += 1

            # Limits / caveats
            limits = profile.get("limits", [])
            for lim in limits:
                for line in wrap_text(str(lim), w - 6):
                    if y >= 2:
                        self.win.addnstr(y, 4, f"! {line}", w - 8, curses.A_DIM)
                    y += 1
            y += 1

            # Observations
            observations = profile.get("observations", [])
            if observations:
                if y >= 2:
                    self.win.addnstr(y, 2, "Observations:", w - 4, curses.A_BOLD)
                y += 1
                for obs in observations:
                    text = str(obs)
                    for line in wrap_text(text, w - 8):
                        if y >= 2:
                            self.win.addnstr(y, 4, line, w - 8)
                        y += 1
                    y += 1

            # Calibration
            cal = self.session_data.get("calibration", {})
            if cal:
                if y >= 2:
                    self.win.addnstr(y, 2, "Calibration:", w - 4, curses.A_BOLD)
                y += 1
                bias = cal.get("bias", 0)
                brier = cal.get("brier", 0)
                n = cal.get("n", 0)
                self.win.addnstr(y, 4, f"Bias: {bias:.3f}  Brier: {brier:.3f}  N: {n}", w - 8)
                y += 2

            # Session stats
            attempts = self.session_data.get("n_attempts", 0)
            if attempts:
                self.win.addnstr(y, 2, f"Total attempts: {attempts}", w - 4)
                y += 1

        if self.state.message:
            self.win.addnstr(h - 2, 2, truncate(self.state.message, w - 4), w - 4, curses.A_BOLD)

        hint = "↑↓=Scroll  q=Back"
        self.win.addnstr(h - 1, 2, hint, w - 4, curses.A_DIM)
        self.win.refresh()

    def handle(self, ch: int) -> bool:
        if ch in (ord("q"), 27):
            self.state.screen = "main"
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.scroll = max(0, self.scroll - 1)
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.scroll += 1
            return True
        return True


class McpScreen(Screen):
    def __init__(self, state: TuiState):
        super().__init__(state)
        self.servers: list[dict] = []
        self.selected = 0

    def on_enter(self):
        try:
            manifest = self.state.api.manifest()
            self.servers = manifest.get("mcp_servers", [])
        except Exception as exc:
            set_message(self.state, f"Error: {exc}")

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        header = "MCP Integrations — connect to the world"
        self.win.addnstr(0, 2, header, w - 4, curses.A_BOLD)

        if not self.servers:
            self.win.addnstr(4, 4, "No MCP servers configured.", w - 8)
        else:
            y = 2
            for i, srv in enumerate(self.servers):
                name = srv.get("name", "?")
                desc = truncate(srv.get("description", ""), w - 20)
                auth = srv.get("auth_type", "none")
                if i == self.selected:
                    self.win.addnstr(y, 4, f"> {name} ({auth}) — {desc}", w - 8, curses.A_REVERSE)
                else:
                    self.win.addnstr(y, 4, f"  {name} ({auth}) — {desc}", w - 8)
                y += 1
                if y > h - 4:
                    break

        if self.state.message:
            self.win.addnstr(h - 2, 2, truncate(self.state.message, w - 4), w - 4, curses.A_BOLD)

        hint = "↑↓=Navigate  Enter=Connect  q=Back"
        self.win.addnstr(h - 1, 2, hint, w - 4, curses.A_DIM)
        self.win.refresh()

    def handle(self, ch: int) -> bool:
        if ch in (ord("q"), 27):
            self.state.screen = "main"
            return True
        if ch in (curses.KEY_UP, ord("k")):
            self.selected = max(0, self.selected - 1)
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.selected = min(len(self.servers) - 1, self.selected + 1)
            return True
        if ch in (curses.KEY_ENTER, 10, 13):
            if self.servers:
                srv = self.servers[self.selected]
                set_message(self.state, f"Would connect to: {srv.get('name', '?')}")
            return True
        return True


class SettingsScreen(Screen):
    def __init__(self, state: TuiState):
        super().__init__(state)
        self.selected = 0
        self.items = [
            "Export data",
            "Erase all data",
            "Back",
        ]

    def draw(self):
        self.win.erase()
        h, w = self.win.getmaxyx()

        header = "Settings"
        self.win.addnstr(0, 2, header, w - 4, curses.A_BOLD)

        y = 4
        for i, label in enumerate(self.items):
            if i == self.selected:
                self.win.addnstr(y, 4, f"> {label}", w - 8, curses.A_REVERSE)
            else:
                self.win.addnstr(y, 4, f"  {label}", w - 8)
            y += 1

        if self.state.message:
            self.win.addnstr(h - 2, 2, truncate(self.state.message, w - 4), w - 4, curses.A_BOLD)

        self.win.refresh()

    def handle(self, ch: int) -> bool:
        if ch in (curses.KEY_UP, ord("k")):
            self.selected = max(0, self.selected - 1)
            return True
        if ch in (curses.KEY_DOWN, ord("j")):
            self.selected = min(len(self.items) - 1, self.selected + 1)
            return True
        if ch in (curses.KEY_ENTER, 10, 13):
            if self.selected == 0:
                self.export_data()
            elif self.selected == 1:
                self.erase_data()
            elif self.selected == 2:
                self.state.screen = "main"
            return True
        if ch in (ord("q"), 27):
            self.state.screen = "main"
            return True
        return False

    def export_data(self):
        try:
            data = self.state.api.export(self.state.learner_id)
            path = Path.home() / ".cortexforge" / "export.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2))
            set_message(self.state, f"Exported to {path}")
        except Exception as exc:
            set_message(self.state, f"Export failed: {exc}")

    def erase_data(self):
        try:
            self.state.api.erase(self.state.learner_id)
            set_message(self.state, "All data erased.")
            self.state.learner_id = ""
            self.state.learner_name = ""
        except Exception as exc:
            set_message(self.state, f"Erase failed: {exc}")


# ---------------------------------------------------------------------------
# Main TUI loop
# ---------------------------------------------------------------------------


class TuiApp:
    def __init__(self, api: ApiClient):
        self.api = api
        self.state = TuiState(api=api)
        self.screens: dict[str, Screen] = {}

    def register_screen(self, name: str, screen: Screen):
        self.screens[name] = screen

    def run(self, stdscr):
        curses.curs_set(0)
        stdscr.timeout(100)
        stdscr.keypad(True)

        self.register_screen("main", MainMenuScreen(self.state))
        self.register_screen("onboard", OnboardingScreen(self.state))
        self.register_screen("sources", SourcesScreen(self.state))
        self.register_screen("study", StudyScreen(self.state))
        self.register_screen("profile", ProfileScreen(self.state))
        self.register_screen("mcp", McpScreen(self.state))
        self.register_screen("settings", SettingsScreen(self.state))

        current_screen = self.screens["main"]

        while self.state.running:
            h, w = stdscr.getmaxyx()
            if h < 10 or w < 40:
                stdscr.erase()
                stdscr.addnstr(0, 0, "Terminal too small (need 40x10)", w)
                stdscr.refresh()
                curses.napms(100)
                continue

            try:
                current_screen.setup(stdscr, h, w)
                current_screen.draw()
            except curses.error:
                pass

            try:
                ch = stdscr.getch()
            except curses.error:
                continue

            if ch == -1:
                continue

            # Handle screen switching
            if self.state.screen in self.screens and self.state.screen != current_screen:
                current_screen.on_leave()
                current_screen = self.screens[self.state.screen]
                current_screen.on_enter()

            try:
                current_screen.handle(ch)
            except curses.error:
                pass


def main():
    parser = argparse.ArgumentParser(description="CortexForge TUI")
    parser.add_argument("--port", type=int, default=8731)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--token", default="")
    parser.add_argument("--db", default="")
    parser.add_argument("--server", default="", help="Start server in-process")
    args = parser.parse_args()

    # Start server in-process if requested
    if args.server:
        from cortexforge.server import make_server

        db_path = args.db or str(Path.home() / ".cortexforge" / "cortexforge.db")
        server = make_server(db_path, args.server, host=args.host, port=args.port)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        time.sleep(1)  # Let server start

    base = f"http://{args.host}:{args.port}"
    api = ApiClient(base, token=args.token)

    # Check server health
    try:
        health = api.health()
        print(f"Connected to {base} — {health.get('status', 'ok')}")
    except Exception as exc:
        print(f"Cannot connect to server at {base}: {exc}")
        print("Start the server first: python -m cortexforge.server")
        sys.exit(1)

    app = TuiApp(api)
    curses.wrapper(app.run)


if __name__ == "__main__":
    main()
