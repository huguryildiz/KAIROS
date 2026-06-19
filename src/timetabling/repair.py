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
