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
     "T": "3", "P": "0", "L": "2", "Instructor Name": "A. Yilmaz",
     "Instructor Email": "a@x.edu", "~Students": "40"},
    {"Course Code": "MATH 101", "Course Name": "Calc", "Section No": "02",
     "T": "4", "P": "0", "L": "0", "Instructor Name": "B. Demir (S)",
     "Instructor Email": "", "~Students": "30"},
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
    rows = [{"Instructor Name": "C (S)", "Instructor Email": "c@x.edu", "Course Code": "EE 201"}]
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


def test_validate_courselist_warns_bad_level():
    # valid cohort (MATH-1) but no 3-digit number -> level undeterminable
    rows = [{"Course Code": "MATH 12", "Section No": "01", "T": "3", "P": "0",
             "L": "0", "Instructor Email": "a@x.edu"}]
    codes = [c for c, _ in validate_courselist(rows)]
    assert "warn_bad_level" in codes
    assert "warn_bad_code" not in codes


def test_validate_courselist_unparseable_code_warns_both():
    rows = [{"Course Code": "???", "Section No": "01", "T": "3", "P": "0",
             "L": "0", "Instructor Email": "a@x.edu"}]
    codes = [c for c, _ in validate_courselist(rows)]
    assert "warn_bad_code" in codes
    assert "warn_bad_level" in codes


def test_validate_courselist_clean_codes_no_level_warning():
    # _ROWS use full codes (CMPE 113, MATH 101) -> levels resolve
    codes = [c for c, _ in validate_courselist(_ROWS)]
    assert "warn_bad_level" not in codes
    assert "warn_bad_code" not in codes


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
             "L": "0", "Instructor Email": "a@x.edu", "~Students": "10", "Year": "2"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].cohort_key == "CMPE-2"   # code parses year 1; Year column wins


def test_year_column_absent_falls_back_to_code():
    secs, _ = build_sections_from_courselist(_ROWS, "001", Config())
    assert secs[0].cohort_key == "CMPE-1"   # no Year column -> derived from code


# --- Dept override column (interoperability for non-conforming code schemes) ---

