# UCTP Phase 2 — Model Fidelity & Full-Scale Solving — Design Spec

**Date:** 2026-06-19
**Status:** Approved (design); pending spec review
**Builds on:** [2026-06-19-course-timetabling-cpsat-design.md](2026-06-19-course-timetabling-cpsat-design.md) (Phase 1)
**Backlog source:** [TODO.md](../../../TODO.md) items 2.1–2.6 + one added soft rule (cohort daily compactness)

---

## 1. Goal & definition of done

Phase 1 produced a working end-to-end pipeline proven on department/faculty *slices*. Phase 2
removes the four modeling limitations that block full-scale solving and then solves the **entire
period** (`001` ~793 sections, `002` ~801 sections) with zero hard-constraint violations under a
time cap, with a calibrated light soft-objective.

**Definition of done:**
- 2.1–2.4 implemented with passing unit tests and the independent validator at **0 hard
  violations**.
- The new **cohort daily-compactness** soft rule implemented and demonstrably reducing student
  idle gaps.
- `--scope all` solves both periods (directly or via documented decomposition); time/quality
  measured.
- Soft weights calibrated against the Phase-1 benchmarks (room fill ~0.53, evening ratio ~7%).
- Results reported for **Computer Engineering** and **Architecture** faculties and the **full
  001/002 periods**, each with the Mode-B comparison. README + TODO.md updated.

**Non-goals (unchanged from Phase 1):** graduate scheduling (toggle only), the web UI (Phase 3),
Mode C warm-start, `rules.pdf` Article 1 (ignored).

---

## 2. Settled decisions (carried in + decided at brainstorm)

- **Roster, period split, cohort key `(Dept_Code, Year_Level)`, lab/window/blackout rules,
  Mode A+B** — all unchanged from Phase 1.
- **2.4 oversize strategy = add large lecture halls** (chosen). The 16 (001) / 8 (002) oversize
  sections are all *real single sections* of Basic-Sciences service courses (TUR/HIST/TEDU/ENGR);
  the university already teaches them in amphitheaters that `classrooms.csv` (capped at 100) omits.
  Capacity stays a **hard** constraint; we add a small, configurable, documented set of synthetic
  halls. (Sub-grouping and soft-overflow were rejected — see §5.4.)
- **Added soft rule:** *as much as possible, 2XX/3XX/4XX (year-2/3/4) courses are scheduled
  "in sequence"* → interpreted as **cohort daily compactness**: a cohort's classes on a given day
  should be consecutive, minimizing student idle gaps. Applied to cohorts with `year_level ∈
  {2,3,4}`. Soft, weighted, tunable (§5.5).
- **Article 1 still ignored** → free block splitting is allowed (enables 2.2).
- **Cohort conflict is SOFT, not hard (revised after implementation).** A hard course-level cohort
  constraint proved still infeasible at scale (Computer Engineering: INFEASIBLE hard / OPTIMAL with
  cohort removed). The `(Dept_Code, Year_Level)` proxy over-counts conflict because students split
  across electives (4XX are mostly electives, 2–3 per student per term). Cohort overlap is therefore
  a weighted penalty the solver minimizes, not a prohibition — see §5.1-R. Rooms/instructors/window
  stay hard, so every period yields a valid timetable.
- **Two previously-approved soft rules are folded in** from
  [2026-06-19-soft-ordering-and-eng-labs-design.md](2026-06-19-soft-ordering-and-eng-labs-design.md):
  **S-Order** (within a cohort, course level rises with start-hour) and **S-EngLab**
  (Engineering lab blocks prefer Thu/Fri). See §5.7.

---

## 3. Current encoding (what Phase 2 changes)

From `src/timetabling/model_cpsat.py` (Phase 1):

- Decision vars `x[block, room, day, start]` over pruned candidates.
- **H1** placement (`AddExactlyOne` per block).
- **H2/H3/H4** room/instructor/cohort no-overlap as `sum(occupancy) ≤ 1` per resource-slot, where
  `cohort_occ` is keyed by `(cohort_key, day, hour)` — i.e. **any two same-cohort blocks conflict**.
- Each `Section` has a **single** `instructor_id`; `blocks_from_tpl` makes one `T+P` theory block
  and one `L` lab block, **never split**.
- `split_roomable` drops sections whose block has no candidate (oversize / longer than the day
  window) and reports them.
- `validate.py` re-derives H2/H3/H4 independently; its cohort check is also section-level.

Phase 2 edits H4, block generation, the instructor model, the room master, and adds two soft terms.

---

## 4. Cross-cutting change: explicit section-internal non-overlap (H_self)

