# Course Timetabling — University Course Timetabling (UCTP)

An OR-Tools **CP-SAT** model that produces a **conflict-free weekly schedule** from
real university data. It assigns each section a **day + time + room**; section/
instructor/size/T-P-L are fixed inputs (the only decision variables are **time and
room**).

> **This phase (Phase 1):** a working end-to-end pipeline with feasibility proven on
> department/faculty slices. Full-period solving (~800 sections) and the web UI are
> later phases — see [TODO.md](TODO.md).

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
| `--out` | dir (default `out/`) | Output folder |

All other parameters (blackout hours, time windows, objective weights,
`max_rooms_per_block`, toggles) live in the `Config` dataclass in
[src/timetabling/config.py](src/timetabling/config.py).

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
python3 -m pytest -q        # 39 tests
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
  derive.py         Section+Block derivation (level, cohort, T+P/L blocks, exclusions)
  model_cpsat.py    candidate generation + pruning + CP-SAT model + solve
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

---

## Verified results (period 001)

Each slice beats the existing program on conflicts / room count / evening ratio:

| Slice | Sections | Status | Hard violations | Mode A vs existing |
|---|---|---|---|---|
| ADA dept | 5 | OPTIMAL | 0 | 1 room vs 4 |
| Econ faculty | 16 | OPTIMAL | 0 | 5 rooms vs 13, 0 vs 9 conflicts |
| Psychology | 35 | FEASIBLE | 0 | 6 rooms vs 19, 0 vs 36 conflicts |
| Architecture | 12 (+5 studios excluded) | OPTIMAL | 0 | 3 rooms vs 10 |

---

## Known limitations (accepted in this phase — details in [TODO.md](TODO.md))

1. **Cohort proxy `(Dept_Code, Year_Level)`** is too restrictive for service/elective
   courses and for *multiple sections of the same course* → infeasible on those faculties
   (e.g. ENG-1: 47 sections / 188 hours, which cannot fit a ~45-hour weekly window).
2. **Long blocks** (studios; T+P ≥ 10h as a single block) do not fit the day window →
   need multi-day splitting; currently excluded and reported.
3. **Oversize sections** (students > the largest room, 100) → excluded and reported.
4. **Team-taught sections** (two comma-joined IDs in Grades `Staff ID`) are treated as
   one synthetic instructor; the name lookup is left blank.
5. **The full period (~800 sections)** does not solve as-is because of #1–#2 — that is
   later-phase work.
