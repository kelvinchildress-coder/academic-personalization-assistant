"""
intent_writer.py
================

Apply a Phase-2 Intent to config/students.json.

Phase 2 introduces a new per-student field:

    students.<Name>.exceptions: List[Exception]

Where each Exception is one of:

    {"type": "pause",       "subject": "Math"|null, "start": "YYYY-MM-DD",
     "end": "YYYY-MM-DD", "source_coach": str, "raw_text": str}
    {"type": "half_target", "subject": "Math"|null, "start": "YYYY-MM-DD",
     "end": "YYYY-MM-DD", "source_coach": str, "raw_text": str}

Group rules are EXPANDED at confirm-time into individual per-student
exceptions (Q2 lock: "expand-on-confirm into individual per-student
overrides"). The GroupRule itself is NOT persisted — only the resulting
per-student exceptions are. This keeps the cascade in src/targets.py
simple: it just iterates each student's exceptions list.

This module does NOT call Slack and does NOT decide UX flow. It only:
  - builds Proposals from Intents (build_proposal)
  - applies a confirmed Proposal to students.json (apply_proposal)

Half-target rule (Q3 lock): half-modifier is multiplicative on Tier 3
(personalized_base) and Tier 4 (locked_base) only — the cascade in
src/targets.py applies that. This file just records the exception.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Tuple

from .intents import (
    Intent,
    Pause,
    HalfTarget,
    GroupRule,
    GroupSelector,
    SetTestBy,
    grades_for_band,
)
from .pending_state import Proposal
from .group_resolver import _coach_to_student_list


def _add_school_days(start_iso: str, days: int) -> str:
    """Inclusive end date — start counts as day 1. Calendar-day math here;
    the targets cascade handles weekends/holidays via calendar_tsa."""
    d = date.fromisoformat(start_iso)
    return (d + timedelta(days=max(0, days - 1))).isoformat()


def _load_students(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())


def _save_students(path: Path, blob: Dict[str, Any]) -> None:
    path.write_text(json.dumps(blob, indent=2, sort_keys=True) + "\n")


def _ensure_exceptions(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Lazy-create the exceptions array on a student profile."""
    exc = profile.get("exceptions")
    if not isinstance(exc, list):
        exc = []
        profile["exceptions"] = exc
    return exc


# ---------------------------------------------------------------------------
# Group expansion (Q2: expand-on-confirm)
# ---------------------------------------------------------------------------


def _expand_group_targets(
    selector: GroupSelector,
    *,
    students_blob: Dict[str, Any],
    coaches_blob: Dict[str, Any],
) -> List[str]:
    """Return the list of student names a GroupSelector resolves to."""
    students = students_blob.get("students") or {}

    if selector.scope == "speaker":
        speaker = selector.speaker_coach
        # Use the schema-tolerant resolver so we work with bare-list,
        # list-of-dicts, or dict-of-dicts shapes of coaches.json.
        roster = _coach_to_student_list(coaches_blob).get(speaker, [])
        candidates = [n for n in roster if n in students]

    if selector.level_band:
        band_grades = set(grades_for_band(selector.level_band) or [])
        if band_grades:
            candidates = [
                n for n in candidates
                if students[n].get("age_grade") in band_grades
            ]

    if selector.explicit_names:
        explicit = set(selector.explicit_names)
        candidates = [n for n in candidates if n in explicit]

    # Dedupe, preserve order
    seen = set()
    out: List[str] = []
    for n in candidates:
        if n not in seen:
            seen.add(n)
            out.append(n)
    return out


# ---------------------------------------------------------------------------
# Proposal building
# ---------------------------------------------------------------------------


def _summarize_pause(p: Pause) -> str:
    end = _add_school_days(p.start_date, p.days)
    subj = f" {p.subject}" if p.subject else ""
    return (
        f"Pause{subj} for {p.student_name} "
        f"from {p.start_date} to {end} ({p.days} day(s))."
    )


def _summarize_half(h: HalfTarget) -> str:
    end = _add_school_days(h.start_date, h.days)
    subj = f" {h.subject}" if h.subject else ""
    return (
        f"Half target{subj} for {h.student_name} "
        f"from {h.start_date} to {end} ({h.days} day(s))."
    )


def _summarize_set_test_by(s: SetTestBy) -> str:
    parts = [f"Set test-out for {s.student} ({s.subject})"]
    if s.target_grade is not None:
        parts.append(f"at grade {s.target_grade}")
    if s.target_date is not None:
        parts.append(f"by {s.target_date.isoformat()}")
    return " ".join(parts) + "."


def _summarize_group(g: GroupRule, expanded: List[str]) -> str:
    end = _add_school_days(g.start_date, g.days)
    verb = "Pause" if g.action == "pause" else "Half target"
    subj = f" {g.subject}" if g.subject else ""
    n = len(expanded)
    preview = ", ".join(expanded[:5])
    if n > 5:
        preview += f", +{n - 5} more"
    return (
        f"{verb}{subj} for {g.selector.describe()} "
        f"({n} student(s): {preview}) "
        f"from {g.start_date} to {end} ({g.days} day(s))."
    )


