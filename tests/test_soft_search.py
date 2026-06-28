from collections import Counter
from timetabling.config import Config
from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, _soft_total


def _sec(sid, iid, level=1, code="X 101", cohort=None):
    s = Section(sid, "001", code, "x", level, code.split()[0], "F",
                cohort or f"{code.split()[0]}-{level}", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def _state(*secs):
    sec_of = {b.block_id: s for s in secs for b in s.blocks}
    sec_instr = {s.section_id: s.instructor_ids for s in secs}
    return State(sec_of, sec_instr, set())


def test_soft_total_includes_instr_days():
    from dataclasses import replace
    cfg = replace(Config(), w_instr_days=3)   # pin weight (default-independent)
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="ADA 102")     # same instructor i1
    st = _state(a, b)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    st.occupy("B_01#T", Candidate("B_01#T", "R2", "Tu", 9, 2))
    # i1 teaches 2 days -> w_instr_days*2 = 6 ; order/cohort all zero here
    assert _soft_total(st, cfg) == 6
    assert st.room_hours_used == Counter({"R1": 2, "R2": 2})


def test_room_hours_used_decrements_on_release():
    cfg = Config()
    a = _sec("A_01", "i1")
    st = _state(a)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    assert st.room_hours_used["R1"] == 2
    st.release("A_01#T")
    assert st.room_hours_used.get("R1", 0) == 0


def test_local_soft_matches_soft_total_over_all_entities():
    from timetabling.soft_search import _local_soft
    cfg = Config()
    secs = [_sec("A_01", "i1", level=2, code="ADA 201"),
            _sec("B_01", "i1", level=2, code="ADA 202"),   # same cohort ADA-2 + instr i1
            _sec("C_01", "i2", level=3, code="EEE 301")]
    st = _state(*secs)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    st.occupy("B_01#T", Candidate("B_01#T", "R1", "Mo", 13, 2))   # gap on Monday for ADA-2
    st.occupy("C_01#T", Candidate("C_01#T", "R2", "Tu", 16, 2))   # evening
    all_cohorts = {s.cohort_key for s in secs}
    all_instrs = {iid for s in secs for iid in s.instructor_ids}
    all_rooms = set(st.room_hours_used)
    all_blocks = set(st.placed)
    assert _local_soft(st, all_cohorts, all_instrs, all_rooms, all_blocks, cfg) == _soft_total(st, cfg)


import random
from timetabling.validate import validate
from timetabling.model import Room, Instructor


def _eval_fn(cfg, base):
    """Build a polish objective evaluator over affected entities: (normalized E, terms)."""
    from timetabling.soft_search import _local_terms, _norm_obj

    def fn(state, cohorts, instrs, rooms, blocks):
        t = _local_terms(state, cohorts, instrs, rooms, blocks, cfg)
        return _norm_obj(t, base, cfg), t
    return fn


def test_relocate_lowers_normalized_objective_and_keeps_placement():
    from timetabling.soft_search import try_relocate, _global_terms
    cfg = Config()
    # cohort ADA-2: sibling B fixed Mo 9-11; A parked Mo 14-16 (idle gap 11-13). Relocating A
    # to the adjacent Mo 11-13 closes the gap -> idle drops -> normalized E drops.
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i2", level=2, code="ADA 202")     # same cohort ADA-2, other instructor
    cand = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 14, 2),
                       Candidate("A_01#T", "R1", "Mo", 11, 2)]}
    st = _state(a, b)
    st.occupy("B_01#T", Candidate("B_01#T", "R2", "Mo", 9, 2))
    st.occupy("A_01#T", cand["A_01#T"][0])       # park with a gap
    ev = _eval_fn(cfg, _global_terms(st, cfg))
    rng = random.Random(0)
    res = try_relocate(st, cand, "A_01#T", rng, ev)
    assert res is not None
    dobj, dterms, revert = res
    assert dobj < 0                              # idle gap closed -> normalized E drops
    assert dterms["conf"] == 0
    assert len(st.placed) == 2                   # never unplaced
    assert st.placed["A_01#T"].start == 11
    revert()                                     # revert restores the gapped slot
    assert st.placed["A_01#T"].start == 14


