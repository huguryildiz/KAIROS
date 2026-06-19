from __future__ import annotations
from typing import List, Dict, Tuple
from collections import defaultdict

from ortools.sat.python import cp_model

from .config import Config
from .model import Section, Block, Room, Instructor, Candidate, Assignment


def _blackout_hours(instructors, cfg: Config):
    closed = set(cfg.friday_blackout)
    if any(ins.is_staff for ins in instructors):
        closed |= set(cfg.seminar_blackout)
    return closed


def feasible_rooms_for(block: Block, section: Section, rooms: List[Room],
                       cfg: Config) -> List[Room]:
    fr = [
        r for r in rooms
        if r.is_physical and r.cap >= section.students and (r.is_lab if block.needs_lab else True)
    ]
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
    cands: List[Candidate] = []
    for r in feasible_rooms:
        for d in cfg.days():
            for h in range(start_lo, end_cap - block.length + 1):
                span = range(h, h + block.length)
                if any((d, hh) in closed for hh in span):
                    continue
                cands.append(Candidate(block.block_id, r.room, d, h, block.length))
    return cands


def build_and_solve(sections: List[Section], rooms: List[Room],
                    instructors: Dict[str, Instructor], cfg: Config
                    ) -> Tuple[List[Assignment], Dict]:
    model = cp_model.CpModel()
    blocks = [(b, s) for s in sections for b in s.blocks]

    x: Dict[tuple, cp_model.IntVar] = {}
    cand_by_block: Dict[str, List[Candidate]] = {}
    unplaced: List[str] = []
    default_instr = Instructor("", "", False, "")
    order_terms = []

    room_occ = defaultdict(list)          # (room, day, hour) -> vars
    instr_occ = defaultdict(list)         # (instr_id, day, hour) -> vars
    cohort_course_occ = defaultdict(list)  # (cohort, course, day, hour) -> vars
    cohort_hour_occ = defaultdict(list)   # (cohort, day, hour) -> vars (compact cohorts only)
    section_occ = defaultdict(list)       # (section_id, day, hour) -> vars
    room_used_vars = defaultdict(list)            # room -> vars
    instr_day_vars = defaultdict(list)            # (instr_id, day) -> vars
    evening_vars = []

    compact_years = {str(y) for y in cfg.compact_cohort_years}

    for b, s in blocks:
        ins_list = _instructors_of(s, instructors)
        cands = gen_candidates(b, s, ins_list, rooms, cfg)
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
            for hh in range(c.start, c.start + c.length):
                room_occ[(c.room, c.day, hh)].append(v)
                for iid in s.instructor_ids:
                    instr_occ[(iid, c.day, hh)].append(v)
                cohort_course_occ[(s.cohort_key, s.code, c.day, hh)].append(v)
                if s.cohort_key.rsplit("-", 1)[-1] in compact_years:
                    cohort_hour_occ[(s.cohort_key, c.day, hh)].append(v)
                section_occ[(s.section_id, c.day, hh)].append(v)
                if hh >= cfg.evening_from_hour:
                    evening_vars.append(v)
            room_used_vars[c.room].append(v)
            for iid in s.instructor_ids:
                instr_day_vars[(iid, c.day)].append(v)
        model.AddExactlyOne(bvars)   # H1

    # H2/H3/H_self: at most one occupant per resource-slot
    for occ in (room_occ, instr_occ, section_occ):
        for key, vs in occ.items():
            if len(vs) > 1:
                model.Add(sum(vs) <= 1)

    # H4 (course-level): at most one distinct course code per (cohort, day, hour)
    course_busy = {}
    slot_courses = defaultdict(list)  # (cohort, day, hour) -> [busy vars]
    for (cohort, course, day, hh), vs in cohort_course_occ.items():
        b = model.NewBoolVar(f"busy|{cohort}|{course}|{day}|{hh}")
        model.AddMaxEquality(b, vs)               # b = OR(vs)
        course_busy[(cohort, course, day, hh)] = b
        slot_courses[(cohort, day, hh)].append(b)
    for (cohort, day, hh), busies in slot_courses.items():
        if len(busies) > 1:                        # >=2 distinct courses can contend
            model.Add(sum(busies) <= 1)

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

    obj = []
    obj += [cfg.w_evening * v for v in evening_vars]
    obj += [cfg.w_room_count * y for y in room_used.values()]
    for (iid, day), d in instr_day.items():
        ins = instructors.get(iid, default_instr)
        w = cfg.w_instr_days if ins.is_staff else cfg.w_parttime_days
        obj.append(w * d)
    obj += [cfg.w_cohort_gap * g for g in gap_terms]
    obj += order_terms
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
