"""One-at-a-time soft-criteria benchmark for the repair solver.

This intentionally separates two questions:

1. Which criteria are directly read by move-based soft polish?
2. Which legacy/CP-SAT soft criteria remain measurable but are not polish dials?

Usage:
  PYTHONPATH=src .venv/bin/python bench/soft_oat.py [period] [N] [converge_s] [anneal_s] [acceptor] [seeds]

Example:
  PYTHONPATH=src .venv/bin/python bench/soft_oat.py 001 9999 80 15 deluge 0,1
"""
from __future__ import annotations

import sys
from collections import defaultdict
from dataclasses import replace
from time import perf_counter

from timetabling.csv_import import (
    ok_rooms,
    ok_rows,
    parse_classrooms,
    parse_courselist,
    read_raw,
)
from timetabling.model_cpsat import _instructors_of, gen_candidates
from timetabling.repair import BATCH, REPAIR_MAX_ROOMS, State, greedy_construct, repair_round
from timetabling.route import mark_virtual
from timetabling.settings import DEFAULT_SETTINGS, build_config
from timetabling.soft_search import _global_terms, anneal_soft
from timetabling.ui_input import (
    build_instructors_from_courselist,
    build_rooms_from_ui,
    build_sections_from_courselist,
)


PERIOD = sys.argv[1] if len(sys.argv) > 1 else "001"
N = int(sys.argv[2]) if len(sys.argv) > 2 else 9999
CONVERGE_S = float(sys.argv[3]) if len(sys.argv) > 3 else 80.0
ANNEAL_S = float(sys.argv[4]) if len(sys.argv) > 4 else 15.0
ACCEPTOR = sys.argv[5] if len(sys.argv) > 5 else "deluge"
SEEDS = [int(s) for s in (sys.argv[6] if len(sys.argv) > 6 else "0").split(",") if s]

POLISH_TERMS = ("idle", "maxrun", "instr_days", "room_stable", "free_day", "conf")
LEGACY_TERMS = (
    "order",
    "englab",
    "cohort_gap",
    "cohort_conflict",
    "instr_days_raw",
    "parttime_days_raw",
    "nonadjacent",
)

PROFILES = {
    "BASE": {},
    "IDLE_MAX": {"w_idle": 30.0},
    "MAXRUN_MAX": {"w_maxrun": 30.0},
    "DAYS_MAX": {"w_instr_days": 30.0, "w_parttime_days": 34.0},
    "ROOM_MAX": {"w_room_stable": 30.0},
    "FREE_MAX": {"w_free_day": 30.0},
    "COHORT_GAP_MAX": {"w_cohort_gap": 30.0},
    "COHORT_CONFLICT_MAX": {"w_cohort_conflict": 150},
    "ORDER_MAX": {"w_order": 10},
    "ENGLAB_MAX": {"w_englab": 10},
    "NONADJ_MAX": {"w_nonadjacent": 10},
}

SELECTED = {
    "IDLE_MAX": "idle",
    "MAXRUN_MAX": "maxrun",
    "DAYS_MAX": "instr_days",
    "ROOM_MAX": "room_stable",
    "FREE_MAX": "free_day",
    "COHORT_GAP_MAX": "cohort_gap",
    "COHORT_CONFLICT_MAX": "cohort_conflict",
    "ORDER_MAX": "order",
    "ENGLAB_MAX": "englab",
    "NONADJ_MAX": "nonadjacent",
}

POLISH_DIALS = {"IDLE_MAX", "MAXRUN_MAX", "DAYS_MAX", "ROOM_MAX", "FREE_MAX"}


def active_settings() -> dict:
    settings = dict(DEFAULT_SETTINGS)
    settings["instr_days_target"] = 2
    settings["free_day_years"] = [2, 3, 4]
    settings["quality_mode"] = "fast"
    settings["weights"] = dict(DEFAULT_SETTINGS["weights"])
    settings["weights"]["instr_days"] = "high"
    return settings


def fresh_state(snapshot, sec_of, sec_instr, virtual_names):
    st = State(sec_of, sec_instr, virtual_names)
    for bid, cand in snapshot.items():
        st.occupy(bid, cand)
    return st


