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
           on success: clear matching dedupe keys from asked_log so
                       follow-up gaps for that field are detected fresh.
  5. Persist asked_log back to data/agent_state.json.

A single tick is bounded by MAX_DMS_PER_TICK to avoid spamming Slack
in case of bugs. If the cap is reached, the next tick continues.
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
    last_inbound_ts_by_coach: Dict[str, str] = field(default_factory=dict)
    version: int = STATE_VERSION

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: Dict[str, Any]) -> "AgentState":
        return cls(
            asked_log=dict(raw.get("asked_log") or {}),
            last_outbound_ts_by_coach=dict(raw.get("last_outbound_ts_by_coach") or {}),
            last_inbound_ts_by_coach=dict(raw.get("last_inbound_ts_by_coach") or {}),
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


def _ts_to_datetime(ts: str) -> Optional[datetime]:
    """Slack ts is 'seconds.microseconds'."""
    try:
        seconds = float(ts)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(seconds, tz=timezone.utc)


def _open_gaps_for_student(
    student_name: str,
    students_blob: Dict[str, Any],
    coaches_blob: Dict[str, Any],
) -> List[GoalGap]:
    """Recompute gaps just for one student so we can match a parsed
    patch back to the gap it resolved (and thus clear asked_log)."""
    return [
        g for g in find_gaps(
            students_config=students_blob,
            coaches_config=coaches_blob,
            asked_log={},          # ignore throttling for this lookup
        )
        if g.student_name == student_name
    ]


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
        last_outbound = state.last_outbound_ts_by_coach.get(coach_name)
        last_inbound = state.last_inbound_ts_by_coach.get(coach_name)
        # We listen since whichever marker is older — that way, if the
        # coach replies before we send a new question, we still catch it.
        marker = last_inbound or last_outbound
        since_dt = _ts_to_datetime(marker) if marker else None

        msgs = slack.fetch_recent_dm_thread(coach_user_id, since=since_dt)
        if not msgs:
            continue

        # Pair each coach reply with the most recent open gap for one of
        # their students. This is best-effort; the LLM/regex parser
        # often handles multi-student replies but we keep matching simple.
        coach_students: List[str] = (coaches_blob.get("coaches") or {}).get(coach_name, [])
        # Lisa Willis -> Lisa C Willis tolerance.
        if not coach_students and coach_name == "Lisa Willis":
            coach_students = (coaches_blob.get("coaches") or {}).get("Lisa C Willis", [])

        open_gaps_by_student: Dict[str, List[GoalGap]] = {}
        for student in coach_students:
            og = _open_gaps_for_student(student, students_blob, coaches_blob)
            if og:
                open_gaps_by_student[student] = og

        # Reload students_blob lazily after each successful patch so
        # follow-up replies see updated state.
        for m in msgs:
            if m.is_bot:
                continue
            text = (m.text or "").strip()
            if not text:
                continue

            # Pick a target gap. If only one student has an open gap,
            # use it; otherwise try matching by student name in the text.
            target_gap: Optional[GoalGap] = None
            if len(open_gaps_by_student) == 1:
                only_student = next(iter(open_gaps_by_student))
                target_gap = open_gaps_by_student[only_student][0]
            else:
                lower = text.lower()
                for student, gs in open_gaps_by_student.items():
                    if student.lower().split()[0] in lower:
                        target_gap = gs[0]
                        break
            if target_gap is None:
                continue

            result.replies_parsed += 1
            parsed = parse_reply(
                text,
                gap=target_gap,
                anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY"),
            )
            if not parsed.patches:
                result.parse_failures += 1
                continue

            for patch in parsed.patches:
                patch.source_ts = m.ts
                patch.source_coach = coach_name
                ok, errs = apply_patch(patch, students_path=students_path)
                if ok:
                    result.patches_applied += 1
                    # Clear any asked_log entries this patch resolves.
                    students_blob = json.loads(students_path.read_text())
                    refreshed = _open_gaps_for_student(
                        patch.student_name, students_blob, coaches_blob
                    )
                    refreshed_keys = {g.dedupe_key for g in refreshed}
                    state.asked_log = {
                        k: v for k, v in state.asked_log.items()
                        if not k.startswith(f"{patch.student_name}|")
                        or k in refreshed_keys
                    }
                    # Refresh open_gaps_by_student so subsequent messages
                    # in this loop see the new state.
                    open_gaps_by_student[patch.student_name] = refreshed
                    if not refreshed:
                        open_gaps_by_student.pop(patch.student_name, None)
                else:
                    result.parse_failures += 1
                    print(
                        f"WARN: rejected patch for {patch.student_name}: "
                        f"{', '.join(errs)}"
                    )

            state.last_inbound_ts_by_coach[coach_name] = m.ts

    _save_state(state_path, state)
    return result


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_coach_slack_ids() -> Dict[str, str]:
    raw = os.environ.get("COACH_SLACK_IDS_JSON", "").strip()
    if not raw:
        return {}
    try:
        return dict(json.loads(raw))
    except json.JSONDecodeError:
        print("WARN: COACH_SLACK_IDS_JSON is not valid JSON; ignoring.")
        return {}


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent.parent
    coach_ids = _load_coach_slack_ids()
    if not coach_ids:
        print(
            "NOOP: COACH_SLACK_IDS_JSON is empty; agent has no one to DM. "
            "Add coach Slack IDs and re-run."
        )
        return 0
    result = run_tick(repo_root=repo_root, coach_slack_ids=coach_ids)
    print(
        f"OK: phase={result.phase} dms={result.dms_sent} "
        f"replies={result.replies_parsed} patches={result.patches_applied} "
        f"parse_failures={result.parse_failures}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
