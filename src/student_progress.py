"""
student_progress.py
===================

Per-student, per-subject progress ledger. Bridges:

  data/latest.json         (today's bookmarklet/API export — daily activity)
  config/students.json     (per-student profile incl. current grade, year-start
                            grade, coach overrides)
  config/grade_xp.json     (total XP required per (grade, subject); skeleton
                            today, populated by scripts/grade_xp_collector.py
                            once the TimeBack API token is provided)

Produces a `StudentProgress` snapshot that downstream code (targets.py,
report_builder.py, the agent) can consume without re-deriving anything.

This module is intentionally read-only and side-effect-free. All writes
happen in scripts/* or src/agent/*.

The TimeBack API client is a stub: TimeBackAPIClient.fetch_remaining_xp()
raises NotImplementedError until TIMEBACK_API_TOKEN is wired in (Step I).
The fallback path uses config/grade_xp.json for totals; when that table
is null for a (grade, subject), `remaining_xp_to_target_grade` will be
None and the cascade in targets.py will correctly fall through past
Tier 1 to Tier 3 / Tier 4.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# We intentionally import lazily inside helpers so this module stays
# importable even before sibling modules are present.


# ---------------------------------------------------------------------------
# Constants & subject normalization
# ---------------------------------------------------------------------------

ALL_SUBJECTS = (
    "Math",
    "Reading",
    "Language",
    "Writing",
    "Science",
    "Vocabulary",
    "FastMath",
)

GRADED_SUBJECTS = frozenset({
    "Math", "Reading", "Language", "Writing", "Science",
})

# Map common alternate spellings the bookmarklet may emit.
SUBJECT_ALIASES = {
    "math": "Math",
    "reading": "Reading",
    "language": "Language",
    "writing": "Writing",
    "science": "Science",
    "vocabulary": "Vocabulary",
    "vocab": "Vocabulary",
    "fastmath": "FastMath",
    "fast math": "FastMath",
}


def normalize_subject(name: Optional[str]) -> Optional[str]:
    """
    Map a raw subject string to one of ALL_SUBJECTS, or return None if
    we can't classify it (e.g., the known Mira Kambic "Unknown" quirk).
    """
    if not name:
        return None
    key = str(name).strip().lower()
    if key in SUBJECT_ALIASES:
        return SUBJECT_ALIASES[key]
    # Tolerate exact-case canonical names.
    for canon in ALL_SUBJECTS:
        if name == canon:
            return canon
    return None


# Convert grade keys ("K", "1st", "2nd", ... "12th") <-> integer (K=0).
_GRADE_KEY_TO_INT = {"K": 0}
_INT_TO_GRADE_KEY = {0: "K"}
for _i in range(1, 13):
    suffix = "th"
    if _i % 100 not in (11, 12, 13):
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(_i % 10, "th")
    _GRADE_KEY_TO_INT[f"{_i}{suffix}"] = _i
    _INT_TO_GRADE_KEY[_i] = f"{_i}{suffix}"


def grade_key_to_int(key: Optional[str]) -> Optional[int]:
    if key is None:
        return None
    if isinstance(key, int):
        return key
    return _GRADE_KEY_TO_INT.get(str(key).strip())


def grade_int_to_key(g: Optional[int]) -> Optional[str]:
    if g is None:
        return None
    return _INT_TO_GRADE_KEY.get(int(g))


# ---------------------------------------------------------------------------
# Name normalization (Lisa Willis -> Lisa C Willis is locked).
# ---------------------------------------------------------------------------

NAME_NORMALIZATIONS = {
    "Lisa Willis": "Lisa C Willis",
}


def normalize_student_name(name: str) -> str:
    return NAME_NORMALIZATIONS.get(name, name)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SubjectProgress:
    """Today's activity + cumulative state for one (student, subject)."""
    subject: str
    xp_today: float
    accuracy_today: Optional[float]   # 0..1 (we coerce % to fraction)
    minutes_today: float
    mastered_today: bool
    no_data: bool
    has_test: bool

    # Cumulative / configured state (may be None when unknown).
    current_grade: Optional[int]
    year_start_grade: Optional[int]
    target_grade_total_xp: Optional[float]   # total XP required at target grade
    remaining_xp_to_target_grade: Optional[float]
    target_grade: Optional[int]
    target_date: Optional[date]
    target_source: str   # "coach_override" | "default_q2" | "non_graded" | "unknown"

    # Free-text explanation for the report.
    detail: str = ""


@dataclass(frozen=True)
class StudentProgress:
    """Whole-student snapshot."""
    name: str
    age_grade: Optional[int]
    total_xp_today: float
    overall_accuracy_today: Optional[float]
    total_minutes_today: float
    absent: bool
    is_stale: bool                       # latest export > 24h old on a school day
    subjects: Tuple[SubjectProgress, ...]
    unknown_subject_rows: Tuple[Dict[str, Any], ...] = ()


