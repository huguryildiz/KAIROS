"""Pure PDF export of the weekly timetable grid. Streamlit-free → unit-testable.

Builds landscape-A4 weekly grids (hours × Mon–Fri) with fpdf2, embedding a
Unicode TTF (DejaVuSans) so Turkish glyphs render. See build_pdf_bundle for the
single-PDF / zip packaging used by the Results view.
"""
from __future__ import annotations

import io
import re
import zipfile
from pathlib import Path
from typing import List, Tuple

from fpdf import FPDF

from .ui_grid import DAYS_ORDER, build_week_grid, filter_assignments
from .i18n import DAY_LABELS, DEFAULT_LANG

_FONT_DIR = Path(__file__).parent / "assets" / "fonts"
_FONT_REGULAR = _FONT_DIR / "DejaVuSans.ttf"
_FONT_BOLD = _FONT_DIR / "DejaVuSans-Bold.ttf"

_HOUR_LO, _HOUR_HI = 9, 21          # grid rows = hours 9..20 inclusive
_TIME_COL_W = 16.0                  # mm
_ROW_H = 14.0                       # mm per hour row


def _cell_text(blocks: list, hour: int, show_instructor: bool) -> str:
    """Compact text for one (day, hour) cell. Only blocks STARTING this hour
    render text (mirrors the on-screen grid), so a 2h block is not duplicated."""
    parts = []
    for a in blocks:
        if int(a.get("start", 0)) != hour:
            continue
        code = str(a.get("course_code") or a.get("section_id") or "")
        room = str(a.get("room") or "")
        line = " ".join(p for p in (code, room) if p)
        if show_instructor:
            name = str(a.get("instructor_name") or "")
            if name:
                line = f"{line}\n{name}" if line else name
        parts.append(line)
    return "\n".join(p for p in parts if p)


def build_grid_pdf(schedule: dict, title: str, lang: str = DEFAULT_LANG,
                   show_instructor: bool = True) -> bytes:
    """Render ONE landscape-A4 weekly grid for an already-filtered schedule.

    schedule: a schedule dict ({"assignments": [...]}) already narrowed to the
        entity (use filter_assignments upstream).
    title: header line, e.g. "Öğretim elemanı: Şükrü Çağ".
    """
    grid = build_week_grid(schedule, _HOUR_LO, _HOUR_HI)
    days = DAY_LABELS.get(lang, DAY_LABELS[DEFAULT_LANG])

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=False)
    pdf.add_font("DejaVu", "", str(_FONT_REGULAR))
    pdf.add_font("DejaVu", "B", str(_FONT_BOLD))
    pdf.add_page()

    # Title
    pdf.set_font("DejaVu", "B", 14)
    pdf.cell(0, 10, title, new_x="LMARGIN", new_y="NEXT")
    pdf.ln(1)

    usable = pdf.w - pdf.l_margin - pdf.r_margin
    day_w = (usable - _TIME_COL_W) / len(DAYS_ORDER)

    # Header row
    pdf.set_font("DejaVu", "B", 9)
    pdf.cell(_TIME_COL_W, 8, "", border=1, align="C")
    for d in DAYS_ORDER:
        pdf.cell(day_w, 8, days.get(d, d), border=1, align="C")
    pdf.ln(8)

    # Hour rows
    for h in range(_HOUR_LO, _HOUR_HI):
        x0, y0 = pdf.get_x(), pdf.get_y()
        pdf.set_font("DejaVu", "B", 8)
        pdf.cell(_TIME_COL_W, _ROW_H, f"{h:02d}:00", border=1, align="C")
        pdf.set_font("DejaVu", "", 7)
        for d in DAYS_ORDER:
            text = _cell_text(grid.get((d, h), []), h, show_instructor)
            x, y = pdf.get_x(), pdf.get_y()
            pdf.multi_cell(day_w, 4, text, border=1, align="C",
                           new_x="RIGHT", new_y="TOP", max_line_height=4)
            pdf.set_xy(x + day_w, y)   # keep row alignment regardless of wrap
        pdf.set_xy(x0, y0 + _ROW_H)

    return bytes(pdf.output())
