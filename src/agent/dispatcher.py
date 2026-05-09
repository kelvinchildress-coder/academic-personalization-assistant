"""
dispatcher.py
=============

Routes one inbound coach DM through the Phase-2 intent pipeline.

Decision tree (in order):

  1. Is there a pending Proposal for (coach_slack_id, channel_id)?
       Yes -> run is_yes()/is_no()/Refine on the message:
         * ConfirmYes  -> apply_proposal() and DM the coach the result
         * ConfirmNo   -> pop_proposal() and DM "ok, dropped"
         * Refine/other-> re-parse and replace pending proposal
                          (or DM "I didn't catch a yes/no — please
                          confirm or send a new instruction").
       Returns DispatchResult(kind="confirmed" | "dropped" | "refined").

  2. No pending Proposal? Parse the message as a free-form Intent
     via parse_intent. Three branches:
       * Pause / HalfTarget / GroupRule -> build_proposal,
         stage_proposal, send confirm DM, return "staged".
       * ConfirmYes/No without a pending proposal -> ignore (return
         "noop"); the gap-driven runner may still consume it for
         classic ratify-default flows.
       * Unknown -> return "unknown" so the runner can fall through to
         its existing gap-driven parse_reply path.

This module is intentionally agnostic about *how* the message arrived
or how the reply gets sent — it takes a SlackIO-shaped object so the
caller can swap in a fake for tests. The Slack object only needs a
`send_dm(user_id, text=...)` method.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol

from .intent_parser import parse_intent
from .intent_writer import apply_proposal, build_proposal
from .intents import (
    ConfirmNo,
    ConfirmYes,
    GroupRule,
    HalfTarget,
    Intent,
    Pause,
    Refine,
    Unknown,
    is_no,
    is_yes,
)
from .pending_state import (
    Proposal,
    get_proposal,
    pop_proposal,
    stage_proposal,
)


# ---------------------------------------------------------------------------
# Result + slack abstraction
# ---------------------------------------------------------------------------


@dataclass
class DispatchResult:
    kind: str             # "staged" | "confirmed" | "dropped" | "refined"
                          # | "needs_clarification" | "noop" | "unknown"
                          # | "error"
    summary: str = ""
    affected_students: int = 0
    errors: List[str] = field(default_factory=list)


class SlackSender(Protocol):
    def send_dm(self, user_id: str, text: str) -> Optional[str]: ...


def _send(slack: SlackSender, user_id: str, text: str) -> None:
    """Best-effort DM. Tries (user_id, text) first; falls back to kwarg."""
    try:
        slack.send_dm(user_id, text)
    except TypeError:
        # Some implementations may accept text as a kwarg only.
        slack.send_dm(user_id, text=text)


# ---------------------------------------------------------------------------
# Public entrypoint
# ---------------------------------------------------------------------------


def dispatch_message(
    *,
    text: str,
    coach_slack_id: str,
    channel_id: str,
    speaker_coach_name: str,
    students_blob: Dict[str, Any],
    coaches_blob: Dict[str, Any],
    students_path: Path,
    pending_path: Path,
    slack: SlackSender,
    anthropic_api_key: Optional[str] = None,
    today: Optional[date] = None,
) -> DispatchResult:
    """Route ONE inbound coach DM through the Phase-2 pipeline."""
    text = (text or "").strip()
    if not text:
        return DispatchResult(kind="noop", summary="empty message")

    # -- 1. Pending proposal awaiting confirm? -----------------------------
    pending = get_proposal(pending_path, coach_slack_id, channel_id)
    if pending is not None:
        return _resolve_pending(
            text=text,
            pending=pending,
            speaker_coach_name=speaker_coach_name,
            students_blob=students_blob,
            coaches_blob=coaches_blob,
            students_path=students_path,
            pending_path=pending_path,
            slack=slack,
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            anthropic_api_key=anthropic_api_key,
        )

    # -- 2. No pending proposal: parse as free-form intent -----------------
    intent = parse_intent(
        text,
        speaker_coach_name=speaker_coach_name,
        anthropic_api_key=anthropic_api_key,
    )

    if isinstance(intent, (Pause, HalfTarget, GroupRule)):
        return _stage_intent(
            intent=intent,
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            students_blob=students_blob,
            coaches_blob=coaches_blob,
            pending_path=pending_path,
            slack=slack,
        )

    if isinstance(intent, (ConfirmYes, ConfirmNo)):
        return DispatchResult(
            kind="noop",
            summary="bare yes/no with no pending proposal",
        )

    return DispatchResult(kind="unknown", summary="no intent matched")


# ---------------------------------------------------------------------------
# Branch: pending proposal present
# ---------------------------------------------------------------------------


def _resolve_pending(
    *,
    text: str,
    pending: Proposal,
    speaker_coach_name: str,
    students_blob: Dict[str, Any],
    coaches_blob: Dict[str, Any],
    students_path: Path,
    pending_path: Path,
    slack: SlackSender,
    coach_slack_id: str,
    channel_id: str,
    anthropic_api_key: Optional[str],
) -> DispatchResult:
    if is_yes(text):
        popped = pop_proposal(pending_path, coach_slack_id, channel_id)
        if popped is None:
            return DispatchResult(kind="error", errors=["proposal vanished"])
        ok, errs, n = apply_proposal(
            popped,
            students_path=students_path,
            source_coach_name=speaker_coach_name,
        )
        if not ok:
            _send(
                slack, coach_slack_id,
                (
                    f":warning: I couldn't apply that change — "
                    f"errors: {'; '.join(errs) or 'unknown'}. "
                    f"No changes were saved."
                ),
            )
            return DispatchResult(kind="error", errors=errs)
        _send(
            slack, coach_slack_id,
            (
                f":white_check_mark: Done — applied to {n} student(s). "
                f"{popped.summary_text}"
            ),
        )
        return DispatchResult(
            kind="confirmed",
            summary=popped.summary_text,
            affected_students=n,
            errors=errs,
        )

    if is_no(text):
        pop_proposal(pending_path, coach_slack_id, channel_id)
        _send(
            slack, coach_slack_id,
            ":no_entry_sign: Got it — dropped that pending change.",
        )
        return DispatchResult(kind="dropped", summary=pending.summary_text)

    # Refine: try a re-parse.
    new_intent = parse_intent(
        text,
        speaker_coach_name=speaker_coach_name,
        anthropic_api_key=anthropic_api_key,
    )
    if isinstance(new_intent, (Pause, HalfTarget, GroupRule)):
        pop_proposal(pending_path, coach_slack_id, channel_id)
        result = _stage_intent(
            intent=new_intent,
            coach_slack_id=coach_slack_id,
            channel_id=channel_id,
            students_blob=students_blob,
            coaches_blob=coaches_blob,
            pending_path=pending_path,
            slack=slack,
            refine_note=pending.summary_text,
        )
        return DispatchResult(
            kind="refined",
            summary=result.summary,
            affected_students=result.affected_students,
        )

    _send(
        slack, coach_slack_id,
        (
            f":question: I'm holding a pending change: "
            f"_{pending.summary_text}_. "
            f"Reply *yes* to apply, *no* to drop, or send a new instruction."
        ),
    )
    return DispatchResult(
        kind="needs_clarification",
        summary=pending.summary_text,
    )


# ---------------------------------------------------------------------------
# Branch: stage a fresh intent
# ---------------------------------------------------------------------------


def _stage_intent(
    *,
    intent: Intent,
    coach_slack_id: str,
    channel_id: str,
    students_blob: Dict[str, Any],
    coaches_blob: Dict[str, Any],
    pending_path: Path,
    slack: SlackSender,
    refine_note: Optional[str] = None,
) -> DispatchResult:
    proposal = build_proposal(
        intent,
        coach_slack_id=coach_slack_id,
        channel_id=channel_id,
        students_blob=students_blob,
        coaches_blob=coaches_blob,
    )
    stage_proposal(pending_path, proposal)

    msg_lines = []
    if refine_note:
        msg_lines.append(f":arrows_counterclockwise: Replaced previous: _{refine_note}_")
    msg_lines.append(f"*Proposed change:* {proposal.summary_text}")
    if proposal.expanded_targets:
        msg_lines.append(
            f"_Affects {len(proposal.expanded_targets)} student(s)._"
        )
    msg_lines.append("Reply *yes* to apply or *no* to drop.")
    _send(slack, coach_slack_id, "\n".join(msg_lines))
    return DispatchResult(
        kind="staged",
        summary=proposal.summary_text,
        affected_students=len(proposal.expanded_targets),
    )
