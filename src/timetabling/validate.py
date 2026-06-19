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

    closed_all = set(cfg.friday_blackout)
    room_occ = defaultdict(list)
    instr_occ = defaultdict(list)
    section_occ = defaultdict(list)

    for a in assignments:
        s = sec_by_id.get(a.section_id)
        if s is None:
            continue
        room = rooms.get(a.room)
        if room is not None and room.cap < s.students:
            viol.append(Violation("capacity",
                        f"{a.block_id} in {a.room} (cap {room.cap}) < {s.students} students"))
        if a.kind == "lab" and (room is None or not room.is_lab):
            viol.append(Violation("lab", f"{a.block_id} lab block in non-lab room {a.room}"))
        end_cap = cfg.undergrad_end if s.level <= 4 else cfg.grad_end
        if a.end > end_cap:
            viol.append(Violation("window",
                        f"{a.block_id} ends {a.end} > allowed {end_cap} (level {s.level})"))
        ins_list = [instructors.get(i, Instructor("", "", False, "")) for i in s.instructor_ids]
        closed = set(closed_all)
        if any(ins.is_staff for ins in ins_list):
            closed |= set(cfg.seminar_blackout)
        for hh in range(a.start, a.end):
            if (a.day, hh) in closed:
                viol.append(Violation("blackout", f"{a.block_id} covers blackout {a.day} {hh}:00"))
                break
        for hh in range(a.start, a.end):
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
