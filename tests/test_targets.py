from datetime import date

from src.models import LOCKED_XP_RULES, Student, TestOutGoal
from src.targets import (
    base_target,
    student_subject_target,
    all_subject_targets,
)


def test_base_target_locked_rules():
    assert base_target("Math") == 25
    assert base_target("Reading") == 25
    assert base_target("Language") == 25
    assert base_target("Writing") == 12.5
    assert base_target("Science") == 12.5
    assert base_target("Vocabulary") == 10
    assert base_target("FastMath") == 10


def test_unknown_subject_returns_zero():
    assert base_target("Underwater Basket Weaving") == 0


def test_default_student_uses_locked_rules():
    s = Student(name="Aaron M")
    targets = all_subject_targets(s, today=date(2026, 5, 4))
    assert targets == LOCKED_XP_RULES


def test_override_replaces_base():
    s = Student(name="Aaron M", xp_overrides={"Math": 30})
    assert student_subject_target(s, "Math", date(2026, 5, 4)) == 30
    # Other subjects untouched
    assert student_subject_target(s, "Reading", date(2026, 5, 4)) == 25


def test_test_out_goal_back_solves_to_per_day():
    # Goal: 100 XP needed in Math by Fri 5/8 (today Mon 5/4) = 4 school days
    # remaining strictly after today (Tue Wed Thu Fri).
    s = Student(
        name="Aaron M",
        test_out_goal=TestOutGoal(subject="Math", target_xp=100, target_date="2026-05-08"),
    )
    target = student_subject_target(s, "Math", date(2026, 5, 4))
    assert target == 25  # 100 / 4


def test_test_out_goal_caps_at_4x_base():
    # Want 1000 Math XP by tomorrow (1 school day remaining): per-day would be
    # 1000, but cap is 4 * base (25) = 100.
    s = Student(
        name="Aaron M",
        test_out_goal=TestOutGoal(subject="Math", target_xp=1000, target_date="2026-05-05"),
    )
    target = student_subject_target(s, "Math", date(2026, 5, 4))
    assert target == 100


def test_test_out_goal_subtracts_starting_xp():
    s = Student(
        name="Aaron M",
        test_out_goal=TestOutGoal(
            subject="Math", target_xp=200, target_date="2026-05-08", starting_xp=100,
        ),
    )
    # Remaining = 200 - 100 = 100 over 4 days = 25
    target = student_subject_target(s, "Math", date(2026, 5, 4), starting_xp_in_subject=100)
    assert target == 25


def test_test_out_goal_for_other_subject_doesnt_affect_this_one():
    s = Student(
        name="Aaron M",
        test_out_goal=TestOutGoal(subject="Reading", target_xp=999, target_date="2026-05-08"),
    )
    # Math should still be base 25, not affected by the Reading goal.
    assert student_subject_target(s, "Math", date(2026, 5, 4)) == 25
