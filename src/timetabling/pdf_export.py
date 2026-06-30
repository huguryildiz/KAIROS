"""Pure PDF export of the weekly timetable grid. Streamlit-free → unit-testable.

Builds landscape-A4 weekly grids (hours × Mon–Fri) with fpdf2, embedding a
Unicode TTF (DejaVuSans) so Turkish glyphs render. The grid mirrors the on-screen
calendar: each session is a colored block spanning its hours, labelled with the
section id, a PRAT/LAB tag, the instructor (name + email) and the room. See
build_pdf_bundle: every entity of the current view (cohort/room/…) is merged
into ONE multi-page PDF, one page per entity, naturally sorted by name.
"""
from __future__ import annotations

import re
import struct
from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from fpdf import FPDF

from .ui_grid import DAYS_ORDER, filter_assignments
from .ui_style import block_color
from .i18n import DAY_LABELS_FULL, DEFAULT_LANG

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"
_FONT_REGULAR = _FONT_DIR / "DejaVuSans.ttf"
_FONT_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"
_LOGO_PATH = Path(__file__).parent.parent.parent / "assets" / "logo.png"
_LOGO_H = 9.0     # mm — height, matches title row

_HOUR_LO, _HOUR_HI = 9, 21          # grid rows = hours 9..20 inclusive
_TIME_COL_W = 16.0                  # mm
_HEADER_H = 9.0                     # mm, day-name header row
_ROW_H = 13.5                       # mm per hour row
_MAX_LANES_PER_PAGE = 2             # keep dense exports readable


def _png_dimensions(path: Path) -> Tuple[int, int] | None:
    try:
        with path.open("rb") as f:
            header = f.read(24)
    except OSError:
        return None
    if len(header) < 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    return struct.unpack(">II", header[16:24])


def _logo_width_mm() -> float:
    dims = _png_dimensions(_LOGO_PATH)
    if not dims:
        return 28.125
    w, h = dims
    return _LOGO_H * (w / h)


def _hex_to_rgb(hex_color: str) -> Tuple[int, int, int]:
    h = str(hex_color or "#888888").lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _tint(hex_color: str, strength: float) -> Tuple[int, int, int]:
    """Blend a color toward white. strength=0 → white, 1 → the color."""
    r, g, b = _hex_to_rgb(hex_color)
    mix = lambda c: round(c * strength + 255 * (1 - strength))
    return mix(r), mix(g), mix(b)


def _blend(rgb_a: Tuple[int, int, int], rgb_b: Tuple[int, int, int],
           f: float) -> Tuple[int, int, int]:
    """Blend rgb_a toward rgb_b. f=1 → all a, f=0 → all b."""
    return tuple(round(a * f + b * (1 - f)) for a, b in zip(rgb_a, rgb_b))


def _block_tag(a: dict) -> str:
    """LAB / PRAT tag mirroring the on-screen grid, or '' for plain theory."""
    if "lab" in str(a.get("block_kind", "")).lower():
        return "LAB"
    if (a.get("section_p") or 0) > 0:
        return "PRAT"
    return ""


def _fit(pdf: FPDF, text: str, max_w: float) -> str:
    """Truncate text with an ellipsis so it fits within max_w (current font)."""
    text = str(text)
    if pdf.get_string_width(text) <= max_w:
        return text
    ell = "…"
    while text and pdf.get_string_width(text + ell) > max_w:
        text = text[:-1]
    return (text + ell) if text else ""


def _course_code_label(a: dict) -> str:
    """Readable block title for dense PDF grids.

    Department exports can be lane-packed into narrow cards; section ids such as
    "ENG 101_01" are often clipped. The course code is the information readers
    scan for first, so prefer it and fall back to section_id for older schedules.
    """
    return str(a.get("course_code") or a.get("section_id") or "")


