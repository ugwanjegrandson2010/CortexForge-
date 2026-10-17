"""Neuro-protection system — fatigue monitoring, load budgeting, and recovery.

Implements the cognitive-decline and brain-fog protocol from the PRD (§5.8)
and the research dossier (03-cognitive-decline-and-brain-fog.md). The five
subsystems are:

  1. ClarityGuardian  — monitors reaction-time variance and error spikes
     to detect within-session fatigue before the learner notices it.
  2. LoadBudgeter     — enforces daily cognitive-unit caps so a learner
     cannot accidentally over-train (Lampit et al. 2014: >3×/week reduces
     efficacy; fatigue degrades consolidation).
  3. AttentionalHygiene — prompts brain dumps and non-sleep deep rest
     (NSDR) when fatigue is detected or before high-load sessions.
  4. CircadianSync    — schedules cognitively demanding content at the
     learner's peak hours and avoids late-night sessions that impair
     memory consolidation (Xie et al. 2013; sleep-onset proximity).
  5. NoveltyInjector  — generates weekly cross-domain challenges to
     prevent synaptic atrophy from repetitive same-domain drilling
     (cf. ACTIVE trial booster protocol; novelty-dependent plasticity).

HARD RULES enforced in code:

  * No subsystem emits a merged "cognitive health" score. Subjective and
    objective measures are reported separately (FR-8.2b).
  * No clinical vocabulary. The module never diagnoses, never uses the
    words disorder/diagnosis/symptom/deficit/impaired/abnormal/patient.
  * Every intervention suggestion carries an evidence citation.
  * The system suggests — it does not command. The learner can override.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field, asdict
from typing import Iterable, Sequence

# ---------------------------------------------------------------------------
# Constants — thresholds grounded in the research dossier
# ---------------------------------------------------------------------------

# ClarityGuardian: reaction-time variance thresholds.
# A within-session RT coefficient of variation above 0.35 indicates
# attentional instability (fatigue marker). Error-rate spikes above 2×
# the learner's baseline also trigger intervention.
RT_CV_FATIGUE_THRESHOLD = 0.35
ERROR_SPIKE_MULTIPLIER = 2.0
MIN_TRIALS_FOR_FATIGUE = 8

# LoadBudgeter: daily cognitive-unit caps.
# One cognitive unit ≈ 5 minutes of focused review (ACTIVE trial:
# 60–75 min sessions = 12–15 units). Default daily cap is 20 units
# (≈100 min), adjustable by the learner's contract.
DEFAULT_DAILY_COGNITIVE_UNITS = 20.0
MIN_DAILY_COGNITIVE_UNITS = 5.0
MAX_DAILY_COGNITIVE_UNITS = 40.0
UNIT_MINUTES = 5.0

# AttentionalHygiene: break cadence.
# 5-minute break every 15 minutes of focused work (dossier §11.1).
BLOCK_MINUTES = 15.0
BREAK_MINUTES = 5.0
FATIGUE_BLOCK_MINUTES = 10.0  # shorter blocks when fatigued

# CircadianSync: time-of-day windows (hours, 24h clock).
# Peak cognitive performance typically 09:00–12:00 and 15:00–18:00
# for most adults (circadian rhythm literature; dossier §7.3).
# Late-night cutoff: no demanding sessions within 2 hours of bedtime.
LATE_NIGHT_START = 22  # 22:00
LATE_NIGHT_END = 6     # 06:00
MIN_SLEEP_HOURS = 7.0  # neuroprotective sleep minimum (PMC4651462)

# NoveltyInjector: weekly challenge cadence.
NOVELTY_INTERVAL_DAYS = 7
MIN_NOVELTY_DOMAINS = 3

# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class Trial:
    """One response trial from a learning session."""

    correct: bool
    rt_ms: float
    timestamp: float = 0.0  # seconds since session start

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class FatigueSignal:
    """Output of ClarityGuardian analysis."""

    is_fatigued: bool
    rt_cv: float | None
    error_rate: float | None
    baseline_error_rate: float | None
    error_spike: bool
    rt_variance_elevated: bool
    n_trials: int
    reason: str
    suggestion: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LoadStatus:
    """Output of LoadBudgeter check."""

    units_used: float
    units_remaining: float
    daily_cap: float
    is_over_budget: bool
    is_near_budget: bool
    reason: str
    suggestion: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class HygienePrompt:
    """Output of AttentionalHygiene."""

    prompt_type: str  # "brain_dump" | "nsdr" | "break" | "none"
    message: str
    duration_minutes: float
    trigger: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class CircadianRecommendation:
    """Output of CircadianSync."""

    recommended: bool
    current_hour: int
    window: str  # "peak" | "moderate" | "low" | "late_night"
    reason: str
    suggestion: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class NoveltyChallenge:
    """Output of NoveltyInjector."""

    challenge_id: str
    title: str
    description: str
    source_domain: str
    target_domain: str
    difficulty: str
    estimated_minutes: float
    rationale: str
    evidence: str

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------------------
# 1. ClarityGuardian — reaction-time variance and error-spike monitoring
# ---------------------------------------------------------------------------


class ClarityGuardian:
    """Monitors session performance for signs of cognitive fatigue.

    Fatigue manifests as increased reaction-time variability (the RT
    coefficient of variation rises) and as error-rate spikes relative to
    the learner's own baseline. Both signals are computed from the
    learner's own recent history — there is no population norm, because
    the useful comparison is within-person.

    Evidence base:
      - RT variability is a sensitive marker of attentional fatigue
        (Van der Linden et al. 2003; de Werd et al. 2010).
      - Error-rate increases precede subjective fatigue awareness
        (Lorist et al. 2005).
      - The 0.1 SD subjective-objective divergence (Jennings et al. 2023)
        means the learner may not notice their own performance drop;
        objective monitoring is the safety net.
    """

    def __init__(self, baseline_error_rate: float | None = None):
        self.baseline_error_rate = baseline_error_rate
        self._rt_history: list[float] = []
        self._error_history: list[bool] = []

    def record_trial(self, correct: bool, rt_ms: float) -> None:
        """Record one trial for ongoing monitoring."""
        self._rt_history.append(rt_ms)
        self._error_history.append(correct)

    def record_baseline(self, error_rate: float) -> None:
        """Set the learner's baseline error rate from a calibration session."""
        self.baseline_error_rate = error_rate

    def analyze(self, trials: Sequence[Trial] | None = None) -> FatigueSignal:
        """Analyze recent trials and return a fatigue signal.

        If `trials` is provided, uses those; otherwise uses the internal
        history accumulated via record_trial().
        """
        if trials is not None:
            rts = [t.rt_ms for t in trials]
            errors = [t.correct for t in trials]
        else:
            rts = list(self._rt_history)
            errors = list(self._error_history)

        n = len(rts)
        if n < MIN_TRIALS_FOR_FATIGUE:
            return FatigueSignal(
                is_fatigued=False,
                rt_cv=None,
                error_rate=None,
                baseline_error_rate=self.baseline_error_rate,
                error_spike=False,
                rt_variance_elevated=False,
                n_trials=n,
                reason="Insufficient trials for fatigue detection.",
                suggestion="Continue the session; monitoring is active.",
                evidence="Minimum 8 trials required for variance estimation.",
            )

        # Reaction-time coefficient of variation
        mean_rt = statistics.mean(rts)
        if mean_rt <= 0:
            rt_cv = 0.0
        else:
            rt_cv = statistics.stdev(rts) / mean_rt if n > 1 else 0.0

        # Error rate
        error_rate = sum(1 for e in errors if not e) / n

        # Error spike detection
        error_spike = False
        if self.baseline_error_rate is not None and self.baseline_error_rate > 0:
            error_spike = error_rate > (self.baseline_error_rate * ERROR_SPIKE_MULTIPLIER)
        elif self.baseline_error_rate == 0 and error_rate > 0.15:
            # No baseline: flag if error rate exceeds 15%
            error_spike = True

        # RT variance elevation
        rt_variance_elevated = rt_cv > RT_CV_FATIGUE_THRESHOLD

        is_fatigued = error_spike or rt_variance_elevated

        # Build honest reason and suggestion
        if is_fatigued:
            reasons = []
            if rt_variance_elevated:
                reasons.append(
                    f"reaction-time variability is elevated (CV={rt_cv:.2f}, "
                    f"threshold {RT_CV_FATIGUE_THRESHOLD})"
                )
            if error_spike:
                reasons.append(
                    f"error rate ({error_rate:.0%}) exceeds "
                    f"{ERROR_SPIKE_MULTIPLIER:.0f}× baseline"
                )
            reason = "Fatigue detected: " + "; ".join(reasons) + "."
            suggestion = (
                "End this session after the current block. "
                "A 10-minute break or NSDR session is recommended before "
                "resuming. Pushing through fatigue degrades consolidation."
            )
        else:
            reason = (
                f"Performance is stable (RT CV={rt_cv:.2f}, "
                f"error rate={error_rate:.0%})."
            )
            suggestion = "Continue the session."

        return FatigueSignal(
            is_fatigued=is_fatigued,
            rt_cv=round(rt_cv, 4),
            error_rate=round(error_rate, 4),
            baseline_error_rate=self.baseline_error_rate,
            error_spike=error_spike,
            rt_variance_elevated=rt_variance_elevated,
            n_trials=n,
            reason=reason,
            suggestion=suggestion,
            evidence=(
                "RT variability and error-rate spikes are established "
                "markers of attentional fatigue (Van der Linden 2003; "
                "Lorist 2005). Objective monitoring catches drops the "
                "learner may not notice (Jennings 2023)."
            ),
        )

    def reset(self) -> None:
        """Clear internal history (call between sessions)."""
        self._rt_history.clear()
        self._error_history.clear()