**Why now:** after 2.1 makes the cohort constraint *course-level*, two blocks of the **same
section** share the same course code, so the cohort constraint no longer separates them. Phase 1
relied on H3 (same instructor) for that separation — fragile once (a) 2.2 splits a section into
several blocks and (b) team-taught/empty-instructor edge cases exist.

**Decision:** add an explicit per-section non-overlap constraint
`section_occ[(section_id, day, hour)] ≤ 1` (only emitted for sections with ≥2 blocks). Cheap, and
it makes "a section never overlaps itself" independent of the instructor/cohort encoding. The
independent validator gets the matching `self`/`section` check.

---

## 5. Feature designs

### 5.1 Course-level cohort constraint (TODO 2.1)

**Rule:** at most **one distinct course code** active per `(cohort, day, hour)`. Sections of the
**same** course code may run in parallel (different student groups); sections of **different**
courses in the same cohort may not overlap.

**Encoding:**
- Group candidate occupancy by `(cohort, course, day, hour)`.
- For each such group with vars `V`, create `busy ∈ {0,1}` linearizing OR: `busy ≥ v ∀v∈V` and
  `busy ≤ Σ V`.
- For each `(cohort, day, hour)` to which **≥2 distinct courses** can contribute, add
  `Σ_course busy ≤ 1`. (Where only one course can occupy a slot, no constraint is needed — multiple
  parallel sections of that one course are allowed; H2/H3/H_self still prevent room/instructor/self
  clashes.)

**Validator:** flag `(cohort, day, hour)` where the set of **distinct course codes** present is >1.

**Expected effect:** service/elective faculties and multi-section courses (CMPE 113 _01–_04, ENG-1)
become feasible.

#### 5.1-R Revision (post-implementation): the cohort constraint is **SOFT**, not hard

Implementing 5.1 as a **hard** constraint and then solving real faculties proved it is still
infeasible at scale. Evidence (period 001, Computer Engineering, 61 sections, soft objective off):

| Configuration | Result |
|---|---|
| course-level cohort **hard** (as above) | **INFEASIBLE** — proven in ~8 s |
| same instance, cohort coupling **removed** (each section its own cohort) | **OPTIMAL** in ~2.5 s |

So rooms, instructors, the day window, blackouts and halls are all satisfiable; the **sole**
binding constraint is the cohort proxy. No single cohort overflows the ~44 h weekly window (CMPE-4
is the worst at 8 courses / 39 h), so the infeasibility is a *combinatorial coupling*: the
`(Dept_Code, Year_Level)` proxy treats a whole year-group as one monolithic student body that can
never have two **different** courses at once. In reality students split across **electives** — and
**4XX courses are mostly electives, of which a student takes only 2–3 per term** — so two same-cohort
courses genuinely do run in parallel for disjoint student subsets. The data carries no
elective/mandatory flag or per-student course set to recover the true sub-groups.

**Decision (user-approved):** make the cohort constraint **soft**. Replace the hard
`Σ_course busy ≤ 1` with a penalty `cfg.w_cohort_conflict * Σ_{(cohort,day,hour)} max(0, (#distinct
courses) − 1)`. Rooms / instructors / capacity / lab / window / blackout / H_self stay **hard**, so
every period now yields a physically valid timetable; the solver **minimizes** student
course-conflicts rather than being forbidden from producing any. `w_cohort_conflict` is weighted
high (student conflict is "almost hard") and calibrated in 2.6.

**Validator / reporting:** cohort overlap is **no longer a hard `Violation`**. `validate.py` keeps
only the genuinely-hard checks (room, instructor, capacity, lab, window, blackout, self, placement);
the cohort course-conflict count is reported as a **soft metric** (`cohort_conflicts`, surfaced in
`mode_b_<period>.json` and `unmet_soft`). "0 hard violations" therefore remains the feasibility bar.

### 5.2 Split long blocks across days (TODO 2.2)

**Rule:** no single block exceeds `cfg.max_block_len` (**default 4** h; Article 1 ignored so 3–4h
blocks are fine).

**`blocks_from_tpl(section_id, T, P, L, Cr, max_block_len)`:**
- theory load = `T+P`, lab load = `L` (default 3h theory if all zero — unchanged).
- A load `n > max_block_len` is split into `ceil(n/max_block_len)` near-equal parts
  (e.g. 10 → 4+3+3; 8 → 4+4).
- **Block ids:** a single block keeps `#T` / `#L` (preserves Phase-1 tests); split blocks become
  `#T1..#Tk` / `#L1..#Lk`. Kind detection becomes `"#L" in block_id`; `section_id =
  block_id.split("#")[0]` still holds.
- Sub-blocks share section/instructor/cohort/course → separated by **H_self** (+ H3). Spreading
  sub-blocks across **non-adjacent days** is *rewarded* by soft #2 (§5.6), not forced (the day
  window already forces spreading when the total load can't fit one day).

