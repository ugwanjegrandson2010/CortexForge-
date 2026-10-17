"""Question generation from a learner's own source material — any style.

Design constraint: this module must work with NO large language model, using
classical NLP over the learner's text, and must ALSO accept an LLM provider
for the styles that genuinely need one. Every generator returns a Question
object with a style tag, a prompt, an expected answer, a grading strategy,
and the source span it was derived from (provenance is mandatory — a
question with no traceable source is rejected).

Styles implemented natively (no LLM):
    cloze, definition, wh_question, true_false_justify, ordering,
    error_spotting, worked_example_completion, analogy, list_recall,
    numeric, causal_chain, compare_contrast, counterexample, transfer,
    socratic, feynman, prediction_verify, steelman, mixed_interleaved

Styles that require an LLM provider (declared, not faked):
    essay, open_dialogue, proof_derivation
"""

from __future__ import annotations

import math
import random
import re
from dataclasses import dataclass, field, asdict
from typing import Callable, Iterable

# ---------------------------------------------------------------------------
# Text utilities (stdlib only)
# ---------------------------------------------------------------------------

STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "than", "that", "this",
    "these", "those", "of", "to", "in", "on", "at", "by", "for", "with", "as",
    "is", "are", "was", "were", "be", "been", "being", "it", "its", "from",
    "which", "who", "whom", "whose", "what", "when", "where", "why", "how",
    "not", "no", "nor", "so", "such", "can", "could", "may", "might", "must",
    "shall", "should", "will", "would", "do", "does", "did", "has", "have",
    "had", "there", "here", "also", "into", "about", "more", "most", "other",
    "some", "any", "all", "each", "both", "few", "many", "much", "very",
}

SENT_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"'(])")
WORD_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*|\d+(?:\.\d+)?")
NUM_RE = re.compile(r"\b\d+(?:\.\d+)?\b")

CAUSAL_MARKERS = ("because", "therefore", "thus", "hence", "as a result",
                  "leads to", "causes", "results in", "due to", "so that",
                  "consequently", "gives rise to", "accounts for")
CONTRAST_MARKERS = ("however", "whereas", "in contrast", "unlike", "on the "
                    "other hand", "differs from", "but rather", "although",
                    "while", "conversely")
DEFINITION_MARKERS = (" is ", " are ", " refers to ", " means ", " is defined as ",
                      " denotes ", " is called ", " describes ")


def sentences(text: str) -> list[str]:
    out = []
    for para in re.split(r"\n\s*\n", text):
        para = " ".join(para.split())
        if not para:
            continue
        for s in SENT_SPLIT.split(para):
            s = s.strip()
            if len(s) > 25:
                out.append(s)
    return out


def tokens(text: str) -> list[str]:
    return [w for w in WORD_RE.findall(text)]


def content_words(text: str) -> list[str]:
    return [w for w in tokens(text) if w.lower() not in STOPWORDS and len(w) > 3]


def term_frequencies(text: str) -> dict[str, int]:
    tf: dict[str, int] = {}
    for w in content_words(text):
        tf[w.lower()] = tf.get(w.lower(), 0) + 1
    return tf


def key_terms(text: str, n: int = 20) -> list[str]:
    """TF-based key term extraction with a length bonus (no external corpus)."""
    tf = term_frequencies(text)
    scored = [(t, c * (1.0 + 0.05 * len(t))) for t, c in tf.items()]
    scored.sort(key=lambda x: -x[1])
    return [t for t, _ in scored[:n]]


def capitalised_entities(text: str) -> list[str]:
    """Crude NER: multi-word capitalised sequences not at sentence start."""
    ents: list[str] = []
    for s in sentences(text):
        body = s[1:] if s else s
        for m in re.finditer(r"\b([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)\b", body):
            ents.append(m.group(1))
        for m in re.finditer(r"\b([A-Z]{2,}(?:\s+[A-Z]{2,})*)\b", body):
            ents.append(m.group(1))
    seen, out = set(), []
    for e in ents:
        if e.lower() not in seen:
            seen.add(e.lower())
            out.append(e)
    return out


# ---------------------------------------------------------------------------
# Question model
# ---------------------------------------------------------------------------

