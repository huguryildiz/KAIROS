from timetabling.ui_input import dept_code_for, grad_dept_codes
from timetabling.settings import build_config, DEFAULT_SETTINGS
from timetabling.config import Config
from timetabling.model import Section, Block, Instructor, Room
from timetabling.model_cpsat import gen_candidates


def test_dept_code_for_normal_and_unk_fallback():
    assert dept_code_for({"Course Code": "PSY501"}) == "PSY"
    assert dept_code_for({"Course Code": "???", "Dept": "Engineering"}) == "ENGINEERING"


def test_grad_dept_codes_only_graduate_sorted():
    rows = [{"Course Code": "PSY501"}, {"Course Code": "PSY101"}, {"Course Code": "CS502"}]
    assert grad_dept_codes(rows) == ["CS", "PSY"]


def test_build_config_maps_grad_overrides_uppercased_and_validated():
    s = dict(DEFAULT_SETTINGS, grad_start_by_dept={"psy": 9, "econ": 99})  # 99 invalid -> dropped
    cfg = build_config(s, {}, 60)
    assert cfg.grad_start_for("PSY") == 9
    assert cfg.grad_start_for("ECON") == cfg.grad_start  # invalid hour dropped


def test_gen_candidates_respects_per_dept_grad_floor():
    cfg = Config(include_grad=True, grad_start=18, grad_start_by_dept=(("PSY", 9),))
    rooms = [Room("R1", 100, False, True)]
    instr = {"a": Instructor("a", "n", True, "PSY")}
    # graduate PSY section (level 5) — overridden floor 9 -> may start in the morning
    s = Section("PSY501_01", "001", "PSY 501", "n", 5, "PSY", "F", "PSY-5", ["a"],
                10, 2, 0, 0, 2, "")
    s.blocks = [Block("PSY501_01#T", "PSY501_01", "theory", 2, False)]
    cands = gen_candidates(s.blocks[0], s, [instr["a"]], rooms, cfg)
    assert cands and min(c.start for c in cands) == 9
    # a graduate section in a non-overridden dept keeps the global 18:00 floor
    s2 = Section("CS501_01", "001", "CS 501", "n", 5, "CS", "F", "CS-5", ["a"],
                 10, 2, 0, 0, 2, "")
    s2.blocks = [Block("CS501_01#T", "CS501_01", "theory", 2, False)]
    cands2 = gen_candidates(s2.blocks[0], s2, [instr["a"]], rooms, cfg)
    assert cands2 and min(c.start for c in cands2) == 18
