"""Unit tests for the VERA-style CSV importer (alias detection, per-row status,
duplicate detection). Mirrors VERA's csvParser.test.js."""
import os

from timetabling.csv_import import (
    normalize_header, map_columns, parse_courselist, read_raw, ok_rows,
    COURSE_POSITIONAL,
)

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")

_EN_HEADER = ["Course Code", "Course Name", "Section No", "T", "P", "L",
              "Lecturer Name", "Lecturer Email", "~Students"]


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
    assert set(r) >= {"Course Code", "Section No", "T", "P", "L", "Lecturer Email"}


# --- read_raw + sample ---------------------------------------------------

def test_read_raw_and_parse_sample_all_ok():
    raw = read_raw(_SAMPLE)
    p = parse_courselist(raw)
    assert p["stats"]["total"] > 0
    assert p["stats"]["error"] == 0
    assert p["stats"]["valid"] == p["stats"]["total"]
