from timetabling.config import Config
from timetabling.model import Section, Room, Instructor
from timetabling.pipeline import run_pipeline, PipelineResult


def _section(sid="CMPE 113_01"):
    from timetabling.derive import blocks_from_tpl
    return Section(
        section_id=sid, period="001", code="CMPE 113", name="Intro",
        level=1, dept_code="CMPE", faculty="", cohort_key="CMPE-1",
        instructor_ids=["a@x.edu"], students=30, T=2, P=0, L=0, Cr=2,
        category="", blocks=blocks_from_tpl(sid, 2, 0, 0, 2), plan_room="",
    )


def test_run_pipeline_cpsat_places_a_small_problem():
    cfg = Config(solve_time_limit_s=10.0)
    rooms = {"A301": Room("A301", 60, False, True)}
    instr = {"a@x.edu": Instructor("a@x.edu", "Dr A", True, "CMPE")}
    res = run_pipeline("001", [_section()], rooms, instr, cfg, solver="cpsat")
    assert isinstance(res, PipelineResult)
    assert res.violations == []
    assert len(res.assignments) == 1
    assert res.schedule["period"] == "001"
    assert res.schedule["assignments"][0]["section_id"] == "CMPE 113_01"
