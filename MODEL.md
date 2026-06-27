# KAIROS — UCTP Optimization Model

A formal description of the University Course Timetabling (UCTP) model implemented in
`src/timetabling/`. This is the ground-truth specification: it mirrors `model_cpsat.py`
(the declarative CP-SAT model), `repair.py` (the production solver), `config.py`
(the tunable defaults), and `settings.py` (the per-school overrides exposed in the UI's
School Settings step). When the code and this document disagree, the code wins — update
this file.

The solver decides, for each undergraduate course **block**, a **(room, day, start-hour)**.
Section / instructor / size / T-P-L are fixed inputs; the only decisions are **time** and
**room**.

---

## 0. Scheduling constraints at a glance

A plain-language checklist of every rule the schedule obeys. Sections 3–6 give the formal
CP-SAT encoding; this list is the human-readable summary. Each item notes whether it is a
**hard** rule (can never be violated) or a **soft** preference (penalized, never blocking),
and where it lives (pruning, model relation, or objective).

### What is fixed vs. decided

- **Fixed inputs:** each section's instructor(s), Section Capacity (quota), and T/P/L hours.
- **Decided:** for every block of every section, a `(room, day, start-hour)`.
- A section is split into **blocks**: theory hours `T+P` into sessions of at most `max_theory_session` h
  (default 2; e.g. `T=3 → 2+1`), plus one lab block of `L` hours (split when `L > max_block_len`,
  default 4). Each block is placed once. Both thresholds are tunable via School Settings.

### Hard constraints — enforced by candidate pruning (per block)

A placement that breaks one of these is never even generated, so it cannot occur.

- **Capacity** — a block goes only in a room whose capacity ≥ the section's size. The virtual
  `Online` room is exempt (unlimited).
- **Lab-room pinning** — a lab block is pinned to the section's designated real lab room; it
  can go nowhere else. Labs with no designated lab room use regular rooms.
- **Daytime window** — an undergraduate block must end by the **Day end** hour (default
  **18:00**; tunable 13–21 in School Settings) and start no earlier than the **Day start**
  hour (default **09:00**; tunable 6–12). Graduate blocks (if enabled) end by **21:00**
  (fixed — `horizon_end` is not a settings field) and start no earlier than the configurable
  **Graduate earliest start** hour (default **18:00**; tunable 6–20 in School Settings).
- **Blackout slots** — closed `(day, hour)` slots are **school-specific and configurable**
  (none by default; add them in the School Settings step). Each slot has a scope: *everyone*
  (closed for all sections) or *full-time only* (closed only when a section has a full-time
  staff instructor — e.g. a faculty seminar). Common examples: a Friday 13:00–14:00
  congregational-prayer hour (everyone), or a Thursday 14:00–16:00 staff seminar
  (full-time only).
- **Instructor availability** — a block is never placed in any hour slot an instructor marked
  unavailable; every co-instructor's unavailability applies (a per-instructor blackout, set
  in the School Settings step). The availability grid is hourly.
- **Fixed session** — if a section declares a fixed slot, its **first block** is pinned to
  exactly that `(day, start-hour)` (its remaining blocks schedule freely).
- **Room type** — rooms carry a categorical type (`normal / lab / pc / studio`). When a section
  declares a `Room Type` demand, its blocks go only in rooms of that **exact** category
  (`pc`→`pc`, `studio`→`studio`, `lab`→`lab`); a generic lab demand falls back to any lab-family
  room (`is_lab`). With no demand, any fitting room.

### Hard constraints — enforced as model relations (across blocks)

- **Exactly-one placement** — every block is scheduled exactly once. (In the `--repair`
  solver this is relaxed so a block may stay unplaced, yielding a partial schedule.)
- **Room no-overlap** — at most one block occupies a physical room in any hour. (The `Online`
  virtual room is exempt.)
- **Instructor no-overlap** — no instructor is double-booked in any hour; every co-instructor
  of a team-taught section counts.
- **Section self no-overlap** — two blocks of the same section never overlap in time.
- **Theory different-day** — a section's theory sessions each fall on a **different day**.
  The number of sessions (and thus days) depends on `max_theory_session` (default 2 h,
  tunable via School Settings "Teori oturumu üst sınırı"); e.g. with default 2 h, `T=3 →
  2+1` across two days; with `max_theory_session=3`, `T=3` fits in one session (one day).
  Lab blocks are exempt.

### Soft preferences — penalized in the objective (never block a schedule)

Listed by default weight magnitude where that comparison is meaningful; weights live in
`config.py`, but `settings.build_config()` may zero or remap some UI-controlled terms at solve
time. The CP-SAT monolith (§7a) and the repair soft polish (§7b) use separate objectives — see
§5 for which terms belong to which path.

- **Cohort course-conflict** (`w_cohort_conflict=50`) — penalize each extra distinct course a
  `(dept, year)` cohort runs in the same slot (CP-SAT monolith objective; no-regress guard in
  repair polish). A *soft proxy* — a hard version was infeasible.
- **Student idle gaps** (`w_idle=15.0` repair / `w_cohort_gap=10.0` monolith) — penalize idle
  hours inside a cohort's day; always-on in the repair polish (fixed weight, not a UI dial).
- **Maxrun — anti-fatigue** (`w_maxrun=10.0`) — penalize consecutive teaching runs longer than
  `max_consecutive_hours`=3 h, over cohorts and instructors (repair polish).
- **Compress instructor weeks** (`w_instr_days=10.0` full-time, `w_parttime_days=14.0`
  part-time when an instructor-days target is active; repair polish uses `w_instr_days` only) —
  CP-SAT monolith penalizes every teaching day; repair polish penalizes days beyond
  `max_instr_days`. In the UI default (`instr_days_target = No target`) `build_config()` forces
  both weights to 0.0; choosing ≤4/≤3/≤2 activates the term and maps the priority preset to
  5.0/10.0/20.0, with part-time set to `w_instr_days + 4.0`.
- **Room stability** (`w_room_stable=10.0`) — penalize each section that uses more than one
  room across its blocks (repair polish).
- **Free day** (`w_free_day=10.0`, year-scoped) — penalize each configured year-level cohort
  that occupies all working days (repair polish). The UI does not expose a free-day weight dial;
  the year multiselect is the on/off scope control. With no selected years, the term is inert.
- **Level ordering** (`w_order=1`) — prefer low-level courses early, high-level courses late;
  level-1 and graduate excluded (CP-SAT monolith).
- **Engineering labs late-week** (`w_englab=1`) — prefer Engineering lab blocks on Thu/Fri
  (CP-SAT monolith).
- **Non-adjacent split** (`w_nonadjacent=0`, disabled) — superseded by the hard theory
  different-day rule.

### What "0 resource conflicts" means

`validate.py` independently re-checks: placement, capacity, lab-room, daytime window,
blackouts, room/instructor/self no-overlap, theory different-day, and the School-Settings
hard rules — **room-type** (lab requirement), **fixed** (pinned first block), and
**instructor-unavailable**. In benchmark summaries, "0 resource conflicts" excludes
`placement` violations caused by an unplaced tail; those are reported separately. Cohort
conflict is a **soft metric**, never a hard violation.

### Per-school configuration (School Settings)

Every value above is a default tuned to our own institution; the **School Settings** UI step
lets another school override them without touching code. A session **Settings** dict plus an
instructor-availability map are turned into a `Config` by `settings.build_config` at solve
time: the day window, blackout slots, Saturday toggle, graduate earliest-start controls,
block-split policy, the instructor-days target, free-day year scope, and the soft-preference
weights (as low / medium / high presets) are configurable. Graduate courses are always
included in the UI; there is no graduate on/off checkbox. Optional course-list columns
(`Year`, `Part-time`, `Room Type`, `Fixed`) override the string-derived cohort / part-time /
room demand / pin. Unconfigured settings reproduce the UI defaults documented here exactly.
The pure profile JSON functions remain in `settings.py`, but the profile expander is currently
disabled in the UI (§9.5).
**§9 is the exhaustive control-by-control list of what the UI exposes.**

