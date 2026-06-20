from timetabling.ui_style import (block_color, dept_color, metric_cards_html,
                                   week_grid_html, brand_css, hero_html,
                                   appbar_html, stepper_html, kpi_chips_html)

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


def test_brand_css_light_vs_dark_tokens():
    light, dark = brand_css("light"), brand_css("dark")
    assert "#F4F6FA" in light and "#0E1220" not in light      # light canvas only
    assert "#0E1220" in dark                                   # dark canvas present
    assert ".tt-blk" in light and ".tt-blk" in dark            # component CSS in both
    assert 'data-testid="stHeader"' in light                   # hides native chrome
    assert brand_css() == light                                # default is light


def test_stepper_marks_status_classes():
    steps = [{"key": "upload", "label": "Yükle", "status": "done"},
             {"key": "solve", "label": "Çöz", "status": "locked"},
             {"key": "results", "label": "Sonuçlar", "status": "active"}]
    html = stepper_html(steps, "tr")
    assert "step done" in html and "step locked" in html and "step active" in html
    assert 'href="#s-upload"' in html
    assert "Yükle" in html and "Sonuçlar" in html


def test_kpi_chips_render_label_value_tone():
    html = kpi_chips_html([("Şube", "793", ""), ("Çakışma", "0", "good")])
    assert "793" in html and "Şube" in html and "kpi good" in html


def test_appbar_live_flag_and_context():
    assert "context-pill live" in appbar_html("tr", "793 şube", live=True)
    assert "Veri" in appbar_html("tr", "Veri bekleniyor", live=False)


def test_hero_html_localized():
    assert "tt-hero" in hero_html("tr") and "tt-hero" in hero_html("en")
