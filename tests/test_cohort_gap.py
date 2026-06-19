from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def _sec(sid, code, instr, cohort):
    s = Section(sid, "001", code, "n", 2, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s


def test_high_gap_weight_avoids_interior_hole():
    # Close Mo-Th hours 9-11 so only Friday {9,10,11} is open; one room; two distinct-course
    # same-cohort 1h sections. They occupy 2 of {9,10,11} on Fri. A gap-blind solver may pick
    # 9 & 11 (hole at 10); with a strong gap weight the solver must pick adjacent hours.
    closed = tuple((d, h) for d in ["Mo", "Tu", "We", "Th"] for h in (9, 10, 11))
    cfg = Config(w_cohort_gap=100, w_evening=0, w_room_count=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0, w_nonadjacent=0,
                 horizon_start=9, undergrad_end=12, friday_blackout=closed,
                 seminar_blackout=())
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s1 = _sec("X201_01", "X 201", "a", "D-2")
    s2 = _sec("X202_01", "X 202", "b", "D-2")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert all(a.day == "Fr" for a in assigns)
    starts = sorted(a.start for a in assigns)
    assert starts[1] - starts[0] == 1            # adjacent: no idle hour between the two classes
