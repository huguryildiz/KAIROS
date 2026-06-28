from timetabling.config import Config
from timetabling.model import Room, Instructor
from timetabling.pipeline import run_pipeline
from timetabling.route import mark_virtual
from timetabling.ui_input import build_sections_from_courselist


def _quiet_cfg(**kwargs):
    base = dict(
        solve_time_limit_s=10.0,
        w_order=0,
        w_englab=0,
        w_room_util=0,
        w_cohort_gap=0,
        w_cohort_conflict=0,
        w_instr_days=0,
        w_parttime_days=0,
        w_nonadjacent=0,
        w_min_working_days=100,
    )
    base.update(kwargs)
    return Config(**base)


def test_cpsat_prefers_distinct_days_for_section_min_working_days():
    cfg = _quiet_cfg()
    rows = [{"Course Code": "X 101", "Course Name": "Split", "Dept": "F",
             "Section No": "01", "Instructor Name": "A", "Instructor Email": "a@x.edu",
             "T": "1", "P": "0", "L": "1", "Section Capacity": "10",
             "Min Working Days": "2"}]
    sections, _ = build_sections_from_courselist(rows, "001", cfg)
    rooms = {
        "R1": Room("R1", 20, False, True),
        "LAB1": Room("LAB1", 20, True, True, type="lab"),
        "Online": Room("Online", 10_000, False, False, is_virtual=True),
    }
    instructors = {"a@x.edu": Instructor("a@x.edu", "A", True, "F")}
    mark_virtual(sections, rooms, cfg)

    res = run_pipeline("001", sections, rooms, instructors, cfg, solver="cpsat")

    assert res.violations == []
    assert len({a.day for a in res.assignments if a.section_id == "X 101_01"}) == 2
    assert res.schedule["unmet_soft"] == []


def test_pipeline_reports_unmet_section_min_working_days():
    cfg = _quiet_cfg()
    rows = [{"Course Code": "X 101", "Course Name": "Single", "Dept": "F",
             "Section No": "01", "Instructor Name": "A", "Instructor Email": "a@x.edu",
             "T": "1", "P": "0", "L": "0", "Section Capacity": "10",
             "Min Working Days": "2"}]
    sections, _ = build_sections_from_courselist(rows, "001", cfg)
    rooms = {
        "R1": Room("R1", 20, False, True),
        "Online": Room("Online", 10_000, False, False, is_virtual=True),
    }
    instructors = {"a@x.edu": Instructor("a@x.edu", "A", True, "F")}
    mark_virtual(sections, rooms, cfg)

    res = run_pipeline("001", sections, rooms, instructors, cfg, solver="cpsat")

    assert res.schedule["unmet_soft"] == [{
        "kind": "min_working_days",
        "section_id": "X 101_01",
        "target_days": 2,
        "actual_days": 1,
        "missing_days": 1,
    }]
