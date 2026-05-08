"""Tests for src.student_progress."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.student_progress import (
    ALL_SUBJECTS,
    GRADED_SUBJECTS,
    grade_int_to_key,
    grade_key_to_int,
    is_export_stale,
    normalize_student_name,
    normalize_subject,
    build_progress_ledger,
)


# -------------------------- normalization ----------------------------------


def test_subject_aliases():
    assert normalize_subject("Math") == "Math"
    assert normalize_subject("math") == "Math"
    assert normalize_subject("vocab") == "Vocabulary"
    assert normalize_subject("fast math") == "FastMath"
    assert normalize_subject("Unknown") is None
    assert normalize_subject("") is None
    assert normalize_subject(None) is None


def test_grade_key_roundtrip():
    assert grade_key_to_int("K") == 0
    assert grade_int_to_key(0) == "K"
    for i in range(1, 13):
        key = grade_int_to_key(i)
        assert grade_key_to_int(key) == i


def test_lisa_willis_normalization():
    assert normalize_student_name("Lisa Willis") == "Lisa C Willis"
    assert normalize_student_name("Lisa C Willis") == "Lisa C Willis"
    assert normalize_student_name("Allison Kim") == "Allison Kim"


# -------------------------- staleness --------------------------------------


def test_export_stale_when_none():
    assert is_export_stale(None)


def test_export_fresh_under_24h():
    now = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)
    earlier = datetime(2026, 5, 8, 6, 0, tzinfo=timezone.utc)
    assert not is_export_stale(earlier, now=now)


def test_export_stale_over_24h():
    now = datetime(2026, 5, 8, 12, 0, tzinfo=timezone.utc)
    earlier = datetime(2026, 5, 7, 6, 0, tzinfo=timezone.utc)
    assert is_export_stale(earlier, now=now)


# -------------------------- ledger end-to-end ------------------------------


def _write_fixture(tmp_path: Path) -> dict:
    latest = {
        "date": "2026-05-04",
        "mode": "morning",
        "timestamp": "2026-05-04T07:00:00+00:00",
        "students": [
            {
                "name": "Allison Kim",
                "total_xp": 50.0,
                "overall_accuracy": 0.85,
                "total_minutes": 40,
                "absent": False,
                "subjects": [
                    {"name": "Math", "xp": 30, "accuracy": 0.9, "minutes": 20,
                     "mastered": False, "no_data": False, "has_test": False},
                    {"name": "Unknown", "xp": 5, "accuracy": 0.5, "minutes": 5,
                     "mastered": False, "no_data": False, "has_test": False},
                ],
            },
            {
                "name": "Lisa Willis",  # legacy spelling
                "total_xp": 0,
                "overall_accuracy": 0,
                "total_minutes": 0,
                "absent": True,
                "subjects": [],
            },
        ],
    }
    students = {
        "version": 1,
        "as_of": "2026-05-04",
        "students": {
            "Allison Kim": {
                "age_grade": 4,
                "current_grade_per_subject": {"Math": 5},
                "year_start_grade_per_subject": {"Math": 4},
                "manual_test_out_grade": {},
                "manual_test_out_date": {},
            },
            "Lisa C Willis": {
                "age_grade": 8,
                "current_grade_per_subject": {},
                "year_start_grade_per_subject": {},
                "manual_test_out_grade": {},
                "manual_test_out_date": {},
            },
        },
    }
    grade_xp = {
        "version": 1,
        "last_updated": None,
        "source": "test",
        "grades": {
            grade_int_to_key(i): {s: None for s in ALL_SUBJECTS}
            for i in range(0, 13)
        },
    }
    paths = {
        "latest": tmp_path / "latest.json",
        "students": tmp_path / "students.json",
        "grade_xp": tmp_path / "grade_xp.json",
    }
    paths["latest"].write_text(json.dumps(latest))
    paths["students"].write_text(json.dumps(students))
    paths["grade_xp"].write_text(json.dumps(grade_xp))
    return paths


def test_build_ledger_handles_unknown_subject_and_name_normalization(tmp_path: Path):
    paths = _write_fixture(tmp_path)
    ledger = build_progress_ledger(
        latest_path=paths["latest"],
        students_path=paths["students"],
        grade_xp_path=paths["grade_xp"],
        now=datetime(2026, 5, 4, 8, 0, tzinfo=timezone.utc),
    )
    assert ledger.school_day.isoformat() == "2026-05-04"
    assert ledger.mode == "morning"
    assert not ledger.is_stale

    by_name = {s.name: s for s in ledger.students}
    assert "Allison Kim" in by_name
    # "Lisa Willis" should have been normalized to "Lisa C Willis".
    assert "Lisa C Willis" in by_name

    allison = by_name["Allison Kim"]
    # Math row passes through, Unknown is captured separately.
    assert any(s.subject == "Math" for s in allison.subjects)
    assert not any(s.subject == "Unknown" for s in allison.subjects)
    assert allison.unknown_subject_rows  # captured for coach review
