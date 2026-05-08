"""
scripts/grade_xp_collector.py
=============================

Hourly cron that polls TimeBack for the total XP required at every
(grade, subject) pair and writes the merged result into
config/grade_xp.json.

Designed to be tolerant: if the API is not yet configured (no token, or
USE_REAL_API still False in src/timeback_api.py), this script logs a
noop and exits 0. The cron can therefore be enabled before the API is
ready without spamming failures.

Two data sources merged into config/grade_xp.json:

  1. The direct grade-XP-total endpoint (preferred). If a value is
     returned, it overwrites whatever was previously in the config.

  2. As a fallback, opportunistic harvesting from the daily bookmarklet
     export (data/latest.json). When a student's row carries
     {current_grade, remaining_xp_to_grade_end, total_xp_in_grade},
     we can derive the grade-total. Today the bookmarklet only emits
     the first two; we keep the slot open.

Idempotent: multiple runs in a day converge on the same file. We never
write None back over a real number, so a transient API miss is harmless.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from src.timeback_api import TimeBackAPIClient        # noqa: E402
from src.student_progress import (                    # noqa: E402
    ALL_SUBJECTS,
    grade_int_to_key,
    grade_key_to_int,
    normalize_subject,
)


CONFIG_PATH = REPO_ROOT / "config" / "grade_xp.json"
LATEST_PATH = REPO_ROOT / "data" / "latest.json"


def _load_existing() -> Dict[str, Any]:
    if not CONFIG_PATH.exists():
        return {
            "version": 1,
            "last_updated": None,
            "source": "scripts/grade_xp_collector.py",
            "grades": {},
        }
    return json.loads(CONFIG_PATH.read_text())


def _ensure_skeleton(blob: Dict[str, Any]) -> Dict[str, Any]:
    """Make sure every (grade_key, subject) slot exists with at least None."""
    grades = blob.setdefault("grades", {})
    # K + 1st..12th
    for gi in range(0, 13):
        key = grade_int_to_key(gi)
        if key is None:
            continue
        slot = grades.setdefault(key, {})
        for s in ALL_SUBJECTS:
            slot.setdefault(s, None)
    return blob


def _harvest_from_latest(
    blob: Dict[str, Any],
) -> int:
    """Opportunistic backfill from data/latest.json. Returns the number
    of cells filled. Today this is a no-op because the bookmarklet does
    not yet emit grade-totals; the function is here so the contract is
    ready when the bookmarklet is updated."""
    if not LATEST_PATH.exists():
        return 0
    try:
        raw = json.loads(LATEST_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return 0
    filled = 0
    for student in raw.get("students") or []:
        for subj_row in student.get("subjects") or []:
            canon = normalize_subject(subj_row.get("name"))
            if canon is None:
                continue
            grade = subj_row.get("current_grade")
            total_for_grade = subj_row.get("total_xp_in_grade")
            if grade is None or total_for_grade is None:
                continue
            gi = grade if isinstance(grade, int) else grade_key_to_int(str(grade))
            if gi is None:
                continue
            key = grade_int_to_key(gi)
            slot = blob["grades"].setdefault(key, {})
            cur = slot.get(canon)
            if cur is None or float(cur) <= 0:
                slot[canon] = float(total_for_grade)
                filled += 1
    return filled


def _harvest_from_api(
    blob: Dict[str, Any],
    client: TimeBackAPIClient,
) -> int:
    if not client.is_configured:
        return 0
    filled = 0
    for gi in range(0, 13):
        key = grade_int_to_key(gi)
        if key is None:
            continue
        for subject in ALL_SUBJECTS:
            val: Optional[float] = client.fetch_grade_xp_total(gi, subject)
            if val is None:
                continue
            slot = blob["grades"].setdefault(key, {})
            cur = slot.get(subject)
            # Only overwrite when we have a real number and it differs.
            if cur is None or float(cur) != float(val):
                slot[subject] = float(val)
                filled += 1
    return filled


def main() -> int:
    client = TimeBackAPIClient()
    blob = _ensure_skeleton(_load_existing())

    api_filled = _harvest_from_api(blob, client)
    latest_filled = _harvest_from_latest(blob)

    if not client.is_configured and latest_filled == 0:
        print(
            "NOOP: TimeBack API not configured (no TIMEBACK_API_TOKEN or "
            "USE_REAL_API=False) and no harvestable values in data/latest.json. "
            "Skipping write."
        )
        return 0

    blob["last_updated"] = datetime.now(timezone.utc).isoformat()
    CONFIG_PATH.write_text(json.dumps(blob, indent=2, sort_keys=True) + "\n")
    print(
        f"OK: wrote {CONFIG_PATH.relative_to(REPO_ROOT)}  "
        f"(api_filled={api_filled}, latest_filled={latest_filled})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