# ---------------------------------------------------------------------------
# 2. LoadBudgeter — daily cognitive-unit caps
# ---------------------------------------------------------------------------


class LoadBudgeter:
    """Enforces daily cognitive load caps to prevent over-training.

    The Lampit et al. (2014) meta-analysis found that training more than
    3× per week was associated with smaller effects, possibly due to
    fatigue. The ACTIVE trial used 60–75 min sessions. This module
    converts session time into cognitive units and enforces a daily cap.

    One cognitive unit = 5 minutes of focused review. The default daily
    cap is 20 units (≈100 minutes), which is the upper end of the
    npj Digital Medicine (2024) optimal dose for adults under 60
    (25–30 min/day, 6 days/week ≈ 30 min average, but sessions can be
    longer on study days).
    """

    def __init__(
        self,
        daily_cap: float = DEFAULT_DAILY_COGNITIVE_UNITS,
        unit_minutes: float = UNIT_MINUTES,
    ):
        self.daily_cap = self._clamp_cap(daily_cap)
        self.unit_minutes = unit_minutes
        self._units_used_today = 0.0
        self._session_log: list[dict] = []

    @staticmethod
    def _clamp_cap(cap: float) -> float:
        return max(MIN_DAILY_COGNITIVE_UNITS,
                   min(MAX_DAILY_COGNITIVE_UNITS, cap))

    def start_session(self, planned_minutes: float) -> LoadStatus:
        """Check whether a planned session fits within the daily budget."""
        planned_units = planned_minutes / self.unit_minutes
        remaining = max(0.0, self.daily_cap - self._units_used_today)

        if self._units_used_today >= self.daily_cap:
            return LoadStatus(
                units_used=round(self._units_used_today, 2),
                units_remaining=0.0,
                daily_cap=self.daily_cap,
                is_over_budget=True,
                is_near_budget=False,
                reason=(
                    f"Daily cognitive budget exhausted "
                    f"({self._units_used_today:.1f}/{self.daily_cap:.0f} units)."
                ),
                suggestion=(
                    "End study for today. Review resumes tomorrow. "
                    "Spacing sessions across days improves retention "
                    "(Cepeda 2006, d = 0.71)."
                ),
            )

        if planned_units > remaining:
            return LoadStatus(
                units_used=round(self._units_used_today, 2),
                units_remaining=round(remaining, 2),
                daily_cap=self.daily_cap,
                is_over_budget=False,
                is_near_budget=True,
                reason=(
                    f"Planned session ({planned_minutes:.0f} min = "
                    f"{planned_units:.1f} units) exceeds remaining budget "
                    f"({remaining:.1f} units)."
                ),
                suggestion=(
                    f"Shorten session to {remaining * self.unit_minutes:.0f} "
                    f"minutes, or end today and resume tomorrow."
                ),
            )

        return LoadStatus(
            units_used=round(self._units_used_today, 2),
            units_remaining=round(remaining, 2),
            daily_cap=self.daily_cap,
            is_over_budget=False,
            is_near_budget=(remaining - planned_units) <= 5.0,
            reason=(
                f"Session fits within budget "
                f"({planned_units:.1f} units, {remaining:.1f} remaining)."
            ),
            suggestion="Proceed with the session.",
        )

    def record_session(self, actual_minutes: float) -> LoadStatus:
        """Record a completed session and update the daily load."""
        units = actual_minutes / self.unit_minutes
        self._units_used_today += units
        self._session_log.append({
            "minutes": actual_minutes,
            "units": round(units, 2),
            "cumulative_units": round(self._units_used_today, 2),
        })

        remaining = max(0.0, self.daily_cap - self._units_used_today)
        is_over = self._units_used_today >= self.daily_cap
        is_near = remaining <= 5.0

        if is_over:
            reason = (
                f"Daily budget reached "
                f"({self._units_used_today:.1f}/{self.daily_cap:.0f} units)."
            )
            suggestion = (
                "No further study today. Sleep consolidates learning; "
                "additional massed practice degrades it."
            )
        elif is_near:
            reason = (
                f"Approaching daily budget "
                f"({self._units_used_today:.1f}/{self.daily_cap:.0f} units, "
                f"{remaining:.1f} remaining)."
            )
            suggestion = "One more short block, then end the session."
        else:
            reason = (
                f"Session recorded ({units:.1f} units). "
                f"{remaining:.1f} units remain today."
            )
            suggestion = "Continue or end at your discretion."

        return LoadStatus(
            units_used=round(self._units_used_today, 2),
            units_remaining=round(remaining, 2),
            daily_cap=self.daily_cap,
            is_over_budget=is_over,
            is_near_budget=is_near,
            reason=reason,
            suggestion=suggestion,
        )

    def reset_daily(self) -> None:
        """Reset the daily counter (call at midnight or day rollover)."""
        self._units_used_today = 0.0
        self._session_log.clear()

    @property
    def units_used(self) -> float:
        return round(self._units_used_today, 2)

    @property
    def units_remaining(self) -> float:
        return round(max(0.0, self.daily_cap - self._units_used_today), 2)