def legacy_terms(state, cfg, instructors) -> dict:
    compact = {str(y) for y in cfg.compact_cohort_years}
    cohort_courses = defaultdict(set)
    cohort_hours = defaultdict(set)
    section_days = defaultdict(lambda: defaultdict(set))

    order = englab = 0
    for bid, cand in state.placed.items():
        sec = state.sec_of[bid]
        if 2 <= sec.level <= 4:
            order += (4 - sec.level) * (cand.start - cfg.horizon_start)
        if cfg.eng_department_match in sec.department and "#L" in bid and cand.day not in cfg.eng_lab_days:
            englab += 1
        if sec.cohort_key.rsplit("-", 1)[-1] in compact:
            for hour in range(cand.start, cand.start + cand.length):
                cohort_hours[(sec.cohort_key, cand.day)].add(hour)
        for hour in range(cand.start, cand.start + cand.length):
            cohort_courses[(sec.cohort_key, cand.day, hour)].add(sec.code)
        section_days[sec.section_id][cand.day].add(bid)

    staff_days = parttime_days = 0
    for iid, days in state.instr_active_days.items():
        if instructors.get(iid) and instructors[iid].is_staff:
            staff_days += len(days)
        else:
            parttime_days += len(days)

    nonadjacent = 0
    for by_day in section_days.values():
        for bids in by_day.values():
            if len(bids) >= 2:
                nonadjacent += len(bids) - 1

    return {
        "order": order,
        "englab": englab,
        "cohort_gap": sum(
            (max(hours) + 1 - min(hours)) - len(hours)
            for hours in cohort_hours.values()
            if len(hours) >= 2
        ),
        "cohort_conflict": sum(max(0, len(courses) - 1) for courses in cohort_courses.values()),
        "instr_days_raw": staff_days,
        "parttime_days_raw": parttime_days,
        "nonadjacent": nonadjacent,
    }


def pct_gain(base: int, value: int) -> float:
    return ((base - value) / base) if base else 0.0


