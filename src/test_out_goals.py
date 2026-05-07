"""
test_out_goals.py
=================

Resolves the *target test-out grade* for a single (student, subject) pair.

This module owns Priority-tier resolution for the "what grade should this
student be testing out into?" question. It does NOT compute XP/day targets —
that is done in src/targets.py. Here we only decide:

    1. Is there a coach override (Priority 0b)? -> use it.
    2. Otherwise, compute the default target grade per the locked Q2 rule:

       default_target_grade = max(
           next_anchor_grade_at_or_above(age_grade),  # anchors: 1, 3, 5, 8
           year_start_grade_in_subject + 2
       )

The "year_start_grade_in_subject + 2" arm is anchored at the *start of the
school year* — it is a snapshot taken at SY start and does NOT move during
the year (per the user's clarification: "the 2 grade growth is from the
start of the year, not at any given point or they would always be chasing
an impossible growth").

Anchor grades are: 1, 3, 5, 8.
For age_grade <= 1 -> 1
For age_grade in {2, 3} -> 3
For age_grade in {4, 5} -> 5
For age_grade in {6, 7, 8} -> 8
For age_grade >= 9 -> the next anchor concept tops out; we cap at 12 but
defer to the (year_start + 2) arm via max().

Subjects that don't carry a "grade" (FastMath, Vocabulary) are handled by
returning None from resolve_target_grade — callers should treat None as
"no grade-mastered target; fall through to personalized base / locked base".
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


# Subjects that have a meaningful grade level.
GRADED_SUBJECTS = frozenset({
    "Math",
    "Reading",
    "Language",
    "Writing",
    "Science",
})

# Subjects that do NOT carry a grade in TimeBack and should not get a
# grade-mastered target.
NON_GRADED_SUBJECTS = frozenset({
    "FastMath",
    "Vocabulary",
})

# The fixed anchor grades from Q2.
ANCHOR_GRADES = (1, 3, 5, 8)

# Hard cap on grade level (TimeBack tops out around 12).
MAX_GRADE = 12


def next_anchor_at_or_above(age_grade: int) -> int:
    """
    Return the smallest anchor grade >= age_grade.

    Anchors: 1, 3, 5, 8. If age_grade > 8 we return age_grade itself
    (capped at MAX_GRADE) so the (year_start + 2) arm can still drive
    the max().
    """
    for a in ANCHOR_GRADES:
        if a >= age_grade:
            return a
    return min(age_grade, MAX_GRADE)


def default_target_grade(age_grade: int, year_start_grade: int) -> int:
    """
    Compute the locked default target test-out grade per Q2.

        max(
            next_anchor_at_or_above(age_grade),
            year_start_grade + 2
        )

    Both inputs are integer grade levels (K is treated as 0 by convention,
    but the caller should convert K->0 before calling). Result is capped
    at MAX_GRADE.
    """
    if age_grade is None or year_start_grade is None:
        raise ValueError("age_grade and year_start_grade are required")

    anchor = next_anchor_at_or_above(int(age_grade))
    growth = int(year_start_grade) + 2
    return min(MAX_GRADE, max(anchor, growth))


@dataclass(frozen=True)
class TargetGradeResolution:
    """Result of resolving a target test-out grade for one subject."""
    subject: str
    target_grade: Optional[int]
    source: str  # "coach_override" | "default_q2" | "non_graded"
    detail: str  # human-readable explanation for the report


def resolve_target_grade(
    *,
    subject: str,
    age_grade: Optional[int],
    year_start_grade: Optional[int],
    coach_override_grade: Optional[int] = None,
) -> TargetGradeResolution:
    """
    Resolve the target test-out grade for one (student, subject) pair.

    Priority order:
      0b. coach_override_grade if provided -> use it.
      Q2. otherwise, default_target_grade(age_grade, year_start_grade).

    Subjects in NON_GRADED_SUBJECTS always resolve to None (no grade
    target). Unknown subjects also resolve to None and are tagged so
    callers can normalize them upstream.
    """
    if subject in NON_GRADED_SUBJECTS:
        return TargetGradeResolution(
            subject=subject,
            target_grade=None,
            source="non_graded",
            detail=f"{subject} is not a graded subject; no test-out grade.",
        )

    if subject not in GRADED_SUBJECTS:
        return TargetGradeResolution(
            subject=subject,
            target_grade=None,
            source="non_graded",
            detail=f"Subject '{subject}' is not recognized as graded.",
        )

    # Priority 0b: coach override wins absolutely.
    if coach_override_grade is not None:
        return TargetGradeResolution(
            subject=subject,
            target_grade=int(coach_override_grade),
            source="coach_override",
            detail=(
                f"Coach override: target grade {int(coach_override_grade)} "
                f"for {subject}."
            ),
        )

    # Q2 default rule.
    if age_grade is None or year_start_grade is None:
        return TargetGradeResolution(
            subject=subject,
            target_grade=None,
            source="default_q2",
            detail=(
                f"Cannot compute default target for {subject}: "
                f"missing age_grade or year_start_grade."
            ),
        )

    tg = default_target_grade(int(age_grade), int(year_start_grade))
    anchor = next_anchor_at_or_above(int(age_grade))
    growth = int(year_start_grade) + 2
    return TargetGradeResolution(
        subject=subject,
        target_grade=tg,
        source="default_q2",
        detail=(
            f"Default Q2: max(anchor>={int(age_grade)}={anchor}, "
            f"year_start({int(year_start_grade)})+2={growth}) = {tg}."
        ),
    )
