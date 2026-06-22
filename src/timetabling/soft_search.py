"""Move-based local-search soft polish for the repair solver. Operates on a converged
State by relocating/swapping already-placed blocks within their legal candidate lists,
guided by a pluggable acceptance criterion. Never unplaces (placement invariant by
construction); restores the best incumbent (soft never regresses globally)."""
from __future__ import annotations
from collections import defaultdict
from time import perf_counter

from .config import Config
from .repair import _cand_soft, _soft_total

CHAIN_MAX_DEPTH = 4   # bounded ejection-chain length in anneal_soft


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


CHEBY_RHO = 1e-3   # augmentation weight in the Chebyshev objective


def _norm_vals(terms, base, cfg):
    """The four normalized toggle values [w_i * term_i / base_i]."""
    return [cfg.w_evening * terms["evening"] / max(base["evening"], 1),
            cfg.w_cohort_gap * terms["gap"] / max(base["gap"], 1),
            cfg.w_room_count * terms["rooms"] / max(base["rooms"], 1),
            cfg.w_instr_days * terms["days"] / max(base["days"], 1)]


def _cheby(terms, base, cfg) -> float:
    """Augmented Chebyshev (min-max) objective: minimize the WORST normalized toggle, with a
    tiny sum augmentation so any Pareto improvement still lowers E (avoids weakly-optimal
    stalls). A weighted SUM over-optimizes the cheap-abundant term (gap); the max term drives
    a FAIR outcome — improving whichever toggle is currently worst."""
    vals = _norm_vals(terms, base, cfg)
    return max(vals) + CHEBY_RHO * sum(vals)


def _slot(c):
    return (c.room, c.day, c.start)


def _dterms(t0, t1):
    return {k: t1[k] - t0[k] for k in t1}


def try_relocate(state, cand_by_block, bid, rng, eval_fn):
    """Move bid to a random alternative legal+free candidate. Leaves state in the new
    config; returns (dobj, dterms, revert) or None. eval_fn(state, cohorts, instrs, rooms,
    blocks) -> (objective, terms) over the affected entities; dobj is the objective delta
    and dterms the per-term delta dict (evening/gap/rooms/days/conf). revert() restores the
    original placement."""
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
    o0, t0 = eval_fn(state, cohorts, instrs, rooms, blocks)
    state.release(bid)
    if not state.free_to_place(c_new, s.section_id, iids):
        state.occupy(bid, c_old)
        return None
    state.occupy(bid, c_new)
    o1, t1 = eval_fn(state, cohorts, instrs, rooms, blocks)

    def revert():
        state.release(bid)
        state.occupy(bid, c_old)
    return o1 - o0, _dterms(t0, t1), revert


def _feasible_ignoring_room(state, c, sid, iids):
    """True if candidate c is free on instructor / section / theory-different-day (room
    conflicts are handled separately by the chain via ejection)."""
    for hh in range(c.start, c.start + c.length):
        for iid in iids:
            if state.instr_slot.get((iid, c.day, hh)):
                return False
        if state.sect_slot.get((sid, c.day, hh)):
            return False
    if "#L" not in c.block_id and any(b != c.block_id
            for b in state.sect_theory_day.get((sid, c.day), ())):
        return False
    return True


def _room_occupants(state, c):
    """Distinct block ids occupying candidate c's room hour-slots (non-virtual)."""
    occ = set()
    if c.room in state.virtual:
        return occ
    for hh in range(c.start, c.start + c.length):
        owner = state.room_owner.get((c.room, c.day, hh))
        if owner is not None:
            occ.add(owner)
    return occ


