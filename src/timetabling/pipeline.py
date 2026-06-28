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
    parts = " ".join(f"{k}={v}" for k, v in kw.items())
    msg = f"[kairos:{event}] {parts}"
    print(json.dumps({"message": msg, "severity": "INFO", "event": event,
                      **{k: str(v) for k, v in kw.items()}}), flush=True)


@dataclass
class PipelineResult:
    sections: list
    unschedulable: list
    assignments: list
    stats: dict
    violations: list
    schedule: dict


def _unmet_min_working_days(assignments: list, sections: list) -> list:
    days_by_section = {}
    for a in assignments:
        days_by_section.setdefault(a.section_id, set()).add(a.day)
    out = []
    for s in sections:
        target = int(getattr(s, "min_working_days", 0) or 0)
        if target <= 0:
            continue
        actual = len(days_by_section.get(s.section_id, ()))
        missing = max(0, target - actual)
        if missing:
            out.append({
                "kind": "min_working_days",
                "section_id": s.section_id,
                "target_days": target,
                "actual_days": actual,
                "missing_days": missing,
            })
    return out


def run_pipeline(period: str, sections: list, rooms: Dict, instructors: Dict,
                 cfg: Config, solver: str = "auto", progress_cb=None) -> PipelineResult:
    t_total = time.perf_counter()
    _emit("pipeline_start", sections=len(sections), rooms=len(rooms), solver_hint=solver)

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
        unmet_soft=_unmet_min_working_days(assignments, schedulable),
        conflicts=[{"kind": v.kind, "detail": v.detail} for v in viol])

    total_elapsed_s = round(time.perf_counter() - t_total, 3)
    stats["total_elapsed_s"] = total_elapsed_s
    # Cloud Run europe-west1: 4 vCPU × $0.000024/s + 8 GiB × $0.0000025/s
    cost_usd = round(total_elapsed_s * (4 * 0.000024 + 8 * 0.0000025), 4)
    _emit("pipeline_done", solver=chosen,
          sections=len(schedulable), violations=len(viol),
          total_elapsed_s=total_elapsed_s, cost_usd=cost_usd)

    return PipelineResult(schedulable, unschedulable, assignments, stats, viol, schedule)