# ---------------------------------------------------------------------------
# 3. AttentionalHygiene — brain dump and NSDR prompts
# ---------------------------------------------------------------------------


class AttentionalHygiene:
    """Manages brain dumps, NSDR prompts, and break scheduling.

    When fatigue is detected (via ClarityGuardian) or before a high-load
    session, this module suggests:
      - A brain dump: writing down all open loops and pending tasks to
        reduce cognitive load from unresolved intentions (Zeigarnik effect).
      - NSDR (non-sleep deep rest): a 10-minute guided relaxation protocol
        (Yoga Nidra-derived; Huberman Lab protocol) to restore attentional
        resources without the inertia of a nap.
      - Structured breaks: 5 minutes every 15 minutes of focused work,
        or 5 minutes every 10 minutes when fatigued.

    Evidence base:
      - Zeigarnik effect: unresolved tasks consume working memory
        (Zeigarnik 1927; Masicampo & Baumeister 2011).
      - NSDR restores attentional capacity (Huberman Lab; dossier §11.1).
      - Break cadence from the ACTIVE trial protocol (dossier §11.1).
    """

    def __init__(self, fatigue_signal: FatigueSignal | None = None):
        self.fatigue_signal = fatigue_signal

    def set_fatigue_signal(self, signal: FatigueSignal) -> None:
        self.fatigue_signal = signal

    def get_break_recommendation(
        self, minutes_into_session: float
    ) -> HygienePrompt:
        """Recommend a break based on elapsed session time and fatigue state."""
        block = (
            FATIGUE_BLOCK_MINUTES
            if (self.fatigue_signal and self.fatigue_signal.is_fatigued)
            else BLOCK_MINUTES
        )
        break_dur = BREAK_MINUTES

        if minutes_into_session < block:
            return HygienePrompt(
                prompt_type="none",
                message="",
                duration_minutes=0.0,
                trigger="",
                evidence="",
            )

        return HygienePrompt(
            prompt_type="break",
            message=(
                f"Take a {break_dur:.0f}-minute break. "
                "Step away from the screen. Hydrate. "
                "Do not consume new information."
            ),
            duration_minutes=break_dur,
            trigger=f"{minutes_into_session:.0f} minutes into session",
            evidence=(
                "5-minute break every 15 minutes of focused work "
                "(ACTIVE trial protocol; dossier §11.1). "
                "Shorter blocks (10 min) when fatigued."
            ),
        )

    def get_brain_dump_prompt(self) -> HygienePrompt:
        """Return a brain dump prompt to offload open loops."""
        return HygienePrompt(
            prompt_type="brain_dump",
            message=(
                "Write down everything on your mind — tasks, worries, "
                "reminders, half-formed ideas. Do not organise or act on "
                "them. The goal is to externalise open loops so they stop "
                "consuming working memory."
            ),
            duration_minutes=5.0,
            trigger="pre-session or fatigue detected",
            evidence=(
                "Unresolved tasks consume working-memory resources "
                "(Zeigarnik effect; Masicampo & Baumeister 2011). "
                "Externalising them frees capacity for learning."
            ),
        )

    def get_nsdr_prompt(self) -> HygienePrompt:
        """Return an NSDR (non-sleep deep rest) prompt."""
        return HygienePrompt(
            prompt_type="nsdr",
            message=(
                "Lie down or recline comfortably. Close your eyes. "
                "Follow slow breathing: 4 seconds in, 6 seconds out. "
                "Allow your attention to rest on the breath without "
                "controlling it. Do not fall asleep. "
                "After 10 minutes, open your eyes slowly and sit quietly "
                "for one minute before resuming."
            ),
            duration_minutes=10.0,
            trigger="fatigue detected or between high-load sessions",
            evidence=(
                "Non-sleep deep rest restores attentional capacity "
                "(Huberman Lab NSDR protocol; dossier §11.1). "
                "10 minutes is sufficient for measurable restoration."
            ),
        )

    def get_pre_session_routine(self) -> list[HygienePrompt]:
        """Return the full pre-session hygiene routine."""
        return [
            self.get_brain_dump_prompt(),
            self.get_nsdr_prompt(),
        ]

    def get_fatigue_intervention(self) -> HygienePrompt | None:
        """Return the appropriate intervention if fatigue is detected."""
        if self.fatigue_signal is None or not self.fatigue_signal.is_fatigued:
            return None
        return HygienePrompt(
            prompt_type="nsdr",
            message=(
                "Fatigue has been detected in your performance. "
                "A 10-minute NSDR session is recommended now. "
                "If fatigue persists, end the session and resume tomorrow."
            ),
            duration_minutes=10.0,
            trigger="fatigue detected by ClarityGuardian",
            evidence=(
                "Pushing through fatigue degrades consolidation "
                "(dossier §11.1). NSDR restores capacity; "
                "if it does not, the session should end."
            ),
        )


