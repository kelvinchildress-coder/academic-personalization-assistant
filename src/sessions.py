"""Session-aware date helpers for TSA's 5-session-per-year calendar.

Reads config/sessions.json (the head-coach-supplied calendar of session
boundaries) and exposes lookup functions that other modules use to:

  - Determine which session a given date falls in.
  - Find the session that just ended (so EoQ summaries can fire).
  - Walk forward to the next session for forecasting.
  - Filter out untracked historical sessions so trend dashboards
    don't show empty bins.

This module never crashes on missing/null dates; untracked sessions are
returned as Session objects with start/end of None, and callers must
handle that case when they care.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SESSIONS_PATH = REPO_ROOT / "config" / "sessions.json"


@dataclass(frozen=True)
class Session:
    sy: str          # "25-26" or "26-27"
    n: int           # 1..5
    start: Optional[date]
    end: Optional[date]
    tracked: bool
    note: str = ""

    @property
    def label(self) -> str:
        return f"SY{self.sy} S{self.n}"

    def contains(self, d: date) -> bool:
        if not self.tracked or self.start is None or self.end is None:
            return False
        return self.start <= d <= self.end


def _parse_iso(s: Optional[str]) -> Optional[date]:
    if s is None:
        return None
    return date.fromisoformat(s)


def load_sessions(path: Optional[Path] = None) -> List[Session]:
    """Load all sessions across all school years, oldest first."""
    p = path or DEFAULT_SESSIONS_PATH
    raw = json.loads(p.read_text())
    out: List[Session] = []
    for sy_block in raw.get("school_years", []):
        sy = sy_block.get("sy", "")
        for s in sy_block.get("sessions", []):
            out.append(Session(
                sy=sy,
                n=int(s.get("n", 0)),
                start=_parse_iso(s.get("start")),
                end=_parse_iso(s.get("end")),
                tracked=bool(s.get("tracked", False)),
                note=s.get("note", "") or "",
            ))
    out.sort(key=lambda x: (x.sy, x.n))
    return out


def session_for_date(d: date, sessions: Optional[List[Session]] = None) -> Optional[Session]:
    """Return the (tracked) session containing `d`, or None if `d` is in
    a break, untracked session, or outside known years."""
    sessions = sessions or load_sessions()
    for s in sessions:
        if s.contains(d):
            return s
    return None


def current_session(today: Optional[date] = None) -> Optional[Session]:
    """Convenience: today's session, if any."""
    return session_for_date(today or date.today())


def session_just_ended(today: Optional[date] = None,
                       sessions: Optional[List[Session]] = None) -> Optional[Session]:
    """If today is the first calendar day after a tracked session's end,
    return that session (so EoQ summaries can fire). Otherwise None.
    Returns the most-recently-ended session whose end == today - 1 day
    or, if today falls in a between-sessions gap, the session whose end
    most recently preceded today (within 7 days)."""
    today = today or date.today()
    sessions = sessions or load_sessions()
    candidates = [s for s in sessions if s.tracked and s.end is not None and s.end < today]
    if not candidates:
        return None
    most_recent = max(candidates, key=lambda s: s.end)
    delta_days = (today - most_recent.end).days
    if delta_days <= 7:
        return most_recent
    return None


def next_session(after: Optional[date] = None,
                 sessions: Optional[List[Session]] = None) -> Optional[Session]:
    """Return the next tracked session whose start > `after`."""
    after = after or date.today()
    sessions = sessions or load_sessions()
    upcoming = [s for s in sessions if s.tracked and s.start is not None and s.start > after]
    if not upcoming:
        return None
    return min(upcoming, key=lambda s: s.start)


def tracked_sessions(sessions: Optional[List[Session]] = None) -> List[Session]:
    """All sessions where tracked=True (i.e. have data we can roll up)."""
    sessions = sessions or load_sessions()
    return [s for s in sessions if s.tracked and s.start is not None and s.end is not None]


def auth_allowed_domains(path: Optional[Path] = None) -> List[str]:
    """Email domains allowed by the dashboard OAuth wall. Read from
    config/sessions.json's `auth_allowed_email_domains` array.
    Returns lowercase domains without leading '@'."""
    p = path or DEFAULT_SESSIONS_PATH
    raw = json.loads(p.read_text())
    domains = raw.get("auth_allowed_email_domains", []) or []
    return [d.strip().lstrip("@").lower() for d in domains if d]