def test_relocate_lowers_instructor_idle_gap():
    from timetabling.soft_search import try_relocate, _global_terms
    cfg = Config(w_idle=0, w_maxrun=0, w_instr_days=0, w_nonadjacent=0,
                 w_evening=0, w_instr_idle=20, w_fairness=0,
                 w_room_stable=0, w_free_day=0)
    # i1 has a same-day hole: A is Mo 9-11, B is parked Mo 15-17. Moving B to Mo 11-13
    # closes the instructor idle gap without changing placement or hard feasibility.
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="BBB 101")
    cand = {"B_01#T": [Candidate("B_01#T", "R2", "Mo", 15, 2),
                       Candidate("B_01#T", "R2", "Mo", 11, 2)]}
    st = _state(a, b)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    st.occupy("B_01#T", cand["B_01#T"][0])
    t0 = _global_terms(st, cfg)
    assert t0["instr_idle"] == 4

    res = try_relocate(st, cand, "B_01#T", random.Random(0), _eval_fn(cfg, t0))

    assert res is not None
    dobj, dterms, revert = res
    assert dterms["instr_idle"] == -4
    assert dobj < 0
    assert st.placed["B_01#T"].start == 11
    revert()
    assert _global_terms(st, cfg)["instr_idle"] == 4


def test_swap_lowers_objective_where_relocate_cannot():
    from timetabling.soft_search import try_swap, _global_terms
    cfg = Config(max_instr_days=0)        # threshold 0 -> instr_days term == raw teaching-day count
    # i1 teaches A,B ; i2 teaches C,D. Distinct cohorts (no conflict/gap interaction).
    # A and C sit at a DIFFERENT hour on the packing day so packing won't double-book the
    # instructor. Initial: i1 on {Mo,We}, i2 on {We,Mo} -> 4 teaching-days. R2 Mo/We slots
    # are both full (relocate stuck). Swapping B(R2 We) <-> D(R2 Mo) packs i1->{Mo} (A Mo14
    # + B Mo9), i2->{We} (C We14 + D We9) = 2 teaching-days.
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="BBB 101")
    c = _sec("C_01", "i2", code="CCC 101")
    d = _sec("D_01", "i2", code="DDD 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 14, 2)],
        "B_01#T": [Candidate("B_01#T", "R2", "We", 9, 2), Candidate("B_01#T", "R2", "Mo", 9, 2)],
        "C_01#T": [Candidate("C_01#T", "R1", "We", 14, 2)],
        "D_01#T": [Candidate("D_01#T", "R2", "Mo", 9, 2), Candidate("D_01#T", "R2", "We", 9, 2)],
    }
    st = _state(a, b, c, d)
    st.occupy("A_01#T", cand["A_01#T"][0])       # i1 Mo 14-16
    st.occupy("B_01#T", cand["B_01#T"][0])       # i1 We 9-11
    st.occupy("C_01#T", cand["C_01#T"][0])       # i2 We 14-16
    st.occupy("D_01#T", cand["D_01#T"][0])       # i2 Mo 9-11
    ev = _eval_fn(cfg, _global_terms(st, cfg))   # teaching-days base = 4
    res = try_swap(st, cand, "B_01#T", "D_01#T", ev)
    assert res is not None
    dobj, dterms, revert = res
    assert dobj < 0                              # teaching-days 4 -> 2
    assert dterms["conf"] == 0
    assert st.placed["B_01#T"].day == "Mo" and st.placed["D_01#T"].day == "We"
    assert len(st.placed) == 4


def test_consolidate_instr_collapses_teaching_days():
    from timetabling.soft_search import try_consolidate_instr, _global_terms
    cfg = Config(max_instr_days=0)        # threshold 0 -> instr_days term == raw teaching-day count
    # i1 teaches A (Mo) and B (We): 2 teaching-days. Each block has a candidate on the day the
    # OTHER sits, so consolidation collapses i1 onto one day whichever sparse day it vacates.
    # Generic relocate rarely targets an already-used day; this primitive proposes it directly.
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="BBB 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2), Candidate("A_01#T", "R1", "We", 14, 2)],
        "B_01#T": [Candidate("B_01#T", "R2", "We", 9, 2), Candidate("B_01#T", "R2", "Mo", 14, 2)],
    }
    st = _state(a, b)
    st.occupy("A_01#T", cand["A_01#T"][0])        # i1 Mo 9-11
    st.occupy("B_01#T", cand["B_01#T"][0])        # i1 We 9-11
    t0 = _global_terms(st, cfg)
    assert t0["instr_days"] == 2
    res = try_consolidate_instr(st, cand, "i1", random.Random(0), _eval_fn(cfg, t0))
    assert res is not None
    dobj, dterms, revert = res
    assert dterms["instr_days"] == -1             # 2 teaching-days -> 1
    assert dobj < 0
    assert len(st.placed) == 2                    # placement invariant
    revert()
    assert _global_terms(st, cfg)["instr_days"] == 2   # revert restores the snapshot


