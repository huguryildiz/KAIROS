from timetabling.ui_input import cohort_from_code, is_part_time, parse_emails


def test_cohort_from_code():
    assert cohort_from_code("CMPE 113") == ("CMPE", "1", "CMPE-1")
    assert cohort_from_code("ADA403") == ("ADA", "4", "ADA-4")
    assert cohort_from_code("???") == ("UNK", "0", "UNK-0")


def test_is_part_time():
    assert is_part_time("B. Demir (S)") is True
    assert is_part_time("A. Yilmaz") is False


def test_parse_emails():
    assert parse_emails("a@x.edu, b@x.edu") == ["a@x.edu", "b@x.edu"]
    assert parse_emails("  ") == []


from timetabling.config import Config
from timetabling.ui_input import (
    build_sections_from_courselist, build_instructors_from_courselist,
    build_rooms_from_ui,
)

_ROWS = [
    {"Course Code": "CMPE 113", "Course Name": "Intro", "Section No": "01",
     "T": "3", "P": "0", "L": "2", "Lecturer Name": "A. Yilmaz",
     "Lecturer Email": "a@x.edu", "~Students": "40"},
    {"Course Code": "MATH 101", "Course Name": "Calc", "Section No": "02",
     "T": "4", "P": "0", "L": "0", "Lecturer Name": "B. Demir (S)",
     "Lecturer Email": "", "~Students": "30"},
]


def test_build_sections_from_courselist():
    secs, rep = build_sections_from_courselist(_ROWS, "001", Config())
    s0 = secs[0]
    assert s0.section_id == "CMPE 113_01"
    assert s0.cohort_key == "CMPE-1"
    assert s0.instructor_ids == ["a@x.edu"]
    assert s0.students == 40
    assert any("#L" in b.block_id for b in s0.blocks)   # lab block exists
    assert rep["missing_email"] == 1                    # MATH row has blank email


def test_build_instructors_part_time():
    instr = build_instructors_from_courselist(_ROWS)
    assert instr["a@x.edu"].is_staff is True
    # B. Demir has a blank email -> not keyed; full-timeness asserted via a present email
    rows = [{"Lecturer Name": "C (S)", "Lecturer Email": "c@x.edu", "Course Code": "EE 201"}]
    instr2 = build_instructors_from_courselist(rows)
    assert instr2["c@x.edu"].is_staff is False


def test_build_rooms_adds_online_virtual():
    rooms = build_rooms_from_ui([{"Room": "A301", "Cap": "60", "Lab": ""}], Config())
    assert rooms["A301"].cap == 60 and rooms["A301"].is_lab is False
    assert rooms["Online"].is_virtual is True


from timetabling.ui_input import validate_courselist
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline


def test_validate_courselist_flags_problems():
    # now returns (code, kwargs) tuples for i18n rendering
    warns = validate_courselist(_ROWS)
    codes = [c for c, _ in warns]
    assert "warn_blank_email" in codes
    assert ("info_part_time", {"n": 1}) in warns


def test_validate_courselist_missing_column():
    warns = validate_courselist([{"Course Code": "X 101"}])
    assert warns[0][0] == "warn_missing_cols"
    assert "Section No" in warns[0][1]["cols"]


def test_ui_inputs_feed_run_pipeline():
    cfg = Config(solve_time_limit_s=10.0)
    secs, _ = build_sections_from_courselist(_ROWS, "001", cfg)
    instr = build_instructors_from_courselist(_ROWS)
    rooms = build_rooms_from_ui(
        [{"Room": "A301", "Cap": "100", "Lab": ""},
         {"Room": "LAB1", "Cap": "40", "Lab": "x"}], cfg)
    mark_virtual(secs, rooms, cfg)
    res = run_pipeline("001", secs, rooms, instr, cfg, solver="cpsat")
    assert res.violations == []
    assert len(res.assignments) >= 2   # at least the two sections' blocks placed


# --- Phase 4: optional Year + Part-time columns ---------------------------

def test_year_column_overrides_cohort_year():
    rows = [{"Course Code": "CMPE 113", "Section No": "01", "T": "3", "P": "0",
             "L": "0", "Lecturer Email": "a@x.edu", "~Students": "10", "Year": "2"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].cohort_key == "CMPE-2"   # code parses year 1; Year column wins


def test_year_column_absent_falls_back_to_code():
    secs, _ = build_sections_from_courselist(_ROWS, "001", Config())
    assert secs[0].cohort_key == "CMPE-1"   # no Year column -> derived from code


def test_parttime_column_overrides_S_marker():
    rows = [{"Course Code": "EE 201", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Lecturer Name": "A. Yilmaz", "Lecturer Email": "a@x.edu", "Part-time": "yes"}]
    instr = build_instructors_from_courselist(rows)
    assert instr["a@x.edu"].is_staff is False   # column says part-time despite no (S)


def test_parttime_falls_back_to_S_when_column_absent():
    rows = [{"Course Code": "EE 201", "Lecturer Name": "B (S)", "Lecturer Email": "b@x.edu"}]
    instr = build_instructors_from_courselist(rows)
    assert instr["b@x.edu"].is_staff is False


# --- Phase 4: Room Type column --------------------------------------------

def test_room_type_requires_lab():
    rows = [{"Course Code": "X 101", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Lecturer Email": "a@x.edu", "Room Type": "computer-lab"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].requires_lab_room is True


def test_room_type_regular_or_blank_no_lab():
    for val in ("", "regular", "classroom", "normal"):
        rows = [{"Course Code": "X 101", "Section No": "01", "T": "3", "P": "0", "L": "0",
                 "Lecturer Email": "a@x.edu", "Room Type": val}]
        secs, _ = build_sections_from_courselist(rows, "001", Config())
        assert secs[0].requires_lab_room is False


# --- Phase 4: Fixed column ------------------------------------------------

def test_parse_fixed():
    from timetabling.ui_input import parse_fixed
    assert parse_fixed("Mo 9") == ("Mo", 9)
    assert parse_fixed("Pzt 09:00") == ("Mo", 9)
    assert parse_fixed("Fri 14") == ("Fr", 14)
    assert parse_fixed("") == ("", -1)
    assert parse_fixed("garbage") == ("", -1)
    assert parse_fixed("Mo") == ("", -1)


def test_fixed_column_sets_section_fields():
    rows = [{"Course Code": "X 101", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Lecturer Email": "a@x.edu", "Fixed": "We 10"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].fixed_day == "We" and secs[0].fixed_start == 10
