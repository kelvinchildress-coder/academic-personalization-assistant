"""
scripts/post_live_update.py
===========================

Runs every ~2 hours during school hours. Detects new low-accuracy /
overperform events and posts them as NEW threaded replies under today's
morning parent message. Never edits the parent.

Env: same as post_morning.py.
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.report_builder import (         # noqa: E402
    detect_new_live_events,
    build_live_update_reply,
    event_key,
    load_roster,
    load_students,
    to_daily_results,
    load_daily_data,
)
from src.slack_threading import (        # noqa: E402
    default_state_path,
    load_state,
    save_state,
    is_state_for_today,
    record_live_events,
)
from scripts.post_morning import _slack_post, _load_coach_slack_ids  # noqa: E402


def main() -> int:
    channel = os.environ.get("SLACK_CHANNEL_ID")
    if not channel:
        print("ERROR: SLACK_CHANNEL_ID is required.", file=sys.stderr)
        return 2

    state_path = default_state_path()
    state = load_state(state_path)

    today = date.today()
    if not is_state_for_today(state, today):
        print(f"NOOP: no morning parent for {today.isoformat()}; skipping live update.")
        return 0

    raw = load_daily_data(REPO_ROOT / "data" / "latest.json")
    students_path = REPO_ROOT / "config" / "students.json"

    # The legacy load_students expects a list-of-dicts shape. Our
    # students.json is keyed by name; build a tolerant adapter.
    students_blob = json.loads(students_path.read_text())
    if isinstance(students_blob, dict) and "students" in students_blob:
        from src.models import Student
        students = [
            Student(name=name) for name in (students_blob.get("students") or {}).keys()
        ]
    else:
        students = load_students(students_path)

    results = to_daily_results(raw, students, today)
    new_events = detect_new_live_events(results, set(state.live_events_posted))
    if not new_events:
        print("NOOP: no new live events.")
        return 0

    coach_ids = _load_coach_slack_ids()
    roster = load_roster(REPO_ROOT / "config" / "coaches.json")

    keys = []
    for student_result, subject_result, kind in new_events:
        coach = roster.coach_for_student(student_result.name) or "Unassigned"
        coach_id = coach_ids.get(coach)
        text = build_live_update_reply(
            coach_slack_id=coach_id,
            coach_name=coach,
            student_name=student_result.name,
            subject=subject_result,
            kind=kind,
        )
        _slack_post(channel, text, thread_ts=state.parent_ts)
        keys.append(event_key(student_result, subject_result, kind))

    state = record_live_events(state, keys)
    save_state(state_path, state)
    print(f"OK: posted {len(keys)} live update(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