def test_dept_column_overrides_department_and_cohort():
    rows = [{"Course Code": "1234", "Section No": "01", "T": "3", "P": "0",
             "L": "0", "Instructor Email": "a@x.edu", "Dept": "psy", "Year": "2"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].dept_code == "PSY"           # upper-cased override
    assert secs[0].cohort_key == "PSY-2"        # Dept + Year override compose


def test_dept_override_with_unparseable_code_no_bad_code_warning():
    rows = [{"Course Code": "1234", "Section No": "01", "T": "3", "P": "0",
             "L": "0", "Instructor Email": "a@x.edu", "Dept": "PSY"}]
    codes = [c for c, _ in validate_courselist(rows)]
    assert "warn_bad_code" not in codes          # Dept supplied -> actionable warning suppressed


def test_unparseable_code_without_dept_still_warns():
    rows = [{"Course Code": "1234", "Section No": "01", "T": "3", "P": "0",
             "L": "0", "Instructor Email": "a@x.edu"}]
    codes = [c for c, _ in validate_courselist(rows)]
    assert "warn_bad_code" in codes


def test_dept_override_sets_instructor_home_dept():
    rows = [{"Course Code": "1234", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Instructor Name": "A. Yilmaz", "Instructor Email": "a@x.edu", "Dept": "PSY"}]
    instr = build_instructors_from_courselist(rows)
    assert instr["a@x.edu"].home_dept == "PSY"


def test_dept_column_in_importer_aliases():
    from timetabling.csv_import import COURSE_COL_MAP, COURSE_POSITIONAL
    assert "Dept" in COURSE_COL_MAP
    # appended at the end so existing positional indices are unchanged
    assert COURSE_POSITIONAL[-1] == "Dept"


def test_parttime_column_overrides_S_marker():
    rows = [{"Course Code": "EE 201", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Instructor Name": "A. Yilmaz", "Instructor Email": "a@x.edu", "Part-time": "yes"}]
    instr = build_instructors_from_courselist(rows)
    assert instr["a@x.edu"].is_staff is False   # column says part-time despite no (S)


def test_parttime_falls_back_to_S_when_column_absent():
    rows = [{"Course Code": "EE 201", "Instructor Name": "B (S)", "Instructor Email": "b@x.edu"}]
    instr = build_instructors_from_courselist(rows)
    assert instr["b@x.edu"].is_staff is False


# --- Phase 4: Room Type column --------------------------------------------

def test_room_type_requires_lab():
    rows = [{"Course Code": "X 101", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Instructor Email": "a@x.edu", "Room Type": "computer-lab"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].requires_lab_room is True


def test_room_type_regular_or_blank_no_lab():
    for val in ("", "regular", "classroom", "normal"):
        rows = [{"Course Code": "X 101", "Section No": "01", "T": "3", "P": "0", "L": "0",
                 "Instructor Email": "a@x.edu", "Room Type": val}]
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
             "Instructor Email": "a@x.edu", "Fixed": "We 10"}]
    secs, _ = build_sections_from_courselist(rows, "001", Config())
    assert secs[0].fixed_day == "We" and secs[0].fixed_start == 10


# --- Two-table data model: locked semantics --------------------------------

def test_dept_is_faculty_and_cohort_from_code():
    rows = [{"Course Code": "ADA 403", "Section No": "ADA 403_01", "T": "3", "P": "0",
             "L": "0", "Instructor Email": "a@x.edu", "Section Capacity": "45",
             "Dept": "Faculty of Econ"}]
    s = build_sections_from_courselist(rows, "001", Config())[0][0]
    assert s.faculty == "Faculty of Econ"      # DEPT -> faculty
    assert s.cohort_key == "ADA-4"             # cohort from code prefix, NOT DEPT
    assert s.dept_code == "ADA"
    assert s.section_id == "ADA 403_01"        # SECTION used directly
    assert s.students == 45                    # Section Capacity drives size


def test_cohort_falls_back_to_dept_when_code_unparseable():
    rows = [{"Course Code": "1234", "Section No": "01", "T": "3", "P": "0", "L": "0",
             "Instructor Email": "a@x.edu", "Section Capacity": "20", "Dept": "PSY"}]
    s = build_sections_from_courselist(rows, "001", Config())[0][0]
    assert s.cohort_key == "PSY-0" and s.dept_code == "PSY"


def test_section_capacity_preferred_then_students_fallback():
    base = {"Course Code": "X 101", "Section No": "01", "T": "2", "P": "0", "L": "0",
            "Instructor Email": "a@x.edu"}
    s1 = build_sections_from_courselist([base | {"Section Capacity": "50",
                                                 "~Students": "30"}], "001", Config())[0][0]
    assert s1.students == 50                    # quota preferred
    s2 = build_sections_from_courselist([base | {"~Students": "30"}],
                                        "001", Config())[0][0]
    assert s2.students == 30                    # falls back to actual


def test_instructor_keyed_by_name_when_email_absent():
    rows = [{"Course Code": "X 101", "Section No": "01", "T": "2", "P": "0", "L": "0",
             "Instructor Name": "Mustafa Yuksel (S)", "Instructor Email": "",
             "Section Capacity": "10"}]
    secs = build_sections_from_courselist(rows, "001", Config())[0]
    assert secs[0].instructor_ids == ["mustafa yuksel"]
    instr = build_instructors_from_courselist(rows)
    assert "mustafa yuksel" in instr and instr["mustafa yuksel"].is_staff is False


def test_required_room_type_categorical():
    def rt(val, L="0"):
        rows = [{"Course Code": "X 101", "Section No": "01", "T": "2", "P": "0", "L": L,
                 "Instructor Email": "a@x.edu", "Section Capacity": "10", "Room Type": val}]
        return build_sections_from_courselist(rows, "001", Config())[0][0]
    assert rt("studio").required_room_type == "studio"
    assert rt("computer pc lab").required_room_type == "pc"
    assert rt("").required_room_type == "" and rt("").requires_lab_room is False
    # L>0 alone is NOT a section-level lab-room demand (the lab *block* carries it);
    # only an explicit Room Type sets requires_lab_room.
    assert rt("", L="2").requires_lab_room is False
    assert rt("pc").requires_lab_room is True


def test_categorical_room_routing_pc_not_lab():
    """A pc-typed section must land in a pc room, never a (wet) lab room."""
    cfg = Config(solve_time_limit_s=10.0)
    rows = [{"Course Code": "CS 101", "Section No": "01", "T": "2", "P": "0", "L": "0",
             "Instructor Email": "a@x.edu", "Section Capacity": "20", "Room Type": "pc"}]
    secs, _ = build_sections_from_courselist(rows, "001", cfg)
    instr = build_instructors_from_courselist(rows)
    rooms = build_rooms_from_ui([{"Room": "WET1", "Capacity": "50", "Type": "lab"},
                                 {"Room": "PC1", "Capacity": "50", "Type": "pc"}], cfg)
    mark_virtual(secs, rooms, cfg)
    res = run_pipeline("001", secs, rooms, instr, cfg, solver="cpsat")
    assert res.violations == []
    a = next(x for x in res.assignments if x.section_id == "CS 101_01")
    assert a.room == "PC1"            # pc demand -> pc room, not the lab room


def test_build_rooms_categorical_type_and_back_compat():
    rooms = build_rooms_from_ui(
        [{"Room": "A1", "Capacity": "30", "Type": "normal"},
         {"Room": "PC1", "Capacity": "20", "Type": "pc"},
         {"Room": "L9", "Cap": "15", "Lab": "x"}], Config())     # legacy keys
    assert rooms["A1"].type == "normal" and rooms["A1"].is_lab is False
    assert rooms["PC1"].type == "pc" and rooms["PC1"].is_lab is True
    assert rooms["L9"].type == "lab" and rooms["L9"].cap == 15    # legacy Lab/Cap honored


def test_end_to_end_ui_path_settings_and_columns():
    """settings -> build_config -> ui_input columns -> run_pipeline, all honored, 0 violations."""
    from timetabling.settings import build_config, DEFAULT_SETTINGS
    cfg = build_config(DEFAULT_SETTINGS, {"a@x.edu": [["Mo", "AM"], ["Mo", "PM"]]}, 10.0)
    rows = [
        {"Course Code": "CS 101", "Section No": "01", "T": "2", "P": "0", "L": "0",
         "Instructor Email": "a@x.edu", "~Students": "20", "Fixed": "We 10"},
        {"Course Code": "CS 201", "Section No": "01", "T": "2", "P": "0", "L": "0",
         "Instructor Email": "b@x.edu", "~Students": "15", "Room Type": "lab"},
    ]
    secs, _ = build_sections_from_courselist(rows, "001", cfg)
    instr = build_instructors_from_courselist(rows)
    rooms = build_rooms_from_ui([{"Room": "R1", "Cap": "50", "Lab": ""},
                                 {"Room": "LAB1", "Cap": "50", "Lab": "x"}], cfg)
    mark_virtual(secs, rooms, cfg)
    res = run_pipeline("001", secs, rooms, instr, cfg, solver="cpsat")
    assert res.violations == []
    a101 = next(a for a in res.assignments if a.section_id == "CS 101_01")
    assert a101.day == "We" and a101.start == 10          # Fixed pin honored
    a201 = next(a for a in res.assignments if a.section_id == "CS 201_01")
    assert a201.room == "LAB1"                              # Room Type=lab -> lab room
