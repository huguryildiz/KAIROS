from __future__ import annotations
from typing import Dict, List
from collections import defaultdict, Counter
from dataclasses import replace
from time import perf_counter

from ortools.sat.python import cp_model

from .config import Config
from .model import Section, Room, Instructor, Candidate, Assignment, overload_eligible_ids
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
        self.sect_theory_day = defaultdict(set)   # (section_id, day) -> {theory block_ids}
        self.instr_day_hours = defaultdict(int)   # (iid, day) -> placed teaching hours
        self.cohort_slot_courses = defaultdict(Counter)   # (cohort, day, hour) -> {course: count}

    def free_to_place(self, c, sid, iids):
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual and (c.room, c.day, hh) in self.room_owner:
                return False
            for iid in iids:
                if self.instr_slot.get((iid, c.day, hh)):
                    return False
            if self.sect_slot.get((sid, c.day, hh)):
                return False
        # a section's theory sessions must each be on a different day
        if "#L" not in c.block_id and any(b != c.block_id
                for b in self.sect_theory_day.get((sid, c.day), ())):
            return False
        return True

    def occupy(self, bid, c):
        s = self.sec_of[bid]; iids = self.sec_instr.get(s.section_id, [])
        self.placed[bid] = c
        self.sect_blocks[s.section_id].add(bid)
        if "#L" not in bid:
            self.sect_theory_day[(s.section_id, c.day)].add(bid)
        for iid in iids:
            self.instr_blocks[iid].add(bid)
            self.instr_day_hours[(iid, c.day)] += c.length
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual:
                self.room_owner[(c.room, c.day, hh)] = bid
            for iid in iids:
                self.instr_slot[(iid, c.day, hh)].add(bid)
            self.sect_slot[(s.section_id, c.day, hh)].add(bid)
            self.cohort_slot_courses[(s.cohort_key, c.day, hh)][s.code] += 1

    def release(self, bid):
        c = self.placed.pop(bid, None)
        if c is None:
            return
        s = self.sec_of[bid]; iids = self.sec_instr.get(s.section_id, [])
        self.sect_blocks[s.section_id].discard(bid)
        if "#L" not in bid:
            self.sect_theory_day[(s.section_id, c.day)].discard(bid)
        for iid in iids:
            self.instr_blocks[iid].discard(bid)
            self.instr_day_hours[(iid, c.day)] -= c.length
        for hh in range(c.start, c.start + c.length):
            if self.room_owner.get((c.room, c.day, hh)) == bid:
                del self.room_owner[(c.room, c.day, hh)]
            for iid in iids:
                self.instr_slot[(iid, c.day, hh)].discard(bid)
            self.sect_slot[(s.section_id, c.day, hh)].discard(bid)
            cnt = self.cohort_slot_courses[(s.cohort_key, c.day, hh)]
            cnt[s.code] -= 1
            if cnt[s.code] <= 0:
                del cnt[s.code]


def _soft_score(state: State, c, s, cfg: Config, eligible, cap) -> int:
    """Weighted soft penalty for placing candidate c. Lower is better. evening + cohort
    are gated by cfg.soft_shaping_in_repair; overload by its own weight (opt-in)."""
    score = 0
    if cfg.soft_shaping_in_repair:
        score += cfg.w_evening * sum(1 for h in range(c.start, c.start + c.length)
                                     if h >= cfg.evening_from_hour)
        for h in range(c.start, c.start + c.length):
            slot = state.cohort_slot_courses.get((s.cohort_key, c.day, h))
            if slot and any(cc != s.code for cc in slot):
                score += cfg.w_cohort_conflict
    if cfg.w_instr_daily_overload and eligible:
        for iid in s.instructor_ids:
            if iid in eligible:
                score += cfg.w_instr_daily_overload * max(
                    0, state.instr_day_hours[(iid, c.day)] + c.length - cap)
    return score


def greedy_construct(state: State, order: List[str], cand_by_block,
                     cfg: Config = None, eligible=None, cap=0) -> None:
    """Greedy construction. With cfg shaping enabled, place each block in its lowest
    soft-score feasible candidate (ties broken by candidate order = best-fit room);
    otherwise first-feasible. Shaping is on when soft_shaping_in_repair is set, or when
    the overload penalty is enabled (its own weight + an eligible set)."""
    eligible = eligible or set()
    shaping = cfg is not None and (cfg.soft_shaping_in_repair
                                   or (cfg.w_instr_daily_overload and eligible))
    for bid in order:
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        if shaping:
            best, best_score = None, None
            for c in cand_by_block[bid]:
                if state.free_to_place(c, s.section_id, iids):
                    sc = _soft_score(state, c, s, cfg, eligible, cap)
                    if best is None or sc < best_score:
                        best, best_score = c, sc
            if best is not None:
                state.occupy(bid, best)
        else:
            for c in cand_by_block[bid]:
                if state.free_to_place(c, s.section_id, iids):
                    state.occupy(bid, c)
                    break


BATCH = 30
REPAIR_TL = 12.0
MAX_FREE = 240
# Repair needs maneuvering room: small neighborhoods place far better with a wide
# best-fit room set. Measured: 12 rooms -> ~82% placed, 24 rooms -> ~95%.
REPAIR_MAX_ROOMS = 24
# polish phase (overload only): bounded re-optimization of already-placed blocks
POLISH_SWEEPS = 4
POLISH_TL = 6.0
POLISH_BUDGET_S = 240.0


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


