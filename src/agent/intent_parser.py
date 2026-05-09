"""
intent_parser.py
================

Parses a coach's *free-form* Slack DM into a Phase-2 Intent object.

Unlike reply_parser.parse_reply (which is gap-driven and answers a
specific open question), parse_intent() handles *unsolicited* statements
like:

  - "Marcus is out today"                      -> Pause (full day)
  - "Pause Marcus's Writing for 3 days"        -> Pause (per-subject, range)
  - "All my L2 kids are at field day Friday"   -> GroupRule (Pause)
  - "Half Math expectations for Maya this week"-> HalfTarget
  - "yes" / "no" / "use 25 instead"            -> Confirm / Refine

Two layers, in order:

  1. Deterministic regex pass — catches the high-frequency patterns
     using the level-band vocabulary from intents.py
     (LL / L1 / L2 / L3 / MS, "my Xth graders", "all my kids",
     "across the school").

  2. Anthropic fallback for ambiguous text. The LLM is asked to emit
     a strict JSON shape that maps cleanly onto one of the Intent
     dataclasses. Output is re-validated before any caller acts on it.

Every Intent that mutates state is still routed through
config_writer's propose-then-confirm flow downstream — this module
does NOT write anything to disk.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, timedelta
from typing import List, Optional, Tuple

from .intents import (
    Intent,
    Pause,
    HalfTarget,
    GroupRule,
    GroupSelector,
    SetTestBy,
    ConfirmYes,
    ConfirmNo,
    Refine,
    Unknown,
    LEVEL_BANDS,
    normalize_level_band,
    grades_for_band,
    is_yes,
    is_no,
)

ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")

GRADED_SUBJECTS = ("Math", "Reading", "Language", "Writing", "Science")
ALL_SUBJECTS = GRADED_SUBJECTS + ("Vocabulary", "FastMath")

_SUBJECT_ALIAS = {
    "math": "Math",
    "reading": "Reading", "read": "Reading",
    "language": "Language", "lang": "Language",
    "writing": "Writing", "write": "Writing",
    "science": "Science", "sci": "Science",
    "vocab": "Vocabulary", "vocabulary": "Vocabulary",
    "fastmath": "FastMath", "fast math": "FastMath",
}


# ---------------------------------------------------------------------------
# Deterministic regex
# ---------------------------------------------------------------------------

# "Marcus is out today" / "Marcus out tomorrow" / "Marcus is out for 3 days"
_RE_PAUSE_STUDENT_OUT = re.compile(
    r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z]\.?)?(?:\s+[A-Z][a-zA-Z'\-]+)?)\s+"
    r"(?:is\s+)?(?:out|absent|sick|away|gone)"
    r"(?:\s+(?:for\s+)?(?:(today|tomorrow|the\s+rest\s+of\s+the\s+week|this\s+week)|(\d+)\s+days?))?\b",
    re.IGNORECASE,
)

# "pause Marcus's writing for 3 days" / "pause writing for Marcus 2 days"
_RE_PAUSE_VERB = re.compile(
    r"\bpause\b.*?\b(math|reading|read|language|lang|writing|write|science|sci|vocab(?:ulary)?|fast\s*math)?"
    r".*?(?:for\s+)?(\d+)\s+days?\b",
    re.IGNORECASE,
)

# "half math expectations for Maya this week" / "half target for L2 kids"
# / "reduced expectations" / "halve writing for Marcus 5 days"
_RE_HALF = re.compile(
    r"\b(?:half|halve|halved|halving|reduced?|reduce)\b.*?"
    r"(?:(math|reading|read|language|lang|writing|write|science|sci))?",
    re.IGNORECASE,
)

# Duration phrases mapped to day counts
_DURATION_PHRASES = {
    "today": 1,
    "tomorrow": 1,
    "this week": 5,
    "the rest of the week": 5,
    "rest of the week": 5,
    "next week": 5,
    "all week": 5,
    "all day": 1,
}

# Level-band tokens — any of these in the text means a group rule
_RE_LEVEL_BAND = re.compile(
    r"\b(LL|L1|L2|L3|MS|kindergarten|K-1|K\s*-\s*1|"
    r"middle\s*school|"
    r"(?:2nd|3rd|4th|5th|6th|7th|8th|second|third|fourth|fifth|sixth|seventh|eighth)"
    r"\s*(?:grade|graders?))\b",
    re.IGNORECASE,
)

# "my kids" / "all my students" / "everyone on my roster"
_RE_MY_GROUP = re.compile(
    r"\b(my|all\s+my|everyone\s+on\s+my)\s+(kids|students|roster|guys|crew)\b",
    re.IGNORECASE,
)

# "across the school" / "all coaches" / "every student"
_RE_ALL_GROUP = re.compile(
    r"\b(across\s+the\s+school|all\s+coaches|every\s+student|school[\-\s]wide)\b",
    re.IGNORECASE,
)

_RE_NUMERIC_DAYS = re.compile(r"\b(\d+)\s+days?\b", re.IGNORECASE)


def _today_iso() -> str:
    return date.today().isoformat()


def _add_days_iso(start_iso: str, days: int) -> str:
    d = date.fromisoformat(start_iso)
    return (d + timedelta(days=max(0, days - 1))).isoformat()


def _normalize_subject(token: Optional[str]) -> Optional[str]:
    if not token:
        return None
    key = re.sub(r"\s+", " ", token.strip().lower())
    return _SUBJECT_ALIAS.get(key) or _SUBJECT_ALIAS.get(key.replace(" ", ""))


def _extract_duration_days(text: str) -> int:
    """Returns number of school days the action should cover. Defaults to 1."""
    low = text.lower()
    for phrase, days in _DURATION_PHRASES.items():
        if phrase in low:
            return days
    m = _RE_NUMERIC_DAYS.search(low)
    if m:
        try:
            return max(1, int(m.group(1)))
        except ValueError:
            pass
    return 1


def _extract_grade_token_band(text: str) -> Optional[str]:
    """If text mentions a level band or grade phrase, return canonical band."""
    m = _RE_LEVEL_BAND.search(text)
    if not m:
        return None
    raw = m.group(1).strip().lower()
    direct = normalize_level_band(raw)
    if direct:
        return direct
    if "kindergarten" in raw or re.search(r"\bk\s*-?\s*1\b", raw):
        return "LL"
    if "middle school" in raw:
        return "L3"
    grade_word = {
        "second": 2, "2nd": 2,
        "third": 3, "3rd": 3,
        "fourth": 4, "4th": 4,
        "fifth": 5, "5th": 5,
        "sixth": 6, "6th": 6,
        "seventh": 7, "7th": 7,
        "eighth": 8, "8th": 8,
    }
    for word, g in grade_word.items():
        if word in raw:
            for band, grades in LEVEL_BANDS.items():
                if g in grades:
                    return band
    return None


def _extract_subject_in_text(text: str) -> Optional[str]:
    for alias, canon in _SUBJECT_ALIAS.items():
        if re.search(rf"\b{re.escape(alias)}\b", text, re.IGNORECASE):
            return canon
    return None


def _build_group_selector(
    text: str,
    speaker_coach_name: str,
) -> Optional[GroupSelector]:
    band = _extract_grade_token_band(text)
    if _RE_ALL_GROUP.search(text):
        return GroupSelector(
            scope="all",
            level_band=band,
            speaker_coach=speaker_coach_name,
        )
    if _RE_MY_GROUP.search(text) or band:
        return GroupSelector(
            scope="speaker",
            level_band=band,
            speaker_coach=speaker_coach_name,
        )
    return None


# ---------------------------------------------------------------------------
# Deterministic pass
# ---------------------------------------------------------------------------


def _parse_deterministic(
    text: str,
    *,
    speaker_coach_name: str,
) -> Intent:
    stripped = text.strip()

    # 0. Bare yes/no on its own line.
    if is_yes(stripped):
        return ConfirmYes(raw_text=text)
    if is_no(stripped):
        return ConfirmNo(raw_text=text)

    low = stripped.lower()

    # 1. Group rule? (level band or "my kids" / "across the school")
    selector = _build_group_selector(stripped, speaker_coach_name)
    if selector:
        # Decide what kind of rule this group is for.
        if _RE_HALF.search(low):
            subject = _extract_subject_in_text(low)
            return GroupRule(
                selector=selector,
                action="half_target",
                subject=subject,
                start_date=_today_iso(),
                days=_extract_duration_days(low),
                raw_text=text,
            )
        if "out" in low or "absent" in low or "field day" in low or "pause" in low:
            return GroupRule(
                selector=selector,
                action="pause",
                subject=_extract_subject_in_text(low),
                start_date=_today_iso(),
                days=_extract_duration_days(low),
                raw_text=text,
            )
        # Group mentioned but no clear verb — surface as Refine for confirm.
        return Refine(raw_text=text, hint=f"group:{selector.describe()}")

    # 2. Half-target for a single student.
    if _RE_HALF.search(low):
        subject = _extract_subject_in_text(low)
        # Try to lift a name (very simple — first capitalized token).
        name_match = re.search(r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)\b", text)
        student = name_match.group(1) if name_match else ""
        if student:
            return HalfTarget(
                student_name=student,
                subject=subject,
                start_date=_today_iso(),
                days=_extract_duration_days(low),
                raw_text=text,
            )

    # 3. "X is out [today/N days]" — full-day or per-subject pause.
    m = _RE_PAUSE_STUDENT_OUT.search(text)
    if m:
        student = m.group(1).strip()
        phrase = (m.group(2) or "").strip().lower()
        days_token = m.group(3)
        if days_token:
            days = max(1, int(days_token))
        elif phrase:
            days = _DURATION_PHRASES.get(phrase, 1)
        else:
            days = 1
        return Pause(
            student_name=student,
            subject=None,  # full-day pause
            start_date=_today_iso(),
            days=days,
            raw_text=text,
        )

    # 4. "pause <subject> for X days" — explicit verb form.
    m = _RE_PAUSE_VERB.search(text)
    if m:
        subj_raw = m.group(1)
        days = max(1, int(m.group(2)))
        subject = _normalize_subject(subj_raw) if subj_raw else None
        # Try to lift a name.
        name_match = re.search(r"\b([A-Z][a-zA-Z'\-]+(?:\s+[A-Z][a-zA-Z'\-]+)?)\b", text)
        student = name_match.group(1) if name_match else ""
        if student:
            return Pause(
                student_name=student,
                subject=subject,
                start_date=_today_iso(),
                days=days,
                raw_text=text,
            )

    return Unknown(raw_text=text)


# ---------------------------------------------------------------------------
# Anthropic fallback
# ---------------------------------------------------------------------------


_LLM_SYSTEM = (
    "You convert a coach's free-text Slack message into a STRICT JSON "
    "intent for an academic config system. Output JSON ONLY, no prose. "
    "Choose ONE of these intent_type values:\n"
    "  pause       - student or group is unavailable for some days\n"
    "  half_target - reduce target XP/grade by half for a window\n"
    "  group_rule  - pause or half_target applied to a group\n"
    "  set_test_by - move/schedule a student's test-out date (and/or set "
    "                  a target grade) for one subject. Examples: 'push "
    "                  Allison's MAP to next Wednesday', 'Marcus tests "
    "                  out of Math at grade 4 by May 30', 'move Sam's "
    "                  reading test to two weeks from today'.\n"
    "  confirm_yes - coach is approving a pending proposal\n"
    "  confirm_no  - coach is rejecting a pending proposal\n"
    "  refine      - coach wants to adjust a pending proposal\n"
    "  unknown     - cannot map to any of the above\n"
    "\n"
    "Schema:\n"
    "{\n"
    '  "intent_type": str,\n'
    '  "student_name": str|null,\n'
    '  "subject": "Math|Reading|Language|Writing|Science"|null,\n'
    '  "start_date": "YYYY-MM-DD"|null,\n'
    '  "days": int|null,\n'
    '  "group_scope": "speaker|all"|null,\n'
    '  "level_band": "LL|L1|L2|L3"|null,\n'
    '  "action": "pause|half_target"|null,\n'
    '  "target_date": "YYYY-MM-DD"|null,\n'
    '  "target_grade": int|null,\n'
    '  "hint": str|null\n'
    "}\n"
    "Use null for fields the coach did not specify. start_date defaults to "
    "today if a relative phrase like 'today' or 'this week' is used. "
    "For set_test_by: target_date is the new test-out deadline (resolve "
    "relative phrases like 'next Wednesday' or 'two weeks out' against "
    "the today value). target_grade is optional and only filled if the "
    "coach explicitly mentions a grade level (e.g. 'at grade 4'). "
    "subject is required for set_test_by (default to 'Math' if the "
    "coach said 'MAP' without naming a subject)."
)


def _parse_with_anthropic(
    text: str,
    *,
    speaker_coach_name: str,
    today_iso: str,
    api_key: str,
) -> Optional[Intent]:
    try:
        import anthropic  # type: ignore
    except ImportError:
        return None
    client = anthropic.Anthropic(api_key=api_key)
    msg = client.messages.create(
        model=ANTHROPIC_MODEL,
        max_tokens=400,
        system=_LLM_SYSTEM,
        messages=[{
            "role": "user",
            "content": (
                f"speaker_coach: {speaker_coach_name}\n"
                f"today: {today_iso}\n"
                f"coach_message:\n{text}\n\n"
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
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw.lower().startswith("json"):
            raw = raw[4:].lstrip()
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(obj, dict):
        return None
    return _intent_from_llm_dict(obj, speaker_coach_name, text, today_iso)


def _intent_from_llm_dict(
    obj: dict,
    speaker_coach_name: str,
    raw_text: str,
    today_iso: str,
) -> Intent:
    kind = (obj.get("intent_type") or "").strip().lower()
    start_date = obj.get("start_date") or today_iso
    days = obj.get("days")
    if not isinstance(days, int) or days < 1:
        days = 1
    subject = obj.get("subject")
    if subject and subject not in GRADED_SUBJECTS:
        subject = None
    if kind == "confirm_yes":
        return ConfirmYes(raw_text=raw_text)
    if kind == "confirm_no":
        return ConfirmNo(raw_text=raw_text)
    if kind == "refine":
        return Refine(raw_text=raw_text, hint=obj.get("hint") or "")
    if kind == "pause":
        return Pause(
            student_name=obj.get("student_name") or "",
            subject=subject,
            start_date=start_date,
            days=days,
            raw_text=raw_text,
        )
    if kind == "half_target":
        return HalfTarget(
            student_name=obj.get("student_name") or "",
            subject=subject,
            start_date=start_date,
            days=days,
            raw_text=raw_text,
        )
    if kind == "group_rule":
        scope = obj.get("group_scope") or "speaker"
        if scope not in ("speaker", "all"):
            scope = "speaker"
        band = obj.get("level_band")
        if band and band not in LEVEL_BANDS:
            band = None
        action = obj.get("action") or "pause"
        if action not in ("pause", "half_target"):
            action = "pause"
        return GroupRule(
            selector=GroupSelector(
                scope=scope,
                level_band=band,
                speaker_coach=speaker_coach_name,
            ),
            action=action,
            subject=subject,
            start_date=start_date,
            days=days,
            raw_text=raw_text,
        )
    if kind == "set_test_by":
        # Subject defaults to Math when coach says "MAP" without naming
        # a subject (most common shorthand at TSA).
        st_subject = subject or "Math"
        # Parse target_date (may be null, may be ISO).
        td_raw = obj.get("target_date")
        td: Optional[date] = None
        if td_raw:
            try:
                td = date.fromisoformat(str(td_raw))
            except ValueError:
                td = None
        # Parse target_grade (may be null, may be int or numeric string).
        tg_raw = obj.get("target_grade")
        tg: Optional[int] = None
        if tg_raw is not None:
            try:
                tg = int(tg_raw)
            except (TypeError, ValueError):
                tg = None
        # Drop entirely-empty SetTestBy (no date, no grade) -> Unknown,
        # so the dispatcher can ask the coach to clarify.
        if td is None and tg is None:
            return Unknown(raw_text=raw_text)
        return SetTestBy(
            student=obj.get("student_name") or "",
            subject=st_subject,
            target_grade=tg,
            target_date=td,
            raw_text=raw_text,
        )
    return Unknown(raw_text=raw_text)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_intent(
    text: str,
    *,
    speaker_coach_name: str,
    anthropic_api_key: Optional[str] = None,
    today_iso: Optional[str] = None,
) -> Intent:
    """Parse a free-form coach DM into a Phase-2 Intent.

    Always returns an Intent (Unknown if nothing matched). Never writes
    to disk — caller is responsible for routing through config_writer's
    propose-then-confirm flow.
    """
    if not text or not text.strip():
        return Unknown(raw_text=text or "")

    today_iso = today_iso or _today_iso()

    det = _parse_deterministic(text, speaker_coach_name=speaker_coach_name)
    if not isinstance(det, Unknown):
        return det

    api_key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
    if api_key:
        llm_intent = _parse_with_anthropic(
            text,
            speaker_coach_name=speaker_coach_name,
            today_iso=today_iso,
            api_key=api_key,
        )
        if llm_intent and not isinstance(llm_intent, Unknown):
            return llm_intent

    return Unknown(raw_text=text)
