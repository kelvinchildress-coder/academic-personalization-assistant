"""
pending_state.py
================

Tiny on-disk state layer for the propose-then-confirm UX.

When a coach sends a free-form intent (e.g. "Marcus is out today"),
the agent does NOT immediately write to config/students.json. Instead
it:

  1. Builds a Proposal describing what it would do
  2. Stores the Proposal in data/pending_proposals.json keyed by
     (coach_slack_id, dm_channel_id)
  3. Replies in the same DM thread asking the coach to confirm
  4. On a ConfirmYes intent: pops the Proposal and applies it
  5. On a ConfirmNo intent: drops the Proposal silently
  6. On a Refine: replaces the Proposal with the new parse

This file does NOT know about Slack — it just persists JSON. The
agent runner is responsible for routing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class Proposal:
    """A staged intent awaiting coach confirmation."""
    coach_slack_id: str
    channel_id: str
    intent_kind: str                       # "pause" | "half_target" | "group_rule"
    payload: Dict[str, Any]                # serialized Intent dataclass
    expanded_targets: List[str] = field(default_factory=list)
    summary_text: str = ""                 # human-readable for confirm DM
    raw_coach_text: str = ""
    created_at: str = ""

    def key(self) -> str:
        return f"{self.coach_slack_id}::{self.channel_id}"


def _load(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {"proposals": {}}
    try:
        blob = json.loads(path.read_text() or "{}")
    except json.JSONDecodeError:
        blob = {}
    if "proposals" not in blob:
        blob["proposals"] = {}
    return blob


def _save(path: Path, blob: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob, indent=2, sort_keys=True))


def stage_proposal(path: Path, prop: Proposal) -> None:
    """Save a Proposal, overwriting any prior pending one for the same key."""
    if not prop.created_at:
        prop.created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    blob = _load(path)
    blob["proposals"][prop.key()] = asdict(prop)
    _save(path, blob)


def get_proposal(
    path: Path, coach_slack_id: str, channel_id: str,
) -> Optional[Proposal]:
    blob = _load(path)
    raw = blob["proposals"].get(f"{coach_slack_id}::{channel_id}")
    if not raw:
        return None
    return Proposal(**raw)


def pop_proposal(
    path: Path, coach_slack_id: str, channel_id: str,
) -> Optional[Proposal]:
    blob = _load(path)
    key = f"{coach_slack_id}::{channel_id}"
    raw = blob["proposals"].pop(key, None)
    _save(path, blob)
    if not raw:
        return None
    return Proposal(**raw)


def list_proposals(path: Path) -> List[Proposal]:
    blob = _load(path)
    return [Proposal(**v) for v in blob["proposals"].values()]


def clear_stale(path: Path, *, max_age_hours: int = 48) -> int:
    """Drop proposals older than max_age_hours. Returns count removed."""
    blob = _load(path)
    cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
    removed = 0
    keep: Dict[str, Any] = {}
    for k, v in blob["proposals"].items():
        try:
            ts = datetime.fromisoformat(v.get("created_at", "")).timestamp()
        except ValueError:
            ts = 0
        if ts >= cutoff:
            keep[k] = v
        else:
            removed += 1
    blob["proposals"] = keep
    _save(path, blob)
    return removed
