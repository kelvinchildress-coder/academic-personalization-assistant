from datetime import date

from src.agent.intents import (
    GroupSelector,
    HalfTarget,
    LEVEL_BANDS,
    Pause,
    SetXp,
    grades_for_band,
    is_no,
    is_yes,
    normalize_level_band,
)


def test_level_band_constants_match_locked_spec():
    assert LEVEL_BANDS["LL"] == (0, 1)
    assert LEVEL_BANDS["L1"] == (2, 3)
    assert LEVEL_BANDS["L2"] == (4, 5)
    assert LEVEL_BANDS["L3"] == (6, 7, 8)
    assert LEVEL_BANDS["MS"] == (6, 7, 8)


def test_normalize_level_band_aliases():
    assert normalize_level_band("LL") == "LL"
    assert normalize_level_band("ll") == "LL"
    assert normalize_level_band("K-1") == "LL"
    assert normalize_level_band("L2") == "L2"
    assert normalize_level_band("level 2") == "L2"
    assert normalize_level_band("4-5") == "L2"
    assert normalize_level_band("MS") == "L3"
    assert normalize_level_band("middle school") == "L3"
    assert normalize_level_band("L3") == "L3"


def test_normalize_level_band_unknown_returns_none():
    assert normalize_level_band("L7") is None
    assert normalize_level_band("") is None
    assert normalize_level_band(None) is None  # type: ignore[arg-type]


def test_grades_for_band_resolution():
    assert grades_for_band("LL") == (0, 1)
    assert grades_for_band("L2") == (4, 5)
    assert grades_for_band("MS") == (6, 7, 8)
    assert grades_for_band("nonsense") == ()


def test_yes_no_token_recognition():
    for t in ["yes", "Yes", "YES.", "y", "yep", "confirm", "do it", "go ahead", "ok", "lgtm"]:
        assert is_yes(t), f"expected yes for {t!r}"
    for t in ["no", "No.", "n", "nope", "cancel", "abort", "don't", "scratch that"]:
        assert is_no(t), f"expected no for {t!r}"
    assert not is_yes("maybe")
    assert not is_no("maybe")
    assert not is_yes("")
    assert not is_no("")


def test_group_selector_description_speaker_with_band():
    sel = GroupSelector(coach_scope="speaker", level_band="L2")
    assert "your" in sel.description()
    assert "L2" in sel.description()


def test_group_selector_description_all_with_grades():
    sel = GroupSelector(coach_scope="all", grades=(4, 5))
    desc = sel.description()
    assert "all students" in desc
    assert "4" in desc and "5" in desc


def test_group_selector_description_explicit_names():
    sel = GroupSelector(student_names=("Marcus Allen", "Layla Smith"))
    desc = sel.description()
    assert "Marcus Allen" in desc
    assert "Layla Smith" in desc


def test_pause_effective_end_defaults_to_start_when_end_missing():
    p = Pause(student="Marcus Allen", date_start=date(2026, 9, 15))
    assert p.effective_end == date(2026, 9, 15)


def test_pause_effective_end_uses_explicit_range():
    p = Pause(
        student="Marcus Allen",
        date_start=date(2026, 9, 15),
        date_end=date(2026, 9, 17),
    )
    assert p.effective_end == date(2026, 9, 17)


def test_half_target_per_subject_scope_preserved():
    h = HalfTarget(
        student="Marcus Allen",
        date_start=date(2026, 9, 15),
        subjects=("Math", "Reading"),
        reason="reduced expectations this week",
    )
    assert h.subjects == ("Math", "Reading")
    assert h.kind == "half_target"


def test_set_xp_basic_construction():
    intent = SetXp(student="Marcus Allen", subject="Math", xp_per_day=30)
    assert intent.kind == "set_xp"
    assert intent.xp_per_day == 30
