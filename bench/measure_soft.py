"""Before/after soft measurement on a CSV subset. Mirrors the UI solve path.
Usage: PYTHONPATH=src python3 bench/measure_soft.py <N> <budget_s> <label>"""
import sys
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
