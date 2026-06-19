from __future__ import annotations
from typing import List, Dict
import json
import csv

from .model import Assignment, Section, Room, Instructor


def build_schedule_dict(period, assignments: List[Assignment], sections: List[Section],
                        rooms: Dict[str, Room], instructors: Dict[str, Instructor],
                        unmet_soft=None, conflicts=None) -> dict:
    sec_by_id = {s.section_id: s for s in sections}
    items = []
    for a in assignments:
        s = sec_by_id.get(a.section_id)
        room = rooms.get(a.room)
        ins = instructors.get(s.instructor_id) if s else None
        items.append({
            "section_id": a.section_id,
            "course_code": s.code if s else "",
            "course_name": s.name if s else "",
            "block_kind": a.kind,
            "instructor_id": s.instructor_id if s else "",
            "instructor_name": ins.name if ins else "",
            "cohort": s.cohort_key if s else "",
            "dept": s.dept_code if s else "",
            "students": s.students if s else 0,
            "day": a.day, "start": a.start, "end": a.end,
            "room": a.room,
            "room_cap": room.cap if room else None,
            "is_lab_room": room.is_lab if room else None,
            "flags": [],
        })
    return {
        "period": period,
        "meta": {"n_assignments": len(items), "n_sections": len(sections)},
        "assignments": items,
        "unmet_soft": unmet_soft or [],
        "conflicts": conflicts or [],
    }


def write_schedule_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: str, payload: dict) -> None:
    fields = ["section_id", "course_code", "course_name", "block_kind", "instructor_id",
              "instructor_name", "cohort", "dept", "students", "day", "start", "end",
              "room", "room_cap", "is_lab_room"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for item in payload["assignments"]:
            w.writerow(item)