def test_moves_keep_hard_feasibility():
    from timetabling.soft_search import try_relocate, _global_terms
    cfg = Config()
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i1": Instructor("i1", "x", True, "D")}
    a = _sec("A_01", "i1")
    cand = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2),
                       Candidate("A_01#T", "R1", "Mo", 9, 2)]}
    st = _state(a)
    st.occupy("A_01#T", cand["A_01#T"][0])
    ev = _eval_fn(cfg, _global_terms(st, cfg))
    rng = random.Random(1)
    try_relocate(st, cand, "A_01#T", rng, ev)
    assigns = [__import__("timetabling.model", fromlist=["Assignment"]).Assignment(
        bid, st.sec_of[bid].section_id, "theory", c.room, c.day, c.start, c.start + c.length)
        for bid, c in st.placed.items()]
    assert validate(assigns, [a], rooms, instr, cfg) == []


def test_schc_accepts_downhill_and_bounded_uphill():
    from timetabling.soft_search import SCHC
    acc = SCHC(counter_limit=3)
    acc.init(cost=100)
    assert acc.accept(-5, 0) is True       # downhill always
    assert acc.accept(0, 1) is True        # flat always
    # bound starts at 100; small uphill that keeps cost <= bound is accepted
    assert acc.accept(+3, 2) is True       # cost 95+3=98 <= bound 100
    # a jump above the current bound is rejected
    assert acc.accept(+50, 3) is False     # would exceed bound 100


def test_schc_refreshes_bound_every_counter_limit():
    from timetabling.soft_search import SCHC
    acc = SCHC(counter_limit=2)
    acc.init(cost=100)
    acc.accept(-40, 0)     # cost -> 60 (bound still 100 for first window)
    acc.accept(-10, 1)     # cost -> 50; after 2 steps bound refreshes to current (50)
    assert acc.accept(+30, 2) is False     # cost 50+30=80 > bound 50 now


def test_anneal_lowers_objective_keeps_placement_and_conf():
    from timetabling.soft_search import anneal_soft, _global_terms
    cfg = Config()
    # 8 cohorts; each has a fixed block Mo 9-11 and a movable block parked Mo 14-16 (idle gap
    # 11-13). Each movable block can slide to a clear Tu 9-11 slot, removing its cohort's gap.
    cand = {}
    secs = []
    for n in range(8):
        secs.append(_sec(f"F{n}_01", f"i{n}", level=2, code=f"C{n} 201"))   # fixed sibling
        secs.append(_sec(f"M{n}_01", f"j{n}", level=2, code=f"C{n} 202"))   # movable
    st = _state(*secs)
    for n in range(8):
        st.occupy(f"F{n}_01#T", Candidate(f"F{n}_01#T", f"R{n}", "Mo", 9, 2))
        bid = f"M{n}_01#T"
        cand[bid] = [Candidate(bid, f"S{n}", "Mo", 14, 2), Candidate(bid, f"S{n}", "Tu", 9, 2)]
        st.occupy(bid, cand[bid][0])             # park with a gap
    t0 = _global_terms(st, cfg)
    placed_before = len(st.placed)
    anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == placed_before       # placement invariant
    assert t1["conf"] <= t0["conf"]              # cohort-conflict guard never exceeded
    assert t1["idle"] < t0["idle"]               # idle gaps strictly improved


def test_anneal_lowers_objective_via_swap_dense():
    from timetabling.soft_search import anneal_soft, _global_terms
    cfg = Config(max_instr_days=0)        # threshold 0 -> instr_days term == raw teaching-day count
    # No empty slot exists -> only a B<->D swap can lower teaching-days (4 -> 2). A/C sit at
    # hour 14 on the packing day so packing won't double-book the instructor.
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="BBB 101")
    c = _sec("C_01", "i2", code="CCC 101")
    d = _sec("D_01", "i2", code="DDD 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 14, 2)],
        "B_01#T": [Candidate("B_01#T", "R2", "We", 9, 2), Candidate("B_01#T", "R2", "Mo", 9, 2)],
        "C_01#T": [Candidate("C_01#T", "R1", "We", 14, 2)],
        "D_01#T": [Candidate("D_01#T", "R2", "Mo", 9, 2), Candidate("D_01#T", "R2", "We", 9, 2)],
    }
    st = _state(a, b, c, d)
    st.occupy("A_01#T", cand["A_01#T"][0])
    st.occupy("B_01#T", cand["B_01#T"][0])
    st.occupy("C_01#T", cand["C_01#T"][0])
    st.occupy("D_01#T", cand["D_01#T"][0])
    t0 = _global_terms(st, cfg)                  # teaching-days = 4
    anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == 4
    assert t1["instr_days"] < t0["instr_days"]   # only a swap can lower instr days here


