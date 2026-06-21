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

from .config import Config

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
    "midday_split": 13,       # -> Config.midday_split_hour (AM/PM boundary)
    "max_theory_session": 2,  # -> Config.max_theory_session
    "max_block_len": 4,       # -> Config.max_block_len
    # [day, hour, staff_only]; staff_only False -> friday_blackout, True -> seminar_blackout
    "blackouts": [["Fr", 13, False], ["Th", 14, True], ["Th", 15, True]],
    "daily_hours_cap": 0,     # 0 = off; N>0 enables the soft per-(instr,day) overload at N hours
    "weights": {              # preset levels, never raw numbers
        "evening": "normal",
        "cohort_gap": "normal",
        "room_count": "normal",
        "instr_days": "normal",
    },
}

# Plain-language presets -> vetted weight values. Keeps the calibrated relative scale intact.
WEIGHT_PRESETS: dict = {
    "evening":    {"off": 0, "normal": 10, "strong": 30},   # -> w_evening
    "cohort_gap": {"off": 0, "normal": 3,  "strong": 8},    # -> w_cohort_gap
    "room_count": {"off": 0, "normal": 2,  "strong": 6},    # -> w_room_count
    "instr_days": {"off": 0, "normal": 3,  "strong": 8},    # -> w_instr_days (+2 -> w_parttime_days)
}


def default_settings() -> dict:
    """A fresh deep copy of DEFAULT_SETTINGS (safe to mutate in session_state)."""
    return copy.deepcopy(DEFAULT_SETTINGS)


def _int(v, default: int) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default


def availability_closed_slots(availability: Dict[str, list], settings: dict) -> frozenset:
    """Turn {email: [[day, "AM"|"PM"], ...]} into a frozenset of (email, day, hour) closed
    slots. AM = [day_start, midday_split); PM = [midday_split, _HORIZON_END)."""
    if not availability:
        return frozenset()
    s = settings or {}
    day_start = _int(s.get("day_start"), 9)
    midday = _int(s.get("midday_split"), 13)
    out = set()
    for email, slots in availability.items():
        for entry in slots or []:
            try:
                day, half = entry[0], str(entry[1]).upper()
            except (TypeError, IndexError):
                continue
            if half == "AM":
                hours = range(day_start, midday)
            elif half == "PM":
                hours = range(midday, _HORIZON_END)
            else:
                continue
            for h in hours:
                out.add((email, day, h))
    return frozenset(out)


def _preset(weights: dict, knob: str) -> int:
    table = WEIGHT_PRESETS[knob]
    return table.get(weights.get(knob, "normal"), table["normal"])


def build_config(settings: dict, availability: Dict[str, list],
                 solve_seconds: float) -> Config:
    """Map a Settings dict + availability into a Config. Never raises on bad input — every
    field falls back to its default and the solve proceeds."""
    s = settings or {}

    # window + midday guard (keep day_start < midday < day_end <= horizon)
    day_start = _int(s.get("day_start"), 9)
    day_end = _int(s.get("day_end"), 18)
    if not (0 <= day_start < day_end <= _HORIZON_END):
        day_start, day_end = 9, 18
    midday = _int(s.get("midday_split"), 13)
    if not (day_start < midday < day_end):
        midday = 13 if day_start < 13 < day_end else (day_start + day_end) // 2

    # blackouts split by the staff_only flag
    universal, staff = [], []
    for row in s.get("blackouts", []):
        try:
            day, hour, staff_only = str(row[0]), int(row[1]), bool(row[2])
        except (TypeError, ValueError, IndexError):
            continue
        (staff if staff_only else universal).append((day, hour))

    # preference weights
    weights = s.get("weights", {}) or {}
    w_instr = _preset(weights, "instr_days")
    w_parttime = w_instr + 2 if w_instr else 0

    # instructor daily-hours soft cap
    cap = _int(s.get("daily_hours_cap"), 0)
    if cap > 0:
        daily_cap, overload_w = cap, 5
    else:
        daily_cap, overload_w = 4, 0   # 4 = Config default; weight 0 = off (today)

    closed = availability_closed_slots(
        availability, {"day_start": day_start, "midday_split": midday})

    return Config(
        horizon_start=day_start,
        undergrad_end=day_end,
        saturday_enabled=bool(s.get("saturday", False)),
        include_grad=bool(s.get("include_grad", False)),
        midday_split_hour=midday,
        max_theory_session=_int(s.get("max_theory_session"), 2),
        max_block_len=_int(s.get("max_block_len"), 4),
        friday_blackout=tuple(universal),
        seminar_blackout=tuple(staff),
        w_evening=_preset(weights, "evening"),
        w_cohort_gap=_preset(weights, "cohort_gap"),
        w_room_count=_preset(weights, "room_count"),
        w_instr_days=w_instr,
        w_parttime_days=w_parttime,
        max_instr_daily_hours=daily_cap,
        w_instr_daily_overload=overload_w,
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
