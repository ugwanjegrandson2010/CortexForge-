# Cognitive Decline and Brain Fog: Measurement, Prevention, and What a Software System Can Honestly Claim

**Research Dossier — CortexForge**
**Date:** 2026-10-17
**Scope:** Intervention scheduler and outcome-measurement layer
**Audience:** Technical implementers. Every claim below is tied to a citation. Unverifiable citations are marked **[UNVERIFIED]**.

---

## Table of Contents

1. [Brain Fog Operationalisation](#1-brain-fog-operationalisation)
2. [Objective vs Subjective Measurement](#2-objective-vs-subjective-measurement)
3. [Cognitive Training in Healthy Older Adults](#3-cognitive-training-in-healthy-older-adults)
4. [Multidomain Interventions](#4-multidomain-interventions)
5. [Long COVID Brain Fog](#5-long-covid-brain-fog)
6. [Physical Exercise and Cognition](#6-physical-exercise-and-cognition)
7. [Sleep, Circadian Timing, and Cognitive Performance](#7-sleep-circadian-timing-and-cognitive-performance)
8. [Dose-Response Evidence](#8-dose-response-evidence)
9. [Outcome Measures Table](#9-outcome-measures-the-product-should-track)
10. [Claims We May Make vs Claims We Must NOT Make](#10-claims-we-may-make-vs-claims-we-must-not-make)
11. [Concrete Intervention Protocol](#11-concrete-intervention-protocol)
12. [References](#12-references)

---

## 1. Brain Fog Operationalisation

Brain fog is a subjective syndrome characterised by mental fatigue, impaired cognitive acuity, and confusion. It is not a clinical diagnosis. No DSM-5 or ICD-11 code exists. The term is used across post-COVID syndrome, coeliac disease, systemic lupus erythematosus, Parkinson's disease, chronic fatigue syndrome, hypoparathyroidism, and postural tachycardia syndrome. The following scales operationalise it with varying degrees of validation.

### 1.1 Brain Fog Scale (BFS) — Debowska et al. (2023)

| Property | Value |
|---|---|
| **Items** | 23 |
| **Factors** | 3: Mental Fatigue (6 items), Impaired Cognitive Acuity (9 items), Confusion (8 items) |
| **Response scale** | 5-point Likert (Never → Always) |
| **Scoring** | Sum of subscale items; higher = worse |
| **Reliability (original)** | Cronbach's α: Factor 1 = 0.79, Factor 2 = 0.80, Factor 3 = 0.78 |
| **Reliability (Turkish validation)** | α = 0.966 for full scale; three-factor structure confirmed |
| **Sample** | 1,452 university students (original); 573 (Turkish validation) |
| **Citation** | Debowska, A., Boduszek, D., Ochman, M., Hrapkowicz, T., Gawęda, M., Pondel, A., et al. (2023). *Personality and Individual Differences.* https://doi.org/10.1016/j.paid.2023.112427 |

**Notes for implementers:** The BFS is the first validated transdiagnostic brain fog scale. Subscale alphas in the original validation (0.78–0.80) are acceptable but not excellent; the Turkish validation showed α = 0.966, suggesting possible cultural response-style differences. The scale was developed in a university sample — generalisation to older adults is assumed but not directly tested. A US general-population validation has been signalled (doi:10.1016/j.paid.2025.113499) but full psychometric data were not available at time of writing.

### 1.2 Fatigue and Altered Cognition Scale (FACs)

| Property | Value |
|---|---|
| **Items** | 20 (10 altered cognition / brain fog, 10 central fatigue) |
| **Factors** | 2: Altered Cognition, Central Fatigue |
| **Response scale** | Electronic visual analogue scale (eVAS), 0–100 |
| **Scoring** | Mean of items per subscale |
| **Reliability** | Cronbach's α reported as "good" (exact values in original paper; two-factor structure replicated in SARS-CoV-2 survivors) |
| **Sample** | 519 participants (development); COVID-19 survivors (replication) |
| **Citation** | [UNVERIFIED — exact α values not extracted from paywalled source] Development: PLOS ONE, 2024. https://doi.org/10.1371/journal.pone.0295593. Replication: PMC11050894 |

**Notes for implementers:** The FACs uniquely separates brain fog from fatigue, which is critical because the two are highly correlated but dissociable. The eVAS format is well-suited to in-app administration. The two-factor structure replicated in COVID-19 survivors, supporting use in long-COVID populations.

### 1.3 Brain Fog Assessment and Severity Scale (BFASS) — Coeliac Disease

| Property | Value |
|---|---|
| **Items** | 12 |
| **Factors** | 2: Cognitive Impairment, Somatic and Affective Experience |
| **Response scale** | [UNVERIFIED — exact scale not extracted] |
| **Scoring** | [UNVERIFIED] |
| **Reliability** | "Strong psychometric properties" (exact α not extracted) |
| **Sample** | Coeliac disease patients |
| **Citation** | Knowles et al. (2024). *Alimentary Pharmacology & Therapeutics.* https://doi.org/10.1111/apt.17942 |

**Notes for implementers:** Disease-specific. The two-factor structure (cognitive vs somatic/affective) is conceptually useful — it confirms that brain fog is not purely cognitive. Not validated for general-population or digital delivery.

### 1.4 Lupus Brain Fog Severity Scale (LBFSS)

| Property | Value |
|---|---|
| **Items** | [UNVERIFIED — exact item count not extracted; 13 domains retained from 21 generated] |
| **Factors** | [UNVERIFIED] |
| **Response scale** | [UNVERIFIED] |
| **Scoring** | [UNVERIFIED] |
| **Reliability** | [UNVERIFIED] |
| **Sample** | 147 SLE participants across 39 countries (qualitative phase) |
| **Citation** | Lupus Science & Medicine, 2026. https://doi.org/10.1136/lupus-2026-002148 |

**Notes for implementers:** The LBFSS is the first lupus-specific cognitive PROM. It is very recent (2026) and full psychometric data were not available at time of writing. Disease-specific; not for general use.

### 1.5 Perceived Deficits Questionnaire-20 (PDQ-20) — Parkinson's Disease

| Property | Value |
|---|---|
| **Items** | 20 |
| **Domains** | Attention, retrospective memory, prospective memory, planning |
| **Response scale** | 5-point Likert |
| **Scoring** | Sum; higher = greater perceived deficit |
| **Reliability** | [UNVERIFIED — exact values not extracted] |
| **Citation** | Sullivan et al. (1990); cited in systematic review: https://doi.org/10.1155/2024/9614163 |

**Notes for implementers:** PDQ-20 measures *perceived* cognitive deficits in Parkinson's disease. It is not a brain fog scale per se, but it captures the subjective cognitive complaints that overlap with brain fog. Disease-specific.

### 1.6 Subjective Scale to Investigate Cognition in Schizophrenia (SSTICS)

| Property | Value |
|---|---|
| **Items** | 21 (full); 14 (short form) |
| **Factors** | [UNVERIFIED — single-factor or multifactor not confirmed from extraction] |
| **Response scale** | Likert-type |
| **Scoring** | [UNVERIFIED] |
| **Reliability** | Cronbach's α = 0.90 (full), 0.88 (short); McDonald's ω = 0.900 (full), 0.881 (short) |
| **Citation** | Stip et al. (2003); German validation: https://doi.org/10.1080/13803395.2026.2627998 |

**Notes for implementers:** SSTICS was developed for schizophrenia, not brain fog. It is included here because it is a well-validated subjective cognition scale with a short form. Not a brain fog measure.

### Summary Table: Brain Fog Scales

| Scale | Items | Factors | Reliability (α) | Population | Validated for Digital? |
|---|---|---|---|---|---|
| BFS | 23 | 3 (MF, ICA, Conf) | 0.78–0.80 (orig); 0.966 (Turkish) | University students | Not tested |
| FACs | 20 | 2 (AC, CF) | "Good" (exact NR) | TBI / COVID survivors | Yes (eVAS) |
| BFASS | 12 | 2 (CI, SAE) | "Strong" (exact NR) | Coeliac disease | Not tested |
| LBFSS | [UNVERIFIED] | [UNVERIFIED] | [UNVERIFIED] | SLE | Not tested |
| PDQ-20 | 20 | 4 domains | [UNVERIFIED] | Parkinson's disease | Not tested |
| SSTICS | 21/14 | [UNVERIFIED] | 0.88–0.90 | Schizophrenia | Not tested |

**Key gap:** No brain fog scale has been validated for ecological momentary assessment (EMA) or repeated in-app administration. The FACs, with its eVAS format, is the closest.

---

## 2. Objective vs Subjective Measurement

### 2.1 The Weak Correlation Between Self-Reported Brain Fog and Objective Cognitive Performance

This is the single most important measurement finding for any product that claims to track both subjective and objective cognition.

**Finding:** Self-reported brain fog correlates weakly with performance on neuropsychological tests. The correlation is statistically significant but small in magnitude.

**Key evidence:**

- **Jennings et al. (2023)** — In 25,796 participants, self-defined brain fog was associated with cognitive scores only 0.1 SD worse than non-brain-fog controls (p < 0.0001). The largest deficit was in cognitive flexibility and inhibition of cognitive interference (0.13 SD). This is a *very small* effect — the overlap between brain-fog and non-brain-fog groups is enormous. (PMC11191638)

- **Guo et al. (2022)** — Long-COVID sufferers report "good" and "bad" days without these subjective states correlating with objective measures of cognition. Brain fog is unlikely to be adequately captured by objective measures alone. (Cited in PMC11191638)

- **Epilepsy study** — Self-reported cognitive complaints were "not strongly associated with objective tests of different cognitive performance measures." (ScienceDirect, S0920121109000345)

- **Subjective Cognitive Concerns (SCC) literature** — The relationship between subjective cognitive concerns and objective neurocognitive performance is "inconsistent, at best" and varies by population (primary medical vs primary psychiatric). (Cambridge, Psychological Medicine)

### 2.2 What This Means for a Product That Measures Both

1. **Subjective and objective measures are not interchangeable.** A user can report severe brain fog while performing within normal limits on cognitive tests, and vice versa. This is not a measurement failure — it reflects the genuine dissociation between subjective experience and objective performance.

2. **Both must be tracked.** Subjective brain fog captures the lived experience (mental fatigue, confusion, perceived acuity) that objective tests miss. Objective tests capture performance deficits that users may not notice or may attribute to other causes.

3. **Do not use subjective reports as a proxy for objective performance, or vice versa.** Report them separately. If they diverge, that divergence is itself clinically meaningful.

4. **The 0.1 SD objective deficit in brain fog** (Jennings et al.) means that a product claiming to "detect cognitive impairment" from brain fog scores alone will have very low sensitivity. Brain fog is a subjective syndrome, not a cognitive deficit per se.

---

## 3. Cognitive Training in Healthy Older Adults

### 3.1 Lampit et al. (2014) — Meta-Analysis of Effect Modifiers

| Property | Value |
|---|---|
| **Design** | Systematic review and meta-analysis of RCTs |
| **Studies** | 52 (51 in some counts; 4,885 participants) |
| **Population** | Cognitively healthy older adults (mean age ≥ 60) |
| **Intervention** | Computerised cognitive training (CCT), ≥ 4 hours |
| **Overall effect** | Hedges' g = 0.22 (small but statistically significant) on global cognition |
| **Key moderator** | Adaptive training > non-adaptive training |
| **Non-adaptive effect** | g ≈ 0.15 (not significant) |
| **Adaptive effect** | g ≈ 0.32 (significant) |
| **Citation** | Lampit, A., Hallock, H., & Valenzuela, M. (2014). *PLOS Medicine.* https://doi.org/10.1371/journal.pmed.1001756 |

**Critical caveat:** The overall effect of g = 0.22 is small. The difference between adaptive (g ≈ 0.32) and non-adaptive (g ≈ 0.15) training is the most actionable finding: **adaptive difficulty is not optional — it is the active ingredient.**

### 3.2 Kelly et al. (2014) — Cognitive Training and Mental Stimulation

| Property | Value |
|---|---|
| **Design** | Systematic review and meta-analysis of RCTs |
| **Studies** | 23 RCTs (5,037 participants) |
| **Population** | Healthy older adults (> 50) |
| **Overall effect** | Small to moderate effects on cognitive function; moderate for working memory (I² = 84%) and large for processing speed (I² = 75%) |
| **Comparison** | Cognitive training vs active control: small effects on global cognition |
| **Citation** | Kelly, M.E., Loughrey, D., Lawlor, B.A., et al. (2014). *Ageing Research Reviews.* https://doi.org/10.1016/j.arr.2014.02.004 |

**Critical caveat:** High heterogeneity (I² = 75–84%) means the pooled effect size should be interpreted with caution. The effects are real but variable across individuals and study designs.

### 3.3 Nguyen et al. (2022) — Publication-Bias-Corrected Meta-Analysis

| Property | Value |
|---|---|
| **Design** | Meta-analysis with publication bias assessment |
| **Key finding** | After correcting for publication bias and low statistical power in primary RCTs, the evidence for cognitive training benefits is weaker than uncorrected meta-analyses suggest |
| **Issues identified** | Low statistical power, selective inclusion of studies, publication bias, large variation in analytic decisions |
| **Citation** | Nguyen et al. (2022). [UNVERIFIED — exact corrected effect size not extracted from available sources] |

**Critical caveat:** This is the most important corrective in the field. The "headline" effect sizes from Lampit and Kelly are likely inflated. The true effect, after bias correction, is probably smaller. A product must not cite the uncorrected numbers as guaranteed outcomes.

### 3.4 ACTIVE Trial — 10-Year Follow-Up

| Property | Value |
|---|---|
| **Design** | Multisite RCT, N = 2,832, community-dwelling adults ≥ 65 |
| **Interventions** | Memory, reasoning, or speed-of-processing training (10 sessions × 60–75 min over 5–6 weeks) |
| **10-year IADL effect** | Memory: ES = 0.48 (99% CI 0.12–0.84); Reasoning: ES = 0.38 (0.02–0.74); Speed: ES = 0.36 (0.01–0.72) |
| **Cognitive durability** | Effects on trained abilities durable to 10 years for reasoning and speed; memory effects attenuated without boosters |
| **Booster effect** | Booster sessions (4 × 75 min at 11 and 35 months) preserved certain improvements |
| **Citation** | Rebok et al. (2014). *Journal of the American Geriatrics Society.* PMC4055506 |

**Critical caveat:** The ACTIVE trial is the strongest evidence for durability of cognitive training effects. However, the effects are **domain-specific** — reasoning training improves reasoning, not memory or speed. The IADL effects, while statistically significant, are small (ES 0.36–0.48). The trial was conducted in a well-functioning, predominantly white, educated sample — generalisation to more diverse populations is uncertain.

### 3.5 Meta-Review of 39 Reviews (Gavelin et al., 2020 / Bahar-Fuchs et al., 2020)

| Property | Value |
|---|---|
| **Design** | Systematic overview of systematic reviews with meta-analysis |
| **Reviews included** | 39 (19 on cognitive training in healthy older adults) |
| **Mean effect (healthy older adults)** | Hedges' g = 0.32 (range 0.13–0.64) |
| **Mean effect (MCI)** | g = 0.40 (range 0.32–0.60) |
| **Mean effect (dementia)** | g = 0.38 (range 0.09–1.16) |
| **Quality correlation** | Positive correlation between review quality and pooled effect size — higher-quality reviews found *larger* effects (counterintuitive; may reflect better study selection) |
| **Citation** | Gavelin et al. (2020) / Bahar-Fuchs et al. (2020). PMC7305099 |

**Critical caveat:** The range of effects across reviews (0.13–0.64) is enormous. The "true" effect depends heavily on which studies are included, how they are coded, and what comparators are used. The field has been plagued by researcher degrees of freedom (see Transparency meta-review, PMC12328470).

### 3.6 Sala & Gobet (2023) — "A Field in Search of a Phenomenon"

| Property | Value |
|---|---|
| **Key claim** | The overall effect of far transfer is null; there is little to no true variability between types of cognitive training |
| **Argument** | Apparent differences between training types are due to sampling error and study artifacts, not genuine moderation |
| **Citation** | Sala, G., & Gobet, F. (2023). *Perspectives on Psychological Science.* PMC9903001 |

**This is the most pessimistic assessment in the field.** It argues that the small effects that do exist are limited to near transfer (improvement on tasks similar to the training task) and that far transfer (improvement on everyday cognition) is essentially zero. A product must engage with this critique.

### 3.7 Honest Summary of Cognitive Training Evidence

| Claim | Evidence Status |
|---|---|
| Cognitive training improves performance on the trained task | **Strong** (near transfer, well-replicated) |
| Cognitive training improves untrained tasks in the same domain | **Moderate** (near transfer, g ≈ 0.2–0.3) |
| Cognitive training improves everyday functioning | **Weak** (far transfer, ES 0.36–0.48 in ACTIVE at 10 years, but domain-specific) |
| Cognitive training prevents dementia | **No direct evidence** (no RCT has shown this) |
| Adaptive training is more effective than non-adaptive | **Moderate** (Lampit et al. moderator analysis) |
| Effects are durable for years without boosters | **Mixed** (reasoning/speed durable; memory attenuates) |
| Commercial brain training products produce far transfer | **No convincing evidence** (Simons et al., 2016; Sala & Gobet, 2023) |

---

## 4. Multidomain Interventions

### 4.1 FINGER Trial (Ngandu et al., 2015)

| Property | Value |
|---|---|
| **Design** | RCT, N = 1,259, aged 60–77, at risk (CAIDE ≥ 6) |
| **Intervention** | 2-year multidomain: diet, exercise, cognitive training, vascular risk monitoring |
| **Control** | General health advice |
| **Primary outcome** | NTB (Neuropsychological Test Battery) total Z score change |
| **Effect** | Estimated mean change at 2 years: 0.20 (SE 0.02, SD 0.51) in intervention vs control |
| **Citation** | Ngandu, T., et al. (2015). *The Lancet.* https://doi.org/10.1016/S0140-6736(15)60461-5 |

**What "multidomain" means concretely in FINGER:**
1. **Diet:** Nutritional counselling based on Finnish nutrition recommendations; individual and group sessions with dietitians
2. **Exercise:** Progressive muscle strength training and aerobic exercise; guided by physiotherapists
3. **Cognitive training:** Group and individual computer-based training (processing speed, executive function, memory)
4. **Vascular risk monitoring:** Regular monitoring and management of blood pressure, lipids, glucose, body weight
5. **Social engagement:** Group activities inherently provided social contact

**Critical caveat:** The FINGER effect (0.20 SD on NTB over 2 years) is statistically significant but small. The trial cannot determine which component(s) drove the effect — it is a package deal. The control group received "general health advice," not a placebo, so the comparison is against minimal intervention, not against no intervention.

### 4.2 US POINTER (Baker et al., 2025)

| Property | Value |
|---|---|
| **Design** | Phase 3 RCT, N = 2,111, aged 60–79, at risk |
| **Interventions** | Structured (38 facilitated meetings over 2 years) vs self-guided multidomain lifestyle |
| **Components** | Physical activity (aerobic 4×/week 30–35 min; resistance training), MIND diet, cognitive/social challenge, cardiovascular monitoring |
| **Primary outcome** | Global cognitive composite Z score |
| **Structured effect** | Mean rate of increase: 0.243 SD/year (95% CI 0.227–0.258) |
| **Self-guided effect** | Mean rate of increase: 0.213 SD/year (95% CI 0.198–0.229) |
| **Between-group difference** | 0.03 SD/year (small but statistically significant) |
| **Citation** | Baker, L.D., et al. (2025). *JAMA.* https://doi.org/10.1001/jama.2025.12923 |

**Critical caveat:** Both groups improved — the self-guided intervention also produced cognitive gains. The between-group difference (0.03 SD/year) is very small. This suggests that **any** structured lifestyle engagement may be beneficial, and the added value of intensive professional facilitation is modest. The absolute effect sizes are small and their clinical meaningfulness is debated.

### 4.3 What "Multidomain" Means — Operational Definition

Based on FINGER and US POINTER, a multidomain intervention must include at minimum:

| Domain | Concrete Components | Minimum Dose (FINGER/POINTER) |
|---|---|---|
| **Physical exercise** | Aerobic + resistance training | 150 min/week moderate aerobic + 2×/week resistance |
| **Diet** | Mediterranean or MIND diet pattern | Dietary counselling sessions; adherence monitoring |
| **Cognitive training** | Computerised or group-based | ≥ 10 sessions over 6 weeks (ACTIVE protocol) |
| **Vascular risk monitoring** | BP, lipids, glucose, BMI | Every 6 months |
| **Social engagement** | Group activities, peer support | Inherent in group-based delivery |

**Key insight:** The multidomain approach is the strongest evidence-based intervention for cognitive decline prevention, but the effect sizes are small and the mechanisms are unclear. It is not possible to attribute effects to individual components.

---

## 5. Long COVID Brain Fog

### 5.1 Prevalence

| Property | Value |
|---|---|
| **Pooled prevalence of brain fog** | 30% (95% CI 28–32) |
| **Pooled prevalence of cognitive impairment** | 25% (95% CI 23–27) |
| **Gender difference** | Female 34% vs male 23% (brain fog); Female 29% vs male 21% (cognitive impairment) |
| **Studies included** | 47 studies, > 25,000 patients |
| **Citation** | Systematic review, 2026. *Medicine.* https://doi.org/10.1097/MD.0000000000049022 |

### 5.2 Narrative Review of Interventions

| Property | Value |
|---|---|
| **Studies reviewed** | 17 intervention studies |
| **Intervention types** | Cognitive training, exercise rehabilitation, rTMS, tDCS, pharmacological |
| **Key finding** | Diverse approaches with range of outcomes; no single intervention has strong evidence |
| **Citation** | PMC11176231 |

### 5.3 Which Interventions Have Any Evidence

| Intervention | Evidence Status | Notes |
|---|---|---|
| **Cognitive training** | **Weak/Moderate** | Small studies; some improvement in attention and processing speed; no large RCTs |
| **Exercise rehabilitation** | **Weak** | Pulmonary/cardiac rehab models; indirect evidence from general exercise-cognition literature |
| **rTMS (repetitive transcranial magnetic stimulation)** | **Very weak** | 6 studies in narrative review; no RCTs specific to long-COVID brain fog |
| **tDCS (transcranial direct current stimulation)** | **Very weak** | Included in narrative review; no RCTs specific to long-COVID brain fog |
| **Pharmacological** | **Insufficient** | No established pharmacotherapy for long-COVID brain fog |

**Critical caveat:** The long-COVID brain fog intervention literature is in its infancy. No intervention has high-quality RCT evidence. A product targeting long-COVID brain fog must be honest that the evidence is preliminary.

---

## 6. Physical Exercise and Cognition

### 6.1 Network Meta-Analysis of 58 RCTs (2025)

| Property | Value |
|---|---|
| **Design** | Network meta-analysis |
| **Studies** | 58 RCTs, 4,349 healthy older adults |
| **Intervention types** | Resistance, aerobic, HIIT, physical-mental (mind-body), multi-modal |
| **Resistance training effect** | SMD = 0.55 (greatest improvement in global cognition) |
| **Aerobic training effect** | SMD = 0.58 (95% CI 0.33–0.83) |
| **Resistance training (alt. analysis)** | SMD = 0.62 (95% CI 0.35–0.88) |
| **Optimal dose** | Twice-weekly, 45 min per session, over 12 weeks |
| **Citation** | *Frontiers in Aging Neuroscience*, 2025. https://doi.org/10.3389/fnagi.2025.1510773 |

**Notes:** Resistance training demonstrated the greatest improvement in global cognitive function in this network meta-analysis. The effect sizes (SMD 0.55–0.62) are moderate and notably larger than those for cognitive training (g = 0.22–0.32). This is one of the strongest arguments for including physical exercise in a cognitive health product.

### 6.2 Exercise and Brain Fog

The direct evidence for exercise reducing brain fog is limited. The mechanism is inferred from:
- Exercise improves cerebral blood flow, BDNF expression, and reduces inflammation
- Exercise improves sleep quality (which may reduce brain fog)
- Exercise improves cardiovascular risk factors (which are associated with cognitive decline)

**No RCT has directly tested whether exercise reduces brain fog as a primary outcome.** This is a gap the product could help fill.

### 6.3 Dose-Response for Exercise

| Parameter | Optimal Dose | Source |
|---|---|---|
| **Frequency** | 2×/week (resistance); 3–4×/week (aerobic) | Network meta-analysis 2025 |
| **Session duration** | 45 min | Network meta-analysis 2025 |
| **Program length** | ≥ 12 weeks | Network meta-analysis 2025 |
| **Intensity** | Moderate-to-vigorous | US POINTER protocol |

---

## 7. Sleep, Circadian Timing, and Cognitive Performance

### 7.1 Spacing Effects

| Property | Value |
|---|---|
| **Phenomenon** | Distributed practice produces better long-term retention than massed practice |
| **Effect size** | d = 0.71 (medium-to-large) — Cepeda et al. (2006) meta-analysis |
| **Replication** | 200+ studies across domains |
| **Citation** | Cepeda, N.J., et al. (2006). *Psychological Bulletin.* [UNVERIFIED — exact citation details] |

**Implication for scheduler:** Spacing learning sessions over days/weeks is one of the most robust findings in cognitive psychology. A scheduler that spaces review sessions will outperform one that masses them. This is not controversial.

### 7.2 Glymphatic System

| Property | Value |
|---|---|
| **Discovery** | Xie et al. (2013) — Science |
| **Mechanism** | CSF influx through perivascular spaces clears interstitial waste (β-amyloid, tau) during sleep |
| **Sleep vs wake** | Interstitial space volume increases 60% during sleep; CSF tracer influx reduced ~95% in awake vs sleeping mice |
| **AQP4 dependence** | Deletion of aquaporin-4 channels reduces β-amyloid clearance by 65% |
| **Citation** | Xie, L., et al. (2013). *Science.* PMC3880190 |

**Implication for scheduler:** Sleep is when the brain clears metabolic waste. A scheduler should not schedule cognitively demanding sessions when the user is sleep-deprived. The minimum 7 hours of sleep for cognitive function is supported by the neuroprotective sleep literature (PMC4651462).

### 7.3 What a Scheduler Can Legitimately Do

| Action | Evidence Basis | Strength |
|---|---|---|
| Space review sessions over days/weeks | Spacing effect (d = 0.71) | **Strong** |
| Avoid scheduling demanding sessions when sleep-deprived | Sleep deprivation impairs cognition; glymphatic clearance | **Moderate** |
| Recommend 7+ hours sleep | Neuroprotective sleep literature | **Moderate** |
| Schedule sessions at consistent circadian times | Circadian rhythm effects on cognitive performance | **Weak-Moderate** |
| Avoid late-night cognitively demanding sessions | Sleep onset proximity impairs memory consolidation | **Moderate** |

---

## 8. Dose-Response Evidence

### 8.1 Cognitive Training Dose

| Parameter | Finding | Source |
|---|---|---|
| **Minimum sessions** | ≥ 10 adaptive sessions needed for measurable effects | Lampit et al. (2014); ACTIVE trial (10 sessions) |
| **Frequency** | < 3 times/week optimal; > 3 times/week may reduce efficacy | Lampit et al. (2014) meta-regression |
| **Session duration** | 20–75 min depending on task | ACTIVE (60–75 min); De Lillo et al. (2021) (20 min) |
| **Program length** | 5–6 weeks (ACTIVE); 21 days (De Lillo et al.) | Multiple |
| **Optimal dose (real-world data)** | < 60: 25–30 min/day, 6 days/week; ≥ 60: 50–55 min/day, 6 days/week | npj Digital Medicine (2024), N = 8,709 |
| **Adaptive vs non-adaptive** | Adaptive training is the active ingredient | Lampit et al. (2014) |

**Key finding:** The "at least 10 adaptive sessions, less than three times weekly" finding comes from Lampit et al.'s moderator analysis. Training more than 3 times per week was associated with *smaller* effects, possibly due to fatigue or reduced motivation.

### 8.2 Near Transfer vs Far Transfer

| Type | Definition | Effect Size | Evidence |
|---|---|---|---|
| **Near transfer** | Improvement on tasks similar to the training task | g ≈ 0.2–0.3 | Well-replicated |
| **Far transfer** | Improvement on loosely related tasks or everyday cognition | ≈ 0 (Sala & Gobet, 2023) to 0.36–0.48 (ACTIVE IADL) | Contested |

**The far transfer debate is the central controversy in the field.** Sala & Gobet (2023) argue it is essentially null. The ACTIVE trial shows small but significant IADL effects at 10 years. The truth is probably: far transfer exists but is small, domain-specific, and requires booster sessions to maintain.

### 8.3 Exercise Dose

| Parameter | Optimal Dose | Source |
|---|---|---|
| **Resistance training** | 2×/week, 45 min, ≥ 12 weeks | Network meta-analysis 2025 |
| **Aerobic training** | 3–4×/week, 30–35 min, ≥ 12 weeks | US POINTER protocol |
| **Combined** | Aerobic + resistance superior to either alone | Network meta-analysis 2025 |

---

## 9. Outcome Measures the Product Should Track

| Measure | What It Captures | Evidence Status | Instrument | Frequency |
|---|---|---|---|---|
| **Subjective brain fog** | Mental fatigue, impaired acuity, confusion | Validated (BFS, FACs) | BFS (23 items) or FACs (20 items) | Weekly |
| **Objective cognitive performance** | Processing speed, working memory, executive function | Well-validated | Custom battery (e.g., n-back, Stroop, TMT) | Baseline, 4 weeks, 12 weeks |
| **Processing speed** | Speed of information processing | Strong (ACTIVE, Lampit) | UFOV or custom | Baseline, 4 weeks, 12 weeks |
| **Working memory** | Ability to hold and manipulate information | Moderate | n-back, digit span | Baseline, 4 weeks, 12 weeks |
| **Executive function** | Inhibition, switching, planning | Moderate | Stroop, TMT-B, task switching | Baseline, 4 weeks, 12 weeks |
| **Physical activity** | Exercise dose and adherence | Strong (network meta-analysis) | Accelerometer + self-report | Continuous |
| **Sleep duration and quality** | Sleep as cognitive modulator | Moderate | PSQI or wearable | Weekly |
| **Vascular risk factors** | BP, lipids, glucose, BMI | Strong (FINGER, POINTER) | Clinical measures | Every 6 months |
| **Social engagement** | Social contact frequency | Moderate (multidomain trials) | Self-report | Weekly |
| **Mood (depression, anxiety)** | Confound for subjective brain fog | Strong (FACs validation) | PHQ-9, GAD-7 | Weekly |
| **Fatigue** | Central fatigue (distinct from brain fog) | Moderate (FACs) | FACs fatigue subscale | Weekly |

**Critical note on subjective-objective divergence:** Track subjective brain fog and objective cognitive performance as separate, non-interchangeable measures. Do not composite them. Report divergence explicitly.

---

## 10. Claims We May Make vs Claims We Must NOT Make

### 10.1 Claims We MAY Make (with appropriate caveats)

| Claim | Evidence Basis | Required Caveat |
|---|---|---|
| "Adaptive cognitive training can improve performance on the trained cognitive skills" | Lampit et al. (2014); ACTIVE trial | "Effects are typically small (g ≈ 0.2–0.3)" |
| "Regular physical exercise is associated with better cognitive function in older adults" | Network meta-analysis 2025; FINGER; POINTER | "Association does not prove causation; effect sizes are moderate" |
| "Spacing learning sessions over time improves long-term retention" | Spacing effect meta-analysis (d = 0.71) | None — this is robust |
| "A multidomain lifestyle programme (diet + exercise + cognitive training + vascular monitoring + social engagement) can slow cognitive decline in at-risk older adults" | FINGER; US POINTER | "Effect sizes are small (0.02–0.20 SD); the approach is evidence-based but not a guarantee" |
| "Our programme is grounded in the FINGER and US POINTER multidomain protocols" | FINGER; US POINTER | "We have adapted these protocols; our specific implementation has not been independently validated" |
| "Cognitive training effects can be maintained for years with booster sessions" | ACTIVE 10-year follow-up | "Effects are domain-specific; memory effects attenuate without boosters" |
| "Sleep is important for cognitive function and brain waste clearance" | Xie et al. (2013); sleep literature | "Most evidence is observational or animal-based; human intervention evidence is limited" |
| "Resistance training twice weekly for 12 weeks is associated with improved cognitive function in older adults" | Network meta-analysis 2025 | "This is the optimal dose from a network meta-analysis; individual results vary" |

### 10.2 Claims We Must NOT Make

| Prohibited Claim | Why |
|---|---|
| "Our product prevents dementia or Alzheimer's disease" | No RCT has shown that any cognitive training product prevents dementia |
| "Our product cures brain fog" | No intervention has been shown to cure brain fog; evidence is preliminary |
| "Brain training improves IQ or general intelligence" | Far transfer to general intelligence is not supported (Sala & Gobet, 2023) |
| "Our product is clinically proven to reverse cognitive decline" | No software product has this evidence; FINGER/POINTER show small slowing of decline, not reversal |
| "Brain fog is a medically recognised condition" | It is a subjective syndrome, not a clinical diagnosis |
| "Our product can diagnose cognitive impairment" | Subjective brain fog scores do not diagnose cognitive impairment (0.1 SD objective deficit) |
| "Exercise eliminates brain fog" | No RCT has tested this directly |
| "Our product replaces medical care for cognitive concerns" | It is a lifestyle intervention, not a medical treatment |
| "Effects are guaranteed" | Effect sizes are small and variable; individual results will vary |
| "Our product is equivalent to FINGER/US POINTER" | We are inspired by these trials; our implementation has not been independently validated |

---

## 11. Concrete Intervention Protocol

### 11.1 Cognitive Training Component

| Parameter | Value | Evidence Basis |
|---|---|---|
| **Session length** | 20–30 min (adaptive); up to 45 min for older adults | npj Digital Medicine (2024); ACTIVE (60–75 min) |
| **Frequency** | 2–3×/week (not more) | Lampit et al. (2014) moderator analysis |
| **Program length** | 12 weeks minimum | Network meta-analysis 2025 (exercise); ACTIVE (5–6 weeks + boosters) |
| **Adaptive difficulty rule** | Adjust difficulty to maintain ~80% accuracy; increase difficulty after 3 consecutive correct, decrease after 2 consecutive incorrect | Lampit et al. (2014) — adaptive > non-adaptive |
| **Minimum sessions** | ≥ 10 adaptive sessions before expecting measurable effects | Lampit et al. (2014); ACTIVE (10 sessions) |
| **Booster sessions** | 4 sessions at 3 months and 6 months post-completion | ACTIVE trial booster protocol |
| **Domains** | Processing speed, working memory, executive function (rotating) | ACTIVE trial (reasoning, speed, memory) |
| **Rest rules** | 5-min break every 15 min; stop if accuracy < 50% for 5 consecutive trials | [UNVERIFIED — based on general cognitive fatigue literature] |

### 11.2 Physical Exercise Component

| Parameter | Value | Evidence Basis |
|---|---|---|
| **Resistance training** | 2×/week, 45 min, moderate intensity | Network meta-analysis 2025 |
| **Aerobic training** | 3×/week, 30 min, moderate-to-vigorous | US POINTER protocol |
| **Program length** | ≥ 12 weeks | Network meta-analysis 2025 |
| **Progression** | Increase resistance by 5–10% when 12 reps achievable | Standard progressive overload principles |

### 11.3 Spacing and Scheduling Rules

| Rule | Evidence Basis |
|---|---|
| Space cognitive training sessions ≥ 24 hours apart | Spacing effect (d = 0.71) |
| Do not schedule demanding sessions when user reports < 6 hours sleep | Sleep deprivation impairs cognition |
| Schedule sessions at consistent times each week | Circadian rhythm stability |
| Avoid scheduling within 2 hours of bedtime | Sleep onset proximity impairs consolidation |
| Include rest days (no cognitive training) | Lampit et al. — > 3×/week reduces efficacy |

### 11.4 Multidomain Integration

| Component | Frequency | Delivery |
|---|---|---|
| Cognitive training | 2–3×/week | In-app, adaptive |
| Physical exercise | 2–3×/week | In-app guidance + wearable tracking |
| Dietary guidance | Weekly | In-app tips + tracking |
| Social engagement | Weekly | Group challenges or peer matching |
| Vascular risk monitoring | Every 6 months | Clinical referral or in-app tracking |
| Sleep tracking | Continuous | Wearable integration |

### 11.5 Measurement Schedule

| Timepoint | Measures |
|---|---|
| **Baseline** | BFS, FACs, cognitive battery, PHQ-9, GAD-7, PSQI, physical activity, vascular risk |
| **Weekly** | BFS (short form), FACs, sleep, physical activity, mood |
| **4 weeks** | Cognitive battery (abbreviated) |
| **12 weeks** | Full cognitive battery, BFS, FACs, PHQ-9, GAD-7, PSQI, physical activity, vascular risk |
| **6 months** | Full reassessment + booster cognitive training |
| **12 months** | Full reassessment |

---

## 12. References

1. Debowska, A., et al. (2023). Brain Fog Scale (BFS): Scale development and validation. *Personality and Individual Differences.* https://doi.org/10.1016/j.paid.2023.112427
2. FACs development. *PLOS ONE*, 2024. https://doi.org/10.1371/journal.pone.0295593
3. FACs in SARS-CoV-2 survivors. PMC11050894.
4. Knowles, et al. (2024). BFASS — Coeliac disease. *Alimentary Pharmacology & Therapeutics.* https://doi.org/10.1111/apt.17942
5. LBFSS. *Lupus Science & Medicine*, 2026. https://doi.org/10.1136/lupus-2026-002148
6. PDQ-20. Sullivan et al. (1990); systematic review: https://doi.org/10.1155/2024/9614163
7. SSTICS. Stip et al. (2003); German validation: https://doi.org/10.1080/13803395.2026.2627998
8. Lampit, A., Hallock, H., & Valenzuela, M. (2014). *PLOS Medicine.* https://doi.org/10.1371/journal.pmed.1001756
9. Kelly, M.E., et al. (2014). *Ageing Research Reviews.* https://doi.org/10.1016/j.arr.2014.02.004
10. Nguyen et al. (2022). [UNVERIFIED — publication bias corrected meta-analysis]
11. Rebok, G.W., et al. (2014). ACTIVE 10-year follow-up. *JAGS.* PMC4055506
12. Gavelin et al. / Bahar-Fuchs et al. (2020). Meta-review of 39 reviews. PMC7305099
13. Sala, G., & Gobet, F. (2023). *Perspectives on Psychological Science.* PMC9903001
14. Ngandu, T., et al. (2015). FINGER trial. *The Lancet.* https://doi.org/10.1016/S0140-6736(15)60461-5
15. Baker, L.D., et al. (2025). US POINTER. *JAMA.* https://doi.org/10.1001/jama.2025.12923
16. Long COVID brain fog prevalence. *Medicine*, 2026. https://doi.org/10.1097/MD.0000000000049022
17. Long COVID brain fog interventions. PMC11176231
18. Network meta-analysis 58 RCTs. *Frontiers in Aging Neuroscience*, 2025. https://doi.org/10.3389/fnagi.2025.1510773
19. Jennings, et al. (2023). Subjective brain fog 4D. PMC11191638
20. Xie, L., et al. (2013). Glymphatic system. *Science.* PMC3880190
21. Cepeda, N.J., et al. (2006). Spacing effect meta-analysis. [UNVERIFIED]
22. Dose-response CCT. *npj Digital Medicine*, 2024. https://doi.org/10.1038/s41746-024-01210-9
23. Transparency in cognitive training meta-analyses. PMC12328470
24. Neuroprotective aspects of sleep. PMC4651462

---

*End of dossier. This document should be reviewed and updated as new evidence emerges. All effect sizes are approximate and should be verified against original sources before use in product copy.*
