from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import validate


def _sec(sid, level, students, blocks, instr="i1", cohort="D-1", code="D 101"):
    s = Section(sid, "001", code, "n", level, "D", "Fac", cohort, [instr],
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s


ROOMS = {"R1": Room("R1", 50, False, True), "LAB-L": Room("LAB-L", 50, True, True)}
INSTR = {"i1": Instructor("i1", "n", True, "D"), "i2": Instructor("i2", "n", False, "D")}


def test_clean_solution_has_no_violations():
    s = _sec("S_01", 1, 10, [Block("S_01#T", "S_01", "theory", 2, False)])
    a = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]
    assert validate.validate(a, [s], ROOMS, INSTR, Config()) == []


def test_detects_room_double_book():
    s1 = _sec("S1_01", 1, 10, [Block("S1_01#T", "S1_01", "theory", 2, False)], instr="i1", cohort="D-1")
    s2 = _sec("S2_01", 1, 10, [Block("S2_01#T", "S2_01", "theory", 2, False)], instr="i2", cohort="D-2")
    a = [Assignment("S1_01#T", "S1_01", "theory", "R1", "Mo", 9, 11),
         Assignment("S2_01#T", "S2_01", "theory", "R1", "Mo", 10, 12)]
    kinds = {v.kind for v in validate.validate(a, [s1, s2], ROOMS, INSTR, Config())}
    assert "room" in kinds


def test_detects_capacity_and_lab_and_window_and_blackout():
    s = _sec("S_01", 1, 99, [Block("S_01#L", "S_01", "lab", 2, True)], instr="i1")
    a = [Assignment("S_01#L", "S_01", "lab", "R1", "Fr", 13, 15)]
    kinds = {v.kind for v in validate.validate(a, [s], ROOMS, INSTR, Config())}
    assert {"capacity", "lab", "blackout"} <= kinds


def test_detects_instructor_conflict():
    s1 = _sec("S1_01", 1, 10, [Block("S1_01#T", "S1_01", "theory", 1, False)],
              instr="i1", cohort="D-1", code="D 101")
    s2 = _sec("S2_01", 1, 10, [Block("S2_01#T", "S2_01", "theory", 1, False)],
              instr="i1", cohort="D-1", code="D 202")
    a = [Assignment("S1_01#T", "S1_01", "theory", "R1", "Mo", 9, 10),
         Assignment("S2_01#T", "S2_01", "theory", "LAB-L", "Mo", 9, 10)]
    kinds = {v.kind for v in validate.validate(a, [s1, s2], ROOMS, INSTR, Config())}
    assert "instructor" in kinds
    assert "cohort" not in kinds
