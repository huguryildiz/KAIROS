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


def _gap_of(hours_by_day) -> int:
    """Total per-day idle gap = sum over days of (span - load) for days with >=2 hours."""
    return sum((max(h) + 1 - min(h)) - len(h) for h in hours_by_day.values() if len(h) >= 2)


def _global_terms(state, cfg) -> dict:
    """Raw (unweighted) counts of the four UI-toggle soft terms over the FULL placement,
    plus cohort-conflict (held as a no-regress guard, not optimized). gap covers ALL
    cohorts (matches report._metrics). Single source of truth for the polish objective."""
    evening = 0
    coh_slot = defaultdict(set)      # (cohort, day, hour) -> {course}
    coh_day = defaultdict(set)       # (cohort, day) -> {hour}
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        for hh in range(c.start, c.start + c.length):
            if hh >= cfg.evening_from_hour:
                evening += 1
            coh_slot[(s.cohort_key, c.day, hh)].add(s.code)
            coh_day[(s.cohort_key, c.day)].add(hh)
    conf = sum(max(0, len(v) - 1) for v in coh_slot.values())
    gap = _gap_of(coh_day)
    rooms = len(state.room_hours_used)
    days = sum(len(d) for d in state.instr_active_days.values())
    return {"evening": evening, "gap": gap, "rooms": rooms, "days": days, "conf": conf}


def _local_terms(state, cohorts, instrs, rooms, blocks, cfg) -> dict:
    """Raw counts of the same terms over only the given entities. Each term is owned by one
    entity type (evening->block, gap/conf->cohort, days->instructor, rooms->room), so
    summing over the FULL entity sets reproduces _global_terms (consistency-tested)."""
    evening = 0
    for bid in blocks:
        c = state.placed.get(bid)
        if c is not None:
            evening += sum(1 for hh in range(c.start, c.start + c.length)
                           if hh >= cfg.evening_from_hour)
    cohort_set = set(cohorts)
    coh_slot = defaultdict(set)
    coh_day = defaultdict(set)
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        if s.cohort_key not in cohort_set:
            continue
        for hh in range(c.start, c.start + c.length):
            coh_slot[(s.cohort_key, c.day, hh)].add(s.code)
            coh_day[(s.cohort_key, c.day)].add(hh)
    conf = sum(max(0, len(v) - 1) for v in coh_slot.values())
    gap = _gap_of(coh_day)
    rooms_used = sum(1 for r in rooms if state.room_hours_used.get(r, 0) > 0)
    days = sum(len(state.instr_active_days.get(iid, ())) for iid in instrs)
    return {"evening": evening, "gap": gap, "rooms": rooms_used, "days": days, "conf": conf}


def _norm_obj(terms, base, cfg) -> float:
    """Normalized weighted sum of the four UI toggles: sum w_i * term_i / base_i. Dividing
    each term by its start value puts the four on a common scale so no single raw magnitude
    dominates, while preserving the user's relative weights. cohort_conflict is NOT in the
    objective (held separately as a no-regress guard)."""
    return (cfg.w_evening * terms["evening"] / max(base["evening"], 1)
            + cfg.w_cohort_gap * terms["gap"] / max(base["gap"], 1)
            + cfg.w_room_count * terms["rooms"] / max(base["rooms"], 1)
            + cfg.w_instr_days * terms["days"] / max(base["days"], 1))


def _slot(c):
    return (c.room, c.day, c.start)


def try_relocate(state, cand_by_block, bid, rng, eval_fn):
    """Move bid to a random alternative legal+free candidate. Leaves state in the new
    config; returns (dobj, dconf, revert) or None. eval_fn(state, cohorts, instrs, rooms,
    blocks) -> (objective, conflict) over the affected entities; dobj/dconf are the after-
    minus-before deltas. revert() restores the original placement."""
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
    o0, f0 = eval_fn(state, cohorts, instrs, rooms, blocks)
    state.release(bid)
    if not state.free_to_place(c_new, s.section_id, iids):
        state.occupy(bid, c_old)
        return None
    state.occupy(bid, c_new)
    o1, f1 = eval_fn(state, cohorts, instrs, rooms, blocks)

    def revert():
        state.release(bid)
        state.occupy(bid, c_old)
    return o1 - o0, f1 - f0, revert


def try_swap(state, cand_by_block, bid1, bid2, eval_fn):
    """Exchange the slots of bid1 and bid2 if each has a candidate for the other's current
    slot and both are feasible. Leaves state swapped; returns (dobj, dconf, revert) or
    None. eval_fn as in try_relocate."""
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
    o0, f0 = eval_fn(state, cohorts, instrs, rooms, blocks)
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
    o1, f1 = eval_fn(state, cohorts, instrs, rooms, blocks)

    def revert():
        state.release(bid1)
        state.release(bid2)
        state.occupy(bid1, c1)
        state.occupy(bid2, c2)
    return o1 - o0, f1 - f0, revert


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


