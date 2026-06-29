from __future__ import annotations
from typing import Dict, List
from collections import defaultdict, Counter
from dataclasses import replace
from time import perf_counter
import os

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


def _soft_score(state: State, c, s, cfg: Config) -> int:
    """Weighted soft penalty for placing candidate c. Lower is better. cohort conflict
    is gated by cfg.soft_shaping_in_repair. A unit instr_days tie-break (strictly below one
    cohort-conflict unit, so it never trades a student conflict for concentration) discourages
    opening a NEW teaching day for an instructor already at/over the day target — the
    construction-stage analog of the CP-SAT instr_days objective; inert when the dial is off
    (max_instr_days >= week length)."""
    score = 0
    if cfg.soft_shaping_in_repair:
        for h in range(c.start, c.start + c.length):
            slot = state.cohort_slot_courses.get((s.cohort_key, c.day, h))
            if slot and any(cc != s.code for cc in slot):
                score += cfg.w_cohort_conflict
    if cfg.max_instr_days < len(cfg.days()):
        for iid in state.sec_instr.get(s.section_id, ()):
            days = state.instr_active_days.get(iid, ())
            if c.day not in days and len(days) >= cfg.max_instr_days:
                score += 1
    return score


def _cand_soft(c, s, cfg: Config):
    """Per-candidate separable soft cost: S-Order + S-EngLab + S-RoomUtil. Independent of
    other blocks, so it folds into a variable's objective coefficient. Mirrors the per-variable
    coefficients in model_cpsat.build_and_solve."""
    cost = 0
    if 2 <= s.level <= 4:
        cost += cfg.w_order * (4 - s.level) * (c.start - cfg.horizon_start)
    if (cfg.eng_department_match in s.department and "#L" in c.block_id
            and c.day not in cfg.eng_lab_days):
        cost += cfg.w_englab
    if cfg.w_room_util and c.cap > 0 and not s.is_virtual and c.cap > s.students:
        cost += cfg.w_room_util * (c.cap - s.students) / c.cap
    if cfg.instr_avoid:
        for iid in s.instructor_ids:
            for hh in range(c.start, c.start + c.length):
                if (iid, c.day, hh) in cfg.instr_avoid:
                    cost += cfg.w_instr_avoid
    if cfg.instr_prefer_ids:
        for iid in s.instructor_ids:
            if iid in cfg.instr_prefer_ids:
                if not any((iid, c.day, hh) in cfg.instr_preferred
                           for hh in range(c.start, c.start + c.length)):
                    cost += cfg.w_instr_prefer
    if cfg.ref_schedule and cfg.w_perturbation:
        ref = cfg.ref_schedule.get(c.block_id)
        if ref is not None and (c.day, c.start, c.room) != ref:
            cost += cfg.w_perturbation
    return cost


def greedy_construct(state: State, order: List[str], cand_by_block,
                     cfg: Config = None) -> None:
    """Greedy construction. With cfg shaping enabled, place each block in its lowest
    soft-score feasible candidate (ties broken by candidate order = best-fit room);
    otherwise first-feasible. Shaping is on when soft_shaping_in_repair is set."""
    shaping = cfg is not None and cfg.soft_shaping_in_repair
    for bid in order:
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        if shaping:
            best, best_score = None, None
            for c in cand_by_block[bid]:
                if state.free_to_place(c, s.section_id, iids):
                    sc = _soft_score(state, c, s, cfg)
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


def _avoid_pairs_viol(placed, sec_of, avoid_pairs) -> int:
    """Count overlapping (day, hour) slots for each user-defined avoid pair."""
    if not avoid_pairs:
        return 0
    pair_codes = {code for pair in avoid_pairs for code in pair}
    code_day_hours: dict = {}   # (code, day) -> set of hours
    for bid, c in placed.items():
        code = sec_of[bid].code
        if code in pair_codes:
            key = (code, c.day)
            if key not in code_day_hours:
                code_day_hours[key] = set()
            for hh in range(c.start, c.start + c.length):
                code_day_hours[key].add(hh)
    total = 0
    for pair in avoid_pairs:
        cl = list(pair)
        if len(cl) != 2:
            continue
        a, b = cl[0], cl[1]
        for (code, day), hours in code_day_hours.items():
            if code == a:
                total += len(hours & code_day_hours.get((b, day), set()))
    return total


_DAY_IDX = {"Mo": 0, "Tu": 1, "We": 2, "Th": 3, "Fr": 4, "Sa": 5}


