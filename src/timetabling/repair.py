from __future__ import annotations
from typing import Dict, List
from collections import defaultdict

from ortools.sat.python import cp_model

from .config import Config
from .model import Section, Room, Instructor, Candidate, Assignment
from .model_cpsat import gen_candidates, _instructors_of

BIG = 10_000


class State:
    """Global assignment + incremental occupancy for fast competitor lookup.
    Virtual-room slots are never tracked as room occupancy (unlimited)."""

    def __init__(self, sec_of, sec_instr, virtual_names):
        self.sec_of = sec_of                # block_id -> Section
        self.sec_instr = sec_instr          # section_id -> [iid]
        self.virtual = set(virtual_names)   # room names exempt from room no-overlap
        self.placed: Dict[str, Candidate] = {}
        self.room_owner: Dict[tuple, str] = {}
        self.instr_blocks = defaultdict(set)
        self.sect_blocks = defaultdict(set)
        self.instr_slot = defaultdict(set)
        self.sect_slot = defaultdict(set)

    def free_to_place(self, c, sid, iids):
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual and (c.room, c.day, hh) in self.room_owner:
                return False
            for iid in iids:
                if self.instr_slot.get((iid, c.day, hh)):
                    return False
            if self.sect_slot.get((sid, c.day, hh)):
                return False
        return True

    def occupy(self, bid, c):
        s = self.sec_of[bid]; iids = self.sec_instr.get(s.section_id, [])
        self.placed[bid] = c
        self.sect_blocks[s.section_id].add(bid)
        for iid in iids:
            self.instr_blocks[iid].add(bid)
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual:
                self.room_owner[(c.room, c.day, hh)] = bid
            for iid in iids:
                self.instr_slot[(iid, c.day, hh)].add(bid)
            self.sect_slot[(s.section_id, c.day, hh)].add(bid)

    def release(self, bid):
        c = self.placed.pop(bid, None)
        if c is None:
            return
        s = self.sec_of[bid]; iids = self.sec_instr.get(s.section_id, [])
        self.sect_blocks[s.section_id].discard(bid)
        for iid in iids:
            self.instr_blocks[iid].discard(bid)
        for hh in range(c.start, c.start + c.length):
            if self.room_owner.get((c.room, c.day, hh)) == bid:
                del self.room_owner[(c.room, c.day, hh)]
            for iid in iids:
                self.instr_slot[(iid, c.day, hh)].discard(bid)
            self.sect_slot[(s.section_id, c.day, hh)].discard(bid)


def greedy_construct(state: State, order: List[str], cand_by_block) -> None:
    for bid in order:
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        for c in cand_by_block[bid]:
            if state.free_to_place(c, s.section_id, iids):
                state.occupy(bid, c)
                break


BATCH = 30
REPAIR_TL = 12.0
MAX_FREE = 240


def competitors(state: State, batch, cand_by_block) -> set:
    comp = set()
    for bid in batch:
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        for c in cand_by_block[bid]:
            if c.room in state.virtual:
                continue
            for hh in range(c.start, c.start + c.length):
                owner = state.room_owner.get((c.room, c.day, hh))
                if owner:
                    comp.add(owner)
        for iid in iids:
            comp |= state.instr_blocks.get(iid, set())
        comp |= state.sect_blocks.get(s.section_id, set())
    return comp - set(batch)