@dataclass(frozen=True)
class ProgressLedger:
    """All students for one school day."""
    school_day: date
    mode: str                             # "morning" | "live" | "manual"
    exported_at: Optional[datetime]
    is_stale: bool
    students: Tuple[StudentProgress, ...]

# TimeBackAPIClient now lives in src/timeback_api.py; re-export so legacy
# imports keep working.
from .timeback_api import TimeBackAPIClient  # noqa: F401

# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_latest(data_path: Path) -> Dict[str, Any]:
    """Load data/latest.json (the bookmarklet/API daily envelope)."""
    return _read_json(data_path)


def load_students_config(students_path: Path) -> Dict[str, Any]:
    """Load config/students.json. The 'students' field is an OBJECT keyed
    by student name (verified shape)."""
    blob = _read_json(students_path)
    return blob


def load_grade_xp_table(grade_xp_path: Path) -> Dict[str, Dict[str, Optional[float]]]:
    """
    Load config/grade_xp.json's 'grades' map. Returns a normalized
    dict: { grade_int: { subject: total_xp_or_none } }.
    """
    blob = _read_json(grade_xp_path)
    raw = blob.get("grades", {})
    out: Dict[int, Dict[str, Optional[float]]] = {}
    for k, subjects in raw.items():
        gi = grade_key_to_int(k)
        if gi is None:
            continue
        out[gi] = {}
        for subj, val in subjects.items():
            canon = normalize_subject(subj) or subj
            out[gi][canon] = (None if val is None else float(val))
    return out


# ---------------------------------------------------------------------------
# Staleness
# ---------------------------------------------------------------------------


def _parse_iso_dt(s: Optional[str]) -> Optional[datetime]:
    if not s:
        return None
    try:
        # Bookmarklet writes ISO-8601 with offset; Python 3.11+ handles fromisoformat.
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None


def is_export_stale(
    exported_at: Optional[datetime],
    *,
    now: Optional[datetime] = None,
    max_age_hours: float = 24.0,
) -> bool:
    """Return True if the export is older than max_age_hours."""
    if exported_at is None:
        return True
    now = now or datetime.now(exported_at.tzinfo)
    delta = now - exported_at
    return delta.total_seconds() > max_age_hours * 3600.0


# ---------------------------------------------------------------------------
# Core builder
# ---------------------------------------------------------------------------


def _coerce_accuracy(raw: Any) -> Optional[float]:
    """Bookmarklet sometimes emits accuracy as 0..1 fraction, sometimes as
    a 0..100 percent. Normalize to fraction in [0,1] or None."""
    if raw is None:
        return None
    try:
        v = float(raw)
    except (TypeError, ValueError):
        return None
    if v < 0:
        return None
    if v > 1.5:
        # Treat as percent.
        return max(0.0, min(1.0, v / 100.0))
    return max(0.0, min(1.0, v))


def _resolve_subject_target(
    *,
    subject: str,
    age_grade: Optional[int],
    year_start_grade: Optional[int],
    coach_override_grade: Optional[int],
    coach_override_date: Optional[date],
) -> Tuple[Optional[int], Optional[date], str, str]:
    """
    Thin wrapper around src.test_out_goals.resolve_target_grade so this
    module stays importable even when run from odd CWDs.

    Returns (target_grade, target_date, source, detail).
    """
    try:
        from .test_out_goals import resolve_target_grade  # type: ignore
    except ImportError:
        from test_out_goals import resolve_target_grade  # type: ignore

    res = resolve_target_grade(
        subject=subject,
        age_grade=age_grade,
        year_start_grade=year_start_grade,
        coach_override_grade=coach_override_grade,
    )
    return (res.target_grade, coach_override_date, res.source, res.detail)


