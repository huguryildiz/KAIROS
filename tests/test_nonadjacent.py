"""Guard for the theory different-day rule (now a HARD constraint).

A section's theory sessions (T:3 -> 2+1) must each be on a different day. The
old soft `w_nonadjacent` term still exists but is superseded for theory by this
hard constraint.
"""
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def _make_section():
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["a"], 10, 0, 0, 0, 0, "Course")
    s.blocks = [Block("S_01#T1", "S_01", "theory", 2, False),
                Block("S_01#T2", "S_01", "theory", 2, False)]
    return s


def test_two_theory_sessions_infeasible_when_one_day_open():
    """Only Monday open -> two theory sessions cannot get different days -> INFEASIBLE
    in the single-shot solver (the repair solver instead leaves one unplaced)."""
    closed = tuple((day, h) for day in ("Tu", "We", "Th", "Fr") for h in range(9, 18))
    cfg = Config(w_cohort_gap=0, w_evening=0, w_room_count=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0,
                 blackout=closed)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    assigns, stats = model_cpsat.build_and_solve([_make_section()], rooms, instr, cfg)
    assert stats["status_name"] == "INFEASIBLE", stats


def test_theory_sessions_spread_across_days():
    """All days open -> the two theory sessions land on different days (hard rule)."""
    cfg = Config(w_cohort_gap=0, w_evening=0, w_room_count=0)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    assigns, stats = model_cpsat.build_and_solve([_make_section()], rooms, instr, cfg)
    assert len(assigns) == 2
    assert assigns[0].day != assigns[1].day
