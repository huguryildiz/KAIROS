"""Pure School-Settings layer: the Settings dict, its mapping into Config, instructor
availability closed-slots, and the download/upload profile JSON. Streamlit-free so it stays
unit-testable. The UI (views/settings.py) only reads/writes the session dicts; this module
turns them into a Config at solve time.

Backward-compatible by construction: DEFAULT_SETTINGS mirrors today's Config defaults, so an
untouched Settings step reproduces the live behavior (same placement, 0 hard violations).
"""
from __future__ import annotations

import copy
import json
from typing import Dict, Tuple

from .config import Config, DAYS, SATURDAY

# Upper bound of the occupancy horizon (Config.horizon_end). Not a settings field — used to
# size the PM availability band. Closing hours past a section's own window is harmless.
_HORIZON_END = 21

# Settings dict schema. Every value mirrors the corresponding Config default, so
# build_config(DEFAULT_SETTINGS, {}, s) == today's Config (on the relevant fields).
DEFAULT_SETTINGS: dict = {
    "day_start": 9,            # -> Config.horizon_start
    "day_end": 18,            # -> Config.undergrad_end
    "saturday": False,        # -> Config.saturday_enabled
    "include_grad": False,    # -> Config.include_grad
    "grad_start": 18,         # -> Config.grad_start (earliest grad start hour; only used when include_grad)
    "grad_start_by_dept": {}, # -> Config.grad_start_by_dept ({dept_code: hour} earliest-start exceptions)
    "max_theory_session": 2,  # -> Config.max_theory_session
    "max_block_len": 4,       # -> Config.max_block_len
    # [day, hour, staff_only]; staff_only True closes the slot only for full-time staff
    # (e.g. a faculty seminar). Empty by default — closed slots are school-specific and added
    # from the UI blackout editor. Rows map straight to Config.blackout triples.
    "blackouts": [],
    # lunch-break protection: when enabled, [lunch_start, lunch_end) is closed every active
    # day (expanded into universal blackout slots in build_config). Default off so an
    # untouched Settings step reproduces today's Config exactly.
    "lunch_enabled": False,
    "lunch_start": 12,        # inclusive hour
    "lunch_end": 13,          # exclusive hour
    "weights": {              # preset levels, never raw numbers
        "cohort_gap": "normal",
        "instr_days": "normal",
    },
}

# Uniform 0-1 preference scale, identical for all four toggles (normalization removes the
# need for per-term magnitudes — only the relative dial matters). UI_REF lifts the 0-1
# preference to an absolute weight ("normal" 0.5 -> 10), comparable to w_order/w_englab and
# below w_cohort_conflict in the <=50 CP-SAT path; the repair polish normalizes it away.
UI_REF: float = 20.0
WEIGHT_LEVELS: dict = {"off": 0.0, "low": 0.25, "normal": 0.5, "high": 0.75, "max": 1.0}


def default_settings() -> dict:
    """A fresh deep copy of DEFAULT_SETTINGS (safe to mutate in session_state)."""
    return copy.deepcopy(DEFAULT_SETTINGS)


def _int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def availability_closed_slots(availability: Dict[str, list], settings: dict) -> frozenset:
    """Turn {email: [[day, slot], ...]} into a frozenset of (email, day, hour) closed
    slots. `slot` is an hour int (e.g. 9 → blocks 09:00–10:00) for the current hourly
    picker, or the legacy half-day code "AM"/"PM" (AM = [day_start, midday_split);
    PM = [midday_split, _HORIZON_END)) — both are accepted so older profiles still load."""
    if not availability:
        return frozenset()
    s = settings or {}
    day_start = _int(s.get("day_start"), 9)
    midday = 13
    out = set()
    for email, slots in availability.items():
        for entry in slots or []:
            try:
                day, val = entry[0], entry[1]
            except (TypeError, IndexError):
                continue
            half = str(val).upper()
            if half == "AM":
                hours = range(day_start, midday)
            elif half == "PM":
                hours = range(midday, _HORIZON_END)
            else:
                try:
                    hours = (int(val),)
                except (TypeError, ValueError):
                    continue
            for h in hours:
                out.add((email, day, h))
    return frozenset(out)


def _preset(weights: dict, knob: str) -> float:
    """Map a knob's 0-1 preference level to an absolute weight (UI_REF x level). Uniform
    across all four toggles."""
    lvl = weights.get(knob, "normal")
    return round(UI_REF * WEIGHT_LEVELS.get(lvl, WEIGHT_LEVELS["normal"]), 1)


