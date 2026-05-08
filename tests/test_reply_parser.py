"""Tests for src.agent.reply_parser (deterministic regex layer)."""

from __future__ import annotations

import pytest

from src.agent.gap_finder import GoalGap
from src.agent.reply_parser import parse_reply


def _gap(kind: str, subject: str | None = None, student: str = "Allison Kim"):
    return GoalGap(
        student_name=student,
        coach_name="Amir Lewis",
        subject=subject,
        kind=kind,
        detail="",
    )


# ------------------------- AGE GRADE replies -------------------------------


def test_bare_integer_reply_to_age_grade():
    res = parse_reply("4", gap=_gap("MISSING_AGE_GRADE"))
    assert len(res.patches) == 1
    p = res.patches[0]
    assert p.student_name == "Allison Kim"
    assert p.updates == {"age_grade": 4}


def test_kindergarten_reply_to_age_grade():
    res = parse_reply("K", gap=_gap("MISSING_AGE_GRADE"))
    assert res.patches and res.patches[0].updates == {"age_grade": 0}


def test_age_grade_with_ordinal_suffix():
    res = parse_reply("7th", gap=_gap("MISSING_AGE_GRADE"))
    assert res.patches and res.patches[0].updates == {"age_grade": 7}


def test_age_grade_in_sentence():
    res = parse_reply("She's in 5", gap=_gap("MISSING_AGE_GRADE"))
    assert res.patches and res.patches[0].updates == {"age_grade": 5}


# ------------------------- USE DEFAULT -------------------------------------


def test_use_default_ratifies_subject():
    res = parse_reply("use default", gap=_gap("MISSING_RATIFICATION", "Math"))
    assert res.patches and res.patches[0].updates == {"ratified": ["Math"]}


def test_default_alone_also_works():
    res = parse_reply("default please", gap=_gap("MISSING_TARGET", "Reading"))
    assert res.patches and res.patches[0].updates == {"ratified": ["Reading"]}


# ------------------------- SUBJECT + GRADE ---------------------------------


def test_subject_grade_for_current_grade_gap():
    res = parse_reply("Math 6", gap=_gap("MISSING_CURRENT_GRADE", "Math"))
    p = res.patches[0]
    assert p.updates == {"current_grade_per_subject": {"Math": 6}}


def test_subject_grade_for_year_start_gap():
    res = parse_reply("Math 4", gap=_gap("MISSING_YEAR_START", "Math"))
    p = res.patches[0]
    assert p.updates == {"year_start_grade_per_subject": {"Math": 4}}


def test_subject_grade_for_target_gap():
    res = parse_reply("Math 7", gap=_gap("MISSING_TARGET", "Math"))
    p = res.patches[0]
    assert p.updates == {"manual_test_out_grade": {"Math": 7}}


def test_alias_lang_resolves_to_language():
    res = parse_reply("Lang 5", gap=_gap("MISSING_CURRENT_GRADE", "Language"))
    p = res.patches[0]
    assert p.updates == {"current_grade_per_subject": {"Language": 5}}


# ------------------------- XP/DAY OVERRIDE ---------------------------------


def test_xp_per_day_override():
    res = parse_reply("Math 30/day", gap=_gap("MISSING_TARGET", "Math"))
    p = res.patches[0]
    assert p.updates == {"overrides.xp_per_day": {"Math": 30.0}}


def test_xp_per_day_with_xp_keyword():
    res = parse_reply("Reading 18 xp/day", gap=_gap("MISSING_TARGET", "Reading"))
    p = res.patches[0]
    assert p.updates == {"overrides.xp_per_day": {"Reading": 18.0}}


# ------------------------- TEST-BY OVERRIDE --------------------------------


def test_test_by_with_grade():
    res = parse_reply(
        "Math by 2027-01-29 to 7",
        gap=_gap("MISSING_TARGET", "Math"),
    )
    p = res.patches[0]
    assert p.updates.get("manual_test_out_date") == {"Math": "2027-01-29"}
    assert p.updates.get("manual_test_out_grade") == {"Math": 7}


def test_test_by_without_grade():
    res = parse_reply(
        "Reading by 2027-05-21",
        gap=_gap("MISSING_TARGET", "Reading"),
    )
    p = res.patches[0]
    assert p.updates.get("manual_test_out_date") == {"Reading": "2027-05-21"}
    assert "manual_test_out_grade" not in p.updates


# ------------------------- EMPTY / GIBBERISH -------------------------------


def test_empty_reply():
    res = parse_reply("", gap=_gap("MISSING_AGE_GRADE"))
    assert res.patches == []
    assert res.warnings


def test_unparseable_reply_no_llm():
    """Without ANTHROPIC_API_KEY in env, gibberish should fall through
    cleanly without crashing or producing a patch."""
    res = parse_reply(
        "ok i'll get back to you next week",
        gap=_gap("MISSING_TARGET", "Math"),
        anthropic_api_key=None,
    )
    # No deterministic match -> no patches produced.
    assert res.patches == []
