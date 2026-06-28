<!-- markdownlint-disable MD033 MD041 -->

<p align="center">
  <img src="assets/icon.svg" alt="Kairos logo" width="120" height="120">
</p>

<h1 align="center">KAIROS</h1>

<p align="center">
  <strong>Course Timetabling</strong><br>
  <sub>Upload a course list and room inventory — get a conflict-free weekly schedule.</sub>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python_3.11-0b1220?style=for-the-badge&logo=python&logoColor=3776AB" alt="Python 3.11">
  <img src="https://img.shields.io/badge/OR--Tools_CP--SAT-0b1220?style=for-the-badge&logo=google&logoColor=4285F4" alt="OR-Tools CP-SAT">
  <img src="https://img.shields.io/badge/Streamlit-0b1220?style=for-the-badge&logo=streamlit&logoColor=FF4B4B" alt="Streamlit">
  <img src="https://img.shields.io/badge/Docker-0b1220?style=for-the-badge&logo=docker&logoColor=2496ED" alt="Docker">
  <img src="https://img.shields.io/badge/Google_Cloud_Run-0b1220?style=for-the-badge&logo=googlecloud&logoColor=4285F4" alt="Google Cloud Run">
  <a href="https://kairos.huguryildiz.com"><img src="https://img.shields.io/badge/kairos.huguryildiz.com-live-4F46E5?style=for-the-badge&logo=googlechrome&logoColor=white" alt="Live"></a>
</p>

---

KAIROS takes a university's raw course and room data and produces a **weekly timetable** where every block has a day, a time, and a room — and no two blocks illegally share any of them. No room is double-booked. No instructor teaches in two places at once. No section exceeds its room's capacity. Every placement is verified by an independent validator after the solver finishes.

It runs two ways: a **web app** for non-technical users and a **command-line solver** for batch runs and benchmarking. The math, rules, and design rationale are in [`MODEL.md`](MODEL.md).

---

## What it does

- **Conflict-free by construction.** Placement-legality rules are enforced during candidate generation, while cross-block resource conflicts are enforced in the solver; room capacity, lab pinning, time-window, blackout, room-overlap, and instructor-overlap violations cannot appear in the output.
- **Optimized, not just valid.** After placement, a soft polish phase minimizes idle gaps, compacts instructor days, reduces late-hour load, and keeps each section in a stable room — all tunable from the UI.
- **Works with what you have.** A course list and a classroom inventory are the only required inputs. Cohorts, teaching blocks, and instructor identities are derived automatically.
- **Verified independently.** A validator re-checks every core constraint from the raw assignment list, decoupled from the solver, so an encoding bug cannot pass silently.
- **Exports a ready-to-use result.** A Mon–Fri grid viewable by cohort, room, instructor, or department; `schedule.json` / `schedule.csv` for downstream use; a multi-page PDF.

---

## The app

A single-page flow, bilingual (Turkish / English), usable on a phone in portrait.

**1 · Data** — Upload a course-list CSV or try the bundled PII-free sample. Review a KPI summary and data-quality warnings. Load a classroom inventory or use the bundled classroom sample.

**2 · Settings** — Configure day window, blackout slots, Saturday toggle, graduate-hour controls, soft-preference presets, and per-instructor availability. Everything is optional — untouched settings fall back to defaults.

**3 · Solve** — One click. A five-phase progress display (candidates → construct → repair → soft polish → validate) runs under a fixed 50-minute budget.

**4 · Results** — Weekly grid, conflict and unschedulable lists, and JSON / CSV / PDF download.

---

## Quick start

Requires Python 3.11+.

```bash
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m streamlit run app.py      # http://localhost:8501
```

The web app works without any private data — a PII-free sample course list ships in `assets/` and classroom data is uploaded by the user.

```bash
.venv/bin/python -m pytest -q      # run the test suite
```

For batch runs and benchmarking:

```bash
PYTHONPATH=src .venv/bin/python -m timetabling \
  --courses assets/sample_courses.csv \
  --rooms assets/sample_classrooms.csv \
  --mode A \
  --repair
```

CLI flags: `--courses` is the course-list CSV to optimize. `--rooms` is the classroom inventory; when omitted, the bundled sample inventory is used. `--mode A` generates a new KAIROS schedule.

---

## Deployment

KAIROS ships as a single Docker image on **Google Cloud Run**, in the institution's own GCP project, `europe-west1`, scale-to-zero. Access is locked to named Google accounts via IAM; the live service is mapped to `kairos.huguryildiz.com`. No PII enters the image — course and classroom data are supplied at runtime.

Every push to `main` triggers [`cloudbuild.yaml`](cloudbuild.yaml). To deploy by hand:

```bash
gcloud run deploy kairos --source . --region europe-west1 \
  --no-allow-unauthenticated \
  --memory 8Gi --cpu 4 --cpu-boost \
  --timeout 3600 --min-instances 0 --max-instances 5
```

> Keep `--memory 8Gi`. A CP-SAT solve needs at least 4 GiB; the Cloud Run default of 512 MiB kills the container mid-solve.

---

## Reference

[`MODEL.md`](MODEL.md) — time grid, hard constraints, soft objective, block derivation, design decisions, and benchmarks.

---

<p align="center">
  <strong>KAIROS</strong> · Course Timetabling<br>
  <sub>Every section, placed on a conflict-free weekly grid.</sub>
</p>
