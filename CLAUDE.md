# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A University Course Timetabling (UCTP) solver: an OR-Tools **CP-SAT** model that assigns
each undergraduate section a **day + time + room**. Section/instructor/size/T-P-L are fixed
inputs; the only decision variables are time and room. Phase 1 (the pipeline + slice-level
feasibility) is complete — see [README.md](README.md) for results and [TODO.md](TODO.md) for
the backlog. Authoritative design: `docs/superpowers/specs/`; implementation plan:
`docs/superpowers/plans/`.

## Commands

```bash
python3 -m pip install -r requirements.txt          # pandas, ortools, pytest

python3 -m pytest -q                                 # all tests (pyproject sets pythonpath=src)
python3 -m pytest tests/test_model_cpsat.py -v       # one file
python3 -m pytest tests/test_validate.py::test_clean_solution_has_no_violations -v   # one test

# Run the solver (note PYTHONPATH=src — required for direct module runs, NOT just pytest)
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Department of Psychology" --mode A,B --time-limit 60
```

`--scope` is `all` | `faculty=<substr of Grades "Dept." column>` | `dept=<cohort dept code>`.
`--period` is `001` (Fall) or `002` (Spring), scheduled independently. Outputs land in `out/`.

## Architecture (the parts that span files)

The pipeline is a chain of small modules under `src/timetabling/`, orchestrated by
`__main__.py`: `io_csv → clean → schedule_parse → join → derive → model_cpsat → validate →
report → export`. Data classes and the `Config` (all tunable parameters) live in `model.py`
and `config.py`.

Key design decisions that aren't obvious from any single file:

- **Hard constraints are enforced by candidate pruning, not model constraints.**
  `model_cpsat.gen_candidates` only emits *legal* `(room, day, start)` placements (capacity,
  lab-room, undergrad <18:00 window, Friday 13–14 and Thursday 14–16 blackouts). The CP-SAT
  model then has only **H1 placement** (`AddExactlyOne` per block) and **H2–H4 no-overlap**
  (room/instructor/cohort, as `sum(occupancy) <= 1` per resource-slot). When changing a hard
  constraint, decide whether it belongs in pruning (a per-block filter) or as a model
  constraint (a cross-block relation).

- **`validate.py` is intentionally independent of the solver.** It re-derives every hard
  violation from the assignment list so a model/encoding bug cannot pass silently. Keep it
  decoupled — do not import model internals into it. It has a `check_placement` flag set
  False for Mode-B benchmarking (whose existing schedule has a different block structure).

- **Roster = the Grades files** (`derive.build_sections`), undergraduate only (~793/period).
  The "~1059" figure in the prompts is the Plan superset. Plan is a LEFT join used only for
  Mode-B benchmark + cohort/cap fallback. `rules.pdf` Article 1 is intentionally IGNORED.

- **Cohort = `(Dept_Code, Year_Level)` is a proxy with a known flaw.** It currently forbids
  *any* two same-cohort sections from overlapping, which over-constrains service/elective
  faculties and multiple sections of the same course → infeasible there. The spec-faithful
  fix (TODO 2.1) is to make cohort conflict *course-level* (same-course sections may run in
  parallel). This is the highest-leverage change for full-scale solving.

- **Blocks come from T/P/L** (`derive.blocks_from_tpl`): one theory block of `T+P` hours, one
  lab block of `L` hours (lab block restricted to lab rooms). A section's two blocks need no
  explicit non-overlap constraint — they share instructor and cohort, so H3/H4 already
  separate them.

- **`split_roomable` pre-filters unschedulable sections** (no fitting room, or a single block
  longer than the day window) and reports them, so the rest solves to 0 violations instead of
  surfacing misleading "placement" violations.

- **`schedule_*.json` is the UI contract** (`export.build_schedule_dict`). A future read-only
  React/shadcn UI consumes it; keep the per-assignment field set stable when editing.

## Gotchas

- **`PYTHONPATH=src`** is needed for `python3 -m timetabling` and ad-hoc scripts; pytest gets
  it automatically from `pyproject.toml`.
- **`data/` is gitignored** (contains PII: lecturer names, staff IDs, grade stats) but the
  CSVs must be present on disk for anything to run — they are not in fresh clones.
- **All CSVs are read `dtype=str`** to preserve leading zeros (`Period="001"`,
  `Staff_ID="00000002"`); convert numerics explicitly via `textnorm.parse_int`. Never
  `split(",")` — fields are quoted and contain commas.
- **Grades `Staff ID` may carry a `(S)` suffix** and team-taught sections carry two
  comma-joined IDs; normalize via `textnorm.normalize_staff_id` before joining to `lecturers`.
- **`--scope faculty=` matches the Grades `Dept.` column** (a faculty/program name like
  "Basic Sciences"), whereas `--scope dept=` matches the cohort dept code (like "ADA"). They
  are different namespaces.

## Git workflow (repo-specific)

Per the user's global rules: commit directly to `main`, no feature branches, no PRs. End-of-
phase deliverables are an English README + TODO.md. The `data/` directory still exists in
history at the initial commit (`71ae3f7`) — rewrite history before any public push if PII
removal is required.
