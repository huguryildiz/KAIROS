from __future__ import annotations
from datetime import datetime
from pathlib import Path
from typing import List, Dict
import json
import csv

from .model import Assignment, Section, Room, Instructor

# Canonical per-assignment column order, shared by the CLI CSV and the UI
# download so both outputs are byte-for-byte identical in shape.
CSV_FIELDS = ["section_id", "course_code", "course_name", "block_kind",
              "instructor_id", "instructor_name", "cohort", "dept", "department",
              "section_cap", "section_p", "day", "start", "end",
              "room", "room_cap", "is_lab_room"]


def build_schedule_dict(period, assignments: List[Assignment], sections: List[Section],
                        rooms: Dict[str, Room], instructors: Dict[str, Instructor],
                        unmet_soft=None, conflicts=None) -> dict:
    sec_by_id = {s.section_id: s for s in sections}
    items = []
    for a in assignments:
        s = sec_by_id.get(a.section_id)
        room = rooms.get(a.room)
        ids = s.instructor_ids if s else []
        names = [instructors[i].name for i in ids if i in instructors and instructors[i].name]
        items.append({
            "section_id": a.section_id,
            "course_code": s.code if s else "",
            "course_name": s.name if s else "",
            "block_kind": a.kind,
            "instructor_id": ",".join(ids),
            "instructor_name": " & ".join(names),
            "cohort": s.cohort_key if s else "",
            "dept": s.dept_code if s else "",
            "department": s.department if s else "",
            "section_cap": s.students if s else 0,
            "section_p": s.P if s else 0,
            "day": a.day, "start": a.start, "end": a.end,
            "room": a.room,
            "room_cap": room.cap if room else None,
            "is_lab_room": room.is_lab if room else None,
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
    # utf-8-sig: BOM lets Excel (notably on macOS) detect UTF-8 so Turkish
    # characters (ş, ğ, ü, …) render correctly instead of mojibake.
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        w.writeheader()
        for item in payload["assignments"]:
            w.writerow(item)


def write_schedule_outputs(
    out_dir: str | Path,
    payload: dict,
    period: str | None = None,
    generated_at: datetime | None = None,
    include_period: bool = True,
) -> dict[str, Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stamp = (generated_at or datetime.now()).strftime("%Y%m%d_%H%M%S")
    suffix = period or payload.get("period")
    stem = f"schedule_{suffix}_{stamp}" if include_period and suffix else f"schedule_{stamp}"
    paths = {
        "json": out / f"{stem}.json",
        "csv": out / f"{stem}.csv",
    }
    write_schedule_json(str(paths["json"]), payload)
    write_csv(str(paths["csv"]), payload)
    return paths
