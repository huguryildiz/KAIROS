# UCTP Phase 2 — Model Fidelity & Full-Scale Solving — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the four Phase-1 modeling limitations (cohort over-constraint, long blocks, team-taught sections, oversize sections), add four soft preferences (cohort daily-compactness, S-Order, S-EngLab, non-adjacent split days), then solve the full 001/002 periods and calibrate.

**Architecture:** Same pipeline (`io_csv → clean → join → derive → model_cpsat → validate → report → export`, driven by `__main__`). Hard constraints stay split between candidate pruning and a few explicit CP-SAT relations; the independent `validate.py` re-derives every hard violation. Phase 2 edits the cohort relation (→ course level), block derivation (→ splitting), the instructor model (→ list), the room master (→ large halls), and adds soft objective terms; plus a faculty-decomposition driver for full-scale solving.

**Tech Stack:** Python 3.9 (Anaconda), pandas, OR-Tools CP-SAT (`ortools`), pytest.

## Global Constraints

- **Quote-aware CSV only**; all columns `dtype=str`; convert numerics via `textnorm.parse_int`. Never `split(",")` on CSV rows.
- **`PYTHONPATH=src`** for any direct `python3 -m timetabling` / ad-hoc run (pytest gets it from `pyproject.toml`).
- **`rules.pdf` Article 1 stays IGNORED** — free block splitting allowed.
- **Soft terms never prune candidates** and never make a feasible instance infeasible; all weights live in `config.Config`.
- **Independent validator must report 0 hard violations** on every solved scope.
- **`schedule_<period>.json` field set stays stable** (UI contract): per-assignment keys unchanged.
- **Cohort key format is `f"{dept_code}-{year}"`** (year is the suffix after the last `-`).
- **Commits go to `main`** (no PRs, no feature branches). Each task ends with a commit.
- **Authoritative design:** [docs/superpowers/specs/2026-06-19-uctp-phase2-design.md](../specs/2026-06-19-uctp-phase2-design.md) and [docs/superpowers/specs/2026-06-19-soft-ordering-and-eng-labs-design.md](../specs/2026-06-19-soft-ordering-and-eng-labs-design.md).

**Known data facts to assert against (period 001 unless noted):**
- 793 undergrad sections (001), 801 (002). Max physical room cap = 100.
- 16 oversize sections (001, max TEDU 101 = 497); 8 (002, max TUR 102 = 434).
- 7 engineering departments; substring `"Engineering"` matches all. `faculty="Computer Engineering"` → 61 sections (18 with a lab).

---

## File Structure

| File | Phase-2 responsibility |
|---|---|
| `src/timetabling/config.py` | New params (Task 1) |
| `src/timetabling/clean.py` | Append large halls to room master (Task 2) |
| `src/timetabling/textnorm.py` | `normalize_staff_ids` comma-split (Task 3) |
| `src/timetabling/model.py` | `Section.instructor_ids: list[str]` (Task 3) |
| `src/timetabling/join.py` | Keep comma-joined normalized ids (Task 3) |
| `src/timetabling/derive.py` | Multi-instructor + split blocks (Tasks 3, 6) |
| `src/timetabling/model_cpsat.py` | Multi-instr, H_self, course-cohort, kind fix, soft terms (Tasks 3–10) |
| `src/timetabling/validate.py` | Multi-instr, self-overlap, course-cohort, kind fix (Tasks 3–6) |
| `src/timetabling/export.py` | Joined instructor names (Task 3) |
| `src/timetabling/decompose.py` | **New** — faculty decomposition driver (Task 11) |
| `src/timetabling/report.py` | `room_fill` metric (Task 12) |
| `src/timetabling/__main__.py` | `--decompose` flag (Task 11); results runs (Task 13) |

---

### Task 1: Config — new Phase 2 parameters

**Files:**
- Modify: `src/timetabling/config.py`
- Test: `tests/test_config_phase2.py`

**Interfaces:**
- Produces (new `Config` fields): `max_block_len:int=4`, `extra_rooms:tuple=((500,2),(250,3),(150,4))`, `compact_cohort_years:tuple=(2,3,4)`, `w_cohort_gap:int=3`, `w_order:int=1`, `w_englab:int=1`, `eng_lab_days:tuple=("Th","Fr")`, `eng_faculty_match:str="Engineering"`, `w_nonadjacent:int=0`.

- [ ] **Step 1: Write the failing test `tests/test_config_phase2.py`**

```python
from timetabling.config import Config

def test_phase2_defaults():
    c = Config()
    assert c.max_block_len == 4
    assert c.extra_rooms == ((500, 2), (250, 3), (150, 4))
    assert c.compact_cohort_years == (2, 3, 4)
    assert c.w_cohort_gap == 3
    assert c.w_order == 1
    assert c.w_englab == 1
    assert c.eng_lab_days == ("Th", "Fr")
    assert c.eng_faculty_match == "Engineering"
    assert c.w_nonadjacent == 0

def test_phase2_overridable():
    c = Config(max_block_len=3, w_cohort_gap=0)
    assert c.max_block_len == 3 and c.w_cohort_gap == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_config_phase2.py -v`
Expected: FAIL with `AttributeError`/`assert` on `max_block_len`.

- [ ] **Step 3: Add the fields to `src/timetabling/config.py`**

Insert these lines inside `@dataclass class Config`, immediately after the existing
`max_rooms_per_block: int = 12` line:

```python
    # phase 2: block splitting
    max_block_len: int = 4
    # phase 2: oversize -> synthetic large halls, list of (cap, count)
    extra_rooms: tuple = ((500, 2), (250, 3), (150, 4))
    # phase 2: cohort daily-compactness applies to these year levels
    compact_cohort_years: tuple = (2, 3, 4)
    # phase 2 soft weights
    w_cohort_gap: int = 3
    w_order: int = 1
    w_englab: int = 1
    eng_lab_days: tuple = ("Th", "Fr")
    eng_faculty_match: str = "Engineering"
    w_nonadjacent: int = 0
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_config_phase2.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/config.py tests/test_config_phase2.py
git commit -m "feat: add Phase 2 config parameters"
```

---

### Task 2: Large lecture halls (oversize, TODO 2.4)

**Files:**
- Modify: `src/timetabling/clean.py` (`build_rooms`)
- Test: `tests/test_clean_halls.py`

**Interfaces:**
- Consumes: `config.Config.extra_rooms`, `config.Config.online_room`.
- Produces: `build_rooms` returns the 101 CSV rooms **plus** synthetic halls named `AMFI-<cap>-<i>` (1-based), each `Room(name, cap, is_lab=False, is_physical=True)`.

- [ ] **Step 1: Write the failing test `tests/test_clean_halls.py`**

```python
from timetabling import io_csv, clean
from timetabling.config import Config

def test_extra_halls_added():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    names = [r for r in rooms if r.startswith("AMFI-")]
    assert len(names) == 2 + 3 + 4                  # (500,2)+(250,3)+(150,4)
    assert rooms["AMFI-500-1"].cap == 500
    assert rooms["AMFI-500-1"].is_physical and not rooms["AMFI-500-1"].is_lab
    assert sum(1 for n in names if rooms[n].cap == 250) == 3

def test_no_extra_halls_when_empty():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config(extra_rooms=()))
    assert not any(n.startswith("AMFI-") for n in rooms)

def test_largest_hall_fits_max_section():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    assert max(r.cap for r in rooms.values()) >= 497
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_clean_halls.py -v`
Expected: FAIL (no `AMFI-*` rooms).

- [ ] **Step 3: Append halls in `src/timetabling/clean.py`**

At the end of `build_rooms`, replace the final `return rooms` with:

```python
    for cap, count in cfg.extra_rooms:
        for i in range(1, count + 1):
            name = f"AMFI-{cap}-{i}"
            rooms[name] = Room(room=name, cap=int(cap), is_lab=False, is_physical=True)
    return rooms
```

