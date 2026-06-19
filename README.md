# Course Timetabling — University Course Timetabling (UCTP)

An OR-Tools **CP-SAT** system that produces a **conflict-free weekly schedule** from real
university data. It assigns each section a **day + time + room**; section / instructor /
size / T-P-L are fixed inputs (the only decision variables are **time and room**).

> **Status.** The full-period schedule is produced by a **warm-started repair solver**
> (`--repair`): a fast greedy construction seeds a solution, then CP-SAT repeatedly
> re-optimizes small neighbourhoods until no more blocks can be placed. Measured full-period,
> all rules on:
>
> | Period | Blocks placed | Hard resource conflicts | Wall time |
> |---|---|---|---|
> | 001 (Fall) | 1566 / 1708 (**91.7%**) | **0** | 297 s |
> | 002 (Spring) | 1585 / 1788 (**88.6%**) | **0** | 628 s |
>
> The residual ~8–11% (mostly Architecture studios in tightly-contended slots) is a hard tail;
> intensifying the repair gains <1 pt for ~3× the runtime, so ~90% conflict-free is the
> practical ceiling — the remainder is best placed manually. See [TODO.md](TODO.md).

---

## Setup

```bash
python3 -m pip install -r requirements.txt   # pandas, ortools, pytest
```

`data/` (the real CSVs) is gitignored — it must be present on disk for anything to run.

## Running

```bash
# full period, repair solver (the main path)
PYTHONPATH=src python3 -m timetabling --period 001 --scope all --mode A --repair

# a single faculty, single-shot CP-SAT (small scopes solve directly)
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Basic Sciences" --mode A,B --time-limit 60
```

**Parameters:**

| Flag | Values | Description |
|---|---|---|
| `--period` | `001` (Fall) \| `002` (Spring) | Term to schedule (independent) |
| `--scope` | `all` \| `faculty=<text>` \| `dept=<CODE>` | Slice to solve. `faculty` matches the Grades `Dept.` column; `dept` matches the cohort dept code |
| `--mode` | `A,B` (default) \| `A` \| `B` | A = solve from scratch, B = benchmark against the existing program |
| `--repair` | flag | Warm-started small-neighbourhood repair solver. The path for full `--scope all` (construction → relatedness-neighbourhood re-optimization → loop until dry). Reports `placed/total`, `wall`, `sweeps`. |
| `--decompose` | flag | Legacy faculty-by-faculty greedy (kept for comparison; ~49% placed). Superseded by `--repair`. |
| `--time-limit` | seconds (default 60) | CP-SAT time limit for the single-shot solver (not used by `--repair`, which has its own per-round budget). |
| `--max-rooms-per-block N` | int | Truncate each block's candidate room list (single-shot model-size lever). |
| `--out` | dir (default `out/`) | Output folder |

All other parameters (blackout hours, time windows, objective weights, `max_block_len`,
`max_theory_session`, soft-term weights, etc.) live in the `Config` dataclass in
[src/timetabling/config.py](src/timetabling/config.py).

## Outputs (`out/`)

- **`schedule_<period>.json`** — the UI-consumable schema (per-assignment `section_id,
  course_code, course_name, block_kind, instructor_id, instructor_name, cohort, dept,
  students, day, start, end, room, room_cap, is_lab_room, flags`; plus `period`, `meta`,
  `unmet_soft`, `conflicts`).
- **`schedule_<period>.csv`** — the same assignments as a flat table.
- **`data_quality_<period>.json`** — parse / room / cohort / join checks + unschedulable list.
- **`mode_b_<period>.json`** — generated vs. existing program (conflict counts, room usage,
  evening ratio).

## Tests

```bash
python3 -m pytest -q        # 86 tests
```

---

## Architecture

```
src/timetabling/
  config.py         Config dataclass + all parameters, DAYS, LAB_SUFFIXES
  model.py          Room, Instructor, Block, Section, Candidate, Assignment, Violation
  textnorm.py       Staff ID / name / int normalization
  schedule_parse.py SCHEDULE grammar (unit / chain / X/Y / dirty -> flag)
  io_csv.py         quote-aware CSV loaders
  clean.py          room classification (lab/online/physical/virtual), instructor objects
  join.py           Grades + enrollment + Plan combined frame
  derive.py         Section + Block derivation (level, cohort, theory/lab blocks, plan_room)
  route.py          mark_virtual (online/oversize -> virtual room), mark_lab_rooms (pin lab block)
  model_cpsat.py    candidate generation + pruning + single-shot CP-SAT model
  repair.py         construction + warm-started small-neighbourhood repair solver (--repair)
  decompose.py      legacy faculty-by-faculty greedy (--decompose)
  validate.py       solver-independent hard-constraint validator
  report.py         data quality + Mode-B benchmark
  export.py         schedule.json + CSV
  __main__.py       CLI / pipeline orchestration
```

Most hard constraints are enforced during **candidate generation** (only legal
`(room, day, start)` placements are produced): capacity, the **pinned lab room**, the
undergraduate <18:00 window, and the Friday 13–14 and Thursday 14–16 (full-time staff
seminar) blackouts. Cross-block relations are model/solver constraints: **placement**,
**room / instructor / self no-overlap**, and **theory different-day**. `validate.py` re-checks
the solution **independently** of the solver, so a solver bug cannot pass silently.

### Key behaviours (all implemented and tested)

