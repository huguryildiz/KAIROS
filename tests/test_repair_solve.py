def test_solve_repair_places_clean_small_instance():
    from timetabling.config import Config
    from timetabling.model import Room, Section, Block, Instructor
    from timetabling.repair import solve_repair
    from timetabling.validate import validate
    cfg = Config(solve_time_limit_s=5)
    rooms = {"R1": Room("R1", 50, False, True), "Online": Room("Online", 9999, False, False, True)}
    instr = {f"i{n}": Instructor(f"i{n}", "x", True, "D") for n in range(4)}

    def sec(sid, iid, students=30, virtual=False):
        s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], students,
                    2, 0, 0, 2, "", is_virtual=virtual)
        s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
        return s

    secs = [sec("A_01", "i0"), sec("B_01", "i1"), sec("C_01", "i2", 300, True)]
    assigns, stats = solve_repair(secs, rooms, instr, cfg)
    assert stats["placed"] == 3 and stats["unplaced"] == []
    assert validate(assigns, secs, rooms, instr, cfg) == []


def test_repair_respects_availability():
    """An instructor unavailable all Monday must never be placed on Monday — proves the
    gen_candidates chokepoint covers the repair path too."""
    from timetabling.config import Config
    from timetabling.model import Room, Section, Block, Instructor
    from timetabling.repair import solve_repair
    cfg = Config(solve_time_limit_s=5,
                 instr_unavailable=frozenset(("i0", "Mo", h) for h in range(9, 18)))
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i0": Instructor("i0", "x", True, "D")}
    s = Section("A_01", "001", "X 101", "x", 1, "X", "F", "X-1", ["i0"], 30, 2, 0, 0, 2, "")
    s.blocks = [Block("A_01#T", "A_01", "theory", 2, False)]
    assigns, stats = solve_repair([s], rooms, instr, cfg)
    assert stats["placed"] == 1
    assert all(a.day != "Mo" for a in assigns)
