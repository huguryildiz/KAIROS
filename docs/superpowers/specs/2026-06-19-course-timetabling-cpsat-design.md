# University Course Timetabling (UCTP) — CP-SAT Design Spec

**Date:** 2026-06-19
**Status:** Approved (design); pending spec review
**Source prompts:** `docs/prompts/START.md`, `docs/prompts/university_course_timetabling_prompt.md`
**Authoritative rules:** `data/rules.pdf` (14 articles; Article 1 explicitly IGNORED by user decision)

---

## 1. Goal & definition of done

Produce a **conflict-free weekly timetable** by assigning every undergraduate section a **(day, start-hour, room)** for each of its blocks, for two independently-scheduled periods (`001` Fall, `002` Spring).

Decision variables are **time and room only**. Section existence, instructor↔course assignment, section size, and T/P/L hours are **fixed inputs (parameters)**.

**Priorities:** (1) feasibility — zero hard-constraint violations; (2) soft-constraint quality.

**Definition of done for this build (agreed scope):**
- Complete end-to-end pipeline: load → clean → join → derive → parse → CP-SAT model → solve → validate → export.
- **Proven on a tractable slice** (one faculty, solved against the full room pool), with a **parameterized, documented path to the full ~800-section period**.
- **OR-Tools installed and run live** in this environment; report real feasibility + Mode-B benchmark metrics; emit a sample `schedule.json`.
- **Feasibility-first, light objective:** include a small weighted soft-objective under a solve-time cap; do not chase optimality.

---

## 2. Settled decisions (carried from the prompt; not re-litigated)

- **Roster = Grades files** (authoritative: which course, which instructor, which period). Undergraduate only (code level 1–4). Graduate 5XX/6XX appear only in Plan → **out of scope by default** (optional toggle).
- **Period split mandatory:** `001` and `002` are two independent timetables.
- **Cohort = `(Dept_Code, Year_Level)`** — a curriculum-based (CB-CTT) proxy for student conflict; its limitation is stated in §13.
- **Lab requirement** ⟺ Grades `L > 0`; lab rooms identified by name suffix; mapping written to an explicit table.
- **Capacity source:** `enrollment_by_section.Students` (fallback Plan `SECT_CAP`).
- **Article 1 of `rules.pdf` (2+1 / ≤3 consecutive hours) is IGNORED** — not enforced, not reported (Mode B does not flag it). Blocks are decomposed freely from T/P/L; 3+ hour single blocks allowed.
- **Default modes: Mode A (from scratch) + Mode B (benchmark)**. Mode C (warm-start repair) is optional/out of scope for this build.
- **Solver: Google OR-Tools CP-SAT.**

---

## 3. Data sources & join map

All CSVs are quote-aware (fields may contain commas inside quotes) — **never `split(",")`**; use `pandas.read_csv` / `csv` module.

| File | Rows | Role |
|---|---|---|
| `2025-01-Grades.csv` / `2025-02-Grades.csv` | 841 / 826 | Authoritative roster + T/P/L/Cr + Staff ID + # students |
| `2025-01-Plan.csv` / `2025-02-Plan.csv` | 1062 / 1056 | Existing room+time program + caps (superset; benchmark/warm-start) |
| `enrollment_by_section.csv` | 1667 | Cohort key `(Dept_Code, Year_Level)` + Students |
| `enrollment_summary.csv` | 132 | Dept×Year aggregates (cross-check only) |
| `classrooms.csv` | 101 | Master room list + ROOM_CAP |
| `lecturers.csv` | 340 | Instructor master + `Is_Staff` (full/part-time) + home dept |

**Join (key = `Section` + `Period`, e.g. `ADA 403_01` + `001`):**
```
Grades  (roster: section + course + lecturer + period + T/P/L/Cr + Staff ID + #students)
  ⨝ enrollment_by_section ON Section+Period  → cohort=(Dept_Code, Year_Level), Students
  ⨝ lecturers             ON Staff_ID         → Is_Staff, home dept
  ⨝ Plan (LEFT JOIN)      ON Section+Period   → existing SCHEDULE + ROOM (Mode B), SECT_CAP
  + classrooms (room master)                  → ROOM_CAP, lab-eligibility (from name)
```
Prefer `Staff_ID` join (name matching is dirty: `(S)` suffix, spacing). ~225 Plan-only sections (no Grades match) are **excluded from the roster by default** (toggle to include).