def _section_title_label(a: dict) -> str:
    """Compact title with course code plus section information.

    Example: course_code='ENG 101', section_id='ENG 101_02' -> 'ENG 101_02'.
    If an older schedule lacks course_code, section_id is still shown.
    """
    course = str(a.get("course_code") or "").strip()
    section = str(a.get("section_id") or "").strip()
    if course and section.startswith(course):
        return section
    return section or course


def _layout_day(blocks: list) -> list:
    """Pack a day's blocks into lanes so overlapping sessions sit side by side.

    Returns [(block, lane_index, n_lanes_in_cluster), ...]. Within a maximal
    overlapping cluster, greedy interval-partitioning gives the minimum lanes."""
    items = sorted(blocks, key=lambda b: (int(b.get("start", 0)), int(b.get("end", 0))))
    out: list = []
    cluster: list = []
    cluster_end = None

    def flush(cl: list) -> None:
        lane_end: List[int] = []          # running end-time per lane
        placed: list = []
        for b in cl:
            s, e = int(b.get("start", 0)), int(b.get("end", 0))
            for li, end in enumerate(lane_end):
                if s >= end:
                    lane_end[li] = e
                    placed.append((b, li))
                    break
            else:
                lane_end.append(e)
                placed.append((b, len(lane_end) - 1))
        n = len(lane_end)
        out.extend((b, li, n) for b, li in placed)

    for b in items:
        s, e = int(b.get("start", 0)), int(b.get("end", 0))
        if cluster and s < cluster_end:
            cluster.append(b)
            cluster_end = max(cluster_end, e)
        else:
            if cluster:
                flush(cluster)
            cluster, cluster_end = [b], e
    if cluster:
        flush(cluster)
    return out


def _assignment_hours(a: dict) -> list[tuple[str, int]]:
    day = a.get("day")
    if day not in DAYS_ORDER:
        return []
    start = int(a.get("start", _HOUR_LO))
    end = int(a.get("end", start + 1))
    return [(day, h) for h in range(max(start, _HOUR_LO), min(end, _HOUR_HI))]


def _paginate_for_readability(schedule: dict,
                              max_lanes: int = _MAX_LANES_PER_PAGE) -> list[dict]:
    """Split dense filtered schedules so one time slot never becomes too narrow."""
    assignments = list(schedule.get("assignments", []))
    if not assignments:
        return [{**schedule, "assignments": []}]

    pages: list[dict] = []
    page_loads: list[dict[tuple[str, int], int]] = []
    items = sorted(assignments, key=lambda a: (
        DAYS_ORDER.index(a.get("day")) if a.get("day") in DAYS_ORDER else 99,
        int(a.get("start", 0)),
        int(a.get("end", 0)),
        str(a.get("section_id") or a.get("course_code") or ""),
    ))

    for a in items:
        hours = _assignment_hours(a)
        for page, load in zip(pages, page_loads):
            if all(load.get(slot, 0) < max_lanes for slot in hours):
                page["assignments"].append(a)
                for slot in hours:
                    load[slot] = load.get(slot, 0) + 1
                break
        else:
            pages.append({**schedule, "assignments": [a]})
            page_loads.append({slot: 1 for slot in hours})
    return pages