def build_proposal(
    intent: Intent,
    *,
    coach_slack_id: str,
    channel_id: str,
    students_blob: Dict[str, Any],
    coaches_blob: Dict[str, Any],
) -> Proposal:
    """Convert an Intent into a Proposal ready for stage_proposal()."""
    if isinstance(intent, Pause):
        return Proposal(
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            intent_kind="pause",
            payload={
                "student_name": intent.student_name,
                "subject": intent.subject,
                "start_date": intent.start_date,
                "days": intent.days,
            },
            expanded_targets=[intent.student_name],
summary_text=_summarize_pause(intent),
            raw_coach_text=intent.raw_text,
        )
    if isinstance(intent, HalfTarget):
        return Proposal(
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            intent_kind="half_target",
            payload={
                "student_name": intent.student_name,
                "subject": intent.subject,
                "start_date": intent.start_date,
                "days": intent.days,
            },
            expanded_targets=[intent.student_name],
            summary_text=_summarize_half(intent),
            raw_coach_text=intent.raw_text,
        )
    if isinstance(intent, GroupRule):
        expanded = _expand_group_targets(
            intent.selector,
            students_blob=students_blob,
            coaches_blob=coaches_blob,
        )
        return Proposal(
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            intent_kind="group_rule",
            payload={
                "selector": {
                    "scope": intent.selector.scope,
                    "level_band": intent.selector.level_band,
                    "explicit_names": intent.selector.explicit_names,
                    "speaker_coach": intent.selector.speaker_coach,
                },
                "action": intent.action,
                "subject": intent.subject,
                "start_date": intent.start_date,
                "days": intent.days,
            },
            expanded_targets=expanded,
            summary_text=_summarize_group(intent, expanded),
            raw_coach_text=intent.raw_text,
        )
    if isinstance(intent, SetTestBy):
        # target_date is a Python date; serialize to ISO for JSON-safe payload.
        td_iso = intent.target_date.isoformat() if intent.target_date else None
        return Proposal(
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            intent_kind="set_test_by",
            payload={
                "student_name": intent.student,
                "subject": intent.subject,
                "target_grade": intent.target_grade,
                "target_date": td_iso,
            },
            expanded_targets=[intent.student],
            summary_text=_summarize_set_test_by(intent),
            raw_coach_text=intent.raw_text,
        )
    raise ValueError(f"Unsupported intent type for proposal: {type(intent).__name__}")


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _exception_for_pause(payload: Dict[str, Any], source_coach: str, raw: str) -> Dict[str, Any]:
    return {
        "type": "pause",
        "subject": payload.get("subject"),
        "start": payload["start_date"],
        "end": _add_school_days(payload["start_date"], int(payload["days"])),
        "source_coach": source_coach,
        "raw_text": raw,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def _exception_for_half(payload: Dict[str, Any], source_coach: str, raw: str) -> Dict[str, Any]:
    return {
        "type": "half_target",
        "subject": payload.get("subject"),
        "start": payload["start_date"],
        "end": _add_school_days(payload["start_date"], int(payload["days"])),
        "source_coach": source_coach,
        "raw_text": raw,
        "created_at": datetime.utcnow().isoformat(timespec="seconds") + "Z",
    }


def apply_proposal(
    proposal: Proposal,
    *,
    students_path: Path,
    source_coach_name: str,
) -> Tuple[bool, List[str], int]:
    """Apply a confirmed Proposal to students.json.

    Returns (ok, errors, num_students_affected).
    """
    errors: List[str] = []
    blob = _load_students(students_path)
    students = blob.get("students") or {}

    if proposal.intent_kind == "pause":
        targets = [proposal.payload["student_name"]]
        builder = _exception_for_pause
        payload = proposal.payload
    elif proposal.intent_kind == "half_target":
        targets = [proposal.payload["student_name"]]
        builder = _exception_for_half
        payload = proposal.payload
    elif proposal.intent_kind == "group_rule":
        targets = list(proposal.expanded_targets)
        action = proposal.payload.get("action") or "pause"
        builder = _exception_for_pause if action == "pause" else _exception_for_half
        # Group payload already has start_date / days / subject at top level.
        payload = {
            "subject": proposal.payload.get("subject"),
            "start_date": proposal.payload["start_date"],
            "days": proposal.payload["days"],
        }
    elif proposal.intent_kind == "set_test_by":
        # SetTestBy writes student.overrides.test_by[subject] directly
        # (Tier 0b), not the exceptions list. Handle inline and return.
        student = proposal.payload["student_name"]
        subject = proposal.payload["subject"]
        target_grade = proposal.payload.get("target_grade")
        target_date = proposal.payload.get("target_date")
        if student not in students:
            return False, [f"unknown student '{student}'"], 0
        profile = students[student]
        overrides = profile.get("overrides")
        if not isinstance(overrides, dict):
            overrides = {}
            profile["overrides"] = overrides
        test_by = overrides.get("test_by")
        if not isinstance(test_by, dict):
            test_by = {}
            overrides["test_by"] = test_by
        # Preserve any existing test_by[subject] fields not being replaced
        # (e.g. coach earlier set target_grade only, now sets target_date only).
        existing = test_by.get(subject) if isinstance(test_by.get(subject), dict) else {}
        merged = dict(existing)
        if target_grade is not None:
            merged["target_grade"] = int(target_grade)
        if target_date is not None:
            merged["target_date"] = target_date  # already ISO string
        merged["source_coach"] = source_coach_name
        merged["raw_text"] = proposal.raw_coach_text
        merged["created_at"] = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        test_by[subject] = merged
        _save_students(students_path, blob)
        return True, [], 1
    else:
        return False, [f"unknown intent_kind '{proposal.intent_kind}'"], 0

    affected = 0
    for name in targets:
        if name not in students:
            errors.append(f"unknown student '{name}'")
            continue
        profile = students[name]
        exc_list = _ensure_exceptions(profile)
        exc_list.append(builder(payload, source_coach_name, proposal.raw_coach_text))
        affected += 1

    if errors and affected == 0:
        return False, errors, 0

    _save_students(students_path, blob)
    return True, errors, affected