**Scale note:** the headline "~1059 sections/period" is the *Plan* superset. The scheduled roster (Grades, undergrad, minus excluded categories) is **~800/period**.

---

## 4. Normalized data model (7 entities)

- **Sections**(section_id, period, code, course_name, level, dept, cohort_key, instructor_id, students, T, P, L, Cr, category, blocks[])
- **Instructors**(staff_id, name, is_staff, home_dept)
- **Rooms**(room, cap, is_lab, is_physical)
- **TimeSlots**: Mon–Fri × start-hours 09–20, 1-hour granularity, horizon end 21:00 → 60 slots
- **Cohorts**(dept, year → member sections)
- **Constraints** (parameterized — see §8/§9, all in `config.py`)
- **Assignments**(block_id → room, day, start, end) — solver output

---

## 5. Derivations (not in data — we compute them)

1. **Cohort** = `(Dept_Code, Year_Level)` from `enrollment_by_section`.
2. **Course level** = first digit of the 3-digit number in the course code. 1–4 = undergraduate; 5/6 = graduate.
3. **Lab room** = `classrooms.ROOM` whose name carries a lab suffix (`-PC-L`, `-L`, `-PSY-L`, `-PSCG-L`, `-PECE-L`, `-EF-L`). No room-type column exists → derive from name and **write the mapping to an explicit table** in the data-quality report. (~14 lab/PC rooms expected.)
4. **Online room** (`Online`, cap 9999) is a placeholder → separated from the physical room pool (`is_physical=False`).
5. **Blocks & hours rule (Mode A):** each section → a **theory block of `T+P` hours** and, if `L>0`, a **lab block of `L` hours** (lab block restricted to lab rooms). The `T+P+L` vs `T+L` ambiguity is resolved empirically: the data-quality step compares derived hours to observed `SCHEDULE` durations and reports mismatches; the chosen rule is documented. Default = `T+P` theory + `L` lab.
6. **Excluded records:** Grades `Category ∈ {Internship, some Mandatory(YOK)}` → may not consume room+slot; filtered and reported.

---

## 6. Time model & SCHEDULE parsing

- Horizon: **Mon–Fri**, start-hours **09–20**, blocks must end by **21:00** (Sat/Sun not observed; Saturday is an off-by-default toggle per Article 3).
- **SCHEDULE grammar** (used in Mode B / data-quality only; ignored in Mode A):
  - Unit: `"<Day> <start> - <end>"`, integer 24h hours, e.g. `Fr 13 - 16` = Fri 13:00–16:00 (3 blocks).
  - Chained multi-session: units space-joined, e.g. `Th 09 - 12 Th 13 - 16`.
  - Multi-day `X/Y`: `Tu/Fr 09 - 12` = both Tue and Fri 09:00–12:00 → expand to two sessions.
  - **Dirty values (~11 rows):** CSV column-shift leaks instructor names / room codes into SCHEDULE. Values not starting with a valid day token → flagged as parse errors, **not auto-repaired**, reported.

---

## 7. CP-SAT encoding — Option A (Boolean assignment grid)

**Chosen** for 1:1 correspondence with the requested formulation, readable linear conflict/soft terms, and tractability-via-pruning. A small interface around the resource-conflict layer leaves room to swap in `AddNoOverlap` (interval model) for full-scale solving without disturbing the rest of the pipeline.

### Sets
- `P` periods {001, 002} — solved independently.
- `S` sections; `B` blocks (each section → 1 theory block + optional lab block); `B_s` blocks of section `s`.
- `R` rooms; `R_lab ⊆ R`. `I` instructors; `C` cohorts.
- `D` days; start-hours `H = {9..20}`. Slot `(d,t)`.
- Per block `b`: `len_b`, `inst(b)`, `cohort(b)`, `needs_lab(b)`, `size_b = students(s)`.

