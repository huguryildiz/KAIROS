from __future__ import annotations
import json
import sys
import time
from dataclasses import dataclass
from typing import Dict

from .config import Config
from .model_cpsat import build_and_solve, split_roomable
from .decompose import solve_decomposed
from .repair import solve_repair
from .validate import validate
from .export import build_schedule_dict

AUTO_REPAIR_THRESHOLD = 50


def _emit(event: str, **kw) -> None:
    print(json.dumps({"event": event, **kw}), flush=True)


@dataclass
class PipelineResult:
    sections: list
    unschedulable: list
    assignments: list
    stats: dict
    violations: list
    schedule: dict


def run_pipeline(period: str, sections: list, rooms: Dict, instructors: Dict,
                 cfg: Config, solver: str = "auto", progress_cb=None) -> PipelineResult:
    t_total = time.perf_counter()

    room_list = list(rooms.values())
    t0 = time.perf_counter()
    schedulable, unschedulable = split_roomable(sections, room_list, cfg, instructors)
    _emit("split_roomable_done",
          schedulable=len(schedulable), unschedulable=len(unschedulable),
          elapsed_s=round(time.perf_counter() - t0, 3))

    chosen = solver
    if chosen == "auto":
        chosen = "repair" if len(schedulable) > AUTO_REPAIR_THRESHOLD else "cpsat"

    t0 = time.perf_counter()
    if chosen == "repair":
        assignments, stats = solve_repair(schedulable, rooms, instructors, cfg,
                                          progress_cb=progress_cb)
    elif chosen == "decompose":
        assignments, stats = solve_decomposed(schedulable, room_list, instructors, cfg)
    else:
        assignments, stats = build_and_solve(schedulable, room_list, instructors, cfg)
    _emit("solve_done", solver=chosen, assignments=len(assignments),
          elapsed_s=round(time.perf_counter() - t0, 3))

    if progress_cb:
        progress_cb(("validate", None))
    t0 = time.perf_counter()
    viol = validate(assignments, schedulable, rooms, instructors, cfg)
    _emit("validate_done", violations=len(viol),
          elapsed_s=round(time.perf_counter() - t0, 3))

    schedule = build_schedule_dict(
        period, assignments, schedulable, rooms, instructors,
        conflicts=[{"kind": v.kind, "detail": v.detail} for v in viol])

    total_elapsed_s = round(time.perf_counter() - t_total, 3)
    stats["total_elapsed_s"] = total_elapsed_s
    _emit("pipeline_done", period=period, solver=chosen,
          sections=len(schedulable), violations=len(viol),
          total_elapsed_s=total_elapsed_s)

    return PipelineResult(schedulable, unschedulable, assignments, stats, viol, schedule)
