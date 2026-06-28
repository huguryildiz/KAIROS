from dataclasses import replace

from timetabling.config import Config
from timetabling.repair import State
from timetabling.model import Candidate, Section
from timetabling.soft_search import _run_excess, _global_terms, _local_terms, _norm_obj
from timetabling.repair import _avoid_pairs_viol


def test_run_excess_counts_only_beyond_threshold():
    assert _run_excess({9, 10, 11}, 3) == 0          # exactly 3 consecutive -> ok
    assert _run_excess({9, 10, 11, 12}, 3) == 1      # 4 consecutive -> 1 over
    assert _run_excess({9, 10, 13, 14}, 3) == 0      # two runs of 2 -> ok
    assert _run_excess(set(), 3) == 0


def _sec(sid, cohort, code, iids, min_working_days=0):
    return Section(section_id=sid, period="001", code=code, name=code, level=2,
                   dept_code=cohort.split("-")[0], department="F", cohort_key=cohort,
                   instructor_ids=iids, students=10, T=0, P=0, L=0, Cr=0, category="",
                   blocks=[], min_working_days=min_working_days)


def test_global_terms_keys_and_room_stable():
    sec_of = {"A#T": _sec("A", "PSY-2", "PSY101", ["i1"])}
    state = State(sec_of, {"A": ["i1"]}, set())
    state.occupy("A#T", Candidate("A#T", "R1", "Mo", 9, 2))
    t = _global_terms(state, Config(max_instr_days=0))   # threshold 0 -> term == raw teaching-day count
    assert set(t) == {"idle", "maxrun", "instr_days", "nonadjacent", "evening",
                      "instr_idle", "fairness", "room_stable", "free_day", "room_util",
                      "min_working_days", "parallel_coord", "conf",
                      "instr_avoid_viol", "instr_prefer_miss", "avoid_pairs_viol",
                      "building_change", "perturbation", "dept_compactness",
                      "dept_fairness", "session_gap"}
    assert t["room_stable"] == 0          # one section, one room
    assert t["instr_days"] == 1           # i1 teaches 1 day, excess over 0 = 1
    assert t["evening"] == 0
    assert t["instr_idle"] == 0
    assert t["fairness"] == 0


def test_global_terms_counts_department_primetime_ratio_spread():
    sec_of = {
        "A1#T": _sec("A1", "PSY-2", "PSY101", ["i1"]),
        "A2#T": _sec("A2", "PSY-2", "PSY102", ["i2"]),
        "B1#T": _sec("B1", "ECON-2", "ECON101", ["i3"]),
        "B2#T": _sec("B2", "ECON-2", "ECON102", ["i4"]),
    }
    sec_of["A1#T"].department = "Psychology"
    sec_of["A2#T"].department = "Psychology"
    sec_of["B1#T"].department = "Economics"
    sec_of["B2#T"].department = "Economics"
    state = State(sec_of, {"A1": ["i1"], "A2": ["i2"], "B1": ["i3"], "B2": ["i4"]}, set())
    state.occupy("A1#T", Candidate("A1#T", "R1", "Mo", 9, 1))
    state.occupy("A2#T", Candidate("A2#T", "R1", "Mo", 16, 1))
    state.occupy("B1#T", Candidate("B1#T", "R2", "Mo", 16, 1))
    state.occupy("B2#T", Candidate("B2#T", "R2", "Tu", 16, 1))

    terms = _global_terms(state, Config(primetime_start=9, primetime_end=16))

    assert terms["dept_fairness"] == 2


