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
        self.instr_active_days = defaultdict(set)  # iid -> {days with >0 placed hours}
        self.cohort_slot_courses = defaultdict(Counter)   # (cohort, day, hour) -> {course: count}
        self.room_hours_used = Counter()   # room -> # occupied hour-slots (virtual excluded)

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
            self.instr_active_days[iid].add(c.day)
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual:
                self.room_owner[(c.room, c.day, hh)] = bid
                self.room_hours_used[c.room] += 1
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
            if self.instr_day_hours[(iid, c.day)] <= 0:
                self.instr_active_days[iid].discard(c.day)
        for hh in range(c.start, c.start + c.length):
            if self.room_owner.get((c.room, c.day, hh)) == bid:
                del self.room_owner[(c.room, c.day, hh)]
                self.room_hours_used[c.room] -= 1
                if self.room_hours_used[c.room] <= 0:
                    del self.room_hours_used[c.room]
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
    # weekly distinct-day overload: placing on a day the instructor doesn't yet teach
    # adds a new day; penalize only when they are already at/over the weekly cap.
    if cfg.w_instr_weekly_overload:
        wcap = cfg.max_instr_weekly_days
        for iid in s.instructor_ids:
            days = state.instr_active_days[iid]
            if c.day not in days and len(days) >= wcap:
                score += cfg.w_instr_weekly_overload
    return score


def _cand_soft(c, s, cfg: Config) -> int:
    """Per-candidate separable soft cost: evening + S-Order + S-EngLab. Independent of
    other blocks, so it folds into a variable's objective coefficient. Mirrors the
    per-variable coefficients in model_cpsat.build_and_solve."""
    cost = cfg.w_evening * sum(1 for h in range(c.start, c.start + c.length)
                               if h >= cfg.evening_from_hour)
    if 2 <= s.level <= 4:
        cost += cfg.w_order * (4 - s.level) * (c.start - cfg.horizon_start)
    if (cfg.eng_faculty_match in s.faculty and "#L" in c.block_id
            and c.day not in cfg.eng_lab_days):
        cost += cfg.w_englab
    return cost


def greedy_construct(state: State, order: List[str], cand_by_block,
                     cfg: Config = None, eligible=None, cap=0) -> None:
    """Greedy construction. With cfg shaping enabled, place each block in its lowest
    soft-score feasible candidate (ties broken by candidate order = best-fit room);
    otherwise first-feasible. Shaping is on when soft_shaping_in_repair is set, or when
    the overload penalty is enabled (its own weight + an eligible set)."""
    eligible = eligible or set()
    shaping = cfg is not None and (cfg.soft_shaping_in_repair
                                   or (cfg.w_instr_daily_overload and eligible)
                                   or cfg.w_instr_weekly_overload)
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
# soft-polish: after placement converges, re-seat already-placed blocks into lower-soft
# slots. Accept-guarded -> never lowers placement. Budget shared under the deadline.
SOFT_POLISH_TL = 6.0
SOFT_POLISH_BUDGET_S = 600.0


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


def _soft_total(state, cfg, staff_ids=frozenset()) -> int:
    """Global weighted soft sum over the current full placement. Single source of truth
    for the accept guard and the convergence check — mirrors the terms add_soft_objective
    puts in the model, plus all four soft terms (per-candidate, cohort-conflict,
    cohort-gap, instr_days, room_count). Cheap (no CP-SAT)."""
    total = 0
    compact = {str(y) for y in cfg.compact_cohort_years}
    coh_courses = defaultdict(set)   # (cohort, day, hour) -> {course}
    coh_hours = defaultdict(set)     # (cohort, day) -> {hour}   (compact years only)
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        total += _cand_soft(c, s, cfg)
        is_compact = s.cohort_key.rsplit("-", 1)[-1] in compact
        for hh in range(c.start, c.start + c.length):
            coh_courses[(s.cohort_key, c.day, hh)].add(s.code)
            if is_compact:
                coh_hours[(s.cohort_key, c.day)].add(hh)
    total += cfg.w_cohort_conflict * sum(max(0, len(v) - 1) for v in coh_courses.values())
    total += cfg.w_cohort_gap * sum((max(h) + 1 - min(h)) - len(h)
                                    for h in coh_hours.values() if len(h) >= 2)
    total += cfg.w_instr_days * sum(len(days) for days in state.instr_active_days.values())
    total += cfg.w_room_count * len(state.room_hours_used)
    return total


