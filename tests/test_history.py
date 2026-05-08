import json
import tempfile
from datetime import date
from pathlib import Path

from src.history import (
    DailySnapshot,
    StudentSnap,
    StudentSubjectSnap,
    build_snapshot_from_report,
    list_dates,
    read_range,
    read_recent,
    read_snapshot,
    write_snapshot,
)


def _tmp_dir() -> Path:
    return Path(tempfile.mkdtemp(prefix="history_test_"))


def _make_snap(iso: str) -> DailySnapshot:
    return DailySnapshot(
        date=iso,
        session={"sy": "26-27", "n": 1, "label": "SY26-27 S1"},
        generated_at="2026-09-15T13:00:00+00:00",
        stale=False,
        students=[
            StudentSnap(
                name="Marcus Allen",
                coach="Lisa C Willis",
                grade=4,
                age_grade=4,
                subjects={
                    "Math": StudentSubjectSnap(target=30, actual=27, tier="personalized_base", status="behind"),
                    "Reading": StudentSubjectSnap(target=25, actual=31, tier="locked_base", status="ahead"),
                },
            )
        ],
    )


def test_write_and_read_roundtrip():
    d = _tmp_dir()
    snap = _make_snap("2026-09-15")
    out = write_snapshot(snap, history_dir=d)
    assert out.exists()
    raw = read_snapshot("2026-09-15", history_dir=d)
    assert raw is not None
    assert raw["date"] == "2026-09-15"
    assert raw["session"]["label"] == "SY26-27 S1"
    assert raw["students"][0]["subjects"]["Math"]["target"] == 30
    assert raw["students"][0]["subjects"]["Math"]["status"] == "behind"


def test_read_snapshot_missing_returns_none():
    d = _tmp_dir()
    assert read_snapshot("2099-01-01", history_dir=d) is None


def test_read_range_inclusive_and_ordered():
    d = _tmp_dir()
    for iso in ["2026-09-13", "2026-09-14", "2026-09-15", "2026-09-16"]:
        write_snapshot(_make_snap(iso), history_dir=d)
    out = read_range("2026-09-14", "2026-09-15", history_dir=d)
    assert [r["date"] for r in out] == ["2026-09-14", "2026-09-15"]


def test_read_range_handles_reversed_args():
    d = _tmp_dir()
    write_snapshot(_make_snap("2026-09-14"), history_dir=d)
    write_snapshot(_make_snap("2026-09-15"), history_dir=d)
    out = read_range("2026-09-15", "2026-09-14", history_dir=d)
    assert [r["date"] for r in out] == ["2026-09-14", "2026-09-15"]


def test_read_recent_returns_last_n_calendar_days():
    d = _tmp_dir()
    for iso in ["2026-09-10", "2026-09-12", "2026-09-15"]:
        write_snapshot(_make_snap(iso), history_dir=d)
    out = read_recent(n_days=4, today=date(2026, 9, 15), history_dir=d)
    # Window is 2026-09-12 .. 2026-09-15 -> two snapshots fall in
    dates_in = {r["date"] for r in out}
    assert dates_in == {"2026-09-12", "2026-09-15"}


def test_list_dates_oldest_first():
    d = _tmp_dir()
    for iso in ["2026-09-15", "2026-09-13", "2026-09-14"]:
        write_snapshot(_make_snap(iso), history_dir=d)
    assert list_dates(history_dir=d) == ["2026-09-13", "2026-09-14", "2026-09-15"]


def test_build_snapshot_from_report_tolerates_missing_fields():
    payload = {
        "students": [
            {
                "name": "Test Kid",
                "coach": "Test Coach",
                "subjects": {
                    "Math": {"target": 25},  # no actual, no tier, no status
                },
            }
        ]
    }
    snap = build_snapshot_from_report("2026-09-15", payload, stale=False)
    assert snap.date == "2026-09-15"
    assert len(snap.students) == 1
    sub = snap.students[0].subjects["Math"]
    assert sub.target == 25
    assert sub.actual == 0
    assert sub.tier == "unknown"
    assert sub.status == "unknown"


def test_build_snapshot_session_field_populated_for_known_date():
    snap = build_snapshot_from_report("2026-09-15", {"students": []}, stale=False)
    # 2026-09-15 falls inside SY26-27 S1
    assert snap.session is not None
    assert snap.session["sy"] == "26-27"
    assert snap.session["n"] == 1


def test_build_snapshot_session_field_none_in_break():
    # Between S1 end (Oct 2) and S2 start (Oct 12)
    snap = build_snapshot_from_report("2026-10-06", {"students": []}, stale=False)
    assert snap.session is None
