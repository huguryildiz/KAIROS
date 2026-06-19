from timetabling.config import Config
from timetabling import derive, join


def test_course_level():
    assert derive.course_level("ADA 403") == 4
    assert derive.course_level("MATH 101") == 1
    assert derive.course_level("ARCH 510") == 5
    assert derive.course_level("X 612") == 6


def test_blocks_from_tpl_theory_only():
    blocks = derive.blocks_from_tpl("S_01", 3, 0, 0, 3)
    assert len(blocks) == 1
    assert blocks[0].kind == "theory" and blocks[0].length == 3 and not blocks[0].needs_lab


def test_blocks_from_tpl_theory_plus_lab():
    blocks = derive.blocks_from_tpl("S_01", 2, 0, 2, 3)
    kinds = {b.kind: b for b in blocks}
    assert kinds["theory"].length == 2 and kinds["lab"].length == 2
    assert kinds["lab"].needs_lab is True


def test_blocks_practice_folds_into_theory():
    blocks = derive.blocks_from_tpl("S_01", 2, 2, 0, 3)
    assert len(blocks) == 1 and blocks[0].length == 4   # T+P


def test_blocks_zero_defaults_to_three():
    blocks = derive.blocks_from_tpl("S_01", 0, 0, 0, 3)
    assert len(blocks) == 1 and blocks[0].length == 3


def test_build_sections_excludes_grad_and_internship():
    df = join.build_section_frame("001")
    sections, rep = derive.build_sections(df, Config())
    assert all(s.level <= 4 for s in sections)
    assert all(s.category not in Config().excluded_categories for s in sections)
    assert rep["excluded"] >= 0 and "hours_rule" in rep
    s = next(s for s in sections if s.section_id == "ADA 403_01")
    assert s.cohort_key == "ADA-4" and s.students == 24
