from __future__ import annotations
from typing import List, Dict, Tuple
from collections import defaultdict
import os

from ortools.sat.python import cp_model

from .config import Config
from .model import Section, Block, Room, Instructor, Candidate, Assignment


def _blackout_hours(instructors, cfg: Config):
    return cfg.closed_hours(any(ins.is_staff for ins in instructors))


def feasible_rooms_for(block: Block, section: Section, rooms: List[Room],
                       cfg: Config) -> List[Room]:
    if section.is_virtual:
        return [r for r in rooms if r.is_virtual][:1]
    if block.needs_lab and section.lab_room:
        return [r for r in rooms if r.room == section.lab_room]   # pinned lab room
    has_lab_blocks = any(b.needs_lab for b in section.blocks)
    room_type_applies = section.requires_lab_room and (block.needs_lab or not has_lab_blocks)
    if room_type_applies:        # explicit Room Type demand
        rt = section.required_room_type
        if rt in ("pc", "studio", "lab"):
            # specific category -> only rooms of exactly that type (UI rooms carry it)
            fr = [r for r in rooms if r.is_physical and r.type == rt
                  and r.cap >= section.students]
        else:
            # generic lab-family demand -> is_lab keeps the CLI path working too
            fr = [r for r in rooms if r.is_physical and r.is_lab and r.cap >= section.students]
    elif block.needs_lab:
        fr = [r for r in rooms if r.is_physical and r.is_lab and r.cap >= section.students]
    else:
        # Plain theory/practice belongs in ordinary classrooms. Lab-family rooms
        # are reserved for lab blocks or explicit Room Type demand.
        fr = [r for r in rooms if r.is_physical and not r.is_lab and r.cap >= section.students]
    # Dept ownership: if a room declares owner dept(s), restrict to sections
    # whose department matches one of them. Empty dept = open to all.
    if fr and section.department:
        fr = [r for r in fr if not r.dept or section.department in {
            d.strip() for d in r.dept.split(";") if d.strip()
        }]
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
            excluded.append({"section_id": s.section_id, "students": s.students,
                             "n_blocks": len(s.blocks), "issues": issues})
        else:
            roomable.append(s)
    return roomable, excluded


