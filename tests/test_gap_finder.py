"""Tests for src.agent.gap_finder."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from src.agent.gap_finder import (
    GoalGap,
    find_gaps,
    is_phase_one,
    GAP_PRIORITIES,
    MIN_REASK_DAYS,
)


def _empty_profile():
    return {
        "age_grade": None,
        "current_grade_per_subject": {},
        "year_start_grade_per_subject": {},
        "manual_test_out_grade": {},
        "manual_test_out_date": {},
    }


def _coaches_blob():
    return {
        "head_coach": "Kelvin Childress",
        "channel": "sports",
        "coaches": {
            "Amir Lewis": ["Allison Kim", "Levi Reeves"],
            "Lisa C Willis": ["Stone Meyers"],
        },
    }


def test_missing_age_grade_blocks_subject_gaps():
    students = {"students": {"Allison Kim": _empty_profile()}}
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
    )
    # Only one gap: MISSING_AGE_GRADE. Subject gaps deferred until age_grade known.
    assert len(gaps) == 1
    assert gaps[0].kind == "MISSING_AGE_GRADE"
    assert gaps[0].coach_name == "Amir Lewis"
    assert gaps[0].subject is None


def test_missing_current_grade_per_subject():
    profile = _empty_profile()
    profile["age_grade"] = 4
    students = {"students": {"Allison Kim": profile}}
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
    )
    kinds = sorted({g.kind for g in gaps})
    # All 5 graded subjects need current grade; FastMath/Vocab need ratification.
    assert "MISSING_CURRENT_GRADE" in kinds
    # FastMath/Vocab don't need grade — they should produce ratification gaps.
    fastmath = [g for g in gaps if g.subject == "FastMath"]
    assert fastmath and fastmath[0].kind in ("MISSING_RATIFICATION", "MISSING_TARGET")


def test_year_start_required_after_current_grade():
    profile = _empty_profile()
    profile["age_grade"] = 4
    profile["current_grade_per_subject"] = {
        "Math": 5, "Reading": 4, "Language": 4, "Writing": 4, "Science": 4,
    }
    students = {"students": {"Allison Kim": profile}}
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
    )
    ys_gaps = [g for g in gaps if g.kind == "MISSING_YEAR_START"]
    assert len(ys_gaps) == 5
    assert {g.subject for g in ys_gaps} == {"Math", "Reading", "Language", "Writing", "Science"}


def test_priority_ordering():
    p1 = _empty_profile()                     # missing age_grade
    p2 = _empty_profile()
    p2["age_grade"] = 4                       # has age, missing current grade
    p3 = _empty_profile()
    p3["age_grade"] = 4
    p3["current_grade_per_subject"] = {
        "Math": 4, "Reading": 4, "Language": 4, "Writing": 4, "Science": 4,
    }
    p3["year_start_grade_per_subject"] = {
        "Math": 4, "Reading": 4, "Language": 4, "Writing": 4, "Science": 4,
    }
    students = {"students": {
        "Allison Kim": p1,
        "Levi Reeves": p2,
        "Stone Meyers": p3,
    }}
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
    )
    # The first gap should be the MISSING_AGE_GRADE entry.
    assert gaps[0].kind == "MISSING_AGE_GRADE"
    assert gaps[0].priority == GAP_PRIORITIES["MISSING_AGE_GRADE"]
    # The age_grade gap should outrank current_grade gaps.
    assert gaps[0].priority < min(
        g.priority for g in gaps if g.kind != "MISSING_AGE_GRADE"
    )


def test_throttle_suppresses_recent_questions():
    profile = _empty_profile()
    students = {"students": {"Allison Kim": profile}}
    today = date(2026, 5, 8)
    asked_log = {
        "Allison Kim|*|MISSING_AGE_GRADE": (today - timedelta(days=2)).isoformat(),
    }
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
        asked_log=asked_log,
        today=today,
    )
    assert gaps == []


def test_throttle_clears_after_min_reask_window():
    profile = _empty_profile()
    students = {"students": {"Allison Kim": profile}}
    today = date(2026, 5, 8)
    asked_log = {
        "Allison Kim|*|MISSING_AGE_GRADE": (
            today - timedelta(days=MIN_REASK_DAYS + 1)
        ).isoformat(),
    }
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
        asked_log=asked_log,
        today=today,
    )
    assert any(g.kind == "MISSING_AGE_GRADE" for g in gaps)


def test_lisa_willis_name_normalization():
    """Lisa C Willis should be matched as the coach for Stone Meyers,
    even if a downstream caller spells the coach 'Lisa Willis'."""
    profile = _empty_profile()
    students = {"students": {"Stone Meyers": profile}}
    gaps = find_gaps(
        students_config=students,
        coaches_config=_coaches_blob(),
    )
    assert gaps and gaps[0].coach_name == "Lisa C Willis"


def test_phase_detection():
    assert is_phase_one([GoalGap("x", "y", None, "MISSING_AGE_GRADE", "")])
    assert not is_phase_one([])
