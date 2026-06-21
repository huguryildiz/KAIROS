"""Tests for the pure School-Settings layer (settings.py): the Settings dict, its
mapping into Config, availability closed-slots, weight presets, and profile JSON."""
from timetabling.settings import (build_config, DEFAULT_SETTINGS, WEIGHT_PRESETS,
                                  availability_closed_slots, profile_to_json,
                                  profile_from_json)


def test_default_settings_build_config_matches_today():
    """Unconfigured settings must reproduce today's Config defaults exactly."""
    cfg = build_config(DEFAULT_SETTINGS, {}, 3000.0)
    assert cfg.horizon_start == 9
    assert cfg.undergrad_end == 18
    assert cfg.friday_blackout == (("Fr", 13),)
    assert cfg.seminar_blackout == (("Th", 14), ("Th", 15))
    assert cfg.saturday_enabled is False
    assert cfg.include_grad is False
    assert cfg.midday_split_hour == 13
    assert cfg.max_theory_session == 2
    assert cfg.max_block_len == 4
    assert cfg.w_evening == 10
    assert cfg.w_cohort_conflict == 50
    assert cfg.w_cohort_gap == 3
    assert cfg.w_room_count == 2
    assert cfg.w_instr_days == 3
    assert cfg.w_parttime_days == 5
    assert cfg.w_instr_daily_overload == 0
    assert cfg.solve_time_limit_s == 3000.0
    assert cfg.repair_time_limit_s == 3000.0
    assert cfg.instr_unavailable == frozenset()


# --- Block 2: policy mapping ------------------------------------------------

def test_policy_fields_map():
    s = dict(DEFAULT_SETTINGS, day_start=8, day_end=17, saturday=True,
             include_grad=True, midday_split=12, max_theory_session=3, max_block_len=3)
    cfg = build_config(s, {}, 60.0)
    assert cfg.horizon_start == 8
    assert cfg.undergrad_end == 17
    assert cfg.saturday_enabled is True
    assert cfg.include_grad is True
    assert cfg.midday_split_hour == 12
    assert cfg.max_theory_session == 3
    assert cfg.max_block_len == 3


def test_blackout_split():
    s = dict(DEFAULT_SETTINGS, blackouts=[["Fr", 13, False], ["We", 10, True]])
    cfg = build_config(s, {}, 60.0)
    assert cfg.friday_blackout == (("Fr", 13),)
    assert cfg.seminar_blackout == (("We", 10),)


def test_daily_hours_cap():
    off = build_config(dict(DEFAULT_SETTINGS, daily_hours_cap=0), {}, 60.0)
    assert off.w_instr_daily_overload == 0
    on = build_config(dict(DEFAULT_SETTINGS, daily_hours_cap=4), {}, 60.0)
    assert on.max_instr_daily_hours == 4
    assert on.w_instr_daily_overload == 5


def test_clamp_guard():
    # midday outside (day_start, day_end) falls back to a sane value, never raises
    s = dict(DEFAULT_SETTINGS, day_start=9, day_end=18, midday_split=20)
    cfg = build_config(s, {}, 60.0)
    assert 9 < cfg.midday_split_hour < 18


# --- Block 3: weight presets ------------------------------------------------

def test_weight_presets_off_and_strong():
    off = build_config(dict(DEFAULT_SETTINGS, weights={
        "evening": "off", "cohort_gap": "off", "room_count": "off", "instr_days": "off"}),
        {}, 60.0)
    assert (off.w_evening, off.w_cohort_gap, off.w_room_count,
            off.w_instr_days, off.w_parttime_days) == (0, 0, 0, 0, 0)
    strong = build_config(dict(DEFAULT_SETTINGS, weights={
        "evening": "strong", "cohort_gap": "strong", "room_count": "strong",
        "instr_days": "strong"}), {}, 60.0)
    assert (strong.w_evening, strong.w_cohort_gap, strong.w_room_count,
            strong.w_instr_days, strong.w_parttime_days) == (30, 8, 6, 8, 10)


def test_weight_presets_normal_parttime_offset():
    cfg = build_config(DEFAULT_SETTINGS, {}, 60.0)
    assert cfg.w_instr_days == 3 and cfg.w_parttime_days == 5


# --- Block 7: availability closed-slots -------------------------------------

def test_availability_closed_slots():
    cs = {"day_start": 9, "midday_split": 13}
    am = availability_closed_slots({"a@x": [["Mo", "AM"]]}, cs)
    assert ("a@x", "Mo", 9) in am and ("a@x", "Mo", 12) in am
    assert ("a@x", "Mo", 13) not in am
    pm = availability_closed_slots({"a@x": [["Tu", "PM"]]}, cs)
    assert ("a@x", "Tu", 13) in pm and ("a@x", "Tu", 20) in pm
    assert ("a@x", "Tu", 12) not in pm


def test_availability_empty():
    assert availability_closed_slots({}, {"day_start": 9, "midday_split": 13}) == frozenset()


# --- Block 8: profile JSON --------------------------------------------------

def test_profile_roundtrip():
    s, a = profile_from_json(profile_to_json(DEFAULT_SETTINGS, {"x@y": [["Mo", "AM"]]}))
    assert s == DEFAULT_SETTINGS
    assert a == {"x@y": [["Mo", "AM"]]}


def test_profile_partial_merges_defaults():
    s, a = profile_from_json('{"settings": {"day_start": 8}, "availability": {}}')
    assert s["day_start"] == 8
    assert s["day_end"] == DEFAULT_SETTINGS["day_end"]
    assert s["weights"] == DEFAULT_SETTINGS["weights"]
    assert a == {}
