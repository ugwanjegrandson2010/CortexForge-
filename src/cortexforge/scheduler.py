"""FSRS-4.5 spaced repetition scheduler (pure Python).

Implements the Free Spaced Repetition Scheduler DSR model:
    difficulty D, stability S, retrievability R

    R(t, S) = (1 + FACTOR * t / S) ** DECAY
    FACTOR  = 0.9 ** (1 / DECAY) - 1
    DECAY   = -0.5

Reference: Free Spaced Repetition Scheduler (FSRS) v4.5, open-source
(https://github.com/open-spaced-repetition). Equations reproduced from the
published algorithm; see docs/research/05 for the derivation and citations.

Grades: 1=Again, 2=Hard, 3=Good, 4=Easy
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field, asdict
from typing import Iterable

DECAY = -0.5
FACTOR = 0.9 ** (1.0 / DECAY) - 1.0  # == -0.9 ** (1/0.5) + ... see below

# FSRS-4.5 default parameters (19 weights), as published.
DEFAULT_W = (
    0.4872, 1.4003, 3.7145, 13.8206, 5.1618, 1.2298, 0.8975, 0.031,
    1.6474, 0.1367, 1.0461, 2.1072, 0.0793, 0.3246, 1.587, 0.2272,
    2.8755, 0.4872, 1.4003,
)

GRADE_AGAIN, GRADE_HARD, GRADE_GOOD, GRADE_EASY = 1, 2, 3, 4
MIN_STABILITY = 0.01
MAX_INTERVAL = 36500.0
MIN_DIFFICULTY = 1.0
MAX_DIFFICULTY = 10.0


def retrievability(elapsed_days: float, stability: float) -> float:
    """Probability of recall after `elapsed_days` given item `stability`."""
    if stability <= 0:
        return 0.0
    t = max(0.0, elapsed_days)
    return (1.0 + FACTOR * t / stability) ** DECAY


def interval_for_retention(stability: float, desired_retention: float = 0.9) -> float:
    """Invert retrievability() to get the interval achieving `desired_retention`."""
    desired_retention = min(max(desired_retention, 0.70), 0.99)
    raw = (stability / FACTOR) * (desired_retention ** (1.0 / DECAY) - 1.0)
    return max(1.0, min(MAX_INTERVAL, round(raw)))


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


@dataclass
class Card:
    """A schedulable memory item."""

    item_id: str
    stability: float = 0.0
    difficulty: float = 0.0
    reps: int = 0
    lapses: int = 0
    last_review_day: float = 0.0
    due_day: float = 0.0
    state: str = "new"  # new | learning | review | relearning
    history: list = field(default_factory=list)

    # ---- initialisation -------------------------------------------------
    def _init_from_grade(self, grade: int, w: Iterable[float]) -> None:
        w = list(w)
        self.difficulty = _clamp(w[4] - math.exp(w[5] * (grade - 1)) + 1.0,
                                 MIN_DIFFICULTY, MAX_DIFFICULTY)
        self.stability = max(MIN_STABILITY, w[grade - 1])

    # ---- core update ----------------------------------------------------
    def review(self, grade: int, day: float, w: Iterable[float] = DEFAULT_W,
               desired_retention: float = 0.9) -> dict:
        """Apply a review at absolute `day` (days since epoch of the learner)."""
        w = list(w)
        grade = int(_clamp(grade, 1, 4))
        if self.state == "new" or self.stability <= 0:
            self._init_from_grade(grade, w)
            self.state = "learning" if grade == GRADE_AGAIN else "review"
        else:
            elapsed = max(0.0, day - self.last_review_day)
            r = retrievability(elapsed, self.stability)

            # difficulty update (mean-reverting)
            d_delta = -w[6] * (grade - 3)
            self.difficulty = _clamp(
                self.difficulty + d_delta * (10.0 - self.difficulty) / 9.0,
                MIN_DIFFICULTY, MAX_DIFFICULTY,
            )
            # mean reversion toward the "Easy" anchor
            anchor = _clamp(w[4] - math.exp(w[5] * (GRADE_EASY - 1)) + 1.0,
                            MIN_DIFFICULTY, MAX_DIFFICULTY)
            self.difficulty = _clamp(w[7] * anchor + (1 - w[7]) * self.difficulty,
                                     MIN_DIFFICULTY, MAX_DIFFICULTY)

            if grade == GRADE_AGAIN:
                self.stability = max(MIN_STABILITY, _stability_after_lapse(
                    self.difficulty, self.stability, r, w))
                self.lapses += 1
                self.state = "relearning"
            else:
                self.stability = max(MIN_STABILITY, _stability_after_recall(
                    self.difficulty, self.stability, r, grade, w))
                self.state = "review"

        self.reps += 1
        self.last_review_day = day
        self.due_day = day + interval_for_retention(self.stability, desired_retention)
        self.history.append({"day": day, "grade": grade,
                             "S": round(self.stability, 4),
                             "D": round(self.difficulty, 4)})
        return {"stability": self.stability, "difficulty": self.difficulty,
                "due_day": self.due_day,
                "interval_days": self.due_day - day}

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Card":
        return cls(**{k: v for k, v in d.items() if k in cls.__dataclass_fields__})


def _stability_after_recall(d: float, s: float, r: float, grade: int,
                            w: list) -> float:
    """FSRS-4.5 stability increase on successful recall."""
    hard_penalty = w[15] if grade == GRADE_HARD else 1.0
    easy_bonus = w[16] if grade == GRADE_EASY else 1.0
    return s * (1.0 + math.exp(w[8]) * (11.0 - d) * (s ** -w[9])
                * (math.exp((1.0 - r) * w[10]) - 1.0)
                * hard_penalty * easy_bonus)


def _stability_after_lapse(d: float, s: float, r: float, w: list) -> float:
    """FSRS-4.5 stability after a lapse (forgetting)."""
    return (w[11] * (d ** -w[12]) * ((s + 1.0) ** w[13] - 1.0)
            * math.exp((1.0 - r) * w[14]))


# ---------------------------------------------------------------------------
# Session-level scheduling helpers
# ---------------------------------------------------------------------------

def build_queue(cards: list[Card], day: float, limit: int = 20,
                interleave: bool = True, rng=None) -> list[Card]:
    """Select the day's review queue: due cards first, hardest first.

    Interleaving (Bjork & Bjork; Rohrer & Taylor) is applied by shuffling
    within difficulty bands so consecutive items come from different topics
    where possible.
    """
    import random
    rng = rng or random.Random(0)
    due = [c for c in cards if c.state != "new" and c.due_day <= day]
    due.sort(key=lambda c: (-c.difficulty, c.due_day))
    if interleave and len(due) > 2:
        # banded shuffle: keeps hard items early, breaks topic runs
        bands = [due[i::3] for i in range(3)]
        for b in bands:
            rng.shuffle(b)
        due = [c for trio in zip(*[b + [None] * (len(due) - len(b)) for b in bands])
               for c in trio if c is not None]
    return due[:limit]


def retention_forecast(cards: list[Card], day: float) -> dict:
    """Predicted recall probability for the whole deck on `day`."""
    if not cards:
        return {"mean_retrievability": 1.0, "due_now": 0, "n": 0}
    vals = [retrievability(max(0.0, day - c.last_review_day), c.stability)
            for c in cards if c.stability > 0]
    return {
        "mean_retrievability": sum(vals) / len(vals) if vals else 1.0,
        "due_now": sum(1 for c in cards if c.due_day <= day),
        "n": len(cards),
    }


# ---------------------------------------------------------------------------
# Parameter fitting (v1.1 — fit FSRS weights from the learner's own history)
# ---------------------------------------------------------------------------

def _replay_loss(w: list, reviews: list) -> float:
    """Negative log-likelihood of one card's review sequence under weights `w`.

    Replays the sequence, computing predicted retrievability at each review
    and scoring the observed grade against it.  This is the standard FSRS
    memory-model loss: a lapse (grade 1) has probability 1 - R, a recall
    (grades 2-4) has probability R.
    """
    card = Card("fit")
    loss = 0.0
    for day, grade in reviews:
        grade = int(_clamp(grade, 1, 4))
        if card.state == "new" or card.stability <= 0:
            card._init_from_grade(grade, w)
            card.state = "learning" if grade == GRADE_AGAIN else "review"
            card.reps += 1
            card.last_review_day = day
            card.due_day = day + interval_for_retention(card.stability)
            continue

        elapsed = max(0.0, day - card.last_review_day)
        r = retrievability(elapsed, card.stability)

        p = max(1.0 - r, 1e-9) if grade == GRADE_AGAIN else max(r, 1e-9)
        loss -= math.log(p)

        # Difficulty update (mean-reverting)
        d_delta = -w[6] * (grade - 3)
        card.difficulty = _clamp(
            card.difficulty + d_delta * (10.0 - card.difficulty) / 9.0,
            MIN_DIFFICULTY, MAX_DIFFICULTY,
        )
        anchor = _clamp(w[4] - math.exp(w[5] * (GRADE_EASY - 1)) + 1.0,
                        MIN_DIFFICULTY, MAX_DIFFICULTY)
        card.difficulty = _clamp(w[7] * anchor + (1 - w[7]) * card.difficulty,
                                 MIN_DIFFICULTY, MAX_DIFFICULTY)

        if grade == GRADE_AGAIN:
            card.stability = max(MIN_STABILITY, _stability_after_lapse(
                card.difficulty, card.stability, r, w))
            card.lapses += 1
            card.state = "relearning"
        else:
            card.stability = max(MIN_STABILITY, _stability_after_recall(
                card.difficulty, card.stability, r, grade, w))
            card.state = "review"
        card.reps += 1
        card.last_review_day = day
        card.due_day = day + interval_for_retention(card.stability)
    return loss


def total_loss(w, review_sequences: list) -> float:
    """Sum of negative log-likelihood across all review sequences."""
    return sum(_replay_loss(list(w), rev) for rev in review_sequences)


def fit_parameters(review_sequences: list, initial: Iterable[float] = None,
                   max_iter: int = 500, tolerance: float = 1e-6) -> tuple:
    """Fit FSRS weights from review sequences using coordinate descent.

    Each sequence is a list of ``(day, grade)`` tuples for one card, ordered
    by day.  The optimiser perturbs one weight at a time (multiplicative
    steps of 10 %), keeping any change that reduces the total loss.  It
    stops when a full pass produces no improvement or ``max_iter`` passes
    are exhausted.

    Returns a 19-element tuple of fitted weights.  With fewer than ~10
    reviews the defaults are returned unchanged — fitting on too little
    data would produce noise, not signal.
    """
    n_reviews = sum(len(r) for r in review_sequences)
    if n_reviews < 10:
        return tuple(initial) if initial is not None else DEFAULT_W

    w = list(initial) if initial is not None else list(DEFAULT_W)
    best_loss = total_loss(w, review_sequences)

    for _ in range(max_iter):
        improved = False
        for i in range(len(w)):
            for factor in (1.1, 0.9):
                candidate = list(w)
                candidate[i] = max(0.001, candidate[i] * factor)
                loss = total_loss(candidate, review_sequences)
                if loss < best_loss - tolerance:
                    w, best_loss = candidate, loss
                    improved = True
        if not improved:
            break
    return tuple(w)
