"""Pure (Streamlit-free) styling + HTML builders for the UI.

Visual language ported from the MÜDEK PÇ project (huguryildiz/mudek-pc-olcum):
a calm corporate light theme — navy primary (#2B3A8C) on a soft canvas, white
surfaces with a subtle card shadow, Inter for text and Geist Mono for numerics.
Kept import-light so the HTML builders stay unit-testable.
"""
from __future__ import annotations
import base64
import os
from html import escape
from typing import List, Tuple

from .ui_grid import build_week_grid, DAYS_ORDER
from .i18n import DAY_LABELS, DEFAULT_LANG, t

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.svg")


def logo_img_html(width: int = 180, path: str = _LOGO_PATH) -> str:
    """Sidebar logo as a base64 <img> — robust against Streamlit's markdown
    sanitizer, which renders raw inline SVG (with comments) as literal text."""
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""
    return (f'<img src="data:image/svg+xml;base64,{b64}" width="{width}" '
            f'style="margin:6px 0 12px" alt="Course Timetabling">')

# Department block palette — calm, professional hues that read on white as
# light-tint chips with a solid color bar (consistent with the navy theme).
_PALETTE = [
    "#2B3A8C", "#0F766E", "#B4490F", "#5671D7", "#6D5BD0",
    "#0E7490", "#B8860B", "#BE385E", "#2F855A", "#7C3AED",
]


def dept_color(dept: str) -> str:
    """Deterministic color for a department code (stable across runs)."""
    key = str(dept or "")
    idx = sum(ord(c) for c in key) % len(_PALETTE)
    return _PALETTE[idx]


BRAND_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Geist+Mono:wght@400;500;600&display=swap');

:root{
  --primary:#2B3A8C; --primary-700:#1F2B67;
  --canvas:#F5F7FA; --ink:#161B26; --border:#E3E7ED; --surface:#FFFFFF;
  --muted:#F1F4F8; --muted-fg:#64748B;
  --above:#0F766E; --above-bg:#F0FDF4; --below:#B4490F; --below-bg:#FEF3EE;
  --font:'Inter',system-ui,-apple-system,sans-serif;
  --mono:'Geist Mono','SF Mono',Menlo,Consolas,monospace;
  --shadow-card:0 1px 3px 0 rgba(22,27,38,.07), 0 1px 2px -1px rgba(22,27,38,.05);
  --shadow-hover:0 4px 12px 0 rgba(22,27,38,.10);
}
html,body,[class*="css"],.stApp,p,span,div,label,input,button,select,textarea{
  font-family:var(--font); color:var(--ink);
}
.stApp{background:var(--canvas);}
.block-container{max-width:1180px; padding-top:2.4rem;}
h1,h2,h3,h4{font-family:var(--font) !important;font-weight:700;letter-spacing:-.012em;
  color:var(--ink);}
.tabular,.tt-time,.tt-card .v,.tt-blk .meta,.tt-step b{font-variant-numeric:tabular-nums;}

/* Sidebar */
section[data-testid="stSidebar"]{background:var(--surface);border-right:1px solid var(--border);}

/* Buttons */
.stButton>button[kind="primary"]{
  background:var(--primary); color:#fff; border:1px solid var(--primary);
  border-radius:8px; font-weight:600; box-shadow:var(--shadow-card);
}
.stButton>button[kind="primary"]:hover{background:var(--primary-700);border-color:var(--primary-700);color:#fff;}
.stButton>button:not([kind="primary"]), .stDownloadButton>button{
  background:var(--surface); color:var(--ink); border:1px solid var(--border);
  border-radius:8px; font-weight:500;
}
.stButton>button:not([kind="primary"]):hover, .stDownloadButton>button:hover{
  border-color:var(--primary); color:var(--primary); box-shadow:var(--shadow-card);
}

/* Hero */
.tt-hero{border:1px solid var(--border); border-radius:10px; padding:26px 28px; margin:4px 0 16px;
  background:var(--surface); box-shadow:var(--shadow-card);}
.tt-hero .eyebrow{font:600 .68rem/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;
  color:var(--primary);}
.tt-hero h1{font-size:2.1rem;line-height:1.1;margin:.5rem 0 .5rem;font-weight:700;}
.tt-hero h1 em{font-style:normal;color:var(--primary);}
.tt-hero p{color:var(--muted-fg);margin:0;max-width:60ch;font-size:1.0rem;}
.tt-steps{display:flex;gap:8px;flex-wrap:wrap;margin-top:18px;}
.tt-step{font:600 12px/1 var(--font);color:var(--ink);background:var(--muted);
  border:1px solid var(--border);padding:7px 12px;border-radius:999px;}
.tt-step b{color:var(--primary);margin-right:7px;font-family:var(--mono);}

/* Metric cards */
.tt-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:8px 0 18px;}
.tt-card{border:1px solid var(--border);border-radius:10px;padding:15px 16px;background:var(--surface);
  box-shadow:var(--shadow-card);transition:box-shadow .2s;}
