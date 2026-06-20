# Course Timetabling

**Conflict-free weekly university schedules, solved from real data.**

A constraint-programming engine built on OR-Tools **CP-SAT** that turns a university's raw
course, instructor, and room data into a coherent **day + time + room** assignment for every
section. Section, instructor, size, and T-P-L are fixed inputs; the engine reasons over the
only two degrees of freedom that matter — **time and room** — and guarantees the result is free
of resource conflicts under one consistent rule set.

---

## At a glance

Full-period schedules are produced by a **warm-started repair solver** (`--repair`): a fast
greedy construction seeds an initial solution, then CP-SAT repeatedly re-optimizes small
neighbourhoods until no further block can be placed. Measured across the full period, every rule
enforced:

| Period | Blocks placed | Hard resource conflicts | Wall time |
|---|---|---|---|
| **001 — Fall** | 1566 / 1708 · **91.7%** | **0** | 297 s |
| **002 — Spring** | 1585 / 1788 · **88.6%** | **0** | 628 s |

The residual ~8–11% is a genuine hard tail — predominantly Architecture studios competing for a
handful of viable slots. Intensifying the repair buys under one point of placement for roughly
triple the runtime, so **~90% conflict-free is the practical ceiling**; the remainder is best
finished by hand. The engineering detail lives in [TODO.md](TODO.md).

---

## Getting started

```bash
python3 -m pip install -r requirements.txt   # pandas, ortools, pytest
```

> Your input is a single course-list CSV (see **Input data** below), placed under `data/`. That
> folder is gitignored, so it is intentionally absent from fresh clones.

## Input data

The engine runs from a single **course list** — one CSV, one row per section. That is the whole
input contract: cohorts, teaching blocks, and instructor identities are all derived from it.

| Column | Meaning |
|---|---|
| `Course Code` | e.g. `CMPE 113` — the department prefix and year level are derived from it (`CMPE`, year 1) |
| `Course Name` | Display name |
| `Section No` | Section number within the course |
| `T` | Weekly theory hours |
| `P` | Weekly practice hours |
| `L` | Weekly lab hours |
| `Lecturer Name` | Display name — informational only |
| `Lecturer Email` | The instructor's identity key. Team-taught sections list comma-separated emails |
| `~Students` | Approximate enrollment — drives room capacity and virtual-room routing |

```csv
Course Code,Course Name,Section No,T,P,L,Lecturer Name,Lecturer Email,~Students
CMPE 113,Introduction to Programming,1,3,0,2,Jane Doe,jane.doe@uni.edu,45
ECON 101,Principles of Economics,1,3,0,0,John Smith,john.smith@uni.edu,120
```

**Derived automatically from the course list:**

- **Cohort** = `(department prefix, year level)` read from the course code (`CMPE 113` → CMPE,
  year 1). Service and elective courses inherit the literal code's cohort — an accepted
  approximation, since cohort conflict is soft (see Architecture).
- **Instructor identity** = email; the display name is cosmetic. A blank email excludes the
  section from instructor no-overlap.
- **Teaching blocks** from `T` / `P` / `L`: theory splits into ≤2h same-section sessions forced
  onto different days; the lab block is split at `max_block_len`.

**Provided separately — not part of the course list:**

- **Classrooms** — room name, capacity, and an explicit lab flag, managed as their own inventory.
- **Period** — Fall (`001`) or Spring (`002`), chosen at solve time.

## Running the solver

```bash
# Full period — the primary path, via the repair solver
PYTHONPATH=src python3 -m timetabling --period 001 --scope all --mode A --repair

# A single faculty — small scopes solve directly in one CP-SAT pass
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Basic Sciences" --mode A,B --time-limit 60
```

### Parameters

