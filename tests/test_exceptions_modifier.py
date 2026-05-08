"""Tests for src/exceptions_modifier.py."""

from __future__ import annotations

from datetime import date

import pytest

from src.exceptions_modifier import (
    apply_exceptions,
    prune_expired,
    _is_active,
    _matches_subject,
    _select_active,
)
from src.targets import TargetResolution, PERSONALIZED_FLOOR_XP


def _make_resolution(*, tier: int, xp: float, subject: str = "Math") -> TargetResolution:
    return TargetResolution(
        student="Marcus",
        subject=subject,
        xp_per_day=xp,
        tier=tier,
        source_label=f"tier{tier}_test",
        target_grade=None,
        target_date=None,
        detail="test",
    )


# ---------------------------------------------------------------------------
# Helper-level
# ---------------------------------------------------------------------------


def test_is_active_within_window():
    exc = {"start": "2026-05-01", "end": "2026-05-10"}
    assert _is_active(exc, date(2026, 5, 5)) is True
    assert _is_active(exc, date(2026, 5, 1)) is True   # inclusive start
    assert _is_active(exc, date(2026, 5, 10)) is True  # inclusive end
    assert _is_active(exc, date(2026, 4, 30)) is False
    assert _is_active(exc, date(2026, 5, 11)) is False


def test_matches_subject_full_day():
    exc = {"subject": None}
    assert _matches_subject(exc, "Math")
    assert _matches_subject(exc, "Reading")


def test_matches_subject_specific():
    exc = {"subject": "Math"}
    assert _matches_subject(exc, "Math")
    assert not _matches_subject(exc, "Reading")


# ---------------------------------------------------------------------------
# Pause
# ---------------------------------------------------------------------------


def test_no_exceptions_returns_unchanged():
    res = _make_resolution(tier=3, xp=42.0)
    out = apply_exceptions(res, student_profile={}, today=date(2026, 5, 8))
    assert out is res or out.xp_per_day == 42.0


def test_full_day_pause_zeroes_target():
    res = _make_resolution(tier=3, xp=42.0)
    profile = {"exceptions": [
        {"type": "pause", "subject": None,
         "start": "2026-05-08", "end": "2026-05-08",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 0.0
    assert out.source_label == "exception_pause"
    assert "Coach Lisa C Willis" in out.detail


def test_per_subject_pause_only_zeroes_that_subject():
    res_math = _make_resolution(tier=3, xp=42.0, subject="Math")
    res_read = _make_resolution(tier=3, xp=25.0, subject="Reading")
    profile = {"exceptions": [
        {"type": "pause", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-08",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out_math = apply_exceptions(res_math, student_profile=profile, today=date(2026, 5, 8))
    out_read = apply_exceptions(res_read, student_profile=profile, today=date(2026, 5, 8))
    assert out_math.xp_per_day == 0.0
    assert out_read.xp_per_day == 25.0


def test_pause_outside_window_does_not_apply():
    res = _make_resolution(tier=3, xp=42.0)
    profile = {"exceptions": [
        {"type": "pause", "subject": None,
         "start": "2026-04-01", "end": "2026-04-05",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 42.0


# ---------------------------------------------------------------------------
# Half target
# ---------------------------------------------------------------------------


def test_half_target_applies_to_tier_3():
    res = _make_resolution(tier=3, xp=40.0)
    profile = {"exceptions": [
        {"type": "half_target", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-12",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 20.0
    assert "half_target" in out.source_label


def test_half_target_applies_to_tier_4():
    res = _make_resolution(tier=4, xp=25.0)
    profile = {"exceptions": [
        {"type": "half_target", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-12",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 12.5
    assert "half_target" in out.source_label


def test_half_target_floors_at_personalized_floor():
    """A halved 15 XP/day should floor at PERSONALIZED_FLOOR_XP (10)."""
    res = _make_resolution(tier=3, xp=15.0)
    profile = {"exceptions": [
        {"type": "half_target", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-12",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == PERSONALIZED_FLOOR_XP


def test_half_target_skipped_for_tier_0_coach_override():
    """Tier 0a coach override is sacrosanct — half-modifier must not touch it."""
    res = _make_resolution(tier=0, xp=40.0)
    res.source_label = "tier0a_coach_override"
    profile = {"exceptions": [
        {"type": "half_target", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-12",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 40.0
    assert "skipped" in out.detail.lower()


def test_half_target_skipped_for_tier_1_grade_mastered():
    res = _make_resolution(tier=1, xp=33.0)
    profile = {"exceptions": [
        {"type": "half_target", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-12",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 33.0


# ---------------------------------------------------------------------------
# Combined
# ---------------------------------------------------------------------------


def test_pause_wins_over_half_target_when_both_active():
    res = _make_resolution(tier=3, xp=40.0)
    profile = {"exceptions": [
        {"type": "half_target", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-12",
         "source_coach": "Coach Lisa C Willis"},
        {"type": "pause", "subject": "Math",
         "start": "2026-05-08", "end": "2026-05-08",
         "source_coach": "Coach Lisa C Willis"},
    ]}
    out = apply_exceptions(res, student_profile=profile, today=date(2026, 5, 8))
    assert out.xp_per_day == 0.0
    assert out.source_label == "exception_pause"


# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------


def test_prune_expired_drops_old_entries():
    excs = [
        {"type": "pause", "end": "2026-04-01"},
        {"type": "pause", "end": "2026-05-08"},
        {"type": "pause", "end": "2026-05-10"},
    ]
    kept, removed = prune_expired(excs, today=date(2026, 5, 8))
    assert removed == 1
    assert len(kept) == 2


def test_prune_expired_keeps_malformed():
    excs = [{"type": "pause"}, {"type": "pause", "end": "bogus"}]
    kept, removed = prune_expired(excs, today=date(2026, 5, 8))
    # Malformed entries should be kept (caller decides what to do).
    assert removed == 0
    assert len(kept) == 2