**Test:** a 10-hour section yields ≥2 blocks, all placed; previously-excluded studios solve.

### 5.3 Team-taught sections (TODO 2.3)

Grades `Staff ID` may hold comma-joined ids (`"00003893,00002022"`), today collapsed into one
unmatched synthetic instructor.

- **`textnorm.normalize_staff_ids(s) -> list[str]`** splits on comma and normalizes each part
  (existing `(S)`/whitespace handling reused).
- **`model.Section.instructor_id: str` → `instructor_ids: list[str]`.**
- **Model:** every id contributes to `instr_occ` and `instr_day`; the section is unschedulable into
  the Thursday seminar blackout if **any** of its instructors is full-time (`is_staff`) — blackout
  set = `friday ∪ (seminar if any is_staff)`.
- **Validator:** instructor conflict checked for each id in `instructor_ids`.
- **Export / schedule.json:** `instructor_name` = joined display names (`" & "`); `instructor_id` =
  comma-joined ids. The per-assignment field set stays stable (UI contract preserved).

### 5.4 Oversize sections → large halls (TODO 2.4, chosen)

- **`cfg.extra_rooms`**: list of `(cap, count)` halls, **default `((500,2),(250,3),(150,4))`**
  (covers observed demand: 001 max 497; 002 max 434). Generated as physical, non-lab rooms named
  `AMFI-<cap>-<i>`.
- **`build_rooms`** appends these after loading `classrooms.csv`.
- Best-fit room selection already picks the smallest fitting room, so a 148-student section takes a
  150-cap hall and a 497 takes a 500-cap hall. **Capacity remains hard;** `split_roomable` no longer
  excludes these sections.