- [ ] **Step 4: Update the existing `test_clean.py` physical-count assertion**

Adding 9 halls makes `Config()`-built physical rooms 109, so
`test_clean.py::test_build_rooms_marks_online_nonphysical_and_lab_count` will fail on
`assert len(physical) == 100`. Make it robust by excluding the synthetic halls. Replace:

```python
    physical = [r for r in rooms.values() if r.is_physical]
    assert len(physical) == 100                      # 101 total - 1 online
```

with:

```python
    physical = [r for r in rooms.values() if r.is_physical and not r.room.startswith("AMFI-")]
    assert len(physical) == 100                      # 101 CSV rooms - 1 online (excl. synthetic halls)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_clean_halls.py tests/test_clean.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/timetabling/clean.py tests/test_clean_halls.py tests/test_clean.py
git commit -m "feat: add synthetic large lecture halls for oversize sections (2.4)"
```

---

### Task 3: Team-taught sections — `instructor_ids` list (TODO 2.3)

**Files:**
- Modify: `src/timetabling/textnorm.py`, `src/timetabling/model.py`, `src/timetabling/derive.py`, `src/timetabling/model_cpsat.py`, `src/timetabling/validate.py`, `src/timetabling/export.py`
- Modify (tests): `tests/test_scaffold.py`, `tests/test_model_cpsat.py`, `tests/test_validate.py`
- Test (new): `tests/test_textnorm.py` (add cases), `tests/test_team_taught.py`

**Interfaces:**
- Produces: `textnorm.normalize_staff_ids(s) -> list[str]`; `model.Section.instructor_ids: list[str]` (replaces `instructor_id`); `model_cpsat.gen_candidates(block, section, instructors_list, rooms, cfg)` and `split_roomable` use a **list** of `Instructor`. `build_and_solve`/`validate` signatures unchanged (still take the `instructors` dict).
- Consumes: callers iterate `section.instructor_ids`.

- [ ] **Step 1: Add the failing `normalize_staff_ids` test to `tests/test_textnorm.py`**

```python
from timetabling.textnorm import normalize_staff_ids

def test_normalize_staff_ids_splits_and_cleans():
    assert normalize_staff_ids("00003893,00002022") == ["00003893", "00002022"]
    assert normalize_staff_ids("00005657 (S)") == ["00005657"]
    assert normalize_staff_ids(" 00006729 , 00007000 (S) ") == ["00006729", "00007000"]
    assert normalize_staff_ids("") == []
    assert normalize_staff_ids(None) == []
```

- [ ] **Step 2: Run it to verify failure**

Run: `python3 -m pytest tests/test_textnorm.py -v`
Expected: FAIL with `ImportError: cannot import name 'normalize_staff_ids'`.

- [ ] **Step 3: Implement `normalize_staff_ids` in `src/timetabling/textnorm.py`**

Add at the end of the file:

```python
def normalize_staff_ids(s) -> list:
    """Split a comma-joined Staff ID cell into a list of normalized ids.
    Drops blanks; reuses normalize_staff_id for (S)/whitespace handling."""
    if s is None:
        return []
    out = []
    for part in str(s).split(","):
        sid = normalize_staff_id(part)
        if sid:
            out.append(sid)
    return out
```

- [ ] **Step 4: Run to verify pass**

Run: `python3 -m pytest tests/test_textnorm.py -v`
Expected: all pass.

- [ ] **Step 5: Write the failing end-to-end team-taught test `tests/test_team_taught.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat, validate

def _sec(sid, instr_ids, blocks, cohort="D-1", level=1, students=10, faculty="Fac"):
    s = Section(sid, "001", "D 101", "n", level, "D", faculty, cohort, instr_ids,
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_both_co_instructors_enter_conflict():
    cfg = Config()
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instructors = {"i1": Instructor("i1", "Ann", False, "D"),
                   "i2": Instructor("i2", "Bob", False, "D")}
    # s1 taught by (i1,i2); s2 taught by i2 alone, different cohort -> i2 shared
    s1 = _sec("S1_01", ["i1", "i2"], [Block("S1_01#T", "S1_01", "theory", 1, False)], cohort="D-1")
    s2 = _sec("S2_01", ["i2"], [Block("S2_01#T", "S2_01", "theory", 1, False)], cohort="E-1")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instructors, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    a = {x.section_id: x for x in assigns}
    # shared instructor i2 -> the two sections cannot occupy the same (day, hour)
    assert not (a["S1_01"].day == a["S2_01"].day and a["S1_01"].start == a["S2_01"].start)
    assert validate.validate(assigns, [s1, s2], {r.room: r for r in rooms}, instructors, cfg) == []

def test_seminar_blackout_if_any_coinstructor_fulltime():
    cfg = Config()
    rooms = [Room("R1", 50, False, True)]
    instructors = {"f": Instructor("f", "Full", True, "D"), "p": Instructor("p", "Part", False, "D")}
    s = _sec("S_01", ["p", "f"], [Block("S_01#T", "S_01", "theory", 1, False)])
    cands = model_cpsat.gen_candidates(s.blocks[0], s,
                                       [instructors["p"], instructors["f"]], rooms, cfg)
    assert not any(c.day == "Th" and c.start in (14, 15) for c in cands)
```

- [ ] **Step 6: Run it to verify failure**

Run: `python3 -m pytest tests/test_team_taught.py -v`
Expected: FAIL (Section has no `instructor_ids`; `gen_candidates` signature mismatch).

- [ ] **Step 7: Rename the model field in `src/timetabling/model.py`**

In `@dataclass class Section`, replace `instructor_id: str` with:

```python
    instructor_ids: List[str]
```

- [ ] **Step 8: Populate it in `src/timetabling/derive.py`**

At the top imports, change `from .textnorm import parse_int` to:

```python
from .textnorm import parse_int, normalize_staff_ids
```

In `build_sections`, replace `instructor_id=r.get("staff_id", "").strip(),` with:

```python
            instructor_ids=normalize_staff_ids(r.get("staff_id", "")),
```

(`join.build_section_frame` already stores `staff_id` via `normalize_staff_id`, which preserves the comma between two ids; `normalize_staff_ids` splits it.)

- [ ] **Step 9: Update `src/timetabling/model_cpsat.py` for multi-instructor**

Replace `_blackout_hours` and `gen_candidates`/`split_roomable` headers and bodies with:

```python
def _blackout_hours(instructors, cfg: Config):
    closed = set(cfg.friday_blackout)
    if any(ins.is_staff for ins in instructors):
        closed |= set(cfg.seminar_blackout)
    return closed


def feasible_rooms_for(block: Block, section: Section, rooms: List[Room],
                       cfg: Config) -> List[Room]:
    fr = [
        r for r in rooms
        if r.is_physical and r.cap >= section.students and (r.is_lab if block.needs_lab else True)
    ]
    fr.sort(key=lambda r: (r.cap, r.room))
    return fr[:cfg.max_rooms_per_block]


def _instructors_of(section: Section, instructors: Dict[str, Instructor]) -> List[Instructor]:
    default = Instructor("", "", False, "")
    return [instructors.get(i, default) for i in section.instructor_ids] or [default]


def split_roomable(sections, rooms, cfg, instructors=None):
    instructors = instructors or {}
    roomable, excluded = [], []
    for s in sections:
        ins_list = _instructors_of(s, instructors)
        issues = []
        for b in s.blocks:
            if gen_candidates(b, s, ins_list, rooms, cfg):
                continue
            if not feasible_rooms_for(b, s, rooms, cfg):
                issues.append([b.block_id, "no room with sufficient capacity"])
            else:
                issues.append([b.block_id, "block longer than daily time window"])
        if issues:
            excluded.append({"section_id": s.section_id, "students": s.students, "issues": issues})
        else:
            roomable.append(s)
    return roomable, excluded


def gen_candidates(block: Block, section: Section, instructors: List[Instructor],
                   rooms: List[Room], cfg: Config) -> List[Candidate]:
    end_cap = cfg.undergrad_end if section.level <= 4 else cfg.grad_end
    start_lo = cfg.horizon_start if section.level <= 4 else cfg.grad_start
    closed = _blackout_hours(instructors, cfg)
    feasible_rooms = feasible_rooms_for(block, section, rooms, cfg)
    cands: List[Candidate] = []
    for r in feasible_rooms:
        for d in cfg.days():
            for h in range(start_lo, end_cap - block.length + 1):
                span = range(h, h + block.length)
                if any((d, hh) in closed for hh in span):
                    continue
                cands.append(Candidate(block.block_id, r.room, d, h, block.length))
    return cands
```

