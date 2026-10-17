"""Bayesian Knowledge Tracing + Item Response Theory + Elo item rating.

All pure Python. Formulas are the standard published ones; see
docs/research/05-question-generation-and-adaptive-learning.md for citations.

BKT (Corbett & Anderson 1994) four parameters per skill:
    p_L0  prior probability of knowing the skill
    p_T   probability of learning (transition) per opportunity
    p_S   probability of slip   (knows it, answers wrong)
    p_G   probability of guess  (does not know it, answers right)

IRT 2PL/3PL:
    P(correct | theta) = c + (1 - c) / (1 + exp(-a * (theta - b)))
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


# ---------------------------------------------------------------------------
# Bayesian Knowledge Tracing
# ---------------------------------------------------------------------------

@dataclass
class BKTParams:
    p_L0: float = 0.20
    p_T: float = 0.15
    p_S: float = 0.10
    p_G: float = 0.20

    def to_dict(self) -> dict:
        return {"p_L0": self.p_L0, "p_T": self.p_T,
                "p_S": self.p_S, "p_G": self.p_G}


class BKTSkill:
    """Tracks mastery probability for one skill."""

    def __init__(self, skill_id: str, params: BKTParams | None = None):
        self.skill_id = skill_id
        self.p = params or BKTParams()
        self.p_known = self.p.p_L0
        self.opportunities = 0
        self.correct = 0
        self.history: list[float] = []

    def update(self, correct: bool) -> float:
        """One BKT step. Returns the posterior P(known) after the observation."""
        k = self.p_known
        if correct:
            num = k * (1.0 - self.p.p_S)
            den = num + (1.0 - k) * self.p.p_G
        else:
            num = k * self.p.p_S
            den = num + (1.0 - k) * (1.0 - self.p.p_G)
        posterior = num / den if den > 0 else k
        # learning transition
        self.p_known = _clamp(posterior + (1.0 - posterior) * self.p.p_T, 1e-6, 1 - 1e-6)
        self.opportunities += 1
        self.correct += 1 if correct else 0
        self.history.append(self.p_known)
        return self.p_known

    @property
    def mastered(self) -> bool:
        return self.p_known >= 0.95

    def predicted_correct(self) -> float:
        """P(correct on next attempt) given current knowledge estimate."""
        k = self.p_known
        return k * (1.0 - self.p.p_S) + (1.0 - k) * self.p.p_G


# ---------------------------------------------------------------------------
# Item Response Theory
# ---------------------------------------------------------------------------

@dataclass
class Item:
    """An item with IRT parameters and an Elo rating."""

    item_id: str
    a: float = 1.0          # discrimination
    b: float = 0.0          # difficulty (logit scale)
    c: float = 0.0          # pseudo-guessing (0 for 2PL)
    elo: float = 1200.0
    n_attempts: int = 0
    n_correct: int = 0
    skill_id: str = ""

    def p_correct(self, theta: float) -> float:
        """3PL item characteristic curve."""
        z = self.a * (theta - self.b)
        return self.c + (1.0 - self.c) / (1.0 + math.exp(-_clamp(z, -30, 30)))

    def information(self, theta: float) -> float:
        """Fisher information — used for maximum-information item selection."""
        p = self.p_correct(theta)
        c = self.c
        if p <= 0 or p >= 1:
            return 0.0
        # 3PL information
        num = (self.a ** 2) * ((p - c) ** 2) * (1.0 - p)
        den = (p * ((1.0 - c) ** 2))
        return num / den if den > 0 else 0.0

    def update_elo(self, correct: bool, k: float = 24.0) -> float:
        """Elo update for item difficulty estimation (Klinkenberg et al. 2011)."""
        expected = 1.0 / (1.0 + 10 ** ((self.elo - 1200.0) / 400.0))
        self.elo += k * ((1.0 if correct else 0.0) - expected)
        self.n_attempts += 1
        self.n_correct += 1 if correct else 0
        return self.elo


def update_theta_mle(theta: float, responses: list[tuple[Item, bool]],
                     lr: float = 0.35, iters: int = 12) -> float:
    """Newton-Raphson MLE update of learner ability from a response set."""
    for _ in range(iters):
        grad = 0.0
        info = 0.0
        for item, correct in responses:
            p = item.p_correct(theta)
            info += item.information(theta)
            if correct:
                grad += item.a * (1.0 - p) * (p - item.c) / max(p, 1e-9)
            else:
                grad -= item.a * p * (p - item.c) / max(1.0 - p, 1e-9)
        if info < 1e-9:
            break
        step = _clamp(grad / info, -lr, lr)
        theta += step
        if abs(step) < 1e-4:
            break
    return _clamp(theta, -4.0, 4.0)


def select_next_item(items: list[Item], theta: float,
                     target_p: float = 0.85,
                     exclude: set[str] | None = None) -> Item | None:
    """Choose the item whose success probability is closest to `target_p`.

    target_p defaults to 0.85 — the error-driven-learning band (Wilson et al.
    2019, Nat. Commun. 10:4646) which maximises learning rate without
    collapsing into frustration. This is the anti-pampering control: the
    learner is kept at ~85% success, never at 100%.
    """
    exclude = exclude or set()
    pool = [i for i in items if i.item_id not in exclude]
    if not pool:
        return None
    return min(pool, key=lambda i: abs(i.p_correct(theta) - target_p))


def calibrate_item(item: Item, responses: list[bool]) -> Item:
    """Rough item calibration: set b from observed p(correct) at known theta."""
    if not responses:
        return item
    p = sum(1 for r in responses if r) / len(responses)
    p = _clamp(p, 0.02, 0.98)
    item.b = -math.log(p / (1.0 - p)) / max(item.a, 0.1)
    return item


# ---------------------------------------------------------------------------
# Calibration of confidence (metacognition)
# ---------------------------------------------------------------------------

def calibration_stats(judgments: list[tuple[float, bool]]) -> dict:
    """Given (confidence 0-1, correct) pairs, return calibration diagnostics.

    Returns Brier score, over/under-confidence bias, and the
    Goodman-Kruskal gamma between confidence and accuracy.
    """
    if not judgments:
        return {"n": 0, "brier": None, "bias": None, "gamma": None}
    brier = sum((c - (1.0 if ok else 0.0)) ** 2 for c, ok in judgments) / len(judgments)
    bias = sum(c for c, _ in judgments) / len(judgments) - \
        sum(1.0 for _, ok in judgments if ok) / len(judgments)

    concordant = discordant = 0
    for i in range(len(judgments)):
        for j in range(i + 1, len(judgments)):
            ci, oi = judgments[i]
            cj, oj = judgments[j]
            if ci == cj or oi == oj:
                continue
            if (ci > cj) == (oi > oj):
                concordant += 1
            else:
                discordant += 1
    gamma = ((concordant - discordant) / (concordant + discordant)
             if (concordant + discordant) else None)
    return {"n": len(judgments), "brier": round(brier, 4),
            "bias": round(bias, 4),
            "gamma": round(gamma, 4) if gamma is not None else None,
            "interpretation": _calibration_label(bias, gamma)}


def _calibration_label(bias: float, gamma: float | None) -> str:
    if bias > 0.15:
        return "overconfident"
    if bias < -0.15:
        return "underconfident"
    if gamma is not None and gamma < 0.2:
        return "poorly_discriminating"
    return "well_calibrated"
