"""Pure (Streamlit-free) styling + HTML builders for the premium single-flow UI.

Visual language ported from the approved mockup (docs/ui-mockup.html): a calm
navy theme on a soft canvas with light + dark variants. The full token-driven
stylesheet is emitted by `brand_css(theme)`; every component rule reads CSS
variables, so switching theme is a pure token swap. Kept import-light so the
HTML builders stay unit-testable.
"""
from __future__ import annotations
import base64
import os
from html import escape
from typing import List, Tuple

from .ui_grid import build_week_grid, DAYS_ORDER
from .i18n import DAY_LABELS, DEFAULT_LANG, t

_LOGO_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "logo.svg")


def logo_img_html(width: int = 150, path: str = _LOGO_PATH) -> str:
    """Logo as a base64 <img> — robust against Streamlit's markdown sanitizer,
    which renders raw inline SVG (with comments) as literal text."""
    try:
        with open(path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("ascii")
    except OSError:
        return ""
    return (f'<img src="data:image/svg+xml;base64,{b64}" width="{width}" '
            f'style="margin:0" alt="Course Timetabling">')


# Per-course block palette — calm, professional hues.
_PALETTE = [
    "#2B3A8C", "#0F766E", "#B4490F", "#5671D7", "#6D5BD0",
    "#0E7490", "#B8860B", "#BE385E", "#2F855A", "#7C3AED",
]


def dept_color(dept: str) -> str:
    """Deterministic color for a department code (stable across runs)."""
    key = str(dept or "")
    idx = sum(ord(c) for c in key) % len(_PALETTE)
    return _PALETTE[idx]


def block_color(a: dict) -> str:
    """Per-course color so each course reads as a distinct block."""
    key = str(a.get("course_code")
              or str(a.get("section_id", "")).split("_")[0]
              or a.get("dept", ""))
    idx = sum(ord(c) for c in key) % len(_PALETTE)
    return _PALETTE[idx]


# --------------------------------------------------------------------------- #
# Theme tokens
# --------------------------------------------------------------------------- #

_LIGHT_TOKENS = {
    "--primary": "#2B3A8C", "--primary-700": "#1F2B67",
    "--primary-50": "#EEF1FB", "--primary-100": "#E0E6F7",
    "--canvas": "#F4F6FA", "--surface": "#FFFFFF", "--surface-2": "#FAFBFD",
    "--ink": "#131722", "--ink-2": "#39414F", "--muted": "#5B6472", "--faint": "#9AA3B2",
    "--border": "#E5E9F1", "--border-2": "#EEF1F6",
    "--good": "#0F766E", "--good-bg": "#ECFDF6", "--good-bd": "#A7E3D4",
    "--warn": "#B4490F", "--warn-bg": "#FEF4EE", "--warn-bd": "#F3CBB4",
    "--info": "#1F4FB8", "--info-bg": "#EEF3FC", "--info-bd": "#C4D6F4",
    "--font": "'Inter',system-ui,-apple-system,sans-serif",
    "--mono": "'Geist Mono','SF Mono',Menlo,Consolas,monospace",
    "--sh-1": "0 1px 2px rgba(20,24,38,.05),0 1px 3px rgba(20,24,38,.06)",
    "--sh-2": "0 2px 6px rgba(20,24,38,.06),0 8px 24px -8px rgba(20,24,38,.12)",
    "--sh-3": "0 10px 40px -12px rgba(31,43,103,.28)",
    "--r-sm": "8px", "--r": "12px", "--r-lg": "16px", "--r-xl": "22px",
    "--tt-bg": "#ffffff", "--tt-ink": "#0b1020", "--dz": "#C2CBDC",
    "--appbar-bg": "rgba(255,255,255,.82)", "--stepper-bg": "rgba(244,246,250,.86)",
    "--body-glow": "#E7ECFA", "--switch-off": "#D4DAE6",
    "--pill-lab-bg": "#F1EEFB", "--pill-lab-bd": "#DAD2F4", "--pill-lab-fg": "#5B4BBE",
}

_DARK_TOKENS = {**_LIGHT_TOKENS, **{
    "--primary": "#7E90EE", "--primary-700": "#5C6FD6",
    "--primary-50": "rgba(126,144,238,.12)", "--primary-100": "rgba(126,144,238,.24)",
    "--canvas": "#0E1220", "--surface": "#161C2C", "--surface-2": "#1B2233",
    "--ink": "#EAEEF7", "--ink-2": "#C5CCDD", "--muted": "#8A93A8", "--faint": "#5E6678",
    "--border": "#28314B", "--border-2": "#222A40",
    "--good": "#34D6AA", "--good-bg": "rgba(52,214,170,.13)", "--good-bd": "rgba(52,214,170,.36)",
    "--warn": "#EFA463", "--warn-bg": "rgba(239,164,99,.13)", "--warn-bd": "rgba(239,164,99,.36)",
    "--info": "#7E90EE", "--info-bg": "rgba(126,144,238,.12)", "--info-bd": "rgba(126,144,238,.32)",
    "--sh-1": "0 1px 2px rgba(0,0,0,.4)", "--sh-2": "0 6px 22px -8px rgba(0,0,0,.55)",
    "--sh-3": "0 18px 50px -16px rgba(0,0,0,.65)",
    "--tt-bg": "#141A28", "--tt-ink": "#F2F5FC", "--dz": "#39425E",
    "--appbar-bg": "rgba(14,18,32,.72)", "--stepper-bg": "rgba(14,18,32,.78)",
    "--body-glow": "rgba(70,86,170,.30)", "--switch-off": "#39425E",
    "--pill-lab-bg": "rgba(124,107,222,.18)", "--pill-lab-bd": "rgba(124,107,222,.4)",
    "--pill-lab-fg": "#B7ABF2",
}}

_FONT_IMPORT = ("@import url('https://fonts.googleapis.com/css2?"
                "family=Inter:wght@400;500;600;700;800&"
                "family=Geist+Mono:wght@400;500;600&display=swap');")

# Hide Streamlit's native chrome so our custom app bar + stepper own the frame.
_HIDE_CHROME = """
header[data-testid="stHeader"]{display:none;}
[data-testid="stToolbar"],#MainMenu,footer{display:none;}
section[data-testid="stSidebar"]{display:none;}
[data-testid="stAppViewContainer"] .block-container{max-width:1160px;padding-top:1rem;padding-bottom:5rem;}
"""

# Component stylesheet — all rules read CSS variables (theme-neutral).
_COMPONENT_CSS = """
*{box-sizing:border-box;}
html,body,.stApp,p,span,div,label,input,button,select,textarea{font-family:var(--font);color:var(--ink);}
.stApp{background:var(--canvas);background-image:radial-gradient(1200px 480px at 78% -8%, var(--body-glow) 0%, rgba(0,0,0,0) 60%);background-repeat:no-repeat;}
h1,h2,h3,h4{margin:0;letter-spacing:-.018em;font-weight:700;color:var(--ink);}
.tabular,.num,.tt-time,.tt-blk .meta{font-variant-numeric:tabular-nums;}

/* App bar (left side: brand + context pill) */
.tt-appbar{display:flex;align-items:center;gap:14px;}
.tt-brand{display:flex;align-items:center;gap:11px;font-weight:700;}
.tt-brand .glyph{width:34px;height:34px;border-radius:10px;flex:none;background:linear-gradient(145deg,var(--primary) 0%,#4456B5 100%);box-shadow:var(--sh-1),inset 0 1px 0 rgba(255,255,255,.25);display:grid;place-items:center;color:#fff;}
.tt-brand .glyph svg{width:19px;height:19px;}
.tt-brand .name{font-size:.98rem;letter-spacing:-.01em;}
.tt-brand .name small{display:block;font:500 .68rem/1.1 var(--mono);color:var(--muted);letter-spacing:.02em;}
.context-pill{display:inline-flex;align-items:center;gap:7px;font:600 .74rem/1 var(--mono);color:var(--ink-2);background:var(--surface-2);border:1px solid var(--border);padding:8px 12px;border-radius:999px;}
.context-pill .dot{width:7px;height:7px;border-radius:50%;background:var(--faint);}
.context-pill.live .dot{background:var(--good);box-shadow:0 0 0 3px var(--good-bg);}

/* Step indicator */
.stepper-wrap{background:var(--stepper-bg);border:1px solid var(--border);border-radius:999px;margin:6px 0 18px;}
.stepper{display:flex;align-items:center;gap:4px;padding:8px 12px;flex-wrap:wrap;}
.step{display:flex;align-items:center;gap:9px;padding:7px 13px 7px 8px;border-radius:999px;border:1px solid transparent;text-decoration:none;transition:.18s;white-space:nowrap;}
.step .idx{width:23px;height:23px;flex:none;border-radius:50%;display:grid;place-items:center;font:700 .74rem/1 var(--mono);color:var(--muted);background:var(--surface);border:1px solid var(--border);}
.step .lbl{font:600 .82rem/1 var(--font);color:var(--muted);}
.step:hover{background:var(--surface);}
.step.active{background:var(--surface);border-color:var(--primary-100);box-shadow:var(--sh-1);}
.step.active .idx{background:var(--primary);color:#fff;border-color:var(--primary);}
.step.active .lbl{color:var(--ink);}
.step.done .idx{background:var(--good-bg);color:var(--good);border-color:var(--good-bd);}
.step.done .lbl{color:var(--ink-2);}
.step.locked{opacity:.45;filter:grayscale(.3);cursor:not-allowed;}
.stp-divider{flex:1;height:1px;background:var(--border);margin:0 2px;min-width:8px;}

/* Section headers */
.eyebrow{font:600 .7rem/1 var(--mono);letter-spacing:.16em;text-transform:uppercase;color:var(--primary);display:flex;align-items:center;gap:9px;margin:8px 0 11px;}
.eyebrow .n{display:grid;place-items:center;width:21px;height:21px;border-radius:6px;background:var(--primary-50);color:var(--primary);font-size:.72rem;border:1px solid var(--primary-100);}

/* Hero */
.tt-hero{position:relative;overflow:hidden;border-radius:var(--r-xl);margin:4px 0 22px;padding:34px 38px;color:#fff;background:radial-gradient(680px 320px at 88% -30%, #5C6CC6 0%, rgba(92,108,198,0) 62%),linear-gradient(135deg,#233178 0%,#2B3A8C 46%,#1C2766 100%);box-shadow:var(--sh-3);}
.tt-hero .eyebrow{color:#AEBBF0;}
.tt-hero .eyebrow .n{background:rgba(255,255,255,.14);color:#fff;border-color:rgba(255,255,255,.2);}
.tt-hero h1{color:#fff;font-size:2.3rem;line-height:1.07;font-weight:800;max-width:18ch;margin:4px 0 0;}
.tt-hero h1 em{font-style:normal;color:#C7D0F4;}
.tt-hero p{position:relative;color:#C9D1EE;max-width:54ch;margin:13px 0 0;font-size:1.0rem;}
.tt-hero .row{position:relative;display:flex;gap:10px;margin-top:20px;flex-wrap:wrap;}
.chip-stat{display:flex;flex-direction:column;gap:3px;padding:10px 15px;border-radius:var(--r);background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);}
.chip-stat .v{font:800 1.12rem/1 var(--font);color:#fff;}
.chip-stat .l{font:600 .62rem/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:#AEBBF0;}

/* KPI chips */
.chips{display:flex;flex-wrap:wrap;gap:11px;margin-bottom:14px;}
.kpi{flex:1;min-width:150px;background:var(--surface);border:1px solid var(--border);border-radius:var(--r);padding:14px 16px;box-shadow:var(--sh-1);position:relative;overflow:hidden;}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--primary);opacity:.55;}
.kpi.good::before{background:var(--good);}.kpi.warn::before{background:var(--warn);}
.kpi .v{font:800 1.6rem/1 var(--font);letter-spacing:-.02em;}
.kpi.good .v{color:var(--good);}.kpi.warn .v{color:var(--warn);}
.kpi .l{font:600 .66rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:8px;}

/* Metric cards (results) */
.tt-cards{display:grid;grid-template-columns:repeat(4,1fr);gap:13px;margin:6px 0 18px;}
.tt-card{border:1px solid var(--border);border-radius:var(--r-lg);padding:18px 20px;background:var(--surface);box-shadow:var(--sh-1);transition:box-shadow .2s,transform .2s;position:relative;overflow:hidden;}
.tt-card:hover{box-shadow:var(--sh-2);transform:translateY(-2px);}
.tt-card .v{font:800 2.0rem/1 var(--font);letter-spacing:-.03em;color:var(--ink);}
.tt-card .l{font:600 .64rem/1 var(--mono);text-transform:uppercase;letter-spacing:.09em;color:var(--muted);margin-top:10px;}
.tt-card.good .v{color:var(--good);}.tt-card.bad .v{color:var(--warn);}.tt-card.brand .v{color:var(--primary);}

/* Pills */
.pill{display:inline-block;font:600 .68rem/1 var(--mono);padding:4px 8px;border-radius:6px;background:var(--surface-2);border:1px solid var(--border);color:var(--ink-2);}
.pill.lab{background:var(--pill-lab-bg);border-color:var(--pill-lab-bd);color:var(--pill-lab-fg);}
.pill.online{background:var(--good-bg);border-color:var(--good-bd);color:var(--good);}

/* Timetable grid — the signature element */
.tt-wrap{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface);box-shadow:var(--sh-1);}
table.tt{border-collapse:collapse;width:100%;table-layout:fixed;}
table.tt th{background:var(--surface-2);color:var(--muted);font:600 .68rem/1 var(--mono);text-transform:uppercase;letter-spacing:.07em;padding:12px 8px;border-bottom:1px solid var(--border);}
table.tt th.tt-time,table.tt td.tt-time{width:62px;}
table.tt td{border-bottom:1px solid var(--border-2);border-left:1px solid var(--border-2);vertical-align:top;height:32px;padding:3px;}
td.tt-time{color:var(--faint);font:500 .72rem/32px var(--mono);text-align:center;background:var(--surface-2);}
.tt-blk{border-radius:7px;padding:5px 9px;margin:1px 0;background:color-mix(in srgb, var(--c) 13%, var(--tt-bg));border-left:3px solid var(--c);color:color-mix(in srgb, var(--c) 70%, var(--tt-ink));box-shadow:0 1px 2px rgba(20,24,38,.04);transition:.15s;}
.tt-blk:hover{transform:translateY(-1px);box-shadow:var(--sh-1);}
.tt-blk.cont{background:color-mix(in srgb, var(--c) 8%, var(--tt-bg));min-height:16px;opacity:.7;border-radius:0;box-shadow:none;}
.tt-blk.lab{border-left-style:dashed;}
.tt-blk .code{font:600 .76rem/1.15 var(--font);display:block;}
.tt-blk .who{font:500 .66rem/1.25 var(--font);display:block;margin-top:2px;opacity:.85;}
.tt-blk .meta{font:500 .64rem/1.2 var(--mono);opacity:.72;display:block;margin-top:1px;}
.tt-blk .tag{font:600 .52rem/1 var(--mono);letter-spacing:.04em;border:1px solid currentColor;border-radius:4px;padding:1px 4px;margin-left:6px;vertical-align:1px;}
.tt-empty{color:var(--faint);font:500 .9rem/1 var(--font);padding:24px;text-align:center;}

/* Streamlit widget integration */
.stButton>button[kind="primary"]{background:linear-gradient(135deg,var(--primary) 0%,#3A49A0 100%);color:#fff;border:1px solid var(--primary);border-radius:10px;font-weight:600;box-shadow:0 1px 2px rgba(31,43,103,.3),0 6px 18px -8px rgba(31,43,103,.5);}
.stButton>button[kind="primary"]:hover{filter:brightness(1.06);color:#fff;border-color:var(--primary);}
.stButton>button:not([kind="primary"]),.stDownloadButton>button{background:var(--surface);color:var(--ink);border:1px solid var(--border);border-radius:10px;font-weight:500;}
.stButton>button:not([kind="primary"]):hover,.stDownloadButton>button:hover{border-color:var(--primary);color:var(--primary);box-shadow:var(--sh-1);}
[data-testid="stFileUploaderDropzone"]{background:var(--surface-2);border:1.6px dashed var(--dz);border-radius:var(--r-lg);}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--primary);}
[data-testid="stFileUploaderDropzone"] *{color:var(--ink);}
/* Glide data grid (st.dataframe / st.data_editor) — themed via its own vars so
   both light and dark follow our tokens. */
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;
  --gdg-accent-color:var(--primary);--gdg-accent-light:var(--primary-50);
  --gdg-bg-cell:var(--surface);--gdg-bg-cell-medium:var(--surface-2);
  --gdg-bg-header:var(--surface-2);--gdg-bg-header-has-focus:var(--primary-50);
  --gdg-bg-header-hovered:var(--surface-2);--gdg-bg-bubble:var(--surface);
  --gdg-border-color:var(--border-2);--gdg-horizontal-border-color:var(--border-2);
  --gdg-text-dark:var(--ink);--gdg-text-medium:var(--muted);--gdg-text-light:var(--faint);
  --gdg-text-header:var(--muted);--gdg-font-family:var(--font);}
/* Misc Streamlit chrome that should follow the theme */
hr{border-color:var(--border) !important;}
[data-testid="stWidgetLabel"] p,[data-testid="stCaptionContainer"],.stRadio label{color:var(--ink);}
[data-baseweb="slider"] [role="slider"]{background:var(--primary) !important;}
[data-testid="stAlert"]{border-radius:var(--r);}
"""


def brand_css(theme: str = "light") -> str:
    """Full <style> block for the given theme ('light' | 'dark'). Switching is a
    pure CSS-variable swap; every component rule reads the tokens."""
    tokens = _DARK_TOKENS if theme == "dark" else _LIGHT_TOKENS
    root = ":root{" + "".join(f"{k}:{v};" for k, v in tokens.items()) + "}"
    return f"<style>{_FONT_IMPORT}{root}{_COMPONENT_CSS}{_HIDE_CHROME}</style>"


# Back-compat alias for any importer expecting the old constant.
BRAND_CSS = brand_css("light")


# --------------------------------------------------------------------------- #
# HTML builders (pure)
# --------------------------------------------------------------------------- #

_GLYPH_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
              'stroke-width="2" stroke-linecap="round"><rect x="3" y="4" '
              'width="18" height="17" rx="2"/><path d="M3 9h18M8 2v4M16 2v4"/>'
              '<path d="M8 13h2M14 13h2M8 17h2"/></svg>')


