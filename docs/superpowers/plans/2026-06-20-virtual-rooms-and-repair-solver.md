# Virtual-Room Fidelity + Warm-Started Repair Solver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Lift full-period placement from ~49% to ~95%+ with 0 hard violations by (a) modeling oversize/online sections in a virtual room instead of fictional amphitheaters, and (b) replacing the greedy permanent-reservation decomposition with a warm-started, small-neighborhood repair solver — all on CP-SAT, with the unused Gurobi backend removed.

**Architecture:** Three phases. **Phase 0** deletes the Gurobi backend (decision: CP-SAT is sufficient — proven). **Phase A** adds a virtual room: sections whose enrollment exceeds the largest real classroom (100), or that the existing plan delivers as `Online`, are routed to an unlimited-capacity virtual room exempt from room no-overlap; the synthetic `AMFI-*` halls are removed. **Phase B** adds `repair.py`: a fast greedy construction seeds a warm start, then CP-SAT repeatedly re-optimizes small *relatedness* neighborhoods (unplaced blocks + the placed blocks competing for their slots) with a **soft** placement constraint, monotonically accepting only non-worsening moves, until no new placements appear.

**Tech Stack:** Python 3, OR-Tools CP-SAT (`ortools.sat.python.cp_model`), pandas, pytest. `pyproject.toml` sets `pythonpath=src` for pytest; ad-hoc runs need `PYTHONPATH=src`.

## Global Constraints

- All CSVs read `dtype=str`; never `split(",")`; normalize via `textnorm`.
- `validate.py` stays solver-independent — never import model/solver internals into it. It checks only: capacity, lab-room, window (<18:00), blackout, room no-overlap, instructor no-overlap, self-overlap (H_self). Cohort is soft, never a `Violation`.
- Block kind detection: `"#L" in block_id` (not `==`). `section_id = block_id.split("#")[0]`.
- `schedule_*.json` is the read-only UI contract (`export.build_schedule_dict`) — keep the per-assignment field set stable; only additive changes allowed.
- Hard constraints by candidate pruning (per-block filters in `gen_candidates`); soft preferences only as `Minimize` penalty terms.
- Commit directly to `main`, no feature branches, no PRs. `data/` contains PII and must remain gitignored.
- Virtual room name = `cfg.online_room` (`"Online"`), already present in `classrooms.csv` with cap 9999.
- Largest real (non-virtual, non-synthetic) classroom capacity = **100**. Verified from data.

---

## File Structure

| File | Responsibility | Phase |
|---|---|---|
| `src/timetabling/model_gurobi.py` | **DELETE** | 0 |
| `src/timetabling/__main__.py` | remove `--solver`; add routing + `--repair` wiring | 0, A, B |
| `src/timetabling/model.py` | add `Room.is_virtual`, `Section.is_virtual`, `Section.plan_room` | A |
| `src/timetabling/config.py` | `extra_rooms` default `()` | A |
| `src/timetabling/clean.py` | mark `Online` virtual; stop injecting AMFI | A |
| `src/timetabling/derive.py` | set `Section.plan_room` | A |
| `src/timetabling/route.py` | **NEW** — `mark_virtual(sections, rooms, cfg)` | A |
| `src/timetabling/model_cpsat.py` | virtual rooms in `feasible_rooms_for`; exempt virtual from room no-overlap | A |
| `src/timetabling/validate.py` | exempt virtual room from capacity/lab/room-overlap | A |
| `src/timetabling/repair.py` | **NEW** — construction + warm-started repair solver | B |

---

## PHASE 0 — Remove Gurobi backend

### Task 0.1: Delete the Gurobi model and its wiring

**Files:**
- Delete: `src/timetabling/model_gurobi.py`
- Modify: `src/timetabling/__main__.py:40-41` (the `--solver` arg) and `:76-80` (the solver branch)

**Interfaces:**
- Produces: Mode-A solve path with no `--solver` flag; CP-SAT `build_and_solve` is the only non-decompose backend.

- [ ] **Step 1: Confirm no test references Gurobi**

Run: `grep -rni "gurobi" src/ tests/ | grep -v __pycache__`
Expected: only matches inside `model_gurobi.py` and `__main__.py` (no test files).

- [ ] **Step 2: Delete the module**

```bash
git rm -f src/timetabling/model_gurobi.py 2>/dev/null || rm -f src/timetabling/model_gurobi.py
```

- [ ] **Step 3: Remove the `--solver` argument** in `src/timetabling/__main__.py`

Delete these two lines (currently `:40-41`):

```python
    ap.add_argument("--solver", default="cpsat", choices=["cpsat", "gurobi"],
                    help="MIP solver backend (default: cpsat)")
```

- [ ] **Step 4: Collapse the solver branch** in `src/timetabling/__main__.py`

Replace the current Mode-A block (the `if args.decompose / elif args.solver == "gurobi" / else` chain) with:

```python
        if args.decompose:
            assignments, stats = solve_decomposed(sections, room_list, instructors, cfg)
        else:
            assignments, stats = _cpsat_solve(sections, room_list, instructors, cfg)
```

- [ ] **Step 5: Verify the suite still passes**

