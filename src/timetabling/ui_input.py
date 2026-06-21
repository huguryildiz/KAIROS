from __future__ import annotations
import re
from typing import List, Dict, Tuple

from .config import Config
from .model import Section, Room, Instructor
from .derive import course_level, blocks_from_tpl
from .textnorm import parse_int

_CODE = re.compile(r"\s*([A-Za-z]+)\D*(\d)")


def cohort_from_code(code: str) -> Tuple[str, str, str]:
    m = _CODE.match(str(code or ""))
    if not m:
        return ("UNK", "0", "UNK-0")
    dept, year = m.group(1).upper(), m.group(2)
    return (dept, year, f"{dept}-{year}")


def is_part_time(lecturer_name: str) -> bool:
    return "(S)" in (lecturer_name or "")


def parse_emails(s: str) -> List[str]:
    return [e.strip() for e in str(s or "").split(",") if e.strip()]


def _truthy(v) -> bool:
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "x", "lab", "✓")


def _is_lab_type(v) -> bool:
    """A Room Type column value that means 'this section needs a lab-flagged room'."""
    s = str(v or "").strip().lower()
    return bool(s) and any(tok in s for tok in
                           ("lab", "pc", "studio", "studyo", "bilgisayar", "laboratuvar"))


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
        sid = f"{code}_{sec_no}" if sec_no else code
        dept, year, cohort = cohort_from_code(code)
        yr = parse_int(r.get("Year"), 0)        # optional Year column overrides cohort year
        if yr > 0:
            cohort = f"{dept}-{yr}"
        T = parse_int(r.get("T"), 0); P = parse_int(r.get("P"), 0)
        L = parse_int(r.get("L"), 0)
        if (T + P + L) == 0:
            report["missing_hours"] += 1
        emails = parse_emails(r.get("Lecturer Email", ""))
        if not emails:
            report["missing_email"] += 1
        students = parse_int(r.get("~Students"), 1) or 1
        fixed_day, fixed_start = parse_fixed(r.get("Fixed"))
        sections.append(Section(
            section_id=sid, period=period, code=code,
            name=str(r.get("Course Name", "")).strip(),
            level=course_level(code), dept_code=dept, faculty="",
            cohort_key=cohort, instructor_ids=emails, students=students,
            T=T, P=P, L=L, Cr=(T + P + L), category="",
            blocks=blocks_from_tpl(sid, T, P, L, T + P + L,
                                   cfg.max_block_len, cfg.max_theory_session),
            plan_room="",
            requires_lab_room=_is_lab_type(r.get("Room Type")),
            fixed_day=fixed_day, fixed_start=fixed_start,
        ))
    return sections, report


def build_instructors_from_courselist(rows: List[Dict]) -> Dict[str, Instructor]:
    out: Dict[str, Instructor] = {}
    for r in rows:
        emails = parse_emails(r.get("Lecturer Email", ""))
        names = [n.strip() for n in str(r.get("Lecturer Name", "")).split(",")]
        dept, _, _ = cohort_from_code(r.get("Course Code", ""))
        # optional Part-time column overrides the "(S)" marker; absent -> fall back to "(S)"
        pt = r.get("Part-time")
        explicit_pt = _truthy(pt) if (pt is not None and str(pt).strip() != "") else None
        for i, email in enumerate(emails):
            name = names[i] if i < len(names) else (names[0] if names else "")
            if email in out:
                continue
            part_time = explicit_pt if explicit_pt is not None else is_part_time(name)
            out[email] = Instructor(staff_id=email, name=name,
                                    is_staff=not part_time, home_dept=dept)
    return out


def build_rooms_from_ui(classroom_rows: List[Dict], cfg: Config) -> Dict[str, Room]:
    rooms: Dict[str, Room] = {}
    for r in classroom_rows:
        name = str(r.get("Room", "")).strip()
        if not name:
            continue
        rooms[name] = Room(room=name, cap=parse_int(r.get("Cap"), 0) or 0,
                           is_lab=_truthy(r.get("Lab")), is_physical=True,
                           is_virtual=False)
    rooms[cfg.online_room] = Room(room=cfg.online_room, cap=10_000, is_lab=False,
                                  is_physical=False, is_virtual=True)
    return rooms


_REQUIRED = ("Course Code", "Section No", "T", "P", "L", "Lecturer Email")


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
    blank_email = sum(1 for r in rows if not parse_emails(r.get("Lecturer Email", "")))
    bad_code = sum(1 for r in rows if cohort_from_code(r.get("Course Code", ""))[0] == "UNK")
    part_time = sum(1 for r in rows if is_part_time(r.get("Lecturer Name", "")))
    if zero_hours:
        warns.append(("warn_zero_hours", {"n": zero_hours}))
    if blank_email:
        warns.append(("warn_blank_email", {"n": blank_email}))
    if bad_code:
        warns.append(("warn_bad_code", {"n": bad_code}))
    warns.append(("info_part_time", {"n": part_time}))
    return warns
