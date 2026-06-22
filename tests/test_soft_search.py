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


def test_soft_total_includes_instr_days_and_room_count():
    from dataclasses import replace
    cfg = replace(Config(), w_instr_days=3, w_room_count=2)   # pin weights (default-independent)
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i1", code="ADA 102")     # same instructor i1
    st = _state(a, b)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    st.occupy("B_01#T", Candidate("B_01#T", "R2", "Tu", 9, 2))
    # i1 teaches 2 days -> w_instr_days*2 = 6 ; 2 distinct rooms -> w_room_count*2 = 4
    # evening/order/cohort all zero here
    assert _soft_total(st, cfg) == 6 + 4
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
    a = _sec("A_01", "i1")                       # level 1, evening is the only toggle here
    cand = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2),   # evening (hour 17)
                       Candidate("A_01#T", "R1", "Mo", 9, 2)]}    # morning
    st = _state(a)
    st.occupy("A_01#T", cand["A_01#T"][0])       # park in evening
    ev = _eval_fn(cfg, _global_terms(st, cfg))
    rng = random.Random(0)
    res = try_relocate(st, cand, "A_01#T", rng, ev)
    assert res is not None
    dobj, dterms, revert = res
    assert dobj < 0                              # evening removed -> normalized E drops
    assert dterms["conf"] == 0
    assert len(st.placed) == 1                   # never unplaced
    assert st.placed["A_01#T"].start == 9
    revert()                                     # revert restores the evening slot
    assert st.placed["A_01#T"].start == 16


def test_swap_lowers_objective_where_relocate_cannot():
    from timetabling.soft_search import try_swap, _global_terms
    cfg = Config()
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
    # 8 distinct-cohort sections, each in its own room, all parked in the evening.
    secs = [_sec(f"S{n}_01", f"i{n}", level=1, code=f"C{n} 101") for n in range(8)]
    cand = {}
    st = _state(*secs)
    for n, s in enumerate(secs):
        bid = f"S{n}_01#T"
        cand[bid] = [Candidate(bid, f"R{n}", "Mo", 16, 2), Candidate(bid, f"R{n}", "Mo", 9, 2)]
        st.occupy(bid, cand[bid][0])             # park all in evening
    t0 = _global_terms(st, cfg)
    placed_before = len(st.placed)
    anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == placed_before       # placement invariant
    assert t1["conf"] <= t0["conf"]              # cohort-conflict guard never exceeded
    assert t1["evening"] < t0["evening"]         # evening toggle strictly improved


def test_anneal_lowers_objective_via_swap_dense():
    from timetabling.soft_search import anneal_soft, _global_terms
    cfg = Config()
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
    assert t1["days"] < t0["days"]               # only a swap can lower days here


def test_chain_unlocks_where_relocate_and_swap_cannot():
    from timetabling.soft_search import try_chain, try_relocate, try_swap, _global_terms
    cfg = Config()
    # A is parked in the evening; its only morning candidate (R1 Mo9) is occupied by B, and
    # B has no candidate at A's evening slot -> neither relocate nor swap can move A. But an
    # ejection chain can: A -> R1 Mo9 ejecting B -> R2 Mo9 (a free slot). evening drops.
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i2", code="BBB 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2), Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2), Candidate("B_01#T", "R2", "Mo", 9, 2)],
    }
    st = _state(a, b)
    st.occupy("A_01#T", cand["A_01#T"][0])        # A evening R1 Mo16
    st.occupy("B_01#T", cand["B_01#T"][0])        # B morning R1 Mo9 (blocks A's target)
    ev = _eval_fn(cfg, _global_terms(st, cfg))
    assert try_relocate(st, cand, "A_01#T", random.Random(0), ev) is None   # target occupied
    assert try_swap(st, cand, "A_01#T", "B_01#T", ev) is None               # no reciprocal cand
    res = try_chain(st, cand, "A_01#T", random.Random(0), ev, max_depth=3)
    assert res is not None
    dobj, dterms, revert = res
    assert dterms["evening"] < 0                   # chain pulled A out of the evening
    assert st.placed["A_01#T"].start == 9 and st.placed["B_01#T"].room == "R2"
    assert len(st.placed) == 2
    revert()
    assert st.placed["A_01#T"].start == 16 and st.placed["B_01#T"].room == "R1"


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


