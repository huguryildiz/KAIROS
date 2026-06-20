from __future__ import annotations
from collections import defaultdict
from typing import Dict, List

DAYS_ORDER = ["Mo", "Tu", "We", "Th", "Fr"]


def build_week_grid(schedule: dict, hour_lo: int = 9, hour_hi: int = 21) -> Dict:
    grid: Dict = defaultdict(list)
    for a in schedule.get("assignments", []):
        day = a.get("day")
        start = int(a.get("start", 0))
        end = int(a.get("end", 0))
        for h in range(max(start, hour_lo), min(end, hour_hi)):
            grid[(day, h)].append(a)
    return dict(grid)


def filter_assignments(schedule: dict, field: str, value: str) -> dict:
    items = schedule.get("assignments", [])
    if value in (None, ""):
        out = list(items)
    else:
        out = [a for a in items if str(a.get(field)) == str(value)]
    return {**schedule, "assignments": out}


def distinct_values(schedule: dict, field: str) -> List[str]:
    vals = {str(a.get(field)) for a in schedule.get("assignments", []) if a.get(field)}
    return sorted(vals)
