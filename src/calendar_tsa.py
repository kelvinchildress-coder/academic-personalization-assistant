"""Calendar A school-day predicate for Texas Sports Academy.

Source: SY25-26 Master Calendar + Session Life Cycle Google Sheet,
"SY25-26 Calendars" tab + "Session Dates" tab. TSA is on Calendar A.

Holidays / breaks are stored as inclusive date ranges. Adding a new closure
is a one-line edit to NON_SCHOOL_RANGES below.

NOTE: This module deliberately does not call out to the network. The full
SY26-27 calendar should be appended here once finalized; until then the
module returns is_school_day() = False for any date past CALENDAR_END so
callers know to refresh.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Tuple


# ---------------------------------------------------------------------------
# SY25-26 Calendar A (TSA)
# ---------------------------------------------------------------------------

CALENDAR_START = date(2025, 8, 13)   # First day of Session 1
CALENDAR_END = date(2026, 6, 30)     # End of school year (provisional)

# Sessions: (first_day, last_day) inclusive.
SESSIONS: List[Tuple[date, date]] = [
    (date(2025, 8, 13), date(2025, 10, 3)),    # Session 1
    (date(2025, 10, 13), date(2025, 12, 19)),  # Session 2
    (date(2026, 1, 6), date(2026, 3, 13)),     # Session 3 (provisional)
    (date(2026, 3, 23), date(2026, 5, 29)),    # Session 4 (provisional)
]

# Anything not inside a session range is automatically NOT a school day, so
# the gaps between sessions (Oct 4-12, Dec 20-Jan 5, Mar 14-22) are handled
# implicitly. We only enumerate IN-SESSION closures here.
NON_SCHOOL_RANGES: List[Tuple[date, date]] = [
    # Labor Day
    (date(2025, 9, 1), date(2025, 9, 1)),
    # Thanksgiving week (Wed-Fri)
    (date(2025, 11, 26), date(2025, 11, 28)),
    # MLK Day
    (date(2026, 1, 19), date(2026, 1, 19)),
    # Presidents Day
    (date(2026, 2, 16), date(2026, 2, 16)),
    # Memorial Day
    (date(2026, 5, 25), date(2026, 5, 25)),
]


@dataclass(frozen=True)
class CalendarInfo:
    """Read-only view of the campus calendar."""

    name: str
    start: date
    end: date


CALENDAR_A = CalendarInfo("Calendar A (TSA)", CALENDAR_START, CALENDAR_END)


# ---------------------------------------------------------------------------
# Predicates
# ---------------------------------------------------------------------------

def _in_any_range(d: date, ranges: Iterable[Tuple[date, date]]) -> bool:
    return any(lo <= d <= hi for lo, hi in ranges)


def in_session(d: date) -> bool:
    """True iff d falls inside one of the SESSIONS ranges (inclusive)."""
    return _in_any_range(d, SESSIONS)


def is_school_day(d: date) -> bool:
    """A school day is: weekday + in a session + not a closure."""
    if d.weekday() >= 5:
        return False
    if not in_session(d):
        return False
    if _in_any_range(d, NON_SCHOOL_RANGES):
        return False
    return True


def school_days_between(start: date, end: date) -> int:
    """Count school days in [start, end] inclusive."""
    if end < start:
        return 0
    n = 0
    d = start
    while d <= end:
        if is_school_day(d):
            n += 1
        d += timedelta(days=1)
    return n


def current_session(d: date) -> int | None:
    """Return 1-based session index for d, or None if d is in a break."""
    for i, (lo, hi) in enumerate(SESSIONS, start=1):
        if lo <= d <= hi:
            return i
    return None


def session_bounds(d: date) -> Tuple[date, date] | None:
    """Return the (first, last) of the session containing d, or None."""
    for lo, hi in SESSIONS:
        if lo <= d <= hi:
            return (lo, hi)
    return None


def school_days_remaining_in_session(d: date) -> int:
    """School days from d (inclusive) to end of current session."""
    bounds = session_bounds(d)
    if bounds is None:
        return 0
    return school_days_between(d, bounds[1])


def school_days_remaining_in_week(d: date) -> int:
    """School days from d (inclusive) through the end of the week (Fri)."""
    end_of_week = d + timedelta(days=(4 - d.weekday()))
    if end_of_week < d:
        return 0
    return school_days_between(d, end_of_week)


def school_days_remaining_in_year(d: date) -> int:
    """School days from d (inclusive) to CALENDAR_END."""
    return school_days_between(d, CALENDAR_END)