def test_cheby_is_max_plus_small_sum_augmentation():
    from timetabling.soft_search import _cheby, CHEBY_RHO
    cfg = Config()  # w_evening=w_cohort_gap=w_room_count=w_instr_days=10
    base = {"evening": 10, "gap": 10, "rooms": 10, "days": 10, "conf": 0}
    # all at baseline -> each normalized value = 10 ; cheby = max(10) + rho*sum(40)
    assert abs(_cheby(base, base, cfg) - (10 + CHEBY_RHO * 40)) < 1e-9
    # halving the WORST (here all equal) term lowers the max; halving below others only
    # lowers the sum-augmentation. Reducing one term to 0 -> max still 10 (others), sum 30.
    one_zero = {"evening": 0, "gap": 10, "rooms": 10, "days": 10, "conf": 0}
    assert abs(_cheby(one_zero, base, cfg) - (10 + CHEBY_RHO * 30)) < 1e-9
    # reducing ALL four lowers the max itself -> much smaller objective
    all_low = {"evening": 5, "gap": 5, "rooms": 5, "days": 5, "conf": 0}
    assert _cheby(all_low, base, cfg) < _cheby(one_zero, base, cfg)


def test_anneal_with_chains_lowers_evening_keeps_invariants():
    from timetabling.soft_search import anneal_soft, _global_terms
    cfg = Config()
    # A parked in the evening; its morning slot is blocked by B. B can escape to R2 (already
    # opened by C, so no new room). The wired loop (relocate+swap+chain) should pull A out of
    # the evening without regressing conflict or placement.
    a = _sec("A_01", "i1", code="ADA 101")
    b = _sec("B_01", "i2", code="BBB 101")
    c = _sec("C_01", "i3", code="CCC 101")
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2), Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2), Candidate("B_01#T", "R2", "Mo", 9, 2)],
        "C_01#T": [Candidate("C_01#T", "R2", "Mo", 14, 2)],
    }
    st = _state(a, b, c)
    st.occupy("A_01#T", cand["A_01#T"][0])
    st.occupy("B_01#T", cand["B_01#T"][0])
    st.occupy("C_01#T", cand["C_01#T"][0])
    t0 = _global_terms(st, cfg)
    anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    t1 = _global_terms(st, cfg)
    assert len(st.placed) == 3            # placement invariant
    assert t1["conf"] <= t0["conf"]       # conflict guard
    assert t1["evening"] < t0["evening"]  # A pulled out of the evening


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


def test_global_terms_raw_four_terms_plus_conf():
    from timetabling.soft_search import _global_terms
    cfg = Config()
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i1", level=2, code="ADA 202")   # same cohort ADA-2 + instr i1
    d = _sec("D_01", "i1", level=2, code="ADA 203")   # same cohort ADA-2 + instr i1
    c = _sec("C_01", "i2", level=1, code="EEE 101")
    st = _state(a, b, d, c)
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # ADA-2 Mo 9,10
    st.occupy("B_01#T", Candidate("B_01#T", "R3", "Mo", 9, 2))   # ADA-2 Mo 9,10 (conflict)
    st.occupy("D_01#T", Candidate("D_01#T", "R1", "Mo", 14, 2))  # ADA-2 Mo 14,15 (gap 11-13)
    st.occupy("C_01#T", Candidate("C_01#T", "R2", "Tu", 16, 2))  # evening hour 17
    t = _global_terms(st, cfg)
    # evening: only hour 17 >= 17 -> 1 ; gap: ADA-2 Mon {9,10,14,15} -> (16-9)-4 = 3
    # rooms: R1,R3,R2 -> 3 ; days: i1 {Mo}=1, i2 {Tu}=1 -> 2 ; conf: hours 9,10 each 2 courses -> 2
    assert t == {"evening": 1, "gap": 3, "rooms": 3, "days": 2, "conf": 2}


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


def test_lahc_accepts_against_history():
    from timetabling.soft_search import LAHC
    acc = LAHC(history_len=3)
    acc.init(cost=100)
    assert acc.accept(-10, 0) is True       # 90 <= hist[0]=100 -> accept, cost=90
    assert acc.accept(+5, 1) is True        # 95 <= hist[1]=100 -> accept, cost=95
    assert acc.accept(+30, 2) is False      # 125 > hist[2]=100 and > cur 95 -> reject


def test_make_acceptor_dispatches():
    from timetabling.config import Config
    from timetabling.soft_search import _make_acceptor, SCHC, LAHC, GreatDeluge, SimAnneal
    import random
    rng = random.Random(0)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="schc"), rng), SCHC)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="lahc"), rng), LAHC)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="deluge"), rng), GreatDeluge)
    assert isinstance(_make_acceptor(Config(soft_polish_acceptor="sa"), rng), SimAnneal)