In `build_and_solve`, replace the candidate-loop instructor handling. Change:

```python
    for b, s in blocks:
        ins = instructors.get(s.instructor_id, default_instr)
        cands = gen_candidates(b, s, ins, rooms, cfg)
```

to:

```python
    for b, s in blocks:
        ins_list = _instructors_of(s, instructors)
        cands = gen_candidates(b, s, ins_list, rooms, cfg)
```

And inside the per-hour loop, replace `instr_occ[(s.instructor_id, c.day, hh)].append(v)` with:

```python
                for iid in s.instructor_ids:
                    instr_occ[(iid, c.day, hh)].append(v)
```

And replace `instr_day_vars[(s.instructor_id, c.day)].append(v)` with:

```python
            for iid in s.instructor_ids:
                instr_day_vars[(iid, c.day)].append(v)
```

(The objective loop `for (iid, day), d in instr_day.items(): ins = instructors.get(iid, default_instr)` is unchanged.)

- [ ] **Step 10: Update `src/timetabling/validate.py` for multi-instructor**

Replace the single-instructor block. Change:

```python
        ins = instructors.get(s.instructor_id, Instructor("", "", False, ""))
        closed = set(closed_all)
        if ins.is_staff:
            closed |= set(cfg.seminar_blackout)
```

to:

```python
        ins_list = [instructors.get(i, Instructor("", "", False, "")) for i in s.instructor_ids]
        closed = set(closed_all)
        if any(ins.is_staff for ins in ins_list):
            closed |= set(cfg.seminar_blackout)
```

And in the occupancy loop, replace `instr_occ[(s.instructor_id, a.day, hh)].append(a.block_id)` with:

```python
            for iid in s.instructor_ids:
                instr_occ[(iid, a.day, hh)].append(a.block_id)
```

- [ ] **Step 11: Update `src/timetabling/export.py` for joined names**

Replace the `ins = ...` line and the two instructor fields in `build_schedule_dict`. Change:

```python
        ins = instructors.get(s.instructor_id) if s else None
```

to:

```python
        ids = s.instructor_ids if s else []
        names = [instructors[i].name for i in ids if i in instructors and instructors[i].name]
```

and change the two dict entries:

```python
            "instructor_id": ",".join(ids),
            "instructor_name": " & ".join(names),
```

- [ ] **Step 12: Fix existing tests that construct `Section` directly**

In `tests/test_scaffold.py::test_model_dataclasses`, change the 9th positional arg `"id"` to `["id"]`:

```python
    s = Section("X_01", "001", "X 101", "n", 1, "X", "Fac", "X-1", ["id"], 30,
                3, 0, 0, 3, "Course")
```

In `tests/test_model_cpsat.py`, update the `_sec` helper so the instructor arg is a list and gen_candidates calls pass a list:

```python
def _sec(sid, level, students, blocks, instr="i1", cohort="D-1"):
    s = Section(sid, "001", "D 101", "n", level, "D", "Fac", cohort, [instr],
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s
```

Then in the three `gen_candidates(...)` calls in that file, wrap the instructor in a list:
`model_cpsat.gen_candidates(b, s, [instr], rooms, cfg)`,
`model_cpsat.gen_candidates(b, s, [full], rooms, cfg)`,
`model_cpsat.gen_candidates(b, s, [part], rooms, cfg)`.

In `tests/test_validate.py`, update the `_sec` helper the same way (instructor arg → `[instr]`).

- [ ] **Step 13: Run the full suite**

Run: `python3 -m pytest -q`
Expected: all pass (including `tests/test_team_taught.py`, `tests/test_derive.py`).
If `tests/test_derive.py` references `instructor_id`, add/adjust an assertion to `instructor_ids` (e.g. a known team-taught section yields ≥2 ids); otherwise leave it.

- [ ] **Step 14: Commit**

```bash
git add src/timetabling tests
git commit -m "feat: team-taught sections via instructor_ids list (2.3)"
```

---

### Task 4: Section-internal non-overlap (H_self)

**Files:**
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve`), `src/timetabling/validate.py`
- Test: `tests/test_self_overlap.py`

**Interfaces:**
- Produces: a section's blocks never share a `(day, hour)`; validator emits `Violation("self", ...)` on overlap.

- [ ] **Step 1: Write the failing test `tests/test_self_overlap.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import model_cpsat, validate

ROOMS = {"R1": Room("R1", 50, False, True), "R2": Room("R2", 50, False, True)}
INSTR = {"i1": Instructor("i1", "n", False, "D")}

def _sec(blocks):
    s = Section("S_01", "001", "D 101", "n", 1, "D", "Fac", "D-1", ["i1"],
                10, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_validator_flags_self_overlap():
    s = _sec([Block("S_01#T1", "S_01", "theory", 2, False),
              Block("S_01#T2", "S_01", "theory", 2, False)])
    a = [Assignment("S_01#T1", "S_01", "theory", "R1", "Mo", 9, 11),
         Assignment("S_01#T2", "S_01", "theory", "R2", "Mo", 10, 12)]
    kinds = {v.kind for v in validate.validate(a, [s], ROOMS, INSTR, Config())}
    assert "self" in kinds

def test_solver_keeps_section_blocks_disjoint():
    s = _sec([Block("S_01#T1", "S_01", "theory", 1, False),
              Block("S_01#T2", "S_01", "theory", 1, False)])
    assigns, stats = model_cpsat.build_and_solve([s], list(ROOMS.values()), INSTR, Config())
    assert len(assigns) == 2
    a1, a2 = assigns
    assert not (a1.day == a2.day and a1.start == a2.start)
    assert validate.validate(assigns, [s], ROOMS, INSTR, Config()) == []
```

- [ ] **Step 2: Run it to verify failure**

Run: `python3 -m pytest tests/test_self_overlap.py -v`
Expected: FAIL (`"self"` not in kinds; solver may overlap the two blocks).

- [ ] **Step 3: Add `section_occ` in `src/timetabling/model_cpsat.py`**

In `build_and_solve`, add a new occupancy map next to the others (after `cohort_occ = defaultdict(list)`):

```python
    section_occ = defaultdict(list)  # (section_id, day, hour) -> vars
```

Inside the per-hour loop (alongside `room_occ[...]`), add:

```python
                section_occ[(s.section_id, c.day, hh)].append(v)
```

In the no-overlap constraints block, add `section_occ` to the iterated maps:

```python
    for occ in (room_occ, instr_occ, cohort_occ, section_occ):
        for key, vs in occ.items():
            if len(vs) > 1:
                model.Add(sum(vs) <= 1)
```

- [ ] **Step 4: Add the self-overlap check in `src/timetabling/validate.py`**

Add a `section_occ` map (next to `room_occ`/`instr_occ`/`cohort_occ`):

```python
    section_occ = defaultdict(list)
```

In the occupancy loop add:

```python
            section_occ[(a.section_id, a.day, hh)].append(a.block_id)
```

After the cohort loop, add:

```python
    for (sid, day, hh), bids in section_occ.items():
        if len(set(bids)) > 1:
            viol.append(Violation("self", f"section {sid} self-overlap {day} {hh}:00 by {bids}"))
```

- [ ] **Step 5: Run tests**

Run: `python3 -m pytest tests/test_self_overlap.py tests/test_validate.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/timetabling/model_cpsat.py src/timetabling/validate.py tests/test_self_overlap.py
git commit -m "feat: explicit section-internal non-overlap (H_self)"
```

---

### Task 5: Course-level cohort constraint (TODO 2.1)

**Files:**
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve`), `src/timetabling/validate.py`
- Test: `tests/test_course_cohort.py`

