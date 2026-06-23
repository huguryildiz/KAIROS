"""Tests for the pure School-Settings layer (settings.py): the Settings dict, its
mapping into Config, availability closed-slots, weight presets, and profile JSON."""
from timetabling.settings import (build_config, DEFAULT_SETTINGS, WEIGHT_LEVELS,
                                  availability_closed_slots, profile_to_json,
                                  profile_from_json)


def test_default_settings_build_config_matches_today():
    """Unconfigured settings must reproduce today's Config defaults exactly."""
    cfg = build_config(DEFAULT_SETTINGS, {}, 3000.0)
    assert cfg.horizon_start == 9
    assert cfg.undergrad_end == 18
    assert cfg.blackout == ()
    assert cfg.saturday_enabled is False
    assert cfg.include_grad is False
    assert cfg.midday_split_hour == 13
    assert cfg.max_theory_session == 2
    assert cfg.max_block_len == 4
    # uniform 0-1 UI scale: every "normal" toggle -> 0.5 x UI_REF(20) = 10
    assert cfg.w_cohort_conflict == 50
    assert cfg.w_cohort_gap == 10
    assert cfg.w_instr_days == 10
    assert cfg.w_parttime_days == 14
    assert cfg.solve_time_limit_s == 3000.0
    assert cfg.repair_time_limit_s == 3000.0
    assert cfg.instr_unavailable == frozenset()


# --- Block 2: policy mapping ------------------------------------------------

def test_policy_fields_map():
    s = dict(DEFAULT_SETTINGS, day_start=8, day_end=17, saturday=True,
             include_grad=True, max_theory_session=3, max_block_len=3)
    cfg = build_config(s, {}, 60.0)
    assert cfg.horizon_start == 8
    assert cfg.undergrad_end == 17
    assert cfg.saturday_enabled is True
    assert cfg.include_grad is True
    assert cfg.max_theory_session == 3
    assert cfg.max_block_len == 3


def test_blackout_scope_preserved():
    s = dict(DEFAULT_SETTINGS, blackouts=[["Fr", 13, False], ["We", 10, True]])
    cfg = build_config(s, {}, 60.0)
    assert cfg.blackout == (("Fr", 13, False), ("We", 10, True))
    # universal closes for everyone; staff-only closes only when a staff instructor teaches
    assert cfg.closed_hours(has_staff=False) == {("Fr", 13)}
    assert cfg.closed_hours(has_staff=True) == {("Fr", 13), ("We", 10)}


def test_lunch_off_by_default():
    """Default settings keep lunch off and carry no baked-in blackouts."""
    cfg = build_config(DEFAULT_SETTINGS, {}, 60.0)
    assert cfg.blackout == ()


def test_lunch_expands_to_universal_blackout():
    s = dict(DEFAULT_SETTINGS, lunch_enabled=True, lunch_start=12, lunch_end=13)
    cfg = build_config(s, {}, 60.0)
    universal = cfg.closed_hours(has_staff=False)   # everyone-closed slots
    # every weekday gets 12:00 closed for everyone
    for d in ("Mo", "Tu", "We", "Th", "Fr"):
        assert (d, 12) in universal
    assert ("Sa", 12) not in universal              # Saturday off -> not closed
    assert ("Sa", 12) not in cfg.closed_hours(has_staff=True)


def test_lunch_respects_saturday_and_multi_hour():
    s = dict(DEFAULT_SETTINGS, lunch_enabled=True, lunch_start=12, lunch_end=14,
             saturday=True)
    cfg = build_config(s, {}, 60.0)
    universal = cfg.closed_hours(has_staff=False)
    assert ("Sa", 12) in universal and ("Sa", 13) in universal
    assert ("Mo", 12) in universal and ("Mo", 13) in universal


def test_lunch_bad_window_ignored():
    s = dict(DEFAULT_SETTINGS, lunch_enabled=True, lunch_start=14, lunch_end=12)
    cfg = build_config(s, {}, 60.0)
    assert cfg.blackout == ()   # invalid window -> no lunch slots, no baked-in defaults


def test_clamp_guard():
    # day_start/day_end outside valid range falls back without raising
    s = dict(DEFAULT_SETTINGS, day_start=20, day_end=5)
    cfg = build_config(s, {}, 60.0)
    assert cfg.horizon_start == 9 and cfg.undergrad_end == 18


# --- Block 3: weight presets ------------------------------------------------

def test_weight_presets_off_and_max():
    # legacy 5-level inputs migrate onto the 3-level scale: off -> low(5), max -> high(20)
    off = build_config(dict(DEFAULT_SETTINGS, instr_days_target=3, weights={
        "cohort_gap": "off", "instr_days": "off"}),
        {}, 60.0)
    assert (off.w_cohort_gap, off.w_instr_days, off.w_parttime_days) == (5, 5, 9)
    mx = build_config(dict(DEFAULT_SETTINGS, instr_days_target=3, weights={
        "cohort_gap": "max", "instr_days": "max"}), {}, 60.0)
    assert (mx.w_cohort_gap, mx.w_instr_days, mx.w_parttime_days) == (20, 20, 24)


def test_weight_presets_levels_and_parttime_offset():
    # uniform levels (low/high) and the +4 part-time offset on top of instr_days
    cfg = build_config(dict(DEFAULT_SETTINGS, instr_days_target=3), {}, 60.0)
    assert cfg.w_instr_days == 10 and cfg.w_parttime_days == 14   # medium (default), active target
    lo = build_config(dict(DEFAULT_SETTINGS, weights={"cohort_gap": "low"}), {}, 60.0)
    hi = build_config(dict(DEFAULT_SETTINGS, weights={"cohort_gap": "high"}), {}, 60.0)
    assert lo.w_cohort_gap == 5 and hi.w_cohort_gap == 20


# --- Block 7: availability closed-slots -------------------------------------

def test_availability_closed_slots():
    cs = {"day_start": 9}
    am = availability_closed_slots({"a@x": [["Mo", "AM"]]}, cs)
    assert ("a@x", "Mo", 9) in am and ("a@x", "Mo", 12) in am
    assert ("a@x", "Mo", 13) not in am
    pm = availability_closed_slots({"a@x": [["Tu", "PM"]]}, cs)
    assert ("a@x", "Tu", 13) in pm and ("a@x", "Tu", 20) in pm
    assert ("a@x", "Tu", 12) not in pm


def test_availability_empty():
    assert availability_closed_slots({}, {"day_start": 9}) == frozenset()


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


def test_availability_labels_keyed_by_email_or_name():
    from views.settings import _email_labels
    courses = [
        {"Instructor Name": "A. Yilmaz", "Instructor Email": "a@x.edu"},
        {"Instructor Name": "Mustafa Yuksel (S)", "Instructor Email": ""},
    ]
    labels, label_to_id = _email_labels(courses)
    ids = set(label_to_id.values())
    assert "a@x.edu" in ids                 # email identity when present
    assert "mustafa yuksel" in ids          # normalized-name identity when no email
