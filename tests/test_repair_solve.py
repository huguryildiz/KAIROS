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