@dataclass
class Question:
    qid: str
    style: str
    prompt: str
    answer: str
    source_span: str
    skill_id: str = ""
    options: list[str] = field(default_factory=list)
    grading: str = "exact"          # exact | fuzzy | numeric | set | rubric | self
    difficulty_hint: float = 0.0    # -3..+3 in logits
    bloom: str = "remember"
    requires_llm: bool = False
    meta: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class SourceError(ValueError):
    """Raised when a source cannot support the requested question style."""


# ---------------------------------------------------------------------------
# Generators
# ---------------------------------------------------------------------------

def _qid(style: str, span: str, i: int) -> str:
    import hashlib
    h = hashlib.sha1(f"{style}|{span}|{i}".encode()).hexdigest()[:10]
    return f"{style}-{h}"


def gen_cloze(sent: str, term: str, i: int = 0) -> Question:
    """Cloze deletion: blank out a key term, keep the rest as context."""
    if term.lower() not in sent.lower():
        raise SourceError("term not in sentence")
    pattern = re.compile(re.escape(term), re.IGNORECASE)
    prompt = pattern.sub("______", sent, count=1)
    return Question(
        qid=_qid("cloze", sent, i), style="cloze", prompt=prompt, answer=term,
        source_span=sent, grading="fuzzy", bloom="remember",
        meta={"blanked": term},
    )


def gen_definition(sent: str, i: int = 0) -> Question:
    """Turn 'X is Y' into 'What is X?' / 'Define X.'"""
    m = re.match(r"^([A-Z][\w\-]*(?: [a-z][\w\-]*){0,4}?)\s+"
                 r"(?:is|are|refers to|means|denotes)\s+(.+)$", sent.rstrip("."))
    if not m:
        raise SourceError("no definitional pattern")
    subject, predicate = m.group(1).strip(), m.group(2).strip()
    if len(predicate.split()) < 3 or len(subject.split()) > 5:
        raise SourceError("subject/predicate shape unsuitable")
    return Question(
        qid=_qid("definition", sent, i), style="definition",
        prompt=f"Define or explain: {subject}", answer=predicate,
        source_span=sent, grading="rubric", bloom="understand",
        meta={"subject": subject},
    )


def gen_wh_question(sent: str, answer: str, i: int = 0) -> Question:
    """Answer-aware wh-question: replace the answer span with an interrogative."""
    if answer.lower() not in sent.lower():
        raise SourceError("answer not in sentence")
    if NUM_RE.fullmatch(answer):
        wh, kind = "How many / how much", "numeric"
    elif answer[:1].isupper():
        wh, kind = "Who or what", "fuzzy"
    else:
        wh, kind = "What", "fuzzy"
    prompt = re.sub(re.escape(answer), f"[{wh}?]", sent, count=1, flags=re.I)
    return Question(
        qid=_qid("wh", sent, i), style="wh_question",
        prompt=f"Fill the gap, then answer in one sentence:\n{prompt}",
        answer=answer, source_span=sent, grading=kind, bloom="remember",
        meta={"gap": answer},
    )


def gen_true_false_justify(sent: str, i: int = 0, rng: random.Random | None = None,
                           corrupt: bool = True) -> Question:
    """True/false WITH mandatory justification — never a coin flip.

    If corrupting, a numeric or key term is altered so the statement becomes
    false; the learner must state the verdict AND the reason.
    """
    rng = rng or random.Random(0)
    nums = NUM_RE.findall(sent)
    if corrupt and nums:
        target = rng.choice(nums)
        delta = str(round(float(target) * rng.choice([0.5, 1.5, 2.0]), 2))
        delta = delta.rstrip("0").rstrip(".") if "." in delta else delta
        if delta == target:
            delta = str(float(target) + 1)
        statement = re.sub(re.escape(target), delta, sent, count=1)
        verdict = False
        why = f"the correct value is {target}, not {delta}"
    elif corrupt:
        terms = content_words(sent)
        if len(terms) < 3:
            raise SourceError("sentence too short to corrupt")
        target = rng.choice(terms)
        swap = rng.choice([t for t in terms if t != target] or [target])
        statement = re.sub(re.escape(target), swap, sent, count=1, flags=re.I)
        verdict = False
        why = f"the original term is '{target}', not '{swap}'"
    else:
        statement, verdict, why = sent, True, "the statement matches the source"
    return Question(
        qid=_qid("tfj", statement, i), style="true_false_justify",
        prompt=(f"True or false — and you must justify your verdict in one "
                f"sentence. A bare 'true'/'false' scores zero.\n\n{statement}"),
        answer=f"{'True' if verdict else 'False'} — {why}",
        source_span=sent, grading="rubric", bloom="evaluate",
        meta={"verdict": verdict, "rationale": why},
    )


