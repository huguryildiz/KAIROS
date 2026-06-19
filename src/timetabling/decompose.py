from __future__ import annotations
from typing import List, Dict, Tuple, Callable
from collections import defaultdict

from .config import Config
from .model import Section, Room, Instructor, Assignment
from .model_cpsat import build_and_solve


def solve_decomposed(sections: List[Section], rooms: List[Room],
                     instructors: Dict[str, Instructor], cfg: Config,
                     group_key: Callable[[Section], str] = lambda s: s.faculty
                     ) -> Tuple[List[Assignment], Dict]:
    """Solve sections group-by-group (default: by faculty), largest group first,
    reserving each group's used (room, day, hour) slots for later groups so the
    shared room pool stays conflict-free across the partition."""
    groups: Dict[str, List[Section]] = defaultdict(list)
    for s in sections:
        groups[group_key(s)].append(s)
    order = sorted(groups, key=lambda g: -len(groups[g]))

    reserved = set()
    all_assigns: List[Assignment] = []
    per_group = []
    for g in order:
        a, st = build_and_solve(groups[g], rooms, instructors, cfg, reserved=reserved)
        for x in a:
            for hh in range(x.start, x.end):
                reserved.add((x.room, x.day, hh))
        all_assigns.extend(a)
        # st always carries status_name/unplaced/wall_time: each group is solved by
        # build_and_solve (never the decomposed path), so these keys are guaranteed.
        per_group.append({"group": g, "n_sections": len(groups[g]),
                          "status": st["status_name"], "unplaced": len(st["unplaced"]),
                          "wall_time": st["wall_time"]})
    stats = {"groups": per_group, "n_groups": len(order),
             "n_assignments": len(all_assigns)}
    return all_assigns, stats
