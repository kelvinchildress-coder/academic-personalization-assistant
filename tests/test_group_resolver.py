import json
import tempfile
from pathlib import Path

from src.agent.group_resolver import resolve
from src.agent.intents import GroupSelector


def _write(d: Path, name: str, payload):
    p = d / name
    p.write_text(json.dumps(payload))
    return p


def _fixture_dir():
    d = Path(tempfile.mkdtemp(prefix="group_resolver_test_"))
    _write(d, "coaches.json", {
        "coaches": {
            "Lisa C Willis": {"students": ["Marcus Allen", "Layla Smith", "Cooper Gregston"]},
            "Amir Lewis":    {"students": ["Aksel Jensen", "Allison Kim"]},
        }
    })
    _write(d, "students.json", {
        "version": "1",
        "students": {
            "Marcus Allen":     {"age_grade": 4},
            "Layla Smith":      {"age_grade": 5},
            "Cooper Gregston":  {"age_grade": 2},
            "Aksel Jensen":     {"age_grade": 6},
            "Allison Kim":      {"age_grade": 7},
        },
    })
    return d


def test_speaker_scope_returns_only_their_roster():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker")
    out = resolve(sel, "Lisa C Willis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert set(out) == {"Marcus Allen", "Layla Smith", "Cooper Gregston"}


def test_speaker_scope_with_l2_band_filters_to_grades_4_5():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker", level_band="L2")
    out = resolve(sel, "Lisa C Willis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert set(out) == {"Marcus Allen", "Layla Smith"}


def test_speaker_scope_with_l1_band_filters_to_grades_2_3():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker", level_band="L1")
    out = resolve(sel, "Lisa C Willis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert out == ["Cooper Gregston"]


def test_speaker_scope_with_ms_band_includes_only_amir_kids():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker", level_band="MS")
    out = resolve(sel, "Amir Lewis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert set(out) == {"Aksel Jensen", "Allison Kim"}


def test_all_scope_returns_school_wide_filtered():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="all", level_band="L2")
    out = resolve(sel, "Kelvin Childress",  # head coach
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert set(out) == {"Marcus Allen", "Layla Smith"}


def test_explicit_names_intersect_with_speaker_roster():
    d = _fixture_dir()
    sel = GroupSelector(student_names=("Marcus Allen", "Aksel Jensen"))
    out = resolve(sel, "Lisa C Willis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    # Aksel is NOT on Lisa's roster, so intersection drops him
    assert out == ["Marcus Allen"]


def test_explicit_grades_filter():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker", grades=(4,))
    out = resolve(sel, "Lisa C Willis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert out == ["Marcus Allen"]


def test_no_filter_returns_all_speaker_kids():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker")
    out = resolve(sel, "Amir Lewis",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert set(out) == {"Aksel Jensen", "Allison Kim"}


def test_unknown_coach_returns_empty():
    d = _fixture_dir()
    sel = GroupSelector(coach_scope="speaker", level_band="L2")
    out = resolve(sel, "Nonexistent Coach",
                  coaches_path=d / "coaches.json",
                  students_path=d / "students.json")
    assert out == []
