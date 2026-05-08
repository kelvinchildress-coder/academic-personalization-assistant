"""Tests for the 4-tier cascade in src.targets."""

from __future__ import annotations

from datetime import date

import pytest

from src.targets import (
    LOCKED_BASE_XP,
    PERSONALIZED_FLOOR_XP,
    base_target,
    resolve_daily_target,
    resolve_all_subjects,
)


def _profile(**overrides):
    p = {
        "age_grade": 4,
        "current_grade_per_subject": {
            "Math": 4, "Reading": 4, "Language": 4, "Writing": 4, "Science": 4,
        },
        "year_start_grade_per_subject": {
            "Math": 4, "Reading": 4, "Language": 4, "Writing": 4, "Science": 4,
        },
        "manual_test_out_grade": {},
        "manual_test_out_date": {},
    }
    p.update(overrides)
    return p


# -------------------------- Tier 4 (locked base) ---------------------------


def test_tier4_locked_base_for_fastmath_when_no_overrides():
    res = resolve_daily_target(
        student_name="Allison Kim",
        subject="FastMath",
        today=date(2026, 5, 8),
        student_profile=_profile(),
    )
    assert res.tier == 4
    assert res.xp_per_day == LOCKED_BASE_XP["FastMath"]


def test_tier4_locked_base_for_writing_when_grades_match():
    # age=4, current=4 -> personalized base == locked base, but the test
    # is that we still cite tier 3 (since it's the personalized path).
    res = resolve_daily_target(
        student_name="Allison Kim",
        subject="Writing",
        today=date(2026, 5, 8),
        student_profile=_profile(),
    )
    # current_grade present + age_grade present -> personalized base wins.
    assert res.tier == 3
    assert res.xp_per_day == LOCKED_BASE_XP["Writing"]


# -------------------------- Tier 3 (personalized) --------------------------


def test_tier3_personalized_above_age_grade_reduces_xp():
    # 4th-grade-age in 7th-grade Math: 25 + 2.5*(4-7) = 17.5
    p = _profile()
    p["current_grade_per_subject"]["Math"] = 7
    p["year_start_grade_per_subject"]["Math"] = 7
    res = resolve_daily_target(
        student_name="x", subject="Math",
        today=date(2026, 5, 8), student_profile=p,
    )
    assert res.tier == 3
    assert res.xp_per_day == 17.5


def test_tier3_personalized_below_age_grade_increases_xp():
    # 4th-grade-age in 1st-grade Reading: 25 + 2.5*(4-1) = 32.5
    p = _profile()
    p["current_grade_per_subject"]["Reading"] = 1
    p["year_start_grade_per_subject"]["Reading"] = 1
    res = resolve_daily_target(
        student_name="x", subject="Reading",
        today=date(2026, 5, 8), student_profile=p,
    )
    assert res.tier == 3
    assert res.xp_per_day == 32.5


def test_tier3_personalized_floor_at_10():
    # Extreme: 4th-grade-age in 12th-grade Math => 25 + 2.5*(4-12) = 5
    # Floor must clamp to 10.
    p = _profile()
    p["current_grade_per_subject"]["Math"] = 12
    p["year_start_grade_per_subject"]["Math"] = 12
    res = resolve_daily_target(
        student_name="x", subject="Math",
        today=date(2026, 5, 8), student_profile=p,
    )
    assert res.tier == 3
    assert res.xp_per_day == PERSONALIZED_FLOOR_XP


def test_tier3_does_not_apply_to_fastmath_or_vocabulary():
    p = _profile()
    p["current_grade_per_subject"]["Math"] = 7   # would be tier 3 for math
    res = resolve_daily_target(
        student_name="x", subject="Vocabulary",
        today=date(2026, 5, 8), student_profile=p,
    )
    assert res.tier == 4
    assert res.xp_per_day == LOCKED_BASE_XP["Vocabulary"]


# -------------------------- Tier 0a (XP override) --------------------------


def test_tier0a_xp_override_wins_absolutely():
    p = _profile()
    p["overrides"] = {"xp_per_day": {"Math": 42}}
    res = resolve_daily_target(
        student_name="x", subject="Math",
        today=date(2026, 5, 8), student_profile=p,
    )
    assert res.tier == 0
    assert res.source_label == "tier0a_coach_xp_override"
    assert res.xp_per_day == 42


def test_legacy_manual_xp_per_day_also_honored():
    p = _profile()
    p["manual_xp_per_day"] = {"Reading": 33}
    res = resolve_daily_target(
        student_name="x", subject="Reading",
        today=date(2026, 5, 8), student_profile=p,
    )
    assert res.tier == 0
    assert res.xp_per_day == 33


# -------------------------- base_target legacy -----------------------------


def test_base_target_locked_values():
    assert base_target("Math") == 25.0
    assert base_target("Writing") == 12.5
    assert base_target("Vocabulary") == 10.0
    assert base_target("Bogus") == 0.0


# -------------------------- resolve_all_subjects ---------------------------


def test_resolve_all_subjects_returns_all_seven():
    out = resolve_all_subjects(
        student_name="x",
        today=date(2026, 5, 8),
        student_profile=_profile(),
    )
    assert set(out.keys()) == {
        "Math", "Reading", "Language", "Writing", "Science",
        "Vocabulary", "FastMath",
    }
    for s, r in out.items():
        assert r.xp_per_day >= PERSONALIZED_FLOOR_XP
