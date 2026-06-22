from views.settings import _expand_blackout


def test_expand_blackout_multi_day_hour_range():
    out = _expand_blackout(["Mo", "Fr"], 13, 17, False)   # 13..16 inclusive -> 4 hours x 2 days
    assert len(out) == 8
    assert ["Fr", 16, False] in out and ["Mo", 13, False] in out
    assert ["Fr", 17, False] not in out                   # end exclusive
