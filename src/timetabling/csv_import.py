"""VERA-style CSV importer for the course list.

Pure (no Streamlit), so it stays unit-testable. Ported from VERA's
``src/admin/utils/csvParser.js``: parse header-less, auto-detect whether the
first data row is a header by fuzzy alias matching, fall back to positional
order otherwise; skip leading comment (``#``) / blank rows; classify every row
as ``ok`` / ``duplicate`` / ``error`` and detect duplicate ``(Course Code,
Section No)`` pairs both within the file and against existing rows.

The view layer (``views/upload.py``) reads a file into raw rows via
:func:`read_raw`, calls :func:`parse_courselist`, stores the full report for the
Review preview and the clean :func:`ok_rows` for the solver.
"""
from __future__ import annotations

import re
from typing import Dict, List, Sequence

# Canonical course-list columns (the UI contract) and their accepted header
# aliases (normalized). TR + EN. Unmatched columns fall back to positional order.
COURSE_COL_MAP: Dict[str, List[str]] = {
    "Course Code":    ["course_code", "code", "ders_kodu", "kod", "course"],
    "Course Name":    ["course_name", "name", "ders_adi", "ad", "title", "course_title"],
    "Section No":     ["section_no", "section", "sube", "sec", "sec_no"],
    "T":              ["t", "theory", "teori"],
    "P":              ["p", "practice", "uygulama"],
    "L":              ["l", "lab", "laboratuvar", "laboratory"],
    "Instructor Name":  ["instructor_name", "instructor", "lecturer_name",
                         "lecturer", "ogretim_uyesi", "hoca"],
    "Instructor Email": ["instructor_email", "email", "e_mail", "mail", "eposta",
                         "lecturer_email"],
    "~Students":      ["students", "ogrenci", "ogrenci_sayisi", "booked_cap",
                       "enrolled", "kayitli", "size", "approx_students"],
    # Section Capacity = the quota (hard room-sizing input). ~Students = actual /
    # expected enrolment (optional, soft). Distinct fields: SECT_CAP vs BOOKED_CAP.
    # Kept after ~Students so the original 9-column positional layout is unchanged.
    "Section Capacity": ["section_capacity", "sect_cap", "section_cap", "kontenjan",
                         "quota", "kapasite"],
    # Phase 4 optional columns (override string-derivation; absent -> derive as today).
    "Year":           ["year", "yil", "sinif", "grade", "year_level", "class"],
    "Part-time":      ["part_time", "parttime", "yari_zamanli", "saatlik", "pt", "adjunct"],
    "Room Type":      ["room_type", "oda_tipi", "roomtype", "venue_type"],
    "Fixed":          ["fixed", "fixed_slot", "sabit", "pinned", "pin"],
    # DEPT = faculty name (e.g. "Faculty of Econ…") -> Section.faculty, and the
    # cohort-program fallback when COURSE_CODE is unparseable. Kept LAST so the
    # positional indices of the columns above stay stable for header-less files.
    "Dept":           ["dept", "department", "bolum", "faculty", "fakulte", "birim"],
}

# Positional fallback order == the canonical column order.
COURSE_POSITIONAL = tuple(COURSE_COL_MAP.keys())

_SEP = re.compile(r"[\s#\-./~]+")
# Turkish-aware lowercasing so "Şube"/"Öğrenci" normalize predictably.
_TR_LOWER = str.maketrans({"İ": "i", "I": "i", "Ş": "s", "Ğ": "g",
                           "Ü": "u", "Ö": "o", "Ç": "c"})
# Diacritic folding applied after lowercasing, so aliases stay ASCII.
_FOLD = str.maketrans({"ş": "s", "ğ": "g", "ü": "u", "ö": "o", "ç": "c", "ı": "i"})


def normalize_header(h: str) -> str:
    """Lower, fold Turkish diacritics, collapse separators to ``_``, trim ``_``."""
    s = str(h or "").strip().translate(_TR_LOWER).lower().translate(_FOLD)
    return _SEP.sub("_", s).strip("_")