def repair_round(state: State, batch, cand_by_block, cfg=None, eligible=None,
                 tl=REPAIR_TL) -> int:
    comp = competitors(state, batch, cand_by_block)
    free = list(dict.fromkeys(list(batch) + list(comp)))[:MAX_FREE]
    free_set = set(free)

    reserved_room, reserved_instr = set(), set()
    frozen_theory_day = defaultdict(set)
    frozen_instr_hours = defaultdict(int)   # (iid, day) -> frozen teaching hours
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        if "#L" not in bid:
            frozen_theory_day[s.section_id].add(c.day)
        for iid in iids:
            frozen_instr_hours[(iid, c.day)] += c.length
        for hh in range(c.start, c.start + c.length):
            if c.room not in state.virtual:
                reserved_room.add((c.room, c.day, hh))
            for iid in iids:
                reserved_instr.add((iid, c.day, hh))

    m = cp_model.CpModel()
    x = {}
    room_occ = defaultdict(list); instr_occ = defaultdict(list); sect_occ = defaultdict(list)
    instr_day_load = defaultdict(list)   # (iid, day) -> per-hour free vars (sum = free hours)
    theory_day = defaultdict(list)
    unpl = {}
    cur = {}
    for bid in free:
        s = state.sec_of[bid]; iids = s.instructor_ids
        is_theory = "#L" not in bid
        fdays = frozen_theory_day.get(s.section_id, set())
        cands = [c for c in cand_by_block[bid]
                 if not (is_theory and c.day in fdays)
                 and not any(((c.room not in state.virtual and (c.room, c.day, hh) in reserved_room)
                             or any((iid, c.day, hh) in reserved_instr for iid in iids))
                            for hh in range(c.start, c.start + c.length))]
        u = m.NewBoolVar(f"u|{bid}")
        unpl[bid] = u
        bvars = []
        for c in cands:
            v = m.NewBoolVar(f"x|{bid}|{c.room}|{c.day}|{c.start}")
            x[(bid, c.room, c.day, c.start)] = v
            bvars.append(v)
            if is_theory:
                theory_day[(s.section_id, c.day)].append(v)
            for hh in range(c.start, c.start + c.length):
                if c.room not in state.virtual:
                    room_occ[(c.room, c.day, hh)].append(v)
                for iid in iids:
                    instr_occ[(iid, c.day, hh)].append(v)
                    instr_day_load[(iid, c.day)].append(v)
                sect_occ[(s.section_id, c.day, hh)].append(v)
        m.AddExactlyOne(bvars + [u])
        if bid in state.placed:
            cur[bid] = state.placed[bid]
    for occ in (room_occ, instr_occ, sect_occ):
        for vs in occ.values():
            if len(vs) > 1:
                m.Add(sum(vs) <= 1)
    for vs in theory_day.values():           # <=1 theory session per (section, day)
        if len(vs) > 1:
            m.Add(sum(vs) <= 1)

    # soft: per-(instructor, day) overload — frozen hours are a constant, free blocks vary.
    # Weighted well under BIG so it only breaks ties and never blocks a placement.
    obj = BIG * sum(unpl.values())
    if cfg is not None and cfg.w_instr_daily_overload and eligible:
        cap = cfg.max_instr_daily_hours
        keys = set(instr_day_load) | set(frozen_instr_hours)
        for key in keys:
            iid = key[0]
            if iid not in eligible:
                continue
            const = frozen_instr_hours.get(key, 0)
            vs = instr_day_load.get(key, [])
            if const + len(vs) <= cap:
                continue
            over = m.NewIntVar(0, const + len(vs), f"iover|{key[0]}|{key[1]}")
            m.Add(over >= sum(vs) + const - cap)
            obj += cfg.w_instr_daily_overload * over
    m.Minimize(obj)

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
    solver.parameters.max_time_in_seconds = tl
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
    cfg = replace(cfg, max_rooms_per_block=max(cfg.max_rooms_per_block, REPAIR_MAX_ROOMS))
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

    eligible = overload_eligible_ids(sections, cfg) if cfg.w_instr_daily_overload else set()

    state = State(sec_of, sec_instr, virtual_names)
    t0 = perf_counter()
    greedy_construct(state, order, cand_by_block, cfg, eligible, cfg.max_instr_daily_hours)

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
                # placement phase: pure placement (no overload steering) so the result
                # matches the baseline; overload is handled additively in POLISH below.
                gained += repair_round(state, batch, cand_by_block)
        if gained == 0 or sweep >= 25:
            break

    # POLISH (overload only): once placement converges, re-optimize the days of
    # overloaded eligible instructors. repair_round never lowers placement (its accept
    # guard), so this strictly reduces overload-hours without costing any placement.
    polish_rounds = 0
    if cfg.w_instr_daily_overload and eligible:
        cap = cfg.max_instr_daily_hours
        t_polish = perf_counter()
        prev = None
        for _ in range(POLISH_SWEEPS):
            bad = sorted({iid for (iid, day), h in state.instr_day_hours.items()
                          if h > cap and iid in eligible})
            if not bad or perf_counter() - t_polish > POLISH_BUDGET_S:
                break
            for iid in bad:
                if perf_counter() - t_polish > POLISH_BUDGET_S:
                    break
                batch = list(state.instr_blocks.get(iid, set()))
                if batch:
                    repair_round(state, batch, cand_by_block, cfg, eligible, tl=POLISH_TL)
                    polish_rounds += 1
            cur = sum(max(0, h - cap) for (iid, day), h in state.instr_day_hours.items()
                      if iid in eligible)
            if prev is not None and cur >= prev:    # no further improvement
                break
            prev = cur

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
        "wall_time": round(perf_counter() - t0, 1),
        "sweeps": sweep,
        "polish_rounds": polish_rounds,
        "placed": len(state.placed),
        "total": total,
    }
    return assignments, stats
