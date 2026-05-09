"""Tests for the SetTestBy intent path through intent_writer.

Covers Phase 3 wire-in: SetTestBy -> build_proposal -> apply_proposal,
which writes to student.overrides.test_by[subject] (Tier 0b in
src/targets.py._read_override_testby).
"""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.agent.intents import SetTestBy
from src.agent.intent_writer import build_proposal, apply_proposal


@pytest.fixture
def coaches_blob():
    # Production schema: dict-of-list.
    return {
        "coaches": {
            "Coach Lisa C Willis": ["Maya", "Marcus", "Jordan"],
            "Coach Bo Sandler": ["Sam"],
        }
    }


@pytest.fixture
def students_blob():
    return {
        "students": {
            "Maya": {"age_grade": 4},
            "Marcus": {"age_grade": 5, "overrides": {"test_by": {
                "Reading": {
                    "target_grade": 6,
                    "target_date": "2026-09-15",
                    "source_coach": "Coach Lisa C Willis",
                },
            }}},
            "Jordan": {"age_grade": 7},
            "Sam": {"age_grade": 4},
        }
    }


# ---------------------------------------------------------------------------
# build_proposal
# ---------------------------------------------------------------------------


def test_set_test_by_build_proposal_with_date_and_grade(students_blob, coaches_blob):
    intent = SetTestBy(
        student="Maya", subject="Math",
        target_grade=5,
        target_date=date(2026, 6, 12),
        raw_text="Push Maya's Math MAP to 6/12 at grade 5",
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    assert p.intent_kind == "set_test_by"
    assert p.expanded_targets == ["Maya"]
    assert p.payload["student_name"] == "Maya"
    assert p.payload["subject"] == "Math"
    assert p.payload["target_grade"] == 5
    # target_date must be ISO string in payload (JSON-safe).
    assert p.payload["target_date"] == "2026-06-12"
    assert "Maya" in p.summary_text
    assert "Math" in p.summary_text


def test_set_test_by_build_proposal_date_only(students_blob, coaches_blob):
    intent = SetTestBy(
        student="Maya", subject="Reading",
        target_grade=None,
        target_date=date(2026, 7, 1),
        raw_text="Move Maya's reading test to July 1",
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    assert p.intent_kind == "set_test_by"
    assert p.payload["target_grade"] is None
    assert p.payload["target_date"] == "2026-07-01"


def test_set_test_by_build_proposal_grade_only(students_blob, coaches_blob):
    intent = SetTestBy(
        student="Marcus", subject="Math",
        target_grade=6,
        target_date=None,
        raw_text="Marcus tests out of Math at grade 6",
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    assert p.intent_kind == "set_test_by"
    assert p.payload["target_grade"] == 6
    assert p.payload["target_date"] is None


# ---------------------------------------------------------------------------
# apply_proposal
# ---------------------------------------------------------------------------


def test_apply_set_test_by_creates_overrides_lazily(
    tmp_path: Path, students_blob, coaches_blob
):
    """Maya has no overrides; apply must lazy-create overrides.test_by[Math]."""
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))

    intent = SetTestBy(
        student="Maya", subject="Math",
        target_grade=5,
        target_date=date(2026, 6, 12),
        raw_text="Push Maya to 6/12 at grade 5",
    )
    proposal = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    ok, errs, n = apply_proposal(
        proposal,
        students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok and n == 1 and not errs

    blob = json.loads(sp.read_text())
    tb = blob["students"]["Maya"]["overrides"]["test_by"]["Math"]
    assert tb["target_grade"] == 5
    assert tb["target_date"] == "2026-06-12"
    assert tb["source_coach"] == "Coach Lisa C Willis"
    assert "raw_text" in tb
    assert "created_at" in tb


def test_apply_set_test_by_preserves_other_subject(
    tmp_path: Path, students_blob, coaches_blob
):
    """Marcus already has overrides.test_by.Reading; setting Math must not
    clobber Reading."""
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))

    intent = SetTestBy(
        student="Marcus", subject="Math",
        target_grade=6,
        target_date=date(2026, 8, 1),
        raw_text="Marcus tests out of Math at grade 6 by Aug 1",
    )
    proposal = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    ok, errs, n = apply_proposal(
        proposal,
        students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok and n == 1 and not errs

    blob = json.loads(sp.read_text())
    tb = blob["students"]["Marcus"]["overrides"]["test_by"]
    # Reading entry must still be there, untouched.
    assert tb["Reading"]["target_grade"] == 6
    assert tb["Reading"]["target_date"] == "2026-09-15"
    # Math entry must be the new one.
    assert tb["Math"]["target_grade"] == 6
    assert tb["Math"]["target_date"] == "2026-08-01"


def test_apply_set_test_by_merges_partial_updates(
    tmp_path: Path, students_blob, coaches_blob
):
    """First apply sets target_grade only; second apply sets target_date only;
    merged result must have both."""
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))

    # Step 1: grade only.
    grade_intent = SetTestBy(
        student="Maya", subject="Math",
        target_grade=5, target_date=None,
        raw_text="Maya tests out of Math at grade 5",
    )
    p1 = build_proposal(
        grade_intent,
        coach_slack_id="U_LISA", channel_id="D_DM",
        students_blob=students_blob, coaches_blob=coaches_blob,
    )
    ok1, _, _ = apply_proposal(
        p1, students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok1

    # Step 2: date only.
    date_intent = SetTestBy(
        student="Maya", subject="Math",
        target_grade=None, target_date=date(2026, 6, 12),
        raw_text="Move Maya's Math MAP to 6/12",
    )
    # Re-load blob from disk so build_proposal sees the post-step-1 state.
    students_blob2 = json.loads(sp.read_text())
    p2 = build_proposal(
        date_intent,
        coach_slack_id="U_LISA", channel_id="D_DM",
        students_blob=students_blob2, coaches_blob=coaches_blob,
    )
    ok2, _, _ = apply_proposal(
        p2, students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok2

    blob = json.loads(sp.read_text())
    tb = blob["students"]["Maya"]["overrides"]["test_by"]["Math"]
    # Merged: grade from step 1, date from step 2.
    assert tb["target_grade"] == 5
    assert tb["target_date"] == "2026-06-12"


def test_apply_set_test_by_unknown_student(
    tmp_path: Path, students_blob, coaches_blob
):
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))

    intent = SetTestBy(
        student="NotARealKid", subject="Math",
        target_grade=5, target_date=date(2026, 6, 12),
        raw_text="Push NotARealKid to 6/12",
    )
    proposal = build_proposal(
        intent,
        coach_slack_id="U_LISA", channel_id="D_DM",
        students_blob=students_blob, coaches_blob=coaches_blob,
    )
    ok, errs, n = apply_proposal(
        proposal,
        students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok is False
    assert n == 0
    assert any("NotARealKid" in e for e in errs)