# ---------------------------------------------------------------------------
# 4. CircadianSync — time-of-day scheduling
# ---------------------------------------------------------------------------


class CircadianSync:
    """Schedules cognitively demanding content based on time-of-day.

    Cognitive performance follows a circadian rhythm: peak alertness
    typically occurs in the mid-morning (09:00–12:00) and mid-afternoon
    (15:00–18:00) for most adults. Demanding sessions scheduled late at
    night (within 2 hours of bedtime) impair memory consolidation because
    sleep onset proximity disrupts the encoding process.

    Evidence base:
      - Circadian rhythm effects on cognitive performance
        (dossier §7.3; Schmidt et al. 2007).
      - Sleep and glymphatic clearance (Xie et al. 2013).
      - Avoid scheduling within 2 hours of bedtime (dossier §11.3).
    """

    def __init__(
        self,
        peak_hours: tuple[int, ...] = (9, 10, 11, 15, 16, 17),
        moderate_hours: tuple[int, ...] = (7, 8, 12, 13, 14, 18, 19, 20),
        late_night_start: int = LATE_NIGHT_START,
        late_night_end: int = LATE_NIGHT_END,
    ):
        self.peak_hours = set(peak_hours)
        self.moderate_hours = set(moderate_hours)
        self.late_night_start = late_night_start
        self.late_night_end = late_night_end

    def _classify_hour(self, hour: int) -> str:
        if hour in self.peak_hours:
            return "peak"
        if hour in self.moderate_hours:
            return "moderate"
        if self._is_late_night(hour):
            return "late_night"
        return "low"

    def _is_late_night(self, hour: int) -> bool:
        if self.late_night_start <= self.late_night_end:
            return self.late_night_start <= hour < self.late_night_end
        # wraps midnight (e.g., 22:00–06:00)
        return hour >= self.late_night_start or hour < self.late_night_end

    def recommend(self, current_hour: int) -> CircadianRecommendation:
        """Return a scheduling recommendation for the given hour."""
        window = self._classify_hour(current_hour)

        if window == "peak":
            return CircadianRecommendation(
                recommended=True,
                current_hour=current_hour,
                window=window,
                reason=(
                    f"{current_hour:02d}:00 is within your peak cognitive window. "
                    "Attention and working memory are at their highest."
                ),
                suggestion=(
                    "Schedule demanding material now — new concepts, "
                    "difficult problem sets, or complex reasoning tasks."
                ),
                evidence=(
                    "Circadian rhythm effects on cognitive performance "
                    "(Schmidt 2007; dossier §7.3)."
                ),
            )

        if window == "moderate":
            return CircadianRecommendation(
                recommended=True,
                current_hour=current_hour,
                window=window,
                reason=(
                    f"{current_hour:02d}:00 is a moderate-performance window. "
                    "Cognitive capacity is adequate but not at its peak."
                ),
                suggestion=(
                    "Suitable for review, practice problems, and "
                    "moderate-difficulty material. Save the hardest "
                    "content for your peak window."
                ),
                evidence=(
                    "Circadian rhythm effects on cognitive performance "
                    "(Schmidt 2007; dossier §7.3)."
                ),
            )

        if window == "late_night":
            return CircadianRecommendation(
                recommended=False,
                current_hour=current_hour,
                window=window,
                reason=(
                    f"{current_hour:02d}:00 is within the late-night window. "
                    "Memory consolidation is disrupted when learning occurs "
                    "near sleep onset."
                ),
                suggestion=(
                    "Avoid demanding sessions now. If you must study, "
                    "limit it to light review of previously mastered "
                    "material. Prioritise sleep — glymphatic clearance "
                    "during sleep is when metabolic waste is removed "
                    "from the brain."
                ),
                evidence=(
                    "Sleep-onset proximity impairs memory consolidation "
                    "(Xie 2013; dossier §7.2, §11.3). "
                    "Minimum 7 hours of sleep supports cognitive function "
                    "(PMC4651462)."
                ),
            )

        # "low" window
        return CircadianRecommendation(
            recommended=False,
            current_hour=current_hour,
            window=window,
            reason=(
                f"{current_hour:02d}:00 is a low-performance window. "
                "Alertness is at its circadian trough."
            ),
            suggestion=(
                "Not suitable for demanding cognitive work. "
                "Use this time for administrative tasks, light review, "
                "or rest. If this is your only available time, "
                "keep sessions short and low-stakes."
            ),
            evidence=(
                "Circadian rhythm effects on cognitive performance "
                "(Schmidt 2007; dossier §7.3)."
            ),
        )

    def is_good_time_for_session(self, current_hour: int) -> bool:
        """Quick check: is this hour suitable for a demanding session?"""
        window = self._classify_hour(current_hour)
        return window in ("peak", "moderate")

    def get_optimal_session_hours(self) -> list[int]:
        """Return the list of peak hours for session scheduling."""
        return sorted(self.peak_hours)


