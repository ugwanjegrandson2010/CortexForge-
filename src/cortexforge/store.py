"""Local persistence for CortexForge — SQLite, parameterised only.

Every statement goes through assert_parameterised() before execution, so an
f-string or %-interpolation cannot slip in unnoticed. The database is a
single local file; there is no network database and no ORM.

Tables
    learner        one row per learner profile
    source         ingested documents (text stored, path recorded)
    question       generated items with provenance
    attempt        every response, with latency and confidence
    skill_state    BKT parameters and current mastery per skill
    card           FSRS scheduling state per question
    profile        computed behavioural profile snapshots
    event          append-only audit log
"""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .security import assert_parameterised, load_json_only, sanitise_text

SCHEMA_VERSION = 1

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS learner (
    learner_id  TEXT PRIMARY KEY,
    display     TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL,
    settings    TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS source (
    source_id   TEXT PRIMARY KEY,
    learner_id  TEXT NOT NULL,
    title       TEXT NOT NULL DEFAULT '',
    origin_path TEXT NOT NULL DEFAULT '',
    sha256      TEXT NOT NULL,
    n_chars     INTEGER NOT NULL DEFAULT 0,
    text        TEXT NOT NULL,
    created_at  REAL NOT NULL,
    FOREIGN KEY (learner_id) REFERENCES learner(learner_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_source_learner ON source(learner_id);

CREATE TABLE IF NOT EXISTS question (
    qid          TEXT PRIMARY KEY,
    learner_id   TEXT NOT NULL,
    source_id    TEXT NOT NULL DEFAULT '',
    style        TEXT NOT NULL,
    bloom        TEXT NOT NULL DEFAULT 'remember',
    prompt       TEXT NOT NULL,
    answer       TEXT NOT NULL DEFAULT '',
    source_span  TEXT NOT NULL DEFAULT '',
    skill_id     TEXT NOT NULL DEFAULT 'general',
    grading      TEXT NOT NULL DEFAULT 'exact',
    requires_llm INTEGER NOT NULL DEFAULT 0,
    difficulty   REAL NOT NULL DEFAULT 0.0,
    meta         TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    FOREIGN KEY (learner_id) REFERENCES learner(learner_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_question_learner ON question(learner_id);
CREATE INDEX IF NOT EXISTS idx_question_skill ON question(skill_id);

CREATE TABLE IF NOT EXISTS attempt (
    attempt_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  TEXT NOT NULL,
    qid         TEXT NOT NULL,
    skill_id    TEXT NOT NULL DEFAULT 'general',
    correct     INTEGER NOT NULL,
    score       REAL NOT NULL DEFAULT 0.0,
    latency_ms  INTEGER NOT NULL DEFAULT 0,
    confidence  REAL,
    response    TEXT NOT NULL DEFAULT '',
    day         REAL NOT NULL,
    created_at  REAL NOT NULL,
    FOREIGN KEY (learner_id) REFERENCES learner(learner_id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_attempt_learner ON attempt(learner_id, day);

CREATE TABLE IF NOT EXISTS skill_state (
    learner_id  TEXT NOT NULL,
    skill_id    TEXT NOT NULL,
    p_known     REAL NOT NULL DEFAULT 0.2,
    p_l0        REAL NOT NULL DEFAULT 0.2,
    p_t         REAL NOT NULL DEFAULT 0.15,
    p_s         REAL NOT NULL DEFAULT 0.1,
    p_g         REAL NOT NULL DEFAULT 0.2,
    opportunities INTEGER NOT NULL DEFAULT 0,
    correct     INTEGER NOT NULL DEFAULT 0,
    updated_at  REAL NOT NULL,
    PRIMARY KEY (learner_id, skill_id)
);

CREATE TABLE IF NOT EXISTS card (
    learner_id  TEXT NOT NULL,
    qid         TEXT NOT NULL,
    stability   REAL NOT NULL DEFAULT 0.0,
    difficulty  REAL NOT NULL DEFAULT 0.0,
    reps        INTEGER NOT NULL DEFAULT 0,
    lapses      INTEGER NOT NULL DEFAULT 0,
    last_day    REAL NOT NULL DEFAULT 0.0,
    due_day     REAL NOT NULL DEFAULT 0.0,
    state       TEXT NOT NULL DEFAULT 'new',
    PRIMARY KEY (learner_id, qid)
);
CREATE INDEX IF NOT EXISTS idx_card_due ON card(learner_id, due_day);

CREATE TABLE IF NOT EXISTS profile (
    profile_id  INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  TEXT NOT NULL,
    kind        TEXT NOT NULL,
    payload     TEXT NOT NULL,
    created_at  REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_profile_learner ON profile(learner_id, kind);

CREATE TABLE IF NOT EXISTS event (
    event_id    INTEGER PRIMARY KEY AUTOINCREMENT,
    learner_id  TEXT NOT NULL DEFAULT '',
    kind        TEXT NOT NULL,
    detail      TEXT NOT NULL DEFAULT '',
    created_at  REAL NOT NULL
);
"""


class Store:
    """Thin, explicit SQLite wrapper. All queries are parameterised.

    Threading: ThreadingHTTPServer serves each request on its own thread, and
    a sqlite3.Connection may only be used by the thread that created it. The
    store therefore keeps one connection *per thread* (thread-local), all
    pointing at the same database file. WAL mode is enabled so concurrent
    readers and a single writer do not block each other.
    """

    def __init__(self, path: str | Path):
        self.path = str(path)
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._all_conns: list[sqlite3.Connection] = []
        self._init_lock = threading.Lock()
        # Create the schema once on the constructing thread.
        self._conn  # noqa: B018  (triggers connection + schema creation)

    @property
    def _conn(self) -> sqlite3.Connection:
        """Return this thread's connection, creating and migrating it once."""
        conn = getattr(self._local, "conn", None)
        if conn is not None:
            return conn
        conn = sqlite3.connect(self.path, isolation_level=None, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.executescript(SCHEMA)
        conn.execute(
            "INSERT OR IGNORE INTO meta(key, value) VALUES (?, ?)",
            ("schema_version", str(SCHEMA_VERSION)))
        self._local.conn = conn
        with self._init_lock:
            self._all_conns.append(conn)
        return conn

    # -- plumbing --------------------------------------------------------
    def _exec(self, sql: str, params: tuple = ()) -> sqlite3.Cursor:
        assert_parameterised(sql, params)
        return self._conn.execute(sql, params)

    def _query(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        return self._exec(sql, params).fetchall()

    def _one(self, sql: str, params: tuple = ()) -> sqlite3.Row | None:
        rows = self._query(sql, params)
        return rows[0] if rows else None

    @contextmanager
    def transaction(self) -> Iterator[None]:
        conn = self._conn
        conn.execute("BEGIN IMMEDIATE")
        try:
            yield
        except Exception:
            conn.execute("ROLLBACK")
            raise
        else:
            conn.execute("COMMIT")

    def close(self) -> None:
        """Close every per-thread connection this store opened."""
        with self._init_lock:
            conns, self._all_conns = self._all_conns, []
        for c in conns:
            try:
                c.close()
            except sqlite3.Error:
                pass
        self._local = threading.local()

    # -- learner ---------------------------------------------------------
    def upsert_learner(self, learner_id: str, display: str = "",
                       settings: dict | None = None) -> None:
        self._exec(
            "INSERT INTO learner(learner_id, display, created_at, settings) "
            "VALUES (?, ?, ?, ?) "
            "ON CONFLICT(learner_id) DO UPDATE SET display=excluded.display, "
            "settings=excluded.settings",
            (learner_id, sanitise_text(display, 200), time.time(),
             json.dumps(settings or {}, separators=(",", ":"))))

    def get_learner(self, learner_id: str) -> dict | None:
        row = self._one("SELECT * FROM learner WHERE learner_id = ?",
                        (learner_id,))
        if not row:
            return None
        d = dict(row)
        d["settings"] = load_json_only(d["settings"])
        return d

    # -- sources ---------------------------------------------------------
    def add_source(self, source_id: str, learner_id: str, title: str,
                   origin_path: str, sha256: str, text: str) -> None:
        self._exec(
            "INSERT OR REPLACE INTO source(source_id, learner_id, title, "
            "origin_path, sha256, n_chars, text, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (source_id, learner_id, sanitise_text(title, 500),
             sanitise_text(origin_path, 1000), sha256, len(text), text,
             time.time()))

    def list_sources(self, learner_id: str) -> list[dict]:
        return [dict(r) for r in self._query(
            "SELECT source_id, title, origin_path, sha256, n_chars, created_at "
            "FROM source WHERE learner_id = ? ORDER BY created_at DESC",
            (learner_id,))]

    def get_source_text(self, source_id: str) -> str | None:
        row = self._one("SELECT text FROM source WHERE source_id = ?",
                        (source_id,))
        return row["text"] if row else None

    # -- questions -------------------------------------------------------
    def add_questions(self, learner_id: str, questions: list) -> int:
        now = time.time()
        n = 0
        with self.transaction():
            for q in questions:
                if getattr(q, "style", "") == "provenance":
                    continue
                self._exec(
                    "INSERT OR REPLACE INTO question(qid, learner_id, "
                    "source_id, style, bloom, prompt, answer, source_span, "
                    "skill_id, grading, requires_llm, difficulty, meta, "
                    "created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (q.qid, learner_id, getattr(q, "source_id", ""), q.style,
                     q.bloom, q.prompt, q.answer, q.source_span, q.skill_id,
                     q.grading, 1 if q.requires_llm else 0,
                     float(q.difficulty_hint),
                     json.dumps(q.meta, separators=(",", ":")), now))
                self._exec(
                    "INSERT OR IGNORE INTO card(learner_id, qid) VALUES (?, ?)",
                    (learner_id, q.qid))
                n += 1
        return n

    def list_questions(self, learner_id: str, skill_id: str | None = None,
                       limit: int = 500) -> list[dict]:
        if skill_id:
            rows = self._query(
                "SELECT * FROM question WHERE learner_id = ? AND skill_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (learner_id, skill_id, int(limit)))
        else:
            rows = self._query(
                "SELECT * FROM question WHERE learner_id = ? "
                "ORDER BY created_at DESC LIMIT ?",
                (learner_id, int(limit)))
        out = []
        for r in rows:
            d = dict(r)
            d["meta"] = load_json_only(d["meta"])
            out.append(d)
        return out

    def count_questions(self, learner_id: str) -> int:
        row = self._one("SELECT COUNT(*) AS n FROM question WHERE learner_id = ?",
                        (learner_id,))
        return int(row["n"]) if row else 0

    # -- attempts --------------------------------------------------------
    def add_attempt(self, learner_id: str, qid: str, skill_id: str,
                    correct: bool, score: float, latency_ms: int,
                    confidence: float | None, response: str, day: float) -> int:
        cur = self._exec(
            "INSERT INTO attempt(learner_id, qid, skill_id, correct, score, "
            "latency_ms, confidence, response, day, created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (learner_id, qid, skill_id, 1 if correct else 0, float(score),
             int(latency_ms), confidence, sanitise_text(response, 8000),
             float(day), time.time()))
        return int(cur.lastrowid or 0)

    def attempts(self, learner_id: str, limit: int = 1000) -> list[dict]:
        return [dict(r) for r in self._query(
            "SELECT * FROM attempt WHERE learner_id = ? "
            "ORDER BY attempt_id DESC LIMIT ?", (learner_id, int(limit)))]

    # -- skill state -----------------------------------------------------
    def upsert_skill(self, learner_id: str, skill_id: str, p_known: float,
                     params: dict, opportunities: int, correct: int) -> None:
        self._exec(
            "INSERT INTO skill_state(learner_id, skill_id, p_known, p_l0, "
            "p_t, p_s, p_g, opportunities, correct, updated_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(learner_id, skill_id) DO UPDATE SET "
            "p_known=excluded.p_known, opportunities=excluded.opportunities, "
            "correct=excluded.correct, updated_at=excluded.updated_at",
            (learner_id, skill_id, float(p_known), float(params["p_L0"]),
             float(params["p_T"]), float(params["p_S"]), float(params["p_G"]),
             int(opportunities), int(correct), time.time()))

    def skill_states(self, learner_id: str) -> list[dict]:
        return [dict(r) for r in self._query(
            "SELECT * FROM skill_state WHERE learner_id = ? "
            "ORDER BY p_known ASC", (learner_id,))]

    # -- cards -----------------------------------------------------------
    def upsert_card(self, learner_id: str, card) -> None:
        self._exec(
            "INSERT INTO card(learner_id, qid, stability, difficulty, reps, "
            "lapses, last_day, due_day, state) VALUES (?,?,?,?,?,?,?,?,?) "
            "ON CONFLICT(learner_id, qid) DO UPDATE SET "
            "stability=excluded.stability, difficulty=excluded.difficulty, "
            "reps=excluded.reps, lapses=excluded.lapses, "
            "last_day=excluded.last_day, due_day=excluded.due_day, "
            "state=excluded.state",
            (learner_id, card.item_id, float(card.stability),
             float(card.difficulty), int(card.reps), int(card.lapses),
             float(card.last_review_day), float(card.due_day), card.state))

    def cards(self, learner_id: str) -> list[dict]:
        return [dict(r) for r in self._query(
            "SELECT * FROM card WHERE learner_id = ?", (learner_id,))]

    # -- profiles --------------------------------------------------------
    def save_profile(self, learner_id: str, kind: str, payload: dict) -> None:
        self._exec(
            "INSERT INTO profile(learner_id, kind, payload, created_at) "
            "VALUES (?,?,?,?)",
            (learner_id, kind,
             json.dumps(payload, separators=(",", ":"), default=str),
             time.time()))

    def latest_profile(self, learner_id: str, kind: str) -> dict | None:
        row = self._one(
            "SELECT payload FROM profile WHERE learner_id = ? AND kind = ? "
            "ORDER BY profile_id DESC LIMIT 1", (learner_id, kind))
        return load_json_only(row["payload"]) if row else None

    # -- audit -----------------------------------------------------------
    def log_event(self, kind: str, detail: str = "",
                  learner_id: str = "") -> None:
        self._exec(
            "INSERT INTO event(learner_id, kind, detail, created_at) "
            "VALUES (?,?,?,?)",
            (learner_id, sanitise_text(kind, 100),
             sanitise_text(detail, 2000), time.time()))

    def events(self, limit: int = 200) -> list[dict]:
        return [dict(r) for r in self._query(
            "SELECT * FROM event ORDER BY event_id DESC LIMIT ?", (int(limit),))]

    # -- export / erase (GDPR-style rights) ------------------------------
    def export_learner(self, learner_id: str) -> dict:
        return {
            "learner": self.get_learner(learner_id),
            "sources": self.list_sources(learner_id),
            "questions": self.list_questions(learner_id, limit=100000),
            "attempts": self.attempts(learner_id, limit=1000000),
            "skills": self.skill_states(learner_id),
            "cards": self.cards(learner_id),
            "events": [e for e in self.events(100000)
                       if e["learner_id"] == learner_id],
        }

    def erase_learner(self, learner_id: str) -> None:
        with self.transaction():
            for table in ("attempt", "card", "skill_state", "question",
                          "source", "profile", "event"):
                self._exec(f"DELETE FROM {table} WHERE learner_id = ?",
                           (learner_id,))
            self._exec("DELETE FROM learner WHERE learner_id = ?",
                       (learner_id,))
