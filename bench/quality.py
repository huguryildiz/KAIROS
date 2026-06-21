"""Generated-schedule quality metrics for the sample CSVs (no 'existing' baseline).

Solves each sample course list via the same UI path the app uses, then runs
report._metrics over the resulting assignments to report distinct rooms used,
evening ratio, average room fill, and hard conflicts — i.e. characteristics of
the schedule Kairos produces, computed only from the two sample files.

    PYTHONPATH=src python3 bench/quality.py
"""
from __future__ import annotations

import json
from pathlib import Path

from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                   build_instructors_from_courselist)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
from timetabling.report import _metrics
from bench.benchmark import load_courses, load_classrooms
from timetabling.ui_input import build_rooms_from_ui

CASES = [("data/sample_courses_2025_001.csv", "001", "Fall"),
         ("data/sample_courses_2025_002.csv", "002", "Spring")]
CLASSROOMS = "data/classrooms.csv"
BUDGET = 3000.0


def main() -> None:
    out = []
    for csv_path, period, label in CASES:
        cfg = build_config({}, {}, BUDGET)
        courses = load_courses(csv_path)
        secs, _ = build_sections_from_courselist(courses, period, cfg)
        instr = build_instructors_from_courselist(courses)
        rooms = build_rooms_from_ui(load_classrooms(CLASSROOMS), cfg)
        mark_virtual(secs, rooms, cfg)
        res = run_pipeline(period, secs, rooms, instr, cfg, solver="auto")
        m = _metrics(res.assignments, secs, rooms, instr, cfg)
        row = {
            "period": period, "label": label, "sections": len(secs),
            "rooms_used": m["rooms_used"], "evening_ratio": m["evening_ratio"],
            "room_fill": m["room_fill"],
            "hard_conflicts": sum(v for k, v in m.get("conflicts", {}).items()
                                  if k != "placement"),
            "unplaced": m.get("conflicts", {}).get("placement", 0),
        }
        out.append(row)
        print(f"[{label} {period}] sections={row['sections']} "
              f"rooms_used={row['rooms_used']} evening={row['evening_ratio']} "
              f"fill={row['room_fill']} hard={row['hard_conflicts']} "
              f"unplaced={row['unplaced']}")
    Path("out").mkdir(exist_ok=True)
    Path("out/quality.json").write_text(json.dumps(out, indent=2))
    print("[done] out/quality.json")


if __name__ == "__main__":
    main()