Run: `PYTHONPATH=src python3 -m pytest -q`
Expected: PASS (68 tests).

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "chore: remove unused Gurobi backend (CP-SAT is sufficient)"
```

---

## PHASE A — Virtual-room model fidelity

### Task A.1: Add `is_virtual` to Room and `is_virtual`/`plan_room` to Section

**Files:**
- Modify: `src/timetabling/model.py` (Room dataclass ~`:6-11`, Section dataclass ~`:31-48`)
- Test: `tests/test_validate.py` (reuse existing Room construction helpers — no new test file)

**Interfaces:**
- Produces: `Room(room, cap, is_lab, is_physical, is_virtual=False)`; `Section(..., blocks=[], is_virtual=False, plan_room="")`.

- [ ] **Step 1: Add the Room field** — in `src/timetabling/model.py`, inside the `Room` frozen dataclass, after `is_physical: bool`:

```python
    is_physical: bool
    is_virtual: bool = False
```

- [ ] **Step 2: Add the Section fields** — after `blocks: List[Block] = field(default_factory=list)`:

```python
    blocks: List[Block] = field(default_factory=list)
    is_virtual: bool = False
    plan_room: str = ""
```

- [ ] **Step 3: Verify nothing breaks** (defaults keep all existing constructors valid)

Run: `PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat: add is_virtual to Room and is_virtual/plan_room to Section"
```

### Task A.2: Mark the Online room virtual; stop injecting AMFI halls

**Files:**
- Modify: `src/timetabling/config.py:33` (`extra_rooms` default)
- Modify: `src/timetabling/clean.py:15-29` (`build_rooms`)
- Test: `tests/test_clean.py`, `tests/test_clean_halls.py`, `tests/test_config_phase2.py`

**Interfaces:**
- Consumes: `Room.is_virtual` (A.1).
- Produces: `build_rooms` returns the `Online` room with `is_virtual=True`, and injects AMFI halls only if `cfg.extra_rooms` is non-empty (now empty by default).

- [ ] **Step 1: Update the failing tests first** — replace the body of `tests/test_clean_halls.py` with:

```python
from timetabling import clean, io_csv
from timetabling.config import Config


def test_no_synthetic_halls_by_default():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    assert not any(n.startswith("AMFI-") for n in rooms)


def test_halls_injected_when_configured():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config(extra_rooms=((500, 1),)))
    assert "AMFI-500-1" in rooms and rooms["AMFI-500-1"].cap == 500
```

In `tests/test_config_phase2.py`, change the `extra_rooms` assertion line to:

```python
    assert c.extra_rooms == ()
```

In `tests/test_clean.py`, add after the existing `Online` assertion:

```python
    assert rooms["Online"].is_virtual is True
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src python3 -m pytest tests/test_clean.py tests/test_clean_halls.py tests/test_config_phase2.py -q`
Expected: FAIL (AMFI still injected; `extra_rooms` still the 3-tuple; `is_virtual` attr default False).

- [ ] **Step 3: Change the config default** — in `src/timetabling/config.py`:

```python
    extra_rooms: tuple = ()
```

- [ ] **Step 4: Mark Online virtual** — in `src/timetabling/clean.py`, change the room construction in `build_rooms`:

```python
        is_physical = name != cfg.online_room
        rooms[name] = Room(room=name, cap=cap, is_lab=classify_room(name),
                           is_physical=is_physical, is_virtual=(name == cfg.online_room))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PYTHONPATH=src python3 -m pytest tests/test_clean.py tests/test_clean_halls.py tests/test_config_phase2.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: Online room is virtual; AMFI halls off by default"
```

### Task A.3: Capture `plan_room` on each Section

**Files:**
- Modify: `src/timetabling/derive.py:88-95` (Section construction in `build_sections`)
- Test: `tests/test_derive.py`

**Interfaces:**
- Consumes: `Section.plan_room` (A.1); the frame's `plan_room` column (`join.build_section_frame`).
- Produces: every built Section carries `plan_room` = the trimmed `plan_room` cell.

- [ ] **Step 1: Write the failing test** — append to `tests/test_derive.py`:

```python
def test_section_carries_plan_room():
    import pandas as pd
    from timetabling.derive import build_sections
    from timetabling.config import Config
    frame = pd.DataFrame([{
        "section_id": "HIST 101_01", "period": "001", "code": "HIST 101",
        "name": "History", "faculty": "Basic Sciences", "T": "2", "P": "0",
        "L": "0", "Cr": "2", "category": "", "staff_id": "00000001",
        "grades_students": "148", "dept_code": "HIST", "year_level": "1",
        "plan_room": "Online",
    }])
    secs, _ = build_sections(frame, Config())
    assert secs[0].plan_room == "Online"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_derive.py::test_section_carries_plan_room -v`
Expected: FAIL (`plan_room` defaults to `""`).

- [ ] **Step 3: Set the field** — in `src/timetabling/derive.py`, add `plan_room=...` to the `Section(...)` call:

```python
            T=T, P=P, L=L, Cr=Cr, category=category,
            blocks=blocks_from_tpl(sid, T, P, L, Cr, cfg.max_block_len),
            plan_room=r.get("plan_room", "").strip(),
        )
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_derive.py::test_section_carries_plan_room -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: build_sections records plan_room on each Section"
```

### Task A.4: `route.py` — mark oversize / online sections virtual

**Files:**
- Create: `src/timetabling/route.py`
- Test: `tests/test_route.py`

**Interfaces:**
- Consumes: `Section.is_virtual`, `Section.plan_room` (A.1, A.3); `Room.is_virtual`, `Room.is_physical`.
- Produces: `mark_virtual(sections: List[Section], rooms: Dict[str, Room], cfg: Config) -> List[Section]` — mutates and returns `sections`; sets `s.is_virtual = True` iff `s.plan_room == cfg.online_room` or `s.students > max_real_cap`, where `max_real_cap` = largest cap among physical non-virtual rooms.

- [ ] **Step 1: Write the failing test** — create `tests/test_route.py`:

```python
from timetabling.model import Room, Section
from timetabling.config import Config
from timetabling.route import mark_virtual