class LAHC:
    """Late Acceptance Hill Climbing (Bykov). Accept iff new cost <= the cost `L` steps ago
    or <= the current cost. One parameter (history length)."""

    def __init__(self, history_len: int):
        self.L = max(1, int(history_len))
        self.cost = 0
        self.hist = []

    def init(self, cost: int):
        self.cost = cost
        self.hist = [cost] * self.L

    def accept(self, delta: int, it: int) -> bool:
        new_cost = self.cost + delta
        idx = it % self.L
        accepted = new_cost <= self.cost or new_cost <= self.hist[idx]
        if accepted:
            self.cost = new_cost
        self.hist[idx] = self.cost
        return accepted


class GreatDeluge:
    """Great Deluge. Accept iff new cost <= a water level that decays each step."""

    def __init__(self, level: float, decay: float):
        self.level = float(level)
        self.decay = float(decay)
        self.cost = 0

    def init(self, cost: int):
        self.cost = cost
        self.level = float(cost)

    def accept(self, delta: int, it: int) -> bool:
        new_cost = self.cost + delta
        accepted = delta <= 0 or new_cost <= self.level
        if accepted:
            self.cost = new_cost
        self.level = max(self.cost, self.level - self.decay)
        return accepted


class SimAnneal:
    """Simulated Annealing with geometric cooling over a fixed step budget."""

    def __init__(self, t0: float, t_end: float, steps: int, rng):
        self.t0 = float(t0)
        self.t_end = max(1e-6, float(t_end))
        self.steps = max(1, int(steps))
        self.rng = rng
        self.cost = 0
        self.ratio = (self.t_end / self.t0) ** (1.0 / self.steps) if self.t0 > 0 else 1.0
        self.t = self.t0

    def init(self, cost: int):
        self.cost = cost
        self.t = self.t0

    def accept(self, delta: int, it: int) -> bool:
        import math
        if delta <= 0:
            accepted = True
        else:
            accepted = self.rng.random() < math.exp(-delta / max(self.t, 1e-6))
        if accepted:
            self.cost += delta
        self.t = max(self.t_end, self.t * self.ratio)
        return accepted


import random as _random


def _make_acceptor(cfg, rng=None):
    a = getattr(cfg, "soft_polish_acceptor", "schc")
    n = cfg.soft_polish_counter_limit
    if a == "lahc":
        return LAHC(n)
    if a == "deluge":
        return GreatDeluge(level=0, decay=max(1, n) / 1000.0)
    if a == "sa":
        return SimAnneal(t0=max(1.0, n / 100.0), t_end=0.1, steps=1_000_000,
                         rng=rng or _random.Random(0))
    return SCHC(n)


def anneal_soft(state, cand_by_block, cfg, budget_s, seed=0):
    """Relocate/swap already-placed blocks to lower the NORMALIZED four-toggle objective
    (evening, cohort_gap[all cohorts], room_count, instr_days), guided by the acceptor.
    cohort_conflict is a no-regress guard: any move that would push global conflict above
    its start value is rejected. Never unplaces; restores the best incumbent so the
    objective never regresses globally and conflict never exceeds baseline."""
    rng = _random.Random(seed)
    placed = [bid for bid in state.placed if cand_by_block.get(bid)]
    base = _global_terms(state, cfg)
    conf_base = base["conf"]

    def eval_fn(st, cohorts, instrs, rooms, blocks):
        t = _local_terms(st, cohorts, instrs, rooms, blocks, cfg)
        return _norm_obj(t, base, cfg), t["conf"]

    e_start = _norm_obj(base, base, cfg)
    acc = _make_acceptor(cfg, rng)
    acc.init(e_start)
    cur = e_start
    conf_cur = conf_base
    best = e_start
    best_snapshot = dict(state.placed)
    at_best = True
    iters = accepted = 0
    t0 = perf_counter()
    if placed:
        while perf_counter() - t0 < budget_s:
            for _ in range(512):                 # amortize the clock check
                iters += 1
                if len(placed) >= 2 and rng.random() < 0.5:
                    b1 = placed[rng.randrange(len(placed))]
                    b2 = placed[rng.randrange(len(placed))]
                    res = try_swap(state, cand_by_block, b1, b2, eval_fn)
                else:
                    bid = placed[rng.randrange(len(placed))]
                    res = try_relocate(state, cand_by_block, bid, rng, eval_fn)
                if res is None:
                    continue
                dobj, dconf, revert = res
                if conf_cur + dconf > conf_base:     # cohort-conflict no-regress guard
                    revert()
                    continue
                if acc.accept(dobj, iters):
                    cur += dobj
                    conf_cur += dconf
                    accepted += 1
                    if cur < best - 1e-9:
                        best = cur
                        best_snapshot = dict(state.placed)
                        at_best = True
                    else:
                        at_best = False
                else:
                    revert()
    if not at_best:                          # restore best incumbent
        for bid in list(state.placed):
            state.release(bid)
        for bid, c in best_snapshot.items():
            state.occupy(bid, c)
    return {"iters": iters, "accepted": accepted, "soft_start": e_start, "soft_end": best}
