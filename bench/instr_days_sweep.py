"""Converge-per-dial sweep for the instructor teaching-day concentration lever (`instr_days`).

WHY (vs bench/steerability.py): the steerability gate varies max_instr_days on ONE frozen
snapshot and runs polish only — that tests a POLISH lever. A CONSTRUCTION-time lever (the
day-affinity tie-break in greedy_construct) changes the converged placement itself, so it must
be measured by RE-CONVERGING once per dial value. This script does exactly that: for each
max_instr_days in {5,4,3,2,1} it builds a fresh State, runs the same greedy + pure-placement
repair sweeps as solve_repair, and reports the instructor teaching-day histogram (the §5
distribution sweep) from the converged snapshot.

ACCEPTANCE (a real, monotone dial): as the target tightens 5->1 the mean teaching-days must
fall and the @1day share must climb, with conf held and placement not regressing. Today's main
is BLIND to the dial in construction (greedy/repair never read max_instr_days), so the baseline
rows are identical across columns — that identical baseline is the numeric "does not bind".

Usage: PYTHONPATH=src python3 bench/instr_days_sweep.py [N] [converge_s] [polish_s]
  N=9999 keeps all ~990 courses; converge_s caps each per-value placement phase; polish_s>0
  additionally runs anneal_soft after converge (default 0 = converge-only, the construction signal).
"""
import sys
from collections import Counter
from dataclasses import replace
from time import perf_counter

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
converge_s = float(sys.argv[2]) if len(sys.argv) > 2 else 90.0
polish_s = float(sys.argv[3]) if len(sys.argv) > 3 else 0.0

TARGETS = [5, 4, 3, 2, 1]          # max_instr_days values to sweep (5 = off)
W_DAYS = 20.0                       # highest weight, so the term has every chance to bind

# ---- load + build (weight-independent: candidate generation ignores soft weights) ----
courses = ok_rows(parse_courselist(read_raw("data/sample_courses_2025_001.csv")))[:N]
cfg0 = build_config({}, {}, polish_s or 90.0)
cfg0 = replace(cfg0, soft_polish_acceptor="lahc")
cfg0 = replace(cfg0, w_instr_days=W_DAYS)
cfg0 = replace(cfg0, max_rooms_per_block=max(cfg0.max_rooms_per_block, REPAIR_MAX_ROOMS))

secs, _ = build_sections_from_courselist(courses, "001", cfg0)
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
    ins_list = _instructors_of(s, instr)
    cand_by_block[b.block_id] = gen_candidates(b, s, ins_list, room_list, cfg0)
order = sorted((b.block_id for b, _ in blocks),
               key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))

print(f"[setup] N={N} blocks={total} converge_s={converge_s:.0f} polish_s={polish_s:.0f} "
      f"w_instr_days={W_DAYS}", flush=True)


def converge(cfg):
    """Mirror solve_repair's placement phase: greedy_construct (soft-shaping ON, so a
    construction-time instr_days bias would act here) + pure-placement repair sweeps."""
    state = State(sec_of, sec_instr, virtual_names)
    t0 = perf_counter()
    greedy_construct(state, order, cand_by_block, cfg)
    sweep = 0
    while perf_counter() - t0 < converge_s:
        sweep += 1
        unplaced = [bid for bid, _ in [(b.block_id, s) for b, s in blocks]
                    if bid not in state.placed]
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
    return state, sweep, perf_counter() - t0


def measure(state):
    """Per-instructor teaching-day distribution over the converged placement."""
    teach = [len(d) for d in state.instr_active_days.values() if d]
    n = len(teach)
    hist = Counter(teach)
    mean = sum(teach) / n if n else 0.0
    at1 = hist.get(1, 0) / n if n else 0.0
    return {"hist": hist, "n": n, "mean": mean, "at1": at1, "placed": len(state.placed)}


# ---- sweep ----
results = {}
for v in TARGETS:
    cfg = replace(cfg0, max_instr_days=v)
    state, sweep, wall = converge(cfg)
    if polish_s > 0:
        anneal_soft(state, cand_by_block, cfg, polish_s, seed=cfg.soft_polish_seed)
    m = measure(state)
    g = _global_terms(state, cfg)
    results[v] = {**m, "excess": g["instr_days"], "conf": g["conf"], "sweep": sweep, "wall": wall}
    print(f"[t={v}] converge={wall:.0f}s sweeps={sweep} placed={m['placed']}/{total} "
          f"instr={m['n']} mean={m['mean']:.2f} @1day={m['at1']:.0%} "
          f"excess(>{v})={g['instr_days']} conf={g['conf']}", flush=True)

# ---- §5-style histogram table ----
max_d = max((max(r["hist"], default=0) for r in results.values()), default=0)
print("\n=== INSTRUCTOR TEACHING-DAY DISTRIBUTION (converged; columns = max_instr_days) ===")
print(f"{'#days':>6s} | " + " ".join(f"t={v:<3d}" for v in TARGETS))
for d in range(1, max_d + 1):
    print(f"{d:>6d} | " + " ".join(f"{results[v]['hist'].get(d, 0):<4d}" for v in TARGETS))
print(f"{'mean':>6s} | " + " ".join(f"{results[v]['mean']:<4.2f}" for v in TARGETS))
print(f"{'@1day':>6s} | " + " ".join(f"{results[v]['at1']*100:<4.0f}" for v in TARGETS))
print(f"{'conf':>6s} | " + " ".join(f"{results[v]['conf']:<4d}" for v in TARGETS))
print("\nBINDS iff mean falls and @1day climbs as t tightens 5->1, with conf held and "
      "placed not regressing. Identical columns = construction is blind to the dial.")
