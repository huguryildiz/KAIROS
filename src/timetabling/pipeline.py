from __future__ import annotations
from dataclasses import dataclass
from typing import Dict

from .config import Config
from .model_cpsat import build_and_solve, split_roomable
from .decompose import solve_decomposed
from .repair import solve_repair
from .validate import validate
from .export import build_schedule_dict

AUTO_REPAIR_THRESHOLD = 120


@dataclass
class PipelineResult:
    sections: list
    unschedulable: list
    assignments: list
    stats: dict
    violations: list
    schedule: dict


def run_pipeline(period: str, sections: list, rooms: Dict, instructors: Dict,
                 cfg: Config, solver: str = "auto") -> PipelineResult:
    room_list = list(rooms.values())
    schedulable, unschedulable = split_roomable(sections, room_list, cfg, instructors)

    chosen = solver
    if chosen == "auto":
        chosen = "repair" if len(schedulable) > AUTO_REPAIR_THRESHOLD else "cpsat"

    if chosen == "repair":
        assignments, stats = solve_repair(schedulable, rooms, instructors, cfg)
    elif chosen == "decompose":
        assignments, stats = solve_decomposed(schedulable, room_list, instructors, cfg)
    else:
        assignments, stats = build_and_solve(schedulable, room_list, instructors, cfg)

    viol = validate(assignments, schedulable, rooms, instructors, cfg)
    schedule = build_schedule_dict(
        period, assignments, schedulable, rooms, instructors,
        conflicts=[{"kind": v.kind, "detail": v.detail} for v in viol])
    return PipelineResult(schedulable, unschedulable, assignments, stats, viol, schedule)
