"""Tests for src/agent/intent_writer.py and src/agent/pending_state.py."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src.agent.intents import (
    Pause, HalfTarget, GroupRule, GroupSelector,
)
from src.agent.intent_writer import (
    build_proposal, apply_proposal, _expand_group_targets,
)
from src.agent.pending_state import (
    Proposal, stage_proposal, get_proposal, pop_proposal, clear_stale,
)


@pytest.fixture
def coaches_blob():
    # Production schema: dict-of-list (bare list of student names).
    # Slack IDs are NOT carried in coaches.json in production; they
    # come from the COACH_SLACK_IDS_JSON env var.
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
            "Maya":   {"age_grade": 4, "exceptions": []},
            "Marcus": {"age_grade": 5},
            "Jordan": {"age_grade": 7, "exceptions": []},
            "Sam":    {"age_grade": 4, "exceptions": []},
        }
    }


def test_pause_proposal_single_student(students_blob, coaches_blob):
    intent = Pause(
        student_name="Marcus", subject=None,
        start_date="2026-05-08", days=1,
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    assert p.intent_kind == "pause"
    assert p.expanded_targets == ["Marcus"]
    assert "Marcus" in p.summary_text


def test_half_target_proposal(students_blob, coaches_blob):
    intent = HalfTarget(
        student_name="Maya", subject="Math",
        start_date="2026-05-08", days=5,
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    assert p.intent_kind == "half_target"
    assert p.payload["subject"] == "Math"
    assert p.payload["days"] == 5


def test_group_rule_l2_expands_to_grade_4_5(students_blob, coaches_blob):
    intent = GroupRule(
        selector=GroupSelector(
            scope="speaker", level_band="L2",
            speaker_coach="Coach Lisa C Willis",
        ),
        action="pause", subject=None,
        start_date="2026-05-08", days=1,
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    # Lisa's roster is Maya/Marcus/Jordan; L2 is grades 4-5; so Maya(4)+Marcus(5).
    assert set(p.expanded_targets) == {"Maya", "Marcus"}


def test_group_rule_all_scope_includes_other_coaches(students_blob, coaches_blob):
    intent = GroupRule(
        selector=GroupSelector(
            scope="all", level_band="L2",
            speaker_coach="Coach Lisa C Willis",
        ),
        action="pause", subject=None,
        start_date="2026-05-08", days=1,
    )
    p = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    # All-scope, L2 grades 4-5: Maya(4), Marcus(5), Sam(4).
    assert set(p.expanded_targets) == {"Maya", "Marcus", "Sam"}


def test_apply_pause_adds_exception(tmp_path: Path, students_blob, coaches_blob):
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))
    intent = Pause(
        student_name="Marcus", subject="Writing",
        start_date="2026-05-08", days=3,
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
    excs = blob["students"]["Marcus"]["exceptions"]
    assert len(excs) == 1
    assert excs[0]["type"] == "pause"
    assert excs[0]["subject"] == "Writing"
    assert excs[0]["start"] == "2026-05-08"
    assert excs[0]["end"] == "2026-05-10"
    assert excs[0]["source_coach"] == "Coach Lisa C Willis"


def test_apply_creates_exceptions_field_lazily(tmp_path: Path, students_blob, coaches_blob):
    """Marcus has no 'exceptions' key in the fixture — apply should add it."""
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))
    assert "exceptions" not in students_blob["students"]["Marcus"]
    intent = Pause(
        student_name="Marcus", subject=None,
        start_date="2026-05-08", days=1,
    )
    proposal = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    ok, _, n = apply_proposal(
        proposal,
        students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok and n == 1
    blob = json.loads(sp.read_text())
    assert "exceptions" in blob["students"]["Marcus"]
    assert len(blob["students"]["Marcus"]["exceptions"]) == 1


def test_apply_group_rule_writes_one_exception_per_student(tmp_path: Path, students_blob, coaches_blob):
    sp = tmp_path / "students.json"
    sp.write_text(json.dumps(students_blob))
    intent = GroupRule(
        selector=GroupSelector(
            scope="speaker", level_band="L2",
            speaker_coach="Coach Lisa C Willis",
        ),
        action="pause", subject=None,
        start_date="2026-05-08", days=1,
    )
    proposal = build_proposal(
        intent,
        coach_slack_id="U_LISA",
        channel_id="D_DM",
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    ok, _, n = apply_proposal(
        proposal,
        students_path=sp,
        source_coach_name="Coach Lisa C Willis",
    )
    assert ok and n == 2
    blob = json.loads(sp.read_text())
    assert len(blob["students"]["Maya"]["exceptions"]) == 1
    assert len(blob["students"]["Marcus"]["exceptions"]) == 1
    assert blob["students"]["Jordan"].get("exceptions", []) == []


def test_pending_state_stage_get_pop(tmp_path: Path):
    sp = tmp_path / "pending.json"
    p = Proposal(
        coach_slack_id="U_LISA", channel_id="D_DM",
        intent_kind="pause", payload={"x": 1},
        expanded_targets=["Marcus"], summary_text="test",
    )
    stage_proposal(sp, p)
    got = get_proposal(sp, "U_LISA", "D_DM")
    assert got is not None and got.summary_text == "test"
    popped = pop_proposal(sp, "U_LISA", "D_DM")
    assert popped is not None
    assert get_proposal(sp, "U_LISA", "D_DM") is None


def test_pending_state_overwrite_replaces(tmp_path: Path):
    sp = tmp_path / "pending.json"
    p1 = Proposal(
        coach_slack_id="U_LISA", channel_id="D_DM",
        intent_kind="pause", payload={"v": 1},
        summary_text="first",
    )
    p2 = Proposal(
        coach_slack_id="U_LISA", channel_id="D_DM",
        intent_kind="pause", payload={"v": 2},
        summary_text="second",
    )
    stage_proposal(sp, p1)
    stage_proposal(sp, p2)
    got = get_proposal(sp, "U_LISA", "D_DM")
    assert got is not None and got.summary_text == "second"
