from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, greedy_construct, competitors, repair_round


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


def test_repair_round_prioritizes_frequent_competitor_when_free_set_is_tight():
    # B has three possible slots. Two are blocked by A, and A has an escape slot. One is
    # blocked by C, which has no useful escape. With room for only one competitor, the
    # ranked competitor list must free A rather than depend on set iteration order.
    a = _sec("A_01", "i1")
    b = _sec("B_01", "i2")
    c = _sec("C_01", "i3")
    sec_of = {block.block_id: section for section in (a, b, c) for block in section.blocks}
    sec_instr = {section.section_id: section.instructor_ids for section in (a, b, c)}
    cands = {
        "A_01#T": [
            Candidate("A_01#T", "R1", "Mo", 9, 2),
            Candidate("A_01#T", "R1", "Mo", 11, 2),
            Candidate("A_01#T", "R2", "Mo", 9, 2),
        ],
        "B_01#T": [
            Candidate("B_01#T", "R1", "Mo", 9, 1),
            Candidate("B_01#T", "R1", "Mo", 10, 1),
            Candidate("B_01#T", "R3", "Mo", 9, 1),
        ],
        "C_01#T": [Candidate("C_01#T", "R3", "Mo", 9, 2)],
    }
    st = State(sec_of, sec_instr, set())
    st.occupy("A_01#T", cands["A_01#T"][0])
    st.occupy("C_01#T", cands["C_01#T"][0])

    assert competitors(st, ["B_01#T"], cands)[0] == "A_01#T"
    gained = repair_round(st, ["B_01#T"], cands, max_free=2)

    assert gained == 1
    assert st.placed["B_01#T"].room == "R1"
    assert len(st.placed) == 3
