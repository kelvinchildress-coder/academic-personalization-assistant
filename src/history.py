"""Daily history layer.

Writes a snapshot of each day's coach-facing report to
data/history/YYYY-MM-DD.json. Snapshots are the canonical record of
what the system thought about each student each day: cascade tier,
target XP per subject, actual XP earned, status flags, and the
session this date belongs to.

Trend analysis, end-of-session summaries, and the dashboard all read
from these snapshot files. The morning-report and EoD scripts each
call write_snapshot() on success.

File shape (data/history/2026-05-08.json):
{
  "date": "2026-05-08",
  "session": {"sy": "25-26", "n": 5, "label": "SY25-26 S5"},
  "generated_at": "2026-05-08T13:04:46+00:00",
  "stale": false,
  "students": [
    {
      "name": "Marcus Allen",
      "coach": "Lisa C Willis",
      "grade": 4,
      "age_grade": 4,
      "subjects": {
        "Math":     {"target": 30, "actual": 27, "tier": "personalized_base", "status": "behind"},
        "Reading":  {"target": 25, "actual": 31, "tier": "locked_base",       "status": "ahead"},
        ...
      }
    },
    ...
  ]
}
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .sessions import current_session

REPO_ROOT = Path(__file__).resolve().parent.parent
HISTORY_DIR = REPO_ROOT / "data" / "history"


@dataclass
class StudentSubjectSnap:
    target: float
    actual: float
    tier: str            # "coach_xp_override" | "coach_test_by" | "grade_mastered" | "personalized_base" | "locked_base"
    status: str          # "ahead" | "on_track" | "behind" | "unknown"


@dataclass
class StudentSnap:
    name: str
    coach: str
    grade: Optional[int] = None
    age_grade: Optional[int] = None
    subjects: Dict[str, StudentSubjectSnap] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "coach": self.coach,
            "grade": self.grade,
            "age_grade": self.age_grade,
            "subjects": {k: asdict(v) for k, v in self.subjects.items()},
        }


@dataclass
class DailySnapshot:
    date: str            # ISO YYYY-MM-DD
    session: Optional[Dict[str, Any]]   # {"sy", "n", "label"} or None for break/untracked
    generated_at: str    # ISO 8601 timestamp
    stale: bool
    students: List[StudentSnap] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date,
            "session": self.session,
            "generated_at": self.generated_at,
            "stale": self.stale,
            "students": [s.to_dict() for s in self.students],
        }


# ----------------------------------------------------------------------
# Writer
# ----------------------------------------------------------------------

def _session_for_iso(iso: str) -> Optional[Dict[str, Any]]:
    s = current_session(date.fromisoformat(iso))
    if s is None:
        return None
    return {"sy": s.sy, "n": s.n, "label": s.label}


def write_snapshot(snap: DailySnapshot, history_dir: Optional[Path] = None) -> Path:
    """Write `snap` to data/history/<date>.json. Creates the directory
    if it doesn't exist. Overwrites any existing file for that date
    (the latest run for a date is the source of truth)."""
    out_dir = history_dir or HISTORY_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / f"{snap.date}.json"
    out_path.write_text(json.dumps(snap.to_dict(), indent=2, sort_keys=False))
    return out_path


def build_snapshot_from_report(today_iso: str, report_payload: Dict[str, Any], stale: bool = False) -> DailySnapshot:
    """Translate a tier-aware report payload (the dict produced by
    src.report_builder.build_tiered_morning_payload) into a DailySnapshot.

    Tolerant of partial payloads: if a field is missing it's stored as
    None / 0 rather than raising. This lets snapshot writes succeed
    even when upstream data has gaps - we'd rather record the gap than
    lose the day.
    """
    students_out: List[StudentSnap] = []
    for student in report_payload.get("students", []) or []:
        subjects: Dict[str, StudentSubjectSnap] = {}
        for subj_name, subj_data in (student.get("subjects") or {}).items():
            subjects[subj_name] = StudentSubjectSnap(
                target=float(subj_data.get("target") or 0),
                actual=float(subj_data.get("actual") or 0),
                tier=str(subj_data.get("tier") or "unknown"),
                status=str(subj_data.get("status") or "unknown"),
            )
        students_out.append(StudentSnap(
            name=str(student.get("name") or ""),
            coach=str(student.get("coach") or ""),
            grade=student.get("grade"),
            age_grade=student.get("age_grade"),
            subjects=subjects,
        ))
    return DailySnapshot(
        date=today_iso,
        session=_session_for_iso(today_iso),
        generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        stale=stale,
        students=students_out,
    )


# ----------------------------------------------------------------------
# Reader
# ----------------------------------------------------------------------

def read_snapshot(iso: str, history_dir: Optional[Path] = None) -> Optional[Dict[str, Any]]:
    """Read a single day's snapshot. Returns None if absent."""
    d = history_dir or HISTORY_DIR
    p = d / f"{iso}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text())


def read_range(start_iso: str, end_iso: str, history_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """All snapshots whose date is in [start_iso, end_iso] inclusive,
    ordered oldest first. Missing days are skipped silently."""
    d = history_dir or HISTORY_DIR
    if not d.exists():
        return []
    out: List[Dict[str, Any]] = []
    start = date.fromisoformat(start_iso)
    end = date.fromisoformat(end_iso)
    if start > end:
        start, end = end, start
    for p in sorted(d.glob("*.json")):
        try:
            iso = p.stem
            day = date.fromisoformat(iso)
        except ValueError:
            continue
        if start <= day <= end:
            out.append(json.loads(p.read_text()))
    return out


def read_recent(n_days: int, today: Optional[date] = None,
                history_dir: Optional[Path] = None) -> List[Dict[str, Any]]:
    """Last `n_days` calendar days of snapshots (calendar, not school days),
    ordered oldest first. Useful for trend windows."""
    today = today or date.today()
    from datetime import timedelta
    start = today - timedelta(days=n_days - 1)
    return read_range(start.isoformat(), today.isoformat(), history_dir)


def list_dates(history_dir: Optional[Path] = None) -> List[str]:
    """All ISO dates we have snapshots for, oldest first."""
    d = history_dir or HISTORY_DIR
    if not d.exists():
        return []
    out = []
    for p in sorted(d.glob("*.json")):
        try:
            date.fromisoformat(p.stem)
            out.append(p.stem)
        except ValueError:
            continue
    return out