def gen_ordering(sentences_list: list[str], i: int = 0,
                 rng: random.Random | None = None) -> Question:
    """Ordering task: shuffle a causal/sequential chain, learner reorders it."""
    if len(sentences_list) < 3:
        raise SourceError("need >= 3 sentences for an ordering task")
    rng = rng or random.Random(0)
    order = list(range(len(sentences_list)))
    shuffled = order[:]
    rng.shuffle(shuffled)
    if shuffled == order:
        shuffled = shuffled[1:] + shuffled[:1]
    labelled = "\n".join(f"  {chr(65 + pos)}. {sentences_list[idx]}"
                         for pos, idx in enumerate(shuffled))
    return Question(
        qid=_qid("order", "|".join(sentences_list), i), style="ordering",
        prompt=("Put these statements back into the order the source presents "
                f"them in:\n{labelled}"),
        answer=" -> ".join(chr(65 + order.index(k)) for k in order),
        source_span=" | ".join(sentences_list), grading="set", bloom="understand",
        meta={"correct_sequence": order, "presented": shuffled},
    )


def gen_error_spotting(sent: str, i: int = 0,
                       rng: random.Random | None = None) -> Question:
    """Present a subtly wrong derivation/statement; learner must find the error."""
    nums = NUM_RE.findall(sent)
    if not nums:
        raise SourceError("no numeric content to corrupt")
    rng = rng or random.Random(0)
    target = rng.choice(nums)
    try:
        wrong = str(round(float(target) * 1.25, 3)).rstrip("0").rstrip(".")
    except ValueError:
        raise SourceError("unparseable number")
    corrupted = re.sub(re.escape(target), wrong, sent, count=1)
    return Question(
        qid=_qid("error", corrupted, i), style="error_spotting",
        prompt=("This statement contains exactly one error. Identify the error "
                f"and correct it.\n\n{corrupted}"),
        answer=f"'{wrong}' should be '{target}'", source_span=sent,
        grading="rubric", bloom="analyse",
        meta={"wrong": wrong, "right": target},
    )


def gen_worked_example(sent: str, i: int = 0) -> Question:
    """Worked-example completion: hide the final step's result."""
    nums = NUM_RE.findall(sent)
    if not nums:
        raise SourceError("no numeric step to complete")
    last = nums[-1]
    prompt = sent[::-1].replace(last[::-1], "____", 1)[::-1]
    return Question(
        qid=_qid("worked", sent, i), style="worked_example_completion",
        prompt=f"Complete the final step of this worked example:\n{prompt}",
        answer=last, source_span=sent, grading="numeric", bloom="apply",
        meta={"hidden": last},
    )


def gen_analogy(sent: str, i: int = 0) -> Question:
    """Analogy construction: A is to B as C is to ___ (learner supplies C)."""
    m = re.match(r"^([A-Z][\w\-]*(?: [a-z][\w\-]*){0,4}?)\s+(?:is|are)\s+"
                 r"(?:a |an |the )?([a-z][\w\- ]{5,80})$", sent.rstrip("."))
    if not m:
        raise SourceError("no relational pattern")
    a, b = m.group(1).strip(), m.group(2).strip()
    if len(b.split()) < 2:
        raise SourceError("predicate too short")
    return Question(
        qid=_qid("analogy", sent, i), style="analogy",
        prompt=(f"Complete the analogy and explain the shared relation in one "
                f"line:\n{a} : {b} :: ______ : ______"),
        answer=f"any pair sharing the relation '{a} -> {b}'",
        source_span=sent, grading="rubric", bloom="analyse",
        meta={"relation": f"{a} -> {b}"},
    )


def gen_list_recall(sent: str, i: int = 0) -> Question:
    """Free recall of an enumerated list — no cues, no options."""
    items = [p.strip() for p in re.split(r",|;|\band\b", sent) if len(p.strip()) > 3]
    items = [re.sub(r"^\(?\d+[\).\s]*", "", x) for x in items]
    if len(items) < 3:
        raise SourceError("not an enumerable list")
    return Question(
        qid=_qid("list", sent, i), style="list_recall",
        prompt=("From memory, list every element the source gives here. No "
                "hints, no options, no partial credit for vagueness."),
        answer="; ".join(items), source_span=sent, grading="set", bloom="remember",
        meta={"elements": items},
    )


