"""
question_drafter.py
===================

Drafts a friendly Slack DM to a coach asking about ONE goal gap. Uses
Anthropic's Claude when ANTHROPIC_API_KEY is set; otherwise falls back
to a deterministic template (so dev / dry-run still works end-to-end).

The drafter ALWAYS includes:
  * The student name (and "Lisa C Willis" normalization).
  * The exact gap kind and subject in plain English.
  * The cascade default value (so the coach can ratify with one word).
  * A short instruction on how to reply: "set Math to 6", "use default",
    "test out by 2027-01-29 to grade 8", or "30/day Math".

Tone: warm, brief, coach-friendly. Never more than ~80 words.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Dict, Optional

from .gap_finder import GoalGap


ANTHROPIC_MODEL = os.environ.get(
    "ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"
)


@dataclass(frozen=True)
class DraftedQuestion:
    text: str
    used_llm: bool


# ---------------------------------------------------------------------------
# Cascade default helpers (keep this module self-contained for tests)
# ---------------------------------------------------------------------------


def _q2_default_target_grade(
    age_grade: Optional[int],
    year_start_grade: Optional[int],
) -> Optional[int]:
    if age_grade is None or year_start_grade is None:
        return None
    anchors = (1, 3, 5, 8)
    anchor = next((a for a in anchors if a >= age_grade), min(age_grade, 12))
    growth = year_start_grade + 2
    return min(12, max(anchor, growth))


def _personalized_base_xp(
    subject: str, age_grade: Optional[int], current_grade: Optional[int]
) -> Optional[float]:
    base_table = {
        "Math": 25.0, "Reading": 25.0, "Language": 25.0,
        "Writing": 12.5, "Science": 12.5,
        "Vocabulary": 10.0, "FastMath": 10.0,
    }
    base = base_table.get(subject)
    if base is None:
        return None
    if subject in ("Vocabulary", "FastMath"):
        return base
    if age_grade is None or current_grade is None:
        return base
    adjusted = base + 2.5 * (age_grade - current_grade)
    return max(10.0, adjusted)


# ---------------------------------------------------------------------------
# Template fallback (no LLM)
# ---------------------------------------------------------------------------


def _template_for_gap(
    gap: GoalGap,
    profile: Dict[str, Any],
) -> str:
    student = gap.student_name
    if gap.kind == "MISSING_AGE_GRADE":
        return (
            f":wave: Quick one — what *age grade* should I record for "
            f"*{student}*? Reply with just a number (K=0, 1-12). "
            f"Once I have that I can compute the right daily targets."
        )

    age_grade = profile.get("age_grade")

    if gap.kind == "MISSING_CURRENT_GRADE":
        return (
            f":wave: For *{student}*, what *current grade* are they working "
            f"in *{gap.subject}*? Reply like `Math 6` or just `6`. "
            f"(Their age grade is {age_grade}.)"
        )

    if gap.kind == "MISSING_YEAR_START":
        cur = (profile.get("current_grade_per_subject") or {}).get(gap.subject)
        return (
            f":wave: For *{student}* in *{gap.subject}*, what grade did they "
            f"*start the school year in*? (They're currently in grade {cur}.) "
            f"This anchors their +2 growth target. Reply like `{gap.subject} 4`."
        )

    if gap.kind in ("MISSING_TARGET", "MISSING_RATIFICATION"):
        ys = (profile.get("year_start_grade_per_subject") or {}).get(gap.subject)
        cur = (profile.get("current_grade_per_subject") or {}).get(gap.subject)
        default_grade = _q2_default_target_grade(age_grade, ys)
        per_base = _personalized_base_xp(gap.subject, age_grade, cur)
        default_grade_str = (
            f"grade {default_grade}" if default_grade is not None else "—"
        )
        per_base_str = (
            f"{per_base:g} XP/day" if per_base is not None else "—"
        )
        return (
            f":wave: Goal check for *{student}* / *{gap.subject}*.\n"
            f"Default test-out target: *{default_grade_str}* by next MAP.\n"
            f"Default daily XP: *{per_base_str}*.\n"
            f"Reply `use default`, or override with e.g. "
            f"`{gap.subject} 7 by 2027-01-29` or `{gap.subject} 30/day`."
        )

    return (
        f":wave: I have a question about *{student}* / *{gap.subject or '—'}* "
        f"({gap.kind}). Could you share more context when you have a moment?"
    )


# ---------------------------------------------------------------------------
# Anthropic-powered drafting
# ---------------------------------------------------------------------------


_SYSTEM_PROMPT = (
    "You are an academic personalization assistant for Texas Sports Academy. "
    "You write very short, warm, professional Slack DMs to coaches asking for "
    "ONE specific piece of information about ONE student. "
    "Always include the cascade-default value so the coach can reply with "
    "'use default' to accept it. Keep messages under 80 words. "
    "Never invent student or coach names. Never ask multiple questions in one "
    "message. Use Slack mrkdwn (single asterisks for bold). "
    "Sign off with no signature; the bot identity is implied."
)


def _draft_with_anthropic(
    gap: GoalGap,
    profile: Dict[str, Any],
    *,
    api_key: str,
) -> Optional[str]:
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None

    age_grade = profile.get("age_grade")
    cur = (profile.get("current_grade_per_subject") or {}).get(gap.subject)
    ys = (profile.get("year_start_grade_per_subject") or {}).get(gap.subject)
    default_grade = _q2_default_target_grade(age_grade, ys)
    per_base = _personalized_base_xp(gap.subject or "", age_grade, cur)

    user_payload = {
        "student": gap.student_name,
        "subject": gap.subject,
        "gap_kind": gap.kind,
        "age_grade": age_grade,
        "current_grade_in_subject": cur,
        "year_start_grade_in_subject": ys,
        "default_target_grade": default_grade,
        "default_personalized_base_xp_per_day": per_base,
        "next_map": "next MAP testing window",
    }

    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=300,
        system=_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": (
                "Draft the Slack DM. Context (JSON):\n"
                f"{user_payload}\n\n"
                "Return ONLY the DM body — no preamble, no explanation."
            ),
        }],
    )
    if not msg.content:
        return None
    text_parts = []
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            text_parts.append(block.text)
    return "\n".join(t.strip() for t in text_parts if t).strip() or None


# ---------------------------------------------------------------------------
# Public entry
# ---------------------------------------------------------------------------


def draft_question(
    gap: GoalGap,
    *,
    student_profile: Dict[str, Any],
    anthropic_api_key: Optional[str] = None,
) -> DraftedQuestion:
    """
    Draft the DM body for one gap. Uses Anthropic when available; falls
    back to a deterministic template otherwise.
    """
    api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        text = _draft_with_anthropic(gap, student_profile, api_key=api_key)
        if text:
            return DraftedQuestion(text=text, used_llm=True)

    return DraftedQuestion(
        text=_template_for_gap(gap, student_profile),
        used_llm=False,
    )
