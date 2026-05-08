"""
exceptions_modifier.py
======================

Phase-2 modifier that composes on top of `src.targets.resolve_daily_target`.

Reads a student's `exceptions` array (added by src/agent/intent_writer.py
on coach confirmation) and adjusts a TargetResolution accordingly:

  - PAUSE      Active pause window for `today` -> xp_per_day = 0.0 and the
               source_label becomes "exception_pause". Tier number is
               preserved on the resolution for provenance, but the label
               and detail make clear the pause overrode the cascade.

  - HALF       Active half_target window for `today`, ONLY applied when
               the cascade winner is Tier 3 (personalized base) or
               Tier 4 (locked base). Multiplies xp_per_day by 0.5 with
               floor PERSONALIZED_FLOOR_XP = 10.

If both a pause and a half_target are active for the same (student,
subject, today), pause wins.

Subject matching:
  - exception.subject == None  -> applies to ALL subjects (full-day pause)
  - exception.subject == X     -> applies only to subject X

Date matching:
  - exception.start <= today <= exception.end  (inclusive both ends)
  - Stored as ISO YYYY-MM-DD strings.

This module is deliberately a *thin wrapper*. It does NOT call into
targets.py or load students.json — callers do that and pass results in.
That keeps it trivially unit-testable and removes coupling.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .targets import PERSONALIZED_FLOOR_XP, TargetResolution


# ---------------------------------------------------------------------------
# Exception filtering
# ---------------------------------------------------------------------------


def _is_active(exc: Dict[str, Any], today: date) -> bool:
    """Return True if `today` falls within [start, end] inclusive."""
    try:
        start = date.fromisoformat(str(exc.get("start") or ""))
        end = date.fromisoformat(str(exc.get("end") or ""))
    except ValueError:
        return False
    return start <= today <= end


def _matches_subject(exc: Dict[str, Any], subject: str) -> bool:
    """Subject==None means 'all subjects' (full-day). Else exact match."""
    sub = exc.get("subject")
    if sub is None:
        return True
    return sub == subject


def _select_active(
    exceptions: List[Dict[str, Any]],
    *,
    subject: str,
    today: date,
) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Find the active pause and half_target (if any) for today/subject."""
    pause = None
    half = None
    for exc in exceptions or []:
        if not isinstance(exc, dict):
            continue
        if not _is_active(exc, today):
            continue
        if not _matches_subject(exc, subject):
            continue
        kind = exc.get("type")
        if kind == "pause" and pause is None:
            pause = exc
        elif kind == "half_target" and half is None:
            half = exc
    return pause, half


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_exceptions(
    resolution: TargetResolution,
    *,
    student_profile: Dict[str, Any],
    today: date,
) -> TargetResolution:
    """Return a (possibly modified) TargetResolution with exceptions applied.

    Original resolution is never mutated — a new TargetResolution is
    returned via dataclasses.replace().
    """
    exceptions = student_profile.get("exceptions") or []
    if not exceptions:
        return resolution

    pause, half = _select_active(
        exceptions,
        subject=resolution.subject,
        today=today,
    )

    # Pause wins outright.
    if pause is not None:
        coach = pause.get("source_coach", "?")
        end = pause.get("end", "?")
        return replace(
            resolution,
            xp_per_day=0.0,
            source_label="exception_pause",
            detail=(
                f"Pause active through {end} (set by {coach}); "
                f"target zeroed. Cascade would have produced "
                f"{resolution.xp_per_day:g} XP/day "
                f"({resolution.source_label})."
            ),
        )

    # Half target applies only when cascade winner is Tier 3 or Tier 4.
    if half is not None and resolution.tier in (3, 4):
        coach = half.get("source_coach", "?")
        end = half.get("end", "?")
        halved = max(PERSONALIZED_FLOOR_XP, resolution.xp_per_day * 0.5)
        return replace(
            resolution,
            xp_per_day=float(halved),
            source_label=f"{resolution.source_label}+half_target",
            detail=(
                f"Half target active through {end} (set by {coach}); "
                f"{resolution.xp_per_day:g} -> {halved:g} XP/day "
                f"(floor {PERSONALIZED_FLOOR_XP:g}). "
                f"Original cascade: {resolution.source_label}."
            ),
        )

    # Half target was present but cascade winner is Tier 0a/0b/1 — ignore
    # per locked design (Q3): half-modifier never touches coach overrides
    # or grade-mastered tiers.
    if half is not None and resolution.tier not in (3, 4):
        return replace(
            resolution,
            detail=(
                f"{resolution.detail} "
                f"[Half target requested but skipped — only applies to "
                f"Tiers 3/4; current winner is Tier {resolution.tier}.]"
            ),
        )

    return resolution


# ---------------------------------------------------------------------------
# Convenience: prune expired exceptions
# ---------------------------------------------------------------------------


def prune_expired(
    exceptions: List[Dict[str, Any]],
    *,
    today: date,
) -> Tuple[List[Dict[str, Any]], int]:
    """Drop exceptions whose end < today. Returns (kept_list, num_removed)."""
    kept: List[Dict[str, Any]] = []
    removed = 0
    for exc in exceptions or []:
        if not isinstance(exc, dict):
            continue
        try:
            end = date.fromisoformat(str(exc.get("end") or ""))
        except ValueError:
            kept.append(exc)
            continue
        if end < today:
            removed += 1
        else:
            kept.append(exc)
    return kept, removed
