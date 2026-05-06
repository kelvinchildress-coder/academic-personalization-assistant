"""Static configuration for Texas Sports Academy (TSA).

Single source of truth for:
- Campus identity
- Coach roster (name + canonical short id)
- Supervisor (Kelvin)
- Slack channel for reports
- Schedule times (morning report, end-of-day report) in America/Chicago

Coach Slack user IDs are NOT hardcoded here. The Slack bot resolves them at
runtime via users.list() so we never have to hand-collect or hand-edit IDs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

# ---------------------------------------------------------------------------
# Campus
# ---------------------------------------------------------------------------

CAMPUS_NAME = "Texas Sports Academy"
CAMPUS_SHORT = "TSA"
CAMPUS_TIMEZONE = "America/Chicago"
CAMPUS_CALENDAR = "A"  # TSA uses Calendar A on the SY25-26 master calendar


# ---------------------------------------------------------------------------
# People
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Coach:
    """A coach (a.k.a. Guide on other campuses) responsible for a roster."""

    full_name: str
    first_name: str
    short_id: str  # stable lookup key, lowercase, used in JSON files

    @property
    def display_name(self) -> str:
        return self.full_name


@dataclass(frozen=True)
class Supervisor:
    """A campus supervisor; receives daily digests but is not a coach."""

    full_name: str
    first_name: str
    short_id: str


COACHES: List[Coach] = [
    Coach("Amir Lewis", "Amir", "amir_lewis"),
    Coach("Cait Arzu", "Cait", "cait_arzu"),
    Coach("DJ Tripoli", "DJ", "dj_tripoli"),
    Coach("Ella Alexander", "Ella", "ella_alexander"),
    Coach("Graham Spraker", "Graham", "graham_spraker"),
    Coach("Greg Annan", "Greg", "greg_annan"),
    Coach("Lisa C Willis", "Lisa", "lisa_c_willis"),
]

SUPERVISOR = Supervisor("Kelvin Childress", "Kelvin", "kelvin_childress")


def coach_by_short_id(short_id: str) -> Coach | None:
    for c in COACHES:
        if c.short_id == short_id:
            return c
    return None


def coach_by_full_name(full_name: str) -> Coach | None:
    norm = full_name.strip().lower()
    for c in COACHES:
        if c.full_name.lower() == norm:
            return c
    return None


# ---------------------------------------------------------------------------
# Slack
# ---------------------------------------------------------------------------

SLACK_REPORT_CHANNEL = "sports"  # bare channel name; bot resolves to ID at runtime


# ---------------------------------------------------------------------------
# Schedule (local times in CAMPUS_TIMEZONE)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DailyJob:
    name: str
    hour: int   # 0-23, local to CAMPUS_TIMEZONE
    minute: int


MORNING_REPORT = DailyJob("morning_report", 7, 0)
END_OF_DAY_REPORT = DailyJob("end_of_day", 15, 0)
LIVE_REFRESH_INTERVAL_MINUTES = 15


# ---------------------------------------------------------------------------
# Accuracy floor
# ---------------------------------------------------------------------------

ACCURACY_FLAG_THRESHOLD = 0.60  # auto-flag any subject below this in a window