def main() -> None:
    settings = active_settings()
    cfg0 = build_config(settings, {}, ANNEAL_S)
    cfg0 = replace(
        cfg0,
        soft_polish_acceptor=ACCEPTOR,
        max_rooms_per_block=max(cfg0.max_rooms_per_block, REPAIR_MAX_ROOMS),
    )

    courses = ok_rows(parse_courselist(read_raw(f"data/sample_courses_2025_{PERIOD}.csv")))[:N]
    sections, _ = build_sections_from_courselist(courses, PERIOD, cfg0)
    instructors = build_instructors_from_courselist(courses)
    rooms = build_rooms_from_ui(ok_rooms(parse_classrooms(read_raw("data/classrooms.csv"))), cfg0)
    mark_virtual(sections, rooms, cfg0)

    room_list = list(rooms.values())
    virtual_names = {room.room for room in room_list if room.is_virtual}
    blocks = [(block, sec) for sec in sections for block in sec.blocks]
    sec_of = {block.block_id: sec for block, sec in blocks}
    sec_instr = {sec.section_id: sec.instructor_ids for sec in sections}
    cand_by_block = {}
    for block, sec in blocks:
        cand_by_block[block.block_id] = gen_candidates(
            block, sec, _instructors_of(sec, instructors), room_list, cfg0
        )
    order = sorted(
        (block.block_id for block, _sec in blocks),
        key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students),
    )

    print(
        f"[setup] period={PERIOD} N={N} blocks={len(blocks)} converge={CONVERGE_S:.0f}s "
        f"anneal={ANNEAL_S:.0f}s acceptor={ACCEPTOR} seeds={SEEDS}",
        flush=True,
    )
    print(
        "[setup] active settings: instr_days_target=2 free_day_years=2,3,4; "
        "all profiles change exactly one weight from BASE",
        flush=True,
    )

    state = State(sec_of, sec_instr, virtual_names)
    t0 = perf_counter()
    greedy_construct(state, order, cand_by_block, cfg0)
    sweep = 0
    while perf_counter() - t0 < CONVERGE_S:
        sweep += 1
        unplaced = [block.block_id for block, _sec in blocks if block.block_id not in state.placed]
        if not unplaced:
            break
        unplaced.sort(key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))
        gained = 0
        for idx in range(0, len(unplaced), BATCH):
            if perf_counter() - t0 >= CONVERGE_S:
                break
            batch = [bid for bid in unplaced[idx : idx + BATCH] if bid not in state.placed]
            if batch:
                gained += repair_round(state, batch, cand_by_block)
        if gained == 0 or sweep >= 25:
            break

    snapshot = dict(state.placed)
    base_polish = _global_terms(state, cfg0)
    base_legacy = legacy_terms(state, cfg0, instructors)
    print(
        f"[converge] wall={perf_counter() - t0:.0f}s sweeps={sweep} "
        f"placed={len(snapshot)}/{len(blocks)} ({len(snapshot) / len(blocks):.2%})",
        flush=True,
    )
    print("[base:polish] " + " ".join(f"{term}={base_polish[term]}" for term in POLISH_TERMS))
    print("[base:legacy] " + " ".join(f"{term}={base_legacy[term]}" for term in LEGACY_TERMS))

    rows = []
    for seed in SEEDS:
        seed_base_polish = None
        seed_base_legacy = None
        for name, overrides in PROFILES.items():
            cfg = replace(cfg0, **overrides)
            st = fresh_state(snapshot, sec_of, sec_instr, virtual_names)
            ts = perf_counter()
            info = anneal_soft(st, cand_by_block, cfg, ANNEAL_S, seed=seed)
            polish = _global_terms(st, cfg)
            legacy = legacy_terms(st, cfg, instructors)
            if name == "BASE":
                seed_base_polish = polish
                seed_base_legacy = legacy
            selected = SELECTED.get(name)
            if selected in POLISH_TERMS:
                base_val = seed_base_polish[selected]
                val = polish[selected]
            elif selected in LEGACY_TERMS:
                base_val = seed_base_legacy[selected]
                val = legacy[selected]
            else:
                base_val = val = 0
            rows.append(
                {
                    "seed": seed,
                    "profile": name,
                    "selected": selected or "-",
                    "gain": pct_gain(base_val, val),
                    "wall": perf_counter() - ts,
                    "iters": info["iters"],
                    "accepted": info["accepted"],
                    "E0": info["soft_start"],
                    "E1": info["soft_end"],
                    "polish": polish,
                    "legacy": legacy,
                }
            )
            print(
                f"[run] seed={seed} {name:19s} sel={selected or '-':16s} "
                f"gain={pct_gain(base_val, val):+7.1%} E={info['soft_start']:.2f}->{info['soft_end']:.2f} "
                f"wall={perf_counter() - ts:.0f}s",
                flush=True,
            )

    print("\n=== ONE-AT-A-TIME SUMMARY ===")
    print(
        f"{'profile':19s} {'kind':15s} {'selected':16s} {'gain_mean':>10s} "
        f"{'gain_range':>19s} {'BASE->profile selected':>24s}"
    )
    for name in PROFILES:
        if name == "BASE":
            continue
        selected = SELECTED[name]
        gains = [row["gain"] for row in rows if row["profile"] == name]
        vals = []
        bases = []
        for row in rows:
            if row["profile"] != name:
                continue
            base_row = next(r for r in rows if r["seed"] == row["seed"] and r["profile"] == "BASE")
            if selected in POLISH_TERMS:
                bases.append(base_row["polish"][selected])
                vals.append(row["polish"][selected])
            else:
                bases.append(base_row["legacy"][selected])
                vals.append(row["legacy"][selected])
        kind = "polish-dial" if name in POLISH_DIALS else "not-polish"
        print(
            f"{name:19s} {kind:15s} {selected:16s} "
            f"{sum(gains) / len(gains):+10.1%} "
            f"[{min(gains):+7.1%},{max(gains):+7.1%}] "
            f"{sum(bases) / len(bases):8.1f}->{sum(vals) / len(vals):8.1f}"
        )

    print("\n=== BASE POST METRICS BY SEED ===")
    for row in rows:
        if row["profile"] != "BASE":
            continue
        print(
            f"seed={row['seed']} polish "
            + " ".join(f"{term}={row['polish'][term]}" for term in POLISH_TERMS)
            + " | legacy "
            + " ".join(f"{term}={row['legacy'][term]}" for term in LEGACY_TERMS)
        )


if __name__ == "__main__":
    main()