def test_chain_unlocks_where_relocate_and_swap_cannot():
    from timetabling.soft_search import try_chain, try_relocate, try_swap, _global_terms
    cfg = Config()
    # cohort ADA-2: sibling E fixed Mo 9-11; A parked Mo 14-16 (idle gap 11-13). A's gap-closing
    # target (R1 Mo11) is occupied by B, and B has no candidate at A's slot -> neither relocate
    # nor swap can move A. An ejection chain can: A -> R1 Mo11 ejecting B -> R2 Mo11 (free).
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    e = _sec("E_01", "i3", level=2, code="ADA 202")   # same cohort ADA-2, fixed sibling
    b = _sec("B_01", "i2", code="BBB 101")            # blocks A's target room
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 14, 2), Candidate("A_01#T", "R1", "Mo", 11, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 11, 2), Candidate("B_01#T", "R2", "Mo", 11, 2)],
    }
    st = _state(a, e, b)
    st.occupy("E_01#T", Candidate("E_01#T", "R0", "Mo", 9, 2))    # ADA-2 fixed Mo 9-11
    st.occupy("A_01#T", cand["A_01#T"][0])        # ADA-2 Mo 14-16 (gap 11-13)
    st.occupy("B_01#T", cand["B_01#T"][0])        # BBB-1 R1 Mo 11-13 (blocks A's target)
    ev = _eval_fn(cfg, _global_terms(st, cfg))
    assert try_relocate(st, cand, "A_01#T", random.Random(0), ev) is None   # target occupied
    assert try_swap(st, cand, "A_01#T", "B_01#T", ev) is None               # no reciprocal cand
    res = try_chain(st, cand, "A_01#T", random.Random(0), ev, max_depth=3)
    assert res is not None
    dobj, dterms, revert = res
    assert dterms["idle"] < 0                       # chain closed the cohort gap
    assert st.placed["A_01#T"].start == 11 and st.placed["B_01#T"].room == "R2"
    assert len(st.placed) == 3
    revert()
    assert st.placed["A_01#T"].start == 14 and st.placed["B_01#T"].room == "R1"


def test_chain_preserves_hard_feasibility():
    from timetabling.soft_search import try_chain, _global_terms
    cfg = Config()
    rooms = {"R1": Room("R1", 50, False, True), "R2": Room("R2", 50, False, True)}
    instr = {"i1": Instructor("i1", "x", True, "D"), "i2": Instructor("i2", "y", True, "D")}
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i2", code="BBB 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2), Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2), Candidate("B_01#T", "R2", "Mo", 9, 2)],
    }
    st = _state(a, b)
    st.occupy("A_01#T", cand["A_01#T"][0])
    st.occupy("B_01#T", cand["B_01#T"][0])
    ev = _eval_fn(cfg, _global_terms(st, cfg))
    try_chain(st, cand, "A_01#T", random.Random(0), ev, max_depth=3)
    assigns = [__import__("timetabling.model", fromlist=["Assignment"]).Assignment(
        bid, st.sec_of[bid].section_id, "theory", c.room, c.day, c.start, c.start + c.length)
        for bid, c in st.placed.items()]
    assert validate(assigns, [a, b], rooms, instr, cfg) == []


def test_anneal_with_chains_lowers_idle_keeps_invariants():
    from timetabling.soft_search import anneal_soft, _global_terms
    cfg = Config()
    # cohort ADA-2: sibling E fixed Mo 9-11; A parked Mo 14-16 (gap). A's gap-closing slot
    # (R1 Mo11) is blocked by B. B can escape to R2 (already opened by C, so no new room). The
    # wired loop (relocate+swap+chain) should close the gap without regressing conflict.
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    e = _sec("E_01", "i3", level=2, code="ADA 202")   # same cohort ADA-2, fixed sibling
    b = _sec("B_01", "i2", code="BBB 101")
    c = _sec("C_01", "i4", code="CCC 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 14, 2), Candidate("A_01#T", "R1", "Mo", 11, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 11, 2), Candidate("B_01#T", "R2", "Mo", 11, 2)],
    }
    st = _state(a, e, b, c)
    st.occupy("E_01#T", Candidate("E_01#T", "R0", "Mo", 9, 2))
    st.occupy("A_01#T", cand["A_01#T"][0])
    st.occupy("B_01#T", cand["B_01#T"][0])
    st.occupy("C_01#T", Candidate("C_01#T", "R2", "Mo", 14, 2))
    t0 = _global_terms(st, cfg)
    anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == 4            # placement invariant
    assert t1["conf"] <= t0["conf"]       # conflict guard
    assert t1["idle"] < t0["idle"]        # cohort gap closed


