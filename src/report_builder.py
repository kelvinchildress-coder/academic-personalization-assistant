"""Build the Slack-ready content for morning report, live updates,
and EOD summary.

Output is plain text (Slack mrkdwn) ready for chat.postMessage.
"""
from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Iterable

from .calendar_tsa import previous_school_days
from .models import (
    CoachRoster,
    Student,
    SubjectResult,
    StudentDailyResult,
    LOCKED_XP_RULES,
)
from .targets import all_subject_targets


# ---------- ingest helpers ----------

def load_roster(path: Path) -> CoachRoster:
    return CoachRoster.from_json(json.loads(path.read_text()))


def load_students(path: Path) -> list[Student]:
    raw = json.loads(path.read_text())
    return [Student.from_json(r) for r in raw]


def load_daily_data(path: Path) -> dict:
    """Load data/latest.json or data/<YYYY-MM-DD>.json (the laptop's
    scraper output, same shape app.py writes today)."""
    return json.loads(path.read_text())


# ---------- transformation ----------

def to_daily_results(
    raw: dict,
    students: list[Student],
    today: date,
) -> list[StudentDailyResult]:
    """Convert app.py's data.json shape into StudentDailyResult list."""
    by_name = {s.name: s for s in students}
    out: list[StudentDailyResult] = []
    for s in raw.get("students", []):
        name = s["name"]
        student = by_name.get(name) or Student(name=name)
        targets = all_subject_targets(student, today)
        subject_results: list[SubjectResult] = []
        for subj_raw in s.get("subjects", []):
            subj_name = subj_raw["name"]
            subject_results.append(SubjectResult(
                name=subj_name,
                xp=float(subj_raw.get("xp", 0)),
                accuracy=int(subj_raw.get("accuracy", 0)),
                minutes=int(subj_raw.get("minutes", 0)),
                target_xp=float(targets.get(subj_name, 0)),
                has_test=bool(subj_raw.get("has_test", False)),
            ))
        out.append(StudentDailyResult(
            name=name,
            date=raw.get("date", today.isoformat()),
            subjects=subject_results,
            absent=bool(s.get("absent", False)),
        ))
    return out


# ---------- morning report ----------

def build_morning_parent_text(today: date) -> str:
    """The header message that all coach replies thread under."""
    return f"*Morning Report — {today.strftime('%a %b %-d')}*"


def build_coach_reply_text(
    coach_name: str,
    coach_slack_id: str | None,
    students: list[StudentDailyResult],
) -> str:
    """One threaded reply per coach, listing today's targets per student."""
    mention = f"<@{coach_slack_id}>" if coach_slack_id else coach_name
    lines = [f"{mention} — *{len(students)} student(s)*"]
    if not students:
        lines.append("_No students assigned._")
        return "\n".join(lines)
    for s in students:
        target = int(round(s.total_target_xp))
        lines.append(f"• *{s.name}* — daily target {target} XP")
    return "\n".join(lines)


def build_head_coach_digest(
    head_coach_name: str,
    head_coach_slack_id: str | None,
    all_results: list[StudentDailyResult],
) -> str:
    """Campus-wide standout issues and successes."""
    mention = f"<@{head_coach_slack_id}>" if head_coach_slack_id else head_coach_name
    flagged = [r for r in all_results if r.flagged_subjects()]
    overperformers = [r for r in all_results if r.overperforming_subjects()]
    lines = [f"{mention} — *Head Coach digest*"]
    lines.append(f"• Roster size: {len(all_results)}")
    if flagged:
        names = ", ".join(r.name for r in flagged[:10])
        lines.append(f"• :warning: Low accuracy yesterday ({len(flagged)}): {names}")
    if overperformers:
        names = ", ".join(r.name for r in overperformers[:10])
        lines.append(f"• :star: Exceeded 125% XP yesterday ({len(overperformers)}): {names}")
    if not flagged and not overperformers:
        lines.append("• No standouts from yesterday.")
    return "\n".join(lines)


# ---------- live updates ----------

def build_live_update_reply(
    coach_slack_id: str | None,
    coach_name: str,
    student_name: str,
    subject: SubjectResult,
    kind: str,   # "low_accuracy" | "overperform"
) -> str:
    mention = f"<@{coach_slack_id}>" if coach_slack_id else coach_name
    if kind == "low_accuracy":
        return (
            f":rotating_light: {mention} — *{student_name}* accuracy "
            f"dropped to {subject.accuracy}% in {subject.name}."
        )
    if kind == "overperform":
        pct = int(round(subject.pct_of_target * 100))
        return (
            f":star: {mention} — *{student_name}* hit {pct}% of XP target "
            f"in {subject.name} ({int(subject.xp)}/{int(subject.target_xp)} XP)."
        )
    raise ValueError(f"Unknown live-update kind: {kind}")


def detect_new_live_events(
    results: list[StudentDailyResult],
    already_posted: set[str],
) -> list[tuple[StudentDailyResult, SubjectResult, str]]:
    """Return (student, subject, kind) tuples for events not yet posted.

    `already_posted` is a set of stable keys we persist across runs in
    data/live_state.json.
    """
    events: list[tuple[StudentDailyResult, SubjectResult, str]] = []
    for r in results:
        if r.absent:
            continue
        for s in r.subjects:
            if s.is_low_accuracy:
                key = f"{r.date}|{r.name}|{s.name}|low_accuracy"
                if key not in already_posted:
                    events.append((r, s, "low_accuracy"))
            if s.is_overperforming:
                key = f"{r.date}|{r.name}|{s.name}|overperform"
                if key not in already_posted:
                    events.append((r, s, "overperform"))
    return events


def event_key(r: StudentDailyResult, s: SubjectResult, kind: str) -> str:
    return f"{r.date}|{r.name}|{s.name}|{kind}"


# ---------- end-of-day summary ----------

def build_eod_summary(
    today: date,
    results: list[StudentDailyResult],
    roster: CoachRoster,
    coach_slack_ids: dict[str, str],
) -> str:
    """List students who did not reach Green, grouped by coach."""
    not_green = [r for r in results if not r.is_green]
    lines = [f"*End-of-Day Summary — {today.strftime('%a %b %-d')}*"]
    if not not_green:
        lines.append(":white_check_mark: Every student finished the day Green!")
        return "\n".join(lines)

    lines.append(f"_{len(not_green)} student(s) did not finish Green today._")
    by_coach: dict[str, list[StudentDailyResult]] = {}
    for r in not_green:
        coach = roster.coach_for_student(r.name) or "(unassigned)"
        by_coach.setdefault(coach, []).append(r)

    for coach_name in sorted(by_coach.keys()):
        sid = coach_slack_ids.get(coach_name)
        mention = f"<@{sid}>" if sid else coach_name
        lines.append(f"\n{mention}:")
        for r in by_coach[coach_name]:
            short = []
            xp_pct = int(round(r.overall_pct * 100))
            short.append(f"{xp_pct}% of target")
            flagged = r.flagged_subjects()
            if flagged:
                fl = ", ".join(f"{s.name} {s.accuracy}%" for s in flagged)
                short.append(f"low accuracy: {fl}")
            if r.absent:
                short = ["absent"]
            lines.append(f"• *{r.name}* — {'; '.join(short)}")
    return "\n".join(lines)


# ---------- 5-school-day trend ----------

def trend_window_dates(today: date) -> list[date]:
    return previous_school_days(today, 5)
