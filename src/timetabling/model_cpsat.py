from __future__ import annotations
from typing import List, Dict, Tuple
from collections import defaultdict

from ortools.sat.python import cp_model

from .config import Config
from .model import (Section, Block, Room, Instructor, Candidate, Assignment,
                    overload_eligible_ids)


def _blackout_hours(instructors, cfg: Config):
    return cfg.closed_hours(any(ins.is_staff for ins in instructors))


def feasible_rooms_for(block: Block, section: Section, rooms: List[Room],
                       cfg: Config) -> List[Room]:
    if section.is_virtual:
        return [r for r in rooms if r.is_virtual][:1]
    if block.needs_lab and section.lab_room:
        return [r for r in rooms if r.room == section.lab_room]   # pinned lab room
    if section.requires_lab_room:        # explicit Room Type = lab -> lab-flagged rooms only
        fr = [r for r in rooms if r.is_physical and r.is_lab and r.cap >= section.students]
    else:
        # non-lab block, or a lab held in a regular room (no designated lab room)
        fr = [r for r in rooms if r.is_physical and r.cap >= section.students]
    fr.sort(key=lambda r: (r.cap, r.room))
    return fr[:cfg.max_rooms_per_block]


def _instructors_of(section: Section, instructors: Dict[str, Instructor]) -> List[Instructor]:
    default = Instructor("", "", False, "")
    return [instructors.get(i, default) for i in section.instructor_ids] or [default]


def split_roomable(sections, rooms, cfg, instructors=None):
    instructors = instructors or {}
    roomable, excluded = [], []
    for s in sections:
        ins_list = _instructors_of(s, instructors)
        issues = []
        for b in s.blocks:
            if gen_candidates(b, s, ins_list, rooms, cfg):
                continue
            if not feasible_rooms_for(b, s, rooms, cfg):
                issues.append([b.block_id, "no room with sufficient capacity"])
            else:
                issues.append([b.block_id, "block longer than daily time window"])
        if issues:
            excluded.append({"section_id": s.section_id, "students": s.students, "issues": issues})
        else:
            roomable.append(s)
    return roomable, excluded


def gen_candidates(block: Block, section: Section, instructors: List[Instructor],
                   rooms: List[Room], cfg: Config) -> List[Candidate]:
    end_cap = cfg.undergrad_end if section.level <= 4 else cfg.grad_end
    start_lo = cfg.horizon_start if section.level <= 4 else cfg.grad_start
    closed = _blackout_hours(instructors, cfg)
    feasible_rooms = feasible_rooms_for(block, section, rooms, cfg)
    # Fixed-slot pin: only the section's first block is pinned to (fixed_day, fixed_start).
    pin = bool(section.fixed_day) and bool(section.blocks) \
        and block.block_id == section.blocks[0].block_id
    # Per-instructor availability (same mechanism as the blackout, keyed per id).
    unavail = cfg.instr_unavailable
    sec_iids = section.instructor_ids
    cands: List[Candidate] = []
    for r in feasible_rooms:
        for d in cfg.days():
            if pin and d != section.fixed_day:
                continue
            for h in range(start_lo, end_cap - block.length + 1):
                if pin and h != section.fixed_start:
                    continue
                span = range(h, h + block.length)
                if any((d, hh) in closed for hh in span):
                    continue
                if unavail and any((iid, d, hh) in unavail
                                   for iid in sec_iids for hh in span):
                    continue
                cands.append(Candidate(block.block_id, r.room, d, h, block.length))
    return cands


