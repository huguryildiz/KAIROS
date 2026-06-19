from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import model_cpsat, validate

ROOMS = {"R1": Room("R1", 50, False, True), "R2": Room("R2", 50, False, True)}
INSTR = {"i1": Instructor("i1", "n", False, "D")}

def _sec(blocks):
    s = Section("S_01", "001", "D 101", "n", 1, "D", "Fac", "D-1", ["i1"],
                10, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_validator_flags_self_overlap():
    s = _sec([Block("S_01#T1", "S_01", "theory", 2, False),
              Block("S_01#T2", "S_01", "theory", 2, False)])
    a = [Assignment("S_01#T1", "S_01", "theory", "R1", "Mo", 9, 11),
         Assignment("S_01#T2", "S_01", "theory", "R2", "Mo", 10, 12)]
    kinds = {v.kind for v in validate.validate(a, [s], ROOMS, INSTR, Config())}
    assert "self" in kinds

def test_solver_keeps_section_blocks_disjoint():
    s = _sec([Block("S_01#T1", "S_01", "theory", 1, False),
              Block("S_01#T2", "S_01", "theory", 1, False)])
    assigns, stats = model_cpsat.build_and_solve([s], list(ROOMS.values()), INSTR, Config())
    assert len(assigns) == 2
    a1, a2 = assigns
    assert not (a1.day == a2.day and a1.start == a2.start)
    assert validate.validate(assigns, [s], ROOMS, INSTR, Config()) == []
