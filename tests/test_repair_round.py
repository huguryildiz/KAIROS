from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, greedy_construct, repair_round


def _sec(sid, iid):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_repair_places_a_blocked_section_by_moving_competitor():
    # A occupies the only slot B's narrow candidate wants; A also has an alt slot.
    a = _sec("A_01", "i1")
    b = _sec("B_01", "i2")
    sec_of = {"A_01#T": a, "B_01#T": b}
    sec_instr = {"A_01": ["i1"], "B_01": ["i2"]}
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2), Candidate("A_01#T", "R2", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2)],   # only R1@9
    }
    st = State(sec_of, sec_instr, set())
    # construct parks A on R1@9 (first free), blocking B's only option
    greedy_construct(st, ["A_01#T", "B_01#T"], cands)
    assert "B_01#T" not in st.placed              # B blocked after construction
    gained = repair_round(st, ["B_01#T"], cands)
    assert gained == 1
    assert len(st.placed) == 2                    # A moved to R2, B took R1@9
    assert st.placed["B_01#T"].room == "R1"
