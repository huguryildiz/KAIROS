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


def _sec_code(sid, iid, code, cohort):
    s = Section(sid, "001", code, "x", 1, "X", "F", cohort, [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_cohort_slot_courses_tracks_and_releases():
    a = _sec_code("A_01", "i1", "MATH 101", "X-1")
    st = State({"A_01#T": a}, {"A_01": ["i1"]}, set())
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))   # spans 9 and 10
    assert "MATH 101" in st.cohort_slot_courses[("X-1", "Mo", 9)]
    assert "MATH 101" in st.cohort_slot_courses[("X-1", "Mo", 10)]
    st.release("A_01#T")
    assert "MATH 101" not in st.cohort_slot_courses[("X-1", "Mo", 9)]


def test_cohort_slot_courses_distinct_courses_coexist():
    a = _sec_code("A_01", "i1", "MATH 101", "X-1")
    b = _sec_code("B_01", "i2", "PHYS 101", "X-1")
    st = State({"A_01#T": a, "B_01#T": b}, {"A_01": ["i1"], "B_01": ["i2"]}, set())
    st.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    st.occupy("B_01#T", Candidate("B_01#T", "R2", "Mo", 9, 2))   # same cohort-slot, diff course
    assert set(st.cohort_slot_courses[("X-1", "Mo", 9)]) == {"MATH 101", "PHYS 101"}
