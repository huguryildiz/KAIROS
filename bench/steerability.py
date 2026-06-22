"""Same-start steerability test for the min-max (augmented-Chebyshev) soft polish.

WHY: cross-run weight comparison is confounded — each pipeline run converges a DIFFERENT
placement (CP-SAT is nondeterministic), so a weight effect is buried under placement noise.
This script removes that noise: it converges ONE placement (greedy + repair sweeps, exactly
as solve_repair does), snapshots the State, then runs anneal_soft from that SAME snapshot
under several weight profiles with the SAME RNG seed. The only thing that varies between
profiles is the weight dial, so any difference in the post-polish terms is the weight effect.

PROFILES (UI_REF=20 -> normal=10, max=20; only the ratio matters under normalization):
  UNIFORM   : idle fixed at 15, all four dials = 10 (normal)
  MAXRUN_MAX: maxrun = 20, rest at their UNIFORM values
  DAYS_MAX  : instr_days = 20, rest at their UNIFORM values
  ROOM_MAX  : room_stable = 20, rest at their UNIFORM values
  FREE_MAX  : free_day = 20, rest at their UNIFORM values

METRICS (post values P, all profiles share the same pre/base snapshot):
  selected_gain_i   = (P_i^uniform - P_i^scenario) / P_i^uniform   (+ = scenario beats uniform on its toggle)
  collateral_loss_j = (P_j^scenario - P_j^uniform) / P_j^uniform   (+ = scenario worse than uniform elsewhere)

Usage: PYTHONPATH=src python3 bench/steerability.py [N] [converge_s] [anneal_s] [acceptor]
  N=9999 keeps all ~990 courses; converge_s caps the placement phase; anneal_s is the
  per-profile polish budget; acceptor in {lahc,schc,deluge,sa} (default lahc).
"""
import sys
from dataclasses import replace
from time import perf_counter

from timetabling.csv_import import read_raw, parse_courselist, ok_rows
from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                   build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.model_cpsat import gen_candidates, _instructors_of
from timetabling.repair import (State, greedy_construct, repair_round, BATCH,
                                REPAIR_MAX_ROOMS)
from timetabling.soft_search import anneal_soft, _global_terms

N = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
converge_s = float(sys.argv[2]) if len(sys.argv) > 2 else 400.0
anneal_s = float(sys.argv[3]) if len(sys.argv) > 3 else 90.0
acceptor = sys.argv[4] if len(sys.argv) > 4 else "lahc"

PROFILES = {
    "UNIFORM":    {},
    "MAXRUN_MAX": {"w_maxrun": 20.0},
    "DAYS_MAX":   {"w_instr_days": 20.0},
    "ROOM_MAX":   {"w_room_stable": 20.0},
    "FREE_MAX":   {"w_free_day": 20.0},
}
SELECTED = {"MAXRUN_MAX": "maxrun", "DAYS_MAX": "instr_days",
            "ROOM_MAX": "room_stable", "FREE_MAX": "free_day"}
TERMS = ("idle", "maxrun", "instr_days", "room_stable", "free_day")

# ---- load + build (weight-independent: candidate generation ignores soft weights) ----
courses = ok_rows(parse_courselist(read_raw("data/sample_courses_2025_001.csv")))[:N]
cfg0 = build_config({}, {}, anneal_s)                       # idle=15 fixed, dials=10 (normal)
cfg0 = replace(cfg0, soft_polish_acceptor=acceptor)
cfg0 = replace(cfg0, free_day_year_levels=(2, 3, 4))       # activate free_day so it can steer
import os as _os                                            # W_IDLE override for idle-dominance retest
cfg0 = replace(cfg0, w_idle=float(_os.environ.get("W_IDLE", cfg0.w_idle)))
cfg0 = replace(cfg0, max_instr_days=int(_os.environ.get("MAX_INSTR_DAYS", 2)))  # excess headroom for DAYS_MAX
cfg0 = replace(cfg0, max_rooms_per_block=max(cfg0.max_rooms_per_block, REPAIR_MAX_ROOMS))

