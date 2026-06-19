# UCTP CP-SAT Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an end-to-end University Course Timetabling pipeline that loads the real CSVs, derives the model, solves a conflict-free timetable with OR-Tools CP-SAT (boolean-grid encoding), validates it independently, and exports `schedule.json` + reports — proven live on one faculty slice with a parameterized path to the full ~800-section period.

**Architecture:** A pipeline of small, single-purpose modules under `src/timetabling/` (load → clean → parse → join → derive → model → solve → validate → report → export), driven by a CLI. Hard constraints are enforced mostly by *candidate pruning* (only legal `(room, day, start)` placements are generated); only placement + instructor/cohort/room no-overlap are explicit CP-SAT constraints. A separate `validate.py` re-derives all hard-constraint violations independently of the solver so an encoding bug cannot pass silently.

**Tech Stack:** Python 3.9 (Anaconda), pandas, OR-Tools CP-SAT (`ortools`), pytest.

## Global Constraints

- **Quote-aware CSV only** — always `pandas.read_csv`, never `split(",")`. Read all columns as `dtype=str` to preserve leading zeros (`Period="001"`, `Staff_ID="00000002"`), convert numerics explicitly.
- **Roster = Grades files**, undergraduate only (course level 1–4) by default. Period `001`/`002` scheduled independently.
- **Cohort key = `f"{Dept_Code}-{Year_Level}"`** from `enrollment_by_section`.
- **`rules.pdf` Article 1 is IGNORED** — never enforced, never reported. Blocks decompose freely from T/P/L; 3+ hour single blocks allowed.
- **Time horizon:** days `["Mo","Tu","We","Th","Fr"]`, integer start-hours, occupancy slots 09–21. Undergrad blocks must **end ≤ 18:00**.
- **Friday prayer blackout** `Fri 13:00–14:00` (all sections) and **Thursday seminar blackout** `Thu 14:00–16:00` (full-time `Is_Staff=True` instructors only) — both parameters in `config.py`.
- **All parameters** (blackouts, windows, toggles, weights, time limit) live in `config.py` as a `Config` dataclass; functions accept a `cfg`.
- **Feasibility-first:** light weighted soft-objective under a solve-time cap (default 60 s); do not chase optimality.
- **Commits go to `main`** (no PRs). Each task ends with a commit.

**Known data facts (from `wc -l` / headers) to assert against:**
- `2025-01-Grades.csv`: 841 data rows; `2025-02-Grades.csv`: 826. `classrooms.csv`: 101; `lecturers.csv`: 340; `enrollment_by_section.csv`: 1667.
- Grades columns include `Period, Code, Name, Section, Dept., T, P, L, Cr, Category, Lecturer, Room, Schedule, # of Students, Staff ID` (note the trailing dot in `Dept.` and the spaces in `# of Students`/`Staff ID`).
- Plan files have **no** `Period` column (period = filename); key columns `COURSE_CODE, SECTION, LECTURER, ROOM, SCHEDULE, SECT_CAP`.
- Grades `Staff ID` may carry a ` (S)` suffix (e.g. `00005657 (S)`); normalize before joining to `lecturers.Staff_ID`.

---

## File Structure

```
pyproject.toml                     pytest config (pythonpath=src)
requirements.txt                   pandas, ortools, pytest
src/timetabling/
  __init__.py
  config.py        Config dataclass + DAYS constant
  model.py         dataclasses: Room, Instructor, Block, Section, Candidate, Assignment, Violation
  io_csv.py        quote-aware loaders (grades/plan/enrollment/classrooms/lecturers)
  textnorm.py      normalize_staff_id, normalize_name, parse_int
  schedule_parse.py  parse_schedule(raw) -> (sessions, errors)
  clean.py         classify_room, build_room_objects, build_instructor_objects
  join.py          build_section_frame(period, ...) -> pandas.DataFrame
  derive.py        build_sections(frame) -> list[Section]; course_level; blocks_from_tpl
  model_cpsat.py   gen_candidates, build_and_solve -> (assignments, stats)
  validate.py      validate(assignments, sections, rooms, instructors, cfg) -> list[Violation]
  report.py        data_quality_report, conflict_report, mode_b_benchmark
  export.py        write_schedule_json, write_csv
  __main__.py      CLI: load → pipeline → solve → validate → export → print evidence
tests/
  test_io_csv.py  test_schedule_parse.py  test_clean.py  test_join.py
  test_derive.py  test_model_cpsat.py  test_validate.py  test_export.py
out/                                generated reports + schedule.json + CSVs (gitignored)
```

---

### Task 1: Scaffold — package, config, data model, OR-Tools install

**Files:**
- Create: `requirements.txt`, `pyproject.toml`, `src/timetabling/__init__.py`, `src/timetabling/config.py`, `src/timetabling/model.py`
- Test: `tests/test_scaffold.py`

**Interfaces:**
- Produces: `config.Config` (dataclass, all params) and `config.DAYS: list[str]`; `model.Room`, `model.Instructor`, `model.Block`, `model.Section`, `model.Candidate`, `model.Assignment`, `model.Violation` dataclasses.

- [ ] **Step 1: Create dependency + pytest config files**

`requirements.txt`:
```
pandas>=1.3
ortools>=9.5
pytest>=7.0
```

`pyproject.toml`:
```toml
[tool.pytest.ini_options]
pythonpath = ["src"]
testpaths = ["tests"]
```

`src/timetabling/__init__.py`:
```python
"""University Course Timetabling (UCTP) CP-SAT pipeline."""
```

- [ ] **Step 2: Install OR-Tools and pytest**

Run: `python3 -m pip install ortools pytest`
Expected: ends with `Successfully installed ortools-... pytest-...` (pandas already present).
Verify: `python3 -c "from ortools.sat.python import cp_model; print('ok')"` → prints `ok`.

- [ ] **Step 3: Write `config.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field

DAYS = ["Mo", "Tu", "We", "Th", "Fr"]
SATURDAY = "Sa"

LAB_SUFFIXES = ("-PC-L", "-PSY-L", "-PSCG-L", "-PECE-L", "-EF-L", "-L")


@dataclass
class Config:
    # time model
    horizon_start: int = 9        # first start hour
    horizon_end: int = 21         # exclusive end of last occupancy slot (20-21)
    undergrad_end: int = 18       # undergrad blocks must end by this hour
    grad_start: int = 18
    grad_end: int = 21
    # blackouts: (day, hour) hour-slots that are closed
    friday_blackout: tuple = (("Fr", 13),)                 # 13:00-14:00
    seminar_blackout: tuple = (("Th", 14), ("Th", 15))     # Thu 14:00-16:00, full-time only
    # toggles
    saturday_enabled: bool = False
    include_grad: bool = False
    include_plan_only: bool = False
    excluded_categories: tuple = ("Internship",)
    online_room: str = "Online"
    # solver
    solve_time_limit_s: float = 60.0
    # objective weights (light)
    w_evening: int = 4
    w_room_count: int = 2
    w_instr_days: int = 3
    w_parttime_days: int = 5
    evening_from_hour: int = 17   # an hour-slot >= this counts as "evening" for the soft penalty

    def days(self) -> list:
        return DAYS + [SATURDAY] if self.saturday_enabled else list(DAYS)
```

- [ ] **Step 4: Write `model.py`**

```python
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List


@dataclass(frozen=True)
class Room:
    room: str
    cap: int
    is_lab: bool
    is_physical: bool


@dataclass(frozen=True)
class Instructor:
    staff_id: str
    name: str
    is_staff: bool          # True = full-time
    home_dept: str


@dataclass(frozen=True)
class Block:
    block_id: str           # e.g. "ADA 403_01#T" or "...#L"
    section_id: str
    kind: str               # "theory" | "lab"
    length: int             # hours
    needs_lab: bool


@dataclass
class Section:
    section_id: str
    period: str
    code: str               # "ADA 403"
    name: str
    level: int              # 1..6
    dept_code: str          # "ADA"
    faculty: str            # Grades "Dept." column (faculty name)
    cohort_key: str         # "ADA-4"
    instructor_id: str
    students: int
    T: int
    P: int
    L: int
    Cr: int
    category: str
    blocks: List[Block] = field(default_factory=list)


@dataclass(frozen=True)
class Candidate:
    block_id: str
    room: str
    day: str
    start: int              # start hour
    length: int


@dataclass(frozen=True)
class Assignment:
    block_id: str
    section_id: str
    kind: str
    room: str
    day: str
    start: int
    end: int                # exclusive (start + length)


@dataclass(frozen=True)
class Violation:
    kind: str               # "instructor" | "cohort" | "room" | "capacity" | "lab" | "window" | "blackout" | "placement"
    detail: str
```

