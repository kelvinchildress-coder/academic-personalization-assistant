"""Phase 4 Part 5 — Coach nudges (pure-functional).

Generates lightweight, coach-facing nudge messages from a DigestV2Payload.

Per Q4-5: nudges are sent to the COACH DM only (never to head coach,
never to public channels). The head-coach digest (Parts 1–4) is the
head coach's view; this module is the per-coach view.

PUBLIC ENTRY POINT
------------------
    build_coach_nudges(payload, coach_slack_ids) -> List[CoachNudge]

Each CoachNudge has:
    - coach_name      str
    - slack_user_id   str  (the U... ID for DM routing)
    - text            str  (Slack mrkdwn)

This module is pure: NO Slack API calls, NO network, NO file I/O. The
poster (a future part) takes the list and calls chat.postMessage per
coach.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .digest_v2 import (
    CONCERN_BEHIND_MULTIPLE_DAYS,
    CONCERN_DEEP_DEFICIT,
    CONCERN_FREQUENT_EXCEPTIONS,
    CONCERN_GAP_NOT_CLOSING,
    DigestV2Payload,
    StudentMetrics,
)

# ---------------------------------------------------------------------------
# Tunables. Kept small and explicit so they can be tuned without touching
# digest_v2 thresholds.
# ---------------------------------------------------------------------------
# Only nudge a coach if at least this many of their students have at least
# one concern. Below this, the head-coach digest is sufficient.
MIN_FLAGGED_STUDENTS_TO_NUDGE = 1

# Cap how many students we surface in a single nudge (keep it short).
MAX_STUDENTS_IN_NUDGE = 5

_CONCERN_LABELS = {
    CONCERN_BEHIND_MULTIPLE_DAYS: "behind multiple days",
    CONCERN_DEEP_DEFICIT: "deep deficit",
    CONCERN_GAP_NOT_CLOSING: "gap not closing",
    CONCERN_FREQUENT_EXCEPTIONS: "frequent exceptions",
}


@dataclass
class CoachNudge:
    coach_name: str
    slack_user_id: str
    text: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fmt_xp(value: float) -> str:
    if value is None:
        return "n/a"
    if abs(value - round(value)) < 0.05:
        return f"{int(round(value))}"
    return f"{value:.1f}"


def _concern_tag(concerns: List[str]) -> str:
    if not concerns:
        return ""
    return ", ".join(_CONCERN_LABELS.get(c, c) for c in concerns)


def _flagged_students_for_coach(
    payload: DigestV2Payload, coach_name: str
) -> List[StudentMetrics]:
    """Return the coach's students that have >=1 concern, sorted by severity desc."""
    out = [
        s
        for s in payload.per_student.values()
        if s.coach == coach_name and s.concerns
    ]
    out.sort(key=lambda s: (-s.severity, s.name))
    return out


def _render_nudge_text(
    coach_name: str,
    flagged: List[StudentMetrics],
    payload: DigestV2Payload,
) -> str:
    """Build the mrkdwn body for a single coach's nudge."""
    lines: List[str] = []
    n_total = len(flagged)
    shown = flagged[:MAX_STUDENTS_IN_NUDGE]

    lines.append(f"Hi {coach_name} — quick weekly check-in for {payload.today}.")
    if n_total == 1:
        lines.append("One student to keep an eye on this week:")
    else:
        lines.append(f"{n_total} students to keep an eye on this week:")
    lines.append("")

    for s in shown:
        tag = _concern_tag(s.concerns)
        tag_part = f" — _{tag}_" if tag else ""
        lines.append(
            f"• *{s.name}*{tag_part}\n"
            f"    deficit {_fmt_xp(s.deficit_total)} XP across "
            f"{s.days_behind} day(s)"
        )

    hidden = n_total - len(shown)
    if hidden > 0:
        lines.append("")
        lines.append(f"_…and {hidden} more — see the head-coach digest for full list._")

    lines.append("")
    lines.append(
        "_Auto-generated weekly nudge — reply in this DM if you want to "
        "set XP overrides or test-by dates for any of these students._"
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def build_coach_nudges(
    payload: DigestV2Payload,
    coach_slack_ids: Dict[str, str],
) -> List[CoachNudge]:
    """Build per-coach nudges from a DigestV2Payload.

    Args:
        payload: A built DigestV2Payload (from src.digest_v2.build_digest_v2).
        coach_slack_ids: Mapping of coach_name -> Slack U... user ID.
            Coaches missing from this map are skipped (with no error) so a
            partial roster doesn't block the whole batch.

    Returns:
        A list of CoachNudge. Coaches with no flagged students or no Slack
        ID on file are omitted. Order matches per_coach iteration order.
    """
    out: List[CoachNudge] = []
    for coach_name in payload.per_coach.keys():
        flagged = _flagged_students_for_coach(payload, coach_name)
        if len(flagged) < MIN_FLAGGED_STUDENTS_TO_NUDGE:
            continue
        slack_id: Optional[str] = coach_slack_ids.get(coach_name)
        if not slack_id:
            # Coach not in Slack ID map — skip rather than crash.
            continue
        text = _render_nudge_text(coach_name, flagged, payload)
        out.append(
            CoachNudge(
                coach_name=coach_name,
                slack_user_id=slack_id,
                text=text,
            )
        )
    return out
