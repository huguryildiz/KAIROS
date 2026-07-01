from views import upload as upload_view


class _FakeStreamlit:
    def __init__(self):
        self.session_state = {}


def test_ingest_fires_courses_uploaded_event(monkeypatch, tmp_path):
    fake = _FakeStreamlit()
    monkeypatch.setattr(upload_view, "st", fake)
    tracked = []
    monkeypatch.setattr(upload_view, "track_event", tracked.append)

    csv_path = tmp_path / "courses.csv"
    csv_path.write_text(
        "Course Code,Course Name,T,P,L,~Students\n"
        "ADA 110,Intro to Data Analytics,3,0,0,40\n"
    )

    upload_view._ingest(str(csv_path))

    assert tracked == ["courses_uploaded"]


def test_ingest_only_fires_once_across_reruns(monkeypatch, tmp_path):
    fake = _FakeStreamlit()
    monkeypatch.setattr(upload_view, "st", fake)
    tracked = []
    monkeypatch.setattr(upload_view, "track_event", tracked.append)

    csv_path = tmp_path / "courses.csv"
    csv_path.write_text(
        "Course Code,Course Name,T,P,L,~Students\n"
        "ADA 110,Intro to Data Analytics,3,0,0,40\n"
    )

    upload_view._ingest(str(csv_path))
    upload_view._ingest(str(csv_path))

    assert tracked == ["courses_uploaded", "courses_uploaded"]
