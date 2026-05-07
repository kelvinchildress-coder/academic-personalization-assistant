from datetime import date

from src.calendar_tsa import (
    is_weekday,
    is_school_day,
    previous_school_days,
    school_days_between,
    school_days_remaining,
)


def test_weekday_basic():
    # 2026-05-04 is a Monday
    assert is_weekday(date(2026, 5, 4)) is True
    # 2026-05-09 is a Saturday
    assert is_weekday(date(2026, 5, 9)) is False


def test_school_day_when_holidays_empty():
    # With HOLIDAYS empty, every weekday is a school day.
    assert is_school_day(date(2026, 5, 4)) is True
    assert is_school_day(date(2026, 5, 9)) is False  # Sat


def test_previous_school_days_window_of_5():
    # End on Mon 2026-05-11; previous 5 school days = the whole previous
    # week Mon 5/4 - Fri 5/8, oldest first.
    out = previous_school_days(date(2026, 5, 11), 5)
    assert out == [
        date(2026, 5, 4),
        date(2026, 5, 5),
        date(2026, 5, 6),
        date(2026, 5, 7),
        date(2026, 5, 8),
    ]


def test_school_days_between_skips_weekends():
    # Mon 5/4 .. Fri 5/8 inclusive = 5 school days
    assert school_days_between(date(2026, 5, 4), date(2026, 5, 8)) == 5
    # Mon 5/4 .. Mon 5/11 inclusive = 6 school days
    assert school_days_between(date(2026, 5, 4), date(2026, 5, 11)) == 6


def test_school_days_remaining_strict_after_today():
    # Today Mon 5/4, target Fri 5/8: 4 school days strictly after today.
    assert school_days_remaining(date(2026, 5, 4), date(2026, 5, 8)) == 4
    # Same day: 0
    assert school_days_remaining(date(2026, 5, 4), date(2026, 5, 4)) == 0
    # Past target: 0
    assert school_days_remaining(date(2026, 5, 8), date(2026, 5, 4)) == 0
