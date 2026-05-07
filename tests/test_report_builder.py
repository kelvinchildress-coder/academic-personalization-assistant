from datetime import date

from src.models import (
    Coach,
    CoachRoster,
    Student,
    SubjectResult,
    StudentDailyResult,
)
from src.report_builder import (
    build_morning_parent_text,
    build_coach_reply_text,
    build_head_coach_digest,
    build_eod_summary,
    detect_new_live_events,
    build_live_update_reply,
)


def _make_result(name, xp=0, accuracy=0, target=25, low=False, over=False):
    """Helper. low=True forces low_accuracy, over=True forces overperform."""
    if low:
        accuracy = 50
        xp = 5  # nonzero so is_low_accuracy triggers
    if over:
        xp = target * 1.4
    sub = SubjectResult(
        name="Math", xp=xp, accuracy=accuracy, minutes=10, target_xp=target,
    )
    return StudentDailyResult(
        name=name, date="2026-05-04", subjects=[sub], absent=False,
    )


def test_morning_parent_format():
    text = build_morning_parent_text(date(2026, 5, 4))
    assert "Morning Report" in text
    assert "Mon" in text


def test_coach_reply_with_mention():
    students = [_make_result("Aaron M", xp=0, accuracy=0)]
    text = build_coach_reply_text("Amir Lewis", "U123", students)
    assert "<@U123>" in text
    assert "Aaron M" in text


def test_coach_reply_falls_back_to_plain_name_when_no_id():
    students = [_make_result("Aaron M")]
    text = build_coach_reply_text("Amir Lewis", None, students)
    assert "Amir Lewis" in text
    assert "<@" not in text


def test_detect_live_events_low_accuracy():
    r = _make_result("Aaron M", low=True)
    events = detect_new_live_events([r], already_posted=set())
    assert len(events) == 1
    _, _, kind = events[0]
    assert kind == "low_accuracy"


def test_detect_live_events_overperform():
    r = _make_result("Aaron M", over=True)
    events = detect_new_live_events([r], already_posted=set())
    kinds = [k for _, _, k in events]
    assert "overperform" in kinds


def test_detect_live_events_dedupe():
    r = _make_result("Aaron M", over=True)
    events1 = detect_new_live_events([r], already_posted=set())
    posted = {f"{r.date}|{r.name}|{r.subjects[0].name}|overperform"}
    events2 = detect_new_live_events([r], already_posted=posted)
    assert events1 and not events2


def test_live_update_reply_low_accuracy_text():
    r = _make_result("Aaron M", low=True)
    text = build_live_update_reply("U123", "Amir Lewis", r.name, r.subjects[0], "low_accuracy")
    assert "Aaron M" in text and "Math" in text and "rotating_light" in text


def test_eod_summary_all_green():
    # Hit target + no low accuracy = green
    r = StudentDailyResult(
        name="Aaron M", date="2026-05-04",
        subjects=[SubjectResult(name="Math", xp=25, accuracy=90, minutes=10, target_xp=25)],
    )
    roster = CoachRoster(head_coach="Kelvin", coaches=[Coach("Amir", ["Aaron M"])])
    text = build_eod_summary(date(2026, 5, 4), [r], roster, {})
    assert "Every student finished the day Green" in text


def test_eod_summary_lists_misses_grouped_by_coach():
    miss = _make_result("Aaron M", xp=10, accuracy=80, target=25)
    roster = CoachRoster(head_coach="Kelvin", coaches=[Coach("Amir Lewis", ["Aaron M"])])
    text = build_eod_summary(date(2026, 5, 4), [miss], roster, {"Amir Lewis": "U999"})
    assert "<@U999>" in text
    assert "Aaron M" in text


def test_head_coach_digest_calls_out_flagged_and_overperformers():
    flagged = _make_result("Brooke S", low=True)
    over = _make_result("Carla R", over=True)
    text = build_head_coach_digest("Kelvin", "U_KELVIN", [flagged, over])
    assert "<@U_KELVIN>" in text
    assert "Brooke S" in text
    assert "Carla R" in text
