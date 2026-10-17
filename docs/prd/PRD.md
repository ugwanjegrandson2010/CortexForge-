# CortexForge — Product Requirements Document

**Version:** 1.0
**Status:** Implemented and verified (see §12 Verification Record)
**Date:** 2026-10-17
**Owner:** ugwanjegrandson2010

---

## 0. One-paragraph summary

CortexForge is a local-first adaptive learning system that measures the learner
before it teaches them, generates questions in any style from the learner's own
source material, schedules those questions with a modern spaced-repetition
algorithm, and tells the learner honest, falsifiable things about how they
behave and what role they occupy in a group. It is explicitly built to **not
pamper** the learner, to be **defensible to a hostile scientific critic**, and
to **reduce cognitive decline and brain-fog formation** through a protocol
grounded in the published evidence rather than in marketing. It ships with
every MCP server pre-declared so the learner's only remaining step is OAuth.

---

## 1. The problem

Three failures in existing learning software:

1. **It teaches before it measures.** Every learner gets the same interface and
   the same difficulty curve, so the first two weeks are wasted calibrating.
2. **It flatters.** Streaks, confetti, "Great job!" — praise for attendance
   rather than for learning. The evidence is unambiguous that this degrades
   calibration: learners leave believing they know things they do not.
3. **It overclaims.** "Brain training makes you smarter" is not supported.
   Far transfer is not established (Nguyen et al. 2022; Owen et al. 2010).
   Products that claim it are lying, and the lie is expensive because the
   learner stops doing the things that do work.

CortexForge is built on the opposite premises:

- Measure first, with validated behavioural tasks.
- Say only what the evidence supports, and attach the uncertainty.
- Prefer the interventions with the largest real effects — which are sleep,
  exercise, and social contact, not brain games.

---

## 2. Goals and non-goals

### Goals

| # | Goal | Success criterion |
|---|------|-------------------|
| G1 | Profile the learner before teaching | Onboarding extracts ≥ 10 facts and produces a written contract |
| G2 | Generate questions in any style from the learner's source | ≥ 18 native styles, 3 LLM styles, zero fabricated items |
| G3 | Schedule optimally | FSRS-4.5 with predicted-recall calibration error < 10 points |
| G4 | Do not pamper | Zero praise-without-information strings in any learner-facing output |
| G5 | Reduce cognitive decline / brain fog | Protocol matches published dose-response; subjective + objective tracked |
| G6 | Ship with MCP pre-wired | ≥ 12 core servers declared; only OAuth remains for the user |
| G7 | Be honest | Every claim carries an evidence grade; no clinical language about the learner |
| G8 | Run everywhere | Linux (all distros), macOS, Windows, iOS, Android, web |

### Non-goals

- **Not a diagnostic tool.** It does not and will not diagnose ADHD, autism,
  dementia, depression, or anything else. Clinical constructs are declared in
  the registry and refused by the profiler.
- **Not a brain-training product.** It does not claim far transfer.
- **Not a social network.** No feeds, no follower counts, no engagement loops.
- **Not a cloud service.** Local-first; the database never leaves the device
  unless the learner exports it.

---

## 3. Users

**Primary — the deliberate self-learner.** 22–55, has a specific subject and a
reason. May be studying for a certification, rebuilding ability after illness
(long COVID brain fog is the most common presentation), or learning a field
deeply for its own sake. Technically comfortable enough to paste text and
authorise an OAuth app. Distrusts gamification.

**Secondary — the recovering learner.** Has measurable cognitive complaints.
Needs the system to distinguish "I feel foggy" from "my performance dropped",
because those are different problems with different fixes.

**Tertiary — the researcher.** Wants the raw trial-level data, the scoring
functions, and the citations. The system must be auditable by this user or it
is not credible.

---

## 4. The honesty contract (the load-bearing requirement)

This is the requirement that everything else serves. It is enforced in code,
not in prose.

### 4.1 Anti-pampering

`profile.validate_statement()` rejects any learner-facing string containing:

- **Praise without information** — "great job", "well done", "you're doing
  amazing", "good effort", "almost there", "you're a natural", "gifted".
- **Unfalsifiable character claims** — "you are a good person", "you are
  lazy", "you are intelligent", "you will always", "you will never".