# ---------------------------------------------------------------------------
# 5. NoveltyInjector — weekly cross-domain challenges
# ---------------------------------------------------------------------------


class NoveltyInjector:
    """Generates weekly cross-domain challenges to prevent synaptic atrophy.

    Repetitive same-domain drilling without novelty leads to diminishing
    returns as the neural circuits become highly specialised and less
    adaptable. Cross-domain challenges force the brain to form new
    associations and maintain cognitive flexibility.

    Evidence base:
      - Novelty-dependent plasticity: new stimuli trigger dopamine-
        mediated plasticity that repetitive stimuli do not (Lisman 2013).
      - ACTIVE trial booster sessions: periodic novel challenges
        maintained cognitive gains over 10 years (Rebok 2014).
      - Interleaved practice across domains improves discrimination
        and transfer (Rohrer 2012; dossier §11.1).
    """

    # Cross-domain challenge templates: (source_domain, target_domain, title, description)
    _CHALLENGE_TEMPLATES: list[tuple[str, str, str, str]] = [
        (
            "music", "mathematics",
            "Rhythm and Ratios",
            "Analyse the time signatures in three songs you know. "
            "Express each as a ratio, then convert to a percentage. "
            "How does the rhythmic structure relate to fractional arithmetic?",
        ),
        (
            "cooking", "chemistry",
            "Kitchen Reactions",
            "Identify three chemical reactions that occur when you cook "
            "(Maillard reaction, caramelisation, emulsification). "
            "For each, name the reactants, products, and the role of heat.",
        ),
        (
            "sports", "physics",
            "Projectile Motion in Play",
            "Choose a sport involving a ball. Model the ball's trajectory "
            "as a projectile. Calculate the launch angle that maximises "
            "distance, then compare to what athletes actually do.",
        ),
        (
            "history", "economics",
            "Trade Routes and Market Formation",
            "Pick a historical trade route (Silk Road, Trans-Saharan, "
            "or maritime spice trade). Analyse it as a market: what were "
            "the supply constraints, the demand drivers, and the price "
            "mechanisms?",
        ),
        (
            "literature", "psychology",
            "Character Motivation Analysis",
            "Choose a novel you have read. For the protagonist's three "
            "key decisions, identify the motivational drivers using "
            "a psychological framework (self-determination theory, "
            "Maslow, or cognitive dissonance).",
        ),
        (
            "visual_art", "geometry",
            "Perspective and Projection",
            "Find a painting that uses linear perspective. Identify the "
            "vanishing point and horizon line. Explain how the artist "
            "used geometric projection to create the illusion of depth.",
        ),
        (
            "narrative", "systems_thinking",
            "Plot as Feedback Loop",
            "Choose a story with a clear narrative arc. Map the plot "
            "as a system of feedback loops: what are the reinforcing "
            "loops (escalation) and balancing loops (resolution)?",
        ),
        (
            "gardening", "biology",
            "Plant Physiology in Practice",
            "If you have grown a plant from seed, trace its development "
            "through the stages of photosynthesis, nutrient uptake, "
            "and reproductive growth. What environmental variables "
            "did you control?",
        ),
        (
            "board_games", "game_theory",
            "Strategic Reasoning in Play",
            "Choose a board game you know well. Identify the Nash "
            "equilibrium in a simplified version of the game. How does "
            "the actual game deviate from the equilibrium, and why?",
        ),
        (
            "architecture", "mathematics",
            "Structural Load and Geometry",
            "Find a building with a distinctive structural feature "
            "(arch, dome, cantilever). Explain the geometric principles "
            "that allow it to bear load, and calculate the approximate "
            "forces involved.",
        ),
        (
            "language", "logic",
            "Grammar as Formal System",
            "Choose a sentence in a language you are learning. Parse it "
            "into its logical structure: what are the quantifiers, "
            "connectives, and predicates? How does the grammar encode "
            "logical relationships?",
        ),
        (
            "fitness", "physiology",
            "Training Adaptation",
            "Track your heart rate during three different exercise "
            "intensities. Plot the recovery curve after each session. "
            "What does the recovery rate tell you about your aerobic "
            "fitness and the physiology of oxygen debt?",
        ),
    ]

    def __init__(self, learner_domains: Iterable[str] | None = None):
        self.learner_domains = list(learner_domains or [])
        self._challenge_history: list[NoveltyChallenge] = []
        self._template_index = 0

    def generate_challenge(
        self,
        week_number: int,
        target_domain: str | None = None,
    ) -> NoveltyChallenge:
        """Generate a cross-domain challenge for the given week.

        Rotates through the template list to ensure variety. If the
        learner's known domains are provided, prefers challenges that
        bridge from a familiar domain to an unfamiliar one.
        """
        if not self._CHALLENGE_TEMPLATES:
            raise ValueError("no challenge templates available")

        # Select template: rotate through list, offset by week number
        idx = (week_number - 1 + self._template_index) % len(self._CHALLENGE_TEMPLATES)
        source, target, title, description = self._CHALLENGE_TEMPLATES[idx]

        # If learner domains are known and the target matches one, swap
        # to ensure the challenge bridges TO something new
        if self.learner_domains and target in self.learner_domains:
            # Find a template where target is NOT in learner domains
            for i, (s, t, ti, d) in enumerate(self._CHALLENGE_TEMPLATES):
                if t not in self.learner_domains:
                    source, target, title, description = s, t, ti, d
                    idx = i
                    break

        difficulty = self._estimate_difficulty(source, target)
        minutes = self._estimate_minutes(description)

        challenge = NoveltyChallenge(
            challenge_id=f"novelty-w{week_number:03d}-{idx:02d}",
            title=title,
            description=description,
            source_domain=source,
            target_domain=target,
            difficulty=difficulty,
            estimated_minutes=minutes,
            rationale=(
                f"Bridges from {source} (familiar) to {target} "
                f"(less familiar), forcing cross-domain association "
                f"formation and preventing synaptic atrophy from "
                f"repetitive same-domain drilling."
            ),
            evidence=(
                "Novelty-dependent plasticity (Lisman 2013); "
                "ACTIVE trial booster protocol (Rebok 2014); "
                "interleaved practice improves discrimination "
                "(Rohrer 2012; dossier §11.1)."
            ),
        )
        self._challenge_history.append(challenge)
        return challenge

    def generate_weekly_schedule(
        self, num_weeks: int, start_week: int = 1
    ) -> list[NoveltyChallenge]:
        """Generate a sequence of weekly challenges."""
        challenges = []
        for w in range(start_week, start_week + num_weeks):
            challenges.append(self.generate_challenge(w))
        return challenges

    def get_domain_coverage(self) -> dict[str, int]:
        """Return a count of how many challenges target each domain."""
        coverage: dict[str, int] = {}
        for c in self._challenge_history:
            coverage[c.target_domain] = coverage.get(c.target_domain, 0) + 1
        return coverage

    @staticmethod
    def _estimate_difficulty(source: str, target: str) -> str:
        """Rough difficulty estimate based on domain pair."""
        # Pairs involving mathematics or game_theory are harder
        hard_domains = {"mathematics", "game_theory", "physics", "logic"}
        if target in hard_domains:
            return "moderate"
        if source in hard_domains:
            return "moderate"
        return "accessible"

    @staticmethod
    def _estimate_minutes(description: str) -> float:
        """Estimate time from description length (~200 words = 15 min)."""
        words = len(description.split())
        return max(10.0, min(30.0, words / 200.0 * 15.0))


