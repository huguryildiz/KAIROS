"""Pure PDF export of the weekly timetable grid. Streamlit-free → unit-testable.

Builds landscape-A4 weekly grids (hours × Mon–Fri) with fpdf2, embedding a
Unicode TTF (DejaVuSans) so Turkish glyphs render. The grid mirrors the on-screen
calendar: each session is a colored block spanning its hours, labelled with the
section id, a PRAT/LAB tag, the instructor (name + email) and the room. See
build_pdf_bundle for the single-PDF / zip packaging used by the Results view.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import List, Tuple

from fpdf import FPDF

from .ui_grid import DAYS_ORDER, filter_assignments
from .ui_style import block_color
from .i18n import DAY_LABELS, DEFAULT_LANG

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"
_FONT_REGULAR = _FONT_DIR / "DejaVuSans.ttf"
_FONT_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"

_HOUR_LO, _HOUR_HI = 9, 21          # grid rows = hours 9..20 inclusive
_TIME_COL_W = 16.0                  # mm
_HEADER_H = 9.0                     # mm, day-name header row
_ROW_H = 13.5                       # mm per hour row


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


def _instructor_text(a: dict) -> str:
    name = str(a.get("instructor_name", "") or "")
    iid = str(a.get("instructor_id", "") or "")
    if name and iid and "@" in iid:
        return f"{name} ({iid})"
    return name or iid


def _fit(pdf: FPDF, text: str, max_w: float) -> str:
    """Truncate text with an ellipsis so it fits within max_w (current font)."""
    text = str(text)
    if pdf.get_string_width(text) <= max_w:
        return text
    ell = "…"
    while text and pdf.get_string_width(text + ell) > max_w:
        text = text[:-1]
    return (text + ell) if text else ""


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


def _draw_block(pdf: FPDF, a: dict, x: float, y: float, w: float, h: float,
                show_instructor: bool, cont: bool = False) -> None:
    color = block_color(a)
    accent = _hex_to_rgb(color)
    fill = _tint(color, 0.13)                  # ~13% color over white (matches UI)
    code_rgb = _blend(accent, (32, 34, 44), 0.72)   # dark tint of the color
    r, bar_w = 2.4, 2.4                        # card corner radius / left-bar width
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
    section = str(a.get("section_id") or a.get("course_code", ""))
    lines = [(section, tag, 7.2, True, code_rgb)]
    if show_instructor:
        instr = _instructor_text(a)
        if instr:
            lines.append((instr, "", 6.0, False, (96, 100, 112)))
    room = str(a.get("room", "") or "")
    if room:
        lines.append((room, "", 6.0, False, _blend(accent, (70, 74, 86), 0.6)))

    pad_l, pad_t = 5.0, 1.6
    tw = w - pad_l - 1.8
    with pdf.rect_clip(x, y, w, h):
        cy = y + pad_t
        for txt, tg, size, bold, rgb in lines:
            lh = size * 0.46
            if cy + lh > y + h:
                break
            pdf.set_font("DejaVu", "B" if bold else "", size)
            pdf.set_text_color(*rgb)
            pdf.set_xy(x + pad_l, cy)
            shown = _fit(pdf, txt, tw - (9.0 if tg else 0))
            pdf.cell(pdf.get_string_width(shown) + 0.5, lh, shown)
            if tg:                              # small bordered tag pill (amber for PRAT)
                _draw_tag(pdf, tg)
            cy += lh + 0.6
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


def build_grid_pdf(schedule: dict, title: str, lang: str = DEFAULT_LANG,
                   show_instructor: bool = True) -> bytes:
    """Render ONE landscape-A4 weekly calendar for an already-filtered schedule.

    schedule: a schedule dict ({"assignments": [...]}) already narrowed to the
        entity (use filter_assignments upstream).
    title: header line, e.g. "Öğretim elemanı: Ahmet Acar".
    """
    days = DAY_LABELS.get(lang, DAY_LABELS[DEFAULT_LANG])

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("DejaVu", "", str(_FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(_FONT_BOLD))
    pdf.add_page()

    # Title
    pdf.set_font("DejaVu", "B", 14)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 9, title, new_x="LMARGIN", new_y="NEXT")

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

    return bytes(pdf.output())


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
    """One PDF per entity. 1 → (pdf, '<entity>.pdf', application/pdf);
    2+ → (zip, 'schedule_<view_field>.zip', application/zip)."""
    pdfs: List[Tuple[str, bytes]] = []
    seen: dict = {}
    for ent in entities:
        view = filter_assignments(schedule, view_field, ent)
        data = build_grid_pdf(view, f"{dim_label}: {ent}", lang)
        base = _sanitize_filename(str(ent))
        seen[base] = seen.get(base, 0) + 1
        fname = base if seen[base] == 1 else f"{base}_{seen[base]}"
        pdfs.append((f"{fname}.pdf", data))

    if len(pdfs) == 1:
        name, data = pdfs[0]
        return data, name, "application/pdf"

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in pdfs:
            zf.writestr(name, data)
    return buf.getvalue(), f"schedule_{view_field}.zip", "application/zip"
