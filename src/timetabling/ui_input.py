from __future__ import annotations
import re
from typing import List, Dict, Tuple

from .config import Config
from .model import Section, Room, Instructor
from .derive import course_level, blocks_from_tpl
from .textnorm import parse_int
from .csv_import import normalize_room_type

_CODE = re.compile(r"\s*([A-Za-z]+)\D*(\d)")


def cohort_from_code(code: str) -> Tuple[str, str, str]:
    m = _CODE.match(str(code or ""))
    if not m:
        return ("UNK", "0", "UNK-0")
    dept, year = m.group(1).upper(), m.group(2)
    return (dept, year, f"{dept}-{year}")


def is_part_time(instructor_name: str) -> bool:
    return "(S)" in (instructor_name or "")


def parse_emails(s: str) -> List[str]:
    return [e.strip() for e in str(s or "").split(",") if e.strip()]


def _truthy(v) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "x", "lab", "✓")


def _room_type_demand(v) -> str:
    """Required room category from a section's Room Type cell: '' (normal) |
    lab | pc | studio. Shares the room inventory's type vocabulary."""
    s = str(v or "").strip().lower()
    if "pc" in s or "bilgisayar" in s:
        return "pc"
    if "studio" in s or "studyo" in s or "stüdyo" in s:
        return "studio"
    if "lab" in s or "laboratuvar" in s:
        return "lab"
    return ""


def normalize_name(name) -> str:
    """Stable instructor key from a display name (fallback when no email):
    drop the (S) part-time marker, collapse whitespace, lowercase."""
    s = str(name or "").replace("(S)", " ")
    return re.sub(r"\s+", " ", s).strip().lower()


def section_id_for(code: str, sec_no: str) -> str:
    """Use SECTION directly as the id when it already contains the course code
    (e.g. 'ADA 403_01'); otherwise compose 'CODE_SEC'."""
    code = str(code or "").strip()
    sec_no = str(sec_no or "").strip()
    if sec_no and code and code.replace(" ", "") in sec_no.replace(" ", ""):
        return sec_no
    return f"{code}_{sec_no}" if sec_no else code


_DAY_ALIASES = {
    "mo": "Mo", "mon": "Mo", "monday": "Mo", "pzt": "Mo", "pazartesi": "Mo",
    "tu": "Tu", "tue": "Tu", "tuesday": "Tu", "sal": "Tu", "sali": "Tu", "salı": "Tu",
    "we": "We", "wed": "We", "wednesday": "We", "car": "We", "çar": "We",
    "carsamba": "We", "çarşamba": "We",
    "th": "Th", "thu": "Th", "thursday": "Th", "per": "Th", "persembe": "Th", "perşembe": "Th",
    "fr": "Fr", "fri": "Fr", "friday": "Fr", "cum": "Fr", "cuma": "Fr",
    "sa": "Sa", "sat": "Sa", "saturday": "Sa", "cmt": "Sa", "cumartesi": "Sa",
}


def parse_fixed(v) -> Tuple[str, int]:
    """Parse a Fixed-slot value like 'Mo 9' / 'Pzt 09:00' / 'Fri 14' into
    (day_code, start_hour). Returns ('', -1) when empty or unparseable."""
    s = str(v or "").strip()
    if not s:
        return ("", -1)
    parts = s.replace(",", " ").split()
    if len(parts) < 2:
        return ("", -1)
    day = _DAY_ALIASES.get(parts[0].lower())
    if not day:
        return ("", -1)
    try:
        hour = int(parts[1].split(":")[0])
    except ValueError:
        return ("", -1)
    return (day, hour) if 0 <= hour <= 23 else ("", -1)


def build_sections_from_courselist(rows: List[Dict], period: str,
                                   cfg: Config) -> Tuple[List[Section], Dict]:
    sections: List[Section] = []
    report = {"missing_email": 0, "missing_hours": 0}
    for r in rows:
        code = str(r.get("Course Code", "")).strip()
        if not code:
            continue
        sec_no = str(r.get("Section No", "")).strip()
        sid = section_id_for(code, sec_no)
        dept, year, _ = cohort_from_code(code)
        faculty = str(r.get("Dept", "")).strip()            # DEPT = faculty name
        if dept == "UNK" and faculty:                       # unparseable code -> DEPT fallback
            dept = faculty.upper()
        yr = parse_int(r.get("Year"), 0)        # optional Year column overrides cohort year (1-6 only)
        eff_year = yr if 1 <= yr <= 6 else year
        cohort = f"{dept}-{eff_year}"
        T = parse_int(r.get("T"), 0); P = parse_int(r.get("P"), 0)
        L = parse_int(r.get("L"), 0)
        if (T + P + L) == 0:
            report["missing_hours"] += 1
        emails = parse_emails(r.get("Instructor Email", ""))
        names = [n.strip() for n in str(r.get("Instructor Name", "")).split(",")]
        if emails:
            instructor_ids = emails
        else:
            report["missing_email"] += 1
            instructor_ids = [normalize_name(n) for n in names if n.strip()]
        # Section Capacity (quota) is the hard size; ~Students (actual) is the fallback.
        students = (parse_int(r.get("Section Capacity"), 0)
                    or parse_int(r.get("~Students"), 0) or 1)
        rtype = _room_type_demand(r.get("Room Type"))       # "" | lab | pc | studio
        fixed_day, fixed_start = parse_fixed(r.get("Fixed"))
        sections.append(Section(
            section_id=sid, period=period, code=code,
            name=str(r.get("Course Name", "")).strip(),
            level=course_level(code), dept_code=dept, faculty=faculty,
            cohort_key=cohort, instructor_ids=instructor_ids, students=students,
            T=T, P=P, L=L, Cr=(T + P + L), category="",
            blocks=blocks_from_tpl(sid, T, P, L, T + P + L,
                                   cfg.max_block_len, cfg.max_theory_session),
            plan_room="",
            requires_lab_room=(rtype in ("lab", "pc", "studio")),
            required_room_type=rtype,
            fixed_day=fixed_day, fixed_start=fixed_start,
        ))
    return sections, report


