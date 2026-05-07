"""XP target math for the Academic Personalization Assistant.

Single source of truth for "how much XP should student X earn in subject Y
today?". The answer is one of three things, in priority order:

  1. A coach-set per-subject XP override (Student.xp_overrides). Wins
     unconditionally.
  2. A test-out goal back-solve when the student has a TestOutGoal in this
     subject. Per-day = max(0, (target_xp - starting_xp_in_subject)) /
     school_days_remaining_strictly_after_today, capped at 4 * base_target.
  3. The locked base rate for that subject (LOCKED_XP_RULES from models).
     Unknown subjects fall back to 0.

This module deliberately stays simple. Pace status, "needs to catch up"
labels, and grade-level math live in report_builder.py and models.py.
"""
from __future__ import annotations

from datetime import date
from typing import Optional

from .calendar_tsa import school_days_remaining
from .models import LOCKED_XP_RULES, Student, TestOutGoal


# Cap for test-out back-solve: never demand more than 4x the locked daily
# base for that subject, even if the goal/timeline says we should.
_TEST_OUT_DAILY_CAP_MULTIPLIER: float = 4.0


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def base_target(subject_name: str) -> float:
    """Locked daily XP target for a subject by name.

    Returns 0 for any subject not in LOCKED_XP_RULES (e.g. "Underwater
    Basket Weaving"), so unknown TimeBack apps don't crash the math.
    """
    return float(LOCKED_XP_RULES.get(subject_name, 0))


def student_subject_target(
    student: Student,
    subject: str,
    today: date,
    starting_xp_in_subject: float = 0.0,
) -> float:
    """The student's effective daily XP target for one subject today.

    Priority: xp_overrides > test_out_goal back-solve > base_target.

    `starting_xp_in_subject` is the student's already-earned XP toward the
    test-out goal as of `today` (not today's XP). It is subtracted from the
    goal target before dividing across the remaining school days. Pass 0 to
    treat the goal as "this much new XP from today onward".
    """
    base = base_target(subject)

    # 1. Coach override wins unconditionally.
    override = student.xp_overrides.get(subject)
    if override is not None:
        return float(override)

    # 2. Test-out goal back-solve (only if it's for THIS subject).
    goal: Optional[TestOutGoal] = student.test_out_goal
    if goal is not None and goal.subject == subject:
        per_day = _back_solve_test_out(
            goal=goal,
            today=today,
            starting_xp_in_subject=starting_xp_in_subject,
            base=base,
        )
        if per_day is not None:
            return per_day

    # 3. Locked base rate (or 0 for unknown subjects).
    return base


def all_subject_targets(student: Student, today: date) -> dict[str, float]:
    """Per-subject daily XP targets for every locked subject.

    Returns a dict keyed by subject name with values from
    student_subject_target(). For a student with no overrides and no
    test-out goal, this equals LOCKED_XP_RULES.
    """
    out: dict[str, float] = {}
    for subject in LOCKED_XP_RULES:
        out[subject] = student_subject_target(student, subject, today)
    return out


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _back_solve_test_out(
    goal: TestOutGoal,
    today: date,
    starting_xp_in_subject: float,
    base: float,
) -> Optional[float]:
    """Return per-day XP needed to hit `goal` by `goal.target_date`.

    Returns None if the goal has no usable date or no remaining XP, so the
    caller can fall back to the base rate.

    - Uses school_days_remaining(today, target_date), which counts school
      days STRICTLY AFTER today through and including target_date.
    - Subtracts both the goal's own starting_xp and any caller-supplied
      starting_xp_in_subject from the target before dividing.
    - Caps the result at 4 * base (never demand more than 4x the locked
      daily rate, even on tight timelines).
    """
    target_date = _parse_iso_date(goal.target_date)
    if target_date is None:
        return None

    remaining_days = school_days_remaining(today, target_date)
    if remaining_days <= 0:
        # Past, same-day, or non-school target: caller falls back to base.
        return None

    xp_remaining = float(goal.target_xp) - float(goal.starting_xp) - float(starting_xp_in_subject)
    if xp_remaining <= 0:
        return 0.0

    per_day = xp_remaining / remaining_days

    if base > 0:
        cap = _TEST_OUT_DAILY_CAP_MULTIPLIER * base
        if per_day > cap:
            per_day = cap

    return per_day


def _parse_iso_date(s: str) -> Optional[date]:
    """Parse 'YYYY-MM-DD'. Returns None on bad input rather than raising,
    so a malformed goal doesn't crash the morning report."""
    try:
        y, m, d = s.split("-")
        return date(int(y), int(m), int(d))
    except (ValueError, AttributeError):
        return None
