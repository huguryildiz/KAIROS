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

## ✅ What it does

- **Conflict-free by construction.** Placement-legality rules are enforced during candidate generation; cross-block resource conflicts are enforced in the solver. Violations cannot appear in the output:
  - room capacity respected for every block
  - every block can use any room large enough for it, so small classes are never crowded out of the scarce smallest rooms (the room pool scales to the inventory)
  - lab blocks pinned to lab/pc/studio rooms; theory blocks excluded from them
  - day window and blackout slots observed
  - no room double-booking, no instructor double-booking, no section self-overlap
  - theory sessions of the same course prefer different days, but may share a day as a soft fallback
  - instructor unavailability slots strictly blocked
- **Optimized, not just valid.** The soft polish phase steers the schedule toward comfort after placement — never at the cost of hard constraints:
  - minimizes cohort idle gaps and reduces late-hour load
  - compacts instructor teaching weeks into fewer days (opt-in)
  - keeps each section in a stable room across its blocks
  - honors per-section minimum spread targets and coordinates parallel sections
  - penalizes user-defined avoid-conflict course pairs
  - spreads multi-session courses across the week
  - balances prime-time access across departments
  - clusters department classes into fewer buildings
  - prefers right-sized rooms over large under-used ones
- **Minimum perturbation.** Upload a previous `schedule_*.json` export as a reference. Assignments that differ in day, start time, or room from the reference receive a soft penalty, steering the new schedule to stay as close as possible to the existing one — useful for incremental updates and rescheduling scenarios.
- **Graded instructor time preferences.** The availability editor supports four tiers per instructor: **unavailable** (hard — never placed in that slot), **avoid** (soft penalty per overlapping hour), **preferred** (soft miss-penalty when a block misses all preferred hours), and **neutral** (default, no cost). Active in both the CP-SAT monolith and the repair soft polish.
- **Works with what you have.** A course list and a classroom inventory are the only required inputs. Cohorts, teaching blocks, and instructor identities are derived automatically.
- **Verified independently.** A validator re-checks every core constraint from the raw assignment list, decoupled from the solver, so an encoding bug cannot pass silently.
- **Exports a ready-to-use result.** A Mon–Fri grid viewable by cohort, room, instructor, or department; `schedule.json` / `schedule.csv` for downstream use; a multi-page PDF.

---

## 🖥️ The app

A single-page flow, bilingual (Turkish / English), usable on a phone in portrait.

**1 · Data** 📥 — Upload a course-list CSV or try the bundled PII-free sample. Review a KPI summary and data-quality warnings. Load a classroom inventory or use the bundled classroom sample.

**2 · Settings** ⚙️ — Configure day window, blackout slots, Saturday toggle, graduate-hour controls, soft-preference presets, and per-instructor availability. Everything is optional — untouched settings fall back to defaults.

**3 · Solve** 🧮 — One click. A five-phase progress display (candidates → construct → repair → soft polish → validate) runs under a fixed 50-minute budget.

**4 · Results** 📊 — Weekly grid, conflict and unschedulable lists, and JSON / CSV / PDF download.

---

## ⚡ Quick start

Requires Python 3.11+.

```bash
.venv/bin/python -m pip install -r requirements.txt
PYTHONPATH=src .venv/bin/python -m streamlit run app.py      # http://localhost:8501
```

The web app works without any private data — PII-free sample course and classroom lists ship in `assets/` (loadable from the UI via "Try sample dataset"), or upload your own.

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

## 🚀 Deployment

KAIROS ships as a single Docker image on **Google Cloud Run**, in the institution's own GCP project, `europe-west1`, scale-to-zero. Access is locked to named Google accounts via IAM; the live service is mapped to `kairos.huguryildiz.com`. No PII enters the image — course and classroom data are supplied at runtime.

Every push to `main` triggers [`cloudbuild.yaml`](cloudbuild.yaml). To deploy by hand:

```bash
gcloud run deploy kairos --source . --region europe-west1 \
  --no-allow-unauthenticated \
  --memory 8Gi --cpu 4 --cpu-boost \
  --timeout 3600 --min-instances 0 --max-instances 5
```

> Keep `--memory 8Gi`. A CP-SAT solve needs at least 4 GiB; the Cloud Run default of 512 MiB kills the container mid-solve.

Optional result archiving can be enabled with Cloud Storage. Create a regional bucket in
`europe-west1`, grant the Cloud Run service account permission to create and list objects
(for example, object creator + object viewer on the bucket, or a custom role with
`storage.objects.create` and `storage.objects.list`), and set:

```bash
gcloud run services update kairos --region europe-west1 \
  --set-env-vars KAIROS_GCS_BUCKET=<bucket>,KAIROS_GCS_PREFIX=schedule-outputs
```

When configured, each solve still writes local `out/` files and also uploads the generated
JSON/CSV schedule outputs to `gs://<bucket>/<prefix>/`.

---

## 📚 Reference

[`MODEL.md`](MODEL.md) — time grid, hard constraints, soft objective, block derivation, design decisions, and benchmarks.

---

<p align="center">
  <strong>KAIROS</strong> · Course Timetabling<br>
  <sub>Every section, placed on a conflict-free weekly grid.</sub>
</p>
