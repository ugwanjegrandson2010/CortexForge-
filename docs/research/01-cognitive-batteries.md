# Game-Based Cognitive Assessment Batteries: A Rigorous Research Dossier

**Purpose.** Reference for implementing scoring algorithms in CortexForge. For each instrument: task mechanics (stimuli, timing, adaptive rule, trial counts), claimed construct, scoring/outcome metric, reliability/validity evidence, and open-source vs proprietary status.

**Epistemic policy.** Every claim is tagged `[VALIDATED]` (replicated, peer-reviewed, adequate sample), `[MODERATE]` (peer-reviewed but limited replication or contested), `[SPECULATIVE]` (plausible but not established), or `[UNVERIFIED]` (citation could not be confirmed during this research pass). Citations I could not confirm against a primary source are marked `[UNVERIFIED]`. Do not fabricate from this document — verify DOIs before publication.

**Author's note on honesty.** This dossier is deliberately structured around a hard truth: *game-based cognitive **assessment*** (measuring ability) has far stronger psychometric support than *game-based cognitive **training*** (improving ability). CortexForge's defensible claim is measurement + calibrated feedback, not "brain training makes you smarter." Section 8 is the load-bearing section for the hostile critic.

---

## 0. Executive orientation

| Instrument | Primary use | Open source? | Evidence quality (as an *assessment*) |
|---|---|---|---|
| COSMOS (Basel) | Research phenotyping, open science | Platform open-access; code not fully public | Weak–Moderate (pilot, calibration ongoing) |
| CANTAB | Clinical trials, diagnosis support | Proprietary (Cambridge Cognition) | Strong (large clinical validation literature) |
| NIH Toolbox Cognition Battery | Population research, lifespan norming | Public-domain instruments; app proprietary | Strong (NIH-funded validation monograph) |
| PennCNB | Genomics, large-scale psychiatric research | Publicly available (free for research) | Strong (large N, heritability established) |
| BrainHQ / Posit Science | Commercial training + assessment | Proprietary (patented) | Moderate–Strong for *speed-of-processing* specifically |
| Lumosity | Commercial training + assessment | Proprietary | Weak–Moderate (self-published RCTs) |
| Dual n-back | WM training research paradigm | Open (trivially reimplementable) | Strong as a *task*; far-transfer claim contested |
| NeuroRacer | Lab training paradigm | Not released | Moderate (single landmark study) |

---

## 1. COSMOS (Cognitive Science Metrics Online Survey) — University of Basel

**Source.** Aeberhard A, Gschwind L, Kossowsky K, Luksys G, Papassotiropoulos A, de Quervain D, Vogler C (2019). "Introducing COSMOS: a Web Platform for Multimodal Game-Based Psychological Assessment Geared Towards Open Science Practice." *Journal of Technology in Behavioral Science* 4(3), 234–244. DOI 10.1007/s41347-018-0071-5. `[VALIDATED as a platform description]`
Platform URL: https://cosmos.psycho.unibas.ch/

**Status.** Open-access publication (CC-BY 4.0). Platform is publicly accessible. The paper describes it as being "in its pilot phase," with five prototype games "undergoing refinement and calibration as psychometric data is being collected." **No published normative data or full validation paper was found in this research pass.** `[UNVERIFIED: full psychometric validation]`

**Claimed constructs (from abstract):** theory of mind, attention, working memory, episodic long- and short-term memory, spatial memory, reaction times, eye-hand coordination, impulsivity, humor appreciation, altruism, fairness, strategic thinking, decision-making, risk-taking.

### 1.1 Task list and mechanics

**HoNk-Back** — gamified N-back (based on Owen et al. 2005 N-back paradigm).
- *Construct:* working memory updating.
- *Mechanics:* Player is a truck driver overtaken by cars. Cars appearing in the rearview mirror trigger a response: flash headlights at cars that also gave a light signal, or wave at cars that overtook without a headlight signal. **Tilting the rearview mirror controls the N condition** (regulates how many cars disappear into the blind spot).
- *Adaptive rule:* N is set by mirror tilt (manual/player-controlled rather than staircase-adaptive in the classic sense).
- *Metric:* response accuracy on N-back matches; reaction time.
- *Note:* This is the closest COSMOS task to a browser-reimplementable paradigm.

**Drag Race** — reaction time / RT variability.
- *Construct:* simple reaction time (SRT), foreseeable reaction time (FRT), response-time variability.
- *Mechanics:* Two yellow lights = get ready; green light after a **variable random interval** → measure spontaneous RT. Gear-shifting requires a defined motor sequence: release accelerator (spacebar) → hit gear button (return) → release → push accelerator again. A continuously moving revmeter defines the optimal shift moment → measures predictable RT.
- *Metric:* SRT, FRT, and **variation in response-time accuracy** across repeated runs.
- *Caveat (from the paper itself):* authors explicitly acknowledge timing noise from monitor response time, OS scheduling, and key debouncing (citing Garaizar et al. 2014; Salmon et al. 2017). They argue the error is small relative to human variability (citing Damian 2010). **For CortexForge: browser RT measurement carries the same caveat and must be documented.**

**Frog Life** — sustained attention / vigilance (go/no-go + signal detection).
- *Construct:* sustained attention, visual vigilance.
- *Mechanics:* Control a frog eating dragonflies (go) while avoiding hornets (no-go). Insects become catchable only after entering a proximity circle; snatch with left/right cursor keys by side of emergence. Simultaneously, predators are announced by **color changes in one of three display details** (pond water, clouds, bush) → press spacebar to escape.
- *Adaptive rule:* After every successful escape, difficulty increases: insect speed accelerates, color-change time decreases, hue-intensity change becomes less pronounced.
- *Scoring:* Munch Score (+ for dragonflies, − for hornets); points for fast escape RTs; 3 health points lost on false alarms; game-over on missed predator.
- *Metric:* go/no-go accuracy, false-alarm rate, escape RT, difficulty level reached.
- *Database schema (relevant for reimplementation):* `games`, `rounds` (with `difficulty`), `actions` (with `action_types`), `levels` tables linked by user ID.

**Shortcuts** — two-tier short-term memory.
- *Construct:* episodic picture recognition + sequence learning.
- *Mechanics:* Memorize a set of picture stimuli (**3 to 10 items**) from a chosen category (food/animals/sport). Except in the "easy" condition (3 items), also memorize a **sequence of differently colored and shaped symbols**. During play, control a panda climbing a rock wall; at intervals, identify which picture was shown at the start (correct → bird lifts panda = "shortcut"), and at predefined intervals reproduce the symbol sequence in order.
- *Metric:* picture recognition accuracy, sequence reproduction accuracy, speed points.

**Joyrate** — theory of mind (a subtype).
- *Construct:* theory of mind / mentalizing about others' preferences.
- *Mechanics:* Rate jocularity of 10 items (cartoons, memes, written jokes) on 0–10, plus agreement with 18 statements (politics, religion, society, sports, education, personality). Then guess how another (randomly assigned) person rated each item. Demographic info on the other player (gender, age, education) is always given; further info unlocked with in-game currency (JokeCoins).
- *Metric:* accuracy of estimating the other person's ratings.

