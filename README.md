# Course Timetabling — University Course Timetabling (UCTP)

An OR-Tools **CP-SAT** model that produces a **conflict-free weekly schedule** from
real university data. It assigns each section a **day + time + room**; section/
instructor/size/T-P-L are fixed inputs (the only decision variables are **time and
room**).

> **Status:** Phase 2 is complete. Per-faculty solving is conflict-free and beats the existing
> program across every measured slice. A complete full-period conflict-free timetable is **not**
> achieved in this phase — a single global solve is intractable, and faculty decomposition places
> ~49% of blocks (0 resource conflicts). Full-period solving is the main open item for future
> work. The web UI is Phase 3.
> See [TODO.md](TODO.md) for the per-item status.

Related documents:

- Design spec: [docs/superpowers/specs/2026-06-19-course-timetabling-cpsat-design.md](docs/superpowers/specs/2026-06-19-course-timetabling-cpsat-design.md)
- Implementation plan: [docs/superpowers/plans/2026-06-19-uctp-cpsat-pipeline.md](docs/superpowers/plans/2026-06-19-uctp-cpsat-pipeline.md)
- Problem specification: [docs/prompts/university_course_timetabling_prompt.md](docs/prompts/university_course_timetabling_prompt.md)

---

## Setup

```bash
python3 -m pip install -r requirements.txt   # pandas, ortools, pytest
```

## Running

```bash
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Department of Psychology" --mode A,B --time-limit 60
```

**Parameters:**

| Flag | Values | Description |
|---|---|---|
| `--period` | `001` (Fall) \| `002` (Spring) | Term to schedule (independent) |
| `--scope` | `all` \| `faculty=<text>` \| `dept=<CODE>` | Slice to solve. `faculty` matches the Grades `Dept.` column; `dept` matches the cohort dept code |
| `--mode` | `A,B` (default) \| `A` \| `B` | A = solve from scratch, B = benchmark against the existing program |
| `--time-limit` | seconds (default 60) | CP-SAT solve time limit |
| `--decompose` | flag | Solve faculty-by-faculty sharing the room pool (for full `--scope all`). Greedy heuristic — produces 0 resource conflicts but may leave sections unplaced. |
| `--max-rooms-per-block N` | int (default unlimited) | Truncate each block's candidate list to at most N rooms; shrinks the model for large scopes (e.g. `--max-rooms-per-block 4` reduces period 001 from ~356k to ~123k variables). |
| `--out` | dir (default `out/`) | Output folder |

All other parameters (blackout hours, time windows, objective weights,
soft-term weights, `max_block_len`, `extra_rooms`, `w_cohort_conflict`, `w_cohort_gap`,
`w_order`, `w_englab`, `eng_faculty_match`, `eng_lab_days`, etc.) live in the `Config`
dataclass in [src/timetabling/config.py](src/timetabling/config.py).

## Outputs (`out/`)

- **`schedule_<period>.json`** — the UI-consumable schema. Each assignment:
  `section_id, course_code, course_name, block_kind, instructor_id, instructor_name,
  cohort, dept, students, day, start, end, room, room_cap, is_lab_room, flags`;
  plus `period`, `meta`, `unmet_soft`, `conflicts`.
- **`schedule_<period>.csv`** — the same assignments as a flat table.
- **`data_quality_<period>.json`** — parse/room/cohort/join checks, lab-room table,
  and the list of unschedulable sections (oversize / block longer than the day window).
- **`mode_b_<period>.json`** — generated vs. existing program (conflict counts, room
  usage, evening ratio).

## Tests

```bash
python3 -m pytest -q        # 68 tests
```

---

## Architecture

```
src/timetabling/
  config.py         Config dataclass + all parameters, DAYS
  model.py          Room, Instructor, Block, Section, Candidate, Assignment, Violation
  textnorm.py       Staff ID / name / int normalization
  schedule_parse.py SCHEDULE grammar (unit / chain / X/Y / dirty -> flag)
  io_csv.py         quote-aware CSV loaders (with period attachment)
  clean.py          room classification (lab/online/physical), instructor master objects
  join.py           Grades join enrollment join Plan combined frame
  derive.py         Section+Block derivation (level, cohort, T+P/L blocks split, exclusions)
  model_cpsat.py    candidate generation + pruning + CP-SAT model + solve
  decompose.py      faculty-by-faculty solve sharing the room pool (--decompose)
  validate.py       solver-independent hard-constraint validator
  report.py         data quality + Mode-B benchmark
  export.py         schedule.json + CSV
  __main__.py       CLI / pipeline orchestration
```

Most hard constraints are enforced during **candidate generation** (only legal
`(room, day, start)` placements are produced): capacity, lab-room, the undergraduate
<18:00 window, and the Friday 13–14 and Thursday 14–16 (full-time) blackouts. Only
**H1 placement** and **H2–H4 room/instructor/cohort no-overlap** are explicit model
constraints. `validate.py` re-checks the solution **independently** of the model, so a
solver bug cannot pass silently.

**Phase 2 behaviors (all implemented and tested):**

- **Cohort conflict is soft** — sections of the *same* course may run in parallel; different
  courses of the same `(dept, year)` cohort incur a weighted penalty (`w_cohort_conflict`,
  default 50) the solver minimizes. This replaces the Phase-1 hard H4 constraint, which was
  proven INFEASIBLE at scale (Computer Engineering). Cohort overlap is **not** a hard violation;
  it is reported as the soft metric `cohort_conflicts` in `mode_b_<period>.json`.
- **H_self** — explicit per-section non-overlap; a section's own blocks can never overlap,
  independent of instructor or cohort encoding.