**Interfaces:**
- Produces: at most one **distinct course code** per `(cohort, day, hour)`; same-course sections may overlap. Validator emits `Violation("cohort", ...)` only when ≥2 distinct course codes share a `(cohort, day, hour)`.
- Replaces the Phase-1 `cohort_occ ≤ 1` relation. Requires `Section.code` (already present).

- [ ] **Step 1: Write the failing test `tests/test_course_cohort.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import model_cpsat, validate

ROOMS = {"R1": Room("R1", 50, False, True), "R2": Room("R2", 50, False, True)}

def _sec(sid, code, instr, blocks, cohort="D-1"):
    s = Section(sid, "001", code, "n", 1, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_same_course_parallel_allowed_by_validator():
    s1 = _sec("C101_01", "C 101", "i1", [Block("C101_01#T", "C101_01", "theory", 1, False)])
    s2 = _sec("C101_02", "C 101", "i2", [Block("C101_02#T", "C101_02", "theory", 1, False)])
    a = [Assignment("C101_01#T", "C101_01", "theory", "R1", "Mo", 9, 10),
         Assignment("C101_02#T", "C101_02", "theory", "R2", "Mo", 9, 10)]
    instr = {"i1": Instructor("i1", "n", False, "D"), "i2": Instructor("i2", "n", False, "D")}
    assert validate.validate(a, [s1, s2], ROOMS, instr, Config()) == []

def test_different_courses_same_cohort_conflict():
    s1 = _sec("C101_01", "C 101", "i1", [Block("C101_01#T", "C101_01", "theory", 1, False)])
    s2 = _sec("C201_01", "C 201", "i2", [Block("C201_01#T", "C201_01", "theory", 1, False)])
    a = [Assignment("C101_01#T", "C101_01", "theory", "R1", "Mo", 9, 10),
         Assignment("C201_01#T", "C201_01", "theory", "R2", "Mo", 9, 10)]
    instr = {"i1": Instructor("i1", "n", False, "D"), "i2": Instructor("i2", "n", False, "D")}
    kinds = {v.kind for v in validate.validate(a, [s1, s2], ROOMS, instr, Config())}
    assert "cohort" in kinds

def test_solver_allows_same_course_parallel():
    # two sections of the same course, same cohort, different instructors, only 1 free
    # day-hour each so they MUST go parallel -> feasible only if course-level cohort allows it
    cfg = Config()
    s1 = _sec("C101_01", "C 101", "i1", [Block("C101_01#T", "C101_01", "theory", 9, False)])
    s2 = _sec("C101_02", "C 101", "i2", [Block("C101_02#T", "C101_02", "theory", 9, False)])
    instr = {"i1": Instructor("i1", "n", False, "D"), "i2": Instructor("i2", "n", False, "D")}
    assigns, stats = model_cpsat.build_and_solve([s1, s2], list(ROOMS.values()), instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE") and len(assigns) == 2
    assert validate.validate(assigns, [s1, s2], ROOMS, instr, cfg) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_course_cohort.py -v`
Expected: FAIL — Phase-1 validator flags same-course parallel as a `cohort` conflict.

- [ ] **Step 3: Replace the cohort relation in `src/timetabling/model_cpsat.py`**

Remove the `cohort_occ` map and its per-hour append, and the `cohort_occ` entry in the
`for occ in (...)` loop. Replace them with a per-`(cohort, course)` busy structure.

Replace the declaration line `cohort_occ = defaultdict(list)   # (cohort, day, hour) -> vars` with:

```python
    cohort_course_occ = defaultdict(list)  # (cohort, course, day, hour) -> vars
```

Replace the per-hour append `cohort_occ[(s.cohort_key, c.day, hh)].append(v)` with:

```python
                cohort_course_occ[(s.cohort_key, s.code, c.day, hh)].append(v)
```

Change the no-overlap loop back to the three slot maps only (drop `cohort_occ`):

```python
    for occ in (room_occ, instr_occ, section_occ):
        for key, vs in occ.items():
            if len(vs) > 1:
                model.Add(sum(vs) <= 1)
```

After that loop, add the course-level cohort relation:

```python
    # H4 (course-level): at most one distinct course code per (cohort, day, hour)
    course_busy = {}
    slot_courses = defaultdict(list)  # (cohort, day, hour) -> [busy vars]
    for (cohort, course, day, hh), vs in cohort_course_occ.items():
        b = model.NewBoolVar(f"busy|{cohort}|{course}|{day}|{hh}")
        model.AddMaxEquality(b, vs)               # b = OR(vs)
        course_busy[(cohort, course, day, hh)] = b
        slot_courses[(cohort, day, hh)].append(b)
    for (cohort, day, hh), busies in slot_courses.items():
        if len(busies) > 1:                        # >=2 distinct courses can contend
            model.Add(sum(busies) <= 1)
```

- [ ] **Step 4: Replace the cohort check in `src/timetabling/validate.py`**

Change the cohort occupancy to record `(section, course)` and flag on distinct course codes.
Replace `cohort_occ[(s.cohort_key, a.day, hh)].append(a.block_id)` with:

```python
            cohort_occ[(s.cohort_key, a.day, hh)].append(s.code)
```

Replace the cohort reporting loop:

```python
    for (cohort, day, hh), bids in cohort_occ.items():
        if len(set(b.split('#')[0] for b in bids)) > 1:
            viol.append(Violation("cohort", f"cohort {cohort} double-booked {day} {hh}:00 by {bids}"))
```

with:

```python
    for (cohort, day, hh), codes in cohort_occ.items():
        if len(set(codes)) > 1:
            viol.append(Violation("cohort",
                        f"cohort {cohort} has {sorted(set(codes))} at {day} {hh}:00"))
```

- [ ] **Step 5: Fix the now-stale `test_validate.py` cohort test**

`test_detects_instructor_and_cohort_conflict` builds both sections with the helper's hardcoded
`code="D 101"`. Under course-level cohort, identical codes are NOT a cohort conflict, so its
`assert "cohort" in kinds` would fail. Give the helper a `code` param and pass distinct codes.

In `tests/test_validate.py`, change the `_sec` helper signature/line to accept `code`:

```python
def _sec(sid, level, students, blocks, instr="i1", cohort="D-1", code="D 101"):
    s = Section(sid, "001", code, "n", level, "D", "Fac", cohort, [instr],
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s
```

In `test_detects_instructor_and_cohort_conflict`, give the two sections distinct codes (same
cohort, same instructor) so both the instructor and cohort paths fire:

```python
    s1 = _sec("S1_01", 1, 10, [Block("S1_01#T", "S1_01", "theory", 1, False)],
              instr="i1", cohort="D-1", code="D 101")
    s2 = _sec("S2_01", 1, 10, [Block("S2_01#T", "S2_01", "theory", 1, False)],
              instr="i1", cohort="D-1", code="D 202")
```

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_course_cohort.py tests/test_validate.py tests/test_model_cpsat.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add src/timetabling/model_cpsat.py src/timetabling/validate.py tests/test_course_cohort.py tests/test_validate.py
git commit -m "feat: course-level cohort constraint (2.1)"
```

---

### Task 6: Split long blocks across days (TODO 2.2)

**Files:**
- Modify: `src/timetabling/derive.py` (`blocks_from_tpl`, `build_sections`), `src/timetabling/model_cpsat.py` (kind detection), `src/timetabling/validate.py` (none if kind comes from `Assignment`), `tests/test_derive.py`
- Test: `tests/test_split_blocks.py`

**Interfaces:**
- Produces: `blocks_from_tpl(section_id, T, P, L, Cr, max_block_len)` — a load `> max_block_len` becomes `ceil(load/max_block_len)` near-equal blocks; single blocks keep ids `#T`/`#L`, split blocks get `#T1..#Tk` / `#L1..#Lk`. Kind detection becomes `"#L" in block_id`.

