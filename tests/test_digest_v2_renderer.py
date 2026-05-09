"""Phase 4 Part 6 — Unit tests for src/digest_v2_renderer.py.

These tests construct DigestV2Payload instances directly (no monkeypatch
needed) and check the rendered Slack mrkdwn for required structure and
absence of forbidden patterns (e.g., **double-star** bold).
"""
from __future__ import annotations

from src.digest_v2 import (
    CONCERN_BEHIND_MULTIPLE_DAYS,
    CONCERN_DEEP_DEFICIT,
    CoachRollup,
    DigestV2Payload,
    StudentMetrics,
)
from src.digest_v2_renderer import render_digest_v2


def _empty_payload():
    return DigestV2Payload(
        today="2026-05-11",
        current_window=("2026-05-07", "2026-05-11"),
        prior_window=("2026-05-02", "2026-05-06"),
        session_label="Session 9",
        days_in_current_window=5,
        days_in_prior_window=5,
    )


def test_render_empty_payload_has_no_concerns_message():
    out = render_digest_v2(_empty_payload())
    assert "Top concerns this week" in out
    assert "No students flagged" in out


def test_render_uses_slack_single_star_bold_not_double_star():
    p = _empty_payload()
    p.per_student["Alice"] = StudentMetrics(
        name="Alice",
        coach="Coach B",
        deficit_total=42.0,
        days_behind=3,
        concerns=[CONCERN_BEHIND_MULTIPLE_DAYS],
        severity=4.5,
    )
    p.top_concerns = [p.per_student["Alice"]]
    out = render_digest_v2(p)
    # Slack syntax: *Alice* (bold). Markdown **Alice** would NOT bold in Slack.
    assert "*Alice*" in out
    # No double-star bold leaking through.
    assert "**Alice**" not in out


def test_render_includes_window_and_session():
    out = render_digest_v2(_empty_payload())
    assert "2026-05-11" in out
    assert "Session 9" in out
    assert "2026-05-07" in out
    assert "2026-05-02" in out


def test_render_per_coach_section_present():
    p = _empty_payload()
    p.per_coach["Coach B"] = CoachRollup(
        name="Coach B",
        n_students=3,
        students_behind=2,
        avg_deficit_per_student=15.0,
    )
    out = render_digest_v2(p)
    assert "Per-coach roll-up" in out
    assert "Coach B" in out
    assert "2/3 students with days behind" in out


def test_render_handles_no_prior_window():
    p = DigestV2Payload(
        today="2026-05-11",
        current_window=("2026-05-07", "2026-05-11"),
        prior_window=None,
        session_label=None,
        days_in_current_window=5,
        days_in_prior_window=0,
    )
    out = render_digest_v2(p)
    assert "n/a" in out  # prior window formatted as n/a


def test_render_concern_tags_human_readable():
    p = _empty_payload()
    p.per_student["Carlos"] = StudentMetrics(
        name="Carlos",
        coach="Coach D",
        deficit_total=80.0,
        days_behind=4,
        concerns=[CONCERN_DEEP_DEFICIT],
        severity=6.2,
    )
    p.top_concerns = [p.per_student["Carlos"]]
    out = render_digest_v2(p)
    assert "deep deficit" in out
    # Severity rendered.
    assert "severity" in out.lower()
