"""
gap_finder.py
=============

Scans config/students.json and identifies missing per-(student, subject)
fields the coach still needs to ratify or override. Produces a
prioritized work list of `GoalGap` records.

A "gap" is anything the agent should ask the coach about. Specifically:

  * MISSING_AGE_GRADE       — student.age_grade is null
  * MISSING_CURRENT_GRADE   — current_grade_per_subject[subject] is null
                              for any of the 5 graded subjects
  * MISSING_YEAR_START      — year_start_grade_per_subject[subject] is null
  * MISSING_TARGET          — no manual_test_out_grade and no override
                              has been ratified by the coach (we treat
                              the Q2 default as "needs ratification once").
  * MISSING_RATIFICATION    — student is fully populated but the coach
                              hasn't acknowledged the cascade-default
                              once. (Stored in profile["ratified"].)

Ranking (highest priority first):
  1. MISSING_AGE_GRADE       — blocks everything else
  2. MISSING_CURRENT_GRADE   — blocks Tier 1 + Tier 3
  3. MISSING_YEAR_START      — blocks Q2 default
  4. MISSING_TARGET          — blocks Tier 0b
  5. MISSING_RATIFICATION    — soft, last priority

We also throttle: a gap that was last asked < `MIN_REASK_DAYS` days ago
is suppressed so we don't spam coaches.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


GRADED_SUBJECTS = ("Math", "Reading", "Language", "Writing", "Science")
ALL_SUBJECTS = GRADED_SUBJECTS + ("Vocabulary", "FastMath")

MIN_REASK_DAYS = 7  # don't ask the same question twice within 7 days

GAP_PRIORITIES = {
    "MISSING_AGE_GRADE": 1,
    "MISSING_CURRENT_GRADE": 2,
    "MISSING_YEAR_START": 3,
    "MISSING_TARGET": 4,
    "MISSING_RATIFICATION": 5,
}


@dataclass(frozen=True)
class GoalGap:
    student_name: str
    coach_name: Optional[str]      # the responsible coach, if known
    subject: Optional[str]         # None for student-wide gaps (age_grade)
    kind: str                      # one of GAP_PRIORITIES keys
    detail: str                    # human-readable for logging/drafting

    @property
    def priority(self) -> int:
        return GAP_PRIORITIES.get(self.kind, 99)

    @property
    def dedupe_key(self) -> str:
        """Stable key for ask-throttling state."""
        return f"{self.student_name}|{self.subject or '*'}|{self.kind}"


# ---------------------------------------------------------------------------
# Throttle state — recorded per (dedupe_key, last_asked_iso_date) in
# data/agent_state.json. We pass the loaded dict in; gap_finder is pure.
# ---------------------------------------------------------------------------


def _was_recently_asked(
    dedupe_key: str,
    asked_log: Dict[str, str],
    today: date,
    *,
    min_reask_days: int = MIN_REASK_DAYS,
) -> bool:
    raw = asked_log.get(dedupe_key)
    if not raw:
        return False
    try:
        last = date.fromisoformat(raw)
    except ValueError:
        return False
    return (today - last) < timedelta(days=min_reask_days)


# ---------------------------------------------------------------------------
# Coach lookup (tolerant)
# ---------------------------------------------------------------------------


def _coach_for_student(coaches_blob: Dict[str, Any], student: str) -> Optional[str]:
    coaches_map = coaches_blob.get("coaches") or {}
    for coach_name, students in coaches_map.items():
        if student in (students or []):
            return coach_name
    # Lisa Willis -> Lisa C Willis
    if student == "Lisa Willis":
        return _coach_for_student(coaches_blob, "Lisa C Willis")
    return None


# ---------------------------------------------------------------------------
# Core gap detection
# ---------------------------------------------------------------------------


def _gaps_for_student(
    name: str,
    profile: Dict[str, Any],
    coach: Optional[str],
) -> List[GoalGap]:
    gaps: List[GoalGap] = []

    if profile.get("age_grade") is None:
        gaps.append(GoalGap(
            student_name=name,
            coach_name=coach,
            subject=None,
            kind="MISSING_AGE_GRADE",
            detail=f"{name}: age_grade is not set.",
        ))
        # Once we know age_grade we can ask about subjects; until then,
        # the per-subject gaps would be premature. Return early.
        return gaps

    cur_per_sub = profile.get("current_grade_per_subject") or {}
    ys_per_sub = profile.get("year_start_grade_per_subject") or {}
    target_grade_map = profile.get("manual_test_out_grade") or {}
    overrides = profile.get("overrides") or {}
    overrides_xp = (overrides.get("xp_per_day") or {})
    ratified = set(profile.get("ratified") or [])

    for subject in ALL_SUBJECTS:
        # Vocabulary / FastMath don't need a per-subject grade.
        if subject in GRADED_SUBJECTS:
            if cur_per_sub.get(subject) is None:
                gaps.append(GoalGap(
                    student_name=name,
                    coach_name=coach,
                    subject=subject,
                    kind="MISSING_CURRENT_GRADE",
                    detail=f"{name} / {subject}: current grade unknown.",
                ))
                continue
            if ys_per_sub.get(subject) is None:
                gaps.append(GoalGap(
                    student_name=name,
                    coach_name=coach,
                    subject=subject,
                    kind="MISSING_YEAR_START",
                    detail=(
                        f"{name} / {subject}: year-start grade unknown "
                        f"(needed for Q2 +2 growth target)."
                    ),
                ))
                continue

        # Once enough is known to compute the cascade default, ask the
        # coach to either ratify it or set an override.
        has_override = (
            target_grade_map.get(subject) is not None
            or overrides_xp.get(subject) is not None
        )
        if not has_override and subject not in ratified:
            kind = "MISSING_RATIFICATION"
            detail = (
                f"{name} / {subject}: cascade default not yet ratified "
                f"by coach."
            )
            # Promote to MISSING_TARGET if the subject has zero progress
            # signals at all — this is a stronger ask.
            if subject in GRADED_SUBJECTS and cur_per_sub.get(subject) is None:
                kind = "MISSING_TARGET"
                detail = f"{name} / {subject}: no target set."
            gaps.append(GoalGap(
                student_name=name,
                coach_name=coach,
                subject=subject,
                kind=kind,
                detail=detail,
            ))

    return gaps


def find_gaps(
    *,
    students_config: Dict[str, Any],
    coaches_config: Dict[str, Any],
    asked_log: Optional[Dict[str, str]] = None,
    today: Optional[date] = None,
    min_reask_days: int = MIN_REASK_DAYS,
) -> List[GoalGap]:
    """
    Public entry point. Returns gaps sorted by priority then student name.
    Suppresses any gap whose dedupe_key was asked within `min_reask_days`.
    """
    today = today or date.today()
    asked_log = asked_log or {}

    out: List[GoalGap] = []
    for name, profile in (students_config.get("students") or {}).items():
        coach = _coach_for_student(coaches_config, name)
        for g in _gaps_for_student(name, profile, coach):
            if _was_recently_asked(g.dedupe_key, asked_log, today, min_reask_days=min_reask_days):
                continue
            out.append(g)

    out.sort(key=lambda g: (g.priority, g.student_name, g.subject or ""))
    return out


def is_phase_one(gaps: Iterable[GoalGap]) -> bool:
    """
    Phase 1 = active onboarding (any unresolved gaps remain).
    Phase 2 = steady state (no gaps; only listen for unsolicited replies).
    """
    return any(True for _ in gaps)