- [ ] **Step 1: Write the failing test `tests/test_split_blocks.py`**

```python
from timetabling.config import Config
from timetabling.model import Room, Instructor
from timetabling import derive, model_cpsat, validate

def test_single_block_keeps_plain_id():
    bs = derive.blocks_from_tpl("S_01", 3, 0, 0, 3, max_block_len=4)
    assert [b.block_id for b in bs] == ["S_01#T"]

def test_long_theory_splits_evenly():
    bs = derive.blocks_from_tpl("S_01", 10, 0, 0, 0, max_block_len=4)
    lens = sorted(b.length for b in bs)
    assert lens == [3, 3, 4]                      # 10 over 3 blocks
    assert all(b.kind == "theory" and not b.needs_lab for b in bs)
    assert [b.block_id for b in bs] == ["S_01#T1", "S_01#T2", "S_01#T3"]

def test_long_lab_splits_and_marks_lab():
    bs = derive.blocks_from_tpl("S_01", 0, 0, 6, 0, max_block_len=4)
    labs = [b for b in bs if b.needs_lab]
    assert len(bs) == 2 and len(labs) == 2 and sorted(b.length for b in bs) == [3, 3]
    assert all("#L" in b.block_id for b in bs)

def test_split_section_solves_clean():
    cfg = Config()
    rooms = [Room("R1", 50, False, True)]
    instr = {"i1": Instructor("i1", "n", False, "D")}
    from timetabling.model import Section
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["i1"],
                10, 10, 0, 0, 0, "Course")
    s.blocks = derive.blocks_from_tpl("S_01", 10, 0, 0, 0, cfg.max_block_len)
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert len(assigns) == len(s.blocks) >= 3
    assert validate.validate(assigns, [s], {r.room: r for r in rooms}, instr, cfg) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_split_blocks.py -v`
Expected: FAIL (`blocks_from_tpl` takes no `max_block_len`).

- [ ] **Step 3: Rewrite `blocks_from_tpl` in `src/timetabling/derive.py`**

Replace the whole function with:

```python
def _split_lengths(total: int, max_len: int) -> List[int]:
    if total <= max_len:
        return [total]
    n = (total + max_len - 1) // max_len          # ceil
    base, extra = divmod(total, n)
    return [base + 1] * extra + [base] * (n - extra)


def _make_blocks(section_id, kind, tag, total, max_len, needs_lab) -> List[Block]:
    lens = _split_lengths(total, max_len)
    if len(lens) == 1:
        return [Block(f"{section_id}#{tag}", section_id, kind, lens[0], needs_lab)]
    return [Block(f"{section_id}#{tag}{i+1}", section_id, kind, ln, needs_lab)
            for i, ln in enumerate(lens)]


def blocks_from_tpl(section_id: str, T: int, P: int, L: int, Cr: int,
                    max_block_len: int = 4) -> List[Block]:
    blocks: List[Block] = []
    theory_len = (T or 0) + (P or 0)
    lab_len = L or 0
    if theory_len > 0:
        blocks += _make_blocks(section_id, "theory", "T", theory_len, max_block_len, False)
    if lab_len > 0:
        blocks += _make_blocks(section_id, "lab", "L", lab_len, max_block_len, True)
    if not blocks:
        default_len = Cr if (Cr and Cr > 0) else 3
        blocks += _make_blocks(section_id, "theory", "T", default_len, max_block_len, False)
    return blocks
```

`_split_lengths(10,4)` → `n=3, base=3, extra=1` → `[4,3,3]` (sorted `[3,3,4]`). Good.

- [ ] **Step 4: Pass `max_block_len` from `build_sections`**

In `build_sections`, change `blocks=blocks_from_tpl(sid, T, P, L, Cr),` to:

```python
            blocks=blocks_from_tpl(sid, T, P, L, Cr, cfg.max_block_len),
```

- [ ] **Step 5: Fix kind detection in `src/timetabling/model_cpsat.py`**

In `build_and_solve`, where assignments are built, change:

```python
                kind = "lab" if bid.endswith("#L") else "theory"
```

to:

```python
                kind = "lab" if "#L" in bid else "theory"
```

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_split_blocks.py tests/test_derive.py -v`
Expected: pass. (`test_derive.py` calls `blocks_from_tpl("S_01", 3, 0, 0, 3)` etc. without `max_block_len`; the new default `=4` keeps them valid. The `test_blocks_zero_defaults_to_three` and `theory_plus_lab` cases still hold.)

- [ ] **Step 7: Commit**

```bash
git add src/timetabling/derive.py src/timetabling/model_cpsat.py tests/test_split_blocks.py
git commit -m "feat: split long blocks across days (parametric max_block_len) (2.2)"
```

---

### Task 7: Cohort daily-compactness soft term (spec §5.5)

**Files:**
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve`)
- Test: `tests/test_cohort_gap.py`

**Interfaces:**
- Produces: a minimized `Σ gap` term over `(cohort, day)` for cohorts whose year (the suffix of `cohort_key` after the last `-`) is in `cfg.compact_cohort_years`; weight `cfg.w_cohort_gap`.

- [ ] **Step 1: Write the failing test `tests/test_cohort_gap.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat

def _sec(sid, code, instr, cohort):
    s = Section(sid, "001", code, "n", 2, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s

def test_high_gap_weight_avoids_interior_hole():
    # Close Mo-Th hours 9-11 so only Friday {9,10,11} is open; one room; two distinct-course
    # same-cohort 1h sections. They occupy 2 of {9,10,11} on Fri. A gap-blind solver may pick
    # 9 & 11 (hole at 10); with a strong gap weight the solver must pick adjacent hours.
    closed = tuple((d, h) for d in ["Mo", "Tu", "We", "Th"] for h in (9, 10, 11))
    cfg = Config(w_cohort_gap=100, w_evening=0, w_room_count=0, w_instr_days=0,
                 w_parttime_days=0, w_order=0, w_englab=0, w_nonadjacent=0,
                 horizon_start=9, undergrad_end=12, friday_blackout=closed,
                 seminar_blackout=())
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s1 = _sec("X201_01", "X 201", "a", "D-2")
    s2 = _sec("X202_01", "X 202", "b", "D-2")
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert all(a.day == "Fr" for a in assigns)
    starts = sorted(a.start for a in assigns)
    assert starts[1] - starts[0] == 1            # adjacent: no idle hour between the two classes
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_cohort_gap.py -v`
Expected: the test exists but the gap term is not yet in the objective, so the solver may return
the `9 & 11` hole and the `starts[1]-starts[0] == 1` assertion FAILs. (Add the term in Step 3.)

- [ ] **Step 3: Add the gap term in `src/timetabling/model_cpsat.py`**

In `build_and_solve`, declare a collector next to the other occupancy maps:

```python
    cohort_hour_occ = defaultdict(list)  # (cohort, day, hour) -> vars (compact cohorts only)
```

Compute the compact-year set once before the `for b, s in blocks:` loop:

```python
    compact_years = {str(y) for y in cfg.compact_cohort_years}
```

Inside the per-hour loop, after the `cohort_course_occ[...]` append, add:

```python
                if s.cohort_key.rsplit("-", 1)[-1] in compact_years:
                    cohort_hour_occ[(s.cohort_key, c.day, hh)].append(v)
```