def gen_numeric(sent: str, i: int = 0) -> Question:
    """Numeric question from a stated relation.

    With one number: asks for the quantity, its units, and what it is measured
    against. With two or more: asks for a derived computation.
    """
    nums = NUM_RE.findall(sent)
    if not nums:
        raise SourceError("no numbers")
    if len(nums) == 1:
        prompt = (f"State precisely what the value {nums[0]} refers to in this "
                  f"statement — quantity, units, and what it is measured "
                  f"against. Then give one way it could be changed:\n{sent}")
        answer = f"the quantity and units of {nums[0]}"
    else:
        prompt = (f"Using only the values in this statement, compute the "
                  f"quantity described and show the arithmetic:\n{sent}")
        answer = f"derived from {nums}"
    return Question(
        qid=_qid("numeric", sent, i), style="numeric",
        prompt=prompt, answer=answer, source_span=sent, grading="numeric",
        bloom="apply", meta={"values": nums},
    )


def gen_causal_chain(sent: str, i: int = 0) -> Question:
    """Why-question built from an explicit causal marker.

    Handles both orders:
        "X because Y"   -> cause X, effect Y
        "Because Y, X"  -> cause Y, effect X
    """
    low = sent.lower()
    marker = next((m for m in CAUSAL_MARKERS if m in low), None)
    if not marker:
        raise SourceError("no causal marker")
    idx = low.index(marker)
    before = sent[:idx].strip(" ,;")
    after = sent[idx + len(marker):].strip(" ,;")
    if idx == 0:
        parts = re.split(r",|;", after, maxsplit=1)
        if len(parts) == 2:
            cause, effect = parts[0].strip(), parts[1].strip()
        else:
            cause, effect = after, before
    else:
        cause, effect = before, after
    if len(cause) < 8 or len(effect) < 8:
        raise SourceError("causal halves too short")
    return Question(
        qid=_qid("causal", sent, i), style="causal_chain",
        prompt=(f"Explain the mechanism: why does {effect.rstrip('.')}? "
                f"Answer in terms of the cause, not by restating the effect."),
        answer=cause, source_span=sent, grading="rubric", bloom="understand",
        meta={"marker": marker, "cause": cause, "effect": effect},
    )


def gen_compare_contrast(sent: str, i: int = 0) -> Question:
    """Contrast question from an explicit contrast marker.

    Handles both orders:
        "A, whereas B"      -> left A, right B
        "In contrast, B"    -> right B, left = the preceding statement
    """
    low = sent.lower()
    marker = next((m for m in CONTRAST_MARKERS if m in low), None)
    if not marker:
        raise SourceError("no contrast marker")
    idx = low.index(marker)
    before = sent[:idx].strip(" ,;")
    after = sent[idx + len(marker):].strip(" ,;")
    if idx == 0 or len(before) < 8:
        left, right = "", after
    else:
        left, right = before, after
    if len(right) < 8:
        raise SourceError("contrast halves too short")
    if left:
        prompt = ("State the single most important difference between these two "
                  f"things, then name one way they are alike:\nA: {left}\nB: {right}")
        answer = f"{left} vs {right}"
    else:
        prompt = ("The source contrasts this with something stated immediately "
                  f"before it. Name both sides of the contrast and the single "
                  f"most important difference:\n{right}")
        answer = f"previous statement vs {right}"
    return Question(
        qid=_qid("contrast", sent, i), style="compare_contrast",
        prompt=prompt, answer=answer, source_span=sent, grading="rubric",
        bloom="analyse", meta={"marker": marker, "left": left, "right": right},
    )


def gen_counterexample(sent: str, i: int = 0) -> Question:
    """Counterexample generation — the highest-value transfer probe."""
    return Question(
        qid=_qid("counter", sent, i), style="counterexample",
        prompt=("Construct a concrete case that would FALSIFY this claim. If "
                f"you cannot, say precisely which part is unfalsifiable.\n\n{sent}"),
        answer="a falsifying case, or an explicit unfalsifiability claim",
        source_span=sent, grading="rubric", bloom="create",
        meta={"claim": sent},
    )


