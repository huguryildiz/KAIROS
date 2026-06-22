"""Before/after soft measurement on a CSV subset. Mirrors the UI solve path.
Usage: PYTHONPATH=src python3 bench/measure_soft.py <N> <budget_s> <label>

Env overrides (soft-polish gate): SOFT_POLISH=1 forces cfg.soft_polish_in_repair
on; SOFT_ACCEPTOR=schc|lahc|deluge|sa picks the acceptor; SOFT_LIMIT=<int> sets
soft_polish_counter_limit."""
import os
import sys
from dataclasses import replace
from time import perf_counter
from timetabling.csv_import import read_raw, parse_courselist, ok_rows
from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                   build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.report import _metrics

N = int(sys.argv[1]) if len(sys.argv) > 1 else 841
budget = float(sys.argv[2]) if len(sys.argv) > 2 else 1200.0
label = sys.argv[3] if len(sys.argv) > 3 else "run"
courses = ok_rows(parse_courselist(read_raw("data/sample_courses_2025_001.csv")))[:N]
cfg = build_config({}, {}, budget)
if os.getenv("SOFT_POLISH"):
    cfg = replace(cfg, soft_polish_in_repair=True)
if os.getenv("SOFT_ACCEPTOR"):
    cfg = replace(cfg, soft_polish_acceptor=os.getenv("SOFT_ACCEPTOR"))
if os.getenv("SOFT_LIMIT"):
    cfg = replace(cfg, soft_polish_counter_limit=int(os.getenv("SOFT_LIMIT")))
# 0-1 preference weights for the four toggles (normalized objective -> only ratios matter).
for _env, _field in (("W_EVENING", "w_evening"), ("W_GAP", "w_cohort_gap"),
                     ("W_ROOM", "w_room_count"), ("W_DAYS", "w_instr_days")):
    if os.getenv(_env) is not None:
        cfg = replace(cfg, **{_field: float(os.getenv(_env))})
secs, _ = build_sections_from_courselist(courses, "001", cfg)
instr = build_instructors_from_courselist(courses)
rooms = build_rooms_from_ui([dict(r) for r in DEFAULT_CLASSROOMS], cfg)
mark_virtual(secs, rooms, cfg)
t0 = perf_counter()
res = run_pipeline("001", secs, rooms, instr, cfg, solver="auto")
wall = perf_counter() - t0
m = _metrics(res.assignments, res.sections, rooms, instr, cfg)
placed, total = res.stats.get("placed"), res.stats.get("total") or res.stats.get("n_blocks")
conf = m["conflicts"]
genuine = sum(v for k, v in conf.items() if k != "placement")
print(f"[{label}] placed={placed}/{total} rate={placed/total:.4f} wall={wall:.0f}s "
      f"| evening={m['evening_blocks']} cohort_conf={m['cohort_conflicts']} "
      f"cohort_gap={m['cohort_gap']} teach_days={m['instr_teaching_days']} "
      f"rooms={m['rooms_used']} | genuine_hard={genuine} tail={conf.get('placement', 0)}")
pre, post = res.stats.get("soft_pre"), res.stats.get("soft_post")
if pre and post:
    keys = ("evening", "gap", "rooms", "days", "conf")
    print(f"  within-run pre ->post (Pareto; only conflict guarded): "
          + " ".join(f"{k} {pre[k]}->{post[k]}" for k in keys))

# Utilization: how full is the grid (physical rooms x days x undergrad teaching hours)?
phys = [r for r in rooms.values() if not r.is_virtual]
days_n = len(cfg.days())
hours_n = max(1, cfg.undergrad_end - cfg.horizon_start)
cap_slots = len(phys) * days_n * hours_n
occ_slots = sum(a.end - a.start for a in res.assignments
                if a.room in rooms and not rooms[a.room].is_virtual)
rooms_used = len({a.room for a in res.assignments
                  if a.room in rooms and not rooms[a.room].is_virtual})
grid = occ_slots / cap_slots if cap_slots else 0.0
print(f"  utilization: grid {occ_slots}/{cap_slots} room-hours = {grid:.1%} full "
      f"| rooms used {rooms_used}/{len(phys)} = {rooms_used/len(phys):.1%} "
      f"({days_n} days x {hours_n}h x {len(phys)} rooms)")
