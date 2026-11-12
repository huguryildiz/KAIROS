from timetabling.ui_style import idle_guard_js


def test_idle_guard_uses_limit_and_redirect():
    js = idle_guard_js(15, "tr")

    # 15 minutes in milliseconds, redirect target and language
    assert ">=900000" in js
    assert "/idle.html?lang=" in js
    assert "__kIdleLang='tr'" in js


def test_idle_guard_holds_during_solve():
    js = idle_guard_js(15, "en")

    # A running solve must reset the idle clock
    assert ".solve-running" in js


def test_idle_guard_check_interval_scales_for_short_limits():
    js = idle_guard_js(0.1, "en")

    # 6 s limit -> checks every 1.5 s, not every 15 s
    assert "},1500);" in js
