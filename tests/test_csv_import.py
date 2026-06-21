"""Unit tests for the VERA-style CSV importer (alias detection, per-row status,
duplicate detection). Mirrors VERA's csvParser.test.js."""
import os

from timetabling.csv_import import (
    normalize_header, map_columns, parse_courselist, read_raw, ok_rows,
    COURSE_POSITIONAL, CLASSROOM_COL_MAP, CLASSROOM_POSITIONAL,
    parse_classrooms, ok_rooms,
)

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")
_SAMPLE_CR = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_classrooms.csv")

_EN_HEADER = ["Course Code", "Course Name", "Section No", "T", "P", "L",
              "Instructor Name", "Instructor Email", "~Students"]


def _row(code="CMPE 113", name="Intro", sec="01", T="3", P="0", L="2",
         ln="A. Yilmaz", le="a@uni.edu", st="50"):
    return [code, name, sec, T, P, L, ln, le, st]


# --- normalize_header ----------------------------------------------------

def test_normalize_header_collapses_separators():
    assert normalize_header("  Course Code ") == "course_code"
    assert normalize_header("~Students") == "students"
    assert normalize_header("Ders Kodu") == "ders_kodu"
    assert normalize_header("Section-No.") == "section_no"


# --- map_columns ---------------------------------------------------------

def test_map_columns_en_header_one_to_one():
    raw = [_EN_HEADER, _row()]
    m = map_columns(raw)
    assert m["has_header"] is True
    assert m["col_index"]["Course Code"] == 0
    assert m["col_index"]["~Students"] == 8
    assert len(m["data_rows"]) == 1


def test_map_columns_tr_aliases():
    raw = [["Ders Kodu", "Ders Adı", "Şube", "Teori", "Uygulama", "Lab",
            "Hoca", "Eposta", "Öğrenci"], _row()]
    m = map_columns(raw)
    assert m["has_header"] is True
    assert m["col_index"]["Course Code"] == 0
    assert m["col_index"]["Section No"] == 2
    assert m["col_index"]["L"] == 5


def test_map_columns_positional_fallback_no_header():
    raw = [_row()]  # first row is data, not a header
    m = map_columns(raw)
    assert m["has_header"] is False
    # positional: each canonical mapped to its index in COURSE_POSITIONAL
    for i, canonical in enumerate(COURSE_POSITIONAL):
        assert m["col_index"][canonical] == i
    assert len(m["data_rows"]) == 1


def test_map_columns_skips_comment_and_blank_rows():
    raw = [["# my comment"], [""], _EN_HEADER, _row()]
    m = map_columns(raw)
    assert m["has_header"] is True
    assert m["first_data_idx"] == 2
    assert len(m["data_rows"]) == 1


# --- parse_courselist ----------------------------------------------------

def test_parse_valid_rows_all_ok():
    raw = [_EN_HEADER, _row(sec="01"), _row(sec="02")]
    p = parse_courselist(raw)
    assert p["stats"] == {"valid": 2, "duplicate": 0, "error": 0, "total": 2}
    assert all(r["status"] == "ok" for r in p["rows"])
    assert p["warning"] is None


def test_parse_duplicate_in_file():
    raw = [_EN_HEADER, _row(sec="01"), _row(sec="01")]
    p = parse_courselist(raw)
    assert p["stats"]["valid"] == 1
    assert p["stats"]["duplicate"] == 1
    assert p["rows"][1]["status"] == "duplicate"


def test_parse_duplicate_against_existing():
    raw = [_EN_HEADER, _row(sec="01")]
    p = parse_courselist(raw, existing=[{"Course Code": "CMPE 113", "Section No": "01"}])
    assert p["stats"]["duplicate"] == 1
    assert p["rows"][0]["status"] == "duplicate"


def test_parse_missing_course_code_is_error():
    raw = [_EN_HEADER, _row(code="")]
    p = parse_courselist(raw)
    assert p["stats"]["error"] == 1
    assert p["rows"][0]["status"] == "error"


def test_parse_nonnumeric_hours_is_error():
    raw = [_EN_HEADER, _row(T="abc")]
    p = parse_courselist(raw)
    assert p["stats"]["error"] == 1
    assert p["rows"][0]["status"] == "error"


def test_parse_row_num_reflects_original_line():
    raw = [["# comment"], _EN_HEADER, _row(sec="01")]
    p = parse_courselist(raw)
    # comment line 1, header line 2, data line 3
    assert p["rows"][0]["row_num"] == 3


def test_parse_warning_present_when_problems():
    raw = [_EN_HEADER, _row(sec="01"), _row(sec="01"), _row(code="")]
    p = parse_courselist(raw)
    assert p["warning"] is not None
    assert "title" in p["warning"] and "desc" in p["warning"]


def test_ok_rows_returns_clean_canonical_dicts():
    raw = [_EN_HEADER, _row(sec="01"), _row(code="")]  # one ok, one error
    p = parse_courselist(raw)
    clean = ok_rows(p)
    assert len(clean) == 1
    r = clean[0]
    assert r["Course Code"] == "CMPE 113"
    assert "status" not in r and "row_num" not in r
    assert set(r) >= {"Course Code", "Section No", "T", "P", "L", "Instructor Email"}


# --- read_raw + sample ---------------------------------------------------

def test_read_raw_and_parse_sample_all_ok():
    raw = read_raw(_SAMPLE)
    p = parse_courselist(raw)
    assert p["stats"]["total"] > 0
    assert p["stats"]["error"] == 0
    assert p["stats"]["valid"] == p["stats"]["total"]


# --- Phase 4: optional columns (backward compatible) ----------------------

