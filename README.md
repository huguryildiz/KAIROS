<!-- markdownlint-disable MD033 -->
<!-- Inline HTML is intentional: centered hero header and badge row. -->

<p align="center">
  <img src="assets/icon.svg" alt="Kairos logo" width="120" height="120">
</p>

<h1 align="center">Kairos</h1>

<p align="center">
  <strong>Course Timetabling</strong><br>
  <sub>Conflict-free weekly university schedules, solved from real data — upload a course list, get every section on a day, time, and room.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/0_hard_conflicts-4F46E5?style=for-the-badge" alt="0 hard conflicts">
  <img src="https://img.shields.io/badge/~90%25_placed-06B6D4?style=for-the-badge" alt="~90% placed">
  &nbsp;
  <img src="https://img.shields.io/badge/Python_3.11-0b1220?style=for-the-badge&logo=python&logoColor=3776AB" alt="Python 3.11">
  <img src="https://img.shields.io/badge/OR--Tools_CP--SAT-0b1220?style=for-the-badge&logo=google&logoColor=4285F4" alt="OR-Tools CP-SAT">
  <img src="https://img.shields.io/badge/Streamlit-0b1220?style=for-the-badge&logo=streamlit&logoColor=FF4B4B" alt="Streamlit">
  <img src="https://img.shields.io/badge/pandas-0b1220?style=for-the-badge&logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/pytest_132_passing-0b1220?style=for-the-badge&logo=pytest&logoColor=0A9EDC" alt="pytest 132 passing">
  <img src="https://img.shields.io/badge/Google_Cloud_Run-0b1220?style=for-the-badge&logo=googlecloud&logoColor=4285F4" alt="Google Cloud Run">
</p>

---

## Overview

**Kairos** turns a university's raw course, instructor, and room data into a coherent **day + time + room** assignment for every section — a weekly timetable that is provably free of resource conflicts under one consistent rule set.

Section, instructor, size, and the T–P–L hour split are **fixed inputs**. The engine reasons over the only two degrees of freedom that matter — **time and room** — and never produces an illegal placement: a room is never double-booked, an instructor is never in two places at once, capacity is never exceeded, and every undergraduate block lands inside the teaching window.

It runs two ways: a **command-line solver** for batch runs and benchmarking, and a **bilingual web app** (Streamlit) where a non-technical user uploads a course list, edits classrooms, presses **Solve**, and reads the result on a Mon–Fri grid. The optimization core is OR-Tools **CP-SAT**; the math, rules, and design rationale are documented in [`MODEL.md`](MODEL.md).

---

## Why Kairos

Hand-building a university timetable means juggling hundreds of sections against a handful of rooms, dozens of instructors, and a tangle of rules — and a single missed clash propagates into the term. The hard part isn't *drawing* the grid; it's guaranteeing nothing collides.

- **Conflict-free by construction.** Hard rules are enforced before the solver ever sees a placement; the schedule cannot encode a room, instructor, capacity, lab, window, or blackout clash.
- **Solved from real data.** One course-list CSV is the entire input contract — cohorts, teaching blocks, and instructor identities are all derived from it.
- **Independently verified.** A validator re-derives every hard violation from the final assignment list, decoupled from the solver, so an encoding bug can never pass silently.
- **Honest about its limits.** Where ~90% conflict-free is the practical ceiling, the README says so and shows the numbers — the residual tail is reported, not hidden.
- **Two front doors.** A scriptable CLI for operators and a zero-friction web app for everyone else, sharing one solve path.
- **Privacy-first deployment.** No PII in the image; runs IAM-gated on the institution's own EU cloud, scale-to-zero.

---

## At a glance

Full-period schedules come from a **warm-started repair solver** (`--repair`): a fast greedy construction seeds an initial solution, then CP-SAT repeatedly re-optimizes small *relatedness* neighbourhoods until no further block can be placed. Measured across the full period, every rule enforced:

| Period | Sections | Blocks placed | Hard resource conflicts | Wall time | Sweeps |
| --- | --- | --- | --- | --- | --- |
| **Fall** | 793 | 1566 / 1708 · **91.7%** | **0** | 297 s | 3 |
| **Spring** | 801 | 1585 / 1788 · **88.6%** | **0** | 628 s | 6 |