def build_instructors_from_courselist(rows: List[Dict]) -> Dict[str, Instructor]:
    out: Dict[str, Instructor] = {}
    for r in rows:
        emails = parse_emails(r.get("Instructor Email", ""))
        names = [n.strip() for n in str(r.get("Instructor Name", "")).split(",")]
        faculty = str(r.get("Dept", "")).strip()           # DEPT = faculty name
        # optional Part-time column overrides the "(S)" marker; absent -> fall back to "(S)"
        pt = r.get("Part-time")
        explicit_pt = _truthy(pt) if (pt is not None and str(pt).strip() != "") else None
        # Identity key = email when present; else the normalized display name.
        if emails:
            pairs = [(email, names[i] if i < len(names) else (names[0] if names else ""))
                     for i, email in enumerate(emails)]
        else:
            pairs = [(normalize_name(n), n) for n in names if n.strip()]
        for key, name in pairs:
            if key in out:
                continue
            part_time = explicit_pt if explicit_pt is not None else is_part_time(name)
            out[key] = Instructor(staff_id=key, name=name.strip(),
                                  is_staff=not part_time, home_dept=faculty)
    return out


def build_rooms_from_ui(classroom_rows: List[Dict], cfg: Config) -> Dict[str, Room]:
    rooms: Dict[str, Room] = {}
    for r in classroom_rows:
        name = str(r.get("Room", "")).strip()
        if not name:
            continue
        cap_raw = r.get("Capacity") if r.get("Capacity") is not None else r.get("Cap")
        # Type column (categorical); legacy Lab boolean accepted as a fallback.
        rtype = normalize_room_type(r.get("Type") if r.get("Type") is not None
                                    else r.get("Lab"), name)
        dept = str(r.get("Dept", "") or "").strip()
        rooms[name] = Room(room=name, cap=parse_int(cap_raw, 0) or 0,
                           is_lab=(rtype != "normal"), is_physical=True,
                           is_virtual=False, type=rtype, dept=dept)
    rooms[cfg.online_room] = Room(room=cfg.online_room, cap=10_000, is_lab=False,
                                  is_physical=False, is_virtual=True, type="normal")
    return rooms


# Per INPUT_SCHEMA.md: required (✓) columns. Email is keyed by name when absent.
_REQUIRED = (
    "Course Code", "Course Name", "Dept",
    "Section No", "Instructor Name",
    "T", "P", "L",
    "Section Capacity",
)


def validate_courselist(rows: List[Dict]) -> List[Tuple[str, Dict]]:
    """Return (i18n_code, kwargs) warnings so the UI can render them per language."""
    if not rows:
        return [("warn_no_rows", {})]
    missing = [c for c in _REQUIRED if c not in rows[0]]
    if missing:
        return [("warn_missing_cols", {"cols": ", ".join(missing)})]
    warns: List[Tuple[str, Dict]] = []
    zero_hours = sum(1 for r in rows
                     if (parse_int(r.get("T"), 0) + parse_int(r.get("P"), 0)
                         + parse_int(r.get("L"), 0)) == 0)
    blank_email = sum(1 for r in rows if not parse_emails(r.get("Instructor Email", "")))
    bad_code = sum(1 for r in rows
                   if cohort_from_code(r.get("Course Code", ""))[0] == "UNK"
                   and not str(r.get("Dept", "")).strip())   # Dept column remedies a bad code
    bad_level = sum(1 for r in rows if course_level(r.get("Course Code", "")) == 0)
    part_time = sum(1 for r in rows if is_part_time(r.get("Instructor Name", "")))
    if zero_hours:
        warns.append(("warn_zero_hours", {"n": zero_hours}))
    if blank_email:
        warns.append(("warn_blank_email", {"n": blank_email}))
    if bad_code:
        warns.append(("warn_bad_code", {"n": bad_code}))
    if bad_level:
        warns.append(("warn_bad_level", {"n": bad_level}))
    warns.append(("info_part_time", {"n": part_time}))
    return warns


# Validation codes that block solving (vs. mere warnings/info). Kept here so the
# review view and the solve gate agree on what "validated" means.
COURSELIST_ERROR_CODES = {"warn_no_rows", "warn_missing_cols"}


def courselist_is_valid(rows: List[Dict]) -> bool:
    """True when the uploaded courselist has no blocking validation errors."""
    return not any(code in COURSELIST_ERROR_CODES
                   for code, _ in validate_courselist(rows))
