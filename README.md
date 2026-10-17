# CortexForge

An adaptive learning system that measures you before it teaches you, generates
questions in any style from your own material, and tells you the truth.

It is built to **not pamper you**. It will not tell you that you are doing
great when you are not. It keeps you at roughly 85% success — the band where
learning is fastest — which means you will fail about one item in seven, on
purpose.

---

## What it does

**Profiles you first.** A 13-probe first-run sequence (~45 minutes) measures
attention, working memory, processing speed, confidence calibration, and how
you behave in group settings. It ends with a written learning contract that
names what would prove it wrong.

**Generates questions in any style from your source.** 18 native styles with
no language model required — cloze, definition, Socratic, counterexample,
steelman, transfer, Feynman, error-spotting, worked-example completion, and
more. Every question carries the source span it came from. A style your
material cannot support is skipped and reported, never fabricated.

**Schedules with FSRS.** The Free Spaced Repetition Scheduler (v4.5), with
predicted-recall calibration tracked against your actual recall.

**Tells you how you behave.** Behavioural economic games and social-cognitive
tasks produce observations like "you rejected offers below 35% of the stake,
accepting a personal cost to punish what you judged unfair" — each with a
confidence label and an explicit statement of what it does *not* measure.

**Tracks cognitive load honestly.** Subjective clarity and objective
performance are measured and reported separately, because they diverge and
conflating them would be a lie.

**Ships with MCP pre-wired.** 34 servers catalogued, 12 in the core set, 18
needing no authentication at all. Notion and Obsidian included. Your only step
is OAuth.

---

## What it will not do

- It will not diagnose anything. Clinical vocabulary is blocked in code.
- It will not claim to make you smarter, prevent dementia, or cure anything.
- It will not claim far transfer from training tasks — that is not established.
- It will not send your data anywhere. No account, no analytics.
- It will not praise you for showing up.

---

## Quick start

```bash
git clone https://github.com/ugwanjegrandson2010/cortexforge
cd cortexforge
python3 -m venv .venv && .venv/bin/pip install -e .
.venv/bin/python -m cortexforge.server
```

Open `http://127.0.0.1:8731`. The server prints an API token on startup; paste
it into the app when prompted (the app stores it in session storage only).

Or without installing:

```bash
python3 run.py
```

### Requirements

Python 3.11+ and nothing else. The core is pure stdlib — no NumPy, no Pandas,
no compiled extensions — so it runs on CPUs without AVX or SSE4.

---

## Verify it works

```bash
# 224 unit tests
.venv/bin/python -m unittest discover -s tests

# 45 end-to-end API checks against a running server
.venv/bin/python -m cortexforge.server --port 8731 --db /tmp/cf.db &
TOKEN=$(grep -oP 'API token \(required for writes\): \K\S+' /dev/stdin)
.venv/bin/python scripts/e2e.py http://127.0.0.1:8731 "$TOKEN"

# 110 platform and packaging checks
.venv/bin/python scripts/test_platforms.py
```

---

## Build for every platform

```bash
bash scripts/build/linux.sh     # tarball, AppImage, .deb, .rpm, PKGBUILD, Flatpak
bash scripts/build/macos.sh     # .app, .dmg, codesign, notarise, staple
bash scripts/build/windows.sh   # portable zip, MSI via WiX
bash scripts/build/mobile.sh    # iOS + Android via Capacitor, store metadata
```

Every build bundles a private Python runtime, so the target machine needs
nothing installed.

---

## Architecture

```
src/cortexforge/
  security.py      CVE-mapped controls, each with a test
  store.py         SQLite, parameterised, thread-local connections
  scheduler.py     FSRS-4.5
  tracing.py       BKT, IRT 2PL/3PL, Elo, calibration
  questiongen.py   18 native styles + 3 declared LLM styles
  instruments.py   Task registry, evidence grades, 14 scorers
  profile.py       Observation synthesis, anti-pampering validator
  onboarding.py    13-probe state machine, learning contract
  mcp.py           34-server catalogue, OAuth discovery (RFC 9470/8414)
  server.py        Hardened stdlib HTTP server
web/               index.html, app.css, app.js
docs/research/     five dossiers, 266 KB, with [UNVERIFIED] markers
docs/prd/PRD.md    the full product requirements document
```

---

## The honesty contract

This is the load-bearing requirement. It is enforced in code.

`profile.validate_statement()` rejects any learner-facing string containing:

- **Praise without information** — "great job", "well done", "good effort",
  "you're a natural".
- **Unfalsifiable character claims** — "you are a good person", "you are lazy",
  "you will always".
- **Clinical vocabulary about the learner** — "disorder", "diagnosis",
  "symptom", "deficit", "impaired", "patient", "ADHD", "autism", "dementia".
- **Statements too short to inform** — fewer than six words.

Constructs graded `weak` are excluded from the profile entirely, not reported
with a caveat. Instruments with restricted licences are declared but never
served. A violation raises; it does not warn.

---

## Security

Every control maps to a known CVE class and is exercised by a test:

| Control | CVE class |
|---|---|
| Path containment | CVE-2021-42740, zip-slip CVE-2018-1002200 |
| Archive budget | CVE-2019-1010206, CVE-2023-45853 |
| XML hardening | CVE-2022-25314, CVE-2023-43644 |
| YAML safety | CVE-2020-14343 |
| SSRF guard | CVE-2024-28849 |
| Output encoding + CSP | CVE-2024-4367 |
| Prototype pollution | CVE-2023-26136 |
| Timing-safe compare | CVE-2023-46809 |
| Secure tokens | CVE-2024-21538 |
| SQL injection | CVE-2022-31197 |
| No deserialisation | pickle-RCE class |

Plus: loopback-only binding, a per-run bearer token on every mutating endpoint
(localhost-CSRF guard), Host-header allowlisting (DNS rebinding), 8 MiB body
caps, and no tracebacks leaked to clients.

---

## Research foundation

Five dossiers under `docs/research/`, each with an explicit epistemic policy
and `[UNVERIFIED]` markers where a citation could not be confirmed:

| Dossier | Size | Covers |
|---|---|---|
| 01-cognitive-batteries | 54 KB | COSMOS, CANTAB, NIH Toolbox, PennCNB, BrainHQ/ACTIVE, Lumosity, dual n-back, the transfer critique |
| 02-social-cognition-and-behaviour | 86 KB | ToM tasks, economic games, personality, impulsivity/risk, loneliness, serious games |
| 03-cognitive-decline-and-brain-fog | 40 KB | Brain-fog scales, objective vs subjective, FINGER, POINTER, long COVID, exercise, sleep, dose-response |
| 04-mcp-catalogue | 36 KB | Every learning-relevant MCP server with transport, auth, config |
| 05-question-generation-and-adaptive-learning | 50 KB | Question taxonomy, AQG, retrieval practice, FSRS equations, desirable difficulties, BKT/IRT/CAT, the 85% rule |

**The honest headline:** game-based cognitive *assessment* has far stronger
psychometric support than game-based cognitive *training*. CortexForge's
defensible claim is measurement plus calibrated feedback — not "brain training
makes you smarter."

---

## Licence

MIT. See `LICENSE` for the notices on third-party instruments and health
claims.
