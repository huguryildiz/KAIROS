from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Room:
    room: str
    cap: int
    is_lab: bool
    is_physical: bool
    is_virtual: bool = False
    type: str = "normal"        # normal | lab | pc | studio (supply side)
    dept: str = ""              # semicolon-separated owner dept names; "" = open to all


@dataclass(frozen=True)
class Instructor:
    staff_id: str
    name: str
    is_staff: bool          # True = full-time
    home_dept: str


@dataclass(frozen=True)
class Block:
    block_id: str           # e.g. "ADA 403_01#T" or "...#L"
    section_id: str
    kind: str               # "theory" | "lab"
    length: int             # hours
    needs_lab: bool


@dataclass
class Section:
    section_id: str
    period: str
    code: str               # "ADA 403"
    name: str
    level: int              # 1..6
    dept_code: str          # "ADA"
    department: str         # Grades "Dept." column (faculty/department name)
    cohort_key: str         # "ADA-4"
    instructor_ids: List[str]
    students: int
    T: int
    P: int
    L: int
    Cr: int
    category: str
    blocks: List[Block] = field(default_factory=list)
    is_virtual: bool = False
    plan_room: str = ""
    lab_room: str = ""          # pinned lab room (from Plan), "" = any lab-family room
    requires_lab_room: bool = False  # back-compat boolean (required_room_type in lab-family)
    required_room_type: str = ""     # normal|lab|pc|studio demand; "" = derive from L
    fixed_day: str = ""         # pin the section's first block to this day ("" = unpinned)
    fixed_start: int = -1       # pin the section's first block to this start hour (-1 = unpinned)


@dataclass(frozen=True)
class Candidate:
    block_id: str
    room: str
    day: str
    start: int              # start hour
    length: int


@dataclass(frozen=True)
class Assignment:
    block_id: str
    section_id: str
    kind: str
    room: str
    day: str
    start: int
    end: int                # exclusive (start + length)


@dataclass(frozen=True)
class Violation:
    kind: str               # "instructor" | "cohort" | "room" | "capacity" | "lab" | "window" | "blackout" | "placement"
    detail: str


def weekly_load_hours(sections) -> dict:
    """Total weekly teaching hours per instructor id (team-taught counts fully per id)."""
    load: dict = {}
    for s in sections:
        h = sum(b.length for b in s.blocks)
        for iid in s.instructor_ids:
            load[iid] = load.get(iid, 0) + h
    return load