def appbar_html(lang: str, context_text: str, live: bool = False) -> str:
    """Left side of the app bar: brand glyph + name + context pill."""
    cls = "context-pill live" if live else "context-pill"
    return (
        f'<div class="tt-appbar"><div class="tt-brand">'
        f'<div class="glyph">{_GLYPH_SVG}</div>'
        f'<div class="name">{escape(t("app_title", lang))}'
        f'<small>{escape(t("app_subtitle", lang))}</small></div></div>'
        f'<span class="{cls}"><span class="dot"></span>{escape(context_text)}</span>'
        f'</div>'
    )


def stepper_html(steps: List[dict], lang: str = DEFAULT_LANG) -> str:
    """Render the step indicator. Each step: {key, label, status} where status
    is one of active|done|locked|todo. Locked steps are non-navigable spans."""
    parts: List[str] = []
    for i, s in enumerate(steps):
        if i:
            parts.append('<div class="stp-divider"></div>')
        status = s.get("status", "todo")
        idx = str(i + 1)
        inner = (f'<span class="idx">{idx}</span>'
                 f'<span class="lbl">{escape(str(s.get("label", "")))}</span>')
        cls = f"step {status}".strip()
        if status == "locked":
            parts.append(f'<span class="{cls}">{inner}</span>')
        else:
            parts.append(f'<a class="{cls}" href="#s-{escape(str(s.get("key","")))}">{inner}</a>')
    return f'<div class="stepper-wrap"><nav class="stepper">{"".join(parts)}</nav></div>'


