from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, greedy_construct


def _sec(sid, iid):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
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
