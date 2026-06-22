"""Move-based local-search soft polish for the repair solver. Operates on a converged
State by relocating/swapping already-placed blocks within their legal candidate lists,
guided by a pluggable acceptance criterion. Never unplaces (placement invariant by
construction); restores the best incumbent (soft never regresses globally)."""
from __future__ import annotations
from collections import defaultdict
from time import perf_counter

from .config import Config
from .repair import _cand_soft, _soft_total


def _local_soft(state, cohorts, instrs, rooms, blocks, cfg: Config) -> int:
    """Weighted soft over only the given entities. Each term is owned by one entity type
    (per-candidate->block, cohort-conflict/gap->cohort, instr_days->instructor,
    room_count->room), so summing over the FULL entity sets equals _soft_total."""
    total = 0
    # per-candidate over the given blocks
    for bid in blocks:
        c = state.placed.get(bid)
        if c is not None:
            total += _cand_soft(c, state.sec_of[bid], cfg)
    # cohort-conflict + cohort-gap over the given cohorts
    compact = {str(y) for y in cfg.compact_cohort_years}
    coh_courses = defaultdict(set)   # (cohort, day, hour) -> {course}
    coh_hours = defaultdict(set)     # (cohort, day) -> {hour}   (compact only)
    cohort_set = set(cohorts)
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        if s.cohort_key not in cohort_set:
            continue
        is_compact = s.cohort_key.rsplit("-", 1)[-1] in compact
        for hh in range(c.start, c.start + c.length):
            coh_courses[(s.cohort_key, c.day, hh)].add(s.code)
            if is_compact:
                coh_hours[(s.cohort_key, c.day)].add(hh)
    total += cfg.w_cohort_conflict * sum(max(0, len(v) - 1) for v in coh_courses.values())
    total += cfg.w_cohort_gap * sum((max(h) + 1 - min(h)) - len(h)
                                    for h in coh_hours.values() if len(h) >= 2)
    # instr_days over the given instructors
    total += cfg.w_instr_days * sum(len(state.instr_active_days.get(iid, ())) for iid in instrs)
    # room_count over the given rooms (a room counts once if it has any occupied slot)
    total += cfg.w_room_count * sum(1 for r in rooms if state.room_hours_used.get(r, 0) > 0)
    return total


def _slot(c):
    return (c.room, c.day, c.start)


def try_relocate(state, cand_by_block, bid, rng, cfg):
    """Move bid to a random alternative legal+free candidate. Leaves state in the new
    config; returns (delta, revert) or None. revert() restores the original placement."""
    s = state.sec_of[bid]
    iids = state.sec_instr.get(s.section_id, [])
    c_old = state.placed.get(bid)
    if c_old is None:
        return None
    alts = [c for c in cand_by_block[bid] if _slot(c) != _slot(c_old)]
    if not alts:
        return None
    c_new = alts[rng.randrange(len(alts))]
    cohorts = {s.cohort_key}
    instrs = set(iids)
    rooms = {c_old.room, c_new.room}
    blocks = {bid}
    before = _local_soft(state, cohorts, instrs, rooms, blocks, cfg)
    state.release(bid)
    if not state.free_to_place(c_new, s.section_id, iids):
        state.occupy(bid, c_old)
        return None
    state.occupy(bid, c_new)
    delta = _local_soft(state, cohorts, instrs, rooms, blocks, cfg) - before

    def revert():
        state.release(bid)
        state.occupy(bid, c_old)
    return delta, revert


def try_swap(state, cand_by_block, bid1, bid2, cfg):
    """Exchange the slots of bid1 and bid2 if each has a candidate for the other's current
    slot and both are feasible. Leaves state swapped; returns (delta, revert) or None."""
    if bid1 == bid2:
        return None
    c1 = state.placed.get(bid1)
    c2 = state.placed.get(bid2)
    if c1 is None or c2 is None:
        return None
    s1 = state.sec_of[bid1]
    s2 = state.sec_of[bid2]
    iids1 = state.sec_instr.get(s1.section_id, [])
    iids2 = state.sec_instr.get(s2.section_id, [])
    c1_new = next((c for c in cand_by_block[bid1] if _slot(c) == _slot(c2)), None)
    c2_new = next((c for c in cand_by_block[bid2] if _slot(c) == _slot(c1)), None)
    if c1_new is None or c2_new is None:
        return None
    cohorts = {s1.cohort_key, s2.cohort_key}
    instrs = set(iids1) | set(iids2)
    rooms = {c1.room, c2.room}
    blocks = {bid1, bid2}
    before = _local_soft(state, cohorts, instrs, rooms, blocks, cfg)
    state.release(bid1)
    state.release(bid2)
    ok = False
    if state.free_to_place(c1_new, s1.section_id, iids1):
        state.occupy(bid1, c1_new)
        if state.free_to_place(c2_new, s2.section_id, iids2):
            state.occupy(bid2, c2_new)
            ok = True
        else:
            state.release(bid1)
    if not ok:
        state.occupy(bid1, c1)
        state.occupy(bid2, c2)
        return None
    delta = _local_soft(state, cohorts, instrs, rooms, blocks, cfg) - before

    def revert():
        state.release(bid1)
        state.release(bid2)
        state.occupy(bid1, c1)
        state.occupy(bid2, c2)
    return delta, revert


class SCHC:
    """Step Counting Hill Climbing (Bykov & Petrovic 2016). Accept a move iff the resulting
    cost is <= a bound; refresh the bound to the current cost every `counter_limit` steps.
    Single parameter, scale-independent. `init(cost)` seeds the running cost + bound."""

    def __init__(self, counter_limit: int):
        self.limit = max(1, int(counter_limit))
        self.cost = 0
        self.bound = 0
        self.counter = 0

    def init(self, cost: int):
        self.cost = cost
        self.bound = cost
        self.counter = 0

    def accept(self, delta: int, it: int) -> bool:
        new_cost = self.cost + delta
        accepted = delta <= 0 or new_cost <= self.bound
        if accepted:
            self.cost = new_cost
        self.counter += 1
        if self.counter >= self.limit:
            self.bound = self.cost
            self.counter = 0
        return accepted
