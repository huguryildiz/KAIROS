from dataclasses import replace

from timetabling.config import Config
from timetabling.repair import State
from timetabling.model import Candidate, Section
from timetabling.soft_search import _run_excess, _global_terms, _local_terms, _norm_obj


def test_run_excess_counts_only_beyond_threshold():
    assert _run_excess({9, 10, 11}, 3) == 0          # exactly 3 consecutive -> ok
    assert _run_excess({9, 10, 11, 12}, 3) == 1      # 4 consecutive -> 1 over
    assert _run_excess({9, 10, 13, 14}, 3) == 0      # two runs of 2 -> ok
    assert _run_excess(set(), 3) == 0


def _sec(sid, cohort, code, iids):
    return Section(section_id=sid, period="001", code=code, name=code, level=2,
                   dept_code=cohort.split("-")[0], department="F", cohort_key=cohort,
                   instructor_ids=iids, students=10, T=0, P=0, L=0, Cr=0, category="",
                   blocks=[])


def test_global_terms_keys_and_room_stable():
    sec_of = {"A#T": _sec("A", "PSY-2", "PSY101", ["i1"])}
    state = State(sec_of, {"A": ["i1"]}, set())
    state.occupy("A#T", Candidate("A#T", "R1", "Mo", 9, 2))
    t = _global_terms(state, Config(max_instr_days=0))   # threshold 0 -> term == raw teaching-day count
    assert set(t) == {"idle", "maxrun", "instr_days", "nonadjacent", "evening",
                      "instr_idle", "fairness", "room_stable", "free_day", "conf"}
    assert t["room_stable"] == 0          # one section, one room
    assert t["instr_days"] == 1           # i1 teaches 1 day, excess over 0 = 1
    assert t["evening"] == 0
    assert t["instr_idle"] == 0
    assert t["fairness"] == 0


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
            "room_stable": 4, "free_day": 2, "conf": 0}
    cfg = Config(w_idle=15, w_maxrun=10, w_instr_days=10, w_nonadjacent=10,
                 w_evening=10, w_instr_idle=10, w_fairness=10,
                 w_room_stable=10, w_free_day=10)
    # at base, every term/base == 1 -> objective == sum of weights
    assert _norm_obj(base, base, cfg) == 15 + 10 + 10 + 10 + 10 + 10 + 10 + 10 + 10
    halved = dict(base, idle=5)               # idle halved -> drops 7.5
    assert abs(_norm_obj(halved, base, cfg)
               - (15 * 0.5 + 10 + 10 + 10 + 10 + 10 + 10 + 10 + 10)) < 1e-9
