from __future__ import annotations
import argparse
import json
import os

from .config import Config
from .io_csv import load_classrooms, load_lecturers
from .join import build_section_frame
from .derive import build_sections
from .clean import build_rooms, build_instructors
from .route import mark_virtual
from .model_cpsat import build_and_solve as _cpsat_solve, split_roomable
from .decompose import solve_decomposed
from .repair import solve_repair
from .validate import validate
from .report import data_quality_report, parse_existing, mode_b_benchmark
from .export import build_schedule_dict, write_schedule_json, write_csv


def _apply_scope(frame, scope: str):
    if scope == "all" or not scope:
        return frame
    key, _, val = scope.partition("=")
    if key == "faculty":
        return frame[frame["faculty"].str.contains(val, case=False, na=False)]
    if key == "dept":
        return frame[frame["dept_code"].str.strip() == val]
    return frame


def main():
    ap = argparse.ArgumentParser(prog="timetabling")
    ap.add_argument("--period", default="001", choices=["001", "002"])
    ap.add_argument("--scope", default="all", help='all | faculty=<substr> | dept=<CODE>')
    ap.add_argument("--mode", default="A,B")
    ap.add_argument("--out", default="out")
    ap.add_argument("--time-limit", type=float, default=60.0)
    ap.add_argument("--max-rooms-per-block", type=int, default=None,
                    help="cap candidate rooms per block (default from Config=12; lower = smaller/faster model)")
    ap.add_argument("--decompose", action="store_true",
                    help="solve faculty-by-faculty sharing the room pool (for full --scope all)")
    ap.add_argument("--repair", action="store_true",
                    help="warm-started small-neighborhood repair solver (full --scope all)")
    args = ap.parse_args()

    cfg = Config(solve_time_limit_s=args.time_limit)
    if args.max_rooms_per_block is not None:
        cfg = Config(solve_time_limit_s=args.time_limit,
                     max_rooms_per_block=args.max_rooms_per_block)
    os.makedirs(args.out, exist_ok=True)

    rooms = build_rooms(load_classrooms(), cfg)
    instructors = build_instructors(load_lecturers())
    frame = _apply_scope(build_section_frame(args.period, cfg.include_plan_only), args.scope)
    all_sections, derive_rep = build_sections(frame, cfg)
    mark_virtual(all_sections, rooms, cfg)
    room_list = list(rooms.values())

    sections, unschedulable = split_roomable(all_sections, room_list, cfg, instructors)

    dq = data_quality_report(args.period, frame, rooms, derive_rep, cfg)
    dq["unschedulable"] = unschedulable
    with open(os.path.join(args.out, f"data_quality_{args.period}.json"), "w", encoding="utf-8") as f:
        json.dump(dq, f, ensure_ascii=False, indent=2)
    print(f"[data-quality] sections={dq['n_grades_sections']} schedulable={len(sections)} "
          f"unschedulable={len(unschedulable)} labs={dq['n_lab_rooms']} "
          f"dirty_schedule={dq['dirty_plan_schedule']} empty_room={dq['empty_plan_room']} "
          f"excluded(grad/intern)={derive_rep['excluded']}")
    if unschedulable:
        print("  unschedulable (excluded, oversize or block>window): "
              + ", ".join(f"{o['section_id']}({o['students']})" for o in unschedulable[:8])
              + (" ..." if len(unschedulable) > 8 else ""))

    modes = set(m.strip().upper() for m in args.mode.split(","))
    assignments, stats = [], {}
    if "A" in modes:
        if args.repair:
            assignments, stats = solve_repair(sections, rooms, instructors, cfg)
        elif args.decompose:
            assignments, stats = solve_decomposed(sections, room_list, instructors, cfg)
        else:
            assignments, stats = _cpsat_solve(sections, room_list, instructors, cfg)
        viol = validate(assignments, sections, rooms, instructors, cfg)
        if "placed" in stats:
            print(f"[mode-A] repair placed={stats['placed']}/{stats['total']} "
                  f"({stats['placed']/stats['total']:.1%}) unplaced={len(stats['unplaced'])} "
                  f"wall={stats['wall_time']:.1f}s sweeps={stats.get('sweeps', '?')} "
                  f"violations={len(viol)}")
        elif "status_name" in stats:
            print(f"[mode-A] status={stats['status_name']} blocks={stats['n_blocks']} "
                  f"vars={stats['n_vars']} unplaced={len(stats['unplaced'])} "
                  f"wall={stats['wall_time']:.1f}s violations={len(viol)}")
        else:
            print(f"[mode-A] decomposed groups={stats['n_groups']} "
                  f"assignments={stats['n_assignments']} violations={len(viol)}")
        payload = build_schedule_dict(
            args.period, assignments, sections, rooms, instructors,
            conflicts=[{"kind": v.kind, "detail": v.detail} for v in viol])
        write_schedule_json(os.path.join(args.out, f"schedule_{args.period}.json"), payload)
        write_csv(os.path.join(args.out, f"schedule_{args.period}.csv"), payload)
        if viol:
            print("  !! HARD violations:", [f"{v.kind}:{v.detail}" for v in viol[:10]])
        else:
            print("  OK: 0 hard-constraint violations (feasible)")

    if "B" in modes:
        existing = parse_existing(frame, sections)
        bench = mode_b_benchmark(args.period, assignments, existing, sections, rooms, instructors, cfg)
        with open(os.path.join(args.out, f"mode_b_{args.period}.json"), "w", encoding="utf-8") as f:
            json.dump(bench, f, ensure_ascii=False, indent=2)
        print(f"[mode-B] existing: conflicts={bench['existing']['conflicts']} "
              f"rooms_used={bench['existing']['rooms_used']} "
              f"evening_ratio={bench['existing']['evening_ratio']}")
        print(f"[mode-B] mode_a:   conflicts={bench['mode_a']['conflicts']} "
              f"rooms_used={bench['mode_a']['rooms_used']} "
              f"evening_ratio={bench['mode_a']['evening_ratio']}")


if __name__ == "__main__":
    main()
