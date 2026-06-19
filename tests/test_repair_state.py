from timetabling.model import Section, Block, Candidate
from timetabling.repair import State


def _sec(sid, iid):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_room_conflict_blocks_second_placement():
    a, b = _sec("A_01", "i1"), _sec("B_01", "i2")
    st = State({"A_01#T": a, "B_01#T": b},
               {"A_01": ["i1"], "B_01": ["i2"]}, set())
    ca = Candidate("A_01#T", "R1", "Mo", 9, 2)
    st.occupy("A_01#T", ca)
    cb = Candidate("B_01#T", "R1", "Mo", 9, 2)  # same room+slot
    assert st.free_to_place(cb, "B_01", ["i2"]) is False
    st.release("A_01#T")
    assert st.free_to_place(cb, "B_01", ["i2"]) is True


def test_virtual_room_never_room_conflicts():
    a, b = _sec("A_01", "i1"), _sec("B_01", "i2")
    st = State({"A_01#T": a, "B_01#T": b},
               {"A_01": ["i1"], "B_01": ["i2"]}, {"Online"})
    st.occupy("A_01#T", Candidate("A_01#T", "Online", "Mo", 9, 2))
    cb = Candidate("B_01#T", "Online", "Mo", 9, 2)
    assert st.free_to_place(cb, "B_01", ["i2"]) is True   # different instructors, virtual room
