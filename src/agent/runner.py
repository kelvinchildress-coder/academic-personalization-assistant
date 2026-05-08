"""
runner.py
=========

Orchestrates one tick of the agent loop:

  1. Load configs and asked-log state.
  2. find_gaps() to prioritize work.
  3. For each new gap (respecting MIN_REASK_DAYS):
       * draft_question()
       * slack_io.send_dm()
       * record dedupe_key in asked_log
  4. For each coach we've recently messaged:
       * fetch_recent_dm_thread() since our outbound ts
       * for each new coach reply:
           parse_reply() -> StructuredPatch
           config_writer.apply_patch()
           on success: mark the corresponding gap as resolved (remove
                       from asked_log so future gaps for that field are
                       fresh).
  5. Persist asked_log back to data/agent_state.json.

A single tick is bounded by MAX_DMS_PER_TICK to avoid spamming Slack
in case of bugs. If the count is reached, the next tick continues.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .gap_finder import GoalGap, find_gaps, is_phase_one
from .question_drafter import draft_question
from .reply_parser import parse_reply
from .config_writer import apply_patch
from .slack_io import SlackIO


MAX_DMS_PER_TICK = 5     # cap outbound messages per run
STATE_VERSION = 1


@dataclass
class AgentState:
    asked_log: Dict[str, str] = field(default_factory=dict)
    last_outbound_ts_by_coach: Dict[str, str] = field(default_factory=dict)
    version: int = STATE_VERSION

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: Dict[str, Any]) -> "AgentState":
        return cls(
            asked_log=dict(raw.get("asked_log") or {}),
            last_outbound_ts_by_coach=dict(raw.get("last_outbound_ts_by_coach") or {}),
            version=int(raw.get("version") or STATE_VERSION),
        )


def _load_state(path: Path) -> AgentState:
    if not path.exists():
        return AgentState()
    try:
        return AgentState.from_json(json.loads(path.read_text()))
    except (json.JSONDecodeError, ValueError):
        return AgentState()


def _save_state(path: Path, state: AgentState) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state.to_json(), indent=2, sort_keys=True) + "\n")


# ---------------------------------------------------------------------------
# Main tick
# ---------------------------------------------------------------------------


@dataclass
class TickResult:
    dms_sent: int = 0
    replies_parsed: int = 0
    patches_applied: int = 0
    parse_failures: int = 0
    phase: str = "phase2"


def run_tick(
    *,
    repo_root: Path,
    coach_slack_ids: Dict[str, str],
    today: Optional[date] = None,
    slack: Optional[SlackIO] = None,
) -> TickResult:
    today = today or date.today()
    state_path = repo_root / "data" / "agent_state.json"
    students_path = repo_root / "config" / "students.json"
    coaches_path = repo_root / "config" / "coaches.json"

    state = _load_state(state_path)
    students_blob = json.loads(students_path.read_text())
    coaches_blob = json.loads(coaches_path.read_text())

    gaps = find_gaps(
        students_config=students_blob,
        coaches_config=coaches_blob,
        asked_log=state.asked_log,
        today=today,
    )
    result = TickResult(phase="phase1" if is_phase_one(gaps) else "phase2")

    slack = slack or SlackIO()

    # --- Outbound: draft + send DMs for top-priority gaps ----------------
    sent = 0
    for gap in gaps:
        if sent >= MAX_DMS_PER_TICK:
            break
        if not gap.coach_name:
            continue
        coach_user_id = coach_slack_ids.get(gap.coach_name)
        if not coach_user_id:
            continue

        profile = (students_blob.get("students") or {}).get(gap.student_name) or {}
        drafted = draft_question(
            gap,
            student_profile=profile,
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
        )
        ts = slack.send_dm(coach_user_id, drafted.text)
        state.asked_log[gap.dedupe_key] = today.isoformat()
        if ts:
            state.last_outbound_ts_by_coach[gap.coach_name] = ts
        sent += 1
    result.dms_sent = sent

    # --- Inbound: parse coach replies since our last outbound -------------
    for coach_name, coach_user_id in coach_slack_ids.items():
        last_ts = state.last_outbound_ts_by_coach.get(coach_name)
        since_dt: Optional[datetime] = None
        if last_ts:
            try:
                since_dt = dat
