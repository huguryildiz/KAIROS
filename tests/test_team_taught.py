from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat, validate

def _sec(sid, instr_ids, blocks, cohort="D-1", level=1, students=10, faculty="Fac"):
    s = Section(sid, "001", "D 101", "n", level, "D", faculty, cohort, instr_ids,
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_both_co_instructors_enter_conflict():
    cfg = Config()
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instructors = {"i1": Instructor("i1", "Ann", False, "D"),
                   "i2": Instructor("i2", "Bob", False, "D")}
    # s1 taught by (i1,i2); s2 taught by i2 alone, different cohort -> i2 shared
    s1 = _sec("S1_01", ["i1", "i2"], [Block("S1_01#T", "S1_01", "theory", 1, False)], cohort="D-1")
    s2 = _sec("S2_01", ["i2"], [Block("S2_01#T", "S2_01", "theory", 1, False)], cohort="E-1")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instructors, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    a = {x.section_id: x for x in assigns}
    # shared instructor i2 -> the two sections cannot occupy the same (day, hour)
    assert not (a["S1_01"].day == a["S2_01"].day and a["S1_01"].start == a["S2_01"].start)
    assert validate.validate(assigns, [s1, s2], {r.room: r for r in rooms}, instructors, cfg) == []

def test_seminar_blackout_if_any_coinstructor_fulltime():
    cfg = Config(blackout=(("Th", 14, True), ("Th", 15, True)))
    rooms = [Room("R1", 50, False, True)]
    instructors = {"f": Instructor("f", "Full", True, "D"), "p": Instructor("p", "Part", False, "D")}
    s = _sec("S_01", ["p", "f"], [Block("S_01#T", "S_01", "theory", 1, False)])
    cands = model_cpsat.gen_candidates(s.blocks[0], s,
                                       [instructors["p"], instructors["f"]], rooms, cfg)
    assert not any(c.day == "Th" and c.start in (14, 15) for c in cands)
