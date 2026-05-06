"""XP target math for the Academic Personalization Assistant.

Daily XP base targets per subject (Texas Sports Academy):
  Math, Reading, Language       = 25 XP/day
  Vocabulary, FastMath          = 10 XP/day
  Writing, Science              = 12.5 XP/day (flat, not alternating-week)

A student's effective daily target in a subject is:
  - Coach's daily_xp_override if one is set, OR
  - The pace required to grade-out by a target date (XP_to_master / school_days_remaining_to_target_date), OR
  - The base rate above.

Pace status (`PaceStatus`) reports earned vs expected. For base-rate goals
the `label` field mirrors the TimeBack Learner Report's string
("On Track" / "Needs To Catch Up" / "Ahead"). For personalized goals we
additionally populate delta_xp, days_remaining, catch_up_xp_per_day.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from .calendar_tsa import (
    is_school_day,
    school_days_between,
    school_days_remaining_in_session,
)
from .models import (
    AccuracyFlag,
    CoachOverride,
    DailyTarget,
    PaceLabel,
    PaceStatus,
    Subject,
)

# ---------------------------------------------------------------------------
# Base daily targets
# ---------------------------------------------------------------------------

BASE_DAILY_TARGETS: dict[Subject, float] = {
    Subject.MATH: 25.0,
    Subject.READING: 25.0,
    Subject.LANGUAGE: 25.0,
    Subject.WRITING: 12.5,
    Subject.SCIENCE: 12.5,
    Subject.VOCABULARY: 10.0,
    Subject.FAST_MATH: 10.0,
}


def base_daily_target(subject: Subject) -> float:
    """Return the campus base XP/day for the given subject."""
    return BASE_DAILY_TARGETS[subject]


# ---------------------------------------------------------------------------
# Effective daily target
# ---------------------------------------------------------------------------

def effective_daily_target(
    student_id: str,
    subject: Subject,
    today: date,
    earned_xp_in_session: float = 0.0,
    override: Optional[CoachOverride] = None,
    grade_out_total_xp_remaining: Optional[float] = None,
) -> DailyTarget:
    """Compute today's XP target for one student in one subject.

    Resolution order:
      1. If a CoachOverride sets daily_xp_override, use it.
      2. If a CoachOverride sets grade_out_by, divide remaining XP by
         school days remaining until that date.
      3. Otherwise return the campus base rate.
    """
    # If today is not a school day, return zero.
    if not is_school_day(today):
        return DailyTarget(
            student_id=student_id,
            subject=subject,
            target_xp=0.0,
            is_personalized=override is not None,
            rationale="non-school-day",
        )

    if override is not None:
        if override.daily_xp_override is not None:
            return DailyTarget(
                student_id=student_id,
                subject=subject,
                target_xp=float(override.daily_xp_override),
                is_personalized=True,
                rationale=f"coach override: {override.daily_xp_override} XP/day",
            )

        if override.grade_out_by is not None and grade_out_total_xp_remaining is not None:
            days = school_days_between(today, override.grade_out_by)
            if days <= 0:
                return DailyTarget(
                    student_id=student_id,
                    subject=subject,
                    target_xp=float(grade_out_total_xp_remaining),
                    is_personalized=True,
                    rationale="grade-out target date is today or past",
                )
            return DailyTarget(
                student_id=student_id,
                subject=subject,
                target_xp=float(grade_out_total_xp_remaining) / days,
                is_personalized=True,
                rationale=f"grade-out by {override.grade_out_by.isoformat()}: {days} school days remaining",
            )

    return DailyTarget(
        student_id=student_id,
        subject=subject,
        target_xp=base_daily_target(subject),
        is_personalized=False,
        rationale="campus base rate",
    )


# ---------------------------------------------------------------------------
# Pace status
# ---------------------------------------------------------------------------

def base_rate_pace(
    earned_xp: float,
    expected_xp: float,
    days_remaining_in_session: int,
    base_daily: float,
) -> PaceStatus:
    """Pace for a base-rate goal. Mirrors TimeBack Learner Report semantics."""
    delta = earned_xp - expected_xp
    if delta >= base_daily:
        label = PaceLabel.AHEAD
    elif delta >= 0:
        label = PaceLabel.ON_TRACK
    else:
        label = PaceLabel.NEEDS_TO_CATCH_UP

    if days_remaining_in_session <= 0:
        catch_up = max(-delta, 0.0)
    else:
        catch_up = max(-delta / days_remaining_in_session, 0.0)

    return PaceStatus(
        label=label,
        earned_xp=earned_xp,
        expected_xp=expected_xp,
        delta_xp=delta,
        days_remaining=days_remaining_in_session,
        catch_up_xp_per_day=catch_up,
    )


def personalized_pace(
    earned_xp: float,
    goal_xp_total: float,
    today: date,
    target_date: date,
) -> PaceStatus:
    """Pace for a personalized (coach override or grade-out-by-date) goal."""
    days = school_days_between(today, target_date)
    days_total = school_days_between(today, target_date)  # alias for clarity
    expected = goal_xp_total - max(
        goal_xp_total * (days_total - max(days, 0)) / max(days_total, 1),
        0.0,
    )
    # Simpler: expected = (school_days_so_far / total_school_days) * goal_xp_total
    # but we only have remaining days here, so caller should supply expected
    # via base_rate_pace if they need that exact form. We instead express
    # progress as (earned vs goal) over (days_remaining).
    delta = earned_xp - (goal_xp_total - (goal_xp_total * max(days, 1) / max(days_total, 1)))

    remaining_xp = max(goal_xp_total - earned_xp, 0.0)
    if days <= 0:
        catch_up = remaining_xp
        label = PaceLabel.AHEAD if remaining_xp <= 0 else PaceLabel.NEEDS_TO_CATCH_UP
    else:
        catch_up = remaining_xp / days
        if remaining_xp <= 0:
            label = PaceLabel.AHEAD
        elif catch_up <= 0:
            label = PaceLabel.AHEAD
        else:
            # Heuristic: if today's required pace exceeds 1.5x base rate equivalent
            label = PaceLabel.NEEDS_TO_CATCH_UP if catch_up > 0 else PaceLabel.ON_TRACK

    return PaceStatus(
        label=label,
        earned_xp=earned_xp,
        expected_xp=goal_xp_total - remaining_xp,
        delta_xp=delta,
        days_remaining=days,
        catch_up_xp_per_day=catch_up,
    )


# ---------------------------------------------------------------------------
# Accuracy flag helper
# ---------------------------------------------------------------------------

def should_flag(
    student_id: str,
    subject: Subject,
    accuracy: float,
    threshold: float,
    window_label: str = "today",
) -> Optional[AccuracyFlag]:
    """Return an AccuracyFlag if accuracy < threshold else None."""
    if accuracy < threshold:
        return AccuracyFlag(
            student_id=student_id,
            subject=subject,
            accuracy=accuracy,
            threshold=threshold,
            window_label=window_label,
        )
    return None
