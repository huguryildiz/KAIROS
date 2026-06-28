"""Move-based local-search soft polish for the repair solver. Operates on a converged
State by relocating/swapping already-placed blocks within their legal candidate lists,
guided by a pluggable acceptance criterion. Never unplaces (placement invariant by
construction); restores the best incumbent (soft never regresses globally)."""
from __future__ import annotations
from collections import defaultdict
from time import perf_counter

from .config import Config, building_of
from .repair import (
    _cand_soft, _soft_total, _min_working_days_missing, _avoid_pairs_viol,
    _parallel_coord_viol,
)

CHAIN_MAX_DEPTH = 4   # bounded ejection-chain length in anneal_soft

_DAY_IDX = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5}


def _day_span(days) -> int:
    """Teaching day span: last day index minus first (Mo+Tu=1, Mo+Fr=4, single day=0)."""
    idxs = [_DAY_IDX[d] for d in days if d in _DAY_IDX]
    return max(idxs) - min(idxs) if len(idxs) > 1 else 0


def _local_soft(state, cohorts, instrs, rooms, blocks, cfg: Config) -> int:
    """Weighted soft over only the given entities. Each term is owned by one entity type
    (per-candidate->block, cohort-conflict/gap->cohort, instr_days->instructor,
    min_working_days->section), so summing over the FULL entity sets equals _soft_total."""
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
    total += cfg.w_nonadjacent * sum(_day_span(state.instr_active_days.get(iid, ())) for iid in instrs)
    section_ids = {state.sec_of[bid].section_id for bid in blocks if bid in state.sec_of}
    total += cfg.w_min_working_days * _min_working_days_missing(state, section_ids)
    return total


def _gap_of(hours_by_day) -> int:
    """Total per-day idle gap = sum over days of (span - load) for days with >=2 hours."""
    return sum((max(h) + 1 - min(h)) - len(h) for h in hours_by_day.values() if len(h) >= 2)


def _run_excess(hours, T: int) -> int:
    """Sum over maximal consecutive runs of max(0, run_len - T). Used by maxrun."""
    if not hours:
        return 0
    hs = sorted(hours)
    total = 0
    run = 1
    for i in range(1, len(hs)):
        if hs[i] == hs[i - 1] + 1:
            run += 1
        else:
            total += max(0, run - T)
            run = 1
    return total + max(0, run - T)


def _evening_of(hours_by_day, cfg) -> int:
    """Late-hour load as occupied hour-slots at or after cfg.evening_from_hour."""
    return sum(1 for hours in hours_by_day.values()
               for h in hours if h >= cfg.evening_from_hour)


def _bad_load_by_entity(hours_by_day, cfg, prefix: str) -> dict:
    """Per entity discomfort used by fairness: gaps + long runs + late slots."""
    pain = defaultdict(int)
    for (entity, _day), hours in hours_by_day.items():
        if not hours:
            continue
        gap = (max(hours) + 1 - min(hours)) - len(hours) if len(hours) >= 2 else 0
        evening = sum(1 for h in hours if h >= cfg.evening_from_hour)
        pain[(prefix, entity)] += gap + _run_excess(hours, cfg.max_consecutive_hours) + evening
    return pain


def _fairness_of(coh_day, instr_day, cfg) -> int:
    """Squared bad-load concentration over cohorts and instructors."""
    pain = defaultdict(int)
    for key, value in _bad_load_by_entity(coh_day, cfg, "cohort").items():
        pain[key] += value
    for key, value in _bad_load_by_entity(instr_day, cfg, "instr").items():
        pain[key] += value
    return sum(v * v for v in pain.values())