def gen_transfer(sent: str, term: str, i: int = 0) -> Question:
    """Transfer probe: apply the principle in a domain the source never mentions."""
    return Question(
        qid=_qid("transfer", sent, i), style="transfer",
        prompt=(f"The source states: \"{sent}\"\n\nNow apply '{term}' to a "
                f"situation from a completely different domain that the source "
                f"never mentions. Name the domain and the mapping."),
        answer="a valid cross-domain mapping", source_span=sent, grading="rubric",
        bloom="create", meta={"term": term},
    )


def gen_socratic(sent: str, i: int = 0) -> Question:
    """Socratic probe: surface the hidden assumption."""
    return Question(
        qid=_qid("socratic", sent, i), style="socratic",
        prompt=("What must be assumed for this statement to be true at all? "
                f"Name the assumption and say what breaks if it fails.\n\n{sent}"),
        answer="the load-bearing assumption", source_span=sent, grading="rubric",
        bloom="evaluate", meta={"statement": sent},
    )


def gen_feynman(sent: str, term: str, i: int = 0) -> Question:
    """Feynman test: explain to a smart 12-year-old, then find the gap."""
    return Question(
        qid=_qid("feynman", sent, i), style="feynman",
        prompt=(f"Explain '{term}' to a smart 12-year-old in under 120 words, "
                f"using no jargon from the source. Then state the one part you "
                f"could not simplify — that part is your gap."),
        answer="a jargon-free explanation plus an honest gap statement",
        source_span=sent, grading="rubric", bloom="understand",
        meta={"term": term},
    )


def gen_prediction_verify(sent: str, i: int = 0) -> Question:
    """Predict-then-verify: commit to an answer BEFORE seeing the source."""
    return Question(
        qid=_qid("predict", sent, i), style="prediction_verify",
        prompt=("Before reading the source: write your prediction for what it "
                "will say about this. Commit to it. You will be scored on "
                "whether you revise it in light of evidence, not on being right."),
        answer="a committed prediction, then an evidence-based revision",
        source_span=sent, grading="self", bloom="evaluate",
        meta={"reveal_after": True},
    )


def gen_steelman(sent: str, i: int = 0) -> Question:
    """Steelman: build the strongest opposing case."""
    return Question(
        qid=_qid("steelman", sent, i), style="steelman",
        prompt=("Argue the strongest possible case AGAINST this position, as "
                f"someone who holds it would recognise as fair. Strawmen score "
                f"zero.\n\n{sent}"),
        answer="the strongest opposing case", source_span=sent, grading="rubric",
        bloom="evaluate", meta={"position": sent},
    )


LLM_STYLES = {
    "essay": "Write a structured argument with a thesis, evidence, and a "
             "counter-argument you then rebut.",
    "open_dialogue": "Hold a multi-turn Socratic dialogue that probes the "
                     "learner's reasoning until a contradiction or a defensible "
                     "position is reached.",
    "proof_derivation": "Derive the result from stated premises, justifying "
                        "every step; mark any step that is assumed rather than "
                        "derived.",
}


