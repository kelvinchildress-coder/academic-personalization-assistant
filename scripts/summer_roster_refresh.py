"""
scripts/summer_roster_refresh.py
================================

End-of-summer roster refresh. Runs once around late July to ask the head
coach for the next school year's coach + student grouping. The reply is
parsed by Anthropic (when available) and a PROPOSAL is written to
data/proposed_roster.json — never directly merged.

Why a proposal-only flow:
  Roster changes affect every downstream report. We want a human in the
  loop. The workflow opens a pull request that updates
  config/coaches.json and resets the per-student fields that should be
  re-collected (current_grade_per_subject, year_start_grade_per_subject)
  while preserving notes and overrides where the student persists.

Two-phase interaction:
  Phase R1 (initial ping):
    DMs the head coach a templated request with the CURRENT roster as
    context. Records "phase=R1" + outbound ts in
    data/summer_state.json. Exits.

  Phase R2 (parse-and-propose):
    On the next run, fetches replies since the R1 outbound ts. Parses
    via Anthropic into a structured roster proposal. Writes
    data/proposed_roster.json + a human-readable diff DM back to the
    head coach. The workflow then opens a PR for review.

Env:
  SLACK_BOT_TOKEN          required
  HEAD_COACH_SLACK_ID      required
  ANTHROPIC_API_KEY        optional (without it, only the initial ping is sent)
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.agent.slack_io import SlackIO  # noqa: E402


STATE_PATH = REPO_ROOT / "data" / "summer_state.json"
PROPOSAL_PATH = REPO_ROOT / "data" / "proposed_roster.json"
COACHES_PATH = REPO_ROOT / "config" / "coaches.json"
STUDENTS_PATH = REPO_ROOT / "config" / "students.json"


# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------


@dataclass
class SummerState:
    phase: str = "idle"                  # idle | R1 | R2_done
    sent_ts: Optional[str] = None
    sent_at: Optional[str] = None        # ISO datetime
    season_year: Optional[int] = None    # the SY we're prepping for, e.g. 2026
    version: int = 1

    def to_json(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_json(cls, raw: Dict[str, Any]) -> "SummerState":
        return cls(
            phase=str(raw.get("phase") or "idle"),
            sent_ts=raw.get("sent_ts"),
            sent_at=raw.get("sent_at"),
            season_year=raw.get("season_year"),
            version=int(raw.get("version") or 1),
        )


def _load_state() -> SummerState:
    if not STATE_PATH.exists():
        return SummerState()
    try:
        return SummerState.from_json(json.loads(STATE_PATH.read_text()))
    except (json.JSONDecodeError, ValueError):
        return SummerState()


def _save_state(state: SummerState) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state.to_json(), indent=2, sort_keys=True) + "\n"
    )


# ---------------------------------------------------------------------------
# Phase R1 — initial ping
# ---------------------------------------------------------------------------


def _format_current_roster(coaches_blob: Dict[str, Any]) -> str:
    lines = []
    for coach, students in (coaches_blob.get("coaches") or {}).items():
        lines.append(f"• *{coach}*: {', '.join(students) if students else '(none)'}")
    return "\n".join(lines)


def _phase_r1_text(coaches_blob: Dict[str, Any], season_year: int) -> str:
    return (
        f":sun_with_face: *End-of-summer roster check — SY{season_year}-{(season_year + 1) % 100:02d}*\n"
        f"Could you confirm the coach + student groupings for the upcoming "
        f"school year? Here's what I have on file right now:\n\n"
        f"{_format_current_roster(coaches_blob)}\n\n"
        f"Reply with any changes (additions, removals, swaps). I'll draft "
        f"a proposed roster update and send it back for your review before "
        f"anything is committed."
    )


def _run_phase_r1(slack: SlackIO, head_coach_user_id: str, season_year: int) -> Optional[str]:
    coaches_blob = json.loads(COACHES_PATH.read_text())
    text = _phase_r1_text(coaches_blob, season_year)
    return slack.send_dm(head_coach_user_id, text)


# ---------------------------------------------------------------------------
# Phase R2 — parse and propose
# ---------------------------------------------------------------------------


_LLM_SYSTEM = (
    "You convert a head coach's free-text reply about next year's roster "
    "into a STRICT JSON object. Output JSON only, no prose. Schema:\n"
    "{\n"
    '  "coaches": { "<coach_name>": ["<student>", ...] },\n'
    '  "added_students": ["<name>", ...],\n'
    '  "removed_students": ["<name>", ...],\n'
    '  "renamed_coaches": { "<old>": "<new>" },\n'
    '  "notes": "<freeform context, optional>"\n'
    "}\n"
    "If the reply is unclear, return the current roster unchanged. "
    "Always include EVERY coach and EVERY student that should exist next "
    "year — this output represents the desired final state, not a delta."
)


def _parse_with_anthropic(
    reply_text: str,
    current_coaches: Dict[str, Any],
    api_key: str,
) -> Optional[Dict[str, Any]]:
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=os.environ.get("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        max_tokens=2000,
        system=_LLM_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"Current roster (JSON):\n{json.dumps(current_coaches, indent=2)}\n\n"
                f"Head coach reply:\n{reply_text}\n\n"
                "Return JSON only."
            ),
        }],
    )
    if not msg.content:
        return None
    raw = ""
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            raw += block.text
    raw = raw.strip()
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


def _build_diff_text(old: Dict[str, Any], new: Dict[str, Any]) -> str:
    old_coaches = set((old.get("coaches") or {}).keys())
    new_coaches = set((new.get("coaches") or {}).keys())
    added_coaches = sorted(new_coaches - old_coaches)
    removed_coaches = sorted(old_coaches - new_coaches)
    lines = []
    if added_coaches:
        lines.append(f"+ Coaches added: {', '.join(added_coaches)}")
    if removed_coaches:
        lines.append(f"- Coaches removed: {', '.join(removed_coaches)}")

    old_students_map = {s: c for c, ss in (old.get("coaches") or {}).items() for s in (ss or [])}
    new_students_map = {s: c for c, ss in (new.get("coaches") or {}).items() for s in (ss or [])}
    added_students = sorted(set(new_students_map) - set(old_students_map))
    removed_students = sorted(set(old_students_map) - set(new_students_map))
    moved = sorted(
        s for s in (set(old_students_map) & set(new_students_map))
        if old_students_map[s] != new_students_map[s]
    )
    if added_students:
        lines.append(f"+ Students added: {', '.join(added_students)}")
    if removed_students:
        lines.append(f"- Students removed: {', '.join(removed_students)}")
    for s in moved:
        lines.append(f"~ {s}: {old_students_map[s]} -> {new_students_map[s]}")
    if not lines:
        lines.append("(no changes detected)")
    return "\n".join(lines)


def _run_phase_r2(
    slack: SlackIO,
    head_coach_user_id: str,
    state: SummerState,
) -> bool:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("NOOP: phase R2 needs ANTHROPIC_API_KEY; will retry next run.")
        return False

    since = None
    if state.sent_ts:
        try:
            since = datetime.fromtimestamp(float(state.sent_ts), tz=timezone.utc)
        except (TypeError, ValueError):
            since = None

    msgs = slack.fetch_recent_dm_thread(head_coach_user_id, since=since)
    coach_replies = [m for m in msgs if not m.is_bot and (m.text or "").strip()]
    if not coach_replies:
        print("NOOP: no head-coach reply yet for summer roster.")
        return False

    combined = "\n\n".join(m.text for m in coach_replies)
    current = json.loads(COACHES_PATH.read_text())
    proposed = _parse_with_anthropic(combined, current, api_key)
    if not proposed:
        print("WARN: could not parse head-coach reply; leaving phase R1 active.")
        return False

    # Preserve top-level fields the LLM didn't touch.
    out = {
        "head_coach": current.get("head_coach"),
        "channel": current.get("channel"),
        "coaches": proposed.get("coaches") or current.get("coaches"),
    }
    PROPOSAL_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROPOSAL_PATH.write_text(json.dumps(out, indent=2, sort_keys=True) + "\n")

    diff = _build_diff_text(current, out)
    slack.send_dm(
        head_coach_user_id,
        (
            ":bookmark_tabs: *Proposed roster update*\n"
            f"```{diff}```\n"
            "I've written the full proposal to `data/proposed_roster.json`. "
            "A pull request will open shortly so you can review and merge."
        ),
    )
    return True


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def _is_summer_window(today: date) -> bool:
    """Run window: late July through first week of August."""
    return (today.month == 7 and today.day >= 20) or (
        today.month == 8 and today.day <= 7
    )


def _season_year(today: date) -> int:
    """The SY year the refresh is preparing FOR (the year of the new SY's fall)."""
    return today.year


def main() -> int:
    today = date.today()
    if not _is_summer_window(today) and not os.environ.get("FORCE_SUMMER_REFRESH"):
        print(f"NOOP: {today.isoformat()} is outside the summer roster window.")
        return 0

    head_coach_user_id = os.environ.get("HEAD_COACH_SLACK_ID")
    if not head_coach_user_id:
        print("ERROR: HEAD_COACH_SLACK_ID is required.", file=sys.stderr)
        return 2

    slack = SlackIO()
    state = _load_state()

    if state.phase in ("idle", "R2_done") or state.season_year != _season_year(today):
        # Send phase R1 ping.
        season_year = _season_year(today)
        ts = _run_phase_r1(slack, head_coach_user_id, season_year)
        state = SummerState(
            phase="R1",
            sent_ts=ts,
            sent_at=datetime.now(timezone.utc).isoformat(),
            season_year=season_year,
        )
        _save_state(state)
        print(f"OK: sent summer roster R1 ping (ts={ts}).")
        return 0

    if state.phase == "R1":
        ok = _run_phase_r2(slack, head_coach_user_id, state)
        if ok:
            state.phase = "R2_done"
            _save_state(state)
            print("OK: wrote data/proposed_roster.json. PR step will open the PR.")
        return 0

    print(f"NOOP: unknown phase '{state.phase}'.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
