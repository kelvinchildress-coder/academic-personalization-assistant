"""
config_writer.py
================

Schema-validated writes to config/students.json. The agent NEVER mutates
the config directly — it builds a `StructuredPatch`, runs it through
`validate_patch`, and only then commits via `apply_patch`.

A patch is a small object describing one or more field updates for one
student. Multiple patches per coach reply are allowed and applied
sequentially; if any fails validation, the entire batch is rejected.

This module is *file-local* — it writes to the workspace's
config/students.json. The actual `git commit` + `git push` is done by
the GitHub Actions workflow that wraps the agent (agent-poll.yml). In
local development, the workspace edits are still useful: you can review
the diff before pushing.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


GRADED_SUBJECTS = ("Math", "Reading", "Language", "Writing", "Science")
ALL_SUBJECTS = GRADED_SUBJECTS + ("Vocabulary", "FastMath")

# Allowed update fields on a per-student patch.
ALLOWED_FIELDS = {
    "age_grade",
    "current_grade_per_subject",
    "year_start_grade_per_subject",
    "manual_test_out_grade",
    "manual_test_out_date",
    "overrides.xp_per_day",
    "ratified",
    "notes",
}

MIN_GRADE = 0   # K
MAX_GRADE = 12


@dataclass
class StructuredPatch:
    """One coach's reply distilled into a per-student set of updates."""
    student_name: str
    updates: Dict[str, Any] = field(default_factory=dict)
    source_ts: Optional[str] = None        # Slack DM ts that produced this patch
    source_coach: Optional[str] = None     # Coach who sent the reply


@dataclass
class ValidationResult:
    ok: bool
    errors: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def _is_int_grade(v: Any) -> bool:
    if isinstance(v, bool):
        return False
    if isinstance(v, int):
        return MIN_GRADE <= v <= MAX_GRADE
    return False


def _is_iso_date(v: Any) -> bool:
    if not isinstance(v, str):
        return False
    try:
        date.fromisoformat(v)
        return True
    except ValueError:
        return False


def _validate_subject_grade_map(d: Any) -> Optional[str]:
    if not isinstance(d, dict):
        return "expected a {subject: grade_int} object"
    for k, v in d.items():
        if k not in GRADED_SUBJECTS:
            return f"subject '{k}' is not a graded subject"
        if v is None:
            continue
        if not _is_int_grade(v):
            return f"subject '{k}' grade '{v}' must be int in [{MIN_GRADE},{MAX_GRADE}]"
    return None


def _validate_subject_date_map(d: Any) -> Optional[str]:
    if not isinstance(d, dict):
        return "expected a {subject: ISO_date} object"
    for k, v in d.items():
        if k not in ALL_SUBJECTS:
            return f"subject '{k}' is not recognized"
        if v is None:
            continue
        if not _is_iso_date(v):
            return f"subject '{k}' date '{v}' is not ISO YYYY-MM-DD"
    return None


def _validate_xp_per_day_map(d: Any) -> Optional[str]:
    if not isinstance(d, dict):
        return "expected a {subject: xp_per_day} object"
    for k, v in d.items():
        if k not in ALL_SUBJECTS:
            return f"subject '{k}' is not recognized"
        if v is None:
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            return f"xp_per_day for '{k}' must be a number"
        if f < 0 or f > 200:
            return f"xp_per_day for '{k}' = {f} is out of range [0, 200]"
    return None


def _validate_ratified(v: Any) -> Optional[str]:
    if not isinstance(v, list):
        return "ratified must be a list of subject names"
    for item in v:
        if item not in ALL_SUBJECTS:
            return f"ratified entry '{item}' is not a recognized subject"
    return None


def validate_patch(
    patch: StructuredPatch,
    *,
    students_blob: Dict[str, Any],
) -> ValidationResult:
    """Validate a patch against the live students_blob (used for
    cross-field checks like 'student must exist')."""
    errors: List[str] = []

    if not patch.student_name:
        errors.append("patch.student_name is required")
    else:
        if patch.student_name not in (students_blob.get("students") or {}):
            errors.append(f"unknown student '{patch.student_name}'")

    for field_name, value in patch.updates.items():
        if field_name not in ALLOWED_FIELDS:
            errors.append(f"field '{field_name}' is not allowed")
            continue

        if field_name == "age_grade":
            if value is not None and not _is_int_grade(value):
                errors.append(
                    f"age_grade must be int in [{MIN_GRADE},{MAX_GRADE}]"
                )
        elif field_name in ("current_grade_per_subject",
                            "year_start_grade_per_subject",
                            "manual_test_out_grade"):
            err = _validate_subject_grade_map(value)
            if err:
                errors.append(f"{field_name}: {err}")
        elif field_name == "manual_test_out_date":
            err = _validate_subject_date_map(value)
            if err:
                errors.append(f"{field_name}: {err}")
        elif field_name == "overrides.xp_per_day":
            err = _validate_xp_per_day_map(value)
            if err:
                errors.append(f"{field_name}: {err}")
        elif field_name == "ratified":
            err = _validate_ratified(value)
            if err:
                errors.append(f"ratified: {err}")
        elif field_name == "notes":
            if value is not None and not isinstance(value, str):
                errors.append("notes must be a string or null")

    return ValidationResult(ok=len(errors) == 0, errors=errors)


# ---------------------------------------------------------------------------
# Apply
# ---------------------------------------------------------------------------


def _set_path(profile: Dict[str, Any], path: str, value: Any) -> None:
    """Set a dotted path inside profile, creating intermediate dicts."""
    if "." not in path:
        profile[path] = value
        return
    head, _, rest = path.partition(".")
    sub = profile.setdefault(head, {})
    if not isinstance(sub, dict):
        raise TypeError(f"path '{head}' is not a dict in profile")
    _set_path(sub, rest, value)


def _merge_dict(profile: Dict[str, Any], key: str, incoming: Dict[str, Any]) -> None:
    cur = profile.setdefault(key, {})
    if not isinstance(cur, dict):
        cur = {}
        profile[key] = cur
    for k, v in incoming.items():
        cur[k] = v


def apply_patch(
    patch: StructuredPatch,
    *,
    students_path: Path,
) -> Tuple[bool, List[str]]:
    """
    Validate + write the patch to disk. Returns (ok, errors).
    """
    blob = json.loads(students_path.read_text())
    result = validate_patch(patch, students_blob=blob)
    if not result.ok:
        return False, result.errors

    profile = blob["students"][patch.student_name]
    for field_name, value in patch.updates.items():
        if field_name == "age_grade":
            profile["age_grade"] = value
        elif field_name == "current_grade_per_subject":
            _merge_dict(profile, "current_grade_per_subject", value)
        elif field_name == "year_start_grade_per_subject":
            _merge_dict(profile, "year_start_grade_per_subject", value)
        elif field_name == "manual_test_out_grade":
            _merge_dict(profile, "manual_test_out_grade", value)
        elif field_name == "manual_test_out_date":
            _merge_dict(profile, "manual_test_out_date", value)
        elif field_name == "overrides.xp_per_day":
            overrides = profile.setdefault("overrides", {})
            xp = overrides.setdefault("xp_per_day", {})
            for k, v in value.items():
                xp[k] = v
        elif field_name == "ratified":
            cur = set(profile.get("ratified") or [])
            cur.update(value)
            profile["ratified"] = sorted(cur)
        elif field_name == "notes":
            profile["notes"] = value

    students_path.write_text(json.dumps(blob, indent=2, sort_keys=True) + "\n")
    return True, []
