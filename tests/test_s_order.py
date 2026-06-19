from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def _sec(sid, code, level, instr, cohort="D-2"):
    s = Section(sid, "001", code, "n", level, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s


def test_low_level_lands_earlier():
    cfg = Config(w_order=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s2 = _sec("X201_01", "X 201", 2, "a")
    s4 = _sec("X401_01", "X 401", 4, "b")
    # Pass s4 first so solver's default (no S-Order) gives s4 the earlier slot.
    # With S-Order the level-2 penalty pushes X201_01 to the earliest hour instead.
    assigns, stats = model_cpsat.build_and_solve([s4, s2], rooms, instr, cfg)
    a = {x.section_id: x for x in assigns}
    assert a["X201_01"].start <= a["X401_01"].start
