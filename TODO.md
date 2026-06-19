# TODO — Future Phases

Phase 1 (pipeline + slice feasibility) and Phase 2 (model fidelity) are complete; the
**Current** section below records the full-period repair solver and the fidelity work that
followed. The Phase 1/2 record and the remaining backlog are kept after it.

---

## Current — Full-period repair solver + model fidelity — ✅ Completed

> **Status.** Full-period schedules are produced by a warm-started repair solver. All rules on,
> measured: period 001 = 1566/1708 placed (**91.7%**, 297 s, 3 sweeps), period 002 =
> 1585/1788 (**88.6%**, 628 s, 6 sweeps), both at **0 hard resource conflicts**. 86 tests pass.

### C.1 Warm-started repair solver (`--repair`) — ✅
`repair.py`: greedy first-fit construction seeds a full solution; CP-SAT then repeatedly frees a
small **relatedness** neighbourhood (unplaced blocks + the placed blocks competing for their
slots), re-solves it with a **soft** placement term (never infeasible), warm-started via
`AddHint`, and commits only non-worsening moves — looping until a sweep places nothing new. Makes
the ~793-section period tractable on CP-SAT (single global solve = UNKNOWN at ~356k vars). The
old per-faculty greedy (`--decompose`, ~49%) is kept for comparison. Tests:
`test_repair_*.py`.

### C.2 Virtual room for online / oversize sections — ✅
Largest real classroom = 100 seats. Sections the Plan delivers as `Online` or with enrollment
>100 are routed (`route.mark_virtual`) to a virtual `Online` room: unlimited capacity, **exempt
from room no-overlap** (instructor/self still apply). Faithful to the data (HIST/TUR online,
TEDU/ENGR roomless seminars). **Replaces the synthetic AMFI halls** (`extra_rooms` now `()`).
`validate` exempts the virtual room from capacity / lab / room-overlap. Tests:
`test_virtual_rooms.py`, `test_route.py`.

### C.3 Theory ≤2h sessions on different days — ✅
`blocks_from_tpl` splits theory into sessions of at most `cfg.max_theory_session` (2h): T:3→2+1,
T:4→2+2 (labs keep `max_block_len`). A **hard** different-day constraint (single-shot model +
repair `State`/`repair_round` + an independent `split_day` validator check) forces a section's
theory sessions onto different days. Supersedes the soft `w_nonadjacent` term for theory. Tests:
`test_split_blocks.py`, `test_different_day.py`, `test_nonadjacent.py`.

### C.4 Lab-room pinning — ✅
`route.mark_lab_rooms` reads each section's designated lab room from the Plan ROOM (the `-L`/`-PC`
token) and pins the lab block to exactly that room; `feasible_rooms_for` returns only that room;
`validate` enforces it (`lab_room`). Labs with no designated lab room (regular-room labs, project
courses) keep no pin and use regular rooms. `-PC` now classifies as a lab (H007/009-PC); the 3
real lab rooms missing from the inventory (A317/A326/DB102-MF-L, cap 50) were added to
`data/classrooms.csv`. Tests: `test_lab_rooms.py`.

### C.5 Gurobi backend removed — ✅
A Gurobi spike confirmed CP-SAT is sufficient (the bottleneck was the decomposition contract,
not the solver). `model_gurobi.py` and the `--solver` flag are removed.

### C — Deferred
- **~8–11% placement tail** (mostly Architecture studios in scarce slots). Repair plateaus;
  a tail-intensification experiment gained <1 pt for ~3× runtime — not worth it. Options: manual
  placement of the residual, or a smarter neighbourhood / restart strategy later.
- README + `mode_b_<period>.json` are refreshed for repair; a periodic full benchmark re-run
  on both periods is the maintenance task.

---

## Phase 1 — ✅ Completed (end-to-end pipeline + slice feasibility)

**Goal achieved:** a working CP-SAT pipeline that turns the real university data into a
conflict-free `day + time + room` assignment per section, with feasibility proven to **0 hard
violations** on department/faculty slices, an independent validator, and a stable JSON contract
for a future UI. Authoritative design: [spec](docs/superpowers/specs/2026-06-19-course-timetabling-cpsat-design.md);
implementation: [plan](docs/superpowers/plans/2026-06-19-uctp-cpsat-pipeline.md).

### 1.1 Pipeline (built, all modules under `src/timetabling/`) — ✅

