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
| **Blackouts** — school-configured closed slots, scope *everyone* or *full-time only* (none by default; e.g. a Friday congregational-prayer hour, a Thursday staff seminar) | candidate pruning |
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
| Testing | **pytest** — 179 tests |
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
| **3 · Classrooms** | Add / edit / delete rooms with capacity and a categorical **Type** (`normal/lab/pc/studio`) — 103 PII-free defaults preloaded; the `Online` virtual room is added automatically |
| **4 · School Settings** | Optional per-school config: day window, blackout slots, Saturday / graduate toggles (incl. a configurable graduate earliest-start hour for daytime grad classes), block-split policy, an instructor daily-hours cap, preference-weight presets, half-day instructor availability, and a download / upload school-profile JSON — backward-compatible (untouched = today's defaults) |
| **5 · Solve** | One **Solve** button → blocking spinner → placement summary, under a fixed 3000 s budget |
| **6 · Results** | Weekly Mon–Fri grid, view by cohort / room / instructor / department / course, conflict + unschedulable lists, and `schedule.json` / `assignments.csv` download |

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
├── defaults.py         PII-free default classroom inventory (103 rooms)
├── i18n.py             Bilingual TR/EN string catalog
├── ui_*.py             Streamlit theming, grid, input, app-shell helpers
└── __main__.py         CLI / pipeline orchestration

views/                  Streamlit step renderers — upload, review, classrooms, settings, solve, results
app.py                  Single-page app shell (app bar + stepper + hero + sections)
assets/                 Brand SVGs + bundled PII-free sample course list
examples/               Tiny demo CSV
tests/                  pytest suite (179 tests)
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
python3 -m pytest -q                         # 148 tests
```

> The web app and tests need **no private data** — classroom defaults come from `defaults.py` and a PII-free sample course list ships in `assets/`. The real institutional CSVs live in `data/`, which is git-ignored and absent from fresh clones.

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
| `~Students` | Actual/expected enrolment — KPIs + soft right-sizing (falls back to `Section Capacity`) |
| `Room Type` | Required room category: `normal` / `lab` / `pc` / `studio` |

```csv
Course Code,Course Name,Dept,Section No,Instructor Name,Instructor Email,Part-time,T,P,L,Section Capacity,~Students,Room Type
CMPE 113,Introduction to Programming,Faculty of Engineering,CMPE 113_01,Jane Doe,jane.doe@uni.edu,,3,0,2,50,45,pc
ECON 101,Principles of Economics,Faculty of Econ.,ECON 101_01,John Smith,john.smith@uni.edu,,3,0,0,120,118,
```

**Classroom inventory** — `Room`, `Capacity`, `Type` (`normal/lab/pc/studio`; derived from the room-name token, e.g. `-PC`→`pc`, when seeding). Defaults ship in `defaults.py`.

**Derived automatically:** cohort `(program code, year level)` from the course code; instructor identity from email-or-name; teaching blocks from `T`/`P`/`L` (theory splits into ≤2 h same-section sessions on different days). The `section → room` assignment is the solver's **output**, never an input.

### Outputs (`out/`)

| File | Contents |
| --- | --- |
| `schedule_<period>.json` | The UI contract — per-assignment `section_id, course_code, block_kind, instructor, cohort, day, start, end, room, …` plus `meta`, `unmet_soft`, `conflicts` |
| `schedule_<period>.csv` | The same assignments as a flat table |
| `data_quality_<period>.json` | Parse / room / cohort / join checks + the unschedulable list |
| `mode_b_<period>.json` | Generated vs. existing program — conflict counts, room usage, evening ratio |

---

## Deployment

Kairos ships as a single Docker image — Streamlit, OR-Tools CP-SAT, and PII-free defaults — on **Google Cloud Run**, in the institution's own GCP project, **`europe-west1`**, **scale-to-zero**. Access is locked to named Google accounts via IAM; the live service is mapped to `kairos.huguryildiz.com`. No PII enters the image — `.dockerignore` keeps `data/` out, and classroom defaults come from `defaults.py`.

**Continuous deploy.** Every push to `main` triggers [`cloudbuild.yaml`](cloudbuild.yaml), which deploys the `kairos` service to `europe-west1` with the resources below. To deploy by hand (same flags, so manual and CI stay in sync):

```bash
gcloud run deploy kairos --source . --region europe-west1 \
  --no-allow-unauthenticated \
  --memory 8Gi --cpu 4 --cpu-boost \
  --timeout 3600 --min-instances 0 --max-instances 2
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
