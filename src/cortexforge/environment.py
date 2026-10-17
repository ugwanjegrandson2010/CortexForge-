"""Environment audit and prescription system.

The Mentat/NPALS specification defines an environment audit that covers five
dimensions of the learner's study environment and produces evidence-ranked
prescriptions. This module implements that specification.

Design rules:
  * Every prescription carries an evidence citation from the research
    literature. A prescription without a citation is not emitted.
  * Prescriptions are ranked by evidence-strength x feasibility, so the
    learner is asked to do the most impactful thing first.
  * Each prescription has an if-then plan: a concrete trigger and a concrete
    action, so adherence is observable rather than aspirational.
  * Adherence is tracked over time so the system can see which prescriptions
    are actually being followed and which need adjustment.
  * Re-audit is scheduled monthly and before exams, because environments
    change and prescriptions decay.

Evidence base (see docs/research/):
  * Phone in another room — Ward et al. 2017 (brain drain)
  * Steady ambient noise or silence — Sörqvist 2015 (irrelevant sound effect)
  * Bright, high-CRT light for alert tasks — circadian/norepinephrine
  * Mildly cool temperature (~20-22 C) for alertness
  * Green views/plants for attention restoration — Kaplan 1995
  * Movement breaks restore attention
  * Speech noise disrupts serial/recall processing
  * Lyrics compete in the phonological loop
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field, asdict
from typing import Any

# ---------------------------------------------------------------------------
# Evidence grading (mirrors instruments.py)
# ---------------------------------------------------------------------------

EVIDENCE_STRONG = "strong"
EVIDENCE_MODERATE = "moderate"
EVIDENCE_WEAK = "weak"

# ---------------------------------------------------------------------------
# Evidence library — maps prescription keys to research citations
# ---------------------------------------------------------------------------


@dataclass
class EvidenceEntry:
    """One piece of research evidence backing a prescription."""

    citation: str
    finding: str
    evidence: str  # EVIDENCE_STRONG | EVIDENCE_MODERATE | EVIDENCE_WEAK
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


EVIDENCE_LIBRARY: dict[str, EvidenceEntry] = {
    "phone_in_another_room": EvidenceEntry(
        citation="Ward et al. 2017",
        finding=("The mere presence of a smartphone reduces available "
                 "cognitive capacity, even when the phone is off and the "
                 "owner is not actively using it."),
        evidence=EVIDENCE_STRONG,
        url="https://doi.org/10.1080/02699931.2016.1166045",
    ),
    "steady_ambient_noise": EvidenceEntry(
        citation="Sörqvist 2015",
        finding=("Irrelevant sound — especially speech — disrupts serial "
                 "recall and reading comprehension. Steady, non-speech "
                 "ambient noise or silence is superior for tasks requiring "
                 "working memory."),
        evidence=EVIDENCE_STRONG,
        url="https://doi.org/10.1177/1747021815572343",
    ),
    "bright_light": EvidenceEntry(
        citation="circadian / norepinephrine",
        finding=("Bright, high-correlated-color-temperature light (>5000K) "
                 "increases alertness and reduces sleepiness during "
                 "sustained attention tasks, via norepinephrine release "
                 "and circadian phase-shifting."),
        evidence=EVIDENCE_MODERATE,
    ),
    "cool_temperature": EvidenceEntry(
        citation="Lan et al. 2011 / Seppänen et al. 2006",
        finding=("Mildly cool ambient temperature (~20-22 C) sustains "
                 "alertness and cognitive performance better than warm "
                 "environments (>25 C), which promote drowsiness."),
        evidence=EVIDENCE_MODERATE,
    ),
    "green_view": EvidenceEntry(
        citation="Kaplan 1995",
        finding=("Exposure to natural views and indoor plants restores "
                 "directed attention via Attention Restoration Theory. "
                 "Even a brief view of greenery reduces mental fatigue."),
        evidence=EVIDENCE_MODERATE,
        url="https://doi.org/10.1080/01490409509513058",
    ),
    "movement_breaks": EvidenceEntry(
        citation="Berman et al. 2008 / Oppezzo & Schwartz 2014",
        finding=("Brief physical movement breaks (5-10 min walking) restore "
                 "directed attention and improve creative problem-solving. "
                 "Sedentary sustained attention degrades within 20-30 min."),
        evidence=EVIDENCE_STRONG,
    ),
    "no_speech_noise": EvidenceEntry(
        citation="Sörqvist 2015 / Zeamer & Fox Tree 2013",
        finding=("Speech noise — even unintelligible — disrupts serial "
                 "recall, reading comprehension, and phonological-loop-"
                 "dependent tasks more than non-speech noise of equal "
                 "loudness."),
        evidence=EVIDENCE_STRONG,
    ),
    "no_lyrics": EvidenceEntry(
        citation="Perham & Currie 2014 / Jäncke 2008",
        finding=("Background music with lyrics competes for phonological-"
                 "loop resources and impairs reading comprehension and "
                 "memory encoding. Instrumental music or silence is "
                 "superior for verbal tasks."),
        evidence=EVIDENCE_MODERATE,
    ),
    "consistent_sleep": EvidenceEntry(
        citation="Walker 2017 / Diekelmann & Born 2010",
        finding=("Consistent sleep timing (same wake time daily) stabilises "
                 "circadian phase, improves memory consolidation, and "
                 "sustains next-day attention. Irregular sleep degrades "
                 "learning even when total sleep duration is adequate."),
        evidence=EVIDENCE_STRONG,
    ),
    "deadline_map": EvidenceEntry(
        citation="Ariely & Wertenbroch 2002",
        finding=("External, self-imposed deadlines improve task completion "
                 "and reduce procrastination. A visible deadline map with "
                 "intermediate checkpoints is more effective than a single "
                 "far-future deadline."),
        evidence=EVIDENCE_MODERATE,
    ),
    "materials_ready": EvidenceEntry(
        citation="Dunlosky et al. 2013",
        finding=("Reducing friction to begin studying — having materials "
                 "visible and ready — increases the probability of session "
                 "initiation. Environmental cues trigger habitual behaviour."),
        evidence=EVIDENCE_MODERATE,
    ),
    "social_accountability": EvidenceEntry(
        citation="Wing & Jeffery 1999 / Gollwitzer & Sheeran 2006",
        finding=("Implementation intentions and social commitment devices "
                 "increase follow-through on planned behaviours. A named "
                 "study partner or household member who knows the plan "
                 "doubles adherence."),
        evidence=EVIDENCE_MODERATE,
    ),
    "notification_block": EvidenceEntry(
        citation="Stothart et al. 2015 / Mark et al. 2018",
        finding=("Notifications — even when not checked — capture attention "
                 "and degrade performance on sustained tasks. Blocking "
                 "notifications during study sessions restores available "
                 "attentional capacity."),
        evidence=EVIDENCE_STRONG,
    ),
    "ergonomic_setup": EvidenceEntry(
        citation="Kroemer & Grandjean 2009",
        finding=("Poor ergonomics (screen height, chair support, viewing "
                 "distance) cause physical discomfort that competes for "
                 "attentional resources and shortens sustainable study "
                 "duration."),
        evidence=EVIDENCE_WEAK,
    ),
    "phone_digital_distance": EvidenceEntry(
        citation="Ward et al. 2017",
        finding=("The mere presence of a smartphone reduces available "
                 "cognitive capacity, even when the phone is off and the "
                 "owner is not actively using it. Physical distance from "
                 "the phone restores attentional resources."),
        evidence=EVIDENCE_STRONG,
        url="https://doi.org/10.1080/02699931.2016.1166045",
    ),
}


def get_evidence(key: str) -> EvidenceEntry | None:
    """Return the evidence entry for a prescription key, or None."""
    return EVIDENCE_LIBRARY.get(key)


def evidence_manifest() -> dict:
    """Machine-readable manifest of all evidence entries."""
    return {k: v.to_dict() for k, v in EVIDENCE_LIBRARY.items()}


# ---------------------------------------------------------------------------
# Environment audit — structured intake across five dimensions
# ---------------------------------------------------------------------------


@dataclass
class PhysicalEnvironment:
    """Physical dimension of the study environment."""

    lighting: str = ""            # dim | moderate | bright | very_bright
    noise_sources: list[str] = field(default_factory=list)
    temperature_c: float | None = None
    green_view: bool = False
    has_indoor_plants: bool = False
    ergonomic_setup: str = ""     # poor | adequate | good
    phone_location: str = ""      # on_desk | pocket | another_room | silent_bag
    desk_clutter: str = ""        # heavy | moderate | minimal

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class DigitalEnvironment:
    """Digital dimension of the study environment."""

    notification_load: str = ""   # high | moderate | low
    blocker_available: bool = False
    blocker_active: bool = False
    distraction_sources: list[str] = field(default_factory=list)
    phone_in_reach: bool = True
    social_media_apps_installed: bool = True
    website_blocker_installed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SocialEnvironment:
    """Social dimension of the study environment."""

    study_partners: list[str] = field(default_factory=list)
    household_support: str = ""   # supportive | neutral | disruptive
    quiet_hours_feasible: bool = False
    quiet_hours: str = ""         # e.g. "22:00-07:00"
    social_commitment_device: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class TemporalEnvironment:
    """Temporal dimension of the study environment."""

    sleep_schedule: str = ""      # consistent | somewhat | irregular
    typical_bedtime: str = ""
    typical_wake_time: str = ""
    anchors: list[str] = field(default_factory=list)
    deadline_map_visible: bool = False
    intermediate_checkpoints: bool = False
    exam_date_known: bool = False
    exam_date: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class MaterialsEnvironment:
    """Materials dimension of the study environment."""

    textbook_access: str = ""     # full | partial | none
    calculator_available: bool = False
    stationery_ready: bool = False
    materials_visible: bool = False
    digital_notes_organised: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class EnvironmentAudit:
    """Complete structured intake across all five dimensions."""

    learner_id: str
    created_at: float = field(default_factory=time.time)
    physical: PhysicalEnvironment = field(default_factory=PhysicalEnvironment)
    digital: DigitalEnvironment = field(default_factory=DigitalEnvironment)
    social: SocialEnvironment = field(default_factory=SocialEnvironment)
    temporal: TemporalEnvironment = field(default_factory=TemporalEnvironment)
    materials: MaterialsEnvironment = field(default_factory=MaterialsEnvironment)

    def to_dict(self) -> dict:
        return {
            "learner_id": self.learner_id,
            "created_at": self.created_at,
            "physical": self.physical.to_dict(),
            "digital": self.digital.to_dict(),
            "social": self.social.to_dict(),
            "temporal": self.temporal.to_dict(),
            "materials": self.materials.to_dict(),
        }

    def dimension_summary(self) -> dict[str, dict]:
        """Return a per-dimension summary of issues detected."""
        return {
            "physical": self._physical_issues(),
            "digital": self._digital_issues(),
            "social": self._social_issues(),
            "temporal": self._temporal_issues(),
            "materials": self._materials_issues(),
        }

    def _physical_issues(self) -> dict:
        issues = []
        p = self.physical
        if p.lighting in ("dim", "moderate"):
            issues.append("lighting too dim for alert tasks")
        if p.noise_sources:
            issues.append(f"noise sources: {', '.join(p.noise_sources)}")
        if p.temperature_c is not None and p.temperature_c > 24:
            issues.append(f"temperature {p.temperature_c}C too warm for alertness")
        if not p.green_view and not p.has_indoor_plants:
            issues.append("no green view or indoor plants")
        if p.ergonomic_setup == "poor":
            issues.append("poor ergonomic setup")
        if p.phone_location in ("on_desk", "pocket"):
            issues.append(f"phone within reach ({p.phone_location})")
        if p.desk_clutter == "heavy":
            issues.append("heavy desk clutter")
        return {"issues": issues, "count": len(issues)}

    def _digital_issues(self) -> dict:
        issues = []
        d = self.digital
        if d.notification_load == "high":
            issues.append("high notification load")
        if not d.blocker_available:
            issues.append("no website blocker available")
        elif not d.blocker_active:
            issues.append("blocker available but not active")
        if d.phone_in_reach:
            issues.append("phone within digital reach")
        if d.social_media_apps_installed and not d.blocker_active:
            issues.append("social media apps unblocked")
        if d.distraction_sources:
            issues.append(f"distraction sources: {', '.join(d.distraction_sources)}")
        return {"issues": issues, "count": len(issues)}

    def _social_issues(self) -> dict:
        issues = []
        s = self.social
        if not s.study_partners:
            issues.append("no study partners")
        if s.household_support == "disruptive":
            issues.append("disruptive household environment")
        if not s.quiet_hours_feasible:
            issues.append("quiet hours not feasible")
        if not s.social_commitment_device:
            issues.append("no social commitment device")
        return {"issues": issues, "count": len(issues)}

    def _temporal_issues(self) -> dict:
        issues = []
        t = self.temporal
        if t.sleep_schedule == "irregular":
            issues.append("irregular sleep schedule")
        if not t.deadline_map_visible:
            issues.append("deadline map not visible")
        if not t.intermediate_checkpoints:
            issues.append("no intermediate checkpoints")
        if t.exam_date_known and not t.deadline_map_visible:
            issues.append("exam date known but not mapped")
        return {"issues": issues, "count": len(issues)}

    def _materials_issues(self) -> dict:
        issues = []
        m = self.materials
        if m.textbook_access == "none":
            issues.append("no textbook access")
        elif m.textbook_access == "partial":
            issues.append("partial textbook access")
        if not m.calculator_available:
            issues.append("calculator not available")
        if not m.stationery_ready:
            issues.append("stationery not ready")
        if not m.materials_visible:
            issues.append("materials not visible from desk")
        return {"issues": issues, "count": len(issues)}


# ---------------------------------------------------------------------------
# Prescription generator — evidence-ranked prescriptions with if-then plans
# ---------------------------------------------------------------------------


@dataclass
class Prescription:
    """One ranked prescription with an if-then plan and evidence citation."""

    rank: int
    key: str
    title: str
    if_condition: str
    then_action: str
    evidence_citation: str
    evidence_finding: str
    evidence_strength: str
    feasibility: float  # 0.0-1.0
    impact_score: float  # evidence_strength * feasibility
    dimension: str      # physical | digital | social | temporal | materials

    def to_dict(self) -> dict:
        return asdict(self)


class PrescriptionGenerator:
    """Generate 3-5 ranked prescriptions from an EnvironmentAudit.

    Each prescription is ranked by evidence_strength x feasibility, so the
    learner is asked to do the most impactful, most doable thing first.
    """

    def __init__(self, audit: EnvironmentAudit):
        self.audit = audit

    def generate(self, max_prescriptions: int = 5) -> list[Prescription]:
        """Generate ranked prescriptions from the audit.

        Returns 3-5 prescriptions sorted by impact_score (descending).
        """
        candidates: list[Prescription] = []
        candidates.extend(self._physical_prescriptions())
        candidates.extend(self._digital_prescriptions())
        candidates.extend(self._social_prescriptions())
        candidates.extend(self._temporal_prescriptions())
        candidates.extend(self._materials_prescriptions())

        # Sort by impact score descending
        candidates.sort(key=lambda p: p.impact_score, reverse=True)

        # Assign ranks and return top N
        ranked = []
        for i, p in enumerate(candidates[:max_prescriptions], 1):
            p.rank = i
            ranked.append(p)
        return ranked

    def _physical_prescriptions(self) -> list[Prescription]:
        p = self.audit.physical
        out = []

        # Phone in another room
        if p.phone_location in ("on_desk", "pocket"):
            ev = EVIDENCE_LIBRARY["phone_in_another_room"]
            out.append(Prescription(
                rank=0, key="phone_in_another_room",
                title="Move your phone to another room",
                if_condition=("If your phone is on your desk or in your pocket "
                              "when you sit down to study"),
                then_action=("then place it in another room, in a drawer or bag, "
                             "out of sight and out of reach for the duration of "
                             "the session"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.95,
                impact_score=self._score(ev.evidence, 0.95),
                dimension="physical",
            ))

        # Steady ambient noise or silence
        has_speech_noise = any(
            s in ("speech", "conversation", "tv", "radio", "music_with_lyrics")
            for s in p.noise_sources
        )
        if has_speech_noise:
            ev = EVIDENCE_LIBRARY["steady_ambient_noise"]
            out.append(Prescription(
                rank=0, key="steady_ambient_noise",
                title="Replace speech noise with steady ambient sound or silence",
                if_condition=("If your study space has speech noise (conversation, "
                              "TV, radio, or music with lyrics) or is unpredictably "
                              "noisy"),
                then_action=("then switch to steady non-speech ambient noise (white "
                             "noise, rain, instrumental music) or silence. Use "
                             "noise-cancelling headphones if the source cannot be "
                             "removed"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.80,
                impact_score=self._score(ev.evidence, 0.80),
                dimension="physical",
            ))

        # Bright light
        if p.lighting in ("dim", "moderate"):
            ev = EVIDENCE_LIBRARY["bright_light"]
            out.append(Prescription(
                rank=0, key="bright_light",
                title="Increase light intensity for alert tasks",
                if_condition=("If your study space is dim or moderately lit and you "
                              "are doing alert, attention-demanding work"),
                then_action=("then increase light to bright, high-CCT (>5000K) — "
                             "open blinds, add a daylight lamp, or move to a "
                             "brighter space"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.85,
                impact_score=self._score(ev.evidence, 0.85),
                dimension="physical",
            ))

        # Cool temperature
        if p.temperature_c is not None and p.temperature_c > 24:
            ev = EVIDENCE_LIBRARY["cool_temperature"]
            out.append(Prescription(
                rank=0, key="cool_temperature",
                title="Cool the room to 20-22 C",
                if_condition=("If your study room is above 24 C"),
                then_action=("then open a window, use a fan, or lower the "
                             "thermostat to 20-22 C. If cooling is not possible, "
                             "move to a cooler room"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.70,
                impact_score=self._score(ev.evidence, 0.70),
                dimension="physical",
            ))

        # Green view
        if not p.green_view and not p.has_indoor_plants:
            ev = EVIDENCE_LIBRARY["green_view"]
            out.append(Prescription(
                rank=0, key="green_view",
                title="Add a green view or indoor plant",
                if_condition=("If your desk has no view of greenery and no indoor "
                              "plants"),
                then_action=("then place a small plant on your desk or reposition "
                             "your desk to face a window with a view of trees or "
                             "grass. If neither is possible, use a nature photograph "
                             "or screensaver"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.75,
                impact_score=self._score(ev.evidence, 0.75),
                dimension="physical",
            ))

        # Movement breaks
        ev = EVIDENCE_LIBRARY["movement_breaks"]
        out.append(Prescription(
            rank=0, key="movement_breaks",
            title="Take a 5-10 minute movement break every 25-30 minutes",
            if_condition=("If you have been studying continuously for more than "
                          "25-30 minutes"),
            then_action=("then stand up, walk for 5-10 minutes, ideally outside "
                         "or at least away from the desk. Do not check your phone "
                         "during the break"),
            evidence_citation=ev.citation,
            evidence_finding=ev.finding,
            evidence_strength=ev.evidence,
            feasibility=0.90,
            impact_score=self._score(ev.evidence, 0.90),
            dimension="physical",
        ))

        # No lyrics
        has_lyrics = "music_with_lyrics" in p.noise_sources
        if has_lyrics:
            ev = EVIDENCE_LIBRARY["no_lyrics"]
            out.append(Prescription(
                rank=0, key="no_lyrics",
                title="Remove lyrics from study music",
                if_condition=("If you study with music that has lyrics"),
                then_action=("then switch to instrumental music, ambient sound, or "
                             "silence. Lyrics compete for phonological-loop resources "
                             "that your verbal tasks need"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.90,
                impact_score=self._score(ev.evidence, 0.90),
                dimension="physical",
            ))

        # Ergonomic setup
        if p.ergonomic_setup == "poor":
            ev = EVIDENCE_LIBRARY["ergonomic_setup"]
            out.append(Prescription(
                rank=0, key="ergonomic_setup",
                title="Fix ergonomic setup",
                if_condition=("If your chair, screen height, or viewing distance "
                              "causes discomfort during study"),
                then_action=("then adjust so the top of your screen is at eye level, "
                             "your feet rest flat on the floor, and your lower back "
                             "is supported. Use a cushion or footrest if needed"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.60,
                impact_score=self._score(ev.evidence, 0.60),
                dimension="physical",
            ))

        return out

    def _digital_prescriptions(self) -> list[Prescription]:
        d = self.audit.digital
        out = []

        # Notification block
        if d.notification_load == "high" or not d.blocker_active:
            ev = EVIDENCE_LIBRARY["notification_block"]
            out.append(Prescription(
                rank=0, key="notification_block",
                title="Block notifications during study sessions",
                if_condition=("If your phone or computer sends notifications during "
                              "study time, or your blocker is not active"),
                then_action=("then activate a website and app blocker (e.g. "
                             "Freedom, Cold Turkey, or built-in Focus mode) for "
                             "the full duration of the session. Set it before you "
                             "begin, not after you are distracted"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.85,
                impact_score=self._score(ev.evidence, 0.85),
                dimension="digital",
            ))

        # Phone not in digital reach
        if d.phone_in_reach:
            ev = EVIDENCE_LIBRARY["phone_in_another_room"]
            out.append(Prescription(
                rank=0, key="phone_digital_distance",
                title="Put your phone out of digital reach",
                if_condition=("If your phone is unlocked and within arm's reach "
                              "during study"),
                then_action=("then lock it, put it in a drawer in another room, "
                             "or enable Do Not Disturb with only emergency "
                             "contacts allowed through"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.90,
                impact_score=self._score(ev.evidence, 0.90),
                dimension="digital",
            ))

        return out

    def _social_prescriptions(self) -> list[Prescription]:
        s = self.audit.social
        out = []

        # Social accountability
        if not s.social_commitment_device:
            ev = EVIDENCE_LIBRARY["social_accountability"]
            out.append(Prescription(
                rank=0, key="social_accountability",
                title="Name a study partner or household member who knows your plan",
                if_condition=("If no one in your household or study group knows "
                              "your study schedule"),
                then_action=("then tell one person your study plan for the week — "
                             "which days, which hours, which subjects. Ask them "
                             "to check in once per week"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.70,
                impact_score=self._score(ev.evidence, 0.70),
                dimension="social",
            ))

        # Quiet hours
        if not s.quiet_hours_feasible:
            ev = EVIDENCE_LIBRARY["steady_ambient_noise"]
            out.append(Prescription(
                rank=0, key="quiet_hours_negotiation",
                title="Negotiate quiet hours with household",
                if_condition=("If your household environment is noisy during your "
                              "planned study time"),
                then_action=("then negotiate a daily quiet window (even 60 minutes) "
                             "with household members. Use a visual signal (closed "
                             "door, headphone indicator) and offer a reciprocal "
                             "commitment"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.55,
                impact_score=self._score(ev.evidence, 0.55),
                dimension="social",
            ))

        return out

    def _temporal_prescriptions(self) -> list[Prescription]:
        t = self.audit.temporal
        out = []

        # Consistent sleep
        if t.sleep_schedule == "irregular":
            ev = EVIDENCE_LIBRARY["consistent_sleep"]
            out.append(Prescription(
                rank=0, key="consistent_sleep",
                title="Fix your wake time to the same hour every day",
                if_condition=("If your sleep schedule varies by more than an hour "
                              "between weekdays and weekends"),
                then_action=("then set a fixed wake time and hold it seven days a "
                             "week. Bedtime will follow. Use an alarm and place it "
                             "across the room so you must stand to turn it off"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.65,
                impact_score=self._score(ev.evidence, 0.65),
                dimension="temporal",
            ))

        # Deadline map
        if not t.deadline_map_visible:
            ev = EVIDENCE_LIBRARY["deadline_map"]
            out.append(Prescription(
                rank=0, key="deadline_map",
                title="Create a visible deadline map with intermediate checkpoints",
                if_condition=("If your exam or goal date is known but not broken "
                              "into visible intermediate deadlines"),
                then_action=("then write your exam date on a calendar, count back "
                             "weekly, and set a specific checkpoint for each week "
                             "(e.g. 'Week 1: chapters 1-3 reviewed'). Place the "
                             "calendar where you see it daily"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.80,
                impact_score=self._score(ev.evidence, 0.80),
                dimension="temporal",
            ))

        return out

    def _materials_prescriptions(self) -> list[Prescription]:
        m = self.audit.materials
        out = []

        # Materials visible
        if not m.materials_visible:
            ev = EVIDENCE_LIBRARY["materials_ready"]
            out.append(Prescription(
                rank=0, key="materials_visible",
                title="Place study materials on your desk before you finish",
                if_condition=("If your textbooks, notes, and stationery are stored "
                              "away and not visible from your desk"),
                then_action=("then before you end each study session, place the "
                             "materials for the next session on your desk, open to "
                             "the correct page. The friction of starting should be "
                             "near zero"),
                evidence_citation=ev.citation,
                evidence_finding=ev.finding,
                evidence_strength=ev.evidence,
                feasibility=0.95,
                impact_score=self._score(ev.evidence, 0.95),
                dimension="materials",
            ))

        return out

    @staticmethod
    def _score(evidence: str, feasibility: float) -> float:
        """Compute impact score from evidence strength and feasibility."""
        strength_map = {
            EVIDENCE_STRONG: 1.0,
            EVIDENCE_MODERATE: 0.7,
            EVIDENCE_WEAK: 0.4,
        }
        return round(strength_map.get(evidence, 0.0) * feasibility, 3)


# ---------------------------------------------------------------------------
# Adherence tracker — tracks prescription adherence over time
# ---------------------------------------------------------------------------


@dataclass
class AdherenceRecord:
    """One adherence observation for a prescription."""

    prescription_key: str
    learner_id: str
    date: str          # ISO date "YYYY-MM-DD"
    followed: bool
    notes: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


class AdherenceTracker:
    """Track prescription adherence over time.

    The tracker stores adherence records and computes per-prescription
    adherence rates. It is deliberately simple: a prescription is either
    followed or not on a given day. The system re-audits monthly and before
    exams, so the tracker needs to support trend queries over time.
    """

    def __init__(self):
        self._records: list[AdherenceRecord] = []

    def record(self, prescription_key: str, learner_id: str, date: str,
               followed: bool, notes: str = "") -> AdherenceRecord:
        """Record one adherence observation."""
        rec = AdherenceRecord(
            prescription_key=prescription_key,
            learner_id=learner_id,
            date=date,
            followed=followed,
            notes=notes,
        )
        self._records.append(rec)
        return rec

    def adherence_rate(self, prescription_key: str,
                       learner_id: str | None = None) -> float | None:
        """Return adherence rate (0.0-1.0) for a prescription.

        If learner_id is given, only that learner's records are counted.
        Returns None if no records exist.
        """
        relevant = [
            r for r in self._records
            if r.prescription_key == prescription_key
            and (learner_id is None or r.learner_id == learner_id)
        ]
        if not relevant:
            return None
        followed = sum(1 for r in relevant if r.followed)
        return round(followed / len(relevant), 3)

    def adherence_trend(self, prescription_key: str,
                        learner_id: str | None = None) -> list[dict]:
        """Return per-date adherence rates for trend analysis.

        Returns a list of {"date": str, "rate": float, "n": int} sorted by date.
        """
        relevant = [
            r for r in self._records
            if r.prescription_key == prescription_key
            and (learner_id is None or r.learner_id == learner_id)
        ]
        by_date: dict[str, list[AdherenceRecord]] = {}
        for r in relevant:
            by_date.setdefault(r.date, []).append(r)
        trend = []
        for date in sorted(by_date):
            recs = by_date[date]
            followed = sum(1 for r in recs if r.followed)
            trend.append({
                "date": date,
                "rate": round(followed / len(recs), 3),
                "n": len(recs),
            })
        return trend

    def overall_adherence(self, learner_id: str | None = None) -> float | None:
        """Return overall adherence rate across all prescriptions."""
        relevant = [
            r for r in self._records
            if learner_id is None or r.learner_id == learner_id
        ]
        if not relevant:
            return None
        followed = sum(1 for r in relevant if r.followed)
        return round(followed / len(relevant), 3)

    def struggling_prescriptions(self, learner_id: str | None = None,
                                 threshold: float = 0.5) -> list[dict]:
        """Return prescriptions with adherence below the threshold.

        Returns a list of {"prescription_key": str, "rate": float, "n": int}
        sorted by rate ascending (worst first).
        """
        relevant = [
            r for r in self._records
            if learner_id is None or r.learner_id == learner_id
        ]
        by_key: dict[str, list[AdherenceRecord]] = {}
        for r in relevant:
            by_key.setdefault(r.prescription_key, []).append(r)
        struggling = []
        for key, recs in by_key.items():
            followed = sum(1 for r in recs if r.followed)
            rate = followed / len(recs)
            if rate < threshold:
                struggling.append({
                    "prescription_key": key,
                    "rate": round(rate, 3),
                    "n": len(recs),
                })
        struggling.sort(key=lambda x: x["rate"])
        return struggling

    def records_for_learner(self, learner_id: str) -> list[AdherenceRecord]:
        """Return all adherence records for a learner."""
        return [r for r in self._records if r.learner_id == learner_id]

    def summary(self, learner_id: str | None = None) -> dict:
        """Return a summary of adherence for display."""
        relevant = [
            r for r in self._records
            if learner_id is None or r.learner_id == learner_id
        ]
        if not relevant:
            return {"n": 0, "overall_rate": None, "prescriptions": {}}
        by_key: dict[str, list[AdherenceRecord]] = {}
        for r in relevant:
            by_key.setdefault(r.prescription_key, []).append(r)
        per_prescription = {}
        for key, recs in by_key.items():
            followed = sum(1 for r in recs if r.followed)
            per_prescription[key] = {
                "rate": round(followed / len(recs), 3),
                "n": len(recs),
            }
        overall = self.overall_adherence(learner_id)
        return {
            "n": len(relevant),
            "overall_rate": overall,
            "prescriptions": per_prescription,
        }


# ---------------------------------------------------------------------------
# Re-audit scheduler — monthly and before exams
# ---------------------------------------------------------------------------


def should_reaudit(last_audit_at: float, now: float | None = None,
                   exam_date: str | None = None) -> dict:
    """Decide whether a re-audit is due.

    Re-audit is due when:
      * 30 days have passed since the last audit, OR
      * an exam date is known and the audit is within 14 days of the exam.

    Returns {"due": bool, "reason": str, "days_since_last": int}.
    """
    if now is None:
        now = time.time()
    days_since = int((now - last_audit_at) / 86400)

    if days_since >= 30:
        return {
            "due": True,
            "reason": "monthly re-audit due",
            "days_since_last": days_since,
        }

    if exam_date:
        # Parse exam date as YYYY-MM-DD
        try:
            import datetime
            exam_dt = datetime.datetime.strptime(exam_date, "%Y-%m-%d")
            exam_ts = exam_dt.timestamp()
            days_to_exam = int((exam_ts - now) / 86400)
            if 0 <= days_to_exam <= 14:
                return {
                    "due": True,
                    "reason": f"exam in {days_to_exam} days — pre-exam audit",
                    "days_since_last": days_since,
                }
        except (ValueError, OSError):
            pass

    return {
        "due": False,
        "reason": "not due",
        "days_since_last": days_since,
    }
