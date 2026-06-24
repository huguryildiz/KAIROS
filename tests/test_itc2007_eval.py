"""Tests for ITC-2007 objective evaluator."""
import pytest
from timetabling.model import Assignment
from timetabling.io_itc2007 import ItcInstance, ItcCourse, ItcRoom
from timetabling.eval_itc2007 import evaluate_itc2007


def _inst():
    return ItcInstance(
        name="test",
        num_days=5,
        periods_per_day=4,
        courses={
            "c1": ItcCourse("c1", "t1", 2, 2, 10, False),
            "c2": ItcCourse("c2", "t2", 1, 1, 50, False),
        },
        rooms={
            "r1": ItcRoom("r1", 20, 0),
            "r2": ItcRoom("r2", 100, 0),
        },
        curricula={"q1": ["c1", "c2"]},
        unavailability=[],
        room_constraints=[],
    )


def _a(course_id, lecture, room, day, period):
    sid = f"{course_id}_L{lecture:02d}"
    return Assignment(
        block_id=f"{sid}#T", section_id=sid, kind="theory",
        room=room, day=day, start=period, end=period + 1,
    )


def test_s1_room_capacity():
    # c2: 50 students, r1 cap=20 → 30 penalty
    assignments = [
        _a("c1", 0, "r2", "Mo", 0),
        _a("c1", 1, "r2", "Tu", 0),
        _a("c2", 0, "r1", "We", 0),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["s1"] == 30


def test_s2_min_working_days():
    # c1 needs min 2 days; both lectures on Monday → 1 actual day → penalty 5
    assignments = [
        _a("c1", 0, "r2", "Mo", 0),
        _a("c1", 1, "r2", "Mo", 1),
        _a("c2", 0, "r2", "Tu", 0),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["s2"] == 5


def test_s3_isolated_lecture():
    # q1 = {c1, c2}; all three lectures on different days with no adjacency → all isolated
    assignments = [
        _a("c1", 0, "r2", "Mo", 0),
        _a("c1", 1, "r2", "Tu", 2),
        _a("c2", 0, "r2", "We", 2),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["s3"] == 6   # 3 isolated × 2


def test_s3_not_isolated_when_adjacent():
    # All on Monday consecutive: p0, p1, p2 → chain, none isolated
    assignments = [
        _a("c1", 0, "r2", "Mo", 0),
        _a("c1", 1, "r2", "Mo", 1),
        _a("c2", 0, "r2", "Mo", 2),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["s3"] == 0


def test_s4_room_stability():
    # c1 uses r1 and r2 → 1 penalty; c2 uses r1 only → 0
    assignments = [
        _a("c1", 0, "r1", "Mo", 0),
        _a("c1", 1, "r2", "Tu", 0),
        _a("c2", 0, "r1", "We", 0),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["s4"] == 1


def test_hard_room_overlap():
    assignments = [
        _a("c1", 0, "r1", "Mo", 0),
        _a("c2", 0, "r1", "Mo", 0),   # same room, same slot
        _a("c1", 1, "r2", "Tu", 0),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["hard_violations"]["room_overlap"] >= 1


def test_total_is_sum():
    assignments = [
        _a("c1", 0, "r2", "Mo", 0),
        _a("c1", 1, "r2", "Tu", 0),
        _a("c2", 0, "r2", "We", 0),
    ]
    result = evaluate_itc2007(assignments, _inst())
    assert result["total"] == result["s1"] + result["s2"] + result["s3"] + result["s4"]
