"""Domain models for the Academic Personalization Assistant.

All dataclasses are frozen by default; mutate by constructing a new instance.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Dict, List, Optional


class Subject(str, Enum):
    """Subjects tracked by TimeBack. String values match TimeBack labels."""

    MATH = "Math"
    READING = "Reading"
    LANGUAGE = "Language"
    WRITING = "Writing"
    SCIENCE = "Science"
    VOCABULARY = "Vocabulary"
    FAST_MATH = "FastMath"


@dataclass(frozen=True)
class Student:
    """A TSA student tied to one coach."""

    sourced_id: str           # TimeBack UUID
    full_name: str
    grade_level: str          # e.g. "3", "K", "PK"
    coach_short_id: str       # see config.COACHES


@dataclass(frozen=True)
class DailyTarget:
    """What a student needs to earn today in one subject."""

    student_id: str
    subject: Subject
    target_xp: float
    is_personalized: bool = False  # True iff a coach override or grade-out goal applies
    rationale: str = ""            # human-readable why


class PaceLabel(str, Enum):
    AHEAD = "Ahead"
    ON_TRACK = "On Track"
    NEEDS_TO_CATCH_UP = "Needs To Catch Up"


@dataclass(frozen=True)
class PaceStatus:
    """Richer pace status for personalized goals.

    For base-rate goals, only `label` is meaningful (it mirrors the TimeBack
    Learner Report string). For personalized goals (coach override XP or
    grade-out-by-date), the additional fields describe the gap.
    """

    label: PaceLabel
    earned_xp: float
    expected_xp: float
    delta_xp: float                # earned - expected
    days_remaining: int            # school days until session end / goal date
    catch_up_xp_per_day: float     # xp/day required to hit goal on time


@dataclass(frozen=True)
class AccuracyFlag:
    """Auto-flag when a student drops below the accuracy floor in a subject."""

    student_id: str
    subject: Subject
    accuracy: float                # 0.0 to 1.0
    threshold: float               # ACCURACY_FLAG_THRESHOLD
    window_label: str              # e.g. "today", "this_week"


@dataclass(frozen=True)
class CoachOverride:
    """Coach-set override for a student in one subject.

    Exactly one of `daily_xp_override` or `grade_out_by` should be set.
    """

    student_id: str
    subject: Subject
    daily_xp_override: Optional[float] = None
    grade_out_by: Optional[date] = None
    target_grade_level: Optional[str] = None  # required iff grade_out_by set
    note: str = ""


@dataclass(frozen=True)
class SubjectProgress:
    """Snapshot of a student's progress in one subject for a window."""

    student_id: str
    subject: Subject
    earned_xp: float
    accuracy: float                # 0.0 to 1.0
    daily_target: float
    pace: PaceStatus
    flag: Optional[AccuracyFlag] = None


@dataclass(frozen=True)
class StudentSnapshot:
    """All subjects for one student at one moment."""

    student: Student
    as_of: date
    by_subject: Dict[Subject, SubjectProgress] = field(default_factory=dict)

    @property
    def has_any_flag(self) -> bool:
        return any(p.flag is not None for p in self.by_subject.values())

    @property
    def hit_all_targets(self) -> bool:
        return all(
            p.earned_xp >= p.daily_target for p in self.by_subject.values()
        )


@dataclass(frozen=True)
class CoachRoster:
    """All students for one coach."""

    coach_short_id: str
    students: List[Student]