---

## 1. Sets and indices

| Symbol | Meaning | Source |
|---|---|---|
| $S$ | sections (one cohort offering of a course) | `derive.build_sections` |
| $B$ | blocks; each section contributes one or more | `derive.blocks_from_tpl` |
| $B_s \subseteq B$ | blocks of section $s$ | |
| $R$ | rooms, physical $R_{\text{phys}}$ plus virtual ($\texttt{Online}$) | `classrooms.csv`, `route.mark_virtual` |
| $I$ | instructors (a section may have several — team teaching) | `lecturers.csv` |
| $I_b \subseteq I$ | instructors of the section owning block $b$ | |
| $D$ | days $\{\mathrm{Mo,Tu,We,Th,Fr}\}$ (Sa optional) | `Config.days()` |
| $H$ | hour-slots, `horizon_start` $\le h <$ `horizon_end` (defaults: $9 \le h < 21$) | `horizon_start`, `horizon_end` |
| $K$ | cohorts $k=(\text{dept code},\ \text{year level})$ | `Section.cohort_key` |
| $\mathcal{C}(b)$ | legal candidate placements $(r,d,h)$ of block $b$ | `gen_candidates` |

**Blocks** are derived from a section's T/P/L hours:

- Theory hours $T+P$ split into sessions of at most `max_theory_session` h (default 2 h; e.g.
  $T{=}3 \to 2+1$), each forced onto a different day.
- One lab block of $L$ hours, split at `max_block_len` h (default 4 h), pinned to the
  section's real lab room.
- Block ids: single `#T` / `#L`; split `#T1..#Tk` / `#L1..#Lk`. Kind detected by
  `"#L" in block_id`; `section_id = block_id.split("#")[0]`.

---

## 2. Parameters

| Symbol | Meaning | Default | Knob |
|---|---|---|---|
| $\mathrm{cap}_r$ | capacity of room $r$ | — | `classrooms.csv` |
| $n_s$ | students in section $s$ | — | enrollment |
| $\ell_b$ | length of block $b$ (hours) | — | T/P/L |
| $\mathrm{lvl}_s$ | course level of section $s$ ($1\dots4$) | — | course code |
| $T$ | instructor-days target (soft; repair: days beyond target penalized; monolith: all teaching days penalized) | `week_len`=off (5 M–F; 6 with Sa) | `max_instr_days` |
| $T_{\text{run}}$ | maxrun threshold (soft; consecutive-hour excess) | $3$ | `max_consecutive_hours` |
| — | undergrad end-of-day | 18:00 | `undergrad_end` |
| — | graduate window | 18:00–21:00 | `grad_start` (tunable); `grad_end=21` fixed — not a settings field (`_HORIZON_END=21` in `settings.py`) |
| — | blackout slots (universal / full-time-only) | none | `blackout` (School Settings) |
| — | AM/PM boundary (legacy half-day availability) | 13:00 (hardcoded in `settings.py`) | — (`Config.midday_split_hour` exists but is not read by `build_config`; vestigial field) |
| — | per-instructor unavailable slots | — | `instr_unavailable` (School Settings) |

---

## 3. Decision variables

| Symbol | Domain | Meaning |
|---|---|---|
| $x_{b,r,d,h}$ | $\{0,1\}$ | $=1$ iff block $b$ occupies room $r$, day $d$, starting at hour $h$ |

- A variable is created **only for legal candidates** $(r,d,h)\in\mathcal{C}(b)$ — see the
  pruning note below. The full index product is never materialized.
- Auxiliary variables used by the objective and the different-day rule are derived from
  $x$: day-activity $z_{s,b,d}=\max_{r,h}x_{b,r,d,h}$, room-used, instructor-day indicators,
  and cohort slot-busy / first / last.

**Candidate pruning (key design decision).** Per-block hard rules are enforced by *not
creating* the variable rather than by adding a model row. `gen_candidates` emits
$(r,d,h)$ only when it already satisfies:

- room capacity $\mathrm{cap}_r \ge n_s$ (the virtual `Online` room is exempt — unlimited);
- lab-room pinning — a lab block only in the section's designated lab room;
- undergrad window: $h \ge \texttt{cfg.horizon\_start}$ and $h + \ell_b \le \texttt{cfg.undergrad\_end}$ (default 9–18; tunable);
- graduate window (level > 4): $h \ge \texttt{cfg.grad\_start\_for(dept)}$ and $h + \ell_b \le \texttt{cfg.grad\_end}$ (default start 18, end fixed 21);
- configured blackout slots (`Config.blackout`; none by default — each is universal or
  full-time-only, resolved per section via `cfg.closed_hours`);
- per-instructor availability (`Config.instr_unavailable`) — a candidate is dropped if any of
  the section's instructors is marked unavailable over its span;
- fixed-slot pin — a section's first block is restricted to its declared `(day, start)`;
- room-type — when a section declares a `Room Type`, only rooms of that category are emitted
  (`pc`/`studio`/`lab` exactly, or any lab-family room for a generic lab demand).

Best-fit additionally caps each block to the `max_rooms_per_block` smallest fitting rooms.

---

## 4. Hard constraints

Listed one per block. Each is a model relation; the per-block rules folded into pruning
(capacity, lab-room, window, blackout) are **not** repeated here.

### H1 — placement (exactly one)

$$
\sum_{(r,d,h)\,\in\,\mathcal{C}(b)} x_{b,r,d,h} \;=\; 1 \qquad \forall\, b \in B
$$

- Every block is scheduled exactly once, into one of its legal candidates.
- Because the sum is over $\mathcal{C}(b)$ only, an infeasible placement is unreachable.
- In `repair` this is **soft** (a block may stay unplaced) so a partial schedule always
  exists; in `model_cpsat` it is hard.

### H2 — room no-overlap