- **Long-block splitting** — `blocks_from_tpl` splits any block longer than `max_block_len`
  (default 4h) into near-equal sub-blocks (e.g. 10h → 4+3+3). Block ids: `#T`/`#L` for
  single blocks, `#T1..#Tk`/`#L1..#Lk` for split ones. Kind detection: `"#L" in block_id`.
  Enables Architecture studios (previously excluded).
- **Team-taught sections** — `Section.instructor_ids` is a `list[str]` (comma-joined Staff IDs
  split); every instructor enters no-overlap (H3); the seminar blackout applies if any
  co-instructor is full-time. `schedule.json` shows joined names.
- **Oversize → large halls** — `cfg.extra_rooms` injects synthetic `AMFI-<cap>-<n>` halls
  (default 2×500, 3×250, 4×150). Capacity stays hard. The real amphitheater inventory is not
  in the data; these capacities are assumed and configurable. Enables Basic Sciences service
  courses (e.g. TEDU 101, 497 students).
- **Faculty decomposition** — `decompose.py` (`--decompose`): solves faculties in sequence,
  reserving used room+instructor slots for later faculties. Greedy heuristic, not a global
  optimum; placed ~49% of blocks in period 001/002 at 0 resource conflicts.

A weighted **soft objective** (minimized under the time cap) covers evening-slot use, room
compactness, instructor / part-time day-compactness, cohort daily-compactness (`w_cohort_gap`
— student idle gaps for year-2/3/4 cohorts), **course-level day-ordering** (`w_order` — within
a cohort, 2XXX courses prefer earlier hours, 4XXX later — S-Order), **Engineering lab days**
(`w_englab` — lab blocks prefer Thursday/Friday — S-EngLab), and cohort course-conflict penalty
(`w_cohort_conflict`). A "spread split blocks across days" term (`w_nonadjacent`) is implemented
but disabled by default (= 0).

---

## Verified results

### Phase 2 — per-faculty (period 001, Mode A, 60s time limit)

Each faculty is solved to **0 hard violations** and beats the existing program:

| Faculty | Sections | Status | Hard violations | Rooms (ours / existing) | Evening ratio (ours / existing) | Room fill | Cohort soft-conflicts | Existing hard-conflicts |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Basic Sciences (incl. TEDU 101, 497 students, via large halls) | 187 | FEASIBLE | 0 | 30 / 76 | 0.029 / 0.325 | 0.797 | 25 | 83 |
| Computer Engineering (was INFEASIBLE with hard cohort; FEASIBLE with soft) | 61 | FEASIBLE | 0 | 11 / 33 | 0.119 / 0.177 | 0.659 | 19 | 70 |
| Architecture (studios split and scheduled; were excluded in Phase 1) | 17 | FEASIBLE | 0 | 4 / 11 | 0.037 / 0.094 | 0.827 | 0 | 65 |

Cohort soft-conflicts are **not hard violations** — they are the penalty the solver minimizes
when the `(dept, year)` proxy over-counts conflict (students split across electives).

### Phase 1 — department/faculty slices (period 001)

| Slice | Sections | Status | Hard violations | Mode A vs existing |
|---|---|---|---|---|
| ADA dept | 5 | OPTIMAL | 0 | 1 room vs 4 |
| Econ faculty | 16 | OPTIMAL | 0 | 5 rooms vs 13, 0 vs 9 conflicts |
| Psychology | 35 | FEASIBLE | 0 | 6 rooms vs 19, 0 vs 36 conflicts |
| Architecture | 12 (+5 studios excluded) | OPTIMAL | 0 | 3 rooms vs 10 |

### Full-period scaling — honest limitation

A single global solve of the full period (~793 sections / ~988 blocks, period 001) is
**intractable** for CP-SAT here: even with the model shrunk to ~123k variables
(`--max-rooms-per-block 4`) and a 300s cap, the solver returns UNKNOWN with nothing placed
(at the default the model is ~356k variables).

Faculty decomposition (`--decompose`, reserving rooms and instructors across faculties) is a
**greedy heuristic**: it produces a resource-valid partial schedule (0 room/instructor
conflicts) but leaves many sections unplaced because later faculties get squeezed out of
reserved slots. Measured results (mrpb=8, 45s/faculty):

| Period | Blocks placed / total | Resource conflicts | Evening ratio | Rooms used / existing |
|---|---|---|---|---|
| 001 | 483 / 988 (~49%) | 0 | 0.070 | 63 / 248 |
| 002 | 446 / ~986 (~45%) | 0 | 0.078 | 53 / 218 |

**Conclusion:** per-faculty timetabling is complete and conflict-free; a **complete full-period
conflict-free timetable is not achieved in Phase 2**. Future paths: better decomposition
(iterative/overlapping partitions, column generation), a commercial MIP solver (e.g. Gurobi),
or finer cohort/curriculum data.

---

## Known limitations

1. **Full-period completeness** — the main open item; see above.
2. **Cohort proxy granularity** — `(Dept_Code, Year_Level)` over-approximates student conflict
   (cross-dept electives uncaptured). Mitigated in Phase 2 by making cohort conflict soft
   (`w_cohort_conflict`), but finer curriculum data (elective flags, per-student course sets)
   would improve scheduling quality further.
3. **Large-hall inventory assumed** — the real amphitheater capacities are not in the data;
   `cfg.extra_rooms` defaults are reasonable but configurable.
4. **Web UI** — Phase 3.

---

## Phase summary

- **Phase 1** — end-to-end CP-SAT pipeline + slice feasibility: complete.
- **Phase 2** — model fidelity (soft cohort, block splitting, team-taught, large halls, soft
  terms, decomposition) + per-faculty verified results: complete.
- **Phase 3** — Streamlit web UI + Cloud Run deployment: not started.
