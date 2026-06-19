from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import model_cpsat, validate, report

ROOMS = {"R1": Room("R1", 50, False, True), "R2": Room("R2", 50, False, True)}

def _sec(sid, code, instr, blocks, cohort="D-1"):
    s = Section(sid, "001", code, "n", 1, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_same_course_parallel_allowed_by_validator():
    s1 = _sec("C101_01", "C 101", "i1", [Block("C101_01#T", "C101_01", "theory", 1, False)])
    s2 = _sec("C101_02", "C 101", "i2", [Block("C101_02#T", "C101_02", "theory", 1, False)])
    a = [Assignment("C101_01#T", "C101_01", "theory", "R1", "Mo", 9, 10),
         Assignment("C101_02#T", "C101_02", "theory", "R2", "Mo", 9, 10)]
    instr = {"i1": Instructor("i1", "n", False, "D"), "i2": Instructor("i2", "n", False, "D")}
    assert validate.validate(a, [s1, s2], ROOMS, instr, Config()) == []

def test_different_courses_same_cohort_conflict():
    s1 = _sec("C101_01", "C 101", "i1", [Block("C101_01#T", "C101_01", "theory", 1, False)])
    s2 = _sec("C201_01", "C 201", "i2", [Block("C201_01#T", "C201_01", "theory", 1, False)])
    a = [Assignment("C101_01#T", "C101_01", "theory", "R1", "Mo", 9, 10),
         Assignment("C201_01#T", "C201_01", "theory", "R2", "Mo", 9, 10)]
    instr = {"i1": Instructor("i1", "n", False, "D"), "i2": Instructor("i2", "n", False, "D")}
    kinds = {v.kind for v in validate.validate(a, [s1, s2], ROOMS, instr, Config())}
    assert "cohort" not in kinds                              # cohort is soft now, not a hard violation
    met = report._metrics(a, [s1, s2], ROOMS, instr, Config())
    assert met["cohort_conflicts"] >= 1                       # but it IS reported as a soft conflict

def test_solver_allows_same_course_parallel():
    # two sections of the same course, same cohort, different instructors, only 1 free
    # day-hour each so they MUST go parallel -> feasible only if course-level cohort allows it
    cfg = Config()
    s1 = _sec("C101_01", "C 101", "i1", [Block("C101_01#T", "C101_01", "theory", 9, False)])
    s2 = _sec("C101_02", "C 101", "i2", [Block("C101_02#T", "C101_02", "theory", 9, False)])
    instr = {"i1": Instructor("i1", "n", False, "D"), "i2": Instructor("i2", "n", False, "D")}
    assigns, stats = model_cpsat.build_and_solve([s1, s2], list(ROOMS.values()), instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE") and len(assigns) == 2
    assert validate.validate(assigns, [s1, s2], ROOMS, instr, cfg) == []
