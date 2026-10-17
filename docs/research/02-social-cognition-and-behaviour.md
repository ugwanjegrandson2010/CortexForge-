# 02 — Game-Based Social-Cognitive and Behavioural Assessment: A Research Dossier

**Project:** CortexForge — Adaptive Learning System  
**Scope:** Instruments that use game-like or interactive tasks to measure how a person behaves socially and what kind of social actor they are.  
**Audience:** Technical implementer building scoring algorithms.  
**Date:** 2026-10-17  

---

## Table of Contents

1. [Theory of Mind (ToM) Tasks](#1-theory-of-mind-tom-tasks)
2. [Social Preference / Economic Games](#2-social-preference--economic-games)
3. [Personality and Social Style Instruments](#3-personality-and-social-style-instruments)
4. [Impulsivity and Risk-Taking](#4-impulsivity-and-risk-taking)
5. [Social Network, Social Capital, and Loneliness](#5-social-network-social-capital-and-loneliness)
6. [Validated Social-Cognitive Serious Games](#6-validated-social-cognitive-serious-games)
7. [Social Profile Specification](#7-social-profile-specification)
8. [Licensing Summary](#8-licensing-summary)
9. [References](#9-references)

---

## 1. Theory of Mind (ToM) Tasks

Theory of Mind (ToM) is the ability to attribute mental states — beliefs, intentions, desires, emotions, knowledge — to oneself and others, and to understand that others have mental states that differ from one's own (Premack & Woodruff, 1978; Wimmer & Perner, 1983). ToM tasks are the closest thing psychology has to a "game" for probing social cognition: they present interactive or narrative scenarios and require the participant to model what another agent knows, feels, or intends.

### 1.1 First- and Second-Order False Belief Tasks

**What they measure:** The ability to understand that another person can hold a belief that is false (first-order: "She believes X, but X is not true") or that one person can hold a false belief about another person's belief (second-order: "He believes that she believes X, but X is not true").

**Task mechanics:**
- **First-order (e.g., Sally-Anne, Cigarette, Washing Machine stories):** A character places an object in location A. While the character is absent, the object is moved to location B. The participant is asked: "Where will the character look for the object?" A correct answer requires the participant to attribute a false belief to the character. Control questions verify memory and factual understanding (e.g., "Where is the object really?").
- **Second-order (e.g., Ice-Cream Van, Burglar, Wallpaper stories):** Two characters are involved. Character A does not witness an event that Character B witnesses (or vice versa). The participant must reason about what Character A believes about Character B's belief. For example: "John thinks that Mary thinks the ice cream van is at the park — but Mary has actually seen it move to the church. Where does John think Mary will go?"

**Scoring formula:**
- Each story yields a binary score: 1 = correct (participant correctly attributes the false belief), 0 = incorrect.
- A participant must answer both the false-belief question AND the control/memory questions correctly to receive the point.
- First-order score: sum across first-order stories (typically 0–2 or 0–4 depending on the number of stories used).
- Second-order score: sum across second-order stories (typically 0–2).
- Some studies require passing both first-order stories before second-order is scored (non-casual performance criterion).

**Psychometric evidence:**
- First-order false belief tasks are near-universal in typically developing children by age 4–5 (Wellman, Cross, & Watson, 2001).
- Second-order tasks develop later, around age 6–7 (Perner & Wimmer, 1985; Sullivan, Zaitchik, & Tager-Flusberg, 1994).
- In adults, these tasks show ceiling effects in neurotypical populations, limiting individual-difference sensitivity (Apperly, 2012).
- Test-retest reliability is generally good for the pass/fail dichotomy but the tasks are too easy for fine-grained adult assessment.

**Licensing:** The specific story materials (Sally-Anne, Ice-Cream Van, etc.) are published in academic papers and widely reproduced in research. The original publications are copyrighted, but the task paradigm itself is not patentable. Individual story texts may be subject to the publisher's copyright. **Status: Research use broadly permitted; build original story analogues to avoid publisher restrictions.**

**CortexForge module (3–8 min):** Present 2 first-order and 2 second-order false-belief vignettes as interactive comic-panel sequences. The participant clicks on where the character will look. Score as binary per story. This is a quick screening module; ceiling effects mean it should not be the sole ToM measure for adults.

---

### 1.2 Strange Stories (Happé, 1994)

**What it measures:** Advanced ToM — the ability to understand non-literal speech, including lies, white lies, double bluffs, irony, sarcasm, persuasion, jokes, figures of speech, and misunderstandings. The participant must infer the speaker's intention when the literal meaning of their utterance is not what they actually mean.

**Task mechanics:**
- 24 short vignettes (2 each of 12 themes: lie, irony, double bluff, pretence, joke, appearance/reality, white lie, persuasion, misunderstanding, forgetting, contrary emotions, idioms) plus 6 control stories of similar conceptual complexity but without ToM demands.
- Stories are read aloud (or presented as text) and the participant is asked: "Why did [character] say that?" or "Was it true what [character] said?"
- The participant provides an open-ended verbal explanation.

**Scoring formula:**
- Each story is scored on a 0–2 scale:
  - **2** = fully correct answer, explicitly mentioning the correct mental state.
  - **1** = partially correct, implicitly mentioning the correct mental state.
  - **0** = incorrect.
- Two scores are derived:
  1. **Correct answer score:** Sum of all story scores (range 0–48 for 24 stories, or 0–10 for a 5-story subset).
  2. **Mental explanation score:** Number of stories for which the participant used a mental (as opposed to physical) justification (range 0–24).
- Inter-rater concordance: 97% for correct answer score, 95% for mental explanation score (Happé et al., 1998).

**Psychometric evidence:**
- Internal consistency: α = 0.61 for social stories, α = 0.76 for control stories in one study (Devine & Hughes, 2016; Hayward & Homer, 2017). The relatively low internal consistency for social stories reflects the heterogeneity of the 12 story types.
- Discriminates between autistic and non-autistic groups (Happé, 1994; White et al., 2009).
- Suitable for both children and adults (Happé, 1994).
- A 16-story subset (8 social + 8 control) takes ~10 minutes (Murray et al., 2017).

**Licensing:** The original Strange Stories materials are copyrighted by Happé and the publishers. **Status: Copyrighted — build original story analogues with the same 12 thematic categories.**

**CortexForge module (3–8 min):** Present 5–8 original vignettes covering the key categories (lie, white lie, irony, double bluff, persuasion). Use a multiple-choice format with 4 options (one correct mental-state explanation, one physical explanation, one incorrect mental-state explanation, one "don't know") to enable automated scoring. Score 2/1/0 per story.

---

### 1.3 Reading the Mind in the Eyes Test — RMET (Baron-Cohen et al., 2001)

**What it measures:** The ability to infer complex mental states (not just basic emotions) from photographs of the eye region of the face. Marketed as an "advanced test of adult social intelligence" and a measure of subtle social sensitivity.

**Task mechanics:**
- 36 (original) or 36 (revised) black-and-white photographs showing only the eye region of actors' faces.
- For each photograph, the participant chooses which of four words best describes what the person in the photograph is thinking or feeling.
- The words are complex mental states (e.g., "contemplating," "flustered," "skeptical," "flirtatious"), not basic emotions.
- A glossary is provided for difficult words.

**Scoring formula:**
- Each item: 1 = correct, 0 = incorrect.
- Total score: sum of all items (range 0–36).
- Higher scores indicate better mental-state recognition from eye-region cues.

**Psychometric evidence:**
- **Internal consistency is poor:** Cronbach's alpha ranges from .37 to .77 across studies, with many below the .70 acceptability threshold (Khorashad et al., 2015; Prevost et al., 2014; Harkness et al., 2010; Voracek & Dressler, 2006; Soderstrand & Almkvist, 2012; Olderbak et al., 2015).
- **Factor structure is unclear:** Confirmatory factor analysis suggests a single factor is inadequate; most items do not load on a single factor (Olderbak et al., 2015).
- **Test-retest reliability is good:** r = .74–.81 across studies (Pinkham et al., 2016; Prevost et al., 2014).
- **Construct validity is questionable:** Convergent validity with other ToM measures is weak; the RMET does not correlate strongly with self-reported empathy or other mentalizing tasks (Olderbak et al., 2015).
- **Cross-cultural validity is limited:** Non-Western participants score differently; the instrument lacks racial/ethnic diversity in stimuli (Khorashad et al., 2015; UNVERIFIED — specific citation needed for the cross-cultural critique).
- **Ceiling effects:** The original 1997 version was too easy; the 2001 revision addressed this but still shows ceiling effects in some populations.
- **Discriminates clinical groups:** Adults with Asperger syndrome/HFA score significantly lower than controls (Baron-Cohen et al., 2001).
- **Inverse correlation with Autism Spectrum Quotient (AQ):** r ≈ –.56 (Baron-Cohen & Wheelwright, 2004).

**Licensing:** The RMET photographs and word lists are copyrighted by Baron-Cohen and the publishers. **Status: Copyrighted — requires permission for research use; clinical use requires purchase. Build original analogues with diverse, validated facial stimuli.**

**CortexForge module (3–8 min):** Present 12–18 original eye-region photographs (sourced from openly licensed or newly created stimuli) with 4 mental-state options each. Score 1/0 per item. Given the psychometric limitations, use this as a supplementary measure, not a primary ToM score.

---

### 1.4 Yoni Task (Shamay-Tsoory & Aharon-Peretz, 2007)

**What it measures:** First-order and second-order, affective and cognitive mental-state attributions based on verbal instructions, eye-gaze direction, and facial expressions. The task separates **affective ToM** (inferring what Yoni feels/likes) from **cognitive ToM** (inferring what Yoni thinks).

**Task mechanics:**
- 98 items total (84 mental items + 14 physical control items) in the full version; 42 mental + 6 control in the short version (Yoni-48).
- A cartoon face named "Yoni" appears at the center of the screen, surrounded by four colored pictures in the corners (fruits, animals, faces, objects).
- A sentence appears at the top: e.g., "Yoni is thinking of…" (cognitive), "Yoni loves…" (affective), or "Yoni is close to…" (physical control).
- The participant clicks on the picture that Yoni is referring to, based on Yoni's gaze direction and facial expression.
- **First-order trials:** Yoni's mental state directly (e.g., "Yoni is thinking of the fruit that is near him").
- **Second-order trials:** Yoni's mental state about another character's mental state (e.g., "Yoni is thinking of the chair that [another face] wants").

**Scoring formula:**
- Each mental item: 1 = correct, 0 = incorrect.
- **Accuracy (ACC):** Sum of correct mental items / total mental items (range 0–1).
- **Response time (RT):** Computed separately; range 0–1 after normalization.
- **Cognitive/Affective Accuracy Index:** Balance between cognitive and affective components.
- Composite scores can be computed for first-order vs. second-order, and cognitive vs. affective.

**Psychometric evidence:**
- The Yoni-48 short version has been validated in Italian clinical settings (Isernia et al., 2022a,b).
- Test-retest reliability: ICC > 0.80 for accuracy; MDC = 0.10 (Isernia et al., 2022a).
- The task discriminates between clinical groups (e.g., schizophrenia, autism) and controls (Shamay-Tsoory et al., 2007).
- Normative data available for the Italian version, adjusted for sex, age, and education (Isernia et al., 2022b).
- The multidimensional structure (cognitive × affective × first/second order) is a key advantage over unidimensional ToM tasks.

**Licensing:** The Yoni task stimuli (cartoon faces, pictures) are copyrighted by the developers. **Status: Copyrighted — build original analogues with the same task structure (central face + 4 corner objects + gaze/expression cues).**

**CortexForge module (3–8 min):** Implement 20–24 original Yoni-style trials (10 cognitive, 10 affective, 4 physical control). Use original cartoon faces and object images. Score accuracy separately for cognitive and affective subscales. This is a strong candidate for the primary ToM module because of its multidimensional scoring.

---

### 1.5 Animations Task — Frith-Happé Moving Shapes (Abell et al., 2000; Castelli et al., 2000, 2002)

**What it measures:** Spontaneous attribution of mental states to ambiguous abstract visual stimuli (geometric shapes). The task measures implicit, unprompted mentalizing — whether the participant spontaneously describes the shapes' interactions in terms of intentions, beliefs, and emotions.

**Task mechanics:**
- 12 silent animations (34–45 seconds each) featuring a large red triangle and a small blue triangle moving on a white background.
- Three conditions:
  1. **Random:** The triangles move purposelessly, without interaction.
  2. **Goal-Directed (GD):** The triangles interact in a purely physical manner (chasing, dancing, fighting, leading).
  3. **Theory of Mind (ToM):** The triangles move as if one is reacting to the other's mental state (coaxing, surprising, seducing, mocking).
- After each animation, the participant provides an open-ended verbal description of what happened.

**Scoring formula:**
- Two dimensions are coded from the verbal descriptions:
  1. **Appropriateness (AP):** 0–3 scale (0 = "don't know"; 1 = focuses on a minor aspect; 2 = partial description; 3 = fully correct description).
  2. **Intentionality (IN):** 0–5 scale (0 = non-purposeful action; 1 = purposeful action without another; 2 = purposeful action with another; 3 = goal-directed intention; 4 = attribution of mental states during reciprocal interaction; 5 = one agent intentionally affecting another's mental state).
- Scores are summed across animations. Intentionality range: 0–40 (8 ToM animations × 5 max).
- The key contrast is ToM condition intentionality vs. GD and Random condition intentionality.

**Psychometric evidence:**
- Discriminates between autistic and non-autistic groups (Abell et al., 2000; Castelli et al., 2000, 2002).
- The ToM condition reliably elicits more mental-state language than GD and Random conditions.
- Normative data available (PMC7215251 — UNVERIFIED, specific normative study).
- The task is non-verbal in stimulus (no faces, no language), making it culturally portable.
- Inter-rater reliability is generally good for the intentionality scale (Castelli et al., 2000).

**Licensing:** The specific animation stimuli are copyrighted by the developers. **Status: Copyrighted — build original geometric-shape animations with the same three-condition structure.**

**CortexForge module (3–8 min):** Present 6 original animations (2 Random, 2 GD, 2 ToM). Use a simplified scoring: present 4 multiple-choice descriptions per animation and have the participant select the best one. Score intentionality level of the selected description. This automates what is normally an open-ended coding task.

---

### 1.6 MASC — Movie for the Assessment of Social Cognition (Dziobek et al., 2006)

**What it measures:** The ability to identify thoughts, feelings, and intentions of characters in a naturalistic social scenario (a dinner party). The MASC is one of the most ecologically valid ToM measures, using dynamic video rather than static stimuli.

**Task mechanics:**
- A 15-minute film depicts four characters (2 male, 2 female) interacting at a dinner party. Themes include dating, friendship, and social conflict.
- The film is paused at 46 (original) or 45 (multiple-choice version) time points.
- At each pause, the participant is asked: "What is [character] feeling/thinking/intending to do?"
- The original version uses open-ended verbal responses; a multiple-choice version (4 options) is also available.
- 6 control questions assess non-social inference (e.g., factual details about the scene).

**Scoring formula:**
- **Original (open-ended) version:** Each response scored 2 (fully correct), 1 (partially correct), or 0 (incorrect) using a standardized scoring key. Total score = sum of all items.
- **Multiple-choice version:** Each item scored 1 (correct) or 0 (incorrect). Total score = sum (range 0–45).
- Subscale scores:
  - **Emotions:** 15 items (α = 0.62)
  - **Thoughts:** 9 items (α = 0.55)
  - **Intentions:** 17 items (α = 0.71)
- Error pattern analysis: **over-mentalizing** (attributing mental states where none exist), **under-mentalizing** (failing to attribute mental states where they exist), **no mentalizing** (no mental-state inference).
- **Cognitive ToM** = thoughts + intentions; **Affective ToM** = emotions.

**Psychometric evidence:**
- Internal consistency: α = 0.84–0.86 for total score (Dziobek et al., 2006; Hassenstab et al., 2007).
- Inter-rater reliability: ICC = 0.99 (Dziobek et al., 2006).
- Test-retest reliability: r = 0.97 (Dziobek et al., 2006).
- Discriminates between autism spectrum disorder and controls (Dziobek et al., 2006).
- Also sensitive to borderline personality disorder (BPD) social cognition deficits (PMC2999836).
- Avoids ceiling effects in a way that simpler ToM tasks do not.
- The multiple-choice version allows error pattern analysis (over- vs. under-mentalizing), which has clinical significance (Montag et al., 2010).

**Licensing:** The MASC film and scoring materials are copyrighted by Dziobek and the publishers. **Status: Copyrighted — clinical/research use requires permission. Build original video vignettes with the same structure (multi-character social scenario, paused questions about mental states).**

**CortexForge module (3–8 min):** Create 3–4 short original video vignettes (30–60 seconds each) depicting social interactions. Pause 8–10 times total and ask multiple-choice questions about characters' feelings, thoughts, and intentions. Score 1/0 per item. Include 2 control questions. This is the strongest candidate for a primary ToM module due to ecological validity and error pattern analysis.

---

### 1.7 TASIT — Awareness of Social Inference Test (McDonald et al., 2003, 2004)

**What it measures:** Emotion recognition and complex social inference (ToM) from dynamic video vignettes. TASIT assesses the ability to integrate cues from facial expressions, prosody, gesture, and social context to interpret emotions, beliefs, and intentions — including the detection of lies and sarcasm.

**Task mechanics:**
- Three parts:
  - **Part 1 — Emotion Evaluation Test:** 24 short video clips portraying one of six basic emotions (happy, sad, fear, disgust, surprise, anger) or neutral. The participant identifies the emotion from 7 options. Maximum score: 28.
  - **Part 2 — Social Inference (Minimal):** 15 video clips depicting sincere and sarcastic interactions between two actors. After each clip, 4 yes/no questions about what the characters are doing, thinking, feeling, or saying. Maximum score: 60.
  - **Part 3 — Social Inference (Enriched):** 16 vignettes with extra contextual information (before or after the dialogue). Tests detection of lies and sarcasm. 4 questions per vignette. Maximum score: 64.
- Two equivalent forms (A and B) for retesting.

**Scoring formula:**
- Part 1: 1 point per correct emotion identification (max 28).
- Part 2: 1 point per correct answer (max 60).
- Part 3: 1 point per correct answer (max 64).
- Total score: sum of all parts (max 152).
- Subscale scores can be computed for emotion recognition, ToM-Minimal, and ToM-Enriched.

**Psychometric evidence:**
- Test-retest reliability (1 week, severe TBI): r = .74 (Part 1), r = .88 (Part 2), r = .83 (Part 3) (McDonald et al., 2006).
- Alternative form reliability (5–26 weeks): r = .83 (Part 1), r = .62 (Part 2), r = .78 (Part 3) (McDonald et al., 2006).
- No practice effects with 1-week re-administration (McDonald et al., 2006).
- Discriminates TBI patients from controls (McDonald & Flanagan, 2004; McDonald et al., 2004).
- Ecological validity: associated with spontaneous social behaviour, particularly use of humour and partner-directed behaviour (McDonald et al., 2004).
- Adolescent norms available (665 schoolchildren; Cambridge Core — UNVERIFIED, specific citation).
- TASIT-S (short form) has excellent internal consistency: Rasch item reliability > .89, item infit/outfit 0.74–1.21 (TASIT-S document, UNSW).
- Gender effects on all subtests; English proficiency affects scores (adolescent study).

**Licensing:** TASIT is published by Pearson Clinical Assessment. **Status: Copyrighted — clinical purchase required. Research licence available (minimum fee AUD 1500 for adaptation). Build original video vignettes with the same three-part structure.**

**CortexForge module (3–8 min):** Create 6–8 original short video vignettes (15–30 seconds each) depicting sincere, sarcastic, and deceptive interactions. Ask 3–4 yes/no questions per vignette. Score 1/0 per question. Focus on sarcasm and lie detection as the key social-cognitive skills.

---

### 1.8 Marble Drop Game — Higher-Order ToM (RUG Social Cognition Group; Meijering et al., 2010; Van Maanen & Verbrugge, 2010)

**What it measures:** Higher-order (second-order and above) social reasoning — the ability to recursively model another agent's reasoning about one's own reasoning ("I think that you think that I think…"). This is a game-theoretic ToM task.

**Task mechanics:**
- A two-player turn-based game equivalent to the centipede game (Rosenthal, 1981).
- A marble drops through a binary tree of trapdoors. Players take turns deciding which trapdoor to open, controlling the marble's path.
- Payoffs are color-graded marbles (not numbers), with all payoffs known in advance.
- The game requires backward induction: to play optimally, a player must predict the opponent's moves, which requires modeling the opponent's predictions of the player's own moves (second-order reasoning).
- **First-order game:** The player needs only to predict the opponent's immediate move.
- **Second-order game:** The player must predict the opponent's prediction of the player's own move.
- Higher orders can be tested with more complex game trees.

**Scoring formula:**
- The primary measure is whether the player successfully applies the required order of reasoning (correct/incorrect per game).
- Reaction times are also recorded and modeled (Van Maanen & Verbrugge, 2010).
- The proportion of games in which the participant successfully applies second-order reasoning is the key metric.
- In Meijering et al. (2010), 94% of participants performed at ceiling when the abstract problem was embedded in the marble game context, suggesting the game context facilitates higher-order reasoning.

**Psychometric evidence:**
- The Marble Drop paradigm has been used in multiple studies by the RUG group (Meijering et al., 2010; Van Maanen & Verbrugge, 2010; Van Maanen et al., 2010).
- A computational cognitive model (ACT-R) has been developed to predict reaction times and strategy use (Van Maanen & Verbrugge, 2010).
- The game-theoretic equivalence to the centipede game provides a formal framework for analyzing strategies.
- The facilitative effect of context (marble game vs. abstract matrix) is a key finding: embedding higher-order reasoning in a game context dramatically improves performance (Meijering et al., 2010).
- **Limitation:** Ceiling effects in the game context mean the task may not discriminate well among neurotypical adults.

**Licensing:** The Marble Drop game was developed at the University of Groningen (RUG). **Status: Research use appears permitted (published in academic papers); no commercial licence identified. Build original game analogues with the same centipede-game structure.**

**CortexForge module (3–8 min):** Implement a simplified marble-drop game with 4–6 trials of increasing complexity (first-order, second-order, third-order). The player competes against a computer opponent. Score whether the player's moves are consistent with the required order of reasoning. This is a genuinely game-like ToM measure and a strong differentiator for CortexForge.

---

## 2. Social Preference / Economic Games

Economic games are the gold standard for measuring social preferences in behavioural economics. They create controlled incentive-compatible situations where participants make real decisions about resource allocation, revealing their social preferences through behaviour rather than self-report.

### 2.1 Ultimatum Game (Güth, Schmittberger, & Schwarze, 1982)

**What it measures:** Fairness preferences and negative reciprocity (willingness to punish unfairness at a cost to oneself).

**Task mechanics:**
- Two players: **Proposer** and **Responder**.
- The Proposer is endowed with a sum of money (e.g., $10) and proposes how to split it with the Responder.
- The Responder can **accept** (both get the proposed split) or **reject** (neither gets anything).
- In the **strategy method**, the Responder indicates their minimum acceptable offer before seeing the actual offer.

**Scoring formula:**
- **Proposer behaviour:** The amount offered to the Responder, as a percentage of the endowment. Higher offers indicate stronger fairness preferences.
- **Responder behaviour:** The minimum acceptable offer (MAO) — the lowest offer the Responder would accept. Higher MAO indicates stronger willingness to punish unfairness.
- Typical findings: Proposers offer 40–50% on average; Responders reject offers below 20–30% (Henrich et al., 2001; Oosterbeek et al., 2004).

**Psychometric evidence:**
- Cross-cultural variation is substantial (Henrich et al., 2001).
- Test-retest reliability is moderate; behaviour is sensitive to framing and incentive compatibility (Oosterbeek et al., 2004).
- The game reliably elicits deviations from pure self-interest, demonstrating social preferences.

**Licensing:** The Ultimatum Game paradigm is a standard experimental economics task published in academic literature. **Status: Public domain — the game structure is not copyrightable. Specific experimental materials may be copyrighted.**

**CortexForge module (3–8 min):** Run 3–5 trials as Proposer and 3–5 trials as Responder (against computer opponents with programmed strategies). Score: mean offer percentage (Proposer) and MAO (Responder). This is a quick, engaging module that directly measures fairness and punishment behaviour.

---

### 2.2 Dictator Game (Kahneman, Knetsch, & Thaler, 1982; Forsythe et al., 1994)

**What it measures:** Pure altruism / generosity — the willingness to give resources to another person when there is no possibility of punishment or reciprocity.

**Task mechanics:**
- Two players: **Dictator** and **Recipient**.
- The Dictator is endowed with a sum of money and decides how much (if any) to give to the Recipient.
- The Recipient has no choice — they must accept whatever the Dictator decides.
- Unlike the Ultimatum Game, there is no strategic incentive to give (the Dictator cannot be punished).

**Scoring formula:**
- The amount given by the Dictator, as a percentage of the endowment.
- Higher amounts indicate stronger altruistic preferences.
- Typical findings: Dictators give 20–30% on average, with a substantial proportion giving nothing (Engel, 2011).

**Psychometric evidence:**
- Meta-analysis by Engel (2011) of 616 studies: mean giving = 28.3% of endowment.
- The Dictator Game is sensitive to framing, anonymity, and social distance.
- Test-retest reliability is moderate; behaviour is context-dependent.
- Considered the cleanest measure of pure altruism because it removes strategic considerations.

**Licensing:** Public domain — standard experimental economics paradigm.

**CortexForge module (3–8 min):** Run 3–5 trials as Dictator with different endowments and recipient descriptions. Score: mean giving percentage. Pair with the Ultimatum Game to separate strategic fairness (Ultimatum) from pure altruism (Dictator).

---

### 2.3 Trust Game (Berg, Dickhaut, & McCabe, 1995)

**What it measures:** Trust (Sender) and trustworthiness/reciprocity (Receiver).

**Task mechanics:**
- Two players: **Sender** (Investor) and **Receiver** (Trustee).
- Both players are endowed with a sum of money (e.g., $10).
- The Sender chooses how much of their endowment to transfer to the Receiver. The transferred amount is **tripled** by the experimenter.
- The Receiver then chooses how much of the tripled amount to return to the Sender.
- The Sender's transfer measures **trust**; the Receiver's return measures **trustworthiness** (reciprocity).

**Scoring formula:**
- **Trust:** The amount sent by the Sender, as a percentage of the endowment. Higher = more trusting.
- **Trustworthiness:** The amount returned by the Receiver, as a percentage of the tripled amount received. Higher = more trustworthy.
- Typical findings: Senders transfer 40–60% on average; Receivers return approximately the amount sent (Berg et al., 1995).

**Psychometric evidence:**
- The Trust Game is one of the most widely used measures of trust in experimental economics.
- Test-retest reliability is moderate; behaviour is sensitive to framing and partner characteristics.
- Correlates with self-reported trust measures (Glaeser et al., 2000).
- Cross-cultural variation exists (Johnson & Mislin, 2011).

**Licensing:** Public domain — standard experimental economics paradigm.

**CortexForge module (3–8 min):** Run 3–5 trials as Sender and 3–5 trials as Receiver. Score: mean transfer percentage (trust) and mean return percentage (trustworthiness). This is a strong measure of reciprocal vs. exploitative social orientation.

---

### 2.4 Public Goods Game (Samuelson, 1954; Marwell & Ames, 1979; Isaac et al., 1985)

**What it measures:** Cooperation in group settings — the willingness to contribute to a common resource at a cost to oneself, and the free-rider problem.

**Task mechanics:**
- A group of N players (typically 4) each receive an endowment (e.g., $10).
- Each player simultaneously chooses how much of their endowment to contribute to a **public pot**.
- The total contributions to the public pot are **multiplied** (typically by a factor between 1 and N, e.g., 1.6) and then **divided equally** among all group members, regardless of individual contribution.
- Individual payoff = (endowment – contribution) + (total contributions × multiplier / N).
- The Nash equilibrium is to contribute nothing (free-ride), but the social optimum is for everyone to contribute everything.

**Scoring formula:**
- **Cooperation rate:** The amount contributed, as a percentage of the endowment. Higher = more cooperative.
- Typical findings: In one-shot games, participants contribute 40–60% of their endowment on average (Ledyard, 1995).
- In repeated games, contributions tend to decline over time (the "end-game effect") unless punishment is available.

**Psychometric evidence:**
- One of the most studied paradigms in experimental economics (Ledyard, 1995).
- Sensitive to group size, multiplier, and framing.
- Conditional cooperation is a robust finding: people cooperate more when they believe others will cooperate (Fischbacher et al., 2001).
- Test-retest reliability is moderate; behaviour is highly context-dependent.

**Licensing:** Public domain — standard experimental economics paradigm.

**CortexForge module (3–8 min):** Run 3–5 trials in a group of 4 (3 computer players with programmed strategies: one full cooperator, one free-rider, one conditional cooperator). Score: mean contribution percentage. Vary the multiplier across trials to test sensitivity to marginal per-capita return.

---

### 2.5 Prisoner's Dilemma (Rapoport & Chammah, 1965; Axelrod, 1984)

**What it measures:** Cooperation vs. defection in a dyadic interaction where individual and collective interests conflict.

**Task mechanics:**
- Two players simultaneously choose to **cooperate (C)** or **defect (D)**.
- Payoff matrix (typical):
  - Both cooperate: R = 3 each (reward)
  - Both defect: P = 1 each (punishment)
  - One defects, one cooperates: T = 5 (temptation) for defector, S = 0 (sucker) for cooperator
  - Requires T > R > P > S and 2R > T + S.
- Can be one-shot or repeated (iterated).

**Scoring formula:**
- **Cooperation rate:** Percentage of trials on which the player chooses C.
- In the iterated version, strategy classification (e.g., tit-for-tat, always defect, always cooperate, win-stay-lose-shift) can be derived from the sequence of choices.

**Psychometric evidence:**
- The Prisoner's Dilemma is the foundational paradigm of cooperation research (Axelrod, 1984).
- In one-shot games, defection is the Nash equilibrium, but 30–50% of participants cooperate (Sally, 1995).
- In the iterated version, tit-for-tat is a robustly successful strategy (Axelrod, 1984).
- Test-retest reliability is moderate; behaviour is sensitive to payoff structure and framing.

**Licensing:** Public domain — standard game theory paradigm.

**CortexForge module (3–8 min):** Run 5–10 trials of an iterated Prisoner's Dilemma against a computer opponent using a tit-for-tat strategy. Score: cooperation rate and strategy classification. This measures whether the participant is a cooperator, defector, or conditional cooperator.

---

## 3. Personality and Social Style Instruments

### 3.1 Big Five / IPIP-NEO (Goldberg, 1999)

**What it measures:** The Five-Factor Model (FFM) of personality: Openness to Experience, Conscientiousness, Extraversion, Agreeableness, Neuroticism (OCEAN). Each domain has 6 facets (30 facets total).

**Task mechanics:**
- Self-report questionnaire with items rated on a 5-point Likert scale (1 = strongly disagree, 5 = strongly agree).
- Versions: IPIP-NEO-300 (300 items), IPIP-NEO-120 (120 items), IPIP-NEO-60 (60 items).
- Items are behavioural/descriptive statements (e.g., "I feel comfortable around people," "I pay attention to details").

**Scoring formula:**
- Reverse-score designated items.
- Sum items within each domain (and facet).
- Domain scores: range depends on version (e.g., 60-item version: 12–60 per domain).
- Higher scores indicate stronger expression of the trait.

**Psychometric evidence:**
- The Big Five model is the dominant personality taxonomy, replicated across cultures and languages (Digman, 1990; Goldberg, 1990; McCrae & John, 1992).
- IPIP-NEO-120 correlates strongly with the proprietary NEO-PI-R (r = .75–.81 for domain scores) (PMC12719228 — UNVERIFIED, specific correlation values).
- Internal consistency: α = .77–.90 for domain scores across versions.
- Test-retest reliability: r = .80–.90 over 1–2 years.
- Predictive validity: Conscientiousness predicts job and academic performance; Neuroticism predicts well-being and health outcomes; Extraversion predicts social outcomes (Barrick & Mount, 1991; Poropat, 2009; Bogg & Roberts, 2004).

**Licensing:** The IPIP items are explicitly in the **public domain** (Goldberg, 1999; ipip.ori.org). **Status: Public domain — free for any use.**

**CortexForge module (3–8 min):** Use the IPIP-NEO-60 (60 items, ~5 minutes). Score all 5 domains and 30 facets. This is the primary personality module and is freely implementable.

---

### 3.2 HEXACO-PI-R (Lee & Ashton, 2004)

**What it measures:** Six personality dimensions: Honesty-Humility (H), Emotionality (E), Extraversion (X), Agreeableness (A), Conscientiousness (C), Openness to Experience (O). Each domain has 4 facets (25 facets total, with one facet split).

**Task mechanics:**
- Self-report questionnaire with items rated on a 5-point Likert scale.
- Versions: HEXACO-PI-R-200 (200 items), HEXACO-PI-R-100 (100 items), HEXACO-60 (60 items).
- The key addition over the Big Five is **Honesty-Humility** (sincerity, fairness, greed avoidance, modesty), which captures morally relevant variance not well-represented in the FFM.

**Scoring formula:**
- Reverse-score designated items.
- Sum items within each domain (and facet).
- Domain scores: range depends on version.
- Higher scores indicate stronger expression of the trait.

**Psychometric evidence:**
- The six-factor structure is replicated across cultures and languages (Lee & Ashton, 2004, 2006).
- Honesty-Humility is independent of the Big Five factors and predicts morally relevant outcomes (e.g., delinquency, workplace deviance) over and above the Big Five (Ashton & Lee, 2007; Lee et al., 2005).
- Internal consistency: α = .77–.89 for domain scores.
- The IPIP-HEXACO scales (public domain) correlate strongly with HEXACO-PI-R scales (Ashton, Lee, & Goldberg, 2007).

**Licensing:** HEXACO-PI-R is free for non-profit academic research. Non-academic use requires a licence (C$2 per administration, minimum 50 administrations). The IPIP-HEXACO scales are in the **public domain** (Ashton, Lee, & Goldberg, 2007). **Status: HEXACO-PI-R — free for research, licensed for commercial. IPIP-HEXACO — public domain.**

**CortexForge module (3–8 min):** Use the IPIP-HEXACO (public domain) or HEXACO-60 (research use). Score all 6 domains. The Honesty-Humility scale is particularly relevant for social behaviour profiling.

---

### 3.3 Dark Triad: MACH-IV, NPI, and SRP-III

**What it measures:** Three socially aversive personality traits:
- **Machiavellianism:** Manipulative, strategic, cynical, amoral interpersonal style.
- **Narcissism:** Grandiose self-importance, entitlement, need for admiration.
- **Psychopathy:** Callousness, lack of empathy, impulsivity, low anxiety.

#### MACH-IV (Christie & Geis, 1970)

**Task mechanics:**
- 20 items rated on a 5-point Likert scale (1 = strongly disagree, 5 = strongly agree).
- Items assess cynical worldview, manipulative tactics, and amorality (e.g., "Never tell anyone the real reason you did something unless it is useful to do so").

**Scoring formula:**
- Sum all 20 items (range 20–100).
- Higher scores indicate stronger Machiavellianism.
- Internal consistency: α = .83–.85 (Christie & Geis, 1970; Jones & Paulhus, 2009).

**Psychometric evidence:**
- The MACH-IV is the most widely cited measure of Machiavellianism (Jones & Paulhus, 2009).
- Internal consistency: α = .83–.85.
- Criticized for conflating Machiavellianism with psychopathy; factor analyses suggest MACH and psychopathy measures may assess the same construct (Jones & Paulhus, 2014; UNVERIFIED — specific citation for the "distinction without a difference" critique).
- Predicts manipulative behaviour in economic games and workplace outcomes.

**Licensing:** The MACH-IV was published in 1970 in *Studies in Machiavellianism* (Academic Press). The instrument was placed in the public domain for academic, educational, and scientific research purposes by the authors. **Status: Public domain for research/educational use. Commercial use may require permission.**

#### Narcissistic Personality Inventory — NPI (Raskin & Hall, 1979)

**Task mechanics:**
- 40 forced-choice items. For each pair, the participant chooses which statement is more self-descriptive (one narcissistic, one non-narcissistic).

**Scoring formula:**
- 1 point for each narcissistic choice (range 0–40).
- Higher scores indicate stronger narcissism.
- Internal consistency: α = .80–.92 (Raskin & Hall, 1979; PMC — UNVERIFIED).

**Licensing:** The NPI is widely used in research. **Status: Research use broadly permitted; specific copyright status unclear — verify before commercial use.**

#### Self-Report Psychopathy Scale-III — SRP-III (Hare, 1985; Williams et al., 2005)

**Task mechanics:**
- 40 items rated on a 5-point Likert scale.
- Assesses callous affect, interpersonal manipulation, and impulsive lifestyle.

**Scoring formula:**
- Sum all items (range 40–200).
- Higher scores indicate stronger subclinical psychopathy.
- Internal consistency: α = .88 (PMC — UNVERIFIED).

**Licensing:** The SRP-III is used in research. **Status: Research use broadly permitted; verify copyright status.**

**CortexForge module (3–8 min):** Use the MACH-IV (20 items, public domain for research) as the primary Dark Triad measure. Optionally add a short narcissism measure (e.g., the Dirty Dozen, 12 items, Jonason & Webster, 2010 — UNVERIFIED licensing). Score each Dark Triad trait separately. These traits are critical for identifying exploitative or manipulative social actors.

---

### 3.4 Empathy Quotient — EQ (Baron-Cohen & Wheelwright, 2004)

**What it measures:** Self-reported empathy, with subscales for cognitive empathy, emotional reactivity, and social skills.

**Task mechanics:**
- 40 empathy items + 20 filler items, rated on a 4-point scale (strongly agree, slightly agree, slightly disagree, strongly disagree).
- Half the items are reverse-scored.

**Scoring formula:**
- 2 points for strongly endorsing the empathic response, 1 point for mild endorsement, 0 for anything else.
- Total score: range 0–80.
- Subscale scores: Cognitive empathy, Emotional reactivity, Social skills (Lawrence et al., 2004).

**Psychometric evidence:**
- Internal consistency: α = .78–.92 across studies (Baron-Cohen & Wheelwright, 2004; Vellante et al., 2013; Voracek & Dressler, 2006).
- Test-retest reliability: r = .84–.97 (Lawrence et al., 2004; Baron-Cohen & Wheelwright, 2004).
- Discriminates between AS/HFA and controls (Baron-Cohen & Wheelwright, 2004).
- Inverse correlation with AQ: r = –.56 (Baron-Cohen & Wheelwright, 2004).
- Normative data: mean ≈ 42–45 for typical adults (Baron-Cohen & Wheelwright, 2004; Cassidy et al., 2016).
- Cut-off of 30 recommended for identifying lack of empathy (Baron-Cohen & Wheelwright, 2004).
- Factor structure: three factors (cognitive empathy, emotional reactivity, social skills) supported by CFA (Lawrence et al., 2004).

**Licensing:** The EQ is copyrighted by Baron-Cohen and Wheelwright. **Status: Copyrighted — research use may require permission. Build original empathy items or use public-domain alternatives.**

**CortexForge module (3–8 min):** Use a short empathy measure (e.g., the 28-item EQ-short, or build original items). Score cognitive and emotional empathy separately. This is a key measure for the social profile.

---

### 3.5 Social Value Orientation — SVO Slider Measure (Murphy et al., 2011)

**What it measures:** Stable preferences for resource allocation between self and others — the weight a person attaches to others' welfare relative to their own.

**Task mechanics:**
- 6 primary items (plus 9 optional secondary items).
- Each item presents a resource allocation task: the participant chooses how to distribute units between themselves and another person.
- The allocations are represented as points on a circle (the "SVO ring"), with the x-axis representing self-payoff and the y-axis representing other-payoff.
- The participant moves a slider to select their preferred allocation.

**Scoring formula:**
- Compute the mean allocation for self (x̄s) and the mean allocation for other (x̄o).
- SVO angle = arctan((x̄o – 50) / (x̄s – 50)).
- Classification by angle:
  - **Altruistic:** > 57.15°
  - **Prosocial:** 22.45° to 57.15°
  - **Individualistic:** –12.04° to 22.45°
  - **Competitive:** < –12.04°
- The **Ring Measure** (Liebrand, 1984) uses 24 items and computes a motivational vector (length = consistency, angle = SVO).

**Psychometric evidence:**
- The SVO Slider Measure has good internal consistency and test-retest reliability (Murphy et al., 2011; Cambridge Core 2022 — UNVERIFIED, specific reliability values).
- Predicts cooperation in economic games, prosocial behaviour, and charitable giving (Murphy et al., 2011).
- The continuous SVO angle provides more resolution than categorical measures.
- The Triple-Dominance Measure (Van Lange et al., 1997) is a simpler 9-item categorical alternative.

**Licensing:** The SVO Slider Measure is freely available for research use (Murphy et al., 2011; vlab.ethz.ch/svo). **Status: Free for research use — build original allocation tasks with the same ring-measure structure.**

**CortexForge module (3–8 min):** Implement 6 original SVO slider items. Compute the SVO angle and classify the participant. This is a direct, behaviourally grounded measure of social preference that complements the economic games.

---

### 3.6 Need for Cognition — NCS (Cacioppo & Petty, 1982)

**What it measures:** The tendency to engage in and enjoy effortful cognitive activity — intellectual curiosity and preference for deep thinking.

**Task mechanics:**
- 18 items (short form) rated on a 5-point Likert scale (1 = extremely uncharacteristic, 5 = extremely characteristic).
- 9 items are reverse-scored.
- Items assess enjoyment of thinking, problem-solving, and complex reasoning (e.g., "I like to have the responsibility of handling a situation that requires a lot of thinking").

**Scoring formula:**
- Reverse-score the 9 designated items.
- Sum all 18 items (range 18–90).
- Higher scores indicate greater need for cognition.

**Psychometric evidence:**
- Internal consistency: α = .90–.94 for the 18-item version (Cacioppo, Petty, & Kao, 1984; Lins de Holanda Coelho et al., 2020).
- Test-retest reliability: high (Cacioppo et al., 1984).
- Correlates modestly with cognitive ability: r = .25 with fluid intelligence, r = .39 with ACT scores (Fleischhauer et al., 2010; Cacioppo & Petty, 1982).
- Not influenced by gender, test anxiety, or social desirability (Cacioppo & Petty, 1982).
- The NCS-6 (6-item short version) has excellent psychometric properties (PMC7545655).

**Licensing:** The NCS is widely used in research. **Status: Research use broadly permitted; the scale is published in academic literature. Verify copyright status for commercial use.**

**CortexForge module (3–8 min):** Use the NCS-6 (6 items, ~2 minutes). Score as a single total. This measures whether the participant is a "deep thinker" or "cognitive miser," which moderates how they approach social-cognitive tasks.

---

### 3.7 General Decision-Making Style Inventory — GDMS (Scott & Bruce, 1995)

**What it measures:** Five decision-making styles:
1. **Rational:** Systematic search for and logical evaluation of alternatives.
2. **Intuitive:** Reliance on hunches, feelings, and impressions.
3. **Dependent:** Reliance on advice and direction from others.
4. **Avoidant:** Tendency to avoid or delay decisions.
5. **Spontaneous:** Desire to complete decisions quickly and immediately.

**Task mechanics:**
- 25 items (5 per subscale) rated on a 5-point Likert scale (1 = strongly disagree, 5 = strongly agree).
- Items describe decision-making habits (e.g., "I make decisions in a logical and systematic way" — rational; "I generally make decisions that feel right to me" — intuitive).

**Scoring formula:**
- Sum items within each subscale (range 5–25 per style).
- Higher scores indicate greater use of that style.
- The dominant style is the one with the highest score.

**Psychometric evidence:**
- Validated in Canada, Sweden, UK, and Italy (Loo, 2000; Thunholm, 2004; Spicer & Sadler-Smith, 2005; Gambetti et al., 2008).
- Internal consistency: good (Scott & Bruce, 1995).
- The five-factor structure is confirmed across cultures.
- The GDMS correlates with decision-making competencies and mental health (Cambridge Core — UNVERIFIED, specific citation).

**Licensing:** The GDMS is published in academic literature. **Status: Research use broadly permitted; verify copyright status.**

**CortexForge module (3–8 min):** Use the full 25-item GDMS (~5 minutes). Score all 5 styles. The dependent and avoidant styles are particularly relevant for social behaviour (reliance on others vs. avoidance of social decisions).

---

## 4. Impulsivity and Risk-Taking

### 4.1 Kirby Monetary Choice Questionnaire — MCQ (Kirby, Petry, & Bickel, 1999)

**What it measures:** Delay discounting — the rate at which a person devalues future rewards relative to immediate rewards. Higher discounting = greater impulsivity.

**Task mechanics:**
- 27 (MCQ-27) or 21 (MCQ-21) dichotomous choices between a smaller immediate reward (SIR) and a larger delayed reward (LDR).
- Items vary in reward magnitude (small, medium, large) and delay (7–186 days).
- Example: "Would you prefer $54 today or $80 in 30 days?"

**Scoring formula:**
- The hyperbolic discounting function: V = A / (1 + kD), where V = present value, A = delayed amount, D = delay, k = discount rate.
- k is estimated by finding the value most consistent with the participant's response pattern.
- k values range from 0.00016 to 0.25 for the MCQ-27.
- Higher k = steeper discounting = greater impulsivity.
- Alternative scoring: proportion of LDR choices (correlates r > .97 with log k).
- The MCQ can be scored for small, medium, and large reward magnitudes separately.

**Psychometric evidence:**
- Test-retest reliability: good (Kirby et al., 1999; PMC6701266 — UNVERIFIED, specific values).
- Convergent validity: correlates with other delay discounting measures and with real-world impulsive behaviour (e.g., substance use, gambling).
- Sensitive to reward magnitude (the "magnitude effect"): people discount large rewards less steeply than small rewards.
- The MCQ is one of the most widely used delay discounting measures in clinical and research settings.

**Licensing:** The MCQ is published in academic literature. **Status: Research use broadly permitted; the specific item set may be copyrighted. Build original items with the same SIR/LDR structure.**

**CortexForge module (3–8 min):** Use 12–15 original MCQ items (subset of the 27). Score: estimate k using the geometric midpoint method, or use proportion of LDR choices as a simpler metric. This is a direct behavioural measure of impulsivity.

---

### 4.2 Balloon Analogue Risk Task — BART (Lejuez et al., 2002)

**What it measures:** Risk-taking propensity — the willingness to take risks for potential rewards in a dynamic, escalating-risk environment.

**Task mechanics:**
- The participant pumps up a series of balloons on a computer screen.
- Each pump earns points (e.g., 5 cents per pump).
- The participant can stop pumping and "collect" the points at any time.
- Each balloon has a hidden explosion point (unknown to the participant). If the balloon explodes, the participant loses all points for that balloon.
- Three balloon colors with different explosion distributions:
  - **Blue:** average explosion at 64 pumps (wide distribution).
  - **Yellow:** average explosion at 16 pumps (medium distribution).
  - **Orange:** average explosion at 4 pumps (narrow distribution).
- Typically 30 balloons (10 of each color).

**Scoring formula:**
- **Adjusted average pumps:** The mean number of pumps for trials on which the balloon did NOT explode (i.e., the participant chose to stop). This is the primary BART score.
- Higher adjusted pumps = greater risk-taking.
- Alternative scores:
  - **Total money earned:** Sum of points collected.
  - **Number of explosions:** Count of balloons that exploded.
  - **Coefficient of variability (CV):** Standard deviation of pumps / mean pumps.
  - **Post-pump loss:** Average difference between pumps on explosion trials and the next successful trial (Schmitz et al., 2016) — measures affective decision-making.

**Psychometric evidence:**
- Test-retest reliability: moderate to good (Lejuez et al., 2002; PMC — UNVERIFIED, specific values).
- Convergent validity: correlates with self-reported risk-taking, sensation-seeking, and real-world risk behaviours (e.g., substance use, unsafe sex).
- Discriminates between clinical groups (e.g., substance users, adolescents with externalizing disorders) and controls.
- Sensitive to ambiguity level: higher ambiguity (blue balloons) produces more risk-taking than low ambiguity (orange balloons) (Smith et al., — UNVERIFIED, specific citation).
- The BART is one of the most widely used behavioural measures of risk-taking.

**Licensing:** The BART paradigm is published in academic literature. **Status: Research use broadly permitted; the specific software implementation may be copyrighted. Build original balloon-task analogues.**

**CortexForge module (3–8 min):** Implement 15–20 original balloon trials (5 of each color). Score: adjusted average pumps. This is a genuinely game-like, engaging task that directly measures risk-taking behaviour.

---

## 5. Social Network, Social Capital, and Loneliness

### 5.1 UCLA Loneliness Scale — Version 3 (Russell, 1996)

**What it measures:** Subjective feelings of loneliness and social isolation.

**Task mechanics:**
- 20 items rated on a 4-point scale (1 = never, 4 = often).
- 11 negative items (e.g., "I feel left out") and 9 positive items (reverse-scored, e.g., "I feel part of a group of friends").

**Scoring formula:**
- Reverse-score the 9 positive items.
- Sum all 20 items (range 20–80).
- Higher scores indicate greater loneliness.

**Psychometric evidence:**
- Internal consistency: α = .89–.94 (Russell, 1996).
- Test-retest reliability: r = .73 over 1 year (Russell, 1996).
- Convergent validity: correlates with other loneliness measures and with measures of interpersonal relationship adequacy.
- Construct validity: correlated with health and well-being measures.
- Factor structure: a global bipolar loneliness factor with two method factors (direction of item wording) fits well across samples (Russell, 1996).
- Limitation: focuses on social loneliness; virtually ignores family loneliness (Wong et al., — UNVERIFIED, specific citation).

**Licensing:** The UCLA Loneliness Scale is published in academic literature. **Status: Research use broadly permitted; verify copyright status.**

**CortexForge module (3–8 min):** Use the full 20-item scale (~3 minutes). Score as a single total. This is a key longitudinal measure for tracking social isolation over time.

---

### 5.2 Social Network Index — SNI (Cohen et al., 1997)

**What it measures:** The structure and diversity of a person's social network — how many different types of social relationships they maintain and how many people they have regular contact with.

**Task mechanics:**
- The participant indicates whether they have regular contact (at least once every 2 weeks) with people in 12 types of social relationships:
  1. Spouse, 2. Parent, 3. Child, 4. Child-in-law, 5. Close relative, 6. Close friend, 7. Religious group member, 8. Student, 9. Employee, 10. Neighbor, 11. Volunteer, 12. Group member.
- For each role, the participant also indicates the number of people with whom they have regular contact.

**Scoring formula:**
Three subscale scores:
1. **Network diversity (high-contact roles):** Number of the 12 roles in which the participant has regular contact with at least one person (range 0–12).
2. **Network size (people in social network):** Total number of people with whom the participant has regular contact across all 12 roles. Values over 6 are recoded to 7 to prevent inflation by large group memberships.
3. **Embedded networks:** Number of network domains (family, friends, church/temple, school, work, neighbors, volunteering, groups) in which the participant has at least 4 high-contact people (range 0–8). For family, the participant must have at least 3 high-contact family roles AND 4 high-contact people.

**Psychometric evidence:**
- The SNI predicts susceptibility to the common cold (Cohen et al., 1997) — a landmark finding linking social network diversity to physical health.
- Network diversity is associated with better mental health and well-being.
- The SNI is widely used in health psychology and social epidemiology.
- Test-retest reliability: moderate to good (Cohen et al., 1997).

**Licensing:** The SNI is published in academic literature and available on Cohen's website (psy.cmu.edu/~scohen/). **Status: Research use broadly permitted.**

**CortexForge module (3–8 min):** Use the full 12-role SNI (~3 minutes). Score all 3 subscales. This is a key longitudinal measure for tracking social capital and network structure over time.

---

## 6. Validated Social-Cognitive Serious Games

### 6.1 Deusto-e-motion 1.0 (Amayra et al., 2020)

**What it measures:** Emotional facial expression recognition and social skills (components of ToM) in children aged 8–12.

**Task mechanics:**
- A virtual serious game with three blocks:
  1. **Block 1:** 14 static emotional expressions + 10 dynamic emotional expressions. Participants identify the corresponding emotion.
  2. **Block 2:** 6 static scenarios where participants identify the emotions experienced by characters.
  3. **Block 3:** 24 social situations simulating a schoolyard. Participants identify their own emotions and the emotions of characters.
- The game automatically records response accuracy, reaction time, and response choice.
- Takes approximately 20 minutes to complete.
- Two versions: a virtual reality version (head-mounted display, motion tracker, joystick) and a serious game version (computer-based).

**Scoring formula:**
- Accuracy: proportion of correct emotion identifications.
- Reaction time: mean response time.
- The game produces separate scores for each block.

**Psychometric evidence:**
- Validated in a sample of 1,236 children aged 8–12 (Amayra et al., 2020).
- Concurrent validity: moderately significant correlation with the Feel facial recognition test (Amayra et al., 2020).
- Age and gender differences found in scores.
- Also validated for children with ADHD and rare diseases (Deusto team, LinkedIn — UNVERIFIED, specific citations).
- Clinical groups (PWS, ASD) showed longer reaction times than controls (Springer — UNVERIFIED, specific citation).

**Licensing:** Deusto-e-motion 1.0 was developed by the University of Deusto. **Status: Copyrighted — developed by a research team; licensing terms unclear. Build original analogues.**

**CortexForge module (3–8 min):** Adapt the three-block structure for adults: (1) 8–10 static/dynamic emotion identification items, (2) 4–6 social scenario emotion identification items, (3) 4–6 schoolyard-style social situations. Score accuracy and reaction time. This is a validated game-based assessment model.

---

### 6.2 SocialVille (Nahum et al., 2014, 2021)

**What it measures:** Social cognition training (not assessment per se, but the exercises are designed to measure and train social cognitive abilities including affect perception, social cue perception, and processing speed).

**Task mechanics:**
- An online, plasticity-based training program with 27 individualized social cognitive exercises.
- Each session consists of 6 exercise blocks, each taking about 10 minutes.
- Exercises target:
  - **Affect perception:** Identifying emotions from faces and voices.
  - **Social cue perception:** Interpreting social interactions and body language.
  - **Processing speed:** Speeded social cognitive tasks.
- The program adapts difficulty based on performance.
- Designed for individuals with schizophrenia but applicable to general populations.

**Scoring formula:**
- Performance on each exercise is scored for accuracy and reaction time.
- The program tracks improvement over sessions.
- Pre- and post-training assessments on standard measures (e.g., MSCEIT, TASIT, ER40, PROID, PFMT) evaluate transfer.

**Psychometric evidence:**
- Pilot study (Nahum et al., 2014): 17 schizophrenia patients completed 24 hours of training. Significant improvements on speeded SocialVille tasks; small to moderate improvements on working memory tasks. Post-training performance similar to initial performance of healthy controls.
- Randomized controlled trial (Nahum et al., 2021): 108 participants (55 intervention, 53 control). SocialVille training improved social cognitive composite scores and functional capacity (UPSA-2) compared to active control.
- High satisfaction, enjoyment, and ease of use ratings.
- No improvements on emotion recognition indices on the MSCEIT or quality of life scales in the pilot study.

**Licensing:** SocialVille was developed by Posit Science (now part of BrainHQ). **Status: Proprietary/commercial — not freely available. Build original analogues with the same exercise structure.**

**CortexForge module (3–8 min):** Implement 4–6 original SocialVille-style exercises: (1) emotion identification from faces, (2) emotion identification from voices, (3) social cue interpretation from body language, (4) speeded social cognitive tasks. Score accuracy and reaction time. This is a game-based assessment model with strong empirical support.

---

## 7. Social Profile Specification

### 7.1 Recommended Measurement Battery

A defensible description of "how this person behaves in a group" and "what role they occupy in a society" requires converging evidence from multiple levels: **ability** (can they mentalize?), **preference** (do they care about others?), **style** (how do they typically behave?), and **context** (what is their social world like?).

#### Tier 1: Core Battery (15–20 minutes)

| Domain | Instrument | What it measures | Scoring |
|--------|-----------|------------------|---------|
| ToM ability | Yoni-48 (or original analogue) | Cognitive & affective ToM, 1st & 2nd order | ACC (0–1), cognitive/affective subscales |
| ToM ability | MASC-style video vignettes (original) | Naturalistic mental-state attribution | Total correct (0–10), error patterns |
| Social preference | SVO Slider (6 items) | Stable resource-allocation preferences | SVO angle, 4-category classification |
| Social preference | Ultimatum Game (3–5 trials) | Fairness & negative reciprocity | Mean offer %, MAO |
| Social preference | Trust Game (3–5 trials) | Trust & trustworthiness | Mean transfer %, mean return % |
| Social preference | Dictator Game (3–5 trials) | Pure altruism | Mean giving % |
| Personality | IPIP-NEO-60 | Big Five domains & facets | 5 domain scores (12–60 each) |
| Dark Triad | MACH-IV (20 items) | Machiavellianism | Total score (20–100) |
| Empathy | EQ-short or original analogue | Self-reported empathy | Total score, cognitive/emotional subscales |
| Impulsivity | MCQ-12 (12 items) | Delay discounting | k value or % LDR choices |
| Risk-taking | BART (15–20 balloons) | Risk propensity | Adjusted average pumps |
| Loneliness | UCLA Loneliness Scale V3 | Subjective loneliness | Total score (20–80) |
| Social network | SNI (12 roles) | Network diversity, size, complexity | 3 subscale scores |

#### Tier 2: Extended Battery (additional 10–15 minutes)

| Domain | Instrument | What it measures |
|--------|-----------|-----------------|
| ToM ability | Strange Stories (5–8 original vignettes) | Advanced ToM (irony, lies, double bluff) |
| ToM ability | Animations Task (6 original animations) | Spontaneous mental-state attribution |
| Higher-order ToM | Marble Drop game (4–6 trials) | 2nd/3rd-order social reasoning |
| Social preference | Public Goods Game (3–5 trials) | Group cooperation |
| Social preference | Prisoner's Dilemma (5–10 trials) | Dyadic cooperation/defection |
| Personality | IPIP-HEXACO (60 items) | Honesty-Humility + Big Five |
| Decision style | GDMS (25 items) | 5 decision-making styles |
| Need for cognition | NCS-6 (6 items) | Intellectual curiosity |
| Social cognition game | Deusto-e-motion-style module | Emotion recognition in social context |

### 7.2 Social Profile Dimensions

From the Tier 1 battery, the following profile dimensions can be computed:

1. **Mentalizing Capacity** (from Yoni + MASC-style vignettes)
   - High / Medium / Low accuracy on cognitive and affective ToM
   - Error pattern: over-mentalizing vs. under-mentalizing vs. accurate

2. **Social Preference Orientation** (from SVO + economic games)
   - Prosocial / Individualistic / Competitive / Altruistic (SVO angle)
   - Fairness sensitivity (Ultimatum Game MAO)
   - Trust level (Trust Game transfer)
   - Altruism level (Dictator Game giving)
   - Reciprocity level (Trust Game return)

3. **Personality Configuration** (from IPIP-NEO + MACH-IV + EQ)
   - Big Five profile (OCEAN scores)
   - Dark Triad profile (Machiavellianism score)
   - Empathy level (EQ total and subscales)
   - Key combinations:
     - High Agreeableness + High EQ + Prosocial SVO = "Cooperator"
     - High MACH + Low EQ + Individualistic SVO = "Operator"
     - High Neuroticism + Low Extraversion + High Loneliness = "Isolate"
     - High Conscientiousness + High Agreeableness + Prosocial SVO = "Steward"

4. **Behavioural Tendencies** (from MCQ + BART)
   - Impulsivity level (delay discounting k)
   - Risk propensity (BART adjusted pumps)
   - Key combination: High k + High BART = "Impulsive risk-taker"

5. **Social Context** (from UCLA Loneliness + SNI)
   - Loneliness level (UCLA score)
   - Network diversity (SNI roles)
   - Network size (SNI people)
   - Network complexity (SNI embedded networks)
   - Key combination: High Loneliness + Low SNI diversity = "Socially isolated"

### 7.3 Social Role Classification

Based on the profile dimensions, the following social roles can be tentatively assigned:

| Role | Defining characteristics | Key measures |
|------|--------------------------|--------------|
| **Cooperator** | Prosocial SVO, high trust, high altruism, high agreeableness, high EQ | SVO, Trust Game, Dictator Game, IPIP-NEO, EQ |
| **Operator** | Individualistic/competitive SVO, high MACH, low EQ, moderate trust | SVO, MACH-IV, EQ, Trust Game |
| **Steward** | Prosocial SVO, high conscientiousness, high agreeableness, low impulsivity | SVO, IPIP-NEO, MCQ |
| **Free-rider** | Individualistic SVO, low trust, low altruism, low agreeableness | SVO, Trust Game, Dictator Game, IPIP-NEO |
| **Punisher** | High Ultimatum MAO, competitive SVO, low agreeableness | Ultimatum Game, SVO, IPIP-NEO |
| **Isolate** | High loneliness, low SNI diversity, low extraversion, high neuroticism | UCLA, SNI, IPIP-NEO |
| **Mentalizer** | High ToM accuracy, high EQ, high need for cognition | Yoni, MASC, EQ, NCS |
| **Cognitive Miser** | Low ToM accuracy, low need for cognition, high impulsivity | Yoni, NCS, MCQ |

### 7.4 What CANNOT Be Inferred

The following inferences are **not defensible** from the proposed battery:

1. **Clinical diagnosis.** No combination of these instruments can diagnose autism, psychopathy, depression, or any clinical condition. They measure continuous traits, not categorical disorders.

2. **Real-world social behaviour.** Economic games and laboratory tasks have limited ecological validity. Behaviour in incentivized laboratory settings does not perfectly predict behaviour in naturalistic social contexts (Levitt & List, 2007).

3. **Stable, invariant "type."** Social preferences and behaviours are context-dependent. The same person may behave prosocially in one context and selfishly in another. The profile describes tendencies, not fixed types.

4. **Moral character.** Measures of Machiavellianism, psychopathy, or honesty-humility do not measure "goodness" or "badness." They describe behavioural tendencies that may be adaptive in some contexts and maladaptive in others.

5. **Cognitive ability.** None of these instruments measure general intelligence, executive function, or cognitive capacity. ToM tasks are influenced by cognitive ability but do not measure it directly.

6. **Motivation or intent.** Behavioural measures reveal what people do, not why they do it. A low offer in the Ultimatum Game could reflect selfishness, strategic thinking, or misunderstanding of the task.

7. **Cultural universality.** Most of these instruments were developed in Western, educated, industrialized, rich, democratic (WEIRD) populations. Their validity across cultures is limited.

8. **Long-term stability.** While personality traits are relatively stable, social preferences and behaviours can change over time and across contexts. A single assessment provides a snapshot, not a trajectory.

9. **Causal relationships.** The profile describes associations between measures, not causal relationships. Low empathy may correlate with selfish behaviour, but the causal direction is unclear.

10. **Individual items.** No single item or task should be interpreted in isolation. The profile is only as valid as the convergence of multiple measures.

---

## 8. Licensing Summary

| Instrument | Licensing Status | CortexForge Implementation |
|-----------|-----------------|--------------------------|
| False Belief tasks | Research use permitted; build original stories | Build original vignettes |
| Strange Stories | Copyrighted (Happé) | Build original analogues |
| RMET | Copyrighted (Baron-Cohen); clinical purchase required | Build original eye-region stimuli |
| Yoni Task | Copyrighted (Shamay-Tsoory) | Build original cartoon-face stimuli |
| Animations Task | Copyrighted (Abell/Castelli) | Build original geometric animations |
| MASC | Copyrighted (Dziobek); clinical purchase | Build original video vignettes |
| TASIT | Copyrighted (Pearson); clinical purchase | Build original video vignettes |
| Marble Drop | Research use appears permitted | Build original game analogues |
| Economic games | Public domain (standard paradigms) | Implement directly |
| IPIP-NEO | **Public domain** (Goldberg, 1999) | Implement directly |
| HEXACO-PI-R | Free for research; licensed for commercial | Use IPIP-HEXACO (public domain) |
| MACH-IV | Public domain for research/educational use | Implement directly |
| NPI | Research use permitted; verify copyright | Implement with caution |
| SRP-III | Research use permitted; verify copyright | Implement with caution |
| EQ | Copyrighted (Baron-Cohen) | Build original empathy items |
| SVO Slider | Free for research use | Build original allocation tasks |
| NCS | Research use permitted; verify copyright | Implement with caution |
| GDMS | Research use permitted; verify copyright | Implement with caution |
| MCQ | Research use permitted; build original items | Build original SIR/LDR items |
| BART | Research use permitted; build original software | Build original balloon task |
| UCLA Loneliness | Research use permitted; verify copyright | Implement with caution |
| SNI | Research use permitted | Implement directly |
| Deusto-e-motion | Copyrighted (U. Deusto) | Build original game module |
| SocialVille | Proprietary (Posit Science/BrainHQ) | Build original game module |

---

## 9. References

### Theory of Mind
- Abell, F., Happé, F., & Frith, U. (2000). Do triangles play tricks? Attribution of mental states to animated shapes in normal and abnormal development. *Cognitive Development*, 15(1), 1–16.
- Apperly, I. A. (2012). What is "theory of mind"? Concepts, cognitive processes and individual differences. *Quarterly Journal of Experimental Psychology*, 65(5), 825–839.
- Baron-Cohen, S., Wheelwright, S., Hill, J., Raste, Y., & Plumb, I. (2001). The "Reading the Mind in the Eyes" test revised version: A study with normal adults, and adults with Asperger syndrome or high-functioning autism. *Journal of Child Psychology and Psychiatry*, 42(2), 241–251.
- Castelli, F., Happé, F., Frith, U., & Frith, C. (2000). Movement and mind: A functional imaging study of perception and interpretation of complex intentional movement patterns. *NeuroImage*, 12(3), 314–325.
- Castelli, F., Frith, C., Happé, F., & Frith, U. (2002). Autism, Asperger syndrome and brain mechanisms for the attribution of mental states to animated shapes. *Brain*, 125(8), 1839–1849.
- Devine, R. T., & Hughes, C. (2016). Measuring theory of mind in middle childhood: Reliability and validity of the Strange Stories task. *Developmental Psychology*, 52(11), 1766–1776.
- Dziobek, I., Fleck, S., Kalbe, E., Rogers, K., Hassenstab, J., Brand, M., ... Convit, A. (2006). Introducing MASC: A movie for the assessment of social cognition. *Journal of Autism and Developmental Disorders*, 36(5), 623–636.
- Happé, F. G. E. (1994). An advanced test of theory of mind: Understanding of story characters' thoughts and feelings by able autistic, mentally handicapped, and normal children and adults. *Journal of Autism and Developmental Disorders*, 24(2), 129–154.
- Happé, F. G. E., Brownell, H., & Winner, E. (1998). The acquired "theory of mind" impairment associated with right hemisphere damage. *Brain and Language*, 63(2), 289–304.
- Hassenstab, J., Dziobek, I., Rogers, K., Wolf, O. T., & Convit, A. (2007). Knowing what others know but not what they feel: A specific impairment in self-reported empathy in adult Asperger syndrome. *Journal of Autism and Developmental Disorders*, 37(5), 866–876.
- Hayward, E. O., & Homer, B. D. (2017). Reliability and validity of advanced theory of mind measures in middle childhood and adolescence. *British Journal of Developmental Psychology*, 35(3), 454–462.
- Isernia, S., et al. (2022a). Measuring cognitive and affective Theory of Mind with the Italian Yoni task: normative data and short versions. *Current Psychology*, 41, 10019–10033.
- Isernia, S., et al. (2022b). Reliability and minimal detectable change of the Yoni task for the theory of mind assessment. *Frontiers in Psychology*, 13, 1023419.
- McDonald, S., & Flanagan, S. (2004). Social perception deficits after traumatic brain injury: Interaction between emotion recognition, mentalizing ability, and social communication. *Neuropsychology*, 18(3), 572–579.
- McDonald, S., Flanagan, S., Martin, I., & Saunders, C. (2004). The ecological validity of TASIT: A test of social perception. *Neuropsychological Rehabilitation*, 14(3), 285–302.
- McDonald, S., et al. (2006). TASIT: A new clinical tool for assessing social perception after traumatic brain injury. *Journal of Head Trauma Rehabilitation*, 21(3), 219–238.
- Meijering, B., Van Maanen, L., Van Rijn, H., & Verbrugge, R. (2010). The facilitative effect of context on second-order social reasoning. In *Proceedings of the 32nd Annual Conference of the Cognitive Science Society*.
- Olderbak, S., Wilhelm, O., Olaru, G., Geiger, M., Brenneman, M. W., & Roberts, R. D. (2015). A psychometric analysis of the reading the mind in the eyes test: Toward a brief form for research and applied settings. *Journal of Personality Assessment*, 97(6), 610–624.
- Perner, J., & Wimmer, H. (1985). "John thinks that Mary thinks that…": Attribution of second-order beliefs by 5- to 10-year-old children. *Journal of Experimental Child Psychology*, 39(3), 437–471.
- Premack, D., & Woodruff, G. (1978). Does the chimpanzee have a theory of mind? *Behavioral and Brain Sciences*, 1(4), 515–526.
- Shamay-Tsoory, S. G., & Aharon-Peretz, J. (2007). Dissociable prefrontal networks for cognitive and affective theory of mind: A neuropsychological investigation. *Neuropsychologia*, 45(13), 3054–3067.
- Sullivan, K., Zaitchik, D., & Tager-Flusberg, H. (1994). Preschoolers can attribute second-order beliefs. *Developmental Psychology*, 30(3), 395–402.
- Van Maanen, L., & Verbrugge, R. (2010). A computational model of second-order social reasoning. In *Proceedings of the 32nd Annual Conference of the Cognitive Science Society*.
- Wellman, H. M., Cross, D., & Watson, J. (2001). Meta-analysis of theory-of-mind development: The truth about false belief. *Child Development*, 72(3), 655–684.
- Wimmer, H., & Perner, J. (1983). Beliefs about beliefs: Representation and constraining function of wrong beliefs in young children's understanding of deception. *Cognition*, 13(1), 103–128.

### Economic Games
- Axelrod, R. (1984). *The Evolution of Cooperation*. Basic Books.
- Berg, J., Dickhaut, J., & McCabe, K. (1995). Trust, reciprocity, and social history. *Games and Economic Behavior*, 10(1), 122–142.
- Engel, C. (2011). Dictator games: A meta study. *Experimental Economics*, 14(4), 583–610.
- Forsythe, R., Horowitz, J. L., Savin, N. E., & Sefton, M. (1994). Fairness in simple bargaining experiments. *Games and Economic Behavior*, 6(3), 347–369.
- Fischbacher, U., Gächter, S., & Fehr, E. (2001). Are people conditionally cooperative? Evidence from a public goods experiment. *Economics Letters*, 71(3), 397–404.
- Güth, W., Schmittberger, R., & Schwarze, B. (1982). An experimental analysis of ultimatum bargaining. *Journal of Economic Behavior & Organization*, 3(4), 367–388.
- Henrich, J., Boyd, R., Bowles, S., Camerer, C., Fehr, E., Gintis, H., & McElreath, R. (2001). In search of homo economicus: Behavioral experiments in 15 small-scale societies. *American Economic Review*, 91(2), 73–78.
- Isaac, R. M., Walker, J. M., & Thomas, S. H. (1985). Divergent evidence on free riding: An experimental examination of possible explanations. *Public Choice*, 43(2), 113–149.
- Johnson, N. D., & Mislin, A. A. (2011). Trust games: A meta-analysis. *Journal of Economic Psychology*, 32(5), 865–889.
- Kahneman, D., Knetsch, J. L., & Thaler, R. H. (1982). Fairness and the assumptions of economics. *Journal of Business*, 55(4), S285–S300.
- Ledyard, J. O. (1995). Public goods: A survey of experimental research. In J. H. Kagel & A. E. Roth (Eds.), *The Handbook of Experimental Economics*. Princeton University Press.
- Marwell, G., & Ames, R. E. (1979). Experiments on the provision of public goods. I. Resources, interest, group size, and the free-rider problem. *American Journal of Sociology*, 84(6), 1335–1360.
- Oosterbeek, H., Sloof, R., & Van de Kuilen, G. (2004). Cultural differences in ultimatum game experiments: Evidence from a meta-analysis. *Experimental Economics*, 7(2), 171–188.
- Rapoport, A., & Chammah, A. M. (1965). *Prisoner's Dilemma*. University of Michigan Press.
- Sally, D. (1995). Conversation and cooperation in social dilemmas: A meta-analysis of experiments from 1958 to 1992. *Rationality and Society*, 7(1), 58–92.
- Samuelson, P. A. (1954). The pure theory of public expenditure. *Review of Economics and Statistics*, 36(4), 387–389.

### Personality
- Ashton, M. C., & Lee, K. (2007). Empirical, theoretical, and practical advantages of the HEXACO model of personality structure. *Personality and Social Psychology Review*, 11(2), 150–166.
- Ashton, M. C., Lee, K., & Goldberg, L. R. (2007). The IPIP–HEXACO scales: An alternative, public-domain measure of the personality constructs in the HEXACO model. *Personality and Individual Differences*, 42(8), 1515–1526.
- Bogg, T., & Roberts, B. W. (2004). Conscientiousness and health-related behaviors: A meta-analysis of the leading behavioral contributors to mortality. *Psychological Bulletin*, 130(6), 887–919.
- Christie, R., & Geis, F. L. (1970). *Studies in Machiavellianism*. Academic Press.
- Digman, J. M. (1990). Personality structure: Emergence of the five-factor model. *Annual Review of Psychology*, 41, 417–440.
- Goldberg, L. R. (1990). An alternative "description of personality": The Big-Five factor structure. *Journal of Personality and Social Psychology*, 59(6), 1216–1229.
- Goldberg, L. R. (1999). A broad-bandwidth, public-domain, personality inventory measuring the lower-level facets of several five-factor models. In I. Mervielde, I. Deary, F. De Fruyt, & F. Ostendorf (Eds.), *Personality Psychology in Europe* (Vol. 7, pp. 7–28). Tilburg University Press.
- Jonason, P. K., & Webster, G. D. (2010). The Dirty Dozen: A concise measure of the Dark Triad. *Psychological Assessment*, 22(2), 420–432.
- Lee, K., & Ashton, M. C. (2004). Psychometric properties of the HEXACO Personality Inventory. *Multivariate Behavioral Research*, 39(2), 329–358.
- Lee, K., & Ashton, M. C. (2006). Further assessment of the HEXACO Personality Inventory: Two new facet scales and an observer report form. *Psychological Assessment*, 18(2), 182–191.
- Lee, K., Ashton, M. C., & de Vries, R. E. (2005). Explaining workplace delinquency and the role of Honesty-Humility: The HEXACO model of personality structure. *Journal of Applied Psychology*, 90(4), 731–740.
- McCrae, R. R., & John, O. P. (1992). An introduction to the five-factor model and its applications. *Journal of Personality*, 60(2), 175–215.
- Poropat, A. E. (2009). A meta-analysis of the five-factor model of personality and academic performance. *Psychological Bulletin*, 135(2), 322–338.
- Raskin, R., & Hall, C. S. (1979). A narcissistic personality inventory. *Psychological Reports*, 45(2), 590–590.

### Empathy
- Baron-Cohen, S., & Wheelwright, S. (2004). The Empathy Quotient: An investigation of adults with Asperger syndrome or high functioning autism, and normal sex differences. *Journal of Autism and Developmental Disorders*, 34(2), 163–175.
- Cassidy, K. R., et al. (2016). The Empathy Quotient: A cross-cultural comparison. *Journal of Autism and Developmental Disorders*, 46(10), 3457–3467.
- Lawrence, E. J., Shaw, P., Baker, D., Baron-Cohen, S., & David, A. S. (2004). Measuring empathy: Reliability and validity of the Empathy Quotient. *Psychological Medicine*, 34(5), 911–919.

### Social Value Orientation
- Liebrand, W. B. G. (1984). The effect of social motives, communication and group size on behaviour in an N-person multi-stage mixed-motive game. *European Journal of Social Psychology*, 14(3), 239–264.
- Murphy, R. O., Ackermann, K. A., & Handgraaf, M. J. J. (2011). Measuring Social Value Orientation. *Judgment and Decision Making*, 6(8), 771–781.
- Van Lange, P. A. M. (1999). The pursuit of joint outcomes and equality in outcomes: An integrative model of social value orientation. *Journal of Personality and Social Psychology*, 77(2), 337–349.
- Van Lange, P. A. M., Otten, W., De Bruin, E. M. N., & Joireman, J. A. (1997). Development of prosocial, individualistic, and competitive orientations: Theory and preliminary evidence. *Journal of Personality and Social Psychology*, 73(4), 733–746.

### Impulsivity and Risk-Taking
- Cacioppo, J. T., & Petty, R. E. (1982). The need for cognition. *Journal of Personality and Social Psychology*, 42(1), 116–131.
- Cacioppo, J. T., Petty, R. E., & Kao, C. F. (1984). The efficient assessment of need for cognition. *Journal of Personality Assessment*, 48(3), 306–307.
- Fleischhauer, M., Enge, S., Brocke, B., Ullrich, J., Strobel, A., & Strobel, A. (2010). Same or different? Clarifying the relationship of need for cognition to intelligence and personality. *Personality and Social Psychology Bulletin*, 36(1), 82–96.
- Kirby, K. N., Petry, N. M., & Bickel, W. K. (1999). Heroin addicts have higher discount rates for delayed rewards than non-drug-using controls. *Journal of Experimental Psychology: General*, 128(1), 78–87.
- Kirby, K. N., & Marakovic, N. N. (1996). Delay-discounting probabilistic rewards: Rates decrease as amounts increase. *Psychonomic Bulletin & Review*, 3(1), 100–104.
- Lejuez, C. W., Read, J. P., Kahler, C. W., Richards, J. B., Ramsey, S. E., Stuart, G. L., ... Brown, R. A. (2002). Evaluation of a behavioral measure of risk taking: The Balloon Analogue Risk Task (BART). *Journal of Experimental Psychology: Applied*, 8(2), 75–84.
- Mazur, J. E. (1987). An adjusting procedure for studying delayed reinforcement. In M. L. Commons, J. E. Mazur, J. A. Nevin, & H. Rachlin (Eds.), *Quantitative Analyses of Behavior* (Vol. 5, pp. 55–73). Erlbaum.
- Schmitz, F., et al. (2016). Post-pump loss in the Balloon Analogue Risk Task. *Assessment*, 23(6), 722–731.

### Social Network and Loneliness
- Cohen, S., Doyle, W. J., Skoner, D. P., Rabin, B. S., & Gwaltney, J. M. (1997). Social ties and susceptibility to the common cold. *JAMA*, 277(24), 1940–1944.
- Russell, D. W. (1996). UCLA Loneliness Scale (Version 3): Reliability, validity, and factor structure. *Journal of Personality Assessment*, 66(1), 20–40.

### Serious Games
- Amayra, I., et al. (2020). Using a virtual serious game (Deusto-e-motion 1.0) to assess the theory of mind in primary school children: Observational descriptive study. *JMIR Serious Games*, 8(2), e12971.
- Nahum, M., et al. (2014). A novel, online social cognitive training program for young adults with schizophrenia: A pilot study. *Schizophrenia Research*, 156(1), 137–142.
- Nahum, M., et al. (2021). Online Social Cognition Training in Schizophrenia: A Double-Blind, Randomized, Controlled Multi-Site Clinical Trial. *Schizophrenia Bulletin*, 47(1), 176–185.

### Decision-Making Styles
- Gambetti, E., Fabbri, M., & Bensi, L. (2008). The General Decision-Making Style Inventory: A validation study on an Italian sample. *Journal of Psychoeducational Assessment*, 26(3), 239–252.
- Loo, R. (2000). A psychometric evaluation of the General Decision-Making Style Inventory. *Personality and Individual Differences*, 29(5), 895–905.
- Scott, S. G., & Bruce, R. A. (1995). Decision-making style: The development and assessment of a new measure. *Educational and Psychological Measurement*, 55(5), 818–831.
- Spicer, D. P., & Sadler-Smith, E. (2005). An examination of the General Decision Making Style questionnaire in two UK samples. *Journal of Managerial Psychology*, 20(2), 137–149.
- Thunholm, P. (2004). Decision-making style: Habit, style or both? *Personality and Individual Differences*, 36(4), 931–944.

---

*End of dossier.*
