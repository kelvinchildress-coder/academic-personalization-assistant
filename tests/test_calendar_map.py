"""Tests for src/calendar_map.py."""

import json
from pathlib import Path

import pytest

from src.calendar_map import (
    is_school_day,
    school_days_between,
    next_map_window_after,
    school_days_until_next_map,
    last_completed_school_day,
    load_map_calendar,
)


@pytest.fixture(scope="module")
def cal():
    return load_map_calendar()


def test_weekend_is_not_school_day(cal):
    assert is_school_day("2026-05-09", cal) is False  # Saturday
    assert is_school_day("2026-05-10", cal) is False  # Sunday


def test_memorial_day_is_holiday(cal):
    assert is_school_day("2026-05-25", cal) is False


def test_summer_break_excluded(cal):
    # Day strictly between SY25-26 last_day (2026-06-05) and SY26-27 first_day (2026-08-12).
    assert is_school_day("2026-07-04", cal) is False


def test_normal_weekday_is_school_day(cal):
    assert is_school_day("2026-05-07", cal) is True   # Thursday during SY


def test_first_day_of_sy26_27_is_school_day(cal):
    assert is_school_day("2026-08-12", cal) is True


def test_winter_break_range_excluded(cal):
    for d in ["2026-12-21", "2026-12-25", "2026-12-31", "2027-01-01"]:
        assert is_school_day(d, cal) is False, d
    assert is_school_day("2027-01-04", cal) is True   # Monday after winter break


def test_school_days_between_inclusive(cal):
    # Mon May 4 through Fri May 8, 2026 -> 5 school days
    assert school_days_between("2026-05-04", "2026-05-08", cal) == 5

def test_school_days_between_skips_holiday(cal):
    # 2026-05-22 (Fri), 5/23-24 weekend, 5/25 Memorial Day (holiday),
    # 5/26 Tue, 5/27 Wed, 5/28 Thu, 5/29 Fri => 1 + 4 = 5 school days
    assert school_days_between("2026-05-22", "2026-05-29", cal) == 5

def test_next_map_window_after_today(cal):
    nxt = next_map_window_after("2026-05-07", cal)
    assert nxt is not None
    assert nxt["season"] == "Spring"
    assert nxt["school_year"] == "SY25-26"
    assert nxt["start"] == "2026-05-19"


def test_next_map_window_skips_current_window(cal):
    # When we're on the start day of a window, "after" semantics should pick the next window.
    nxt = next_map_window_after("2026-05-19", cal)
    assert nxt is not None
    assert nxt["season"] == "Fall"
    assert nxt["school_year"] == "SY26-27"


def test_school_days_until_next_map_today(cal):
    # From 2026-05-07 (Thursday) to 2026-05-19 (Tuesday) exclusive of both ends.
    # School days in [2026-05-08, 2026-05-18]: Fri 5/8, Mon-Fri 5/11-15, Mon 5/18 = 7
    n = school_days_until_next_map("2026-05-07", cal)
    assert n == 7


def test_last_completed_school_day_after_weekend(cal):
    # Monday 2026-05-04 -> last completed = Friday 2026-05-01
    assert last_completed_school_day("2026-05-04", cal) == "2026-05-01"


def test_last_completed_school_day_after_holiday(cal):
    # Tuesday 2026-05-26 (after Memorial Day) -> last completed = Friday 2026-05-22
    assert last_completed_school_day("2026-05-26", cal) == "2026-05-22"