The residual ~8–11% is a genuine hard tail — predominantly Architecture studios competing for a handful of viable slots. Intensifying the repair buys under one point of placement for roughly triple the runtime, so **~90% conflict-free is the practical ceiling**; the remainder is best finished by hand.

### Generated vs. the existing program — period 001

| Metric | Kairos | Existing program |
| --- | --- | --- |
| Hard resource conflicts | **0** | ~1091 (room, instructor, window, blackout, capacity, split-day) |
| Distinct rooms used | 92 | 248 |
| Evening (≥17h) ratio | 0.19 | 0.22 |
| Avg room fill (students / cap) | 0.72 | 0.50 |

Measured under one stricter, consistent rule model. The honest claim: our schedule is conflict-free under a single coherent rule set; the existing one is not, under those same rules.

---

## The model

Hard rules and soft preferences are kept strictly apart. **Hard constraints can never be violated**; **soft preferences are weighted penalties** the solver minimizes, so they can never cause infeasibility.

### Hard constraints

| Rule | Where enforced |
| --- | --- |
| **Room capacity** — seats ≥ enrolled students | candidate pruning |
| **Pinned lab room** — a lab block sits only in its designated lab room | candidate pruning |
| **Undergraduate window** — every block ends by 18:00 | candidate pruning |
| **Blackouts** — Friday 13–14, Thursday 14–16 (full-time staff seminar) | candidate pruning |
| **Placement** — exactly one slot per block | CP-SAT model |
| **Room / instructor no-overlap** — incl. team-taught co-instructors | CP-SAT model |
| **Self no-overlap** — a section's own blocks never collide | CP-SAT model |
| **Theory different-day** — a section's theory sessions fall on distinct days | model + repair + validator |

Most hard rules are enforced **during candidate generation** — only legal `(room, day, start)` placements are ever produced — while cross-block relations become model/solver constraints. A virtual `Online` room absorbs online and oversize (>100) sections: unlimited capacity, exempt from room no-overlap, while instructor and self constraints still apply.

### Soft objective (minimized)

| Term | Weight | Intent |
| --- | --- | --- |
| **Cohort conflict** (`w_cohort_conflict`) | 50 | Same-course sections may run in parallel; different courses in a `(dept, year)` cohort incur a penalty — a hard cohort rule was proven INFEASIBLE at scale |
| **Evening use** (`w_evening`) | 10 | Discourage ≥17:00 slots |
| **Part-time day-compactness** (`w_parttime_days`) | 5 | Cluster a part-time instructor's days |
| **Instructor day-compactness** (`w_instr_days`) | 3 | Fewer distinct teaching days per instructor |
| **Cohort daily gap** (`w_cohort_gap`) | 3 | Minimize student idle gaps within a day |
| **Room compactness** (`w_room_count`) | 2 | Reuse fewer distinct rooms |
| **Course-level ordering** (`w_order`, S-Order) | 1 | Lower-level courses earlier in the day |
| **Engineering lab days** (`w_englab`, S-EngLab) | 1 | Engineering labs prefer Thu/Fri |

All weights live in the `Config` dataclass at [`src/timetabling/config.py`](src/timetabling/config.py).

---

## Solve chain

The pipeline is a chain of small, single-purpose modules. A course list becomes legal candidates, the solver places and optimizes them, and an independent validator re-checks the result before it is exported as the UI contract.

```text
┌──────────────────────────────────────────┐
│   course list                            │
│   CSV · one row per section              │
└──────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────┐
│   derive blocks                          │
│   T·P·L → cohort, theory & lab blocks    │
└──────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────┐
│   prune candidates                       │
│   legal (room, day, start) only:         │
│   capacity · lab · window · blackout     │
└──────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────┐
│   CP-SAT / repair                        │
│   place + optimize · no-overlap,         │
│   different-day · soft objective         │
└──────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────┐
│   validate                               │
│   independent re-check, decoupled        │
│   from the solver                        │
└──────────────────────────────────────────┘
                      │
                      ▼
┌──────────────────────────────────────────┐
│   schedule.json                          │
│   the UI contract  (+ assignments.csv)   │
└──────────────────────────────────────────┘
```

---

## Architecture

