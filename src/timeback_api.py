"""
timeback_api.py
===============

Single seam for all TimeBack API access. Until the API token + endpoint
shape are confirmed, this module exposes a structured client whose two
data-fetching methods raise NotImplementedError when run without a token
and return safe defaults when the token is absent.

The contract:

  TimeBackAPIClient.is_configured -> bool
  TimeBackAPIClient.fetch_grade_xp_total(grade_int, subject) -> Optional[float]
  TimeBackAPIClient.fetch_student_cumulative_xp(student_name, subject) -> Optional[float]

Both methods MUST be safe to call without a token: they return None
(meaning "unknown") so downstream callers can fall through the cascade
gracefully.

When you have API docs, fill in the two `_real_*` private methods and
flip USE_REAL_API to True. No other file in the project needs to change.
"""

from __future__ import annotations

import os
from typing import Optional

# Flip to True when _real_* methods are implemented.
USE_REAL_API = False

# Recognized canonical subjects (kept aligned with student_progress.ALL_SUBJECTS).
_KNOWN_SUBJECTS = (
    "Math", "Reading", "Language", "Writing", "Science",
    "Vocabulary", "FastMath",
)


class TimeBackAPIClient:
    """Thin wrapper around the TimeBack HTTP API.

    This client is intentionally side-effect-free at construction time so
    it can be safely instantiated in environments where the token is not
    set (CI dry-runs, local tests, etc.).
    """

    def __init__(
        self,
        token: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout_seconds: float = 15.0,
    ):
        self.token = token or os.environ.get("TIMEBACK_API_TOKEN")
        self.base_url = (
            base_url
            or os.environ.get("TIMEBACK_API_BASE_URL")
            or "https://alpha.timeback.com/api"
        ).rstrip("/")
        self.timeout_seconds = float(timeout_seconds)

    @property
    def is_configured(self) -> bool:
        return bool(self.token) and USE_REAL_API

    # ------------------------------------------------------------------ #
    # Public methods (always safe to call)                               #
    # ------------------------------------------------------------------ #

    def fetch_grade_xp_total(
        self, grade: int, subject: str
    ) -> Optional[float]:
        """Total XP required at (grade, subject) to be considered
        'mastered' for that grade/subject.

        Returns None when the API is not configured OR the value is
        unknown for that pair.
        """
        if not self.is_configured:
            return None
        if subject not in _KNOWN_SUBJECTS:
            return None
        try:
            return self._real_fetch_grade_xp_total(int(grade), str(subject))
        except NotImplementedError:
            return None

    def fetch_student_cumulative_xp(
        self, student_name: str, subject: str
    ) -> Optional[float]:
        """Cumulative XP a student has accumulated *within their current
        grade* for `subject`. Used by targets.py Tier 1 to compute
        remaining XP. Returns None when unknown."""
        if not self.is_configured:
            return None
        if subject not in _KNOWN_SUBJECTS:
            return None
        try:
            return self._real_fetch_student_cumulative_xp(
                str(student_name), str(subject)
            )
        except NotImplementedError:
            return None

    # ------------------------------------------------------------------ #
    # Private — IMPLEMENT WHEN API DOCS ARE AVAILABLE                    #
    # ------------------------------------------------------------------ #

    def _real_fetch_grade_xp_total(
        self, grade: int, subject: str
    ) -> Optional[float]:
        """
        IMPLEMENTATION NOTES (for the next agent who has API access):

        Likely endpoint shape (based on the QTI API doc tab observed in
        the user's browser session):

          GET {base_url}/learning-metrics/grades/{grade}/subjects/{subject}
          Headers: Authorization: Bearer {token}
          Response (assumed):
            {
              "grade": "5th",
              "subject": "Math",
              "total_xp": 1240.0,
              "as_of": "2026-05-01T00:00:00Z"
            }

        If the real endpoint differs, update this method and keep the
        return contract: a positive float, or None if not available.
        """
        raise NotImplementedError(
            "Set USE_REAL_API=True and implement _real_fetch_grade_xp_total."
        )

    def _real_fetch_student_cumulative_xp(
        self, student_name: str, subject: str
    ) -> Optional[float]:
        """
        Likely endpoint shape:

          GET {base_url}/students/{student_id_or_name}/cumulative-xp
            ?subject={subject}
          Headers: Authorization: Bearer {token}
          Response (assumed):
            {
              "student": "Mason McDougald",
              "subject": "Math",
              "current_grade": "5th",
              "cumulative_xp_in_grade": 412.0,
              "as_of": "2026-05-04T07:00:00Z"
            }

        Note: TimeBack identifies students by UUID internally. We
        currently only have display names; you may need a one-time
        name->id lookup table built from /students.
        """
        raise NotImplementedError(
            "Set USE_REAL_API=True and implement _real_fetch_student_cumulative_xp."
        )
