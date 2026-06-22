from timetabling.settings import build_config, DEFAULT_SETTINGS


def test_build_config_maps_soft_dials_and_free_day_years():
    s = dict(DEFAULT_SETTINGS,
             weights={"maxrun": "max", "instr_days": "off", "room_stable": "normal", "free_day": "high"},
             free_day_years=[3, 4])
    cfg = build_config(s, {}, 60)
    assert cfg.w_maxrun == 20.0 and cfg.w_instr_days == 0.0
    assert cfg.w_room_stable == 10.0 and cfg.w_free_day == 15.0
    assert cfg.free_day_year_levels == (3, 4)
    assert cfg.w_idle == 15.0                       # fixed, not from UI