| Layer | Stack |
| --- | --- |
| Solver core | OR-Tools **CP-SAT** (pure Python) |
| Data pipeline | pandas · dataclasses · `src/timetabling/` |
| Full-period solver | Warm-started small-neighbourhood **repair** (`repair.py`) |
| Validation | Solver-independent re-derivation (`validate.py`) |
| Web app | **Streamlit** ≥ 1.40 — one container, no separate frontend build |
| i18n / theming | Bilingual TR/EN · light/dark CSS design tokens |
| Testing | **pytest** — 132 tests |
| Packaging | Docker (`python:3.11-slim`) |
| Deployment | **Google Cloud Run** — EU region, IAM-gated, scale-to-zero |

The architecture rests on a deliberate split between solving and checking: `model_cpsat.py` and `repair.py` produce a schedule, and `validate.py` re-derives every hard violation from the assignment list with no knowledge of the solver's internals — so a model bug surfaces as a reported violation instead of a silent error.

---

## The app

A single-page progressive flow that walks a user from raw CSV to a placed timetable. Bilingual (Turkish / English), with a light/dark theme toggle, and usable on a phone in portrait orientation.

| Step | What happens |
| --- | --- |
| **1 · Upload courses** | Drop a course-list CSV — or press **Try with sample dataset** (100 sections across 20 departments, bundled, PII-free) |
| **2 · Review data** | KPI summary (sections, courses, departments, instructors) and non-blocking data-quality warnings |
| **3 · Classrooms** | Add / edit / delete rooms with capacity and an explicit **is-lab** flag — 103 PII-free defaults preloaded; the `Online` virtual room is added automatically |
| **4 · Solve** | One **Solve** button → blocking spinner → placement summary, under a fixed 1200 s budget |
| **5 · Results** | Weekly Mon–Fri grid, view by cohort / room / instructor / department / course, conflict + unschedulable lists, and `schedule.json` / `assignments.csv` download |

```bash
PYTHONPATH=src streamlit run app.py      # http://localhost:8501
```

---

## Project Structure

```text
src/timetabling/        The solver and pipeline (importable, framework-free)
├── config.py           Config dataclass — every tunable parameter, DAYS, LAB_SUFFIXES
├── model.py            Room, Instructor, Block, Section, Candidate, Assignment, Violation
├── textnorm.py         Staff-ID / name / int normalization
├── schedule_parse.py   SCHEDULE grammar (unit / chain / X-over-Y / dirty → flag)
├── io_csv.py           Quote-aware CSV loaders (dtype=str, leading zeros preserved)
├── clean.py            Room classification (lab / online / physical / virtual)
├── join.py             Grades + enrollment + Plan combined frame
├── derive.py           Section + Block derivation (level, cohort, T/P/L blocks)
├── route.py            mark_virtual (online/oversize → virtual room), mark_lab_rooms (pin lab)
├── model_cpsat.py      Candidate generation + pruning + single-shot CP-SAT model
├── repair.py           Construction + warm-started neighbourhood repair solver (--repair)
├── decompose.py        Legacy faculty-by-faculty greedy (--decompose), kept for comparison
├── validate.py         Solver-independent hard-constraint validator
├── report.py           Data-quality report + Mode-B benchmark
├── export.py           schedule.json (UI contract) + CSV
├── pipeline.py         run_pipeline() — one solve path shared by CLI and UI
├── defaults.py         PII-free default classroom inventory (103 rooms)
├── i18n.py             Bilingual TR/EN string catalog
├── ui_*.py             Streamlit theming, grid, input, app-shell helpers
└── __main__.py         CLI / pipeline orchestration

views/                  Streamlit step renderers — upload, review, classrooms, solve, results
app.py                  Single-page app shell (app bar + stepper + hero + sections)
assets/                 Brand SVGs + bundled PII-free sample course list
examples/               Tiny demo CSV
tests/                  pytest suite (132 tests)
MODEL.md                Full model + rules + design rationale
DEPLOY.md               Google Cloud Run deployment runbook
Dockerfile              Streamlit + OR-Tools image for Cloud Run
data/                   Real institutional CSVs (git-ignored — contains PII)
```

---

## Quick Start

Requires Python 3.11+.

```bash
python3 -m pip install -r requirements.txt   # pandas, ortools, pytest, streamlit

# Web app (the easy path — try it with the bundled sample dataset)
PYTHONPATH=src streamlit run app.py

# Run the tests
python3 -m pytest -q                         # 132 tests
```

> The web app and tests need **no private data** — classroom defaults come from `defaults.py` and a PII-free sample course list ships in `assets/`. The real institutional CSVs live in `data/`, which is git-ignored and absent from fresh clones.