def test_anneal_conflict_guard_holds():
    from timetabling.soft_search import anneal_soft, _global_terms
    cfg = Config()
    # B sits in the evening (no conflict). Its only evening-reducing relocate lands on A's
    # cohort slot (Mo 9-11), which would create a cohort conflict. The conflict guard must
    # block it even though it lowers the objective -> conflict never exceeds baseline (0).
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i2", code="ADA 102")       # same cohort ADA-1
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R2", "Mo", 16, 2), Candidate("B_01#T", "R3", "Mo", 9, 2)],
    }
    st = _state(a, b)
    st.occupy("A_01#T", cand["A_01#T"][0])        # ADA-1 Mo 9-11
    st.occupy("B_01#T", cand["B_01#T"][0])        # ADA-1 Mo 16-18 (evening, no conflict)
    t0 = _global_terms(st, cfg)
    assert t0["conf"] == 0
    anneal_soft(st, cand, cfg, budget_s=1.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == 2
    assert t1["conf"] <= t0["conf"]               # conflict guard: never above baseline
    assert st.placed["B_01#T"].start == 16        # evening->morning blocked (would conflict)


def test_global_terms_raw_terms_plus_conf():
    from timetabling.soft_search import _global_terms
    cfg = Config(max_instr_days=0)        # threshold 0 -> instr_days term == raw teaching-day count
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i1", level=2, code="ADA 202")   # same cohort ADA-2 + instr i1
    d = _sec("D_01", "i1", level=2, code="ADA 203")   # same cohort ADA-2 + instr i1
    c = _sec("C_01", "i2", level=1, code="EEE 101")
    st = _state(a, b, d, c)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # ADA-2 Mo 9,10
    st.occupy("B_01#T", Candidate("B_01#T", "R3", "Mo", 9, 2))   # ADA-2 Mo 9,10 (conflict)
    st.occupy("D_01#T", Candidate("D_01#T", "R1", "Mo", 14, 2))  # ADA-2 Mo 14,15 (gap 11-13)
    st.occupy("C_01#T", Candidate("C_01#T", "R2", "Tu", 16, 2))
    t = _global_terms(st, cfg)
    # idle: ADA-2 Mon {9,10,14,15} -> (16-9)-4 = 3 ; maxrun: runs of 2 -> 0
    # instr_days: i1 {Mo}=1, i2 {Tu}=1 -> 2 ; room_stable: each section 1 room -> 0
    # evening: C has hour 17 for its cohort and instructor -> 2
    # instr_idle: i1 has Mo {9,10,14,15} -> 3 ; fairness = cohort/instructor pain squares
    # free_day: no year config -> 0 ; conf: hours 9,10 each 2 courses -> 2
    assert t == {"idle": 3, "maxrun": 0, "instr_days": 2, "nonadjacent": 0,
                 "evening": 2, "instr_idle": 3, "fairness": 20,
                 "room_stable": 0, "free_day": 0, "conf": 2}


def test_local_terms_match_global_over_all_entities():
    from timetabling.soft_search import _global_terms, _local_terms
    cfg = Config()
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i1", level=2, code="ADA 202")
    d = _sec("D_01", "i1", level=2, code="ADA 203")
    c = _sec("C_01", "i2", level=1, code="EEE 101")
    st = _state(a, b, d, c)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    st.occupy("B_01#T", Candidate("B_01#T", "R3", "Mo", 9, 2))
    st.occupy("D_01#T", Candidate("D_01#T", "R1", "Mo", 14, 2))
    st.occupy("C_01#T", Candidate("C_01#T", "R2", "Tu", 16, 2))
    all_cohorts = {st.sec_of[bid].cohort_key for bid in st.placed}
    all_instrs = {iid for bid in st.placed for iid in st.sec_instr.get(st.sec_of[bid].section_id, [])}
    all_rooms = set(st.room_hours_used)
    all_blocks = set(st.placed)
    assert _local_terms(st, all_cohorts, all_instrs, all_rooms, all_blocks, cfg) == _global_terms(st, cfg)


def test_lahc_initializes_history_and_cursor():
    from timetabling.soft_search import LAHC
    acc = LAHC(history_len=3)
    acc.init(cost=100)
    assert acc.cost == 100.0
    assert acc.hist == [100.0, 100.0, 100.0]
    assert acc.pos == 0


def test_lahc_accepts_downhill_flat_and_late_uphill():
    from timetabling.soft_search import LAHC
    acc = LAHC(history_len=3)
    acc.init(cost=100)
    assert acc.accept(-10, 999) is True
    assert acc.cost == 90.0
    assert acc.accept(0, 999) is True
    assert acc.cost == 90.0
    assert acc.accept(+5, 999) is True       # 95 <= hist slot (100) -> late-accept
    assert acc.cost == 95.0


def test_lahc_rejects_above_current_and_late_history_but_advances():
    from timetabling.soft_search import LAHC
    acc = LAHC(history_len=3)
    acc.init(cost=100)
    assert acc.accept(-10, 0) is True        # 90, pos 0->1
    assert acc.accept(+5, 1) is True         # 95 <= hist[1]=100, pos 1->2
    assert acc.pos == 2
    assert acc.accept(+30, 2) is False       # 125 > cur 95 and > hist[2]=100 -> reject
    assert acc.cost == 95.0
    assert acc.hist[2] == 95.0               # reject still writes current cost
    assert acc.pos == 0                       # cursor advances on reject


def test_lahc_history_len_one_is_greedy_hill_climbing():
    from timetabling.soft_search import LAHC
    acc = LAHC(history_len=1)
    acc.init(cost=100)
    assert acc.accept(+1, 0) is False
    assert acc.cost == 100.0
    assert acc.accept(0, 0) is True
    assert acc.cost == 100.0
    assert acc.accept(-1, 0) is True
    assert acc.cost == 99.0


def test_lahc_uses_internal_cursor_not_external_iteration_id():
    from timetabling.soft_search import LAHC
    acc = LAHC(history_len=3)
    acc.init(cost=100)
    assert acc.pos == 0
    acc.accept(-1, 100)
    assert acc.pos == 1
    acc.accept(-1, 7)
    assert acc.pos == 2
    acc.accept(-1, 1000)
    assert acc.pos == 0


def test_make_acceptor_dispatches():
    from timetabling.config import Config
    from timetabling.soft_search import _make_acceptor, SCHC, LAHC, GreatDeluge, SimAnneal
    import random
    rng = random.Random(0)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="schc"), rng), SCHC)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="lahc"), rng), LAHC)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="deluge"), rng), GreatDeluge)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="sa"), rng), SimAnneal)


