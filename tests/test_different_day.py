from timetabling.config import Config
from timetabling.model import Room, Section, Block, Instructor, Assignment
from timetabling.model_cpsat import build_and_solve
from timetabling.validate import validate


def _theory_section(t1=2, t2=1):
    s = Section("S_01", "001", "S 201", "n", 2, "D", "F", "D-2", ["i1"], 30,
                t1 + t2, 0, 0, 3, "")
    s.blocks = [Block("S_01#T1", "S_01", "theory", t1, False),
                Block("S_01#T2", "S_01", "theory", t2, False)]
    return s


def test_theory_sessions_solved_on_different_days():
    cfg = Config(solve_time_limit_s=5)
    rooms = [Room("R1", 50, False, True)]
    instr = {"i1": Instructor("i1", "n", False, "D")}
    s = _theory_section()
    assigns, stats = build_and_solve([s], rooms, instr, cfg)
    assert len(assigns) == 2
    assert len({a.day for a in assigns}) == 2                     # forced apart
    assert validate(assigns, [s], {"R1": rooms[0]}, instr, cfg) == []


def test_validate_flags_same_day_theory_sessions():
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i1": Instructor("i1", "n", False, "D")}
    s = _theory_section()
    a = [Assignment("S_01#T1", "S_01", "theory", "R1", "Mo", 9, 11),
         Assignment("S_01#T2", "S_01", "theory", "R1", "Mo", 14, 15)]   # both Monday
    v = validate(a, [s], rooms, instr, Config())
    assert any(x.kind == "split_day" for x in v)
