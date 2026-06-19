from timetabling.config import Config
from timetabling.model import Room, Instructor
from timetabling import derive, model_cpsat, validate


def test_single_block_keeps_plain_id():
    bs = derive.blocks_from_tpl("S_01", 2, 0, 0, 2, max_block_len=4)
    assert [b.block_id for b in bs] == ["S_01#T"]   # T<=2 stays one session


def test_theory_splits_into_two_hour_sessions():
    assert sorted(b.length for b in derive.blocks_from_tpl("S_01", 3, 0, 0, 3)) == [1, 2]
    assert sorted(b.length for b in derive.blocks_from_tpl("S_01", 4, 0, 0, 4)) == [2, 2]
    bs = derive.blocks_from_tpl("S_01", 5, 0, 0, 5)
    assert sorted(b.length for b in bs) == [1, 2, 2]
    assert [b.block_id for b in bs] == ["S_01#T1", "S_01#T2", "S_01#T3"]
    assert all(b.kind == "theory" and not b.needs_lab for b in bs)


def test_long_lab_splits_and_marks_lab():
    bs = derive.blocks_from_tpl("S_01", 0, 0, 6, 0, max_block_len=4)
    labs = [b for b in bs if b.needs_lab]
    assert len(bs) == 2 and len(labs) == 2 and sorted(b.length for b in bs) == [3, 3]
    assert all("#L" in b.block_id for b in bs)


def test_split_section_solves_clean():
    cfg = Config()
    rooms = [Room("R1", 50, False, True)]
    instr = {"i1": Instructor("i1", "n", False, "D")}
    from timetabling.model import Section
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["i1"],
                10, 10, 0, 0, 0, "Course")
    s.blocks = derive.blocks_from_tpl("S_01", 10, 0, 0, 0, cfg.max_block_len)
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert len(assigns) == len(s.blocks) >= 3
    assert validate.validate(assigns, [s], {r.room: r for r in rooms}, instr, cfg) == []
