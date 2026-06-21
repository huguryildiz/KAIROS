from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import decompose, validate


def _sec(sid, code, fac, instr, cohort):
    s = Section(sid, "001", code, "n", 2, "D", fac, cohort, [instr], 20, 1, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s


def test_shared_instructor_across_faculties_no_conflict():
    # Single room, single shared instructor "x", only Fri 9/10/11 open. Two sections in different
    # faculties both taught by x must NOT land on the same (day,hour).
    closed = tuple([(d, h) for d in ["Mo", "Tu", "We", "Th"] for h in (9, 10, 11)])
    cfg = Config(solve_time_limit_s=15, horizon_start=9, undergrad_end=12,
                 blackout=closed)
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instr = {"x": Instructor("x", "n", False, "D")}
    fa = _sec("FA_01", "A 201", "Faculty A", "x", "A-2")
    fb = _sec("FB_01", "B 201", "Faculty B", "x", "B-2")
    assigns, stats = decompose.solve_decomposed([fa, fb], rooms, instr, cfg)
    assert len(assigns) == 2
    v = validate.validate(assigns, [fa, fb], {r.room: r for r in rooms}, instr, cfg)
    assert not any(viol.kind == "instructor" for viol in v)   # shared instructor not double-booked
    # confirm they really are at different (day,hour)
    a = {x.section_id: x for x in assigns}
    assert not (a["FA_01"].day == a["FB_01"].day and a["FA_01"].start == a["FB_01"].start)