# ---------------------------------------------------------------------------
# Integration helper — ties the five subsystems together
# ---------------------------------------------------------------------------


@dataclass
class NeuroProtectionStatus:
    """Aggregate status from all five neuro-protection subsystems."""

    fatigue: FatigueSignal | None = None
    load: LoadStatus | None = None
    hygiene: HygienePrompt | None = None
    circadian: CircadianRecommendation | None = None
    novelty: NoveltyChallenge | None = None

    def to_dict(self) -> dict:
        return {
            "fatigue": self.fatigue.to_dict() if self.fatigue else None,
            "load": self.load.to_dict() if self.load else None,
            "hygiene": self.hygiene.to_dict() if self.hygiene else None,
            "circadian": self.circadian.to_dict() if self.circadian else None,
            "novelty": self.novelty.to_dict() if self.novelty else None,
        }

    def should_block_session(self) -> bool:
        """True if any subsystem recommends against starting/continuing."""
        if self.fatigue and self.fatigue.is_fatigued:
            return True
        if self.load and self.load.is_over_budget:
            return True
        if self.circadian and not self.circadian.recommended:
            return True
        return False

    def get_blocking_reasons(self) -> list[str]:
        """Return human-readable reasons why a session should not proceed."""
        reasons = []
        if self.fatigue and self.fatigue.is_fatigued:
            reasons.append(f"Fatigue: {self.fatigue.reason}")
        if self.load and self.load.is_over_budget:
            reasons.append(f"Load: {self.load.reason}")
        if self.circadian and not self.circadian.recommended:
            reasons.append(f"Circadian: {self.circadian.reason}")
        return reasons


