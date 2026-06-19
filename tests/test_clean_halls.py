from timetabling import io_csv, clean
from timetabling.config import Config

def test_extra_halls_added():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    names = [r for r in rooms if r.startswith("AMFI-")]
    assert len(names) == 2 + 3 + 4                  # (500,2)+(250,3)+(150,4)
    assert rooms["AMFI-500-1"].cap == 500
    assert rooms["AMFI-500-1"].is_physical and not rooms["AMFI-500-1"].is_lab
    assert sum(1 for n in names if rooms[n].cap == 250) == 3

def test_no_extra_halls_when_empty():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config(extra_rooms=()))
    assert not any(n.startswith("AMFI-") for n in rooms)

def test_largest_hall_fits_max_section():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    assert max(r.cap for r in rooms.values()) >= 497
