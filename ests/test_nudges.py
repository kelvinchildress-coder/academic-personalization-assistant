"""Phase 4 Part 6 — Unit tests for src/nudges.py."""
from __future__ import annotations

from src.digest_v2 import (
    CONCERN_BEHIND_MULTIPLE_DAYS,
    CoachRollup,
    DigestV2Payload,
    StudentMetrics,
)
from src.nudges import (
    MAX_STUDENTS_IN_NUDGE,
    build_coach_nudges,
)


def _payload_with_coach(coach_name: str, students):
    p = DigestV2Payload(
        today="2026-05-11",
        current_window=("2026-05-07", "2026-05-11"),
        prior_window=("2026-05-02", "2026-05-06"),
        session_label="Session 9",
        days_in_current_window=5,
        days_in_prior_window=5,
    )
    p.per_coach[coach_name] = CoachRollup(
        name=coach_name,
        n_students=len(students),
        students_behind=sum(1 for s in students if s.concerns),
    )
    for s in students:
        p.per_student[s.name] = s
    return p


def test_no_concerns_yields_no_nudges():
    s = StudentMetrics(name="Anna", coach="Coach P")
    p = _payload_with_coach("Coach P", [s])
    out = build_coach_nudges(p, {"Coach P": "U123"})
    assert out == []


def test_coach_with_flagged_student_gets_nudge():
    s = StudentMetrics(
        name="Anna",
        coach="Coach P",
        deficit_total=40.0,
        days_behind=3,
        concerns=[CONCERN_BEHIND_MULTIPLE_DAYS],
        severity=3.0,
    )
    p = _payload_with_coach("Coach P", [s])
    out = build_coach_nudges(p, {"Coach P": "U123"})
    assert len(out) == 1
    nudge = out[0]
    assert nudge.coach_name == "Coach P"
    assert nudge.slack_user_id == "U123"
    assert "Anna" in nudge.text
    assert "behind multiple days" in nudge.text


def test_missing_slack_id_silently_skips_coach():
    s = StudentMetrics(
        name="Bob",
        coach="Coach Q",
        deficit_total=40.0,
        days_behind=3,
        concerns=[CONCERN_BEHIND_MULTIPLE_DAYS],
        severity=3.0,
    )
    p = _payload_with_coach("Coach Q", [s])
    # Empty Slack ID map -> no nudges, no exception.
    out = build_coach_nudges(p, {})
    assert out == []


def test_nudge_caps_student_count_with_overflow_message():
    students = [
        StudentMetrics(
            name=f"S{i}",
            coach="Coach R",
            deficit_total=40.0,
            days_behind=3,
            concerns=[CONCERN_BEHIND_MULTIPLE_DAYS],
            severity=3.0,
        )
        for i in range(MAX_STUDENTS_IN_NUDGE + 3)
    ]
    p = _payload_with_coach("Coach R", students)
    out = build_coach_nudges(p, {"Coach R": "U999"})
    assert len(out) == 1
    text = out[0].text
    # The overflow line should reference the head-coach digest.
    assert "head-coach digest" in text


def test_nudge_uses_slack_single_star_bold():
    s = StudentMetrics(
        name="Diana",
        coach="Coach S",
        deficit_total=40.0,
        days_behind=3,
        concerns=[CONCERN_BEHIND_MULTIPLE_DAYS],
        severity=3.0,
    )
    p = _payload_with_coach("Coach S", [s])
    out = build_coach_nudges(p, {"Coach S": "U777"})
    text = out[0].text
    assert "*Diana*" in text
    assert "**Diana**" not in text