def _sec(sid, students, plan_room=""):
    return Section(section_id=sid, period="001", code="X 101", name="x", level=1,
                   dept_code="X", faculty="F", cohort_key="X-1", instructor_ids=["i"],
                   students=students, T=2, P=0, L=0, Cr=2, category="",
                   plan_room=plan_room)


def test_marks_online_and_oversize_virtual():
    rooms = {"R": Room("R", 100, False, True), "Online": Room("Online", 9999, False, False, True)}
    cfg = Config()
    secs = [_sec("a", 50), _sec("b", 148, "Online"), _sec("c", 497), _sec("d", 100)]
    mark_virtual(secs, rooms, cfg)
    assert [s.is_virtual for s in secs] == [False, True, True, False]
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_route.py -v`
Expected: FAIL (`No module named 'timetabling.route'`).

- [ ] **Step 3: Implement** — create `src/timetabling/route.py`:

```python
from __future__ import annotations
from typing import Dict, List

from .config import Config
from .model import Room, Section


def mark_virtual(sections: List[Section], rooms: Dict[str, Room], cfg: Config) -> List[Section]:
    """Route sections with no real classroom to the virtual room: those the
    existing plan delivers as Online, or whose enrollment exceeds the largest
    real (physical, non-virtual) classroom."""
    max_real = max((r.cap for r in rooms.values() if r.is_physical and not r.is_virtual),
                   default=0)
    for s in sections:
        if s.plan_room == cfg.online_room or s.students > max_real:
            s.is_virtual = True
    return sections
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_route.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: route.mark_virtual flags online/oversize sections virtual"
```

### Task A.5: Virtual sections get virtual-room candidates; exempt virtual from room no-overlap

**Files:**
- Modify: `src/timetabling/model_cpsat.py:18-25` (`feasible_rooms_for`) and `:84-138` (occupancy in `build_and_solve`)
- Test: `tests/test_model_cpsat.py`

**Interfaces:**
- Consumes: `Section.is_virtual`, `Room.is_virtual`.
- Produces: `feasible_rooms_for` returns `[the virtual room]` for a virtual section; `build_and_solve` never adds virtual-room slots to `room_occ` (unlimited concurrency), but instructor/self no-overlap still apply.

- [ ] **Step 1: Write the failing test** — append to `tests/test_model_cpsat.py`:

```python
def test_virtual_sections_share_virtual_room_without_conflict():
    from timetabling.model import Room, Section, Block, Instructor
    from timetabling.config import Config
    from timetabling.model_cpsat import build_and_solve
    cfg = Config(solve_time_limit_s=5)
    rooms = [Room("Online", 9999, False, False, True)]
    instr = {"i1": Instructor("i1", "A", True, "D"), "i2": Instructor("i2", "B", True, "D")}

    def vsec(sid, iid):
        s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 300,
                    2, 0, 0, 2, "", is_virtual=True)
        s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
        return s

    secs = [vsec("X 101_01", "i1"), vsec("X 101_02", "i2")]
    assigns, stats = build_and_solve(secs, rooms, instr, cfg)
    assert len(assigns) == 2                      # both placed
    assert {a.room for a in assigns} == {"Online"}  # both in the virtual room
    # same day+hour allowed in the virtual room (different instructors)
    slots = {(a.day, a.start) for a in assigns}
    # they MAY share a slot; the key assertion is both placed with 0 conflicts
    from timetabling.validate import validate
    rooms_d = {"Online": rooms[0]}
    assert validate(assigns, secs, rooms_d, instr, cfg) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_model_cpsat.py::test_virtual_sections_share_virtual_room_without_conflict -v`
Expected: FAIL (virtual section gets no candidates → unplaced; or room_occ forces a conflict).

- [ ] **Step 3: Route virtual sections to the virtual room** — replace `feasible_rooms_for` in `src/timetabling/model_cpsat.py`:

```python
def feasible_rooms_for(block: Block, section: Section, rooms: List[Room],
                       cfg: Config) -> List[Room]:
    if section.is_virtual:
        return [r for r in rooms if r.is_virtual][:1]
    fr = [
        r for r in rooms
        if r.is_physical and r.cap >= section.students and (r.is_lab if block.needs_lab else True)
    ]
    fr.sort(key=lambda r: (r.cap, r.room))
    return fr[:cfg.max_rooms_per_block]
