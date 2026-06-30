# KAIROS — Input Data Schema

The two tables a user provides to the KAIROS timetabling UI, and how the solver
derives everything else from them. This is the **input contract**: the importer
(`csv_import.py`), the section/room builders (`ui_input.py`), and the data
classes (`model.py`) all conform to it. The optimization model itself is
specified separately in [MODEL.md](MODEL.md); this file is only about *what goes in*.

There are exactly **two independent inputs**, modeled as two tables:

1. **Sections** — the course offerings for one period (uploaded each term).
2. **Rooms** — the classroom inventory (stable; seeded from defaults, edited, or
   imported once).

The `section → room` assignment is the **solver's output**, never an input — so
no room is named on a section row, and no section is named on a room row.

---

## Table 1 — Sections (course list)

One row per section (a single offering of a course). The importer detects a header
row and matches each column by **alias** (TR/EN, case-insensitive), so column order
does not matter — both the clean sample headers (`Course Code`, `Section No`, …) and
a registrar export's headers (`COURSE_CODE`, `SECTION`, `SECT_CAP`, …) are accepted.
A header-less file falls back to a fixed **positional** order (`COURSE_POSITIONAL`
in `csv_import.py`); the table below lists the columns grouped logically, not in that
fallback order.

| Column | Required | Meaning / effect on the solver |
|---|:---:|---|
| `COURSE_CODE` | ✓ | Course code. Source of the **cohort program code** (`ADA 403` → `ADA`). |
| `COURSE_NAME` | ✓ | Display name. |
| `DEPT` | ✓ | **Department/faculty name** (e.g. "Faculty of Econ…") → `Section.department`. **Not** the cohort key (see §Cohort). |
| `SECTION` | ✓ | Section identifier. `"ADA 403_01"` is used **directly** as `section_id`; a bare `"01"` is composed with the code. |
| `LECTURER` | ✓ | Instructor **display name**. Fallback unique key when `Email` is absent. |
| `Email` | optional · recommended | Instructor's **unique key** (instructor no-overlap + availability key when present). |
| `Part-time` | optional | Boolean. Overrides the `(S)` name marker; empty/`false` ⇒ full-time. |
| `T` | ✓ | Theory hours → theory blocks. |
| `P` | ✓ | Practice/application hours (`U` = Uygulama) → blocks. |
| `L` | ✓ | Lab hours → lab block. `L > 0` always produces a block with `needs_lab=True`. If the legacy Plan path pins a specific lab-family room, that exact room is used. Otherwise, an explicit `Room Type` demand (`lab` / `pc` / `studio`) restricts the lab block to that exact room type; with no explicit demand, any lab-family room of sufficient capacity is eligible. |
| `Section Capacity` | ✓ | **Quota.** The **hard** room-sizing input (`room.Capacity ≥ Section Capacity`). |
| `~Students` | optional | Legacy/estimated enrolment field. Current solver stores one section size: `Section Capacity` wins; `~Students` is only a fallback in importer paths that permit it. There is no separate soft right-sizing signal yet. |
| `Room Type` | optional | **Required room category** (demand): `lab / pc / studio`. Empty or `normal` ⇒ no explicit categorical demand. If the section has lab blocks (`L > 0`), the explicit demand applies to those lab blocks while non-lab blocks still use `normal` rooms. If the section has no lab blocks, the explicit demand applies to its theory/practice blocks. Shares Table 2's vocabulary. |
| `Fixed` | optional | Fixed slot for the section's first block (e.g. `"Mo 9"`). |
| `Year` | optional | Overrides the cohort year level. |
| `Min Working Days` | optional | Soft target for how many distinct days this section should occupy. Empty/invalid means no target; unmet days are reported in `unmet_soft` and penalized, never treated as a hard violation. |
| `Parallel Policy` | optional | Course-code scoped soft policy for parallel sections: `same-time`, `spread`, or `lab-after-theory`. Empty/invalid means off. Settings entries for the same course code override the CSV value. |

**Not section columns** (deliberately excluded — they belong to the room table or
are solver output): `ROOM`, `ROOM_CAP`, `SCHEDULE`.

## Table 2 — Rooms (classroom inventory)

| Column | Required | Meaning |
|---|:---:|---|
| `Room` | ✓ | Room name (unique). |
| `Capacity` | ✓ | Seats. |
| `Type` | ✓ | Room category: `normal / lab / pc / studio`. Derived from a name token (`-PC` → `pc`, `-L` → `lab`) when seeding; editable. |
| `Dept` | optional | **Department ownership** for a room. Semicolon-separated list of department names (e.g. `"Department of Software Engineering;Dept.of Electric&Electronics Engineering"`). When set, only sections whose `DEPT` matches one of the listed values may be assigned to this room. Empty = open to all departments (general pool). |

The user must upload a classroom CSV or load the built-in sample in the Classrooms step before solving.

---

## Shared type vocabulary

Both tables speak one controlled vocabulary: **`normal / lab / pc / studio`**.

- **Supply** = a room's `Type`. **Demand** = a section's `Room Type`.
- **Matching:** when a section names an explicit `Room Type`, `feasible_rooms_for()`
  restricts lab blocks to that exact category (`lab`, `pc`, or `studio`); if the
  section has no lab blocks, the same demand applies to its theory/practice
  blocks. With no explicit demand (`Room Type` empty or `normal`), lab blocks use
  any fitting lab-family room and non-lab blocks use fitting `normal` rooms, after
  capacity and ownership checks. A lab block is pinned only when the legacy Plan
  route found a specific lab room.
- A single boolean `is_lab` is insufficient: `lab ≠ pc ≠ studio` (a programming
  course must not land in a wet lab; **Architecture studios** are their own
  category).

---

## Derivations & semantics

**Cohort** = `(program code, year level)` — a **soft proxy**, never a hard rule
(see MODEL.md §5.15).
- Program code = the **letter prefix of `COURSE_CODE`** (`ADA 403` → `ADA`) — *not*
  `DEPT`. `DEPT` is faculty-level (it groups many programs), too coarse for a
  cohort; using it would manufacture false conflicts.
- Year level = the first digit of the course number (`ADA 4̲03` → `4`), or the
  `Year` column when present.
- Fallback: if a code cannot be parsed (no letter+digit), the cohort program falls
  back to the (mandatory) `DEPT` so every section still belongs to a cohort.

**Instructor identity.**
- `Email` present → it is the unique key (handles same-name lecturers and spelling
  variants correctly).
- `Email` absent → the normalized `LECTURER` name is the key, and the UI warns that
  uniqueness is name-based.
- Part-time = the `Part-time` boolean when given, else inferred from the `(S)`
  marker in the name. The full-time-only blackout applies if **any** co-instructor
  is full-time.

**Capacity — current implementation.**
- `Section Capacity` (quota) → the hard capacity input; room matching uses it.
- `~Students` → optional fallback/preview field. When `Section Capacity` is
  present, the solver and exported `section_cap` use `Section Capacity`, not a
  separate actual-enrolment value.
- A room's `Capacity` → the room's own size (Table 2).

**What is *not* in either file** (it lives in the **School Settings** step, not the
upload): institutional policy (day window, weights, blackouts) and per-instructor
availability (keyed by the same email-or-name identity).