def _is_comment(row: Sequence) -> bool:
    return str(row[0] if row else "").strip().startswith("#")


def _is_blank(row: Sequence) -> bool:
    return all(str(c or "").strip() == "" for c in row)


def map_columns(raw_rows: List[List], col_map: Dict[str, List[str]] = COURSE_COL_MAP) -> Dict:
    """Detect header (by alias) + build a canonical->column-index map.

    ``col_map`` is a canonical-field -> header-aliases mapping; the positional
    fallback order is ``tuple(col_map.keys())``. Defaults to the course list, but
    pass :data:`CLASSROOM_COL_MAP` to detect a classroom CSV instead.

    Returns ``{data_rows, col_index, detected_columns, has_header,
    first_data_idx}``. ``detected_columns`` = ``[{field, label, source}]`` with
    ``source`` in ``{"header", "positional"}``.
    """
    positional = tuple(col_map.keys())
    if not raw_rows:
        col_index = {f: i for i, f in enumerate(positional)}
        detected = [{"field": f, "label": f"column {i + 1}", "source": "positional"}
                    for i, f in enumerate(positional)]
        return {"data_rows": [], "col_index": col_index,
                "detected_columns": detected, "has_header": False,
                "first_data_idx": 0}

    first_data_idx = next(
        (i for i, r in enumerate(raw_rows)
         if not _is_comment(r) and not _is_blank(r)), -1)
    candidate = raw_rows[first_data_idx:] if first_data_idx >= 0 else raw_rows
    first_data_idx = first_data_idx if first_data_idx >= 0 else 0

    first_row = [str(c or "").strip() for c in candidate[0]]
    normalized = [normalize_header(c) for c in first_row]

    header_idx: Dict[str, int] = {}
    for canonical, aliases in col_map.items():
        idx = next((i for i, h in enumerate(normalized) if h in aliases), -1)
        if idx >= 0:
            header_idx[canonical] = idx

    has_header = len(header_idx) > 0
    data_rows = candidate[1:] if has_header else candidate

    col_index: Dict[str, int] = {}
    detected: List[Dict] = []
    for pos, canonical in enumerate(positional):
        if has_header and canonical in header_idx:
            idx = header_idx[canonical]
            col_index[canonical] = idx
            detected.append({"field": canonical, "label": first_row[idx],
                             "source": "header"})
        else:
            col_index[canonical] = pos
            detected.append({"field": canonical, "label": f"column {pos + 1}",
                             "source": "positional"})

    return {"data_rows": data_rows, "col_index": col_index,
            "detected_columns": detected, "has_header": has_header,
            "first_data_idx": first_data_idx}


def _cell(row: Sequence, idx: int) -> str:
    if idx is None or idx < 0 or idx >= len(row):
        return ""
    return str(row[idx] if row[idx] is not None else "").strip()


def _is_intish(s: str) -> bool:
    """Blank counts as valid (treated as 0 downstream); else must be an int."""
    s = s.strip()
    if s == "":
        return True
    try:
        int(s)
        return True
    except ValueError:
        return False


def _dup_key(code: str, sec: str) -> str:
    return f"{code.strip().lower()}|{sec.strip().lower()}"