```

- [ ] **Step 4: Exempt the virtual room from room no-overlap** — in `build_and_solve`, just before the candidate loop add:

```python
    virtual_names = {r.room for r in rooms if r.is_virtual}
```

and change the room-occupancy line inside the per-candidate hour loop from:

```python
                room_occ[(c.room, c.day, hh)].append(v)
```

to:

```python
                if c.room not in virtual_names:
                    room_occ[(c.room, c.day, hh)].append(v)
```

and guard the `room_used_vars` line so the virtual room is not penalized:

```python
            if c.room not in virtual_names:
                room_used_vars[c.room].append(v)
```

- [ ] **Step 5: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_model_cpsat.py::test_virtual_sections_share_virtual_room_without_conflict -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: virtual sections use the virtual room, exempt from room no-overlap"
```

### Task A.6: `validate.py` exempts the virtual room from capacity / lab / room-overlap

**Files:**
- Modify: `src/timetabling/validate.py:33-63`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `Room.is_virtual`.
- Produces: assignments in a virtual room never raise capacity, lab, or room-overlap violations; instructor/self/window/blackout checks unchanged.

- [ ] **Step 1: Write the failing test** — append to `tests/test_validate.py`:

```python
def test_virtual_room_exempt_from_capacity_and_room_overlap():
    from timetabling.model import Room, Section, Block, Instructor, Assignment
    from timetabling.config import Config
    from timetabling.validate import validate
    rooms = {"Online": Room("Online", 9999, False, False, True)}
    instr = {"i1": Instructor("i1", "A", True, "D"), "i2": Instructor("i2", "B", True, "D")}

    def vsec(sid, iid):
        s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 300,
                    2, 0, 0, 2, "", is_virtual=True)
        s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
        return s

    secs = [vsec("X 101_01", "i1"), vsec("X 101_02", "i2")]
    # both in the SAME virtual slot, 300 students each > cap-less virtual room
    a = [Assignment("X 101_01#T", "X 101_01", "theory", "Online", "Mo", 9, 11),
         Assignment("X 101_02#T", "X 101_02", "theory", "Online", "Mo", 9, 11)]
    assert validate(a, secs, rooms, instr, Config()) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_validate.py::test_virtual_room_exempt_from_capacity_and_room_overlap -v`
Expected: FAIL (capacity 9999≥300 passes, but room no-overlap flags the shared `Online` slot).

- [ ] **Step 3: Implement the exemptions** — in `src/timetabling/validate.py`, inside the `for a in assignments:` loop, replace the capacity/lab block and the room-occupancy append. After `room = rooms.get(a.room)` add `is_virt = room is not None and room.is_virtual` and gate the checks:

```python
        room = rooms.get(a.room)
        is_virt = room is not None and room.is_virtual
        if not is_virt and room is not None and room.cap < s.students:
            viol.append(Violation("capacity",
                        f"{a.block_id} in {a.room} (cap {room.cap}) < {s.students} students"))
        if a.kind == "lab" and not is_virt and (room is None or not room.is_lab):
            viol.append(Violation("lab", f"{a.block_id} lab block in non-lab room {a.room}"))
```

and change the room-occupancy append inside the `for hh in range(a.start, a.end):` loop:

```python
        for hh in range(a.start, a.end):
            if not is_virt:
                room_occ[(a.room, a.day, hh)].append(a.block_id)
            for iid in s.instructor_ids:
                instr_occ[(iid, a.day, hh)].append(a.block_id)
            section_occ[(a.section_id, a.day, hh)].append(a.block_id)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_validate.py::test_virtual_room_exempt_from_capacity_and_room_overlap -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: validate exempts virtual room from capacity/lab/room-overlap"
```

### Task A.7: Wire routing into the pipeline (run before `split_roomable`)

**Files:**
- Modify: `src/timetabling/__main__.py:50-56`
- Test: manual end-to-end run (asserted via printed counts)

**Interfaces:**
- Consumes: `route.mark_virtual` (A.4).
- Produces: `__main__` calls `mark_virtual(all_sections, rooms, cfg)` after `build_sections` and before `split_roomable`.

- [ ] **Step 1: Add the import** — in `src/timetabling/__main__.py` with the other imports:

```python
from .route import mark_virtual
```

- [ ] **Step 2: Call routing before split** — change the data-prep block:

```python
    frame = _apply_scope(build_section_frame(args.period, cfg.include_plan_only), args.scope)
    all_sections, derive_rep = build_sections(frame, cfg)
    mark_virtual(all_sections, rooms, cfg)
    room_list = list(rooms.values())

    sections, unschedulable = split_roomable(all_sections, room_list, cfg, instructors)
```

- [ ] **Step 3: End-to-end smoke run** (real data must be present)

Run: `PYTHONPATH=src python3 -m timetabling --period 001 --scope faculty="Basic Sciences" --mode A --time-limit 30`
Expected: `[mode-A] ... violations=0`, and the HIST/TUR/TEDU sections place in `Online` (inspect `out/schedule_001.csv` — their `room` column = `Online`).