After the course-cohort relation (Task 5 block), build the gap term:

```python
    # soft: cohort daily compactness (minimize student idle gaps)
    gap_terms = []
    ch_by_cd = defaultdict(dict)  # (cohort, day) -> {hour: active bool}
    for (cohort, day, hh), vs in cohort_hour_occ.items():
        a = model.NewBoolVar(f"chact|{cohort}|{day}|{hh}")
        model.AddMaxEquality(a, vs)
        ch_by_cd[(cohort, day)][hh] = a
    BIG = cfg.horizon_end + 1
    for (cohort, day), hourmap in ch_by_cd.items():
        hours = sorted(hourmap)
        if len(hours) < 2:
            continue
        load = sum(hourmap[h] for h in hours)
        first = model.NewIntVar(0, BIG, f"first|{cohort}|{day}")
        last = model.NewIntVar(0, BIG, f"last|{cohort}|{day}")
        model.AddMaxEquality(last, [(h + 1) * hourmap[h] for h in hours])
        model.AddMinEquality(first, [h * hourmap[h] + BIG * (1 - hourmap[h]) for h in hours])
        gap = model.NewIntVar(0, cfg.horizon_end, f"gap|{cohort}|{day}")
        model.Add(gap >= last - first - load)
        gap_terms.append(gap)
```

Then add to the objective (after the existing `obj += [...]` lines, before `if obj:`):

```python
    obj += [cfg.w_cohort_gap * g for g in gap_terms]
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_cohort_gap.py tests/test_model_cpsat.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/model_cpsat.py tests/test_cohort_gap.py
git commit -m "feat: cohort daily-compactness soft term (spec 5.5)"
```

---

### Task 8: S-Order soft term — level rises with start-hour (spec §5.7)

**Files:**
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve`)
- Test: `tests/test_s_order.py`

**Interfaces:**
- Produces: per-candidate penalty `w_order * (4 - level) * (start - horizon_start)` for `section.level ∈ {2,3,4}`.

- [ ] **Step 1: Write the failing test `tests/test_s_order.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat

def _sec(sid, code, level, instr, cohort="D-2"):
    s = Section(sid, "001", code, "n", level, "D", "Fac", cohort, [instr],
                10, 0, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s

def test_low_level_lands_earlier():
    cfg = Config(w_order=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    s2 = _sec("X201_01", "X 201", 2, "a")
    s4 = _sec("X401_01", "X 401", 4, "b")
    assigns, stats = model_cpsat.build_and_solve([s2, s4], rooms, instr, cfg)
    a = {x.section_id: x for x in assigns}
    assert a["X201_01"].start <= a["X401_01"].start
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_s_order.py -v`
Expected: may FAIL (no ordering pressure yet).

- [ ] **Step 3: Add the term in `src/timetabling/model_cpsat.py`**

Declare a collector before the `for b, s in blocks:` loop:

```python
    order_terms = []
```

Inside the candidate loop, right after `bvars.append(v)`, add:

```python
            if 2 <= s.level <= 4:
                coeff = cfg.w_order * (4 - s.level) * (c.start - cfg.horizon_start)
                if coeff:
                    order_terms.append(coeff * v)
```

Add to the objective:

```python
    obj += order_terms
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_s_order.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/model_cpsat.py tests/test_s_order.py
git commit -m "feat: S-Order soft term (course level rises with start-hour)"
```

---

### Task 9: S-EngLab soft term — Engineering labs prefer Thu/Fri (spec §5.7)

**Files:**
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve`)
- Test: `tests/test_s_englab.py`

**Interfaces:**
- Produces: per-lab-candidate penalty `w_englab` when `cfg.eng_faculty_match in section.faculty` and `day ∉ cfg.eng_lab_days`.

- [ ] **Step 1: Write the failing test `tests/test_s_englab.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat

def test_eng_lab_prefers_thu_fri():
    cfg = Config(w_englab=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0, w_order=0)
    rooms = [Room("LAB-L", 50, True, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("E201_01", "E 201", "n", 2, "E", "Department of Computer Engineering",
                "E-2", ["a"], 10, 0, 0, 2, 0, "Course")
    s.blocks = [Block("E201_01#L", "E201_01", "lab", 2, True)]
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert assigns and assigns[0].day in ("Th", "Fr")

def test_non_eng_lab_unconstrained():
    cfg = Config(w_englab=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0, w_order=0)
    rooms = [Room("LAB-L", 50, True, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("P201_01", "P 201", "n", 2, "P", "Department of Psychology",
                "P-2", ["a"], 10, 0, 0, 2, 0, "Course")
    s.blocks = [Block("P201_01#L", "P201_01", "lab", 2, True)]
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")  # no day forced
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_s_englab.py -v`
Expected: `test_eng_lab_prefers_thu_fri` FAILs (lab may land Mon).

- [ ] **Step 3: Add the term in `src/timetabling/model_cpsat.py`**

Declare a collector before the `for b, s in blocks:` loop:

```python
    englab_terms = []
```

Inside the candidate loop, after the S-Order block, add:

```python
            if (cfg.eng_faculty_match in s.faculty and b.needs_lab
                    and c.day not in cfg.eng_lab_days):
                englab_terms.append(cfg.w_englab * v)
```

Add to the objective:

```python
    obj += englab_terms
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_s_englab.py -v`
Expected: pass.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/model_cpsat.py tests/test_s_englab.py
git commit -m "feat: S-EngLab soft term (engineering labs prefer Thu/Fri)"
```

---

### Task 10: Non-adjacent split-day soft term (#2)

**Files:**
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve`)
- Test: `tests/test_nonadjacent.py`

**Interfaces:**
- Produces: penalty `w_nonadjacent * Σ_{(section,day)} max(0, (#blocks on day) − 1)` for sections with ≥2 blocks; rewards spreading split blocks across days. Default weight 0.

- [ ] **Step 1: Write the failing test `tests/test_nonadjacent.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat

def test_split_blocks_spread_when_weighted():
    cfg = Config(w_nonadjacent=100, w_cohort_gap=0, w_evening=0, w_room_count=0,
                 w_instr_days=0, w_parttime_days=0, w_order=0)
    rooms = [Room("R1", 50, False, True)]
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("S_01", "S 201", "n", 2, "D", "Fac", "D-2", ["a"], 10, 0, 0, 0, 0, "Course")
    s.blocks = [Block("S_01#T1", "S_01", "theory", 2, False),
                Block("S_01#T2", "S_01", "theory", 2, False)]
    assigns, stats = model_cpsat.build_and_solve([s], rooms, instr, cfg)
    assert len(assigns) == 2
    assert assigns[0].day != assigns[1].day        # pushed onto different days
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_nonadjacent.py -v`
Expected: may FAIL (blocks could share a day).

- [ ] **Step 3: Add the term in `src/timetabling/model_cpsat.py`**

Declare a collector before the `for b, s in blocks:` loop:

```python
    sbd = defaultdict(list)  # (section_id, block_id, day) -> vars (multi-block sections)
```

Inside the candidate loop, after the S-EngLab block, add:

```python
            if len(s.blocks) >= 2:
                sbd[(s.section_id, b.block_id, c.day)].append(v)
```

After the gap-term block, build the penalty:

```python
    # soft: spread a section's split blocks across days
    nonadj_terms = []
    sbd_bool = {}
    sd_blocks = defaultdict(set)
    for (sid, bid, day), vs in sbd.items():
        z = model.NewBoolVar(f"sbd|{sid}|{bid}|{day}")
        model.AddMaxEquality(z, vs)
        sbd_bool[(sid, bid, day)] = z
        sd_blocks[(sid, day)].add(bid)
    for (sid, day), bids in sd_blocks.items():
        if len(bids) >= 2:
            extra = model.NewIntVar(0, len(bids), f"sameday|{sid}|{day}")
            model.Add(extra >= sum(sbd_bool[(sid, b, day)] for b in bids) - 1)
            nonadj_terms.append(extra)
    obj += [cfg.w_nonadjacent * t for t in nonadj_terms]
```

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_nonadjacent.py -q`
Expected: pass.

- [ ] **Step 5: Run the FULL suite to confirm no regression across the model changes**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add src/timetabling/model_cpsat.py tests/test_nonadjacent.py
git commit -m "feat: non-adjacent split-day soft term (#2)"
```