- **Clinical vocabulary about the learner** — "disorder", "diagnosis",
  "symptom", "deficit", "impaired", "abnormal", "patient", "ADHD", "autism",
  "dementia".
- **Statements too short to inform** — fewer than six words.

Every generated statement is passed through this validator before it reaches
the learner. A violation raises, it does not warn.

### 4.2 Evidence grading

Every construct carries a grade: `strong`, `moderate`, `weak`, or `none`.

- `strong` — multiple independent replications, meta-analytic support.
- `moderate` — replicated but with caveats.
- `weak` — single study, contested, or poor psychometrics.
- `none` — exploratory only.

**Weak constructs are excluded from the profile entirely.** They are not
reported with a caveat; they are not reported. The RMET analogue is the worked
example: the construct is real, the stimulus set is copyrighted, the
psychometrics are contested (Oakley 2016; Kittel 2022), so the system offers it
as practice and refuses to characterise the learner from it.

### 4.3 Licence discipline

`instruments.REGISTRY` declares every instrument with its licence:

- `open` — may be served.
- `restricted` — declared but never served (RMET originals).
- `clinical_only` — declared, never served, never scored (ASRS).

`servable_tasks()` filters on this. `validate_registry()` fails the build if an
open task has no citations or a clinical task is marked open.

### 4.4 Falsifiability

The learning contract names what would prove it wrong:

- If measured success rate sits outside 75–95% for three consecutive sessions,
  the difficulty model is wrong.
- If predicted recall diverges from actual recall by more than 10 points over
  100 reviews, the scheduler is miscalibrated.
- If confidence–accuracy bias does not shrink over four weeks, the calibration
  feedback is not working.
- If self-reported clarity does not improve while task performance does, the
  system is training the task and not the person.

---

## 5. Functional requirements

### 5.1 First-run onboarding (G1)

**FR-1.1** On first open, the system runs a 13-probe sequence, ~45 minutes
total, each probe stating its purpose in plain language before it runs.

**FR-1.2** Probes adapt. A probe whose question is already answered by an
earlier probe is skipped, and the skip reason is recorded and shown.

**FR-1.3** The learner may leave at any point. Partial onboarding produces a
valid contract with a smaller evidence base, and the contract says so.

**FR-1.4** The sequence covers: goal type, subject and its shape, available
source material, cognitive baseline (attention, working memory, speed),
confidence calibration, social behaviour (fairness, altruism, cooperation,
strategy), social preference orientation, theory of mind, social
connectedness, brain-fog baseline, real time constraints, and difficulty
preference.

**FR-1.5** Output is a `LearningContract`: goal, subject shape, session length
and frequency, target success rate, applicable question styles, the
intervention plan, the falsifiers, and the explicit gaps.

**FR-1.6** The contract is readable prose the learner can challenge, not a
settings dump.

### 5.2 Source ingestion (G2)

**FR-2.1** Accept pasted text, files, and content pulled from connected note
systems (Notion, Obsidian, Joplin, Logseq) via MCP.

**FR-2.2** Cap source size at 32 MiB per document, 4 M characters after
extraction. Reject larger before reading into memory.

**FR-2.3** Store a SHA-256 of the normalised text so re-ingestion is
idempotent.

**FR-2.4** Sanitise all text: strip control characters, normalise to NFC, cap
length. Control characters are removed rather than escaped — they have no
legitimate place in question text and are a log-injection and terminal-escape
vector.

### 5.3 Question generation (G2)

**FR-3.1** Generate questions in any of these styles from the learner's own
source. Native (no LLM required):

| Style | Bloom | What it tests |
|---|---|---|
| `cloze` | remember | Term recall in context |
| `definition` | understand | Concept articulation |
| `wh_question` | remember | Answer-aware gap fill |
| `true_false_justify` | evaluate | Verdict **plus** reasoning |
| `ordering` | understand | Sequence reconstruction |
| `error_spotting` | analyse | Finding a planted error |
| `worked_example_completion` | apply | Completing a derivation |
| `analogy` | analyse | Relational mapping |
| `list_recall` | remember | Uncued enumeration |
| `numeric` | apply | Quantity and units |
| `causal_chain` | understand | Mechanism, not restatement |
| `compare_contrast` | analyse | Discriminating two things |
| `counterexample` | create | Falsifying a claim |
| `transfer` | create | Cross-domain application |
| `socratic` | evaluate | Surfacing hidden assumptions |
| `feynman` | understand | Jargon-free explanation + gap |
| `prediction_verify` | evaluate | Commit, then revise on evidence |
| `steelman` | evaluate | Strongest opposing case |

