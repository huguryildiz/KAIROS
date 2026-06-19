from timetabling.model import Room, Section
from timetabling.config import Config
from timetabling.route import mark_virtual


def _sec(sid, students, plan_room=""):
    return Section(section_id=sid, period="001", code="X 101", name="x", level=1,
                   dept_code="X", faculty="F", cohort_key="X-1", instructor_ids=["i"],
                   students=students, T=2, P=0, L=0, Cr=2, category="",
                   plan_room=plan_room)


def test_marks_online_and_oversize_virtual():
    rooms = {"R": Room("R", 100, False, True), "Online": Room("Online", 9999, False, False, True)}
    cfg = Config()
    secs = [_sec("a", 50), _sec("b", 148, "Online"), _sec("c", 497), _sec("d", 100)]
    mark_virtual(secs, rooms, cfg)
    assert [s.is_virtual for s in secs] == [False, True, True, False]