def test_soft_score_instr_days_tiebreak_is_dial_gated():
    """Construction-time instr_days bias: an instructor already at/over the day target pays a
    unit penalty for a NEW teaching day, zero for a day they already use; OFF (target == week
    length) adds nothing either way."""
    from dataclasses import replace
    from timetabling.repair import _soft_score
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="ADA 102")            # same instructor i1
    st = _state(a, b)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # i1 active days = {Mo}
    s_b = st.sec_of["B_01#T"]
    used = Candidate("B_01#T", "R2", "Mo", 11, 2)     # reuses Mo (no conflict at 11-13)
    new = Candidate("B_01#T", "R2", "Tu", 9, 2)       # opens a new day for i1

    off = replace(Config(), max_instr_days=5)          # 5 == len(days()) -> inert
    assert _soft_score(st, used, s_b, off) == 0
    assert _soft_score(st, new, s_b, off) == 0

    tight = replace(Config(), max_instr_days=1)         # i1 at 1 day -> a new day costs +1
    assert _soft_score(st, used, s_b, tight) == 0
    assert _soft_score(st, new, s_b, tight) == 1


def test_free_cohort_day_noop_when_year_not_configured():
    from dataclasses import replace
    from timetabling.soft_search import try_free_cohort_day, _global_terms
    # cohort ADA-2 (year=2) but free_day_year_levels only covers year 3
    cfg = replace(Config(), free_day_year_levels=(3,), w_free_day=10.0)
    days = ["Mo", "Tu", "We", "Th", "Fr"]
    secs = [_sec(f"S{i}", f"i{i}", level=2, code=f"ADA {200+i}") for i in range(5)]
    cand = {f"S{i}#T": [Candidate(f"S{i}#T", f"R{i}", d, 9, 2)] for i, d in enumerate(days)}
    st = _state(*secs)
    for i, d in enumerate(days):
        st.occupy(f"S{i}#T", cand[f"S{i}#T"][0])
    base = _global_terms(st, cfg)
    ev = _eval_fn(cfg, base)
    res = try_free_cohort_day(st, cand, "ADA-2", random.Random(0), ev, cfg)
    assert res is None