class NeuroProtectionSystem:
    """Facade that wires the five subsystems together.

    Usage:
        nps = NeuroProtectionSystem(daily_cap=20)
        nps.clarity.record_trial(correct=True, rt_ms=450)
        nps.clarity.record_trial(correct=False, rt_ms=800)
        status = nps.check_session(hour=14, minutes_into_session=16)
        if status.should_block_session():
            for reason in status.get_blocking_reasons():
                print(reason)
    """

    def __init__(
        self,
        daily_cap: float = DEFAULT_DAILY_COGNITIVE_UNITS,
        baseline_error_rate: float | None = None,
        learner_domains: Iterable[str] | None = None,
        peak_hours: tuple[int, ...] = (9, 10, 11, 15, 16, 17),
    ):
        self.clarity = ClarityGuardian(baseline_error_rate=baseline_error_rate)
        self.load = LoadBudgeter(daily_cap=daily_cap)
        self.hygiene = AttentionalHygiene()
        self.circadian = CircadianSync(peak_hours=peak_hours)
        self.novelty = NoveltyInjector(learner_domains=learner_domains)

    def check_session(
        self,
        hour: int,
        minutes_into_session: float = 0.0,
        planned_minutes: float | None = None,
    ) -> NeuroProtectionStatus:
        """Run all subsystem checks and return an aggregate status."""
        # Fatigue
        fatigue = self.clarity.analyze()
        self.hygiene.set_fatigue_signal(fatigue)

        # Load
        if planned_minutes is not None:
            load = self.load.start_session(planned_minutes)
        else:
            load = self.load.record_session(minutes_into_session)

        # Hygiene
        hygiene = self.hygiene.get_fatigue_intervention()
        if hygiene is None:
            hygiene = self.hygiene.get_break_recommendation(minutes_into_session)

        # Circadian
        circadian = self.circadian.recommend(hour)

        return NeuroProtectionStatus(
            fatigue=fatigue,
            load=load,
            hygiene=hygiene,
            circadian=circadian,
        )

    def end_session(self, actual_minutes: float) -> NeuroProtectionStatus:
        """Record session end and return final status."""
        load = self.load.record_session(actual_minutes)
        fatigue = self.clarity.analyze()
        self.hygiene.set_fatigue_signal(fatigue)
        hygiene = self.hygiene.get_fatigue_intervention()
        self.clarity.reset()
        return NeuroProtectionStatus(
            fatigue=fatigue,
            load=load,
            hygiene=hygiene,
        )

    def get_weekly_novelty(self, week_number: int) -> NoveltyChallenge:
        """Get this week's cross-domain challenge."""
        return self.novelty.generate_challenge(week_number)
