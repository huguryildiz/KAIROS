from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import report


def test_room_fill_metric():
    rooms = {"R1": Room("R1", 100, False, True)}
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["a"],
                50, 1, 0, 0, 0, "Course")
    s.blocks = [Block("S_01#T", "S_01", "theory", 1, False)]
    a = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 10)]
    m = report._metrics(a, [s], rooms, instr, Config())
    assert m["room_fill"] == 0.5                  # 50 / 100