- [ ] **Step 4: Full suite**

Run: `PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: route oversize/online sections to virtual room in pipeline"
```

---

## PHASE B — Warm-started repair solver

### Task B.1: Occupancy `State` with incremental competitor lookup

**Files:**
- Create: `src/timetabling/repair.py` (State only this task)
- Test: `tests/test_repair_state.py`

**Interfaces:**
- Produces:
  - `State(sec_of: Dict[str, Section], sec_instr: Dict[str, list], virtual_names: set)`
  - `state.placed: Dict[str, Candidate]`
  - `state.free_to_place(c: Candidate, sid: str, iids: list) -> bool`
  - `state.occupy(block_id: str, c: Candidate) -> None`
  - `state.release(block_id: str) -> None`
  - virtual-room slots never enter room occupancy (so virtual blocks never room-conflict).

- [ ] **Step 1: Write the failing test** — create `tests/test_repair_state.py`:

```python
from timetabling.model import Section, Block, Candidate
from timetabling.repair import State


def _sec(sid, iid):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_room_conflict_blocks_second_placement():
    a, b = _sec("A_01", "i1"), _sec("B_01", "i2")
    st = State({"A_01#T": a, "B_01#T": b},
               {"A_01": ["i1"], "B_01": ["i2"]}, set())
    ca = Candidate("A_01#T", "R1", "Mo", 9, 2)
    st.occupy("A_01#T", ca)
    cb = Candidate("B_01#T", "R1", "Mo", 9, 2)  # same room+slot
    assert st.free_to_place(cb, "B_01", ["i2"]) is False
    st.release("A_01#T")
    assert st.free_to_place(cb, "B_01", ["i2"]) is True


def test_virtual_room_never_room_conflicts():
    a, b = _sec("A_01", "i1"), _sec("B_01", "i2")
    st = State({"A_01#T": a, "B_01#T": b},
               {"A_01": ["i1"], "B_01": ["i2"]}, {"Online"})
    st.occupy("A_01#T", Candidate("A_01#T", "Online", "Mo", 9, 2))
    cb = Candidate("B_01#T", "Online", "Mo", 9, 2)
    assert st.free_to_place(cb, "B_01", ["i2"]) is True   # different instructors, virtual room
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_state.py -v`
Expected: FAIL (`No module named 'timetabling.repair'`).

- [ ] **Step 3: Implement** — create `src/timetabling/repair.py`:

```python
from __future__ import annotations
from typing import Dict, List
from collections import defaultdict

from ortools.sat.python import cp_model

from .config import Config
from .model import Section, Room, Instructor, Candidate, Assignment
from .model_cpsat import gen_candidates, _instructors_of

BIG = 10_000


class State:
    """Global assignment + incremental occupancy for fast competitor lookup.
    Virtual-room slots are never tracked as room occupancy (unlimited)."""

    def __init__(self, sec_of, sec_instr, virtual_names):
        self.sec_of = sec_of                # block_id -> Section
        self.sec_instr = sec_instr          # section_id -> [iid]
        self.virtual = set(virtual_names)   # room names exempt from room no-overlap
        self.placed: Dict[str, Candidate] = {}
        self.room_owner: Dict[tuple, str] = {}
        self.instr_blocks = defaultdict(set)
        self.sect_blocks = defaultdict(set)
        self.instr_slot = defaultdict(set)
        self.sect_slot = defaultdict(set)

    def free_to_place(self, c, sid, iids):
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual and (c.room, c.day, hh) in self.room_owner:
                return False
            for iid in iids:
                if self.instr_slot.get((iid, c.day, hh)):
                    return False
            if self.sect_slot.get((sid, c.day, hh)):
                return False
        return True

    def occupy(self, bid, c):
        s = self.sec_of[bid]; iids = self.sec_instr.get(s.section_id, [])
        self.placed[bid] = c
        self.sect_blocks[s.section_id].add(bid)
        for iid in iids:
            self.instr_blocks[iid].add(bid)
        for hh in range(c.start, c.start + c.length):
            if c.room not in self.virtual:
                self.room_owner[(c.room, c.day, hh)] = bid
            for iid in iids:
                self.instr_slot[(iid, c.day, hh)].add(bid)
            self.sect_slot[(s.section_id, c.day, hh)].add(bid)

    def release(self, bid):
        c = self.placed.pop(bid, None)
        if c is None:
            return
        s = self.sec_of[bid]; iids = self.sec_instr.get(s.section_id, [])
        self.sect_blocks[s.section_id].discard(bid)
        for iid in iids:
            self.instr_blocks[iid].discard(bid)
        for hh in range(c.start, c.start + c.length):
            if self.room_owner.get((c.room, c.day, hh)) == bid:
                del self.room_owner[(c.room, c.day, hh)]
            for iid in iids:
                self.instr_slot[(iid, c.day, hh)].discard(bid)
            self.sect_slot[(s.section_id, c.day, hh)].discard(bid)
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: repair.State occupancy with virtual-room exemption"
```

### Task B.2: Greedy first-fit construction

**Files:**
- Modify: `src/timetabling/repair.py` (add `greedy_construct`)
- Test: `tests/test_repair_construct.py`

