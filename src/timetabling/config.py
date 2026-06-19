from __future__ import annotations
from dataclasses import dataclass

DAYS = ["Mo", "Tu", "We", "Th", "Fr"]
SATURDAY = "Sa"

LAB_SUFFIXES = ("-PC-L", "-PSY-L", "-PSCG-L", "-PECE-L", "-EF-L", "-L")


@dataclass
class Config:
    # time model
    horizon_start: int = 9        # first start hour
    horizon_end: int = 21         # exclusive end of last occupancy slot (20-21)
    undergrad_end: int = 18       # undergrad blocks must end by this hour
    grad_start: int = 18
    grad_end: int = 21
    # blackouts: (day, hour) hour-slots that are closed
    friday_blackout: tuple = (("Fr", 13),)                 # 13:00-14:00
    seminar_blackout: tuple = (("Th", 14), ("Th", 15))     # Thu 14:00-16:00, full-time only
    # toggles
    saturday_enabled: bool = False
    include_grad: bool = False
    include_plan_only: bool = False
    excluded_categories: tuple = ("Internship",)
    online_room: str = "Online"
    # solver
    solve_time_limit_s: float = 60.0
    max_rooms_per_block: int = 12   # best-fit: only the K smallest fitting rooms per block
    # objective weights (light)
    w_evening: int = 4
    w_room_count: int = 2
    w_instr_days: int = 3
    w_parttime_days: int = 5
    evening_from_hour: int = 17   # an hour-slot >= this counts as "evening" for the soft penalty

    def days(self) -> list:
        return DAYS + [SATURDAY] if self.saturday_enabled else list(DAYS)
