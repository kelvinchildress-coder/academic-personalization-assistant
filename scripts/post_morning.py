"""
scripts/post_morning.py
=======================

Daily 07:00 CT entry point. Builds the tier-aware morning report from
data/latest.json + config/* and posts:
  1. A parent message in #sports.
  2. One threaded reply per coach.
  3. Persists the parent thread_ts to data/state.json so live-update and
     EOD scripts can thread under it.

Stale-data rule (locked): if the latest export is stale, we DO NOT post
the parent. Instead we DM the head coach and exit 0.

Env:
  SLACK_BOT_TOKEN         (required)
  SLACK_CHANNEL_ID        (required, e.g. C0XXXXXXX for #sports)
  HEAD_COACH_SLACK_ID     (optional but strongly recommended for stale DMs)
  COACH_SLACK_IDS_JSON    (optional JSON map: {"Coach Name": "U0XXXXXXX"})
  TIMEZONE                (optional; default "America/Chicago")
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.report_builder import (        # noqa: E402
    build_tiered_morning_payload,
    build_stale_data_dm,
    load_roster,
)
from src.student_progress import build_default_ledger  # noqa: E402
from src.slack_threading import (        # noqa: E402
    default_state_path,
    load_state,
    save_state,
    reset_for_new_day,
)

from src.history import (                # noqa: E402
    build_snapshot_from_report,
    write_snapshot,
)

def _load_coach_slack_ids() -> Dict[str, str]:
    raw = os.environ.get("COACH_SLACK_IDS_JSON", "").strip()
    if not raw:
        return {}
    try:
        return dict(json.loads(raw))
    except json.JSONDecodeError:
        print("WARN: COACH_SLACK_IDS_JSON is not valid JSON; ignoring.", file=sys.stderr)
        return {}


def _slack_post(channel: str, text: str, thread_ts: Optional[str] = None) -> dict:
    """Thin wrapper using the slack_sdk WebClient to keep this script
    self-contained. Falls back to printing if slack_sdk is missing
    (useful for local dry-runs)."""
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("DRY-RUN (no SLACK_BOT_TOKEN). Would post to", channel)
        print("---")
        print(text)
        print("---")
        return {"ok": True, "ts": "dry-run", "channel": channel}
    try:
        from slack_sdk import WebClient  # type: ignore
    except ImportError:
        print("ERROR: slack_sdk not installed; add it to requirements.txt", file=sys.stderr)
        raise
    client = WebClient(token=token)
    kwargs = {"channel": channel, "text": text, "unfurl_links": False, "unfurl_media": False}
    if thread_ts:
        kwargs["thread_ts"] = thread_ts
    resp = client.chat_postMessage(**kwargs)
    return resp.data if hasattr(resp, "data") else dict(resp)


def _slack_dm(user_id: str, text: str) -> None:
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token or not user_id:
        print(f"DRY-RUN DM to {user_id or '?'}:")
        print(text)
        return
    try:
        from slack_sdk import WebClient  # type: ignore
    except ImportError:
        print("ERROR: slack_sdk not installed.", file=sys.stderr)
        return
    client = WebClient(token=token)
    # Open a DM channel, then post.
    conv = client.conversations_open(users=user_id)
    ch = conv["channel"]["id"] if "channel" in conv.data else None
    if ch:
        client.chat_postMessage(channel=ch, text=text, unfurl_links=False)


def main() -> int:
    channel = os.environ.get("SLACK_CHANNEL_ID")
    if not channel:
        print("ERROR: SLACK_CHANNEL_ID is required.", file=sys.stderr)
        return 2

    coach_slack_ids = _load_coach_slack_ids()
    head_coach_slack_id = os.environ.get("HEAD_COACH_SLACK_ID") or None

    # Build the ledger and resolve tiers.
    ledger = build_default_ledger()
    today: date = ledger.school_day

    # Load configs needed by the payload builder.
    students_config = json.loads((REPO_ROOT / "config" / "students.json").read_text())
    grade_xp_blob = json.loads((REPO_ROOT / "config" / "grade_xp.json").read_text())
    # Normalize grade_xp_table to {int: {subject: float|None}}
    from src.student_progress import grade_key_to_int, normalize_subject
    grade_xp_table: Dict[int, Dict[str, Optional[float]]] = {}
    for k, subjects in (grade_xp_blob.get("grades") or {}).items():
        gi = grade_key_to_int(k)
        if gi is None:
            continue
        grade_xp_table[gi] = {
            (normalize_subject(s) or s): (None if v is None else float(v))
            for s, v in subjects.items()
        }
    roster = load_roster(REPO_ROOT / "config" / "coaches.json")

    payload = build_tiered_morning_payload(
        ledger=ledger,
        students_config=students_config,
        grade_xp_table=grade_xp_table,
        roster=roster,
        coach_slack_ids=coach_slack_ids,
    )

    if payload.is_stale:
        # Locked rule: skip the post entirely.
        print("STALE: skipping morning post; DMing head coach.")
        if head_coach_slack_id and payload.head_coach_dm_text:
            _slack_dm(head_coach_slack_id, payload.head_coach_dm_text)
        # Still record a stale-day snapshot so trend analysis knows
        # the day was attempted but skipped.
        try:
            snap = build_snapshot_from_report(today.isoformat(), {"students": []}, stale=True)
            write_snapshot(snap)
            print(f"[history] wrote stale snapshot for {today.isoformat()}")
        except Exception as e:
            print(f"[history] WARN: could not write stale snapshot: {e}", file=sys.stderr)
        return 0

    # Post parent.
    parent_resp = _slack_post(channel, payload.parent_text)
    parent_ts = parent_resp.get("ts")
    if not parent_ts:
        print("ERROR: parent post returned no ts; aborting.", file=sys.stderr)
        return 3

    # Post each coach block as a threaded reply.
    for block in payload.coach_blocks:
        _slack_post(channel, block.text, thread_ts=parent_ts)

    # Persist state.
    state = reset_for_new_day(today, channel, parent_ts)
    save_state(default_state_path(), state)

    # Phase 1: write daily history snapshot for trend analysis,
    # session rollups, and dashboard. Best-effort; never block the
    # main flow on a snapshot failure.
    try:
        report_dict = payload.to_history_dict() if hasattr(payload, "to_history_dict") else {
            "students": [
                {
                    "name": getattr(b, "coach_name", "") or "",
                    "coach": getattr(b, "coach_name", "") or "",
                    "subjects": {},
                }
                for b in payload.coach_blocks
            ]
        }
        snap = build_snapshot_from_report(today.isoformat(), report_dict, stale=False)
        write_snapshot(snap)
        print(f"[history] wrote snapshot for {today.isoformat()}")
    except Exception as e:
        print(f"[history] WARN: could not write snapshot: {e}", file=sys.stderr)

    print(f"OK: posted morning report for {today.isoformat()} (parent_ts={parent_ts})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
