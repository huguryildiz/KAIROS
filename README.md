<!-- markdownlint-disable MD033 MD041 -->
<!-- Inline HTML is intentional: centered hero header and badge row. -->

<p align="center">
  <img src="assets/icon.svg" alt="Kairos logo" width="120" height="120">
</p>

<h1 align="center">KAIROS</h1>

<p align="center">
  <strong>Course Timetabling</strong><br>
  <sub>Conflict-free weekly university schedules, solved from real data — upload a course list and room inventory, then place each feasible block on a day, time, and room.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python_3.11-0b1220?style=for-the-badge&logo=python&logoColor=3776AB" alt="Python 3.11">
  <img src="https://img.shields.io/badge/OR--Tools_CP--SAT-0b1220?style=for-the-badge&logo=google&logoColor=4285F4" alt="OR-Tools CP-SAT">
  <img src="https://img.shields.io/badge/Streamlit-0b1220?style=for-the-badge&logo=streamlit&logoColor=FF4B4B" alt="Streamlit">
  <img src="https://img.shields.io/badge/pandas-0b1220?style=for-the-badge&logo=pandas&logoColor=white" alt="pandas">
  <img src="https://img.shields.io/badge/pytest-0b1220?style=for-the-badge&logo=pytest&logoColor=0A9EDC" alt="pytest">
  <img src="https://img.shields.io/badge/Docker-0b1220?style=for-the-badge&logo=docker&logoColor=2496ED" alt="Docker">
  <img src="https://img.shields.io/badge/Google_Cloud_Run-0b1220?style=for-the-badge&logo=googlecloud&logoColor=4285F4" alt="Google Cloud Run">
  <a href="https://kairos.huguryildiz.com"><img src="https://img.shields.io/badge/kairos.huguryildiz.com-live-4F46E5?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Live"></a>
</p>

---

## Overview

**Kairos** turns a university's raw course and room data into coherent **day + time + room** assignments — a weekly timetable whose placed blocks are provably free of resource conflicts under one consistent rule set.

Section, instructor, size, and the T–P–L hour split are **fixed inputs**. The engine reasons over the only two degrees of freedom that matter — **time and room** — and never produces an illegal placement: a room is never double-booked, an instructor is never in two places at once, capacity is never exceeded, and every undergraduate block lands inside the teaching window.

It runs two ways: a **command-line solver** for batch runs and benchmarking, and a **bilingual web app** (Streamlit) where a non-technical user uploads a course list, edits classrooms, presses **Solve**, and reads the result on a Mon–Fri grid. The optimization core is OR-Tools **CP-SAT**; the math, rules, and design rationale are documented in [`MODEL.md`](MODEL.md).

---

## Why Kairos

Hand-building a university timetable means juggling hundreds of sections against a handful of rooms, dozens of instructors, and a tangle of rules — and a single missed clash propagates into the term. The hard part isn't *drawing* the grid; it's guaranteeing nothing collides.

- **Conflict-free by construction.** Hard rules are enforced before the solver ever sees a placement; the schedule cannot encode a room, instructor, capacity, lab, window, or blackout clash.
- **Solved from real data.** A course-list CSV plus a classroom inventory are the input contract — cohorts, teaching blocks, and instructor identities are derived from the course list.
- **Independently verified.** A validator re-derives the core hard-resource violations from the final assignment list, decoupled from the solver, so an encoding bug in those rules cannot pass silently.
- **Honest about its limits.** Placement and any residual tail are reported with the numbers, not hidden — and the scaling study shows exactly where a single solve stops being practical.
- **Two front doors.** A scriptable CLI for operators and a zero-friction web app for everyone else, sharing one solve path.
- **Privacy-first deployment.** No PII in the image; runs IAM-gated on the institution's own EU cloud, scale-to-zero.

---

## The model

Hard rules and soft preferences are kept strictly apart. **Hard constraints can never be violated**; **soft preferences are weighted penalties** the solver minimizes, so they can never cause infeasibility.