def _draw_block(pdf: FPDF, a: dict, x: float, y: float, w: float, h: float,
                show_instructor: bool, cont: bool = False) -> None:
    color = block_color(a)
    accent = _hex_to_rgb(color)
    fill = _tint(color, 0.13)                  # ~13% color over white (matches UI)
    code_rgb = _blend(accent, (32, 34, 44), 0.72)   # dark tint of the color
    r, bar_w = 2.4, 1.4                        # card corner radius / left-bar width
    # 1) Whole card filled with the accent — supplies the rounded left corners.
    pdf.set_fill_color(*accent)
    pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=r)
    # 2) Tint over everything EXCEPT the left bar strip → full-height left accent
    #    bar whose outer-left corners follow the card, inner edge straight.
    with pdf.rect_clip(x + bar_w, y, w - bar_w, h):
        pdf.set_fill_color(*fill)
        pdf.rect(x, y, w, h, style="F", round_corners=True, corner_radius=r)
    # 3) Soft outline.
    pdf.set_draw_color(*_tint(color, 0.45))
    pdf.set_line_width(0.2)
    pdf.rect(x, y, w, h, style="D", round_corners=True, corner_radius=r)
    # 4) Continuation hour: a dashed top rule (this session began an hour earlier).
    if cont:
        pdf.set_draw_color(*_tint(color, 0.55))
        pdf.set_line_width(0.25)
        pdf.set_dash_pattern(dash=1.1, gap=1.1)
        pdf.line(x + bar_w + 1.0, y + 0.5, x + w - 1.5, y + 0.5)
        pdf.set_dash_pattern()                 # reset to solid

    tag = _block_tag(a)
    title = _section_title_label(a)
    lines = [(title, "", 7.4, True, code_rgb, True, "text")]
    room = str(a.get("room", "") or "")
    if room:
        lines.append((room, "", 5.1, False, _blend(accent, (70, 74, 86), 0.6), False, "text"))
    if show_instructor:
        name = str(a.get("instructor_name", "") or "")
        iid = str(a.get("instructor_id", "") or "")
        if name:
            lines.append((name, "", 5.1, False, (96, 100, 112), False, "text"))
        elif iid and not name:
            lines.append((iid, "", 5.1, False, (96, 100, 112), False, "text"))
    if tag:
        lines.append((tag, "", 4.4, True, _hex_to_rgb("#b45309") if tag == "PRAT" else (90, 95, 110), False, "tag"))

    pad_l, pad_t = 4.0, 1.1
    tw = w - pad_l - 1.8
    with pdf.rect_clip(x, y, w, h):
        cy = y + pad_t
        for txt, tg, size, bold, rgb, is_code, kind in lines:
            avail = tw
            if is_code:
                while size > 4.8:
                    pdf.set_font("DejaVu", "B" if bold else "", size)
                    if pdf.get_string_width(str(txt)) <= avail:
                        break
                    size -= 0.4
            lh = size * 0.43
            if cy + lh > y + h:
                break
            pdf.set_font("DejaVu", "B" if bold else "", size)
            pdf.set_text_color(*rgb)
            pdf.set_xy(x + pad_l, cy)
            if kind == "tag":
                tag_w = min(tw, pdf.get_string_width(str(txt)) + 3.0)
                pdf.set_draw_color(*rgb)
                pdf.set_line_width(0.18)
                pdf.rect(x + pad_l, cy + 0.2, tag_w, lh + 1.0,
                         style="D", round_corners=True, corner_radius=0.6)
                pdf.cell(tag_w, lh + 1.0, str(txt), align="C")
            else:
                shown = _fit(pdf, txt, avail)
                pdf.cell(pdf.get_string_width(shown) + 0.5, lh, shown)
            cy += lh + 0.35
    pdf.set_text_color(0, 0, 0)


def _draw_tag(pdf: FPDF, tag: str) -> None:
    """Bordered mini-pill drawn inline after the section code (PRAT amber / LAB color)."""
    rgb = (180, 83, 9) if tag == "PRAT" else (90, 95, 110)
    pdf.set_font("DejaVu", "B", 4.6)
    tw = pdf.get_string_width(tag)
    x, y = pdf.get_x() + 1.4, pdf.get_y()
    pw, ph = tw + 2.2, 2.7
    pdf.set_draw_color(*rgb)
    pdf.set_line_width(0.18)
    pdf.rect(x, y + 0.5, pw, ph, style="D", round_corners=True, corner_radius=0.6)
    pdf.set_text_color(*rgb)
    pdf.set_xy(x, y + 0.4)
    pdf.cell(pw, ph, tag, align="C")