- [ ] **Step 5: Write `tests/test_scaffold.py`**

```python
from timetabling.config import Config, DAYS
from timetabling.model import Room, Section, Block

def test_config_defaults():
    cfg = Config()
    assert DAYS == ["Mo", "Tu", "We", "Th", "Fr"]
    assert cfg.undergrad_end == 18
    assert cfg.days() == ["Mo", "Tu", "We", "Th", "Fr"]
    cfg2 = Config(saturday_enabled=True)
    assert "Sa" in cfg2.days()

def test_model_dataclasses():
    r = Room("A216", 25, False, True)
    assert r.cap == 25 and not r.is_lab
    s = Section("X_01", "001", "X 101", "n", 1, "X", "Fac", "X-1", "id", 30,
                3, 0, 0, 3, "Course")
    assert s.blocks == []
```

- [ ] **Step 6: Run tests**

Run: `python3 -m pytest tests/test_scaffold.py -v`
Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt pyproject.toml src/timetabling/__init__.py src/timetabling/config.py src/timetabling/model.py tests/test_scaffold.py
git commit -m "feat: scaffold package, config, data model; install ortools"
```

---

### Task 2: `textnorm.py` — string/number normalization helpers

**Files:**
- Create: `src/timetabling/textnorm.py`
- Test: `tests/test_textnorm.py`

**Interfaces:**
- Produces: `normalize_staff_id(s: str) -> str`, `normalize_name(s: str) -> str`, `parse_int(s, default=None) -> int|None`.

- [ ] **Step 1: Write the failing test `tests/test_textnorm.py`**

```python
from timetabling.textnorm import normalize_staff_id, normalize_name, parse_int

def test_normalize_staff_id_strips_s_suffix():
    assert normalize_staff_id("00005657 (S)") == "00005657"
    assert normalize_staff_id(" 00006729 ") == "00006729"
    assert normalize_staff_id("") == ""

def test_normalize_name():
    assert normalize_name("Mustafa Kerem Yüksel (S)") == "Mustafa Kerem Yüksel"
    assert normalize_name("  Orhan   Gencel ") == "Orhan Gencel"

def test_parse_int():
    assert parse_int("24") == 24
    assert parse_int("", default=0) == 0
    assert parse_int("3,70", default=-1) == -1   # comma-decimal is not an int
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_textnorm.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'timetabling.textnorm'`.

- [ ] **Step 3: Write `src/timetabling/textnorm.py`**

```python
from __future__ import annotations
import re

_S_SUFFIX = re.compile(r"\(S\)")
_WS = re.compile(r"\s+")


def normalize_staff_id(s: str) -> str:
    if s is None:
        return ""
    s = _S_SUFFIX.sub("", str(s))
    return _WS.sub("", s).strip()


def normalize_name(s: str) -> str:
    if s is None:
        return ""
    s = _S_SUFFIX.sub("", str(s))
    return _WS.sub(" ", s).strip()


def parse_int(s, default=None):
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return default
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_textnorm.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/textnorm.py tests/test_textnorm.py
git commit -m "feat: text/number normalization helpers"
```

---

### Task 3: `schedule_parse.py` — SCHEDULE grammar parser

**Files:**
- Create: `src/timetabling/schedule_parse.py`
- Test: `tests/test_schedule_parse.py`

**Interfaces:**
- Produces: `ParsedSession(day:str, start:int, end:int)` dataclass; `parse_schedule(raw:str, valid_days=frozenset(...)) -> tuple[list[ParsedSession], list[str]]`. Returns `(sessions, errors)`; values not starting with a valid day token yield an error string and are NOT repaired.

- [ ] **Step 1: Write the failing test `tests/test_schedule_parse.py`**

```python
from timetabling.schedule_parse import parse_schedule, ParsedSession

def test_single_unit():
    sessions, errors = parse_schedule("Fr 13 - 16")
    assert errors == []
    assert sessions == [ParsedSession("Fr", 13, 16)]

def test_chained_sessions():
    sessions, errors = parse_schedule("Th 09 - 12 Th 13 - 16")
    assert errors == []
    assert sessions == [ParsedSession("Th", 9, 12), ParsedSession("Th", 13, 16)]

def test_multiday_slash():
    sessions, errors = parse_schedule("Tu/Fr 09 - 12")
    assert errors == []
    assert sessions == [ParsedSession("Tu", 9, 12), ParsedSession("Fr", 9, 12)]

def test_empty_is_empty_no_error():
    assert parse_schedule("") == ([], [])
    assert parse_schedule("   ") == ([], [])

def test_dirty_value_flagged_not_repaired():
    sessions, errors = parse_schedule("Işıl Sevilay Yılmaz")
    assert sessions == []
    assert len(errors) == 1 and "does not start with a valid day" in errors[0]

def test_dirty_room_code_flagged():
    sessions, errors = parse_schedule("D232")
    assert sessions == []
    assert len(errors) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_schedule_parse.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/schedule_parse.py`**

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

VALID_DAYS = frozenset({"Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"})


@dataclass(frozen=True)
class ParsedSession:
    day: str
    start: int
    end: int


def _expand_days(token: str) -> List[str]:
    # "Tu/Fr" -> ["Tu", "Fr"]; "Fr" -> ["Fr"]
    return [d for d in token.split("/") if d]


def parse_schedule(raw: str, valid_days=VALID_DAYS) -> Tuple[List[ParsedSession], List[str]]:
    """Parse a SCHEDULE cell into sessions. Returns (sessions, errors).
    Grammar (repeated): <day[/day...]> <start:int> '-' <end:int>.
    A value whose first token is not a valid day is reported as an error and
    NOT auto-repaired (handles ~11 column-shift rows)."""
    if raw is None:
        return [], []
    text = str(raw).strip()
    if text == "":
        return [], []

    tokens = text.split()
    first_day_token = tokens[0].split("/")[0]
    if first_day_token not in valid_days:
        return [], [f"SCHEDULE value does not start with a valid day token: {text!r}"]

    sessions: List[ParsedSession] = []
    errors: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        day_token = tokens[i]
        days = _expand_days(day_token)
        if not days or any(d not in valid_days for d in days):
            errors.append(f"Unexpected token where a day was expected: {day_token!r} in {text!r}")
            break
        # need: start, '-', end
        if i + 3 >= n + 0 or i + 3 > n:  # ensure 3 more tokens exist (start, '-', end)
            errors.append(f"Incomplete session after {day_token!r} in {text!r}")
            break
        start_tok, dash_tok, end_tok = tokens[i + 1], tokens[i + 2], tokens[i + 3]
        if dash_tok != "-" or not start_tok.isdigit() or not end_tok.isdigit():
            errors.append(f"Malformed session near {day_token!r} in {text!r}")
            break
        start, end = int(start_tok), int(end_tok)
        if not (0 <= start < end <= 24):
            errors.append(f"Bad hour range {start}-{end} in {text!r}")
            break
        for d in days:
            sessions.append(ParsedSession(d, start, end))
        i += 4
    return sessions, errors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_schedule_parse.py -v`
Expected: 6 passed.

- [ ] **Step 5: Sanity-check the parser against real data**

Run:
```bash
python3 -c "
import pandas as pd; from timetabling.schedule_parse import parse_schedule
df = pd.read_csv('data/2025-01-Plan.csv', dtype=str).fillna('')
bad = [s for s in df['SCHEDULE'] if s.strip() and parse_schedule(s)[1]]
print('dirty SCHEDULE rows:', len(bad)); print(bad[:5])
"
```
Expected: a small count (single digits, ~5–11) of dirty values printed (instructor names / room codes), confirming the flag-not-repair behavior.

- [ ] **Step 6: Commit**

```bash
git add src/timetabling/schedule_parse.py tests/test_schedule_parse.py
git commit -m "feat: SCHEDULE grammar parser (units, chains, X/Y, dirty-flagging)"
```

---

