"""Regression guard for the non-adjacent split-day soft term (Task 10).

Two sub-tests:

1. objective_guard — block all days except Monday so both 2h blocks are
   forced onto the same day.  With w_nonadjacent=100 the expected objective
   is exactly 100 (one same-day excess).  If the term is removed from the
   objective this assertion fails (objective would be 0.0).

2. spread_test — with all days open and w_nonadjacent=100, the solver should
   push the two blocks onto *different* days (cost 0 < cost 100 for same day).
   Without the term the solver has no preference and its default, verified
   empirically, places both blocks on the same day.
"""
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def _make_section():
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["a"], 10, 0, 0, 0, 0, "Course")
    s.blocks = [Block("S_01#T1", "S_01", "theory", 2, False),
                Block("S_01#T2", "S_01", "theory", 2, False)]
    return s


def test_nonadjacent_objective_guard():
    """Objective must be 100 when both blocks are forced onto the same day.

    All days except Monday are blacked out (hours 9-17 on Tu/We/Th/Fr blocked),
    so the solver has no choice but to put both 2-h blocks on Monday.
    The non-adjacent term should add exactly 1 * w_nonadjacent = 100 to the
    objective.  Removing the term from obj leaves objective == 0, failing this.
    """
    # Block every slot on Tu, We, Th, Fr (hours 9..17 for the 2h undergrad window)
    closed = tuple(
        (day, h)
        for day in ("Tu", "We", "Th", "Fr")
        for h in range(9, 18)
    )
    cfg = Config(w_nonadjacent=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0, w_order=0, w_englab=0,
                 friday_blackout=closed, seminar_blackout=())
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = _make_section()
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE"), stats
    assert len(assigns) == 2
    # Both blocks must land on Monday (only available day)
    assert assigns[0].day == "Mo" and assigns[1].day == "Mo"
    # Objective must reflect the same-day penalty
    assert stats["objective"] == 100.0, (
        f"Expected objective 100 (one same-day penalty), got {stats['objective']}. "
        "The non-adjacent term is likely missing from the objective."
    )


def test_split_blocks_spread_when_weighted():
    """With all days open and w_nonadjacent=100, blocks land on different days.

    Without the term CP-SAT's default (verified empirically: same day), the
    assertion fails.  With the term the solver prefers the 0-cost split.
    """
    # NOTE: This is a behavioral demonstration, NOT a strict regression guard.
    # Whether the solver spreads the two blocks without the term depends on CP-SAT's
    # default search heuristic, so this test can pass even if the term is removed.
    # The real regression guard for this feature is test_nonadjacent_objective_guard,
    # which asserts the term's contribution to the objective directly.
    cfg = Config(w_nonadjacent=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0, w_order=0)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = _make_section()
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert len(assigns) == 2
    assert assigns[0].day != assigns[1].day, (
        f"Expected blocks on different days, got {assigns[0].day} and {assigns[1].day}. "
        "The non-adjacent term is likely missing from the objective."
    )
