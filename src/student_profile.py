"""
src/student_profile.py
Extended student profile data (current grade per subject, age grade, year-start
grade snapshot, manual test-out goals, manual test-out dates).

Kept separate from src/models.py to avoid mutating frozen dataclasses there.
A StudentProfile is keyed by student NAME and merges with the basic Student
model at lookup time inside src/test_out_goals.py and src/targets.py.

Source of truth: config/students.json. Schema:

{
  "version": "1",
  "as_of": "ISO date the profiles were last refreshed",
  "students": {
    "Andie Childress": {
      "age_grade": "4th",
      "current_grade_per_subject": {
        "Math": "5th", "Reading": "4th", "Language": "4th",
        "Writing": "3rd", "Science": "4th",
        "FastMath": null, "Vocabulary": null
      },
      "year_start_grade_per_subject": {  // snapshot taken at SY start; never moves up mid-year
        "Math": "4th", "Reading": "3rd", "Language": "4th",
        "Writing": "3rd", "Science": "4th",
        "FastMath": null, "Vocabulary": null
      },
      "manual_test_out_grade": {       // optional per-subject coach override
        "Math": "6th"
      },
      "manual_test_out_date": {        // optional per-subject coach override (ISO)
        "Math": "2027-01-26"
      }
    },
    ...
  }
}

All fields are optional. Missing fields fall back to the cascade in
src/test_out_goals.py.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


DEFAULT_PATH = Path(__file__).resolve().parent.parent / "config" / "students.json"


@dataclass
class StudentProfile:
    name: str
    age_grade: Optional[str] = None
    current_grade_per_subject: dict[str, Optional[str]] = field(default_factory=dict)
    year_start_grade_per_subject: dict[str, Optional[str]] = field(default_factory=dict)
    manual_test_out_grade: dict[str, str] = field(default_factory=dict)
    manual_test_out_date: dict[str, str] = field(default_factory=dict)

    def to_target_input(self) -> dict:
        """Shape expected by src.test_out_goals.resolve_target(..., student=...)."""
        return {
            "name": self.name,
            "age_grade": self.age_grade,
            "current_grade_per_subject": dict(self.current_grade_per_subject),
            "year_start_grade_per_subject": dict(self.year_start_grade_per_subject),
            "manual_test_out_grade": dict(self.manual_test_out_grade),
            "manual_test_out_date": dict(self.manual_test_out_date),
        }

    @classmethod
    def from_dict(cls, name: str, d: dict) -> "StudentProfile":
        return cls(
            name=name,
            age_grade=d.get("age_grade"),
            current_grade_per_subject=dict(d.get("current_grade_per_subject") or {}),
            year_start_grade_per_subject=dict(d.get("year_start_grade_per_subject") or {}),
            manual_test_out_grade=dict(d.get("manual_test_out_grade") or {}),
            manual_test_out_date=dict(d.get("manual_test_out_date") or {}),
        )


@dataclass
class StudentProfileBook:
    """Collection keyed by student name. Empty book is valid."""
    version: str = "1"
    as_of: Optional[str] = None
    profiles: dict[str, StudentProfile] = field(default_factory=dict)

    def get(self, name: str) -> StudentProfile:
        """Return the profile, or an empty one if missing (graceful fallback)."""
        return self.profiles.get(name) or StudentProfile(name=name)

    def has_complete_profile(self, name: str, required_subjects: list[str]) -> bool:
        """A profile is "complete" when age_grade is set AND every required
        subject has both a current_grade and a year_start_grade. Used by the
        agent to know which students still need coach clarification.
        """
        p = self.profiles.get(name)
        if p is None or not p.age_grade:
            return False
        for s in required_subjects:
            cg = p.current_grade_per_subject.get(s)
            ys = p.year_start_grade_per_subject.get(s)
            if not cg or not ys:
                return False
        return True

    def missing_fields(self, name: str, required_subjects: list[str]) -> list[str]:
        """Return list of human-readable missing-field labels for the agent."""
        p = self.profiles.get(name) or StudentProfile(name=name)
        missing = []
        if not p.age_grade:
            missing.append("age_grade")
        for s in required_subjects:
            if not p.current_grade_per_subject.get(s):
                missing.append(f"current_grade_per_subject[{s}]")
            if not p.year_start_grade_per_subject.get(s):
                missing.append(f"year_start_grade_per_subject[{s}]")
        return missing

    @classmethod
    def from_dict(cls, d: dict) -> "StudentProfileBook":
        students_raw = d.get("students") or {}
        profiles = {n: StudentProfile.from_dict(n, v) for n, v in students_raw.items()}
        return cls(
            version=str(d.get("version", "1")),
            as_of=d.get("as_of"),
            profiles=profiles,
        )

    def to_dict(self) -> dict:
        out_students: dict[str, dict] = {}
        for n, p in self.profiles.items():
            out_students[n] = {
                "age_grade": p.age_grade,
                "current_grade_per_subject": dict(p.current_grade_per_subject),
                "year_start_grade_per_subject": dict(p.year_start_grade_per_subject),
                "manual_test_out_grade": dict(p.manual_test_out_grade),
                "manual_test_out_date": dict(p.manual_test_out_date),
            }
        return {"version": self.version, "as_of": self.as_of, "students": out_students}


def load_student_profiles(path: Optional[Path] = None) -> StudentProfileBook:
    p = Path(path) if path else DEFAULT_PATH
    if not p.exists():
        return StudentProfileBook()
    with p.open("r", encoding="utf-8") as f:
        return StudentProfileBook.from_dict(json.load(f))


def save_student_profiles(book: StudentProfileBook, path: Optional[Path] = None) -> None:
    p = Path(path) if path else DEFAULT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        json.dump(book.to_dict(), f, indent=2, sort_keys=True)
        f.write("\n")