def test_global_terms_department_primetime_balanced_or_single_dept_is_zero():
    sec_of = {
        "A1#T": _sec("A1", "PSY-2", "PSY101", ["i1"]),
        "A2#T": _sec("A2", "PSY-2", "PSY102", ["i2"]),
        "B1#T": _sec("B1", "ECON-2", "ECON101", ["i3"]),
        "B2#T": _sec("B2", "ECON-2", "ECON102", ["i4"]),
    }
    sec_of["A1#T"].department = "Psychology"
    sec_of["A2#T"].department = "Psychology"
    sec_of["B1#T"].department = "Economics"
    sec_of["B2#T"].department = "Economics"
    state = State(sec_of, {"A1": ["i1"], "A2": ["i2"], "B1": ["i3"], "B2": ["i4"]}, set())
    state.occupy("A1#T", Candidate("A1#T", "R1", "Mo", 9, 1))
    state.occupy("A2#T", Candidate("A2#T", "R1", "Mo", 16, 1))
    state.occupy("B1#T", Candidate("B1#T", "R2", "Mo", 10, 1))
    state.occupy("B2#T", Candidate("B2#T", "R2", "Tu", 16, 1))

    assert _global_terms(state, Config())["dept_fairness"] == 0

    sec_of["B1#T"].department = ""
    sec_of["B1#T"].dept_code = ""
    sec_of["B2#T"].department = ""
    sec_of["B2#T"].dept_code = ""

    assert _global_terms(state, Config())["dept_fairness"] == 0


def test_local_terms_count_department_primetime_for_affected_pairs():
    sec_of = {
        "A1#T": _sec("A1", "PSY-2", "PSY101", ["i1"]),
        "A2#T": _sec("A2", "PSY-2", "PSY102", ["i2"]),
        "B1#T": _sec("B1", "ECON-2", "ECON101", ["i3"]),
        "B2#T": _sec("B2", "ECON-2", "ECON102", ["i4"]),
    }
    sec_of["A1#T"].department = "Psychology"
    sec_of["A2#T"].department = "Psychology"
    sec_of["B1#T"].department = "Economics"
    sec_of["B2#T"].department = "Economics"
    state = State(sec_of, {"A1": ["i1"], "A2": ["i2"], "B1": ["i3"], "B2": ["i4"]}, set())
    state.occupy("A1#T", Candidate("A1#T", "R1", "Mo", 9, 1))
    state.occupy("A2#T", Candidate("A2#T", "R1", "Mo", 16, 1))
    state.occupy("B1#T", Candidate("B1#T", "R2", "Mo", 16, 1))
    state.occupy("B2#T", Candidate("B2#T", "R2", "Tu", 16, 1))

    terms = _local_terms(state, {"PSY-2"}, {"i1"}, {"R1"}, {"A1#T"}, Config())

    assert terms["dept_fairness"] == 2


def test_global_terms_counts_department_building_compactness():
    sec_of = {
        "A#T": _sec("A", "PSY-2", "PSY101", ["i1"]),
        "B#T": _sec("B", "PSY-2", "PSY102", ["i2"]),
        "C#T": _sec("C", "ECON-2", "ECON101", ["i3"]),
    }
    sec_of["A#T"].department = "Psychology"
    sec_of["B#T"].department = "Psychology"
    sec_of["C#T"].department = "Economics"
    state = State(sec_of, {"A": ["i1"], "B": ["i2"], "C": ["i3"]}, set())
    state.occupy("A#T", Candidate("A#T", "A101", "Mo", 9, 1))
    state.occupy("B#T", Candidate("B#T", "B201", "Tu", 9, 1))
    state.occupy("C#T", Candidate("C#T", "C301", "We", 9, 1))

    terms = _global_terms(state, Config())

    assert terms["dept_compactness"] == 1


def test_local_terms_count_department_compactness_for_affected_department():
    sec_of = {
        "A#T": _sec("A", "PSY-2", "PSY101", ["i1"]),
        "B#T": _sec("B", "PSY-2", "PSY102", ["i2"]),
        "C#T": _sec("C", "ECON-2", "ECON101", ["i3"]),
    }
    sec_of["A#T"].department = "Psychology"
    sec_of["B#T"].department = "Psychology"
    sec_of["C#T"].department = "Economics"
    state = State(sec_of, {"A": ["i1"], "B": ["i2"], "C": ["i3"]}, set())
    state.occupy("A#T", Candidate("A#T", "A101", "Mo", 9, 1))
    state.occupy("B#T", Candidate("B#T", "B201", "Tu", 9, 1))
    state.occupy("C#T", Candidate("C#T", "C301", "We", 9, 1))

    terms = _local_terms(state, {"PSY-2"}, {"i1"}, {"A101", "B201"}, {"A#T"}, Config())

    assert terms["dept_compactness"] == 1