### Task 4: `io_csv.py` — quote-aware loaders

**Files:**
- Create: `src/timetabling/io_csv.py`
- Test: `tests/test_io_csv.py`

**Interfaces:**
- Produces: `DATA_DIR: Path`; `load_grades(period:str) -> DataFrame`, `load_plan(period:str) -> DataFrame`, `load_enrollment() -> DataFrame`, `load_classrooms() -> DataFrame`, `load_lecturers() -> DataFrame`. All return `dtype=str` frames with NaN filled as `""`. `load_plan` attaches a `period` column (`001`/`002`) from the filename. Period→filename map: `001`→`2025-01-*`, `002`→`2025-02-*`.

- [ ] **Step 1: Write the failing test `tests/test_io_csv.py`**

```python
import pytest
from timetabling import io_csv

def test_load_grades_counts_and_columns():
    g = io_csv.load_grades("001")
    assert len(g) == 841
    for col in ["Period", "Code", "Section", "T", "P", "L", "Cr",
                "Category", "Lecturer", "Room", "Schedule", "# of Students", "Staff ID", "Dept."]:
        assert col in g.columns
    assert set(g["Period"].unique()) == {"001"}

def test_load_grades_002():
    assert len(io_csv.load_grades("002")) == 826

def test_load_plan_attaches_period_and_has_no_native_period():
    p = io_csv.load_plan("001")
    assert "period" in p.columns and set(p["period"].unique()) == {"001"}
    assert "SECTION" in p.columns and "SCHEDULE" in p.columns

def test_load_masters():
    assert len(io_csv.load_classrooms()) == 101
    assert len(io_csv.load_lecturers()) == 340
    assert len(io_csv.load_enrollment()) == 1667
    # quote-aware: course names with commas must not shift columns
    assert "ROOM_CAP" in io_csv.load_classrooms().columns
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_io_csv.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/io_csv.py`**

```python
from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_PERIOD_FILE = {"001": "2025-01", "002": "2025-02"}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, dtype=str).fillna("")


def load_grades(period: str) -> pd.DataFrame:
    return _read(f"{_PERIOD_FILE[period]}-Grades.csv")


def load_plan(period: str) -> pd.DataFrame:
    df = _read(f"{_PERIOD_FILE[period]}-Plan.csv")
    df = df.copy()
    df["period"] = period
    return df


def load_enrollment() -> pd.DataFrame:
    return _read("enrollment_by_section.csv")


def load_classrooms() -> pd.DataFrame:
    return _read("classrooms.csv")


def load_lecturers() -> pd.DataFrame:
    return _read("lecturers.csv")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_io_csv.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/io_csv.py tests/test_io_csv.py
git commit -m "feat: quote-aware CSV loaders with period attachment"
```

---

### Task 5: `clean.py` — room classification & domain master objects

**Files:**
- Create: `src/timetabling/clean.py`
- Test: `tests/test_clean.py`

**Interfaces:**
- Consumes: `io_csv` frames; `config.LAB_SUFFIXES`, `config.Config`; `model.Room`, `model.Instructor`; `textnorm`.
- Produces: `classify_room(name:str) -> bool` (is_lab); `build_rooms(classrooms_df, cfg) -> dict[str, Room]`; `build_instructors(lecturers_df) -> dict[str, Instructor]` keyed by `staff_id`.

- [ ] **Step 1: Write the failing test `tests/test_clean.py`**

```python
from timetabling import io_csv, clean
from timetabling.config import Config

def test_classify_room():
    assert clean.classify_room("A514-PC-L") is True
    assert clean.classify_room("A211-PC-L") is True
    assert clean.classify_room("A231-H") is False
    assert clean.classify_room("F306") is False

def test_build_rooms_marks_online_nonphysical_and_lab_count():
    rooms = clean.build_rooms(io_csv.load_classrooms(), Config())
    assert "Online" in rooms and rooms["Online"].is_physical is False
    physical = [r for r in rooms.values() if r.is_physical]
    assert len(physical) == 100                      # 101 total - 1 online
    labs = [r for r in physical if r.is_lab]
    assert 8 <= len(labs) <= 20                       # ~14 lab/PC rooms
    assert rooms["A216"].cap == 25

def test_build_instructors_full_vs_part_time():
    instr = clean.build_instructors(io_csv.load_lecturers())
    assert len(instr) == 340
    sample = next(iter(instr.values()))
    assert isinstance(sample.is_staff, bool)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_clean.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/clean.py`**

```python
from __future__ import annotations
from typing import Dict
import pandas as pd

from .config import Config, LAB_SUFFIXES
from .model import Room, Instructor
from .textnorm import normalize_staff_id, normalize_name, parse_int


def classify_room(name: str) -> bool:
    n = str(name).strip().upper()
    return any(n.endswith(suf) for suf in LAB_SUFFIXES)


def build_rooms(classrooms_df: pd.DataFrame, cfg: Config) -> Dict[str, Room]:
    rooms: Dict[str, Room] = {}
    for _, row in classrooms_df.iterrows():
        name = row["ROOM"].strip()
        if not name:
            continue
        cap = parse_int(row["ROOM_CAP"], default=0)
        is_physical = name != cfg.online_room
        rooms[name] = Room(room=name, cap=cap, is_lab=classify_room(name),
                            is_physical=is_physical)
    return rooms


def build_instructors(lecturers_df: pd.DataFrame) -> Dict[str, Instructor]:
    instr: Dict[str, Instructor] = {}
    for _, row in lecturers_df.iterrows():
        sid = normalize_staff_id(row["Staff_ID"])
        if not sid:
            continue
        instr[sid] = Instructor(
            staff_id=sid,
            name=normalize_name(row["Name"]),
            is_staff=str(row["Is_Staff"]).strip().lower() == "true",
            home_dept=str(row["Dept"]).strip(),
        )
    return instr
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_clean.py -v`
Expected: 3 passed. (If the lab count assertion fails, print `[r.room for r in physical if r.is_lab]` and adjust the documented suffix list in `config.LAB_SUFFIXES` to match observed lab rooms — record the change in the data-quality report.)

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/clean.py tests/test_clean.py
git commit -m "feat: room classification (lab/online/physical) and instructor master objects"
```

---

### Task 6: `join.py` — build the joined section frame

**Files:**
- Create: `src/timetabling/join.py`
- Test: `tests/test_join.py`

**Interfaces:**
- Consumes: `io_csv` frames; `textnorm.normalize_staff_id`.
- Produces: `build_section_frame(period:str, include_plan_only:bool=False) -> DataFrame` with columns: `section_id, period, code, name, faculty, T, P, L, Cr, category, staff_id, grades_students, lecturer_name, dept_code, year_level, enroll_students, plan_sect_cap, plan_room, plan_schedule`. One row per Grades section (LEFT joins on enrollment + plan). `dept_code`/`year_level` come from `enrollment_by_section`.

- [ ] **Step 1: Write the failing test `tests/test_join.py`**

```python
from timetabling import join

def test_build_section_frame_001():
    df = join.build_section_frame("001")
    assert len(df) == 841                       # one row per Grades section
    row = df[df["section_id"] == "ADA 403_01"].iloc[0]
    assert row["staff_id"] == "00005657"        # (S) stripped
    assert row["dept_code"] == "ADA" and row["year_level"] == "4"
    assert row["plan_schedule"] == "Fr 13 - 16" # LEFT join into Plan
    assert int(row["T"]) == 3

def test_enrollment_join_coverage():
    df = join.build_section_frame("001")
    matched = (df["dept_code"] != "").sum()
    assert matched / len(df) > 0.85             # most sections find a cohort
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_join.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/join.py`**

```python
from __future__ import annotations
import pandas as pd

from . import io_csv
from .textnorm import normalize_staff_id, normalize_name


