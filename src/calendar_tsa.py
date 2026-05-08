"""
src/calendar_map.py
MAP-aware Calendar A helpers for the Academic Personalization Assistant.

This module sits ON TOP of src/calendar_tsa.py. It loads
config/map_calendar.json and exposes:

  - load_map_calendar(path=...)
  - is_school_day(iso, calendar_data)
  - school_days_between(start_iso, end_iso, calendar_data)
  - next_map_window_after(iso, calendar_data)
  - school_days_until_next_map(iso, calendar_data)
  - last_completed_school_day(iso, calendar_data)

All dates are ISO strings (YYYY-MM-DD). All ranges are INCLUSIVE on both ends
unless explicitly noted (function docstrings).

The legacy src/calendar_tsa.py remains the source of truth for the
morning-report cron schedule and per-day target weighting (which subjects
count today). This module is the source of truth for goal-date math.
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable, Optional, TypedDict


class MapWindow(TypedDict):
    season: str
    school_year: str
    start: str
    end: str


class MapCalendar(TypedDict):
    version: str
    calendar: str
    school_year: str
    next_school_year: str
    map_windows: list[MapWindow]
    no_school_days: list[dict]
    school_year_bounds: list[dict]


DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "map_calendar.json"


def load_map_calendar(path: Optional[Path] = None) -> MapCalendar:
    p = Path(path) if path else DEFAULT_PATH
    with p.open("r", encoding="utf-8") as f:
        return json.load(f)


def _expand_no_school(no_school_entries: Iterable[dict]) -> set[str]:
    out: set[str] = set()
    for entry in no_school_entries:
        if "date" in entry:
            out.add(entry["date"])
        elif "start" in entry and "end" in entry:
            d0 = date.fromisoformat(entry["start"])
            d1 = date.fromisoformat(entry["end"])
            cur = d0
            while cur <= d1:
                out.add(cur.isoformat())
                cur += timedelta(days=1)
    return out


def _summer_breaks(school_year_bounds: Iterable[dict]) -> list[tuple[str, str]]:
    """Return list of (exclusive_start, exclusive_end) summer-break intervals.
    Days strictly between SY N last_day and SY N+1 first_day are not school days."""
    bounds = sorted(
        [b for b in school_year_bounds if b.get("first_day") and b.get("last_day")],
        key=lambda b: b["last_day"],
    )
    summers: list[tuple[str, str]] = []
    for i in range(len(bounds)):
        last = bounds[i].get("last_day")
        # Find any bound that follows
        for j in range(i + 1, len(bounds)):
            nxt = bounds[j].get("first_day")
            if nxt and nxt > last:
                summers.append((last, nxt))
                break
    # Also handle the case where only the closing year's last_day is known
    # (preceding year's first_day is null but last_day is known) -> we cannot
    # define a summer for unknown predecessors; that's fine.
    return summers


def is_school_day(iso: str, cal: MapCalendar) -> bool:
    d = date.fromisoformat(iso)
    if d.weekday() >= 5:  # 5=Sat, 6=Sun
        return False
    no_school = _expand_no_school(cal["no_school_days"])
    if iso in no_school:
        return False
    for sy_last, sy_next_first in _summer_breaks(cal["school_year_bounds"]):
        if sy_last < iso < sy_next_first:
            return False
    return True


def school_days_between(start_iso: str, end_iso: str, cal: MapCalendar) -> int:
    """INCLUSIVE on both ends. Returns count of school days in [start, end]."""
    if end_iso < start_iso:
        return 0
    d0 = date.fromisoformat(start_iso)
    d1 = date.fromisoformat(end_iso)
    count = 0
    cur = d0
    while cur <= d1:
        if is_school_day(cur.isoformat(), cal):
            count += 1
        cur += timedelta(days=1)
    return count


def next_map_window_after(iso: str, cal: MapCalendar) -> Optional[MapWindow]:
    """Return the first MAP window whose start date is strictly after `iso`.
    None if no future MAP windows are configured."""
    candidates = [w for w in cal["map_windows"] if w["start"] > iso]
    if not candidates:
        return None
    return min(candidates, key=lambda w: w["start"])


def school_days_until_next_map(iso: str, cal: MapCalendar) -> Optional[int]:
    """School days strictly between `iso` (exclusive) and the next MAP start
    (exclusive). Returns None if no future MAP window exists."""
    nxt = next_map_window_after(iso, cal)
    if not nxt:
        return None
    d_after = (date.fromisoformat(iso) + timedelta(days=1)).isoformat()
    d_before = (date.fromisoformat(nxt["start"]) - timedelta(days=1)).isoformat()
    if d_before < d_after:
        return 0
    return school_days_between(d_after, d_before, cal)


def last_completed_school_day(iso: str, cal: MapCalendar, max_lookback: int = 90) -> Optional[str]:
    """Walk backward from `iso - 1` until we find a school day.
    Returns None if no school day found within `max_lookback` days."""
    d = date.fromisoformat(iso) - timedelta(days=1)
    for _ in range(max_lookback):
        s = d.isoformat()
        if is_school_day(s, cal):
            return s
        d -= timedelta(days=1)
    return None


def school_days_remaining_in_year(iso: str, cal: MapCalendar) -> Optional[int]:
    """School days from `iso` (inclusive) through the last_day of the current
    school year (inclusive). Returns None if `iso` is past all known years."""
    bounds = sorted(cal["school_year_bounds"], key=lambda b: b.get("last_day") or "")
    for b in bounds:
        last = b.get("last_day")
        first = b.get("first_day")
        if last and last >= iso and (first is None or first <= iso):
            return school_days_between(iso, last, cal)
    return None

def previous_school_days(iso: str, n: int, cal: Optional[MapCalendar] = None, max_lookback: int = 365) -> list[str]:
    """Return the most recent `n` school-day ISO dates strictly before `iso`,
    ordered oldest -> newest. Walks backward from `iso - 1`; gives up after
    `max_lookback` calendar days.

    Designed for trend-window math (e.g. last 5 school days). If `cal` is
    None, loads the default MAP calendar via load_map_calendar().
    """
    if cal is None:
        cal = load_map_calendar()
    out: list[str] = []
    d = date.fromisoformat(iso) - timedelta(days=1)
    for _ in range(max_lookback):
        s = d.isoformat()
        if is_school_day(s, cal):
            out.append(s)
            if len(out) >= n:
                break
        d -= timedelta(days=1)
    return list(reversed(out))
