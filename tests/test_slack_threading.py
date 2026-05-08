"""Tests for src.slack_threading state persistence."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from src.slack_threading import (
    ThreadState,
    is_state_for_today,
    load_state,
    record_live_events,
    reset_for_new_day,
    save_state,
)


def test_load_state_missing_file_returns_empty(tmp_path: Path):
    state = load_state(tmp_path / "missing.json")
    assert isinstance(state, ThreadState)
    assert state.parent_ts is None
    assert state.live_events_posted == []


def test_load_state_corrupt_file_returns_empty(tmp_path: Path):
    p = tmp_path / "bad.json"
    p.write_text("not json")
    state = load_state(p)
    assert state.parent_ts is None


def test_save_and_load_roundtrip(tmp_path: Path):
    p = tmp_path / "state.json"
    state = ThreadState(
        current_day="2026-05-08",
        parent_ts="1715000000.000100",
        channel="C012345",
        live_events_posted=["k1", "k2"],
    )
    save_state(p, state)
    loaded = load_state(p)
    assert loaded.current_day == "2026-05-08"
    assert loaded.parent_ts == "1715000000.000100"
    assert loaded.live_events_posted == ["k1", "k2"]


def test_is_state_for_today_requires_match_and_parent_ts():
    today = date(2026, 5, 8)
    s_today = ThreadState(current_day="2026-05-08", parent_ts="1.1", channel="C")
    s_yesterday = ThreadState(current_day="2026-05-07", parent_ts="1.1", channel="C")
    s_no_ts = ThreadState(current_day="2026-05-08", parent_ts=None, channel="C")
    assert is_state_for_today(s_today, today)
    assert not is_state_for_today(s_yesterday, today)
    assert not is_state_for_today(s_no_ts, today)


def test_reset_for_new_day_clears_events():
    today = date(2026, 5, 8)
    state = reset_for_new_day(today, "C012345", "1715000000.000100")
    assert state.current_day == "2026-05-08"
    assert state.parent_ts == "1715000000.000100"
    assert state.channel == "C012345"
    assert state.live_events_posted == []


def test_record_live_events_dedupes_and_sorts():
    state = ThreadState(live_events_posted=["b", "a"])
    state = record_live_events(state, ["c", "a", "b"])
    assert state.live_events_posted == ["a", "b", "c"]
