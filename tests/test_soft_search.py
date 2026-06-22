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
    cfg = Config()  # w_instr_days=3, w_room_count=2
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


def test_relocate_lowers_soft_and_keeps_placement():
    from timetabling.soft_search import try_relocate
    cfg = Config()
    a = _sec("A_01", "i1")                       # level 1, evening is the only soft
    cand = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2),   # evening (hour 17) cost 10
                       Candidate("A_01#T", "R1", "Mo", 9, 2)]}    # morning cost 0
    st = _state(a)
    st.occupy("A_01#T", cand["A_01#T"][0])       # park in evening
    rng = random.Random(0)
    res = try_relocate(st, cand, "A_01#T", rng, cfg)
    assert res is not None
    delta, revert = res
    assert delta == -10                          # evening -> morning
    assert len(st.placed) == 1                   # never unplaced
    assert st.placed["A_01#T"].start == 9
    revert()                                     # revert restores the evening slot
    assert st.placed["A_01#T"].start == 16


def test_swap_helps_where_relocate_cannot():
    from timetabling.soft_search import try_swap
    cfg = Config()
    # i1 teaches A (level2, S-Order penalizes late start). Two single-room slots, both full.
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i2", level=1, code="EEE 101")
    # A at late slot R1 Mo13 (S-Order (4-2)*(13-9)=8); B at early R1 Mo9 (level1 -> 0).
    # Swap -> A at Mo9 (0), B at Mo13 (0). delta = -8. No empty slot exists (relocate stuck).
    cand = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 13, 2), Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2), Candidate("B_01#T", "R1", "Mo", 13, 2)],
    }
    st = _state(a, b)
    st.occupy("A_01#T", cand["A_01#T"][0])       # Mo13
    st.occupy("B_01#T", cand["B_01#T"][0])       # Mo9
    res = try_swap(st, cand, "A_01#T", "B_01#T", cfg)
    assert res is not None
    delta, revert = res
    assert delta == -8
    assert st.placed["A_01#T"].start == 9 and st.placed["B_01#T"].start == 13
    assert len(st.placed) == 2


def test_moves_keep_hard_feasibility():
    from timetabling.soft_search import try_relocate
    cfg = Config()
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i1": Instructor("i1", "x", True, "D")}
    a = _sec("A_01", "i1")
    cand = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 16, 2),
                       Candidate("A_01#T", "R1", "Mo", 9, 2)]}
    st = _state(a)
    st.occupy("A_01#T", cand["A_01#T"][0])
    rng = random.Random(1)
    try_relocate(st, cand, "A_01#T", rng, cfg)
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


def test_anneal_soft_never_raises_soft_and_keeps_placement():
    from timetabling.soft_search import anneal_soft
    cfg = Config()
    secs = [_sec(f"S{n}_01", f"i{n}", level=1, code=f"ADA 10{n}") for n in range(8)]
    cand = {}
    st = _state(*secs)
    for n, s in enumerate(secs):
        bid = f"S{n}_01#T"
        # each block: an evening option (parked) + a free morning option in its own room
        cand[bid] = [Candidate(bid, f"R{n}", "Mo", 16, 2), Candidate(bid, f"R{n}", "Mo", 9, 2)]
        st.occupy(bid, cand[bid][0])             # park all in evening
    start_soft = _soft_total(st, cfg)
    placed_before = len(st.placed)
    stats = anneal_soft(st, cand, cfg, budget_s=2.0, seed=0)
    assert len(st.placed) == placed_before       # placement invariant
    assert stats["soft_end"] <= stats["soft_start"]
    assert _soft_total(st, cfg) <= start_soft     # never worse than start
    assert _soft_total(st, cfg) < start_soft      # and here it strictly improves (all evenings clearable)
