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
    s.lab_room = "LAB-L"                         # pinned, but assigned to R1 below
    a = [Assignment("S_01#L", "S_01", "lab", "R1", "Fr", 13, 15)]
    cfg = Config(blackout=(("Fr", 13, False),))
    kinds = {v.kind for v in validate.validate(a, [s], ROOMS, INSTR, cfg)}
    assert {"capacity", "lab_room", "blackout"} <= kinds


def test_room_type_requirement_applies_to_lab_block_only_for_mixed_section():
    rooms = {
        "R1": Room("R1", 40, False, True, type="normal"),
        "PC1": Room("PC1", 40, True, True, type="pc"),
    }
    instr = {"i1": Instructor("i1", "n", False, "D")}
    theory = Block("S_01#T", "S_01", "theory", 2, False)
    lab = Block("S_01#L", "S_01", "lab", 2, True)
    s = _sec("S_01", 1, 20, [theory, lab], instr="i1")
    s.requires_lab_room = True
    s.required_room_type = "pc"

    ok = [
        Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11),
        Assignment("S_01#L", "S_01", "lab", "PC1", "Tu", 9, 11),
    ]
    wrong_lab = [
        Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11),
        Assignment("S_01#L", "S_01", "lab", "R1", "Tu", 9, 11),
    ]

    assert validate.validate(ok, [s], rooms, instr, Config()) == []
    assert any(v.kind == "room_type" for v in validate.validate(wrong_lab, [s], rooms, instr, Config()))


def test_plain_theory_in_lab_family_room_is_room_type_violation():
    rooms = {
        "R1": Room("R1", 40, False, True, type="normal"),
        "ARCH-STD1": Room("ARCH-STD1", 60, True, True, type="studio"),
    }
    instr = {"i1": Instructor("i1", "n", False, "D")}
    theory = Block("EE 311_01#T", "EE 311_01", "theory", 2, False)
    s = _sec("EE 311_01", 3, 35, [theory], instr="i1", code="EE 311")
    a = [Assignment("EE 311_01#T", "EE 311_01", "theory", "ARCH-STD1", "Mo", 9, 11)]

    assert any(v.kind == "room_type" for v in validate.validate(a, [s], rooms, instr, Config()))


def test_instructor_unavailable_violation():
    s = _sec("S_01", 1, 10, [Block("S_01#T", "S_01", "theory", 2, False)], instr="i1")
    cfg = Config(instr_unavailable=frozenset({("i1", "Mo", 9), ("i1", "Mo", 10)}))
    bad = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]   # covers closed Mo 9,10
    kinds = {v.kind for v in validate.validate(bad, [s], ROOMS, INSTR, cfg)}
    assert "instructor_unavailable" in kinds
    ok = [Assignment("S_01#T", "S_01", "theory", "R1", "Tu", 9, 11)]
    kinds2 = {v.kind for v in validate.validate(ok, [s], ROOMS, INSTR, cfg)}
    assert "instructor_unavailable" not in kinds2


def test_fixed_violation():
    s = _sec("S_01", 1, 10, [Block("S_01#T", "S_01", "theory", 2, False)])
    s.fixed_day = "We"
    s.fixed_start = 10
    bad = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]   # off the fixed slot
    kinds = {v.kind for v in validate.validate(bad, [s], ROOMS, INSTR, Config())}
    assert "fixed" in kinds
    ok = [Assignment("S_01#T", "S_01", "theory", "R1", "We", 10, 12)]   # on the fixed slot
    kinds2 = {v.kind for v in validate.validate(ok, [s], ROOMS, INSTR, Config())}
    assert "fixed" not in kinds2


def test_room_type_violation():
    s = _sec("S_01", 1, 10, [Block("S_01#T", "S_01", "theory", 2, False)])
    s.requires_lab_room = True
    bad = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]   # R1 is not a lab
    kinds = {v.kind for v in validate.validate(bad, [s], ROOMS, INSTR, Config())}
    assert "room_type" in kinds
    ok = [Assignment("S_01#T", "S_01", "theory", "LAB-L", "Mo", 9, 11)]  # LAB-L is a lab
    kinds2 = {v.kind for v in validate.validate(ok, [s], ROOMS, INSTR, Config())}
    assert "room_type" not in kinds2


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