def build_section_frame(period: str, include_plan_only: bool = False) -> pd.DataFrame:
    grades = io_csv.load_grades(period).copy()
    enroll = io_csv.load_enrollment().copy()
    plan = io_csv.load_plan(period).copy()

    g = pd.DataFrame({
        "section_id": grades["Section"].str.strip(),
        "period": grades["Period"].str.strip(),
        "code": grades["Code"].str.strip(),
        "name": grades["Name"].str.strip(),
        "faculty": grades["Dept."].str.strip(),
        "T": grades["T"], "P": grades["P"], "L": grades["L"], "Cr": grades["Cr"],
        "category": grades["Category"].str.strip(),
        "staff_id": grades["Staff ID"].map(normalize_staff_id),
        "grades_students": grades["# of Students"],
        "lecturer_name": grades["Lecturer"].map(normalize_name),
    })

    e = enroll[enroll["Period"].str.strip() == period][
        ["Section", "Dept_Code", "Year_Level", "Students"]
    ].rename(columns={"Section": "section_id", "Dept_Code": "dept_code",
                      "Year_Level": "year_level", "Students": "enroll_students"})
    e["section_id"] = e["section_id"].str.strip()
    e = e.drop_duplicates("section_id")

    p = plan[["SECTION", "SECT_CAP", "ROOM", "SCHEDULE"]].rename(columns={
        "SECTION": "section_id", "SECT_CAP": "plan_sect_cap",
        "ROOM": "plan_room", "SCHEDULE": "plan_schedule"})
    p["section_id"] = p["section_id"].str.strip()
    p = p.drop_duplicates("section_id")

    df = g.merge(e, on="section_id", how="left").merge(p, on="section_id", how="left")
    df = df.fillna("")

    if include_plan_only:
        extra = p[~p["section_id"].isin(df["section_id"])].copy()
        extra["period"] = period
        df = pd.concat([df, extra], ignore_index=True).fillna("")
    return df
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_join.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/join.py tests/test_join.py
git commit -m "feat: build joined section frame (Grades ⨝ enrollment ⨝ Plan)"
```

---

### Task 7: `derive.py` — domain Sections + Blocks, level, cohort, exclusions

**Files:**
- Create: `src/timetabling/derive.py`
- Test: `tests/test_derive.py`

**Interfaces:**
- Consumes: joined frame from `join.build_section_frame`; `config.Config`; `model.Section`, `model.Block`; `textnorm.parse_int`.
- Produces: `course_level(code:str) -> int`; `blocks_from_tpl(section_id, T, P, L, Cr) -> list[Block]`; `build_sections(frame, cfg) -> tuple[list[Section], dict]` where the dict is a derivation report (`excluded`, `missing_cohort`, `missing_hours`, `hours_rule`). Sections with `category in cfg.excluded_categories` or (default) graduate level (>4 when `include_grad` False) are dropped and counted.

- [ ] **Step 1: Write the failing test `tests/test_derive.py`**

```python
from timetabling.config import Config
from timetabling import derive, join

def test_course_level():
    assert derive.course_level("ADA 403") == 4
    assert derive.course_level("MATH 101") == 1
    assert derive.course_level("ARCH 510") == 5
    assert derive.course_level("X 612") == 6

def test_blocks_from_tpl_theory_only():
    blocks = derive.blocks_from_tpl("S_01", 3, 0, 0, 3)
    assert len(blocks) == 1
    assert blocks[0].kind == "theory" and blocks[0].length == 3 and not blocks[0].needs_lab

def test_blocks_from_tpl_theory_plus_lab():
    blocks = derive.blocks_from_tpl("S_01", 2, 0, 2, 3)
    kinds = {b.kind: b for b in blocks}
    assert kinds["theory"].length == 2 and kinds["lab"].length == 2
    assert kinds["lab"].needs_lab is True

def test_blocks_practice_folds_into_theory():
    blocks = derive.blocks_from_tpl("S_01", 2, 2, 0, 3)
    assert len(blocks) == 1 and blocks[0].length == 4   # T+P

def test_blocks_zero_defaults_to_three():
    blocks = derive.blocks_from_tpl("S_01", 0, 0, 0, 3)
    assert len(blocks) == 1 and blocks[0].length == 3

def test_build_sections_excludes_grad_and_internship():
    df = join.build_section_frame("001")
    sections, rep = derive.build_sections(df, Config())
    assert all(s.level <= 4 for s in sections)
    assert all(s.category not in Config().excluded_categories for s in sections)
    assert rep["excluded"] >= 0 and "hours_rule" in rep
    # cohort key shape
    s = next(s for s in sections if s.section_id == "ADA 403_01")
    assert s.cohort_key == "ADA-4" and s.students == 24
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_derive.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/derive.py`**

```python
from __future__ import annotations
import re
from typing import List, Tuple, Dict

from .config import Config
from .model import Section, Block
from .textnorm import parse_int

_NUM = re.compile(r"(\d{3})")


def course_level(code: str) -> int:
    m = _NUM.search(str(code))
    if not m:
        return 0
    return int(m.group(1)[0])


def blocks_from_tpl(section_id: str, T: int, P: int, L: int, Cr: int) -> List[Block]:
    blocks: List[Block] = []
    theory_len = (T or 0) + (P or 0)
    lab_len = L or 0
    if theory_len > 0:
        blocks.append(Block(f"{section_id}#T", section_id, "theory", theory_len, False))
    if lab_len > 0:
        blocks.append(Block(f"{section_id}#L", section_id, "lab", lab_len, True))
    if not blocks:
        default_len = Cr if (Cr and Cr > 0) else 3
        blocks.append(Block(f"{section_id}#T", section_id, "theory", default_len, False))
    return blocks


def _students(row) -> int:
    for key in ("enroll_students", "plan_sect_cap", "grades_students"):
        v = parse_int(row.get(key, ""), default=None)
        if v is not None and v > 0:
            return v
    return 1


def build_sections(frame, cfg: Config) -> Tuple[List[Section], Dict]:
    sections: List[Section] = []
    report = {"excluded": 0, "missing_cohort": 0, "missing_hours": 0,
              "hours_rule": "theory = T+P, lab = L (default 3h if all zero)"}
    for _, row in frame.iterrows():
        r = row.to_dict()
        sid = r.get("section_id", "").strip()
        if not sid:
            continue
        category = r.get("category", "").strip()
        if category in cfg.excluded_categories:
            report["excluded"] += 1
            continue
        code = r.get("code", "").strip()
        level = course_level(code)
        if not cfg.include_grad and level > 4:
            report["excluded"] += 1
            continue
        T = parse_int(r.get("T"), 0); P = parse_int(r.get("P"), 0)
        L = parse_int(r.get("L"), 0); Cr = parse_int(r.get("Cr"), 0)
        if (T + P + L) == 0:
            report["missing_hours"] += 1
        dept_code = r.get("dept_code", "").strip()
        year = r.get("year_level", "").strip()
        if dept_code and year:
            cohort = f"{dept_code}-{year}"
        else:
            report["missing_cohort"] += 1
            dept_code = dept_code or (code.split()[0] if code else "UNK")
            cohort = f"{dept_code}-{level}"
        s = Section(
            section_id=sid, period=r.get("period", "").strip(), code=code,
            name=r.get("name", "").strip(), level=level, dept_code=dept_code,
            faculty=r.get("faculty", "").strip(), cohort_key=cohort,
            instructor_id=r.get("staff_id", "").strip(), students=_students(r),
            T=T, P=P, L=L, Cr=Cr, category=category,
            blocks=blocks_from_tpl(sid, T, P, L, Cr),
        )
        sections.append(s)
    return sections, report
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_derive.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/derive.py tests/test_derive.py
git commit -m "feat: derive Sections+Blocks (level, cohort, hours rule, exclusions)"
```

---

### Task 8: `model_cpsat.py` — candidate generation, pruning, CP-SAT solve

**Files:**
- Create: `src/timetabling/model_cpsat.py`
- Test: `tests/test_model_cpsat.py`

**Interfaces:**
- Consumes: `model.Section/Block/Room/Instructor/Candidate/Assignment`; `config.Config`.
- Produces:
  - `gen_candidates(block, section, instructor, rooms, cfg) -> list[Candidate]`
  - `build_and_solve(sections, rooms, instructors, cfg) -> tuple[list[Assignment], dict]` where dict = `{status, status_name, objective, wall_time, n_blocks, n_vars, unplaced:[block_id]}`.

- [ ] **Step 1: Write the failing test `tests/test_model_cpsat.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor
from timetabling import model_cpsat

