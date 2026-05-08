"""
reply_parser.py
===============

Parses a coach's free-text Slack reply into one or more StructuredPatch
objects ready to be validated + applied via config_writer.

Two layers, in order:

  1. Fast deterministic regex pass — catches the common patterns
     ("Math 6", "use default", "Math 30/day", "test by 2027-01-29 grade 7",
     numeric reply to MISSING_AGE_GRADE).

  2. Anthropic fallback for ambiguous text. The LLM is asked to return a
     strict JSON shape that we then re-validate before any write.

Even when the LLM is used, every output is run through
config_writer.validate_patch() before being applied. Malformed patches
are rejected and the agent re-asks the question politely.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Dict, List, Optional, Tuple

from .config_writer import (
    StructuredPatch,
    GRADED_SUBJECTS,
    ALL_SUBJECTS,
)
from .gap_finder import GoalGap


ANTHROPIC_MODEL = os.environ.get(
    "ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"
)


@dataclass
class ParseResult:
    patches: List[StructuredPatch] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    used_llm: bool = False


# ---------------------------------------------------------------------------
# Subject normalization
# ---------------------------------------------------------------------------


_SUBJECT_ALIAS = {
    "math": "Math",
    "reading": "Reading",
    "read": "Reading",
    "language": "Language",
    "lang": "Language",
    "writing": "Writing",
    "write": "Writing",
    "science": "Science",
    "sci": "Science",
    "vocab": "Vocabulary",
    "vocabulary": "Vocabulary",
    "fastmath": "FastMath",
    "fast math": "FastMath",
    "fast-math": "FastMath",
}


def _canon_subject(token: str) -> Optional[str]:
    return _SUBJECT_ALIAS.get(token.strip().lower())


def _grade_token_to_int(tok: str) -> Optional[int]:
    t = tok.strip().lower().rstrip(".")
    if t in ("k", "kindergarten", "kinder"):
        return 0
    m = re.match(r"^(\d{1,2})(?:st|nd|rd|th)?$", t)
    if m:
        v = int(m.group(1))
        if 0 <= v <= 12:
            return v
    return None


# ---------------------------------------------------------------------------
# Regex patterns
# ---------------------------------------------------------------------------

# "Math 6", "Math: 6", "Math grade 6"
_RE_SUBJECT_GRADE = re.compile(
    r"\b(math|reading|read|language|lang|writing|write|science|sci|vocab|vocabulary|fastmath|fast\s*math)"
    r"\s*(?:grade|gr|level|:)?\s*"
    r"(k|\d{1,2}(?:st|nd|rd|th)?)"
    r"(?!\s*/\s*day)",
    re.IGNORECASE,
)

# "Math 30/day", "math 25 xp/day", "math: 30 per day"
_RE_SUBJECT_XP = re.compile(
    r"\b(math|reading|read|language|lang|writing|write|science|sci|vocab|vocabulary|fastmath|fast\s*math)"
    r"\s*(?::|=|->)?\s*"
    r"(\d+(?:\.\d+)?)"
    r"\s*(?:xp)?\s*(?:/|per)\s*day\b",
    re.IGNORECASE,
)

# "by 2027-01-29 grade 7", "Math by 2027-01-29 to 7", etc.
_RE_TEST_BY = re.compile(
    r"\b(math|reading|read|language|lang|writing|write|science|sci)"
    r"[^\d]+by\s+"
    r"(\d{4}-\d{2}-\d{2})"
    r"(?:[^\d]+(?:to|grade|level)?\s*(k|\d{1,2}))?",
    re.IGNORECASE,
)

# "use default" / "default" / "ratify" / "ok use default"
_RE_USE_DEFAULT = re.compile(
    r"\b(use\s+default|defaults?|ratify|accept\s+default|sounds\s+good|ok\s+default)\b",
    re.IGNORECASE,
)

# Bare integer ("4", "7th", "K") — typically an age_grade reply.
_RE_BARE_GRADE = re.compile(
    r"^\s*(k|kindergarten|\d{1,2}(?:st|nd|rd|th)?)\s*\.?\s*$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Deterministic parse
# ---------------------------------------------------------------------------


def _parse_deterministic(
    text: str,
    *,
    gap: GoalGap,
) -> ParseResult:
    out = ParseResult()
    student = gap.student_name

    # 1. Bare grade response when the gap is age_grade.
    if gap.kind == "MISSING_AGE_GRADE":
        m = _RE_BARE_GRADE.match(text)
        if m:
            g = _grade_token_to_int(m.group(1))
            if g is not None:
                out.patches.append(StructuredPatch(
                    student_name=student,
                    updates={"age_grade": g},
                ))
                return out
        # Try to find a single number anywhere.
        nums = re.findall(r"\b(k|\d{1,2})\b", text, re.IGNORECASE)
        if len(nums) == 1:
            g = _grade_token_to_int(nums[0])
            if g is not None:
                out.patches.append(StructuredPatch(
                    student_name=student,
                    updates={"age_grade": g},
                ))
                return out

    # 2. "Use default" => ratify the subject in question.
    if _RE_USE_DEFAULT.search(text) and gap.subject:
        out.patches.append(StructuredPatch(
            student_name=student,
            updates={"ratified": [gap.subject]},
        ))
        return out

    grade_updates_current: Dict[str, int] = {}
    grade_updates_year_start: Dict[str, int] = {}
    grade_updates_target: Dict[str, int] = {}
    date_updates: Dict[str, str] = {}
    xp_updates: Dict[str, float] = {}

    # 3. "Math 30/day" -> overrides.xp_per_day
    for m in _RE_SUBJECT_XP.finditer(text):
        canon = _canon_subject(m.group(1))
        if not canon:
            continue
        try:
            val = float(m.group(2))
        except ValueError:
            continue
        xp_updates[canon] = val

    # 4. "Math by 2027-01-29 to 7" -> manual_test_out_grade + manual_test_out_date
    for m in _RE_TEST_BY.finditer(text):
        canon = _canon_subject(m.group(1))
        if not canon or canon not in GRADED_SUBJECTS:
            continue
        try:
            d = date.fromisoformat(m.group(2))
        except ValueError:
            continue
        date_updates[canon] = d.isoformat()
        if m.group(3):
            g = _grade_token_to_int(m.group(3))
            if g is not None:
                grade_updates_target[canon] = g

    # 5. "Math 6" -> depends on which gap is open.
    consumed_spans: List[Tuple[int, int]] = []
    for m in _RE_TEST_BY.finditer(text):
        consumed_spans.append(m.span())
    for m in _RE_SUBJECT_XP.finditer(text):
        consumed_spans.append(m.span())

    def _is_consumed(span: Tuple[int, int]) -> bool:
        s, e = span
        for cs, ce in consumed_spans:
            if cs <= s and ce >= e:
                return True
        return False

    for m in _RE_SUBJECT_GRADE.finditer(text):
        if _is_consumed(m.span()):
            continue
        canon = _canon_subject(m.group(1))
        if not canon or canon not in GRADED_SUBJECTS:
            continue
        g = _grade_token_to_int(m.group(2))
        if g is None:
            continue
        # Map to whichever grade-field the open gap is asking for.
        if gap.kind == "MISSING_CURRENT_GRADE" and gap.subject == canon:
            grade_updates_current[canon] = g
        elif gap.kind == "MISSING_YEAR_START" and gap.subject == canon:
            grade_updates_year_start[canon] = g
        elif gap.kind in ("MISSING_TARGET", "MISSING_RATIFICATION"):
            grade_updates_target[canon] = g
        else:
            # Unsolicited extra info — apply to current_grade by default.
            grade_updates_current[canon] = g

    # Assemble patches. We collapse into ONE patch per student so
    # validate_patch sees the whole proposal.
    updates: Dict[str, Any] = {}
    if grade_updates_current:
        updates["current_grade_per_subject"] = grade_updates_current
    if grade_updates_year_start:
        updates["year_start_grade_per_subject"] = grade_updates_year_start
    if grade_updates_target:
        updates["manual_test_out_grade"] = grade_updates_target
    if date_updates:
        updates["manual_test_out_date"] = date_updates
    if xp_updates:
        updates["overrides.xp_per_day"] = xp_updates

    if updates:
        out.patches.append(StructuredPatch(
            student_name=student,
            updates=updates,
        ))
    return out


# ---------------------------------------------------------------------------
# Anthropic fallback
# ---------------------------------------------------------------------------


_LLM_SYSTEM = (
    "You convert a coach's free-text Slack reply into a STRICT JSON "
    "object describing config updates for ONE student. Output JSON ONLY, "
    "no prose. Schema:\n"
    "{\n"
    '  "student_name": str,\n'
    '  "updates": {\n'
    '     "age_grade": int|null,\n'
    '     "current_grade_per_subject": {Subject: int}|null,\n'
    '     "year_start_grade_per_subject": {Subject: int}|null,\n'
    '     "manual_test_out_grade": {Subject: int}|null,\n'
    '     "manual_test_out_date": {Subject: "YYYY-MM-DD"}|null,\n'
    '     "overrides.xp_per_day": {Subject: number}|null,\n'
    '     "ratified": [Subject]|null,\n'
    '     "notes": str|null\n'
    "  }\n"
    "}\n"
    "Subject must be one of: Math, Reading, Language, Writing, Science, "
    "Vocabulary, FastMath. Grade ints are 0..12 (K=0). Omit any field "
    "the coach did not address (do NOT include null fields). If the "
    "reply is ambiguous or off-topic, return {\"student_name\": ..., "
    "\"updates\": {}}."
)


def _parse_with_anthropic(
    text: str,
    *,
    gap: GoalGap,
    api_key: str,
) -> Optional[StructuredPatch]:
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=600,
        system=_LLM_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"student_name: {gap.student_name}\n"
                f"open_gap: {gap.kind} (subject: {gap.subject})\n"
                f"coach_reply:\n{text}\n\n"
                "Return JSON only."
            ),
        }],
    )
    if not msg.content:
        return None
    raw = ""
    for block in msg.content:
        if getattr(block, "type", None) == "text":
            raw += block.text
    raw = raw.strip()
    # Strip code fences if any.
    if raw.startswith("```"):
        raw = raw.strip("`")
        # Drop a leading "json" tag.
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    name = obj.get("student_name") or gap.student_name
    updates = obj.get("updates") or {}
    if not isinstance(updates, dict):
        return None
    # Strip nulls / empty maps.
    cleaned = {k: v for k, v in updates.items() if v not in (None, {}, [])}
    if not cleaned:
        return None
    return StructuredPatch(student_name=name, updates=cleaned)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_reply(
    text: str,
    *,
    gap: GoalGap,
    anthropic_api_key: Optional[str] = None,
) -> ParseResult:
    """Parse a coach reply. Always returns a ParseResult; check .patches."""
    if not text or not text.strip():
        return ParseResult(warnings=["empty reply"])

    det = _parse_deterministic(text, gap=gap)
    if det.patches:
        return det

    api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        patch = _parse_with_anthropic(text, gap=gap, api_key=api_key)
        if patch:
            return ParseResult(patches=[patch], used_llm=True)

    return ParseResult(warnings=["could not parse reply"])
