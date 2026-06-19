from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat, validate, report


def _sec(sid, code, instr, cohort="D-2"):
    s = Section(sid, "001", code, "n", 2, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s


def test_cohort_conflict_is_soft_not_hard():
    # Only Fri 9 is open (block Mo-Th 9-11 and Fri 10,11). Two DIFFERENT-course same-cohort
    # 1h sections, TWO rooms (so room is not binding), distinct instructors. Both are forced to
    # Fri 9 -> a cohort course-conflict is UNAVOIDABLE. Under hard cohort this was INFEASIBLE;
    # under soft cohort the solver places both (0 hard violations) and pays the penalty once.
    closed = tuple([(d, h) for d in ["Mo", "Tu", "We", "Th"] for h in (9, 10, 11)]
                   + [("Fr", 10), ("Fr", 11)])
    W = 50
    cfg = Config(w_cohort_conflict=W, w_evening=0, w_room_count=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0, w_nonadjacent=0, w_cohort_gap=0,
                 horizon_start=9, undergrad_end=12, friday_blackout=closed, seminar_blackout=())
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s1 = _sec("X201_01", "X 201", "a")
    s2 = _sec("X202_01", "X 202", "b")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert len(assigns) == 2                                   # both placed (not infeasible)
    rooms_by = {r.room: r for r in rooms}
    assert validate.validate(assigns, [s1, s2], rooms_by, instr, cfg) == []   # 0 HARD violations
    assert stats["objective"] == float(W)                     # exactly one unit of cohort penalty
    m = report._metrics(assigns, [s1, s2], rooms_by, instr, cfg)
    assert m["cohort_conflicts"] == 1                          # reported as a soft metric


def test_no_conflict_when_room_free_and_slots_available():
    # Same two sections but the full window is open and two rooms exist -> the solver can separate
    # them in time at zero penalty. objective 0, no cohort conflict.
    cfg = Config(w_cohort_conflict=50, w_evening=0, w_room_count=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0, w_nonadjacent=0, w_cohort_gap=0)
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s1 = _sec("X201_01", "X 201", "a")
    s2 = _sec("X202_01", "X 202", "b")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instr, cfg)
    m = report._metrics(assigns, [s1, s2], {r.room: r for r in rooms}, instr, cfg)
    assert m["cohort_conflicts"] == 0