### 1.2 Assessment for CortexForge
- **Strengths:** explicit open-science design; the paper itself frames COSMOS as a vehicle for settling the brain-training question without industry conflict of interest; SQL schemas documented; browser-native.
- **Weaknesses:** pilot-phase, no published norms found, no published reliability/validity coefficients found. Treat all COSMOS constructs as `[SPECULATIVE]` until validation papers appear.
- **Reusable mechanics:** HoNk-Back (N-back), Frog Life (go/no-go + signal detection), Shortcuts (recognition + sequence), Drag Race (RT paradigms).

---

## 2. CANTAB (Cambridge Neuropsychological Test Automated Battery) — Cambridge Cognition

**Status.** **Proprietary.** Commercial licensing via Cambridge Cognition (cambridgecognition.com) and Lafayette Instrument. Touchscreen-based, historically validated on the Monkey CANTAB platform. Normative data "available for selected tests, test variants and outcome measures." `[VALIDATED as proprietary clinical battery]`

**Structure (from Cambridge Cognition product pages):**
- *Attention & psychomotor speed:* Match To Sample Visual Search (MTS), Motor Screening Task (MOT), Rapid Visual Information Processing (RVP), Reaction Time (RTI).
- *Emotion & social cognition:* Emotional Bias Task (EBT), Emotion Recognition Task (ERT).
- *Executive function:* Cambridge Gambling Task (CGT), Intra-Extra Dimensional Set Shift (IED), Multitasking Test (MTT), One Touch Stockings of Cambridge (OTS), Spatial Working Memory (SWM), Stockings Of Cambridge (SOC), Stop Signal Task (SST).
- *Memory:* Delayed Matching To Sample (DMS), Digit Span (DGS), Paired Associates Learning (PAL), Pattern Recognition Memory (PRM), Spatial Span (SSP), Verbal Recognition Memory (VRM), Verbal Paired Associates (VPA).

### 2.1 Detailed task mechanics and outcome measures

**Paired Associates Learning (PAL)** — visual memory / new learning. Sensitive to early Alzheimer's disease.
- *Mechanics:* Boxes shown in a circle, opened in randomized order to reveal a pattern (or empty). Then each pattern appears in the center one at a time; select the box where it was. **Error → entire trial repeated** (with re-randomized order). Difficulty escalates: **2, 4, 6, 8, 12 boxes** (one protocol reports 20 trials total, 4 trials each at 2/4/6/8/12 boxes; a clinical-trials protocol reports 2→8 patterns). Pre-training stage for familiarization. Novel patterns every trial.
- *Outcome measures:* **PAL Total Errors Adjusted** (total errors adjusted for stages not completed due to early discontinuation); **PAL First Attempt Memory Score** (times the correct box chosen on first attempt across stages); stages completed; mean errors to success.
- *Reliability:* PAL is among the more reliable CANTAB tasks. Web-vs-lab ICC for PAL performance indices ρ ≥ 0.60 (Feenstra et al. 2020, PMID 32749999). One-year stability moderate-to-good in children. `[MODERATE–VALIDATED]`

**Spatial Working Memory (SWM)** — visuospatial WM + strategy.
- *Mechanics:* Colored boxes on screen; search for a hidden blue "token" by opening boxes one at a time. Once found, a new token is hidden (never in a previously-used box). **30 trials total**; box count increases up to **8 boxes** (4/6/8 token conditions). Self-ordered task.
- *Outcome measures:* **SWM Between Errors** (times a previously-found box is revisited across all assessed trials); **SWM Strategy** (number of unique starting points used in the 6- and 8-box tasks; **lower = better strategy**).
- *Reliability:* ICC 0.51–0.59 at 3 weeks in children (Fisher et al. 2011); web-vs-lab ρ ≥ 0.60. `[MODERATE]`

**Rapid Visual Information Processing (RVP)** — sustained attention.
- *Mechanics:* White box center screen; single digits flash at **100 digits/minute**. A target sequence of three digits (e.g., 5-2-7) is displayed alongside; respond as fast as possible when it appears. ~7–8 minutes.
- *Outcome measures:* **RVP A′** (signal-detection sensitivity to target; higher = better); **RVP Median Response Latency** (median RT on correct trials); **RVP Probability of False Alarm** (false alarms / (false alarms + correct rejections)).
- *Reliability:* internal consistency α = 0.49 for RVP A′ (low); one-year stability coefficient 0.62. `[MODERATE–WEAK]` — note the low internal consistency.

**Reaction Time (RTI)** — motor and mental response speed.
- *Mechanics:* Hold a response button; stimulus appears; release button (reaction time), then select the correct target on screen (movement time). Simple and 5-choice variants. ~3 minutes.
- *Outcome measures:* **RTI Median Five-Choice Reaction Time** (release latency); **RTI Median Five-Choice Movement Time** (release → target selection); total errors.
- *Reliability:* **The only CANTAB task with acceptable internal consistency** in the Jyväskylä child study (α = 0.87 for 5-choice movement time); stability coefficient 0.67 for movement time. `[MODERATE]`

**Other tasks (mechanics summary):**
- *IED (Intra-Extra Dimensional Set Shift):* rule-learning/shifting; stages 1–9; outcome = stages completed, errors, pre-ED errors, EDS errors. Temporal stability ~0.78 (14–42 days, children).
- *OTS/SOC (One Touch Stockings of Cambridge / Stockings of Cambridge):* Tower of Hanoi-derived spatial planning. OTS outcome: **number solved on first choice**, mean choices to correct, median latency of first choice (OTSMDLFC), median latency to correct.
- *MTT (Multitasking Test):* arrow direction vs. location conflict; outcomes = median latency congruent (ASTLCMD), median latency switching (ASTLSWMD), error scores (Stroop-like interference).
- *ERT (Emotion Recognition Task):* morphing faces; % correct per emotion, overall response latencies.
- *PRM/SRM:* pattern/spatial recognition memory; number correct, median correct latency.
- *DMS (Delayed Matching to Sample):* simultaneous + 0/4/12 s delays; % correct, latency.
- *VRM (Verbal Recognition Memory):* 18-word study phase → immediate free recall → 36-word recognition → 20-min delayed recall.

### 2.2 Reliability summary and CortexForge implication
CANTAB reliability is **task-dependent and often only moderate**. A scoping review of computerized batteries reported CANTAB ICCs from **0.23 to 0.94** depending on task and interval. Internal consistency is acceptable only for RTI in at least one population study. **Lesson for CortexForge: do not assume a task is reliable because it is commercially validated; report per-task reliability in your own population.**

---

## 3. NIH Toolbox Cognition Battery (NIHTB-CB)

**Status.** Instruments are **public-domain / freely usable** (NIH); the administration **app is proprietary** (iPad-based). `[VALIDATED]`

