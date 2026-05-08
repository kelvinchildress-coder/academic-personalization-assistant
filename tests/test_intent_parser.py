"""Tests for src/agent/intent_parser.py — deterministic layer only.

The Anthropic fallback is exercised live in integration; here we just
assert the regex/keyword pass produces the right Intent shape so the
LLM is only invoked when needed.
"""

from __future__ import annotations

from datetime import date

import pytest

from src.agent.intent_parser import parse_intent
from src.agent.intents import (
    Pause,
    HalfTarget,
    GroupRule,
    ConfirmYes,
    ConfirmNo,
    Refine,
    Unknown,
)


SPEAKER = "Coach Lisa C Willis"


def test_empty_returns_unknown():
    out = parse_intent("", speaker_coach_name=SPEAKER)
    assert isinstance(out, Unknown)


def test_yes_token():
    out = parse_intent("yes", speaker_coach_name=SPEAKER)
    assert isinstance(out, ConfirmYes)


def test_no_token():
    out = parse_intent("no thanks", speaker_coach_name=SPEAKER)
    assert isinstance(out, ConfirmNo)


def test_student_out_today_full_day_pause():
    out = parse_intent("Marcus is out today", speaker_coach_name=SPEAKER)
    assert isinstance(out, Pause)
    assert out.student_name == "Marcus"
    assert out.subject is None
    assert out.days == 1
    assert out.start_date == date.today().isoformat()


def test_student_out_three_days():
    out = parse_intent("Maya is out for 3 days", speaker_coach_name=SPEAKER)
    assert isinstance(out, Pause)
    assert out.student_name == "Maya"
    assert out.days == 3


def test_pause_subject_for_student():
    out = parse_intent(
        "pause Marcus writing for 5 days",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, Pause)
    assert out.student_name == "Marcus"
    assert out.subject == "Writing"
    assert out.days == 5


def test_half_target_single_student():
    out = parse_intent(
        "Half Math expectations for Maya this week",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, HalfTarget)
    assert out.student_name == "Maya"
    assert out.subject == "Math"
    assert out.days == 5


def test_group_rule_l2_band_pause():
    out = parse_intent(
        "All my L2 kids are at field day Friday",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, GroupRule)
    assert out.action == "pause"
    assert out.selector.level_band == "L2"
    assert out.selector.scope == "speaker"


def test_group_rule_4th_graders_to_l2():
    out = parse_intent(
        "My 4th graders are out tomorrow",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, GroupRule)
    assert out.selector.level_band == "L2"
    assert out.action == "pause"


def test_group_rule_ms_band():
    out = parse_intent(
        "All my MS students need half writing this week",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, GroupRule)
    assert out.action == "half_target"
    assert out.selector.level_band == "L3"
    assert out.subject == "Writing"


def test_group_rule_school_wide():
    out = parse_intent(
        "Pause across the school for 2 days",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, GroupRule)
    assert out.selector.scope == "all"
    assert out.action == "pause"
    assert out.days == 2


def test_unknown_freeform():
    out = parse_intent(
        "Hey, can you remind me what Marcus's score was last Tuesday?",
        speaker_coach_name=SPEAKER,
    )
    # No exception/pause/group action — should fall to Unknown so dispatcher
    # can route to historical-query handler.
    assert isinstance(out, Unknown)


def test_kindergarten_to_ll_band():
    out = parse_intent(
        "My kindergarten kids are out today",
        speaker_coach_name=SPEAKER,
    )
    assert isinstance(out, GroupRule)
    assert out.selector.level_band == "LL"
