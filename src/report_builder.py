"""Build the Slack-ready content for morning report, live updates,
and EOD summary.

Output is plain text (Slack mrkdwn) ready for chat.postMessage.

This module preserves the original v1 API (build_morning_parent_text,
build_coach_reply_text, build_head_coach_digest, build_live_update_reply,
detect_new_live_events, build_eod_summary, to_daily_results, ...) and
adds a new tier-aware reporting layer that consumes the cascade output
from src.targets.resolve_all_subjects:

  build_tiered_morning_payload(...)   — parent + per-coach threaded replies,
                                        each row cites its cascade tier and
                                        includes on-track / behind / ahead
                                        status. Handles Unknown subjects and
                                        stale-data short-circuit.
  build_stale_data_dm(...)            — DM body for the head coach when the
                                        latest export is stale.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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
    return CoachRoster.from_dict(json.loads(path.read_text()))


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
                accuracy=float(subj_raw.get("accuracy", 0)),
                minutes=float(subj_raw.get("minutes", 0)),
                target_xp=float(targets.get(subj_name, 0.0)),
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
        lines.append(f"• *{s.name}* — target {target} XP today")
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
    kind: str,
) -> str:
    """One-line update for a fresh event during the day."""
    mention = f"<@{coach_slack_id}>" if coach_slack_id else coach_name
    if kind == "low_accuracy":
        return (
            f":warning: {mention} — *{student_name}* "
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


# ---------- end of day ----------

def build_eod_summary(
    today: date,
    results: list[StudentDailyResult],
) -> str:
    """End-of-day wrap-up — final threaded reply on the morning parent."""
    n = len(results)
    absent = sum(1 for r in results if r.absent)
    flagged = sum(1 for r in results if r.flagged_subjects())
    over = sum(1 for r in results if r.overperforming_subjects())
    return (
        f"*EOD — {today.strftime('%a %b %-d')}*  "
        f":busts_in_silhouette: {n} students  "
        f":zzz: {absent} absent  "
        f":warning: {flagged} low-acc  "
        f":star: {over} >125%."
    )


def trend_window_dates(today: date) -> list[date]:
    """The last 5 school days ending today (inclusive)."""
    return previous_school_days(today, 5)


# ===========================================================================
# NEW (v2) — tier-aware reporting layer
#
# Consumes:
#   - src.student_progress.ProgressLedger
#   - src.targets.resolve_all_subjects (via resolve_daily_target)
#   - config/coaches.json (CoachRoster)
#
# Produces:
#   - a Slack payload object describing the parent message + a list of
#     per-coach threaded replies, each row citing its cascade tier.
#
# Status emojis:
#   :white_check_mark:  on-track  (xp_today >= target * 0.9 and accuracy ok)
#   :warning:           behind    (xp_today <  target * 0.9)
#   :rocket:            ahead     (xp_today >= target * 1.25)
#   :red_circle:        stale / no data
# ===========================================================================


# Status thresholds (locked).
ACCURACY_FLOOR = 0.60
OVERPERFORM_PCT = 1.25
ON_TRACK_PCT = 0.90


@dataclass(frozen=True)
class TieredSubjectRow:
    student: str
    subject: str
    xp_today: float
    target_xp: float
    accuracy_today: Optional[float]
    tier: int
    source_label: str
    status: str           # "on_track" | "behind" | "ahead" | "no_data"
    target_grade: Optional[int]
    target_date: Optional[date]
    detail: str

    @property
    def emoji(self) -> str:
        return {
            "on_track": ":white_check_mark:",
            "behind": ":warning:",
            "ahead": ":rocket:",
            "no_data": ":red_circle:",
        }.get(self.status, ":grey_question:")


@dataclass(frozen=True)
class TieredCoachBlock:
    coach_name: str
    coach_slack_id: Optional[str]
    student_rows: Tuple[Tuple[str, Tuple[TieredSubjectRow, ...]], ...]
    unknown_subject_flags: Tuple[str, ...]   # student names with Unknown rows
    text: str                                # ready-to-post Slack mrkdwn


@dataclass(frozen=True)
class TieredMorningPayload:
    parent_text: str
    coach_blocks: Tuple[TieredCoachBlock, ...]
    head_coach_dm_text: Optional[str]        # populated only on staleness
    is_stale: bool
  
# Tier integer -> canonical name string used in history snapshots.
    # Keep this stable; the dashboard and trend analysis read by name.
    _TIER_NAMES = {
        0: "coach_xp_override",
        1: "coach_test_by",
        2: "grade_mastered",
        3: "personalized_base",
        4: "locked_base",
    }

    def to_history_dict(self) -> dict:
        """Convert this payload into the dict shape expected by
        src.history.build_snapshot_from_report().

        Output:
        {
          "students": [
            {
              "name": "Marcus Allen",
              "coach": "Lisa C Willis",
              "subjects": {
                "Math":    {"target": 30, "actual": 27, "tier": "personalized_base", "status": "behind"},
                "Reading": {"target": 25, "actual": 31, "tier": "locked_base",       "status": "ahead"},
                ...
              }
            },
            ...
          ]
        }

        Notes:
          - Status "no_data" is preserved as-is (history layer treats it
            the same as "unknown").
          - Tier integers are translated to canonical names via _TIER_NAMES.
          - Unknown subjects flagged on a coach block are NOT included as
            student-subject rows here; they're surfaced separately by the
            morning report's unknown_subject_flags field.
        """
        students_out: list = []
        seen: set = set()  # de-dupe across coach blocks (defensive)
        for block in self.coach_blocks:
            coach_name = getattr(block, "coach_name", "") or ""
            for student_name, subject_rows in (getattr(block, "student_rows", ()) or ()):
                key = (coach_name, student_name)
                if key in seen:
                    continue
                seen.add(key)
                subjects: dict = {}
                for row in subject_rows:
                    tier_name = self._TIER_NAMES.get(
                        int(getattr(row, "tier", -1)), "unknown"
                    )
                    subjects[row.subject] = {
                        "target": float(getattr(row, "target_xp", 0) or 0),
                        "actual": float(getattr(row, "xp_today", 0) or 0),
                        "tier": tier_name,
                        "status": str(getattr(row, "status", "unknown")),
                    }
                students_out.append({
                    "name": student_name,
                    "coach": coach_name,
                    "subjects": subjects,
                })
        return {"students": students_out}

def _classify_status(
    *, xp_today: float, target_xp: float, accuracy: Optional[float], no_data: bool
) -> str:
    if no_data:
        return "no_data"
    if target_xp <= 0:
        return "no_data"
    pct = xp_today / target_xp
    if pct >= OVERPERFORM_PCT:
        return "ahead"
    if pct < ON_TRACK_PCT:
        return "behind"
    if accuracy is not None and accuracy < ACCURACY_FLOOR:
        return "behind"
    return "on_track"


def _short_tier_tag(tier: int, source_label: str) -> str:
    """Compact tier tag for inline display, e.g. '[T1 grade-mastered]'."""
    short = {
        "tier0a_coach_xp_override": "coach XP",
        "tier0b_coach_test_by": "coach test-by",
        "tier1_grade_mastered": "grade-mastered",
        "tier3_personalized_base": "personalized",
        "tier4_locked_base": "base",
    }.get(source_label, source_label)
    return f"[T{tier} {short}]"


def _row_line(row: TieredSubjectRow) -> str:
    target_str = (
        f"{row.target_xp:.1f}".rstrip("0").rstrip(".") if row.target_xp else "—"
    )
    xp_str = f"{row.xp_today:.0f}" if row.xp_today == int(row.xp_today) else f"{row.xp_today:.1f}"
    acc = (
        f"{int(round(row.accuracy_today * 100))}%"
        if row.accuracy_today is not None
        else "—"
    )
    return (
        f"   {row.emoji} {row.subject}: {xp_str}/{target_str} XP "
        f"({acc} acc) {_short_tier_tag(row.tier, row.source_label)}"
    )


def _build_rows_for_student(
    *,
    student_progress: Any,                 # src.student_progress.StudentProgress
    student_profile: Dict[str, Any],
    today: date,
    grade_xp_table: Optional[Dict[int, Dict[str, Optional[float]]]],
    map_calendar_path: Optional[Path] = None,
) -> List[TieredSubjectRow]:
    from .targets import resolve_daily_target  # local import avoids cycles
    rows: List[TieredSubjectRow] = []
    for sp in student_progress.subjects:
        res = resolve_daily_target(
            student_name=student_progress.name,
            subject=sp.subject,
            today=today,
            student_profile=student_profile,
            grade_xp_table=grade_xp_table,
            cumulative_xp_in_current_grade=None,    # populated in Step I
            map_calendar_path=map_calendar_path,
        )
        status = _classify_status(
            xp_today=sp.xp_today,
            target_xp=res.xp_per_day,
            accuracy=sp.accuracy_today,
            no_data=sp.no_data,
        )
        rows.append(TieredSubjectRow(
            student=student_progress.name,
            subject=sp.subject,
            xp_today=float(sp.xp_today),
            target_xp=float(res.xp_per_day),
            accuracy_today=sp.accuracy_today,
            tier=res.tier,
            source_label=res.source_label,
            status=status,
            target_grade=res.target_grade,
            target_date=res.target_date,
            detail=res.detail,
        ))
    return rows


def _coach_for_student(roster: CoachRoster, student_name: str) -> Optional[str]:
    """Tolerant lookup that also handles Lisa Willis -> Lisa C Willis."""
    direct = roster.coach_for_student(student_name)
    if direct:
        return direct
    if student_name == "Lisa Willis":
        return roster.coach_for_student("Lisa C Willis")
    return None


def build_tiered_morning_payload(
    *,
    ledger: Any,                                  # ProgressLedger
    students_config: Dict[str, Any],
    grade_xp_table: Optional[Dict[int, Dict[str, Optional[float]]]],
    roster: CoachRoster,
    coach_slack_ids: Optional[Dict[str, str]] = None,
    map_calendar_path: Optional[Path] = None,
) -> TieredMorningPayload:
    """
    Top-level builder for the morning report.

    Stale-data rule: if the ledger is stale, return a payload with
    is_stale=True and a head_coach_dm_text populated. The runner SHOULD
    skip the parent post entirely in this case (per locked rule).
    """
    today = ledger.school_day
    coach_slack_ids = coach_slack_ids or {}
    profiles_by_name = (students_config.get("students") or {})

    if ledger.is_stale:
        return TieredMorningPayload(
            parent_text="",
            coach_blocks=tuple(),
            head_coach_dm_text=build_stale_data_dm(today, ledger.exported_at),
            is_stale=True,
        )

    parent_text = (
        f"*Morning Report — {today.strftime('%a %b %-d')}*  "
        f"_({len(ledger.students)} students · mode: {ledger.mode})_"
    )

    # Group students by coach.
    by_coach: Dict[str, List[Any]] = {}
    unassigned: List[Any] = []
    for sp in ledger.students:
        coach = _coach_for_student(roster, sp.name)
        if coach is None:
            unassigned.append(sp)
        else:
            by_coach.setdefault(coach, []).append(sp)

    blocks: List[TieredCoachBlock] = []
    for coach in sorted(by_coach.keys()):
        slack_id = coach_slack_ids.get(coach)
        mention = f"<@{slack_id}>" if slack_id else coach
        students_for_coach = by_coach[coach]

        student_blocks: List[Tuple[str, Tuple[TieredSubjectRow, ...]]] = []
        unknown_flags: List[str] = []

        text_lines = [f"{mention} — *{len(students_for_coach)} student(s)*"]
        for sp in sorted(students_for_coach, key=lambda x: x.name):
            profile = profiles_by_name.get(sp.name) or {}
            rows = _build_rows_for_student(
                student_progress=sp,
                student_profile=profile,
                today=today,
                grade_xp_table=grade_xp_table,
                map_calendar_path=map_calendar_path,
            )
            student_blocks.append((sp.name, tuple(rows)))

            header = f"• *{sp.name}*"
            if sp.absent:
                header += "  _(absent)_"
            if sp.unknown_subject_rows:
                unknown_flags.append(sp.name)
                header += "  :grey_question: _has Unknown subject rows; coach review needed_"
            text_lines.append(header)
            for row in rows:
                text_lines.append(_row_line(row))

        block_text = "\n".join(text_lines)
        blocks.append(TieredCoachBlock(
            coach_name=coach,
            coach_slack_id=slack_id,
            student_rows=tuple(student_blocks),
            unknown_subject_flags=tuple(unknown_flags),
            text=block_text,
        ))

    if unassigned:
        # Surface unassigned students in a synthetic "Unassigned" block so the
        # head coach sees them and the agent can ask about coach grouping.
        head_id = coach_slack_ids.get(roster.head_coach)
        mention = f"<@{head_id}>" if head_id else roster.head_coach
        lines = [f"{mention} — :grey_question: *{len(unassigned)} unassigned student(s)*"]
        for sp in sorted(unassigned, key=lambda x: x.name):
            lines.append(f"• {sp.name}  _(no coach in roster)_")
        blocks.append(TieredCoachBlock(
            coach_name="Unassigned",
            coach_slack_id=head_id,
            student_rows=tuple((sp.name, tuple()) for sp in unassigned),
            unknown_subject_flags=tuple(),
            text="\n".join(lines),
        ))

    return TieredMorningPayload(
        parent_text=parent_text,
        coach_blocks=tuple(blocks),
        head_coach_dm_text=None,
        is_stale=False,
    )


def build_stale_data_dm(today: date, exported_at: Optional[datetime]) -> str:
    """DM body for the head coach when latest export is stale (locked rule:
    SKIP the morning post; DM head coach instead)."""
    when = exported_at.isoformat() if exported_at else "unknown"
    return (
        f":red_circle: *Skipping morning report — {today.strftime('%a %b %-d')}*\n"
        f"The latest TimeBack export is stale (last seen: {when}). "
        f"Per protocol I'm not posting today's report. "
        f"Please refresh the bookmarklet export or check the API ingestion job."
    )
