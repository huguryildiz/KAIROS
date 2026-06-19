from timetabling.config import Config
from timetabling import derive, join


def test_course_level():
    assert derive.course_level("ADA 403") == 4
    assert derive.course_level("MATH 101") == 1
    assert derive.course_level("ARCH 510") == 5
    assert derive.course_level("X 612") == 6


def test_blocks_from_tpl_theory_only():
    blocks = derive.blocks_from_tpl("S_01", 3, 0, 0, 3)   # 3h theory -> 2 + 1
    assert len(blocks) == 2 and sorted(b.length for b in blocks) == [1, 2]
    assert all(b.kind == "theory" and not b.needs_lab for b in blocks)


def test_blocks_from_tpl_theory_plus_lab():
    blocks = derive.blocks_from_tpl("S_01", 2, 0, 2, 3)
    kinds = {b.kind: b for b in blocks}
    assert kinds["theory"].length == 2 and kinds["lab"].length == 2
    assert kinds["lab"].needs_lab is True


def test_blocks_practice_folds_into_theory():
    blocks = derive.blocks_from_tpl("S_01", 2, 2, 0, 3)   # T+P = 4h -> 2 + 2
    assert len(blocks) == 2 and sorted(b.length for b in blocks) == [2, 2]
    assert all(b.kind == "theory" for b in blocks)


def test_blocks_zero_defaults_to_three():
    blocks = derive.blocks_from_tpl("S_01", 0, 0, 0, 3)   # defaults to Cr=3 -> 2 + 1
    assert len(blocks) == 2 and sorted(b.length for b in blocks) == [1, 2]


def test_build_sections_excludes_grad_and_internship():
    df = join.build_section_frame("001")
    sections, rep = derive.build_sections(df, Config())
    assert all(s.level <= 4 for s in sections)
    assert all(s.category not in Config().excluded_categories for s in sections)
    assert rep["excluded"] >= 0 and "hours_rule" in rep
    s = next(s for s in sections if s.section_id == "ADA 403_01")
    assert s.cohort_key == "ADA-4" and s.students == 24


def test_section_carries_plan_room():
    import pandas as pd
    from timetabling.derive import build_sections
    from timetabling.config import Config
    frame = pd.DataFrame([{
        "section_id": "HIST 101_01", "period": "001", "code": "HIST 101",
        "name": "History", "faculty": "Basic Sciences", "T": "2", "P": "0",
        "L": "0", "Cr": "2", "category": "", "staff_id": "00000001",
        "grades_students": "148", "dept_code": "HIST", "year_level": "1",
        "plan_room": "Online",
    }])
    secs, _ = build_sections(frame, Config())
    assert secs[0].plan_room == "Online"
