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
    grad_start_by_dept: tuple = ()          # ((dept_code, hour), ...) earliest-start exceptions
    max_consecutive_hours: int = 3          # soft maxrun threshold (cumulative back-to-back)
    max_instr_days: int = 5                 # soft instr_days target: penalize an instructor's
                                            # teaching-days beyond this (5 = off; UI dial 5/3/1)
    free_day_year_levels: tuple = ()        # cohort year-levels that want >=1 empty day
    # soft weights (normalized objective; absolute values are relative-preference only)
    w_idle: float = 15.0                    # always-on student idle gaps (fixed, not a dial)
    w_maxrun: float = 10.0                  # dial: anti-fatigue consecutive runs
    w_room_stable: float = 10.0             # dial: per-section room stability
    w_free_day: float = 10.0                # dial: year-scoped free day
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
    include_grad: bool = True
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
    # The four UI-toggle weights are absolute numbers, but the UI presents them on a uniform
    # 0-1 preference scale (settings.WEIGHT_LEVELS x UI_REF); "normal" = 0.5 x 20 = 10, the
    # same for all four (no hidden per-term priority). The repair polish (soft_search) divides
    # each by its solve-time baseline, so only their RATIOS matter there; model_cpsat (<=50
    # path) uses them as absolute coefficients alongside w_order/w_englab/w_cohort_conflict.
    w_cohort_gap: float = 10.0
    w_order: int = 1
    w_englab: int = 1
    eng_lab_days: tuple = ("Th", "Fr")
    eng_faculty_match: str = "Engineering"
    w_nonadjacent: int = 0
    w_instr_days: float = 10.0
    w_parttime_days: float = 14.0
    # apply cohort-conflict soft shaping in the repair greedy construction
    # (default on; --no-soft-shaping turns it off for baseline A/B runs)
    soft_shaping_in_repair: bool = True
    # run the post-convergence move-based SOFT-POLISH (soft_search.anneal_soft) that re-seats
    # already-placed blocks to lower the normalized weighted-sum soft objective (idle/maxrun/
    # instr_days/room_stable/free_day) under a conf no-regress guard. Default ON: the move-based
    # local search measurably steers the surviving dials at scale (steerability gate, 2026-06-22)
    # while never regressing placement (accept guard) or conf. Bounded by the repair deadline.
    soft_polish_in_repair: bool = True
    # move-based soft polish (soft_search.anneal_soft): acceptor + its single parameter.
    soft_polish_acceptor: str = "deluge"      # schc | lahc | deluge | sa (deluge wins full Fall+Spring A/B, measured 2026-06-23)
    soft_polish_counter_limit: int = 5000     # SCHC counter / LAHC history length
    soft_polish_seed: int = 0
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

    def grad_start_for(self, dept_code: str) -> int:
        for d, h in self.grad_start_by_dept:
            if d == dept_code:
                return h
        return self.grad_start
