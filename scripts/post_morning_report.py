#!/usr/bin/env python3
"""Post the morning report to Slack: parent header + threaded coach
replies + head-coach digest.

Reads:
  - data/latest.json        (laptop scraper output OR synthetic test data)
  - config/coaches.json     (roster)
  - students.json           (xp overrides + test-out goals; backward
                             compatible with simple list-of-strings)

Reads SLACK_BOT_TOKEN from env. Writes data/morning_state.json
(parent message ts + coach→reply ts mapping + coach→slack_id mapping)
so live-update and EOD jobs can thread under the same parent and
reuse coach IDs without re-querying Slack.

If data/latest.json is missing or stale (older than today), this
script does NOT post a public report. Instead it DMs the head coach
with a 'ingest skipped' alert and exits 0.

Usage:
    python -m scripts.post_morning_report
    python -m scripts.post_morning_report --dry-run
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.calendar_tsa import is_school_day  # noqa: E402
from src.models import CoachRoster, Student  # noqa: E402
from src.report_builder import (  # noqa: E402
    build_coach_reply_text,
    build_head_coach_digest,
    build_morning_parent_text,
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
    parser.add_argument("--dry-run", action="store_true",
                        help="Print messages instead of posting to Slack.")
    parser.add_argument("--data-file", default="data/latest.json")
    parser.add_argument("--force", action="store_true",
                        help="Run even if today is not a school day.")
    args = parser.parse_args()

    today = _today_ct()
    if not args.force and not is_school_day(today):
        print(f"[morning] {today} is not a school day; exiting.")
        return 0

    data_path = REPO_ROOT / args.data_file
    if not data_path.exists():
        print(f"[morning] {data_path} missing — alerting head coach.")
        return _alert_head_coach(args.dry_run, "data/latest.json was missing.")

    raw = load_daily_data(data_path)
    raw_date = raw.get("date", "")
    if raw_date != today.isoformat():
        print(f"[morning] data/latest.json is for {raw_date}, not {today} — alerting.")
        return _alert_head_coach(
            args.dry_run,
            f"data/latest.json is stale (latest={raw_date}, today={today}).",
        )

    roster = load_roster(REPO_ROOT / "config" / "coaches.json")
    students_path = REPO_ROOT / "students.json"
    students = load_students(students_path) if students_path.exists() else []
    results = to_daily_results(raw, students, today)

    if args.dry_run:
        print("[morning] DRY RUN — would post:")
        print("---PARENT---")
        print(build_morning_parent_text(today))
        for coach in roster.coaches:
            coach_results = [r for r in results if r.name in coach.students]
            print(f"---REPLY: {coach.name}---")
            print(build_coach_reply_text(coach.name, None, coach_results))
        print("---HEAD COACH DIGEST---")
        print(build_head_coach_digest(roster.head_coach, None, results))
        return 0

    poster = SlackPoster()

    # Resolve all coach + head-coach Slack IDs in one users.list pass.
    names = [c.name for c in roster.coaches] + [roster.head_coach]
    slack_ids = poster.resolve_users(names)

    # Channel
    channel = roster.coach_for_student.__self__.__dict__ if False else None  # noqa
    channel_name = json.loads((REPO_ROOT / "config" / "coaches.json").read_text()).get("channel", "sports")

    # Parent message
    parent_text = build_morning_parent_text(today)
    parent = poster.post(channel_name, parent_text)
    parent_ts = parent["ts"]
    print(f"[morning] parent posted ts={parent_ts}")

    # Threaded reply per coach
    coach_reply_ts: dict[str, str] = {}
    for coach in roster.coaches:
        coach_results = [r for r in results if r.name in coach.students]
        text = build_coach_reply_text(coach.name, slack_ids.get(coach.name), coach_results)
        reply = poster.post(channel_name, text, thread_ts=parent_ts)
        coach_reply_ts[coach.name] = reply["ts"]

    # Head coach digest
    digest_text = build_head_coach_digest(
        roster.head_coach, slack_ids.get(roster.head_coach), results
    )
    poster.post(channel_name, digest_text, thread_ts=parent_ts)

    # Persist state for live-updates and EOD jobs
    state = {
        "date": today.isoformat(),
        "channel": channel_name,
        "parent_ts": parent_ts,
        "coach_reply_ts": coach_reply_ts,
        "slack_ids": slack_ids,
        "head_coach": roster.head_coach,
    }
    state_path = REPO_ROOT / "data" / "morning_state.json"
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(json.dumps(state, indent=2))
    print(f"[morning] wrote {state_path}")
    return 0


def _alert_head_coach(dry_run: bool, reason: str) -> int:
    if dry_run:
        print(f"[morning] DRY RUN — would DM head coach: {reason}")
        return 0
    poster = SlackPoster()
    roster = load_roster(REPO_ROOT / "config" / "coaches.json")
    head_id = poster.resolve_user(roster.head_coach)
    if not head_id:
        print(f"[morning] could not resolve head coach {roster.head_coach}; aborting alert.")
        return 0
    poster.dm(
        head_id,
        f":warning: *Morning report skipped today*\n{reason}\n"
        "Run the scrape manually or wait for the laptop to come back online.",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
