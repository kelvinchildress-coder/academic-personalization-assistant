"""Structured intent types produced by the natural-language reply parser.

Phase 2 expands the agent's grammar from "set Marcus math to 30" to a
full vocabulary of coach actions:

  - SetXp           : per-student-per-subject XP/day override
  - SetTestBy       : per-student-per-subject test-out-by date override
  - Pause           : suspend a student (full or per-subject) for a date
                       or date range
  - HalfTarget      : reduced-expectation modifier (50% of base/personalized
                       tier) for a date or date range
  - GroupRule       : a rule like "all my L2 kids should do 30 XP/day in
                       math" that gets EXPANDED to individual SetXp
                       patches at confirm time
  - ConfirmYes      : "yes" / "confirm" / "do it" reply to a pending
                       proposal posted by the bot
  - ConfirmNo       : "no" / "cancel" reply to a pending proposal
  - Refine          : free-text refinement of a pending proposal
  - Unknown         : fallback when nothing parsed; agent re-asks

All intents are immutable dataclasses with `kind` discriminators so
downstream code can pattern-match by isinstance.

Level-band vocabulary (locked per TSA):
  LL  = grades K (=0), 1
  L1  = grades 2, 3
  L2  = grades 4, 5
  L3  = grades 6, 7, 8 (synonym: MS / Middle School)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import List, Literal, Optional, Tuple, Union

# ----------------------------------------------------------------------
# Level band vocabulary (locked)
# ----------------------------------------------------------------------

LEVEL_BANDS: dict[str, Tuple[int, ...]] = {
    "LL": (0, 1),         # K, 1
    "L1": (2, 3),
    "L2": (4, 5),
    "L3": (6, 7, 8),
    "MS": (6, 7, 8),      # synonym of L3
}

# Reverse helpers for parsing free text.
_LEVEL_BAND_ALIASES: dict[str, str] = {
    "ll": "LL",
    "level low": "LL",
    "lower level": "LL",
    "k-1": "LL",
    "k/1": "LL",
    "k1": "LL",
    "l1": "L1",
    "level 1": "L1",
    "2-3": "L1",
    "2/3": "L1",
    "23": "L1",
    "l2": "L2",
    "level 2": "L2",
    "4-5": "L2",
    "4/5": "L2",
    "45": "L2",
    "l3": "L3",
    "level 3": "L3",
    "ms": "L3",
    "middle school": "L3",
    "middleschool": "L3",
    "6-8": "L3",
    "6/7/8": "L3",
}


def normalize_level_band(token: str) -> Optional[str]:
    """Canonicalize free-text level band reference to LL/L1/L2/L3.
    Returns None if the token doesn't match any known band."""
    if not token:
        return None
    t = token.strip().lower().replace("  ", " ")
    return _LEVEL_BAND_ALIASES.get(t)


def grades_for_band(band: str) -> Tuple[int, ...]:
    """Resolve LL/L1/L2/L3/MS to the concrete grade ints. Returns ()
    if band is unknown."""
    return LEVEL_BANDS.get(band, ())


# ----------------------------------------------------------------------
# Selector — defines who a group statement applies to
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class GroupSelector:
    """Describes the population a group rule applies to.

    Exactly one of `level_band`, `grades`, or `student_names` is the
    primary selector. `coach_scope` defaults to 'speaker' meaning 'the
    coach who sent this message'; head-coach broad statements set
    coach_scope='all'.
    """
    coach_scope: Literal["speaker", "all"] = "speaker"
    level_band: Optional[str] = None              # LL / L1 / L2 / L3
    grades: Tuple[int, ...] = ()                  # explicit grade ints
    student_names: Tuple[str, ...] = ()           # explicit name list

    def description(self) -> str:
        """Human-readable rendering for confirmation DMs."""
        parts: list = []
        if self.coach_scope == "all":
            parts.append("all students at the school")
        else:
            parts.append("your")
        if self.level_band:
            parts.append(self.level_band)
        if self.grades:
            parts.append("grade(s) " + ", ".join(str(g) for g in self.grades))
        if self.student_names:
            parts.append("(" + ", ".join(self.student_names) + ")")
        return " ".join(parts)


# ----------------------------------------------------------------------
# Per-intent dataclasses
# ----------------------------------------------------------------------

