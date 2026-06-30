# Changelog

All notable releases of KAIROS are documented here.

## v1.0.0 — 2026-06-30

First stable release.

**KAIROS** — a University Course Timetabling (UCTP) solver. CP-SAT assigns each section a **day + time + room**, deployed as a bilingual (TR/EN) Streamlit app at **kairos.huguryildiz.com**.

### Highlights
- **Repair solver** for full-period scheduling (warm-started, deluge acceptor): ~99.3% (Fall 001), ~100% (Spring 002), **0 hard conflicts**.
- **Hard constraints as candidate pruning** — only legal `(room, day, start)` triples are generated; CP-SAT enforces room/instructor/cohort no-overlap + theory different-day.
- **Soft preferences** steerable at scale: max-run, instructor days (target-gated), room stability, free-day, evening, idle, fairness, same-day theory, parallel-section coordination.
- **Solver-independent `validate.py`** re-derives every hard violation from the assignments.
- **5-step mobile-first UI:** upload → review → classrooms → solve → results, with a five-phase solve progress display and a tunable soft-polish budget.
- Cloud Run deployment (8Gi / 4 vCPU); UI runs on uploaded CSVs only (no PII on disk).

### Docs
`MODEL.md` (formal model), `README.md`, `INPUT_SCHEMA.md` — all synced to code.

Release: <https://github.com/huguryildiz/KAIROS/releases/tag/v1.0.0>