---

### Task 11: Full-period decomposition driver (TODO 2.5)

**Files:**
- Create: `src/timetabling/decompose.py`
- Modify: `src/timetabling/model_cpsat.py` (`build_and_solve` accepts `reserved`), `src/timetabling/__main__.py` (`--decompose`)
- Test: `tests/test_decompose.py`

**Interfaces:**
- Produces: `model_cpsat.build_and_solve(sections, rooms, instructors, cfg, reserved=None)` where `reserved` is a `set[(room, day, hour)]` of forbidden slots; `decompose.solve_decomposed(sections, rooms, instructors, cfg, group_key=lambda s: s.faculty) -> (assignments, stats)` solves groups in descending size, reserving each group's used slots for the next.

- [ ] **Step 1: Write the failing test `tests/test_decompose.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import decompose, validate

def _sec(sid, code, fac, instr, cohort):
    s = Section(sid, "001", code, "n", 2, "D", fac, cohort, [instr], 40, 1, 0, 0, 0, "Course")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 1, False)]
    return s

def test_decomposition_is_conflict_free_across_groups():
    cfg = Config(solve_time_limit_s=10)
    rooms = [Room("R1", 50, False, True)]               # single shared room -> forces reservation
    instr = {"a": Instructor("a", "n", False, "D"), "b": Instructor("b", "n", False, "D")}
    fa = _sec("FA_01", "A 201", "Faculty A", "a", "A-2")
    fb = _sec("FB_01", "B 201", "Faculty B", "b", "B-2")
    assigns, stats = decompose.solve_decomposed([fa, fb], rooms, instr, cfg)
    assert len(assigns) == 2
    # both used the one room -> must differ in (day, hour)
    s = {(x.room, x.day, x.start) for x in assigns}
    assert len(s) == 2
    assert validate.validate(assigns, [fa, fb], {r.room: r for r in rooms}, instr, cfg) == []
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_decompose.py -v`
Expected: FAIL (`No module named 'timetabling.decompose'`).

- [ ] **Step 3: Add `reserved` support to `src/timetabling/model_cpsat.py`**

Change the signature:

```python
def build_and_solve(sections: List[Section], rooms: List[Room],
                    instructors: Dict[str, Instructor], cfg: Config,
                    reserved=None) -> Tuple[List[Assignment], Dict]:
```

Right after `cands = gen_candidates(b, s, ins_list, rooms, cfg)`, filter reserved slots:

```python
        if reserved:
            cands = [c for c in cands
                     if not any((c.room, c.day, hh) in reserved
                                for hh in range(c.start, c.start + c.length))]
```

- [ ] **Step 4: Create `src/timetabling/decompose.py`**

```python
from __future__ import annotations
from typing import List, Dict, Tuple, Callable
from collections import defaultdict

from .config import Config
from .model import Section, Room, Instructor, Assignment
from .model_cpsat import build_and_solve


def solve_decomposed(sections: List[Section], rooms: List[Room],
                     instructors: Dict[str, Instructor], cfg: Config,
                     group_key: Callable[[Section], str] = lambda s: s.faculty
                     ) -> Tuple[List[Assignment], Dict]:
    """Solve sections group-by-group (default: by faculty), largest group first,
    reserving each group's used (room, day, hour) slots for later groups so the
    shared room pool stays conflict-free across the partition."""
    groups: Dict[str, List[Section]] = defaultdict(list)
    for s in sections:
        groups[group_key(s)].append(s)
    order = sorted(groups, key=lambda g: -len(groups[g]))

    reserved = set()
    all_assigns: List[Assignment] = []
    per_group = []
    for g in order:
        a, st = build_and_solve(groups[g], rooms, instructors, cfg, reserved=reserved)
        for x in a:
            for hh in range(x.start, x.end):
                reserved.add((x.room, x.day, hh))
        all_assigns.extend(a)
        per_group.append({"group": g, "n_sections": len(groups[g]),
                          "status": st["status_name"], "unplaced": len(st["unplaced"]),
                          "wall_time": st["wall_time"]})
    stats = {"groups": per_group, "n_groups": len(order),
             "n_assignments": len(all_assigns)}
    return all_assigns, stats
```

- [ ] **Step 5: Wire `--decompose` into `src/timetabling/__main__.py`**

Add the import near the others:

```python
from .decompose import solve_decomposed
```

Add the CLI flag after the `--time-limit` argument:

```python
    ap.add_argument("--decompose", action="store_true",
                    help="solve faculty-by-faculty sharing the room pool (for full --scope all)")
```

Replace the Mode-A solve line `assignments, stats = build_and_solve(sections, room_list, instructors, cfg)` with:

```python
        if args.decompose:
            assignments, stats = solve_decomposed(sections, room_list, instructors, cfg)
        else:
            assignments, stats = build_and_solve(sections, room_list, instructors, cfg)
```

Guard the existing `stats`-printing line (decomposed stats have a different shape):

```python
        if "status_name" in stats:
            print(f"[mode-A] status={stats['status_name']} blocks={stats['n_blocks']} "
                  f"vars={stats['n_vars']} unplaced={len(stats['unplaced'])} "
                  f"wall={stats['wall_time']:.1f}s violations={len(viol)}")
        else:
            print(f"[mode-A] decomposed groups={stats['n_groups']} "
                  f"assignments={stats['n_assignments']} violations={len(viol)}")
```

(Move the `viol = validate(...)` line above this print so `viol` is available in both branches.)

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_decompose.py tests/test_model_cpsat.py -v`
Expected: pass.

- [ ] **Step 7: Commit**

```bash
git add src/timetabling/decompose.py src/timetabling/model_cpsat.py src/timetabling/__main__.py tests/test_decompose.py
git commit -m "feat: faculty decomposition driver with shared-room reservation (2.5)"
```

---

### Task 12: Room-fill metric + soft calibration (TODO 2.6)

**Files:**
- Modify: `src/timetabling/report.py` (`_metrics`)
- Test: `tests/test_room_fill.py`

**Interfaces:**
- Produces: `_metrics(...)` returns an added `room_fill` key = mean over assignments of `students / room_cap` (rounded 3 dp). Surfaces in `mode_b_<period>.json` for both `mode_a` and `existing`.

- [ ] **Step 1: Write the failing test `tests/test_room_fill.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import report

