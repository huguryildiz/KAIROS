from timetabling import io_csv, clean
from timetabling.config import Config


def test_classify_room():
    assert clean.classify_room("A514-PC-L") is True
    assert clean.classify_room("A211-PC-L") is True
    assert clean.classify_room("A231-H") is False
    assert clean.classify_room("F306") is False


def test_build_rooms_marks_online_nonphysical_and_lab_count():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    assert "Online" in rooms and rooms["Online"].is_physical is False
    physical = [r for r in rooms.values() if r.is_physical and not r.room.startswith("AMFI-")]
    assert len(physical) == 100                      # 101 CSV rooms - 1 online (excl. synthetic halls)
    labs = [r for r in physical if r.is_lab]
    assert 8 <= len(labs) <= 20                       # ~14 lab/PC rooms
    assert rooms["A216"].cap == 25


def test_build_instructors_full_vs_part_time():
    instr = clean.build_instructors(io_csv.load_lecturers())
    assert len(instr) == 340
    sample = next(iter(instr.values()))
    assert isinstance(sample.is_staff, bool)
