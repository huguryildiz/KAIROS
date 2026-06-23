"""Does the try_free_cohort_day compound move actually give cohorts a free day?

The steerability gate asks the WRONG question for free_day (weight-responsiveness). The
RIGHT question: with free_day active, does enabling the compound move leave MORE cohorts
with a free day than disabling it? This converges ONE snapshot, then runs anneal_soft from
that identical snapshot with the move ON vs OFF (monkeypatched to None), free_day weight
maxed in both arms, over several seeds. Reports the free_day TERM and the actual COUNT of
configured cohorts that end up with >=1 free day.

Usage: PERIOD=001 PYTHONPATH=src python3 bench/free_day_move_ab.py [N] [converge_s] [anneal_s] [n_seeds]
"""
import os
import sys
from dataclasses import replace
from time import perf_counter

import timetabling.soft_search as ss
from timetabling.csv_import import read_raw, parse_courselist, ok_rows, parse_classrooms, ok_rooms
from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                   build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.model_cpsat import gen_candidates, _instructors_of
from timetabling.repair import (State, greedy_construct, repair_round, BATCH,
                                REPAIR_MAX_ROOMS)
from timetabling.soft_search import anneal_soft, _global_terms

N = int(sys.argv[1]) if len(sys.argv) > 1 else 400
converge_s = float(sys.argv[2]) if len(sys.argv) > 2 else 60.0
anneal_s = float(sys.argv[3]) if len(sys.argv) > 3 else 30.0
n_seeds = int(sys.argv[4]) if len(sys.argv) > 4 else 5
SEEDS = list(range(n_seeds))
PERIOD = os.environ.get("PERIOD", "001")
YEARS = (2, 3, 4)

courses = ok_rows(parse_courselist(read_raw(f"data/sample_courses_2025_{PERIOD}.csv")))[:N]
cfg0 = build_config({}, {}, anneal_s)
cfg0 = replace(cfg0, soft_polish_acceptor="deluge")
cfg0 = replace(cfg0, free_day_year_levels=YEARS)
cfg0 = replace(cfg0, w_free_day=20.0)                      # free_day maxed in BOTH arms
cfg0 = replace(cfg0, max_instr_days=int(os.environ.get("MAX_INSTR_DAYS", 2)))
cfg0 = replace(cfg0, max_rooms_per_block=max(cfg0.max_rooms_per_block, REPAIR_MAX_ROOMS))

secs, _ = build_sections_from_courselist(courses, PERIOD, cfg0)
instr = build_instructors_from_courselist(courses)
rooms = build_rooms_from_ui(ok_rooms(parse_classrooms(read_raw("data/classrooms.csv"))), cfg0)
mark_virtual(secs, rooms, cfg0)
room_list = list(rooms.values())
virtual_names = {r.room for r in room_list if r.is_virtual}
blocks = [(b, s) for s in secs for b in s.blocks]
total = len(blocks)
sec_of = {b.block_id: s for b, s in blocks}
sec_instr = {s.section_id: s.instructor_ids for s in secs}
cand_by_block = {}
for b, s in blocks:
    cand_by_block[b.block_id] = gen_candidates(b, s, _instructors_of(s, instr), room_list, cfg0)
order = sorted((b.block_id for b, _ in blocks),
               key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))

n_days = len(cfg0.days())
years = {str(y) for y in YEARS}


def cohort_stats(state):
    """(#configured cohorts, #with a free day, free_day term) from a placed state."""
    days_by_cohort = {}
    for bid, c in state.placed.items():
        ck = sec_of[bid].cohort_key
        if ck.rsplit("-", 1)[-1] in years:
            days_by_cohort.setdefault(ck, set()).add(c.day)
    n_cohorts = len(days_by_cohort)
    n_free = sum(1 for d in days_by_cohort.values() if len(d) < n_days)
    term = sum(max(0, len(d) - (n_days - 1)) for d in days_by_cohort.values())
    return n_cohorts, n_free, term


print(f"[converge] PERIOD={PERIOD} N={N} blocks={total} seeds={SEEDS}", flush=True)
state = State(sec_of, sec_instr, virtual_names)
t0 = perf_counter()
greedy_construct(state, order, cand_by_block, cfg0)
sweep = 0
while perf_counter() - t0 < converge_s:
    sweep += 1
    unplaced = [b.block_id for b, s in blocks if b.block_id not in state.placed]
    if not unplaced:
        break
    unplaced.sort(key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))
    gained = 0
    for i in range(0, len(unplaced), BATCH):
        if perf_counter() - t0 >= converge_s:
            break
        batch = [bid for bid in unplaced[i:i + BATCH] if bid not in state.placed]
        if batch:
            gained += repair_round(state, batch, cand_by_block)
    if gained == 0 or sweep >= 25:
        break
snapshot = dict(state.placed)
nc, nf, term = cohort_stats(state)
print(f"[converge] done {perf_counter()-t0:.0f}s placed={len(snapshot)}/{total} "
      f"({len(snapshot)/total:.1%}) | configured cohorts={nc} with-free-day={nf} "
      f"free_day_term={term}", flush=True)


def fresh_state():
    st = State(sec_of, sec_instr, virtual_names)
    for bid, c in snapshot.items():
        st.occupy(bid, c)
    return st


_real_move = ss.try_free_cohort_day


def run_arm(move_on):
    ss.try_free_cohort_day = _real_move if move_on else (lambda *a, **k: None)
    frees, terms, confs = [], [], []
    for seed in SEEDS:
        st = fresh_state()
        anneal_soft(st, cand_by_block, cfg0, anneal_s, seed=seed)
        nc, nf, term = cohort_stats(st)
        frees.append(nf)
        terms.append(term)
        confs.append(_global_terms(st, cfg0)["conf"])
    ss.try_free_cohort_day = _real_move
    return frees, terms, confs


def agg(v):
    return sum(v) / len(v), min(v), max(v)


nc0, nf0, _ = cohort_stats(state)
print(f"\nconfigured cohorts = {nc0} (free_day weight = 20 in BOTH arms)\n", flush=True)
for label, on in (("MOVE OFF", False), ("MOVE ON ", True)):
    frees, terms, confs = run_arm(on)
    fm, flo, fhi = agg(frees)
    tm, tlo, thi = agg(terms)
    print(f"[{label}] cohorts-with-free-day {fm:.1f}[{flo},{fhi}]  "
          f"free_day_term {tm:.1f}[{tlo},{thi}]  conf {agg(confs)[0]:.0f}", flush=True)