@dataclass(frozen=True)
class SetXp:
    kind: Literal["set_xp"] = "set_xp"
    student: str = ""
    subject: str = ""
    xp_per_day: float = 0.0
    raw_text: str = ""


@dataclass(frozen=True)
class SetTestBy:
    kind: Literal["set_test_by"] = "set_test_by"
    student: str = ""
    subject: str = ""
    target_grade: Optional[int] = None
    target_date: Optional[date] = None
    raw_text: str = ""


@dataclass(frozen=True)
class Pause:
    """A pause/exception. Covers all 4 sub-cases:
      - single day, all subjects   (date_start == date_end, subjects=())
      - single day, per-subject    (date_start == date_end, subjects=("Math",))
      - date range, all subjects   (date_start < date_end, subjects=())
      - date range, per-subject    (date_start < date_end, subjects=("Writing",))

    For group pauses (e.g. "whole roster pause Friday for field trip"),
    the agent expands the selector at confirm time into one Pause per
    student.
    """
    kind: Literal["pause"] = "pause"
    student: str = ""
    date_start: Optional[date] = None
    date_end: Optional[date] = None        # inclusive; if None, treated as same as date_start
    subjects: Tuple[str, ...] = ()          # () means "all subjects"
    reason: str = ""
    raw_text: str = ""

    @property
    def effective_end(self) -> Optional[date]:
        return self.date_end or self.date_start


@dataclass(frozen=True)
class HalfTarget:
    """Half-target modifier — applies 0.5x multiplier to Tiers 3 & 4 only
    (personalized_base, locked_base). Coach overrides remain untouched.
    """
    kind: Literal["half_target"] = "half_target"
    student: str = ""
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    subjects: Tuple[str, ...] = ()          # () means all subjects
    reason: str = ""
    raw_text: str = ""

    @property
    def effective_end(self) -> Optional[date]:
        return self.date_end or self.date_start


@dataclass(frozen=True)
class GroupRule:
    """A statement like 'all my L2 kids should do 30 XP/day in math'.

    At confirm time, the agent expands `selector` into a list of
    student names and emits one SetXp (or Pause / HalfTarget) per
    student. Group rules themselves are NEVER persisted — only the
    expanded per-student patches.
    """
    kind: Literal["group_rule"] = "group_rule"
    selector: GroupSelector = field(default_factory=GroupSelector)
    inner_kind: Literal["set_xp", "pause", "half_target"] = "set_xp"
    subject: Optional[str] = None
    xp_per_day: Optional[float] = None
    date_start: Optional[date] = None
    date_end: Optional[date] = None
    reason: str = ""
    raw_text: str = ""


@dataclass(frozen=True)
class ConfirmYes:
    kind: Literal["confirm_yes"] = "confirm_yes"
    raw_text: str = ""


@dataclass(frozen=True)
class ConfirmNo:
    kind: Literal["confirm_no"] = "confirm_no"
    raw_text: str = ""


@dataclass(frozen=True)
class Refine:
    """Free-text refinement of a pending proposal. The downstream
    handler sends this back through the parser with the original
    proposal as context."""
    kind: Literal["refine"] = "refine"
    text: str = ""
    raw_text: str = ""


@dataclass(frozen=True)
class Unknown:
    kind: Literal["unknown"] = "unknown"
    raw_text: str = ""
    reason: str = ""


# Union type for parser output.
Intent = Union[
    SetXp, SetTestBy, Pause, HalfTarget, GroupRule,
    ConfirmYes, ConfirmNo, Refine, Unknown,
]


# ----------------------------------------------------------------------
# Confirmation-word helpers (deterministic, no LLM needed)
# ----------------------------------------------------------------------

_YES_TOKENS = {
    "yes", "y", "yep", "yeah", "yup", "sure", "confirm", "confirmed",
    "do it", "go", "go ahead", "proceed", "ok", "okay", "k", "approved",
    "lgtm", "looks good", "sounds good", "ship it",
}
_NO_TOKENS = {
    "no", "n", "nope", "cancel", "cancelled", "stop", "abort",
    "don't", "do not", "never mind", "nevermind", "scratch that",
}


def is_yes(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower().rstrip(".!")
    return t in _YES_TOKENS


def is_no(text: str) -> bool:
    if not text:
        return False
    t = text.strip().lower().rstrip(".!")
    return t in _NO_TOKENS
