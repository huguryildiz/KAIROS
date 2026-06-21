from timetabling.config import Config
from timetabling.model import Section, Block, Candidate
from timetabling.repair import _cand_soft, State, repair_round


def _sec(sid, iid, level=1, faculty="F", code="X 101"):
    s = Section(sid, "001", code, "x", level, code.split()[0], faculty,
                f"{code.split()[0]}-{level}", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_cand_soft_counts_evening_hours():
    cfg = Config()  # w_evening=10, evening_from_hour=17
    s = _sec("A_01", "i1")
    morning = Candidate("A_01#T", "R1", "Mo", 9, 2)   # 9-11, no evening
    evening = Candidate("A_01#T", "R1", "Mo", 16, 2)  # 16-18, hour 17 is evening
    assert _cand_soft(morning, s, cfg) == 0
    assert _cand_soft(evening, s, cfg) == 10


def test_cand_soft_penalizes_late_start_for_low_levels():
    cfg = Config()  # w_order=1
    s = _sec("A_01", "i1", level=2)
    early = Candidate("A_01#T", "R1", "Mo", 9, 2)    # (4-2)*(9-9)=0
    late = Candidate("A_01#T", "R1", "Mo", 14, 2)    # (4-2)*(14-9)=10
    assert _cand_soft(early, s, cfg) == 0
    assert _cand_soft(late, s, cfg) == 10


def _state(*secs):
    sec_of = {b.block_id: s for s in secs for b in s.blocks}
    sec_instr = {s.section_id: s.instructor_ids for s in secs}
    return State(sec_of, sec_instr, set())


def test_repair_round_pulls_block_off_evening_when_placement_equal():
    cfg = Config()
    a = _sec("A_01", "i1")
    cands = {"A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2),
                        Candidate("A_01#T", "R1", "Mo", 16, 2)]}
    st = _state(a)
    st.occupy("A_01#T", cands["A_01#T"][1])     # park in evening
    repair_round(st, ["A_01#T"], cands, cfg)
    assert st.placed["A_01#T"].start == 9       # secondary soft pulls it to morning


def test_soft_never_costs_a_placement():
    cfg = Config()
    a, b = _sec("A_01", "i1"), _sec("B_01", "i2")
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2),     # soft-best, contested
                   Candidate("A_01#T", "R1", "Mo", 16, 2)],   # evening, free
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2)],    # only morning R1@9
    }
    st = _state(a, b)
    repair_round(st, ["A_01#T", "B_01#T"], cands, cfg)
    assert len(st.placed) == 2                   # placement dominates soft
    assert st.placed["A_01#T"].start == 16
    assert st.placed["B_01#T"].start == 9


def test_repair_avoids_cohort_conflict_when_placement_equal():
    # Two different courses in the SAME cohort; B is fixed Mo 9-11. A can go Mo 9-11
    # (conflict) or Tu 9-11 (no conflict) — equal placement, so soft must pick Tu.
    cfg = Config()
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i2", level=2, code="ADA 202")  # same cohort ADA-2
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2),
                   Candidate("A_01#T", "R2", "Tu", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R2", "Mo", 9, 2)],
    }
    st = _state(a, b)
    st.occupy("B_01#T", cands["B_01#T"][0])      # B fixed Mo
    st.occupy("A_01#T", cands["A_01#T"][0])      # A parked Mo (conflicts with B's cohort slot)
    repair_round(st, ["A_01#T"], cands, cfg)     # B is a frozen competitor
    assert st.placed["A_01#T"].day == "Tu"       # moved off the conflicting cohort slot


def test_repair_compacts_cohort_day_when_placement_equal():
    # cohort ADA-2: B fixed Mo 9-11. A parked Mo 13-15 (2h gap) but can go Mo 11-13
    # (contiguous, gap 0). Equal placement -> cohort_gap term must pick the contiguous slot.
    cfg = Config()
    a = _sec("A_01", "i1", level=2, code="ADA 201")
    b = _sec("B_01", "i2", level=2, code="ADA 202")
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 11, 2),   # contiguous after B -> gap 0
                   Candidate("A_01#T", "R1", "Mo", 13, 2)],  # leaves an 11-13 idle gap
        "B_01#T": [Candidate("B_01#T", "R2", "Mo", 9, 2)],
    }
    st = _state(a, b)
    st.occupy("B_01#T", cands["B_01#T"][0])
    st.occupy("A_01#T", cands["A_01#T"][1])     # parked at the gappy 13
    repair_round(st, ["A_01#T"], cands, cfg)
    assert st.placed["A_01#T"].start == 11


def test_cohort_gap_term_isolated_from_s_order():
    # Isolates cohort_gap from S-Order: both A options START at 13 (identical S-Order
    # and evening cost), so only the per-(cohort,day) idle gap can break the tie.
    # cohort ADA-3 (compact year 3). B fixed Mo 9-11.
    #   A=Mo 13-15 -> Monday cohort hours {9,10,13,14}: span 6 - load 4 = gap 2
    #   A=Tu 13-15 -> no idle gap on any day: gap 0
    cfg = Config()
    a = _sec("A_01", "i1", level=3, code="ADA 301")
    b = _sec("B_01", "i2", level=3, code="ADA 302")  # same cohort ADA-3
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 13, 2),   # gap 2 within Monday
                   Candidate("A_01#T", "R1", "Tu", 13, 2)],  # gap 0
        "B_01#T": [Candidate("B_01#T", "R2", "Mo", 9, 2)],
    }
    st = _state(a, b)
    st.occupy("B_01#T", cands["B_01#T"][0])
    st.occupy("A_01#T", cands["A_01#T"][0])     # parked on the gappy Monday slot
    repair_round(st, ["A_01#T"], cands, cfg)
    assert st.placed["A_01#T"].day == "Tu"      # cohort_gap term moves it off Monday
