"""Regression: the per-block best-fit room cap (REPAIR_MAX_ROOMS / max_rooms_per_block)
must be wide enough that many tiny sections do not starve on the smallest rooms.

This reproduces the Spring-2026 failure in miniature: with the window collapsed to a
single (day, start) slot, N one-hour sections (distinct instructors, so the instructor
is never the binding constraint) must each take a *distinct* room. When only the K
smallest rooms are offered and K < N, the small rooms saturate and sections go unplaced
even though larger rooms sit empty. Widening K lets them spill into the larger rooms.
"""
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling.model_cpsat import gen_candidates, _instructors_of
from timetabling.repair import State, greedy_construct, _repair_room_cap


def _tiny_section(idx):
    iid = f"i{idx}"
    s = Section(f"S{idx}_01", "001", f"X {idx}", "x", 1, "X", "F", "X-1",
                [iid], 1, 1, 0, 0, 1, "")
    s.blocks = [Block(f"S{idx}_01#T", f"S{idx}_01", "theory", 1, False)]
    return s


def _one_slot_cfg(max_rooms):
    # Collapse the horizon to Mo@9 only: undergrad_end = start+1 -> one start hour;
    # blackout closes hour 9 on every other weekday.
    blackout = tuple((d, 9, False) for d in ("Tu", "We", "Th", "Fr"))
    return Config(horizon_start=9, undergrad_end=10, blackout=blackout,
                  max_rooms_per_block=max_rooms)


def _place_all(max_rooms):
    sections = [_tiny_section(i) for i in range(8)]
    # 6 small rooms (cap 5) + 6 large rooms (cap 100); only one usable (day, start).
    rooms = [Room(f"S{i}", 5, False, True) for i in range(6)] + \
            [Room(f"L{i}", 100, False, True) for i in range(6)]
    instructors = {f"i{i}": Instructor(f"i{i}", f"i{i}", True, "X") for i in range(8)}
    cfg = _one_slot_cfg(max_rooms)
    sec_of = {b.block_id: s for s in sections for b in s.blocks}
    sec_instr = {s.section_id: s.instructor_ids for s in sections}
    cand = {b.block_id: gen_candidates(b, s, _instructors_of(s, instructors), rooms, cfg)
            for s in sections for b in s.blocks}
    order = sorted(cand, key=lambda bid: (len(cand[bid]), bid))
    state = State(sec_of, sec_instr, set())
    greedy_construct(state, order, cand, cfg)
    return len(state.placed), len(sec_of)


def test_narrow_room_pool_starves_tiny_sections():
    # K = 6 smallest rooms < 8 contending sections -> at most 6 place.
    placed, total = _place_all(max_rooms=6)
    assert total == 8
    assert placed < total


def test_wide_room_pool_places_all_tiny_sections():
    # K = 12 (all rooms) -> every section finds a distinct room.
    placed, total = _place_all(max_rooms=12)
    assert placed == total


def test_repair_room_cap_never_below_inventory():
    # The pool must never be smaller than the physical room count, on any school size, so
    # the 24-smallest-rooms starvation cannot recur regardless of the room mix.
    cfg = Config()
    for n in (5, 50, 200):
        rooms = [Room(f"R{i}", 30, False, True) for i in range(n)]
        assert _repair_room_cap(rooms, cfg) >= n


def test_repair_room_cap_excludes_virtual_rooms():
    # Virtual rooms are unlimited and exempt from no-overlap; they must not inflate the cap.
    cfg = Config()
    rooms = [Room(f"R{i}", 30, False, True) for i in range(60)]
    rooms.append(Room("VIRTUAL", 9999, False, False, True))
    assert _repair_room_cap(rooms, cfg) == 60