### Hard constraints

| Rule | Where enforced |
| --- | --- |
| **Room capacity** — seats ≥ section size (`Section Capacity`, with `~Students` only as fallback) | candidate pruning |
| **Pinned lab room** — a lab block sits only in its designated lab room | candidate pruning |
| **Undergraduate window** — every block ends by 18:00 | candidate pruning |
| **Blackouts** — school-configured closed slots, scope *everyone* or *full-time only* (none by default; e.g. a Friday congregational-prayer hour, a Thursday staff seminar) | candidate pruning |
| **Placement** — exactly one slot per block | CP-SAT model |
| **Room / instructor no-overlap** — incl. team-taught co-instructors | CP-SAT model |
| **Self no-overlap** — a section's own blocks never collide | CP-SAT model |
| **Theory different-day** — a section's theory sessions fall on distinct days | model + repair + validator |
| **Room type** — an explicit section `Room Type` demand (`lab/pc/studio`) is honored exactly; empty/`normal` means no categorical restriction | candidate pruning |
| **Instructor unavailability** — per-instructor hourly availability configured in Settings is excluded from that instructor's candidates; legacy AM/PM profile codes still decode on load | candidate pruning |
| **Fixed slot** — a section with a `Fixed` column value is pinned to exactly that `(day, start)` slot | candidate pruning + CP-SAT |
| **Room ownership** — rooms with a `Dept` column value are restricted to that owning department | candidate pruning |

Most hard rules are enforced **during candidate generation** — only legal `(room, day, start)` placements are ever produced — while cross-block relations become model/solver constraints. A virtual `Online` room absorbs online and oversize sections (those whose enrollment exceeds the capacity of every physical room in the loaded inventory): unlimited capacity, exempt from room no-overlap, while instructor and self constraints still apply.

### Soft objective (minimized)

The CP-SAT monolith (small scopes, ≤50 sections) and the repair soft polish (full period) minimize separate weighted-sum objectives. All weights live in `Config` at [`src/timetabling/config.py`](src/timetabling/config.py).

**Repair soft polish** (`soft_search.anneal_soft`, deluge acceptor — primary path for full-period solves):

| Term | Default weight | Intent |
| --- | --- | --- |
| **Student idle gaps** (`w_idle`) | 15 | Minimize idle hours inside a cohort's day — always-on, fixed weight |
| **Anti-fatigue** (`w_maxrun`) | 10 | Penalize consecutive teaching runs longer than `max_consecutive_hours` |
| **Instructor day-compactness** (`w_instr_days` / `w_parttime_days`) | 10 / 14 | Fewer teaching days beyond the `instr_days_target` dial (No target = off) |
| **Room stability** (`w_room_stable`) | 10 | Penalize sections that use more than one room across their blocks |
| **Free day** (`w_free_day`) | 10 | Reward each configured year-level cohort that has at least one free weekday — scope-controlled (year multiselect), not weight-steerable |

**CP-SAT monolith** (`model_cpsat.py` — small scopes):

| Term | Default weight | Intent |
| --- | --- | --- |
| **Cohort conflict** (`w_cohort_conflict`) | 50 | Different courses in a `(dept, year)` cohort incur a penalty — a hard cohort rule was proven INFEASIBLE at scale |
| **Student idle gaps** (`w_cohort_gap`) | 10 | Minimize idle hours inside a cohort's day |
| **Instructor day-compactness** (`w_instr_days` / `w_parttime_days`) | 10 / 14 | Fewer distinct teaching days per instructor |
| **Course-level ordering** (`w_order`) | 1 | Lower-level courses earlier in the day |
| **Engineering lab days** (`w_englab`) | 1 | Engineering labs prefer Thu/Fri |

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
                      ▼  (repair path only)
