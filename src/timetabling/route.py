from __future__ import annotations
from typing import Dict, List

from .config import Config
from .model import Room, Section
from .clean import classify_room


def mark_lab_rooms(sections: List[Section], rooms: Dict[str, Room], cfg: Config) -> List[Section]:
    """Pin each section's lab block to the specific lab room recorded in the Plan
    ROOM (the lab-suffixed token present in our inventory). Sections whose lab is
    held in a regular room (no lab token) keep lab_room='' and their lab block is
    later treated as a normal room block."""
    for s in sections:
        for t in s.plan_room.split():
            if classify_room(t) and t in rooms and rooms[t].is_lab:
                s.lab_room = t
                break
    return sections


def mark_virtual(sections: List[Section], rooms: Dict[str, Room], cfg: Config) -> List[Section]:
    """Route sections with no real classroom to the virtual room: those the
    existing plan delivers as Online, or whose enrollment exceeds the largest
    real (physical, non-virtual) classroom."""
    max_real = max((r.cap for r in rooms.values() if r.is_physical and not r.is_virtual),
                   default=0)
    for s in sections:
        if s.plan_room == cfg.online_room or s.students > max_real:
            s.is_virtual = True
    return sections
