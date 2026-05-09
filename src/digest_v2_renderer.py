"""Phase 4 Part 2 — Head-coach digest v2 renderer (pure-functional).

Takes a DigestV2Payload (built by src/digest_v2.py) and produces a Slack
mrkdwn-formatted string suitable for posting to a head-coach DM.

This module is pure: NO Slack API calls, NO network, NO file I/O. The
posting script in Part 3 is responsible for choosing the destination and
calling the Slack client.

Layout (top to bottom):
    1. Header — date, session label, window
    2. Top concerns — per-student, with concern tags + severity
    3. Per-coach roll-up — counts + trend clusters
    4. Footer — sample sizes (days in current/prior windows)
"""
from __future__ import annotations

from typing import List

from .digest_v2 import (
    CONCERN_BEHIND_MULTIPLE_DAYS,
    CONCERN_DEEP_DEFICIT,
    CONCERN_FREQUENT_EXCEPTIONS,
    CONCERN_GAP_NOT_CLOSING,
    CoachRollup,
    DigestV2Payload,
    StudentMetrics,
)

# ---------------------------------------------------------------------------
# Concern label map (human-readable, short).
# ---------------------------------------------------------------------------
_CONCERN_LABELS = {
    CONCERN_BEHIND_MULTIPLE_DAYS: "behind multiple days",
    CONCERN_DEEP_DEFICIT: "deep deficit",
    CONCERN_GAP_NOT_CLOSING: "gap not closing",
    CONCERN_FREQUENT_EXCEPTIONS: "frequent exceptions",
}


def _fmt_window(window) -> str:
    """Format a (start_iso, end_iso) tuple as 'start → end'."""
    if not window:
        return "n/a"
    start, end = window
    return f"{start} → {end}"


def _fmt_xp(value: float) -> str:
    """Format an XP number compactly (no decimals if whole)."""
    if value is None:
        return "n/a"
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}"
    return f"{value:.1f}"


def _fmt_delta(delta) -> str:
    """Format prior-window delta with sign and direction word."""
    if delta is None:
        return "no prior data"
    if abs(delta) < 0.5:
        return "flat vs prior 5"
    if delta > 0:
        return f"+{_fmt_xp(delta)} XP worse vs prior 5"
    return f"{_fmt_xp(abs(delta))} XP better vs prior 5"


def _concern_tags(concerns: List[str]) -> str:
    """Render concern codes as comma-separated human labels."""
    if not concerns:
        return ""
    return ", ".join(_CONCERN_LABELS.get(c, c) for c in concerns)


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------
def _render_header(payload: DigestV2Payload) -> List[str]:
    out: List[str] = []
    session = payload.session_label or "Session n/a"
    out.append(f"*Head Coach Digest — {payload.today}*")
    out.append(f"_{session}_")
    out.append(
        f"Current window: {_fmt_window(payload.current_window)}  "
        f"(prior: {_fmt_window(payload.prior_window)})"
    )
    return out


def _render_student_line(s: StudentMetrics) -> str:
    """One bullet for a top-concern student."""
    tags = _concern_tags(s.concerns)
    tag_part = f" — {tags}" if tags else ""
    severity_part = (
        f" _(severity {s.severity:.1f})_" if s.severity > 0 else ""
    )
    return (
        f"• *{s.name}* (coach {s.coach}){tag_part}{severity_part}\n"
        f"    deficit {_fmt_xp(s.deficit_total)} XP across {s.days_behind} "
        f"day(s); {_fmt_delta(s.deficit_delta)}; "
        f"{s.exceptions_active} exception(s) active"
    )


def _render_top_concerns(payload: DigestV2Payload) -> List[str]:
    out: List[str] = ["", "*Top concerns this week*"]
    if not payload.top_concerns:
        out.append("_No students flagged this week — all on track._")
        return out
    for s in payload.top_concerns:
        out.append(_render_student_line(s))
    return out


def _render_coach_rollup(coach: CoachRollup) -> List[str]:
    """Render one coach's roll-up block (header + trend clusters)."""
    out: List[str] = []
    behind_str = (
        f"{coach.students_behind}/{coach.n_students} students with days behind"
        if coach.n_students
        else "no students"
    )
    avg_str = (
        f"avg deficit {_fmt_xp(coach.avg_deficit_per_student)} XP/student"
        if coach.n_students
        else ""
    )
    suffix = f"; {avg_str}" if avg_str else ""
    out.append(f"• *{coach.name}* — {behind_str}{suffix}")
    if coach.trend_clusters:
        for category, names in coach.trend_clusters.items():
            label = _CONCERN_LABELS.get(category, category)
            joined = ", ".join(names)
            out.append(f"    ↳ trend: _{label}_ — {joined}")
    return out


def _render_per_coach(payload: DigestV2Payload) -> List[str]:
    out: List[str] = ["", "*Per-coach roll-up*"]
    if not payload.per_coach:
        out.append("_No coach data this week._")
        return out
    # Sort by students_behind desc, then avg_deficit desc, then name.
    coaches = sorted(
        payload.per_coach.values(),
        key=lambda c: (-c.students_behind, -c.avg_deficit_per_student, c.name),
    )
    for coach in coaches:
        out.extend(_render_coach_rollup(coach))
    return out


def _render_footer(payload: DigestV2Payload) -> List[str]:
    out: List[str] = [""]
    out.append(
        f"_Sample sizes: {payload.days_in_current_window} day(s) current, "
        f"{payload.days_in_prior_window} day(s) prior._"
    )
    return out


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def render_digest_v2(payload: DigestV2Payload) -> str:
    """Render a DigestV2Payload as Slack mrkdwn text.

    The output is a single string with newline-separated lines, ready to be
    passed as the `text` parameter to Slack's chat.postMessage. Bold uses
    `*x*` (Slack syntax, NOT `**x**`).
    """
    parts: List[str] = []
    parts.extend(_render_header(payload))
    parts.extend(_render_top_concerns(payload))
    parts.extend(_render_per_coach(payload))
    parts.extend(_render_footer(payload))
    return "\n".join(parts)
