from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat


def test_eng_lab_prefers_configured_days():
    """Regression guard: S-EngLab term moves Engineering lab to the preferred day.

    eng_lab_days is set to ("Mo",) so only Monday is penalty-free.
    Without the term, CP-SAT's default picks Fr (verified empirically).
    With the term and w_englab=100, the solver picks Mo (0 cost) over Fr (100 cost).
    The test goes RED if englab_terms are absent from the objective.
    """
    cfg = Config(w_englab=100, eng_lab_days=("Mo",),
                 w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0, w_order=0)
    rooms = [Room("LAB-L", 50, True, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("E201_01", "001", "E 201", "n", 2, "E", "Department of Computer Engineering",
                "E-2", ["a"], 10, 0, 0, 2, 0, "Course")
    s.blocks = [Block("E201_01#L", "E201_01", "lab", 2, True)]
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert assigns and assigns[0].day == "Mo"


def test_non_eng_lab_unconstrained():
    # Psychology (non-Engineering) must be EXEMPT from the S-EngLab penalty.
    # Make Monday the only penalty-free day (eng_lab_days=("Mo",)) AND block Monday entirely,
    # so an Engineering lab WOULD be forced to pay w_englab on a Tue-Fri day. A correctly-guarded
    # Psychology lab pays nothing -> objective 0.0; if the faculty guard were buggy, objective
    # would be 100. This is the regression guard for faculty isolation.
    closed = tuple(("Mo", h) for h in range(9, 18))
    cfg = Config(w_englab=100, eng_lab_days=("Mo",), w_cohort_gap=0, w_evening=0,
                 w_room_count=0, w_instr_days=0, w_parttime_days=0, w_order=0,
                 w_nonadjacent=0, blackout=closed)
    rooms = [Room("LAB-L", 50, True, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("P201_01", "001", "P 201", "n", 2, "P", "Department of Psychology",
                "P-2", ["a"], 10, 0, 0, 2, 0, "Course")
    s.blocks = [Block("P201_01#L", "P201_01", "lab", 2, True)]
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert assigns and assigns[0].day != "Mo"      # Monday blocked -> lands Tue-Fri
    assert stats["objective"] == 0.0               # no englab penalty for non-Engineering