def parse_courselist(raw_rows: List[List], existing: Sequence[Dict] = ()) -> Dict:
    """Classify every data row and return a report.

    ``existing`` is a list of already-loaded course dicts (with ``Course Code`` /
    ``Section No``); their ``(code, section)`` keys mark incoming rows duplicate.

    Returns ``{rows, stats, detected_columns, warning}`` where each row carries
    the 9 canonical fields plus ``row_num``, ``status`` (``ok``/``duplicate``/
    ``error``) and ``status_label``.
    """
    m = map_columns(raw_rows)
    ci = m["col_index"]
    row_offset = m["first_data_idx"] + (2 if m["has_header"] else 1)

    existing_keys = {
        _dup_key(str(e.get("Course Code", "")), str(e.get("Section No", "")))
        for e in (existing or [])
        if str(e.get("Course Code", "")).strip()
    }
    seen: set = set()

    rows: List[Dict] = []
    valid = duplicate = error = 0

    for i, raw in enumerate(m["data_rows"]):
        if _is_blank(raw):
            continue
        rec = {canonical: _cell(raw, ci.get(canonical)) for canonical in COURSE_POSITIONAL}
        rec["row_num"] = i + row_offset

        code = rec["Course Code"]
        sec = rec["Section No"]
        bad_hours = not all(_is_intish(rec[k]) for k in ("T", "P", "L"))
        cap = str(rec["Section Capacity"] or rec["~Students"]).strip()
        key = _dup_key(code, sec)

        if not code:
            rec["status"], rec["status_label"] = "error", "err_code"
            error += 1
        elif bad_hours:
            rec["status"], rec["status_label"] = "error", "err_hours"
            error += 1
        elif not cap:
            rec["status"], rec["status_label"] = "error", "err_capacity"
            error += 1
        elif key in existing_keys:
            rec["status"], rec["status_label"] = "duplicate", "dup"
            duplicate += 1
        elif key in seen:
            rec["status"], rec["status_label"] = "duplicate", "dup_file"
            duplicate += 1
        else:
            seen.add(key)
            rec["status"], rec["status_label"] = "ok", "ok"
            valid += 1

        rows.append(rec)

    stats = {"valid": valid, "duplicate": duplicate, "error": error,
             "total": len(rows)}

    warning = None
    if duplicate or error:
        parts = []
        if duplicate:
            parts.append(f"{duplicate} duplicate")
        if error:
            parts.append(f"{error} error" + ("s" if error != 1 else ""))
        warning = {"title": ", ".join(parts),
                   "desc": f"{duplicate + error} row(s) skipped; "
                           f"{valid} valid row(s) will be imported."}

    return {"rows": rows, "stats": stats,
            "detected_columns": m["detected_columns"], "warning": warning}


def ok_rows(parsed: Dict) -> List[Dict]:
    """Clean canonical course dicts for the ``ok`` rows (drop bookkeeping fields)."""
    return [{c: r[c] for c in COURSE_POSITIONAL}
            for r in parsed["rows"] if r["status"] == "ok"]


# --- Classroom list -------------------------------------------------------
# Same header-less alias importer as the course list, so the Classrooms step
# can show the identical "detected columns" chips. Canonical columns (the
# editor/UI contract) + accepted header aliases (TR/EN). Unmatched columns fall
# back to positional order. Mirrors the raw data format (ROOM/ROOM_CAP) too.
CLASSROOM_COL_MAP: Dict[str, List[str]] = {
    "Room": ["room", "oda", "room_name", "derslik", "sinif", "classroom",
             "mekan", "salon", "name"],
    "Capacity": ["capacity", "cap", "room_cap", "kapasite", "size", "seats"],
    "Type": ["type", "tip", "oda_tipi", "room_type", "kind", "tur", "lab"],
    "Dept": ["dept", "department", "bolum", "bölüm", "faculty", "fakulte",
             "birim", "owner", "sahip"],
}
CLASSROOM_POSITIONAL = tuple(CLASSROOM_COL_MAP.keys())

# Room-type vocabulary (shared with sections' Room Type demand). Lab-family =
# everything that is not a plain classroom.
ROOM_TYPES = ("normal", "lab", "pc", "studio")
# Legacy truthy tokens kept so an old boolean Lab column still reads as lab-family.
_LAB_TRUTHY = {"1", "true", "yes", "y", "x", "lab", "✓", "evet", "var"}


def room_type_from_name(name: str) -> str:
    """Categorical room type derived from a room-name token: ``-PC`` -> ``pc``,
    ``-L`` -> ``lab``, ``-STD``/``-STU`` -> ``studio``, else ``normal``."""
    n = str(name or "")
    if "-PC" in n:
        return "pc"
    if "-STD" in n or "-STU" in n:
        return "studio"
    if "-L" in n:
        return "lab"
    return "normal"