`io_csv → clean → schedule_parse → join → derive → model_cpsat → validate → report → export`,
orchestrated by `__main__.py`. CLI flags: `--period` (001/002), `--scope`
(`all` / `faculty=` / `dept=`), `--mode` (A/B/A,B), `--time-limit`, `--out`. All tunables in the
`Config` dataclass (`config.py`).

### 1.2 Constraint model (decided and implemented) — ✅

- **Hard constraints by candidate pruning, not model constraints.** `gen_candidates` emits only
  legal `(room, day, start)` placements: capacity, lab-room, undergrad <18:00 window, Friday
  13–14 and Thursday 14–16 blackouts.
- **CP-SAT model carries only** H1 placement (`AddExactlyOne` per block) and H2–H4 no-overlap
  (room / instructor / cohort, as `sum(occupancy) <= 1` per resource-slot).
- **Soft preferences** are weighted penalty terms in `Minimize` (never pruning), so they cannot
  cause infeasibility. Phase-1 objective covers evening-slot use, room compactness, and
  instructor / part-time day-compactness.
- **Blocks from T/P/L** (`blocks_from_tpl`): one theory block of `T+P` hours, one lab block of
  `L` hours (lab block restricted to lab rooms). The two blocks share instructor + cohort, so
  H3/H4 already separate them — no explicit per-section non-overlap needed.
- **Cohort = `(Dept_Code, Year_Level)`** proxy (known over-restrictive flaw → TODO 2.1).

### 1.3 Independent validator + pre-filter — ✅

- `validate.py` re-derives every hard violation from the assignment list, decoupled from the
  solver, so a model/encoding bug cannot pass silently (`check_placement` flag off for Mode-B).
- `split_roomable` pre-filters unschedulable sections (no fitting room, or a single block longer
  than the day window) and reports them, so the rest solves to 0 violations.

### 1.4 Outputs + UI contract — ✅

`schedule_<period>.json` (UI contract, stable per-assignment field set), `schedule_<period>.csv`,
`data_quality_<period>.json` (parse/room/cohort/join checks + unschedulable list),
`mode_b_<period>.json` (generated vs. existing program).

### 1.5 Verified results (period 001) — ✅ each slice beats the existing program

| Slice | Sections | Status | Hard violations | Mode A vs existing |
|---|---|---|---|---|
| ADA dept | 5 | OPTIMAL | 0 | 1 room vs 4 |
| Econ faculty | 16 | OPTIMAL | 0 | 5 rooms vs 13, 0 vs 9 conflicts |
| Psychology | 35 | FEASIBLE | 0 | 6 rooms vs 19, 0 vs 36 conflicts |
| Architecture | 12 (+5 studios excluded) | OPTIMAL | 0 | 3 rooms vs 10 |

Test suite green (`python3 -m pytest -q`).

### 1.6 Known limitations carried into Phase 2

1. Cohort proxy too restrictive for service/elective + multi-section courses → infeasible there
   (e.g. ENG-1: 47 sections / 188 h vs a ~45 h week). → **2.1**
2. Long single blocks (studios, T+P ≥ ~10h) do not fit the day window → need multi-day split;
   excluded + reported. → **2.2**
3. Oversize sections (students > largest room = 100) → excluded + reported. → **2.4**
4. Team-taught sections (comma-joined Staff IDs) treated as one synthetic instructor, name
   blank. → **2.3**
5. Full period (~793 sections) does not solve as-is because of #1–#2. → **2.1/2.5**

---

## Phase 2 — Model fidelity and full-scale solving

> **Status (2026-06-19):** Phase 2 is complete. All model items (2.1–2.8) are implemented,
> tested, and verified on real data. Per-faculty results: 0 hard violations, beats the existing
> program across all three faculties. Full-period solving via decomposition is measured but
> partial (~49% placed); complete full-period solving is deferred. 68 tests pass.

### 2.1 Cohort constraint fix → SOFT cohort penalty — ✅ Done

- **Outcome:** Course-level cohort constraint implemented, then revised to **soft** after
  proving still INFEASIBLE at scale (Computer Engineering, 61 sections: INFEASIBLE with hard
  course-level cohort / OPTIMAL with cohort removed). The `(Dept_Code, Year_Level)` proxy
  over-counts conflict because students split across electives — 4XX courses are mostly
  electives, of which a student takes only 2–3 per term. Cohort overlap is now a weighted
  penalty (`w_cohort_conflict`, default 50) the solver minimizes, not a prohibition.
  Reported as soft metric `cohort_conflicts` in `mode_b_<period>.json`; **not** a hard
  `Violation`. Rooms, instructors, capacity, lab, window, blackout, and H_self stay hard.
