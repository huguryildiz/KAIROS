"""ITC-2007 Curriculum-Based Course Timetabling (.ectt/.ctt) parser and KAIROS adapter."""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple


# ---------------------------------------------------------------------------
# Parsed instance representation
# ---------------------------------------------------------------------------

@dataclass
class ItcCourse:
    course_id: str
    teacher_id: str
    num_lectures: int
    min_working_days: int
    num_students: int
    double_lectures: bool


@dataclass
class ItcRoom:
    room_id: str
    capacity: int
    building: int


@dataclass
class ItcInstance:
    name: str
    num_days: int
    periods_per_day: int
    courses: Dict[str, ItcCourse]
    rooms: Dict[str, ItcRoom]
    curricula: Dict[str, List[str]]          # curriculum_id -> [course_id, ...]
    unavailability: List[Tuple[str, int, int]]  # [(course_id, day, period), ...]
    room_constraints: List[Tuple[str, str]]     # [(course_id, room_id), ...]


def parse_ectt(path: str) -> ItcInstance:
    """Parse an ITC-2007 .ectt/.ctt instance file into an ItcInstance."""
    with open(path) as f:
        lines = [l.rstrip() for l in f]

    header: Dict[str, str] = {}
    for line in lines:
        upper = line.upper()
        if upper.startswith(("COURSES:", "ROOMS:", "CURRICULA:",
                              "UNAVAILABILITY", "ROOM_CONSTRAINTS", "END")):
            break
        if ":" in line:
            k, _, v = line.partition(":")
            header[k.strip()] = v.strip()

    name = header.get("Name", "")
    num_days = int(header.get("Days", 5))
    periods_per_day = int(header.get("Periods_per_day", 6))

    courses: Dict[str, ItcCourse] = {}
    rooms: Dict[str, ItcRoom] = {}
    curricula: Dict[str, List[str]] = {}
    unavailability: List[Tuple[str, int, int]] = []
    room_constraints: List[Tuple[str, str]] = []

    section = None
    for line in lines:
        upper = line.upper()
        if upper == "COURSES:":
            section = "courses"
            continue
        elif upper == "ROOMS:":
            section = "rooms"
            continue
        elif upper == "CURRICULA:":
            section = "curricula"
            continue
        elif upper.startswith("UNAVAILABILITY"):
            section = "unavail"
            continue
        elif upper.startswith("ROOM_CONSTRAINTS"):
            section = "room_constraints"
            continue
        elif upper == "END.":
            break

        if not line or ":" in line:
            continue

        parts = line.split()
        if not parts:
            continue

        if section == "courses" and len(parts) >= 6:
            courses[parts[0]] = ItcCourse(
                course_id=parts[0],
                teacher_id=parts[1],
                num_lectures=int(parts[2]),
                min_working_days=int(parts[3]),
                num_students=int(parts[4]),
                double_lectures=parts[5] == "1",
            )
        elif section == "rooms" and len(parts) >= 2:
            rooms[parts[0]] = ItcRoom(
                room_id=parts[0],
                capacity=int(parts[1]),
                building=int(parts[2]) if len(parts) > 2 else 0,
            )
        elif section == "curricula" and len(parts) >= 3:
            qid = parts[0]
            n = int(parts[1])
            curricula[qid] = parts[2:2 + n]
        elif section == "unavail" and len(parts) == 3:
            unavailability.append((parts[0], int(parts[1]), int(parts[2])))
        elif section == "room_constraints" and len(parts) == 2:
            room_constraints.append((parts[0], parts[1]))

    return ItcInstance(
        name=name,
        num_days=num_days,
        periods_per_day=periods_per_day,
        courses=courses,
        rooms=rooms,
        curricula=curricula,
        unavailability=unavailability,
        room_constraints=room_constraints,
    )


# ---------------------------------------------------------------------------
# KAIROS adapter
# ---------------------------------------------------------------------------

from .config import Config, DAYS
from .model import Section, Block, Room, Instructor


def adapt_itc2007(instance: ItcInstance, time_limit: float = 300.0) -> tuple:
    """Map ItcInstance → (sections, rooms, instructors, cfg) for run_pipeline.

    Design choices:
    - One KAIROS Section per ITC-2007 lecture (T=1, no lab).
    - Curriculum conflicts are enforced as HARD constraints by injecting each
      curriculum as a fake instructor. KAIROS's instructor no-overlap (H2) then
      prevents two courses in the same curriculum from sharing a period.
    - Room capacities are set to 999_999 to disable hard capacity pruning,
      because ITC-2007 treats capacity as a soft penalty (S1), not a hard limit.
      The evaluator reads real capacities from ItcInstance.
    - Teacher unavailability is mapped to Config.instr_unavailable.
    - Room constraints (.ectt extension) are intentionally ignored — noted in
      runner output.
    """
    # course_id → list of curriculum IDs it belongs to
    course_curricula: Dict[str, List[str]] = {cid: [] for cid in instance.courses}
    for qid, course_ids in instance.curricula.items():
        for cid in course_ids:
            if cid in course_curricula:
                course_curricula[cid].append(qid)

    # Rooms with inflated capacity
    rooms: Dict[str, Room] = {
        rid: Room(
            room=rid,
            cap=999_999,
            is_lab=False,
            is_physical=True,
            is_virtual=False,
            dept="",
        )
        for rid in instance.rooms
    }

    # Real teachers + one fake instructor per curriculum (for hard H3 conflict)
    instructors: Dict[str, Instructor] = {}
    for course in instance.courses.values():
        tid = course.teacher_id
        if tid not in instructors:
            instructors[tid] = Instructor(
                staff_id=tid, name=tid, is_staff=True, home_dept=""
            )
    for qid in instance.curricula:
        fid = f"__q{qid}"
        instructors[fid] = Instructor(
            staff_id=fid, name=f"curriculum {qid}", is_staff=False, home_dept=""
        )

    # Unavailability: teacher-level (course_id → teacher_id → (day_str, period))
    unavail_set: set = set()
    for course_id, day_idx, period in instance.unavailability:
        teacher_id = instance.courses[course_id].teacher_id
        unavail_set.add((teacher_id, DAYS[day_idx], period))

    # One Section per lecture
    sections = []
    for course_id, course in instance.courses.items():
        instr_ids = [course.teacher_id] + [
            f"__q{qid}" for qid in course_curricula.get(course_id, [])
        ]
        for i in range(course.num_lectures):
            sid = f"{course_id}_L{i:02d}"
            block = Block(
                block_id=f"{sid}#T",
                section_id=sid,
                kind="theory",
                length=1,
                needs_lab=False,
            )
            sections.append(Section(
                section_id=sid,
                period=instance.name,
                code=course_id,
                name=course_id,
                level=1,
                dept_code="",
                department="",
                cohort_key="",
                instructor_ids=instr_ids,
                students=course.num_students,
                T=1, P=0, L=0, Cr=1,
                category="",
                blocks=[block],
            ))

    cfg = Config(
        horizon_start=0,
        horizon_end=instance.periods_per_day,
        undergrad_end=instance.periods_per_day,
        grad_start=instance.periods_per_day,
        grad_end=instance.periods_per_day,
        saturday_enabled=False,
        include_grad=False,
        soft_shaping_in_repair=False,
        soft_polish_in_repair=False,
        instr_unavailable=frozenset(unavail_set),
        blackout=(),
        w_cohort_conflict=0,
        w_cohort_gap=0,
        w_order=0,
        w_englab=0,
        w_nonadjacent=0,
        solve_time_limit_s=time_limit,
    )

    return sections, rooms, instructors, cfg
