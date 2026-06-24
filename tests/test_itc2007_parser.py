"""Tests for ITC-2007 .ectt parser and KAIROS adapter."""
import pytest
from pathlib import Path
from timetabling.io_itc2007 import parse_ectt, adapt_itc2007, ItcInstance

COMP01 = Path("benchmarks/itc2007/comp01.ectt")
skip_if_missing = pytest.mark.skipif(
    not COMP01.exists(), reason="comp01.ectt not downloaded"
)


# ---------------------------------------------------------------------------
# Parser tests
# ---------------------------------------------------------------------------

@skip_if_missing
def test_parse_comp01_header():
    inst = parse_ectt(str(COMP01))
    assert inst.name == "Fis0506-1"
    assert inst.num_days == 5
    assert inst.periods_per_day == 6
    assert len(inst.courses) == 30
    assert len(inst.rooms) == 6
    assert len(inst.curricula) == 14


@skip_if_missing
def test_parse_comp01_course():
    inst = parse_ectt(str(COMP01))
    c = inst.courses["c0001"]
    assert c.teacher_id == "t000"
    assert c.num_lectures == 6
    assert c.min_working_days == 4
    assert c.num_students == 130


@skip_if_missing
def test_parse_comp01_rooms():
    inst = parse_ectt(str(COMP01))
    assert inst.rooms["rB"].capacity == 200
    assert inst.rooms["rE"].capacity == 9


@skip_if_missing
def test_parse_comp01_curricula():
    inst = parse_ectt(str(COMP01))
    assert set(inst.curricula["q000"]) == {"c0001", "c0002", "c0004", "c0005"}


@skip_if_missing
def test_parse_comp01_unavailability():
    inst = parse_ectt(str(COMP01))
    # c0001 (teacher t000) blocked all of Friday (day 4, periods 0-5)
    friday_blocks = [(c, d, p) for c, d, p in inst.unavailability if c == "c0001"]
    assert len(friday_blocks) == 6
    assert all(d == 4 for _, d, _ in friday_blocks)


@skip_if_missing
def test_parse_comp01_total_lectures():
    inst = parse_ectt(str(COMP01))
    total = sum(c.num_lectures for c in inst.courses.values())
    assert total == 160  # sum from comp01 spec


# ---------------------------------------------------------------------------
# Adapter tests
# ---------------------------------------------------------------------------

@skip_if_missing
def test_adapt_comp01_section_count():
    inst = parse_ectt(str(COMP01))
    sections, rooms, instructors, cfg = adapt_itc2007(inst, time_limit=10.0)
    total_lectures = sum(c.num_lectures for c in inst.courses.values())
    assert len(sections) == total_lectures


@skip_if_missing
def test_adapt_comp01_rooms():
    inst = parse_ectt(str(COMP01))
    sections, rooms, instructors, cfg = adapt_itc2007(inst, time_limit=10.0)
    assert len(rooms) == len(inst.rooms)
    assert all(r.cap == 999_999 for r in rooms.values())


@skip_if_missing
def test_adapt_comp01_curriculum_instructors():
    inst = parse_ectt(str(COMP01))
    sections, rooms, instructors, cfg = adapt_itc2007(inst, time_limit=10.0)
    assert "__qq000" in instructors
    # c0001 is in q000 and q002 → every lecture section must list both
    c0001_secs = [s for s in sections if s.code == "c0001"]
    assert len(c0001_secs) == 6
    assert all("__qq000" in s.instructor_ids for s in c0001_secs)
    assert all("__qq002" in s.instructor_ids for s in c0001_secs)


@skip_if_missing
def test_adapt_comp01_unavailability():
    inst = parse_ectt(str(COMP01))
    sections, rooms, instructors, cfg = adapt_itc2007(inst, time_limit=10.0)
    # t000 (c0001 teacher) blocked Friday (day 4 → "Fr") all 6 periods
    assert all(("t000", "Fr", p) in cfg.instr_unavailable for p in range(6))


@skip_if_missing
def test_adapt_comp01_config_horizon():
    inst = parse_ectt(str(COMP01))
    sections, rooms, instructors, cfg = adapt_itc2007(inst, time_limit=10.0)
    assert cfg.horizon_start == 0
    assert cfg.horizon_end == inst.periods_per_day
