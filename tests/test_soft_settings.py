from timetabling.settings import build_config, DEFAULT_SETTINGS, profile_from_json


def test_build_config_maps_soft_dials_and_free_day_years():
    s = dict(DEFAULT_SETTINGS,
             weights={"maxrun": "high", "instr_days": "low", "room_stable": "medium", "free_day": "high"},
             free_day_years=[3, 4])
    cfg = build_config(s, {}, 60)
    assert cfg.w_maxrun == 20.0 and cfg.w_instr_days == 5.0
    assert cfg.w_room_stable == 10.0 and cfg.w_free_day == 20.0
    assert cfg.free_day_year_levels == (3, 4)
    assert cfg.w_idle == 15.0                       # fixed, not from UI


def test_build_config_three_levels_map_to_5_10_20():
    for lvl, expect in (("low", 5.0), ("medium", 10.0), ("high", 20.0)):
        cfg = build_config(dict(DEFAULT_SETTINGS, weights={"maxrun": lvl}), {}, 60)
        assert cfg.w_maxrun == expect


def test_default_settings_medium_maps_to_todays_default():
    cfg = build_config(DEFAULT_SETTINGS, {}, 60)
    assert cfg.w_maxrun == 10.0 and cfg.w_room_stable == 10.0  # medium == 10, unchanged from before


def test_unknown_priority_falls_back_to_medium():
    cfg = build_config(dict(DEFAULT_SETTINGS, weights={"maxrun": "bogus"}), {}, 60)
    assert cfg.w_maxrun == 10.0


def test_legacy_5level_profile_migrates_to_three():
    # off/low -> low(5), normal -> medium(10), high/max -> high(20)
    text = ('{"settings": {"weights": '
            '{"maxrun": "max", "instr_days": "off", "room_stable": "normal", "free_day": "high"}}}')
    s, _ = profile_from_json(text)
    cfg = build_config(s, {}, 60)
    assert cfg.w_maxrun == 20.0        # max -> high
    assert cfg.w_instr_days == 5.0     # off -> low
    assert cfg.w_room_stable == 10.0   # normal -> medium
    assert cfg.w_free_day == 20.0      # high -> high
