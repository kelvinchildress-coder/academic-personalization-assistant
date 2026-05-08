"""Tests for src/agent/dispatcher.py — uses an in-memory FakeSlack."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

from src.agent.dispatcher import dispatch_message, DispatchResult
from src.agent.pending_state import get_proposal, list_proposals


@dataclass
class FakeSlack:
    sent: List[Dict[str, Any]] = field(default_factory=list)

    def send_dm(self, user_id: str, *, channel_id: Optional[str] = None,
                text: str = "") -> Optional[str]:
        self.sent.append({"user": user_id, "channel": channel_id, "text": text})
        return "1234567890.000001"


COACH = "Coach Lisa C Willis"
COACH_SLACK = "U_LISA"
CHAN = "D_DM"


@pytest.fixture
def coaches_blob():
    return {
        "coaches": {
            COACH: {"slack_id": COACH_SLACK, "students": ["Maya", "Marcus", "Jordan"]},
            "Coach Bo Sandler": {"slack_id": "U_BO", "students": ["Sam"]},
        }
    }


@pytest.fixture
def students_blob():
    return {
        "students": {
            "Maya":   {"age_grade": 4},
            "Marcus": {"age_grade": 5},
            "Jordan": {"age_grade": 7},
            "Sam":    {"age_grade": 4},
        }
    }


@pytest.fixture
def workspace(tmp_path: Path, students_blob):
    sp = tmp_path / "students.json"
    pp = tmp_path / "pending.json"
    sp.write_text(json.dumps(students_blob))
    return sp, pp


# ---------------------------------------------------------------------------
# Stage
# ---------------------------------------------------------------------------


def test_pause_intent_gets_staged(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()
    res = dispatch_message(
        text="Marcus is out today",
        coach_slack_id=COACH_SLACK,
        channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob,
        coaches_blob=coaches_blob,
        students_path=sp,
        pending_path=pp,
        slack=slack,
    )
    assert res.kind == "staged"
    assert "Marcus" in res.summary
    assert get_proposal(pp, COACH_SLACK, CHAN) is not None
    assert any("yes" in m["text"].lower() for m in slack.sent)


def test_unknown_returns_unknown(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()
    res = dispatch_message(
        text="Hey what was Maya's score last Tuesday",
        coach_slack_id=COACH_SLACK,
        channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob,
        coaches_blob=coaches_blob,
        students_path=sp,
        pending_path=pp,
        slack=slack,
    )
    assert res.kind == "unknown"
    assert get_proposal(pp, COACH_SLACK, CHAN) is None
    assert slack.sent == []


def test_bare_yes_with_no_pending_is_noop(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()
    res = dispatch_message(
        text="yes",
        coach_slack_id=COACH_SLACK,
        channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob,
        coaches_blob=coaches_blob,
        students_path=sp,
        pending_path=pp,
        slack=slack,
    )
    assert res.kind == "noop"
    assert slack.sent == []


# ---------------------------------------------------------------------------
# Confirm + Apply
# ---------------------------------------------------------------------------


def test_yes_confirms_and_applies(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()

    # Stage.
    dispatch_message(
        text="Marcus is out today",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    # Confirm.
    res = dispatch_message(
        text="yes",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    assert res.kind == "confirmed"
    assert res.affected_students == 1
    # Pending cleared.
    assert get_proposal(pp, COACH_SLACK, CHAN) is None
    # Exception persisted.
    blob = json.loads(sp.read_text())
    excs = blob["students"]["Marcus"]["exceptions"]
    assert len(excs) == 1
    assert excs[0]["type"] == "pause"
    # Slack got a confirm message.
    assert any(":white_check_mark:" in m["text"] for m in slack.sent)


def test_no_drops_pending(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()

    dispatch_message(
        text="Marcus is out today",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    res = dispatch_message(
        text="no",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    assert res.kind == "dropped"
    assert get_proposal(pp, COACH_SLACK, CHAN) is None
    # Original students.json unchanged (no exceptions written).
    blob = json.loads(sp.read_text())
    assert "exceptions" not in blob["students"]["Marcus"] or \
           blob["students"]["Marcus"].get("exceptions") == []


# ---------------------------------------------------------------------------
# Refine
# ---------------------------------------------------------------------------


def test_refine_replaces_pending_proposal(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()

    # Stage A.
    dispatch_message(
        text="Marcus is out today",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    p1 = get_proposal(pp, COACH_SLACK, CHAN)
    assert p1 is not None and "Marcus" in p1.summary_text

    # Refine: send a different intent without yes/no.
    res = dispatch_message(
        text="Maya is out for 3 days",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    assert res.kind == "refined"
    p2 = get_proposal(pp, COACH_SLACK, CHAN)
    assert p2 is not None and "Maya" in p2.summary_text


def test_unrecognized_text_with_pending_asks_for_clarity(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()
    dispatch_message(
        text="Marcus is out today",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    res = dispatch_message(
        text="thanks",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    assert res.kind == "needs_clarification"
    assert get_proposal(pp, COACH_SLACK, CHAN) is not None
    assert any("yes" in m["text"].lower() and "no" in m["text"].lower()
               for m in slack.sent)


def test_group_rule_l2_stages_with_expansion(workspace, students_blob, coaches_blob):
    sp, pp = workspace
    slack = FakeSlack()
    res = dispatch_message(
        text="All my L2 kids are at field day Friday",
        coach_slack_id=COACH_SLACK, channel_id=CHAN,
        speaker_coach_name=COACH,
        students_blob=students_blob, coaches_blob=coaches_blob,
        students_path=sp, pending_path=pp, slack=slack,
    )
    assert res.kind == "staged"
    # Lisa's L2 kids (grades 4-5): Maya + Marcus -> 2 students.
    assert res.affected_students == 2
