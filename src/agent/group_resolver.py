"""Resolve a GroupSelector into a concrete list of student names.

Reads:
  - config/coaches.json — to find which students belong to a coach
  - config/students.json — to read each student's age_grade

Returns the list of student names that match the selector. Used by the
config_writer at confirm time to expand a GroupRule into per-student
patches before writing.

This module is read-only and side-effect-free. It never writes config.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .intents import GroupSelector, grades_for_band

REPO_ROOT = Path(__file__).resolve().parent.parent.parent


def _load_coaches(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or (REPO_ROOT / "config" / "coaches.json")
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def _load_students(path: Optional[Path] = None) -> Dict[str, Any]:
    p = path or (REPO_ROOT / "config" / "students.json")
    if not p.exists():
        return {"students": {}}
    return json.loads(p.read_text())


def _coach_to_student_list(coaches_blob: Dict[str, Any]) -> Dict[str, List[str]]:
    """Best-effort extraction of {coach_name: [student_name, ...]} from
    config/coaches.json. Tolerant of multiple shapes seen in the wild."""
    out: Dict[str, List[str]] = {}
    coaches = coaches_blob.get("coaches") or coaches_blob
    if isinstance(coaches, list):
        for entry in coaches:
            name = entry.get("name") or entry.get("coach")
            kids = entry.get("students") or entry.get("roster") or []
            if name and isinstance(kids, list):
                out[name] = [str(k) for k in kids]
    elif isinstance(coaches, dict):
        for name, val in coaches.items():
            if isinstance(val, dict):
                kids = val.get("students") or val.get("roster") or []
                if isinstance(kids, list):
                    out[name] = [str(k) for k in kids]
            elif isinstance(val, list):
                out[name] = [str(k) for k in val]
    return out


def _student_grade(students_blob: Dict[str, Any], student_name: str) -> Optional[int]:
    s = (students_blob.get("students") or {}).get(student_name)
    if not isinstance(s, dict):
        return None
    g = s.get("age_grade")
    if g is None:
        return None
    try:
        return int(g)
    except (ValueError, TypeError):
        return None


def resolve(selector: GroupSelector,
            speaker_coach_name: str,
            coaches_path: Optional[Path] = None,
            students_path: Optional[Path] = None) -> List[str]:
    """Return the list of student names matched by `selector`.

    `speaker_coach_name` is the coach who sent the original DM (used
    when selector.coach_scope == 'speaker'). Pass head-coach name with
    scope='all' for school-wide rules.
    """
    coaches_blob = _load_coaches(coaches_path)
    students_blob = _load_students(students_path)
    coach_roster = _coach_to_student_list(coaches_blob)

    # 1. Build the candidate pool of students by coach scope.
    if selector.coach_scope == "speaker":
        candidates = list(coach_roster.get(speaker_coach_name, []))
    else:
        candidates = []
        for kids in coach_roster.values():
            candidates.extend(kids)

    # 2. Apply explicit name list (intersection).
    if selector.student_names:
        wanted = {n.strip() for n in selector.student_names}
        candidates = [c for c in candidates if c in wanted]
        return _dedupe_keep_order(candidates)

    # 3. Apply grade/level filter.
    target_grades: set[int] = set()
    if selector.level_band:
        target_grades.update(grades_for_band(selector.level_band))
    if selector.grades:
        target_grades.update(int(g) for g in selector.grades)

    if not target_grades:
        # No grade filter -> return whole candidate pool (e.g. "all my kids")
        return _dedupe_keep_order(candidates)

    matched = []
    for name in candidates:
        g = _student_grade(students_blob, name)
        if g is not None and g in target_grades:
            matched.append(name)
    return _dedupe_keep_order(matched)


def _dedupe_keep_order(seq: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for x in seq:
        if x not in seen:
            seen.add(x)
            out.append(x)
    return out


def all_coach_names(coaches_path: Optional[Path] = None) -> List[str]:
    """Convenience: list every coach name in the roster."""
    blob = _load_coaches(coaches_path)
    return list(_coach_to_student_list(blob).keys())
