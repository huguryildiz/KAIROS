from timetabling import ui_app


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}
        self.html_calls = []

    def html(self, content, **kwargs):
        self.html_calls.append((content, kwargs))


def test_track_event_fires_gtag_via_html(monkeypatch):
    fake = _FakeStreamlit()
    monkeypatch.setattr(ui_app, "st", fake)

    ui_app.track_event("courses_uploaded")

    assert len(fake.html_calls) == 1
    content, kwargs = fake.html_calls[0]
    assert "window.parent.gtag" in content
    assert "'courses_uploaded'" in content
    assert kwargs == {"unsafe_allow_javascript": True}


def test_track_event_dedupes_within_session(monkeypatch):
    fake = _FakeStreamlit()
    monkeypatch.setattr(ui_app, "st", fake)

    ui_app.track_event("solve_clicked")
    ui_app.track_event("solve_clicked")

    assert len(fake.html_calls) == 1


def test_track_event_fires_again_for_a_different_name(monkeypatch):
    fake = _FakeStreamlit()
    monkeypatch.setattr(ui_app, "st", fake)

    ui_app.track_event("solve_clicked")
    ui_app.track_event("solve_completed")

    assert len(fake.html_calls) == 2