def test_free_cohort_day_noop_when_cohort_has_free_day():
    from dataclasses import replace
    from timetabling.soft_search import try_free_cohort_day, _global_terms
    # cohort ADA-2 only uses 4 of 5 days → already has a free day
    cfg = replace(Config(), free_day_year_levels=(2,), w_free_day=10.0)
    days_used = ["Mo", "Tu", "We", "Th"]  # Fr is free
    secs = [_sec(f"S{i}", f"i{i}", level=2, code=f"ADA {200+i}") for i in range(4)]
    cand = {f"S{i}#T": [Candidate(f"S{i}#T", f"R{i}", d, 9, 2)] for i, d in enumerate(days_used)}
    st = _state(*secs)
    for i, d in enumerate(days_used):
        st.occupy(f"S{i}#T", cand[f"S{i}#T"][0])
    base = _global_terms(st, cfg)
    ev = _eval_fn(cfg, base)
    res = try_free_cohort_day(st, cand, "ADA-2", random.Random(0), ev, cfg)
    assert res is None


def test_free_cohort_day_empties_target_day_and_lowers_free_day_term():
    from dataclasses import replace
    from timetabling.soft_search import try_free_cohort_day, _global_terms
    # cohort ADA-2 uses all 5 days (1 block each); each block has candidates on every other day
    cfg = replace(Config(), free_day_year_levels=(2,), w_free_day=10.0)
    all_days = ["Mo", "Tu", "We", "Th", "Fr"]
    secs = [_sec(f"S{i}", f"i{i}", level=2, code=f"ADA {200+i}") for i in range(5)]
    cand = {}
    for i, d in enumerate(all_days):
        bid = f"S{i}#T"
        # own day first so cand[bid][0] is the initial placement; alts follow
        cand[bid] = [Candidate(bid, f"R{i}", d, 9, 2)] + [
            Candidate(bid, f"R{i}", x, 9, 2) for x in all_days if x != d]
    st = _state(*secs)
    for i, d in enumerate(all_days):
        st.occupy(f"S{i}#T", cand[f"S{i}#T"][0])  # place each on its own day
    base = _global_terms(st, cfg)
    assert base["free_day"] == 1  # all 5 days used: max(0, 5-4) = 1
    ev = _eval_fn(cfg, base)
    res = try_free_cohort_day(st, cand, "ADA-2", random.Random(0), ev, cfg)
    assert res is not None
    dobj, dterms, revert = res
    assert dterms["free_day"] < 0            # free day created: term drops
    assert dobj < 0                          # objective improved
    assert len(st.placed) == 5              # placement invariant
    days_in_use = {c.day for bid, c in st.placed.items()
                   if st.sec_of[bid].cohort_key == "ADA-2"}
    assert len(days_in_use) == 4            # one day vacated


def test_free_cohort_day_revert_restores_state():
    from dataclasses import replace
    from timetabling.soft_search import try_free_cohort_day, _global_terms
    cfg = replace(Config(), free_day_year_levels=(2,), w_free_day=10.0)
    all_days = ["Mo", "Tu", "We", "Th", "Fr"]
    secs = [_sec(f"S{i}", f"i{i}", level=2, code=f"ADA {200+i}") for i in range(5)]
    cand = {}
    for i, d in enumerate(all_days):
        bid = f"S{i}#T"
        cand[bid] = [Candidate(bid, f"R{i}", d, 9, 2)] + [
            Candidate(bid, f"R{i}", x, 9, 2) for x in all_days if x != d]
    st = _state(*secs)
    for i, d in enumerate(all_days):
        st.occupy(f"S{i}#T", cand[f"S{i}#T"][0])  # places each on its own day
    base = _global_terms(st, cfg)
    snapshot_before = {bid: (c.day, c.start) for bid, c in st.placed.items()}
    ev = _eval_fn(cfg, base)
    res = try_free_cohort_day(st, cand, "ADA-2", random.Random(0), ev, cfg)
    assert res is not None
    _, _, revert = res
    revert()
    snapshot_after = {bid: (c.day, c.start) for bid, c in st.placed.items()}
    assert snapshot_before == snapshot_after
    assert _global_terms(st, cfg)["free_day"] == 1  # back to all-days-used


