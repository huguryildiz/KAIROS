from views import settings as settings_view


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {"courses": [], "set_rev": 0}
        self.multiselect_calls = []

    def multiselect(self, *args, **kwargs):
        self.multiselect_calls.append((args, kwargs))
        return []


def test_grad_by_dept_renders_disabled_when_no_graduate_departments(monkeypatch):
    fake = _FakeStreamlit()
    monkeypatch.setattr(settings_view, "st", fake)

    settings = {}
    settings_view._grad_by_dept("en", settings)

    assert len(fake.multiselect_calls) == 1
    _, kwargs = fake.multiselect_calls[0]
    assert kwargs["disabled"] is True
    assert settings["grad_start_by_dept"] == {}


def test_grad_by_dept_renders_year_override_graduate_departments(monkeypatch):
    fake = _FakeStreamlit()
    fake.session_state["courses"] = [
        {"Course Code": "PSY 101", "Dept": "Psychology", "Year": "5"},
        {"Course Code": "CS 102", "Year": "2"},
    ]
    monkeypatch.setattr(settings_view, "st", fake)

    settings_view._grad_by_dept("en", {})

    assert len(fake.multiselect_calls) == 1
    args, kwargs = fake.multiselect_calls[0]
    assert args[1] == ["PSY"]
    assert kwargs["disabled"] is False
    assert kwargs["format_func"]("PSY") == "PSY · Psychology"
