# TODO — Future Phases

Phase 1 (end-to-end pipeline + slice-level feasibility proof) is complete.
See [README.md](README.md). The items below are the backlog for later phases.

---

## Phase 2 — Model fidelity and full-scale solving

### 2.1 Cohort constraint fix (high priority, spec-faithful)

- **Problem:** Currently *any* two sections of the same cohort cannot overlap. But spec
  hard-constraint #3 says "in two **courses** at the same time" → different **sections**
  of the same course (opened in parallel for different student groups) should be allowed
  to overlap.
- **To do:** Enforce cohort no-overlap at the **course-code level**: at most one *distinct
  course code* active per `(cohort, slot)`; sections of the same course may run in parallel.
  CP encoding: a `course_busy[cohort, course, day, hour]` indicator variable +
  `sum(course_busy) <= 1` per `(cohort, slot)`.
- **Expected effect:** Cases like CMPE 113 _01–_04 and service courses become feasible.
- **Test:** two sections of the same course may run in parallel; two sections of
  *different* courses may not.

### 2.2 Split long blocks across multiple days

- **Problem:** A single block of T+P ≥ ~10h does not fit the 09–18 window (studio courses).
- **To do:** Extend `blocks_from_tpl` to split a long theory load into smaller blocks spread
  across multiple days (Article 1 is already IGNORED; free splitting is allowed). A section's
  blocks already cannot overlap via the cohort/instructor constraints; additionally reward
  "spread across non-adjacent days" (soft #2). Make the split strategy parametric (e.g. a max
  block length).
- **Test:** a 10-hour section is split into ≥2 blocks and placed.

### 2.3 Team-taught sections

- **Problem:** Grades `Staff ID` carries two comma-joined IDs for some sections
  (`"00003893,00002022"`) → treated as one synthetic instructor, name left blank.
- **To do:** Split the IDs; treat the section as belonging to *all* listed instructors
  (include each in instructor no-overlap); show joined names for the UI.

### 2.4 Oversize sections

- **Problem:** 16 sections (largest TEDU 101 = 497 students) exceed the largest room (100).
- **Options:** (a) add large lecture halls to the room master; (b) split the section into
  parallel sub-groups; (c) turn the capacity constraint into a soft "overflow penalty"
  (optional). Currently excluded and reported — apply once decided.

### 2.5 Full-period solve and decomposition

- After 2.1–2.2, attempt the **full 001 period (~793 sections)** with `--scope all`; measure
  time/quality. If needed:
  - **Faculty-based decomposition** sharing the room pool + a shared-room reservation scheme.
  - Warm start (hint from the existing program) — Mode C.
- Also run the **002 (Spring) period** and report (the pipeline is period-parametric).

### 2.6 Soft objective calibration

- Tune weights against benchmarks: room fill ~0.53, evening ratio ~7%.
- Incrementally add soft #2/#4/#5/#7/#8/#14 (non-adjacent days, day balance, daily load,
  instructor free days, part-time clustering, practicum buffer) and measure their effect.

---

## Phase 3 — Web UI (read-only)

- React + shadcn/ui; does not run the solver, only reads `schedule_<period>.json`.
- Weekly grid (Mon–Fri × 09:00–21:00); room / instructor / cohort / department filters.
- Highlight conflicts and unmet soft constraints; Mode-B comparison summary.
- The JSON contract is fixed in `export.py` — the UI consumes that.

---

## Optional / out of scope (if requested)

- **Graduate (5XX/6XX)** inclusion toggle (`include_grad`) + 18–21 evening preference.
- **Saturday** toggle (`saturday_enabled`) — Dean-approved exceptions.
- **Plan-only ~225 sections** inclusion (`include_plan_only`) with hour estimation.
- Exam-period scheduling (outside the weekly timetable — Article 13).

## Data-quality follow-ups

- Review the lab-room mapping (13 rooms found; the spec said ~14).
- Also report dirty rows in the Grades `Schedule` column (currently checked via Plan;
  Plan 001 had 0 dirty rows).
- Add the `enrollment_summary` cross-check of department×year totals to the report.