### Parameters
- `cap_r` room capacity; `size_b` section size.
- **Candidate set** `Cand_b = {(r,d,h)}` generated with all single-block hard rules pre-applied (pruning):
  room feasible (`cap_r ≥ size_b`; lab match if `needs_lab`), start legal (`h + len_b ≤ 18` undergrad window; `h + len_b ≤ 21` horizon), no blackout coverage (Friday 13–14; Thursday 14–16 for full-time instructors).

### Decision variables
- `x[b,r,d,h] ∈ {0,1}` defined only over `Cand_b`. = 1 iff block `b` starts at hour `h`, day `d`, room `r`.

### Hard constraints
- **(H1) Placement:** `Σ_{(r,d,h)∈Cand_b} x[b,r,d,h] = 1` ∀b.
- **(H2) Room no-overlap:** ∀ room `r`, slot `(d,t)`: `Σ_b Σ_{h: h≤t<h+len_b} x[b,r,d,h] ≤ 1`.
- **(H3) Instructor no-overlap:** ∀ instructor `i`, slot `(d,t)`: `Σ_{b:inst=i} Σ_{r,h: h≤t<h+len_b} x[b,r,d,h] ≤ 1`.
- **(H4) Cohort no-overlap:** ∀ cohort `c`, slot `(d,t)`: `Σ_{b:cohort=c} Σ_{r,h: h≤t<h+len_b} x[b,r,d,h] ≤ 1`.
- **(H5–H10) capacity / lab / undergrad-window / Friday blackout / seminar blackout / within-day** are enforced by **candidate pruning** (only legal `(r,d,h)` are generated), keeping the model small.
- **Internal section non-overlap:** implied by H3+H4 (a section's two blocks share instructor and cohort).

> Only H1–H4 are explicit constraints; everything else is pruned at candidate-generation time.

### Soft objective (minimize weighted penalty; light, time-capped)
Implemented subset for this build: **evening-slot use**, **room compactness** (distinct rooms used; benchmark fill 0.53), **instructor day-compactness** (teaching-days per instructor, cluster to ≤2), **part-time-instructor clustering** (`Is_Staff=False` weighted heavier). Hooks left for: dept day-balance, section no-consecutive-days, cohort daily-load, graduate evening preference (if grad toggle on). All weights in `config.py`.

---

## 8. Hard constraints (rule mapping)

instructor / cohort / room no-double-book · room cap ≥ students · `L>0` → lab room · every block placed & contained within one day · **undergrad blocks end ≤ 18:00** (Articles 3 & 5; ENG 101/102 bound to undergrad window) · **Friday 13:00–14:00 prayer blackout** (param) for all sections · **full-time-staff (`Is_Staff=True`) Thursday 14:00–16:00 seminar blackout** (Article 6, param).

## 9. Soft constraints (Article mapping)

Article 2 (no consecutive days, soft) · Article 4 (grad evening, soft, if toggled) · Article 7 (≤2 free days / instructor compactness, soft) · Article 14 (buffer after practicum, soft) · room compactness · evening-use minimization · part-time clustering · dept balance. **Article 1 omitted** by user decision.

All blackout hours, time windows, Saturday toggle, grad toggle, and objective weights are **parameters in `config.py`**.

---

## 10. Modes

- **Mode A (from scratch, default):** ignore existing `SCHEDULE`; build candidates from structure only; solve.
- **Mode B (benchmark, default):** parse existing program as ground truth; report all its conflicts (by type) and compare to Mode A output: conflict counts, room usage, evening ratio. Article 1 violations are **not** reported.
- **Mode C (warm-start repair):** out of scope for this build (interface left open).

---

## 11. Scale strategy & subset proof

- **Period split** is the first decomposition (001, 002 independent).
- Rooms are the **global coupling** → clean per-department decomposition is not conflict-free.
- **Subset proof = one faculty** (e.g. Faculty of Econ. & Admin. Sciences / `ADA` cluster) solved against the **full room pool** — honest and feasibility-valid.
- **Full-scale path (`--scope all`):** attempt whole period under the time cap (pruned ~800 sections is often tractable for CP-SAT); fallback = faculty-partition with a shared-room reservation note. Any partitioning limitation is **stated, not hidden**.

---

## 12. Architecture (modules)

```
src/timetabling/
  io_csv.py         quote-aware load of all 8 CSVs
  clean.py          (S)-suffix normalize, room outlier, dirty-SCHEDULE flagging
  join.py           Grades ⨝ enrollment ⨝ lecturers ⨝ Plan(LEFT) + classrooms
  derive.py         cohort, level, lab-room map, blocks from T/P/L (+ hours reconciliation)
  schedule_parse.py SCHEDULE grammar (units, chains, X/Y), dirty → flag
  model_cpsat.py    candidate generation + pruning + CP-SAT build (Option A)
  solve.py          solver config, time cap, period/slice decomposition driver
  validate.py       independent re-check of ALL hard constraints on the solution
  report.py         data-quality report, conflict report, Mode-B benchmark
  export.py         schedule.json (UI schema) + CSV timetables
  config.py         all parameters (blackouts, windows, toggles, weights, time limits)
  model.py          dataclasses: Section, Instructor, Room, TimeSlot, Cohort, Block, Assignment
cli: python -m timetabling --period 001 --scope faculty=ECON [--mode A,B] ...
tests/   unit tests per module (parser, pruning, validator especially)
out/     generated reports + schedule.json + CSVs
```
`validate.py` re-derives conflicts **independently of the model** so a solver/encoding bug cannot silently pass.

---

## 13. Outputs

1. **Data-quality report** — parse issues, 251 empty ROOMs, ~11 dirty SCHEDULEs, join gaps (~225 Plan-only), lab-room mapping table, hours-rule reconciliation, `enrollment_summary` cross-check.
2. **Mathematical formulation doc** — sets, params, decision vars, hard/soft, objective (matches code; §7).
3. **`schedule.json`** — UI-consumable; per block: `section_id, course_code, course_name, block_kind, instructor_id, instructor_name, cohort, dept, students, day, start, end, room, room_cap, is_lab_room, flags[]`; plus `period`, `meta`, `unmet_soft[]`, `conflicts[]`.
4. **Conflict report** by type (instructor / cohort / room / capacity / lab-mismatch / multi-session-internal / missing-dirty-data) + **Mode-B benchmark** table (generated vs. existing: conflicts, room usage, evening ratio).

---

## 14. Verification plan (feasibility-first)

`validate.py` runs on every solve and must report **zero hard-constraint violations** on the slice. Evidence shown at completion: validator output (0 violations), Mode-B comparison table, and a sample of `schedule.json`. Unit tests cover the SCHEDULE parser (units / chains / `X/Y` / dirty), candidate pruning (window, blackout, capacity, lab), and the independent validator.

---

## 15. Assumptions, limitations, out of scope

- **Cohort proxy:** `(Dept_Code, Year_Level)` overstates conflict (treats all same-dept/year students as one group) and misses cross-dept electives. Its effect is discussed in the report; not corrected in this build.
- **Hours rule** (`T+P` theory + `L` lab) is a Mode-A modeling choice validated against data, not ground truth.
- **Subset solve** uses the full room pool for one faculty → may under-count room contention vs. a full solve; stated explicitly.
- **Out of scope:** Mode C warm-start; graduate scheduling (toggle only); the web UI (later step — this build only emits its JSON contract); Articles 8, 11, 12, 13 (governance/exams); Article 1 (ignored).

## 16. Dependencies & environment

- Python 3.9 (Anaconda); `pandas` present; **`ortools` to be installed** (`requirements.txt`).
- Repo is **not yet a git repo** → `git init` first; commits go to `main` (no PRs, per user global rule).

## 17. Open parameters to confirm at runtime

- Friday prayer blackout default `Fri 13:00–14:00` (002 data supports; 001 weaker — kept as a per-period parameter).
- Seminar blackout default `Thu 14:00–16:00` (2019 reference; 2025 value assumed, parameterized).
- Soft-objective weights: start conservative, tune lightly against benchmarks (room fill 0.53, evening ratio ~7%).
