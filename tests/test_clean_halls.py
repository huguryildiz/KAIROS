from timetabling import io_csv, clean
from timetabling.config import Config


def test_no_synthetic_halls_by_default():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    assert not any(n.startswith("AMFI-") for n in rooms)


def test_halls_injected_when_configured():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config(extra_rooms=((500, 1),)))
    assert "AMFI-500-1" in rooms and rooms["AMFI-500-1"].cap == 500
