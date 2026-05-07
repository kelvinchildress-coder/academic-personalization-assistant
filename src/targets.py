"""
targets.py
==========

Resolves the daily XP target for each (student, subject) on a given school
day using the locked 4-tier priority cascade (with absolute coach
overrides at Tier 0). Cites the winning tier so report_builder can show
the user *why* a target is what it is.

Cascade (highest priority wins):

  Tier 0a  Coach absolute XP/day override
           student.overrides.xp_per_day[subject]  (or legacy
           manual_xp_per_day[subject])
           -> use exactly that XP/day. Bypasses everything below.

  Tier 0b  Coach absolute test-by override
           student.overrides.test_by[subject] = {target_grade, target_date}
           (or legacy manual_test_out_grade / manual_test_out_date)
           -> drives a Tier-1-style calculation but with coach-chosen
           grade/date.

  Tier 1   Grade-mastered XP/day (auto)
           remaining_xp_to_target_grade / school_days_until_target_date
           target_date defaults to next MAP after today.
           target_grade defaults per Q2 (year-start anchored).
           Skipped if remaining_xp or schools_days unknown.

  Tier 2   Adjusted coach XP/day (RESERVED — not used in v1)
           Stub kept so the priority order stays stable.

  Tier 3   Personalized base XP/day
           locked_base + 2.5 * (age_grade - current_grade_in_subject)
           - Only adjusts: Math, Reading, Language, Writing, Science.
           - FastMath, Vocabulary always pass through to Tier 4.
           - Floor: 10 XP/day for any subject.

  Tier 4   Locked TSA base
           Math/Reading/Language: 25
           Writing/Science: 12.5
           FastMath/Vocabulary: 10
           Always available; the floor.

Public API:
  - resolve_daily_target(...) -> TargetResolution      (NEW; rich)
  - resolve_all_subjects(...) -> dict[str, TargetResolution]   (NEW)
  - all_subject_targets(student, today) -> dict[str, float]    (LEGACY,
        kept for report_builder.py backward compat; thin wrapper)
  - base_target(subject_name) -> float                          (LEGACY)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Dict, Optional

# Locked XP rules (TSA defaults, Tier 4). Kept here as a self-contained
# constant so this module remains importable even if models.py is absent
# in some test environments.
LOCKED_BASE_XP: Dict[str, float] = {
    "Math": 25.0,
    "Reading": 25.0,
    "Language": 25.0,
    "Writing": 12.5,
    "Science": 12.5,
    "Vocabulary": 10.0,
    "FastMath": 10.0,
}

PERSONALIZED_FLOOR_XP = 10.0
PERSONALIZED_PER_GRADE_DELTA = 2.5
PERSONALIZED_SUBJECTS = frozenset({
    "Math", "Reading", "Language", "Writing", "Science",
})

# Backward-compat: some legacy callers import LOCKED_XP_RULES from
# .models. Re-export equivalent here for test isolation.
LOCKED_XP_RULES = dict(LOCKED_BASE_XP)


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TargetResolution:
    """The resolved daily XP target for one (student, subject) pair."""
    student: str
    subject: str
    xp_per_day: float
    tier: int                     # 0..4
    source_label: str             # short tag, e.g. "tier1_grade_mastered"
    target_grade: Optional[int]
    target_date: Optional[date]
    detail: str                   # human-readable explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "student": self.student,
            "subject": self.subject,
            "xp_per_day": self.xp_per_day,
            "tier": self.tier,
            "source_label": self.source_label,
            "target_grade": self.target_grade,
            "target_date": self.target_date.isoformat() if self.target_date else None,
            "detail": self.detail,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _floor(xp: float) -> float:
    return max(PERSONALIZED_FLOOR_XP, float(xp))


def base_target(subject_name: str) -> float:
    """Tier 4 — locked base. Returns 0.0 for unknown subjects to mirror
    legacy behavior (caller decides what to do with 0)."""
    return float(LOCKED_BASE_XP.get(subject_name, 0.0))


def _personalized_base(
    *, subject: str, age_grade: Optional[int], current_grade: Optional[int]
) -> Optional[float]:
    """
    Tier 3. Returns None when not applicable (subject not in
    PERSONALIZED_SUBJECTS, or grades unknown). Floored at 10 XP.
    """
    if subject not in PERSONALIZED_SUBJECTS:
        return None
    if age_grade is None or current_grade is None:
        return None
    base = LOCKED_BASE_XP.get(subject)
    if base is None:
        return None
    adjusted = base + PERSONALIZED_PER_GRADE_DELTA * (int(age_grade) - int(current_grade))
    return _floor(adjusted)


def _school_days_until(
    target_date: date,
    today: date,
    *,
    map_calendar_path: Optional[Path] = None,
) -> Optional[int]:
    """
    Count remaining school days strictly between today (exclusive) and
    target_date (inclusive). Uses src.calendar_map if MAP/holiday data is
    present; falls back to src.calendar_tsa otherwise.
    """
    if target_date <= today:
        return None
    # Try the new MAP-aware calendar first.
    try:
        from .calendar_map import school_days_between  # type: ignore
        try:
            return int(school_days_between(today, target_date, calendar_path=map_calendar_path))
        except TypeError:
            return int(school_days_between(today, target_date))
    except Exception:
        pass
    # Fallback to the original TSA calendar.
    try:
        from .calendar_tsa import school_days_remaining  # type: ignore
        return int(school_days_remaining(today, target_date))
    except Exception:
        return None


def _next_map_after(
    today: date, *, map_calendar_path: Optional[Path] = None
) -> Optional[date]:
    try:
        from .calendar_map import next_map_after  # type: ignore
        try:
            return next_map_after(today, calendar_path=map_calendar_path)
        except TypeError:
            return next_map_after(today)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Cascade
# ---------------------------------------------------------------------------


def _read_override_xp(profile: Dict[str, Any], subject: str) -> Optional[float]:
    """Tier 0a: explicit coach XP/day override."""
    overrides = profile.get("overrides") or {}
    xp_map = overrides.get("xp_per_day") or profile.get("manual_xp_per_day") or {}
    val = xp_map.get(subject)
    if val is None:
        return None
    try:
        return float(val)
    except (TypeError, ValueError):
        return None


def _read_override_testby(
    profile: Dict[str, Any], subject: str
) -> tuple[Optional[int], Optional[date]]:
    """Tier 0b: coach test-by override (target_grade, target_date)."""
    overrides = profile.get("overrides") or {}
    tb_map = overrides.get("test_by") or {}
    grade_map = profile.get("manual_test_out_grade") or {}
    date_map = profile.get("manual_test_out_date") or {}

    grade: Optional[int] = None
    when: Optional[date] = None

    if subject in tb_map and isinstance(tb_map[subject], dict):
        g = tb_map[subject].get("target_grade")
        d = tb_map[subject].get("target_date")
        if g is not None:
            try:
                grade = int(g)
            except (TypeError, ValueError):
                grade = None
        if d:
            try:
                when = date.fromisoformat(str(d))
            except ValueError:
                when = None

    # Legacy fallback maps.
    if grade is None and grade_map.get(subject) is not None:
        try:
            grade = int(grade_map[subject])
        except (TypeError, ValueError):
            pass
    if when is None and date_map.get(subject):
        try:
            when = date.fromisoformat(str(date_map[subject]))
        except ValueError:
            pass

    return grade, when


def resolve_daily_target(
    *,
    student_name: str,
    subject: str,
    today: date,
    student_profile: Dict[str, Any],
    grade_xp_table: Optional[Dict[int, Dict[str, Optional[float]]]] = None,
    cumulative_xp_in_current_grade: Optional[float] = None,
    map_calendar_path: Optional[Path] = None,
) -> TargetResolution:
    """
    Walk the cascade for one (student, subject) and return the resolved
    daily XP target with full provenance.

    Args:
      student_name: display name (already normalized).
      subject: canonical subject name.
      today: school day to resolve for.
      student_profile: the per-student dict from config/students.json,
          extended with optional 'overrides.xp_per_day' and
          'overrides.test_by' maps.
      grade_xp_table: { grade_int: { subject: total_xp_or_none } }
          from config/grade_xp.json. Tier 1 needs this; if missing or
          null for the lookup, Tier 1 is skipped.
      cumulative_xp_in_current_grade: how many XP the student has
          accumulated within their current grade. Until the TimeBack
          API is wired (Step I), this will typically be None and Tier 1
          will be skipped.
      map_calendar_path: optional override path for MAP calendar JSON.

    Returns:
      TargetResolution.
    """
    # ---- Tier 0a ----------------------------------------------------------
    override_xp = _read_override_xp(student_profile, subject)
    if override_xp is not None:
        return TargetResolution(
            student=student_name,
            subject=subject,
            xp_per_day=float(override_xp),
            tier=0,
            source_label="tier0a_coach_xp_override",
            target_grade=None,
            target_date=None,
            detail=(
                f"Coach absolute XP/day override: "
                f"{override_xp:g} XP/day for {subject}."
            ),
        )

    age_grade = student_profile.get("age_grade")
    cur_per_sub = student_profile.get("current_grade_per_subject") or {}
    ys_per_sub = student_profile.get("year_start_grade_per_subject") or {}
    current_grade = cur_per_sub.get(subject)
    year_start_grade = ys_per_sub.get(subject)

    # ---- Tier 0b / Tier 1 (both share grade-mastered math) ---------------
    override_grade, override_date = _read_override_testby(student_profile, subject)

    # Resolve the *effective* target_grade via test_out_goals so Q2 default
    # (year-start anchored) applies cleanly when no override.
    try:
        from .test_out_goals import resolve_target_grade
    except ImportError:
        from test_out_goals import resolve_target_grade  # type: ignore

    target_resolution = resolve_target_grade(
        subject=subject,
        age_grade=age_grade,
        year_start_grade=year_start_grade,
        coach_override_grade=override_grade,
    )
    effective_target_grade = target_resolution.target_grade
    target_grade_source = target_resolution.source  # coach_override / default_q2 / non_graded

    # Effective target date: explicit override > next MAP.
    effective_target_date = override_date or _next_map_after(
        today, map_calendar_path=map_calendar_path
    )

    # Try grade-mastered math (Tier 0b uses it with coach grade/date;
    # Tier 1 uses it with default grade/date).
    if (
        effective_target_grade is not None
        and effective_target_date is not None
        and grade_xp_table is not None
        and cumulative_xp_in_current_grade is not None
    ):
        total_xp_at_target = grade_xp_table.get(int(effective_target_grade), {}).get(subject)
        if total_xp_at_target is not None:
            remaining = float(total_xp_at_target) - float(cumulative_xp_in_current_grade)
            remaining = max(0.0, remaining)
            sd = _school_days_until(
                effective_target_date, today, map_calendar_path=map_calendar_path
            )
            if sd is not None and sd > 0:
                xp_per_day = remaining / float(sd)
                if target_grade_source == "coach_override" or override_date is not None:
                    tier = 0
                    label = "tier0b_coach_test_by"
                    why = (
                        f"Coach test-by override: {remaining:.0f} XP remaining to "
                        f"grade {effective_target_grade} {subject} over {sd} school "
                        f"days -> {xp_per_day:.1f} XP/day."
                    )
                else:
                    tier = 1
                    label = "tier1_grade_mastered"
                    why = (
                        f"Grade-mastered: {remaining:.0f} XP remaining to grade "
                        f"{effective_target_grade} {subject} by next MAP "
                        f"{effective_target_date.isoformat()} over {sd} school "
                        f"days -> {xp_per_day:.1f} XP/day."
                    )
                return TargetResolution(
                    student=student_name,
                    subject=subject,
                    xp_per_day=float(xp_per_day),
                    tier=tier,
                    source_label=label,
                    target_grade=int(effective_target_grade),
                    target_date=effective_target_date,
                    detail=why,
                )

    # ---- Tier 2 (reserved) -----------------------------------------------
    # Intentionally not implemented in v1.

    # ---- Tier 3 ----------------------------------------------------------
    pb = _personalized_base(
        subject=subject, age_grade=age_grade, current_grade=current_grade
    )
    if pb is not None:
        return TargetResolution(
            student=student_name,
            subject=subject,
            xp_per_day=float(pb),
            tier=3,
            source_label="tier3_personalized_base",
            target_grade=effective_target_grade,
            target_date=effective_target_date,
            detail=(
                f"Personalized base: {LOCKED_BASE_XP[subject]:g} + 2.5 * "
                f"({age_grade} - {current_grade}) = {pb:g} XP/day "
                f"(floored at {PERSONALIZED_FLOOR_XP:g})."
            ),
        )

    # ---- Tier 4 ----------------------------------------------------------
    base = base_target(subject)
    return TargetResolution(
        student=student_name,
        subject=subject,
        xp_per_day=float(base),
        tier=4,
        source_label="tier4_locked_base",
        target_grade=effective_target_grade,
        target_date=effective_target_date,
        detail=f"Locked TSA base for {subject}: {base:g} XP/day.",
    )


def resolve_all_subjects(
    *,
    student_name: str,
    today: date,
    student_profile: Dict[str, Any],
    grade_xp_table: Optional[Dict[int, Dict[str, Optional[float]]]] = None,
    cumulative_xp_by_subject: Optional[Dict[str, float]] = None,
    subjects: Optional[tuple[str, ...]] = None,
    map_calendar_path: Optional[Path] = None,
) -> Dict[str, TargetResolution]:
    """Resolve the cascade for every subject in one call."""
    subj_iter = subjects or tuple(LOCKED_BASE_XP.keys())
    cum = cumulative_xp_by_subject or {}
    out: Dict[str, TargetResolution] = {}
    for s in subj_iter:
        out[s] = resolve_daily_target(
            student_name=student_name,
            subject=s,
            today=today,
            student_profile=student_profile,
            grade_xp_table=grade_xp_table,
            cumulative_xp_in_current_grade=cum.get(s),
            map_calendar_path=map_calendar_path,
        )
    return out


# ---------------------------------------------------------------------------
# Legacy facade (kept so report_builder.py keeps working unchanged)
# ---------------------------------------------------------------------------


def _profile_from_legacy_student(student: Any) -> Dict[str, Any]:
    """
    Convert the legacy `Student` model (from src.models) into the dict
    shape resolve_daily_target expects. Best-effort; tolerates missing
    fields.
    """
    profile: Dict[str, Any] = {}
    for attr in (
        "age_grade",
        "current_grade_per_subject",
        "year_start_grade_per_subject",
        "manual_test_out_grade",
        "manual_test_out_date",
        "manual_xp_per_day",
        "overrides",
    ):
        if hasattr(student, attr):
            profile[attr] = getattr(student, attr)
    return profile


def student_subject_target(
    student: Any, subject_name: str, today: date
) -> float:
    """Legacy single-subject API."""
    profile = _profile_from_legacy_student(student)
    name = getattr(student, "name", "") or ""
    res = resolve_daily_target(
        student_name=name,
        subject=subject_name,
        today=today,
        student_profile=profile,
    )
    return float(res.xp_per_day)


def all_subject_targets(student: Any, today: date) -> Dict[str, float]:
    """
    Legacy whole-student API used by report_builder.py. Returns just the
    XP/day numbers keyed by subject. New code should call
    resolve_all_subjects() to get full provenance.
    """
    profile = _profile_from_legacy_student(student)
    name = getattr(student, "name", "") or ""
    rich = resolve_all_subjects(
        student_name=name,
        today=today,
        student_profile=profile,
    )
    return {s: r.xp_per_day for s, r in rich.items()}