def kpi_chips_html(items: List[Tuple[str, str, str]]) -> str:
    """items = [(label, value, tone)] with tone in {'', 'good', 'warn'}."""
    cells = "".join(
        f'<div class="kpi {escape(tone)}"><div class="v">{escape(str(v))}</div>'
        f'<div class="l">{escape(label)}</div></div>'
        for (label, v, tone) in items)
    return f'<div class="chips">{cells}</div>'


def hero_html(lang: str = DEFAULT_LANG) -> str:
    """Hero banner (replaces the old views/home.py page)."""
    return (
        f'<div class="tt-hero">'
        f'<div class="eyebrow"><span class="n">◆</span>{escape(t("hero_eyebrow", lang))}</div>'
        f'<h1>{t("hero_title_html", lang)}</h1>'
        f'<p>{escape(t("hero_body", lang))}</p>'
        f'<div class="row">'
        f'<div class="chip-stat"><span class="v">~793</span><span class="l">{escape(t("hero_stat_sections", lang))}</span></div>'
        f'<div class="chip-stat"><span class="v">0</span><span class="l">{escape(t("hero_stat_conflicts", lang))}</span></div>'
        f'<div class="chip-stat"><span class="v">91.7%</span><span class="l">{escape(t("hero_stat_placed", lang))}</span></div>'
        f'<div class="chip-stat"><span class="v">CP-SAT</span><span class="l">{escape(t("hero_stat_engine", lang))}</span></div>'
        f'</div></div>'
    )