| Flag | Values | Description |
|---|---|---|
| `--period` | `001` (Fall) \| `002` (Spring) | Term to schedule — each is solved independently |
| `--scope` | `all` \| `faculty=<text>` \| `dept=<CODE>` | The slice to solve. `faculty` matches the Grades `Dept.` column; `dept` matches the cohort dept code |
| `--mode` | `A,B` (default) \| `A` \| `B` | **A** solves from scratch; **B** benchmarks against the existing program |
| `--repair` | flag | Warm-started small-neighbourhood repair solver — the path for full `--scope all`. Construction → relatedness-neighbourhood re-optimization → loop until dry. Reports `placed/total`, `wall`, `sweeps` |
| `--decompose` | flag | Legacy faculty-by-faculty greedy (~49% placed). Retained for comparison; superseded by `--repair` |
| `--time-limit` | seconds (default 60) | CP-SAT budget for the single-shot solver. The repair solver manages its own per-round budget and ignores this |
| `--max-rooms-per-block N` | int | Truncate each block's candidate room list — a single-shot model-size lever |
| `--out` | dir (default `out/`) | Output folder |

Every other parameter — blackout hours, time windows, objective weights, `max_block_len`,
`max_theory_session`, soft-term weights — is centralized in the `Config` dataclass at
[src/timetabling/config.py](src/timetabling/config.py).

## Outputs (`out/`)

| File | Contents |
|---|---|
| **`schedule_<period>.json`** | The UI-consumable contract: per-assignment `section_id, course_code, course_name, block_kind, instructor_id, instructor_name, cohort, dept, students, day, start, end, room, room_cap, is_lab_room, flags`, plus `period`, `meta`, `unmet_soft`, `conflicts` |
| **`schedule_<period>.csv`** | The same assignments as a flat table |
| **`data_quality_<period>.json`** | Parse / room / cohort / join checks, plus the unschedulable list |
| **`mode_b_<period>.json`** | Generated vs. existing program — conflict counts, room usage, evening ratio |

## Tests

```bash
python3 -m pytest -q        # 86 tests
```

---

## Architecture

The pipeline is a chain of small, single-purpose modules, orchestrated end-to-end by
`__main__.py`:

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

The design rests on a deliberate split. Most hard constraints are enforced **during candidate
generation** — only legal `(room, day, start)` placements are ever produced: capacity, the
**pinned lab room**, the undergraduate <18:00 window, and the Friday 13–14 and Thursday 14–16
(full-time staff seminar) blackouts. Cross-block relations become model/solver constraints:
**placement**, **room / instructor / self no-overlap**, and **theory different-day**. Finally,
`validate.py` re-checks the solution **independently of the solver**, so an encoding bug can
never pass silently.

### Key behaviours — all implemented and tested

- **Repair solver (`--repair`).** A greedy first-fit construction seeds a full-period solution.
  CP-SAT then repeatedly frees a small *relatedness* neighbourhood — the unplaced blocks plus the
  placed blocks competing for the slots they need — re-solves it with a **soft** placement term
  (so no neighbourhood is ever infeasible), warm-started from current positions, and commits only
  non-worsening moves, looping until a full sweep places nothing new. This is what makes the
  793/801-section period tractable on CP-SAT, where a single global solve of ~356k variables
  returns UNKNOWN.

- **Virtual room for online / oversize sections.** The largest *real* classroom seats 100.
  Sections the Plan delivers as `Online`, or whose enrollment exceeds 100, are routed
  (`route.mark_virtual`) to a virtual `Online` room — unlimited capacity, **exempt from room
  no-overlap**, while instructor and self constraints still apply. This is faithful to the data:
  HIST/TUR common courses run online and TEDU/ENGR seminars are roomless. It replaces the earlier
  *synthetic AMFI halls*, which assumed amphitheatre capacities the data never contained.

- **Theory distributes into ≤2h sessions on different days.** `blocks_from_tpl` splits a
  section's theory hours into sessions of at most `cfg.max_theory_session` (2h): T:3 → 2+1,
  T:4 → 2+2. A **hard** constraint — enforced in the model, the repair solver, and an independent
  `split_day` validator check — forces a section's theory sessions onto **different days**. Labs
  retain `max_block_len`.