def _parallel_coord_viol(placed, sec_of, parallel_policies, course_codes=None) -> int:
    """Soft violations for course-code scoped parallel-section policies."""
    if not parallel_policies:
        return 0
    policies = {str(code).strip(): str(policy).strip()
                for code, policy in parallel_policies
                if str(code).strip() and str(policy).strip()}
    if course_codes is not None:
        wanted = {str(c).strip() for c in course_codes}
        policies = {code: policy for code, policy in policies.items() if code in wanted}
    if not policies:
        return 0

    by_code = defaultdict(list)
    for bid, cand in placed.items():
        s = sec_of[bid]
        if s.code in policies:
            by_code[s.code].append((bid, s, cand))

    total = 0
    for code, rows in by_code.items():
        policy = policies.get(code)
        section_ids = {s.section_id for _bid, s, _cand in rows}
        if policy in ("same-time", "spread") and len(section_ids) < 2:
            continue
        if policy == "same-time":
            slots_by_tag = defaultdict(set)
            for bid, _s, cand in rows:
                tag = bid.split("#", 1)[1] if "#" in bid else ""
                if tag.startswith("T"):
                    slots_by_tag[tag].add((cand.day, cand.start))
            total += sum(max(0, len(slots) - 1) for slots in slots_by_tag.values())
        elif policy == "spread":
            counts_by_tag_slot = defaultdict(int)
            for bid, _s, cand in rows:
                tag = bid.split("#", 1)[1] if "#" in bid else ""
                if tag.startswith("T"):
                    counts_by_tag_slot[(tag, cand.day, cand.start)] += 1
            total += sum(max(0, count - 1) for count in counts_by_tag_slot.values())
        elif policy == "lab-after-theory":
            theory_end = {}
            labs = []
            for bid, s, cand in rows:
                if "#L" in bid:
                    labs.append((s.section_id, cand))
                else:
                    key = (_DAY_IDX.get(cand.day, -1), cand.start + cand.length)
                    theory_end[s.section_id] = max(theory_end.get(s.section_id, key), key)
            for sid, cand in labs:
                if sid not in theory_end:
                    continue
                lab_key = (_DAY_IDX.get(cand.day, -1), cand.start)
                if lab_key < theory_end[sid]:
                    total += 1
    return total


def _soft_total(state, cfg, staff_ids=frozenset()) -> int:
    """Global weighted soft sum over the current full placement. Single source of truth
    for the accept guard and the convergence check — mirrors the terms add_soft_objective
    puts in the model, plus the soft terms (per-candidate, cohort-conflict, cohort-gap,
    instr_days). Cheap (no CP-SAT)."""
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
    total += cfg.w_min_working_days * _min_working_days_missing(state)
    total += cfg.w_avoid_pairs * _avoid_pairs_viol(state.placed, state.sec_of, cfg.avoid_pairs)
    total += cfg.w_parallel_coord * _parallel_coord_viol(
        state.placed, state.sec_of, cfg.parallel_policies)
    if cfg.w_building_change:
        from .config import building_of
        instr_hour_bldg = {}
        for bid, c in state.placed.items():
            s = state.sec_of[bid]
            bldg = building_of(c.room)
            if bldg is None:
                continue
            for iid in state.sec_instr.get(s.section_id, []):
                for hh in range(c.start, c.start + c.length):
                    instr_hour_bldg[(iid, c.day, hh)] = bldg
        bldg_change = sum(
            1 for (iid, day, hh), b1 in instr_hour_bldg.items()
            if instr_hour_bldg.get((iid, day, hh + 1), b1) != b1
        )
        total += cfg.w_building_change * bldg_change
    return total


def _min_working_days_missing(state, section_ids=None) -> int:
    """Missing distinct teaching days over section targets. `section_ids` scopes the
    term for local-search neighborhoods; None means all sections known to the state."""
    wanted = set(section_ids) if section_ids is not None else None
    sections = {}
    days_by_section = defaultdict(set)
    for bid, s in state.sec_of.items():
        if wanted is None or s.section_id in wanted:
            sections[s.section_id] = s
    for bid, c in state.placed.items():
        s = state.sec_of[bid]
        if wanted is None or s.section_id in wanted:
            days_by_section[s.section_id].add(c.day)
    return sum(max(0, int(getattr(s, "min_working_days", 0) or 0)
                   - len(days_by_section.get(sid, ())))
               for sid, s in sections.items()
               if int(getattr(s, "min_working_days", 0) or 0) > 0)


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

    # --- per-candidate: S-Order + S-EngLab ---
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

    # --- per-section minimum working days: missing distinct days below target ---
    free_sections = {state.sec_of[bid].section_id for bid in free}
    sections_by_id = {s.section_id: s for s in state.sec_of.values()
                      if s.section_id in free_sections}
    frozen_section_days = _dd(set)
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        sid = state.sec_of[bid].section_id
        if sid in free_sections:
            frozen_section_days[sid].add(c.day)

    free_section_day_vars = _dd(list)
    for (bid, _room, day, _start), v in x.items():
        sid = state.sec_of[bid].section_id
        if sid in free_sections:
            free_section_day_vars[(sid, day)].append(v)

    for sid, s in sections_by_id.items():
        target = int(getattr(s, "min_working_days", 0) or 0)
        if target <= 0:
            continue
        active_days = len(frozen_section_days.get(sid, ()))
        day_bools = []
        for day in cfg.days():
            if day in frozen_section_days.get(sid, ()):
                continue
            vs = free_section_day_vars.get((sid, day), ())
            if not vs:
                continue
            d = m.NewBoolVar(f"secday|{sid}|{day}")
            m.AddMaxEquality(d, vs)
            day_bools.append(d)
        missing = m.NewIntVar(0, target, f"minwd|{sid}")
        m.Add(missing >= target - active_days - sum(day_bools))
        penalty.append(cfg.w_min_working_days * missing)
        ub += cfg.w_min_working_days * target

    return penalty, ub