def test_free_cohort_day_returns_none_when_no_alt_available():
    from dataclasses import replace
    from timetabling.soft_search import try_free_cohort_day, _global_terms
    # cohort ADA-2 uses all 5 days; the lightest day (Mo) has 1 block with NO off-day candidates
    cfg = replace(Config(), free_day_year_levels=(2,), w_free_day=10.0)
    all_days = ["Mo", "Tu", "We", "Th", "Fr"]
    secs = [_sec(f"S{i}", f"i{i}", level=2, code=f"ADA {200+i}") for i in range(5)]
    cand = {}
    for i, d in enumerate(all_days):
        bid = f"S{i}#T"
        if i == 0:  # S0 on Mo: only same-day candidates (no alternatives off Mo)
            cand[bid] = [Candidate(bid, f"R{i}", "Mo", 9, 2), Candidate(bid, f"R{i}", "Mo", 11, 2)]
        else:
            cand[bid] = [Candidate(bid, f"R{i}", d, 9, 2)]
    st = _state(*secs)
    for i, d in enumerate(all_days):
        st.occupy(f"S{i}#T", cand[f"S{i}#T"][0])
    # Ensure Mo is the chosen src_day by making its block the only one with alternatives filtered out
    # (already guaranteed since all days have 1 block and Mo is first in dict iteration order)
    base = _global_terms(st, cfg)
    ev = _eval_fn(cfg, base)
    res = try_free_cohort_day(st, cand, "ADA-2", random.Random(0), ev, cfg)
    assert res is None
    # state must be unchanged after failed attempt
    assert all(st.placed[f"S{i}#T"].day == d for i, d in enumerate(all_days))


def test_anneal_free_cohort_day_steers_free_day_term():
    from dataclasses import replace
    from timetabling.soft_search import anneal_soft, _global_terms
    # cohort ADA-2 fills all 5 days; anneal_soft with free_day_year_levels=(2,) should
    # trigger try_free_cohort_day and reduce the free_day term to 0
    cfg = replace(Config(), free_day_year_levels=(2,), w_free_day=20.0)
    all_days = ["Mo", "Tu", "We", "Th", "Fr"]
    starts = [9, 11, 13, 15, 17]  # staggered: any two sections can share a day without time-overlap
    secs = [_sec(f"S{i}", f"i{i}", level=2, code=f"ADA {200+i}") for i in range(5)]
    cand = {}
    for i, d in enumerate(all_days):
        bid = f"S{i}#T"
        # Each section keeps its own start time on any day so consolidation never creates conf
        cand[bid] = [Candidate(bid, f"R{i}", d, starts[i], 1)] + [
            Candidate(bid, f"R{i}", x, starts[i], 1) for x in all_days if x != d]
    st = _state(*secs)
    for i, d in enumerate(all_days):
        st.occupy(f"S{i}#T", cand[f"S{i}#T"][0])  # places each on its own day
    t0 = _global_terms(st, cfg)
    assert t0["free_day"] == 1
    placed_before = len(st.placed)
    anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == placed_before       # placement invariant
    assert t1["conf"] <= t0["conf"]              # conflict guard
    assert t1["free_day"] < t0["free_day"]       # free day created


def test_soft_score_cohort_conflict_dominates_instr_days():
    """The instr_days tie-break is strictly below one cohort-conflict unit, so greedy never
    trades a student conflict for instructor concentration."""
    from dataclasses import replace
    from timetabling.repair import _soft_score
    a = _sec("A_01", "i1", level=2, code="ADA 201")     # cohort ADA-2
    b = _sec("B_01", "i1", level=2, code="ADA 202")     # same cohort + instructor
    st = _state(a, b)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # ADA-2 busy Mo 9-11; i1 {Mo}
    s_b = st.sec_of["B_01#T"]
    tight = replace(Config(), max_instr_days=1)
    on_mo = Candidate("B_01#T", "R2", "Mo", 9, 2)       # reuses Mo (0 days) but 2h conflict
    on_tu = Candidate("B_01#T", "R2", "Tu", 9, 2)       # new day (+1) but conflict-free
    assert _soft_score(st, on_mo, s_b, tight) == 2 * Config().w_cohort_conflict
    assert _soft_score(st, on_tu, s_b, tight) == 1
    assert _soft_score(st, on_mo, s_b, tight) > _soft_score(st, on_tu, s_b, tight)
