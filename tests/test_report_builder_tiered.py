"""Tests for the tier-aware reporting layer in src.report_builder."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Tuple

import pytest

from src.models import CoachRoster, Coach
from src.report_builder import (
    build_tiered_morning_payload,
    build_stale_data_dm,
)


# Lightweight stand-ins matching the duck-typed shapes the builder reads.
@dataclass(frozen=True)
class _Subject:
    subject: str
    xp_today: float = 0.0
    accuracy_today: float | None = None
    minutes_today: float = 0.0
    mastered_today: bool = False
    no_data: bool = False
    has_test: bool = False
    current_grade: int | None = None
    year_start_grade: int | None = None
    target_grade_total_xp: float | None = None
    remaining_xp_to_target_grade: float | None = None
    target_grade: int | None = None
    target_date: date | None = None
    target_source: str = "default_q2"
    detail: str = ""


@dataclass(frozen=True)
class _Student:
    name: str
    age_grade: int | None = 4
    total_xp_today: float = 0.0
    overall_accuracy_today: float | None = None
    total_minutes_today: float = 0.0
    absent: bool = False
    is_stale: bool = False
    subjects: Tuple[_Subject, ...] = ()
    unknown_subject_rows: Tuple = ()


@dataclass(frozen=True)
class _Ledger:
    school_day: date
    mode: str
    exported_at: datetime | None
    is_stale: bool
    students: Tuple[_Student, ...]


def _roster() -> CoachRoster:
    return CoachRoster(
        head_coach="Kelvin Childress",
        coaches=[
            Coach(name="Amir Lewis", students=["Allison Kim"]),
            Coach(name="Lisa C Willis", students=["Stone Meyers"]),
        ],
        channel="sports",
    )


def _students_config():
    return {
        "students": {
            "Allison Kim": {
                "age_grade": 4,
                "current_grade_per_subject": {"Math": 4},
                "year_start_grade_per_subject": {"Math": 4},
                "manual_test_out_grade": {},
                "manual_test_out_date": {},
            },
            "Stone Meyers": {
                "age_grade": 8,
                "current_grade_per_subject": {"Math": 8},
                "year_start_grade_per_subject": {"Math": 8},
                "manual_test_out_grade": {},
                "manual_test_out_date": {},
            },
        }
    }


def test_stale_ledger_returns_dm_only():
    ledger = _Ledger(
        school_day=date(2026, 5, 8),
        mode="morning",
        exported_at=None,
        is_stale=True,
        students=(),
    )
    payload = build_tiered_morning_payload(
        ledger=ledger,
        students_config=_students_config(),
        grade_xp_table={},
        roster=_roster(),
    )
    assert payload.is_stale
    assert payload.parent_text == ""
    assert payload.coach_blocks == ()
    assert payload.head_coach_dm_text and ":red_circle:" in payload.head_coach_dm_text


def test_payload_groups_students_by_coach_and_cites_tier():
    students = (
        _Student(
            name="Allison Kim",
            subjects=(_Subject(subject="Math", xp_today=10.0, accuracy_today=0.85),),
        ),
        _Student(
            name="Stone Meyers",
            subjects=(_Subject(subject="Math", xp_today=20.0, accuracy_today=0.7),),
        ),
    )
    ledger = _Ledger(
        school_day=date(2026, 5, 8),
        mode="morning",
        exported_at=datetime(2026, 5, 8, 7, tzinfo=timezone.utc),
        is_stale=False,
        students=students,
    )
    payload = build_tiered_morning_payload(
        ledger=ledger,
        students_config=_students_config(),
        grade_xp_table={},
        roster=_roster(),
        coach_slack_ids={"Amir Lewis": "U_AMIR", "Lisa C Willis": "U_LISA"},
    )
    assert not payload.is_stale
    coach_names = [b.coach_name for b in payload.coach_blocks]
    assert set(coach_names) >= {"Amir Lewis", "Lisa C Willis"}

    # Each block text should mention the coach + a tier tag like [T...] in the row.
    for block in payload.coach_blocks:
        if block.coach_name == "Amir Lewis":
            assert "<@U_AMIR>" in block.text
            assert "[T" in block.text  # tier-tag marker present
            assert "Allison Kim" in block.text


def test_unassigned_students_surface_for_head_coach():
    students = (
        _Student(
            name="Ghost Pupil",
            subjects=(_Subject(subject="Math"),),
        ),
    )
    ledger = _Ledger(
        school_day=date(2026, 5, 8),
        mode="morning",
        exported_at=datetime(2026, 5, 8, 7, tzinfo=timezone.utc),
        is_stale=False,
        students=students,
    )
    payload = build_tiered_morning_payload(
        ledger=ledger,
        students_config={"students": {}},
        grade_xp_table={},
        roster=_roster(),
        coach_slack_ids={"Kelvin Childress": "U_HEAD"},
    )
    block_names = [b.coach_name for b in payload.coach_blocks]
    assert "Unassigned" in block_names


def test_stale_data_dm_contains_date_and_protocol():
    text = build_stale_data_dm(date(2026, 5, 8), datetime(2026, 5, 7, 7, tzinfo=timezone.utc))
    assert "Skipping morning report" in text
    assert "May 8" in text or "5-8" in text or "2026-05-08" in text or "May" in text