def build_and_solve(sections: List[Section], rooms: List[Room],
                    instructors: Dict[str, Instructor], cfg: Config,
                    reserved=None, reserved_instr=None) -> Tuple[List[Assignment], Dict]:
    model = cp_model.CpModel()
    blocks = [(b, s) for s in sections for b in s.blocks]

    x: Dict[tuple, cp_model.IntVar] = {}
    cand_by_block: Dict[str, List[Candidate]] = {}
    unplaced: List[str] = []
    default_instr = Instructor("", "", False, "")
    order_terms = []
    englab_terms = []
    sbd = defaultdict(list)  # (section_id, block_id, day) -> vars (multi-block sections)

    room_occ = defaultdict(list)          # (room, day, hour) -> vars
    instr_occ = defaultdict(list)         # (instr_id, day, hour) -> vars
    cohort_course_occ = defaultdict(list)  # (cohort, course, day, hour) -> vars
    cohort_hour_occ = defaultdict(list)   # (cohort, day, hour) -> vars (compact cohorts only)
    section_occ = defaultdict(list)       # (section_id, day, hour) -> vars
    room_used_vars = defaultdict(list)            # room -> vars
    instr_day_vars = defaultdict(list)            # (instr_id, day) -> vars
    instr_day_load = defaultdict(list)            # (instr_id, day) -> per-hour vars (sum = daily hours)
    evening_vars = []

    compact_years = {str(y) for y in cfg.compact_cohort_years}
    virtual_names = {r.room for r in rooms if r.is_virtual}

    for b, s in blocks:
        ins_list = _instructors_of(s, instructors)
        cands = gen_candidates(b, s, ins_list, rooms, cfg)
        if reserved:
            cands = [c for c in cands
                     if not any((c.room, c.day, hh) in reserved
                                for hh in range(c.start, c.start + c.length))]
        if reserved_instr and s.instructor_ids:
            cands = [c for c in cands
                     if not any((iid, c.day, hh) in reserved_instr
                                for iid in s.instructor_ids
                                for hh in range(c.start, c.start + c.length))]
        cand_by_block[b.block_id] = cands
        if not cands:
            unplaced.append(b.block_id)
            continue
        bvars = []
        for c in cands:
            v = model.NewBoolVar(f"x|{c.block_id}|{c.room}|{c.day}|{c.start}")
            x[(c.block_id, c.room, c.day, c.start)] = v
            bvars.append(v)
            if 2 <= s.level <= 4:
                coeff = cfg.w_order * (4 - s.level) * (c.start - cfg.horizon_start)
                if coeff:
                    order_terms.append(coeff * v)
            if (cfg.eng_faculty_match in s.faculty and b.needs_lab
                    and c.day not in cfg.eng_lab_days):
                englab_terms.append(cfg.w_englab * v)
            if len(s.blocks) >= 2:
                sbd[(s.section_id, b.block_id, c.day)].append(v)
            for hh in range(c.start, c.start + c.length):
                if c.room not in virtual_names:
                    room_occ[(c.room, c.day, hh)].append(v)
                for iid in s.instructor_ids:
                    instr_occ[(iid, c.day, hh)].append(v)
                    instr_day_load[(iid, c.day)].append(v)
                cohort_course_occ[(s.cohort_key, s.code, c.day, hh)].append(v)
                if s.cohort_key.rsplit("-", 1)[-1] in compact_years:
                    cohort_hour_occ[(s.cohort_key, c.day, hh)].append(v)
                section_occ[(s.section_id, c.day, hh)].append(v)
                if hh >= cfg.evening_from_hour:
                    evening_vars.append(v)
            if c.room not in virtual_names:
                room_used_vars[c.room].append(v)
            for iid in s.instructor_ids:
                instr_day_vars[(iid, c.day)].append(v)
        model.AddExactlyOne(bvars)   # H1

    # H2/H3/H_self: at most one occupant per resource-slot
    for occ in (room_occ, instr_occ, section_occ):
        for key, vs in occ.items():
            if len(vs) > 1:
                model.Add(sum(vs) <= 1)

    # H4 course-level cohort conflict is SOFT: penalize each distinct course beyond the first
    # in a (cohort, day, hour) slot. Rooms/instructors/self stay hard, so a schedule always exists.
    slot_courses = defaultdict(list)
    for (cohort, course, day, hh), vs in cohort_course_occ.items():
        b = model.NewBoolVar(f"busy|{cohort}|{course}|{day}|{hh}")
        model.AddMaxEquality(b, vs)
        slot_courses[(cohort, day, hh)].append(b)
    cohort_conflict_terms = []
    for (cohort, day, hh), busies in slot_courses.items():
        if len(busies) > 1:
            excess = model.NewIntVar(0, len(busies), f"cohconf|{cohort}|{day}|{hh}")
            model.Add(excess >= sum(busies) - 1)
            cohort_conflict_terms.append(excess)

    # soft: cohort daily compactness (minimize student idle gaps)
    gap_terms = []
    ch_by_cd = defaultdict(dict)  # (cohort, day) -> {hour: active bool}
    for (cohort, day, hh), vs in cohort_hour_occ.items():
        a = model.NewBoolVar(f"chact|{cohort}|{day}|{hh}")
        model.AddMaxEquality(a, vs)
        ch_by_cd[(cohort, day)][hh] = a
    BIG = cfg.horizon_end + 1
    for (cohort, day), hourmap in ch_by_cd.items():
        hours = sorted(hourmap)
        if len(hours) < 2:
            continue
        load = sum(hourmap[h] for h in hours)
        first = model.NewIntVar(0, BIG, f"first|{cohort}|{day}")
        last = model.NewIntVar(0, BIG, f"last|{cohort}|{day}")
        model.AddMaxEquality(last, [(h + 1) * hourmap[h] for h in hours])
        model.AddMinEquality(first, [h * hourmap[h] + BIG * (1 - hourmap[h]) for h in hours])
        gap = model.NewIntVar(0, cfg.horizon_end, f"gap|{cohort}|{day}")
        model.Add(gap >= last - first - load)
        gap_terms.append(gap)

    # soft: spread a section's split blocks across days
    nonadj_terms = []
    sbd_bool = {}
    sd_blocks = defaultdict(set)
    for (sid, bid, day), vs in sbd.items():
        z = model.NewBoolVar(f"sbd|{sid}|{bid}|{day}")
        model.AddMaxEquality(z, vs)
        sbd_bool[(sid, bid, day)] = z
        sd_blocks[(sid, day)].add(bid)
    for (sid, day), bids in sd_blocks.items():
        if len(bids) >= 2:
            extra = model.NewIntVar(0, len(bids), f"sameday|{sid}|{day}")
            model.Add(extra >= sum(sbd_bool[(sid, b, day)] for b in bids) - 1)
            nonadj_terms.append(extra)

    # HARD: a section's theory sessions land on different days (T:3 -> 2+1, two days)
    theory_sd = defaultdict(list)
    for (sid, bid, day), z in sbd_bool.items():
        if "#L" not in bid:
            theory_sd[(sid, day)].append(z)
    for (sid, day), zs in theory_sd.items():
        if len(zs) >= 2:
            model.Add(sum(zs) <= 1)

    # soft: room-used indicators
    room_used = {}
    for room, vs in room_used_vars.items():
        y = model.NewBoolVar(f"room_used|{room}")
        model.Add(sum(vs) >= 1).OnlyEnforceIf(y)
        model.Add(sum(vs) == 0).OnlyEnforceIf(y.Not())
        room_used[room] = y

    # soft: instructor-day indicators (heavier weight for part-time)
    instr_day = {}
    for (iid, day), vs in instr_day_vars.items():
        d = model.NewBoolVar(f"iday|{iid}|{day}")
        model.Add(sum(vs) >= 1).OnlyEnforceIf(d)
        model.Add(sum(vs) == 0).OnlyEnforceIf(d.Not())
        instr_day[(iid, day)] = d

    # soft: per-(instructor, day) overload — hours beyond cfg.max_instr_daily_hours.
    # instr_day_load sums one var per occupied hour, so its sum == daily teaching hours.
    overload_terms = []
    if cfg.w_instr_daily_overload:
        cap = cfg.max_instr_daily_hours
        eligible = overload_eligible_ids(sections, cfg)
        for (iid, day), vs in instr_day_load.items():
            if iid not in eligible or len(vs) <= cap:
                continue
            over = model.NewIntVar(0, len(vs), f"iover|{iid}|{day}")
            model.Add(over >= sum(vs) - cap)
            overload_terms.append(over)

    # soft: per-instructor weekly distinct-day overload — days beyond
    # cfg.max_instr_weekly_days. instr_day[(iid, day)] is 1 iff the instructor teaches
    # that day, so their sum == distinct teaching days for the week.
    weekday_overload_terms = []
    if cfg.w_instr_weekly_overload:
        wcap = cfg.max_instr_weekly_days
        by_instr = defaultdict(list)
        for (iid, day), d in instr_day.items():
            by_instr[iid].append(d)
        for iid, ds in by_instr.items():
            if len(ds) <= wcap:
                continue
            over = model.NewIntVar(0, len(ds), f"iwover|{iid}")
            model.Add(over >= sum(ds) - wcap)
            weekday_overload_terms.append(over)

    obj = []
    obj += [cfg.w_evening * v for v in evening_vars]
    obj += [cfg.w_room_count * y for y in room_used.values()]
    for (iid, day), d in instr_day.items():
        ins = instructors.get(iid, default_instr)
        w = cfg.w_instr_days if ins.is_staff else cfg.w_parttime_days
        obj.append(w * d)
    obj += [cfg.w_cohort_gap * g for g in gap_terms]
    obj += order_terms
    obj += englab_terms
    obj += [cfg.w_nonadjacent * t for t in nonadj_terms]
    obj += [cfg.w_cohort_conflict * t for t in cohort_conflict_terms]
    obj += [cfg.w_instr_daily_overload * t for t in overload_terms]
    obj += [cfg.w_instr_weekly_overload * t for t in weekday_overload_terms]
    if obj:
        model.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.solve_time_limit_s
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    assignments: List[Assignment] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (bid, room, day, start), v in x.items():
            if solver.Value(v) == 1:
                length = next(c.length for c in cand_by_block[bid]
                              if c.room == room and c.day == day and c.start == start)
                sid = bid.split("#")[0]
                kind = "lab" if "#L" in bid else "theory"
                assignments.append(Assignment(bid, sid, kind, room, day, start, start + length))

    stats = {
        "status": int(status),
        "status_name": solver.StatusName(status),
        "objective": solver.ObjectiveValue() if obj and status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "wall_time": solver.WallTime(),
        "n_blocks": len(blocks),
        "n_vars": len(x),
        "unplaced": unplaced,
    }
    return assignments, stats
