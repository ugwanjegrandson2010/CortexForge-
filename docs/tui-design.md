# CortexForge TUI — Design Document

**Version:** 1.0
**Date:** 2026-10-18
**Platform:** Python 3.11+ · Terminal (80×24 minimum, responsive) · `http://127.0.0.1:8731`
**Design Philosophy:** Neurodesign — minimal chrome, one primary action per screen, dual-coded content, calm palette, keyboard-first. Mirrors the web UI's IA but optimizes for terminal constraints (no mouse-first assumption, no infinite scroll, chunked views).

---

## Table of Contents

1. [Technology Stack](#1-technology-stack)
2. [Architecture Overview](#2-architecture-overview)
3. [Module Structure](#3-module-structure)
4. [Data Models & API Mapping](#4-data-models--api-mapping)
5. [Design Tokens & Theming](#5-design-tokens--theming)
6. [Key Bindings](#6-key-bindings)
7. [Screen-by-Screen Layouts](#7-screen-by-screen-layouts)
   - 7.1 Splash / Health Check
   - 7.2 Auth (Login / Register / Reset)
   - 7.3 Onboarding (13 Probes)
   - 7.4 Dashboard
   - 7.5 Study Session (FSRS)
   - 7.6 Profile (Observations)
   - 7.7 Sources (List + Add + Generate)
   - 7.8 Tutor Dialogue
   - 7.9 Molecule Viewer (ASCII Molecular Visualization)
   - 7.10 Settings
8. [ASCII Molecular Visualization](#8-ascii-molecular-visualization)
9. [Code Patterns](#9-code-patterns)
10. [Error Handling & Resilience](#10-error-handling--resilience)
11. [State Machine & Navigation](#11-state-machine--navigation)
12. [Accessibility & Ergonomics](#12-accessibility--ergonomics)
13. [Testing Strategy](#13-testing-strategy)
14. [Implementation Roadmap](#14-implementation-roadmap)

---

## 1. Technology Stack

### Primary: **Textual** (recommended)

`textual` is a modern TUI framework built on `rich`. It gives us a DOM-like widget tree, CSS-like styling, an async message-passing event loop, and a screen stack — everything a multi-screen app needs, without hand-rolling curses internals.

| Concern | Library | Why |
|---|---|---|
| **TUI framework** | `textual` ≥ 0.86 | Widget tree, screen stack, async events, CSS-like styles, live bindings. 10× less boilerplate than curses. |
| **Rendering / primitives** | `rich` ≥ 13 | `Panel`, `Table`, `Bar` (progress), `Text` with spans, `Columns`, `Syntax`, `Markdown`. Used directly for custom widgets and fallback rendering. |
| **HTTP client** | `httpx` ≥ 0.27 | Async, `Client` with base_url + default headers, timeouts, transparent JSON. Matches the async event loop. |
| **Data models** | `pydantic` ≥ 2 | Request/response validation, serialization, type safety. Models mirror the server's dict shapes. |
| **Local persistence** | `tomllib` / `tomli-w` | Stdlib (3.11+) read + `tomli-w` write for the TUI config (`~/.cortexforge/tui.toml`). Token cached here. |
| **Terminal detection** | `shutil.get_terminal_size`, `os.environ` | Responsive layout, color-depth detection (`COLORTERM`, `TERM`). |

### Fallback: raw `curses`

If `textual` is unavailable (e.g. restricted environment), the same architecture works on `curses`:
- Screens become functions that take `stdscr` and draw with `addstr` / `panel`.
- An event loop maps `getch()` to the same `Action` enum used by Textual message handlers.
- Progress bars drawn with `rich.bar` or manual `█▓░` blocks.
- The API client is shared verbatim (it has no UI dependency).

> **Recommendation:** build on Textual. It is the difference between ~1,500 lines and ~3,500 lines for the same result, and it degrades gracefully to 16-color terminals.

### Dependencies

```toml
[project.optional-dependencies]
tui = [
    "textual>=0.86",
    "rich>=13.7",
    "httpx>=0.27",
    "pydantic>=2.5",
    "tomli-w>=1.0",
]
```

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        CortexForge TUI                       │
│                                                              │
│  ┌──────────┐   ┌──────────────┐   ┌──────────────────────┐ │
│  │  Screens │◄─►│  App (Textual)│◄─►│  Widget Library     │ │
│  │  (views) │   │  event loop  │   │  (ProgressBar, etc) │ │
│  └────┬─────┘   └──────┬───────┘   └──────────────────────┘ │
│       │                │                                      │
│  ┌────▼────────────────▼────┐                                │
│  │      API Client (httpx)   │  X-CortexForge-Token header   │
│  └────────────┬──────────────┘                                │
│               │ HTTP/JSON                                     │
└───────────────┼──────────────────────────────────────────────┘
                │
        http://127.0.0.1:8731
                │
┌───────────────▼──────────────────────────────────────────────┐
│              CortexForge Server (existing)                    │
│   /api/health · /api/manifest · /api/account/* · /api/session  │
│   /api/attempt · /api/profile · /api/source · /api/generate   │
│   /api/tutor/* · /api/onboarding/* · /api/learner-profile     │
└──────────────────────────────────────────────────────────────┘
```

### Layered design

1. **Transport** — `ApiClient`: thin async wrapper over httpx. Owns base URL, token header, timeouts, error normalization. No UI imports.
2. **Domain** — `models.py`: pydantic models for every server payload (`Question`, `Card`, `Profile`, `Observation`, `Probe`, `Session`, `Account`). Validation + `.from_dict()`.
3. **State** — `store.py`: a `Store` holding the authenticated session, cached profile/session, and an in-memory event bus (Textual messages or a simple observer list for curses). Screens subscribe to state changes.
4. **Views** — `screens/`: one Textual `Screen` subclass per screen. Composed from reusable widgets.
5. **Widgets** — `widgets/`: custom Textual widgets (`ConfidenceMeter`, `FSRSBar`, `MoleculeView`, `StatCard`, `ProbeCard`).
6. **Theme** — `theme.py`: palette + style constants shared by every screen.

### Message-passing (Textual)

Each screen posts typed messages upward; the `CortexForgeApp` handles navigation:

```python
# messages.py
class Navigate(Message):
    def __init__(self, screen: str, **ctx): ...

class Authenticated(Message):
    def __init__(self, account: Account): ...

class SessionUpdated(Message): ...
class Toast(Message):
    def __init__(self, text: str, severity: str = "info"): ...
```

Screens react in `on_*` handlers. This keeps navigation centralized and testable.

---

## 3. Module Structure

```
cortexforge-tui/
├── pyproject.toml
├── README.md
└── src/cortexforge_tui/
    ├── __init__.py
    ├── __main__.py                 # python -m cortexforge_tui
    ├── app.py                      # CortexForgeApp: screen stack, routing, global keys
    ├── config.py                   # load/save ~/.cortexforge/tui.toml, token cache
    ├── theme.py                    # palette, styles, ASCII helpers, color depth
    ├── messages.py                 # Textual message types
    │
    ├── api/
    │   ├── __init__.py
    │   ├── client.py               # ApiClient (httpx async, base_url, token, timeouts)
    │   └── errors.py               # ApiError, AuthError, NetworkError, ServerError
    │
    ├── domain/
    │   ├── __init__.py
    │   └── models.py               # pydantic: Question, Card, Profile, Observation,
    │                               #          Probe, Session, Account, Contract, Forecast
    │
    ├── store/
    │   ├── __init__.py
    │   └── store.py                # Store: session cache, observer bus, derived stats
    │
    ├── widgets/
    │   ├── __init__.py
    │   ├── common.py               # StatCard, SectionTitle, HelpBar, ToastOverlay
    │   ├── progress.py             # Bar (textual), Ring (ASCII), Sparkline
    │   ├── confidence.py           # ConfidenceMeter (0.0–1.0 slider)
    │   ├── fsrs.py                 # FSRSGradeBar (Again/Hard/Good/Easy)
    │   ├── molecule.py             # MoleculeView (ASCII 3D projection)
    │   ├── question.py             # QuestionCard (prompt + options)
    │   └── probe.py                # ProbeCard (onboarding)
    │
    ├── screens/
    │   ├── __init__.py
    │   ├── splash.py               # SplashScreen (health check + logo)
    │   ├── auth.py                 # AuthScreen (login/register/reset tabs)
    │   ├── onboarding.py           # OnboardingScreen (probe runner)
    │   ├── dashboard.py            # DashboardScreen
    │   ├── study.py                # StudyScreen (FSRS loop)
    │   ├── profile.py              # ProfileScreen (observations)
    │   ├── sources.py              # SourcesScreen + SourceDetail + AddSource modal
    │   ├── tutor.py                # TutorScreen (dialogue)
    │   ├── molecule.py             # MoleculeScreen (visualization playground)
    │   └── settings.py             # SettingsScreen
    │
    ├── render/
    │   ├── __init__.py
    │   ├── ascii.py                # box-drawing, dividers, banner logo
    │   └── palette.py              # color names → rich/styles, depth-aware
    │
    └── util/
        ├── __init__.py
        ├── keys.py                 # Action enum, key normalization
        └── text.py                 # wrap, truncate, pad, strip_ansi
```

**Line-count estimate:** ~3,200 LOC total; ~450 for the app shell + API + store, ~250 per screen, ~600 for widgets + molecule renderer.

---

## 4. Data Models & API Mapping

Pydantic models mirror the server payloads exactly. Every model has `from_dict` with defaults so partial responses don't crash the UI.

### 4.1 Auth

```
POST /api/account/create     {email, password, display_name?}
  → 201 {account_id, email, api_token, display_name, learner_id, verified, created_at}

POST /api/account/login      {email, password}
  → 200 {session_token, account_id, learner_id, api_token, expires_at}

POST /api/account/session    {session_token}
  → 200 {account_id, learner_id, email, api_token, display_name, verified}
  → 401 invalid or expired

POST /api/account/logout     {session_token}            → {logged_out: true}
POST /api/account/reset-request {email}                → {sent: true}
POST /api/account/reset      {token, new_password}      → {reset: true}
```

The TUI stores `api_token` (for `X-CortexForge-Token`) and `session_token` (for resume) in `~/.cortexforge/tui.toml`, permissions `0600`.

### 4.2 Manifest & Onboarding

```
GET  /api/manifest           → {tasks, styles[], mcp, probes[]}
POST /api/onboarding/start   {learner_id}               → {learner_id, probes[], progress}
GET  /api/onboarding/next?learner_id=         → {probe|null, progress}
POST /api/onboarding/record  {learner_id, probe_id, answer} → {recorded, progress}
POST /api/onboarding/finish  {learner_id}               → {contract, summary}
```

### 4.3 Study

```
GET  /api/session?learner_id=&limit=20
  → {day, n_due, items: Question[], forecast}

POST /api/attempt  {learner_id, qid, correct, grade(1-4), confidence(0-1),
                     latency_ms, skill_id, response}
  → {p_known, mastered, schedule, next_due_day}
```

`grade` maps to FSRS: `1=Again, 2=Hard, 3=Good, 4=Easy`. The server clamps 1–4.

### 4.4 Profile

```
GET  /api/profile?learner_id=
  → {profile: {learner_id, observations[], social_role, learning_shape,
                unmeasured[], limits[]}, session: {...}}
```

Each `Observation`: `{construct, evidence, statement, action, confidence, caveat}`.

### 4.5 Sources

```
POST /api/source   {learner_id, text, title?, origin_path?}
  → {source_id, sha256, n_chars}
POST /api/generate {learner_id, source_id|text, styles?, max_per_style?, skill_id?}
  → {generated, questions[], provenance}
```

### 4.6 Learner Profile & Misc

```
GET  /api/learner-profile?learner_id=   → LearnerProfile dict
POST /api/learner-profile/update {learner_id, event_type, ...}
POST /api/erase       {learner_id, confirm:"ERASE"}   → {erased}
GET  /api/export      ?learner_id=                    → full export dict
```

### Model sketch (pydantic)

```python
# domain/models.py
from __future__ import annotations
from pydantic import BaseModel, Field

class Account(BaseModel):
    account_id: str
    email: str
    api_token: str
    learner_id: str
    display_name: str = ""
    verified: bool = False
    session_token: str = ""
    expires_at: float = 0.0

class Question(BaseModel):
    qid: str
    style: str
    prompt: str
    answer: str
    source_span: str = ""
    skill_id: str = ""
    options: list[str] = []
    grading: str = "exact"          # exact|fuzzy|numeric|set|rubric|self
    difficulty_hint: float = 0.0
    bloom: str = "remember"
    requires_llm: bool = False
    meta: dict = {}

class Observation(BaseModel):
    construct: str
    evidence: list[str] = []
    statement: str
    action: str
    confidence: str = "low"         # low|moderate|high
    caveat: str = ""

class Profile(BaseModel):
    learner_id: str
    observations: list[Observation] = []
    social_role: str = ""
    social_role_basis: list[str] = []
    learning_shape: str = ""
    learning_basis: list[str] = []
    unmeasured: list[str] = []
    limits: list[str] = []

class Probe(BaseModel):
    probe_id: str
    name: str
    purpose: str
    minutes: float = 0
    yields: list[str] = []
    task_id: str = ""
    kind: str = "task"              # task|interview|calibration|source
    question: str = ""
    options: list[str] = []
    depends_on: list[str] = []

class SessionInfo(BaseModel):
    day: float = 0
    n_due: int = 0
    items: list[Question] = []
    forecast: dict = {}

class AttemptResult(BaseModel):
    p_known: float = 0.0
    mastered: bool = False
    schedule: dict = {}
    next_due_day: float = 0.0
```

---

## 5. Design Tokens & Theming

### Palette (calm, blue-green base; amber reserved for CTAs/achievements)

| Token | Dark (256-color) | Fallback (16-color) | Usage |
|---|---|---|---|
| `bg` | `#0d1117` | black | background |
| `panel` | `#161b22` | blue/black | card background |
| `fg` | `#c9d1d9` | white | primary text |
| `muted` | `#8b949e` | bright black | secondary text |
| `accent` | `#58a6ff` | cyan | primary action, links |
| `accent2` | `#3fb950` | green | success, "Good", mastered |
| `warn` | `#d29922` | yellow | caution, "Hard" |
| `danger` | `#f85149` | red | "Again", errors, limits |
| `highlight` | `#a371f7` | magenta | focus ring, selection |
| `cta` | `#f0b429` | bright yellow | amber CTA / achievements only |

Depth-aware: detect `COLORTERM=truecolor` → 24-bit; `TERM=xterm-256color` → 256; else 16. The `render/palette.py` module resolves a logical color to the nearest supported value.

### Typography

- **Headers:** `rich.Text` with `bold` + accent color; section titles prefixed with a glyph (`◆`, `▸`, `✦`).
- **Box drawing:** `rich` box characters (`│ ─ ┌ ┐ └ ┘ ├ ┤ ┬ ┴ ┼`) for crisp panels; fall back to `+ - |` for dumb terminals.
- **Progress:** `rich.progress.Bar` or manual `███████░░░ 72%`.
- **Sparkline:** `▁▂▃▄▅▆▇█` for trend data.

### Banner logo (shown on splash + auth)

```
   ______  ____   ______  ________  ____  ____  ______
  / ___/ / __ \ / ____/ /_  __/ / / /  |/  / / / ____/
 / /   / / /_/ // __/     / / / /_/ / /|_/ / / / __/
/ /___/ / _, _// /___    / / / __  / /  / / / /_/ /
\____/ /_/ |_|/_____/    /_/ /_/ /_/_/  /_/\____/

        F O R G E   Y O U R   M I N D
```

(ASCII-art logo in `render/ascii.py`; width auto-fits terminal.)

---

## 6. Key Bindings

### Global (every screen)

| Key | Action |
|---|---|
| `q` / `Ctrl-C` | Quit (confirm if mid-session) |
| `?` | Toggle help overlay |
| `1`–`9` | Jump to screen (when on dashboard or via command palette) |
| `Esc` | Back / cancel / close modal |
| `Ctrl-L` | Redraw (refresh data) |

### Navigation

| Key | Action |
|---|---|
| `↑` / `k` | Move selection up |
| `↓` / `j` | Move selection down |
| `Enter` / `Space` | Activate / select |
| `Tab` | Next field / focus |
| `Shift-Tab` | Previous field |
| `g` then `g` | Go to top (vim-style, lists) |

### Study screen

| Key | Action |
|---|---|
| `Space` | Reveal answer |
| `1` / `A` | Grade **Again** |
| `2` / `H` | Grade **Hard** |
| `3` / `G` | Grade **Good** |
| `4` / `E` | Grade **Easy** |
| `+` / `-` | Adjust confidence ±0.1 (before grading) |
| `s` | Skip card (bury) |
| `t` | Open tutor hint |
| `q` | End session |

### Text input (auth, sources, tutor)

| Key | Action |
|---|---|
| `Ctrl-U` | Clear line |
| `Ctrl-W` | Delete word |
| `Ctrl-E` | Move to end |
| `Ctrl-A` | Move to start |
| `Left/Right` | Cursor move |
| `Backspace` | Delete |
| `Enter` | Submit |

### Command palette (Textual `CommandPalette`)

Bound to `Ctrl-P` from any screen. Fuzzy-matches screens + actions:
```
> dashboard
> study
> profile
> add source
> settings
```

---

## 7. Screen-by-Screen Layouts

All mockups assume 80×24. Panels use `rich` box characters. `[...]` marks a focus ring.

### 7.1 Splash / Health Check

Shown on launch; auto-advances on success, offers retry on failure.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│                                                                              │
│            ______  ____   ______  ________  ____  ____  ______              │
│           / ___/ / __ \ / ____/ /_  __/ / / /  |/  / / / ____/              │
│          / /   / / /_/ // __/     / / / /_/ / /|_/ / / / __/                 │
│         / /___/ / _, _// /___    / / / __  / /  / / / /_/ /                  │
│         \____/ /_/ |_|/_____/    /_/ /_/ /_/_/  /_/\____/                   │
│                                                                              │
│                  F O R G E   Y O U R   M I N D                                │
│                                                                              │
│                                                                              │
│                        ┌───────────────────────────┐                         │
│                        │  Connecting to 127.0.0.1:8731                        │
│                        │  ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱ 78%                       │
│                        └───────────────────────────┘                         │
│                                                                              │
│                        [ Cancel ]  [ Retry ]                                 │
│                                                                              │
│ ──────────────────────────────────────────────────────────────────────────── │
│  ? Help    q Quit                                                             │
└──────────────────────────────────────────────────────────────────────────────┘
```

On failure, the panel turns red and shows:
```
  ✗ Cannot reach the CortexForge server.
    Start it with:  cortexforge --port 8731
    [ Retry ]   [ Configure URL ]   [ Quit ]
```

### 7.2 Auth (Login / Register / Reset)

Three tabs across the top; form fields below. Footer shows validation hints.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CortexForge TUI                                          127.0.0.1:8731    │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│            ______  ____   ______  ________  ____  ____  ______              │
│           / ___/ / __ \ / ____/ /_  __/ / / /  |/  / / / ____/              │
│          / /   / / /_/ // __/     / / / /_/ / /|_/ / / / __/                 │
│         / /___/ / _, _// /___    / / / __  / /  / / / /_/ /                  │
│         \____/ /_/ |_|/_____/    /_/ /_/ /_/_/  /_/\____/                   │
│                                                                              │
│   ┌──────────┐  ┌──────────────┐  ┌──────────────┐                          │
│   │ [Login]  │  │  Register    │  │   Reset      │                          │
│   └──────────┘  └──────────────┘  └──────────────┘                          │
│                                                                              │
│     Email                                                                    │
│   ┌────────────────────────────────────────────────────────────┐             │
│   │ you@example.com                                               │             │
│   └────────────────────────────────────────────────────────────┘             │
│                                                                              │
│     Password                                                                 │
│   ┌────────────────────────────────────────────────────────────┐             │
│   │ ********************************************************   │             │
│   └────────────────────────────────────────────────────────────┘             │
│                                                                              │
│     Display name  (optional)                                                 │
│   ┌────────────────────────────────────────────────────────────┐             │
│   │ Ada Lovelace                                               │             │
│   └────────────────────────────────────────────────────────────┘             │
│                                                                              │
│                        [ ⟶  Sign in ]                                         │
│                        Forgot password?                                       │
│                                                                              │
│ ──────────────────────────────────────────────────────────────────────────── │
│  Tab switch field · Enter submit · Esc back                                    │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Register** adds a `Confirm password` field and shows live password strength:
```
   Password strength  ▰▰▰▱▱▱▱▱▱▱ 4/10  [weak]
   ✓ 8+ characters   ✓ upper+lower   ✗ number   ✗ symbol
```

### 7.3 Onboarding (13 Probes)

Centered card, progress bar, one probe at a time. Interview probes show options; task probes launch the instrument; calibration shows a confidence question.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CortexForge TUI                                                    Onboarding │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│                        ◆  Onboarding  ·  Step 3 of 13                         │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                                                                      │   │
│   │   What you are actually trying to do                                │   │
│   │                                                                      │   │
│   │   "Everything downstream depends on this. A system built for       │   │
│   │    passing an exam is not the system built for understanding a      │   │
│   │    field for its own sake."                                          │   │
│   │                                                                      │   │
│   │   Which of these is closest to why you are here?                    │   │
│   │                                                                      │   │
│   │      ▸ Pass a specific exam or certification, with a date           │   │
│   │        Understand a subject deeply, with no deadline                │   │
│   │        Build a practical skill I will use at work                   │   │
│   │        Recover or rebuild ability I feel I have lost                │   │
│   │        I am not sure yet — help me find out                         │   │
│   │                                                                      │   │
│   │   Estimated time remaining: ~10 min                                 │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱  23% complete                          │
│                                                                              │
│                        [ Skip for now ]   [ Next → ]                         │
│                                                                              │
│ ──────────────────────────────────────────────────────────────────────────── │
│  ↑↓ select · Enter confirm · Esc skip                                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.4 Dashboard

Default landing view. Three-column layout: stats rail, main action panel, today's queue preview + sparkline.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  CortexForge TUI                              learner_ada   ● verified  ⚙  ?  │
├───────────────┬──────────────────────────────────────────┬───────────────────┤
│  NAV          │                                          │  TODAY            │
│               │   Welcome back, Ada.                     │                   │
│  ▸ Dashboard  │                                          │  Due now      24  │
│    Study      │   ┌──────────────────────────────────┐   │  New today     8  │
│    Sources    │   │                                  │   │  Mastered    41%  │
│    Profile    │   │   Continue learning              │   │  Retention   92%  │
│    Tutor      │   │   ▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱▱▱▱▱▱▱▱▱▱▱ 62%     │   │                   │
│    Molecule   │   │                                  │   │  Streak  🔥 12d  │
│    Settings   │   │   You are 62% through your        │   │                   │
│               │   │   current learning contract.      │   │  Next review    │
│  ───────────  │   │                                  │   │  in 3.2 h       │
│  CONTRACT     │   └──────────────────────────────────┘   │                   │
│  ▰▰▰▰▰▰▰▰▱▱  │                                          │  ┌─────────────┐  │
│  72% mastered │   ┌────────────┐  ┌────────────┐         │  │  RETENTION  │  │
│               │   │  SKILLS    │  │  ACTIVITY  │         │  │   SPARKLINE │  │
│  SKILL RADAR  │   │            │  │  ▁▂▃▅▆▇█   │         │  │ ▁▂▃▄▅▆▇█   │  │
│  ◆ recall  ████│   │  recall    │  │  last 14d  │         │  │  next 14d  │  │
│  ◆ speed   ███ │   │  speed     │  │            │         │  │ ▁▂▃▄▅▆▇█   │  │
│  ◆ memory  ██  │   │  memory    │  │            │         │  └─────────────┘  │
│  ◆ control █   │   │  control   │  │            │         │                   │
│               │   │            │  │            │         │  ┌─────────────┐  │
│               │   └────────────┘  └────────────┘         │  │   MOLECULE  │  │
│               │                                          │  │   ○──○      │  │
│               │   ┌──────────────────────────────────┐   │  │  /   /      │  │
│               │   │  ▸ Start today's session (24)     │   │  │ ○──○──○    │  │
│               │   └──────────────────────────────────┘   │  └─────────────┘  │
│               │                                          │                   │
├───────────────┴──────────────────────────────────────────┴───────────────────┤
│  1 Dashboard · 2 Study · 3 Sources · 4 Profile · 5 Tutor · 6 Molecule · 7 Settings │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.5 Study Session (FSRS)

Full-screen focus mode. Question card centered; confidence meter; FSRS grade bar appears after reveal.

**Before reveal:**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Study  ·  Card 5 of 24  ·  Session 6m 12s              learner_ada   ?  q   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │                                                                      │   │
│   │   Recall  ·  Difficulty ●●●○○○  ·  Bloom: remember                  │   │
│   │                                                                      │   │
│   │   "In the context of binary search, what invariant must hold        │   │
│   │    for the algorithm to be correct on a sorted array?"               │   │
│   │                                                                      │   │
│   │                                                                      │   │
│   │   ┌────────────────────────────────────────────────────────────┐     │   │
│   │   │  A. The array must be strictly ascending                    │     │   │
│   │   │  B. The array must contain no duplicates                    │     │   │
│   │   │  C. The search space must be halved each step               │     │   │
│   │   │  D. The target must exist in the array                      │     │   │
│   │   └────────────────────────────────────────────────────────────┘     │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   Confidence  [────●────────────]  0.40     (+/- adjust · Space reveal)       │
│                                                                              │
│   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱  5/24                                │
│                                                                              │
│ ──────────────────────────────────────────────────────────────────────────── │
│  ↑↓ choose · Space reveal · t tutor hint · s skip · q end session            │
└──────────────────────────────────────────────────────────────────────────────┘
```

**After reveal (grade bar appears):**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Study  ·  Card 5 of 24  ·  Session 6m 40s              learner_ada   ?  q   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │   "In the context of binary search, what invariant must hold        │   │
│   │    for the algorithm to be correct on a sorted array?"               │   │
│   │                                                                      │   │
│   │   ┌────────────────────────────────────────────────────────────┐     │   │
│   │   │  A. The array must be strictly ascending                    │     │   │
│   │   │  B. The array must contain no duplicates                    │     │   │
│   │   │  C. The search space must be halved each step        ✓      │     │   │
│   │   │  D. The target must exist in the array                      │     │   │
│   │   └────────────────────────────────────────────────────────────┘     │   │
│   │                                                                      │   │
│   │   Why: Binary search relies on the sorted order to discard half      │   │
│   │   of the remaining search space at each step.                        │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   How well did you know it?                                                  │
│   ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐                        │
│   │  AGAIN   │ │  HARD    │ │  GOOD ✓  │ │  EASY    │                        │
│   │    1     │ │    2     │ │    3     │ │    4     │                        │
│   │  <10m    │ │  1d      │ │  3d      │ │  7d      │                        │
│   └──────────┘ └──────────┘ └──────────┘ └──────────┘                        │
│                                                                              │
│ ──────────────────────────────────────────────────────────────────────────── │
│  1 Again · 2 Hard · 3 Good · 4 Easy · +/- confidence                         │
└──────────────────────────────────────────────────────────────────────────────┘
```

On grading, the bar flashes the next interval and advances. Session end shows a summary panel with accuracy, mean confidence, and calibration.

### 7.6 Profile (Observations)

Two-pane layout: observations list (left) + learning shape summary (right).

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Profile  ·  learner_ada                                    ⚙ Settings   ?  │
├───────────────────────────────┬──────────────────────────────────────────────┤
│  OBSERVATIONS                │  LEARNING SHAPE                              │
│                              │                                              │
│  ▸ inhibitory_control        │  ┌──────────────────────────────────────┐    │
│    ● moderate                │  │  "Strong analytical recall with a   │    │
│                              │  │   tendency to over-prepare under    │    │
│  ▸ working_memory           │  │   deadline pressure."                │    │
│    ● high                    │  └──────────────────────────────────────┘    │
│                              │                                              │
│  ▸ processing_speed          │  SOCIAL ROLE                                │
│    ● high                    │  ┌──────────────────────────────────────┐    │
│                              │  │  "Independent verifier — prefers   │    │
│  ▸ calibration_bias          │  │   to cross-check answers before     │    │
│    ● under-confident          │  │   committing."                      │    │
│                              │  └──────────────────────────────────────┘    │
│  ▸ cooperation               │                                              │
│    ● moderate                │  BASIS                                       │
│                              │  ▸ 42 attempts · calibration σ = 0.18        │
│  ───────────────             │  ▸ 3 social tasks · ultimatum, dictator     │
│  UNMEASURED                  │                                              │
│  ▸ working_memory_updating  │  LIMITS                                      │
│  ▸ altruism                  │  ▸ No baseline for updating tasks           │
│  ▸ strategic_reasoning       │  ▸ Only 2 sources ingested                   │
│                              │                                              │
├───────────────────────────────┴──────────────────────────────────────────────┤
│  ↑↓ browse observation · Enter expand · Ctrl-L refresh                        │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.7 Sources (List + Add + Generate)

**List view:**
```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Sources  ·  5 ingested                                      + Add source   ? │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  SEARCH: [ binary search.............................. ]             │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │ ▸ Algorithms.pdf                              12,480 chars · 3 styles│   │
│   │   src-3f2a…   Generated 18 questions   ● has questions               │   │
│   ├──────────────────────────────────────────────────────────────────────┤   │
│   │   Organic_Chemistry_Notes.md                  8,920 chars · 2 styles │   │
│   │   src-7b1c…   Generated 12 questions   ● has questions               │   │
│   ├──────────────────────────────────────────────────────────────────────┤   │
│   │   Linear_Algebra_Ch1.txt                     5,100 chars · 0 styles │   │
│   │   src-9e4d…   No questions yet      [ Generate → ]                   │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▰▱▱▱▱  5/5 loaded                            │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  ↑↓ browse · Enter open · g generate · + add new · Esc back                   │
└──────────────────────────────────────────────────────────────────────────────┘
```

**Add source modal** (overlay):
```
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  Add source                                                   [✕]   │   │
│   │                                                                      │   │
│   │  Title                                                              │   │
│   │  ┌──────────────────────────────────────────────────────────────┐    │   │
│   │  │ Algorithms.pdf                                                 │    │   │
│   │  └──────────────────────────────────────────────────────────────┘    │   │
│   │                                                                      │   │
│   │  Paste text (or file path)                                          │   │
│   │  ┌──────────────────────────────────────────────────────────────┐    │   │
│   │  │ Binary search is an efficient algorithm for finding an        │    │   │
│   │  │ item from a sorted list of items. It works by repeatedly      │    │   │
│   │  │ dividing in half the portion of the list that could contain   │    │   │
│   │  │ the item...                                                    │    │   │
│   │  │                                                                │    │   │
│   │  └──────────────────────────────────────────────────────────────┘    │   │
│   │                                                                      │   │
│   │  Styles  [✓ definitional] [✓ causal] [✓ mcq] [ ] numeric [ ] rubric  │   │
│   │                                                                      │   │
│   │  ┌──────────────────────┐  ┌──────────────────────┐                  │   │
│   │  │     Save source      │  │  Save + generate     │                  │   │
│   │  └──────────────────────┘  └──────────────────────┘                  │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.8 Tutor Dialogue

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Tutor  ·  Recall session                              learner_ada   ?  q   │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  TUTOR                                                                │   │
│   │  You graded that "Hard" but your confidence was 0.85. That gap      │   │
│   │  is worth examining — what made you less sure than you felt?        │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  YOU                                                                  │   │
│   │  I recognized the pattern but second-guessed the edge case.           │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  TUTOR                                                                │   │
│   │  That's a classic overcorrection signal. Here's a ladder:            │   │
│   │  1. What does the sorted invariant actually guarantee?               │   │
│   │  2. Where could it break with duplicates?                            │   │
│   │  3. Can you construct a counterexample?                             │   │
│   │                                                                      │   │
│   │  [ Ask a follow-up ]  [ Get a hint ]  [ New question ]               │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  >                                                                    │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  Type to respond · Enter send · h hint · n new question · Esc exit            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.9 Molecule Viewer (ASCII Molecular Visualization)

Full-screen playground. Left: molecule selector + rotation controls. Right: ASCII 3D projection.

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Molecule  ·  Visualization playground                      learner_ada   ?  │
├───────────────────────────────┬──────────────────────────────────────────────┤
│  MOLECULE                     │                                              │
│                              │            H                                 │
│  ▸ caffeine                   │            |                                 │
│    water                      │       H — C — N — C                          │
│    benzene                    │       |   ||  |   \                          │
│    ethanol                    │       N — C — O    C = O                     │
│    dopamine                   │       |   |   |    /                         │
│    glucose                    │       H — C — C — H                          │
│                              │           |                                   │
│  ───────────────              │           CH3                                │
│  CONTROLS                    │                                              │
│  ▸ auto-rotate  ON           │        ( drag to rotate )                    │
│    spin X  ──●────  0.4      │                                              │
│    spin Y  ────●──  0.6      │   Legend:  C ●   N ●   O ●   H ○             │
│    zoom    ──●─────  1.0×    │                                              │
│    bonds   [✓] show           │   Atoms: 24   Bonds: 25   Rot: 32°/18°       │
│    labels  [✓] show           │                                              │
│                              │                                              │
│  ───────────────              │                                              │
│  PRESETS                     │                                              │
│  ▸ ball-and-stick             │                                              │
│    space-filling              │                                              │
│    wireframe                  │                                              │
│                              │                                              │
├───────────────────────────────┴──────────────────────────────────────────────┤
│  ←→↑↓ rotate · +/- zoom · a auto-rotate · r reset · 1-5 presets · Esc back    │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 7.10 Settings

```
┌──────────────────────────────────────────────────────────────────────────────┐
│  Settings  ·  learner_ada                                    ⚙   ?  q       │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌──────────────────────────────────────────────────────────────────────┐   │
│   │  SESSION                                                            │   │
│   │                                                                      │   │
│   │  Daily card limit          [────●────]  20                           │   │
│   │  Target success rate       [──●──────]  0.80                         │   │
│   │  Enable forethought      [✓]                                        │   │
│   │  Enable reflection       [✓]                                        │   │
│   │                                                                      │   │
│   ├──────────────────────────────────────────────────────────────────────┤   │
│   │  DISPLAY                                                            │   │
│   │                                                                      │   │
│   │  Color depth            [ 256 ▼ ]  (auto | 16 | 256 | truecolor)   │   │
│   │  ASCII style             [ rounded ▼ ]  (ascii|rounded|double)      │   │
│   │  Reduce motion          [ ]                                        │   │
│   │  Show confidence meter  [✓]                                        │   │
│   │                                                                      │   │
│   ├──────────────────────────────────────────────────────────────────────┤   │
│   │  ACCOUNT                                                            │   │
│   │                                                                      │   │
│   │  Email           you@example.com                                     │   │
│   │  Display name    Ada Lovelace                                        │   │
│   │  API token       ••••••••••••••••••••••••  [ Reveal ]  [ Copy ]    │   │
│   │                                                                      │   │
│   │  [ Change password ]              [ Log out ]                       │   │
│   │                                                                      │   │
│   ├──────────────────────────────────────────────────────────────────────┤   │
│   │  DANGER ZONE                                                        │   │
│   │                                                                      │   │
│   │  [ Erase all learner data ]   (type ERASE to confirm)               │   │
│   │                                                                      │   │
│   └──────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
├──────────────────────────────────────────────────────────────────────────────┤
│  ↑↓ adjust · Enter toggle · Esc back                                           │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 8. ASCII Molecular Visualization

This is the Three.js-inspired centerpiece: a real-time 3D renderer that projects molecules to ASCII. It is a self-contained widget (`widgets/molecule.py`) usable from the Molecule screen and as a decorative element on the Dashboard.

### Approach

1. **Molecule representation** — atoms have 3D coordinates (Å), bonds connect pairs. Built-in presets (caffeine, water, benzene, ethanol, dopamine, glucose) defined as data.
2. **Camera** — a view matrix from yaw/pitch/distance. Auto-rotate increments yaw each frame.
3. **Projection** — perspective divide → 2D screen coordinates.
4. **Depth sorting** — atoms sorted back-to-front (painter's algorithm) for correct occlusion.
5. **Rendering** — draw bonds as lines (Bresenham) between projected atom positions; draw atoms as characters (`●` `○` `◆`) sized by element and depth. Element → color and radius map:

| Element | Symbol | Color | Relative radius |
|---|---|---|---|
| C | `●` | white | 1.0 |
| N | `●` | blue | 0.95 |
| O | `●` | red | 0.9 |
| H | `○` | muted | 0.55 |

6. **Bond styles** — single `─│╱╲`, double `═║`, triple `≡`. Bond order from preset data.
7. **Modes** — `ball-and-stick` (atoms + bonds), `space-filling` (atoms only, scaled by van der Waals radius), `wireframe` (bonds only).

### Renderer signature

```python
# widgets/molecule.py
from dataclasses import dataclass
from textual.app import ComposeResult
from textual.widget import Widget
from textual.message import Message

@dataclass
class Atom:
    element: str           # "C", "N", "O", "H"
    x: float; y: float; z: float   # Å

@dataclass
class Bond:
    a: int; b: int         # atom indices
    order: int = 1         # 1, 2, 3

@dataclass
class Molecule:
    name: str
    atoms: list[Atom]
    bonds: list[Bond]

class MoleculeView(Widget):
    """Renders a molecule as ASCII art, redrawn on a timer."""

    class Rotated(Message):
        def __init__(self, yaw: float, pitch: float): ...

    def __init__(self, molecule: Molecule, *, auto_rotate: bool = True,
                 spin_x: float = 0.4, spin_y: float = 0.6,
                 zoom: float = 1.0, show_bonds: bool = True,
                 show_labels: bool = True, style: str = "rounded"):
        ...
    def on_mount(self) -> None:
        # start a 30fps timer for auto-rotation
    def rotate(self, dyaw: float, dpitch: float) -> None: ...
    def reset(self) -> None: ...
    def render(self) -> Text:
        # project, sort, draw bonds (Bresenham), draw atoms, return rich Text
```

### Projection math (core)

```python
import math

def project(atoms: list[Atom], yaw: float, pitch: float,
            dist: float, w: int, h: int, fov: float = 40.0):
    cy, sy = math.cos(yaw), math.sin(yaw)
    cp, sp = math.cos(pitch), math.sin(pitch)
    out = []
    for a in atoms:
        # rotate around Y then X
        x1 = a.x * cy + a.z * sy
        z1 = -a.x * sy + a.z * cy
        y1 = a.y * cp - z1 * sp
        z2 = a.y * sp + z1 * cp
        # perspective
        zc = z2 + dist
        if zc <= 0.1:
            zc = 0.1
        s = (min(w, h) * fov) / zc
        sx = w / 2 + x1 * s
        sy2 = h / 2 - y1 * s
        out.append((sx, sy2, zc))
    return out
```

### Frame pipeline (30fps)

```
timer tick → update yaw/pitch → project all atoms →
  sort by depth (far→near) →
  rasterize bonds into a 2D char buffer (Bresenham, respect bond order) →
  rasterize atoms into the buffer (overwrite bonds, size by depth) →
  annotate with labels (element symbol) →
  convert buffer → rich.Text with per-cell color spans →
  widget.refresh()
```

### Key bindings (Molecule screen)

| Key | Action |
|---|---|
| `← →` | Rotate yaw ±5° |
| `↑ ↓` | Rotate pitch ±5° |
| `+ / -` | Zoom in/out |
| `a` | Toggle auto-rotate |
| `b` | Toggle bonds |
| `l` | Toggle labels |
| `r` | Reset view |
| `1–5` | Switch preset |
| `space` | Cycle render mode |

### Integration

- **Dashboard**: a small static (or slowly rotating) molecule in the right rail as a "daily molecule" decoration.
- **Molecule screen**: full interactive renderer.
- **Study screen**: optional "molecule of the moment" — when a chemistry question is active, show its molecule in a side panel.

---

## 9. Code Patterns

### 9.1 ApiClient (async httpx)

```python
# api/client.py
import httpx
from .errors import ApiError, AuthError, NetworkError, ServerError

class ApiClient:
    def __init__(self, base_url: str = "http://127.0.0.1:8731",
                 token: str = "", timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self._token = token
        self._timeout = timeout
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self._timeout,
                headers=self._headers(),
            )
        return self._client

    def _headers(self) -> dict[str, str]:
        h = {"Accept": "application/json"}
        if self._token:
            h["X-CortexForge-Token"] = self._token
        return h

    def set_token(self, token: str) -> None:
        self._token = token
        if self._client is not None:
            self._client.headers.update(self._headers())

    async def get(self, path: str, **params) -> dict:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, payload: dict | None = None) -> dict:
        return await self._request("POST", path, json=payload or {})

    async def _request(self, method: str, path: str, **kw) -> dict:
        client = await self._get_client()
        try:
            r = await client.request(method, path, **kw)
        except httpx.ConnectError as e:
            raise NetworkError(f"cannot reach {self.base_url}: {e}") from e
        except httpx.TimeoutException as e:
            raise NetworkError(f"timeout calling {path}") from e
        if r.status_code == 401:
            raise AuthError(r.json().get("error", "unauthorized"))
        if r.status_code >= 400:
            raise ServerError(r.status_code, r.json().get("error", "server error"))
        return r.json()

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
```

### 9.2 Store (state + observer)

```python
# store/store.py
import asyncio
from typing import Callable, Any
from domain.models import Account, Profile, SessionInfo

class Store:
    """Hovered session state + derived stats. Notifies observers on change."""

    def __init__(self, api: ApiClient):
        self.api = api
        self.account: Account | None = None
        self.profile: Profile | None = None
        self.session: SessionInfo | None = None
        self._observers: list[Callable[[str, Any], None]] = []

    def subscribe(self, fn: Callable[[str, Any], None]) -> None:
        self._observers.append(fn)

    def _emit(self, event: str, payload: Any = None) -> None:
        for fn in self._observers:
            try:
                fn(event, payload)
            except Exception:
                pass

    async def restore(self) -> bool:
        """Resume from cached session token. Returns True if valid."""
        token = config.load_session_token()
        if not token:
            return False
        try:
            info = await self.api.post("/api/account/session",
                                       {"session_token": token})
            self.account = Account(**info)
            self.api.set_token(self.account.api_token)
            self._emit("authenticated", self.account)
            return True
        except AuthError:
            config.clear_session()
            return False

    async def refresh_profile(self) -> None:
        if not self.account:
            return
        data = await self.api.get("/api/profile",
                                  learner_id=self.account.learner_id)
        self.profile = Profile(**data["profile"])
        self._emit("profile_updated", self.profile)

    async def refresh_session(self) -> None:
        if not self.account:
            return
        data = await self.api.get("/api/session",
                                  learner_id=self.account.learner_id)
        self.session = SessionInfo(**data)
        self._emit("session_updated", self.session)
```

### 9.3 Screen base + navigation

```python
# screens/dashboard.py
from textual.screen import Screen
from textual.containers import Horizontal, Vertical
from textual.widgets import Static, ListView, ListItem, Label
from textual import on

class DashboardScreen(Screen):
    CSS_PATH = "screens/dashboard.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("s", "study", "Study"),
        ("1", "goto('dashboard')", "Dashboard"),
        ("2", "goto('study')", "Study"),
    ]

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="dash-body"):
            yield NavRail(id="nav")
            with Vertical(id="dash-main"):
                yield WelcomeBanner()
                yield ContinuePanel()
                yield StatsRow()
            yield TodayRail(id="today")
        yield Footer()

    def on_mount(self) -> None:
        self.store.subscribe(self._on_store_event)
        self.run_worker(self._refresh(), exclusive=True)

    def _on_store_event(self, event: str, payload: Any) -> None:
        if event == "session_updated":
            self.query_one("#today", TodayRail).update(payload)

    async def _refresh(self) -> None:
        await asyncio.gather(
            self.store.refresh_profile(),
            self.store.refresh_session(),
        )
```

### 9.4 Progress bar widget

```python
# widgets/progress.py
from textual.widgets import Static
from rich.text import Text

class Bar(Static):
    """A labeled horizontal progress bar with optional percentage."""

    def __init__(self, label: str, ratio: float, *,
                 width: int = 30, color: str = "accent",
                 show_pct: bool = True, **kw):
        super().__init__(**kw)
        self.label = label
        self.ratio = max(0.0, min(1.0, ratio))
        self.width = width
        self.color = color
        self.show_pct = show_pct

    def render(self) -> Text:
        t = Text()
        t.append(f"{self.label:<16} ", style="muted")
        filled = int(self.width * self.ratio)
        bar = "█" * filled + "░" * (self.width - filled)
        t.append(bar, style=self.color)
        if self.show_pct:
            t.append(f"  {self.ratio*100:4.0f}%", style="bold")
        return t
```

### 9.5 Confidence meter

```python
# widgets/confidence.py
class ConfidenceMeter(Static):
    """0.0–1.0 confidence slider; +/- adjusts, shown before grading."""

    def __init__(self, value: float = 0.5, *, width: int = 40, **kw):
        super().__init__(**kw)
        self.value = max(0.0, min(1.0, value))
        self.width = width

    def render(self) -> Text:
        t = Text("Confidence  ")
        pos = int(self.width * self.value)
        t.append("[" + "─" * pos, style="muted")
        t.append("●", style="highlight")
        t.append("─" * (self.width - pos - 1) + "]", style="muted")
        t.append(f"  {self.value:.2f}", style="bold")
        return t

    def adjust(self, delta: float) -> None:
        self.value = max(0.0, min(1.0, self.value + delta))
        self.refresh()
```

### 9.6 FSRS grade bar

```python
# widgets/fsrs.py
GRADES = [
    ("Again", 1, "danger",  "<10m"),
    ("Hard",  2, "warn",    "1d"),
    ("Good",  3, "accent2", "3d"),
    ("Easy",  4, "accent",  "7d"),
]

class FSRSGradeBar(Static):
    """Four-button FSRS grading bar; keys 1-4 select."""

    def __init__(self, **kw):
        super().__init__(**kw)
        self.selected = 2  # default "Good"

    def render(self) -> Text:
        t = Text()
        for i, (name, key, color, nxt) in enumerate(GRADES):
            marker = "✓" if i == self.selected else " "
            t.append(f" ┌──────────┐ ", style=color)
            t.append("\n")
            t.append(f" │ {marker} {name:<6} │ ", style=color)
            t.append("\n")
            t.append(f" │    {key}     │ ", style=color)
            t.append(f" → {nxt}")
            t.append("\n")
            t.append(f" └──────────┘ ", style=color)
            t.append("   ")
        return t
```

### 9.7 Toast / notification overlay

```python
# widgets/common.py
class ToastOverlay(Static):
    """Transient message that auto-dismisses; severity colors the border."""

    def __init__(self, text: str, severity: str = "info", **kw):
        super().__init__(**kw)
        self.text = text
        self.severity = severity

    def on_mount(self) -> None:
        self.set_timer(2.5, self.dismiss)

    def render(self) -> Text:
        style = {"info": "accent", "ok": "accent2",
                 "warn": "warn", "error": "danger"}[self.severity]
        t = Text(f" {self.text} ", style=f"bold {style}")
        return t
```

---

## 10. Error Handling & Resilience

| Condition | Behavior |
|---|---|
| Server unreachable | Splash shows retry + configure URL. All screens show a non-blocking "offline" banner. |
| 401 Unauthorized | Clear cached token, navigate to Auth screen with a toast. |
| 429 Rate limited | Show toast with retry-after; disable the triggering button for the window. |
| 5xx Server error | Toast with generic message (server never leaks tracebacks). Show "retry" on the action. |
| Network drop mid-session | Study screen buffers attempts locally; reconnect in background; sync on restore. |
| Timeout | Per-request 10s timeout; idempotent calls (profile, session) retry once. |
| Invalid JSON | Pydantic validation error → toast "unexpected server response"; do not crash. |
| Terminal too small | Minimum 80×24; below that, show a single-line "resize terminal" message. |

All API errors surface as `ApiError` subclasses. Screens catch and map to toasts; the app catches unhandled exceptions and shows a fatal dialog with an option to restart.

---

## 11. State Machine & Navigation

```
                    ┌──────────┐
            launch  │  SPLASH  │  health check
                    └────┬─────┘
                         │ ok
                         ▼
                  ┌──────────────┐   cached session   ┌────────────┐
                  │    AUTH      │ ──────────────────► │ DASHBOARD  │
                  │ login/register│  (resume)          └─────┬──────┘
                  └──────┬───────┘                         │
                         │ login/register success          │ 1-7, g
                         ▼                                 ▼
                  ┌──────────────┐   first run      ┌────────────┐
                  │  DASHBOARD   │ ◄──────────────── │ ONBOARDING │
                  └──────┬───────┘                   └────────────┘
                         │
        ┌────────────────┼────────────────┬───────────┬──────────┬──────────┐
        ▼                ▼                ▼           ▼          ▼          ▼
   ┌─────────┐    ┌──────────┐    ┌──────────┐  ┌────────┐ ┌────────┐ ┌──────────┐
   │  STUDY  │    │ SOURCES  │    │ PROFILE  │  │ TUTOR  │ │MOLECULE │ │ SETTINGS │
   └─────────┘    └──────────┘    └──────────┘  └────────┘ └────────┘ └──────────┘
```

- Navigation is centralized in `CortexForgeApp.action_goto(screen)`.
- A screen stack (Textual `ScreenStack`) enables back navigation (`Esc` pops).
- `g` prefix (vim-style) opens a command palette from anywhere.
- Mid-session `q` asks "End session? Progress will be saved." with `[End] [Cancel]`.

---

## 12. Accessibility & Ergonomics

- **Color is never the only channel.** Every state has an icon + text + color (dual-coded). Severity glyphs: `●` info, `✓` success, `⚠` caution, `✗` error.
- **Focus ring** visible on the active element (`highlight` color).
- **Keyboard-first** — every action reachable without a mouse; mouse still works (Textual widgets support clicks).
- **Reduce motion** setting disables auto-rotation and flash animations.
- **Minimum contrast** — palette chosen for WCAG AA on both light and dark terminals.
- **No information in color alone** — progress bars always show a numeric percentage.
- **Terminal size** — graceful degradation below 80×24; critical actions remain reachable.
- **Screen-reader friendly** — Textual exposes an accessibility tree; decorative ASCII is marked `aria-hidden` via `Text`.

---

## 13. Testing Strategy

| Layer | Tool | What |
|---|---|---|
| **Unit** | `pytest` | Domain models, projection math, FSRS mapping, text utils, palette depth resolution. |
| **Widget** | `textual`'s `run_test()` | Headless pilot: mount each screen, assert widgets render, simulate keys, assert navigation + toasts. |
| **API contract** | `pytest-httpx` | Mock the server; assert requests carry `X-CortexForge-Token` and correct payloads; assert error mapping. |
| **Integration** | `textual-dev` + live server | Manual + scripted run against `cortexforge` on :8731. |
| **Snapshot** | `pytest-textual-screenshot` | Golden-master screenshots of each screen for visual regression. |
| **Smoke** | `scripts/smoke_tui.py` | CI: boot app headless, drive splash→auth→dashboard, assert no crashes. |

Headless example:
```python
async def test_dashboard_loads():
    app = CortexForgeApp()
    async with app.run_test(size=(80, 24)) as pilot:
        await pilot.press("2")           # go to study
        await pilot.pause()
        assert isinstance(app.screen, StudyScreen)
```

---

## 14. Implementation Roadmap

| Phase | Deliverable | Est. LOC |
|---|---|---|
| **0 — Skeleton** | `pyproject`, `app.py`, theme, splash, config, ApiClient, errors, store | ~500 |
| **1 — Auth** | AuthScreen (login/register/reset), token cache, splash resume | ~450 |
| **2 — Dashboard** | DashboardScreen, nav rail, stat cards, progress widgets, sparkline | ~600 |
| **3 — Study** | StudyScreen, QuestionCard, ConfidenceMeter, FSRSGradeBar, session summary | ~700 |
| **4 — Profile + Sources** | ProfileScreen (observations), SourcesScreen (list/add/generate) | ~650 |
| **5 — Tutor** | TutorScreen, dialogue scroll, hint/question actions | ~400 |
| **6 — Molecule** | MoleculeView renderer, presets, projection, modes, MoleculeScreen | ~550 |
---

*End of design document.*

**Total ≈ 5,000 LOC.** Phases 0–3 deliver a working MVP (splash → auth → dashboard → study). Each subsequent phase is independently shippable.

---

*End of design document.*
