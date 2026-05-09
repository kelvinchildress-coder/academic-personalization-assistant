"""Phase 4 Part 6 — Unit tests for src/digest_v2.py.

Tests use synthetic history snapshots injected via monkeypatch on
src.digest_v2.read_range, so they run without touching disk or the real
data/history directory.

Snapshot shape (matches Phase 1 history.py):
    {
        "date": "YYYY-MM-DD",
        "students": [
            {
                "name": "...",
                "coach": "...",
                "subjects": [
                    {
                        "name": "Math",
                        "target_xp": 30,
                        "actual_xp": 12,
                        "status": "behind",          # or "on_track"
                        "tier": "personalized_base", # or coach_xp_override / coach_test_by / age_grade
                    },
                    ...
                ],
            },
            ...
        ],
    }
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Dict, List

import pytest

from src import digest_v2 as dv2


# ---------------------------------------------------------------------------
# Synthetic snapshot helpers
# ---------------------------------------------------------------------------
def _subj(name, tgt, act, status="on_track", tier="personalized_base"):
    return {
        "name": name,
        "target_xp": tgt,
        "actual_xp": act,
        "status": status,
        "tier": tier,
    }


def _student(name, coach, subjects):
    return {"name": name, "coach": coach, "subjects": subjects}


def _snapshot(d: date, students: List[Dict]):
    return {"date": d.isoformat(), "students": students}


def _patch_read_range(monkeypatch, snapshots_by_date: Dict[date, Dict]):
    """Patch dv2.read_range to return our synthetic snapshots."""

    def fake_read_range(start_iso: str, end_iso: str):
        start = date.fromisoformat(start_iso)
        end = date.fromisoformat(end_iso)
        out = []
        d = start
        while d <= end:
            if d in snapshots_by_date:
                out.append(snapshots_by_date[d])
            d += timedelta(days=1)
        return out

    monkeypatch.setattr(dv2, "read_range", fake_read_range)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_empty_history_produces_empty_payload(monkeypatch):
    _patch_read_range(monkeypatch, {})
    payload = dv2.build_digest_v2(date(2026, 5, 11))
    assert payload.per_student == {}
    assert payload.per_coach == {}
    assert payload.top_concerns == []
    assert payload.days_in_current_window == 0


def test_single_student_on_track_is_not_a_concern(monkeypatch):
    today = date(2026, 5, 11)
    snaps = {}
    for i in range(5):
        d = today - timedelta(days=i)
        snaps[d] = _snapshot(
            d,
            [
                _student(
                    "Alice",
                    "Coach Bob",
                    [_subj("Math", 30, 30, status="on_track")],
                )
            ],
        )
    _patch_read_range(monkeypatch, snaps)
    payload = dv2.build_digest_v2(today)
    assert "Alice" in payload.per_student
    s = payload.per_student["Alice"]
    assert s.concerns == []
    assert s.severity == 0.0


def test_student_behind_multiple_days_is_flagged(monkeypatch):
    today = date(2026, 5, 11)
    snaps = {}
    for i in range(5):
        d = today - timedelta(days=i)
        snaps[d] = _snapshot(
            d,
            [
                _student(
                    "Bob",
                    "Coach Carol",
                    [_subj("Math", 30, 5, status="behind")],
                )
            ],
        )
    _patch_read_range(monkeypatch, snaps)
    payload = dv2.build_digest_v2(today)
    s = payload.per_student["Bob"]
    assert dv2.CONCERN_BEHIND_MULTIPLE_DAYS in s.concerns
    assert s.severity > 0


def test_top_concerns_sorted_and_capped(monkeypatch):
    today = date(2026, 5, 11)
    students = [
        _student(
            f"Student{i}",
            "Coach X",
            [_subj("Math", 30, 0, status="behind")],
        )
        for i in range(10)
    ]
    snaps = {}
    for i in range(5):
        d = today - timedelta(days=i)
        snaps[d] = _snapshot(d, students)
    _patch_read_range(monkeypatch, snaps)
    payload = dv2.build_digest_v2(today)
    assert len(payload.top_concerns) <= dv2.TOP_CONCERNS_N


def test_coach_trend_cluster_threshold(monkeypatch):
    """Two+ students under the same coach with the same concern -> cluster."""
    today = date(2026, 5, 11)
    students = [
        _student(
            "Alpha",
            "Coach Z",
            [_subj("Math", 30, 0, status="behind")],
        ),
        _student(
            "Beta",
            "Coach Z",
            [_subj("Math", 30, 0, status="behind")],
        ),
    ]
    snaps = {}
    for i in range(5):
        d = today - timedelta(days=i)
        snaps[d] = _snapshot(d, students)
    _patch_read_range(monkeypatch, snaps)
    payload = dv2.build_digest_v2(today)
    coach_z = payload.per_coach.get("Coach Z")
    assert coach_z is not None
    # Cluster appears because COACH_TREND_THRESHOLD = 2.
    assert any(
        len(v) >= dv2.COACH_TREND_THRESHOLD
        for v in coach_z.trend_clusters.values()
    )


def test_window_constants_per_q4_decisions():
    assert dv2.CURRENT_WINDOW_DAYS == 5
    assert dv2.PRIOR_WINDOW_DAYS == 5
    assert dv2.TOP_CONCERNS_N == 5
    assert dv2.COACH_TREND_THRESHOLD == 2
