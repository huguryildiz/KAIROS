from __future__ import annotations
from typing import Dict
import pandas as pd

from .config import Config, LAB_SUFFIXES
from .model import Room, Instructor
from .textnorm import normalize_staff_id, normalize_name, parse_int


def classify_room(name: str) -> bool:
    n = str(name).strip().upper()
    return any(n.endswith(suf) for suf in LAB_SUFFIXES)


def build_rooms(classrooms_df: pd.DataFrame, cfg: Config) -> Dict[str, Room]:
    rooms: Dict[str, Room] = {}
    for _, row in classrooms_df.iterrows():
        name = row["ROOM"].strip()
        if not name:
            continue
        cap = parse_int(row["ROOM_CAP"], default=0)
        is_physical = name != cfg.online_room
        rooms[name] = Room(room=name, cap=cap, is_lab=classify_room(name),
                           is_physical=is_physical, is_virtual=(name == cfg.online_room))
    for cap, count in cfg.extra_rooms:
        for i in range(1, count + 1):
            name = f"AMFI-{cap}-{i}"
            rooms[name] = Room(room=name, cap=int(cap), is_lab=False, is_physical=True)
    return rooms


def build_instructors(lecturers_df: pd.DataFrame) -> Dict[str, Instructor]:
    instr: Dict[str, Instructor] = {}
    for _, row in lecturers_df.iterrows():
        sid = normalize_staff_id(row["Staff_ID"])
        if not sid:
            continue
        instr[sid] = Instructor(
            staff_id=sid,
            name=normalize_name(row["Name"]),
            is_staff=str(row["Is_Staff"]).strip().lower() == "true",
            home_dept=str(row["Dept"]).strip(),
        )
    return instr
