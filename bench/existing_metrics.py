"""Existing (manual) schedule metrics from the Grades/Plan data — NO solve.

Parses the current hand-made timetable (Plan SCHEDULE/ROOM columns) and scores
it under the same rule model, for the before/after comparison. Solve-free, so it
won't contend with anything running. Requires the Grades/Plan CSVs staged in
data/ (data/2025-0X-Grades.csv, -Plan.csv).

    PYTHONPATH=src python3 bench/existing_metrics.py
"""
from __future__ import annotations

import json
from pathlib import Path

from timetabling.config import Config
from timetabling.io_csv import load_classrooms, load_lecturers
from timetabling.clean import build_rooms, build_instructors
from timetabling.join import build_section_frame
from timetabling.derive import build_sections
from timetabling.route import mark_virtual, mark_lab_rooms
from timetabling.report import parse_existing, _metrics


def main() -> None:
    cfg = Config()
    rooms = build_rooms(load_classrooms(), cfg)
    instructors = build_instructors(load_lecturers())
    out = []
    for period, label in [("001", "Fall"), ("002", "Spring")]:
        frame = build_section_frame(period, cfg.include_plan_only)
        sections, _ = build_sections(frame, cfg)
        mark_virtual(sections, rooms, cfg)
        mark_lab_rooms(sections, rooms, cfg)
        existing = parse_existing(frame, sections)
        m = _metrics(existing, sections, rooms, instructors, cfg, check_placement=False)
        conf = m.get("conflicts", {})
        row = {
            "period": period, "label": label,
            "n_assignments": len(existing),
            "hard_conflicts": sum(conf.values()),
            "conflicts": conf,
            "rooms_used": m["rooms_used"],
            "evening_ratio": m["evening_ratio"],
            "room_fill": m["room_fill"],
        }
        out.append(row)
        print(f"[{label} {period}] existing: assignments={row['n_assignments']} "
              f"hard={row['hard_conflicts']} rooms_used={row['rooms_used']} "
              f"evening={row['evening_ratio']} fill={row['room_fill']} "
              f"conflicts={conf}")
    Path("out").mkdir(exist_ok=True)
    Path("out/existing_metrics.json").write_text(json.dumps(out, indent=2))
    print("[done] out/existing_metrics.json")


if __name__ == "__main__":
    main()
