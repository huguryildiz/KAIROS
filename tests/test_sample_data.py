import os

import pandas as pd

from timetabling.config import Config
from timetabling.ui_input import build_sections_from_courselist, validate_courselist

CSV = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")


def _rows():
    return pd.read_csv(CSV, dtype=str).fillna("").to_dict("records")


def test_sample_csv_loads_and_builds_sections():
    secs, _ = build_sections_from_courselist(_rows(), "001", Config())
    assert len(secs) >= 1


def test_sample_demonstrates_part_time_and_no_missing_cols():
    # validate returns no "missing required column" warning, and flags part-time
    warns = dict(validate_courselist(_rows()))
    assert "warn_missing_cols" not in warns
    assert warns.get("info_part_time", {}).get("n", 0) >= 1