- **Lab block pinned to its real lab room.** `route.mark_lab_rooms` reads each section's
  designated lab room from the Plan (the `-L`/`-PC`-suffixed token) and pins the lab block to
  exactly that room; `validate` enforces it (`lab_room`). Sections whose lab is held in a regular
  room — or that are project courses — keep no pin and use regular rooms. The three real lab rooms
  missing from `classrooms.csv` (A317/A326/DB102-MF-L, cap 50) were added to the data, and `-PC`
  rooms (e.g. H007/009-PC) now classify as labs.

- **Cohort conflict is soft, by design.** Sections of the *same* course may run in parallel;
  different courses within the same `(dept, year)` cohort incur a weighted penalty
  (`w_cohort_conflict`, default 50) rather than a hard violation. A hard course-level cohort
  constraint was proven INFEASIBLE at scale. It surfaces as `cohort_conflicts` in
  `mode_b_<period>.json`.

- **Team-taught sections.** `Section.instructor_ids` is a `list[str]`; every id enters instructor
  no-overlap, and the seminar blackout applies if any co-instructor is full-time.

A weighted **soft objective** — minimized under the time cap — shapes the quality of feasible
schedules: evening-slot use, room compactness, instructor / part-time day-compactness, cohort
daily-compactness (`w_cohort_gap`), course-level day-ordering (`w_order`, S-Order), and
Engineering lab-day preference (`w_englab`, S-EngLab). The former `w_nonadjacent` term is
superseded for theory by the hard different-day rule.

---

## Verified results

### Full period — repair solver, Mode A, all rules

| Period | Sections | Blocks placed | Hard resource conflicts | Wall time | Sweeps |
|---|---|---|---|---|---|
| 001 | 793 | 1566 / 1708 · 91.7% | 0 | 297 s | 3 |
| 002 | 801 | 1585 / 1788 · 88.6% | 0 | 628 s | 6 |

The reported "violations" equal the unplaced-block count — each unplaced block registers as a
`placement` check — meaning **zero real room / instructor / capacity / lab-room / window /
blackout / self / different-day conflicts** among the blocks that *were* placed.

### Generated vs. existing program — period 001, Mode-B style

| Metric | Ours | Existing Plan |
|---|---|---|
| Hard resource conflicts | **0** | ~1091 — room 325, instructor 522, window 91, blackout 85, capacity 6, split-day 62 |
| Distinct rooms used | 92 | 248 |
| Evening (≥17h) ratio | 0.19 | 0.22 |
| Avg room fill (students / cap) | 0.72 | 0.50 |

The existing program's "conflicts" are measured under *our* stricter, consistent rule model;
roughly 176 are rule-definition differences (it legitimately uses evening and blackout slots we
forbid), and the rest include cross-listing and coordinator-listing artifacts. The honest
claim — and the one this project stands behind — is precise: our schedule is conflict-free under
one coherent rule set; the existing one is not, under those same rules.

### Per-faculty single-shot

`--scope faculty=...` without `--repair` solves a single faculty (≈30–200 sections) to
OPTIMAL/FEASIBLE with **0 hard violations** in seconds to minutes — ideal for inspecting one
program at a time.

---

## Known limitations

1. **The ~8–11% placement tail** — mostly Architecture studios (long blocks, scarce slots). The
   repair plateaus, and intensification has poor ROI; the residual is best resolved by manual
   placement or a future smarter neighbourhood/solver strategy.
2. **Cohort proxy granularity** — `(Dept_Code, Year_Level)` over-approximates student conflict;
   finer curriculum data would sharpen quality.
3. **Web UI** — not yet started. A read-only viewer can consume `schedule_<period>.json` today; a
   simple self-contained HTML timetable generator exists as a scratch tool.

---

## Project history

- **Phase 1** — end-to-end CP-SAT pipeline and slice feasibility.
- **Phase 2** — model fidelity (soft cohort, block splitting, team-taught) and per-faculty results.
- **Current** — full-period **repair solver**; **virtual rooms** for online/oversize (AMFI halls
  removed); **theory 2+1 split with a hard different-day rule**; **lab-room pinning**; **Gurobi
  backend removed** (CP-SAT proved sufficient). The full record is in [TODO.md](TODO.md).