def try_chain(state, cand_by_block, bid, rng, eval_fn, max_depth=4):
    """Bounded ejection (Kempe-style) chain. Move bid to a candidate slot; if that slot's
    room is held by a single other block, eject it and recurse (it seeks its own slot), up
    to max_depth, until some block lands in a fully free slot. Each hop stays
    instructor/section/theory-day feasible; only single-block ROOM conflicts are ejected.
    Leaves state in the chained config; returns (dobj, dterms, revert) or None. Unlocks
    moves that relocate/swap cannot in dense (100%-room) regions."""
    old = {}                                  # bid -> original candidate (restore target)
    cohorts, instrs, rooms, blocks = set(), set(), set(), set()

    def note(b, c):
        s = state.sec_of[b]
        cohorts.add(s.cohort_key)
        instrs.update(state.sec_instr.get(s.section_id, []))
        rooms.add(c.room)
        blocks.add(b)

    def restore_old():
        for b in old:
            if b in state.placed:
                state.release(b)
        for b, c in old.items():
            state.occupy(b, c)

    if state.placed.get(bid) is None:
        return None
    old[bid] = state.placed[bid]
    note(bid, old[bid])
    state.release(bid)                         # take the first block in hand
    new = {}
    to_place = bid
    ok = False
    for depth in range(max_depth):
        s = state.sec_of[to_place]
        iids = state.sec_instr.get(s.section_id, [])
        cands = [c for c in cand_by_block[to_place]
                 if not (depth == 0 and _slot(c) == _slot(old[to_place]))]
        order = list(range(len(cands)))
        rng.shuffle(order)
        chosen = victim = None
        for i in order:
            c = cands[i]
            if not _feasible_ignoring_room(state, c, s.section_id, iids):
                continue
            occ = _room_occupants(state, c)    # to_place is in hand -> only other blocks
            if not occ:
                chosen = c
                break
            if len(occ) == 1:
                v = next(iter(occ))
                if v not in old:               # never re-eject a chain member
                    chosen, victim = c, v
                    break
        if chosen is None:
            break                              # dead end: to_place is in hand
        note(to_place, chosen)
        if victim is not None:
            old.setdefault(victim, state.placed[victim])
            note(victim, state.placed[victim])
            state.release(victim)              # eject -> next in hand
        state.occupy(to_place, chosen)
        new[to_place] = chosen
        if victim is None:
            ok = True
            break
        to_place = victim
    if not ok:
        restore_old()
        return None
    new = {b: state.placed[b] for b in old}
    o1, t1 = eval_fn(state, cohorts, instrs, rooms, blocks)
    restore_old()
    o0, t0 = eval_fn(state, cohorts, instrs, rooms, blocks)
    for b in new:                              # re-apply the chained config
        if b in state.placed:
            state.release(b)
    for b, c in new.items():
        state.occupy(b, c)

    def revert():
        for b in new:
            if b in state.placed:
                state.release(b)
        for b, c in old.items():
            state.occupy(b, c)
    return o1 - o0, _dterms(t0, t1), revert


def try_swap(state, cand_by_block, bid1, bid2, eval_fn):
    """Exchange the slots of bid1 and bid2 if each has a candidate for the other's current
    slot and both are feasible. Leaves state swapped; returns (dobj, dterms, revert) or
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
    o0, t0 = eval_fn(state, cohorts, instrs, rooms, blocks)
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
    o1, t1 = eval_fn(state, cohorts, instrs, rooms, blocks)

    def revert():
        state.release(bid1)
        state.release(bid2)
        state.occupy(bid1, c1)
        state.occupy(bid2, c2)
    return o1 - o0, _dterms(t0, t1), revert


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
    """Relocate/swap/chain already-placed blocks to lower the augmented-Chebyshev (min-max)
    objective over the four toggles (evening, cohort_gap[all cohorts], room_count,
    instr_days) — minimizing the WORST normalized toggle drives a FAIR outcome rather than
    over-optimizing the cheap-abundant one (gap). cohort_conflict is a no-regress guard.
    Never unplaces; restores the best incumbent so the objective never regresses globally."""
    rng = _random.Random(seed)
    placed = [bid for bid in state.placed if cand_by_block.get(bid)]
    base = _global_terms(state, cfg)

    def eval_fn(st, cohorts, instrs, rooms, blocks):
        t = _local_terms(st, cohorts, instrs, rooms, blocks, cfg)
        return _norm_obj(t, base, cfg), t

    # Objective = augmented Chebyshev (min-max) over the four toggles, evaluated on the GLOBAL
    # per-term totals (cur_terms, tracked incrementally). The moves return per-term local
    # deltas (dterms); the global max is not separable, so the objective is computed here, not
    # in the move. No-regress guard over cohort_conflict only; placement invariant by
    # construction. The four toggles trade off, but the min-max drives a FAIR outcome.
    cur_terms = dict(base)
    e_start = _cheby(cur_terms, base, cfg)
    acc = _make_acceptor(cfg, rng)
    acc.init(e_start)
    cur = e_start
    best = e_start
    best_snapshot = dict(state.placed)
    at_best = True
    iters = accepted = 0
    t0 = perf_counter()
    if placed:
        while perf_counter() - t0 < budget_s:
            for _ in range(512):                 # amortize the clock check
                iters += 1
                r = rng.random()
                if len(placed) >= 2 and r < 0.4:
                    b1 = placed[rng.randrange(len(placed))]
                    b2 = placed[rng.randrange(len(placed))]
                    res = try_swap(state, cand_by_block, b1, b2, eval_fn)
                elif r < 0.7:
                    bid = placed[rng.randrange(len(placed))]
                    res = try_chain(state, cand_by_block, bid, rng, eval_fn, CHAIN_MAX_DEPTH)
                else:
                    bid = placed[rng.randrange(len(placed))]
                    res = try_relocate(state, cand_by_block, bid, rng, eval_fn)
                if res is None:
                    continue
                _dobj, dterms, revert = res
                if cur_terms["conf"] + dterms["conf"] > base["conf"]:
                    revert()                     # cohort-conflict no-regress guard
                    continue
                new_terms = {k: cur_terms[k] + dterms[k] for k in cur_terms}
                new_e = _cheby(new_terms, base, cfg)
                if acc.accept(new_e - cur, iters):
                    cur = new_e
                    cur_terms = new_terms
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