**Interfaces:**
- Consumes: `State` (B.1).
- Produces: `greedy_construct(state: State, order: List[str], cand_by_block: Dict[str, List[Candidate]]) -> None` — places each block id (in `order`) at its first conflict-free candidate.

- [ ] **Step 1: Write the failing test** — create `tests/test_repair_construct.py`:

```python
from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, greedy_construct


def _sec(sid, iid):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_greedy_places_both_in_distinct_slots():
    a, b = _sec("A_01", "i1"), _sec("B_01", "i1")   # same instructor -> must differ in time
    sec_of = {"A_01#T": a, "B_01#T": b}
    sec_instr = {"A_01": ["i1"], "B_01": ["i1"]}
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2), Candidate("B_01#T", "R1", "Mo", 11, 2)],
    }
    st = State(sec_of, sec_instr, set())
    greedy_construct(st, ["A_01#T", "B_01#T"], cands)
    assert len(st.placed) == 2
    assert st.placed["B_01#T"].start == 11   # forced off the taken 9:00 slot
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_construct.py -v`
Expected: FAIL (`greedy_construct` not defined).

- [ ] **Step 3: Implement** — append to `src/timetabling/repair.py`:

```python
def greedy_construct(state: State, order: List[str], cand_by_block) -> None:
    for bid in order:
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        for c in cand_by_block[bid]:
            if state.free_to_place(c, s.section_id, iids):
                state.occupy(bid, c)
                break
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_construct.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: repair.greedy_construct first-fit construction"
```

### Task B.3: Relatedness competitor selection + monotonic repair round

**Files:**
- Modify: `src/timetabling/repair.py` (add `competitors`, `repair_round`, module consts `BATCH`, `REPAIR_TL`, `MAX_FREE`)
- Test: `tests/test_repair_round.py`

**Interfaces:**
- Consumes: `State` (B.1).
- Produces:
  - `competitors(state, batch: List[str], cand_by_block) -> set` — placed blocks occupying any room-slot a batch block could use, plus same-instructor and same-section placed blocks, minus the batch itself.
  - `repair_round(state, batch, cand_by_block) -> int` — re-solves the freed neighborhood with soft placement, warm-started; commits only if it places ≥ what the neighborhood had; returns net new placements.

- [ ] **Step 1: Write the failing test** — create `tests/test_repair_round.py`:

```python
from timetabling.model import Section, Block, Candidate
from timetabling.repair import State, greedy_construct, repair_round


def _sec(sid, iid, cands_meta):
    s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], 30, 2, 0, 0, 2, "")
    s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
    return s


def test_repair_places_a_blocked_section_by_moving_competitor():
    # A occupies the only slot B's narrow candidate wants; A also has an alt slot.
    a = _sec("A_01", "i1", None)
    b = _sec("B_01", "i2", None)
    sec_of = {"A_01#T": a, "B_01#T": b}
    sec_instr = {"A_01": ["i1"], "B_01": ["i2"]}
    cands = {
        "A_01#T": [Candidate("A_01#T", "R1", "Mo", 9, 2), Candidate("A_01#T", "R2", "Mo", 9, 2)],
        "B_01#T": [Candidate("B_01#T", "R1", "Mo", 9, 2)],   # only R1@9
    }
    st = State(sec_of, sec_instr, set())
    # construct in an order that parks A on R1@9, blocking B
    greedy_construct(st, ["A_01#T", "B_01#T"], cands)
    assert "B_01#T" not in st.placed              # B blocked after construction
    gained = repair_round(st, ["B_01#T"], cands)
    assert gained == 1
    assert len(st.placed) == 2                    # A moved to R2, B took R1@9
    assert st.placed["B_01#T"].room == "R1"
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_round.py -v`
Expected: FAIL (`repair_round` not defined).

- [ ] **Step 3: Implement** — append to `src/timetabling/repair.py`:

