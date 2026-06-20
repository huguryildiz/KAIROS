from timetabling.ui_style import (block_color, dept_color, metric_cards_html,
                                   week_grid_html)

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


def test_block_color_per_course():
    # color keyed on the course: same course → same hue (sections share it),
    # deterministic, and the palette spreads courses across several hues.
    a = {"course_code": "A 101", "section_id": "A_01", "dept": "A"}
    b = {"course_code": "A 101", "section_id": "A_02", "dept": "A"}
    assert block_color(a) == block_color(b)        # two sections of one course match
    assert block_color(a).startswith("#")
    spread = {block_color({"course_code": cc}) for cc in
              ("A 101", "B 201", "C 301", "PHYS 101", "EE 201", "MATH 102")}
    assert len(spread) > 1                         # not every course collapses to one color


def test_week_grid_html_renders_blocks_and_lab_tag():
    html = week_grid_html(_SCHED)
    assert "A 101" in html and "B 201" in html     # course code (in the cell tooltip)
    assert "LAB" in html                           # lab block tagged
    assert "tt-blk cont" in html                   # 2h theory has a continuation slice
    assert week_grid_html({"assignments": []}).count("tt-empty") == 1


def test_week_grid_cell_stacks_section_lecturer_room():
    # each cell shows three lines: section id, lecturer, room
    html = week_grid_html(_SCHED)
    assert "A_01" in html                          # section id (line 1)
    assert "X" in html and "Y" in html             # lecturer name (line 2)
    assert "R1" in html and "R2" in html           # room (line 3)
    assert 'class="who"' in html                   # lecturer line rendered


def test_metric_cards_html():
    html = metric_cards_html([("Placed", "100%", "good")])
    assert "Placed" in html and "100%" in html and "tt-card good" in html