┌──────────────────────────────────────────┐
│   soft polish                            │
│   anneal_soft · deluge acceptor          │
│   idle / maxrun / instr_days /           │
│   room_stable / free_day                 │
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
│   the UI contract  (+ schedule.csv)      │
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
| Testing | **pytest** — 287 tests |
| Packaging | Docker (`python:3.11-slim`) |
| Deployment | **Google Cloud Run** — EU region, IAM-gated, scale-to-zero |

The architecture rests on a deliberate split between solving and checking: `model_cpsat.py` and `repair.py` produce a schedule (the repair path adds a `soft_search.py` polish phase after convergence), and `validate.py` re-derives the core hard-resource violations from the assignment list with no knowledge of the solver's internals — so model bugs in those rules surface as reported violations instead of silent errors.

---

## The app

A single-page progressive flow that walks a user from raw CSV to a placed timetable. Bilingual (Turkish / English), with a light/dark theme toggle, and usable on a phone in portrait orientation.

| Step | What happens |
| --- | --- |
| **1 · Data** | One numbered step bundling three sub-sections: **upload** a course-list CSV — or press **Try with sample dataset** (100 sections across 14 departments, bundled, PII-free); a **review** with a KPI summary (sections, courses, departments, instructors) and non-blocking data-quality warnings; and a **classroom** step — upload a room-inventory CSV or load the bundled 107-room sample (PII-free, `normal/lab/pc/studio` types, optional `Dept` ownership column); the `Online` virtual room is added automatically |
| **2 · School Settings** | Optional per-school config: day window, blackout slots, Saturday toggle, global/per-department graduate earliest-start controls (graduate courses are always included), block-split policy, instructor-days target, free-day year scope, preference-weight presets, and per-hour instructor availability — backward-compatible (untouched = today's UI defaults) |
| **3 · Solve** | **Solve** button — disabled with a targeted warning and a scroll-to link if course data has blocking errors (missing required columns / no rows) or the classroom inventory is empty; otherwise one click starts the 5-phase progress display (candidates → construct → repair sweeps → soft polish → validate) with a Python-driven step indicator and animated progress bar, under a fixed 3000 s budget |
| **4 · Results** | Weekly Mon–Fri grid, view by cohort / room / instructor / department / course, conflict + unschedulable lists, and `schedule.json` / `schedule.csv` / multi-page PDF download |

The course-list CSV may carry optional columns — `Year`, `Part-time`, `Room Type`, `Fixed` — that override the cohort year / part-time flag / room-type demand (`normal/lab/pc/studio`) / pinned slot otherwise derived from the course code and instructor name (absent → derived as before).

```bash
PYTHONPATH=src streamlit run app.py      # http://localhost:8501
```

---

## Project Structure

```text
src/timetabling/        The solver and pipeline (importable, framework-free)
├── config.py           Config dataclass — every tunable parameter, DAYS, LAB_SUFFIXES
├── settings.py         School-Settings layer — Settings dict ↔ Config, availability, profile JSON
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
├── i18n.py             Bilingual TR/EN string catalog
├── soft_search.py      Move-based local-search soft polish (anneal_soft, deluge acceptor — post-convergence phase of repair)
├── pdf_export.py       Landscape-A4 PDF timetable export (fpdf2, DejaVuSans for Turkish glyphs)
├── csv_import.py       UI-side CSV upload helper (encoding detection, header validation)
├── ui_*.py             Streamlit theming, grid, input, app-shell helpers
└── __main__.py         CLI / pipeline orchestration

views/                  Streamlit step renderers — upload, review, classrooms, settings, solve, results
app.py                  Single-page app shell (app bar + stepper + hero + sections)
assets/                 Brand SVGs + bundled PII-free sample course list + sample classroom inventory
tests/                  pytest suite (287 tests)
MODEL.md                Full model + rules + design rationale
Dockerfile              Streamlit + OR-Tools image for Cloud Run
cloudbuild.yaml         Cloud Run continuous deploy (push to main)
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
python3 -m pytest -q                         # 287 tests in this checkout
```

> The web app and **most** tests need **no private data** — a PII-free sample course list ships in `assets/` and classroom data is uploaded by the user. The real institutional CSVs live in `data/`, which is git-ignored and absent from fresh clones; the legacy CLI Grades-path tests (`io_csv` / `join` / `derive`) require those files.

### Docker (local)

Build and run the same image that ships to Cloud Run:

```bash
docker build -t kairos .
docker run --rm -p 8501:8080 kairos
# then open http://localhost:8501
```

`data/` is never copied in (see `.dockerignore`) — the container is ready to use with uploaded input and the bundled PII-free sample. Cloud Run injects `$PORT`; locally the container listens on `8080`, which the command above maps to `8501`.

### Command-line solver

```bash
# Full period — the primary path, via the repair solver
PYTHONPATH=src python3 -m timetabling --period 001 --scope all --mode A --repair

# A single faculty — small scopes solve directly in one CP-SAT pass
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope department="Basic Sciences" --mode A,B --time-limit 60
```

| Flag | Values | Description |
| --- | --- | --- |
| `--period` | `001` (Fall) · `002` (Spring) | Term to schedule — each solved independently |
| `--scope` | `all` · `department=<text>` · `dept=<CODE>` | The slice to solve |
| `--mode` | `A,B` (default) · `A` · `B` | **A** solves from scratch; **B** benchmarks against the existing program |
| `--repair` | flag | Warm-started neighbourhood repair — the path for full `--scope all` |
| `--decompose` | flag | Legacy faculty-by-faculty greedy (~49%), kept for comparison |
| `--time-limit` | seconds (default 60) | CP-SAT budget for the single-shot solver |
| `--max-rooms-per-block N` | int | Truncate each block's candidate room list (model-size lever) |
| `--out` | dir (default `out/`) | Output folder |
| `--no-soft-shaping` | flag | Disable cohort-conflict soft shaping during greedy construction |

---

## Input contract

Two independent tables: a **course list** (one row per section, uploaded each term) and a
**classroom inventory** (stable; defaults shipped). The full contract is [`INPUT_SCHEMA.md`](INPUT_SCHEMA.md).

**Course list** — required: `Course Code`, `Course Name`, `Dept`, `Section No`, `Instructor Name`, `T`/`P`/`L`, `Section Capacity`. Optional: `Instructor Email`, `Part-time`, `~Students`, `Room Type`, `Fixed`, `Year`.

| Column | Meaning |
| --- | --- |
| `Course Code` | e.g. `CMPE 113` — the cohort **program code** and year level derive from it (`CMPE`, year 1) |
| `Dept` | **Faculty name** (e.g. "Faculty of Engineering") — display grouping, and the cohort fallback when the code is unparseable |
| `Section No` | Section id; `CMPE 113_01` is used directly, a bare `01` is composed |
| `T` / `P` / `L` | Weekly theory / practice / lab hours |
| `Instructor Name` | Display name; the instructor identity key when no email is given |
| `Instructor Email` | The instructor's unique identity key when present; team-taught sections list comma-separated emails |
| `Part-time` | Boolean (overrides the `(S)` name marker) |
| `Section Capacity` | The quota — the **hard** room-sizing input |
| `~Students` | Optional legacy/estimated enrolment field; current solver uses it only as a fallback when no section capacity is available |
| `Room Type` | Explicit required room category: `lab` / `pc` / `studio`; empty or `normal` means no categorical restriction |

```csv
Course Code,Course Name,Dept,Section No,Instructor Name,Instructor Email,Part-time,T,P,L,Section Capacity,~Students,Room Type
CMPE 113,Introduction to Programming,Faculty of Engineering,CMPE 113_01,Jane Doe,jane.doe@uni.edu,,3,0,2,50,45,pc
ECON 101,Principles of Economics,Faculty of Econ.,ECON 101_01,John Smith,john.smith@uni.edu,,3,0,0,120,118,
```

**Classroom inventory** — `Room`, `Capacity`, `Type` (`normal/lab/pc/studio`; derived from the room-name token, e.g. `-PC`→`pc`, when seeding). Upload your own CSV or use the built-in sample in the Classrooms step.

**Derived automatically:** cohort `(program code, year level)` from the course code; instructor identity from email-or-name; teaching blocks from `T`/`P`/`L` (theory splits into ≤2 h same-section sessions on different days). The `section → room` assignment is the solver's **output**, never an input.

### Outputs (`out/`)

| File | Contents |
| --- | --- |
| `schedule_<period>.json` | The UI contract — per-assignment `section_id, course_code, block_kind, instructor_id, instructor_name, cohort, day, start, end, room, …` plus `meta`, `unmet_soft`, `conflicts` |
| `schedule_<period>.csv` | The same assignments as a flat table |
| `data_quality_<period>.json` | Parse / room / cohort / join checks + the unschedulable list |
| `mode_b_<period>.json` | Generated vs. existing program — conflict counts, room usage, evening ratio |

---

## Deployment

Kairos ships as a single Docker image — Streamlit and OR-Tools CP-SAT — on **Google Cloud Run**, in the institution's own GCP project, **`europe-west1`**, **scale-to-zero**. Access is locked to named Google accounts via IAM; the live service is mapped to `kairos.huguryildiz.com`. No PII enters the image — `.dockerignore` keeps `data/` out; classroom and course data are supplied by the user at runtime.

**Continuous deploy.** Every push to `main` triggers [`cloudbuild.yaml`](cloudbuild.yaml), which deploys the `kairos` service to `europe-west1` with the resources below. To deploy by hand (same flags, so manual and CI stay in sync):

```bash
gcloud run deploy kairos --source . --region europe-west1 \
  --no-allow-unauthenticated \
  --memory 8Gi --cpu 4 --cpu-boost \
  --timeout 3600 --min-instances 0 --max-instances 5
```

**Grant access** to the 1–2 named users, and reach the IAM-gated service through a local proxy:

```bash
gcloud run services add-iam-policy-binding kairos --region europe-west1 \
  --member="user:alice@gmail.com" --role="roles/run.invoker"
gcloud run services proxy kairos --region europe-west1 --port 8080   # then open http://localhost:8080
```

> **Two traps to know:**
>
> - **Memory:** a CP-SAT solve needs **≥ 4 GiB** (the Cloud Run default of 512 MiB OOM-kills the container — SIGKILL, uncatchable — and the Solve button silently does nothing while lighter clicks still work); the service runs at **8 GiB** for headroom at larger problem sizes. Keep `--memory 8Gi`.
> - **Region:** `kairos.huguryildiz.com` is domain-mapped to the `europe-west1` service. Apply resource changes (`gcloud run services update kairos --region europe-west1 …`) there — not to a same-named service in another region. A deploy without `--memory/--cpu/--timeout` can revert the service to the 512 MiB / 1 vCPU / 300 s defaults, so bake them into `cloudbuild.yaml` (already done) or re-pass them.
> - **Concurrency cap:** `--max-instances 5` limits simultaneous containers. Each solve job can hold a container for up to 50 min; five is enough for a small-scale rollout and keeps runaway cost bounded.
>
> **KVKK:** keep the service in an EU region and enable Cloud Audit Logs. The solve runs synchronously inside one long request under a fixed **3000 s / 50 min** budget (`_SOLVE_SECONDS` in [`views/solve.py`](views/solve.py)); `--timeout 3600` (60 min) keeps the request alive past it, a ~10 min margin for container startup and response streaming.

---

## Reference

- [`MODEL.md`](MODEL.md) — the full model: time grid, hard rules, soft objective, block derivation, and the design decisions behind them.

---

<p align="center">
  <strong>Kairos</strong> · Course Timetabling<br>
  <sub>🗓️ Every section, placed on a conflict-free weekly grid.</sub>
</p>