.tt-card:hover{box-shadow:var(--shadow-hover);}
.tt-card .v{font:700 1.9rem/1 var(--font);color:var(--ink);}
.tt-card .l{font:600 10px/1 var(--mono);text-transform:uppercase;letter-spacing:.08em;
  color:var(--muted-fg);margin-top:9px;}
.tt-card.good .v{color:var(--above);} .tt-card.bad .v{color:var(--below);} .tt-card.brand .v{color:var(--primary);}

/* Timetable grid — the signature element */
.tt-wrap{border:1px solid var(--border);border-radius:10px;overflow:hidden;background:var(--surface);
  box-shadow:var(--shadow-card);}
table.tt{border-collapse:collapse;width:100%;table-layout:fixed;}
table.tt th{background:var(--muted);color:var(--muted-fg);font:600 11px/1 var(--mono);
  text-transform:uppercase;letter-spacing:.06em;padding:11px 8px;border-bottom:1px solid var(--border);}
table.tt th.tt-time, table.tt td.tt-time{width:60px;}
table.tt td{border-bottom:1px solid #EEF1F6;border-left:1px solid #F2F4F8;
  vertical-align:top;height:30px;padding:3px;}
td.tt-time{color:var(--muted-fg);font:500 12px/30px var(--mono);text-align:center;background:#FAFBFD;}
.tt-blk{border-radius:6px;padding:4px 8px;margin:1px 0;
  background:color-mix(in srgb, var(--c) 11%, #fff);
  border-left:3px solid var(--c);
  color:color-mix(in srgb, var(--c) 70%, #0b1020);}
.tt-blk.cont{background:color-mix(in srgb, var(--c) 7%, #fff);min-height:14px;opacity:.7;
  border-radius:0;}
.tt-blk.lab{border-left-style:dashed;}
.tt-blk .code{font:600 12px/1.15 var(--font);display:block;}
.tt-blk .meta{font:500 10px/1.2 var(--mono);opacity:.7;display:block;margin-top:2px;}
.tt-blk .tag{font:600 8px/1 var(--mono);letter-spacing:.04em;border:1px solid currentColor;
  border-radius:4px;padding:1px 4px;margin-left:6px;vertical-align:1px;}
.tt-empty{color:#9AA3B2;font:500 13px/1 var(--font);padding:22px;text-align:center;}
</style>
"""


def metric_cards_html(cards: List[Tuple[str, str, str]]) -> str:
    """cards = [(label, value, tone)] where tone in {'', 'good', 'bad', 'brand'}."""
    cells = "".join(
        f'<div class="tt-card {escape(tone)}"><div class="v">{escape(str(v))}</div>'
        f'<div class="l">{escape(label)}</div></div>'
        for (label, v, tone) in cards)
    return f'<div class="tt-cards">{cells}</div>'


def _block_html(a: dict, is_start: bool, meta_field: str = "room") -> str:
    color = dept_color(a.get("dept", ""))
    is_lab = "lab" in str(a.get("block_kind", "")).lower()
    klass = "tt-blk" + (" lab" if is_lab else "") + ("" if is_start else " cont")
    if not is_start:
        return f'<div class="{klass}" style="--c:{color}"></div>'
    tag = '<span class="tag">LAB</span>' if is_lab else ""
    meta = escape(str(a.get(meta_field, "") or a.get("room", "")))
    code = escape(str(a.get("course_code") or a.get("section_id", "")))
    title = " · ".join(str(a.get(k, "")) for k in ("instructor_name", "room", "cohort") if a.get(k))
    return (f'<div class="{klass}" style="--c:{color}" title="{escape(title)}">'
            f'<span class="code">{code}{tag}</span>'
            f'<span class="meta">{meta}</span></div>')


def week_grid_html(schedule: dict, hour_lo: int = 9, hour_hi: int = 21,
                   meta_field: str = "room", lang: str = DEFAULT_LANG) -> str:
    grid = build_week_grid(schedule, hour_lo, hour_hi)
    if not schedule.get("assignments"):
        return (f'<div class="tt-wrap"><div class="tt-empty">'
                f'{t("grid_empty", lang)}</div></div>')
    days = DAY_LABELS.get(lang, DAY_LABELS[DEFAULT_LANG])
    head = '<th class="tt-time"></th>' + "".join(
        f"<th>{days.get(d, d)}</th>" for d in DAYS_ORDER)
    rows = []
    for h in range(hour_lo, hour_hi):
        cells = [f'<td class="tt-time">{h:02d}:00</td>']
        for d in DAYS_ORDER:
            blocks = grid.get((d, h), [])
            inner = "".join(_block_html(a, is_start=(int(a.get("start", 0)) == h),
                                        meta_field=meta_field)
                            for a in blocks)
            cells.append(f"<td>{inner}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="tt-wrap"><table class="tt"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