- **Repair solver (`--repair`).** Greedy first-fit construction seeds a full-period solution;
  then CP-SAT repeatedly frees a small *relatedness* neighbourhood (the unplaced blocks plus
  the placed blocks competing for the slots they need), re-solves it with a **soft** placement
  term (so a neighbourhood is never infeasible), warm-started from current positions, and
  commits only non-worsening moves — looping until a full sweep places nothing new. This is
  what makes the 793/801-section full period tractable on CP-SAT (a single global solve of
  ~356k variables returns UNKNOWN).
- **Virtual room for online / oversize sections.** The largest *real* classroom is 100 seats;
  sections the Plan delivers as `Online`, or whose enrollment exceeds 100, are routed
  (`route.mark_virtual`) to a virtual `Online` room (unlimited capacity, **exempt from room
  no-overlap**; instructor / self constraints still apply). This is faithful to the data —
  HIST/TUR common courses run online, TEDU/ENGR seminars are roomless — and replaces the
  earlier *synthetic AMFI halls* (which assumed amphitheatre capacities not present in the data).
- **Theory distributes into ≤2h sessions on different days.** `blocks_from_tpl` splits a
  section's theory hours into sessions of at most `cfg.max_theory_session` (2h): T:3 → 2+1,
  T:4 → 2+2. A **hard** constraint (model + repair + an independent `split_day` validator
  check) forces a section's theory sessions onto **different days**. Labs keep `max_block_len`.
- **Lab block pinned to its real lab room.** `route.mark_lab_rooms` reads each section's
  designated lab room from the Plan (the `-L`/`-PC`-suffixed room) and pins the lab block to
  exactly that room; `validate` enforces it (`lab_room`). Sections whose lab is held in a
  regular room (or are project courses) keep no pin and use regular rooms. The three real lab
  rooms missing from `classrooms.csv` (A317/A326/DB102-MF-L, cap 50) were added to the data;
  `-PC` rooms (e.g. H007/009-PC) now classify as labs.
- **Cohort conflict is soft.** Sections of the *same* course may run in parallel; different
  courses of the same `(dept, year)` cohort incur a weighted penalty (`w_cohort_conflict`,
  default 50) — **not** a hard violation. A hard course-level cohort constraint was proven
  INFEASIBLE at scale. Reported as `cohort_conflicts` in `mode_b_<period>.json`.
- **Team-taught sections.** `Section.instructor_ids` is a `list[str]`; every id enters
  instructor no-overlap; the seminar blackout applies if any co-instructor is full-time.

A weighted **soft objective** (minimized under the time cap) covers evening-slot use, room
compactness, instructor / part-time day-compactness, cohort daily-compactness (`w_cohort_gap`),
course-level day-ordering (`w_order`, S-Order), and Engineering lab-day preference (`w_englab`,
S-EngLab). The old `w_nonadjacent` soft term is superseded for theory by the hard different-day
rule.

---

## Verified results

### Full period, repair solver (Mode A, all rules)

| Period | Sections | Blocks placed | Hard resource conflicts | Wall time | Sweeps |
|---|---|---|---|---|---|
| 001 | 793 | 1566 / 1708 (91.7%) | 0 | 297 s | 3 |
| 002 | 801 | 1585 / 1788 (88.6%) | 0 | 628 s | 6 |

The reported "violations" equal the unplaced-block count (each unplaced block is a `placement`
check), i.e. **0 real room / instructor / capacity / lab-room / window / blackout / self /
different-day conflicts** among placed blocks.

### Generated vs. existing program (period 001, Mode-B style)

| Metric | Ours | Existing Plan |
|---|---|---|
| Hard resource conflicts | **0** | ~1091 (room 325, instructor 522, window 91, blackout 85, capacity 6, split-day 62) |
| Distinct rooms used | 92 | 248 |
| Evening (≥17h) ratio | 0.19 | 0.22 |
| Avg room fill (students / cap) | 0.72 | 0.50 |

The existing-program "conflicts" are measured under our (stricter, consistent) rule model;
~176 are rule-definition differences (it legitimately uses evening / blackout slots we forbid),
and the rest include cross-listing / coordinator-listing artifacts. The honest claim: our
schedule is conflict-free under one coherent rule set; the existing one is not under those rules.

### Per-faculty single-shot (small scopes solve directly to 0 violations)

`--scope faculty=...` without `--repair` solves a single faculty (≈30–200 sections) to
OPTIMAL/FEASIBLE with 0 hard violations in seconds–minutes — useful for inspecting one
program at a time.

---

## Known limitations

1. **~8–11% placement tail** — mostly Architecture studios (long blocks, scarce slots). Repair
   plateaus; intensification has poor ROI. Best handled by manual placement of the residual or
   a future smarter neighbourhood/solver strategy.
2. **Cohort proxy granularity** — `(Dept_Code, Year_Level)` over-approximates student conflict;
   finer curriculum data would improve quality.
3. **Web UI** — not started (a read-only viewer can consume `schedule_<period>.json`; a simple
   self-contained HTML timetable generator exists as a scratch tool).

---

## History

- **Phase 1** — end-to-end CP-SAT pipeline + slice feasibility.
- **Phase 2** — model fidelity (soft cohort, block splitting, team-taught) + per-faculty results.
- **Current** — full-period **repair solver**; **virtual rooms** for online/oversize (AMFI halls
  removed); **theory 2+1 split + hard different-day**; **lab-room pinning**; **Gurobi backend
  removed** (CP-SAT is sufficient). See [TODO.md](TODO.md).