def test_room_fill_metric():
    rooms = {"R1": Room("R1", 100, False, True)}
    instr = {"a": Instructor("a", "n", False, "D")}
    s = Section("S_01", "001", "S 201", "n", 2, "D", "Fac", "D-2", ["a"],
                50, 1, 0, 0, 0, "Course")
    s.blocks = [Block("S_01#T", "S_01", "theory", 1, False)]
    a = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 10)]
    m = report._metrics(a, [s], rooms, instr, Config())
    assert m["room_fill"] == 0.5                  # 50 / 100
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_room_fill.py -v`
Expected: FAIL (`KeyError: 'room_fill'`).

- [ ] **Step 3: Add `room_fill` in `src/timetabling/report.py`**

In `_metrics`, before the `return {`, add:

```python
    sec_by_id = {s.section_id: s for s in sections}
    fills = []
    for a in assignments:
        s = sec_by_id.get(a.section_id)
        room = rooms.get(a.room)
        if s and room and room.cap:
            fills.append(s.students / room.cap)
    room_fill = round(sum(fills) / len(fills), 3) if fills else 0.0
```

Add `"room_fill": room_fill,` to the returned dict.

- [ ] **Step 4: Run tests**

Run: `python3 -m pytest tests/test_room_fill.py -q`
Expected: pass.

- [ ] **Step 5: Calibrate weights against benchmarks (measurement, not code)**

Run on a representative faculty and read `out/mode_b_001.json`:

```bash
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Computer Engineering" --mode A,B --time-limit 60
```

Target: `mode_a` `room_fill` ≈ 0.53 and `evening_ratio` ≈ 0.07, with **0 validator violations**.
Tune in `config.py` (no test needed; this is the calibration loop):
- If `room_fill` too low (rooms too empty) → raise `w_room_count`; if too high/over-packed → lower it.
- If `evening_ratio` too high → raise `w_evening`.
- Keep `w_cohort_gap`, `w_order`, `w_englab` small enough that feasibility/room/evening are not regressed (start at the Task-1 defaults and adjust ±1–2).
- If the cohort-gap / order effects are not visible, raise their weight one step and re-run.
Record the chosen weights and the before/after metrics in the commit message.

- [ ] **Step 6: Commit**

```bash
git add src/timetabling/report.py src/timetabling/config.py tests/test_room_fill.py
git commit -m "feat: room_fill metric + calibrate soft weights vs benchmarks (2.6)"
```

---

### Task 13: Full-period results + documentation

**Files:**
- Modify: `README.md`, `TODO.md`, `CLAUDE.md`
- (No new tests — this task runs the solver and records evidence.)

- [ ] **Step 1: Confirm the whole suite is green**

Run: `python3 -m pytest -q`
Expected: all pass.

- [ ] **Step 2: Produce the required result runs**

```bash
PYTHONPATH=src python3 -m timetabling --period 001 --scope faculty="Computer Engineering" --mode A,B --time-limit 120
PYTHONPATH=src python3 -m timetabling --period 001 --scope faculty="Architecture" --mode A,B --time-limit 120
PYTHONPATH=src python3 -m timetabling --period 001 --scope all --mode A,B --time-limit 300
PYTHONPATH=src python3 -m timetabling --period 002 --scope all --mode A,B --time-limit 300
```

If a full `--scope all` run does not reach a feasible solution with 0 violations under the cap,
re-run that period with `--decompose` and record which path was used:

```bash
PYTHONPATH=src python3 -m timetabling --period 001 --scope all --decompose --mode A,B --time-limit 300
```

For each run, capture from stdout / `out/`: status, `violations` (must be 0), `rooms_used`,
`room_fill`, `evening_ratio`, and the Mode-B `existing` vs `mode_a` comparison.

- [ ] **Step 3: Update `README.md`**

- Move Phase 2 items from "Known limitations" into a new **"Verified results (Phase 2)"** table
  with the CompEng, Architecture, and full 001/002 rows (sections, status, hard violations,
  room_fill, evening_ratio, Mode-A vs existing).
- Document the new flags/params: `--decompose`; `max_block_len`, `extra_rooms`,
  `compact_cohort_years`, `w_cohort_gap`, `w_order`, `w_englab`, `eng_lab_days`,
  `eng_faculty_match`, `w_nonadjacent`.
- State the new behaviors: course-level cohort, split blocks, team-taught `instructor_ids`,
  synthetic large halls (with the assumption note), cohort daily-compactness, S-Order, S-EngLab.

- [ ] **Step 4: Update `TODO.md`**

Mark 2.1–2.6 done; record the chosen oversize strategy (large halls) and the new soft rules
(cohort daily-compactness, S-Order, S-EngLab). Move any genuinely-deferred item (e.g. the O(n²)
inversion-based S-Order upgrade) to a clearly-labeled "deferred" subsection. Phase 3 (web UI)
remains.

- [ ] **Step 5: Update `CLAUDE.md`**

In the "Architecture" / "Gotchas" sections, record the Phase-2 facts a future session needs:
- Cohort conflict is **course-level** (same-course sections may run in parallel); H_self enforces
  section-internal non-overlap.
- Blocks may be **split** (`max_block_len`); block ids are `#T`/`#L` or `#T1..`/`#L1..`; kind =
  `"#L" in block_id`.
- Sections carry **`instructor_ids: list[str]`** (team-taught); blackout = union over instructors.
- **Synthetic large halls** (`AMFI-*`) come from `cfg.extra_rooms` and are an assumption.
- New soft terms and their weights; `--decompose` for full-scale solving.
- Add `decompose.py` to the module list.

- [ ] **Step 6: Commit**

```bash
git add README.md TODO.md CLAUDE.md
git commit -m "docs: Phase 2 results (CompEng/Architecture/full 001-002) + update README/TODO/CLAUDE"
```

---

## Self-Review

**Spec coverage:**
- 2.1 course-level cohort → Task 5. ✔ (H_self prerequisite → Task 4. ✔)
- 2.2 split long blocks → Task 6. ✔
- 2.3 team-taught → Task 3. ✔
- 2.4 oversize → large halls → Task 2. ✔
- 2.5 full-period + decomposition → Task 11 (+ Task 13 runs). ✔
- 2.6 soft calibration → Task 12. ✔
- Cohort daily-compactness (spec §5.5) → Task 7. ✔
- S-Order (spec §5.7) → Task 8. ✔
- S-EngLab (spec §5.7) → Task 9. ✔
- #2 non-adjacent (spec §5.6) → Task 10. ✔
- Reporting CompEng/Architecture/full + Mode-B (DoD) → Task 13. ✔

**Deferred (recorded, not implemented):** the secondary staged softs (#4 dept day-balance, #5
cohort daily-load, #7 instructor free-days, #14 practicum buffer) listed in spec §5.6 are added
**only if** the Task-12 calibration shows a benchmark gap — they are tuning knobs, gated by YAGNI;
config fields for them are introduced at that point. The O(n²) inversion S-Order upgrade stays in
TODO. Both are noted in Task 12 / Task 13.

**Type/signature consistency:** `Section.instructor_ids: list[str]` (Task 3) is used by
`model_cpsat`/`validate`/`export` consistently; `gen_candidates(block, section, instructors_list,
rooms, cfg)` updated with all callers (Task 3); `build_and_solve(..., reserved=None)` (Task 11)
matches `decompose.solve_decomposed` usage; `blocks_from_tpl(..., max_block_len)` (Task 6) matches
the `build_sections` call site; kind detection `"#L" in bid` (Task 6) matches the split ids.

**Placeholder scan:** no TBD/TODO/"handle edge cases"; every code step shows complete code.
Task 12 Step 5 and Task 13 are measurement/documentation tasks by nature — their actions are
explicit commands with target numbers, not code placeholders.

---

## Addendum — Task 14 (added during execution): soften cohort to a penalty

After Tasks 1–11 landed, calibration (Task 12) revealed the course-level cohort constraint is still
**hard-infeasible** at faculty/full scale (Computer Engineering: INFEASIBLE with cohort hard,
OPTIMAL with cohort coupling removed — proof in spec §5.1-R). The `(Dept_Code, Year_Level)` proxy
over-counts conflict because students split across electives (4XX are mostly electives, 2–3 per
student/term). Per the user's decision, the cohort constraint becomes **soft**: a weighted penalty
the solver minimizes, with rooms/instructors/window/etc. staying hard. Full task text and TDD steps:
[.superpowers/sdd/task-14-brief.md](../../../.superpowers/sdd/task-14-brief.md) (kept in the SDD
workspace). It modifies `config.py` (`w_cohort_conflict`), `model_cpsat.py` (hard `<=1` → penalty),
`validate.py` (cohort no longer a hard violation), `report.py` (`cohort_conflicts` soft metric),
and the cohort tests. Task 12 calibration and Task 13 full-period results are run **after** Task 14,
since they depend on full-period feasibility.
