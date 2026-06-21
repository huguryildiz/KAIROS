from collections import defaultdict

from timetabling.config import Config
from timetabling.model import (Section, Block, Room, Instructor,
                               weekly_load_hours, overload_eligible_ids)
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


def _two_block_instr(weekly_hours_each=3):
    s1 = _sec("S1_01", 1, 10, [], instr="i1", cohort="D-1")
    s2 = _sec("S2_01", 1, 10, [], instr="i1", cohort="D-1")
    s1.blocks = [Block("S1_01#T", "S1_01", "theory", weekly_hours_each, False)]
    s2.blocks = [Block("S2_01#T", "S2_01", "theory", weekly_hours_each, False)]
    return s1, s2


def test_weekly_load_and_exemption_helper():
    s1, s2 = _two_block_instr(3)                      # i1 carries 6h/week
    assert weekly_load_hours([s1, s2]) == {"i1": 6}
    # exempt threshold below 6 -> i1 excluded; threshold >=6 (or 0) -> included
    assert overload_eligible_ids([s1, s2], Config(overload_exempt_weekly=4)) == set()
    assert overload_eligible_ids([s1, s2], Config(overload_exempt_weekly=8)) == {"i1"}
    assert overload_eligible_ids([s1, s2], Config(overload_exempt_weekly=0)) == {"i1"}


def _max_daily_hours(assigns):
    daily = defaultdict(int)
    for a in assigns:
        daily[a.day] += a.end - a.start
    return max(daily.values())


def test_daily_overload_penalty_spreads_instructor():
    # one instructor, two 3h theory blocks = 6h; a 4h/day cap pushes them onto two days.
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instructors = {"i1": Instructor("i1", "n", False, "D")}

    cfg_on = Config(solve_time_limit_s=10, w_instr_daily_overload=50,
                    overload_exempt_weekly=8)        # 6h/wk i1 is eligible
    s1, s2 = _two_block_instr(3)
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instructors, cfg_on)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert _max_daily_hours(assigns) <= cfg_on.max_instr_daily_hours

    # exempt the instructor (weekly cap below their load) -> penalty must not apply,
    # so the model is free to stack both blocks on one day (instr-day penalty prefers it).
    cfg_exempt = Config(solve_time_limit_s=10, w_instr_daily_overload=50,
                        overload_exempt_weekly=4)    # 6h/wk i1 is exempt
    s1b, s2b = _two_block_instr(3)
    assigns_x, _ = model_cpsat.build_and_solve([s1b, s2b], rooms, instructors, cfg_exempt)
    assert _max_daily_hours(assigns_x) == 6


def _four_1h_sections():
    secs = []
    for k in range(4):
        s = _sec(f"S{k}_01", 2, 10, [], instr="i1", cohort="D-1")
        s.blocks = [Block(f"S{k}_01#T", f"S{k}_01", "theory", 1, False)]
        secs.append(s)
    return secs


def test_weekly_day_cap_concentrates_instructor():
    # Four 1h theory sections taught by one instructor. With day-spread preference OFF,
    # the base model is free to scatter them across days; the weekly distinct-day cap
    # (soft) must pull them onto at most `max_instr_weekly_days` days.
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instructors = {"i1": Instructor("i1", "n", False, "D")}

    base = Config(solve_time_limit_s=10, w_instr_days=0, w_parttime_days=0)
    a_base, _ = model_cpsat.build_and_solve(_four_1h_sections(), rooms, instructors, base)
    assert len({a.day for a in a_base}) == 4          # nothing rewards fewer days -> scattered

    capped = Config(solve_time_limit_s=10, w_instr_days=0, w_parttime_days=0,
                    w_instr_weekly_overload=50, max_instr_weekly_days=1)
    a_cap, stats = model_cpsat.build_and_solve(_four_1h_sections(), rooms, instructors, capped)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert len(a_cap) == 4                             # all still placed (soft, never blocks)
    assert len({a.day for a in a_cap}) <= capped.max_instr_weekly_days