secs, _ = build_sections_from_courselist(courses, "001", cfg0)
instr = build_instructors_from_courselist(courses)
rooms = build_rooms_from_ui([dict(r) for r in DEFAULT_CLASSROOMS], cfg0)
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

# ---- converge ONE placement (mirrors solve_repair: greedy + pure-placement sweeps) ----
print(f"[converge] N={N} blocks={total} converge_budget={converge_s:.0f}s "
      f"anneal_budget={anneal_s:.0f}s/profile acceptor={acceptor}", flush=True)
state = State(sec_of, sec_instr, virtual_names)
t0 = perf_counter()
greedy_construct(state, order, cand_by_block, cfg0)
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

snapshot = dict(state.placed)
placed_n = len(snapshot)
base = _global_terms(state, cfg0)
print(f"[converge] done in {perf_counter() - t0:.0f}s sweeps={sweep} "
      f"placed={placed_n}/{total} ({placed_n / total:.2%}) tail={total - placed_n}", flush=True)
print(f"[base/pre] " + " ".join(f"{k}={base[k]}" for k in TERMS + ("conf",)),
      flush=True)


def fresh_state():
    """A clean State re-occupied from the converged snapshot — identical starting point for
    every profile (anneal_soft mutates state in place, so each profile needs its own)."""
    st = State(sec_of, sec_instr, virtual_names)
    for bid, c in snapshot.items():
        st.occupy(bid, c)
    return st


# ---- run anneal_soft from the SAME snapshot under each weight profile ----
results = {}
for name, overrides in PROFILES.items():
    cfg = replace(cfg0, **overrides) if overrides else cfg0
    st = fresh_state()
    pre = _global_terms(st, cfg)             # == base for every profile (same snapshot)
    ts = perf_counter()
    info = anneal_soft(st, cand_by_block, cfg, anneal_s, seed=cfg.soft_polish_seed)
    post = _global_terms(st, cfg)
    results[name] = {"post": post, "info": info, "wall": perf_counter() - ts}
    sel = SELECTED.get(name, "-")
    print(f"[{name:8s}] sel={sel:7s} wall={results[name]['wall']:.0f}s "
          f"iters={info['iters']} acc={info['accepted']} "
          f"E {info['soft_start']:.4f}->{info['soft_end']:.4f} | "
          + " ".join(f"{k} {base[k]}->{post[k]}" for k in TERMS)
          + f" | conf {base['conf']}->{post['conf']}", flush=True)

# ---- steerability table (vs UNIFORM post) ----
uni = results["UNIFORM"]["post"]
print("\n=== STEERABILITY (post values; deltas vs UNIFORM post) ===")
header = f"{'profile':9s} " + " ".join(f"{t:>20s}" for t in TERMS) + f"{'conf':>8s}"
print(header)
print(f"{'UNIFORM':9s} " + " ".join(f"{uni[t]:>20d}" for t in TERMS) + f"{uni['conf']:>8d}")
for name in ("MAXRUN_MAX", "DAYS_MAX", "ROOM_MAX", "FREE_MAX"):
    post = results[name]["post"]
    sel = SELECTED[name]
    cells = []
    for t in TERMS:
        rel = (post[t] - uni[t]) / uni[t] if uni[t] else 0.0
        if t == sel:                          # selected toggle: report as a GAIN (improvement vs uniform)
            cells.append(f"{post[t]:>6d} g{-rel:+6.1%}*")
        else:                                 # others: report as collateral loss (+ = worse)
            cells.append(f"{post[t]:>6d} c{rel:+6.1%} ")
    print(f"{name:9s} " + " ".join(f"{c:>20s}" for c in cells) + f"{post['conf']:>8d}")
print("\n  * = selected toggle; g = selected_gain (+ better than uniform); "
      "c = collateral_loss (+ worse than uniform). conf must stay <= base "
      f"({base['conf']}).")
