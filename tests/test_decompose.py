from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import decompose, validate


def _sec(sid, code, fac, instr, cohort):
    s = Section(sid, "001", code, "n", 2, "D", fac, cohort, [instr], 40, 1, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s


def test_decomposition_is_conflict_free_across_groups():
    cfg = Config(solve_time_limit_s=10)
    rooms = [Room("R1", 50, False, True)]               # single shared room -> forces reservation
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    fa = _sec("FA_01", "A 201", "Faculty A", "a", "A-2")
    fb = _sec("FB_01", "B 201", "Faculty B", "b", "B-2")
    assigns, stats = decompose.solve_decomposed([fa, fb], rooms, instr, cfg)
    assert len(assigns) == 2
    assert stats["n_groups"] == 2
    assert len(stats["groups"]) == 2
    assert stats["n_assignments"] == 2
    # both used the one room -> must differ in (day, hour)
    s = {(x.room, x.day, x.start) for x in assigns}
    assert len(s) == 2
    assert validate.validate(assigns, [fa, fb], {r.room: r for r in rooms}, instr, cfg) == []