def repair_round(state: State, batch, cand_by_block) -> int:
    comp = competitors(state, batch, cand_by_block)
    free = list(dict.fromkeys(list(batch) + list(comp)))[:MAX_FREE]
    free_set = set(free)

    reserved_room, reserved_instr = set(), set()
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        for hh in range(c.start, c.start + c.length):
            if c.room not in state.virtual:
                reserved_room.add((c.room, c.day, hh))
            for iid in iids:
                reserved_instr.add((iid, c.day, hh))

    m = cp_model.CpModel()
    x = {}
    room_occ = defaultdict(list); instr_occ = defaultdict(list); sect_occ = defaultdict(list)
    unpl = {}
    cur = {}
    for bid in free:
        s = state.sec_of[bid]; iids = s.instructor_ids
        cands = [c for c in cand_by_block[bid]
                 if not any(((c.room not in state.virtual and (c.room, c.day, hh) in reserved_room)
                             or any((iid, c.day, hh) in reserved_instr for iid in iids))
                            for hh in range(c.start, c.start + c.length))]
        u = m.NewBoolVar(f"u|{bid}")
        unpl[bid] = u
        bvars = []
        for c in cands:
            v = m.NewBoolVar(f"x|{bid}|{c.room}|{c.day}|{c.start}")
            x[(bid, c.room, c.day, c.start)] = v
            bvars.append(v)
            for hh in range(c.start, c.start + c.length):
                if c.room not in state.virtual:
                    room_occ[(c.room, c.day, hh)].append(v)
                for iid in iids:
                    instr_occ[(iid, c.day, hh)].append(v)
                sect_occ[(s.section_id, c.day, hh)].append(v)
        m.AddExactlyOne(bvars + [u])
        if bid in state.placed:
            cur[bid] = state.placed[bid]
    for occ in (room_occ, instr_occ, sect_occ):
        for vs in occ.values():
            if len(vs) > 1:
                m.Add(sum(vs) <= 1)
    m.Minimize(BIG * sum(unpl.values()))

    for bid in free:
        if bid in cur:
            c = cur[bid]
            key = (bid, c.room, c.day, c.start)
            if key in x:
                m.AddHint(x[key], 1)
                m.AddHint(unpl[bid], 0)
        else:
            m.AddHint(unpl[bid], 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = REPAIR_TL
    solver.parameters.num_search_workers = 8
    st = solver.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return 0

    new_assign = {}
    for (b, room, day, start), v in x.items():
        if solver.Value(v) == 1:
            length = next(c.length for c in cand_by_block[b]
                          if c.room == room and c.day == day and c.start == start)
            new_assign[b] = Candidate(b, room, day, start, length)

    old_count = sum(1 for bid in free if bid in state.placed)
    if len(new_assign) < old_count:
        return 0
    for bid in free:
        state.release(bid)
    for bid, c in new_assign.items():
        state.occupy(bid, c)
    return len(new_assign) - old_count


def solve_repair(sections, rooms, instructors, cfg):
    room_list = list(rooms.values())
    virtual_names = {r.room for r in room_list if r.is_virtual}
    blocks = [(b, s) for s in sections for b in s.blocks]
    total = len(blocks)
    sec_of = {b.block_id: s for b, s in blocks}
    sec_instr = {s.section_id: s.instructor_ids for s in sections}

    cand_by_block = {}
    for b, s in blocks:
        ins_list = _instructors_of(s, instructors)
        cand_by_block[b.block_id] = gen_candidates(b, s, ins_list, room_list, cfg)

    order = sorted((b.block_id for b, _ in blocks),
                   key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))

    state = State(sec_of, sec_instr, virtual_names)
    greedy_construct(state, order, cand_by_block)

    sweep = 0
    while True:
        sweep += 1
        unplaced = [bid for bid, _ in [(b.block_id, s) for b, s in blocks]
                    if bid not in state.placed]
        if not unplaced:
            break
        unplaced.sort(key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))
        gained = 0
        for i in range(0, len(unplaced), BATCH):
            batch = [bid for bid in unplaced[i:i + BATCH] if bid not in state.placed]
            if batch:
                gained += repair_round(state, batch, cand_by_block)
        if gained == 0 or sweep >= 25:
            break

    assignments = []
    for bid, c in state.placed.items():
        s = sec_of[bid]
        kind = "lab" if "#L" in bid else "theory"
        assignments.append(Assignment(bid, s.section_id, kind, c.room, c.day, c.start,
                                       c.start + c.length))
    unplaced_ids = [b.block_id for b, _ in blocks if b.block_id not in state.placed]
    stats = {
        "status_name": "REPAIR",
        "n_blocks": total,
        "n_vars": 0,
        "unplaced": unplaced_ids,
        "wall_time": 0.0,
        "placed": len(state.placed),
        "total": total,
    }
    return assignments, stats
