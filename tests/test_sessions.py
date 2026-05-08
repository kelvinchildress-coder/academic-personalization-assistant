from datetime import date

from src.sessions import (
    Session,
    auth_allowed_domains,
    current_session,
    load_sessions,
    next_session,
    session_for_date,
    session_just_ended,
    tracked_sessions,
)


def test_load_sessions_returns_all_years():
    sessions = load_sessions()
    sy_set = {s.sy for s in sessions}
    assert "25-26" in sy_set
    assert "26-27" in sy_set
    # 5 sessions per year, 2 years = 10 total
    assert len(sessions) == 10


def test_sy_25_26_s1_through_s4_are_untracked():
    sessions = load_sessions()
    untracked = [s for s in sessions if s.sy == "25-26" and s.n in (1, 2, 3, 4)]
    assert len(untracked) == 4
    for s in untracked:
        assert not s.tracked
        assert s.start is None
        assert s.end is None


def test_sy_25_26_s5_is_tracked_with_end_jun_5():
    sessions = load_sessions()
    s5 = [s for s in sessions if s.sy == "25-26" and s.n == 5][0]
    assert s5.tracked
    assert s5.end == date(2026, 6, 5)


def test_sy_26_27_all_five_tracked_with_correct_dates():
    sessions = load_sessions()
    by_n = {s.n: s for s in sessions if s.sy == "26-27"}
    assert by_n[1].start == date(2026, 8, 12) and by_n[1].end == date(2026, 10, 2)
    assert by_n[2].start == date(2026, 10, 12) and by_n[2].end == date(2026, 12, 18)
    assert by_n[3].start == date(2027, 1, 4) and by_n[3].end == date(2027, 2, 19)
    assert by_n[4].start == date(2027, 3, 1) and by_n[4].end == date(2027, 4, 16)
    assert by_n[5].start == date(2027, 4, 26) and by_n[5].end == date(2027, 6, 4)
    for s in by_n.values():
        assert s.tracked


def test_session_for_date_inside_window():
    s = session_for_date(date(2026, 9, 15))
    assert s is not None
    assert s.sy == "26-27" and s.n == 1


def test_session_for_date_in_break_returns_none():
    # Between SY26-27 S1 (ends Oct 2) and S2 (starts Oct 12)
    assert session_for_date(date(2026, 10, 6)) is None


def test_session_just_ended_day_after_session_end():
    s = session_just_ended(today=date(2026, 10, 3))
    assert s is not None
    assert s.sy == "26-27" and s.n == 1


def test_session_just_ended_outside_7_day_window_returns_none():
    s = session_just_ended(today=date(2026, 11, 1))
    assert s is None


def test_next_session_returns_correct_upcoming():
    s = next_session(after=date(2026, 10, 5))
    assert s is not None
    assert s.sy == "26-27" and s.n == 2


def test_tracked_sessions_excludes_untracked():
    tracked = tracked_sessions()
    # 1 (S5 of 25-26) + 5 (all of 26-27) = 6
    assert len(tracked) == 6
    for s in tracked:
        assert s.start is not None and s.end is not None


def test_auth_allowed_domains_loaded():
    domains = auth_allowed_domains()
    assert "sportsacademy.school" in domains
    assert "alpha.school" in domains
    assert "2hourlearning.com" in domains
    # Lowercase, no @ prefix
    for d in domains:
        assert d == d.lower()
        assert not d.startswith("@")
