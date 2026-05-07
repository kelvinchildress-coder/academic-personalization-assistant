"""
slack_threading.py
==================

Persists the day's parent-message thread_ts so that live updates and the
EOD summary can post as threaded replies (NOT edits) to the morning
parent message, per the locked rule:

  "Live updates are NEW threaded replies, NOT parent message edits."

State lives in data/state.json with shape:

  {
    "current_day": "2026-05-04",
    "parent_ts": "1715000000.000100",
    "channel": "C0123456",
    "live_events_posted": [
      "2026-05-04|Mason McDougald|Math|low_accuracy",
      ...
    ]
  }

When a NEW school day's morning report posts, the prior day's state is
overwritten (we keep only "today" state; long-term history lives in
Slack itself).

This module is pure I/O glue — Slack posting itself is done by the
existing src/slack_poster.py, called from scripts/post_*.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date
from pathlib import Path
from typing import List, Optional


STATE_VERSION = 1


@dataclass
class ThreadState:
    current_day: Optional[str] = None        # ISO date string
    parent_ts: Optional[str] = None
    channel: Optional[str] = None
    live_events_posted: List[str] = field(default_factory=list)
    version: int = STATE_VERSION

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: dict) -> "ThreadState":
        return cls(
            current_day=raw.get("current_day"),
            parent_ts=raw.get("parent_ts"),
            channel=raw.get("channel"),
            live_events_posted=list(raw.get("live_events_posted") or []),
            version=int(raw.get("version") or STATE_VERSION),
        )


def load_state(path: Path) -> ThreadState:
    """Load thread state, returning an empty ThreadState if absent."""
    if not path.exists():
        return ThreadState()
    try:
        return ThreadState.from_json(json.loads(path.read_text()))
    except (json.JSONDecodeError, ValueError):
        return ThreadState()


def save_state(path: Path, state: ThreadState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_json(), indent=2, sort_keys=True) + "\n")


def is_state_for_today(state: ThreadState, today: date) -> bool:
    """Returns True if the persisted state belongs to `today`."""
    return state.current_day == today.isoformat() and bool(state.parent_ts)


def reset_for_new_day(today: date, channel: str, parent_ts: str) -> ThreadState:
    """Build a fresh state for a new school day."""
    return ThreadState(
        current_day=today.isoformat(),
        parent_ts=parent_ts,
        channel=channel,
        live_events_posted=[],
    )


def record_live_events(state: ThreadState, event_keys: List[str]) -> ThreadState:
    seen = set(state.live_events_posted)
    for k in event_keys:
        seen.add(k)
    state.live_events_posted = sorted(seen)
    return state


def default_state_path(repo_root: Optional[Path] = None) -> Path:
    root = repo_root or Path(__file__).resolve().parent.parent
    return root / "data" / "state.json"
