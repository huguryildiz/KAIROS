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
