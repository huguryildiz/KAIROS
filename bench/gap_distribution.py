"""Gap distribution measurement for #2 (uzun boşluk / izole ders ayrımı).

Runs the full pipeline and reports per-cohort per-day idle gap distribution.
Output guides the long-gap threshold selection before implementing the new soft term.

Usage:
    PYTHONPATH=src python3 bench/gap_distribution.py [N] [budget_s]

    N         number of course rows to use (default: 841, full dataset)
    budget_s  solver time budget in seconds (default: 1200)
"""
import sys
from collections import defaultdict

from timetabling.csv_import import read_raw, parse_courselist, ok_rows, parse_classrooms, ok_rooms
from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                   build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline

N = int(sys.argv[1]) if len(sys.argv) > 1 else 841
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0

courses = ok_rows(parse_courselist(read_raw("data/sample_courses_2025_001.csv")))[:N]
cfg = build_config({}, {}, budget)
secs, _ = build_sections_from_courselist(courses, "001", cfg)
instr = build_instructors_from_courselist(courses)
rooms = build_rooms_from_ui(ok_rooms(parse_classrooms(read_raw("data/classrooms.csv"))), cfg)
mark_virtual(secs, rooms, cfg)

res = run_pipeline("001", secs, rooms, instr, cfg, solver="auto")

# Build section lookup: section_id -> Section
sec_by_sid = {s.section_id: s for s in res.sections}

# Accumulate occupied hours per (cohort_key, day)
coh_day: dict = defaultdict(set)
for a in res.assignments:
    s = sec_by_sid.get(a.section_id)
    if s is None:
        continue
    for h in range(a.start, a.end):
        coh_day[(s.cohort_key, a.day)].add(h)


def _contiguous_runs(hours: list) -> list:
    """Split sorted list of hours into contiguous runs [(start, end), ...]."""
    if not hours:
        return []
    runs = []
    run_start = prev = hours[0]
    for h in hours[1:]:
        if h == prev + 1:
            prev = h
        else:
            runs.append((run_start, prev))
            run_start = prev = h
    runs.append((run_start, prev))
    return runs


# Analyse gaps
gap_counts: dict = defaultdict(int)   # gap_size_hours -> number of occurrences
isolated_days = 0     # cohort-days with exactly 1 contiguous block (no idle possible)
compact_days = 0      # cohort-days with >1 block but zero idle between them
total_days = len(coh_day)

for (_cohort, _day), hours in coh_day.items():
    runs = _contiguous_runs(sorted(hours))
    if len(runs) == 1:
        isolated_days += 1
        continue
    gaps_this_day = [runs[i + 1][0] - runs[i][1] - 1 for i in range(len(runs) - 1)]
    if all(g == 0 for g in gaps_this_day):
        compact_days += 1
        continue
    for g in gaps_this_day:
        if g > 0:
            gap_counts[g] += 1

# Print report
placed = res.stats.get("placed", "?")
total_blocks = res.stats.get("total") or res.stats.get("n_blocks", "?")
print(f"\n=== Gap Distribution  ({N} courses, placed {placed}/{total_blocks} blocks) ===")
print(f"  cohort-days analysed : {total_days}")
print(f"  isolated  (1 block)  : {isolated_days:4d}  ({100 * isolated_days / total_days:.1f}%)")
print(f"  compact   (no idle)  : {compact_days:4d}  ({100 * compact_days / total_days:.1f}%)")
gapped_days = total_days - isolated_days - compact_days
print(f"  has idle gap         : {gapped_days:4d}  ({100 * gapped_days / total_days:.1f}%)")

total_gaps = sum(gap_counts.values())
if total_gaps == 0:
    print("\n  No idle gaps found — threshold irrelevant.")
    sys.exit(0)

print(f"\n  Individual idle gaps : {total_gaps} occurrences")
print(f"  {'gap':>5}  {'count':>6}  {'%':>6}  {'cum%':>6}  bar")
print(f"  {'-'*5}  {'-'*6}  {'-'*6}  {'-'*6}  ---")
cumulative = 0
p80_threshold = None
for g in sorted(gap_counts):
    cumulative += gap_counts[g]
    pct = 100 * gap_counts[g] / total_gaps
    cum_pct = 100 * cumulative / total_gaps
    bar = "█" * max(1, round(pct / 2))
    print(f"  {g:>4}h  {gap_counts[g]:>6}  {pct:>5.1f}%  {cum_pct:>5.1f}%  {bar}")
    if cum_pct >= 80 and p80_threshold is None:
        p80_threshold = g

print(f"\n  80th-percentile gap  : {p80_threshold}h")
print(f"  → gaps ≤ {p80_threshold}h: tolerate (or small penalty)")
print(f"  → gaps > {p80_threshold}h: penalize (long-gap term)")
print(f"\n  Note: 'isolated' cohort-days may also need a separate penalty (ITC-2007 S3).")
print(f"  Decide: merge into one term (w_gap) or two separate weights (w_isolated, w_long_gap)?")
