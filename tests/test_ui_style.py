from timetabling.ui_style import (block_color, dept_color, metric_cards_html,
                                   week_grid_html, brand_css, hero_html,
                                   hero_anim_html, appbar_html, stepper_html,
                                   kpi_chips_html, data_table_html)

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
    assert "brand_static.css" in light and "brand_static.css" in dark  # static file linked
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


def test_appbar_brand_only():
    html = appbar_html("tr")
    assert "tt-brand" in html and "Kairos" in html
    assert "context-pill" not in html


def test_hero_html_localized():
    assert "tt-hero" in hero_html("tr") and "tt-hero" in hero_html("en")


def test_hero_html_embeds_decorative_animation():
    html = hero_html("tr")
    # the self-solving mini-grid is present, decorative, and styled by CSS hooks
    assert 'class="tt-hero-anim"' in html and 'aria-hidden="true"' in html
    assert html.count('class="blk"') == 9          # all course blocks rendered
    assert html.count("<i></i>") == 25             # 5×5 empty-cell backdrop
    from timetabling.ui_style import _COMPONENT_CSS
    assert "@keyframes solveIn" in _COMPONENT_CSS and ".tt-hero-anim" in _COMPONENT_CSS
    assert "prefers-reduced-motion" in _COMPONENT_CSS   # freezes when motion reduced


def test_hero_anim_day_labels_follow_language():
    tr, en = hero_anim_html("tr"), hero_anim_html("en")
    assert "<span>Pzt</span>" in tr and "<span>Cum</span>" in tr
    assert "Mon" not in tr
    assert "<span>Mon</span>" in en and "<span>Fri</span>" in en
    assert "Pzt" not in en


def test_data_table_html_themed_and_escaped():
    # Our own HTML table (themed via tokens) — not st.dataframe's glide canvas,
    # which can't follow the in-app dark theme. Renders headers, cells, escapes.
    html = data_table_html(["Course Code", "T", "~Students"],
                           [["CMPE 113", "3", "50"], ["A<b>", "1", "9"]],
                           numeric=("T", "~Students"))
    assert "tt-table-wrap" in html and 'table class="tt-data"' in html
    assert "CMPE 113" in html and "<th>Course Code</th>" in html
    assert '<th class="num">T</th>' in html                  # numeric col right-aligned
    assert '<td class="num">50</td>' in html
    assert "A&lt;b&gt;" in html and "<b>" not in html        # HTML-escaped


def test_data_table_html_empty_rows_render_placeholder():
    html = data_table_html(["A", "B"], [])
    assert "tt-td-empty" in html and 'colspan="2"' in html


def test_data_table_html_max_height_inlined():
    assert "--tt-table-h:220px" in data_table_html(["A"], [["x"]], max_height=220)