- **Test:** `test_course_cohort.py` (same-course sections may overlap; different-course
  sections incur a penalty but are not forbidden).

### 2.2 Split long blocks across multiple days — ✅ Done

- **Outcome:** `blocks_from_tpl` splits any block longer than `cfg.max_block_len` (default 4h)
  into near-equal sub-blocks (e.g. 10h → 4+3+3). Block ids: `#T`/`#L` for single blocks,
  `#T1..#Tk`/`#L1..#Lk` for split ones. Kind detection: `"#L" in block_id`. Enables
  Architecture studios (previously excluded). A "spread across non-adjacent days" soft term
  (`w_nonadjacent`) is implemented but **disabled by default (= 0)**; calibrate before enabling.
- **Test:** `test_split_blocks.py`, `test_nonadjacent.py`.

### 2.3 Team-taught sections — ✅ Done

- **Outcome:** `Section.instructor_ids: list[str]` (comma-joined IDs split). Every ID enters
  instructor no-overlap (H3) and day soft terms. Seminar blackout applies if any co-instructor
  is full-time. `schedule.json` shows joined display names.
- **Test:** `test_team_taught.py`.

### 2.4 Oversize sections → large halls — ✅ Done (option a: add large halls)

- **Outcome:** `cfg.extra_rooms = ((500,2),(250,3),(150,4))` injects synthetic `AMFI-<cap>-<n>`
  halls into the room master. Capacity stays hard. The real amphitheater inventory is not in
  the data; capacities are assumed and configurable (documented in the data-quality report).
  Enables Basic Sciences service courses (TEDU 101, 497 students).
- **Test:** `test_clean_halls.py`.

### 2.5 Full-period solve and decomposition — ✅ Done (measured; full solve deferred)

- **Outcome:** `decompose.py` (`--decompose`) solves faculties in sequence, reserving
  `(room, instructor, day, hour)` across groups. Measured (mrpb=8, 45s/faculty):
  period 001 placed 483/988 blocks (~49%), period 002 placed 446, both at **0 resource
  conflicts**. Evening ratio ~7%, 63/53 rooms vs existing 248/218. Single global solve
  is intractable (UNKNOWN at 300s, ~123k–356k variables) — see deferred work below.
- **Test:** `test_decompose.py`.

### 2.6 Soft objective calibration — ✅ Done

- **Outcome:** `w_evening` tuned to 10; evening ratio ~0.07 achieved (matching the ~7%
  benchmark). New `room_fill` metric added to `mode_b_<period>.json`. `w_cohort_conflict`
  set to 50 (high, student conflict is "almost hard"). `w_nonadjacent` remains 0 (disabled)
  pending further need. Weights for remaining staged softs (`w_day_balance`, `w_daily_load`,
  etc.) stay at 0 — YAGNI until a benchmark gap warrants them.

### 2.7 Course-level day-ordering (S-Order, soft) — ✅ Done (cheap form)

- **Outcome:** Per-candidate term `w_order * (4 − level) * (start − horizon_start)` for
  `level ∈ {2,3,4}`; pushes lower-level courses earlier in the day. `w_order` in `config.py`.
  The faithful inversion-count form is deferred (see deferred work below).
- **Test:** `test_s_order.py`.

### 2.8 Engineering lab days (S-EngLab, soft) — ✅ Done

- **Outcome:** Lab-block candidates of an Engineering section (`section.faculty` contains
  `cfg.eng_faculty_match = "Engineering"`) are penalized `w_englab` when `day ∉
  cfg.eng_lab_days` (default `("Th","Fr")`). Soft only, no pruning. Covers all 7 Engineering
  departments.
- **Test:** `test_s_englab.py`.

### Deferred / future work (not in Phase 2 scope)

1. **Complete full-period conflict-free timetable.** The single global CP-SAT solve is
   intractable at full scale (~793 sections, period 001). Paths forward:
   - Better decomposition: iterative / overlapping partitions, column generation.
   - Commercial MIP solver (e.g. Gurobi) which scales better than CP-SAT on dense
     assignment LPs.
   - Finer cohort/curriculum data (elective flags, per-student course sets) to make the
     cohort constraint tighter and less combinatorially explosive.
2. **Finer cohort modeling.** The `(Dept_Code, Year_Level)` proxy remains an
   over-approximation of student conflict. True sub-groups (mandatory vs elective, actual
   course enrollment) would allow a harder cohort constraint without infeasibility.