LLM-required (declared, never faked): `essay`, `open_dialogue`,
`proof_derivation`.

**FR-3.2** Every question carries a mandatory `source_span`. A question with no
traceable source is rejected at construction.

**FR-3.3** A style the source cannot support is **skipped and reported**, never
fabricated. The skip report names the style and the reason.

**FR-3.4** `true_false_justify` always demands justification in the prompt. A
bare "true"/"false" scores zero. This is stated in the prompt itself.

**FR-3.5** Questions are ordered by Bloom level (recall first) and can be
interleaved by skill so consecutive items rarely share a skill.

### 5.4 Scheduling (G3)

**FR-4.1** Implement FSRS-4.5: difficulty `D`, stability `S`, retrievability
`R(t,S) = (1 + FACTOR·t/S)^DECAY` with `DECAY = -0.5`,
`FACTOR = 0.9^(1/DECAY) − 1`.

**FR-4.2** `R(t=S) = 0.9` by construction — verified by test.

**FR-4.3** Interval for a target retention is the analytic inverse of `R`.

**FR-4.4** Lapses reduce stability and move the card to `relearning`.

**FR-4.5** Difficulty is clamped to [1, 10] and mean-reverts toward the Easy
anchor.

**FR-4.6** Session queue is due-first, hardest-first, with banded interleaving.

### 5.5 Difficulty calibration (G4)

**FR-5.1** Item selection targets a success probability of **0.85** by default
— the error-driven-learning band (Wilson et al. 2019, *Nat. Commun.* 10:4646).

**FR-5.2** The learner may choose 0.70 (gentler) or 0.60 (maximum) at
onboarding, and the choice is recorded in the contract.