def _global_terms(state, cfg) -> dict:
    """Raw counts of the soft terms over the FULL placement. idle/conf over cohorts (all),
    maxrun over cohorts+instructors, instr_days over instructors, room_stable and
    min_working_days per section, free_day over cohorts in the configured year-levels."""
    coh_day = defaultdict(set)        # (cohort, day) -> {hour}
    coh_slot = defaultdict(set)       # (cohort, day, hour) -> {course}
    instr_day = defaultdict(set)      # (iid, day) -> {hour}
    sec_rooms = defaultdict(set)      # section_id -> {room}
    coh_days_used = defaultdict(set)  # cohort -> {day}
    instr_avoid_viol = 0
    instr_prefer_miss = 0
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        sec_rooms[s.section_id].add(c.room)
        coh_days_used[s.cohort_key].add(c.day)
        for hh in range(c.start, c.start + c.length):
            coh_day[(s.cohort_key, c.day)].add(hh)
            coh_slot[(s.cohort_key, c.day, hh)].add(s.code)
        for iid in state.sec_instr.get(s.section_id, []):
            for hh in range(c.start, c.start + c.length):
                instr_day[(iid, c.day)].add(hh)
                if cfg.instr_avoid and (iid, c.day, hh) in cfg.instr_avoid:
                    instr_avoid_viol += 1
            if iid in cfg.instr_prefer_ids:
                if not any((iid, c.day, hh) in cfg.instr_preferred
                           for hh in range(c.start, c.start + c.length)):
                    instr_prefer_miss += 1
    T = cfg.max_consecutive_hours
    maxrun = (sum(_run_excess(h, T) for h in coh_day.values())
              + sum(_run_excess(h, T) for h in instr_day.values()))
    evening = _evening_of(coh_day, cfg) + _evening_of(instr_day, cfg)
    instr_idle = _gap_of(instr_day)
    fairness = _fairness_of(coh_day, instr_day, cfg)
    years = {str(y) for y in cfg.free_day_year_levels}
    n_days = len(cfg.days())
    free_day = sum(max(0, len(days) - (n_days - 1))
                   for cohort, days in coh_days_used.items()
                   if cohort.rsplit("-", 1)[-1] in years) if years else 0
    room_util = sum(max(0, (c.cap - state.sec_of[bid].students) / c.cap)
                    for bid, c in state.placed.items()
                    if not state.sec_of[bid].is_virtual and c.cap > 0)
    building_change = 0
    if cfg.w_building_change:
        instr_hour_bldg = {}
        for bid, c in state.placed.items():
            s = state.sec_of[bid]
            bldg = building_of(c.room)
            if bldg is None:
                continue
            for iid in state.sec_instr.get(s.section_id, []):
                for hh in range(c.start, c.start + c.length):
                    instr_hour_bldg[(iid, c.day, hh)] = bldg
        building_change = sum(
            1 for (iid, day, hh), b1 in instr_hour_bldg.items()
            if instr_hour_bldg.get((iid, day, hh + 1), b1) != b1
        )
    return {
        "idle": _gap_of(coh_day),
        "maxrun": maxrun,
        "instr_days": sum(max(0, len(d) - cfg.max_instr_days)
                          for d in state.instr_active_days.values()),
        "nonadjacent": sum(_day_span(d) for d in state.instr_active_days.values()),
        "evening": evening,
        "instr_idle": instr_idle,
        "fairness": fairness,
        "room_stable": sum(max(0, len(rs) - 1) for rs in sec_rooms.values()),
        "free_day": free_day,
        "room_util": room_util,
        "min_working_days": _min_working_days_missing(state),
        "parallel_coord": _parallel_coord_viol(
            state.placed, state.sec_of, cfg.parallel_policies),
        "instr_avoid_viol": instr_avoid_viol,
        "instr_prefer_miss": instr_prefer_miss,
        "conf": sum(max(0, len(v) - 1) for v in coh_slot.values()),
        "avoid_pairs_viol": _avoid_pairs_viol(state.placed, state.sec_of, cfg.avoid_pairs),
        "building_change": building_change,
    }