```python
BATCH = 30
REPAIR_TL = 12.0
MAX_FREE = 240


def competitors(state: State, batch, cand_by_block) -> set:
    comp = set()
    for bid in batch:
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        for c in cand_by_block[bid]:
            if c.room in state.virtual:
                continue
            for hh in range(c.start, c.start + c.length):
                owner = state.room_owner.get((c.room, c.day, hh))
                if owner:
                    comp.add(owner)
        for iid in iids:
            comp |= state.instr_blocks.get(iid, set())
        comp |= state.sect_blocks.get(s.section_id, set())
    return comp - set(batch)


def repair_round(state: State, batch, cand_by_block) -> int:
    comp = competitors(state, batch, cand_by_block)
    free = list(dict.fromkeys(list(batch) + list(comp)))[:MAX_FREE]
    free_set = set(free)

    reserved_room, reserved_instr = set(), set()
    for bid, c in state.placed.items():
        if bid in free_set:
            continue
        s = state.sec_of[bid]; iids = state.sec_instr.get(s.section_id, [])
        for hh in range(c.start, c.start + c.length):
            if c.room not in state.virtual:
                reserved_room.add((c.room, c.day, hh))
            for iid in iids:
                reserved_instr.add((iid, c.day, hh))

    m = cp_model.CpModel()
    x = {}
    room_occ = defaultdict(list); instr_occ = defaultdict(list); sect_occ = defaultdict(list)
    unpl = {}
    cur = {}
    for bid in free:
        s = state.sec_of[bid]; iids = s.instructor_ids
        cands = [c for c in cand_by_block[bid]
                 if not any(((c.room not in state.virtual and (c.room, c.day, hh) in reserved_room)
                             or any((iid, c.day, hh) in reserved_instr for iid in iids))
                            for hh in range(c.start, c.start + c.length))]
        u = m.NewBoolVar(f"u|{bid}")
        unpl[bid] = u
        bvars = []
        for c in cands:
            v = m.NewBoolVar(f"x|{bid}|{c.room}|{c.day}|{c.start}")
            x[(bid, c.room, c.day, c.start)] = v
            bvars.append(v)
            for hh in range(c.start, c.start + c.length):
                if c.room not in state.virtual:
                    room_occ[(c.room, c.day, hh)].append(v)
                for iid in iids:
                    instr_occ[(iid, c.day, hh)].append(v)
                sect_occ[(s.section_id, c.day, hh)].append(v)
        m.AddExactlyOne(bvars + [u])
        if bid in state.placed:
            cur[bid] = state.placed[bid]
    for occ in (room_occ, instr_occ, sect_occ):
        for vs in occ.values():
            if len(vs) > 1:
                m.Add(sum(vs) <= 1)
    m.Minimize(BIG * sum(unpl.values()))

    for bid in free:
        if bid in cur:
            c = cur[bid]
            key = (bid, c.room, c.day, c.start)
            if key in x:
                m.AddHint(x[key], 1)
                m.AddHint(unpl[bid], 0)
        else:
            m.AddHint(unpl[bid], 1)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = REPAIR_TL
    solver.parameters.num_search_workers = 8
    st = solver.Solve(m)
    if st not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return 0

    new_assign = {}
    for (b, room, day, start), v in x.items():
        if solver.Value(v) == 1:
            length = next(c.length for c in cand_by_block[b]
                          if c.room == room and c.day == day and c.start == start)
            new_assign[b] = Candidate(b, room, day, start, length)

    old_count = sum(1 for bid in free if bid in state.placed)
    if len(new_assign) < old_count:
        return 0
    for bid in free:
        state.release(bid)
    for bid, c in new_assign.items():
        state.occupy(bid, c)
    return len(new_assign) - old_count
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_round.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: repair.repair_round relatedness neighborhood, monotonic accept"
```

### Task B.4: `solve_repair` entry point (loop-until-dry, build/return contract)

**Files:**
- Modify: `src/timetabling/repair.py` (add `solve_repair`)
- Test: `tests/test_repair_solve.py`

**Interfaces:**
- Consumes: all of B.1–B.3.
- Produces: `solve_repair(sections, rooms, instructors, cfg) -> Tuple[List[Assignment], Dict]` — same shape as `model_cpsat.build_and_solve`: `stats` has `status_name`, `n_blocks`, `n_vars` (0; not a single model), `unplaced` (list of block ids), `wall_time` (0.0; sweeps not timed here), plus `placed`/`total`. `rooms` is a `Dict[str, Room]` (matches `__main__` call site).

- [ ] **Step 1: Write the failing test** — create `tests/test_repair_solve.py`:

```python
def test_solve_repair_places_clean_small_instance():
    from timetabling.config import Config
    from timetabling.model import Room, Section, Block, Instructor
    from timetabling.repair import solve_repair
    from timetabling.validate import validate
    cfg = Config(solve_time_limit_s=5)
    rooms = {"R1": Room("R1", 50, False, True), "Online": Room("Online", 9999, False, False, True)}
    instr = {f"i{n}": Instructor(f"i{n}", "x", True, "D") for n in range(4)}

    def sec(sid, iid, students=30, virtual=False):
        s = Section(sid, "001", "X 101", "x", 1, "X", "F", "X-1", [iid], students,
                    2, 0, 0, 2, "", is_virtual=virtual)
        s.blocks = [Block(f"{sid}#T", sid, "theory", 2, False)]
        return s

    secs = [sec("A_01", "i0"), sec("B_01", "i1"), sec("C_01", "i2", 300, True)]
    assigns, stats = solve_repair(secs, rooms, instr, cfg)
    assert stats["placed"] == 3 and stats["unplaced"] == []
    assert validate(assigns, secs, rooms, instr, cfg) == []
```

