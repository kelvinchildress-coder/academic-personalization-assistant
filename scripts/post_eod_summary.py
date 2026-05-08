#!/usr/bin/env python3
"""Post the end-of-day summary as a threaded reply under the morning
parent: list students who did not finish Green, grouped by coach.

Usage:
    python -m scripts.post_eod_summary
    python -m scripts.post_eod_summary --dry-run
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.calendar_tsa import is_school_day  # noqa: E402
from src.report_builder import (  # noqa: E402
    build_eod_summary,
    load_daily_data,
    load_roster,
    load_students,
    to_daily_results,
)
from src.slack_poster import SlackPoster  # noqa: E402
from src.history import (  # noqa: E402
    build_snapshot_from_report,
    read_snapshot,
    write_snapshot,
)

CT = ZoneInfo("America/Chicago")


def _today_ct() -> date:
    return datetime.now(CT).date()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--data-file", default="data/latest.json")
    args = parser.parse_args()

    today = _today_ct()
    if not is_school_day(today):
        print(f"[eod] {today} not a school day; exiting.")
        return 0

    morning_path = REPO_ROOT / "data" / "morning_state.json"
    if not morning_path.exists():
        print("[eod] morning_state.json missing; exiting.")
        return 0
    morning_state = json.loads(morning_path.read_text())
    if morning_state.get("date") != today.isoformat():
        print(f"[eod] morning_state is for {morning_state.get('date')}, not today; exiting.")
        return 0

    data_path = REPO_ROOT / args.data_file
    if not data_path.exists():
        print(f"[eod] {data_path} missing; exiting.")
        return 0
    raw = load_daily_data(data_path)
    if raw.get("date") != today.isoformat():
        print(f"[eod] data/latest.json is for {raw.get('date')}; exiting.")
        return 0

    roster = load_roster(REPO_ROOT / "config" / "coaches.json")
    students_path = REPO_ROOT / "students.json"
    students = load_students(students_path) if students_path.exists() else []
    results = to_daily_results(raw, students, today)
    slack_ids: dict[str, str] = morning_state.get("slack_ids", {})

    text = build_eod_summary(today, results, roster, slack_ids)

    if args.dry_run:
        print("[eod] DRY RUN — would post:")
        print(text)
        return 0

  poster = SlackPoster()
    poster.post(morning_state["channel"], text, thread_ts=morning_state["parent_ts"])
    print("[eod] posted.")

    # Phase 1: refresh the day's history snapshot with end-of-day actuals.
    # If a morning snapshot exists for today, we update it in-place; otherwise
    # we write a fresh EOD-only snapshot. Best-effort; never block on this.
    try:
        existing = read_snapshot(today.isoformat()) or {}
        eod_payload = {
            "students": [
                {
                    "name": r.student_name,
                    "coach": r.coach_name,
                    "subjects": {
                        s.subject: {
                            "target": s.target_xp,
                            "actual": s.actual_xp,
                            "tier": s.tier if hasattr(s, "tier") else "unknown",
                            "status": s.status,
                        }
                        for s in r.subject_results
                    } if hasattr(r, "subject_results") else {},
                }
                for r in results
            ]
        }
        snap = build_snapshot_from_report(today.isoformat(), eod_payload, stale=existing.get("stale", False))
        write_snapshot(snap)
        print(f"[history] updated snapshot for {today.isoformat()} with EOD actuals")
    except Exception as e:
        print(f"[history] WARN: could not update EOD snapshot: {e}", file=sys.stderr)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