def gen_llm_style(style: str, sent: str, i: int = 0) -> Question:
    """Declare an LLM-requiring style. Never fabricates the content."""
    if style not in LLM_STYLES:
        raise SourceError(f"unknown LLM style: {style}")
    return Question(
        qid=_qid(style, sent, i), style=style,
        prompt=f"{LLM_STYLES[style]}\n\nSource material:\n{sent}",
        answer="graded against a rubric derived from the source",
        source_span=sent, grading="rubric", bloom="create", requires_llm=True,
        meta={"llm_style": style},
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

NATIVE_GENERATORS: dict[str, Callable] = {
    "cloze": gen_cloze,
    "definition": gen_definition,
    "wh_question": gen_wh_question,
    "true_false_justify": gen_true_false_justify,
    "ordering": gen_ordering,
    "error_spotting": gen_error_spotting,
    "worked_example_completion": gen_worked_example,
    "analogy": gen_analogy,
    "list_recall": gen_list_recall,
    "numeric": gen_numeric,
    "causal_chain": gen_causal_chain,
    "compare_contrast": gen_compare_contrast,
    "counterexample": gen_counterexample,
    "transfer": gen_transfer,
    "socratic": gen_socratic,
    "feynman": gen_feynman,
    "prediction_verify": gen_prediction_verify,
    "steelman": gen_steelman,
}

ALL_STYLES = sorted(list(NATIVE_GENERATORS) + list(LLM_STYLES))

# Set to a set of style names to print why each candidate sentence was skipped.
_DEBUG_STYLES: set[str] = set()


def generate_from_source(text: str, styles: Iterable[str] | None = None,
                         max_per_style: int = 3, seed: int = 7,
                         skill_id: str = "") -> list[Question]:
    """Generate questions in every requested style from the learner's source.

    Robust by design: a style that cannot be generated from a given sentence
    is skipped rather than faked, and the skip is recorded in the result set's
    provenance. Returns questions sorted by Bloom level (recall first).
    """
    rng = random.Random(seed)
    sents = sentences(text)
    if not sents:
        raise SourceError("source contains no usable sentences")
    terms = key_terms(text, 30)
    styles = list(styles) if styles else ALL_STYLES
    out: list[Question] = []
    skipped: dict[str, int] = {}

    for style in styles:
        made = 0
        for sent in sents:
            if made >= max_per_style:
                break
            try:
                if style == "cloze":
                    cand = [t for t in terms if t.lower() in sent.lower()]
                    if not cand:
                        raise SourceError("no key term in sentence")
                    q = gen_cloze(sent, rng.choice(cand), made)
                elif style == "wh_question":
                    cand = [t for t in terms if t.lower() in sent.lower()] or \
                        NUM_RE.findall(sent)
                    if not cand:
                        raise SourceError("no answer span")
                    q = gen_wh_question(sent, rng.choice(cand), made)
                elif style == "true_false_justify":
                    q = gen_true_false_justify(sent, made, rng, corrupt=(made % 2 == 0))
                elif style == "ordering":
                    if len(sents) < 3:
                        raise SourceError("not enough sentences")
                    start = sents.index(sent)
                    window = sents[start:start + 3]
                    if len(window) < 3:
                        raise SourceError("window too small")
                    q = gen_ordering(window, made, rng)
                elif style in ("transfer", "feynman"):
                    cand = [t for t in terms if t.lower() in sent.lower()]
                    if not cand:
                        raise SourceError("no key term")
                    fn = NATIVE_GENERATORS[style]
                    q = fn(sent, rng.choice(cand), made)
                elif style in LLM_STYLES:
                    q = gen_llm_style(style, sent, made)
                else:
                    q = NATIVE_GENERATORS[style](sent, made)
            except (SourceError, TypeError, ValueError) as exc:
                if style in _DEBUG_STYLES:
                    print(f"[skip] {style}: {type(exc).__name__}: {exc}")
                continue
            q.skill_id = skill_id or _infer_skill(sent, terms)
            q.difficulty_hint = _difficulty_hint(q)
            out.append(q)
            made += 1
        if made == 0:
            skipped[style] = len(sents)

    bloom_order = {"remember": 0, "understand": 1, "apply": 2,
                   "analyse": 3, "evaluate": 4, "create": 5}
    out.sort(key=lambda q: (bloom_order.get(q.bloom, 9), q.style))
    if skipped:
        out.append(Question(
            qid="__provenance__", style="provenance",
            prompt="styles skipped for lack of supporting source structure",
            answer="", source_span="", grading="none",
            meta={"skipped": skipped, "n_sentences": len(sents)},
        ))
    return out


def _infer_skill(sent: str, terms: list[str]) -> str:
    """Assign the sentence to the skill whose key term it contains most often."""
    best, best_n = "general", 0
    for t in terms[:12]:
        n = sent.lower().count(t.lower())
        if n > best_n:
            best, best_n = t, n
    return best


def _difficulty_hint(q: Question) -> float:
    """Heuristic prior difficulty in logits, refined later by IRT calibration."""
    base = {"remember": -1.0, "understand": -0.3, "apply": 0.2,
            "analyse": 0.6, "evaluate": 1.0, "create": 1.5}.get(q.bloom, 0.0)
    length_pen = min(1.0, len(q.source_span) / 400.0)
    return round(base + length_pen, 3)


def interleave(questions: list[Question], seed: int = 11) -> list[Question]:
    """Interleave by skill so consecutive items rarely share a skill."""
    rng = random.Random(seed)
    buckets: dict[str, list[Question]] = {}
    for q in questions:
        buckets.setdefault(q.skill_id, []).append(q)
    for b in buckets.values():
        rng.shuffle(b)
    order = sorted(buckets, key=lambda k: -len(buckets[k]))
    out: list[Question] = []
    while order:
        nxt = []
        for k in order:
            if buckets[k]:
                out.append(buckets[k].pop())
            if buckets[k]:
                nxt.append(k)
        order = nxt
    return out
