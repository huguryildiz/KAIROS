from timetabling.config import Config
from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, greedy_construct


def _sec(sid, iid):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def _sec_code(sid, iid, code, cohort):
    s = Section(sid, "001", code, "x", 1, "X", "F", cohort, [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_greedy_places_both_in_distinct_slots():
    a, b = _sec("A_01", "i1"), _sec("B_01", "i1")   # same instructor -> must differ in time
    sec_of = {"A_01#T": a, "B_01#T": b}
    sec_instr = {"A_01": ["i1"], "B_01": ["i1"]}
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2), Candidate("B_01#T", "R1", "Mo", 11, 2)],
    }
    st = State(sec_of, sec_instr, set())
    greedy_construct(st, ["A_01#T", "B_01#T"], cands)
    assert len(st.placed) == 2
    assert st.placed["B_01#T"].start == 11   # forced off the taken 9:00 slot


def test_greedy_prefers_daytime_under_soft_shaping():
    a = _sec("A_01", "i1")
    st = State({"A_01#T": a}, {"A_01": ["i1"]}, set())
    cands = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 17, 2),   # evening, listed first
                        Candidate("A_01#T", "R1", "Mo", 9, 2)]}   # daytime
    greedy_construct(st, ["A_01#T"], cands, Config())
    assert st.placed["A_01#T"].start == 9    # shaping picked daytime over the first (evening)


def test_greedy_avoids_cohort_conflict_under_soft_shaping():
    a = _sec_code("A_01", "i1", "MATH 101", "X-1")
    b = _sec_code("B_01", "i2", "PHYS 101", "X-1")   # same cohort, diff instructor+room
    st = State({"A_01#T": a, "B_01#T": b}, {"A_01": ["i1"], "B_01": ["i2"]}, set())
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # MATH at Mo 9-11
    cands = {"B_01#T": [Candidate("B_01#T", "R2", "Mo", 9, 2),    # overlaps cohort slot
                        Candidate("B_01#T", "R2", "Mo", 11, 2)]}  # no overlap
    greedy_construct(st, ["B_01#T"], cands, Config())
    assert st.placed["B_01#T"].start == 11   # avoided the cohort-conflicting 9:00 slot


def test_soft_shaping_off_is_first_feasible():
    a = _sec("A_01", "i1")
    st = State({"A_01#T": a}, {"A_01": ["i1"]}, set())
    cands = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 17, 2),
                        Candidate("A_01#T", "R1", "Mo", 9, 2)]}
    greedy_construct(st, ["A_01#T"], cands, Config(soft_shaping_in_repair=False))
    assert st.placed["A_01#T"].start == 17   # no shaping -> first feasible


def test_overload_shaping_independent_of_soft_toggle():
    a = _sec("A_01", "i1")
    b = _sec("B_01", "i1")    # same instructor i1
    st = State({"A_01#T": a, "B_01#T": b}, {"A_01": ["i1"], "B_01": ["i1"]}, set())
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # i1 has 2h Monday
    cands = {"B_01#T": [Candidate("B_01#T", "R1", "Mo", 11, 2),  # Mon -> i1 hits 4h
                        Candidate("B_01#T", "R1", "Tu", 9, 2)]}  # Tue -> no overload
    cfg = Config(soft_shaping_in_repair=False, w_instr_daily_overload=50, max_instr_daily_hours=2)
    greedy_construct(st, ["B_01#T"], cands, cfg, eligible={"i1"}, cap=2)
    assert st.placed["B_01#T"].day == "Tu"   # overload shaping still active with soft off