def metric_cards_html(cards: List[Tuple[str, str, str]]) -> str:
    """cards = [(label, value, tone)] where tone in {'', 'good', 'bad', 'brand'}."""
    cells = "".join(
        f'<div class="tt-card {escape(tone)}"><div class="v">{escape(str(v))}</div>'
        f'<div class="l">{escape(label)}</div></div>'
        for (label, v, tone) in cards)
    return f'<div class="tt-cards">{cells}</div>'


def _block_html(a: dict, is_start: bool) -> str:
    color = block_color(a)
    is_lab = "lab" in str(a.get("block_kind", "")).lower()
    klass = "tt-blk" + (" lab" if is_lab else "") + ("" if is_start else " cont")
    if not is_start:
        return f'<div class="{klass}" style="--c:{color}"></div>'
    tag = '<span class="tag">LAB</span>' if is_lab else ""
    section = escape(str(a.get("section_id") or a.get("course_code", "")))
    instructor = escape(str(a.get("instructor_name", "")))
    room = escape(str(a.get("room", "")))
    title = " · ".join(str(a.get(k, "")) for k in
                       ("course_code", "instructor_name", "room", "cohort") if a.get(k))
    lines = [f'<span class="code">{section}{tag}</span>']
    if instructor:
        lines.append(f'<span class="who">{instructor}</span>')
    if room:
        lines.append(f'<span class="meta">{room}</span>')
    return (f'<div class="{klass}" style="--c:{color}" title="{escape(title)}">'
            f'{"".join(lines)}</div>')


def week_grid_html(schedule: dict, hour_lo: int = 9, hour_hi: int = 21,
                   lang: str = DEFAULT_LANG) -> str:
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
            inner = "".join(_block_html(a, is_start=(int(a.get("start", 0)) == h))
                            for a in blocks)
            cells.append(f"<td>{inner}</td>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return (f'<div class="tt-wrap"><table class="tt"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table></div>')