def add_soft_objective(m, x, free, cand_by_block, state, free_set, cfg,
                       staff_ids=frozenset()):
    """Build the joint soft penalty over the free neighborhood, accounting for the
    frozen (non-free) placement as constants. Returns (penalty_terms, penalty_ub) so the
    caller can set BIG > penalty_ub and keep placement lexicographically dominant. Each
    term is gated by its weight, so disabled preferences cost nothing."""
    from collections import defaultdict as _dd

    penalty = []
    ub = 0
    length_of = {bid: (cand_by_block[bid][0].length if cand_by_block[bid] else 0)
                 for bid in free}

    # --- per-candidate: evening + S-Order + S-EngLab ---
    for bid in free:
        s = state.sec_of[bid]
        best = 0
        for c in cand_by_block[bid]:
            v = x.get((bid, c.room, c.day, c.start))
            if v is None:
                continue
            sc = _cand_soft(c, s, cfg)
            if sc:
                penalty.append(sc * v)
                if sc > best:
                    best = sc
        ub += best

    # frozen (non-free) placement: distinct courses present per (cohort, day, hour)
    frozen_courses = _dd(set)
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        s = state.sec_of[bid]
        for hh in range(c.start, c.start + c.length):
            frozen_courses[(s.cohort_key, c.day, hh)].add(s.code)

    # --- cohort-conflict: penalize each distinct course beyond the first per slot ---
    cc_free = _dd(lambda: _dd(list))     # (cohort, day, hour) -> course -> [free vars]
    for (bid, room, day, start), v in x.items():
        s = state.sec_of[bid]
        for hh in range(start, start + length_of[bid]):
            cc_free[(s.cohort_key, day, hh)][s.code].append(v)
    for slot in set(cc_free) | set(frozen_courses):
        cohort, day, hh = slot
        fro = frozen_courses.get(slot, set())
        busy = []
        for course, vs in cc_free.get(slot, {}).items():
            if course in fro:            # already constant-present via a frozen block
                continue
            b = m.NewBoolVar(f"cbusy|{cohort}|{course}|{day}|{hh}")
            m.AddMaxEquality(b, vs)
            busy.append(b)
        n_terms = len(fro) + len(busy)
        if n_terms <= 1:
            continue
        excess = m.NewIntVar(0, n_terms, f"cconf|{cohort}|{day}|{hh}")
        m.Add(excess >= len(fro) + sum(busy) - 1)
        penalty.append(cfg.w_cohort_conflict * excess)
        ub += cfg.w_cohort_conflict * n_terms

    # --- cohort-gap: minimize per-(cohort, day) idle span (compact-cohort years only) ---
    compact_years = {str(y) for y in cfg.compact_cohort_years}

    def _is_compact(cohort_key):
        return cohort_key.rsplit("-", 1)[-1] in compact_years

    frozen_hours = _dd(set)              # (cohort, day) -> {hour} from frozen blocks
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        s = state.sec_of[bid]
        if _is_compact(s.cohort_key):
            for hh in range(c.start, c.start + c.length):
                frozen_hours[(s.cohort_key, c.day)].add(hh)

    ch_free = _dd(list)                  # (cohort, day, hour) -> [free vars]
    for (bid, room, day, start), v in x.items():
        s = state.sec_of[bid]
        if _is_compact(s.cohort_key):
            for hh in range(start, start + length_of[bid]):
                ch_free[(s.cohort_key, day, hh)].append(v)

    active = _dd(dict)                   # (cohort, day) -> {hour: bool var or constant 1}
    for (cohort, day, hh), vs in ch_free.items():
        a = m.NewBoolVar(f"chact|{cohort}|{day}|{hh}")
        m.AddMaxEquality(a, vs)
        active[(cohort, day)][hh] = a
    for (cohort, day), hrs in frozen_hours.items():
        for hh in hrs:
            active[(cohort, day)][hh] = 1     # frozen block -> constant-active

    HB = cfg.horizon_end + 1
    for (cohort, day), hourmap in active.items():
        hours = sorted(hourmap)
        if len(hours) < 2:
            continue
        load = sum(hourmap[h] for h in hours)
        first = m.NewIntVar(0, HB, f"first|{cohort}|{day}")
        last = m.NewIntVar(0, HB, f"last|{cohort}|{day}")
        m.AddMaxEquality(last, [(h + 1) * hourmap[h] for h in hours])
        m.AddMinEquality(first, [h * hourmap[h] + HB * (1 - hourmap[h]) for h in hours])
        gap = m.NewIntVar(0, cfg.horizon_end, f"cgap|{cohort}|{day}")
        m.Add(gap >= last - first - load)
        penalty.append(cfg.w_cohort_gap * gap)
        ub += cfg.w_cohort_gap * cfg.horizon_end

    return penalty, ub


