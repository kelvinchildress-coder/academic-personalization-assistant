"""Domain models for the Academic Personalization Assistant.

Single source of truth for the runtime objects passed between the scraper-
ingest layer, target math, report builders, and Slack posting layer.

All models are name-based (TimeBack UUIDs are not required to operate, since
the scraper output already carries display names that match coach rosters).
Models are frozen dataclasses where reasonable; mutable lists/dicts use
field(default_factory=...) so default values are not shared across instances.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


# ---------------------------------------------------------------------------
# Locked daily XP rules (authoritative; per Texas Sports Academy)
# ---------------------------------------------------------------------------

LOCKED_XP_RULES: dict[str, float] = {
    "Math": 25,
    "Reading": 25,
    "Language": 25,
    "Writing": 12.5,
    "Science": 12.5,
    "Vocabulary": 10,
    "FastMath": 10,
}


# ---------------------------------------------------------------------------
# Coach + roster
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Coach:
    """One coach and the names of the students assigned to them."""
    name: str
    students: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CoachRoster:
    """The full TSA roster: head coach, the campus Slack channel, and coaches.

    Constructed via from_dict() from config/coaches.json which has shape:
        {
            "head_coach": "Kelvin Childress",
            "channel": "sports",
            "coaches": {
                "Ella Alexander": ["JT Kambic", "Tallulah Chaney", ...],
                "Amir Lewis": ["Allison Kim", ...],
                ...
            }
        }
    """
    head_coach: str
    coaches: list[Coach] = field(default_factory=list)
    channel: str = "sports"

    @classmethod
    def from_dict(cls, d: dict) -> "CoachRoster":
        coaches_raw = d.get("coaches", {}) or {}
        if isinstance(coaches_raw, dict):
            coaches = [Coach(name=n, students=list(s)) for n, s in coaches_raw.items()]
        else:
            # Tolerant: also accept a list-of-objects shape.
            coaches = [
                Coach(name=c["name"], students=list(c.get("students", [])))
                for c in coaches_raw
            ]
        return cls(
            head_coach=d.get("head_coach", ""),
            coaches=coaches,
            channel=d.get("channel", "sports"),
        )

    def coach_for_student(self, student_name: str) -> Optional[str]:
        """Return the coach's name for this student, or None if unassigned."""
        for c in self.coaches:
            if student_name in c.students:
                return c.name
        return None

    @property
    def all_student_names(self) -> list[str]:
        out: list[str] = []
        for c in self.coaches:
            out.extend(c.students)
        return out


# ---------------------------------------------------------------------------
# Test-out goal (per-subject back-solve target with date)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class TestOutGoal:
    """A coach-set goal: 'reach <target_xp> XP in <subject> by <target_date>'.

    starting_xp lets the back-solve subtract XP the student already has on the
    day the goal is set (or any later snapshot we choose).
    """
    subject: str
    target_xp: float
    target_date: str          # ISO YYYY-MM-DD
    starting_xp: float = 0.0
    note: str = ""


# ---------------------------------------------------------------------------
# Student (name-based, optional overrides)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Student:
    """A TSA student. Only `name` is required.

    `xp_overrides` lets a coach hard-set a daily XP target for a subject
    (e.g. {"Math": 30}). It WINS over both the locked base rate and a
    test-out goal back-solve.

    `test_out_goal` is at most one TestOutGoal at a time. If both an override
    AND a goal exist for the same subject, the override wins.
    """
    name: str
    xp_overrides: dict[str, float] = field(default_factory=dict)
    test_out_goal: Optional[TestOutGoal] = None

    @classmethod
    def from_json(cls, raw) -> "Student":
        """Accepts either a plain string ('Allison Kim') or a dict object."""
        if isinstance(raw, str):
            return cls(name=raw)
        if not isinstance(raw, dict):
            raise TypeError(f"Cannot build Student from {type(raw).__name__}")
        goal_raw = raw.get("test_out_goal")
        goal = None
        if isinstance(goal_raw, dict):
            goal = TestOutGoal(
                subject=goal_raw["subject"],
                target_xp=float(goal_raw["target_xp"]),
                target_date=str(goal_raw["target_date"]),
                starting_xp=float(goal_raw.get("starting_xp", 0.0)),
                note=str(goal_raw.get("note", "")),
            )
        return cls(
            name=raw["name"],
            xp_overrides={k: float(v) for k, v in (raw.get("xp_overrides") or {}).items()},
            test_out_goal=goal,
        )


# ---------------------------------------------------------------------------
# Per-subject daily result (one row from the scraper)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class SubjectResult:
    """One subject's progress for one student on one day.

    `accuracy` is a percent in [0, 100]. `xp` and `target_xp` are XP units.
    `minutes` is wall-clock time-on-task. `has_test` is a flag for test-out
    interactions on the day.
    """
    name: str
    xp: float
    accuracy: float
    minutes: float
    target_xp: float
    has_test: bool = False

    @property
    def is_low_accuracy(self) -> bool:
        """Below 60% in any app the student worked in today."""
        return self.xp > 0 and self.accuracy < 60

    @property
    def is_overperforming(self) -> bool:
        """At or above 125% of today's XP target in this subject."""
        return self.target_xp > 0 and self.xp >= 1.25 * self.target_xp

    @property
    def pct_of_target(self) -> float:
        """xp / target_xp; 0 if no target."""
        if self.target_xp <= 0:
            return 0.0
        return self.xp / self.target_xp

    @property
    def hit_target(self) -> bool:
        return self.target_xp > 0 and self.xp >= self.target_xp


# ---------------------------------------------------------------------------
# Per-student daily result (all subjects)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StudentDailyResult:
    """All subject results for one student on one day."""
    name: str
    date: str                # ISO YYYY-MM-DD (kept as string to mirror scraper)
    subjects: list[SubjectResult] = field(default_factory=list)
    absent: bool = False

    @property
    def total_xp(self) -> float:
        return sum(s.xp for s in self.subjects)

    @property
    def total_target_xp(self) -> float:
        return sum(s.target_xp for s in self.subjects)

    @property
    def overall_pct(self) -> float:
        if self.total_target_xp <= 0:
            return 0.0
        return self.total_xp / self.total_target_xp

    @property
    def is_green(self) -> bool:
        """Hit total target XP today AND no low-accuracy subjects.

        Absent students are not considered Green.
        """
        if self.absent:
            return False
        if self.total_target_xp <= 0:
            return False
        if self.total_xp < self.total_target_xp:
            return False
        if self.flagged_subjects():
            return False
        return True

    def flagged_subjects(self) -> list[SubjectResult]:
        """Subjects where the student worked but accuracy < 60%."""
        return [s for s in self.subjects if s.is_low_accuracy]

    def overperforming_subjects(self) -> list[SubjectResult]:
        """Subjects where the student exceeded 125% of target."""
        return [s for s in self.subjects if s.is_overperforming]
