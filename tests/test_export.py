import json
from datetime import datetime
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import export


def test_build_schedule_dict_schema(tmp_path):
    s = Section("ADA 403_01", "001", "ADA 403", "EDA", 4, "ADA", "Fac", "ADA-4",
                ["i1"], 24, 3, 0, 0, 3, "Course")
    s.blocks = [Block("ADA 403_01#T", "ADA 403_01", "theory", 3, False)]
    rooms = {"G005": Room("G005", 60, False, True)}
    instr = {"i1": Instructor("i1", "Mustafa Kerem Yüksel", True, "ADA")}
    a = [Assignment("ADA 403_01#T", "ADA 403_01", "theory", "G005", "Fr", 13, 16)]
    payload = export.build_schedule_dict("001", a, [s], rooms, instr)
    assert payload["period"] == "001"
    item = payload["assignments"][0]
    assert item["section_id"] == "ADA 403_01"
    assert item["course_code"] == "ADA 403" and item["course_name"] == "EDA"
    assert item["instructor_name"] == "Mustafa Kerem Yüksel"
    assert item["cohort"] == "ADA-4" and item["dept"] == "ADA"
    assert item["department"] == "Fac" and item["day"] == "Fr"
    assert item["start"] == 13 and item["end"] == 16
    assert item["room"] == "G005" and item["room_cap"] == 60 and item["is_lab_room"] is False

    p = tmp_path / "schedule.json"
    export.write_schedule_json(str(p), payload)
    assert json.loads(p.read_text())["assignments"][0]["section_id"] == "ADA 403_01"


def test_write_schedule_outputs_creates_out_json_and_csv_with_timestamp(tmp_path):
    payload = {"period": "001", "meta": {}, "assignments": [
        {"section_id": "ADA 403_01", "course_code": "ADA 403"}
    ]}

    written = export.write_schedule_outputs(
        tmp_path / "out",
        payload,
        period="001",
        generated_at=datetime(2026, 6, 28, 14, 5, 9),
    )

    assert written["json"] == tmp_path / "out" / "schedule_001_20260628_140509.json"
    assert written["csv"] == tmp_path / "out" / "schedule_001_20260628_140509.csv"
    assert json.loads(written["json"].read_text())["assignments"][0]["section_id"] == "ADA 403_01"
    assert written["csv"].read_text(encoding="utf-8-sig").startswith("section_id,course_code")


def test_write_schedule_outputs_can_omit_period_from_filename(tmp_path):
    payload = {"period": "001", "meta": {}, "assignments": []}

    written = export.write_schedule_outputs(
        tmp_path / "out",
        payload,
        period="001",
        generated_at=datetime(2026, 6, 28, 14, 5, 9),
        include_period=False,
    )

    assert written["json"] == tmp_path / "out" / "schedule_20260628_140509.json"
    assert written["csv"] == tmp_path / "out" / "schedule_20260628_140509.csv"
