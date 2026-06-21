"""Headless benchmark for the KAIROS solver.

Mirrors the UI solve path (views/solve.py) exactly — importer -> sections/
instructors/rooms -> mark_virtual -> run_pipeline(solver="auto") — so the
numbers match what a user gets in the app, but without Streamlit, so it can run
as a Cloud Run Job / cron / CI and dump a metrics JSON.

The full-period path auto-selects the `repair` solver (a greedy + small-
neighbourhood heuristic), so there is NO MIP optimality gap — the reportable
metrics are placement rate, wall time, hard violations (target 0), and counts.

Usage (PYTHONPATH=src required, like every direct module run):

    PYTHONPATH=src python3 bench/benchmark.py \
        --case data/sample_courses_2025_001.csv:001 \
        --case data/sample_courses_2025_002.csv:002 \
        --runs 3 --time-limit 3000 --out out/benchmark.json
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import statistics
from collections import Counter
from pathlib import Path
from time import perf_counter

from timetabling.csv_import import read_raw, parse_courselist, ok_rows
from timetabling.settings import build_config
from timetabling.ui_input import (
    build_sections_from_courselist,
    build_instructors_from_courselist,
    build_rooms_from_ui,
)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
from timetabling.defaults import DEFAULT_CLASSROOMS


def load_courses(csv_path: str) -> list:
    """Parse a CSV through the UI importer into an ok-rows course list."""
    return ok_rows(parse_courselist(read_raw(csv_path)))


def load_classrooms(path: str) -> list:
    """Read a real classroom inventory (ROOM,ROOM_CAP) into UI-shaped rows.
    Room type is left for build_rooms_from_ui to derive from the name token."""
    import csv
    rows = []
    with open(path, newline="", encoding="utf-8-sig") as fh:
        for r in csv.DictReader(fh):
            name = (r.get("ROOM") or r.get("Room") or "").strip()
            if not name:
                continue
            cap = r.get("ROOM_CAP") or r.get("Capacity") or r.get("Cap") or "0"
            rows.append({"Room": name, "Capacity": cap})
    return rows


def solve_courses(courses: list, period: str, time_limit: float,
                  label: str = "", classroom_rows: list | None = None) -> dict:
    """One solve of a pre-built course list. Returns a flat metrics dict (no PII).

    Mirrors the UI path: build sections/instructors/rooms -> mark_virtual ->
    run_pipeline(solver="auto"). Used for whole-file runs, the nested-subset
    scaling study, and the synthetic large-scale study (which passes a scaled
    classroom pool so tightness stays constant as size grows)."""
    cfg = build_config({}, {}, time_limit)
    if classroom_rows is None:
        classroom_rows = [dict(r) for r in DEFAULT_CLASSROOMS]

    secs, _ = build_sections_from_courselist(courses, period, cfg)
    instr = build_instructors_from_courselist(courses)
    rooms = build_rooms_from_ui(classroom_rows, cfg)
    mark_virtual(secs, rooms, cfg)

    t0 = perf_counter()
    res = run_pipeline(period, secs, rooms, instr, cfg, solver="auto")
    wall = perf_counter() - t0

    stats = res.stats
    placed = stats.get("placed")
    total = stats.get("total") or stats.get("n_blocks")
    viol_by_kind = Counter(v.kind for v in res.violations)
    # "placement" = unplaced-block tail (a heuristic leaves a tail); everything
    # else is a genuine hard conflict (room/instructor/capacity/lab/window/...).
    genuine = sum(n for k, n in viol_by_kind.items() if k != "placement")

    return {
        "label": label,
        "period": period,
        "solver": stats.get("status_name"),               # "REPAIR" | "OPTIMAL" | ...
        "n_courses": len(courses),
        "n_sections": len(secs),
        "schedulable": len(res.sections),
        "unschedulable": len(res.unschedulable),
        "n_rooms": len(rooms),
        "n_blocks": total,
        "blocks_placed": placed,
        "placement_rate": round(placed / total, 4) if placed and total else None,
        "hard_violations": len(res.violations),
        "genuine_conflicts": genuine,
        "violations_by_kind": dict(viol_by_kind),
        "sweeps": stats.get("sweeps"),
        "polish_rounds": stats.get("polish_rounds"),
        # wall_time as the solver reports it; pipeline_wall is end-to-end (incl. derive/validate)
        "solver_wall_s": stats.get("wall_time"),
        "pipeline_wall_s": round(wall, 1),
    }


def summarize(runs: list[dict]) -> dict:
    """Median/min/max over repeated runs of one cell (same subset, timing varies)."""
    walls = [r["pipeline_wall_s"] for r in runs]
    rates = [r["placement_rate"] for r in runs if r["placement_rate"] is not None]
    head = runs[0]
    return {
        "label": head["label"],
        "period": head["period"],
        "solver": head["solver"],
        "n_sections": head["n_sections"],
        "schedulable": head["schedulable"],
        "unschedulable": head["unschedulable"],
        "n_blocks": head["n_blocks"],
        "runs": len(runs),
        "wall_s_median": round(statistics.median(walls), 1),
        "wall_s_min": round(min(walls), 1),
        "wall_s_max": round(max(walls), 1),
        "placement_rate_median": round(statistics.median(rates), 4) if rates else None,
        "genuine_conflicts_max": max(r["genuine_conflicts"] for r in runs),
        "hard_violations_max": max(r["hard_violations"] for r in runs),
    }


def _print_run(r: dict, tag: str) -> None:
    print(f"[{tag}] solver={r['solver']} sections={r['n_sections']} "
          f"placed={r['blocks_placed']}/{r['n_blocks']} ({r['placement_rate']:.1%}) "
          f"wall={r['pipeline_wall_s']:.1f}s "
          f"genuine_conflicts={r['genuine_conflicts']} "
          f"(unplaced_tail={r['hard_violations'] - r['genuine_conflicts']})")


def _print_summary(s: dict) -> None:
    print(f"  -> n={s['n_sections']}: median wall={s['wall_s_median']}s "
          f"(min {s['wall_s_min']} / max {s['wall_s_max']}), "
          f"placement={s['placement_rate_median']:.1%}, "
          f"genuine_conflicts={s['genuine_conflicts_max']}\n")


def _sizes_for(total: int, sizes_arg: str, steps: int) -> list[int]:
    """Explicit --sizes wins; else `steps` evenly-spaced points up to `total`."""
    if sizes_arg:
        out = sorted({min(int(x), total) for x in sizes_arg.split(",") if x.strip()})
    else:
        step = max(1, total // steps)
        out = sorted({min(step * k, total) for k in range(1, steps + 1)} | {total})
    return [n for n in out if n > 0]


def run_scale(csv_path: str, period: str, args) -> tuple[list, list]:
    """Scaling study: nested seeded subsets of increasing size from one CSV."""
    import random
    courses = load_courses(csv_path)
    # One deterministic shuffle, then sizes are PREFIXES -> nested subsets, so the
    # curve shows pure scaling (adding sections to the same base), not sampling noise.
    shuffled = list(courses)
    random.Random(args.seed).shuffle(shuffled)
    sizes = _sizes_for(len(shuffled), args.sizes, args.steps)
    print(f"[scale] {os.path.basename(csv_path)} p{period}: "
          f"{len(shuffled)} courses, sizes={sizes}, seed={args.seed}\n")

    all_runs, summaries = [], []
    for n in sizes:
        subset = shuffled[:n]
        cell = []
        for i in range(args.runs):
            r = solve_courses(subset, period, args.time_limit, label=f"n{n}")
            cell.append(r)
            _print_run(r, f"n={n} run {i+1}/{args.runs}")
        all_runs.extend(cell)
        s = summarize(cell)
        summaries.append(s)
        _print_summary(s)
    return summaries, all_runs


def _replicate(base_courses: list, target_n: int) -> list:
    """Build `target_n` synthetic course rows by tiling the base list. Each tile
    gets globally-unique section numbers AND unique instructor emails, so neither
    section ids nor instructor no-overlap collide across tiles — i.e. the tiles
    are independent 'faculties'. Course codes are kept valid (DEPT NNN) so cohort
    / level parsing is unchanged."""
    out, sec_ctr = [], 0
    n_tiles = -(-target_n // len(base_courses))   # ceil
    for tile in range(n_tiles):
        for c in base_courses:
            r = dict(c)
            sec_ctr += 1
            r["Section No"] = str(sec_ctr)                     # globally unique
            r["SECTION"] = str(sec_ctr)
            email = str(c.get("Instructor Email") or c.get("Email") or "x@uni.edu")
            r["Instructor Email"] = f"t{tile}+{email}"         # unique per tile
            r["Email"] = r["Instructor Email"]
            out.append(r)
            if len(out) >= target_n:
                return out
    return out


def _scale_rooms(base_rooms: list, factor: int) -> list:
    """Tile the classroom inventory `factor` times with unique room names, so the
    section/room ratio (tightness) stays ~constant as the section count grows."""
    out = []
    for k in range(max(1, factor)):
        for r in base_rooms:
            rr = dict(r)
            rr["Room"] = f"{r['Room']}~{k}"
            out.append(rr)
    return out


def run_synth(csv_path: str, period: str, args) -> tuple[list, list]:
    """Single-scope ceiling study: synthetic course lists beyond the real sample,
    with the classroom pool scaled in lockstep so tightness is held constant and
    the curve isolates how solve TIME scales with raw problem size."""
    base = load_courses(csv_path)
    base_n = len(base)
    base_rooms = [dict(r) for r in DEFAULT_CLASSROOMS]
    sizes = _sizes_for(max(args.max_n, base_n), args.sizes, args.steps)
    sizes = [n for n in sizes if n >= base_n] or [base_n]
    print(f"[synth] base={base_n} sections / {len(base_rooms)} rooms; "
          f"sizes={sizes}, budget={args.time_limit:.0f}s\n")

    all_runs, summaries = [], []
    for n in sizes:
        courses = _replicate(base, n)
        factor = -(-n // base_n)                              # ceil tiles -> room copies
        rooms = _scale_rooms(base_rooms, factor)
        cell = []
        for i in range(args.runs):
            r = solve_courses(courses, period, args.time_limit,
                              label=f"n{n}", classroom_rows=rooms)
            cell.append(r)
            _print_run(r, f"n={n} ({r['n_rooms']} rooms) run {i+1}/{args.runs}")
        all_runs.extend(cell)
        s = summarize(cell)
        s["n_rooms"] = cell[0]["n_rooms"]
        summaries.append(s)
        _print_summary(s)
    return summaries, all_runs


def run_cases(cases: list[str], args) -> tuple[list, list]:
    """Whole-file mode: solve each CSV in full, `runs` times."""
    all_runs, summaries = [], []
    for case in cases:
        csv_path, _, period = case.rpartition(":")
        if not csv_path:
            raise SystemExit(f"bad --case {case!r}: expected CSV:PERIOD")
        courses = load_courses(csv_path)
        rooms = load_classrooms(args.classrooms) if args.classrooms else None
        cell = []
        for i in range(args.runs):
            r = solve_courses(courses, period, args.time_limit,
                              label=os.path.basename(csv_path),
                              classroom_rows=rooms)
            cell.append(r)
            _print_run(r, f"{r['label']} p{period} run {i+1}/{args.runs}")
        all_runs.extend(cell)
        s = summarize(cell)
        summaries.append(s)
        _print_summary(s)
    return summaries, all_runs


def main() -> None:
    ap = argparse.ArgumentParser(description="KAIROS solver benchmark (headless)")
    ap.add_argument("--case", action="append", metavar="CSV:PERIOD",
                    help="whole-file mode; repeatable, e.g. data/...001.csv:001")
    ap.add_argument("--scale", metavar="CSV:PERIOD",
                    help="scaling study: nested subsets of one CSV by section count")
    ap.add_argument("--synth", metavar="CSV:PERIOD",
                    help="single-scope ceiling: synthetic sizes beyond the sample, "
                         "rooms scaled in lockstep (constant tightness)")
    ap.add_argument("--max-n", type=int, default=3000,
                    help="synth: largest synthetic section count (default 3000)")
    ap.add_argument("--sizes", default="",
                    help="scale/synth: explicit section counts, e.g. 1000,2000,3000")
    ap.add_argument("--steps", type=int, default=8,
                    help="scale/synth: # evenly-spaced sizes if --sizes omitted")
    ap.add_argument("--seed", type=int, default=42, help="scale: shuffle seed")
    ap.add_argument("--classrooms", default="",
                    help="case: real classroom inventory CSV (ROOM,ROOM_CAP); "
                         "default = embedded DEFAULT_CLASSROOMS")
    ap.add_argument("--runs", type=int, default=3,
                    help="repeats per cell; report median (default 3)")
    ap.add_argument("--time-limit", type=float, default=3000.0,
                    help="repair deadline seconds (default 3000, matches prod budget)")
    ap.add_argument("--out", default="out/benchmark.json")
    args = ap.parse_args()
    if not args.case and not args.scale and not args.synth:
        ap.error("give --case / --scale / --synth CSV:PERIOD")

    env = {
        "platform": platform.platform(),
        "python": platform.python_version(),
        "cpu_count": os.cpu_count(),
        "time_limit_s": args.time_limit,
        "mode": "synth" if args.synth else "scale" if args.scale else "case",
    }
    print(f"[env] {env['platform']} | python {env['python']} | "
          f"cpu={env['cpu_count']} | budget={args.time_limit:.0f}s | runs={args.runs}\n")

    summaries: list[dict] = []
    all_runs: list[dict] = []
    if args.synth:
        csv_path, _, period = args.synth.rpartition(":")
        if not csv_path:
            raise SystemExit(f"bad --synth {args.synth!r}: expected CSV:PERIOD")
        s, r = run_synth(csv_path, period, args)
        summaries += s
        all_runs += r
    if args.scale:
        csv_path, _, period = args.scale.rpartition(":")
        if not csv_path:
            raise SystemExit(f"bad --scale {args.scale!r}: expected CSV:PERIOD")
        s, r = run_scale(csv_path, period, args)
        summaries += s
        all_runs += r
    if args.case:
        s, r = run_cases(args.case, args)
        summaries += s
        all_runs += r

    payload = {"env": env, "summary": summaries, "runs": all_runs}
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"[done] wrote {out}")
    # Also emit the full JSON to stdout so a Cloud Run Job persists it in Cloud
    # Logging even when the ephemeral filesystem is discarded.
    print("=== BENCHMARK_JSON_BEGIN ===")
    print(json.dumps(payload, ensure_ascii=False))
    print("=== BENCHMARK_JSON_END ===")


if __name__ == "__main__":
    main()