$$
\sum_{\substack{b,\,h' \,:\, h\,\in\,[h',\,h'+\ell_b)}} x_{b,r,d,h'} \;\le\; 1
\qquad \forall\, r \in R_{\text{phys}},\; d,\; h
$$

- At most one block occupies a physical room during any hour-slot.
- The inner condition $h\in[h',h'+\ell_b)$ expands a block over every hour it spans.
- The virtual `Online` room is excluded from $R_{\text{phys}}$ — it has unlimited capacity
  and is exempt from this constraint.

### H3 — instructor no-overlap

$$
\sum_{\substack{b \,:\, i \in I_b}}\ \sum_{\substack{h' \,:\, h\,\in\,[h',\,h'+\ell_b)}} x_{b,\cdot,d,h'} \;\le\; 1
\qquad \forall\, i \in I,\; d,\; h
$$

- No instructor is double-booked in any hour-slot.
- A team-taught section enters the sum of **every** co-instructor.

### H_self — intra-section no-overlap

$$
\sum_{\substack{b \in B_s,\, h' \,:\, h\,\in\,[h',\,h'+\ell_b)}} x_{b,\cdot,d,h'} \;\le\; 1
\qquad \forall\, s \in S,\; d,\; h
$$

- Distinct blocks of the same section never overlap (a student in the section could not
  attend both).
- Same shape as H3 but grouped by section instead of instructor.

### H_day — theory different-day

$$
\sum_{b \,\in\, B_s^{\text{theory}}} z_{s,b,d} \;\le\; 1
\qquad \forall\, s \in S,\; d \in D,
\qquad z_{s,b,d} = \max_{r,h} x_{b,r,d,h}
$$

- A section's theory sessions each fall on a **different day** (e.g. a $2+1$ split occupies
  two days, not one).
- Hard in **both** `model_cpsat` and `repair`; re-checked as `split_day` in `validate`.
- Lab blocks are excluded (the rule keys on $b\in B_s^{\text{theory}}$).

> **Cohort overlap is deliberately not a hard constraint.** A hard course-level cohort
> rule was proven infeasible at scale, so it is a *soft* term (§5.8). "0 resource conflicts"
> therefore means H2, H3, H_self, H_day plus the pruned rules (capacity, lab-room, window,
> blackout) all hold for placed blocks; unplaced tails are tracked separately as placement
> violations.

---

## 5. Soft objective

The CP-SAT monolith (§7a) and the repair soft polish (§7b) minimize different weighted-sum
objectives. Weights live in `config.py`. The two paths share the weight fields
`w_instr_days` / `w_parttime_days` (but with different semantics — see §5.1). The repair
polish has terms absent from the monolith (`w_idle`, `w_maxrun`, `w_room_stable`,
`w_free_day`); the monolith has terms not in the polish objective (`w_cohort_gap`, `w_order`,
`w_englab`). `w_cohort_conflict` appears in both but as an objective term in the monolith and
as a no-regress guard in the polish.

$$
\min \;\; \sum_{t} w_t \cdot \mathrm{pen}_t
$$

### 5.1 Instructor-days — $w_{\text{instr}}=10.0$ (full-time), $w_{\text{pt}}=14.0$ (part-time)

$$
\mathrm{pen}_{\text{days}} \;=\; \sum_{i,d} w_i\, \delta_{i,d},
\qquad \delta_{i,d} = \big[\, i \text{ teaches on day } d \,\big]
$$

- One unit per distinct day an instructor teaches → compress each instructor's week.
- Part-time staff carry the heavier weight (fewer trips to campus).

**Semantics differ by path.** In the CP-SAT monolith the weight applies to *every* teaching
day; in the repair soft polish it applies to days **beyond the target** $T = $ `max_instr_days`
($\max(0,\ \text{days}_i - T)$). In the School-Settings/UI path, `build_config` forces
`w_instr_days = w_parttime_days = 0` when `instr_days_target` is "No target" (the default),
making the term inert until the target dial is activated. Raw `Config()` still carries the
legacy nonzero weights used by CLI/model tests unless a Settings dict is built.

**Target lever (`instr_days_target` → `max_instr_days`).** The School-Settings control maps
**No target → $T = $ week length** (5, or 6 with Saturday) which is the term's **off state**
(no headroom ⇒ inert ⇒ the build forces $w_{\text{instr}} = w_{\text{pt}} = 0$), and **≤4 /
≤3 / ≤2 → $T = 4/3/2$**, which creates headroom so the priority dial steers. Default is **No
target** (opt-in; an untouched settings step reproduces today's schedule). The consolidation
move in the soft polish (`soft_search`) is gated on $T < $ week length, so a weight alone
cannot steer this term — *the target must create headroom first*.

**Measured steerability (2026-06-23, deluge polish).** Measured across **TED University's**
real Fall and Spring rosters. Same-snapshot sweep
(`bench/instr_days_target_sweep.py`; converge once, polish each target from the identical
snapshot, $w_{\text{instr}}$ maxed). Metric = real per-instructor teaching-day distribution
(target-independent, so comparable across targets). As the target tightens **No target → ≤4 →
≤3**, mean teaching-days falls **monotonically** and the matching $\le k$ share climbs, with
`conf` held at baseline (no placement/conflict regression) on **both** Fall (001) and Spring
(002) rosters:

| target | 001 mean days | 001 %≤3 | 002 mean days | 002 %≤3 |
| --- | --- | --- | --- | --- |
| No target | 3.82 | 36% | 3.65 | 41% |
| ≤4 | 3.54 | 39% | 3.40 | 43% |
| ≤3 | 3.38 | **56%** | 3.22 | **61%** |
| ≤2 | 3.38 | 55% | 3.23 | 60% |

*(full data, ~97%/93% greedy snapshot, 2 seeds, 20 s polish; `conf` 229/230 held throughout.)*

- **≤3 is the reliable sweet spot:** the largest clean monotone gain, %≤3 jumps to ~56–61%.
- **≤2 saturates near ≤3 under a short polish budget.** With more relative budget it separates
  (N=400, fully-converged snapshot, 12 s: ≤2 mean **2.79** vs ≤3 **2.96** on 001, and **2.76**
  vs **2.86** on 002; %≤2 climbs to **54%** on both) — so ≤2 is realizable but wants the longer
  production solve budget.
- **Multi-seed gate** (`bench/acceptor_ab.py`, deluge, N=400, 5 seeds, $T=2$): `instr_days`
  selected_gain **+57.8 % [+54 %, +61 %]**, sign-stable (no flip), `conf` held. In the same
  run `maxrun` (+28 %) and `room_stable` (+15 %) also steer stably; `free_day` flips sign —
  it is scope-controlled, not weight-steerable.

### 5.2 Cohort idle gaps — $w_{\text{gap}}=10.0$ (monolith) / $w_{\text{idle}}=15.0$ (repair polish)

$$
\mathrm{gap}_{k,d} \;\ge\; \mathrm{last}_{k,d} - \mathrm{first}_{k,d} - \mathrm{load}_{k,d},
\qquad \mathrm{pen}_{\text{gap}} = \sum_{k,d} \mathrm{gap}_{k,d}
$$

- Penalizes idle gaps inside a cohort's day: span (last $-$ first) minus busy hours.
- In the CP-SAT monolith, `w_cohort_gap` applies to cohorts of year level
  $\in\{2,3,4\}$ (`compact_cohort_years`). In the repair soft polish, `idle`
  is computed over all cohorts.
- $\mathrm{first}/\mathrm{last}$ are min/max active hour of the cohort that day.
- In the CP-SAT monolith the weight is `w_cohort_gap=10.0`; in the repair soft polish the
  same metric is `idle`, weighted `w_idle=15.0` (always-on, fixed — not a UI dial).

### 5.3 Maxrun — $w_{\text{maxrun}}=10.0$ (repair polish)

- Penalizes cumulative consecutive teaching hours beyond `max_consecutive_hours`=3, over both
  cohorts and instructors.
- Repair soft polish term only. UI dial: low / medium / high (default medium = 10.0).

### 5.4 Room stability — $w_{\text{room\_stable}}=10.0$ (repair polish)

- Penalizes each section that uses more than one distinct physical room across its blocks
  ($\max(0,\lvert\text{rooms}(s)\rvert - 1)$).
- Repair soft polish term only. UI dial: low / medium / high (default medium = 10.0).

### 5.5 Free day — $w_{\text{free\_day}}=10.0$ (repair polish, year-scoped)

- Penalizes each configured year-level cohort ($\in$ `free_day_year_levels`) that occupies
  all working days (i.e. has no completely empty day in the week).
- Controlled by year scope (multiselect in the UI), not by a weight dial. `w_free_day` remains
  a fixed `Config` coefficient (10.0) used by repair polish, but with no selected years there
  are no cohorts in scope, so the term is inert.

### 5.6 S-Order — $w_{\text{order}}=1$ (monolith)

$$
\mathrm{pen}_{\text{order}} \;=\; \sum_{b,r,d,h} w_{\text{order}}\,(4-\mathrm{lvl}_s)\,(h-\texttt{cfg.horizon\_start})\; x_{b,r,d,h}
\qquad (\,2 \le \mathrm{lvl}_s \le 4\,)
$$

- Encourages low-level courses early and high-level courses late in the day.
- Coefficient grows with start hour and with how low the level is; level-1 and graduate
  excluded.

### 5.7 S-EngLab — $w_{\text{englab}}=1$ (monolith)

$$
\mathrm{pen}_{\text{englab}} \;=\; \sum_{\substack{b \text{ Eng. lab}\\ (r,d,h):\, d \notin \{\mathrm{Th,Fr}\}}} x_{b,r,d,h}
$$

- One unit per Engineering **lab** block placed off Thursday/Friday (`eng_lab_days`).
- Matches sections whose faculty contains `eng_department_match` $=$ "Engineering".

### 5.8 Cohort-conflict — $w_{\text{coh}}=50$

$$
\mathrm{excess}_{k,d,h} \;\ge\; \Big(\textstyle\sum_{c} \mathrm{busy}_{k,c,d,h}\Big) - 1,
\qquad \mathrm{pen}_{\text{coh}} = \sum_{k,d,h} \mathrm{excess}_{k,d,h}
$$

- For each cohort-slot, penalizes every **distinct course** busy beyond the first
  ($\mathrm{busy}_{k,c,d,h}=\max x$ over that course's blocks in the slot).
- A *soft* proxy: $(\text{dept},\text{year})$ over-counts conflict because students split
  across electives, so a hard rule was infeasible. High weight (50) but not prohibitive.
- In the CP-SAT monolith this enters the objective directly; in the repair solver it is a
  **no-regress guard** (`conf`): soft-polish moves are rejected if `conf` would increase.
- Reported as `cohort_conflicts`; **never** a `Violation` in `validate`.

### 5.9 Non-adjacent split — $w_{\text{nonadj}}=0$ (disabled)

- Would penalize a section's split blocks sharing a day; **superseded** for theory by the
  hard different-day rule (H_day), so the weight is $0$.

---

## 7. Solution methods

Both solvers share the same candidate generation and constraints.

**(a) Monolithic — `model_cpsat.build_and_solve`.**

- Builds the full model above and calls CP-SAT once.
- Used for **scoped** runs (a faculty/department, Mode A/B benchmarking).
- A single *global* solve (~367 k variables) returns **UNKNOWN** — it does not scale to the
  full period, which is why (b) exists.

**(b) Repair — `repair.solve_repair` (`--repair`, production).**

1. **Greedy construction (soft-shaping)** — place each block in its **lowest soft-score**
   feasible candidate (ties broken by candidate order = best-fit room). The soft score is
   `w_cohort_conflict·new_cohort_conflicts` (with an `instr_days` tie-break of 1 per new
   instructor-day beyond target, when the target is active). Cohort-conflict shaping is **on
   by default** (`soft_shaping_in_repair=True`, `--no-soft-shaping` to disable).
   `new_cohort_conflicts` is myopic (sees only already-placed blocks), so the reduction is
   partial but cheap and placement-safe.
2. **Warm-started small-neighbourhood repair** — repeatedly free a small batch of unplaced
   blocks plus their competitors and re-solve that neighbourhood with CP-SAT (soft H1,
   warm-started from the current placement); frozen blocks stay as reservations. Loop until
   no gains.
3. **Move-based soft polish** (`soft_search.anneal_soft`) — once placement converges,
   re-seat already-placed blocks to lower the normalized five-term objective
   (idle / maxrun / instr_days / room_stable / free_day) under a `conf` no-regress guard.
   Moves: relocate, chain, swap, consolidate_instr, free_cohort_day. Acceptor: Great Deluge
   (default). Bounded by the `repair_time_limit_s` deadline; the placement count never
   decreases (hard placement guard + accept guard).

**Repair solver — top-level flow**

```mermaid
flowchart TD
    A([Start]) --> B[gen_candidates\nfor every block]
    B --> C[Sort all blocks\nfewest candidates first\nthen largest section]
    C --> D[Greedy construction\nplace each block in lowest\nsoft-score feasible candidate]
    D --> E{Unplaced\nblocks?}
    E -- No --> P
    E -- Yes --> F[Sort unplaced\nby candidate count]
    F --> G[Next batch of 30\nunplaced blocks]
    G --> H[repair_round\nsee detail below]
    H --> I{More\nbatches?}
    I -- Yes --> G
    I -- No --> J{gained > 0\nAND sweep < 25?}
    J -- Yes --> E
    J -- No --> P[Soft polish\nanneal_soft · deluge\nidle/maxrun/instr_days/room_stable/free_day]
    P --> R([Done\nassignments + stats])
```

**repair\_round — neighbourhood sub-solver**

```mermaid
flowchart TD
    A([batch: unplaced blocks]) --> B[competitors\nroom / instructor / section conflicts\nup to MAX_FREE=240 total]
    B --> C[Build mini CP-SAT model\nsoft H1: placed OR unplaced var\nH2 room · H3 instr · H_self · H_day]
    C --> D[Add warm-start hints\ncurrent placement → hint=1\nunplaced → hint=1 on unplaced var]
    D --> E[Solve\n12 s · 8 workers]
    E --> F{OPTIMAL or\nFEASIBLE?}
    F -- No --> Z([return 0])
    F -- Yes --> G{new_placed\n≥ old_placed?}
    G -- No → accept guard --> Z
    G -- Yes --> H[Release free set\nfrom state]
    H --> I[Occupy new assignments\ninto state]
    I --> J([return gained])
```

**Pseudocode — `solve_repair`**

`solve_repair` accepts an optional `progress_cb=None` callable. When provided, it is called once at each of the 4 phase boundaries below with an event tuple:

| Call site | Tuple emitted |
| --- | --- |
| After candidate generation, before sort | `("gen_candidates", total_blocks)` |
| Before greedy construction | `("construct", None)` |
| After `unplaced` recheck, before sort (each sweep where `unplaced ≠ []`) | `("repair_sweep", sweep_number, n_unplaced)` |
| Before `anneal_soft` (only if `soft_polish_in_repair`) | `("soft_polish", None)` |

`pipeline.py` additionally fires `("validate", None)` immediately before calling `validate()`. The UI (`views/solve.py`) maps these 5 event keys to step labels ("1/5 · …" … "5/5 · …") and drives a Python-controlled progress bar (no JS timers).

```text
solve_repair(sections, rooms, cfg, progress_cb=None):

  # ── Phase 1: candidate generation ─────────────────────────────────────────
  FOR each (block, section):
      cand_by_block[block_id] = gen_candidates(block, section, cfg)
      # pruned by capacity, lab-room, window, blackout, instructor-unavail

  # sort: hardest-to-place first (fewest legal slots), break ties largest section
  order = sort block_ids by (|cand_by_block[bid]| ASC, section.students DESC)

  # ── Phase 2: greedy construction ──────────────────────────────────────────
  state = State()   # empty occupancy dicts
  FOR bid in order:
      best, best_score = None, ∞
      FOR c in cand_by_block[bid]:
          IF state.free_to_place(c):      # O(ℓ·ι) — room/instr/sect/theory-day
              score = _soft_score(state, c, s, cfg)
              # = w_cohort_conflict × new_cohort_conflicts
              #   + 1 if opening a new instr-day beyond target (tie-break, < 1 conflict unit)
              IF score < best_score:
                  best, best_score = c, score
      IF best ≠ None: state.occupy(bid, best)

  # ── Phase 3: repair sweep loop ────────────────────────────────────────────
  t0 = now();  sweep = 0
  WHILE now() − t0 < deadline AND sweep < 25:
      sweep += 1
      unplaced = [bid ∉ state.placed]
      IF unplaced = []: BREAK

      sort unplaced by (|cand_by_block[bid]| ASC, students DESC)
      gained = 0
      FOR batch in sliding_window(unplaced, BATCH=30):
          IF now() − t0 ≥ deadline: BREAK
          batch = [bid for bid in batch if bid ∉ state.placed]   # recheck after prior rounds
          IF batch ≠ []:
              gained += repair_round(state, batch, cand_by_block)

      IF gained = 0: BREAK   # converged — no improvement possible

  # ── Phase 4: move-based soft polish ───────────────────────────────────────
  IF cfg.soft_polish_in_repair:
      budget = min(SOFT_POLISH_BUDGET_S, max(30.0, 0.75 × |placed|), remaining_deadline)
      # anneal_soft: deluge acceptor; moves = relocate / chain / swap /
      #              consolidate_instr / free_cohort_day
      # objective: normalized(idle + maxrun + instr_days + room_stable + free_day)
      # guard: conf (cohort-conflict) must not increase
      anneal_soft(state, cand_by_block, cfg, budget)

  RETURN build_assignments(state), stats
```

---

**Pseudocode — `repair_round`**

```text
repair_round(state, batch, cand_by_block, tl=12s):

  # ── 1. Identify free neighbourhood ────────────────────────────────────────
  comp = competitors(state, batch, cand_by_block)
  # comp = all placed blocks that share a legal (room, day, h) or instructor
  #        slot with ANY candidate of ANY block in batch, plus same-section blocks

  free     = dedupe(batch + comp)[:MAX_FREE=240]   # capped: O(1) model size
  free_set = set(free)

  # ── 2. Derive reservations from the frozen part of state ──────────────────
  reserved_room  = {(room, day, h) : bid ∉ free_set, h ∈ span(placed[bid])}
  reserved_instr = {(iid,  day, h) : bid ∉ free_set, iid ∈ instructors(bid)}
  frozen_theory_day = {section_id → {day} : bid ∉ free_set, bid is theory block}

  # ── 3. Build mini CP-SAT model ────────────────────────────────────────────
  m = CpModel()
  FOR bid in free:
      # filter candidates that would clash with frozen blocks
      cands = [c for c in cand_by_block[bid]
               IF ¬reserved_room_conflict(c)
               AND ¬reserved_instr_conflict(c)
               AND ¬(theory AND c.day ∈ frozen_theory_day[section])]

      u[bid] = BoolVar()            # 1 ↔ left unplaced (soft H1)
      FOR c in cands:
          x[bid,c] = BoolVar()

      m.AddExactlyOne({x[bid,c] : c ∈ cands} ∪ {u[bid]})

  # no-overlap constraints over the free set (room / instructor / section / theory-day)
  FOR (room, day, h): m.Add( Σ x[bid,c] ≤ 1 )   where c covers h, c.room=room, bid ∈ free
  FOR (iid,  day, h): m.Add( Σ x[bid,c] ≤ 1 )   where iid ∈ instructors(bid)
  FOR (sect, day, h): m.Add( Σ x[bid,c] ≤ 1 )   where bid.section = sect
  FOR (sect, day):   m.Add( Σ x[bid,c] ≤ 1 )   theory only — one theory session per (sect, day)

  # objective: minimize unplaced count only (pure placement; no soft terms)
  # soft shaping is done in greedy construction, not here
  BIG = 10 000
  m.Minimize( BIG × Σ u[bid] )

  # ── 4. Warm-start hints ───────────────────────────────────────────────────
  FOR bid in free:
      IF bid ∈ state.placed:
          hint( x[bid, current_candidate] = 1,  u[bid] = 0 )
      ELSE:
          hint( u[bid] = 1 )

  # ── 5. Solve ──────────────────────────────────────────────────────────────
  solver.max_time_in_seconds = tl    # 12 s
  solver.num_search_workers  = 8
  status = solver.Solve(m)

  IF status ∉ {OPTIMAL, FEASIBLE}: RETURN 0   # no improvement possible

  new_assign = {bid: c  where solver.Value(x[bid,c]) = 1}
  old_count  = |{bid ∈ free : bid ∈ state.placed}|

  # ── 6. Accept guard ───────────────────────────────────────────────────────
  IF |new_assign| < old_count:   # would drop placements → reject, state unchanged
      RETURN 0

  release free_set from state
  occupy new_assign into state

  RETURN |new_assign| − old_count   # ≥ 0; positive means new placements gained
```

Current preserved full-roster benchmark (`out/benchmark_real.json`, 300 s single-worker
budget, Apple M1 Pro arm64) on TED University's Fall/Spring sample course lists
(`sample_courses_2025_0XX.csv`) places **1924 / 1981** Fall blocks (97.1 %) and
**1863 / 2011** Spring blocks (92.6 %). Both runs have **0 genuine resource conflicts**; the
unplaced tail appears as validator `placement` violations (57 / 148), not as room,
instructor, capacity, window, blackout, or split-day clashes.

**Measured effect of soft-shaping** (period 001, cohort-conflict, **on by default**,
two `--no-soft-shaping` baselines for the noise band):

| metric | baseline (off) | shaping on |
|---|---|---|
| placed assignments | 1581–1584 | 1602 (no loss — slightly higher) |
| cohort-conflict (proxy) | ~540–575 | 384 (≈ −31 %) |

Soft-shaping costs **no placement** (spreading cohorts also distributes load and improves
packing). The cohort-conflict proxy drops by roughly a third versus the manual program's
far worse 139 cohort-conflicts, while preserving 0 resource conflicts.

**Soft-polish acceptor — tuning A/B** (the move-based polish
`soft_search.anneal_soft` uses an *acceptance rule* to decide which neighbourhood moves to
keep. `bench/acceptor_ab.py`, converged snapshots, 3 seeds, 30 s polish/run. Objective `E`
is the normalized weighted sum, starts at 55, lower is better. These figures are tuning
evidence for the acceptor choice, not the headline full-roster placement table above):

| period | deluge | lahc / schc |
|---|---|---|
| **Fall (001)** tuning snapshot | E **40.6** | E 54.4 |
| **Spring (002)** tuning snapshot | E **42.5** | E 54.3 |

Per-dial steerability (`selected_gain` = how much maxing a dial improves its own term vs the
same-run uniform profile; **bold** = sign-stable across seeds, `~` = not sign-stable):

| dial | deluge (Fall / Spring) | lahc (Fall / Spring) |
|---|---|---|
| maxrun — long runs | **+28 % / +24 %** | +4 %~ / +14 % |
| instr_days — concentrate days¹ | **+14 % / +12 %** | +3 %~ / −2 %~ |
| room_stable — one room | **+5 % / +8 %** | +3 %~ / +4 %~ |
| free_day — year-scoped | −4 %~ / +3 %~ | +9 % / −4 %~ |

`conf` (cohort-conflict guard) stayed ≤ baseline in every run; placement 99–100 %.

**Decision: `soft_polish_acceptor = "deluge"`** (default since commit `30e2ce6`). Deluge is a
fast-decay great-deluge ≈ disciplined greedy descent: it digs far deeper (E ≈ 40 vs 54) and
follows the weight gradient predictably, so 3 of 4 dials steer sign-stably in *both* periods.
LAHC/SCHC wander and steer noisily; at the production history length they coincide.

¹ `instr_days` only steers when its target is below the working-week length
(`max_instr_days < len(days)`); the A/B set `max_instr_days = 2` for headroom. `free_day` is
not weight-steerable and ships scope-only (year selection) — but it is *not* inert; see the
move-on/off verification below. Timings are Apple M1 Pro; the harness ran an x86_64 Rosetta
Python, so native arm64 is somewhat faster.

**`free_day` — why the steerability table understates it, and how it is actually verified.**
The `selected_gain` metric above is the *wrong* test for `free_day`. It compares maxing the dial
($w_{\text{free\_day}}=20$) against the uniform profile ($w=10$) with the **compound move
running in both arms**, so it measures only *weight*-responsiveness — and the move already does
its job at $w=10$, so doubling the weight adds nothing (≈ 0 %, sign-unstable `~`). The right test
is **move-on vs move-off** (`bench/free_day_move_ab.py`): from one converged snapshot, run the
polish with the `try_free_cohort_day` compound move enabled vs disabled, the `free_day` weight
fixed in both arms, and count the cohorts that end up with a free day. The move — which
atomically vacates a configured cohort's least-loaded day, relocating every block off it or
reverting wholesale — genuinely frees more cohort-days, sign-consistent across seeds with `conf`
held at baseline, on **both** periods:

| period | cohorts with a free day, move OFF → ON | `free_day` term | `conf` |
| --- | --- | --- | --- |
| Fall (001), N=400, 5 seeds | 25.8 [25,26] → **29.4 [29,30]** (+3.6 of 41) | 15.2 → 11.6 | 52 (held) |
| Spring (002), N=250, 3 seeds | 13.0 [13,13] → **14.7 [14,15]** (+1.7 of 24) | 11.0 → 9.3 | 40 (held) |

So the feature **works in absolute terms** — the *move* frees cohort-days; the *weight dial*
simply cannot steer it, which is why the UI exposes `free_day` as a **scope control only** (the
year multiselect; `_WEIGHT_KNOBS = ("maxrun", "instr_days", "room_stable")` omits it) rather than
an off/normal/strong dial. The cohorts that keep all five days are feasibility-locked — their
blocks cannot fit into four days under the room/instructor constraints, so no weight or move can
free them. (Operational note: `gen_candidates` for Spring is memory-superlinear in $N$ — N=400
needs ≈ 2.5 GiB resident and thrashes a low-free-RAM machine into a 0 %-CPU swap hang during
converge; use a smaller $N$ for Spring polish benches.)

---

## 8. Validation (independent)

`validate.py` re-derives the core hard-resource violations directly from the assignment list,
importing no solver internals, so model/encoding bugs in those checked rules cannot pass
silently. It checks: room,
instructor, capacity, **lab_room**, **room_type** (categorical room demand), **fixed** (pinned
first block), window ($h + \ell_b \le \texttt{cfg.undergrad\_end}$, default 18:00), blackout, **instructor_unavailable** (per-instructor
availability), H_self, and **split_day** (theory different-day). Cohort conflict is a **soft
metric**, not a `Violation` — reported in `mode_b_<period>.json` / `unmet_soft`, never failing
validation.

### 8.1 Independent verification run (2026-06-23)

Running `validate.py` over the preserved full-roster benchmark (`out/benchmark_real.json`)
returns **0 genuine resource conflicts** on both sample datasets. The remaining validator
violations are `placement` violations for the reported unplaced tail:

| | Fall (`001`) | Spring (`002`) |
| --- | --- | --- |
| placed blocks | 1924 / 1981 (97.1 %) | 1863 / 2011 (92.6 %) |
| placement violations (unplaced tail) | 57 | 148 |
| capacity · lab_room · room_type | 0 · 0 · 0 | 0 · 0 · 0 |
| fixed · window · blackout | 0 · 0 · 0 | 0 · 0 · 0 |
| instructor_unavailable | 0 | 0 |
| room · instructor · self (no-overlap) | 0 · 0 · 0 | 0 · 0 · 0 |
| split_day | 0 | 0 |
| **genuine resource conflicts** | **0** | **0** |
| soft (minimized): idle / maxrun / room_stable | 128 / 1079 / 517 | 107 / 1105 / 484 |
| soft: instr_days / free_day / conf | 0 / 0 / 229 | 0 / 0 / 230 |

`instr_days = 0` and `free_day = 0` because their UI controls are off by default (No target /
no year scope, §5.1 / §5.5); `conf` is the **soft** cohort-conflict proxy (§5.8), not a hard
violation. `repair` is not solver-free: after greedy construction, each `repair_round` builds a
mini CP-SAT model over a bounded neighbourhood (§7b). Those rounds may leave a block unplaced
under a time budget, but they do not introduce illegal resource placements.

---

## 9. UI-adjustable parameters (School Settings)

Everything in §§2–6 is a `Config` default tuned to our own institution. The UI's **Step 2 —
School Settings** (`views/settings.py`) lets another school override a curated subset *without
touching code*: the step writes a plain **Settings** dict (plus an availability map) into
session state, and `settings.build_config(settings, availability, solve_seconds)` maps it into
a `Config` at solve time. The mapping is **backward-compatible by construction** —
`DEFAULT_SETTINGS` mirrors today's `Config` defaults, so an untouched step reproduces the exact
UI-default behavior documented above. `build_config` **never raises**:
every bad field falls back to its default and the solve proceeds.

### 9.1 Policy & block structure (the "Policy" expander)

| UI control | Range | `Config` field | Effect |
|---|---|---|---|
| Day start | 6–12 | `horizon_start` | earliest start hour (default 09:00) |
| Day end | 13–21 | `undergrad_end` | undergrad end-of-day window (default 18:00) |
| Max theory session | 1–6 | `max_theory_session` | longest single theory session before splitting (default 2 h) |
| Max block length | 1–8 | `max_block_len` | longest lab block before splitting (default 4 h) |
| Instructor-days target | No target / ≤4 / ≤3 / ≤2 | `max_instr_days` + `w_instr_days` | No target → term off (weight forced 0); ≤4/≤3/≤2 sets target and activates the instr_days soft term. See §5.1. |
| Saturday | checkbox | `saturday_enabled` | add Sa to the teaching week |
| Graduate | (always True — not a UI control; hardcoded `s["include_grad"] = True` in `views/settings.py`) | `include_grad` | graduate courses are always scheduled; the field exists in `Config` and `DEFAULT_SETTINGS` but no checkbox is rendered. |
| Graduate earliest start | 6–20 | `grad_start` | earliest hour a graduate block may start (default 18:00). Lower it to allow daytime graduate classes; guarded to `day_start ≤ grad_start < 21`, else reverts to 18. |
| Lunch break | (not currently rendered in UI) | `lunch_enabled`, `lunch_start`, `lunch_end` | `build_config` supports it: when on, `[lunch_start, lunch_end)` is closed every active day as a universal blackout. Present in `DEFAULT_SETTINGS` but no UI control is shown; effectively always off. |

The day window is guarded (`0 ≤ day_start < day_end ≤ 21`); out-of-order values silently
revert to `9 / 18`. The AM/PM boundary for legacy half-day availability is no longer a
user-facing control — it is fixed at 13:00.

### 9.2 Preference weights (low / medium / high presets)

Schools pick a **plain-language level**, never a raw number. Presets: `UI_REF=20.0` ×
`WEIGHT_LEVELS` → low=5.0, medium=10.0, high=20.0 (uniform across all dials).

| UI control | `Config` field(s) | low / medium / high |
|---|---|---|
| Maxrun | `w_maxrun` (§5.3) | 5.0 / 10.0 / 20.0 |
| Instructor days¹ | `w_instr_days` / `w_parttime_days` (§5.1) | 5.0 / 10.0 / 20.0 |
| Room stability | `w_room_stable` (§5.4) | 5.0 / 10.0 / 20.0 |

`free_day` (§5.5) has a fixed `Config` weight of 10.0 and is not exposed as a dial — only its
year scope (multiselect) is configurable. With no selected years it is inert. `w_cohort_gap=10.0`
is fixed at medium and not exposed.

¹ Only active when `instr_days_target` is set. With "No target", `build_config()` forces
`w_instr_days = 0.0` and `w_parttime_days = 0.0`; when active,
`w_parttime_days = w_instr_days + 4.0`.

### 9.3 Blackouts (add/remove list)

Each row is `[day, hour, staff_only]` → a `Config.blackout` triple. `staff_only = false` → a
**universal** blackout (closed for everyone); `staff_only = true` → a **full-time-only**
blackout (closed only when a section has a full-time staff instructor — e.g. a faculty seminar).
**Empty by default** (no blackout slots). The *lunch break* toggle (§9.1) adds its own universal
slots over `[lunch_start, lunch_end)` for every active day. All are enforced by candidate
pruning (§3).

### 9.4 Instructor availability (the "Availability" expander)

Per-instructor (keyed by the **email-or-name identity** from the uploaded course list — email
when present, else the normalized display name) a **per-hour grid** (one checkbox per teaching
hour over `[day_start, day_end)` on each active day) marks unavailable slots, stored as a
frozenset of `(identity, day, hour)` closed slots (`availability_closed_slots`) →
`Config.instr_unavailable`. A candidate is pruned if **any** co-instructor of the section is
closed over the block's span (hard, §3). Legacy half-day codes (`AM = [day_start, 13)`,
`PM = [13, 21)`) are still decoded on load so older saved data keeps working; the AM/PM boundary
is fixed at 13:00.

### 9.5 School profile (the "Profile" expander) — *currently disabled in the UI*

The profile import/export (`profile_to_json` / `profile_from_json`, `views/settings._profile`)
would download the current Settings + availability as `kairos_school_profile.json` and restore
it from an upload (`profile_from_json` merges only **known** keys onto `DEFAULT_SETTINGS`, so a
partial or older file stays safe). The render call is **commented out** for now — an out-of-spec
JSON upload can crash the parser — so the expander is not shown; the pure functions remain for
when the upload path validates the schema defensively.

### 9.6 Adjacent but *not* in the Settings step

- **Solve budget** (`solve_time_limit_s` / `repair_time_limit_s`) comes from the **Solve** step,
  not Settings; it is the `solve_seconds` argument to `build_config`.
- **Course-list column overrides** ride on the uploaded CSV, not the Settings dict: `Year`,
  `Part-time`, `Room Type`, and `Fixed` override the string-derived cohort / part-time / lab /
  pinned-slot per row (§0, §3).
- **Fixed at `config.py` defaults — deliberately not exposed:** the cohort-conflict weight
  (`w_cohort_conflict=50`, §5.8), the always-on idle weight (`w_idle=15.0`, §5.2),
  cohort-compactness (`w_cohort_gap=10.0`, §5.2), level-ordering (`w_order`, §5.6),
  Engineering-lab preference (`w_englab`, §5.7), and the repair soft-shaping toggle (§7b).
  These are calibrated globals, not per-school policy.

---

## 10. Time & space complexity

Two regimes govern cost, and the whole engineering story of §7 — why the monolith is
abandoned for repair — is a complexity story:

1. **Model construction and all of repair's bookkeeping are polynomial — in fact *linear in
   the number of blocks* $B$** for a fixed time/room configuration. This is a direct
   consequence of candidate pruning (§3): hard per-block rules cost **zero** model rows.
2. **The CP-SAT search itself is NP-hard.** UCTP generalizes graph colouring and bin
   packing; the worst case is exponential in the number of Booleans. Both solvers therefore
   **bound the search by a wall-clock limit**, trading the optimality/feasibility *guarantee*
   for a predictable *runtime*.

The design keeps every *deterministic* phase linear, and keeps every *NP-hard* phase on a
subproblem of bounded size.

### 10.1 Size parameters

| Symbol | Meaning | Typical (Fall / Spring) | Bounded by config? |
|---|---|---|---|
| $S$ | sections | 990 / 969 | input |
| $B$ | blocks, $\Theta(S)$ ($\approx 2.0\,S$) | 1981 / 2011 | input |
| $\lvert R\rvert$ | rooms (physical + `Online`) | 103 + 1 | input |
| $\lvert I\rvert$ | instructors | 302 / 307 | input |
| $K$ | cohorts $(\text{dept},\text{year})$ | 152 / 147 | input |
| $\lvert D\rvert$ | days | 5 (6 with Sa) | **const** |
| $\lvert H\rvert$ | hour-slots (legal undergrad starts $\le \lvert H\rvert$) | 12 (~8 starts) | **const** |
| $\rho$ | `max_rooms_per_block` | 12 mono / 24 repair | **const** |
| $\ell$ | max block length (`max_block_len`) | $\le 4$ | **const** |
| $\iota$ | instructors per section (team teaching) | ~1 | **const** |
| $P$ | candidate fan-out $\rho\lvert D\rvert(\lvert H\rvert-\ell+1)$ | $\le \sim\!480$ | **const** |

The point: every dimension that could make the model big — rooms-per-block, days, hours,
block length, co-instructors — is a **bounded configuration constant**. The only
free-growing dimension is the roster ($S$, hence $B$). Define the per-block **candidate
fan-out** $P=\max_b\lvert\mathcal C(b)\rvert\le\rho\lvert D\rvert(\lvert H\rvert-\ell+1)=O(1)$
in roster size.

**Dataset profile — TED University sample course lists** (`data/sample_courses_2025_0XX.csv`,
the product datasets; gitignored, so the concrete numbers are recorded here):

| Metric | Fall (`001`) | Spring (`002`) |
| --- | --- | --- |
| Schedulable sections (course rows) | 990 | 969 |
| Distinct course codes | 624 | 600 |
| Sessions to place (blocks) | 1,981 | 2,011 |
| — theory / lab | 1,896 / 85 | 1,940 / 71 |
| Instructors (unique) | 302 | 307 |
| Departments (cohort codes) | 60 | 57 |
| Cohorts (dept × year) | 152 | 147 |
| Classrooms (real, of which labs) | 103 (17) | 103 (17) |
| Online/oversize sections → virtual room | 28 | 13 |
| Room capacity (min / median / max) | 20 / 45 / 100 | 20 / 45 / 100 |
| Team-taught sections | 1 | 0 |

Full-period 300 s benchmark (`out/benchmark_real.json`, single worker): Fall **97.1 %**
placed / 303 s, Spring **92.6 %** / 303 s, **0 genuine resource conflicts**. The remaining
57 / 148 blocks are `placement` violations (unplaced tails), not illegal resource clashes.
Separate tuning/headline artifacts such as `out/ted_headline_arm64.json` use smaller
schedulable subsets and should not be mixed with the full-roster table. Notes on the sample:
every instructor is flagged full-time (`is_staff = True`), so `w_parttime_days` never engages
on this data; the online/oversize sections carry a sentinel capacity (999 Fall / 500 Spring)
and route to the single unlimited `Online` virtual room (exempt from room no-overlap), so they
are not real seat counts.

### 10.2 Model size (shared by both solvers)

Candidate pruning makes the variable set **sparse**: a variable exists only for a legal
$(r,d,h)$, never the full $B\times\lvert R\rvert\times\lvert D\rvert\times\lvert H\rvert$
product (`gen_candidates`, model_cpsat.py:70; var creation, model_cpsat.py:142).

$$\lvert x\rvert \;=\; \sum_{b}\lvert\mathcal C(b)\rvert \;\le\; B\cdot P \;=\; O(B).$$

Concretely the full-period monolith is **≈367 k variables** (§7a) — about $B\times 208$
effective, well below the $B\times P$ cap because pinned labs contribute one room and large
sections fit few rooms.

Every variable enters $O(\ell\iota)$ resource-slot rows, so the constraint system is also
linear:

| Constraint (§4–§6) | # rows | # literals | Code |
|---|---|---|---|
| H1 placement | $B$ | $O(BP)$ | `AddExactlyOne`, model_cpsat.py:165 |
| H2 room no-overlap | $\le\lvert R\rvert\lvert D\rvert\lvert H\rvert$ | $O(BP\ell)$ | model_cpsat.py:168-171 |
| H3 instructor no-overlap | $\le\lvert I\rvert\lvert D\rvert\lvert H\rvert$ | $O(BP\ell\iota)$ | model_cpsat.py:168-171 |
| H_self section no-overlap | $\le\lvert S\rvert\lvert D\rvert\lvert H\rvert$ | $O(BP\ell)$ | model_cpsat.py:168-171 |
| H_day theory diff-day | $O(\lvert S\rvert\lvert D\rvert)$ | $O(B\lvert D\rvert)$ | model_cpsat.py:223-230 |
| soft terms (all) | $O(K\lvert D\rvert\lvert H\rvert+\lvert I\rvert\lvert D\rvert+\lvert R\rvert)$ | $O(BP\ell)$ | model_cpsat.py:174-251 |

**Total model size $=O(BP\ell\iota)=O(B)$** for fixed config. The $\ell\iota$ factors are the
span expansion (a block occupies $\ell$ hours) and team teaching (each co-instructor enters
H3); both are small constants. Linearity is the whole payoff of pruning — the four pruned
per-block rules (capacity, lab-room, window, blackout) add **no** rows at all.

### 10.3 Monolithic `build_and_solve`

| Phase | Time | Space |
|---|---|---|
| Build (candidates + occupancy dicts) | $\Theta(BP\ell\iota)$ — linear | $\Theta(BP\ell\iota)$ |
| Solve (CP-SAT) | **NP-hard**, capped by `solve_time_limit_s` | $\propto$ model size |

- **Build** is dominated by `gen_candidates` ($O(P\ell\iota)$ per block — the blackout /
  availability membership checks scan the $\ell$-hour span, model_cpsat.py:87-95) plus
  populating the occupancy dictionaries ($O(\ell\iota)$ per variable, model_cpsat.py:154-164).
- **Solve** is the NP-hard part. Without a limit the worst case is $2^{O(BP)}$; here it is
  bounded by `CpSolver.max_time_in_seconds` over `CPSAT_MAX_WORKERS` (default 8)
  (model_cpsat.py:254-255). The
  **time is capped; the guarantee is not** — at ≈367 k variables CP-SAT cannot even certify
  feasibility within budget and returns **UNKNOWN** (§7a). That single fact is why the repair
  solver exists.
- **Space** is the model ($\Theta(B)$) plus CP-SAT's internal state ($\propto$ model size with
  a large constant) — the source of the **≥4 GiB RAM floor**: a full-period solve blows past
  Cloud Run's 512 MiB default and OOM-kills (CLAUDE.md / README Deployment).

### 10.4 Repair `solve_repair` (production)

Deterministic preprocessing is linear; the NP-hard search is sliced into **constant-size**
neighbourhoods.

| Phase | Time | Space | Code |
|---|---|---|---|
| Generate all candidates | $O(BP\ell\iota)$ | $O(BP)$ stored | repair.py:463-467 |
| Sort blocks (fewest cands first) | $O(B\log B)$ | — | repair.py:469-470 |
| Greedy construction | $O(BP\ell\iota)$ | $O(B\ell\iota)$ state | repair.py:133 |
| Repair sweep loop | $\le 25\lceil B/30\rceil=O(B)$ rounds | $O(1)$ live model | repair.py:481-498 |
| — each `repair_round` | build $O(FP\ell\iota)$; solve $\le$ 12 s | $O(1)$, $F\le 240$ | repair.py:320 |
| Polish (move-based soft, opt-in) | remaining `repair_time_limit_s` budget | $O(1)$ | soft_search.py:anneal_soft |

- **Greedy construction** checks each candidate with `free_to_place` ($O(\ell\iota)$) and, with
  soft-shaping on, `_soft_score` ($O(\ell)$) — repair.py:99-154. Linear overall.
- **The decisive property:** `BATCH = 30` and `MAX_FREE = 240` (repair.py:157-159) cap every
  CP-SAT call to a neighbourhood of **≤240 blocks regardless of $B$**. The live model each
  round is therefore $O(1)$ in the roster — its build time, memory, and per-solve cost do not
  grow with the school. Each round is bounded by `REPAIR_TL`=12 s over `CPSAT_MAX_WORKERS`
  (default 8; repair.py:399-401). The sweep count is bounded (≤25, plus a `gained==0` early exit), so the
  total is $O(B)$ rounds, the whole loop hard-capped by the `repair_time_limit_s` deadline
  (repair.py:482, 492, 497).

**Monolith vs repair, stated as complexity:** the monolith solves **one $\Theta(B)$
NP-hard model** (UNKNOWN at full size); repair solves **many $O(1)$-sized NP-hard models**
(each trivially small and time-boxed at 12 s). That is exactly why repair scales where the
  monolith does not. The preserved full-roster benchmark uses a 300 s single-worker budget:
**Fall 303 s / 97.1 %, Spring 303 s / 92.6 %, both 0 genuine resource conflicts** (§7).

### 10.5 Space summary

- **Monolith:** $O(BP\ell\iota)$ model + CP-SAT internals — the ≥4 GiB RAM floor.
- **Repair:** $O(BP)$ for `cand_by_block` + $O(B\ell\iota)$ for the `State` occupancy dicts
  (`room_owner` / `instr_slot` / `sect_slot` / `cohort_slot_courses`, repair.py:17-97), and a
  **bounded $O(1)$ live mini-model**. So repair's *peak solver memory is independent of $B$* —
  the second reason it is the production path.
- **Block derivation** (`build_sections` / `blocks_from_tpl`, derive.py): $O(S)$ time, $O(B)$
  output. Negligible.
- **Validation** (`validate.py`, §8) re-derives violations from the assignment list by
  bucketing into resource-slot maps: $O(A\ell\iota)$ time over $A=O(B)$ assignments, $O(B)$
  space. Linear, no solver state.

### 10.6 At a glance

| | Monolith | Repair |
|---|---|---|
| Deterministic build time | $O(BP\ell\iota)$ | $O(BP\ell\iota+B\log B)$ |
| Variables | $O(BP)$, one model | $O(BP)$ stored, **$O(1)$ live** |
| Search | one NP-hard $\Theta(B)$ model, $\le$ `solve_time_limit_s` | $O(B)$ NP-hard **$O(1)$** models, each $\le$12 s, all $\le$ `repair_time_limit_s` |
| Peak solver RAM | $\propto B$ (≥4 GiB floor) | $\propto B$ stored + **$O(1)$ live** |
| Full-period outcome | UNKNOWN (~367 k vars) | 97.1 % / 92.6 % in the 300 s single-worker benchmark, 0 genuine resource conflicts |

**Bottom line:** deterministic work is **linear in the roster**; the **NP-hard search is
confined** — to a *time* box in the monolith, and additionally to a *size* box ($O(1)$
neighbourhoods) in repair. Candidate pruning buys the linear model; bounded neighbourhoods
buy the scalable solve.

## 11. Comparison with existing timetable

**Existing** columns are parsed from the `Schedule` field in the Grades CSVs
(`data/2025-01-Grades.csv` / `data/2025-02-Grades.csv`) and re-validated with the KAIROS
validator. The preserved comparison artifacts are not all the same scope: `out/mode_b_001.json`
is the full Fall Mode-B comparison, while `out/mode_b_002.json` is a Spring departmental-scope
run. Treat Spring KAIROS ratios there as representative, not full-period absolute counts.

| Metric | Existing · Fall 001 | KAIROS · Fall 001 | Existing · Spring 002 | KAIROS · Spring 002 |
| --- | --- | --- | --- | --- |
| Blocks scheduled / total | 1 232 / 1 708 | 1 588 / 1 708 | 1 231 / — | 446 / —² |
| Coverage | 72 % | **93 %** | — | —² |
| Hard/resource violations (total) | 1 006 | **0 resource** / 120 placement | 981 | **0 resource** / 575 placement² |
| — Room conflicts | 325 | 0 | 318 | 0 |
| — Instructor conflicts | 522 | 0 | 534 | 0 |
| — Window violations (>18:00) | 91 | 0 | 92 | 0 |
| — Blackout violations | 0 | 0 | 37 | 0 |
| — Capacity overflows | 6 | 0 | 0 | 0 |
| — Split-day violations | 62 | 0 | — | 0 |
| Rooms used | 248 | **94** | 218 | 53² |
| Room fill rate | 50.3 % | **70.8 %** | 53.1 % | 71.4 %² |
| Evening blocks ratio | 22.2 % | **12.6 %** | 24.2 % | 7.8 %² |
| Cohort conflicts (soft) | 549 | **370** | 584 | 100² |
| Solve time | manual | artifact-specific | manual | artifact-specific² |

² `out/mode_b_002.json` mode\_a is a departmental-scope run; ratios are representative, absolute
counts are not full-period.

**Key takeaways:**

- **Resource conflicts drop from ~1 000 → 0:** the existing timetable has hundreds of room
  overlaps, instructor double-bookings, and window violations; KAIROS eliminates resource
  clashes by construction (candidate pruning ensures only legal placements enter the model;
  hard constraints H1–H3 / H_self prevent residual overlaps). Under time budgets, unplaced
  tails are reported separately as `placement` violations.
- **Coverage rises from ~72 % → ≥93 %:** the Grades CSV leaves many blocks without a `Schedule`
  entry; the repair solver fills them within the same wall-clock budget.
- **Room utilisation improves by ~20 pp:** 248 → 94 rooms at 50 % → 71 % fill — fewer rooms
  used, each more efficiently.
- **Evening load falls** (22 % → 13 %): the undergrad end-of-day cap (default 18:00) is a hard
  candidate-pruning rule, so daytime placements are preferred by construction.
- **Cohort conflicts decrease:** the soft cohort-conflict weight penalises same-cohort
  simultaneous offerings, reducing student scheduling pressure (Fall: 549 → 370).
