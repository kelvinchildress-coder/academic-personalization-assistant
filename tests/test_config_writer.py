"""Tests for src.agent.config_writer (validation + apply)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.config_writer import (
    StructuredPatch,
    apply_patch,
    validate_patch,
)


def _empty_blob():
    return {
        "version": 1,
        "as_of": "2026-05-08",
        "students": {
            "Allison Kim": {
                "age_grade": None,
                "current_grade_per_subject": {},
                "year_start_grade_per_subject": {},
                "manual_test_out_grade": {},
                "manual_test_out_date": {},
            }
        },
    }


# -------------------------- validation --------------------------------------


def test_unknown_student_rejected():
    patch = StructuredPatch(student_name="Ghost", updates={"age_grade": 4})
    res = validate_patch(patch, students_blob=_empty_blob())
    assert not res.ok
    assert any("unknown student" in e for e in res.errors)


def test_age_grade_must_be_int_in_range():
    patch = StructuredPatch(student_name="Allison Kim", updates={"age_grade": 99})
    res = validate_patch(patch, students_blob=_empty_blob())
    assert not res.ok


def test_age_grade_zero_is_valid():
    patch = StructuredPatch(student_name="Allison Kim", updates={"age_grade": 0})
    res = validate_patch(patch, students_blob=_empty_blob())
    assert res.ok


def test_unknown_subject_in_grade_map_rejected():
    patch = StructuredPatch(
        student_name="Allison Kim",
        updates={"current_grade_per_subject": {"Bogus": 5}},
    )
    res = validate_patch(patch, students_blob=_empty_blob())
    assert not res.ok


def test_xp_per_day_out_of_range_rejected():
    patch = StructuredPatch(
        student_name="Allison Kim",
        updates={"overrides.xp_per_day": {"Math": 9999}},
    )
    res = validate_patch(patch, students_blob=_empty_blob())
    assert not res.ok


def test_iso_date_format_required():
    patch = StructuredPatch(
        student_name="Allison Kim",
        updates={"manual_test_out_date": {"Math": "January 29, 2027"}},
    )
    res = validate_patch(patch, students_blob=_empty_blob())
    assert not res.ok


def test_disallowed_field_rejected():
    patch = StructuredPatch(
        student_name="Allison Kim",
        updates={"secret_field": "bad"},
    )
    res = validate_patch(patch, students_blob=_empty_blob())
    assert not res.ok


# -------------------------- apply roundtrip ---------------------------------


def test_apply_age_grade_roundtrip(tmp_path: Path):
    p = tmp_path / "students.json"
    p.write_text(json.dumps(_empty_blob()))
    ok, errs = apply_patch(
        StructuredPatch(student_name="Allison Kim", updates={"age_grade": 4}),
        students_path=p,
    )
    assert ok and not errs
    blob = json.loads(p.read_text())
    assert blob["students"]["Allison Kim"]["age_grade"] == 4


def test_apply_grade_map_merges(tmp_path: Path):
    p = tmp_path / "students.json"
    blob = _empty_blob()
    blob["students"]["Allison Kim"]["current_grade_per_subject"] = {"Math": 5}
    p.write_text(json.dumps(blob))
    ok, errs = apply_patch(
        StructuredPatch(
            student_name="Allison Kim",
            updates={"current_grade_per_subject": {"Reading": 4}},
        ),
        students_path=p,
    )
    assert ok
    after = json.loads(p.read_text())["students"]["Allison Kim"]
    assert after["current_grade_per_subject"] == {"Math": 5, "Reading": 4}


def test_apply_overrides_xp_per_day_dotted_path(tmp_path: Path):
    p = tmp_path / "students.json"
    p.write_text(json.dumps(_empty_blob()))
    ok, _ = apply_patch(
        StructuredPatch(
            student_name="Allison Kim",
            updates={"overrides.xp_per_day": {"Math": 30}},
        ),
        students_path=p,
    )
    assert ok
    after = json.loads(p.read_text())["students"]["Allison Kim"]
    assert after["overrides"]["xp_per_day"] == {"Math": 30}


def test_apply_ratified_dedupes_and_sorts(tmp_path: Path):
    p = tmp_path / "students.json"
    blob = _empty_blob()
    blob["students"]["Allison Kim"]["ratified"] = ["Reading"]
    p.write_text(json.dumps(blob))
    ok, _ = apply_patch(
        StructuredPatch(
            student_name="Allison Kim",
            updates={"ratified": ["Math", "Reading"]},
        ),
        students_path=p,
    )
    assert ok
    after = json.loads(p.read_text())["students"]["Allison Kim"]
    assert after["ratified"] == ["Math", "Reading"]


def test_apply_rejected_patch_does_not_mutate_file(tmp_path: Path):
    p = tmp_path / "students.json"
    original = _empty_blob()
    p.write_text(json.dumps(original))
    ok, errs = apply_patch(
        StructuredPatch(student_name="Ghost", updates={"age_grade": 4}),
        students_path=p,
    )
    assert not ok
    assert errs
    after = json.loads(p.read_text())
    assert after == original
