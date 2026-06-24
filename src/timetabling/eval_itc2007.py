"""ITC-2007 CB-CTT objective evaluator.

Computes S1 (RoomCapacity) + S2 (MinWorkingDays) + S3 (CurriculumCompactness)
+ S4 (RoomStability) from a list of KAIROS Assignments and a parsed ItcInstance.
Also checks hard constraints (room overlap, teacher conflict, curriculum conflict).
"""
from __future__ import annotations
from collections import defaultdict
from typing import Dict, List

from .model import Assignment
from .io_itc2007 import ItcInstance


def evaluate_itc2007(assignments: List[Assignment], instance: ItcInstance) -> Dict:
    """Compute ITC-2007 objective.

    Returns:
        dict with s1, s2, s3, s4, total (int each) and hard_violations (dict).

    section_id format is "{course_id}_L{i:02d}" — we recover course_id by
    splitting on the last "_L" occurrence.
    """

    def course_of(section_id: str) -> str:
        return section_id.rsplit("_L", 1)[0]

    # Group by course
    by_course: Dict[str, List[Assignment]] = defaultdict(list)
    for a in assignments:
        by_course[course_of(a.section_id)].append(a)

    # Index by (day, period) and (room, day, period)
    by_slot: Dict[tuple, List[Assignment]] = defaultdict(list)
    by_room_slot: Dict[tuple, List[Assignment]] = defaultdict(list)
    for a in assignments:
        by_slot[(a.day, a.start)].append(a)
        by_room_slot[(a.room, a.day, a.start)].append(a)

    # S1: RoomCapacity — 1 point per student that cannot be seated
    s1 = 0
    for a in assignments:
        cid = course_of(a.section_id)
        students = instance.courses[cid].num_students if cid in instance.courses else 0
        cap = instance.rooms[a.room].capacity if a.room in instance.rooms else 999_999
        s1 += max(0, students - cap)

    # S2: MinWorkingDays — 5 points per missing distinct day per course
    s2 = 0
    for cid, course_assignments in by_course.items():
        actual_days = len({a.day for a in course_assignments})
        min_days = instance.courses[cid].min_working_days if cid in instance.courses else 0
        s2 += 5 * max(0, min_days - actual_days)

    # S3: CurriculumCompactness — 2 points per isolated lecture per curriculum
    # A lecture (course c, day d, period p) is isolated in curriculum q if
    # no other course in q is at (d, p-1) or (d, p+1).
    # Build: (curriculum_id, day, period) → set of course_ids present
    curric_slot: Dict[tuple, set] = defaultdict(set)
    for a in assignments:
        cid = course_of(a.section_id)
        for qid, qcourses in instance.curricula.items():
            if cid in qcourses:
                curric_slot[(qid, a.day, a.start)].add(cid)

    s3 = 0
    for a in assignments:
        cid = course_of(a.section_id)
        p = a.start
        d = a.day
        for qid, qcourses in instance.curricula.items():
            if cid not in qcourses:
                continue
            has_prev = bool(curric_slot.get((qid, d, p - 1)))
            has_next = bool(curric_slot.get((qid, d, p + 1)))
            if not has_prev and not has_next:
                s3 += 2

    # S4: RoomStability — 1 point per extra room used per course
    s4 = 0
    for cid, course_assignments in by_course.items():
        distinct_rooms = len({a.room for a in course_assignments})
        s4 += max(0, distinct_rooms - 1)

    total = s1 + s2 + s3 + s4

    # Hard constraint violations (informational)
    hard: Dict[str, int] = {"room_overlap": 0, "teacher_overlap": 0, "curriculum_overlap": 0}

    for slot_as in by_room_slot.values():
        if len(slot_as) > 1:
            hard["room_overlap"] += len(slot_as) - 1

    for slot_as in by_slot.values():
        courses_here = [course_of(a.section_id) for a in slot_as]
        teachers_here = [
            instance.courses[c].teacher_id for c in courses_here if c in instance.courses
        ]
        for t in set(teachers_here):
            count = teachers_here.count(t)
            if count > 1:
                hard["teacher_overlap"] += count - 1
        for qid, qcourses in instance.curricula.items():
            in_slot = [c for c in courses_here if c in qcourses]
            if len(in_slot) > 1:
                hard["curriculum_overlap"] += len(in_slot) - 1

    return {
        "s1": s1,
        "s2": s2,
        "s3": s3,
        "s4": s4,
        "total": total,
        "hard_violations": hard,
    }
