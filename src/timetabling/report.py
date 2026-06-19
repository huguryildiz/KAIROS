from __future__ import annotations
from typing import List
from collections import Counter

from .config import Config
from .model import Assignment, Section, Room, Instructor
from .schedule_parse import parse_schedule
from .validate import validate


def data_quality_report(period, frame, rooms, derive_report, cfg: Config) -> dict:
    empty_room = sum(1 for _, r in frame.iterrows() if str(r.get("plan_room", "")).strip() == "")
    dirty = 0
    for _, r in frame.iterrows():
        sched = str(r.get("plan_schedule", "")).strip()
        if sched and parse_schedule(sched)[1]:
            dirty += 1
    missing_cohort = (frame["dept_code"].astype(str).str.strip() == "").sum()
    labs = [r.room for r in rooms.values() if r.is_lab and r.is_physical]
    return {
        "period": period,
        "n_grades_sections": len(frame),
        "empty_plan_room": int(empty_room),
        "dirty_plan_schedule": int(dirty),
        "missing_cohort_join": int(missing_cohort),
        "n_physical_rooms": sum(1 for r in rooms.values() if r.is_physical),
        "n_lab_rooms": len(labs),
        "lab_rooms": sorted(labs),
        "derive": derive_report,
    }


def parse_existing(frame, sections: List[Section]) -> List[Assignment]:
    """Build Assignments from the existing Plan SCHEDULE (Mode B ground truth).
    Each parsed session gets a unique block id (#E0, #E1, ...) so the Mode-B
    validator reports real resource conflicts, not derived-vs-actual block
    structure mismatches."""
    if hasattr(frame, "iterrows"):
        lookup = {str(r["section_id"]).strip(): r for _, r in frame.iterrows()}
    else:
        lookup = frame
    out: List[Assignment] = []
    for s in sections:
        r = lookup.get(s.section_id)
        if r is None:
            continue
        room = str(r.get("plan_room", "")).strip()
        sessions, errors = parse_schedule(str(r.get("plan_schedule", "")))
        if errors or not sessions:
            continue
        for idx, sess in enumerate(sessions):
            out.append(Assignment(f"{s.section_id}#E{idx}", s.section_id, "theory",
                                  room, sess.day, sess.start, sess.end))
    return out


def _metrics(assignments, sections, rooms, instructors, cfg, check_placement=True) -> dict:
    v = validate(assignments, sections, rooms, instructors, cfg, check_placement=check_placement)
    by_kind = Counter(x.kind for x in v)
    rooms_used = len({a.room for a in assignments if a.room})
    evening = sum(1 for a in assignments
                  if any(h >= cfg.evening_from_hour for h in range(a.start, a.end)))
    sec_by_id = {s.section_id: s for s in sections}
    fills = []
    for a in assignments:
        s = sec_by_id.get(a.section_id)
        room = rooms.get(a.room)
        if s and room and room.cap:
            fills.append(s.students / room.cap)
    room_fill = round(sum(fills) / len(fills), 3) if fills else 0.0
    return {
        "n_assignments": len(assignments),
        "conflicts": dict(by_kind),
        "n_violations": len(v),
        "rooms_used": rooms_used,
        "evening_blocks": evening,
        "evening_ratio": round(evening / len(assignments), 3) if assignments else 0.0,
        "room_fill": room_fill,
    }


def mode_b_benchmark(period, mode_a, existing, sections, rooms, instructors, cfg) -> dict:
    return {
        "period": period,
        "mode_a": _metrics(mode_a, sections, rooms, instructors, cfg, check_placement=True),
        "existing": _metrics(existing, sections, rooms, instructors, cfg, check_placement=False),
    }
