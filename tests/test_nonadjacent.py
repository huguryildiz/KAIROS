"""Guard for the theory different-day soft penalty.

A section's theory sessions prefer different days, but the solver may place them
on the same day when there is no legal alternative.
"""
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat
from timetabling.validate import validate


def _make_section():
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["a"], 10, 0, 0, 0, 0, "Course")
    s.blocks = [Block("S_01#T1", "S_01", "theory", 2, False),
                Block("S_01#T2", "S_01", "theory", 2, False)]
    return s


def test_two_theory_sessions_same_day_when_only_one_day_open():
    """Only Monday open -> two theory sessions share Monday instead of making CP-SAT infeasible."""
    closed = tuple((day, h) for day in ("Tu", "We", "Th", "Fr") for h in range(9, 18))
    cfg = Config(w_cohort_gap=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0,
                 blackout=closed)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    assigns, stats = model_cpsat.build_and_solve([_make_section()], rooms, instr, cfg)
    assert stats["status_name"] in {"OPTIMAL", "FEASIBLE"}, stats
    assert len(assigns) == 2
    assert {a.day for a in assigns} == {"Mo"}
    assert validate(assigns, [_make_section()], {"R1": rooms[0]}, instr, cfg) == []


def test_theory_sessions_spread_across_days():
    """All days open -> the two theory sessions still prefer different days."""
    cfg = Config(w_cohort_gap=0, w_instr_days=0, w_parttime_days=0,
                 w_order=0, w_englab=0, w_nonadjacent=10)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    assigns, stats = model_cpsat.build_and_solve([_make_section()], rooms, instr, cfg)
    assert len(assigns) == 2
    assert assigns[0].day != assigns[1].day
