"""Controlled multi-seed acceptor A/B for the move-based soft polish, from ONE shared snapshot.

WHY: single-run steerability is high-variance (room_stable swung -0.6% .. +8.0% across two
runs with different snapshots). To DECIDE lahc vs deluge vs schc we must (1) hold the snapshot
fixed and (2) average over seeds. This converges ONE placement, then runs every (acceptor x
seed x weight-profile) combo from that identical snapshot. The only things that vary are the
acceptor and the RNG seed, so differences are the acceptor effect + measurable variance.

Reports:
  (1) optimization depth + UNIFORM balance: soft_end E (comparable across snapshots — always
      starts at Σ weights = 55 for UNIFORM) and the 5 term counts, mean over seeds.
  (2) steering: per-dial selected_gain = (uni_term - max_term)/uni_term, computed WITHIN each
      (acceptor,seed) then aggregated mean[min,max] over seeds. Sign-stable + large = reliable.

Usage: PYTHONPATH=src python3 bench/acceptor_ab.py [N] [converge_s] [anneal_s] [n_seeds]
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
anneal_s = float(sys.argv[3]) if len(sys.argv) > 3 else 60.0
n_seeds = int(sys.argv[4]) if len(sys.argv) > 4 else 3

import os as _os0
ACCEPTORS = _os0.environ.get("ACCEPTORS", "lahc,deluge,schc").split(",")
SEEDS = list(range(n_seeds))
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

# ---- load + build (identical to norm_ab.py / steerability.py for comparability) ----
import os as _os
PERIOD = _os.environ.get("PERIOD", "001")                 # "001" Fall (default) | "002" Spring
courses = ok_rows(parse_courselist(read_raw(f"data/sample_courses_2025_{PERIOD}.csv")))[:N]
cfg0 = build_config({}, {}, anneal_s)
cfg0 = replace(cfg0, free_day_year_levels=(2, 3, 4))
cfg0 = replace(cfg0, w_idle=float(_os.environ.get("W_IDLE", cfg0.w_idle)))
cfg0 = replace(cfg0, max_instr_days=int(_os.environ.get("MAX_INSTR_DAYS", 2)))
cfg0 = replace(cfg0, max_rooms_per_block=max(cfg0.max_rooms_per_block, REPAIR_MAX_ROOMS))

secs, _ = build_sections_from_courselist(courses, PERIOD, cfg0)
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
    cand_by_block[b.block_id] = gen_candidates(b, s, _instructors_of(s, instr), room_list, cfg0)
order = sorted((b.block_id for b, _ in blocks),
               key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))

# ---- converge ONE placement (shared by all acceptors+seeds) ----
print(f"[converge] N={N} blocks={total} converge={converge_s:.0f}s anneal={anneal_s:.0f}s/run "
      f"acceptors={ACCEPTORS} seeds={SEEDS}", flush=True)
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
base = _global_terms(state, cfg0)
print(f"[converge] done {perf_counter() - t0:.0f}s placed={len(snapshot)}/{total} "
      f"({len(snapshot) / total:.2%})", flush=True)
print(f"[base] " + " ".join(f"{k}={base[k]}" for k in TERMS + ("conf",)), flush=True)


def fresh_state():
    st = State(sec_of, sec_instr, virtual_names)
    for bid, c in snapshot.items():
        st.occupy(bid, c)
    return st


# ---- run every (acceptor, seed, profile) from the shared snapshot ----
# results[acc][seed][profile] = {"post": terms, "E": soft_end}
results = {a: {s: {} for s in SEEDS} for a in ACCEPTORS}
for acc in ACCEPTORS:
    for seed in SEEDS:
        for name, overrides in PROFILES.items():
            cfg = replace(cfg0, soft_polish_acceptor=acc, **overrides)
            st = fresh_state()
            info = anneal_soft(st, cand_by_block, cfg, anneal_s, seed=seed)
            post = _global_terms(st, cfg)
            results[acc][seed][name] = {"post": post, "E": info["soft_end"]}
        u = results[acc][seed]["UNIFORM"]
        print(f"  [{acc:6s} seed={seed}] UNIFORM E={u['E']:.2f} | "
              + " ".join(f"{k} {u['post'][k]}" for k in TERMS)
              + f" | conf {u['post']['conf']}", flush=True)


def agg(vals):
    return sum(vals) / len(vals), min(vals), max(vals)


# ---- (1) optimization depth + UNIFORM balance ----
print("\n=== (1) OPTIMIZATION DEPTH + UNIFORM BALANCE (mean over seeds; E starts 55, lower=better) ===")
print(f"{'acceptor':9s} {'E_end':>18s} " + " ".join(f"{t:>12s}" for t in TERMS))
for acc in ACCEPTORS:
    Es = [results[acc][s]["UNIFORM"]["E"] for s in SEEDS]
    em, elo, ehi = agg(Es)
    cells = []
    for t in TERMS:
        tm, _, _ = agg([results[acc][s]["UNIFORM"]["post"][t] for s in SEEDS])
        cells.append(f"{tm:>12.0f}")
    print(f"{acc:9s} {em:>7.2f}[{elo:.1f},{ehi:.1f}] " + " ".join(cells))
print(f"{'base':9s} {'55.00':>18s} " + " ".join(f"{base[t]:>12d}" for t in TERMS))

# ---- (2) steering: per-dial selected_gain, mean[min,max] over seeds ----
print("\n=== (2) STEERING: selected_gain = (uni-max)/uni per (acc,seed), mean[min,max] over seeds ===")
print("    (+ = maxing the dial improved its term vs same-run uniform; sign-stable+large = reliable)")
print(f"{'acceptor':9s} " + " ".join(f"{SELECTED[p]:>22s}" for p in
      ("MAXRUN_MAX", "DAYS_MAX", "ROOM_MAX", "FREE_MAX")))
for acc in ACCEPTORS:
    cells = []
    for p in ("MAXRUN_MAX", "DAYS_MAX", "ROOM_MAX", "FREE_MAX"):
        sel = SELECTED[p]
        gains = []
        for s in SEEDS:
            uni = results[acc][s]["UNIFORM"]["post"][sel]
            mx = results[acc][s][p]["post"][sel]
            gains.append((uni - mx) / uni if uni else 0.0)
        gm, glo, ghi = agg(gains)
        stable = "" if (glo > 0 and ghi > 0) or (glo < 0 and ghi < 0) else "~"  # ~ = sign flips
        cells.append(f"{gm:+5.1%}[{glo:+4.0%},{ghi:+4.0%}]{stable}")
    print(f"{acc:9s} " + " ".join(f"{c:>22s}" for c in cells))

# ---- (3) collateral: mean total |Δ| on non-selected terms when maxing a dial ----
print("\n=== (3) COLLATERAL: mean Σ|other-term %change vs uniform| when maxing each dial ===")
print(f"{'acceptor':9s} " + " ".join(f"{SELECTED[p]:>12s}" for p in
      ("MAXRUN_MAX", "DAYS_MAX", "ROOM_MAX", "FREE_MAX")))
for acc in ACCEPTORS:
    cells = []
    for p in ("MAXRUN_MAX", "DAYS_MAX", "ROOM_MAX", "FREE_MAX"):
        sel = SELECTED[p]
        cols = []
        for s in SEEDS:
            uni = results[acc][s]["UNIFORM"]["post"]
            mx = results[acc][s][p]["post"]
            col = sum(abs((mx[t] - uni[t]) / uni[t]) for t in TERMS if t != sel and uni[t])
            cols.append(col)
        cm, _, _ = agg(cols)
        cells.append(f"{cm:>11.1%}")
    print(f"{acc:9s} " + " ".join(f"{c:>12s}" for c in cells))