def _sec(sid, level, students, blocks, instr="i1", cohort="D-1"):
    s = Section(sid, "001", "D 101", "n", level, "D", "Fac", cohort, instr,
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

def test_gen_candidates_respects_capacity_and_window():
    cfg = Config()
    rooms = [Room("R1", 30, False, True), Room("R2", 10, False, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#T", "S_01", "theory", 3, False)
    s = _sec("S_01", 1, 25, [b])
    cands = model_cpsat.gen_candidates(b, s, instr, rooms, cfg)
    # only R1 (cap>=25), starts so that start+3<=18 -> 9..15, 5 weekdays, minus Fri-13 blackout coverage
    assert all(c.room == "R1" for c in cands)
    assert all(c.start + b.length <= cfg.undergrad_end for c in cands)
    # Friday 13:00 blackout: no candidate covering Fri hour 13
    assert not any(c.day == "Fr" and c.start <= 13 < c.start + b.length for c in cands)

def test_gen_candidates_lab_requires_lab_room():
    cfg = Config()
    rooms = [Room("R1", 50, False, True), Room("LAB-L", 50, True, True)]
    instr = Instructor("i1", "n", False, "D")
    b = Block("S_01#L", "S_01", "lab", 2, True)
    s = _sec("S_01", 1, 20, [b])
    cands = model_cpsat.gen_candidates(b, s, instr, rooms, cfg)
    assert cands and all(c.room == "LAB-L" for c in cands)

def test_gen_candidates_seminar_blackout_fulltime_only():
    cfg = Config()
    rooms = [Room("R1", 50, False, True)]
    b = Block("S_01#T", "S_01", "theory", 1, False)
    s = _sec("S_01", 1, 10, [b])
    full = Instructor("i1", "n", True, "D")
    part = Instructor("i2", "n", False, "D")
    c_full = model_cpsat.gen_candidates(b, s, full, rooms, cfg)
    c_part = model_cpsat.gen_candidates(b, s, part, rooms, cfg)
    assert not any(x.day == "Th" and x.start in (14, 15) for x in c_full)
    assert any(x.day == "Th" and x.start in (14, 15) for x in c_part)

def test_build_and_solve_tiny_feasible_instance():
    cfg = Config(solve_time_limit_s=10)
    rooms = [Room("R1", 50, False, True), Room("R2", 50, False, True)]
    instructors = {"i1": Instructor("i1", "n", False, "D")}
    # two sections, same instructor+cohort, each one 1h theory block -> must not overlap in time
    s1 = _sec("S1_01", 1, 10, [], instr="i1", cohort="D-1")
    s2 = _sec("S2_01", 1, 10, [], instr="i1", cohort="D-1")
    s1.blocks = [Block("S1_01#T", "S1_01", "theory", 1, False)]
    s2.blocks = [Block("S2_01#T", "S2_01", "theory", 1, False)]
    assigns, stats = model_cpsat.build_and_solve([s1, s2], rooms, instructors, cfg)
    assert stats["status_name"] in ("OPTIMAL", "FEASIBLE")
    assert len(assigns) == 2
    a1, a2 = assigns
    # same instructor => cannot share the same (day, hour)
    assert not (a1.day == a2.day and a1.start == a2.start)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_model_cpsat.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/model_cpsat.py`**

```python
from __future__ import annotations
from typing import List, Dict, Tuple
from collections import defaultdict

from ortools.sat.python import cp_model

from .config import Config
from .model import Section, Block, Room, Instructor, Candidate, Assignment


def _blackout_hours(instructor: Instructor, cfg: Config):
    closed = set(cfg.friday_blackout)
    if instructor.is_staff:
        closed |= set(cfg.seminar_blackout)
    return closed


def gen_candidates(block: Block, section: Section, instructor: Instructor,
                   rooms: List[Room], cfg: Config) -> List[Candidate]:
    end_cap = cfg.undergrad_end if section.level <= 4 else cfg.grad_end
    start_lo = cfg.horizon_start if section.level <= 4 else cfg.grad_start
    closed = _blackout_hours(instructor, cfg)

    feasible_rooms = [
        r for r in rooms
        if r.is_physical and r.cap >= section.students and (r.is_lab if block.needs_lab else True)
    ]
    cands: List[Candidate] = []
    for r in feasible_rooms:
        for d in cfg.days():
            for h in range(start_lo, end_cap - block.length + 1):
                span = range(h, h + block.length)
                if any((d, hh) in closed for hh in span):
                    continue
                cands.append(Candidate(block.block_id, r.room, d, h, block.length))
    return cands


def build_and_solve(sections: List[Section], rooms: List[Room],
                    instructors: Dict[str, Instructor], cfg: Config
                    ) -> Tuple[List[Assignment], Dict]:
    model = cp_model.CpModel()
    sec_by_id = {s.section_id: s for s in sections}
    blocks = [(b, s) for s in sections for b in s.blocks]

    x: Dict[tuple, cp_model.IntVar] = {}
    cand_by_block: Dict[str, List[Candidate]] = {}
    unplaced: List[str] = []
    default_instr = Instructor("", "", False, "")

    # occupancy maps: key -> list of bool vars covering it
    room_occ = defaultdict(list)     # (room, day, hour)
    instr_occ = defaultdict(list)    # (instr_id, day, hour)
    cohort_occ = defaultdict(list)   # (cohort, day, hour)
    room_used_vars = defaultdict(list)            # room -> vars
    instr_day_vars = defaultdict(list)            # (instr_id, day) -> vars
    evening_vars = []

    for b, s in blocks:
        ins = instructors.get(s.instructor_id, default_instr)
        cands = gen_candidates(b, s, ins, rooms, cfg)
        cand_by_block[b.block_id] = cands
        if not cands:
            unplaced.append(b.block_id)
            continue
        bvars = []
        for c in cands:
            v = model.NewBoolVar(f"x|{c.block_id}|{c.room}|{c.day}|{c.start}")
            x[(c.block_id, c.room, c.day, c.start)] = v
            bvars.append(v)
            for hh in range(c.start, c.start + c.length):
                room_occ[(c.room, c.day, hh)].append(v)
                instr_occ[(s.instructor_id, c.day, hh)].append(v)
                cohort_occ[(s.cohort_key, c.day, hh)].append(v)
                if hh >= cfg.evening_from_hour:
                    evening_vars.append(v)
            room_used_vars[c.room].append(v)
            instr_day_vars[(s.instructor_id, c.day)].append(v)
        model.AddExactlyOne(bvars)   # H1

    # H2/H3/H4: at most one occupant per resource-slot
    for occ in (room_occ, instr_occ, cohort_occ):
        for key, vs in occ.items():
            if len(vs) > 1:
                model.Add(sum(vs) <= 1)

    # soft: room-used indicators
    room_used = {}
    for room, vs in room_used_vars.items():
        y = model.NewBoolVar(f"room_used|{room}")
        model.Add(sum(vs) >= 1).OnlyEnforceIf(y)
        model.Add(sum(vs) == 0).OnlyEnforceIf(y.Not())
        room_used[room] = y

    # soft: instructor-day indicators (heavier weight for part-time)
    instr_day = {}
    for (iid, day), vs in instr_day_vars.items():
        d = model.NewBoolVar(f"iday|{iid}|{day}")
        model.Add(sum(vs) >= 1).OnlyEnforceIf(d)
        model.Add(sum(vs) == 0).OnlyEnforceIf(d.Not())
        instr_day[(iid, day)] = d

    obj = []
    obj += [cfg.w_evening * v for v in evening_vars]
    obj += [cfg.w_room_count * y for y in room_used.values()]
    for (iid, day), d in instr_day.items():
        ins = instructors.get(iid, default_instr)
        w = cfg.w_instr_days if ins.is_staff else cfg.w_parttime_days
        obj.append(w * d)
    if obj:
        model.Minimize(sum(obj))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = cfg.solve_time_limit_s
    solver.parameters.num_search_workers = 8
    status = solver.Solve(model)

    assignments: List[Assignment] = []
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        for (bid, room, day, start), v in x.items():
            if solver.Value(v) == 1:
                length = next(c.length for c in cand_by_block[bid]
                              if c.room == room and c.day == day and c.start == start)
                sid = bid.split("#")[0]
                kind = "lab" if bid.endswith("#L") else "theory"
                assignments.append(Assignment(bid, sid, kind, room, day, start, start + length))

    stats = {
        "status": int(status),
        "status_name": solver.StatusName(status),
        "objective": solver.ObjectiveValue() if obj and status in (cp_model.OPTIMAL, cp_model.FEASIBLE) else None,
        "wall_time": solver.WallTime(),
        "n_blocks": len(blocks),
        "n_vars": len(x),
        "unplaced": unplaced,
    }
    return assignments, stats
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_model_cpsat.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/model_cpsat.py tests/test_model_cpsat.py
git commit -m "feat: CP-SAT boolean-grid model with candidate pruning and light objective"
```

---

### Task 9: `validate.py` — independent hard-constraint checker

**Files:**
- Create: `src/timetabling/validate.py`
- Test: `tests/test_validate.py`

**Interfaces:**
- Consumes: `list[Assignment]`, `list[Section]`, `dict[str,Room]`, `dict[str,Instructor]`, `config.Config`; `model.Violation`.
- Produces: `validate(assignments, sections, rooms, instructors, cfg) -> list[Violation]`. Re-derives every hard constraint independently of the solver. Empty list = feasible.

- [ ] **Step 1: Write the failing test `tests/test_validate.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import validate

def _sec(sid, level, students, blocks, instr="i1", cohort="D-1"):
    s = Section(sid, "001", "D 101", "n", level, "D", "Fac", cohort, instr,
                students, 0, 0, 0, 0, "Course")
    s.blocks = blocks
    return s

ROOMS = {"R1": Room("R1", 50, False, True), "LAB-L": Room("LAB-L", 50, True, True)}
INSTR = {"i1": Instructor("i1", "n", True, "D"), "i2": Instructor("i2", "n", False, "D")}

def test_clean_solution_has_no_violations():
    s = _sec("S_01", 1, 10, [Block("S_01#T", "S_01", "theory", 2, False)])
    a = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]
    assert validate.validate(a, [s], ROOMS, INSTR, Config()) == []

def test_detects_room_double_book():
    s1 = _sec("S1_01", 1, 10, [Block("S1_01#T", "S1_01", "theory", 2, False)], instr="i1", cohort="D-1")
    s2 = _sec("S2_01", 1, 10, [Block("S2_01#T", "S2_01", "theory", 2, False)], instr="i2", cohort="D-2")
    a = [Assignment("S1_01#T", "S1_01", "theory", "R1", "Mo", 9, 11),
         Assignment("S2_01#T", "S2_01", "theory", "R1", "Mo", 10, 12)]
    kinds = {v.kind for v in validate.validate(a, [s1, s2], ROOMS, INSTR, Config())}
    assert "room" in kinds

def test_detects_capacity_and_lab_and_window_and_blackout():
    s = _sec("S_01", 1, 99, [Block("S_01#L", "S_01", "lab", 2, True)], instr="i1")
    # lab block placed in non-lab room R1, capacity 50 < 99, Friday 13 covered, ends 14<=18 ok but blackout
    a = [Assignment("S_01#L", "S_01", "lab", "R1", "Fr", 13, 15)]
    kinds = {v.kind for v in validate.validate(a, [s], ROOMS, INSTR, Config())}
    assert {"capacity", "lab", "blackout"} <= kinds

def test_detects_instructor_and_cohort_conflict():
    s1 = _sec("S1_01", 1, 10, [Block("S1_01#T", "S1_01", "theory", 1, False)], instr="i1", cohort="D-1")
    s2 = _sec("S2_01", 1, 10, [Block("S2_01#T", "S2_01", "theory", 1, False)], instr="i1", cohort="D-1")
    a = [Assignment("S1_01#T", "S1_01", "theory", "R1", "Mo", 9, 10),
         Assignment("S2_01#T", "S2_01", "theory", "LAB-L", "Mo", 9, 10)]
    kinds = {v.kind for v in validate.validate(a, [s1, s2], ROOMS, INSTR, Config())}
    assert "instructor" in kinds and "cohort" in kinds
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_validate.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/validate.py`**

```python
from __future__ import annotations
from typing import List, Dict
from collections import defaultdict

from .config import Config
from .model import Assignment, Section, Room, Instructor, Violation


def validate(assignments: List[Assignment], sections: List[Section],
             rooms: Dict[str, Room], instructors: Dict[str, Instructor],
             cfg: Config) -> List[Violation]:
    viol: List[Violation] = []
    sec_by_id = {s.section_id: s for s in sections}

    # placement: every block of every section must appear exactly once
    placed = defaultdict(int)
    for a in assignments:
        placed[a.block_id] += 1
    for s in sections:
        for b in s.blocks:
            if placed.get(b.block_id, 0) != 1:
                viol.append(Violation("placement",
                            f"{b.block_id} placed {placed.get(b.block_id, 0)} times (expected 1)"))

    closed_all = set(cfg.friday_blackout)
    room_occ = defaultdict(list)
    instr_occ = defaultdict(list)
    cohort_occ = defaultdict(list)

    for a in assignments:
        s = sec_by_id.get(a.section_id)
        if s is None:
            continue
        room = rooms.get(a.room)
        # capacity
        if room is not None and room.cap < s.students:
            viol.append(Violation("capacity",
                        f"{a.block_id} in {a.room} (cap {room.cap}) < {s.students} students"))
        # lab
        if a.kind == "lab" and (room is None or not room.is_lab):
            viol.append(Violation("lab", f"{a.block_id} lab block in non-lab room {a.room}"))
        # window (undergrad)
        end_cap = cfg.undergrad_end if s.level <= 4 else cfg.grad_end
        if a.end > end_cap:
            viol.append(Violation("window",
                        f"{a.block_id} ends {a.end} > allowed {end_cap} (level {s.level})"))
        # blackout
        ins = instructors.get(s.instructor_id, Instructor("", "", False, ""))
        closed = set(closed_all)
        if ins.is_staff:
            closed |= set(cfg.seminar_blackout)
        for hh in range(a.start, a.end):
            if (a.day, hh) in closed:
                viol.append(Violation("blackout", f"{a.block_id} covers blackout {a.day} {hh}:00"))
                break
        # occupancy accumulation
        for hh in range(a.start, a.end):
            room_occ[(a.room, a.day, hh)].append(a.block_id)
            instr_occ[(s.instructor_id, a.day, hh)].append(a.block_id)
            cohort_occ[(s.cohort_key, a.day, hh)].append(a.block_id)

    for (room, day, hh), bids in room_occ.items():
        if len(bids) > 1:
            viol.append(Violation("room", f"room {room} double-booked {day} {hh}:00 by {bids}"))
    for (iid, day, hh), bids in instr_occ.items():
        if len(set(b.split('#')[0] for b in bids)) > 1:
            viol.append(Violation("instructor", f"instructor {iid} double-booked {day} {hh}:00 by {bids}"))
    for (cohort, day, hh), bids in cohort_occ.items():
        if len(set(b.split('#')[0] for b in bids)) > 1:
            viol.append(Violation("cohort", f"cohort {cohort} double-booked {day} {hh}:00 by {bids}"))

    return viol
```

> Note: instructor/cohort occupancy ignores a block overlapping *itself* by keying on the section id; two distinct sections sharing a slot is the real conflict.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_validate.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/validate.py tests/test_validate.py
git commit -m "feat: independent hard-constraint validator"
```

---

### Task 10: `export.py` — schedule.json + CSV

**Files:**
- Create: `src/timetabling/export.py`
- Test: `tests/test_export.py`

**Interfaces:**
- Consumes: `list[Assignment]`, `list[Section]`, `dict[str,Room]`, `dict[str,Instructor]`.
- Produces: `build_schedule_dict(period, assignments, sections, rooms, instructors, unmet_soft=None, conflicts=None) -> dict`; `write_schedule_json(path, payload)`; `write_csv(path, payload)`. JSON schema per assignment: `section_id, course_code, course_name, block_kind, instructor_id, instructor_name, cohort, dept, students, day, start, end, room, room_cap, is_lab_room, flags`.

- [ ] **Step 1: Write the failing test `tests/test_export.py`**

```python
import json
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import export

def test_build_schedule_dict_schema(tmp_path):
    s = Section("ADA 403_01", "001", "ADA 403", "EDA", 4, "ADA", "Fac", "ADA-4",
                "i1", 24, 3, 0, 0, 3, "Course")
    s.blocks = [Block("ADA 403_01#T", "ADA 403_01", "theory", 3, False)]
    rooms = {"G005": Room("G005", 60, False, True)}
    instr = {"i1": Instructor("i1", "Mustafa Kerem Yüksel", True, "ADA")}
    a = [Assignment("ADA 403_01#T", "ADA 403_01", "theory", "G005", "Fr", 13, 16)]
    payload = export.build_schedule_dict("001", a, [s], rooms, instr)
    assert payload["period"] == "001"
    item = payload["assignments"][0]
    assert item["section_id"] == "ADA 403_01"
    assert item["course_code"] == "ADA 403" and item["course_name"] == "EDA"
    assert item["instructor_name"] == "Mustafa Kerem Yüksel"
    assert item["cohort"] == "ADA-4" and item["day"] == "Fr"
    assert item["start"] == 13 and item["end"] == 16
    assert item["room"] == "G005" and item["room_cap"] == 60 and item["is_lab_room"] is False

    p = tmp_path / "schedule.json"
    export.write_schedule_json(str(p), payload)
    assert json.loads(p.read_text())["assignments"][0]["section_id"] == "ADA 403_01"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_export.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/export.py`**

```python
from __future__ import annotations
from typing import List, Dict
import json
import csv

from .model import Assignment, Section, Room, Instructor


def build_schedule_dict(period, assignments: List[Assignment], sections: List[Section],
                        rooms: Dict[str, Room], instructors: Dict[str, Instructor],
                        unmet_soft=None, conflicts=None) -> dict:
    sec_by_id = {s.section_id: s for s in sections}
    items = []
    for a in assignments:
        s = sec_by_id.get(a.section_id)
        room = rooms.get(a.room)
        ins = instructors.get(s.instructor_id) if s else None
        items.append({
            "section_id": a.section_id,
            "course_code": s.code if s else "",
            "course_name": s.name if s else "",
            "block_kind": a.kind,
            "instructor_id": s.instructor_id if s else "",
            "instructor_name": ins.name if ins else "",
            "cohort": s.cohort_key if s else "",
            "dept": s.dept_code if s else "",
            "students": s.students if s else 0,
            "day": a.day, "start": a.start, "end": a.end,
            "room": a.room,
            "room_cap": room.cap if room else None,
            "is_lab_room": room.is_lab if room else None,
            "flags": [],
        })
    return {
        "period": period,
        "meta": {"n_assignments": len(items), "n_sections": len(sections)},
        "assignments": items,
        "unmet_soft": unmet_soft or [],
        "conflicts": conflicts or [],
    }


def write_schedule_json(path: str, payload: dict) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_csv(path: str, payload: dict) -> None:
    fields = ["section_id", "course_code", "course_name", "block_kind", "instructor_id",
              "instructor_name", "cohort", "dept", "students", "day", "start", "end",
              "room", "room_cap", "is_lab_room"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for item in payload["assignments"]:
            w.writerow(item)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_export.py -v`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add src/timetabling/export.py tests/test_export.py
git commit -m "feat: schedule.json + CSV export (UI-consumable schema)"
```

---

### Task 11: `report.py` + `__main__.py` — reports, Mode B, CLI, live run

**Files:**
- Create: `src/timetabling/report.py`, `src/timetabling/__main__.py`
- Test: `tests/test_report.py`

**Interfaces:**
- Consumes: all prior modules.
- Produces:
  - `report.data_quality_report(period, frame, rooms, derive_report, cfg) -> dict`
  - `report.parse_existing(frame, sections) -> list[Assignment]` (Mode B: build assignments from Plan `SCHEDULE`)
  - `report.mode_b_benchmark(period, mode_a, existing, sections, rooms, instructors, cfg) -> dict` (conflict counts, room usage, evening ratio for both)
  - CLI `python -m timetabling --period 001 --scope faculty="..."|dept=ADA|all --mode A,B --out out/`

- [ ] **Step 1: Write the failing test `tests/test_report.py`**

```python
from timetabling.config import Config
from timetabling.model import Section, Block, Room, Instructor, Assignment
from timetabling import report

def test_parse_existing_builds_assignments_from_plan_schedule():
    s = Section("ADA 403_01", "001", "ADA 403", "EDA", 4, "ADA", "Fac", "ADA-4",
                "i1", 24, 3, 0, 0, 3, "Course")
    s.blocks = [Block("ADA 403_01#T", "ADA 403_01", "theory", 3, False)]
    frame = {"ADA 403_01": {"plan_room": "G005", "plan_schedule": "Fr 13 - 16"}}
    assigns = report.parse_existing(frame, [s])
    assert len(assigns) == 1
    a = assigns[0]
    assert a.day == "Fr" and a.start == 13 and a.end == 16 and a.room == "G005"

def test_mode_b_benchmark_shape():
    s = Section("S_01", "001", "S 101", "n", 1, "S", "Fac", "S-1", "i1", 10,
                2, 0, 0, 2, "Course")
    s.blocks = [Block("S_01#T", "S_01", "theory", 2, False)]
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i1": Instructor("i1", "n", False, "S")}
    a = [Assignment("S_01#T", "S_01", "theory", "R1", "Mo", 9, 11)]
    bench = report.mode_b_benchmark("001", a, a, [s], rooms, instr, Config())
    assert "mode_a" in bench and "existing" in bench
    assert "conflicts" in bench["mode_a"] and "rooms_used" in bench["mode_a"]
    assert "evening_ratio" in bench["mode_a"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write `src/timetabling/report.py`**

```python
from __future__ import annotations
from typing import List, Dict
from collections import Counter

from .config import Config
from .model import Assignment, Section, Room, Instructor
from .schedule_parse import parse_schedule
from .validate import validate


def data_quality_report(period, frame, rooms, derive_report, cfg: Config) -> dict:
    empty_room = sum(1 for _, r in frame.iterrows() if str(r.get("plan_room", "")).strip() == "")
    dirty = 0
    for _, r in frame.iterrows():
        sched = str(r.get("plan_schedule", "")).strip()
        if sched and parse_schedule(sched)[1]:
            dirty += 1
    missing_cohort = (frame["dept_code"].astype(str).str.strip() == "").sum()
    labs = [r.room for r in rooms.values() if r.is_lab and r.is_physical]
    return {
        "period": period,
        "n_grades_sections": len(frame),
        "empty_plan_room": int(empty_room),
        "dirty_plan_schedule": int(dirty),
        "missing_cohort_join": int(missing_cohort),
        "n_physical_rooms": sum(1 for r in rooms.values() if r.is_physical),
        "n_lab_rooms": len(labs),
        "lab_rooms": sorted(labs),
        "derive": derive_report,
    }


def parse_existing(frame, sections: List[Section]) -> List[Assignment]:
    """Build Assignments from the existing Plan SCHEDULE (Mode B ground truth)."""
    if hasattr(frame, "iterrows"):
        lookup = {str(r["section_id"]).strip(): r for _, r in frame.iterrows()}
    else:
        lookup = frame
    out: List[Assignment] = []
    for s in sections:
        r = lookup.get(s.section_id)
        if r is None:
            continue
        room = str(r.get("plan_room", "")).strip()
        sessions, errors = parse_schedule(str(r.get("plan_schedule", "")))
        if errors or not sessions:
            continue
        # map sessions onto blocks in order; if counts differ, zip the shorter
        for sess, blk in zip(sessions, (s.blocks * 5)):
            out.append(Assignment(blk.block_id, s.section_id, blk.kind, room,
                                   sess.day, sess.start, sess.end))
    return out


def _metrics(assignments: List[Assignment], sections, rooms, instructors, cfg) -> dict:
    v = validate(assignments, sections, rooms, instructors, cfg)
    by_kind = Counter(x.kind for x in v)
    rooms_used = len({a.room for a in assignments})
    evening = sum(1 for a in assignments if any(h >= cfg.evening_from_hour for h in range(a.start, a.end)))
    return {
        "n_assignments": len(assignments),
        "conflicts": dict(by_kind),
        "n_violations": len(v),
        "rooms_used": rooms_used,
        "evening_blocks": evening,
        "evening_ratio": round(evening / len(assignments), 3) if assignments else 0.0,
    }


def mode_b_benchmark(period, mode_a, existing, sections, rooms, instructors, cfg) -> dict:
    return {
        "period": period,
        "mode_a": _metrics(mode_a, sections, rooms, instructors, cfg),
        "existing": _metrics(existing, sections, rooms, instructors, cfg),
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_report.py -v`
Expected: 2 passed.

- [ ] **Step 5: Write `src/timetabling/__main__.py`**

```python
from __future__ import annotations
import argparse
import json
import os

from .config import Config
from .io_csv import load_classrooms, load_lecturers
from .join import build_section_frame
from .derive import build_sections
from .clean import build_rooms, build_instructors
from .model_cpsat import build_and_solve
from .validate import validate
from .report import data_quality_report, parse_existing, mode_b_benchmark
from .export import build_schedule_dict, write_schedule_json, write_csv


def _apply_scope(frame, scope: str):
    if scope == "all" or not scope:
        return frame
    key, _, val = scope.partition("=")
    if key == "faculty":
        return frame[frame["faculty"].str.contains(val, case=False, na=False)]
    if key == "dept":
        return frame[frame["dept_code"].str.strip() == val]
    return frame


def main():
    ap = argparse.ArgumentParser(prog="timetabling")
    ap.add_argument("--period", default="001", choices=["001", "002"])
    ap.add_argument("--scope", default="all", help='all | faculty=<substr> | dept=<CODE>')
    ap.add_argument("--mode", default="A,B")
    ap.add_argument("--out", default="out")
    ap.add_argument("--time-limit", type=float, default=60.0)
    args = ap.parse_args()

    cfg = Config(solve_time_limit_s=args.time_limit)
    os.makedirs(args.out, exist_ok=True)

    rooms = build_rooms(load_classrooms(), cfg)
    instructors = build_instructors(load_lecturers())
    frame = _apply_scope(build_section_frame(args.period, cfg.include_plan_only), args.scope)
    sections, derive_rep = build_sections(frame, cfg)
    room_list = list(rooms.values())

    dq = data_quality_report(args.period, frame, rooms, derive_rep, cfg)
    with open(os.path.join(args.out, f"data_quality_{args.period}.json"), "w", encoding="utf-8") as f:
        json.dump(dq, f, ensure_ascii=False, indent=2)
    print(f"[data-quality] sections={dq['n_grades_sections']} "
          f"labs={dq['n_lab_rooms']} dirty_schedule={dq['dirty_plan_schedule']} "
          f"empty_room={dq['empty_plan_room']} excluded={derive_rep['excluded']}")

    modes = set(m.strip().upper() for m in args.mode.split(","))
    assignments, stats = [], {}
    if "A" in modes:
        assignments, stats = build_and_solve(sections, room_list, instructors, cfg)
        viol = validate(assignments, sections, rooms, instructors, cfg)
        print(f"[mode-A] status={stats['status_name']} blocks={stats['n_blocks']} "
              f"vars={stats['n_vars']} unplaced={len(stats['unplaced'])} "
              f"wall={stats['wall_time']:.1f}s violations={len(viol)}")
        payload = build_schedule_dict(
            args.period, assignments, sections, rooms, instructors,
            conflicts=[{"kind": v.kind, "detail": v.detail} for v in viol])
        write_schedule_json(os.path.join(args.out, f"schedule_{args.period}.json"), payload)
        write_csv(os.path.join(args.out, f"schedule_{args.period}.csv"), payload)
        if viol:
            print("  !! HARD violations:", [f"{v.kind}:{v.detail}" for v in viol[:10]])
        else:
            print("  OK: 0 hard-constraint violations (feasible)")

    if "B" in modes:
        existing = parse_existing(frame, sections)
        bench = mode_b_benchmark(args.period, assignments, existing, sections, rooms, instructors, cfg)
        with open(os.path.join(args.out, f"mode_b_{args.period}.json"), "w", encoding="utf-8") as f:
            json.dump(bench, f, ensure_ascii=False, indent=2)
        print(f"[mode-B] existing: conflicts={bench['existing']['conflicts']} "
              f"rooms_used={bench['existing']['rooms_used']} "
              f"evening_ratio={bench['existing']['evening_ratio']}")
        print(f"[mode-B] mode_a:   conflicts={bench['mode_a']['conflicts']} "
              f"rooms_used={bench['mode_a']['rooms_used']} "
              f"evening_ratio={bench['mode_a']['evening_ratio']}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 6: Run the full test suite**

Run: `python3 -m pytest -v`
Expected: all tests across all modules pass.

- [ ] **Step 7: Live run on a department slice (feasibility proof)**

Run: `python3 -m timetabling --period 001 --scope dept=ADA --mode A,B --time-limit 60`
Expected: prints `[mode-A] status=OPTIMAL|FEASIBLE ... violations=0` and `OK: 0 hard-constraint violations (feasible)`; writes `out/schedule_001.json`, `out/schedule_001.csv`, `out/data_quality_001.json`, `out/mode_b_001.json`.

- [ ] **Step 8: Live run on a faculty slice (scale check)**

Run: `python3 -m timetabling --period 001 --scope faculty="Faculty of Econ. and Administ. Sciences" --mode A,B --time-limit 120`
Expected: feasible (0 violations) or, if `unplaced > 0` / `INFEASIBLE` within the cap, the printed diagnostics identify the binding resource. If infeasible at faculty scale within the cap, document it and fall back to the `dept=ADA` proof as the demonstrated slice (this is the agreed subset-proof scope; full-scale tuning is out of scope for this build).

- [ ] **Step 9: Commit**

```bash
git add src/timetabling/report.py src/timetabling/__main__.py tests/test_report.py out/
git commit -m "feat: data-quality + Mode-B reports, CLI, live faculty-slice run"
```

---

## Self-Review

**1. Spec coverage** (each spec section → task):
- Quote-aware load, period attach (spec §3) → Task 4. Lecturer `(S)` normalize (§5/§9 clean) → Tasks 2,6. Room outlier/online + lab map (§5) → Task 5. Dirty SCHEDULE flag (§6) → Task 3 + reported in Task 11. Join map (§3) → Task 6. Cohort/level/blocks/hours rule/exclusions (§5) → Task 7. Time model + windows + blackouts (§6/§7/§8) → enforced via pruning in Task 8, re-checked in Task 9. CP-SAT boolean grid + H1–H4 + light objective (§7) → Task 8. Independent validator (§14) → Task 9. schedule.json schema + CSV (§13) → Task 10. Data-quality + conflict + Mode-B benchmark (§13) → Task 11. Subset-proof + scale path (§11) → Task 11 steps 7–8. Modes A/B (§10) → Task 11. **Math formulation doc (§13.2)** is the spec §7 itself (already written/committed) — no code task needed; CLI echoes the model stats.
- Gap check: Mode C (warm-start) is explicitly out of scope (spec §10/§15) — correctly no task. Graduate scheduling toggled off by default (§2) — `include_grad` parameter exists in Task 1 config, unused path acceptable.

**2. Placeholder scan:** No "TBD/TODO". Every code step has complete code; every test step has full assertions. The faculty-slice step (Task 11 step 8) has an explicit documented fallback rather than a vague "handle if it fails."

**3. Type consistency:** `Section` fields (`dept_code`, `cohort_key`, `instructor_id`, `blocks`, `level`, `students`) are used identically in Tasks 7–11. `Block(block_id, section_id, kind, length, needs_lab)` consistent across Tasks 7–10. `Candidate(block_id, room, day, start, length)` consistent Tasks 8. `Assignment(block_id, section_id, kind, room, day, start, end)` consistent Tasks 8–11. `Violation(kind, detail)` consistent Tasks 9,11. `build_and_solve(...) -> (assignments, stats)` and `validate(...) -> list[Violation]` signatures match their callers in `__main__.py`. `build_section_frame` columns produced in Task 6 (`faculty`, `dept_code`, `plan_room`, `plan_schedule`) are exactly those consumed in Tasks 7 & 11.

Fixed inline during review: none required.

---

## Notes for the implementer

- Run everything from the repo root so `pythonpath=src` (pyproject) resolves imports.
- `out/` is gitignored except where Task 11 explicitly adds generated artifacts for the record; if you prefer not to commit generated JSON, drop `out/` from the Task 11 `git add`.
- If `gen_candidates` produces zero candidates for a block (e.g. a section larger than every room, or a lab section with no lab room big enough), that block lands in `stats["unplaced"]` and the model is reported infeasible-by-construction rather than silently dropping it — investigate via the data-quality report.