def repair_round(state: State, batch, cand_by_block, cfg=None, eligible=None,
                 tl=REPAIR_TL, staff_ids=frozenset()) -> int:
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

    # objective: lexicographic — placement dominates, soft only breaks ties.
    penalty, penalty_ub = [], 0
    if cfg is not None and cfg.soft_shaping_in_repair:
        penalty, penalty_ub = add_soft_objective(
            m, x, free, cand_by_block, state, free_set, cfg, staff_ids)
    # per-(instructor, day) overload — frozen hours are a constant, free blocks vary.
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
            penalty.append(cfg.w_instr_daily_overload * over)
            penalty_ub += cfg.w_instr_daily_overload * (const + len(vs))
    big = max(BIG, penalty_ub + 1)
    m.Minimize(big * sum(unpl.values()) + sum(penalty))

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

    old_placed = {bid: state.placed[bid] for bid in free if bid in state.placed}
    old_count = len(old_placed)
    if len(new_assign) < old_count:
        return 0
    # soft-aware accept guard. A timed-out (FEASIBLE, not OPTIMAL) solve can return a
    # same-placement solution that is WORSE on the joint soft objective than the current
    # one; the count-only guard would commit it and let soft drift upward (measured). So
    # when soft shaping is active and placement is not improved, commit only if the GLOBAL
    # weighted soft sum does not increase, else revert. Frozen blocks are unchanged within
    # a round, so the global delta equals the free-set delta. Pure placement sweeps
    # (cfg is None) skip this entirely, preserving the placement baseline exactly.
    soft_guard = (cfg is not None and cfg.soft_shaping_in_repair
                  and len(new_assign) == old_count)
    old_soft = _soft_total(state, cfg) if soft_guard else 0
    for bid in free:
        state.release(bid)
    for bid, c in new_assign.items():
        state.occupy(bid, c)
    if soft_guard and _soft_total(state, cfg) > old_soft:
        for bid in new_assign:
            state.release(bid)
        for bid, c in old_placed.items():
            state.occupy(bid, c)
        return 0
    return len(new_assign) - old_count


def _cohort_gap_now(state, block_ids, cfg) -> int:
    """Current total (cohort, day) idle gap over the given placed blocks."""
    by_day = defaultdict(set)
    for bid in block_ids:
        c = state.placed.get(bid)
        if c is None:
            continue
        for hh in range(c.start, c.start + c.length):
            by_day[c.day].add(hh)
    return sum((max(hrs) + 1 - min(hrs)) - len(hrs)
               for hrs in by_day.values() if len(hrs) >= 2)


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
    staff_ids = frozenset(iid for iid, ins in instructors.items()
                          if getattr(ins, "is_staff", False))

    state = State(sec_of, sec_instr, virtual_names)
    t0 = perf_counter()
    # Overall wall-clock budget (UI/CLI). The repair loop runs to convergence well within
    # this for current sizes; the deadline is a hard upper bound that bounds runaway sweeps
    # on much larger inputs (and keeps the synchronous UI request under Cloud Run limits).
    deadline = getattr(cfg, "repair_time_limit_s", float("inf")) if cfg else float("inf")
    greedy_construct(state, order, cand_by_block, cfg, eligible, cfg.max_instr_daily_hours)

    sweep = 0
    while perf_counter() - t0 < deadline:
        sweep += 1
        unplaced = [bid for bid, _ in [(b.block_id, s) for b, s in blocks]
                    if bid not in state.placed]
        if not unplaced:
            break
        unplaced.sort(key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))
        gained = 0
        for i in range(0, len(unplaced), BATCH):
            if perf_counter() - t0 >= deadline:
                break
            batch = [bid for bid in unplaced[i:i + BATCH] if bid not in state.placed]
            if batch:
                # placement phase: pure placement (no overload steering) so the result
                # matches the baseline; overload is handled additively in POLISH below.
                gained += repair_round(state, batch, cand_by_block)
        if gained == 0 or sweep >= 25:
            break

    # SOFT-POLISH: move-based local search (soft_search.anneal_soft). Replaces the
    # CP-SAT frozen-LNS passes, which were a measured no-op at scale. OFF by default
    # (cfg.soft_polish_in_repair) until the 841 gate is green.
    soft_polish_rounds = 0
    if cfg.soft_polish_in_repair:
        from .soft_search import anneal_soft
        budget = min(SOFT_POLISH_BUDGET_S, max(0.0, deadline - (perf_counter() - t0)))
        if budget > 0:
            anneal_soft(state, cand_by_block, cfg, budget, seed=cfg.soft_polish_seed)
            soft_polish_rounds = 1

    # POLISH (overload only): once placement converges, re-optimize the days of
    # overloaded eligible instructors. repair_round never lowers placement (its accept
    # guard), so this strictly reduces overload-hours without costing any placement.
    polish_rounds = 0
    if cfg.w_instr_daily_overload and eligible:
        cap = cfg.max_instr_daily_hours
        t_polish = perf_counter()
        # keep polish within the overall deadline: never exceed the remaining budget.
        polish_budget = min(POLISH_BUDGET_S, max(0.0, deadline - (t_polish - t0)))
        prev = None
        for _ in range(POLISH_SWEEPS):
            bad = sorted({iid for (iid, day), h in state.instr_day_hours.items()
                          if h > cap and iid in eligible})
            if not bad or perf_counter() - t_polish > polish_budget:
                break
            for iid in bad:
                if perf_counter() - t_polish > polish_budget:
                    break
                batch = list(state.instr_blocks.get(iid, set()))
                if batch:
                    repair_round(state, batch, cand_by_block, cfg, eligible,
                                 tl=POLISH_TL, staff_ids=staff_ids)
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
        "soft_polish_rounds": soft_polish_rounds,
        "placed": len(state.placed),
        "total": total,
    }
    return assignments, stats