def _local_terms(state, cohorts, instrs, rooms, blocks, cfg) -> dict:
    """Same terms over only the given entities. Each term is owned by one entity type:
    idle/conf/free_day -> cohort, maxrun -> cohort+instructor, instr_days -> instructor,
    room_stable/min_working_days -> section (derived from blocks). Summing over the full
    sets == _global_terms."""
    cohort_set, instr_set = set(cohorts), set(instrs)
    sections = {bid.split("#")[0] for bid in blocks}
    course_codes = {state.sec_of[bid].code for bid in blocks if bid in state.sec_of}
    coh_day = defaultdict(set)
    coh_slot = defaultdict(set)
    coh_days_used = defaultdict(set)
    instr_day = defaultdict(set)
    sec_rooms = defaultdict(set)
    instr_avoid_viol = 0
    instr_prefer_miss = 0
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        if s.section_id in sections:
            sec_rooms[s.section_id].add(c.room)
        if s.cohort_key in cohort_set:
            coh_days_used[s.cohort_key].add(c.day)
            for hh in range(c.start, c.start + c.length):
                coh_day[(s.cohort_key, c.day)].add(hh)
                coh_slot[(s.cohort_key, c.day, hh)].add(s.code)
        for iid in state.sec_instr.get(s.section_id, []):
            if iid in instr_set:
                for hh in range(c.start, c.start + c.length):
                    instr_day[(iid, c.day)].add(hh)
                    if cfg.instr_avoid and (iid, c.day, hh) in cfg.instr_avoid:
                        instr_avoid_viol += 1
                if s.section_id in sections and iid in cfg.instr_prefer_ids:
                    if not any((iid, c.day, hh) in cfg.instr_preferred
                               for hh in range(c.start, c.start + c.length)):
                        instr_prefer_miss += 1
    T = cfg.max_consecutive_hours
    maxrun = (sum(_run_excess(h, T) for h in coh_day.values())
              + sum(_run_excess(h, T) for h in instr_day.values()))
    evening = _evening_of(coh_day, cfg) + _evening_of(instr_day, cfg)
    instr_idle = _gap_of(instr_day)
    fairness = _fairness_of(coh_day, instr_day, cfg)
    years = {str(y) for y in cfg.free_day_year_levels}
    n_days = len(cfg.days())
    free_day = sum(max(0, len(days) - (n_days - 1))
                   for cohort, days in coh_days_used.items()
                   if cohort.rsplit("-", 1)[-1] in years) if years else 0
    local_instr_hour_bldg = {}
    if cfg.w_building_change:
        for bid, c in state.placed.items():
            s = state.sec_of[bid]
            bldg = building_of(c.room)
            if bldg is None:
                continue
            for iid in state.sec_instr.get(s.section_id, []):
                if iid in instr_set:
                    for hh in range(c.start, c.start + c.length):
                        local_instr_hour_bldg[(iid, c.day, hh)] = bldg
    local_building_change = sum(
        1 for (iid, day, hh), b1 in local_instr_hour_bldg.items()
        if local_instr_hour_bldg.get((iid, day, hh + 1), b1) != b1
    )
    return {
        "idle": _gap_of(coh_day),
        "maxrun": maxrun,
        "instr_days": sum(max(0, len(state.instr_active_days.get(iid, ())) - cfg.max_instr_days)
                          for iid in instr_set),
        "nonadjacent": sum(_day_span(state.instr_active_days.get(iid, ())) for iid in instr_set),
        "evening": evening,
        "instr_idle": instr_idle,
        "fairness": fairness,
        "room_stable": sum(max(0, len(rs) - 1) for rs in sec_rooms.values()),
        "free_day": free_day,
        "room_util": sum(max(0, (c.cap - state.sec_of[bid].students) / c.cap)
                         for bid, c in state.placed.items()
                         if bid.split("#")[0] in sections
                         and not state.sec_of[bid].is_virtual and c.cap > 0),
        "min_working_days": _min_working_days_missing(state, sections),
        "parallel_coord": _parallel_coord_viol(
            state.placed, state.sec_of, cfg.parallel_policies, course_codes),
        "instr_avoid_viol": instr_avoid_viol,
        "instr_prefer_miss": instr_prefer_miss,
        "conf": sum(max(0, len(v) - 1) for v in coh_slot.values()),
        "avoid_pairs_viol": _avoid_pairs_viol(
            state.placed, state.sec_of,
            [p for p in cfg.avoid_pairs
             if p & {state.sec_of[bid].code for bid in blocks if bid in state.sec_of}]
            if cfg.avoid_pairs else []),
        "building_change": local_building_change,
    }