def test_optional_columns_appended_after_original_nine():
    assert COURSE_POSITIONAL[:9] == tuple(_EN_HEADER)
    assert COURSE_POSITIONAL[9:] == (
        "Section Capacity", "Year", "Part-time", "Room Type", "Fixed", "Dept")


def test_backward_compat_9col_still_parses_with_empty_new_fields():
    raw = [_row()]  # header-less 9-column row, exactly as today
    p = parse_courselist(raw)
    assert p["stats"] == {"valid": 1, "duplicate": 0, "error": 0, "total": 1}
    r = ok_rows(p)[0]
    assert r["Course Code"] == "CMPE 113"
    assert r["Year"] == "" and r["Part-time"] == ""
    assert r["Room Type"] == "" and r["Fixed"] == ""


def test_new_column_aliases_detected_from_header():
    header = _EN_HEADER + ["Year", "Part-time", "Room Type", "Fixed"]
    raw = [header, _row() + ["2", "yes", "lab", "Mo 9"]]
    m = map_columns(raw)
    assert m["col_index"]["Year"] == 9
    assert m["col_index"]["Part-time"] == 10
    assert m["col_index"]["Room Type"] == 11
    assert m["col_index"]["Fixed"] == 12
    r = ok_rows(parse_courselist(raw))[0]
    assert r["Year"] == "2" and r["Part-time"] == "yes"
    assert r["Room Type"] == "lab" and r["Fixed"] == "Mo 9"


# --- Classroom importer ---------------------------------------------------

def test_map_columns_accepts_classroom_col_map():
    raw = [["ROOM", "ROOM_CAP"], ["A216", "25"]]
    m = map_columns(raw, CLASSROOM_COL_MAP)
    assert m["has_header"] is True
    assert m["col_index"]["Room"] == 0
    assert m["col_index"]["Capacity"] == 1
    # No Type column in the file -> positional fallback for Type.
    typ = next(d for d in m["detected_columns"] if d["field"] == "Type")
    assert typ["source"] == "positional"
    room = next(d for d in m["detected_columns"] if d["field"] == "Room")
    assert room["source"] == "header" and room["label"] == "ROOM"


def test_parse_classrooms_room_cap_header_type_from_name():
    raw = [["ROOM", "ROOM_CAP"], ["A211-PC-L", "99"], ["A316-L", "40"], ["A216", "25"]]
    p = parse_classrooms(raw)
    assert p["stats"] == {"valid": 3, "duplicate": 0, "error": 0, "total": 3}
    rooms = ok_rooms(p)
    assert rooms[0] == {"Room": "A211-PC-L", "Capacity": "99", "Type": "pc", "Dept": ""}   # -PC
    assert rooms[1] == {"Room": "A316-L", "Capacity": "40", "Type": "lab", "Dept": ""}     # -L
    assert rooms[2] == {"Room": "A216", "Capacity": "25", "Type": "normal", "Dept": ""}


def test_parse_classrooms_explicit_type_column_wins():
    raw = [["Room", "Capacity", "Type"],
           ["A216", "25", "pc"], ["A317-L", "40", ""], ["B100", "40", "studio"]]
    p = parse_classrooms(raw)
    rooms = ok_rooms(p)
    assert rooms[0]["Type"] == "pc"        # explicit category wins over name (no token)
    assert rooms[1]["Type"] == "lab"       # blank cell -> derived from -L name token
    assert rooms[2]["Type"] == "studio"


def test_parse_classrooms_legacy_lab_boolean_maps_to_lab():
    raw = [["Room", "Capacity", "Lab"], ["A216", "25", "yes"], ["B100", "40", ""]]
    p = parse_classrooms(raw)
    rooms = ok_rooms(p)
    assert rooms[0]["Type"] == "lab"       # legacy truthy Lab cell -> generic lab
    assert rooms[1]["Type"] == "normal"


def test_parse_classrooms_blank_cap_ok_zero():
    raw = [["Room", "Capacity"], ["A216", ""]]
    p = parse_classrooms(raw)
    assert p["stats"]["valid"] == 1
    assert ok_rooms(p)[0]["Capacity"] == "0"


def test_parse_classrooms_missing_room_and_bad_cap_are_errors():
    raw = [["Room", "Cap"], ["", "25"], ["A216", "abc"]]
    p = parse_classrooms(raw)
    assert p["stats"]["error"] == 2
    assert ok_rooms(p) == []


def test_parse_classrooms_duplicate_room_flagged():
    raw = [["Room", "Cap"], ["A216", "25"], ["a216", "30"]]  # case-insensitive
    p = parse_classrooms(raw)
    assert p["stats"]["valid"] == 1 and p["stats"]["duplicate"] == 1
    assert p["rows"][1]["status"] == "duplicate"


def test_parse_classrooms_headerless_positional():
    raw = [["A216", "25"]]  # no header row
    m = map_columns(raw, CLASSROOM_COL_MAP)
    assert m["has_header"] is False
    for i, canonical in enumerate(CLASSROOM_POSITIONAL):
        assert m["col_index"][canonical] == i
    p = parse_classrooms(raw)
    assert p["stats"]["valid"] == 1
    assert ok_rooms(p)[0]["Room"] == "A216"


def test_read_raw_and_parse_sample_classrooms_all_ok():
    p = parse_classrooms(read_raw(_SAMPLE_CR))
    assert p["stats"]["total"] > 0
    assert p["stats"]["error"] == 0
    assert p["stats"]["valid"] == p["stats"]["total"]
    # Room/Capacity/Type header -> all three matched by header.
    srcs = {d["field"]: d["source"] for d in p["detected_columns"]}
    assert srcs["Room"] == "header" and srcs["Capacity"] == "header"
    assert srcs["Type"] == "header"
    # categorical types parsed straight from the column
    assert {r["Type"] for r in ok_rooms(p)} <= {"normal", "lab", "pc", "studio"}
