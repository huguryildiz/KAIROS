from timetabling.ui_style import dept_color, metric_cards_html, week_grid_html

_SCHED = {"assignments": [
    {"section_id": "A_01", "course_code": "A 101", "room": "R1", "day": "Mo",
     "start": 9, "end": 11, "block_kind": "theory", "instructor_name": "X",
     "cohort": "A-1", "dept": "A"},
    {"section_id": "B_01", "course_code": "B 201", "room": "R2", "day": "Tu",
     "start": 10, "end": 11, "block_kind": "lab", "instructor_name": "Y",
     "cohort": "B-2", "dept": "B"},
]}


def test_dept_color_deterministic():
    assert dept_color("CMPE") == dept_color("CMPE")
    assert dept_color("CMPE").startswith("#")


def test_week_grid_html_renders_blocks_and_lab_tag():
    html = week_grid_html(_SCHED)
    assert "A 101" in html and "B 201" in html
    assert "LAB" in html                       # lab block tagged
    assert "tt-blk cont" in html               # 2h theory has a continuation slice
    assert week_grid_html({"assignments": []}).count("tt-empty") == 1


def test_week_grid_meta_field_adapts():
    # default meta = room; when viewing by cohort we show the room, by room the cohort
    assert "R1" in week_grid_html(_SCHED)                      # default meta_field=room
    html_cohort = week_grid_html(_SCHED, meta_field="cohort")
    assert "A-1" in html_cohort                                # cohort shown as the block meta


def test_metric_cards_html():
    html = metric_cards_html([("Placed", "100%", "good")])
    assert "Placed" in html and "100%" in html and "tt-card good" in html