def build_config(settings: dict, availability: Dict[str, list],
                 solve_seconds: float) -> Config:
    """Map a Settings dict + availability into a Config. Never raises on bad input — every
    field falls back to its default and the solve proceeds."""
    s = settings or {}

    # window guard
    day_start = _int(s.get("day_start"), 9)
    day_end = _int(s.get("day_end"), 18)
    if not (0 <= day_start < day_end <= _HORIZON_END):
        day_start, day_end = 9, 18

    # graduate earliest-start hour. Grad sessions still end by Config.grad_end (21:00); only
    # the start floor is user-tunable so daytime grad classes are allowed. Must sit in
    # [day_start, grad_end); falls back to 18 (today's behavior) on bad input.
    grad_start = _int(s.get("grad_start"), 18)
    if not (day_start <= grad_start < _HORIZON_END):
        grad_start = 18

    # per-department earliest-start exceptions ({dept_code: hour}). Each hour must sit in
    # [day_start, _HORIZON_END); the dept is upper-cased and deduped. Invalid rows are dropped.
    grad_pairs = {}
    for dept, hour in (s.get("grad_start_by_dept", {}) or {}).items():
        h = _int(hour, -1)
        if day_start <= h < _HORIZON_END:
            grad_pairs[str(dept).strip().upper()] = h

    # blackouts as (day, hour, staff_only) triples — a single list; the scope (everyone vs
    # full-time only) rides on the third field, so there is no separate seminar field.
    blackout_rows = []
    for row in s.get("blackouts", []):
        try:
            day, hour, staff_only = str(row[0]), int(row[1]), bool(row[2])
        except (TypeError, ValueError, IndexError):
            continue
        blackout_rows.append((day, hour, staff_only))

    # lunch-break protection -> universal (staff_only=False) daily window over every active day
    if bool(s.get("lunch_enabled", False)):
        l0 = _int(s.get("lunch_start"), 12)
        l1 = _int(s.get("lunch_end"), 13)
        if 0 <= l0 < l1 <= _HORIZON_END:
            active_days = list(DAYS) + ([SATURDAY] if bool(s.get("saturday", False)) else [])
            for d in active_days:
                for h in range(l0, l1):
                    blackout_rows.append((d, h, False))
    blackout_rows = list(dict.fromkeys(blackout_rows))   # dedupe, preserve order

    # preference weights
    weights = s.get("weights", {}) or {}
    w_instr = _preset(weights, "instr_days")
    w_parttime = round(w_instr + 4, 1) if w_instr else 0.0

    closed = availability_closed_slots(
        availability, {"day_start": day_start})

    return Config(
        horizon_start=day_start,
        undergrad_end=day_end,
        saturday_enabled=bool(s.get("saturday", False)),
        include_grad=bool(s.get("include_grad", False)),
        grad_start=grad_start,
        grad_start_by_dept=tuple(grad_pairs.items()),
        max_theory_session=_int(s.get("max_theory_session"), 2),
        max_block_len=_int(s.get("max_block_len"), 4),
        blackout=tuple(blackout_rows),
        w_cohort_gap=_preset(weights, "cohort_gap"),
        w_instr_days=w_instr,
        w_parttime_days=w_parttime,
        instr_unavailable=closed,
        solve_time_limit_s=float(solve_seconds),
        repair_time_limit_s=float(solve_seconds),
    )


def profile_to_json(settings: dict, availability: Dict[str, list]) -> str:
    """Serialize a school profile (settings + availability) for download."""
    return json.dumps({"settings": settings, "availability": availability},
                      ensure_ascii=False, indent=2)


def profile_from_json(text: str) -> Tuple[dict, Dict[str, list]]:
    """Parse an uploaded profile, merging known keys onto DEFAULT_SETTINGS so a partial or
    older file is safe. Returns (settings, availability)."""
    data = json.loads(text)
    s = default_settings()
    incoming = data.get("settings", {}) if isinstance(data, dict) else {}
    if isinstance(incoming, dict):
        for k, v in incoming.items():
            if k in DEFAULT_SETTINGS:
                s[k] = v
        if isinstance(incoming.get("weights"), dict):
            s["weights"] = {**DEFAULT_SETTINGS["weights"], **incoming["weights"]}
    avail = data.get("availability", {}) if isinstance(data, dict) else {}
    if not isinstance(avail, dict):
        avail = {}
    return s, avail
