from __future__ import annotations
from typing import List, Dict
from collections import defaultdict

from .config import Config
from .model import Assignment, Section, Room, Instructor, Violation


def validate(assignments: List[Assignment], sections: List[Section],
             rooms: Dict[str, Room], instructors: Dict[str, Instructor],
             cfg: Config, check_placement: bool = True) -> List[Violation]:
    """Re-derive every hard-constraint violation independently of the solver.
    Empty list = feasible. Set check_placement=False for Mode-B benchmarking of
    an existing schedule whose session structure differs from our derived blocks."""
    viol: List[Violation] = []
    sec_by_id = {s.section_id: s for s in sections}

    if check_placement:
        placed = defaultdict(int)
        for a in assignments:
            placed[a.block_id] += 1
        for s in sections:
            for b in s.blocks:
                if placed.get(b.block_id, 0) != 1:
                    viol.append(Violation("placement",
                                f"{b.block_id} placed {placed.get(b.block_id, 0)} times (expected 1)"))
    block_by_id = {b.block_id: b for s in sections for b in s.blocks}
    has_lab_blocks = {s.section_id: any(b.needs_lab for b in s.blocks) for s in sections}

    room_occ = defaultdict(list)
    instr_occ = defaultdict(list)
    section_occ = defaultdict(list)

    for a in assignments:
        s = sec_by_id.get(a.section_id)
        if s is None:
            continue
        room = rooms.get(a.room)
        is_virt = room is not None and room.is_virtual
        if not is_virt and room is not None and room.cap < s.students:
            viol.append(Violation("capacity",
                        f"{a.block_id} in {a.room} (cap {room.cap}) < {s.students} students"))
        if a.kind == "lab" and not is_virt and s.lab_room and a.room != s.lab_room:
            viol.append(Violation("lab_room",
                        f"{a.block_id} lab not in pinned {s.lab_room} (got {a.room})"))
        block = block_by_id.get(a.block_id)
        is_lab_block = bool(block.needs_lab) if block is not None else (a.kind == "lab")
        mixed_lab_section = has_lab_blocks.get(s.section_id, False)
        room_type_applies = s.requires_lab_room and (is_lab_block or not mixed_lab_section)
        if room_type_applies and not is_virt and room is not None:
            rt = s.required_room_type
            ok = (room.type == rt) if rt in ("pc", "studio", "lab") else room.is_lab
            if not ok:
                viol.append(Violation("room_type",
                            f"{a.block_id} in {a.room} ({room.type}) but section "
                            f"requires {rt or 'a lab'} room"))
        elif is_lab_block and not is_virt and room is not None and not room.is_lab:
            viol.append(Violation("room_type",
                        f"{a.block_id} lab in ordinary room {a.room} ({room.type})"))
        elif not is_lab_block and not is_virt and room is not None and room.is_lab:
            viol.append(Violation("room_type",
                        f"{a.block_id} theory/practice in lab-family room {a.room} ({room.type})"))
        if s.fixed_day and s.blocks and a.block_id == s.blocks[0].block_id \
                and (a.day != s.fixed_day or a.start != s.fixed_start):
            viol.append(Violation("fixed",
                        f"{a.block_id} not at fixed {s.fixed_day} {s.fixed_start}:00 "
                        f"(got {a.day} {a.start})"))
        end_cap = cfg.undergrad_end if s.level <= 4 else cfg.grad_end
        if a.end > end_cap:
            viol.append(Violation("window",
                        f"{a.block_id} ends {a.end} > allowed {end_cap} (level {s.level})"))
        ins_list = [instructors.get(i, Instructor("", "", False, "")) for i in s.instructor_ids]
        closed = cfg.closed_hours(any(ins.is_staff for ins in ins_list))
        for hh in range(a.start, a.end):
            if (a.day, hh) in closed:
                viol.append(Violation("blackout", f"{a.block_id} covers blackout {a.day} {hh}:00"))
                break
        if cfg.instr_unavailable:
            hit = next(((iid, hh) for iid in s.instructor_ids
                        for hh in range(a.start, a.end)
                        if (iid, a.day, hh) in cfg.instr_unavailable), None)
            if hit:
                viol.append(Violation("instructor_unavailable",
                            f"{a.block_id}: {hit[0]} unavailable {a.day} {hit[1]}:00"))
        for hh in range(a.start, a.end):
            if not is_virt:
                room_occ[(a.room, a.day, hh)].append(a.block_id)
            for iid in s.instructor_ids:
                instr_occ[(iid, a.day, hh)].append(a.block_id)
            section_occ[(a.section_id, a.day, hh)].append(a.block_id)

    for (room, day, hh), bids in room_occ.items():
        if len(bids) > 1:
            viol.append(Violation("room", f"room {room} double-booked {day} {hh}:00 by {bids}"))
    for (iid, day, hh), bids in instr_occ.items():
        if len(set(b.split('#')[0] for b in bids)) > 1:
            viol.append(Violation("instructor", f"instructor {iid} double-booked {day} {hh}:00 by {bids}"))
    for (sid, day, hh), bids in section_occ.items():
        if len(set(bids)) > 1:
            viol.append(Violation("self", f"section {sid} self-overlap {day} {hh}:00 by {bids}"))

    return viol
