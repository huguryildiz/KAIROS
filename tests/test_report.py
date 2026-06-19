from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import report


def test_parse_existing_builds_assignments_from_plan_schedule():
    s = Section("ADA 403_01", "001", "ADA 403", "EDA", 4, "ADA", "Fac", "ADA-4",
                "i1", 24, 3, 0, 0, 3, "Course")
    s.blocks = [Block("ADA 403_01#T", "ADA 403_01", "theory", 3, False)]
    frame = {"ADA 403_01": {"plan_room": "G005", "plan_schedule": "Fr 13 - 16"}}
    assigns = report.parse_existing(frame, [s])
    assert len(assigns) == 1
    a = assigns[0]
    assert a.day == "Fr" and a.start == 13 and a.end == 16 and a.room == "G005"


def test_mode_b_benchmark_shape():
    s = Section("S_01", "001", "S 101", "n", 1, "S", "Fac", "S-1", "i1", 10,
                2, 0, 0, 2, "Course")
    s.blocks = [Block("S_01#T", "S_01", "theory", 2, False)]
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i1": Instructor("i1", "n", False, "S")}
    a = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]
    bench = report.mode_b_benchmark("001", a, a, [s], rooms, instr, Config())
    assert "mode_a" in bench and "existing" in bench
    assert "conflicts" in bench["mode_a"] and "rooms_used" in bench["mode_a"]
    assert "evening_ratio" in bench["mode_a"]