### Command-line solver

```bash
# Full period — the primary path, via the repair solver
PYTHONPATH=src python3 -m timetabling --period 001 --scope all --mode A --repair

# A single faculty — small scopes solve directly in one CP-SAT pass
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Basic Sciences" --mode A,B --time-limit 60
```

| Flag | Values | Description |
| --- | --- | --- |
| `--period` | `001` (Fall) · `002` (Spring) | Term to schedule — each solved independently |
| `--scope` | `all` · `faculty=<text>` · `dept=<CODE>` | The slice to solve |
| `--mode` | `A,B` (default) · `A` · `B` | **A** solves from scratch; **B** benchmarks against the existing program |
| `--repair` | flag | Warm-started neighbourhood repair — the path for full `--scope all` |
| `--decompose` | flag | Legacy faculty-by-faculty greedy (~49%), kept for comparison |
| `--time-limit` | seconds (default 60) | CP-SAT budget for the single-shot solver |
| `--max-rooms-per-block N` | int | Truncate each block's candidate room list (model-size lever) |
| `--out` | dir (default `out/`) | Output folder |

---

## Input contract

The engine runs from a single **course list** — one CSV, one row per section.

| Column | Meaning |
| --- | --- |
| `Course Code` | e.g. `CMPE 113` — department prefix and year level are derived from it (`CMPE`, year 1) |
| `Course Name` | Display name |
| `Section No` | Section number within the course |
| `T` / `P` / `L` | Weekly theory / practice / lab hours |
| `Lecturer Name` | Display name — informational only |
| `Lecturer Email` | The instructor's identity key; team-taught sections list comma-separated emails |
| `~Students` | Approximate enrollment — drives room capacity and virtual-room routing |

```csv
Course Code,Course Name,Section No,T,P,L,Lecturer Name,Lecturer Email,~Students
CMPE 113,Introduction to Programming,1,3,0,2,Jane Doe,jane.doe@uni.edu,45
ECON 101,Principles of Economics,1,3,0,0,John Smith,john.smith@uni.edu,120
```

**Derived automatically:** cohort `(department prefix, year level)` from the course code; instructor identity from email; teaching blocks from `T`/`P`/`L` (theory splits into ≤2 h same-section sessions on different days). **Provided separately:** the classroom inventory (name, capacity, explicit lab flag) and the period.

### Outputs (`out/`)

| File | Contents |
| --- | --- |
| `schedule_<period>.json` | The UI contract — per-assignment `section_id, course_code, block_kind, instructor, cohort, day, start, end, room, …` plus `meta`, `unmet_soft`, `conflicts` |
| `schedule_<period>.csv` | The same assignments as a flat table |
| `data_quality_<period>.json` | Parse / room / cohort / join checks + the unschedulable list |
| `mode_b_<period>.json` | Generated vs. existing program — conflict counts, room usage, evening ratio |

---

## Deployment

Kairos ships as a single Docker image — Streamlit, OR-Tools CP-SAT, and PII-free defaults — on **Google Cloud Run**, in the institution's own GCP project, **EU region**, **scale-to-zero**. Access is locked to named Google accounts via IAM; the live deployment is reached through `gcloud run services proxy` or the domain mapping at `kairos.huguryildiz.com`.

```bash
gcloud run deploy timetabling --source . \
  --no-allow-unauthenticated \
  --memory 4Gi --cpu 4 --cpu-boost \
  --timeout 3600 --min-instances 0 --max-instances 2
```

> **Memory matters:** a CP-SAT solve needs **≥ 4 GiB** — the Cloud Run default of 512 MiB OOM-kills the container and the Solve button silently does nothing. The full runbook (regions, IAM, KVKK notes, troubleshooting) is in [`DEPLOY.md`](DEPLOY.md).

---

## Reference

- [`MODEL.md`](MODEL.md) — the full model: time grid, hard rules, soft objective, block derivation, and the design decisions behind them.
- [`TODO.md`](TODO.md) — phase-by-phase engineering record and remaining backlog.
- [`CLAUDE.md`](CLAUDE.md) — repository conventions and gotchas.

---

<p align="center">
  <strong>Kairos</strong> · Course Timetabling<br>
  <sub>🗓️ Every section, placed on a conflict-free weekly grid.</sub>
</p>