def _norm_obj(terms, base, cfg) -> float:
    """Normalized weighted sum of the non-guard terms. conf is held separately as a
    no-regress guard (not here). Dividing by base puts terms on a common scale -> weights are
    pure relative preference; at base each term contributes exactly its weight."""
    return (cfg.w_idle * terms["idle"] / max(base["idle"], 1)
            + cfg.w_maxrun * terms["maxrun"] / max(base["maxrun"], 1)
            + cfg.w_instr_days * terms["instr_days"] / max(base["instr_days"], 1)
            + cfg.w_nonadjacent * terms["nonadjacent"] / max(base["nonadjacent"], 1)
            + cfg.w_evening * terms["evening"] / max(base["evening"], 1)
            + cfg.w_instr_idle * terms["instr_idle"] / max(base["instr_idle"], 1)
            + cfg.w_fairness * terms["fairness"] / max(base["fairness"], 1)
            + cfg.w_room_stable * terms["room_stable"] / max(base["room_stable"], 1)
            + cfg.w_free_day * terms["free_day"] / max(base["free_day"], 1)
            + cfg.w_room_util * terms["room_util"] / max(base["room_util"], 1)
            + cfg.w_min_working_days * terms["min_working_days"] / max(base["min_working_days"], 1)
            + cfg.w_parallel_coord * terms["parallel_coord"] / max(base["parallel_coord"], 1)
            + cfg.w_instr_avoid * terms["instr_avoid_viol"] / max(base["instr_avoid_viol"], 1)
            + cfg.w_instr_prefer * terms["instr_prefer_miss"] / max(base["instr_prefer_miss"], 1)
            + cfg.w_avoid_pairs * terms["avoid_pairs_viol"] / max(base["avoid_pairs_viol"], 1)
            + cfg.w_building_change * terms["building_change"] / max(base["building_change"], 1))


def _slot(c):
    return (c.room, c.day, c.start)


def _dterms(t0, t1):
    return {k: t1[k] - t0[k] for k in t1}