def normalize_room_type(value: str, name: str = "") -> str:
    """Map an explicit Type cell to the vocabulary; fall back to the name token.
    Accepts categorical strings, TR/EN synonyms, and the legacy boolean Lab cell."""
    s = str(value or "").strip().lower()
    if not s:
        return room_type_from_name(name)
    if "pc" in s or "bilgisayar" in s:
        return "pc"
    if "studio" in s or "studyo" in s or "stüdyo" in s:
        return "studio"
    if s in ROOM_TYPES:
        return s
    if "lab" in s or "laboratuvar" in s:
        return "lab"
    if s in _LAB_TRUTHY:          # legacy boolean Lab column -> generic lab
        return "lab"
    return "normal"


def parse_classrooms(raw_rows: List[List], existing: Sequence[Dict] = ()) -> Dict:
    """Classify every classroom row and return a report mirroring
    :func:`parse_courselist` (``rows`` / ``stats`` / ``detected_columns`` /
    ``warning``), so the Classrooms step shows the same detected-column chips and
    stat badges.

    Columns: ``Room`` (required), ``Capacity`` (int; blank -> 0), ``Type``
    (categorical ``normal/lab/pc/studio`` from a Type column, else derived from
    the room name's ``-PC`` / ``-L`` / ``-STD`` token). Duplicate room names
    (in-file or vs ``existing``) are flagged.
    """
    m = map_columns(raw_rows, CLASSROOM_COL_MAP)
    ci = m["col_index"]
    row_offset = m["first_data_idx"] + (2 if m["has_header"] else 1)

    existing_keys = {str(e.get("Room", "")).strip().lower()
                     for e in (existing or []) if str(e.get("Room", "")).strip()}
    seen: set = set()

    rows: List[Dict] = []
    valid = duplicate = error = 0
    for i, raw in enumerate(m["data_rows"]):
        if _is_blank(raw):
            continue
        room = _cell(raw, ci.get("Room"))
        cap_raw = _cell(raw, ci.get("Capacity"))
        rtype = normalize_room_type(_cell(raw, ci.get("Type")), room)
        dept = _cell(raw, ci.get("Dept"))
        rec = {"Room": room, "Capacity": cap_raw, "Type": rtype, "Dept": dept,
               "row_num": i + row_offset}

        key = room.strip().lower()
        if not room:
            rec["status"], rec["status_label"] = "error", "err_room"
            error += 1
        elif not _is_intish(cap_raw):
            rec["status"], rec["status_label"] = "error", "err_cap"
            error += 1
        elif key in existing_keys or key in seen:
            rec["status"], rec["status_label"] = "duplicate", "dup_room"
            duplicate += 1
        else:
            seen.add(key)
            rec["status"], rec["status_label"] = "ok", "ok"
            valid += 1
        rows.append(rec)

    stats = {"valid": valid, "duplicate": duplicate, "error": error,
             "total": len(rows)}
    return {"rows": rows, "stats": stats,
            "detected_columns": m["detected_columns"], "warning": None}


def ok_rooms(parsed: Dict) -> List[Dict]:
    """Clean ``Room``/``Capacity``/``Type`` dicts for the ``ok`` rows (Capacity
    normalized to an int string; blank -> ``"0"``)."""
    out = []
    for r in parsed["rows"]:
        if r["status"] != "ok":
            continue
        cap = str(r["Capacity"]).strip()
        cap = str(int(cap)) if cap.lstrip("-").isdigit() else "0"
        out.append({"Room": r["Room"], "Capacity": cap, "Type": r["Type"],
                    "Dept": r.get("Dept", "")})
    return out


def read_raw(file_or_path) -> List[List[str]]:
    """Read a CSV file/path/buffer into raw rows (list of list[str]).

    Header-less and ``dtype=str`` to preserve leading zeros; blank lines kept so
    line numbers in the report match the original file.
    """
    import pandas as pd
    df = pd.read_csv(file_or_path, header=None, dtype=str,
                     skip_blank_lines=False, keep_default_na=False)
    return df.fillna("").astype(str).values.tolist()
