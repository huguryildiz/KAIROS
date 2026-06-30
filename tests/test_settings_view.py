from views import settings as settings_view


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {"courses": [], "set_rev": 0}
        self.multiselect_calls = []

    def multiselect(self, *args, **kwargs):
        self.multiselect_calls.append((args, kwargs))
        return []


class _FakeAvoidPairsStreamlit:
    def __init__(self):
        self.session_state = {
            "set_rev": 0,
            "courses": [
                {"Course Code": "ADA 110", "Course Name": "Statistics for Analytics"},
                {"Course Code": "ADA 312", "Course Name": "Statistical Learning"},
            ],
        }

    def caption(self, *args, **kwargs):
        return None

    def columns(self, spec, **kwargs):
        return [self for _ in spec]

    def selectbox(self, label, options, **kwargs):
        return list(options)[0]

    def button(self, *args, **kwargs):
        return False

    def markdown(self, *args, **kwargs):
        return None

    def container(self, *args, **kwargs):
        return self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def rerun(self):
        raise AssertionError("rerun should only happen after a button click")


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


def test_avoid_pairs_existing_rules_do_not_rerun_without_click(monkeypatch):
    fake = _FakeAvoidPairsStreamlit()
    monkeypatch.setattr(settings_view, "st", fake)

    settings_view._avoid_pairs("en", {"avoid_pairs": [["ADA 110", "ADA 312"]]})
