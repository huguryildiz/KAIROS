#!/usr/bin/env python
"""Run KAIROS on an ITC-2007 CB-CTT instance and compare against published best-known results.

Usage:
  .venv/bin/python benchmarks/run_itc2007.py benchmarks/itc2007/comp01.ectt
  .venv/bin/python benchmarks/run_itc2007.py benchmarks/itc2007/comp01.ectt --time-limit 300 --solver cpsat
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from timetabling.io_itc2007 import parse_ectt, adapt_itc2007
from timetabling.eval_itc2007 import evaluate_itc2007
from timetabling.pipeline import run_pipeline

# Best-known upper bounds — source: Lü & Hao / Asín Achá & Nieuwenhuis / Kiefer et al.,
# as compiled in Table 13 of arxiv:2201.07525 "Educational Timetabling: Problems, Benchmarks,
# and State-of-the-Art Results". These are NOT KAIROS scores.
BEST_KNOWN = {
    "Fis0506-1": 5,    # comp01
    "Ing0203-2": 24,   # comp02
    "comp04": 35,
    "comp05": 284,
    "comp06": 27,
    "comp07": 6,
    "comp08": 37,
    "comp09": 96,
    "comp10": 4,
    "comp12": 294,
    "comp13": 59,
    "comp14": 51,
    "comp15": 62,
    "comp16": 18,
    "comp17": 56,
    "comp18": 61,
    "comp19": 57,
    "comp20": 4,
    "comp21": 74,
}


def main():
    ap = argparse.ArgumentParser(description="KAIROS × ITC-2007 CB-CTT benchmark runner")
    ap.add_argument("instance", help="Path to .ectt or .ctt file")
    ap.add_argument("--time-limit", type=float, default=300.0, help="Solver time limit in seconds")
    ap.add_argument("--solver", default="auto", choices=["auto", "cpsat", "repair"])
    args = ap.parse_args()

    W = 62
    print(f"\n{'='*W}")
    print(f"  KAIROS × ITC-2007 Curriculum-Based Course Timetabling")
    print(f"{'='*W}")
    print(f"  Instance : {args.instance}")
    print(f"  Solver   : {args.solver}")
    print(f"  Limit    : {args.time_limit}s")
    print(f"{'='*W}\n")

    t0 = time.perf_counter()

    # 1. Parse
    instance = parse_ectt(args.instance)
    total_lectures = sum(c.num_lectures for c in instance.courses.values())
    print(f"  Instance : {instance.name}")
    print(f"  Courses  : {len(instance.courses)}")
    print(f"  Rooms    : {len(instance.rooms)}")
    print(f"  Grid     : {instance.num_days} days × {instance.periods_per_day} periods")
    print(f"  Curricula: {len(instance.curricula)}")
    print(f"  Lectures : {total_lectures}  (each becomes one KAIROS section)")
    print()

    # 2. Adapt
    sections, rooms, instructors, cfg = adapt_itc2007(instance, time_limit=args.time_limit)

    # 3. Solve
    print("  Solving...\n")
    result = run_pipeline(
        period=instance.name,
        sections=sections,
        rooms=rooms,
        instructors=instructors,
        cfg=cfg,
        solver=args.solver,
    )
    elapsed = time.perf_counter() - t0

    placed = len(result.assignments)
    pct = f"{100 * placed // total_lectures}%" if total_lectures else "N/A"

    if result.unschedulable:
        print(f"  WARNING: {len(result.unschedulable)} sections could not be placed:")
        for u in result.unschedulable[:5]:
            print(f"    - {u['section_id']}: {u.get('issues', '')}")
        print()

    # 4. Evaluate ITC-2007 objective
    scores = evaluate_itc2007(result.assignments, instance)

    print(f"  Placed        : {placed}/{total_lectures} ({pct})")
    print(f"  Elapsed       : {elapsed:.1f}s")
    print()
    print(f"  {'─'*50}")
    print(f"  ITC-2007 Objective (lower is better)")
    print(f"  {'─'*50}")
    print(f"  S1 RoomCapacity   : {scores['s1']:>6}   (1 pt × students over capacity)")
    print(f"  S2 MinWorkingDays : {scores['s2']:>6}   (5 pt × missing days per course)")
    print(f"  S3 Compactness    : {scores['s3']:>6}   (2 pt × isolated lectures)")
    print(f"  S4 RoomStability  : {scores['s4']:>6}   (1 pt × extra rooms per course)")
    print(f"  {'─'*50}")
    print(f"  TOTAL             : {scores['total']:>6}")

    bk = BEST_KNOWN.get(instance.name)
    if bk is not None:
        gap = scores["total"] - bk
        sign = "+" if gap >= 0 else ""
        pct_gap = f"{gap / max(bk, 1) * 100:.0f}%" if bk else "N/A"
        print(f"  Best Known (lit.) : {bk:>6}   (arxiv:2201.07525)")
        print(f"  Gap               : {sign}{gap:>5}   ({sign}{pct_gap} vs best)")
    else:
        print(f"  Best Known        :    N/A   (instance name '{instance.name}' not in table)")

    hv = scores["hard_violations"]
    total_hard = sum(hv.values())
    print()
    if total_hard == 0:
        print("  Hard constraints  : ALL SATISFIED")
    else:
        print(f"  HARD VIOLATIONS   : {total_hard} total  ← solution is INFEASIBLE")
        for k, v in hv.items():
            if v:
                print(f"    {k}: {v}")

    print()
    print("  Notes:")
    print("  - Room constraints (.ectt extension, not in original ITC-2007) are ignored.")
    print("  - Unavailability mapped at teacher level (not per-course).")
    print("  - Capacity pruning disabled (cap=999999); S1 uses real room capacities.")
    print(f"{'='*W}\n")


if __name__ == "__main__":
    main()
