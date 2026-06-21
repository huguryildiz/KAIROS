import os

from timetabling.config import Config
from timetabling.ui_input import build_sections_from_courselist, validate_courselist
from timetabling.csv_import import read_raw, parse_courselist, ok_rows

CSV = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")


def _rows():
    # Route through the alias importer, exactly as the upload flow does, so the
    # raw-header sample (COURSE_CODE/LECTURER/…) maps to canonical column names.
    return ok_rows(parse_courselist(read_raw(CSV)))


def test_sample_csv_loads_and_builds_sections():
    secs, _ = build_sections_from_courselist(_rows(), "001", Config())
    assert len(secs) >= 1


def test_sample_demonstrates_part_time_and_no_missing_cols():
    # validate returns no "missing required column" warning, and flags part-time
    warns = dict(validate_courselist(_rows()))
    assert "warn_missing_cols" not in warns
    assert warns.get("info_part_time", {}).get("n", 0) >= 1
