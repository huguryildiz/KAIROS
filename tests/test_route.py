from timetabling.model import Room, Section
from timetabling.config import Config
from timetabling.route import mark_virtual, mark_lab_rooms


def _lab_sec(sid, plan_room):
    return Section(sid, "001", "X 101", "x", 2, "X", "F", "X-2", ["i"], 30,
                   2, 0, 2, 4, "", plan_room=plan_room)


def test_mark_lab_rooms_pins_designated_lab_room():
    rooms = {"A514-PC-L": Room("A514-PC-L", 30, True, True),
             "DB14": Room("DB14", 40, False, True),
             "DB16": Room("DB16", 40, False, True)}
    s1 = _lab_sec("CMPE 113_02", "A514-PC-L DB14")   # lab token present -> pin
    s2 = _lab_sec("ECON 331_01", "DB16 D232")         # no lab token -> empty
    mark_lab_rooms([s1, s2], rooms, Config())
    assert s1.lab_room == "A514-PC-L"
    assert s2.lab_room == ""


def _sec(sid, students, plan_room=""):
    return Section(section_id=sid, period="001", code="X 101", name="x", level=1,
                   dept_code="X", department="F", cohort_key="X-1", instructor_ids=["i"],
                   students=students, T=2, P=0, L=0, Cr=2, category="",
                   plan_room=plan_room)


def test_marks_online_and_oversize_virtual():
    rooms = {"R": Room("R", 100, False, True), "Online": Room("Online", 9999, False, False, True)}
    cfg = Config()
    secs = [_sec("a", 50), _sec("b", 148, "Online"), _sec("c", 497), _sec("d", 100)]
    mark_virtual(secs, rooms, cfg)
    assert [s.is_virtual for s in secs] == [False, True, True, False]