def test_global_terms_count_evening_instr_idle_and_fairness():
    sec_of = {
        "A#T": _sec("A", "PSY-2", "PSY101", ["i1"]),
        "B#T": _sec("B", "PSY-2", "PSY102", ["i1"]),
    }
    state = State(sec_of, {"A": ["i1"], "B": ["i1"]}, set())
    state.occupy("A#T", Candidate("A#T", "R1", "Mo", 9, 2))
    state.occupy("B#T", Candidate("B#T", "R2", "Mo", 15, 3))

    t = _global_terms(state, Config(evening_from_hour=17))

    assert t["evening"] == 2        # cohort hour 17 + instructor hour 17
    assert t["instr_idle"] == 4     # i1: span 09-18, load 5
    assert t["fairness"] == 50      # cohort pain 5^2 + instructor pain 5^2


def test_local_terms_consistency_with_global():
    sec_of = {"A#T": _sec("A", "PSY-2", "PSY101", ["i1"]),
              "B#T": _sec("B", "PSY-2", "PSY102", ["i2"])}
    state = State(sec_of, {"A": ["i1"], "B": ["i2"]}, set())
    state.occupy("A#T", Candidate("A#T", "R1", "Mo", 9, 2))
    state.occupy("B#T", Candidate("B#T", "R1", "Mo", 11, 2))
    cfg = Config(free_day_year_levels=(2,))
    g = _global_terms(state, cfg)
    allc = {state.sec_of[b].cohort_key for b in state.placed}
    alli = {i for b in state.placed for i in state.sec_instr.get(state.sec_of[b].section_id, [])}
    allr = {c.room for c in state.placed.values()}
    l = _local_terms(state, allc, alli, allr, set(state.placed), cfg)
    assert l == g


def test_norm_obj_weights_and_normalization():
    base = {"idle": 10, "maxrun": 5, "instr_days": 20, "nonadjacent": 3,
            "evening": 2, "instr_idle": 4, "fairness": 8,
            "room_stable": 4, "free_day": 2, "room_util": 6, "min_working_days": 2,
            "parallel_coord": 5,
            "conf": 0,
            "instr_avoid_viol": 0, "instr_prefer_miss": 0, "avoid_pairs_viol": 0,
            "building_change": 0, "perturbation": 0, "dept_compactness": 2,
            "dept_fairness": 2, "session_gap": 2}
    cfg = Config(w_idle=15, w_maxrun=10, w_instr_days=10, w_nonadjacent=10,
                 w_evening=10, w_instr_idle=10, w_fairness=10,
                 w_room_stable=10, w_free_day=10, w_room_util=1,
                 w_min_working_days=10, w_parallel_coord=10, w_dept_compact=10,
                 w_dept_fairness=10, w_session_gap=10)
    # at base, every term/base == 1 -> objective == sum of weights
    assert _norm_obj(base, base, cfg) == 15 + 10 + 10 + 10 + 10 + 10 + 10 + 10 + 10 + 1 + 10 + 10 + 10 + 10 + 10
    halved = dict(base, idle=5)               # idle halved -> drops 7.5
    assert abs(_norm_obj(halved, base, cfg)
               - (15 * 0.5 + 10 + 10 + 10 + 10 + 10 + 10 + 10 + 10 + 1 + 10 + 10 + 10 + 10 + 10)) < 1e-9


def test_global_terms_counts_min_working_days_missing_days():
    sec_of = {"A#T": _sec("A", "PSY-2", "PSY101", ["i1"], min_working_days=2)}
    state = State(sec_of, {"A": ["i1"]}, set())
    state.occupy("A#T", Candidate("A#T", "R1", "Mo", 9, 1))

    assert _global_terms(state, Config())["min_working_days"] == 1


def test_local_terms_counts_min_working_days_for_affected_section():
    sec_of = {
        "A#T": _sec("A", "PSY-2", "PSY101", ["i1"], min_working_days=2),
        "B#T": _sec("B", "PSY-2", "PSY102", ["i2"], min_working_days=2),
    }
    state = State(sec_of, {"A": ["i1"], "B": ["i2"]}, set())
    state.occupy("A#T", Candidate("A#T", "R1", "Mo", 9, 1))
    state.occupy("B#T", Candidate("B#T", "R1", "Mo", 11, 1))

    terms = _local_terms(state, {"PSY-2"}, {"i1"}, {"R1"}, {"A#T"}, Config())

    assert terms["min_working_days"] == 1


