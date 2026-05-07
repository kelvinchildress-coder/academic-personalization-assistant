#!/usr/bin/env python3
"""Every 30 min during school hours: scan data/latest.json for newly
crossed thresholds (accuracy<60% or XP>=125% of target in any subject)
and post NEW threaded replies under the morning parent message.

State file: data/live_state.json — set of event keys already posted.
Reset implicitly when morning_state.json's date != today (handled below).

Reads SLACK_BOT_TOKEN from env. Idempotent: safe to run repeatedly.

Usage:
    python -m scripts.post_live_updates
    python -m scripts.post_live_updates --dry-run
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
from src.models import CoachRoster  # noqa: E402
from src.report_builder import (  # noqa: E402
    build_live_update_reply,
    detect_new_live_events,
    event_key,
    load_daily_data,
    load_roster,
    load_students,
    to_daily_results,
)
from src.slack_poster import SlackPoster  # noqa: E402


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
        print(f"[live] {today} not a school day; exiting.")
        return 0

    morning_path = REPO_ROOT / "data" / "morning_state.json"
    if not morning_path.exists():
        print("[live] morning_state.json missing — morning report not posted yet; exiting.")
        return 0

    morning_state = json.loads(morning_path.read_text())
    if morning_state.get("date") != today.isoformat():
        print(f"[live] morning_state is for {morning_state.get('date')}, not today; exiting.")
        return 0

    data_path = REPO_ROOT / args.data_file
    if not data_path.exists():
        print(f"[live] {data_path} missing; exiting.")
        return 0

    raw = load_daily_data(data_path)
    if raw.get("date") != today.isoformat():
        print(f"[live] data/latest.json is for {raw.get('date')}; exiting.")
        return 0

    students_path = REPO_ROOT / "students.json"
    students = load_students(students_path) if students_path.exists() else []
    roster = load_roster(REPO_ROOT / "config" / "coaches.json")
    results = to_daily_results(raw, students, today)

    state_path = REPO_ROOT / "data" / "live_state.json"
    if state_path.exists():
        live_state = json.loads(state_path.read_text())
        if live_state.get("date") != today.isoformat():
            live_state = {"date": today.isoformat(), "posted": []}
    else:
        live_state = {"date": today.isoformat(), "posted": []}
    already = set(live_state["posted"])

    events = detect_new_live_events(results, already)
    if not events:
        print("[live] no new threshold events.")
        return 0

    channel = morning_state["channel"]
    parent_ts = morning_state["parent_ts"]
    slack_ids: dict[str, str] = morning_state.get("slack_ids", {})

    if args.dry_run:
        print(f"[live] DRY RUN — {len(events)} new event(s):")
        for r, s, kind in events:
            coach = roster.coach_for_student(r.name) or "(unassigned)"
            text = build_live_update_reply(slack_ids.get(coach), coach, r.name, s, kind)
            print(f"  -> {text}")
        return 0

    poster = SlackPoster()
    for r, s, kind in events:
        coach = roster.coach_for_student(r.name) or "(unassigned)"
        text = build_live_update_reply(slack_ids.get(coach), coach, r.name, s, kind)
        poster.post(channel, text, thread_ts=parent_ts)
        already.add(event_key(r, s, kind))

    live_state["posted"] = sorted(already)
    state_path.write_text(json.dumps(live_state, indent=2))
    print(f"[live] posted {len(events)} replies; state -> {state_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
