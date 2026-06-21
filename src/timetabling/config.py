from __future__ import annotations
from dataclasses import dataclass

DAYS = ["Mo", "Tu", "We", "Th", "Fr"]
SATURDAY = "Sa"

LAB_SUFFIXES = ("-PC-L", "-PSY-L", "-PSCG-L", "-PECE-L", "-EF-L", "-PC", "-L")


@dataclass
class Config:
    # time model
    horizon_start: int = 9        # first start hour
    horizon_end: int = 21         # exclusive end of last occupancy slot (20-21)
    undergrad_end: int = 18       # undergrad blocks must end by this hour
    grad_start: int = 18
    grad_end: int = 21
    # blackouts: (day, hour, staff_only) hour-slots that are closed. staff_only=True closes
    # the slot only for sections taught by a full-time instructor (e.g. a faculty seminar);
    # staff_only=False (or a bare 2-tuple) closes it for everyone. Use
    # cfg.closed_hours(has_staff) to resolve to the (day, hour) set for a given section.
    # Empty by default — closed slots are school-specific, supplied via the UI blackout
    # editor or an explicit Config (e.g. a Fri lunch hour, or a Thu full-time-only seminar).
    blackout: tuple = ()
    # per-instructor unavailability (UI School-Settings populates this; CLI leaves it empty).
    # frozenset of (instructor_id/email, day, hour) — read in gen_candidates like a per-id blackout.
    instr_unavailable: frozenset = frozenset()
    # AM/PM boundary hour for half-day instructor availability (UI setting)
    midday_split_hour: int = 13
    # toggles
    saturday_enabled: bool = False
    include_grad: bool = False
    include_plan_only: bool = False
    excluded_categories: tuple = ("Internship",)
    online_room: str = "Online"
    # solver
    solve_time_limit_s: float = 60.0
    # overall wall-clock budget for the repair solver (UI sets this; CLI leaves it
    # unbounded so the documented full-period benchmark runs to convergence — the repair
    # solver still manages its own per-round budget and ignores --time-limit).
    repair_time_limit_s: float = float("inf")
    max_rooms_per_block: int = 12   # best-fit: only the K smallest fitting rooms per block
    # phase 2: block splitting
    max_block_len: int = 4
    # undergrad theory distributes into sessions of at most this many hours,
    # each forced onto a different day (T:3 -> 2+1 on two days)
    max_theory_session: int = 2
    # phase 2: oversize -> synthetic large halls, list of (cap, count)
    extra_rooms: tuple = ()
    # phase 2: cohort daily-compactness applies to these year levels
    compact_cohort_years: tuple = (2, 3, 4)
    # phase 2 soft weights
    w_cohort_conflict: int = 50  # soft cohort (student course-conflict); high but not hard
    w_cohort_gap: int = 3
    w_order: int = 1
    w_englab: int = 1
    eng_lab_days: tuple = ("Th", "Fr")
    eng_faculty_match: str = "Engineering"
    w_nonadjacent: int = 0
    # objective weights (light)
    w_evening: int = 10
    w_room_count: int = 2
    w_instr_days: int = 3
    w_parttime_days: int = 5
    # soft: penalize each teaching-hour beyond this many per (instructor, day).
    # 0 = disabled (opt-in). A hard cap is INFEASIBLE: ~19 instructors carry
    # >20h/week (service courses) and cannot fit 5 days at 4h. See TODO.md.
    max_instr_daily_hours: int = 4
    w_instr_daily_overload: int = 0
    # soft: penalize each distinct teaching DAY beyond this many per instructor per week.
    # 0 = disabled (opt-in). Soft, never hard — a tight cap would be INFEASIBLE for
    # high-load instructors. Distinct from w_instr_days (which minimizes days outright);
    # this only penalizes days *beyond* the cap.
    max_instr_weekly_days: int = 5
    w_instr_weekly_overload: int = 0
    # exempt high-load instructors (e.g. Basic Sciences service courses): apply the
    # overload penalty only to instructors whose total weekly teaching load is at most
    # this many hours. 0 = no exemption (penalize everyone).
    overload_exempt_weekly: int = 16
    # apply evening + cohort-conflict soft shaping in the repair greedy construction
    # (default on; --no-soft-shaping turns it off for baseline A/B runs)
    soft_shaping_in_repair: bool = True
    evening_from_hour: int = 17   # an hour-slot >= this counts as "evening" for the soft penalty

    def days(self) -> list:
        return DAYS + [SATURDAY] if self.saturday_enabled else list(DAYS)

    def closed_hours(self, has_staff: bool) -> set:
        """Resolve `blackout` to the set of closed (day, hour) slots for a section, given
        whether it is taught by a full-time instructor. staff_only entries apply only when
        has_staff. Bare 2-tuples are treated as universal (staff_only=False)."""
        out = set()
        for entry in self.blackout:
            day, hour = entry[0], entry[1]
            staff_only = bool(entry[2]) if len(entry) > 2 else False
            if staff_only and not has_staff:
                continue
            out.add((day, hour))
        return out
