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
caller can swap in a fake for tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Protocol

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
    errors: List[str] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.errors is None:
            self.errors = []


class SlackSender(Protocol):
    def send_dm(self, user_id: str, *, channel_id: Optional[str] = None,
                text: str = "") -> Optional[str]: ...


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
    """Route ONE inbound coach DM through the Phase-2 pipeline.

    See module docstring for the decision tree.
    """
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
        # Bare yes/no with no pending proposal -> let the gap-driven
        # runner handle it (e.g. "ratify default" affirmation).
        return DispatchResult(
            kind="noop",
            summary="bare yes/no with no pending proposal",
        )

    # Unknown / Refine without context -> let the runner's existing
    # parse_reply pipeline try.
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
        # Apply.
        popped = pop_proposal(pending_path, coach_slack_id, channel_id)
        if popped is None:
            return DispatchResult(kind="error", errors=["proposal vanished"])
        ok, errs, n = apply_proposal(
            popped,
            students_path=students_path,
            source_coach_name=speaker_coach_name,
        )
        if not ok:
            slack.send_dm(
                coach_slack_id,
                channel_id=channel_id,
                text=(
                    f":warning: I couldn't apply that change — "
                    f"errors: {'; '.join(errs) or 'unknown'}. "
                    f"No changes were saved."
                ),
            )
            return DispatchResult(kind="error", errors=errs)
        slack.send_dm(
            coach_slack_id,
            channel_id=channel_id,
            text=(
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
        slack.send_dm(
            coach_slack_id,
            channel_id=channel_id,
            text=":no_entry_sign: Got it — dropped that pending change.",
        )
        return DispatchResult(kind="dropped", summary=pending.summary_text)

    # Try to interpret as a Refine: re-parse and replace the pending
    # proposal IF the new parse yields a real intent (not Unknown).
    new_intent = parse_intent(
        text,
        speaker_coach_name=speaker_coach_name,
        anthropic_api_key=anthropic_api_key,
    )
    if isinstance(new_intent, (Pause, HalfTarget, GroupRule)):
        # Pop the old, stage the new.
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

    # Not yes, not no, not a recognizable refinement -> ask for clarity.
    slack.send_dm(
        coach_slack_id,
        channel_id=channel_id,
        text=(
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
    slack.send_dm(
        coach_slack_id,
        channel_id=channel_id,
        text="\n".join(msg_lines),
    )
    return DispatchResult(
        kind="staged",
        summary=proposal.summary_text,
        affected_students=len(proposal.expanded_targets),
    )
