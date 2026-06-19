from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def _sec(sid, code, instr, cohort):
    s = Section(sid, "001", code, "n", 2, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s


def test_gap_term_penalizes_forced_interior_hole():
    # Close Mo-Th hours 9-11 AND Friday hour 10, leaving only Fri {9, 11} open.
    # Two distinct-course same-cohort 1h sections in one room are FORCED onto Fri 9 and Fri 11,
    # leaving hour 10 idle => the cohort has an unavoidable interior gap of 1 hour.
    # With every other weight zeroed, the objective must equal w_cohort_gap * 1 -- true only if
    # the gap term is actually wired into the objective (without it the objective would be 0.0).
    # This is the regression guard: a strict placement test is not possible because no other
    # objective term prefers non-adjacency, so the gap term's effect is otherwise tie-breaking.
    closed = tuple([(d, h) for d in ["Mo", "Tu", "We", "Th"] for h in (9, 10, 11)] + [("Fr", 10)])
    K = 5
    cfg = Config(w_cohort_gap=K, w_evening=0, w_room_count=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0, w_nonadjacent=0,
                 horizon_start=9, undergrad_end=12, friday_blackout=closed,
                 seminar_blackout=())
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s1 = _sec("X201_01", "X 201", "a", "D-2")
    s2 = _sec("X202_01", "X 202", "b", "D-2")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instr, cfg)
    assert stats["status_name"] == "OPTIMAL"
    assert all(a.day == "Fr" for a in assigns)
    assert sorted(a.start for a in assigns) == [9, 11]
    assert stats["objective"] == float(K)