def _new_pdf() -> FPDF:
    """Fresh landscape-A4 PDF with the embedded Unicode font registered."""
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("DejaVu", "", str(_FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(_FONT_BOLD))
    return pdf


def _draw_grid_page(pdf: FPDF, schedule: dict, title: str,
                    lang: str, show_instructor: bool) -> None:
    """Append ONE landscape-A4 weekly-grid page to `pdf` for the filtered
    schedule. Caller manages page setup; this only draws."""
    days = DAY_LABELS_FULL.get(lang, DAY_LABELS_FULL[DEFAULT_LANG])
    pdf.add_page()

    # Logo PNG — top-right corner, vertically centred on the title row.
    row_y = pdf.get_y()
    logo_w = _logo_width_mm() if _LOGO_PATH.exists() else 0.0
    if _LOGO_PATH.exists():
        logo_x = pdf.w - pdf.r_margin - logo_w
        logo_y = row_y + (9 - _LOGO_H) / 2
        pdf.image(str(_LOGO_PATH), x=logo_x, y=logo_y, w=logo_w, h=_LOGO_H)

    # Title — reset cursor to left margin (logo drawing leaves it mid-page).
    pdf.set_xy(pdf.l_margin, row_y)
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(20, 20, 20)
    title_w = pdf.w - pdf.l_margin - pdf.r_margin - (logo_w + 4 if _LOGO_PATH.exists() else 0)
    pdf.cell(title_w, 9, title, new_x="LMARGIN", new_y="NEXT")

    grid_x = pdf.l_margin
    grid_y = pdf.get_y() + 2
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    day_w = (usable - _TIME_COL_W) / len(DAYS_ORDER)
    n_rows = _HOUR_HI - _HOUR_LO
    body_y = grid_y + _HEADER_H

    # Header row (day names) — light fill.
    pdf.set_fill_color(244, 245, 248)
    pdf.set_draw_color(210, 213, 220)
    pdf.set_line_width(0.2)
    pdf.rect(grid_x, grid_y, _TIME_COL_W, _HEADER_H, style="DF")
    pdf.set_font("DejaVu", "B", 9)
    pdf.set_text_color(90, 95, 105)
    for i, d in enumerate(DAYS_ORDER):
        x = grid_x + _TIME_COL_W + i * day_w
        pdf.rect(x, grid_y, day_w, _HEADER_H, style="DF")
        pdf.set_xy(x, grid_y)
        pdf.cell(day_w, _HEADER_H, days.get(d, d), align="C")

    # Hour rows: time labels + horizontal/vertical gridlines.
    pdf.set_draw_color(225, 227, 233)
    pdf.set_line_width(0.15)
    for r in range(n_rows):
        y = body_y + r * _ROW_H
        pdf.set_font("DejaVu", "B", 8)
        pdf.set_text_color(120, 125, 135)
        pdf.set_xy(grid_x, y)
        pdf.cell(_TIME_COL_W, _ROW_H, f"{_HOUR_LO + r:02d}:00", align="C")
        pdf.line(grid_x, y, grid_x + usable, y)             # row separator
    bottom = body_y + n_rows * _ROW_H
    pdf.line(grid_x, bottom, grid_x + usable, bottom)
    for i in range(len(DAYS_ORDER) + 1):                    # column separators
        x = grid_x + _TIME_COL_W + i * day_w
        pdf.line(x, body_y, x, bottom)
    pdf.line(grid_x, body_y, grid_x, bottom)

    # Blocks per day (lane-packed for overlaps), spanning their hours.
    by_day: dict = {d: [] for d in DAYS_ORDER}
    for a in schedule.get("assignments", []):
        d = a.get("day")
        if d in by_day:
            by_day[d].append(a)

    gap = 0.7                                   # vertical gap between hour cards
    for col, d in enumerate(DAYS_ORDER):
        x_day = grid_x + _TIME_COL_W + col * day_w
        for a, lane, n_lanes in _layout_day(by_day[d]):
            start = int(a.get("start", _HOUR_LO))
            s = max(start, _HOUR_LO)
            e = min(int(a.get("end", start + 1)), _HOUR_HI)
            lane_w = day_w / n_lanes
            bx = x_day + lane * lane_w + 0.6
            bw = lane_w - 1.2
            # One card per hour the session occupies (mirrors the on-screen grid).
            for hh in range(s, e):
                byy = body_y + (hh - _HOUR_LO) * _ROW_H + gap
                bh = _ROW_H - 2 * gap
                _draw_block(pdf, a, bx, byy, bw, bh, show_instructor,
                            cont=(hh > start))


def build_grid_pdf(schedule: dict, title: str, lang: str = DEFAULT_LANG,
                   show_instructor: bool = True) -> bytes:
    """Render ONE landscape-A4 weekly calendar for an already-filtered schedule.

    schedule: a schedule dict ({"assignments": [...]}) already narrowed to the
        entity (use filter_assignments upstream).
    title: header line, e.g. "Öğretim elemanı: Ahmet Acar".
    """
    pdf = _new_pdf()
    _draw_grid_page(pdf, schedule, title, lang, show_instructor)
    return bytes(pdf.output())


_NATSORT_RE = re.compile(r"(\d+)|(\D+)")


def _natsort_key(s: str) -> tuple:
    """Natural-sort key: 'EE-2' < 'EE-10' < 'EE-11'. Digits are sorted as ints,
    text segments case-insensitively."""
    out: list = []
    for d, t in _NATSORT_RE.findall(str(s)):
        out.append((0, int(d)) if d else (1, t.lower()))
    return tuple(out)


def _sanitize_filename(name: str) -> str:
    """Filesystem-safe name: keep letters (incl. Turkish) + digits, spaces→'_'."""
    name = (name or "").strip()
    name = re.sub(r"\s+", "_", name)
    name = re.sub(r"[^\w\-]", "_", name, flags=re.UNICODE)  # \w keeps Türkçe
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "schedule"


def build_pdf_bundle(schedule: dict, view_field: str, entities: List[str],
                     dim_label: str, lang: str = DEFAULT_LANG
                     ) -> Tuple[bytes, str, str]:
    """Merge every entity of the current view into ONE multi-page PDF, one page
    per entity, naturally sorted by name (so EE-1, EE-2, …, EE-10 read in order).

    Returns (pdf_bytes, filename, mime).  For a single entity the filename is
    '<entity>.pdf'; for multiples it is
    'schedule_<view_field>_<YYYYMMDD>_<HHMMSS>.pdf' (download timestamp)."""
    ents = sorted({str(e) for e in entities}, key=_natsort_key)
    # For the instructor view, enrich the page title with the email so it reads
    # "Öğretim elemanı: Ahmet Güneş (agunes@uni.edu)" — mirrors the UI dropdown.
    name_to_email: dict = {}
    if view_field == "instructor_name":
        for a in schedule.get("assignments", []):
            nm = str(a.get("instructor_name", "") or "")
            em = str(a.get("instructor_id", "") or "")
            if nm and "@" in em and nm not in name_to_email:
                name_to_email[nm] = em
    pdf = _new_pdf()
    for ent in ents:
        view = filter_assignments(schedule, view_field, ent)
        ent_label = f"{ent} ({name_to_email[ent]})" if ent in name_to_email else ent
        pages = _paginate_for_readability(view)
        for idx, page in enumerate(pages, start=1):
            suffix = f" ({idx}/{len(pages)})" if len(pages) > 1 else ""
            _draw_grid_page(pdf, page, f"{dim_label}: {ent_label}{suffix}", lang, True)
    data = bytes(pdf.output())
    if len(ents) == 1:
        fname = _sanitize_filename(ents[0])
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        fname = f"schedule_{view_field}_{stamp}"
    return data, f"{fname}.pdf", "application/pdf"
