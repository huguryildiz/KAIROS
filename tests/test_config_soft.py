from timetabling.config import Config


def test_grad_start_for_default_and_override():
    cfg = Config(grad_start=18, grad_start_by_dept=(("PSY", 9), ("ECON", 16)))
    assert cfg.grad_start_for("PSY") == 9
    assert cfg.grad_start_for("ECON") == 16
    assert cfg.grad_start_for("CS") == 18      # falls back to global default


def test_new_soft_weight_defaults():
    cfg = Config()
    assert cfg.max_consecutive_hours == 3
    assert cfg.free_day_year_levels == ()
    assert cfg.w_idle == 15.0
    assert cfg.w_maxrun == 10.0 and cfg.w_room_stable == 10.0 and cfg.w_free_day == 10.0