def build_subject_progress(
    *,
    subject: str,
    raw_subject_row: Dict[str, Any],
    student_profile: Dict[str, Any],
    grade_xp_table: Dict[int, Dict[str, Optional[float]]],
) -> SubjectProgress:
    """Build a single SubjectProgress row."""
    canon = normalize_subject(subject) or subject

    age_grade = student_profile.get("age_grade")
    cur_per_sub = student_profile.get("current_grade_per_subject") or {}
    ys_per_sub = student_profile.get("year_start_grade_per_subject") or {}

    current_grade = cur_per_sub.get(canon)
    if isinstance(current_grade, str):
        current_grade = grade_key_to_int(current_grade)

    year_start_grade = ys_per_sub.get(canon)
    if isinstance(year_start_grade, str):
        year_start_grade = grade_key_to_int(year_start_grade)

    # Coach overrides (Tier 0b) live alongside profile data.
    override_grade_map = student_profile.get("manual_test_out_grade") or {}
    override_date_map = student_profile.get("manual_test_out_date") or {}
    coach_override_grade = override_grade_map.get(canon)
    coach_override_date_raw = override_date_map.get(canon)
    coach_override_date: Optional[date] = None
    if coach_override_date_raw:
        try:
            coach_override_date = date.fromisoformat(str(coach_override_date_raw))
        except ValueError:
            coach_override_date = None

    target_grade, target_date, target_source, detail = _resolve_subject_target(
        subject=canon,
        age_grade=age_grade,
        year_start_grade=year_start_grade,
        coach_override_grade=coach_override_grade,
        coach_override_date=coach_override_date,
    )

    # Look up total XP at the target grade (None until grade_xp.json populated).
    total_xp_at_target: Optional[float] = None
    if target_grade is not None and canon in GRADED_SUBJECTS:
        total_xp_at_target = grade_xp_table.get(int(target_grade), {}).get(canon)

    # remaining_xp_to_target_grade is best-effort. Without API, we cannot
    # know cumulative-XP-earned-in-current-grade. Leave None to let
    # targets.py fall through to Tier 3.
    remaining_xp = None  # populated by Step I

    return SubjectProgress(
        subject=canon,
        xp_today=float(raw_subject_row.get("xp") or 0.0),
        accuracy_today=_coerce_accuracy(raw_subject_row.get("accuracy")),
        minutes_today=float(raw_subject_row.get("minutes") or 0.0),
        mastered_today=bool(raw_subject_row.get("mastered")),
        no_data=bool(raw_subject_row.get("no_data")),
        has_test=bool(raw_subject_row.get("has_test")),
        current_grade=current_grade,
        year_start_grade=year_start_grade,
        target_grade_total_xp=total_xp_at_target,
        remaining_xp_to_target_grade=remaining_xp,
        target_grade=target_grade,
        target_date=target_date,
        target_source=target_source,
        detail=detail,
    )


def build_student_progress(
    *,
    raw_student: Dict[str, Any],
    students_config: Dict[str, Any],
    grade_xp_table: Dict[int, Dict[str, Optional[float]]],
    is_stale: bool,
) -> StudentProgress:
    name = normalize_student_name(str(raw_student.get("name", "")).strip())
    profile = (students_config.get("students") or {}).get(name) or {}

    raw_subjects = raw_student.get("subjects") or []
    rows: List[SubjectProgress] = []
    unknown_rows: List[Dict[str, Any]] = []

    for sr in raw_subjects:
        canon = normalize_subject(sr.get("name"))
        if canon is None:
            # Mira Kambic-style "Unknown" rows. Preserve for downstream
            # tagging so the report can flag them.
            unknown_rows.append(dict(sr))
            continue
        rows.append(
            build_subject_progress(
                subject=canon,
                raw_subject_row=sr,
                student_profile=profile,
                grade_xp_table=grade_xp_table,
            )
        )

    return StudentProgress(
        name=name,
        age_grade=profile.get("age_grade"),
        total_xp_today=float(raw_student.get("total_xp") or 0.0),
        overall_accuracy_today=_coerce_accuracy(raw_student.get("overall_accuracy")),
        total_minutes_today=float(raw_student.get("total_minutes") or 0.0),
        absent=bool(raw_student.get("absent")),
        is_stale=is_stale,
        subjects=tuple(rows),
        unknown_subject_rows=tuple(unknown_rows),
    )


def build_progress_ledger(
    *,
    latest_path: Path,
    students_path: Path,
    grade_xp_path: Path,
    now: Optional[datetime] = None,
) -> ProgressLedger:
    """
    Top-level builder. Loads all three inputs, normalizes them, returns
    a fully-resolved ProgressLedger ready for targets.py / report_builder.py.
    """
    latest = load_latest(latest_path)
    students_config = load_students_config(students_path)
    grade_xp_table = load_grade_xp_table(grade_xp_path)

    exported_at = _parse_iso_dt(latest.get("timestamp") or latest.get("exported_at"))
    school_day_str = latest.get("date") or latest.get("school_day")
    school_day = date.fromisoformat(school_day_str) if school_day_str else date.today()
    mode = str(latest.get("mode") or "manual")
    stale = is_export_stale(exported_at, now=now)

    students_out: List[StudentProgress] = []
    for raw in (latest.get("students") or []):
        students_out.append(
            build_student_progress(
                raw_student=raw,
                students_config=students_config,
                grade_xp_table=grade_xp_table,
                is_stale=stale,
            )
        )

    return ProgressLedger(
        school_day=school_day,
        mode=mode,
        exported_at=exported_at,
        is_stale=stale,
        students=tuple(students_out),
    )


# ---------------------------------------------------------------------------
# Convenience: default paths
# ---------------------------------------------------------------------------


def default_paths(repo_root: Optional[Path] = None) -> Dict[str, Path]:
    root = repo_root or Path(__file__).resolve().parent.parent
    return {
        "latest": root / "data" / "latest.json",
        "students": root / "config" / "students.json",
        "grade_xp": root / "config" / "grade_xp.json",
    }


def build_default_ledger(now: Optional[datetime] = None) -> ProgressLedger:
    """Convenience wrapper for scripts/cron — uses repo-default paths."""
    paths = default_paths()
    return build_progress_ledger(
        latest_path=paths["latest"],
        students_path=paths["students"],
        grade_xp_path=paths["grade_xp"],
        now=now,
    )