- **Reported:** the synthetic halls and the explicit assumption ("we lack the real amphitheater
  inventory; capacities are assumed and configurable") are written to the data-quality report.

**Rejected alternatives:** (b) sub-grouping inflates section counts, can't share the single real
instructor (H3), and misrepresents already-existing sections; (c) soft-overflow seats students
where they physically don't fit and only flags the problem.

### 5.5 Cohort daily compactness (added soft rule)

For each `(cohort, day)` with `year_level ∈ cfg.compact_cohort_years` (**default `(2,3,4)`**):
- `cohort_hour[(cohort,day,h)]` = OR over all of the cohort's candidate vars covering hour `h`.
- `first` = earliest active hour, `last` = latest active hour + 1 (via `AddMinEquality` /
  `AddMaxEquality` with the standard "ignore inactive hours" trick), `load` = `Σ cohort_hour`.
- `gap = (last − first) − load ≥ 0`; minimize `Σ gap` weighted by **`cfg.w_cohort_gap`**.
- Built only for cohorts that can have ≥2 blocks on a day (otherwise `gap≡0`).

This is the priority soft term per the user's new rule; weight calibrated in 5.6 and can be set to
0 to disable.

### 5.6 Soft-objective calibration (TODO 2.6)

Keep the Phase-1 terms (evening use, room count, instructor-day compactness, part-time clustering)
and add, **incrementally measuring each**: #2 non-adjacent days for a section's split blocks, #4
department day-balance, #5 cohort daily-load cap, #7 instructor free-days, #8 part-time clustering
(already partial), #14 practicum buffer, plus the §5.5 cohort-gap term. New weights live in
`Config` and start at conservative values (several at 0 until calibrated). Targets: room fill
~0.53, evening ratio ~7%; do not chase optimality under the time cap.

### 5.7 Imported soft terms: S-Order & S-EngLab (folded-in spec)

From [2026-06-19-soft-ordering-and-eng-labs-design.md](2026-06-19-soft-ordering-and-eng-labs-design.md);
both are best-effort, per-candidate linear terms added in the existing candidate loop (no aux
vars, no pruning, can never cause infeasibility).

- **S-Order** — within a cohort, course-code **level rises with start-hour**. For every candidate
  of a block whose `section.level ∈ {2,3,4}`, add `w_order * (4 − level) * (start − horizon_start)`.
  Low level → large coefficient → pushed early; high level → ~0 → drifts to the later slots the
  low levels vacate. Per-placement, so implicitly cohort-local. `w_order` light (e.g. 1).
- **S-EngLab** — Engineering **lab blocks prefer Thu/Fri**. For every **lab-block** candidate whose
  `day ∉ cfg.eng_lab_days`, add `w_englab`. "Engineering" = `section.faculty` contains
  `cfg.eng_faculty_match` (**confirmed `"Engineering"`**, matches all 7 engineering departments:
  Computer, Software, Civil, Industrial, Mechanical, Electric&Electronics, Faculty of Engineering).

**Relationship to §5.5.** S-Order (orders a cohort's day by level) and §5.5 cohort-gap (packs a
cohort's day with no holes) are **complementary** and jointly satisfiable (e.g. 2XX 09–11, 4XX
11–13 is both ordered and gap-free); they target the same year-2/3/4 population by different
attributes (course level vs cohort year). Weights are calibrated together in 5.6.

---

## 6. Full-period solve & decomposition (TODO 2.5)

1. After 5.1–5.5, run `--scope all` for `001` and `002`; record status, wall time, violations,
   room usage, evening ratio, total gap.
2. If a period does not solve within the cap, fall back to **faculty-based decomposition** sharing
   the global room pool via a reservation scheme (Phase-1 spec §11): solve faculties in sequence,
   freezing already-used `(room, day, hour)` slots for later faculties. The under-counting risk of
   any partition is **stated, not hidden**.
3. A `--decompose` CLI flag (off by default) selects the decomposition driver.

---

## 7. Config changes (all in `config.py`)

| Param | Default | Purpose |
|---|---|---|
| `max_block_len` | `4` | 5.2 block splitting |
| `extra_rooms` | `((500,2),(250,3),(150,4))` | 5.4 large halls |
| `compact_cohort_years` | `(2,3,4)` | 5.5 which cohorts get gap penalty |
| `w_cohort_gap` | `3` (tune) | 5.5 weight |
| `w_nonadjacent` | `0` (tune) | 5.6 / #2 non-adjacent split days (shipped) |
| `w_day_balance`, `w_daily_load`, `w_instr_freeday`, `w_practicum_buffer` | `0` (tune) | 5.6 staged softs — **added during calibration only if a benchmark gap warrants** (YAGNI) |
| `w_order` | `1` (tune) | 5.7 S-Order level→start-hour |
| `w_englab` | `1` (tune) | 5.7 S-EngLab Thu/Fri lab pref. |
| `eng_lab_days` | `("Th","Fr")` | 5.7 preferred lab days |
| `eng_faculty_match` | `"Engineering"` | 5.7 Engineering faculty substring |

---

## 8. Files touched

`config.py` (params) · `model.py` (`instructor_ids`) · `textnorm.py` (`normalize_staff_ids`) ·
`join.py` (keep comma-joined normalized ids) · `derive.py` (split blocks, multi-instructor,
pass `max_block_len`) · `clean.py` (append `extra_rooms`) · `model_cpsat.py` (course-level cohort,
H_self, multi-instructor occupancy/blackout, cohort-gap + staged softs) · `validate.py`
(course-level cohort, multi-instructor, self-overlap) · `export.py` (joined instructor names) ·
`report.py` (synthetic-hall note, new soft metrics) · `__main__.py` (decomposition driver/flag) ·
`tests/` (update + new). The pipeline order and the `schedule.json` contract are unchanged.

---

## 9. Verification plan

Independent validator must report **0 hard violations** on every solved scope. New/updated unit
tests:
- **2.1:** two sections of the **same** course (same cohort) may overlap; two sections of
  **different** courses (same cohort) may **not**.
- **H_self:** a section's two blocks never share a `(day, hour)`.
- **2.2:** a 10-hour section produces ≥2 blocks, each ≤ `max_block_len`, all placed.
- **2.3:** a comma-joined `Staff ID` yields ≥2 `instructor_ids`, all entering instructor
  no-overlap; the seminar blackout triggers if any co-instructor is full-time.
- **2.4:** a 148-student section receives a fitting hall; oversize sections leave the
  unschedulable list.
- **5.5:** on a small instance with high `w_cohort_gap`, the chosen schedule has no interior gap
  for a year-2/3/4 cohort.
- **5.7 S-Order:** with high `w_order`, a cohort's level-2 block starts no later than its level-4
  block; level-1/5+ blocks add no order penalty.
- **5.7 S-EngLab:** with high `w_englab`, an Engineering lab block lands on Thu/Fr when feasible;
  a non-Engineering lab block is unaffected.

Evidence at completion: validator output (0 violations), Mode-B tables, and sample `schedule.json`
for CompEng, Architecture, and full 001/002.

---

## 10. Assumptions & limitations

- **Large-hall inventory is assumed** (capacities/counts configurable), since the real
  amphitheater list is not in the data; documented in the report.
- **Cohort proxy `(Dept_Code, Year_Level)`** is still an over-approximation of student conflict
  (now relaxed to course level, but cross-dept electives remain uncaptured).
- **Decomposition** (if needed) under-counts room contention versus a single global solve; stated
  explicitly when used.
- Hours rule (`T+P` theory + `L` lab) and the ignored Article 1 are unchanged from Phase 1.
