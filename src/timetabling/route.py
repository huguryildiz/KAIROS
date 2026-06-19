from __future__ import annotations
from typing import Dict, List

from .config import Config
from .model import Room, Section


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
