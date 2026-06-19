# Design — Two new soft constraints: course-level day-ordering & Engineering lab days

**Date:** 2026-06-19
**Status:** Approved — implementation folded into **Phase 2**
([2026-06-19-uctp-phase2-design.md](2026-06-19-uctp-phase2-design.md) §5.6)
**Relates to:** [course-timetabling-cpsat-design.md](2026-06-19-course-timetabling-cpsat-design.md) §8–9

Two new **soft** preferences are added to the CP-SAT light objective. Both are
"mümkün mertebe" (best-effort): they add weighted penalty terms, never prune candidates,
and so can never make a feasible instance infeasible. Weights live in `config.py`.

---

## S-Order — course-code level rises with start-hour, within a cohort

**Intent.** Within the same **cohort / department** (`cohort_key`, e.g. `ADA-4`), lower-coded
courses (2XXX) should land in **earlier hours of the day**, higher-coded courses (4XXX) in
**later hours**. The axis is **start hour of day only** — the day index (Mon→Fri) is irrelevant.

- **Level** = `Section.level` (first digit of the course code, already derived by
  `derive.course_level`). Only 2/3/4 participate; 1XXX and 5XXX+ are neutral (skipped).
- **Encoding (chosen — cheap, linear):** for each legal placement candidate of a block whose
  section level ∈ {2,3,4}, add penalty
  `w_order * (MAXLVL − level) * (start_hour − horizon_start)`
  where `MAXLVL = 4`. Low level → large coefficient → pushed to small start hours (early);
  high level → coefficient → 0 → free, so it naturally drifts to the later slots the low
  levels vacate. No auxiliary variables; one extra linear term per candidate.
- **Scope.** The penalty is per-placement, so it is implicitly cohort-local: a 2XXX in one
  department is never compared against a 4XXX in another. (No cross-cohort term is added.)
- **Alternative (faithful, deferred):** count cohort-internal *inversions* — for blocks
  i, j in the same cohort with `level_i < level_j`, penalize when `start_i > start_j`.
  O(n²) Boolean aux vars per cohort; rejected for now because full-scale feasibility is
  already tight (see TODO 2.1). Kept as a future upgrade in TODO.

**New config:** `w_order: int` (light, e.g. `1`).

## S-EngLab — Engineering-faculty lab blocks prefer Thursday/Friday

**Intent.** For sections in the **Engineering faculty**, the **lab block** (the `L` block from
T/P/L, restricted to lab rooms) should preferentially be scheduled on **Thursday or Friday**.

- **Faculty match.** `Section.faculty` is the Grades "Dept." column (same namespace as
  `--scope faculty=`). A section is "Engineering" when its faculty contains
  `cfg.eng_faculty_match` (**confirmed = `"Engineering"`**). That substring matches all 7
  engineering departments in the data: Computer, Software, Civil, Industrial, Mechanical,
  `Dept.of Electric&Electronics Engineering`, and `Faculty of Engineering`.
- **Encoding.** For each lab-block placement candidate whose `day ∉ cfg.eng_lab_days`, add
  penalty `w_englab`. Soft only — it nudges, never prunes, so days other than Thu/Fri stay
  available when needed. (The existing Thursday 14–16 full-time seminar blackout is already
  handled by candidate pruning and does not conflict.)

**New config:** `w_englab: int`, `eng_lab_days: tuple = ("Th", "Fr")`,
`eng_faculty_match: str = "Engineering"`.

---

## Objective integration

Both terms join the existing `model.Minimize(sum(obj))` in `model_cpsat.py` alongside
evening-use, room-count, and instructor/part-time day-compactness. They are added during the
same per-candidate loop that already walks each block's candidates, so no new pass is needed.
Keep weights small and tune against benchmarks (TODO 2.6); start with the existing terms
dominant so feasibility and room/evening quality are not regressed.

## Out of scope

- No change to hard constraints or candidate pruning.
- Implementation lands in **Phase 2** (alongside 2.1–2.6 and the cohort daily-compactness
  rule); both soft terms are propagated to the Phase 2 plan, TODO, README, and CLAUDE.md.
