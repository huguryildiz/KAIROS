from timetabling.model import Room, Section, Block, Instructor
from timetabling.config import Config
from timetabling.model_cpsat import feasible_rooms_for, build_and_solve


def test_feasible_rooms_for_virtual_returns_virtual_room():
    rooms = [Room("R1", 100, False, True), Room("Online", 9999, False, False, True)]
    blk = Block("S#T", "S", "theory", 2, False)
    vs = Section("S", "001", "X 101", "x", 1, "X", "F", "X-1", ["i"], 300,
                 2, 0, 0, 2, "", is_virtual=True)
    assert [r.room for r in feasible_rooms_for(blk, vs, rooms, Config())] == ["Online"]
    ps = Section("S", "001", "X 101", "x", 1, "X", "F", "X-1", ["i"], 50,
                 2, 0, 0, 2, "")
    got = feasible_rooms_for(blk, ps, rooms, Config())
    assert got and all(r.is_physical and not r.is_virtual for r in got)


def test_virtual_room_unlimited_concurrency():
    # 60 virtual 2h sections exceed the virtual room's ~40 time-slots: they all
    # fit ONLY if the virtual room is exempt from room no-overlap.
    cfg = Config(solve_time_limit_s=10)
    rooms = [Room("Online", 9999, False, False, True)]
    instr = {f"i{n}": Instructor(f"i{n}", "x", True, "D") for n in range(60)}

    def vsec(n):
        s = Section(f"C{n}_01", "001", f"C{n} 101", "x", 1, f"C{n}", "F", f"C{n}-1",
                    [f"i{n}"], 300, 2, 0, 0, 2, "", is_virtual=True)
        s.blocks = [Block(f"C{n}_01#T", f"C{n}_01", "theory", 2, False)]
        return s

    secs = [vsec(n) for n in range(60)]
    assigns, stats = build_and_solve(secs, rooms, instr, cfg)
    assert len(assigns) == 60
    assert {a.room for a in assigns} == {"Online"}


def test_validate_exempts_virtual_room():
    from timetabling.model import Assignment
    from timetabling.validate import validate
    rooms = {"Online": Room("Online", 9999, False, False, True)}
    instr = {"i1": Instructor("i1", "A", True, "D"), "i2": Instructor("i2", "B", True, "D")}

    def vsec(sid, iid):
        s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 300,
                    2, 0, 0, 2, "", is_virtual=True)
        s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
        return s

    secs = [vsec("X 101_01", "i1"), vsec("X 101_02", "i2")]
    # both in the SAME virtual slot, 300 students each — exempt from capacity + room overlap
    a = [Assignment("X 101_01#T", "X 101_01", "theory", "Online", "Mo", 9, 11),
         Assignment("X 101_02#T", "X 101_02", "theory", "Online", "Mo", 9, 11)]
    assert validate(a, secs, rooms, instr, Config()) == []