3. **S-Order faithful form.** The current cheap per-candidate term is an approximation;
   the cohort-internal inversion-count form (Boolean aux per pair) would be more precise
   but is heavier — revisit only if the cheap form proves too weak at scale.
4. **Mode C warm start.** Hint the solver from the existing program's schedule — not started.
5. **`w_nonadjacent` calibration.** The non-adjacent-split soft term is implemented but
   disabled (`= 0`); enable once full-period solving stabilizes.

---

## Phase 3 — Web UI + interactive deployment (Solve-on-demand)

A web UI so 1-2 known users can **trigger** solves from outside the institution network,
instead of an operator running the CLI, and view the result. Decisions made 2026-06-19.
(Supersedes the earlier "read-only React UI" idea — the interactive Streamlit UI covers it.)

**Input model (user-provided, replaces the fixed `data/` CSVs for UI runs):**

- **Course list = the primary input.** One row per **section**, columns:
  `Course Code | Course Name | Section No | T | P | L | Lecturer Name | Lecturer Email | ~Students`.
- **Upload (CSV + Excel `.xlsx`) is primary; in-UI row entry is secondary** (for small
  edits/additions). Excel support adds an `openpyxl` dependency.
- **Cohort is derived from the course code** (dept = letter prefix, year level = first digit
  of the number, e.g. `CMPE 113` → CMPE, year 1). Service/elective courses get the wrong
  cohort — the known, accepted flaw (same as TODO 2.1). No enrollment file in the UI flow.
- **Instructor identity = email** (display name kept separately, for show only). Solves the
  name-collision problem the current `Staff_ID` keying guards against. Team-taught = comma-
  separated emails; blank email → section excluded from instructor no-overlap (warn).
- **Classrooms are NOT re-uploaded** — managed in a dedicated "Classrooms" screen
  (add/edit/delete room + capacity + an explicit **is-lab** flag; today lab-room status is
  derived from the room name in `clean.py`, so the UI must set it explicitly).
- **Period** (001/002) is a selection.
- Upload validation reuses the `data_quality_*` checks (missing columns, T+P+L=0, oversize).

**UI / deployment:**

- **UI tech: Streamlit** (pure Python, no separate frontend build). Chosen over React/shadcn
  for a 1-2-user internal tool — fastest path to a working "Solve" UI.
- **No FastAPI / no job system.** Because Streamlit is Python and runs in the **same
  container** as the solver, it calls `run_pipeline()` **directly** — the earlier FastAPI
  `/solve` + `BackgroundTasks` layer is unnecessary at this scale.
- **Refactor first:** extract a callable `run_pipeline(period, scope, mode, time_limit)` from
  `__main__.py` so the CLI and Streamlit share one code path (no duplication).
- **Solve UX: blocking spinner.** Solve button → `st.spinner` while `run_pipeline()` runs →
  show results. Fine for 1-2 users / one solve at a time (no async job tracking needed).
- **Input form** mirrors the CLI flags: `period` (001/002), `scope` (all / faculty= / dept=),
  `mode` (A / B / A,B), `time-limit` (slider).
- **Result views, built in order:**
  - **A** (v0): flat assignments table + search/filter + CSV/JSON download + an
    "unschedulable sections" section (from `data_quality_*`).
  - **B:** weekly Mon-Fri × hour grid + room / instructor / cohort / department filters.
  - **C:** conflict highlighting + Mode-B comparison summary.
  - Consumes the fixed `schedule_<period>.json` / `export.py` contract.
- **Target: Google Cloud Run** — single Docker image (Streamlit + OR-Tools CP-SAT + `data/`),
  in the user's own GCP project, **EU/TR region**, locked to 1-2 people via IAM/auth,
  **4-8 vCPU** (~800-section problem is small; 64-96 vCPU is overkill). Scale-to-zero → no
  idle cost, fits seasonal use. Browser talks directly to Cloud Run (no Vercel — would only
  add a second platform + CORS).
- **PII / KVKK:** gate is the institution's policy — confirmed OK on the user's own,
  region-controlled cloud. Fallback if data may not leave the building: on-prem/intranet VM
  with VPN/reverse-proxy. Enable disk encryption and access logging regardless.
- **Rejected alternatives:** Vercel/GitHub Pages (frontend-only, can't run the solver);
  Gurobi WLS (licensing only, different paid solver); Google OR API / MathOpt Service
  (Alpha/Beta, quota-limited, sends PII to a shared Google service, and does **not** support
  CP-SAT — only GLOP/PDLP/SCIP, would require reformulating the model as a MIP).

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