**Source.** Weintraub S, Dikmen SS, Heaton RK, Tulsky DS, Zelazo PD, Bauer PJ, Gershon RC (2013). "Cognition assessment using the NIH Toolbox." *Neurology* 80(11 Suppl 3):S54–S64. Plus the *Monographs of the Society for Research in Child Development* 78(4) 2013 monograph (chapters I–VII). `[VALIDATED]`

**Domain structure:**
- *Crystallized:* Picture Vocabulary Test (TPVT), Oral Reading Recognition Test (TORRT).
- *Fluid:* Flanker Inhibitory Control & Attention, Dimensional Change Card Sort (DCCS), List Sorting Working Memory (LSWM), Picture Sequence Memory (PSM), Pattern Comparison Processing Speed (PCPS).
- *Composites:* Fluid Cognition Composite, Crystallized Cognition Composite, Total Cognition Composite.

### 3.1 Subtests: mechanics, trials, scoring

**Flanker Inhibitory Control and Attention Test**
- *Construct:* inhibitory control + selective attention.
- *Mechanics:* Horizontal row of five stimuli. **Ages 3–7: fish**; **ages 8–85: arrows**. Focus on the central stimulus, ignore flankers. Congruent (all same direction) vs. incongruent (center opposite). **20 trials** for ages 8–85; for ages 3–7, if ≥90% on fish, 20 additional arrow trials. ~3 minutes. (One validation study used 25 trials per block: 16 congruent, 9 incongruent, scoring on the first 20.)
- *Scoring — the "two-vector" method (identical for Flanker and DCCS):*
  - Accuracy vector and RT vector each range **0–5**; total score **0–10**.
  - **If accuracy ≤ 80%: total score = accuracy score.**
  - **If accuracy > 80%: total score = accuracy score + RT score.**
  - Accuracy score = **0.125 × number of correct responses** (40 accuracy points possible: 20 fish + 20 arrows; ages ≥8 automatically receive 20 fish points).
  - RT score uses **raw incongruent median RT**, computed only from correct trials with RT ≥ 100 ms and within 3 SDs of the individual's mean.
- *Reliability:* test–retest ICC 0.73–0.90 (7–21 day interval, adults 20–65); Flanker ICC ≈ 0.74 in a mixed sample. `[VALIDATED]`

**Dimensional Change Card Sort (DCCS)**
- *Construct:* cognitive flexibility / set-shifting.
- *Mechanics:* Two target pictures varying on **shape and color** (e.g., yellow balls, blue trucks). Match bivalent test pictures first by one dimension (e.g., color), then switch. Blocks: practice → preswitch (color) → postswitch (shape) → **30 mixed trials**. Cue word ("shape"/"color") appears **800 ms** before the bivalent target. App gives feedback on correct and incorrect responses.
- *Scoring:* same two-vector accuracy+RT method as Flanker. A "SAA" (speed-accuracy) variant combines accuracy on all trials with log-transformed speed on incongruent trials.
- *Reliability:* ICC 0.71 (total sample); notably lower (0.41) in fragile X syndrome. `[MODERATE–VALIDATED]`

**List Sorting Working Memory (LSWM)**
- *Construct:* working memory (simultaneous storage + manipulation).
- *Mechanics:* Recall and sequence items by size within one category (1-List) then across two categories (2-List). **12 items** presented.
- *Scoring:* **sum of items correctly recalled and sequenced on 1-List and 2-List; range 0–26.**
- *Reliability:* poorer temporal consistency than DCCS/Flanker/PCPS in longitudinal work. `[MODERATE]`

**Picture Sequence Memory (PSM)**
- *Construct:* episodic memory.
- *Mechanics:* Sequence of pictured activities; recall the order.
- *Scoring:* number of adjacent pairs correctly recalled.
- *Reliability:* ICC 0.78 (lowest of the NIH Toolbox measures in one report). `[MODERATE]`

**Pattern Comparison Processing Speed (PCPS)**
- *Construct:* processing speed.
- *Mechanics:* Pairs of simple pictures; decide same/different as fast as possible.
- *Scoring:* **raw score = number correct in 90 seconds; range 0–130** (one source lists "130 items or 85 seconds" — the 90-second figure is from the NIH scoring manual). `[MODERATE: verify exact timing against current manual]`
- *Reliability:* moderate-to-good.

**Picture Vocabulary (TPVT) / Oral Reading Recognition (TORRT)** — crystallized.
- *Reliability:* TPVT ICC 0.80 (95% CI 0.71–0.86); TORRT ICC 0.90 (95% CI 0.85–0.93), comparable to WRAT-4 (0.84). `[VALIDATED]`

### 3.2 Score types (critical for implementation)

- **Uncorrected Standard Score:** mean **100, SD 15**; compares to all test-takers regardless of demographics; intended to monitor **absolute change over time**.
- **Age-corrected Standard Score:** mean 100, SD 15; corrects for age only.
- **Fully Corrected T-Score:** mean **50, SD 10**; adjusts for **age, sex, race/ethnicity (White/Asian, Black, Hispanic, multiracial), and educational attainment** (parental education for ages 3–17). Source: Casaletto KB, Umlauf A, Beaumont J, Gershon R, Slotkin J, Akshoomoff N, Heaton RK (2015). "Demographically corrected normative standards for the English version of the NIH Toolbox Cognition Battery." *J Int Neuropsychol Soc* 21(5):378–391. `[VALIDATED]`
- Casaletto et al. found fully-corrected T-scores are the **best indicator of potential individual impairment** and of deviation from prior functioning.

### 3.3 Validation and its limits (read this carefully)

- **Short-term test–retest:** good (ICC 0.73–0.90 adults; 0.78–0.99 across the whole sample in Weintraub et al. 2013). `[VALIDATED]`
- **Long-term stability in youth (9–15 y, 3-year):** **low-to-moderate**, ICCs **0.31–0.76**, with significant site differences; authors recommend refinement before wide use for impairment determination or longitudinal tracking. (Cambridge *Psychological Medicine*.) `[VALIDATED — and it is a caution]`
- **Practice effects:** documented; reliable-change cutoffs proposed (e.g., DCCS T ≥ 12, Flanker T ≥ 10, LSWM T ≥ 12, PSM T ≥ 17, PCPS T ≥ 11, Fluid Composite T ≥ 9 at 90% CI). `[MODERATE]`
- **Clinical sensitivity:** significant deficits in Fluid Cognition Composite and subtests in clinical samples vs. norms. `[VALIDATED]`

**CortexForge implication:** the fully-corrected T-score approach (demographic adjustment) is the right model for *honest* feedback — it prevents penalizing a learner for education/age and prevents inflating scores. But long-term stability is only moderate; **do not claim precision better than the instrument supports.**

---

## 4. Penn Computerized Neurocognitive Battery (PennCNB)

**Status.** **Publicly available** for research (per the JINS performance-validity paper: "a publicly available collection of tests"). Administered on computer, ~1 hour, fixed order, clickable icons. `[VALIDATED]`