- [ ] **Step 2: Run it to verify it fails**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_solve.py -v`
Expected: FAIL (`solve_repair` not defined).

- [ ] **Step 3: Implement** — append to `src/timetabling/repair.py`:

```python
def solve_repair(sections, rooms, instructors, cfg):
    room_list = list(rooms.values())
    virtual_names = {r.room for r in room_list if r.is_virtual}
    blocks = [(b, s) for s in sections for b in s.blocks]
    total = len(blocks)
    sec_of = {b.block_id: s for b, s in blocks}
    sec_instr = {s.section_id: s.instructor_ids for s in sections}

    cand_by_block = {}
    for b, s in blocks:
        ins_list = _instructors_of(s, instructors)
        cand_by_block[b.block_id] = gen_candidates(b, s, ins_list, room_list, cfg)

    order = sorted((b.block_id for b, _ in blocks),
                   key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))

    state = State(sec_of, sec_instr, virtual_names)
    greedy_construct(state, order, cand_by_block)

    sweep = 0
    while True:
        sweep += 1
        unplaced = [bid for bid, _ in [(b.block_id, s) for b, s in blocks]
                    if bid not in state.placed]
        if not unplaced:
            break
        unplaced.sort(key=lambda bid: (len(cand_by_block[bid]), -sec_of[bid].students))
        gained = 0
        for i in range(0, len(unplaced), BATCH):
            batch = [bid for bid in unplaced[i:i + BATCH] if bid not in state.placed]
            if batch:
                gained += repair_round(state, batch, cand_by_block)
        if gained == 0 or sweep >= 25:
            break

    assignments = []
    for bid, c in state.placed.items():
        s = sec_of[bid]
        kind = "lab" if "#L" in bid else "theory"
        assignments.append(Assignment(bid, s.section_id, kind, c.room, c.day, c.start,
                                       c.start + c.length))
    unplaced_ids = [b.block_id for b, _ in blocks if b.block_id not in state.placed]
    stats = {
        "status_name": "REPAIR",
        "n_blocks": total,
        "n_vars": 0,
        "unplaced": unplaced_ids,
        "wall_time": 0.0,
        "placed": len(state.placed),
        "total": total,
    }
    return assignments, stats
```

- [ ] **Step 4: Run it to verify it passes**

Run: `PYTHONPATH=src python3 -m pytest tests/test_repair_solve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "feat: repair.solve_repair loop-until-dry entry point"
```

### Task B.5: Wire `--repair` into the CLI

**Files:**
- Modify: `src/timetabling/__main__.py` (arg + Mode-A branch)
- Test: end-to-end run on full scope

**Interfaces:**
- Consumes: `repair.solve_repair` (B.4).
- Produces: `--repair` selects the repair solver for Mode-A; printed line reports `placed/total`.

- [ ] **Step 1: Add the flag** — in `src/timetabling/__main__.py`, near `--decompose`:

```python
    ap.add_argument("--repair", action="store_true",
                    help="warm-started small-neighborhood repair solver (full --scope all)")
```

- [ ] **Step 2: Add the import**

```python
from .repair import solve_repair
```

- [ ] **Step 3: Branch Mode-A** — extend the solver selection:

```python
        if args.repair:
            assignments, stats = solve_repair(sections, rooms, instructors, cfg)
        elif args.decompose:
            assignments, stats = solve_decomposed(sections, room_list, instructors, cfg)
        else:
            assignments, stats = _cpsat_solve(sections, room_list, instructors, cfg)
```

- [ ] **Step 4: Report placement** — after the `validate` call, extend the status print to handle repair stats:

```python
        if "placed" in stats:
            print(f"[mode-A] repair placed={stats['placed']}/{stats['total']} "
                  f"({stats['placed']/stats['total']:.1%}) unplaced={len(stats['unplaced'])} "
                  f"violations={len(viol)}")
        elif "status_name" in stats:
            print(f"[mode-A] status={stats['status_name']} blocks={stats['n_blocks']} "
                  f"vars={stats['n_vars']} unplaced={len(stats['unplaced'])} "
                  f"wall={stats['wall_time']:.1f}s violations={len(viol)}")
        else:
            print(f"[mode-A] decomposed groups={stats['n_groups']} "
                  f"assignments={stats['n_assignments']} violations={len(viol)}")
```

- [ ] **Step 5: Full-scope end-to-end run**

Run: `PYTHONPATH=src python3 -m timetabling --period 001 --scope all --mode A --repair`
Expected: `[mode-A] repair placed=~937/988 (~94%+) unplaced=~51 violations=0`. Wall time a few minutes.

- [ ] **Step 6: Full suite**

Run: `PYTHONPATH=src python3 -m pytest -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "feat: --repair CLI flag (warm-started repair solver, full scope)"
```

---

## Self-Review

**Spec coverage:**
- Remove Gurobi → Task 0.1. ✓
- Virtual room for online/oversize, drop AMFI → A.1–A.7. ✓
- Repair architecture (construction + warm-start + soft-H1 + monotonic + loop-until-dry) → B.1–B.5. ✓
- 0 hard violations preserved → validate exemptions (A.6) + end-to-end checks (A.7, B.5). ✓
- UI contract stable → export untouched; virtual room surfaces as `room="Online"`, `room_cap=9999` (additive only). ✓

**Open follow-ups (out of scope, log in TODO.md):** closing the residual ~5% tail (targeted instructor-graph neighborhoods, longer final solve); optional evening window for virtual/online sections; updating README results + `mode_b` benchmark to report repair placement.

**Type consistency:** `State(sec_of, sec_instr, virtual_names)`, `repair_round(state, batch, cand_by_block) -> int`, `solve_repair(sections, rooms_dict, instructors, cfg) -> (assignments, stats)` — consistent across B.1–B.5 and the `__main__` call site (passes `rooms` dict, matching `solve_repair`).