def gen_candidates(block: Block, section: Section, instructors: List[Instructor],
                   rooms: List[Room], cfg: Config) -> List[Candidate]:
    end_cap = cfg.undergrad_end if section.level <= 4 else cfg.grad_end
    start_lo = cfg.horizon_start if section.level <= 4 else cfg.grad_start_for(section.dept_code)
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
                cands.append(Candidate(block.block_id, r.room, d, h, block.length, r.cap))
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
    room_util_terms = []
    avoid_terms = []
    prefer_miss_terms = []
    code_day_hour_vars = defaultdict(list)  # (code, day, hour) -> vars (for avoid_pairs)
    sbd = defaultdict(list)  # (section_id, block_id, day) -> vars (multi-block sections)

    room_occ = defaultdict(list)          # (room, day, hour) -> vars
    instr_occ = defaultdict(list)         # (instr_id, day, hour) -> vars
    cohort_course_occ = defaultdict(list)  # (cohort, course, day, hour) -> vars
    cohort_hour_occ = defaultdict(list)   # (cohort, day, hour) -> vars (compact cohorts only)
    section_occ = defaultdict(list)       # (section_id, day, hour) -> vars
    instr_day_vars = defaultdict(list)            # (instr_id, day) -> vars
    section_day_vars = defaultdict(list)           # (section_id, day) -> vars

    compact_years = {str(y) for y in cfg.compact_cohort_years}
    virtual_names = {r.room for r in rooms if r.is_virtual}
    _avoid_pair_codes = {code for pair in cfg.avoid_pairs for code in pair}

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
            if (cfg.eng_department_match in s.department and b.needs_lab
                    and c.day not in cfg.eng_lab_days):
                englab_terms.append(cfg.w_englab * v)
            if cfg.w_room_util and c.cap > 0 and not s.is_virtual:
                waste = c.cap - s.students
                if waste > 0:
                    room_util_terms.append(cfg.w_room_util * (100 * waste // c.cap) * v)
            if s.code in _avoid_pair_codes:
                for hh in range(c.start, c.start + c.length):
                    code_day_hour_vars[(s.code, c.day, hh)].append(v)
            for iid in s.instructor_ids:
                if cfg.instr_avoid:
                    for hh in range(c.start, c.start + c.length):
                        if (iid, c.day, hh) in cfg.instr_avoid:
                            avoid_terms.append(int(round(cfg.w_instr_avoid)) * v)
                if iid in cfg.instr_prefer_ids:
                    if not any((iid, c.day, hh) in cfg.instr_preferred
                               for hh in range(c.start, c.start + c.length)):
                        prefer_miss_terms.append(int(round(cfg.w_instr_prefer)) * v)
            if len(s.blocks) >= 2:
                sbd[(s.section_id, b.block_id, c.day)].append(v)
            for hh in range(c.start, c.start + c.length):
                if c.room not in virtual_names:
                    room_occ[(c.room, c.day, hh)].append(v)
                for iid in s.instructor_ids:
                    instr_occ[(iid, c.day, hh)].append(v)
                cohort_course_occ[(s.cohort_key, s.code, c.day, hh)].append(v)
                if s.cohort_key.rsplit("-", 1)[-1] in compact_years:
                    cohort_hour_occ[(s.cohort_key, c.day, hh)].append(v)
                section_occ[(s.section_id, c.day, hh)].append(v)
            for iid in s.instructor_ids:
                instr_day_vars[(iid, c.day)].append(v)
            if s.min_working_days > 0:
                section_day_vars[(s.section_id, c.day)].append(v)
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

    # soft: instructor-day indicators (heavier weight for part-time)
    instr_day = {}
    for (iid, day), vs in instr_day_vars.items():
        d = model.NewBoolVar(f"iday|{iid}|{day}")
        model.Add(sum(vs) >= 1).OnlyEnforceIf(d)
        model.Add(sum(vs) == 0).OnlyEnforceIf(d.Not())
        instr_day[(iid, day)] = d

    obj = []
    for (iid, day), d in instr_day.items():
        ins = instructors.get(iid, default_instr)
        w = cfg.w_instr_days if ins.is_staff else cfg.w_parttime_days
        obj.append(w * d)
    section_day = {}
    for (sid, day), vs in section_day_vars.items():
        d = model.NewBoolVar(f"sday|{sid}|{day}")
        model.AddMaxEquality(d, vs)
        section_day[(sid, day)] = d
    for s in sections:
        if s.min_working_days <= 0:
            continue
        days = [section_day[(s.section_id, day)]
                for day in cfg.days() if (s.section_id, day) in section_day]
        if not days:
            continue
        missing = model.NewIntVar(0, s.min_working_days, f"minwd|{s.section_id}")
        model.Add(missing >= s.min_working_days - sum(days))
        obj.append(cfg.w_min_working_days * missing)
    obj += [cfg.w_cohort_gap * g for g in gap_terms]
    obj += order_terms
    obj += englab_terms
    obj += [cfg.w_nonadjacent * t for t in nonadj_terms]
    obj += [cfg.w_cohort_conflict * t for t in cohort_conflict_terms]
    obj += room_util_terms
    obj += avoid_terms
    obj += prefer_miss_terms
    if cfg.avoid_pairs and cfg.w_avoid_pairs:
        code_busy = {}
        for (code, day, hh), vs in code_day_hour_vars.items():
            b_var = model.NewBoolVar(f"cbusy|{code}|{day}|{hh}")
            model.AddMaxEquality(b_var, vs)
            code_busy[(code, day, hh)] = b_var
        for pair in cfg.avoid_pairs:
            cl = list(pair)
            if len(cl) != 2:
                continue
            ca, cb = cl[0], cl[1]
            for (code, day, hh) in list(code_day_hour_vars):
                if code != ca:
                    continue
                ba = code_busy.get((ca, day, hh))
                bb = code_busy.get((cb, day, hh))
                if ba is None or bb is None:
                    continue
                overlap = model.NewBoolVar(f"avp|{ca}|{cb}|{day}|{hh}")
                model.Add(overlap >= ba + bb - 1)
                obj.append(int(round(cfg.w_avoid_pairs)) * overlap)
    if cfg.w_building_change:
        from .config import building_of as _bldg_of
        w_bc = int(round(cfg.w_building_change)) or 1
        ib_cands = defaultdict(list)   # (iid, day, hh, bldg) -> [vars]
        for b_obj, s in blocks:
            for c in cand_by_block.get(b_obj.block_id, []):
                v = x.get((b_obj.block_id, c.room, c.day, c.start))
                if v is None:
                    continue
                bldg = _bldg_of(c.room)
                if bldg is None:
                    continue
                for iid in s.instructor_ids:
                    for hh in range(c.start, c.start + c.length):
                        ib_cands[(iid, c.day, hh, bldg)].append(v)
        iid_day_hh_bldgs = defaultdict(list)
        for (iid, day, hh, bldg), vs in ib_cands.items():
            iid_day_hh_bldgs[(iid, day, hh)].append((bldg, vs))
        t_idx = 0
        for (iid, day, hh), bldg_vs_h in iid_day_hh_bldgs.items():
            bldg_vs_h1 = iid_day_hh_bldgs.get((iid, day, hh + 1), [])
            if not bldg_vs_h1:
                continue
            for b1, vs1 in bldg_vs_h:
                for b2, vs2 in bldg_vs_h1:
                    if b1 == b2:
                        continue
                    for v1 in vs1:
                        for v2 in vs2:
                            t = model.NewBoolVar(f"bc_{t_idx}")
                            t_idx += 1
                            model.Add(t >= v1 + v2 - 1)
                            obj.append(w_bc * t)
    if obj:
        model.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.solve_time_limit_s
    solver.parameters.num_search_workers = int(os.environ.get("CPSAT_MAX_WORKERS", 8))
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