**Sources.** Gur RC, Richard J, Hughett P, Calkins ME, Macy L, Bilker WB, Gur RE (2010). *Neuropsychology*; Moore TM, Reise SP, Gur RE, Hakonarson H, Gur RC (2015). "Psychometric properties of the Penn Computerized Neurocognitive Battery." *Neuropsychology* 29(2):235–246 (PMC4345134); Gur et al. (2012) *Neuropsychology*; Roalf et al. (2014). `[VALIDATED]`

### 4.1 Domains and tests (14 core tests, ~1 hour)

| Domain | Tests |
|---|---|
| Executive function | Penn Conditional Exclusion Test (PCET) — abstraction/mental flexibility; Penn Continuous Performance Test (PCPT) — attention; Letter N-Back (LNB) — working memory |
| Episodic memory | Penn Word Memory Test (PWMT) — verbal; Penn Face Memory Test (PFMT) — face; Visual Object Learning Test (VOLT) — spatial |
| Complex cognition | Penn Matrix Reasoning Test (PMAT) — nonverbal reasoning (Raven's-derived); Penn Line Orientation Test (PLOT) — spatial processing (Benton-derived); Abbreviated Penn Verbal Reasoning Test (PVRT) — language reasoning |
| Social cognition | Penn Emotion Recognition Test (ER-40) — emotion identification; Penn Emotion Differentiation Test (EMODIFF); Age Differentiation Test |
| Sensorimotor / psychomotor speed | Mouse Practice (MP); Computerized Finger Tapping Test (CTAP); Penn Digit Symbol Substitution Test (DSST) — processing speed |

### 4.2 Task mechanics (selected)

- **PCPT:** vertical and horizontal lines in **7-segment displays** appear at **1 per second**; press spacebar when lines form a complete number (first half) or complete letter (second half). Measures vigilance/visual attention independent of WM.
- **Letter N-Back (LNB):** sequential letters; respond to n-back matches. Working memory.
- **PCET:** abstraction/concept formation; **4 alternate forms**.
- **PMAT:** computerized Raven's Progressive Matrices analogue.
- **PLOT:** computerized Benton Judgment of Line Orientation.
- **CTAP:** number of taps in a **10-second** period (motor speed only).
- **ER-40:** emotion identification; **2 forms**.

### 4.3 Scoring — the accuracy/speed/efficiency system (core to CortexForge)

- Every test yields **accuracy** (number correct) and **speed** (median RT for correct responses), **except** psychomotor tests which yield speed only.
- **Raw accuracy and speed are converted to z-scores** using the sample mean and SD.
- **Speed z-scores are multiplied by −1** so that higher = better (faster).
- **Efficiency score = average of the standardized accuracy and speed z-scores** for a test.
- **ABF (a category-learning composite) accuracy = (number of categories learned) × (% correct responses).**

**Reference means/SDs (from Moore et al. 2015, healthy large sample) — useful for sanity-checking your own distributions:**

| Test | Accuracy mean (SD) | Median RT ms (SD) |
|---|---|---|
| AGD | 41.68 (7.16) | 2423 (700) |
| FME | 30.50 (4.31) | 1995 (480) |
| EMI | 33.25 (3.40) | 1950 (393) |
| VME | 36.82 (3.34) | 1510 (323) |
| LAN | 10.72 (3.04) | 6197 (2409) |
| EMD | 43.26 (7.04) | 3012 (778) |
| NVR | 11.96 (4.65) | 6907 (3823) |
| SME | 15.54 (2.44) | 1807 (426) |
| WM | 17.54 (2.61) | 548 (140) |
| ABF | 1.91 (0.73) | 2409 (929) |

### 4.4 Reliability and validity

- **Factor structure:** accuracy yields **three reliable factors** (executive/complex cognition, episodic memory, social cognition); speed yields **two factors** (fast-response tests vs. deliberation-requiring tests). `[VALIDATED]`
- **Test–retest (school-age children with HIV, Botswana):** summary scores ICC > 0.80; domain scores ICC 0.66–0.88; individual tests ICC 0.50–0.82, **lowest for memory tests**. `[MODERATE]`
- **Internal consistency (PNC sample):** Cronbach's α — Memory 0.91, Social Cognition 0.97, Executive 0.90, Complex Cognition 0.90. `[VALIDATED]`
- **Heritability:** established in twin/family studies (Calkins et al. 2010; Greenwood et al. 2007; Gur et al. 2007). `[VALIDATED]`
- **Clinical sensitivity:** validated in schizophrenia, 22q11.2/16p11.2 CNV carriers, and other conditions; duplications vs. deletions dissociate accuracy vs. speed. `[VALIDATED]`
- **Practice effects:** minimal, limited to speed; robust to repeated measures. `[VALIDATED]`

**CortexForge implication:** the **accuracy/speed/efficiency** decomposition is the single most reusable scoring architecture in this dossier. It is simple, transparent, and defensible. Adopt it as the default scoring model.

---

## 5. BrainHQ / Posit Science and the ACTIVE Trial

**Status.** **Proprietary** (patented exercises; Posit Science). Web + iOS + Android. `[MODERATE–VALIDATED]`

### 5.1 The ACTIVE trial (the strongest far-transfer evidence in the field)

**Design.** Advanced Cognitive Training for Independent and Vital Elderly (ACTIVE; NCT00298558). **N = 2,832** (2,802 enrolled per some reports), aged ≥65, no dementia, six sites. Four arms: memory training, reasoning training, **speed-of-processing training**, and no-contact control. Training: **10 sessions over 5–6 weeks (~10 hours)**; a subset received **booster training at 11 and 35 months** (total ~18–22 hours over 3 years). Funded by NIH ($33.7M); **no Posit Science involvement**. Followed 10 and 20 years. `[VALIDATED]`

**Key results:**
- All three training arms improved on trained tasks. Speed training showed the largest gains: **87% of speed-trained participants showed meaningful improvement** on the targeted ability (vs. 74% reasoning, 26% memory).
- **Transfer:** speed training generalized to the **Useful Field of View (UFOV)** task (a standardized measure of visual speed and attention) and to a priori **instrumental activities of daily living (IADL)** measures — equivalent to ~**24 months of preserved independent-living skills**.
- **10-year follow-up:** 71% of speed-trained retained improvements; comparable for reasoning; memory did not.
- **Real-world:** **48% reduction in at-fault automobile crashes** (state DMV records) in the speed-training arm. `[MODERATE — single trial, but objective outcome]`
- **20-year dementia outcome (2026, *Alzheimer's & Dementia: TRCI*):** Medicare claims linked for 2,763 of 2,802 participants (1999–2019). **Speed training + boosters: HR 0.74–0.75 (95% CI ~0.59–0.95)** for diagnosed ADRD vs. control — a **~25% risk reduction** (40% dementia incidence vs. 49% control). **Speed training without boosters: HR 1.01 (ns).** **No main effect of memory or reasoning training.** Each additional speed session associated with lower risk. `[MODERATE–VALIDATED]`

**The critique of the 20-year finding (must be cited for balance).** A 2025 reanalysis (PMC13284741) notes that **after Bonferroni–Dunn correction, all confidence intervals include HR = 1**; sign tests reject both "no effect" and "only one training type effective"; GMM estimation suggests a **common protective effect concentrated in the youngest age group (65–69, HR 0.77, 95% CI 0.64–0.93)**. `[MODERATE — this is a live methodological dispute]`

### 5.2 Double Decision (the ACTIVE speed-training exercise)

- *Construct:* visual speed of processing; **useful field of view (UFOV)**.
- *Mechanics:* A central vehicle flashes briefly; a peripheral **Route 66 sign** appears simultaneously. After a mask, the player (a) chooses which of two central vehicles was shown, and (b) indicates where the peripheral sign appeared.
- *Adaptive rule:* Flash duration adapts. **Starts ~500 ms**; correct → shorter; incorrect → longer. Range **32 ms to 2600 ms**. Difficulty also increases via: added peripheral distractors (0→47), sign moving farther into the periphery, central vehicles becoming more similar, more complex backgrounds. 15 progressive levels; 8→16 peripheral directions.
- *Metric:* **Score in milliseconds** = average presentation time of correct responses, in **log milliseconds** (RT is positively skewed). **Lower = better.** 25 presentations per session in one study.
- *Other BrainHQ exercises:* Divided Attention (color-shape-fill inhibitory control), Target Tracker (multiple-object tracking, visual WM), Mixed Signals (audiovisual Stroop), Sound Sweeps.

**CortexForge implication:** Double Decision is **fully reimplementable in a browser with geometric stimuli** (a shape at center, a shape in the periphery, a mask, two response channels, an adaptive exposure-time staircase). This is the single most evidence-backed mechanic in this dossier for *older-adult* outcomes. **However:** the evidence is for the *specific* speed-of-processing paradigm, not for "brain training" generally. Do not generalize.

---

## 6. Lumosity and NeuroRacer (Gazzaley lab)

### 6.1 Lumosity

**Status.** **Proprietary** (Lumos Labs). ~49 exercises. `[WEAK–MODERATE]`

**Key trial.** Hardy JL, Nelson RA, Thomason ME, Sternberg DA, Katovich K, Farzin F, Scanlon M (2015). "Enhancing cognitive abilities with comprehensive training: A large, online, randomized, active-controlled trial." *PLoS ONE* 10(9):e0134467. `[MODERATE — self-published by the company]`
- *Design:* 11,470 consented; **4,715 completed**. Treatment = off-the-shelf Lumosity (up to 49 game-like tasks); active control = **online crossword puzzles**. 15 min/day, 5 days/week, **10 weeks**.
- *Result:* treatment improved more on the primary outcome (aggregate neuropsychological index): **Cohen's d = 0.255 (95% CI 0.198–0.312)**. Gains on processing speed, short-term memory, working memory, problem solving, fluid reasoning.
- *The company's own stated limitations:* **~50% attrition in both arms**; risk of experimenter bias, attrition bias, and publication bias. `[This candor is worth noting — but the limitations are serious.]`
- *Independent replication:* a 2025 randomized active-controlled study of a commercial brain-training app (Peak) in 103 healthy older adults found **practice effects on trained tasks but no transfer** to working memory, processing speed, attention, or language vs. active control. `[VALIDATED — negative]`

### 6.2 NeuroRacer (Gazzaley lab, UCSF)

**Status.** **Not publicly released.** `[MODERATE]`

**Source.** Anguera JA, Boccanfuso J, Rintoul JL, Al-Hashimi O, Faraji F, Janowich J, Kong E, Larraburo Y, Rolle C, Johnston E, Gazzaley A (2013). "Video game training enhances cognitive control in older adults." *Nature* 501:97–101. DOI 10.1038/nature12486. `[VALIDATED — single landmark study]`

- *Mechanics:* 3D driving game. Steer a car along a winding road (left thumb/joystick) while responding to signs that pop up (shoot a specific shape/color with the right hand). Multitasking cost = performance drop when driving + sign task are combined vs. each alone.
- *Design:* 174 participants aged 20s–70s played with EEG at baseline. Then **46 (or 16 in the training arm, depending on report) healthy older adults aged 60–85** trained at home: **1 h/day, 3×/week, 4 weeks (12 h total)**. Active control and no-contact control. Follow-up at 6 months.
- *Results:* Older adults reduced multitasking costs, reaching levels **beyond untrained 20-year-olds**; gains persisted **6 months**. Transfer to **untrained** sustained attention and working memory (~100 ms improvement in WM RT). EEG: enhanced **midline frontal theta power** and frontal–posterior theta coherence, correlated with sustained-attention gains. **Critically: benefits were absent when drive and sign tasks were trained separately** — the multitasking challenge itself was necessary.
- *Caveats:* small training sample; not replicated at scale; not released as software.

**CortexForge implication:** the **multitasking-cost metric** (dual-task vs. single-task performance decrement) is a clean, reimplementable, and theoretically motivated outcome measure. The "adaptive difficulty + dual-task interference" design is the transferable lesson. But treat the far-transfer claim as `[MODERATE]`, not established.

---

## 7. Dual n-back and the working-memory-training transfer debate

### 7.1 The task (fully specified — trivially reimplementable)

**Source.** Jaeggi SM, Buschkuehl M, Jonides J, Perrig WJ (2008). "Improving fluid intelligence with training on working memory." *PNAS* 105(19):6829–6833. DOI 10.1073/pnas.0801268105. `[VALIDATED as a task]`

**Mechanics:**
- **Visual stream:** a square in **one of 8 spatial locations**.
- **Auditory stream:** **one of 8 letters** (spoken consonants).
- Presented **simultaneously**. Trial duration **3 s**: **500 ms stimulus presentation + 2500 ms interstimulus interval** (respond during the ISI).
- Respond when the current stimulus matches the one **n trials back** — separately for visual and auditory (both can be targets).
- **Adaptive rule (original Jaeggi):** with **12 targets per block**, if the participant makes **fewer than 3 mistakes per modality**, advance to n+1.
- **Session structure:** 20 blocks of 20 trials (one variant: 20 runs of 20+n trials). Training dose in the original: **8, 12, 17, or 19 days**.
- **Alternative adaptive rule (widely used):** advance if accuracy > 85%; drop a level if < 70%; else hold. Or: advance if ≥90% correct in both tasks; drop if ≤70%.

### 7.2 The original claim

Jaeggi et al. 2008 reported **transfer from dual n-back training to fluid intelligence (Gf)**, with a **dose-dependent** effect (gain varied with training days: F(3,30) = 9.25, p < 0.001, ηp² = 0.48). `[The original finding]`

### 7.3 The rebuttals

- **Melby-Lervåg M, Hulme C (2013).** "Is working memory training effective? A meta-analytic review." *Developmental Psychology* 49:270. DOI 10.1037/a0028228. 23 studies. Found reliable short-term WM improvements, **not maintained** weeks later; **no convincing generalization** to nonverbal/verbal ability, attention inhibition, word reading, or arithmetic. `[VALIDATED]`
- **Melby-Lervåg M, Redick TS, Hulme C (2016).** "Working memory training does not improve performance on measures of intelligence or other measures of 'far transfer': Evidence from a meta-analytic review." *Perspectives on Psychological Science* 11(4):512–534. DOI 10.1177/1745691616635612. **No convincing evidence of far transfer** (nonverbal ability, verbal ability, word decoding, reading comprehension, arithmetic) **when compared with a treated (active) control**. `[VALIDATED]`
- **Redick TS et al. (2013).** "No evidence of intelligence improvement after working memory training: a randomized, placebo-controlled study." *J Exp Psychol Gen*. Both training groups improved on trained tasks (persisting 6 months) but **no transfer** to non-trained measures vs. a passive control. `[VALIDATED]`
- **Multi-level meta-analysis of n-back training** (Soeveri? / *Psychon Bull Rev* 2017, DOI 10.3758/s13423-016-1217-0): medium transfer to **untrained n-back**; **very small** effects to other WM tasks, Gf, and cognitive control. Concludes prior meta-analyses **overestimated** transfer by including untrained variants of the training task in the "WM transfer" domain. `[VALIDATED]`
- **Simons DJ, Boot WR, Charness N, Gathercole SE, Chabris CF, Hambrick DZ, Stine-Morrow EAL (2016).** "Do 'brain-training' programs work?" *Psychological Science in the Public Interest* 17(3):103–186. DOI 10.1177/1529100616661983. **Extensive evidence for improvement on trained tasks; less for closely related tasks; little for distantly related tasks or everyday performance.** Notes most studies had major design/analysis shortcomings. `[VALIDATED — the field's consensus review]`

### 7.4 The honest counter-position (what a defender can legitimately say)

1. **Near transfer is real and robust.** Training improves the trained task and closely related tasks. This is not nothing — it is the basis for *assessment* and for *skill acquisition*.
2. **Far transfer is small, inconsistent, and largely disappears against active controls.** The most defensible reading: **small effects exist but are not reliably distinguishable from placebo/expectancy without rigorous controls.**
3. **Karbach J, Verhaeghen P (2014).** "Making working memory work: A meta-analysis of executive-control and working memory training in older adults." *Psychological Science* 25(11):2027–2037. DOI 10.1177/0956797614548725. 49 articles, 61 samples. Found significant near-transfer **and** significant but **smaller** far-transfer (net gain ~0.2 SD; net posttest ~0.25 SD) in **older adults**. Gains did **not** vary with total training time; no difference between adaptive and non-adaptive training. `[MODERATE — contested by Melby-Lervåg 2016 on active-control grounds]`
4. **Lampit A, Hallock H, Valenzuela M (2014).** "Computerized cognitive training in cognitively healthy older adults: a systematic review and meta-analysis of effect modifiers." *PLoS Medicine* 11(11):e1001756. 52 studies, 4,885 participants. Overall effect **g = 0.22 (95% CI 0.15–0.29)**. Domain effects: processing speed g = 0.31, visuospatial g = 0.30, nonverbal memory g = 0.24, WM g = 0.22, verbal memory g = 0.08. **No significant effect for executive function or attention.** **Home-based training was ineffective vs. group-based; >3 sessions/week was ineffective vs. ≤3.** `[VALIDATED — and directly relevant to a home-based product]`
5. **The ACTIVE speed-of-processing result is the genuine exception** (Section 5): a large, NIH-funded, industry-independent RCT with objective real-world outcomes and a 20-year dementia signal. But it is **one paradigm**, and even it is now under methodological challenge.
6. **The correct framing for CortexForge:** do **not** claim far transfer. Claim **validated measurement** (Section 3–4 psychometrics) + **calibrated honest feedback** + **near-transfer skill acquisition**. If you later run a trial, pre-register it, use an active control, and report against the Simons et al. (2016) best-practice checklist.

---

## 8. The "brain training does not transfer" critique — full statement

**The two strongest papers:**

1. **Owen AM, Hampshire A, Grahn JA, Stenton R, Dajani S, Burns AS, Howard RJ, Ballard CG (2010).** "Putting brain training to the test." *Nature* 465(7299):775–778. DOI 10.1038/nature09042. `[VALIDATED]`
   - **N = 11,430** (of 52,617 registered), aged 18–60, six-week online study (BBC Lab UK collaboration).
   - Three groups: experimental 1 (reasoning/planning/problem-solving), experimental 2 (broader: STM, attention, visuospatial, math), control (answered obscure questions using online resources).
   - Training: min 10 min/day, 3×/week, six weeks. Mean sessions: 28.4 / 23.9 / 18.7.
   - Benchmark tests (all groups, pre and post): grammatical reasoning, verbal short-term memory (VSTM), spatial working memory (SWM), paired-associates learning (PAL).
   - **Result: improvements on every trained task, but NO transfer to untrained tasks — "even when those tasks were cognitively closely related."** Effect sizes across all four benchmark tests were very small.
   - Owen's quote: "There were absolutely no transfer effects."

2. **Nguyen L, Murphy K, Andrews G (2022).** "A game a day keeps cognitive decline away? A systematic review and meta-analysis of commercially-available brain training programs in healthy and cognitively impaired older adults." *Neuropsychology Review* 32(3):601–630. DOI 10.1007/s11065-021-09515-2. `[VALIDATED]`
   - Small significant **near-transfer** effects for both healthy and MCI samples.
   - **Far transfer not observed for MCI**; small significant effect for **subjective but not objective** far-transfer measures in healthy samples.
   - Domain analysis: significant transfer to executive function, memory, processing speed in healthy older adults — **but after adjusting for publication bias, only processing speed remained significant.**
   - **No significant transfer to attention, objective everyday functioning, fluid intelligence, or visuospatial domains.**
   - Conclusion: "no convincing empirical evidence to suggest brain training programmes lead to tangible transfer effects in older adults."

**Supporting:** a 2025 RCT of a commercial brain-training app in 103 older adults found practice effects on trained tasks with **no transfer** to WM, processing speed, attention, or language vs. active control. `[VALIDATED — negative]`

### 8.1 The honest counter-position (steel-manned)

- **Near transfer is not in dispute.** Every meta-analysis agrees training improves trained and closely-related tasks.
- **Effect sizes are small but non-zero** in older adults (Lampit g = 0.22; Karbach net far-transfer ~0.2 SD). The dispute is whether these survive active-control and publication-bias correction — often they do not.
- **ACTIVE is a real counter-example** for one specific paradigm (speed of processing) with objective outcomes (crashes, IADL, 20-year dementia diagnosis). It is the strongest evidence in the field and should not be dismissed.
- **The defensible synthesis:** *Task-specific and near-transfer gains are real; broad far-transfer to fluid intelligence or everyday function is not established for the general consumer brain-training category; one specific speed-of-processing paradigm has the best (though now contested) far-transfer evidence.*
- **What this means for a hostile critic:** CortexForge should **not** be positioned as brain training. Position it as **measurement + calibrated feedback + near-transfer skill practice**, with any far-transfer claim explicitly deferred to a pre-registered trial.

---

## 9. Master table: task → construct → mechanics → metric → evidence quality

| Task | Construct | Mechanics (stimuli / timing / adaptive / trials) | Metric | Evidence quality |
|---|---|---|---|---|
| **CANTAB PAL** | Visual memory, new learning | Boxes in circle; open in random order; pattern→box; error repeats trial; 2/4/6/8/12 boxes; 20 trials | Total Errors Adjusted; First Attempt Memory Score; stages completed | **Strong** |
| **CANTAB SWM** | Visuospatial WM + strategy | Boxes; find hidden tokens; never revisit; 30 trials; up to 8 boxes | Between Errors; Strategy (lower=better) | **Strong** |
| **CANTAB RVP** | Sustained attention | Digits at 100/min; detect 3-digit target sequence; ~7–8 min | A′ (sensitivity); median RT; false-alarm probability | **Moderate** (low α=0.49 for A′) |
| **CANTAB RTI** | Psychomotor speed | Hold button; release on stimulus; select target; simple + 5-choice | Median 5-choice RT; median movement time | **Moderate–Strong** |
| **CANTAB IED** | Set-shifting | Rule-learning stages 1–9 | Stages completed; errors | **Moderate** |
| **CANTAB OTS/SOC** | Spatial planning | Tower-of-Hanoi analogue | Solved on first choice; mean choices; latencies | **Moderate** |
| **NIH Flanker** | Inhibitory control, attention | 5 arrows (or fish, 3–7); congruent/incongruent; 20 trials; ~3 min | Two-vector accuracy(0–5)+RT(0–5)=0–10 | **Strong** |
| **NIH DCCS** | Cognitive flexibility | Shape/color matching; cue 800 ms; 30 mixed trials | Two-vector accuracy+RT | **Strong** |
| **NIH LSWM** | Working memory | Recall/sequence 1-List then 2-List; 12 items | Sum correct, range 0–26 | **Moderate** |
| **NIH PSM** | Episodic memory | Sequence of pictured activities | Adjacent pairs correct | **Moderate** |
| **NIH PCPS** | Processing speed | Same/different picture pairs; 90 s | Number correct, range 0–130 | **Moderate** |
| **NIH TPVT/TORRT** | Crystallized ability | Vocabulary; reading | ICC 0.80 / 0.90 | **Strong** |
| **PennCNB PCPT** | Vigilance, attention | 7-segment lines at 1/s; number then letter halves | Accuracy + median RT → efficiency z | **Strong** |
| **PennCNB LNB** | Working memory | Sequential letters; n-back | Accuracy + median RT | **Strong** |
| **PennCNB PCET** | Abstraction, flexibility | Category learning; 4 forms | Accuracy + median RT | **Strong** |
| **PennCNB PMAT** | Nonverbal reasoning | Raven's analogue | Accuracy + median RT | **Strong** |
| **PennCNB PLOT** | Spatial processing | Benton line orientation analogue | Accuracy + median RT | **Strong** |
| **PennCNB ER-40** | Emotion identification | Face stimuli; 2 forms | Accuracy + median RT | **Strong** |
| **PennCNB CTAP** | Motor speed | Finger tapping, 10 s | Number of taps | **Moderate** |
| **COSMOS HoNk-Back** | WM updating | Truck-driver N-back; mirror tilt sets N | Accuracy; RT | **Weak** (pilot) |
| **COSMOS Frog Life** | Sustained attention, vigilance | Go/no-go + color-change signal detection; escalating difficulty | Munch Score; false alarms; escape RT; level | **Weak** (pilot) |
| **COSMOS Shortcuts** | Episodic + sequence memory | 3–10 pictures + symbol sequence; recognition + reproduction | Recognition accuracy; sequence accuracy | **Weak** (pilot) |
| **COSMOS Drag Race** | Simple/predictable RT, variability | Green light after random interval; gear-shift sequence | SRT; FRT; RT variability | **Weak** (pilot) |
| **COSMOS Joyrate** | Theory of mind | Rate jokes/statements; guess other's ratings | Estimation accuracy | **Weak** (pilot) |
| **BrainHQ Double Decision** | Visual processing speed, UFOV | Central vehicle + peripheral sign; mask; adaptive 32–2600 ms; distractors 0–47; 25 presentations | Score = mean log-ms of correct responses (lower=better) | **Moderate–Strong** (ACTIVE) |
| **BrainHQ Divided Attention** | Inhibitory control, divided attention | Color-shape-fill | Adaptive score | **Moderate** |
| **BrainHQ Target Tracker** | Visual WM | Multiple-object tracking | Adaptive score | **Moderate** |
| **Lumosity (aggregate)** | Multiple | Up to 49 game-like tasks; 15 min/day | Grand Index (aggregate) | **Weak–Moderate** |
| **NeuroRacer** | Cognitive control, multitasking | Drive + sign-shoot; adaptive; 12 h training | Multitasking cost; WM RT; sustained attention | **Moderate** |
| **Dual n-back** | WM updating | 8 locations + 8 letters; 500 ms + 2500 ms ISI; adaptive n | n-level reached; accuracy; d′ | **Strong as task; far-transfer contested** |
| **UFOV (ACTIVE proximal)** | Visual speed, attention | Central + peripheral identification with distractors | Threshold display duration | **Strong** |

---

## 10. Browser-reimplementable mechanics with NO external assets (text/geometric stimuli only)

The following can be built in a browser using only canvas/SVG/DOM primitives (shapes, colors, letters, digits) — no images, audio, or licensed assets. Ordered by evidence strength.

### 10.1 Fully reimplementable, strong evidence

1. **Flanker (NIH-style).** Five chevrons/arrows drawn as SVG paths; congruent/incongruent; 20 trials; two-vector scoring. **No assets.** `Strong`
2. **DCCS (NIH-style).** Two target shapes (circle/square) in two colors; cue word text; 30 mixed trials; two-vector scoring. **No assets.** `Strong`
3. **Pattern Comparison (NIH-style).** Pairs of simple geometric figures (e.g., 3-segment line drawings); same/different; 90 s. **No assets.** `Strong`
4. **List Sorting (NIH-style).** Text labels of animals/foods with an ordinal size dimension; 1-List/2-List; sum correct 0–26. **No assets** (text only). `Strong`
5. **PennCNB-style accuracy/speed/efficiency battery.** Any of: Letter N-Back (letters), PCPT (7-segment line displays — pure geometry), PCET (category learning with geometric exemplars), PMAT (generated Raven's-style matrices from geometric primitives), PLOT (line-orientation with drawn lines). All **no assets**. Adopt the **accuracy z + (−RT z) → efficiency** scoring. `Strong`
6. **Dual n-back.** 8-position square grid (geometry) + 8 letters (text); 500 ms + 2500 ms; adaptive n. **No assets.** `Strong as task`
7. **CANTAB PAL analogue.** Boxes in a circle (geometry); patterns generated procedurally (e.g., colored polygon combinations); error-repeats-trial; 2/4/6/8/12 boxes. **No assets.** `Strong`
8. **CANTAB SWM analogue.** Colored boxes; hidden token; self-ordered search; 4/6/8 boxes; 30 trials. **No assets.** `Strong`
9. **CANTAB RVP analogue.** Digits at 100/min (text); 3-digit target sequence; A′, median RT, false-alarm probability. **No assets.** `Strong`
10. **CANTAB RTI analogue.** Button-hold/release + target selection among 5 drawn circles. **No assets.** `Strong`
11. **Double Decision / UFOV analogue.** Central shape + peripheral shape + mask; adaptive exposure 32–2600 ms; distractors; log-ms score. **No assets** (shapes only). `Moderate–Strong`
12. **Multitasking-cost paradigm (NeuroRacer-style).** A simple continuous tracking task (moving dot controlled by pointer) + a discrete go/no-go shape task; measure dual-task decrement. **No assets.** `Moderate`

### 10.2 Reimplementable with text/geometry, weaker evidence

13. **COSMOS Frog Life analogue.** Go/no-go with geometric "prey"/"predator" shapes + a color-change signal-detection channel; escalating difficulty. `Weak`
14. **COSMOS Shortcuts analogue.** Procedurally generated symbol sequences (colored shapes) + text-labeled picture surrogates; recognition + sequence reproduction. `Weak`
15. **COSMOS Drag Race analogue.** Random-interval green-light RT + a timed multi-key sequence for predictable RT. `Weak`
16. **COSMOS Joyrate analogue.** Text jokes/statements + numeric rating + estimation of another's rating. `Weak`
17. **Stop Signal Task (SST).** Go stimuli (shapes) with occasional stop signal (color change); SSRT computed via the race model. `Moderate` (not detailed above; CANTAB SST exists)
18. **Digit Span (DGS).** Text digits forward/backward. `Moderate`
19. **Verbal Recognition Memory (VRM) analogue.** Text word lists; free recall + recognition. `Moderate`

### 10.3 NOT reimplementable without external assets (exclude or substitute)

- **CANTAB ERT / PennCNB ER-40** — require standardized face photographs (licensing + privacy). *Substitute:* procedurally generated schematic faces (evidence would not transfer).
- **CANTAB DMS / PRM / SRM** — use standardized pattern sets; can be **procedurally regenerated** as geometric patterns, but norms would not apply.
- **PennCNB PFMT** — face memory; requires face stimuli.
- **BrainHQ Sound Sweeps / Mixed Signals** — require audio assets.
- **Lumosity exercises** — proprietary and asset-heavy.

### 10.4 Implementation cautions

1. **RT measurement in browsers is noisy.** COSMOS itself flags monitor response time, OS scheduling, and key debouncing. Use `performance.now()`, requestAnimationFrame-based stimulus timing, and document the noise floor. Consider reporting RT in coarse bins rather than ms-level precision.
2. **Adaptive staircases must be specified exactly** (step size, reversal rules, termination) or scores are not comparable across users.
3. **Practice effects are real** (NIH Toolbox documents them). Either include a fixed practice block and score only live trials, or model practice as a covariate.
4. **Reliability is task-specific and often only moderate.** Measure and report ICC in your own population before making individual-level claims.
5. **Never claim far transfer.** Claim measurement, calibrated feedback, and near-transfer skill acquisition.

---

## 11. Citation ledger (with verification status)

**Verified against primary or authoritative secondary sources during this pass:**
- Aeberhard et al. 2019, *J Technol Behav Sci* 4(3):234–244, DOI 10.1007/s41347-018-0071-5 — COSMOS platform. ✔
- Anguera et al. 2013, *Nature* 501:97–101, DOI 10.1038/nature12486 — NeuroRacer. ✔
- Casaletto et al. 2015, *J Int Neuropsychol Soc* 21(5):378–391 — NIH Toolbox fully-corrected T-scores. ✔
- Gur et al. 2010; Moore et al. 2015, *Neuropsychology* 29(2):235–246, PMC4345134 — PennCNB psychometrics. ✔
- Hardy et al. 2015, *PLoS ONE* 10(9):e0134467 — Lumosity RCT. ✔
- Karbach & Verhaeghen 2014, *Psychol Sci* 25(11):2027–2037, DOI 10.1177/0956797614548725. ✔
- Lampit, Hallock & Valenzuela 2014, *PLoS Med* 11(11):e1001756. ✔
- Melby-Lervåg & Hulme 2013, *Dev Psychol* 49:270, DOI 10.1037/a0028228. ✔
- Melby-Lervåg, Redick & Hulme 2016, *Perspect Psychol Sci* 11(4):512–534, DOI 10.1177/1745691616635612. ✔
- Nguyen, Murphy & Andrews 2022, *Neuropsychol Rev* 32(3):601–630, DOI 10.1007/s11065-021-09515-2. ✔
- Owen et al. 2010, *Nature* 465(7299):775–778, DOI 10.1038/nature09042. ✔
- Simons et al. 2016, *Psychol Sci Public Interest* 17(3):103–186, DOI 10.1177/1529100616661983. ✔
- Jaeggi et al. 2008, *PNAS* 105(19):6829–6833, DOI 10.1073/pnas.0801268105. ✔
- Weintraub et al. 2013, *Neurology* 80(11 Suppl 3):S54–S64; *Monogr Soc Res Child Dev* 78(4). ✔
- ACTIVE 20-year dementia: *Alzheimer's & Dementia: TRCI* 2026 (PMC12884427), HR 0.74–0.75 with boosters. ✔
- ACTIVE reanalysis: PMC13284741 (2025). ✔
- CANTAB product pages and clinical-trials protocol SAP (NCT03276221). ✔

**Marked UNVERIFIED / needs confirmation before publication:**
- Exact PCPS timing (90 s vs. 85 s) — sources conflict; verify against the current NIH Toolbox scoring manual. `[UNVERIFIED]`
- Full COSMOS psychometric validation paper and normative data — none found. `[UNVERIFIED]`
- Exact ACTIVE training-arm N for NeuroRacer (16 vs. 46) — reports conflict. `[UNVERIFIED]`
- CANTAB PAL exact trial count (20 trials / 4 per box condition vs. 2→8 patterns) — protocols differ by version. `[UNVERIFIED]`
- Soeveri/author attribution for the 2017 multi-level n-back meta-analysis (*Psychon Bull Rev*, DOI 10.3758/s13423-016-1217-0) — DOI verified, author list not confirmed. `[UNVERIFIED]`

---

*End of dossier. Section 8 is the section to hand a hostile critic. Section 10 is the section to hand an engineer.*
