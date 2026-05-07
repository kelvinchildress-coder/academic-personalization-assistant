"""
scripts/post_eod.py
===================

End-of-day summary. Posts a final threaded reply on today's morning
parent message at ~17:30 CT. Does nothing if no parent exists for today.
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
    build_eod_summary,
    to_daily_results,
    load_daily_data,
)
from src.slack_threading import (        # noqa: E402
    default_state_path,
    load_state,
    is_state_for_today,
)
from scripts.post_morning import _slack_post  # noqa: E402


def main() -> int:
    channel = os.environ.get("SLACK_CHANNEL_ID")
    if not channel:
        print("ERROR: SLACK_CHANNEL_ID is required.", file=sys.stderr)
        return 2

    state = load_state(default_state_path())
    today = date.today()
    if not is_state_for_today(state, today):
        print(f"NOOP: no parent for {today.isoformat()}.")
        return 0

    raw = load_daily_data(REPO_ROOT / "data" / "latest.json")

    students_path = REPO_ROOT / "config" / "students.json"
    students_blob = json.loads(students_path.read_text())
    if isinstance(students_blob, dict) and "students" in students_blob:
        from src.models import Student
        students = [
            Student(name=name) for name in (students_blob.get("students") or {}).keys()
        ]
    else:
        from src.report_builder import load_students
        students = load_students(students_path)

    results = to_daily_results(raw, students, today)
    text = build_eod_summary(today, results)
    _slack_post(channel, text, thread_ts=state.parent_ts)
    print(f"OK: EOD summary posted for {today.isoformat()}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
