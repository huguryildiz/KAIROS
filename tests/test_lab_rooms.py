from timetabling.config import Config
from timetabling.model import Room, Section, Block, Instructor, Assignment
from timetabling.model_cpsat import feasible_rooms_for
from timetabling.validate import validate


def _lab_block():
    return Block("S_01#L", "S_01", "lab", 2, True)


def _sec(lab_room=""):
    return Section("S_01", "001", "X 201", "x", 2, "X", "F", "X-2", ["i1"], 25,
                   2, 0, 2, 4, "", lab_room=lab_room)


def test_feasible_rooms_pins_lab_block_to_designated_room():
    rooms = [Room("LAB1", 30, True, True), Room("LAB2", 30, True, True), Room("R1", 40, False, True)]
    got = feasible_rooms_for(_lab_block(), _sec("LAB2"), rooms, Config())
    assert [r.room for r in got] == ["LAB2"]


def test_lab_without_designated_room_uses_lab_family_rooms():
    rooms = [Room("LAB1", 30, True, True), Room("R1", 40, False, True)]
    got = feasible_rooms_for(_lab_block(), _sec(""), rooms, Config())
    assert [r.room for r in got] == ["LAB1"]


def test_validate_flags_lab_not_in_pinned_room():
    rooms = {"LAB1": Room("LAB1", 30, True, True), "LAB2": Room("LAB2", 30, True, True)}
    instr = {"i1": Instructor("i1", "n", False, "D")}
    s = _sec("LAB2"); s.blocks = [_lab_block()]
    wrong = [Assignment("S_01#L", "S_01", "lab", "LAB1", "Mo", 9, 11)]
    assert any(x.kind == "lab_room" for x in validate(wrong, [s], rooms, instr, Config()))
    right = [Assignment("S_01#L", "S_01", "lab", "LAB2", "Mo", 9, 11)]
    assert validate(right, [s], rooms, instr, Config()) == []


def test_validate_flags_unpinned_lab_in_regular_room():
    rooms = {"R1": Room("R1", 40, False, True)}
    instr = {"i1": Instructor("i1", "n", False, "D")}
    s = _sec(""); s.blocks = [_lab_block()]
    a = [Assignment("S_01#L", "S_01", "lab", "R1", "Mo", 9, 11)]
    assert any(x.kind == "room_type" for x in validate(a, [s], rooms, instr, Config()))