**FR-5.3** The system never targets 1.0. A learner at 100% is not learning;
the session summary says so explicitly ("This set was too easy to produce
learning").

**FR-5.4** Session summaries report one of four honest verdicts:
`under-challenged` (≥90%), `in the productive band` (75–90%),
`struggling productively` (50–75%), `over-loaded` (<50%).

### 5.6 Knowledge tracing

**FR-6.1** Bayesian Knowledge Tracing per skill with the four standard
parameters (`p_L0`, `p_T`, `p_S`, `p_G`), updated on every attempt.

**FR-6.2** IRT 2PL/3PL for item parameters, with Fisher information for
selection and Newton–Raphson MLE for ability.

**FR-6.3** Elo rating per item as a fallback difficulty estimator.

**FR-6.4** Mastery threshold at `p_known ≥ 0.95`.

### 5.7 Behavioural profiling (G1, G7)

**FR-7.1** Serve 20 instruments across cognitive and social domains. Each
declares mechanics, scoring, evidence grade, licence, and citations.

**FR-7.2** Refuse to serve restricted and clinical instruments.

**FR-7.3** Every observation carries a confidence label (`low`, `moderate`,
`high`) derived from trial count and evidence grade.

**FR-7.4** Observations below 8 trials are marked provisional in the text.

**FR-7.5** Every observation carries a caveat naming what it does **not**
measure.

**FR-7.6** Infer a group role (Sustainer, Enforcer, Competitor, Giver,
Withholder, Reciprocator, Unclassified) with its basis listed, and note when
the basis is a single task.

**FR-7.7** Infer a study shape (Overconfident self-assessor, Broad but
shallow, Under-reviewing, Backlogged, Steady) from the learner's own metrics.

**FR-7.9** Provide PennCNB-style composite scoring: raw accuracy and speed
converted to z-scores, the speed z sign-flipped, and efficiency as the mean of
the two. This is the most reusable scoring architecture in the literature
because it makes tasks with different natural scales comparable. When the
reference values are the learner's own baseline, the result must be labelled a
within-person index and never presented as a norm.

**FR-7.10** Provide NIH Toolbox two-vector scoring for accuracy-and-speed
tasks: accuracy and RT each scored 0–5 and summed to 0–10, with the Toolbox's
own rule that **below 80% accuracy the total is the accuracy vector alone**,
because speed is not interpretable when the learner is not getting the items
right.

### 5.8 Cognitive-decline and brain-fog protocol (G5)

**FR-8.1** Track subjective clarity (5 domains: holding a thought, finding a
word, following a conversation, remembering why, rereading) at baseline and
longitudinally.

**FR-8.2** Track objective performance separately, and report the two
separately. Self-reported fog correlates weakly with test performance
(approximately 0.1 SD across 25,796 participants; Jennings et al. 2023); a
system that conflates them is lying to the learner.

**FR-8.2a** Surface the *divergence* between subjective and objective as its
own signal, because the divergence is informative and the two must never be
averaged. `divergence_signal()` returns one of four states:

| State | Pattern | Response |
|---|---|---|
| `concordant_impairment` | reports difficulty, performance also down | reduce load until the trend reverses |
| `subjective_only` | reports difficulty, performance intact | show the objective data; the feeling is real but is not a measurement of capacity |
| `objective_only` | performance down, no complaint | act first — this will not prompt self-referral |
| `concordant_healthy` | both within range | continue |

**FR-8.2b** The system must never emit a merged "cognitive health" score.

**FR-8.2c** State plainly that home-based cognitive training was found
*ineffective* in the Lampit et al. meta-analysis, and that the interventions
with the largest measured effects on cognition are physical activity and sleep
— which this system logs as covariates rather than pretending to replace.

**FR-8.3** Protocol rules grounded in the dose-response evidence:

- Adaptive difficulty held near the target success rate.
- Spaced review on FSRS, not a fixed calendar.
- Interleaved practice within a session.
- Retrieval before review — rereading is not offered as a study method.
- Confidence rating on every item.
- Sessions split into blocks with breaks when ≥20 minutes.
- Shorter blocks and more breaks when the fatigue baseline is elevated.
- Session ends early rather than pushing through fatigue.
- Physical activity and sleep logged as covariates, because both have larger
  effects on cognition than any cognitive training does.

**FR-8.4** Claims discipline. The system **may** claim: improved retention of
the learner's own material; measured calibration improvement; tracked
subjective clarity. It **must not** claim: increased intelligence, prevention
of dementia, treatment of any condition, or far transfer from training tasks.

### 5.9 MCP integration (G6)

**FR-9.1** Ship with ≥ 12 core MCP servers pre-declared. The learner's only
step is OAuth.

**FR-9.2** Notion and Obsidian are mandatory inclusions and must be able to
assimilate completely into the learning system as source corpora.

**FR-9.3** Catalogue ≥ 30 servers across knowledge bases, spaced repetition,
academic, documents, code, web, memory, productivity, math, and media.

**FR-9.4** Never inline a secret in the generated config. API-key servers
reference an environment variable; OAuth servers carry only a URL and a token
cache path.

**FR-9.5** Write the config with `0600` permissions.

**FR-9.6** Implement OAuth discovery per RFC 9470 (protected resource
metadata) then RFC 8414 (authorization server metadata).

**FR-9.7** Re-validate every redirect target before following it.

**FR-9.8** Store tokens outside the repository with `0600` permissions, and
redact them in any status output.

### 5.10 Data rights

**FR-10.1** Full export of all learner data as JSON.

**FR-10.2** Full erasure, requiring the literal confirmation string `ERASE`.

**FR-10.3** Erasure removes every row across every table, verified by test.

---

## 6. Non-functional requirements

### 6.1 Security (CVE-informed)

Every control is tied to a known CVE class and exercised by a test.

| Control | Function | CVE class |
|---|---|---|
| Path containment | `safe_join` | CVE-2021-42740, zip-slip CVE-2018-1002200 |
| Archive budget | `check_archive_budget` | CVE-2019-1010206, CVE-2023-45853 |
| XML hardening | `parse_xml_safe` | CVE-2022-25314, CVE-2023-43644 |
| YAML safety | `load_yaml_safe` | CVE-2020-14343 |
| SSRF guard | `validate_outbound_url` | CVE-2024-28849 |
| Output encoding | `escape_html`, CSP | CVE-2024-4367 |
| Prototype pollution | `safe_merge`, `load_json_only` | CVE-2023-26136 |
| Timing-safe compare | `constant_time_compare` | CVE-2023-46809 |
| Secure tokens | `secure_token` | CVE-2024-21538 |
| SQL injection | `assert_parameterised` | CVE-2022-31197 |
| No deserialisation | `load_json_only` | pickle-RCE class |

Additional controls:

- **NFR-S1** Bind to `127.0.0.1` only. Refuse any other host without an
  explicit override.
- **NFR-S2** Require a per-run bearer token for every mutating endpoint, so a
  malicious page in the learner's browser cannot drive the local API
  (localhost-CSRF / DNS-rebinding class).
- **NFR-S3** Validate the `Host` header against an allowlist.
- **NFR-S4** Cap request bodies at 8 MiB.
- **NFR-S5** Emit CSP, `X-Content-Type-Options`, `X-Frame-Options`,
  `Referrer-Policy`, `Permissions-Policy`, COOP, CORP, `Cache-Control: no-store`
  on every response.
- **NFR-S6** Never leak a traceback to the client; log the type and message
  internally.
- **NFR-S7** Render all server data with `textContent`, never `innerHTML`.
- **NFR-S8** Hold the API token in memory only, never `localStorage`.
- **NFR-S9** No third-party scripts, no `eval`, no dynamic `Function`.

### 6.2 Platform support (G8)

| Platform | Mechanism | Status |
|---|---|---|
| Linux — all distros | AppImage, Flatpak, `.deb`, `.rpm`, Arch PKGBUILD, tarball | Build scripts provided |
| macOS | `.app` bundle, `.dmg`, notarisation workflow | Build scripts provided |
| Windows | Portable `.zip`, MSI via WiX | Build scripts provided |
| iOS | Capacitor wrapper, App Store submission assets | Build scripts provided |
| Android | Capacitor wrapper, Play Store AAB | Build scripts provided |
| Web | The server's own HTTP surface | Implemented and verified |

### 6.3 Performance

- **NFR-P1** Pure-Python core, stdlib only. No NumPy, no Pandas, no compiled
  extensions — so it runs on CPUs without AVX/SSE4 (verified on this machine,
  which supports only SSSE3).
- **NFR-P2** Cold start under 2 seconds.
- **NFR-P3** Question generation from a 10 k-character source in under 1
  second.
- **NFR-P4** Concurrent request handling via per-thread SQLite connections in
  WAL mode.

### 6.4 Accessibility

- **NFR-A1** WCAG 2.2 AA contrast in the dark theme.
- **NFR-A2** Full keyboard operability; visible focus rings.
- **NFR-A3** `role="status"` with `aria-live="polite"` on the status region.
- **NFR-A4** Respect `prefers-reduced-motion`.
- **NFR-A5** No colour-only information.

---

## 7. Architecture

```
cortexforge/
├── src/cortexforge/
│   ├── security.py      CVE-mapped controls, all testable
│   ├── store.py         SQLite, parameterised, thread-local connections
│   ├── scheduler.py     FSRS-4.5
│   ├── tracing.py       BKT, IRT, Elo, calibration
│   ├── questiongen.py   18 native styles + 3 LLM styles
│   ├── instruments.py   Task registry, evidence grades, 14 scorers
│   ├── profile.py       Observation synthesis, anti-pampering validator
│   ├── onboarding.py    13-probe state machine, learning contract
│   ├── mcp.py           34-server catalogue, OAuth discovery
│   └── server.py        Hardened stdlib HTTP server
├── web/                 index.html, app.css, app.js
├── tests/               test_core.py, test_security.py
├── scripts/             e2e.py, build/*.sh
└── docs/
    ├── research/        five dossiers, 266 KB
    └── prd/             this document
```

**Data flow:** source text → sanitise → generate → store → schedule → present →
attempt → BKT/IRT update → FSRS reschedule → profile synthesis → honest
feedback.

---

## 8. Research foundation

Five dossiers, each with an explicit epistemic policy and `[UNVERIFIED]`
markers where a citation could not be confirmed.

| Dossier | Size | Covers |
|---|---|---|
| `01-cognitive-batteries.md` | 54 KB | COSMOS, CANTAB, NIH Toolbox, PennCNB, BrainHQ/ACTIVE, Lumosity/NeuroRacer, dual n-back, the transfer critique |
| `02-social-cognition-and-behaviour.md` | 86 KB | ToM tasks, economic games, personality instruments, impulsivity/risk, loneliness, serious games |
| `03-cognitive-decline-and-brain-fog.md` | 40 KB | Brain-fog scales, objective vs subjective, cognitive training evidence, FINGER, POINTER, long COVID, exercise, sleep, dose-response |
| `04-mcp-catalogue.md` | 36 KB | Every MCP server relevant to learning, with transport, auth, and config |
| `05-question-generation-and-adaptive-learning.md` | 50 KB | Question taxonomy, AQG, retrieval practice, FSRS equations, desirable difficulties, feedback, metacognition, BKT/IRT/CAT, the 85% rule |

**The honest headline from the research:** game-based cognitive *assessment*
has far stronger psychometric support than game-based cognitive *training*.
CortexForge's defensible claim is measurement plus calibrated feedback — not
"brain training makes you smarter."

---

## 9. Success metrics

| Metric | Target | How measured |
|---|---|---|
| Onboarding completion | ≥ 70% of starters finish ≥ 10 probes | Server event log |
| Contract accuracy | ≥ 80% of learners agree the contract describes them | In-app single question |
| Calibration improvement | Mean absolute bias falls ≥ 30% over 4 weeks | `calibration_stats` |
| Retention accuracy | Predicted vs actual recall within 10 points over 100 reviews | FSRS log |
| Success-rate band | ≥ 70% of sessions land in 75–90% | Session summaries |
| Pampering leaks | Zero | Validator + test suite |
| Clinical leaks | Zero | Validator + test suite |
| Fabricated questions | Zero | Provenance requirement |

---

## 10. Risks and mitigations

| Risk | Severity | Mitigation |
|---|---|---|
| Learner believes it diagnoses them | High | Clinical vocabulary blocked in code; disclaimer always emitted |
| Learner believes it prevents dementia | High | Claims discipline in §5.8.4; no such copy anywhere |
| Weak-evidence construct drives a life decision | High | Weak constructs excluded from the profile entirely |
| Harsh feedback causes dropout | Medium | Feedback is informative, never punishing; difficulty is learner-selectable |
| MCP token leak | High | 0600 files outside repo, never inlined, redacted in status |
| Local API driven by a hostile page | High | Bearer token + Host allowlist + CSP |
| SQLite corruption under concurrency | Medium | Per-thread connections, WAL, `busy_timeout`, regression tests |
| Overfitting the scheduler to one learner | Low | FSRS parameters are per-learner and re-fittable |

---

## 11. Roadmap

**v1.0 (this release)** — core engine, onboarding, generation, scheduling,
profiling, MCP, hardened server, web client, 224 unit tests, 45 E2E checks.

**v1.1** — in-canvas task rendering (currently the tasks are scored server-side
and the client accepts trial data); FSRS parameter fitting from the learner's
own review history.

**v1.2** — LLM provider integration for the three declared LLM styles, with
rubric-based grading.

**v1.3** — packaged desktop builds for all platforms; mobile wrappers.

**v2.0** — multi-learner study groups using the social instruments as the
actual group protocol.

---

## 12. Verification record

All figures below are from actual runs on this machine, not estimates.

### Unit tests

```
$ .venv/bin/python -m unittest discover -s tests
Ran 224 tests in 8.840s
OK
```

Coverage by area:

| Area | Tests | What is proven |
|---|---|---|
| FSRS scheduler | 17 | `R(t=S)=0.9`; interval inversion; lapse handling; difficulty bounds; queue ordering |
| BKT | 7 | Posterior update direction; mastery convergence; probability bounds |
| IRT | 11 | Monotonic ICC; `P=0.5` at difficulty; information peak; θ update direction; **selection targets 0.85 and never 1.0** |
| Calibration | 6 | Brier bounds; over/under-confidence detection; gamma |
| Question generation | 20 | All 18 native styles produce; every question has provenance; no pampering; Bloom ordering; interleaving |
| Store | 17 | Round-trips; GDPR export/erase; SQL-injection-as-data; **concurrency regression** |
| Instruments | 20 | Registry validity; restricted/clinical refused; 14 scorers correct |
| Profile | 9 | Role inference; limits always present; clinical task refused |
| Anti-pampering | 14 | **Every** pampering, unfalsifiable, and clinical phrase blocked |
| Onboarding | 19 | Sequence completes; adaptive skipping; contract classification; clamping; falsifiers |
| MCP | 18 | Notion+Obsidian present; **no secrets inlined**; 0600 permissions; OAuth separation |
| Security | 70 | Every CVE-mapped control, positive and negative |

### End-to-end API tests

```
$ .venv/bin/python scripts/e2e.py http://127.0.0.1:8731 "$TOKEN"
45/45 checks passed
ALL E2E CHECKS PASSED
```

Covers: liveness, manifest, auth enforcement (missing/wrong/correct token),
Host-header rejection, three path-traversal vectors, the full onboarding flow,
source ingestion, generation across ≥15 styles with provenance on every item,
session and attempts, profile honesty checks, MCP plan and config, export and
erase, and five input-validation rejections.

### Browser verification

Driven against a live server:

```
title: CortexForge
tabs: Setup | Sources | Study | Profile | Integrations
h1: Build your learning system
bg: rgb(14, 17, 22)          (CSS applied)
status: ready
style chips: 21
mcp table rows: 9
mcp oauth pills: 8
probe card: What you are actually trying to do
progress: 0/13 complete · 55 min remaining
```

### Bugs found and fixed during verification

1. **Causal/contrast/numeric generators produced nothing.** Clause-initial
   markers ("Because…", "In contrast…") left the cause span empty. Fixed to
   handle both clause orders; numeric now handles single-value statements.
2. **Analogy and definition generators mangled text** ("pproximately").
   Over-greedy regex. Replaced with anchored patterns.
3. **`safe_join` allowed symlink escape.** Containment was checked before
   resolution. Now resolves every component first.
4. **`load_yaml_safe` crashed when PyYAML was absent.** Tag check ran after the
   import. Reordered.
5. **SQL guard missed `{}` and `%s` placeholders.** Real injection vectors.
   Added to the pattern.
6. **SVO scorer could not represent competitiveness.** `atan2(other, self)`
   spans only 0–90°. Reimplemented on the ring's deviation frame so all four
   published orientations are reachable.
7. **`grade_feedback` emitted "Correct."** which the validator rejects as
   uninformative. Rewritten to always inform.
8. **Onboarding skip logic read a key nothing wrote** (`source_available`).
   Added `_source_present()` and used it in both places.
9. **SQLite connections were thread-bound but the server is threaded.** Every
   request after the first raised `ProgrammingError`. Fixed with thread-local
   connections, WAL, and `busy_timeout`; two regression tests added.

### Environment

- Python 3.14.8, stdlib only (no NumPy/Pandas — this CPU supports only SSSE3)
- Arch Linux, 2 cores, 3 GB RAM
- Server verified on `127.0.0.1:8731`

---

## 13. Open questions

1. Should the three LLM-required styles be enabled by default when a provider
   is configured, or opt-in per session?
2. Should the social instruments run before or after the learner has trust in
   the system? Running them first yields cleaner data but a worse first
   impression.
3. What is the right re-test interval for the behavioural battery — 4 weeks,
   8 weeks, or event-driven on a performance drop?
4. Should the learning contract be renegotiable mid-course, and if so, how
   often before it stops being a contract?

---

## 14. Appendix — claims we may and may not make

**May claim:**

- "Measures your attention, working memory, and processing speed with tasks
  adapted from validated instruments."
- "Generates questions in 18 styles from your own material."
- "Schedules review with FSRS, a modern spaced-repetition algorithm."
- "Tracks your confidence calibration and tells you when it drifts."
- "Tracks your self-reported mental clarity over time."
- "Keeps you at the difficulty where learning is fastest, which means you will
  fail about one item in seven."

**Must not claim:**

- "Makes you smarter."
- "Prevents dementia" or "reduces your risk of Alzheimer's."
- "Treats brain fog" or "cures long COVID."
- "Diagnoses ADHD/autism/depression."
- "Improves your IQ."
- "Trains your brain to transfer to other tasks."
- "Clinically proven."

**Must always state:**

- "These are behavioural observations from short tasks, not a personality test."
- "Every number here has a confidence label; 'low' means the estimate is
  unstable."
- "Constructs with weak evidence are excluded from this profile entirely."
- "Nothing here is a clinical assessment and nothing here diagnoses anything."
- "Behaviour measured in a game is a sample of behaviour, not a summary of a
  person."
