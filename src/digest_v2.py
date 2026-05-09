"""Phase 4 Part 1 — Head-coach digest v2 (pure-functional aggregator).

Reads Phase-1 daily snapshots (data/history/YYYY-MM-DD.json) and computes
the structured payload the head-coach digest renderer (Part 2) will format.

Locked design (per user Q4 picks):
  Q4-1  Cadence:        Monday 7am CT (handled in workflow, not here).
  Q4-2  Trend window:   current = last 5 school days; prior = the 5
                          school days immediately before that.
  Q4-3  Concern score:  recurrence_count * magnitude_z, where
                          magnitude_z is how many stdevs below the
                          school-wide median the student's deficit is.
                          Higher score = bigger concern.
  Q4-4  Coach trend:    fires when >= 2 of a coach's students share
                          the same concern category in the current
                          window, regardless of roster size.
  Q4-5  Nudges:         delivered to coach DM only (handled in Part 5).

This module does NOT call Slack and does NOT render text. It only:
  - loads the history window
  - computes per-student / per-coach metrics
  - scores concerns and detects coach-level trend clusters

The renderer in Part 2 takes a DigestV2Payload and produces Slack
markdown. The poster in Part 3 sends it to the head coach.
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .history import read_range, HISTORY_DIR


# ---------------------------------------------------------------------------
# Constants (tunable, locked per Q4 picks)
# ---------------------------------------------------------------------------

CURRENT_WINDOW_DAYS = 5     # school days, but we sample by calendar days
PRIOR_WINDOW_DAYS = 5       # ditto
TOP_CONCERNS_N = 5
COACH_TREND_THRESHOLD = 2   # Q4-4

# Concern categories (used for both per-student tagging and coach-trend
# detection). Strings are kept stable so Part 2 / Part 5 can switch on them.
CONCERN_BEHIND_MULTIPLE_DAYS = "behind_multiple_days"
CONCERN_DEEP_DEFICIT = "deep_deficit"
CONCERN_GAP_NOT_CLOSING = "gap_not_closing"
CONCERN_FREQUENT_EXCEPTIONS = "frequent_exceptions"


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class StudentMetrics:
    name: str
    coach: str
    # Aggregates across the current window.
    days_present: int = 0
    target_total: float = 0.0
    actual_total: float = 0.0
    deficit_total: float = 0.0          # sum(max(target - actual, 0))
    days_behind: int = 0                # count of subject-days with status=="behind"
    exceptions_active: int = 0          # count of subject-days with tier=="coach_xp_override" or tier=="coach_test_by"
    # Delta vs prior window (same shape, prior 5 days). None if no prior data.
    prior_deficit_total: Optional[float] = None
    deficit_delta: Optional[float] = None       # current - prior (positive = worse)
    # Categorized concerns (subset of CONCERN_* constants).
    concerns: List[str] = field(default_factory=list)
    # Severity score (Q4-3); 0.0 if no concerns.
    severity: float = 0.0


@dataclass
class CoachRollup:
    name: str
    n_students: int = 0
    students_behind: int = 0          # count with at least 1 day behind in window
    avg_deficit_per_student: float = 0.0
    # Coach-level trend clusters: concern_category -> list of student names
    # who share that concern. Only categories with >= COACH_TREND_THRESHOLD
    # entries are reported.
    trend_clusters: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class DigestV2Payload:
    today: str                          # ISO date the digest was built for
    current_window: Tuple[str, str]     # (start_iso, end_iso) inclusive
    prior_window: Optional[Tuple[str, str]]
    session_label: Optional[str]
    per_student: Dict[str, StudentMetrics] = field(default_factory=dict)
    per_coach: Dict[str, CoachRollup] = field(default_factory=dict)
    top_concerns: List[StudentMetrics] = field(default_factory=list)
    coach_trend_clusters: List[Tuple[str, str, List[str]]] = field(default_factory=list)
    # ^ list of (coach_name, concern_category, [student_names])
    days_in_current_window: int = 0
    days_in_prior_window: int = 0


# ---------------------------------------------------------------------------
# Window arithmetic
# ---------------------------------------------------------------------------


def compute_windows(
    today_iso: str,
    current_days: int = CURRENT_WINDOW_DAYS,
    prior_days: int = PRIOR_WINDOW_DAYS,
) -> Tuple[Tuple[str, str], Tuple[str, str]]:
    """Return (current_window, prior_window) as inclusive ISO ranges.

    Uses calendar days for boundaries and lets read_range() filter to
    actual snapshot files (so weekends/holidays without snapshots are
    naturally skipped).
    """
    today = date.fromisoformat(today_iso)
    cur_end = today - timedelta(days=1)             # yesterday inclusive
    cur_start = cur_end - timedelta(days=current_days - 1)
    prior_end = cur_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=prior_days - 1)
    return (
        (cur_start.isoformat(), cur_end.isoformat()),
        (prior_start.isoformat(), prior_end.isoformat()),
    )


# ---------------------------------------------------------------------------
# Per-student metrics
# ---------------------------------------------------------------------------


def _aggregate_student_window(
    snapshots: List[Dict[str, Any]],
    student_name: str,
) -> Tuple[int, float, float, float, int, int, str]:
    """Return (days_present, target_total, actual_total, deficit_total,
    days_behind, exceptions_active, coach_name)."""
    days_present = 0
    target_total = 0.0
    actual_total = 0.0
    deficit_total = 0.0
    days_behind = 0
    exceptions_active = 0
    coach_name = ""
    for snap in snapshots:
        for s in snap.get("students") or []:
            if s.get("name") != student_name:
                continue
            days_present += 1
            coach_name = s.get("coach") or coach_name
            for subj_name, subj in (s.get("subjects") or {}).items():
                t = float(subj.get("target") or 0.0)
                a = float(subj.get("actual") or 0.0)
                target_total += t
                actual_total += a
                if t > a:
                    deficit_total += (t - a)
                if (subj.get("status") or "") == "behind":
                    days_behind += 1
                tier = subj.get("tier") or ""
                if tier in ("coach_xp_override", "coach_test_by"):
                    exceptions_active += 1
    return (
        days_present, target_total, actual_total, deficit_total,
        days_behind, exceptions_active, coach_name,
    )


def compute_student_metrics(
    student_name: str,
    current_snapshots: List[Dict[str, Any]],
    prior_snapshots: List[Dict[str, Any]],
) -> StudentMetrics:
    cur = _aggregate_student_window(current_snapshots, student_name)
    days_present, target_total, actual_total, deficit_total, days_behind, exc, coach = cur
    pri = _aggregate_student_window(prior_snapshots, student_name)
    prior_deficit = pri[3] if pri[0] > 0 else None
    delta = (deficit_total - prior_deficit) if prior_deficit is not None else None
    return StudentMetrics(
        name=student_name,
        coach=coach,
        days_present=days_present,
        target_total=target_total,
        actual_total=actual_total,
        deficit_total=deficit_total,
        days_behind=days_behind,
        exceptions_active=exc,
        prior_deficit_total=prior_deficit,
        deficit_delta=delta,
    )


# ---------------------------------------------------------------------------
# Concern categorization (deterministic; thresholds are conservative)
# ---------------------------------------------------------------------------


def categorize_concerns(m: StudentMetrics) -> List[str]:
    """Tag a student with zero or more CONCERN_* categories."""
    out: List[str] = []
    if m.days_behind >= 3:
        out.append(CONCERN_BEHIND_MULTIPLE_DAYS)
    if m.target_total > 0 and (m.deficit_total / m.target_total) >= 0.30:
        out.append(CONCERN_DEEP_DEFICIT)
    if m.deficit_delta is not None and m.deficit_delta > 0:
        # Deficit grew vs prior window.
        out.append(CONCERN_GAP_NOT_CLOSING)
    if m.exceptions_active >= 2:
        out.append(CONCERN_FREQUENT_EXCEPTIONS)
    return out


# ---------------------------------------------------------------------------
# Severity scoring (Q4-3)
# ---------------------------------------------------------------------------


def score_severity(
    m: StudentMetrics,
    school_median_deficit: float,
    school_stdev_deficit: float,
) -> float:
    """severity = recurrence_count * magnitude_z.

    recurrence_count = number of CONCERN_* tags this student carries.
    magnitude_z = max(0, (deficit - median) / stdev). Clamped at 0 so
    students at-or-above the median never score.
    """
    if not m.concerns:
        return 0.0
    if school_stdev_deficit <= 0:
        # Degenerate: everybody same. Use deficit ratio as a soft proxy.
        if school_median_deficit <= 0:
            return float(len(m.concerns))
        z = max(0.0, (m.deficit_total - school_median_deficit) / school_median_deficit)
    else:
        z = max(0.0, (m.deficit_total - school_median_deficit) / school_stdev_deficit)
    return float(len(m.concerns)) * z


# ---------------------------------------------------------------------------
# Coach roll-up + trend cluster detection (Q4-4)
# ---------------------------------------------------------------------------


def build_coach_rollups(
    per_student: Dict[str, StudentMetrics],
    threshold: int = COACH_TREND_THRESHOLD,
) -> Dict[str, CoachRollup]:
    """Group per-student metrics by coach, compute roll-ups, and detect
    concern clusters where >= threshold of a coach's students share a
    concern category."""
    by_coach: Dict[str, CoachRollup] = {}
    for m in per_student.values():
        if not m.coach:
            continue
        roll = by_coach.setdefault(m.coach, CoachRollup(name=m.coach))
        roll.n_students += 1
        if m.days_behind > 0:
            roll.students_behind += 1
    # Average deficit per student.
    for coach_name, roll in by_coach.items():
        if roll.n_students == 0:
            continue
        total_def = sum(
            m.deficit_total for m in per_student.values() if m.coach == coach_name
        )
        roll.avg_deficit_per_student = total_def / roll.n_students
    # Trend clusters: by (coach, concern_category).
    cluster_acc: Dict[Tuple[str, str], List[str]] = {}
    for m in per_student.values():
        if not m.coach:
            continue
        for c in m.concerns:
            cluster_acc.setdefault((m.coach, c), []).append(m.name)
    for (coach_name, concern), names in cluster_acc.items():
        if len(names) >= threshold:
            by_coach[coach_name].trend_clusters[concern] = sorted(names)
    return by_coach


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def build_digest(
    today_iso: str,
    *,
    history_dir: Optional[Path] = None,
    student_names: Optional[List[str]] = None,
    session_label: Optional[str] = None,
) -> DigestV2Payload:
    """Build the complete head-coach digest payload for `today_iso`.

    Args:
      today_iso:       The day the digest is being generated (typically
                         Monday, but this function is calendar-agnostic).
      history_dir:     Optional override; defaults to data/history/.
      student_names:   Optional restrict-to list. If None, every student
                         seen in the current window is included.
      session_label:   Optional pre-resolved session label for the header.
                         If None, taken from the most recent snapshot.
    """
    cur_window, prior_window = compute_windows(today_iso)
    cur_snaps = read_range(cur_window[0], cur_window[1], history_dir=history_dir)
    pri_snaps = read_range(prior_window[0], prior_window[1], history_dir=history_dir)

    if not cur_snaps:
        return DigestV2Payload(
            today=today_iso,
            current_window=cur_window,
            prior_window=prior_window,
            session_label=session_label,
            days_in_current_window=0,
            days_in_prior_window=len(pri_snaps),
        )

    # Discover student set if caller did not provide one.
    if student_names is None:
        seen: Dict[str, None] = {}
        for snap in cur_snaps:
            for s in snap.get("students") or []:
                nm = s.get("name")
                if nm:
                    seen.setdefault(nm, None)
        student_names = list(seen.keys())

    per_student: Dict[str, StudentMetrics] = {}
    for name in student_names:
        m = compute_student_metrics(name, cur_snaps, pri_snaps)
        m.concerns = categorize_concerns(m)
        per_student[name] = m

    # School-wide stats for severity scoring.
    deficits = [m.deficit_total for m in per_student.values() if m.days_present > 0]
    if deficits:
        median_def = statistics.median(deficits)
        stdev_def = statistics.pstdev(deficits) if len(deficits) > 1 else 0.0
    else:
        median_def, stdev_def = 0.0, 0.0
    for m in per_student.values():
        m.severity = score_severity(m, median_def, stdev_def)

    # Top concerns (highest severity first; tie-break by deficit_total then name).
    top = sorted(
        [m for m in per_student.values() if m.concerns],
        key=lambda x: (-x.severity, -x.deficit_total, x.name),
    )[:TOP_CONCERNS_N]

    coach_rollups = build_coach_rollups(per_student, threshold=COACH_TREND_THRESHOLD)
    cluster_list: List[Tuple[str, str, List[str]]] = []
    for coach_name, roll in coach_rollups.items():
        for concern, names in roll.trend_clusters.items():
            cluster_list.append((coach_name, concern, names))
    # Stable ordering: coach name, then concern category.
    cluster_list.sort(key=lambda t: (t[0], t[1]))

    # Resolve session label from the most recent snapshot if not provided.
    if session_label is None:
        last = cur_snaps[-1]
        sess = last.get("session") or {}
        session_label = sess.get("label") if isinstance(sess, dict) else None

    return DigestV2Payload(
        today=today_iso,
        current_window=cur_window,
        prior_window=prior_window,
        session_label=session_label,
        per_student=per_student,
        per_coach=coach_rollups,
        top_concerns=top,
        coach_trend_clusters=cluster_list,
        days_in_current_window=len(cur_snaps),
        days_in_prior_window=len(pri_snaps),
    )
