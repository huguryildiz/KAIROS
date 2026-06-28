from collections import defaultdict

from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def _sec(sid, level, students, blocks, instr="i1", cohort="D-1"):
    s = Section(sid, "001", "D 101", "n", level, "D", "Fac", cohort, [instr],
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s


def test_gen_candidates_respects_capacity_and_window():
    cfg = Config(blackout=(("Fr", 13, False),))
    rooms = [Room("R1", 30, False, True), Room("R2", 10, False, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#T", "S_01", "theory", 3, False)
    s = _sec("S_01", 1, 25, [b])
    cands = model_cpsat.gen_candidates(b, s, [instr], rooms, cfg)
    assert all(c.room == "R1" for c in cands)
    assert all(c.start + b.length <= cfg.undergrad_end for c in cands)
    assert not any(c.day == "Fr" and c.start <= 13 < c.start + b.length for c in cands)


def test_gen_candidates_lab_pinned_to_lab_room():
    cfg = Config()
    rooms = [Room("R1", 50, False, True), Room("LAB-L", 50, True, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#L", "S_01", "lab", 2, True)
    s = _sec("S_01", 1, 20, [b])
    s.lab_room = "LAB-L"                         # pinned -> candidates only in LAB-L
    cands = model_cpsat.gen_candidates(b, s, [instr], rooms, cfg)
    assert cands and all(c.room == "LAB-L" for c in cands)


def test_requires_lab_room_restricts_to_lab_rooms():
    cfg = Config()
    rooms = [Room("R1", 50, False, True), Room("LAB-L", 50, True, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#T", "S_01", "theory", 2, False)   # a theory block (not a lab block)
    s = _sec("S_01", 1, 20, [b])
    s.requires_lab_room = True                         # explicit Room Type = lab
    fr = [r.room for r in model_cpsat.feasible_rooms_for(b, s, rooms, cfg)]
    assert fr == ["LAB-L"]                              # only the lab-flagged room
    cands = model_cpsat.gen_candidates(b, s, [instr], rooms, cfg)
    assert cands and all(c.room == "LAB-L" for c in cands)


def test_mixed_section_room_type_applies_to_lab_block_only():
    cfg = Config()
    rooms = [
        Room("R1", 50, False, True, type="normal"),
        Room("PC1", 50, True, True, type="pc"),
    ]
    theory = Block("S_01#T", "S_01", "theory", 2, False)
    lab = Block("S_01#L", "S_01", "lab", 2, True)
    s = _sec("S_01", 1, 20, [theory, lab])
    s.requires_lab_room = True
    s.required_room_type = "pc"

    theory_rooms = [r.room for r in model_cpsat.feasible_rooms_for(theory, s, rooms, cfg)]
    lab_rooms = [r.room for r in model_cpsat.feasible_rooms_for(lab, s, rooms, cfg)]

    assert theory_rooms == ["R1"]
    assert lab_rooms == ["PC1"]


def test_plain_theory_excludes_lab_family_rooms():
    cfg = Config()
    rooms = [
        Room("R1", 50, False, True, type="normal"),
        Room("PC1", 50, True, True, type="pc"),
        Room("ARCH-STD1", 60, True, True, type="studio"),
    ]
    theory = Block("EE 311_01#T", "EE 311_01", "theory", 2, False)
    s = _sec("EE 311_01", 3, 35, [theory])

    got = [r.room for r in model_cpsat.feasible_rooms_for(theory, s, rooms, cfg)]

    assert got == ["R1"]


def test_availability_removes_candidates():
    cfg = Config(instr_unavailable=frozenset(("i1", "Mo", h) for h in range(9, 13)))
    rooms = [Room("R1", 50, False, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#T", "S_01", "theory", 2, False)
    s = _sec("S_01", 1, 20, [b])                 # instructor i1
    cands = model_cpsat.gen_candidates(b, s, [instr], rooms, cfg)
    assert cands                                  # still placeable other days/times
    assert not any(c.day == "Mo" and c.start < 13 for c in cands)


def test_fixed_pins_first_block():
    cfg = Config()
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#T", "S_01", "theory", 2, False)
    s = _sec("S_01", 1, 20, [b])
    s.fixed_day = "We"
    s.fixed_start = 10
    cands = model_cpsat.gen_candidates(b, s, [instr], rooms, cfg)
    assert cands and all(c.day == "We" and c.start == 10 for c in cands)


def test_gen_candidates_seminar_blackout_fulltime_only():
    cfg = Config(blackout=(("Th", 14, True), ("Th", 15, True)))
    rooms = [Room("R1", 50, False, True)]
    b = Block("S_01#T", "S_01", "theory", 1, False)
    s = _sec("S_01", 1, 10, [b])
    full = Instructor("i1", "n", True, "D")
    part = Instructor("i2", "n", False, "D")
    c_full = model_cpsat.gen_candidates(b, s, [full], rooms, cfg)
    c_part = model_cpsat.gen_candidates(b, s, [part], rooms, cfg)
    assert not any(x.day == "Th" and x.start in (14, 15) for x in c_full)
    assert any(x.day == "Th" and x.start in (14, 15) for x in c_part)


def test_feasible_rooms_best_fit_caps_and_prefers_smallest():
    cfg = Config(max_rooms_per_block=2)
    rooms = [Room("BIG", 100, False, True), Room("MED", 40, False, True),
             Room("SMALL", 30, False, True), Room("TINY", 10, False, True)]
    b = Block("S_01#T", "S_01", "theory", 2, False)
    s = _sec("S_01", 1, 25, [b])
    chosen = [r.room for r in model_cpsat.feasible_rooms_for(b, s, rooms, cfg)]
    assert chosen == ["SMALL", "MED"]   # smallest two that fit >=25, TINY excluded


def test_split_roomable_separates_oversize():
    cfg = Config()
    rooms = [Room("R1", 50, False, True)]
    small = _sec("S1_01", 1, 40, [Block("S1_01#T", "S1_01", "theory", 2, False)])
    big = _sec("S2_01", 1, 500, [Block("S2_01#T", "S2_01", "theory", 2, False)])
    roomable, oversize = model_cpsat.split_roomable([small, big], rooms, cfg)
    assert [s.section_id for s in roomable] == ["S1_01"]
    assert len(oversize) == 1 and oversize[0]["section_id"] == "S2_01"


def test_build_and_solve_tiny_feasible_instance():
    cfg = Config(solve_time_limit_s=10)
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instructors = {"i1": Instructor("i1", "n", False, "D")}
    s1 = _sec("S1_01", 1, 10, [], instr="i1", cohort="D-1")
    s2 = _sec("S2_01", 1, 10, [], instr="i1", cohort="D-1")
    s1.blocks = [Block("S1_01#T", "S1_01", "theory", 1, False)]
    s2.blocks = [Block("S2_01#T", "S2_01", "theory", 1, False)]
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instructors, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert len(assigns) == 2
    a1, a2 = assigns
    assert not (a1.day == a2.day and a1.start == a2.start)
