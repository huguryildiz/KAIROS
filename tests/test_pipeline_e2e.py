import os
import pytest

from timetabling.csv_import import read_raw, parse_courselist, ok_rows
from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
    build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.validate import validate

_SAMPLE = "data/sample_courses_2025_001.csv"


@pytest.mark.skipif(not os.path.exists(_SAMPLE), reason="sample CSV not on disk")
def test_pipeline_zero_hard_violations_with_soft_polish():
    courses = ok_rows(parse_courselist(read_raw(_SAMPLE)))[:60]
    cfg = build_config({}, {}, 60)
    secs, _ = build_sections_from_courselist(courses, "001", cfg)
    instr = build_instructors_from_courselist(courses)
    rooms = build_rooms_from_ui([dict(r) for r in DEFAULT_CLASSROOMS], cfg)
    mark_virtual(secs, rooms, cfg)
    res = run_pipeline("001", secs, rooms, instr, cfg, solver="auto")
    viol = validate(res.assignments, res.sections, rooms, instr, cfg)
    assert [v for v in viol if v.kind != "placement"] == []   # 0 genuine hard violations
