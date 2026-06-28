from __future__ import annotations
import argparse
import json
import os

from .config import Config
from .io_csv import load_classrooms, load_lecturers
from .join import build_section_frame
from .derive import build_sections
from .clean import build_rooms, build_instructors
from .route import mark_virtual, mark_lab_rooms
from .model_cpsat import split_roomable
from .pipeline import run_pipeline
from .report import data_quality_report, parse_existing, mode_b_benchmark
from .export import write_schedule_json, write_csv
from .csv_import import read_raw, parse_courselist, ok_rows, parse_classrooms, ok_rooms
from .ui_input import (build_sections_from_courselist,
                       build_instructors_from_courselist, build_rooms_from_ui)


def _apply_scope(frame, scope: str):
    if scope == "all" or not scope:
        return frame
    key, _, val = scope.partition("=")
    if key == "department":
        return frame[frame["department"].str.contains(val, case=False, na=False)]
    if key == "dept":
        return frame[frame["dept_code"].str.strip() == val]
    return frame


def main():
    ap = argparse.ArgumentParser(prog="timetabling")
    ap.add_argument("--courses", help="course-list CSV to solve")
    ap.add_argument("--rooms", help="classroom CSV; defaults to assets/sample_classrooms.csv with --courses")
    ap.add_argument("--period", default="001", choices=["001", "002"],
                    help="legacy data/ source term: 001 or 002")
    ap.add_argument("--scope", default="all", help='all | department=<substr> | dept=<CODE>')
    ap.add_argument("--mode", default="A,B")
    ap.add_argument("--out", default="out")
    ap.add_argument("--time-limit", type=float, default=60.0)
    ap.add_argument("--max-rooms-per-block", type=int, default=None,
                    help="cap candidate rooms per block (default from Config=12; lower = smaller/faster model)")
    ap.add_argument("--decompose", action="store_true",
                    help="solve department-by-department sharing the room pool (for full --scope all)")
    ap.add_argument("--repair", action="store_true",
                    help="warm-started small-neighborhood repair solver (full --scope all)")
    ap.add_argument("--no-soft-shaping", action="store_true",
                    help="disable cohort-conflict shaping in repair greedy "
                         "construction (for baseline A/B; default on)")
    args = ap.parse_args()

    cfg_kwargs = {"solve_time_limit_s": args.time_limit}
    if args.max_rooms_per_block is not None:
        cfg_kwargs["max_rooms_per_block"] = args.max_rooms_per_block
    if args.no_soft_shaping:
        cfg_kwargs["soft_shaping_in_repair"] = False
    cfg = Config(**cfg_kwargs)
    os.makedirs(args.out, exist_ok=True)

    uploaded = bool(args.courses)
    frame = None
    if uploaded:
        course_rows = ok_rows(parse_courselist(read_raw(args.courses)))
        if not course_rows:
            raise SystemExit("no valid course rows found")
        room_csv = args.rooms or os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
                                              "assets", "sample_classrooms.csv")
        room_rows = ok_rooms(parse_classrooms(read_raw(room_csv)))
        if not room_rows:
            raise SystemExit("no valid classroom rows found")
        all_sections, derive_rep = build_sections_from_courselist(course_rows, "uploaded", cfg)
        instructors = build_instructors_from_courselist(course_rows)
        rooms = build_rooms_from_ui(room_rows, cfg)
        mark_virtual(all_sections, rooms, cfg)
        room_list = list(rooms.values())
        sections, unschedulable = split_roomable(all_sections, room_list, cfg, instructors)
        dq = {"source": "uploaded_csv", "n_sections": len(all_sections),
              "n_rooms": len(rooms), "derive": derive_rep,
              "unschedulable": unschedulable}
        with open(os.path.join(args.out, "data_quality.json"), "w", encoding="utf-8") as f:
            json.dump(dq, f, ensure_ascii=False, indent=2)
        print(f"[data-quality] source=uploaded_csv sections={len(all_sections)} "
              f"schedulable={len(sections)} unschedulable={len(unschedulable)} "
              f"rooms={len(rooms)}")
    else:
        rooms = build_rooms(load_classrooms(), cfg)
        instructors = build_instructors(load_lecturers())
        frame = _apply_scope(build_section_frame(args.period, cfg.include_plan_only), args.scope)
        all_sections, derive_rep = build_sections(frame, cfg)
        mark_virtual(all_sections, rooms, cfg)
        mark_lab_rooms(all_sections, rooms, cfg)
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
        solver = "repair" if args.repair else "decompose" if args.decompose else "cpsat"
        period_label = "uploaded" if uploaded else args.period
        res = run_pipeline(period_label, all_sections, rooms, instructors, cfg, solver=solver)
        assignments, stats, viol = res.assignments, res.stats, res.violations
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
        schedule_stem = "schedule" if uploaded else f"schedule_{args.period}"
        write_schedule_json(os.path.join(args.out, f"{schedule_stem}.json"), res.schedule)
        write_csv(os.path.join(args.out, f"{schedule_stem}.csv"), res.schedule)
        if viol:
            print("  !! HARD violations:", [f"{v.kind}:{v.detail}" for v in viol[:10]])
        else:
            print("  OK: 0 hard-constraint violations (feasible)")

    if "B" in modes:
        if uploaded:
            print("[mode-B] skipped: existing-plan benchmark requires legacy source data")
            return
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
