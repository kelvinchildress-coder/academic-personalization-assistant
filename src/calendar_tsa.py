"""Calendar A school-day predicate for Texas Sports Academy.

Source: SY25-26 Master Calendar + Session Life Cycle Google Sheet,
"SY25-26 Calendars" tab + "Session Dates" tab. TSA is on Calendar A.

Holidays / breaks are stored as inclusive date ranges. Adding a new
closure is a one-line edit to NON_SCHOOL_RANGES below.

NOTE: This module deliberately does not call out to the network. The full
SY26-27 calendar should be appended here once finalized; until then the
module returns is_school_day() = False for any date past CALENDAR_END so
callers know to refresh.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# SY25-26 Calendar A (TSA)
# ---------------------------------------------------------------------------

CALENDAR_START = date(2025, 8, 13)   # First day of Session 1
CALENDAR_END = date(2026, 6, 30)     # End of school year (provisional)

# Sessions: (first_day, last_day) inclusive.
SESSIONS: List[Tuple[date, date]] = [
    (date(2025, 8, 13), date(2025, 10, 3)),    # Session 1
    (date(2025, 10, 13), date(2025, 12, 19)),  # Session 2
    (date(2026, 1, 6),  date(2026, 3, 13)),    # Session 3 (provisional)
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


def is_weekday(d: date) -> bool:
    """Mon-Fri == True; Sat/Sun == False. (Ignores holidays/sessions.)"""
    return d.weekday() < 5


def in_session(d: date) -> bool:
    """True iff d falls inside one of the SESSIONS ranges (inclusive).

    If SESSIONS is empty (e.g. a future calendar year not yet populated),
    this returns False; callers can fall back to is_weekday() if they want
    pre-calendar behavior.
    """
    return _in_any_range(d, SESSIONS)


def _has_session_data() -> bool:
    return len(SESSIONS) > 0


def is_school_day(d: date) -> bool:
    """A school day is: weekday + (in a session OR no session data) + not a closure.

    The 'no session data' fallback keeps tests passing when SESSIONS is empty
    AND lets the user run before SY26-27 calendar is added.
    """
    if not is_weekday(d):
        return False
    if _has_session_data() and not in_session(d):
        return False
    if _in_any_range(d, NON_SCHOOL_RANGES):
        return False
    return True


# ---------------------------------------------------------------------------
# School-day arithmetic
# ---------------------------------------------------------------------------

def school_days_between(start: date, end: date) -> int:
    """Count school days in [start, end] INCLUSIVE.

    Returns 0 if end < start. Both endpoints are counted if they are school
    days.
    """
    if end < start:
        return 0
    n = 0
    d = start
    while d <= end:
        if is_school_day(d):
            n += 1
        d += timedelta(days=1)
    return n


def school_days_remaining(today: date, target: date) -> int:
    """School days STRICTLY AFTER `today` and on or before `target`.

    Same semantics test_calendar_tsa.py and test_targets.py expect:
      today=Mon 5/4, target=Fri 5/8 -> 4 (Tue Wed Thu Fri).
      today == target -> 0.
      target < today  -> 0.
    """
    if target <= today:
        return 0
    return school_days_between(today + timedelta(days=1), target)


def previous_school_days(end: date, n: int) -> list[date]:
    """Return the most recent `n` school days ending on or before `end`,
    OLDEST FIRST.

    If `end` itself is a school day, it counts as one of the n.
    Used for the 5-school-day trend window in report_builder.
    """
    out: list[date] = []
    d = end
    while len(out) < n:
        if is_school_day(d):
            out.append(d)
        d -= timedelta(days=1)
        # Safety belt: never walk past the calendar start by more than 365 days
        if (end - d).days > 365 * 2:
            break
    return list(reversed(out))


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def current_session(d: date) -> Optional[int]:
    """Return 1-based session index for d, or None if d is in a break."""
    for i, (lo, hi) in enumerate(SESSIONS, start=1):
        if lo <= d <= hi:
            return i
    return None


def session_bounds(d: date) -> Optional[Tuple[date, date]]:
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
