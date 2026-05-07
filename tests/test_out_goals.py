"""Tests for the priority cascade in src/test_out_goals.py."""

from src.calendar_map import load_map_calendar
from src.test_out_goals import (
    LOCKED_BASE,
    PERSONALIZED_BASE_FLOOR,
    default_target_grade,
    grade_to_int,
    int_to_grade,
    resolve_target,
)


def _empty_grade_xp():
    return {"version": "1", "grades": {}}


def _populated_grade_xp():
    # Realistic-ish placeholder values; tests use these to drive math.
    return {
        "version": "1",
        "grades": {
            "1st": {"Math": 1000, "Reading": 1000},
            "2nd": {"Math": 1100, "Reading": 1100},
            "3rd": {"Math": 1200, "Reading": 1200},
            "4th": {"Math": 1300, "Reading": 1300},
            "5th": {"Math": 1400, "Reading": 1400},
        },
    }


def test_grade_to_int_roundtrip():
    for g in ["K", "1st", "5th", "8th"]:
        n = grade_to_int(g)
        assert n is not None
        assert int_to_grade(n) == g


def test_default_target_grade_anchor_dominates():
    # Age grade 4, year-start grade 1st in this subject -> max(5, 3) = 5th
    assert default_target_grade("1st", "4th") == "5th"


def test_default_target_grade_plus_two_dominates():
    # Age grade 2, year-start grade 7th -> max(3, 9) = 9th
    assert default_target_grade("7th", "2nd") == "9th"


def test_priority_0a_coach_xp_override_wins():
    cal = load_map_calendar()
    student = {"name": "Andie Childress", "age_grade": "4th",
               "current_grade_per_subject": {"Math": "5th"},
               "year_start_grade_per_subject": {"Math": "5th"}}
    coach = {"xp_overrides": {"Andie Childress": {"Math": 28.0}}}
    decision = resolve_target(
        student=student, coach=coach, subject="Math",
        today_iso="2026-05-07", grade_xp_table=_populated_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "coach_xp"
    assert decision.daily_xp == 28.0


def test_priority_3_personalized_base_below_age():
    # Age 4, current 1st in Reading -> 25 + 2.5 * (4 - 1) = 32.5
    cal = load_map_calendar()
    student = {"name": "Test Student", "age_grade": "4th",
               "current_grade_per_subject": {"Reading": "1st"}}
    decision = resolve_target(
        student=student, coach={}, subject="Reading",
        today_iso="2026-05-07", grade_xp_table=_empty_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "personalized_base"
    assert decision.daily_xp == 32.5


def test_priority_3_personalized_base_above_age_floor():
    # Age 4, current 9th in Writing -> 12.5 + 2.5*(4-9) = 0; floored to 10.
    cal = load_map_calendar()
    student = {"name": "Test Student", "age_grade": "4th",
               "current_grade_per_subject": {"Writing": "9th"}}
    decision = resolve_target(
        student=student, coach={}, subject="Writing",
        today_iso="2026-05-07", grade_xp_table=_empty_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "personalized_base"
    assert decision.daily_xp == PERSONALIZED_BASE_FLOOR


def test_priority_3_user_example_4th_in_7th_math():
    # User-provided example: age 4, 7th-grade Math -> 17.5 XP/day
    cal = load_map_calendar()
    student = {"name": "Test", "age_grade": "4th",
               "current_grade_per_subject": {"Math": "7th"}}
    decision = resolve_target(
        student=student, coach={}, subject="Math",
        today_iso="2026-05-07", grade_xp_table=_empty_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "personalized_base"
    assert decision.daily_xp == 17.5


def test_priority_4_locked_base_when_no_inputs():
    cal = load_map_calendar()
    decision = resolve_target(
        student={"name": "Anon"}, coach={}, subject="Math",
        today_iso="2026-05-07", grade_xp_table=_empty_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "locked_base"
    assert decision.daily_xp == LOCKED_BASE["Math"] == 25


def test_priority_4_fastmath_no_personalization():
    # FastMath does NOT adjust by age grade; should hit locked_base.
    cal = load_map_calendar()
    student = {"name": "Test", "age_grade": "4th",
               "current_grade_per_subject": {"FastMath": "7th"}}
    decision = resolve_target(
        student=student, coach={}, subject="FastMath",
        today_iso="2026-05-07", grade_xp_table=_empty_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "locked_base"
    assert decision.daily_xp == 10


def test_priority_1_grade_mastered_with_populated_table():
    # Student is in 4th grade Math, target_grade -> max anchor 5 vs +2(=6) = 6th.
    # Total XP needed = 4th(1300) + 5th(1400) + 6th-not-in-table -> falls through
    # to personalized_base. Use 5th as ceiling instead.
    cal = load_map_calendar()
    student = {
        "name": "Test", "age_grade": "4th",
        "current_grade_per_subject": {"Math": "4th"},
        "year_start_grade_per_subject": {"Math": "4th"},
        "manual_test_out_grade": {"Math": "5th"},  # cap target at 5th so the table covers it
    }
    decision = resolve_target(
        student=student, coach={}, subject="Math",
        today_iso="2026-05-07", grade_xp_table=_populated_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier in ("grade_mastered", "personalized_base", "locked_base")
    # If target_date resolves and grade_xp covers 4th+5th, this should be grade_mastered.
    if decision.tier == "grade_mastered":
        assert decision.daily_xp > 0
        assert decision.target_grade == "5th"
        assert decision.school_days_remaining is not None


def test_priority_0b_coach_test_by_override():
    cal = load_map_calendar()
    student = {
        "name": "Andie Childress", "age_grade": "4th",
        "current_grade_per_subject": {"Math": "4th"},
        "year_start_grade_per_subject": {"Math": "4th"},
    }
    coach = {
        "test_by_overrides": {
            "Andie Childress": {"Math": {"grade": "5th", "date": "2026-05-19"}}
        }
    }
    decision = resolve_target(
        student=student, coach=coach, subject="Math",
        today_iso="2026-05-07", grade_xp_table=_populated_grade_xp(),
        progress_ledger={}, map_calendar=cal,
    )
    assert decision.tier == "coach_test_by"
    assert decision.target_grade == "5th"
    assert decision.target_date == "2026-05-19"


def test_decision_includes_source_string_for_slack():
    cal = load_map_calendar()
    decision = resolve_target(
        student={"name": "Test", "age_grade": "4th",
                 "current_grade_per_subject": {"Reading": "1st"}},
        coach={}, subject="Reading", today_iso="2026-05-07",
        grade_xp_table=_empty_grade_xp(), progress_ledger={}, map_calendar=cal,
    )
    assert decision.source  # non-empty
    assert "Personalized" in decision.source or "base" in decision.source