def repair_round(state: State, batch, cand_by_block, cfg=None,
                 tl=REPAIR_TL, staff_ids=frozenset()) -> int:
    comp = competitors(state, batch, cand_by_block)
    free = list(dict.fromkeys(list(batch) + list(comp)))[:MAX_FREE]
    free_set = set(free)

    reserved_room, reserved_instr = set(), set()
    frozen_theory_day = defaultdict(set)
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        if "#L" not in bid:
            frozen_theory_day[s.section_id].add(c.day)
        for hh in range(c.start, c.start + c.length):
            if c.room not in state.virtual:
                reserved_room.add((c.room, c.day, hh))
            for iid in iids:
                reserved_instr.add((iid, c.day, hh))

    m = cp_model.CpModel()
    x = {}
    room_occ = defaultdict(list); instr_occ = defaultdict(list); sect_occ = defaultdict(list)
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
    solver.parameters.num_search_workers = int(os.environ.get("CPSAT_MAX_WORKERS", 8))
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


def solve_repair(sections, rooms, instructors, cfg, progress_cb=None):
    _pb = progress_cb or (lambda _: None)
    cfg = replace(cfg, max_rooms_per_block=max(cfg.max_rooms_per_block, REPAIR_MAX_ROOMS))
    room_list = list(rooms.values())
    virtual_names = {r.room for r in room_list if r.is_virtual}
    blocks = [(b, s) for s in sections for b in s.blocks]
    total = len(blocks)
    sec_of = {b.block_id: s for b, s in blocks}
    sec_instr = {s.section_id: s.instructor_ids for s in sections}

    _pb(("gen_candidates", total))
    cand_by_block = {}
    for b, s in blocks:
        ins_list = _instructors_of(s, instructors)
        cand_by_block[b.block_id] = gen_candidates(b, s, ins_list, room_list, cfg)

    order = sorted((b.block_id for b, _ in blocks),
                   key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))

    state = State(sec_of, sec_instr, virtual_names)
    t0 = perf_counter()
    # Overall wall-clock budget (UI/CLI). The repair loop runs to convergence well within
    # this for current sizes; the deadline is a hard upper bound that bounds runaway sweeps
    # on much larger inputs (and keeps the synchronous UI request under Cloud Run limits).
    deadline = getattr(cfg, "repair_time_limit_s", float("inf")) if cfg else float("inf")
    _pb(("construct", None))
    greedy_construct(state, order, cand_by_block, cfg)

    sweep = 0
    while perf_counter() - t0 < deadline:
        sweep += 1
        unplaced = [bid for bid, _ in [(b.block_id, s) for b, s in blocks]
                    if bid not in state.placed]
        if not unplaced:
            break
        _pb(("repair_sweep", sweep, len(unplaced)))
        unplaced.sort(key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))
        gained = 0
        for i in range(0, len(unplaced), BATCH):
            if perf_counter() - t0 >= deadline:
                break
            batch = [bid for bid in unplaced[i:i + BATCH] if bid not in state.placed]
            if batch:
                gained += repair_round(state, batch, cand_by_block)
        if gained == 0 or sweep >= 25:
            break

    # SOFT-POLISH: move-based local search (soft_search.anneal_soft). Replaces the
    # CP-SAT frozen-LNS passes, which were a measured no-op at scale.
    post_repair_placed = dict(state.placed)
    soft_polish_rounds = 0
    soft_pre = soft_post = None
    if cfg.soft_polish_in_repair:
        from .soft_search import anneal_soft, _global_terms
        # Scale cap by problem size (~0.75 s/block); prevents tiny inputs from burning
        # the full 600 s budget (e.g. 100 blocks → ≈75 s, 841 blocks → 600 s).
        size_cap = max(30.0, len(state.placed) * 0.75)
        polish_cap = getattr(cfg, "soft_polish_budget_s", SOFT_POLISH_BUDGET_S)
        budget = min(min(float(polish_cap), size_cap), max(0.0, deadline - (perf_counter() - t0)))
        if budget > 0:
            _pb(("soft_polish", None))
            # within-run before/after: the only correct soft comparison (placement is
            # CP-SAT-nondeterministic, so a separate flag-off run is a different baseline).
            soft_pre = _global_terms(state, cfg)
            anneal_soft(state, cand_by_block, cfg, budget, seed=cfg.soft_polish_seed)
            soft_post = _global_terms(state, cfg)
            soft_polish_rounds = 1

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
        "soft_polish_rounds": soft_polish_rounds,
        "soft_pre": soft_pre,
        "soft_post": soft_post,
        "post_repair_assignments": [
            {
                "block_id": bid,
                "room": c.room,
                "day": c.day,
                "start": c.start,
                "end": c.start + c.length,
            }
            for bid, c in sorted(post_repair_placed.items())
        ],
        "placed": len(state.placed),
        "total": total,
    }
    return assignments, stats
