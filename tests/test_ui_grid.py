from timetabling.ui_grid import build_week_grid, filter_assignments, distinct_values

_SCHED = {"assignments": [
    {"section_id": "A_01", "course_code": "A 101", "room": "R1", "day": "Mo",
     "start": 9, "end": 11, "block_kind": "theory", "instructor_name": "X",
     "cohort": "A-1", "dept": "A"},
    {"section_id": "B_01", "course_code": "B 201", "room": "R2", "day": "Tu",
     "start": 10, "end": 11, "block_kind": "lab", "instructor_name": "Y",
     "cohort": "B-2", "dept": "B"},
]}


def test_build_week_grid_spans_hours():
    grid = build_week_grid(_SCHED)
    assert len(grid[("Mo", 9)]) == 1
    assert len(grid[("Mo", 10)]) == 1     # 2h block occupies 9 and 10
    assert ("Mo", 11) not in grid or grid[("Mo", 11)] == []


def test_filter_and_distinct():
    assert distinct_values(_SCHED, "dept") == ["A", "B"]
    only_a = filter_assignments(_SCHED, "dept", "A")
    assert len(only_a["assignments"]) == 1
    assert filter_assignments(_SCHED, "dept", "")["assignments"] == _SCHED["assignments"]