def test_avoid_pairs_viol_no_overlap():
    placed = {
        "A#T": Candidate("A#T", "R1", "Mo", 9, 2),
        "B#T": Candidate("B#T", "R1", "Tu", 9, 2),
    }
    sec_of = {
        "A#T": _sec("A", "PSY-2", "CS101", ["i1"]),
        "B#T": _sec("B", "PSY-3", "CS102", ["i2"]),
    }
    pairs = (frozenset({"CS101", "CS102"}),)
    assert _avoid_pairs_viol(placed, sec_of, pairs) == 0


def test_avoid_pairs_viol_overlap():
    placed = {
        "A#T": Candidate("A#T", "R1", "Mo", 9, 2),   # hours 9, 10
        "B#T": Candidate("B#T", "R2", "Mo", 10, 2),  # hours 10, 11
    }
    sec_of = {
        "A#T": _sec("A", "PSY-2", "CS101", ["i1"]),
        "B#T": _sec("B", "PSY-3", "CS102", ["i2"]),
    }
    pairs = (frozenset({"CS101", "CS102"}),)
    assert _avoid_pairs_viol(placed, sec_of, pairs) == 1   # hour 10 overlaps


def test_parallel_same_time_penalty_drops_when_theory_slots_match():
    sec_of = {
        "A_01#T": _sec("A_01", "PSY-2", "PSY101", ["i1"]),
        "A_02#T": _sec("A_02", "PSY-2", "PSY101", ["i2"]),
    }
    state = State(sec_of, {"A_01": ["i1"], "A_02": ["i2"]}, set())
    state.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    state.occupy("A_02#T", Candidate("A_02#T", "R2", "Tu", 9, 2))
    cfg = Config(parallel_policies=(("PSY101", "same-time"),))
    assert _global_terms(state, cfg)["parallel_coord"] == 1
    state.release("A_02#T")
    state.occupy("A_02#T", Candidate("A_02#T", "R2", "Mo", 9, 2))
    assert _global_terms(state, cfg)["parallel_coord"] == 0


def test_parallel_spread_penalizes_matching_theory_slots():
    sec_of = {
        "A_01#T": _sec("A_01", "PSY-2", "PSY101", ["i1"]),
        "A_02#T": _sec("A_02", "PSY-2", "PSY101", ["i2"]),
    }
    state = State(sec_of, {"A_01": ["i1"], "A_02": ["i2"]}, set())
    state.occupy("A_01#T", Candidate("A_01#T", "R1", "Mo", 9, 2))
    state.occupy("A_02#T", Candidate("A_02#T", "R2", "Mo", 9, 2))
    cfg = Config(parallel_policies=(("PSY101", "spread"),))
    assert _global_terms(state, cfg)["parallel_coord"] == 1
    state.release("A_02#T")
    state.occupy("A_02#T", Candidate("A_02#T", "R2", "Tu", 9, 2))
    assert _global_terms(state, cfg)["parallel_coord"] == 0


def test_parallel_lab_after_theory_penalizes_early_lab():
    sec = _sec("A_01", "PSY-2", "PSY101", ["i1"])
    lab = _sec("A_01", "PSY-2", "PSY101", ["i1"])
    sec_of = {"A_01#T": sec, "A_01#L": lab}
    state = State(sec_of, {"A_01": ["i1"]}, set())
    state.occupy("A_01#T", Candidate("A_01#T", "R1", "Tu", 9, 2))
    state.occupy("A_01#L", Candidate("A_01#L", "R2", "Mo", 9, 2))
    cfg = Config(parallel_policies=(("PSY101", "lab-after-theory"),))
    assert _global_terms(state, cfg)["parallel_coord"] == 1
    state.release("A_01#L")
    state.occupy("A_01#L", Candidate("A_01#L", "R2", "We", 9, 2))
    assert _global_terms(state, cfg)["parallel_coord"] == 0
