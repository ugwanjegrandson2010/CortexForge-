# 05 — Question Generation and Adaptive Learning Science

**CortexForge Research Dossier**

This dossier covers the science and engineering of turning a learner's own source material into optimally-scheduled questions in any style. It is written for the implementer of the item generator and the scheduler. Every claim is cited; unverifiable citations are marked **[UNVERIFIED]**.

---

## Table of Contents

1. [Taxonomy of Question Types](#1-taxonomy-of-question-types)
2. [Automatic Question Generation from Text](#2-automatic-question-generation-from-text)
3. [Retrieval Practice](#3-retrieval-practice)
4. [Spaced Repetition Algorithms](#4-spaced-repetition-algorithms)
5. [Desirable Difficulties](#5-desirable-difficulties)
6. [Feedback and Grading](#6-feedback-and-grading)
7. [Metacognition and Calibration](#7-metacognition-and-calibration)
8. [Knowledge Tracing](#8-knowledge-tracing)
9. [The Desirable-Difficulty vs. Pampering Boundary](#9-the-desirable-difficulty-vs-pampering-boundary)
10. [Question-Style Specification Table](#a-question-style-specification-table)
11. [FSRS Update Equations](#b-fsrs-update-equations)
12. [BKT Update Equations](#c-bkt-update-equations)
13. [Difficulty-Calibration Rule Set](#d-difficulty-calibration-rule-set)

---

## 1. Taxonomy of Question Types

### 1.1 Bloom's Revised Taxonomy (Anderson & Krathwohl, 2001)

Anderson & Krathwohl (2001) revised Bloom's (1956) taxonomy along two dimensions: **Knowledge Dimension** (Factual, Conceptual, Procedural, Metacognitive) and **Cognitive Process Dimension** (Remember, Understand, Apply, Analyze, Evaluate, Create). The cognitive process dimension is the relevant axis for question generation:

| Level | Process | Definition | Question-Generation Trigger |
|-------|---------|------------|------------------------------|
| 1 | **Remember** | Retrieve relevant knowledge from long-term memory | Fact recall, definition, list |
| 2 | **Understand** | Construct meaning from instructional messages | Paraphrase, summarize, explain, classify |
| 3 | **Apply** | Carry out a procedure in a given situation | Execute algorithm, solve novel problem |
| 4 | **Analyze** | Break material into parts and determine relationships | Differentiate, organize, attribute, compare |
| 5 | **Evaluate** | Make judgments based on criteria and standards | Critique, judge, rank, steelman |
| 6 | **Create** | Put elements together to form a coherent whole | Generate, plan, produce, design |

**Citation:** Anderson, L. W., & Krathwohl, D. R. (Eds.). (2001). *A Taxonomy for Learning, Teaching, and Assessing: A Revision of Bloom's Taxonomy of Educational Objectives.* Longman.

### 1.2 Webb's Depth of Knowledge (DoK)

Webb's DoK (1997, 2002) classifies tasks by cognitive complexity, not content:

| DoK Level | Name | Description | Question-Generation Trigger |
|-----------|------|-------------|------------------------------|
| 1 | **Recall & Reproduction** | Recall facts, terms, concepts; perform simple procedures | Fact recall, definition, single-step computation |
| 2 | **Skills & Concepts** | Use conceptual knowledge; engage in mental processing beyond habitual response | Classify, compare, organize, estimate |
| 3 | **Strategic Thinking & Reasoning** | Reason, develop a plan, use evidence; explain thinking | Open-ended problem, justification, inference |
| 4 | **Extended Thinking** | Complex reasoning, planning, developing over time; multiple sources | Research project, multi-step investigation, synthesis |

**Citation:** Webb, N. L. (1997). *Criteria for Alignment of Expectations and Assessments in Mathematics and Science Education.* Council of Chief State School Officers. **[UNVERIFIED — exact publication details]**

### 1.3 The "Any Kind of Style" Space

CortexForge must generate questions in any style. The following style space is defined by the intersection of **cognitive process** (Bloom/DoK) and **response format**:

| Style | Bloom Level | DoK Level | Response Format | Generation Algorithm |
|-------|-------------|-----------|-----------------|---------------------|
| Multiple choice | 1–3 | 1–2 | Select 1 of N | Distractor generation + answer key |
| Multiple answer | 2–4 | 2–3 | Select all applicable | Distractor generation + multi-key |
| True/False with justification | 2–3 | 2 | Binary + free-text rationale | Negation or perturbation + justification prompt |
| Cloze/deletion | 1–2 | 1–2 | Fill-in-blank | POS/entity masking |
| Short answer | 1–3 | 1–3 | Free-text, 1–5 words | Wh-transformation, answer extraction |
| Essay | 4–6 | 3–4 | Free-text, paragraph+ | Prompt construction from learning objectives |
| Socratic dialogue | 3–5 | 2–3 | Multi-turn dialogue | Recursive question generation from learner response |
| Worked-example completion | 3 | 2 | Fill-in steps of worked example | Step deletion from worked solution |
| Error-spotting | 4 | 3 | Identify and correct error | Error injection into correct solution |
| Counterexample generation | 4–5 | 3 | Produce counterexample | Negation of universal claim, boundary-case search |
| Proof/derivation | 3–5 | 3–4 | Formal derivation | Theorem statement → proof skeleton |
| Analogy | 2–3 | 2 | Map A:B :: C:? | Relational mapping from source |
| Transfer/novel-context | 3 | 2–3 | Apply known concept to new scenario | Context substitution, parameter variation |
| Feynman explanation | 2 | 2 | Explain in plain language | "Explain like I'm 12" prompt |
| Debate/steelman | 5 | 3 | Argue for/against position | Position assignment + argument generation |
| Prediction-then-verify | 3–4 | 2–3 | Predict outcome, then check | Pre-experiment prediction prompt |
| Interleaved mixed set | 1–6 | 1–4 | Mixed formats | Scheduler-driven format mixing |

---

## 2. Automatic Question Generation from Text

### 2.1 Research Literature

Automatic Question Generation (AQG) is a mature NLP subfield. The key approaches:

#### 2.1.1 Sentence-Level QG (Classic NLP)

Heilman & Smith (2009) describe an overgenerate-and-rank framework: transform declarative sentences into questions via syntactic rules, then rank by a logistic regression model. Their system achieved 43.3% precision at rank-10 and generated ~6.8 acceptable questions per 250 words of source text.

**Algorithm (Heilman & Smith, 2009):**
1. Parse sentence with dependency parser
2. Identify answer phrases (NP, VP, PP)
3. Apply wh-movement transformation rules
4. Overgenerate candidate questions
5. Rank with learned model (features: question length, answer frequency, transformation type)
6. Output top-K

**Citation:** Heilman, M., & Smith, N. A. (2009). Question Generation via Overgenerating Transformations and Ranking. *CMU-LTI-09-013.*

#### 2.1.2 Answer-Aware QG (Neural)

Modern QG uses seq2seq models (T5, BART, GPT) conditioned on the answer span:

- **T5-based QG:** Fine-tune T5 on SQuAD or similar QA datasets. Input: `[answer] <hl> answer </hl> [context]`. Output: question.
- **BART-based QG:** Similar, with denoising pretraining benefit.
- **Answer-aware vs. answer-agnostic:** Answer-aware QG produces more focused questions; answer-agnostic QG produces more diverse but lower-quality questions.

**Citation:** Du, X., Shao, J., & Cardie, C. (2017). Learning to Ask: Neural Question Generation for Reading Comprehension. *ACL 2017.* **[UNVERIFIED]**

#### 2.1.3 Distractor Generation

Distractor generation is the critical component for MCQ generation. Key approaches:

1. **WordNet-based:** Select hyponyms/siblings of the answer key from WordNet synsets. Risk: contextually inappropriate distractors (e.g., "wolf" as distractor for "dog" in a domestic-animal context).
2. **Embedding-based:** Select words with high cosine similarity to the answer key in embedding space but not synonyms.
3. **Contextual embedding-based:** Use BERT/RoBERTa to score distractor plausibility in context.
4. **Transformer-based (CQG):** Sun & Wang (2024) generate multigram distractors using text-to-text transformers + WordNet, achieving SOTA on cloze question generation.

**Distractor quality metrics:**
- **Reliability:** Filling the blank with the distractor yields a grammatically correct but logically wrong sentence.
- **Plausibility:** The distractor is not manifestly incorrect; it presents sufficient confusion.
- **Discrimination:** The distractor attracts students who don't know the answer (measured by distractor efficiency in IRT).

**Citation:** Awalurahman, H. W., & Budi, I. D. (2024). Automatic distractor generation in multiple-choice questions: a systematic literature review. *PeerJ Computer Science*, 10, e2611.

### 2.2 Classic NLP Techniques (No Large Model Required)

These techniques work with standard NLP libraries (spaCy, NLTK, Stanford CoreNLP):

#### 2.2.1 Cloze Deletion by POS/Entity

**Algorithm:**
1. Tokenize and POS-tag the source text
2. Select candidate answer spans:
   - Named entities (PERSON, ORG, GPE, DATE, etc.)
   - Noun phrases (NP chunks)
   - Numerical expressions
   - Key terms (TF-IDF top-k)
3. For each candidate, create a cloze by replacing the span with a blank
4. Generate distractors:
   - Same POS tag, different entity
   - Same entity type, different entity
   - Hypernym/hyponym from WordNet
5. Rank cloze candidates by:
   - Sentence position (earlier = more context)
   - Answer span frequency in document
   - Syntactic complexity of the sentence

**Implementation sketch:**
```python
import spacy
from spacy.tokens import Span

nlp = spacy.load("en_core_web_sm")

def generate_cloze(sentence, answer_span):
    doc = nlp(sentence)
    # Find the token span matching answer_span
    start = None
    end = None
    for i, token in enumerate(doc):
        if token.idx == answer_span.start_char:
            start = i
        if token.idx + len(token.text) == answer_span.end_char:
            end = i + 1
    if start is None or end is None:
        return None
    # Create cloze
    cloze = sentence[:doc[start].idx] + "_____" + sentence[doc[end-1].idx + len(doc[end-1].text):]
    # Generate distractors (same entity type)
    distractors = get_distractors_same_type(doc[start:end].label_, answer_span.text)
    return {"cloze": cloze, "answer": answer_span.text, "distractors": distractors}
```

#### 2.2.2 Wh-Question Transformation

**Algorithm:**
1. Parse sentence with dependency parser
2. Identify the answer phrase and its grammatical role:
   - Subject → "Who" or "What"
   - Object → "What" or "Whom"
   - Temporal PP → "When"
   - Locative PP → "Where"
   - Manner/Reason PP → "How" or "Why"
3. Apply wh-movement:
   - Replace answer phrase with wh-word
   - Move wh-word to front
   - Invert subject-auxiliary if needed
4. Filter ungrammatical outputs with a language model or rule-based checker

**Example:**
- Sentence: "Photosynthesis converts light energy into chemical energy."
- Answer: "Photosynthesis" (subject) → "What converts light energy into chemical energy?"
- Answer: "chemical energy" (object) → "What does photosynthesis convert light energy into?"

#### 2.2.3 Definition Extraction

**Algorithm:**
1. Pattern-based extraction:
   - "X is a Y" → "What is X?" / "Define X."
   - "X refers to Y" → "What does X refer to?"
   - "X, which is Y," → "What is X?"
2. Hearst patterns (1992) for hyponymy extraction:
   - "X and other Y" → X is a hyponym of Y
   - "Y such as X" → X is a hyponym of Y
3. Generate definition questions: "What is [term]?" with the extracted definition as answer.

**Citation:** Hearst, M. A. (1992). Automatic acquisition of hyponyms from large text corpora. *COLING 1992.*

#### 2.2.4 Causal-Chain Extraction

**Algorithm:**
1. Identify causal connectives: "because", "therefore", "as a result", "leads to", "causes", "due to", "consequently"
2. Extract cause-effect pairs:
   - "A because B" → Cause: B, Effect: A
   - "A, therefore B" → Cause: A, Effect: B
3. Generate questions:
   - Cause question: "Why [effect]?" → Answer: cause
   - Effect question: "What happens if [cause]?" → Answer: effect
4. For multi-hop causal chains: "A → B → C", generate "What is the ultimate cause of C?"

**Citation:** Stasaski, K., Rathod, M., Tu, T., Xiao, Y., & Hearst, M. A. (2021). Automatically Generating Cause-and-Effect Questions from Passages. *BEA Workshop 2021.*

---

## 3. Retrieval Practice

### 3.1 The Testing Effect

The testing effect (retrieval practice effect) is one of the most robust findings in cognitive psychology: taking a test on material improves long-term retention more than spending equivalent time restudying the material.

**Key finding:** Roediger & Karpicke (2006) showed that students who took a recall test after reading a passage retained significantly more after one week than students who reread the passage multiple times — even when the test was given without feedback.

**Citation:** Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science*, 17(3), 249–255.

### 3.2 Meta-Analytic Evidence

- **Rowland (2014):** Meta-analysis of 272 experiments; overall effect size g = 0.50 (medium). Practice testing outperformed restudying across a wide range of conditions.
- **Adesope, Trevisan, & Sundararajan (2017):** Meta-analysis of 217 experiments; practice tests produced a mean effect size of g = 0.61 compared to restudying. Effect was moderated by test format (short-answer > multiple-choice), feedback presence, and retention interval.

**Citations:**
- Rowland, C. A. (2014). The effect of testing versus restudy on retention: A meta-analytic review of the testing effect. *Psychological Bulletin*, 140(6), 1432–1463. **[UNVERIFIED — exact volume/pages]**
- Adesope, O. O., Trevisan, D. A., & Sundararajan, N. (2017). Rethinking the use of tests: A meta-analysis of practice testing. *Review of Educational Research*, 87(3), 659–701.

### 3.3 Boundary Conditions — When Testing Does NOT Help

The testing effect is not universal. Boundary conditions include:

1. **Very short retention intervals:** If the final test is immediate, restudying can outperform testing (the "reverse testing effect").
2. **Very difficult material with no prior knowledge:** If learners have zero prior knowledge, testing without feedback can produce errors that are not corrected, leading to negative learning.
3. **Complex, unstructured material:** Testing helps most for well-structured, meaningful material. For arbitrary lists, the effect is smaller.
4. **When feedback is absent and errors persist:** Without feedback, incorrect responses during testing can become learned (the "negative testing effect").
5. **Very long retention intervals with no spacing:** A single test provides limited benefit; the effect is maximized with spaced, repeated testing.

**Citation:** Roediger, H. L., & Karpicke, J. D. (2006). The power of testing memory: Basic research and implications for educational practice. *Perspectives on Psychological Science*, 1(3), 181–210.

---

## 4. Spaced Repetition Algorithms

### 4.1 SM-2 (SuperMemo 2)

The classic algorithm, still used by Anki (in modified form):

**State variables per item:**
- `n`: repetition number (consecutive successful recalls)
- `EF`: easiness factor (initial 2.5, minimum 1.3)
- `I`: inter-repetition interval (days)

**Algorithm:**
```
if q >= 3 (correct):
    if n == 0: I = 1
    elif n == 1: I = 6
    else: I = round(I * EF)
    n = n + 1
else (incorrect):
    n = 0
    I = 1

EF = EF + (0.1 - (5 - q) * (0.08 + (5 - q) * 0.02))
if EF < 1.3: EF = 1.3
```

**Grade scale (q):** 0=total blackout, 1=incorrect but familiar, 2=incorrect but seemed easy, 3=correct with serious difficulty, 4=correct after hesitation, 5=perfect.

**Citation:** Wozniak, P. (1990). *Algorithm SM-2.* SuperMemo.

### 4.2 SM-18

SM-18 (2016) introduced the two-component model of memory (stability + retrievability) and is the basis for FSRS. It uses:
- **Memory Stability (S):** the interval at which retrievability drops to 90%
- **Retrievability (R):** probability of recall at time t
- **Difficulty (D):** derived from the grade-response function

The exact SM-18 formulas are proprietary and not fully published. The open-source FSRS algorithm is the publicly available successor.

### 4.3 FSRS (Free Spaced Repetition Scheduler)

FSRS is the state-of-the-art open-source spaced repetition algorithm. It uses the DSR (Difficulty, Stability, Retrievability) model.

#### 4.3.1 Core Formulas (FSRS-5)

**Retrievability (forgetting curve):**
```
R(t, S) = (1 + FACTOR * t / S) ^ DECAY
```
where `FACTOR = 0.9^(-1/DECAY) - 1` ensures `R(S, S) = 0.9`.

For FSRS-4.5: `DECAY = -0.5`, `FACTOR = 19/81`
For FSRS-4: `DECAY = -1`, `FACTOR = 1/9`

**Next interval for target retention r:**
```
I(r, S) = S / FACTOR * (r^(1/DECAY) - 1)
```

**Initial stability after first rating:**
```
S_0(G) = w[G-1]
```
where G ∈ {1=Again, 2=Hard, 3=Good, 4=Easy} and w[0..3] are parameters.

**Initial difficulty after first rating:**
```
D_0(G) = w_4 - e^(w_5 * (G - 1)) + 1
```

**Difficulty update (with mean reversion):**
```
ΔD(G) = -w_6 * (G - 3)
D' = D + ΔD * (10 - D) / 9
D'' = w_7 * D_0(4) + (1 - w_7) * D'
```

**Stability after successful review (recall):**
```
S'_r(D, S, R, G) = S * (e^w_8 * (11 - D) * S^(-w_9) * (e^(w_10 * (1-R)) - 1) * w_15[if G=2] * w_16[if G=4] + 1)
```

**Stability after forgetting (lapse):**
```
S'_f(D, S, R) = w_11 * D^(-w_12) * ((S+1)^w_13 - 1) * e^(w_14 * (1-R))
```

**Same-day review stability:**
```
S'(S, G) = S * e^(w_17 * (G - 3 + w_18)) * S^(-w_19)
```

**Default FSRS-5 parameters (19 parameters):**
```
[0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621]
```

**Citation:** Ye, J., et al. (2023). *FSRS: A Free Spaced Repetition Scheduler.* GitHub: open-spaced-repetition/fsrs4anki. Also: MaiMemo (2022). *A Stochastic Shortest Path Algorithm for Optimizing Spaced Repetition Scheduling.* ACM KDD.

### 4.4 Anki's Implementation

Anki uses a modified SM-2 with:
- Initial ease factor: 2500 (equivalent to EF=2.5 in SM-2's 100x scale)
- Ease bonus: 1.3 for "Easy"
- Interval modifier: configurable (default 100%)
- Maximum interval: 36500 days
- Lapse penalty: interval reset to 1 day, ease factor decreased by 20%

**Citation:** Anki FAQ. https://faqs.ankiweb.net/what-spaced-repetition-algorithm

### 4.5 Leitner Boxes

Simple box-based system:
- Box 1: review daily
- Box 2: review every 3 days
- Box 3: review every 5 days
- Box 4: review every 7 days
- Box 5: review every 14 days

**Algorithm:**
```
if correct: move to next box
if incorrect: move to box 1 (or back one box in some variants)
```

**Citation:** Leitner, S. (1972). *So lernt man lernen.* Verlag Herder.

### 4.6 Half-Life Regression (Duolingo HLR)

Duolingo's HLR model predicts the half-life of a word in memory:

**Forgetting curve:**
```
p = 2^(-Δ/h)
```
where Δ = lag time since last practice, h = half-life.

**Half-life prediction:**
```
h = 2^(Θ · x)
```
where Θ = learned regression weights, x = feature vector (word identity, practice history, etc.).

**Loss function:**
```
ℓ(⟨p, Δ, x⟩; Θ) = (p - 2^(-Δ/2^(Θ·x)))² + α(-Δ/log₂(p) - 2^(Θ·x))² + λ||Θ||²₂
```

**Citation:** Settles, B., & Meeder, B. (2016). A Trainable Spaced Repetition Model for Language Learning. *ACL 2016.*

---

## 5. Desirable Difficulties

### 5.1 Bjork & Bjork's Framework

Bjork & Bjork (2011) identified five "desirable difficulties" — conditions that make learning harder in the short term but improve long-term retention and transfer:

1. **Spacing:** Distributing practice over time rather than massing it.
2. **Interleaving:** Mixing different types of problems or topics within a session.
3. **Generation:** Attempting to solve a problem before being shown the solution.
4. **Varied practice:** Practicing under varied conditions rather than constant conditions.
5. **Testing:** Using tests as learning events rather than just assessments.

**Citation:** Bjork, E. L., & Bjork, R. A. (2011). Making things hard on yourself, but in a good way: Creating desirable difficulties to enhance learning. *Psychology and the Real World*, 2, 56–64.

### 5.2 Evidence for Each

#### 5.2.1 Spacing

- **Cepeda et al. (2006):** Meta-analysis of 254 studies; spacing effect is robust across materials and ages. Optimal gap is approximately 10–20% of the retention interval.
- **Cepeda et al. (2008):** The "temporal ridgeline" — for a retention interval of 1 year, the optimal gap is ~1 month; for 1 week, ~1 day.

**Citations:**
- Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin*, 132(3), 354–380.
- Cepeda, N. J., Vul, E., Rohrer, D., Wixted, J. T., & Pashler, H. (2008). Spacing effects in learning: A temporal ridgeline of optimal retention. *Psychological Science*, 19(11), 1095–1102.

#### 5.2.2 Interleaving

- **Rohrer & Taylor (2007):** Interleaved practice tripled test scores (63% vs. 20%) for geometry volume problems, Cohen's d = 1.34. However, interleaving impaired practice accuracy (60% vs. 89%, d = 1.06).
- **Rohrer & Taylor (2010):** Isolated the interleaving effect from spacing by equating spacing across conditions; interleaving still produced significant benefits.

**Citations:**
- Rohrer, D., & Taylor, K. (2007). The shuffling of mathematics problems improves learning. *Instructional Science*, 35(6), 481–498.
- Rohrer, D., & Taylor, K. (2010). The effects of interleaved practice. *Applied Cognitive Psychology*, 24(6), 837–848.

#### 5.2.3 Generation

- **Kapur (2016):** Productive failure — students who attempt to solve problems before instruction outperform those who receive direct instruction first, on conceptual understanding and transfer tests.
- **Schwartz & Bransford (1998):** Generation of answers before reading a text improves learning from the text.

**Citation:** Kapur, M. (2016). Examining productive failure, productive success, unproductive failure, and unproductive success in learning. *Educational Psychologist*, 51(2), 289–299. **[UNVERIFIED]**

#### 5.2.4 Varied Practice

- **Rohrer & Taylor (2007):** Varied practice (different problem types) improves transfer to novel problems.
- **Kerr & Booth (1978):** Varied practice of a motor skill improves retention and transfer.

---

## 6. Feedback and Grading

### 6.1 Immediate vs. Delayed Feedback

The evidence is nuanced:

- **Immediate feedback** is better for procedural skills and when the learner is a novice (prevents error consolidation).
- **Delayed feedback** can be better for conceptual learning and transfer (allows the learner to process the error without the "answer" cue present).
- **Shute (2008):** Feedback should be "just-in-time" — not necessarily immediate, but timed to when the learner is ready to process it.

**Citation:** Shute, V. J. (2008). Focus on formative feedback. *Review of Educational Research*, 78(1), 153–189.

### 6.2 Knowledge-of-Results vs. Knowledge-of-Correct-Response

- **Knowledge-of-results (KR):** Telling the learner whether they were right or wrong, without providing the correct answer.
- **Knowledge-of-correct-response (KCR):** Providing the correct answer.

**Evidence:** KCR is generally more effective than KR alone, especially for difficult items. However, KR + generation (asking the learner to produce the correct answer before revealing it) is more effective than KCR alone.

**Citation:** Butler, A. C., & Woodward, N. R. (2018). Toward consilience in the use of task-level feedback to promote learning. *Educational Psychology Review*, 30, 1–24. **[UNVERIFIED]**

### 6.3 The "No Pampering" Question

#### 6.3.1 Praise

- **Mueller & Dweck (1998):** Praise for intelligence ("You're smart") leads to fixed-mindset responses (avoidance of challenge, helplessness after failure). Praise for effort ("You worked hard") promotes growth-mindset responses.
- **Haimovitz & Dweck (2017):** Praise that focuses on the process (strategies, effort) is beneficial; praise that focuses on the person (intelligence, talent) is harmful.

**Citation:** Mueller, C. M., & Dweck, C. S. (1998). Praise for intelligence can undermine children's motivation and performance. *Journal of Personality and Social Psychology*, 75(1), 33–52.

#### 6.3.2 Growth-Mindset Interventions — The Failed Replications

- **Sisk et al. (2018):** Two meta-analyses found that the correlation between growth mindset and academic achievement is weak (r ≈ 0.10), and that mindset interventions have small effects on achievement (d ≈ 0.08). The effects are not zero but are much smaller than claimed by Dweck and popularizers.

**Citation:** Sisk, V. F., Burgoyne, A. P., Sun, J., Butler, J. L., & Macnamara, B. N. (2018). To what extent and under which circumstances are growth mind-sets important to academic achievement? Two meta-analyses. *Psychological Science*, 29(4), 549–571.

#### 6.3.3 Overlearning

- **Rohrer & Taylor (2007):** Overlearning (continuing practice after mastery) provides diminishing returns but does not harm. However, it consumes time that could be spent on spacing or interleaving.
- **Driskell, Willis, & Copper (1992):** Meta-analysis found overlearning improves retention but the effect is small and decays over time.

**Citation:** Driskell, J. E., Willis, R. P., & Copper, C. (1992). Effect of overlearning on retention. *Journal of Applied Psychology*, 77(5), 615–622. **[UNVERIFIED]**

#### 6.3.4 Risk of Demotivation from Harsh Feedback

- **Kluger & DeNisi (1996):** Feedback interventions improve performance in ~50% of cases but harm performance in ~40%. Feedback that threatens self-esteem or is perceived as controlling can reduce motivation.
- **The "no pampering" principle:** Feedback should be honest and specific, not harsh. The goal is to provide accurate information about performance, not to punish or coddle.

**Citation:** Kluger, A. N., & DeNisi, A. (1996). The effects of feedback interventions on performance: A historical review, a meta-analysis, and a preliminary feedback intervention theory. *Psychological Bulletin*, 119(2), 254–284.

---

## 7. Metacognition and Calibration

### 7.1 Dunning-Kruger Effect

The Dunning-Kruger effect (Kruger & Dunning, 1999) describes a cognitive bias where:
- Low-ability individuals overestimate their competence (they lack the metacognitive skill to recognize their incompetence).
- High-ability individuals slightly underestimate their competence (they assume tasks that are easy for them are also easy for others).

**Implication for CortexForge:** The system must not rely solely on learner self-assessment. It should use objective performance data to calibrate difficulty.

**Citation:** Kruger, J., & Dunning, D. (1999). Unskilled and unaware of it: How difficulties in recognizing one's own incompetence lead to inflated self-assessments. *Journal of Personality and Social Psychology*, 77(6), 1121–1134.

### 7.2 Judgments of Learning (JOL) and Miscalibration

- **JOLs** are learners' predictions about how well they will remember material in the future.
- **Miscalibration:** Learners are systematically overconfident, especially for material they have rereaded multiple times.
- **The "illusion of fluency":** Rereading creates a sense of fluency (ease of processing) that is mistaken for understanding. This is the primary mechanism behind the failure of rereading as a study strategy.

**Citation:** Bjork, R. A., Dunlosky, J., & Kornell, N. (2013). Self-regulated learning: Beliefs, techniques, and illusions. *Annual Review of Psychology*, 64, 417–444.

### 7.3 Measuring and Correcting Calibration

**Calibration measures:**
- **Calibration bias:** Mean(JOL) − Mean(actual performance). Positive = overconfident.
- **Calibration accuracy:** Correlation between JOLs and actual performance (resolution).
- **Overconfidence index:** Proportion of items where JOL > actual performance.

**Correction strategies:**
1. **Provide objective feedback:** Show learners their actual performance vs. their predictions.
2. **Use delayed JOLs:** Asking learners to predict performance after a delay (rather than immediately) improves calibration.
3. **Use tests as calibration tools:** The act of testing provides objective feedback that corrects the illusion of fluency.

**Implementation:**
```python
def compute_calibration(jol_list, performance_list):
    """
    jol_list: list of learner's predicted probability of recall (0-1)
    performance_list: list of actual recall outcomes (0 or 1)
    """
    import numpy as np
    jol = np.array(jol_list)
    perf = np.array(performance_list)
    bias = np.mean(jol - perf)  # positive = overconfident
    resolution = np.corrcoef(jol, perf)[0, 1]  # higher = better discrimination
    overconfidence = np.mean(jol > perf)
    return {"bias": bias, "resolution": resolution, "overconfidence": overconfidence}
```

---

## 8. Knowledge Tracing

### 8.1 Bayesian Knowledge Tracing (BKT)

BKT (Corbett & Anderson, 1995) models each skill as a binary latent variable (known/unknown) updated by observed performance.

**Parameters:**
- `P(L_0)`: prior probability of knowing the skill
- `P(T)`: probability of learning the skill after an opportunity to apply it (transition)
- `P(S)`: probability of slipping (making a mistake when the skill is known)
- `P(G)`: probability of guessing correctly when the skill is unknown

**Update equations:**

```
# Prior (before observation)
P(L_t) = P(L_{t-1} | obs) + (1 - P(L_{t-1} | obs)) * P(T)

# If observation = correct:
P(L_t | obs=correct) = P(L_t) * (1 - P(S)) / [P(L_t) * (1 - P(S)) + (1 - P(L_t)) * P(G)]

# If observation = wrong:
P(L_t | obs=wrong) = P(L_t) * P(S) / [P(L_t) * P(S) + (1 - P(L_t)) * (1 - P(G))]

# Probability of correct response at time t+1:
P(C_{t+1}) = P(L_{t+1}) * (1 - P(S)) + (1 - P(L_{t+1})) * P(G)
```

**Citation:** Corbett, A. T., & Anderson, J. R. (1995). Knowledge tracing: Modeling the acquisition of procedural knowledge. *User Modeling and User-Adapted Interaction*, 4(4), 253–278.

### 8.2 Deep Knowledge Tracing (DKT)

DKT (Piech et al., 2015) replaces the binary latent state with a recurrent neural network (LSTM) that maintains a distributed hidden state:

```
h_t = LSTM(x_t, h_{t-1})
y_t = softmax(W * h_t + b)
```

where `x_t` is the one-hot encoded (skill, correctness) pair at time t, and `y_t` is the predicted probability of correctness on each skill at time t+1.

**Advantages:** Can model complex skill interactions, latent skill structures.
**Disadvantages:** Requires large datasets, less interpretable, can be unstable.

**Citation:** Piech, C., et al. (2015). Deep Knowledge Tracing. *NeurIPS 2015.*

### 8.3 Item Response Theory (IRT)

#### 8.3.1 2PL Model

```
P(correct | θ, a, b) = 1 / (1 + e^(-a(θ - b)))
```

where:
- `θ` = learner ability
- `a` = item discrimination (how well the item distinguishes high/low ability)
- `b` = item difficulty

#### 8.3.2 3PL Model

```
P(correct | θ, a, b, c) = c + (1 - c) / (1 + e^(-a(θ - b)))
```

where `c` = guessing parameter (pseudo-chance level).

#### 8.3.3 Fisher Information

The Fisher information for an item at ability level θ:

```
I(θ) = a² * (P(θ) - c)² / (1 - c)² * (1 - P(θ)) / P(θ)
```

**Item selection by maximum Fisher information:** Select the item with the highest I(θ̂) where θ̂ is the current ability estimate. This is the standard CAT item selection criterion.

**Citation:** Baker, F. B., & Kim, S.-H. (2017). *Item Response Theory: Parameter Estimation Techniques.* CRC Press. **[UNVERIFIED]**

### 8.4 Elo-Style Rating for Items

The Elo rating system can be adapted for adaptive learning:

```
# Expected score for learner with rating R_L on item with rating R_I:
E = 1 / (1 + 10^((R_I - R_L) / 400))

# After observing score S (0 or 1):
R_L' = R_L + K * (S - E)
R_I' = R_I + K * ((1 - S) - (1 - E)) = R_I - K * (S - E)
```

where K is the learning rate (typically 20–32 for educational applications).

**Citation:** Pelánek, R. (2016). Applications of the Elo rating system in adaptive educational systems. *Computers & Education*, 98, 169–179.

### 8.5 Computerized Adaptive Testing (CAT)

**Algorithm:**
1. Initialize θ̂ = 0 (or prior mean)
2. For each item:
   a. Select item with maximum Fisher information at θ̂
   b. Administer item, observe response
   c. Update θ̂ via maximum likelihood or Bayesian estimation
3. Stop when standard error of θ̂ < threshold or max items reached

**Citation:** van der Linden, W. J., & Glas, C. A. W. (2010). *Elements of Adaptive Testing.* Springer. **[UNVERIFIED]**

---

## 9. The Desirable-Difficulty vs. Pampering Boundary

### 9.1 The 85% Rule

Wilson et al. (2019) derived the "Eighty Five Percent Rule": for binary classification tasks with stochastic gradient descent, the optimal training error rate is ~15.87% (i.e., ~85% accuracy). Training at this difficulty maximizes the rate of learning.

**Key insight:** This is not a universal constant — it depends on the noise structure of the learning problem. But it provides a principled target: the learner should be failing ~15% of the time.

**Citation:** Wilson, R. C., Shenhav, A., Straccia, M., & Cohen, J. D. (2019). The Eighty Five Percent Rule for optimal learning. *Nature Communications*, 10, 4646.

### 9.2 Productive Failure vs. Unproductive Failure

- **Productive failure (Kapur, 2016):** Failure that leads to deeper conceptual understanding when followed by instruction. The key is that the failure occurs during exploration of a problem space, and the subsequent instruction addresses the learner's failed attempts.
- **Unproductive failure:** Failure that leads to frustration and dropout without subsequent instruction or support.

**Boundary conditions:**
1. **Prior knowledge:** Productive failure requires sufficient prior knowledge to engage with the problem. Complete novices need more scaffolding.
2. **Feedback timing:** Immediate feedback can undermine productive failure (the learner doesn't struggle enough). Delayed feedback allows productive struggle.
3. **Task difficulty:** The task must be challenging but not impossible. The 85% rule provides a quantitative target.
4. **Emotional support:** The system must acknowledge the difficulty without being condescending. "This is hard, and that's why it's worth doing" rather than "Don't worry, you'll get it."

### 9.3 When Difficulty Helps vs. When It Produces Frustration

| Condition | Difficulty Helps | Difficulty Harms |
|-----------|-----------------|------------------|
| Prior knowledge | Sufficient to engage with problem | Insufficient — learner is lost |
| Feedback | Delayed, specific, actionable | Immediate and complete (pampering) or absent (abandonment) |
| Task structure | Well-defined problem space | Ill-defined, no path forward |
| Learner state | Growth mindset, high self-efficacy | Fixed mindset, low self-efficacy |
| Social context | Supportive, normalized struggle | Punitive, shame-inducing |
| Success rate | ~85% (Wilson et al.) | >95% (boredom) or <50% (frustration) |

### 9.4 The "No Pampering" Principle

CortexForge must not pamper the learner. The evidence-based interpretation:

1. **Do not reduce difficulty when the learner struggles.** Instead, provide scaffolding (hints, worked examples) that allows the learner to succeed at the challenging task.
2. **Do not provide immediate complete answers.** Allow the learner to struggle productively before revealing the solution.
3. **Do not praise intelligence or ability.** Praise effort, strategies, and progress.
4. **Do not avoid negative feedback.** Provide honest, specific feedback about errors. The "no pampering" principle is not "be harsh" — it is "be honest."
5. **Do not let the learner off the hook.** If the learner is overconfident (Dunning-Kruger), provide objective performance data that corrects their self-assessment.

---

## A. Question-Style Specification Table

| Style | Generation Algorithm | Grading Method | When to Use |
|-------|---------------------|----------------|-------------|
| Multiple choice | Answer extraction + distractor generation (WordNet/embedding) | Exact match | Bloom 1–3, DoK 1–2; initial learning, factual recall |
| Multiple answer | Multi-key extraction + distractor generation | Partial credit (F1 score) | Bloom 2–4, DoK 2–3; conceptual understanding |
| True/False + justification | Negation/perturbation of true statement | Binary + LLM-graded justification | Bloom 2–3, DoK 2; misconception detection |
| Cloze/deletion | POS/entity masking + distractor generation | Exact match or fuzzy match | Bloom 1–2, DoK 1–2; vocabulary, key terms |
| Short answer | Wh-transformation, answer extraction | Fuzzy match (edit distance, embedding similarity) | Bloom 1–3, DoK 1–3; recall with production |
| Essay | Prompt construction from learning objectives | LLM-graded rubric | Bloom 4–6, DoK 3–4; deep understanding, transfer |
| Socratic dialogue | Recursive question generation from learner response | Multi-turn LLM evaluation | Bloom 3–5, DoK 2–3; conceptual exploration |
| Worked-example completion | Step deletion from worked solution | Exact match per step | Bloom 3, DoK 2; procedural learning |
| Error-spotting | Error injection into correct solution | Exact match (error location) | Bloom 4, DoK 3; debugging, critical analysis |
| Counterexample generation | Negation of universal claim, boundary-case search | LLM-graded validity | Bloom 4–5, DoK 3; mathematical reasoning |
| Proof/derivation | Theorem statement → proof skeleton | LLM-graded logical validity | Bloom 3–5, DoK 3–4; formal reasoning |
| Analogy | Relational mapping from source (A:B :: C:?) | LLM-graded relational similarity | Bloom 2–3, DoK 2; conceptual understanding |
| Transfer/novel-context | Context substitution, parameter variation | Same as base question type | Bloom 3, DoK 2–3; application, transfer |
| Feynman explanation | "Explain like I'm 12" prompt | LLM-graded clarity and accuracy | Bloom 2, DoK 2; conceptual understanding |
| Debate/steelman | Position assignment + argument generation | LLM-graded argument quality | Bloom 5, DoK 3; critical thinking, perspective-taking |
| Prediction-then-verify | Pre-experiment prediction prompt | Binary (prediction correct?) + calibration | Bloom 3–4, DoK 2–3; hypothesis testing |
| Interleaved mixed set | Scheduler-driven format mixing | Per-item grading | Bloom 1–6, DoK 1–4; comprehensive review, transfer |

---

## B. FSRS Update Equations (Complete)

### B.1 FSRS-5 Default Parameters

```
w = [0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621]
```

### B.2 State Variables

- `S`: Stability (days until retrievability drops to 90%)
- `D`: Difficulty (1–10 scale)
- `R`: Retrievability (probability of recall)
- `G`: Grade (1=Again, 2=Hard, 3=Good, 4=Easy)
- `t`: Days since last review

### B.3 Retrievability

```
R(t, S) = (1 + FACTOR * t / S) ^ DECAY
```

For FSRS-5: `DECAY = -0.5`, `FACTOR = 19/81`

### B.4 Initial State (First Review)

```
S_0(G) = w[G-1]
D_0(G) = w[4] - e^(w[5] * (G - 1)) + 1
```

### B.5 Difficulty Update

```
ΔD(G) = -w[6] * (G - 3)
D' = D + ΔD * (10 - D) / 9
D'' = w[7] * D_0(4) + (1 - w[7]) * D'
```

### B.6 Stability Update (Successful Review)

```
S'_r(D, S, R, G) = S * (e^w[8] * (11 - D) * S^(-w[9]) * (e^(w[10] * (1-R)) - 1) * w[15][if G=2] * w[16][if G=4] + 1)
```

### B.7 Stability Update (Lapse)

```
S'_f(D, S, R) = w[11] * D^(-w[12]) * ((S+1)^w[13] - 1) * e^(w[14] * (1-R))
```

### B.8 Same-Day Review

```
S'(S, G) = S * e^(w[17] * (G - 3 + w[18])) * S^(-w[19])
```

### B.9 Next Interval

```
I(r, S) = S / FACTOR * (r^(1/DECAY) - 1)
```

where `r` is the target retention (typically 0.9).

---

## C. BKT Update Equations (Complete)

### C.1 Parameters

- `P(L_0)`: prior probability of knowing the skill (typically 0.3)
- `P(T)`: transition probability (typically 0.1)
- `P(S)`: slip probability (typically 0.1)
- `P(G)`: guess probability (typically 0.2)

### C.2 Update Rules

```
# Step 1: Compute prior probability of knowing at time t
P(L_t) = P(L_{t-1} | obs_{t-1}) + (1 - P(L_{t-1} | obs_{t-1})) * P(T)

# Step 2: Update based on observation
if obs_t == correct:
    P(L_t | obs_t) = P(L_t) * (1 - P(S)) / [P(L_t) * (1 - P(S)) + (1 - P(L_t)) * P(G)]
else:
    P(L_t | obs_t) = P(L_t) * P(S) / [P(L_t) * P(S) + (1 - P(L_t)) * (1 - P(G))]

# Step 3: Predict probability of correct response at t+1
P(C_{t+1}) = P(L_t | obs_t) * (1 - P(S)) + (1 - P(L_t | obs_t)) * P(G)
```

### C.3 Mastery Threshold

A skill is considered "mastered" when `P(L_t | obs) > 0.95` (configurable).

---

## D. Difficulty-Calibration Rule Set

### D.1 Target Success Rate

**Primary target:** 85% success rate (Wilson et al., 2019).

**Implementation:**
```python
def target_success_rate(window=20):
    """
    Compute the target success rate based on recent performance.
    Returns the fraction of items that should be answered correctly.
    """
    return 0.85  # Wilson et al. (2019)
```

### D.2 Difficulty Adjustment Rules

```python
def adjust_difficulty(recent_success_rate, current_difficulty, window=20):
    """
    Adjust item difficulty to maintain ~85% success rate.
    
    recent_success_rate: fraction correct in last `window` items
    current_difficulty: current difficulty level (1-10)
    """
    target = 0.85
    tolerance = 0.05  # acceptable range: 0.80-0.90
    
    if recent_success_rate > target + tolerance:
        # Too easy — increase difficulty
        return min(10, current_difficulty + 0.5)
    elif recent_success_rate < target - tolerance:
        # Too hard — decrease difficulty, but not below 1
        return max(1, current_difficulty - 0.5)
    else:
        # In the productive-failure band — maintain
        return current_difficulty
```

### D.3 The "No Pampering" Constraints

```python
def no_pampering_constraints():
    """
    Hard constraints that prevent the system from pampering the learner.
    """
    return {
        "min_difficulty_floor": 1.0,  # Never go below difficulty 1
        "max_scaffold_before_reveal": 3,  # Max hints before showing solution
        "min_struggle_time_seconds": 30,  # Minimum time before hint is offered
        "no_immediate_answer_reveal": True,  # Never show answer immediately
        "no_difficulty_reduction_on_failure": True,  # Don't make it easier when they fail
        "require_justification_for_tf": True,  # T/F always requires justification
        "calibration_feedback_frequency": 10,  # Show calibration stats every 10 items
    }
```

### D.4 Frustration Detection and Response

```python
def detect_frustration(recent_responses, time_per_item, window=5):
    """
    Detect when the learner is frustrated (not just challenged).
    
    Returns: "productive_struggle" | "frustration" | "boredom"
    """
    recent = recent_responses[-window:]
    success_rate = sum(recent) / len(recent)
    avg_time = sum(time_per_item[-window:]) / len(window)
    
    if success_rate < 0.3 and avg_time > 120:
        # Failing a lot and taking too long — frustration
        return "frustration"
    elif success_rate > 0.95 and avg_time < 10:
        # Succeeding easily and quickly — boredom
        return "boredom"
    else:
        return "productive_struggle"

def respond_to_frustration():
    """
    When frustration is detected, provide scaffolding (not easier questions).
    """
    return {
        "action": "provide_scaffold",
        "scaffold_types": ["hint", "worked_example", "simpler_prerequisite"],
        "do_not": ["reduce_difficulty", "show_answer", "skip_item"],
    }

def respond_to_boredom():
    """
    When boredom is detected, increase difficulty or introduce novelty.
    """
    return {
        "action": "increase_challenge",
        "methods": ["increase_difficulty", "introduce_novel_context", "switch_to_higher_bloom"],
    }
```

### D.5 Calibration Feedback

```python
def provide_calibration_feedback(jol_list, performance_list):
    """
    Provide feedback that corrects metacognitive miscalibration.
    """
    calibration = compute_calibration(jol_list, performance_list)
    
    if calibration["bias"] > 0.1:
        return "You predicted {predicted:.0%} but scored {actual:.0%}. You may be overconfident — testing yourself is the best way to calibrate.".format(
            predicted=sum(jol_list)/len(jol_list),
            actual=sum(performance_list)/len(performance_list)
        )
    elif calibration["bias"] < -0.1:
        return "You predicted {predicted:.0%} but scored {actual:.0%}. You may be underconfident — you know more than you think.".format(
            predicted=sum(jol_list)/len(jol_list),
            actual=sum(performance_list)/len(performance_list)
        )
    else:
        return "Your predictions are well-calibrated. Keep testing yourself to maintain this awareness."
```

---

## References

1. Adesope, O. O., Trevisan, D. A., & Sundararajan, N. (2017). Rethinking the use of tests: A meta-analysis of practice testing. *Review of Educational Research*, 87(3), 659–701.
2. Anderson, L. W., & Krathwohl, D. R. (Eds.). (2001). *A Taxonomy for Learning, Teaching, and Assessing: A Revision of Bloom's Taxonomy of Educational Objectives.* Longman.
3. Awalurahman, H. W., & Budi, I. D. (2024). Automatic distractor generation in multiple-choice questions: a systematic literature review. *PeerJ Computer Science*, 10, e2611.
4. Bjork, E. L., & Bjork, R. A. (2011). Making things hard on yourself, but in a good way: Creating desirable difficulties to enhance learning. *Psychology and the Real World*, 2, 56–64.
5. Bjork, R. A., Dunlosky, J., & Kornell, N. (2013). Self-regulated learning: Beliefs, techniques, and illusions. *Annual Review of Psychology*, 64, 417–444.
6. Cepeda, N. J., Pashler, H., Vul, E., Wixted, J. T., & Rohrer, D. (2006). Distributed practice in verbal recall tasks: A review and quantitative synthesis. *Psychological Bulletin*, 132(3), 354–380.
7. Cepeda, N. J., Vul, E., Rohrer, D., Wixted, J. T., & Pashler, H. (2008). Spacing effects in learning: A temporal ridgeline of optimal retention. *Psychological Science*, 19(11), 1095–1102.
8. Corbett, A. T., & Anderson, J. R. (1995). Knowledge tracing: Modeling the acquisition of procedural knowledge. *User Modeling and User-Adapted Interaction*, 4(4), 253–278.
9. Driskell, J. E., Willis, R. P., & Copper, C. (1992). Effect of overlearning on retention. *Journal of Applied Psychology*, 77(5), 615–622. **[UNVERIFIED]**
10. Heilman, M., & Smith, N. A. (2009). Question Generation via Overgenerating Transformations and Ranking. *CMU-LTI-09-013.*
11. Hearst, M. A. (1992). Automatic acquisition of hyponyms from large text corpora. *COLING 1992.*
12. Kapur, M. (2016). Examining productive failure, productive success, unproductive failure, and unproductive success in learning. *Educational Psychologist*, 51(2), 289–299. **[UNVERIFIED]**
13. Kluger, A. N., & DeNisi, A. (1996). The effects of feedback interventions on performance: A historical review, a meta-analysis, and a preliminary feedback intervention theory. *Psychological Bulletin*, 119(2), 254–284.
14. Kruger, J., & Dunning, D. (1999). Unskilled and unaware of it: How difficulties in recognizing one's own incompetence lead to inflated self-assessments. *Journal of Personality and Social Psychology*, 77(6), 1121–1134.
15. Leitner, S. (1972). *So lernt man lernen.* Verlag Herder.
16. Mueller, C. M., & Dweck, C. S. (1998). Praise for intelligence can undermine children's motivation and performance. *Journal of Personality and Social Psychology*, 75(1), 33–52.
17. Pelánek, R. (2016). Applications of the Elo rating system in adaptive educational systems. *Computers & Education*, 98, 169–179.
18. Piech, C., et al. (2015). Deep Knowledge Tracing. *NeurIPS 2015.*
19. Roediger, H. L., & Karpicke, J. D. (2006). Test-enhanced learning: Taking memory tests improves long-term retention. *Psychological Science*, 17(3), 249–255.
20. Roediger, H. L., & Karpicke, J. D. (2006). The power of testing memory: Basic research and implications for educational practice. *Perspectives on Psychological Science*, 1(3), 181–210.
21. Rohrer, D., & Taylor, K. (2007). The shuffling of mathematics problems improves learning. *Instructional Science*, 35(6), 481–498.
22. Rohrer, D., & Taylor, K. (2010). The effects of interleaved practice. *Applied Cognitive Psychology*, 24(6), 837–848.
23. Rowland, C. A. (2014). The effect of testing versus restudy on retention: A meta-analytic review of the testing effect. *Psychological Bulletin*, 140(6), 1432–1463. **[UNVERIFIED]**
24. Settles, B., & Meeder, B. (2016). A Trainable Spaced Repetition Model for Language Learning. *ACL 2016.*
25. Shute, V. J. (2008). Focus on formative feedback. *Review of Educational Research*, 78(1), 153–189.
26. Sisk, V. F., Burgoyne, A. P., Sun, J., Butler, J. L., & Macnamara, B. N. (2018). To what extent and under which circumstances are growth mind-sets important to academic achievement? Two meta-analyses. *Psychological Science*, 29(4), 549–571.
27. Stasaski, K., Rathod, M., Tu, T., Xiao, Y., & Hearst, M. A. (2021). Automatically Generating Cause-and-Effect Questions from Passages. *BEA Workshop 2021.*
28. Webb, N. L. (1997). *Criteria for Alignment of Expectations and Assessments in Mathematics and Science Education.* Council of Chief State School Officers. **[UNVERIFIED]**
29. Wilson, R. C., Shenhav, A., Straccia, M., & Cohen, J. D. (2019). The Eighty Five Percent Rule for optimal learning. *Nature Communications*, 10, 4646.
30. Wozniak, P. (1990). *Algorithm SM-2.* SuperMemo.
31. Ye, J., et al. (2023). *FSRS: A Free Spaced Repetition Scheduler.* GitHub: open-spaced-repetition/fsrs4anki.