def try_relocate(state, cand_by_block, bid, rng, eval_fn):
    """Move bid to a random alternative legal+free candidate. Leaves state in the new
    config; returns (dobj, dterms, revert) or None. eval_fn(state, cohorts, instrs, rooms,
    blocks) -> (objective, terms) over the affected entities; dobj is the objective delta
    and dterms the per-term delta dict (idle/maxrun/instr_days/room_stable/free_day/conf). revert() restores the
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


def try_consolidate_instr(state, cand_by_block, iid, rng, eval_fn):
    """Targeted move for instr_days: relocate one of instructor iid's blocks off a single-block
    teaching day onto a day iid already teaches, vacating the sparse day and cutting iid's
    active-day count. Falls back to the least-loaded active day when none is single-block.
    Generic relocate/swap almost never lands such a move at scale (it requires the target day
    to be one iid ALREADY uses); this primitive proposes it directly. Same return contract as
    try_relocate; None when no feasible consolidating move exists."""
    blocks_by_day = defaultdict(list)
    for bid in state.instr_blocks.get(iid, ()):
        c = state.placed.get(bid)
        if c is not None:
            blocks_by_day[c.day].append(bid)
    if len(blocks_by_day) < 2:
        return None
    single = [d for d, bs in blocks_by_day.items() if len(bs) == 1]
    src_day = (single[rng.randrange(len(single))] if single
               else min(blocks_by_day, key=lambda d: len(blocks_by_day[d])))
    target_days = set(blocks_by_day) - {src_day}
    src_blocks = blocks_by_day[src_day][:]
    rng.shuffle(src_blocks)
    for bid in src_blocks:
        s = state.sec_of[bid]
        iids = state.sec_instr.get(s.section_id, [])
        c_old = state.placed.get(bid)
        if c_old is None:
            continue
        alts = [c for c in cand_by_block[bid]
                if c.day in target_days and _slot(c) != _slot(c_old)]
        if not alts:
            continue
        c_new = alts[rng.randrange(len(alts))]
        cohorts = {s.cohort_key}
        instrs = set(iids)
        rooms = {c_old.room, c_new.room}
        eblocks = {bid}
        o0, t0 = eval_fn(state, cohorts, instrs, rooms, eblocks)
        state.release(bid)
        if not state.free_to_place(c_new, s.section_id, iids):
            state.occupy(bid, c_old)
            continue
        state.occupy(bid, c_new)
        o1, t1 = eval_fn(state, cohorts, instrs, rooms, eblocks)

        def revert(bid=bid, c_old=c_old):
            state.release(bid)
            state.occupy(bid, c_old)
        return o1 - o0, _dterms(t0, t1), revert
    return None


def try_free_cohort_day(state, cand_by_block, cohort_key, rng, eval_fn, cfg):
    """Compound move for free_day: vacate the least-loaded day for cohort_key, creating a
    cohort-wide free day. Only attempts when the cohort's year level is in
    cfg.free_day_year_levels and the cohort currently occupies ALL working days. All blocks
    on the chosen day must find feasible alternatives on other days; if any block cannot
    relocate the whole move is reverted atomically. Same return contract as try_relocate;
    returns None when infeasible or the cohort already has a free day."""
    years = {str(y) for y in cfg.free_day_year_levels}
    if cohort_key.rsplit("-", 1)[-1] not in years:
        return None

    blocks_by_day = defaultdict(list)
    for bid, c in state.placed.items():
        if state.sec_of[bid].cohort_key == cohort_key:
            blocks_by_day[c.day].append(bid)

    n_days = len(cfg.days())
    if len(blocks_by_day) < n_days:
        return None  # cohort already has a free day

    src_day = min(blocks_by_day, key=lambda d: len(blocks_by_day[d]))
    src_blocks = list(blocks_by_day[src_day])

    old = {}        # bid -> original Candidate
    new_c = {}      # bid -> new Candidate
    cohorts = {cohort_key}
    instrs, rooms, blocks_set = set(), set(), set()

    def _revert_partial():
        for b in list(new_c):
            state.release(b)
            state.occupy(b, old[b])

    for bid in src_blocks:
        s = state.sec_of[bid]
        iids = state.sec_instr.get(s.section_id, [])
        c_old = state.placed.get(bid)
        if c_old is None:
            _revert_partial()
            return None
        alts = [c for c in cand_by_block.get(bid, []) if c.day != src_day]
        rng.shuffle(alts)
        placed_ok = False
        for c_new in alts:
            state.release(bid)
            if state.free_to_place(c_new, s.section_id, iids):
                state.occupy(bid, c_new)
                old[bid] = c_old
                new_c[bid] = c_new
                instrs.update(iids)
                rooms |= {c_old.room, c_new.room}
                blocks_set.add(bid)
                placed_ok = True
                break
            else:
                state.occupy(bid, c_old)
        if not placed_ok:
            _revert_partial()
            return None

    # All blocks moved off src_day — evaluate post → revert → pre → re-apply
    o1, t1 = eval_fn(state, cohorts, instrs, rooms, blocks_set)
    for b in list(new_c):
        state.release(b)
        state.occupy(b, old[b])
    o0, t0 = eval_fn(state, cohorts, instrs, rooms, blocks_set)
    for b in list(new_c):
        state.release(b)
        state.occupy(b, new_c[b])

    def revert():
        for b in list(new_c):
            state.release(b)
            state.occupy(b, old[b])

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
    """Late Acceptance Hill Climbing (Bykov). Accept iff new cost <= the cost `L` scored
    candidates ago or <= the current cost. One parameter (history length).

    The ring advances on every scored candidate passed to accept() via an internal cursor,
    NOT the caller's iteration id `it`. anneal_soft increments `it` on loop turns that never
    reach accept() (infeasible moves, conf-guard reverts), so `it % L` would index the ring
    sparsely; the internal cursor keeps "L scored candidates ago" canonical. `it` is kept in
    the signature only for protocol parity with SCHC/Deluge/SA."""

    def __init__(self, history_len: int):
        self.L = max(1, int(history_len))
        self.cost = 0.0
        self.hist = []
        self.pos = 0

    def init(self, cost: float):
        self.cost = float(cost)
        self.hist = [self.cost] * self.L
        self.pos = 0

    def accept(self, delta: float, it: int) -> bool:
        candidate = self.cost + float(delta)
        late = self.hist[self.pos]
        accepted = candidate <= self.cost or candidate <= late
        if accepted:
            self.cost = candidate
        self.hist[self.pos] = self.cost
        self.pos = (self.pos + 1) % self.L
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
    """Relocate/swap/chain already-placed blocks to lower the normalized weighted-sum objective
    over the non-guard soft terms (idle, maxrun, instr_days, room_stable, free_day,
    min_working_days, and optional advanced dials); each is
    divided by its polish-start baseline so weights are pure relative preference. cohort
    conflict (conf) is a no-regress guard. Never unplaces; restores the best incumbent so the
    objective never regresses globally."""
    rng = _random.Random(seed)
    placed = [bid for bid in state.placed if cand_by_block.get(bid)]
    instr_list = sorted({iid for iids in state.sec_instr.values() for iid in iids})
    # The targeted instr-day consolidation move only earns its move-budget share when the
    # instr_days dial is on (max_instr_days below the working-day count gives the term headroom);
    # when off it would propose mostly-rejected moves and starve maxrun/room_stable, so skip it.
    consolidate_on = bool(instr_list) and cfg.max_instr_days < len(cfg.days())
    years = {str(y) for y in cfg.free_day_year_levels}
    cohort_list = sorted({state.sec_of[bid].cohort_key for bid in state.placed
                          if state.sec_of[bid].cohort_key.rsplit("-", 1)[-1] in years})
    free_day_on = bool(cohort_list)
    base = _global_terms(state, cfg)

    def eval_fn(st, cohorts, instrs, rooms, blocks):
        t = _local_terms(st, cohorts, instrs, rooms, blocks, cfg)
        return _norm_obj(t, base, cfg), t

    # Objective = normalized weighted sum over the non-guard soft terms, evaluated on the
    # GLOBAL per-term totals (cur_terms, tracked incrementally via the moves' per-term local
    # deltas, dterms). No-regress guard over cohort_conflict only; placement invariant by
    # construction.
    cur_terms = dict(base)
    e_start = _norm_obj(cur_terms, base, cfg)
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
                elif r < 0.85 or (not consolidate_on and not free_day_on):
                    bid = placed[rng.randrange(len(placed))]
                    res = try_relocate(state, cand_by_block, bid, rng, eval_fn)
                elif consolidate_on and (not free_day_on or r < 0.925):
                    iid = instr_list[rng.randrange(len(instr_list))]
                    res = try_consolidate_instr(state, cand_by_block, iid, rng, eval_fn)
                else:
                    cohort = cohort_list[rng.randrange(len(cohort_list))]
                    res = try_free_cohort_day(state, cand_by_block, cohort, rng, eval_fn, cfg)
                if res is None:
                    continue
                _dobj, dterms, revert = res
                if cur_terms["conf"] + dterms["conf"] > base["conf"]:
                    revert()                     # cohort-conflict no-regress guard
                    continue
                new_terms = {k: cur_terms[k] + dterms[k] for k in cur_terms}
                new_e = _norm_obj(new_terms, base, cfg)
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
