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
_ICON_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "assets", "icon.svg")


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
    "--card": "#FFFFFF", "--card-bd": "#E5E9F1",
    "--ink": "#131722", "--ink-2": "#39414F", "--muted": "#5B6472", "--faint": "#9AA3B2",
    "--border": "#E5E9F1", "--border-2": "#EEF1F6",
    "--good": "#0F766E", "--good-bg": "#ECFDF6", "--good-bd": "#A7E3D4",
    "--warn": "#B4490F", "--warn-bg": "#FEF4EE", "--warn-bd": "#F3CBB4",
    "--error": "#C81E1E", "--error-bg": "#FEF2F2", "--error-bd": "#FECACA",
    "--info": "#1F4FB8", "--info-bg": "#EEF3FC", "--info-bd": "#C4D6F4",
    "--font": "'Inter',system-ui,-apple-system,sans-serif",
    "--serif": "'Fraunces',Georgia,'Times New Roman',serif",
    "--mono": "'Geist Mono','SF Mono',Menlo,Consolas,monospace",
    "--sh-1": "0 1px 2px rgba(20,24,38,.05),0 1px 3px rgba(20,24,38,.06)",
    "--sh-2": "0 2px 6px rgba(20,24,38,.06),0 8px 24px -8px rgba(20,24,38,.12)",
    "--sh-3": "0 10px 40px -12px rgba(31,43,103,.28)",
    "--r-sm": "8px", "--r": "12px", "--r-lg": "16px", "--r-xl": "22px",
    "--tt-bg": "#ffffff", "--tt-ink": "#0b1020", "--dz": "#C2CBDC",
    "--appbar-bg": "rgba(255,255,255,.82)", "--stepper-bg": "rgba(244,246,250,.86)",
    "--body-glow": "#E7ECFA",
    "--head-1": "#2B3A8C", "--head-2": "#6D5BD0",
    "--pill-lab-bg": "#F1EEFB", "--pill-lab-bd": "#DAD2F4", "--pill-lab-fg": "#5B4BBE",
}

_DARK_TOKENS = {**_LIGHT_TOKENS, **{
    "--primary": "#7E90EE", "--primary-700": "#5C6FD6",
    "--primary-50": "rgba(126,144,238,.12)", "--primary-100": "rgba(126,144,238,.24)",
    "--canvas": "#0E1220", "--surface": "#161C2C", "--surface-2": "#1B2233",
    "--card": "#1F2740", "--card-bd": "#33405E",
    "--ink": "#EAEEF7", "--ink-2": "#C5CCDD", "--muted": "#8A93A8", "--faint": "#5E6678",
    "--border": "#28314B", "--border-2": "#222A40",
    "--good": "#34D6AA", "--good-bg": "rgba(52,214,170,.13)", "--good-bd": "rgba(52,214,170,.36)",
    "--warn": "#EFA463", "--warn-bg": "rgba(239,164,99,.13)", "--warn-bd": "rgba(239,164,99,.36)",
    "--error": "#F87171", "--error-bg": "rgba(248,113,113,.13)", "--error-bd": "rgba(248,113,113,.36)",
    "--info": "#7E90EE", "--info-bg": "rgba(126,144,238,.12)", "--info-bd": "rgba(126,144,238,.32)",
    "--sh-1": "0 1px 2px rgba(0,0,0,.4)", "--sh-2": "0 6px 22px -8px rgba(0,0,0,.55)",
    "--sh-3": "0 18px 50px -16px rgba(0,0,0,.65)",
    "--tt-bg": "#141A28", "--tt-ink": "#F2F5FC", "--dz": "#39425E",
    "--appbar-bg": "rgba(14,18,32,.72)", "--stepper-bg": "rgba(14,18,32,.78)",
    "--body-glow": "rgba(70,86,170,.30)",
    "--head-1": "#9FB0F5", "--head-2": "#C9B6F5",
    "--pill-lab-bg": "rgba(124,107,222,.18)", "--pill-lab-bd": "rgba(124,107,222,.4)",
    "--pill-lab-fg": "#B7ABF2",
}}

_FONT_IMPORT = ("@import url('https://fonts.googleapis.com/css2?"
                "family=Inter:wght@400;500;600;700;800&"
                "family=Fraunces:opsz,wght@9..144,500;9..144,600&"
                "family=Geist+Mono:wght@400;500;600&display=swap');")

# Hide Streamlit's native chrome so our custom app bar + stepper own the frame.
_HIDE_CHROME = """
header[data-testid="stHeader"]{display:none;}
[data-testid="stToolbar"],#MainMenu,footer{display:none;}
section[data-testid="stSidebar"]{display:none;}
[data-testid="stAppViewContainer"] .block-container{max-width:1160px;padding-top:0;padding-bottom:1rem;}
"""

# Component stylesheet — all rules read CSS variables (theme-neutral).
_COMPONENT_CSS = """
*{box-sizing:border-box;}
html,body,.stApp,p,span,div,label,input,button,select,textarea{font-family:var(--font);color:var(--ink);}
.stApp{background:var(--canvas);background-image:radial-gradient(1200px 480px at 78% -8%, var(--body-glow) 0%, rgba(0,0,0,0) 60%);background-repeat:no-repeat;}
h1,h2,h3,h4{margin:0;letter-spacing:-.018em;font-weight:700;color:var(--ink);}
.tabular,.num,.tt-time,.tt-blk .meta{font-variant-numeric:tabular-nums;}

/* Sticky glass header — frosted bar holding brand + controls + stepper.
   backdrop-filter blurs whatever scrolls behind it; the translucent --appbar-bg
   token keeps text legible in both themes. */
.st-key-topbar{position:sticky;top:0;z-index:50;
  background:var(--appbar-bg);
  -webkit-backdrop-filter:blur(16px) saturate(160%);
  backdrop-filter:blur(16px) saturate(160%);
  border:1px solid var(--border);border-radius:var(--r-lg);
  box-shadow:var(--sh-1);padding:6px 14px 8px;margin-bottom:18px;}
/* Strip Streamlit default gap/padding inside topbar so nothing drifts. */
.st-key-topbar [data-testid="stVerticalBlock"]{gap:0!important;padding:0!important;}
.st-key-topbar [data-testid="stBlock"]{padding:0!important;gap:0!important;}
/* Inside the glass bar the stepper sheds its own surface so it reads as one pane. */
.st-key-topbar .stepper-wrap{background:transparent;border:none;margin:4px 0 0;}

/* App bar (left side: brand) */
.tt-appbar{display:flex;align-items:center;gap:14px;}
.tt-brand{display:flex;align-items:center;gap:11px;font-weight:700;}
.tt-brand .glyph{width:40px;height:40px;border-radius:10px;flex:none;overflow:hidden;box-shadow:var(--sh-1);}
.tt-brand .glyph img{width:100%;height:100%;display:block;border-radius:inherit;}
.tt-brand .name{font-family:var(--serif);font-weight:600;font-size:1.16rem;letter-spacing:-.005em;background:linear-gradient(95deg,var(--head-1) 0%,var(--head-2) 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}
/* Subtitle keeps a solid muted tone (reset the gradient text-fill). */
.tt-brand .name small{display:block;font:500 .68rem/1.1 var(--mono);color:var(--muted);letter-spacing:.02em;background:none;-webkit-text-fill-color:var(--muted);}

/* Step indicator */
.stepper-wrap{background:var(--stepper-bg);border:1px solid var(--border);border-radius:999px;margin:6px 0 18px;}
.stepper{display:flex;align-items:center;gap:4px;padding:5px 8px 15px;flex-wrap:wrap;}
.step{display:flex;align-items:center;gap:9px;padding:7px 13px 7px 8px;border-radius:999px;border:1px solid transparent;text-decoration:none;white-space:nowrap;transition:background .2s ease,border-color .2s ease,box-shadow .2s ease,transform .2s ease;}
.step .idx{width:23px;height:23px;flex:none;border-radius:50%;display:grid;place-items:center;font:700 .74rem/1 var(--mono);color:var(--muted);background:var(--surface);border:1px solid var(--border);transition:background .25s ease,color .25s ease,border-color .25s ease,transform .25s ease;}
.step .lbl{font:600 .82rem/1 var(--font);color:var(--muted);transition:color .25s ease;}
.step:hover{background:var(--surface);transform:translateY(-1px);}
.step:hover .idx{transform:scale(1.06);}
.step.active{background:var(--surface);border-color:var(--primary-100);box-shadow:var(--sh-1);}
.step.active .idx{background:var(--primary);color:#fff;border-color:var(--primary);animation:stepPulse 2.4s ease-in-out infinite;}
.step.active .lbl{color:var(--ink);}
.step.done .idx{background:var(--good-bg);color:var(--good);border-color:var(--good-bd);}
.step.done .lbl{color:var(--ink-2);}
.step.locked{opacity:.45;filter:grayscale(.3);cursor:not-allowed;}
.stp-divider{flex:1;height:2px;border-radius:2px;background:var(--border);margin:0 2px;min-width:8px;overflow:hidden;position:relative;}
.stp-divider.done{background:color-mix(in srgb,var(--primary) 42%,var(--border));}
/* A heartbeat blip travels left→right across each connector; per-divider --d
   delays make it read as one pulse sweeping the whole stepper, then resting. */
.stp-divider::after{content:"";position:absolute;top:0;bottom:0;left:0;width:46%;border-radius:inherit;background:linear-gradient(90deg,transparent,color-mix(in srgb,var(--primary) 92%,transparent),transparent);transform:translateX(-160%);animation:stepSweep 3s ease-in-out var(--d,0s) infinite;}
@keyframes stepPulse{
  0%{box-shadow:0 0 0 0 color-mix(in srgb,var(--primary) 50%,transparent);}
  70%{box-shadow:0 0 0 8px color-mix(in srgb,var(--primary) 0%,transparent);}
  100%{box-shadow:0 0 0 0 color-mix(in srgb,var(--primary) 0%,transparent);}
}
@keyframes stepSweep{
  0%{transform:translateX(-160%);}
  16%{transform:translateX(260%);}
  100%{transform:translateX(260%);}
}
@media (prefers-reduced-motion:reduce){
  .step,.step .idx,.step .lbl{transition:none;}
  .step.active .idx{animation:none;}
  .stp-divider::after{animation:none;display:none;}
}

/* Section headers — Inter, bold + tight (crisp/technical); serif stays brand-only. */
.eyebrow{font-family:var(--font);font-weight:700;font-size:1.5rem;line-height:1.12;letter-spacing:-.02em;text-transform:none;color:var(--primary);display:flex;align-items:center;gap:12px;margin:10px 0 12px;}
.eyebrow .n{display:grid;place-items:center;width:28px;height:28px;border-radius:8px;background:var(--primary-50);color:var(--primary);font:700 .85rem/1 var(--mono);border:1px solid var(--primary-100);flex:none;}
/* Gradient-toned label */
.eyebrow .lbl{background:linear-gradient(95deg,var(--head-1) 0%,var(--head-2) 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}
/* Permalink anchor — restores the per-section link, revealed on hover. */
.eyebrow .anchor{display:inline-flex;align-items:center;color:var(--faint);opacity:0;transition:opacity .15s,color .15s;text-decoration:none;}
.eyebrow:hover .anchor{opacity:.65;}
.eyebrow .anchor:hover{opacity:1;color:var(--primary);}
.eyebrow .anchor svg{width:17px;height:17px;}

/* Hero */
.tt-hero{position:relative;overflow:hidden;border-radius:var(--r-xl);margin:4px 0 22px;padding:34px 38px;color:#fff;background:radial-gradient(680px 320px at 88% -30%, #5C6CC6 0%, rgba(92,108,198,0) 62%),linear-gradient(135deg,#233178 0%,#2B3A8C 46%,#1C2766 100%);box-shadow:var(--sh-3);}
.tt-hero h1{font-size:2.3rem;line-height:1.07;font-weight:800;max-width:18ch;margin:0;
  background:linear-gradient(115deg,#FFFFFF 0%,#EAEEFF 42%,#C2CCF6 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}
.tt-hero h1 em{font-style:normal;
  background:linear-gradient(115deg,#CBD4FB 0%,#AEB6F2 46%,#CBA8F1 100%);
  -webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}
.tt-hero p{position:relative;color:#C9D1EE;max-width:54ch;margin:13px 0 0;font-size:1.0rem;}
.tt-hero .row{position:relative;display:flex;gap:10px;margin-top:20px;flex-wrap:wrap;}
.chip-stat{display:flex;flex-direction:column;gap:3px;padding:10px 15px;border-radius:var(--r);background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.14);}
.chip-stat .v{font:800 1.12rem/1 var(--font);color:#fff;}
.chip-stat .l{font:600 .62rem/1 var(--mono);letter-spacing:.1em;text-transform:uppercase;color:#AEBBF0;}
.chip-stat.good{background:rgba(52,211,153,.14);border-color:rgba(52,211,153,.32);}
.chip-stat.good .v{color:#6EE7B7;}
.chip-stat.bad{background:rgba(248,113,113,.14);border-color:rgba(248,113,113,.34);}
.chip-stat.bad .v{color:#FCA5A5;}

/* KPI chips */
.chips{display:flex;flex-wrap:wrap;gap:11px;margin-bottom:14px;}
.kpi{flex:1;min-width:150px;background:var(--card);border:1px solid var(--card-bd);border-radius:var(--r);padding:14px 16px;box-shadow:var(--sh-1);position:relative;overflow:hidden;}
.kpi::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--primary);opacity:.55;}
.kpi.good::before{background:var(--good);}.kpi.warn::before{background:var(--warn);}
.kpi .v{font:800 1.6rem/1 var(--font);letter-spacing:-.02em;}
.kpi.good .v{color:var(--good);}.kpi.warn .v{color:var(--warn);}
.kpi .l{font:600 .66rem/1 var(--mono);letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin-top:8px;}

/* Metric cards (results) — same visual language as .kpi chips */
.tt-cards{display:flex;flex-wrap:wrap;gap:11px;margin:6px 0 18px;}
.tt-card{flex:1;min-width:150px;background:var(--card);border:1px solid var(--card-bd);border-radius:var(--r);padding:14px 16px;box-shadow:var(--sh-1);position:relative;overflow:hidden;transition:box-shadow .2s,transform .2s;}
.tt-card:hover{box-shadow:var(--sh-2);transform:translateY(-2px);}
.tt-card::before{content:"";position:absolute;left:0;top:0;bottom:0;width:3px;background:var(--primary);opacity:.55;}
.tt-card.good::before{background:var(--good);}.tt-card.bad::before{background:var(--warn);}.tt-card.brand::before{background:var(--primary);}
.tt-card .v{font:800 1.6rem/1 var(--font);letter-spacing:-.02em;color:var(--ink);}
.tt-card .l{font:600 .66rem/1 var(--mono);text-transform:uppercase;letter-spacing:.08em;color:var(--muted);margin-top:8px;}
.tt-card.good .v{color:var(--good);}.tt-card.bad .v{color:var(--warn);}.tt-card.brand .v{color:var(--primary);}

/* Pills */
.pill{display:inline-block;font:600 .68rem/1 var(--mono);padding:4px 8px;border-radius:6px;background:var(--surface-2);border:1px solid var(--border);color:var(--ink-2);}
.pill.lab{background:var(--pill-lab-bg);border-color:var(--pill-lab-bd);color:var(--pill-lab-fg);}
.pill.online{background:var(--good-bg);border-color:var(--good-bd);color:var(--good);}

/* Timetable grid — the signature element */
.tt-wrap{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;background:var(--surface);box-shadow:var(--sh-1);}
.tt-scroll{overflow-x:auto;-webkit-overflow-scrolling:touch;}
table.tt{border-collapse:collapse;width:100%;min-width:480px;table-layout:fixed;}
table.tt th{background:var(--surface-2);color:var(--muted);font:600 .68rem/1 var(--mono);text-transform:uppercase;letter-spacing:.07em;padding:12px 8px;border-bottom:1px solid var(--border);}
table.tt th.tt-time,table.tt td.tt-time{width:62px;}
table.tt td{border-bottom:1px solid var(--border-2);border-left:1px solid var(--border-2);vertical-align:top;height:32px;padding:3px;}
td.tt-time{color:var(--faint);font:500 .72rem/32px var(--mono);text-align:center;background:var(--surface-2);}
.tt-blk{border-radius:7px;padding:5px 9px;margin:1px 0;background:color-mix(in srgb, var(--c) 13%, var(--tt-bg));border-left:3px solid var(--c);color:color-mix(in srgb, var(--c) 70%, var(--tt-ink));box-shadow:0 1px 2px rgba(20,24,38,.04);transition:.15s;}
.tt-blk:hover{transform:translateY(-1px);box-shadow:var(--sh-1);}
.tt-blk.cont{border-radius:0 0 7px 7px;border-top:1px dashed color-mix(in srgb,var(--c) 40%,transparent);}

.tt-blk .code{font:600 .76rem/1.15 var(--font);display:block;}
.tt-blk .who{font:500 .66rem/1.25 var(--font);display:block;margin-top:2px;opacity:.85;}
.tt-blk .meta{font:500 .64rem/1.2 var(--mono);opacity:.72;display:block;margin-top:1px;}
.tt-blk .tag{font:600 .52rem/1 var(--mono);letter-spacing:.04em;border:1px solid currentColor;border-radius:4px;padding:1px 4px;margin-left:6px;vertical-align:1px;}
.tt-empty{color:var(--faint);font:500 .9rem/1 var(--font);padding:24px;text-align:center;}

/* Read-only data table (uploaded courselist / room inventory previews). Our own
   HTML/CSS so it follows the in-app light/dark theme — st.dataframe's glide grid
   paints its canvas from Streamlit's *native* (light) theme and can't be
   re-themed via CSS. Header sticks; the wrapper scrolls internally (both axes)
   so a wide table stays contained on a phone in portrait. */
.tt-table-wrap{border:1px solid var(--border);border-radius:var(--r-lg);overflow:auto;max-width:100%;max-height:var(--tt-table-h,340px);background:var(--surface);box-shadow:var(--sh-1);-webkit-overflow-scrolling:touch;}
table.tt-data{border-collapse:collapse;width:100%;font:500 .82rem/1.45 var(--font);color:var(--ink-2);}
table.tt-data thead th{position:sticky;top:0;z-index:1;background:var(--surface-2);color:var(--muted);font:600 .66rem/1 var(--mono);text-transform:uppercase;letter-spacing:.06em;text-align:left;padding:11px 14px;border-bottom:1px solid var(--border);white-space:nowrap;}
table.tt-data tbody td{padding:9px 14px;border-bottom:1px solid var(--border-2);white-space:nowrap;}
table.tt-data th.num,table.tt-data td.num{text-align:right;font-variant-numeric:tabular-nums;}
table.tt-data tbody tr:nth-child(even){background:var(--surface-2);}
table.tt-data tbody tr:hover{background:var(--primary-50);}
table.tt-data tbody tr:last-child td{border-bottom:none;}
td.tt-td-empty{color:var(--faint);text-align:center;padding:20px;}
.cr-edit-head{font:600 .92rem/1.3 var(--font);color:var(--ink-2);margin:20px 0 8px;}

/* CSV import preview (VERA-style): detected-column chips, stat badges, status pills */
.imp-detect{display:flex;flex-wrap:wrap;gap:6px;align-items:center;margin:4px 0 12px;font:600 .66rem/1 var(--mono);}
.imp-detect .lbl{color:var(--muted);text-transform:uppercase;letter-spacing:.06em;}
.imp-detect .col{background:var(--surface-2);border:1px solid var(--border);border-radius:6px;padding:4px 8px;color:var(--ink-2);}
.imp-detect .col em{font-style:normal;color:var(--faint);}
.imp-detect .col.pos{border-style:dashed;color:var(--muted);}
.imp-stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;}
.imp-badge{display:inline-flex;align-items:baseline;gap:5px;border-radius:8px;padding:5px 11px;font:600 .72rem/1 var(--font);border:1px solid var(--border);background:var(--surface-2);color:var(--ink-2);}
.imp-badge .n{font:800 .9rem/1 var(--font);font-variant-numeric:tabular-nums;}
.imp-badge.good{background:var(--good-bg);border-color:var(--good-bd);color:var(--good);}
.imp-badge.warn{background:var(--warn-bg);border-color:var(--warn-bd);color:var(--warn);}
.imp-badge.bad{background:var(--error-bg);border-color:var(--error-bd);color:var(--error);}
.tt-data tr.row-dup{background:var(--warn-bg);}
.tt-data tr.row-err{background:var(--error-bg);}
.st-pill{display:inline-block;font:600 .64rem/1 var(--mono);padding:4px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface-2);color:var(--muted);white-space:nowrap;}
.st-pill.ok{background:var(--good-bg);border-color:var(--good-bd);color:var(--good);}
.st-pill.duplicate{background:var(--warn-bg);border-color:var(--warn-bd);color:var(--warn);}
.st-pill.error{background:var(--error-bg);border-color:var(--error-bd);color:var(--error);}

/* Solve "loading button" — replaces the real Streamlit button while solver runs
   so the spinner text appears in the same visual slot as the button. */
.solve-running{display:flex;align-items:center;justify-content:center;gap:10px;
  padding:.55rem 1rem;min-height:42px;border-radius:10px;
  background:radial-gradient(ellipse at 80% -20%,#7080D8 0%,rgba(112,128,216,0) 60%),
             linear-gradient(135deg,#3A4EA0 0%,#2F42A0 46%,#233178 100%);
  color:#fff;font:600 .9rem/1 var(--font);border:1px solid #2B3A8C;
  box-shadow:0 1px 2px rgba(31,43,103,.3),0 6px 18px -8px rgba(31,43,103,.5);
  opacity:.9;cursor:wait;}
.solve-spin{width:16px;height:16px;border:2.5px solid rgba(255,255,255,.35);
  border-top-color:#fff;border-radius:50%;flex:none;
  animation:solveSpin .7s linear infinite;}
@keyframes solveSpin{to{transform:rotate(360deg);}}
/* Solve button — centred, auto-width, shimmer on load; CSS SVG wand casts on click.
   SVG wand: stick (white line, bottom-left→top-right) + gold handle knob + gold 5-pt star at tip.
   transform-origin matches handle position (5/24≈21%, 19/24≈79%) so tip swings on rotate. */
.st-key-solve_btn{display:flex;justify-content:center;}
.st-key-solve_btn button{position:relative;overflow:hidden;padding:12px 40px!important;display:inline-flex!important;align-items:center;justify-content:center;gap:7px;}
.st-key-solve_btn button::before{content:"";display:inline-block;flex:none;width:20px;height:20px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cline x1='19' y1='5' x2='5' y2='19' stroke='white' stroke-width='2.5' stroke-linecap='round'/%3E%3Ccircle cx='5' cy='19' r='2.2' fill='%23B8860B'/%3E%3Cpolygon points='19,1.5 19.9,3.7 22.3,3.9 20.5,5.5 21.1,7.8 19,6.6 16.9,7.8 17.5,5.5 15.7,3.9 18.1,3.7' fill='%23FFD700'/%3E%3C/svg%3E") center/contain no-repeat;transform-origin:21% 79%;}
.st-key-solve_btn button::after{content:"";position:absolute;top:-50%;left:-80%;width:45%;height:200%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.26),transparent);transform:skewX(-12deg);animation:wandShimmer 1.6s ease-in-out 0.1s 3;}
.st-key-solve_btn button.wand-casting::before{animation:wandCast 0.5s ease-in-out;}
@keyframes wandShimmer{0%{left:-80%}100%{left:140%}}
@keyframes wandCast{0%{transform:rotate(0deg)}20%{transform:rotate(-22deg)}55%{transform:rotate(15deg)}80%{transform:rotate(-5deg)}100%{transform:rotate(0deg)}}

/* Expander — default Streamlit expander renders a white card in dark mode;
   repaint surface, border and label to match the theme. */
[data-testid="stExpander"] details{
  background:var(--surface)!important;border:1px solid var(--border)!important;
  border-radius:var(--r)!important;}
[data-testid="stExpander"] summary{
  color:var(--ink)!important;background:transparent!important;}
[data-testid="stExpander"] summary:hover{background:var(--surface-2)!important;}
[data-testid="stExpander"] summary svg{fill:var(--muted)!important;}
[data-testid="stExpander"] summary *{color:var(--ink)!important;}
[data-testid="stExpanderDetails"]{background:var(--surface)!important;}

/* Streamlit widget integration */
.stButton>button[kind="primary"],.stButton>button[data-testid="stBaseButton-primary"]{background:radial-gradient(ellipse at 80% -20%,#7080D8 0%,rgba(112,128,216,0) 60%),linear-gradient(135deg,#3A4EA0 0%,#2F42A0 46%,#233178 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #2B3A8C!important;border-radius:10px;font-weight:600;box-shadow:0 1px 2px rgba(31,43,103,.3),0 6px 18px -8px rgba(31,43,103,.5);}
.stButton>button[kind="primary"] p,.stButton>button[data-testid="stBaseButton-primary"] p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.stButton>button[kind="primary"]:hover,.stButton>button[data-testid="stBaseButton-primary"]:hover{filter:brightness(1.06);color:#fff!important;-webkit-text-fill-color:#fff!important;border-color:var(--primary)!important;}
.stButton>button[kind="primary"]:hover p,.stButton>button[data-testid="stBaseButton-primary"]:hover p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
/* Secondary + download buttons — explicit surface bg + ink text so they read on both themes (!important beats Streamlit's base theme) */
.stButton>button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]),.stDownloadButton>button{background:var(--surface)!important;color:var(--ink)!important;border:1px solid var(--border)!important;border-radius:10px;font-weight:500;}
.stDownloadButton>button p{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
.stButton>button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):hover,.stDownloadButton>button:hover{background:var(--surface-2)!important;border:2px solid var(--primary)!important;color:var(--primary)!important;box-shadow:none!important;}
/* Premium download buttons — JSON (indigo) + CSV (emerald).
   st-key-* lives on the PARENT of stDownloadButton, so selectors use the ancestor pattern:
   .st-key-X [data-testid="stDownloadButton"] button — specificity (0,3,1) > generic (0,2,1). */
.st-key-dl_json [data-testid="stDownloadButton"] button,
.st-key-dl_json [data-testid="stBaseButton-secondary"]{background:linear-gradient(135deg,#3A4EA0 0%,#2F42A0 46%,#233178 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #2B3A8C!important;border-radius:12px!important;font-weight:600!important;letter-spacing:.01em;padding:12px 20px!important;box-shadow:0 1px 3px rgba(31,43,103,.35),0 6px 18px -8px rgba(31,43,103,.55)!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button p,
.st-key-dl_json [data-testid="stBaseButton-secondary"] p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button:hover{background:linear-gradient(135deg,#4A5EB0 0%,#3F52B0 46%,#334188 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #2B3A8C!important;box-shadow:0 4px 14px -4px rgba(31,43,103,.6)!important;transform:translateY(-1px)!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button:hover p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button,
.st-key-dl_csv [data-testid="stBaseButton-secondary"]{background:linear-gradient(135deg,#1A7A42 0%,#186C3A 46%,#115530 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #166235!important;border-radius:12px!important;font-weight:600!important;letter-spacing:.01em;padding:12px 20px!important;box-shadow:0 1px 3px rgba(17,85,48,.35),0 6px 18px -8px rgba(17,85,48,.55)!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button p,
.st-key-dl_csv [data-testid="stBaseButton-secondary"] p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button:hover{background:linear-gradient(135deg,#2A8A52 0%,#267C4A 46%,#195C38 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #166235!important;box-shadow:0 4px 14px -4px rgba(17,85,48,.6)!important;transform:translateY(-1px)!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button:hover p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
/* Theme toggle (☀️/🌙) — icon button that follows the surface, not a glaring white box in dark */
.st-key-theme_btn button{background:var(--surface-2)!important;border:1px solid var(--border)!important;color:var(--ink)!important;border-radius:10px;padding:8px 0;width:100%;}
.st-key-theme_btn button:hover{background:var(--surface)!important;border-color:var(--primary)!important;}
/* ── Upload dropzone card ── premium animated dropzone.
   Rest: dashed border + soft shadow, a glow breathing behind the icon, the
   upload arrow rising out of its tray. Hover/drag (the moment that matters):
   the card lifts and a gradient comet sweeps the perimeter to say "drop here". */
@property --dz-ang{syntax:"<angle>";initial-value:0deg;inherits:false;}
.st-key-upload_card{position:relative;border:1.8px dashed var(--primary);border-radius:var(--r-xl);background:var(--surface);text-align:center;padding-bottom:28px;margin:4px 0 6px;box-shadow:var(--sh-1);transition:transform .3s ease,box-shadow .3s ease,border-color .3s ease;animation:dzEnter .55s cubic-bezier(.22,1,.36,1) both;}
.st-key-upload_card>[data-testid="stVerticalBlock"]{gap:0!important;position:relative;z-index:1;}
/* Gradient comet ring — masked to a 2px outline, revealed + spun on hover. */
.st-key-upload_card::after{content:"";position:absolute;inset:-2px;border-radius:inherit;padding:2px;pointer-events:none;opacity:0;transition:opacity .35s ease;
  background:conic-gradient(from var(--dz-ang),transparent 0deg,var(--primary) 55deg,var(--head-2) 110deg,transparent 175deg,transparent 360deg);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;
  animation:dzSpin 3.4s linear infinite;}
.st-key-upload_card:hover{transform:translateY(-2px);box-shadow:var(--sh-2);border-color:var(--primary-700);}
.st-key-upload_card:hover::after{opacity:1;}
/* Header is purely visual; let clicks fall through to the invisible file-input
   overlay above it so tapping the icon / title opens the browse dialog. */
.dz-header{padding:40px 32px 16px;display:flex;flex-direction:column;align-items:center;gap:10px;pointer-events:none;}
.dz-iconwrap{position:relative;width:54px;height:54px;display:grid;place-items:center;}
.dz-glow{position:absolute;width:84px;height:84px;border-radius:50%;z-index:0;pointer-events:none;
  background:radial-gradient(circle,color-mix(in srgb,var(--primary) 36%,transparent) 0%,transparent 68%);
  animation:dzPulse 3s ease-in-out infinite;}
.dz-icon{position:relative;z-index:1;width:54px;height:54px;border-radius:14px;background:var(--surface-2);border:1px solid var(--border);display:grid;place-items:center;color:var(--primary);box-shadow:var(--sh-1);transition:transform .3s ease,border-color .3s ease,box-shadow .3s ease;}
.dz-icon>svg,.dz-icon .dz-arrow{grid-area:1/1;}
.dz-icon>svg{width:26px;height:26px;}
.dz-icon .dz-arrow{display:grid;place-items:center;color:var(--primary);animation:dzArrow 2.2s ease-in-out infinite;}
.dz-icon .dz-arrow svg{width:26px;height:26px;}
.st-key-upload_card:hover .dz-icon{transform:scale(1.08) translateY(-2px);border-color:var(--primary);box-shadow:var(--sh-2);}
.dz-title{font:700 1.08rem/1.2 var(--font);color:var(--ink);margin:0;transition:color .3s ease;}
.st-key-upload_card:hover .dz-title{color:var(--primary);}
.dz-sub{font:500 .85rem/1.4 var(--font);color:var(--muted);margin:0;}
@keyframes dzEnter{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes dzSpin{to{--dz-ang:360deg;}}
@keyframes dzPulse{0%,100%{transform:scale(.8);opacity:.5;}50%{transform:scale(1.15);opacity:.9;}}
@keyframes dzArrow{0%,100%{transform:translateY(2px);opacity:.45;}50%{transform:translateY(-3px);opacity:1;}}
@media (prefers-reduced-motion:reduce){
  .st-key-upload_card,.dz-glow,.dz-icon .dz-arrow{animation:none;}
  .st-key-upload_card::after{animation:none;}
}
/* Overlay the dz-header with a transparent clickable file input */
.st-key-upload_card [data-testid="stFileUploader"]{position:absolute;top:0;left:0;right:0;height:175px;z-index:5;padding:0!important;margin:0!important;}
.st-key-upload_card [data-testid="stFileUploaderDropzone"]{position:absolute;inset:0;background:transparent!important;border:none!important;box-shadow:none!important;padding:0!important;cursor:pointer;}
.st-key-upload_card [data-testid="stFileUploaderDropzone"] *:not(button){display:none!important;}
.st-key-upload_card [data-testid="stFileUploaderDropzone"] button{display:block!important;position:absolute!important;inset:0!important;width:100%!important;height:100%!important;opacity:0!important;cursor:pointer!important;border:none!important;background:transparent!important;}
.st-key-upload_card [data-testid="stFileUploaderFile"]{display:none!important;}
.st-key-upload_card [data-testid="stHorizontalBlock"]{padding:0 20px!important;justify-content:center!important;}
.st-key-upload_card [data-testid="column"]{padding:0!important;}
/* Upload success / error state */
@keyframes uploadPop{0%{opacity:0;transform:scale(.6);}65%{transform:scale(1.12);}100%{opacity:1;transform:scale(1);}}
@keyframes uploadRise{0%{opacity:0;transform:translateY(10px);}100%{opacity:1;transform:translateY(0);}}
.upload-ok{display:flex;flex-direction:column;align-items:center;gap:6px;padding:20px 0 8px;}
.upload-ok .chk{width:52px;height:52px;border-radius:50%;background:var(--good-bg);border:2px solid var(--good-bd);display:grid;place-items:center;color:var(--good);animation:uploadPop .45s cubic-bezier(.34,1.56,.64,1) both;}
.upload-ok .chk svg{width:26px;height:26px;}
.upload-ok .ok-title{font:700 .98rem/1.2 var(--font);color:var(--good);margin:0;animation:uploadRise .3s .25s ease both;}
.upload-ok .ok-sub{font:500 .8rem/1.4 var(--font);color:var(--muted);margin:0;animation:uploadRise .3s .35s ease both;}
.upload-err{display:flex;flex-direction:column;align-items:center;gap:6px;padding:20px 16px 14px;background:var(--error-bg);border:1px solid var(--error-bd);border-radius:var(--r);margin:8px 0;}
.upload-err .err-icon{width:52px;height:52px;border-radius:50%;background:var(--error-bg);border:2px solid var(--error-bd);display:grid;place-items:center;color:var(--error);animation:uploadPop .45s cubic-bezier(.34,1.56,.64,1) both;}
.upload-err .err-icon svg{width:26px;height:26px;}
.upload-err .err-title{font:700 .98rem/1.2 var(--font);color:var(--error);margin:0;text-align:center;animation:uploadRise .3s .25s ease both;}
.upload-err .err-detail{font:400 .78rem/1.5 var(--mono);color:var(--error);background:var(--error-bd);border-radius:var(--r-sm);padding:6px 12px;margin:4px 0 0;max-width:100%;word-break:break-all;text-align:center;animation:uploadRise .3s .3s ease both;}
.upload-err .err-hint{font:400 .8rem/1.4 var(--font);color:var(--muted);margin:0;text-align:center;animation:uploadRise .3s .38s ease both;}
/* Invalid file type: red icon + text for the rejected-file row. Exclude the
   dropzone itself (it is ALSO a <section>) so the empty zone stays transparent
   — otherwise the error bg out-specifies the dropzone rule and paints it red. */
.st-key-upload_card [data-testid="stFileUploader"] section:not([data-testid="stFileUploaderDropzone"]){background:var(--error-bg)!important;border:1px solid var(--error-bd)!important;border-radius:var(--r-sm)!important;margin:4px 12px!important;}
.st-key-upload_card [data-testid="stFileUploader"] section:not([data-testid="stFileUploaderDropzone"]) svg{color:var(--error)!important;fill:var(--error)!important;}
.st-key-upload_card [data-testid="stFileUploader"] section:not([data-testid="stFileUploaderDropzone"]) small{color:var(--error)!important;}
.st-key-upload_card [data-testid="stFileUploaderDeleteBtn"]{color:var(--error)!important;opacity:.75;}
.st-key-upload_card [data-testid="stFileUploaderDeleteBtn"]:hover{opacity:1;}
/* "Try with sample dataset" — auto-width (fits its label), centered in the card;
   the primary gradient already applies. A light sheen sweeps across on hover so
   the call-to-action feels alive. */
.st-key-load_sample,.st-key-load_sample .stButton{display:flex;justify-content:center;width:100%;}
.st-key-load_sample button{position:relative;overflow:hidden;width:auto!important;padding:12px 40px!important;}
.st-key-load_sample button::after{content:"";position:absolute;top:0;left:-130%;width:60%;height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.28),transparent);transform:skewX(-18deg);transition:left .6s ease;}
.st-key-load_sample button:hover::after{left:150%;}
@media (prefers-reduced-motion:reduce){.st-key-load_sample button::after{transition:none;}}
/* Fallback: plain dropzone (outside upload card) keeps the default look */
[data-testid="stFileUploaderDropzone"]{background:var(--surface-2);border:1.6px dashed var(--dz);border-radius:var(--r-lg);}
[data-testid="stFileUploaderDropzone"]:hover{border-color:var(--primary);}
[data-testid="stFileUploaderDropzone"] *{color:var(--ink)!important;}
[data-testid="stFileUploaderDropzone"] button{background:var(--surface)!important;color:var(--ink)!important;border:1px solid var(--border)!important;border-radius:10px;font-weight:600!important;}
[data-testid="stFileUploaderDropzone"] button:hover{background:var(--surface-2)!important;border-color:var(--primary)!important;color:var(--primary)!important;}
/* Glide data grid (st.dataframe / st.data_editor) is themed in brand_css() with
   LITERAL token values (not var() indirection): the grid canvas reads its
   --gdg-* custom properties at paint time and does not resolve nested var()
   references, so dark mode only takes when the hexes are inlined per theme. */
[data-testid="stDataFrame"],[data-testid="stDataEditor"]{border:1px solid var(--border);border-radius:var(--r-lg);overflow:hidden;}

/* Text / number / select inputs — DOM (BaseWeb) widgets, so unlike the glide
   canvas they DO follow CSS. Paint their surfaces with the theme tokens. In
   light mode the token values equal Streamlit's native light colors, so this is
   a no-op there and only takes visible effect in dark. */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"],
[data-testid="stTextInput"] [data-baseweb="base-input"],
[data-testid="stNumberInput"] [data-baseweb="base-input"]{
  background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important;}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{
  background:transparent!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-testid="stTextInput"] input::placeholder,[data-testid="stNumberInput"] input::placeholder{color:var(--faint)!important;}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within,
[data-testid="stNumberInput"] [data-baseweb="input"]:focus-within{
  border-color:var(--primary)!important;box-shadow:0 0 0 3px var(--primary-50)!important;}
[data-testid="stNumberInput"] button{background:var(--surface-2)!important;color:var(--ink-2)!important;border-color:var(--border)!important;}
[data-testid="stNumberInput"] button:hover{background:var(--surface)!important;color:var(--primary)!important;}
/* Selectbox closed control + its caret. */
[data-testid="stSelectbox"] [data-baseweb="select"]>div:first-child{
  background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:10px!important;color:var(--ink)!important;}
[data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-value-container"] *{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-testid="stSelectbox"] [data-baseweb="select"] svg{fill:var(--muted)!important;}
/* Selectbox open menu — themed in brand_css() via _popover_css() with literal
   token values so the portal dropdown is always readable in dark mode. */
/* Checkbox label + box border follow the theme; the tick uses the brand primary. */
[data-testid="stCheckbox"] label,[data-testid="stCheckbox"] label *{color:var(--ink)!important;}
[data-testid="stCheckbox"] [data-baseweb="checkbox"]>span:first-of-type{border-color:var(--border)!important;}

/* Misc Streamlit chrome that should follow the theme */
hr{border-color:var(--border) !important;}
[data-testid="stWidgetLabel"] p,[data-testid="stCaptionContainer"],.stRadio label{color:var(--ink);}
[data-testid="stCaptionContainer"] code{font:600 .9rem/1.55 var(--mono);color:var(--ink-2);background:none;padding:0;}
[data-baseweb="slider"] [role="slider"]{background:var(--primary) !important;}
[data-testid="stAlert"]{border-radius:var(--r);}

/* ── Premium language switch (st.segmented_control: 🇹🇷 TR | 🇬🇧 EN) ── */
/* Track: frameless — just hosts the two round flag buttons, like the theme toggle. */
[data-testid="stButtonGroup"]{
  display:inline-flex;width:auto;align-items:center;
  gap:8px;padding:0;border:0;background:transparent;box-shadow:none;}
[data-testid="stButtonGroup"]>div{display:inline-flex;align-items:center;gap:4px;}
/* Segments: round 32px buttons matching the theme toggle; flag emoji is the label. */
[data-testid="stBaseButton-segmented_control"],
[data-testid="stBaseButton-segmented_controlActive"]{
  border:1px solid var(--border)!important;background:var(--surface-2)!important;
  box-shadow:var(--sh-1)!important;
  border-radius:50%!important;width:32px!important;height:32px!important;
  min-width:32px!important;min-height:32px!important;padding:0!important;flex:none;
  display:inline-flex!important;align-items:center;justify-content:center;
  font:600 1rem/1 var(--font)!important;color:var(--muted)!important;
  transition:background .16s,color .16s,box-shadow .16s,transform .16s;}
[data-testid="stBaseButton-segmented_control"] p,
[data-testid="stBaseButton-segmented_controlActive"] p{
  font:inherit!important;color:inherit!important;letter-spacing:-.005em;}
/* Inactive hover — lift toward the surface without committing. */
[data-testid="stBaseButton-segmented_control"]:hover{
  background:var(--surface)!important;color:var(--primary)!important;
  border-color:var(--primary)!important;box-shadow:var(--sh-2)!important;
  transform:translateY(-1px);}
/* Active segment — primary gradient, white text, soft lift. */
[data-testid="stBaseButton-segmented_controlActive"]{
  background:linear-gradient(135deg,var(--primary) 0%,#4456B5 100%)!important;
  color:#fff!important;border-color:transparent!important;
  box-shadow:0 1px 2px rgba(31,43,103,.28),0 4px 12px -6px rgba(31,43,103,.5),
    inset 0 1px 0 rgba(255,255,255,.22)!important;}
[data-testid="stBaseButton-segmented_controlActive"]:hover{filter:brightness(1.05);}

/* ── Right control group: theme button + lang switch on one tight row ──
   Flip the container's vertical block to a right-aligned horizontal flex.
   Cover both self and descendant stVerticalBlock targets. Strip all default
   Streamlit padding/margin so controls sit flush. */
.st-key-topctrls,
.st-key-topctrls[data-testid="stVerticalBlock"],
.st-key-topctrls [data-testid="stVerticalBlock"]{
  flex-direction:row!important;align-items:center!important;
  justify-content:flex-end!important;gap:8px!important;
  padding:0!important;margin:0!important;}
/* Let flex align-items:center on the column do the vertical centring; no manual
   nudge, so the 32px control buttons line up with the 40px-logo brand row. */
.st-key-topctrls{margin-top:0!important;}
.st-key-topctrls [data-testid="stElementContainer"]{
  width:auto!important;padding:0!important;margin:0!important;}
/* Right column direct-child stVerticalBlock (A): center the topctrls block
   vertically within it. Use > (direct child) so we don't override the inner
   flex-row stVerticalBlock (C) that holds the buttons side by side. */
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]>[data-testid="stVerticalBlock"]{
  padding:0!important;margin:0!important;justify-content:center!important;}

/* App-bar columns: keep brand + controls on ONE vertically-centered row at every
   width. Pin to nowrap + center so neither column ever stack-wraps or drifts. */
.st-key-topbar [data-testid="stHorizontalBlock"]{
  flex-wrap:nowrap!important;align-items:center!important;gap:10px;}
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]{
  width:auto!important;min-width:0!important;padding:0!important;}
/* Zero element-container padding in the brand row so Kairos aligns with the buttons. */
.st-key-topbar [data-testid="stHorizontalBlock"] [data-testid="stElementContainer"]{
  padding:0!important;margin:0!important;}
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child{
  flex:1 1 auto!important;display:flex!important;align-items:center!important;
  align-self:stretch!important;}
/* Streamlit collapses the brand's markdown/element wrappers to a ~12px line box
   even though the brand glyph is 28–40px, so as block children the brand
   top-aligns and its mid-line drifts BELOW the control buttons. Stretch the
   column to the full row height, force each inner wrapper to fill it, and
   flex-centre — so the brand's mid-line lands on the row centre = the buttons. */
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child>[data-testid="stVerticalBlock"],
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child [data-testid="stElementContainer"],
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child [data-testid="stMarkdown"],
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child [data-testid="stMarkdownContainer"]{
  display:flex!important;align-items:center!important;height:100%!important;}
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:last-child{
  flex:0 0 auto!important;display:flex!important;align-items:center!important;
  justify-content:flex-end!important;}

/* Theme + language toggles — identical premium round icon buttons. Both are
   st.button (the lang switch shows the OTHER language's flag and toggles on
   click, like the theme toggle). Scoped to their widget keys so other
   secondary buttons keep their own style. */
.st-key-theme_btn button,
.st-key-lang_btn button{
  width:32px!important;height:32px!important;min-width:32px!important;min-height:32px!important;
  padding:0!important;border-radius:50%!important;flex:none;
  display:inline-flex!important;align-items:center;justify-content:center;
  font-size:1rem;line-height:1;
  background:var(--surface-2)!important;border:1px solid var(--border)!important;
  color:var(--ink-2)!important;box-shadow:var(--sh-1)!important;
  transition:border-color .16s,color .16s,box-shadow .16s,transform .16s;}
.st-key-theme_btn button:hover,
.st-key-lang_btn button:hover{
  border-color:var(--primary)!important;color:var(--primary)!important;
  box-shadow:var(--sh-2)!important;transform:translateY(-1px);}

/* Tooltips (button help, widget hints) — default to a light bubble that is
   unreadable in dark mode; repaint to theme tokens so both modes are legible. */
[data-baseweb="tooltip"]>div,
[data-testid="stTooltipContent"]{
  background:var(--tt-bg)!important;color:var(--tt-ink)!important;
  border:1px solid var(--border)!important;border-radius:var(--r-sm)!important;
  box-shadow:var(--sh-2)!important;
  font:500 .78rem/1.35 var(--font)!important;padding:7px 11px!important;}
[data-baseweb="tooltip"] [data-testid="stTooltipContent"],
[data-baseweb="tooltip"] [data-testid="stTooltipContent"] *{
  color:var(--tt-ink)!important;background:transparent!important;}

/* ── Mobile portrait ── Streamlit stacks the [7,2] app-bar columns full-width
   on narrow screens; tune the brand, context pill, control group and hero so
   nothing overflows or crowds. */
@media (max-width:640px){
  [data-testid="stAppViewContainer"] .block-container{
    padding-left:.85rem;padding-right:.85rem;padding-top:0;}
  /* Glass header: drop sticky + blur on phones (costly); keep translucent frame. */
  .st-key-topbar{position:static;-webkit-backdrop-filter:none;backdrop-filter:none;
    padding:8px 12px 6px;margin-bottom:12px;}
  /* Ensure brand + controls stay on ONE row even on narrow phones. */
  .st-key-topbar [data-testid="stHorizontalBlock"]{
    display:flex!important;flex-wrap:nowrap!important;
    align-items:center!important;gap:8px!important;}
  .tt-brand .name{font-size:1.05rem;}
  .tt-brand .glyph{width:28px;height:28px;border-radius:8px;}
  /* Step indicator → full row, horizontally scrollable, mockup-style.
     Numbers + labels stay visible; connectors collapse to 1px lines.
     Active step keeps its highlighted pill. */
  .stepper-wrap{border-radius:0;border-left:none;border-right:none;margin:4px -4px 14px;}
  .stepper{gap:0;padding:7px 10px 18px;flex-wrap:nowrap;overflow-x:auto;-webkit-overflow-scrolling:touch;scrollbar-width:none;}
  .stepper::-webkit-scrollbar{display:none;}
  .stp-divider{height:1px;min-width:14px;flex:1;animation:none;}
  .stp-divider::after{display:none;}
  .step{gap:7px;padding:6px 10px 6px 7px;white-space:nowrap;}
  .step:hover{transform:none;}
  .step .lbl{font-size:.78rem;}
  .step .idx{width:21px;height:21px;font-size:.7rem;}
  .step.active .idx{animation:none;}
  /* Hero: smaller padding + type so the gradient title fits the viewport. */
  .tt-hero{padding:24px 20px;border-radius:var(--r-lg);margin-bottom:16px;}
  .tt-hero h1{font-size:1.72rem;max-width:none;}
  .tt-hero p{font-size:.92rem;}
  .tt-hero .row{gap:8px;}
  .chip-stat{padding:8px 12px;}
  .chip-stat .v{font-size:1rem;}
  /* Upload card — on mobile the absolute-overlay approach blocks the cloud icon
     because Streamlit's own styles give the dropzone an opaque background.
     Reset to flow layout: dz-header (icon only) shows above the native uploader. */
  .st-key-upload_card [data-testid="stFileUploader"]{
    position:static!important;height:auto!important;}
  .st-key-upload_card [data-testid="stFileUploaderDropzone"]{
    position:relative!important;inset:auto!important;}
  .st-key-upload_card [data-testid="stFileUploaderDropzone"] *:not(button){
    display:revert!important;}
  .st-key-upload_card [data-testid="stFileUploaderDropzone"] button{
    position:static!important;inset:auto!important;
    width:auto!important;height:auto!important;opacity:1!important;}
  .st-key-upload_card .dz-header{padding:20px 16px 8px;}
  .st-key-upload_card .dz-title,.st-key-upload_card .dz-sub{display:none!important;}
}

/* Footer: quiet attribution, centered, mono — sits flush at the page bottom. */
.tt-footer{margin-top:32px;padding:16px 12px 4px;border-top:1px solid var(--border);
  text-align:center;font:500 .74rem/1.5 var(--mono);color:var(--muted);}
.tt-footer a{color:var(--good);font-weight:600;text-decoration:none;}
.tt-footer a:hover{text-decoration:underline;text-underline-offset:3px;}
"""


def _datagrid_css(tokens: dict) -> str:
    """Glide data-grid (st.dataframe/st.data_editor) theme with LITERAL hex
    values for the active theme. The grid canvas reads --gdg-* at paint time and
    does not resolve nested var() references, so dark mode requires inlined
    values rather than var(--surface)-style indirection."""
    t = tokens
    gdg = {
        "--gdg-accent-color": t["--primary"], "--gdg-accent-light": t["--primary-50"],
        "--gdg-bg-cell": t["--surface"], "--gdg-bg-cell-medium": t["--surface-2"],
        "--gdg-bg-header": t["--surface-2"], "--gdg-bg-header-has-focus": t["--primary-50"],
        "--gdg-bg-header-hovered": t["--surface-2"], "--gdg-bg-bubble": t["--surface"],
        "--gdg-border-color": t["--border-2"], "--gdg-horizontal-border-color": t["--border-2"],
        "--gdg-text-dark": t["--ink"], "--gdg-text-medium": t["--muted"],
        "--gdg-text-light": t["--faint"], "--gdg-text-header": t["--muted"],
        "--gdg-font-family": t["--font"],
    }
    decls = "".join(f"{k}:{v};" for k, v in gdg.items())
    return f'[data-testid="stDataFrame"],[data-testid="stDataEditor"]{{{decls}}}'


def _popover_css(tokens: dict) -> str:
    """Selectbox dropdown (portal-rendered by BaseWeb) with LITERAL token values.
    CSS variables can fail to resolve inside body-root portals in some Streamlit
    builds, so we inline the hex/rgba values the same way _datagrid_css does."""
    surface = tokens["--surface"]
    border = tokens["--border"]
    ink = tokens["--ink"]
    primary = tokens["--primary"]
    p50 = tokens["--primary-50"]
    sh2 = tokens["--sh-2"]
    r = tokens["--r"]
    font = tokens["--font"]
    return (
        # Cover the portal root and ALL descendant divs/uls — BaseWeb nests
        # deeper than >div>div in some Streamlit builds, so a shallow selector
        # misses intermediate wrappers and leaves them white in dark mode.
        f'[data-baseweb="popover"] div,'
        f'[data-baseweb="popover"] ul{{'
        f'background:{surface}!important;background-color:{surface}!important;}}'
        f'[data-baseweb="popover"] [role="listbox"],'
        f'[data-baseweb="popover"] [data-baseweb="menu"]{{'
        f'background:{surface}!important;border:1px solid {border}!important;'
        f'box-shadow:{sh2}!important;border-radius:{r}!important;}}'
        f'[data-baseweb="popover"] [role="option"],'
        f'[data-baseweb="popover"] li{{'
        f'background:transparent!important;background-color:transparent!important;'
        f'color:{ink}!important;font-family:{font}!important;'
        f'border-left:3px solid transparent!important;}}'
        f'[data-baseweb="popover"] [role="option"]:hover,'
        f'[data-baseweb="popover"] [role="option"][aria-selected="true"],'
        f'[data-baseweb="popover"] li:hover{{'
        f'background:{p50}!important;background-color:{p50}!important;'
        f'border-left:3px solid {primary}!important;'
        f'color:{ink}!important;}}'
        f'[data-baseweb="popover"] [role="option"]:hover div,'
        f'[data-baseweb="popover"] [role="option"][aria-selected="true"] div,'
        f'[data-baseweb="popover"] li:hover div{{'
        f'background:transparent!important;background-color:transparent!important;}}'
    )


def brand_css(theme: str = "light") -> str:
    """Full <style> block for the given theme ('light' | 'dark'). Switching is a
    pure CSS-variable swap; every component rule reads the tokens."""
    tokens = _DARK_TOKENS if theme == "dark" else _LIGHT_TOKENS
    root = ":root{" + "".join(f"{k}:{v};" for k, v in tokens.items()) + "}"
    return (f"<style>{_FONT_IMPORT}{root}{_COMPONENT_CSS}"
            f"{_datagrid_css(tokens)}{_popover_css(tokens)}{_HIDE_CHROME}</style>")


# Back-compat alias for any importer expecting the old constant.
BRAND_CSS = brand_css("light")


# --------------------------------------------------------------------------- #
# HTML builders (pure)
# --------------------------------------------------------------------------- #

_LINK_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
             'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
             '<path d="M10 13a5 5 0 0 0 7.07 0l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"/>'
             '<path d="M14 11a5 5 0 0 0-7.07 0l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"/></svg>')


_CHECK_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="20 6 9 17 4 12"/></svg>'
)

_X_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
    '<line x1="18" y1="6" x2="6" y2="18"/>'
    '<line x1="6" y1="6" x2="18" y2="18"/></svg>'
)

_UPLOAD_ICON_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>'
    '<polyline points="17 8 12 3 7 8"/>'
    '<line x1="12" y1="3" x2="12" y2="15"/>'
    '</svg>'
)

# Split into a static tray + a floating arrow so the arrow can animate (rise out
# of the tray) independently while the tray stays put — see `.dz-arrow` CSS.
_UPLOAD_TRAY_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/></svg>'
)
_UPLOAD_ARROW_SVG = (
    '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
    '<polyline points="17 8 12 3 7 8"/>'
    '<line x1="12" y1="3" x2="12" y2="15"/></svg>'
)


def upload_error_html(filename: str, detail: str, lang: str = DEFAULT_LANG) -> str:
    """Error banner shown inside the upload card when the CSV cannot be parsed."""
    title = escape(t("upload_error_title", lang))
    hint = escape(t("upload_error_hint", lang))
    fname = escape(filename)
    det = escape(str(detail)[:200])
    return (
        f'<div class="upload-err">'
        f'<div class="err-icon">{_X_SVG}</div>'
        f'<p class="err-title">{title}</p>'
        f'<p class="err-detail">{fname} — {det}</p>'
        f'<p class="err-hint">{hint}</p>'
        f'</div>'
    )


def upload_success_html(filename: str, n_rows: int, lang: str = DEFAULT_LANG) -> str:
    """Animated success banner shown inside the upload card after a file is loaded."""
    rows_label = escape(t("upload_loaded", lang, n=n_rows))
    fname = escape(filename)
    return (
        f'<div class="upload-ok">'
        f'<div class="chk">{_CHECK_SVG}</div>'
        f'<p class="ok-title">{rows_label}</p>'
        f'<p class="ok-sub">{fname}</p>'
        f'</div>'
    )


def dropzone_html(lang: str = DEFAULT_LANG) -> str:
    """Custom upload card header: icon + title + subtitle. Rendered above the
    native st.file_uploader inside a .st-key-upload_card container; CSS strips
    the uploader's native chrome so the two read as one unified card."""
    title = escape(t("upload_dropzone_title", lang))
    sub = escape(t("upload_dropzone_sub", lang))
    return (
        f'<div class="dz-header">'
        f'<div class="dz-iconwrap"><span class="dz-glow"></span>'
        f'<div class="dz-icon">{_UPLOAD_TRAY_SVG}'
        f'<span class="dz-arrow">{_UPLOAD_ARROW_SVG}</span></div></div>'
        f'<p class="dz-title">{title}</p>'
        f'<p class="dz-sub">{sub}</p>'
        f'</div>'
    )


def eyebrow_html(n, label: str, key: str) -> str:
    """Numbered section header: badge + gradient label + a permalink anchor that
    targets the section's ``#s-<key>`` scroll anchor (rendered by app._anchor)."""
    return (
        f'<div class="eyebrow"><span class="n">{escape(str(n))}</span>'
        f'<span class="lbl">{escape(label)}</span>'
        f'<a class="anchor" href="#s-{escape(key)}" title="{escape(label)}" '
        f'aria-label="{escape(label)}">{_LINK_SVG}</a></div>'
    )


def appbar_html(lang: str) -> str:
    """Left side of the app bar: brand logo + name."""
    return (
        f'<div class="tt-appbar"><div class="tt-brand">'
        f'<div class="glyph">{logo_img_html(34, _ICON_PATH)}</div>'
        f'<div class="name">{escape(t("app_title", lang))}</div></div>'
        f'</div>'
    )


def stepper_html(steps: List[dict], lang: str = DEFAULT_LANG) -> str:
    """Render the step indicator. Each step: {key, label, status} where status
    is one of active|done|locked|todo. Locked steps are non-navigable spans."""
    parts: List[str] = []
    for i, s in enumerate(steps):
        if i:
            # A connector is "done" (tinted) once the step it leaves is complete.
            # Stagger the heartbeat blip per connector so it sweeps left→right.
            prev_done = steps[i - 1].get("status") == "done"
            cls = "stp-divider done" if prev_done else "stp-divider"
            delay = f"{(i - 1) * 0.45:.2f}s"
            parts.append(f'<div class="{cls}" style="--d:{delay}"></div>')
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


def hero_html(lang: str = DEFAULT_LANG, chips=None) -> str:
    """Hero banner. ``chips`` is a list of ``(value, label, tone)`` (tone in
    {'', 'good', 'bad'}); when None the static proof chips are shown — so the
    hero turns into a live dashboard as data is loaded and solved (see
    ``ui_app.hero_chips``)."""
    if chips is None:
        chips = [
            ("793", t("hero_stat_sections", lang), ""),
            ("0", t("hero_stat_conflicts", lang), ""),
            (t("hero_stat_speed_v", lang), t("hero_stat_speed", lang), ""),
            ("CP-SAT", t("hero_stat_engine", lang), ""),
        ]
    cells = "".join(
        f'<div class="chip-stat {escape(tone)}"><span class="v">{escape(str(v))}</span>'
        f'<span class="l">{escape(label)}</span></div>'
        for (v, label, tone) in chips)
    return (
        f'<div class="tt-hero">'
        f'<h1>{t("hero_title_html", lang)}</h1>'
        f'<p>{escape(t("hero_body", lang))}</p>'
        f'<div class="row">{cells}</div></div>'
    )


def footer_html(lang: str = DEFAULT_LANG) -> str:
    """Quiet attribution footer shown below the last section."""
    return (
        f'<div class="tt-footer">© 2026 {escape(t("footer_dev", lang))} '
        f'<a href="https://huguryildiz.com/" target="_blank" rel="noopener">'
        f'Hüseyin Uğur Yıldız</a></div>'
    )


def metric_cards_html(cards: List[Tuple[str, str, str]]) -> str:
    """cards = [(label, value, tone)] where tone in {'', 'good', 'bad', 'brand'}."""
    cells = "".join(
        f'<div class="tt-card {escape(tone)}"><div class="v">{escape(str(v))}</div>'
        f'<div class="l">{escape(label)}</div></div>'
        for (label, v, tone) in cards)
    return f'<div class="tt-cards">{cells}</div>'


def data_table_html(columns: List[str], rows: List[List], max_height: int = 340,
                    numeric: Tuple[str, ...] = ()) -> str:
    """Read-only themed table for tabular previews (uploaded courselist, room
    inventory). Rendered as our own HTML/CSS so it follows the in-app light/dark
    theme — unlike ``st.dataframe``, whose glide-grid canvas is painted from
    Streamlit's *native* (light) theme and cannot be re-themed from CSS.

    ``columns`` are header labels; ``rows`` are row sequences aligned to them.
    ``numeric`` lists column labels to right-align with tabular figures. The
    wrapper scrolls internally (both axes), capped at ``max_height`` px."""
    num = set(numeric)
    head = "".join(
        f'<th class="num">{escape(str(c))}</th>' if c in num else f'<th>{escape(str(c))}</th>'
        for c in columns)
    if not rows:
        body = f'<tr><td class="tt-td-empty" colspan="{max(len(columns), 1)}">—</td></tr>'
    else:
        trs = []
        for r in rows:
            tds = "".join(
                (f'<td class="num">{escape("" if v is None else str(v))}</td>'
                 if (i < len(columns) and columns[i] in num)
                 else f'<td>{escape("" if v is None else str(v))}</td>')
                for i, v in enumerate(r))
            trs.append(f"<tr>{tds}</tr>")
        body = "".join(trs)
    return (f'<div class="tt-table-wrap" style="--tt-table-h:{int(max_height)}px">'
            f'<table class="tt-data"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div>')


_IMP_STATUS_LABEL = {
    "ok": "import_status_ok", "dup": "import_status_dup",
    "dup_file": "import_status_dup_file", "err_code": "import_status_err_code",
    "err_hours": "import_status_err_hours",
}
# Columns shown in the import preview (canonical field -> i18n-free short header).
_IMP_COLS = ("Course Code", "Course Name", "Section No", "T", "P", "L",
             "Lecturer Email", "~Students")
_IMP_NUM = {"T", "P", "L", "~Students"}


def import_preview_html(report: dict, lang: str = DEFAULT_LANG) -> str:
    """Render the VERA-style import preview: detected-column chips, stat badges
    and a per-row preview table with colored status pills. ``report`` is the dict
    from ``csv_import.parse_courselist``."""
    detected = report.get("detected_columns", [])
    stats = report.get("stats", {})
    rows = report.get("rows", [])

    chips = "".join(
        f'<span class="col{"" if d["source"] == "header" else " pos"}">'
        f'{escape(str(d["field"]))} <em>→ {escape(str(d["label"]))}'
        f'{"" if d["source"] == "header" else " (" + t("import_positional", lang) + ")"}'
        f'</em></span>'
        for d in detected)
    detect_html = (f'<div class="imp-detect"><span class="lbl">'
                   f'{t("import_detected", lang)}</span>{chips}</div>')

    def _badge(n, key, tone):
        return (f'<span class="imp-badge {tone}"><span class="n">{n}</span>'
                f'{t(key, lang)}</span>')
    badges = [_badge(stats.get("valid", 0), "import_valid", "good")]
    if stats.get("duplicate", 0):
        badges.append(_badge(stats["duplicate"], "import_duplicate", "warn"))
    if stats.get("error", 0):
        badges.append(_badge(stats["error"], "import_error", "bad"))
    badges.append(_badge(stats.get("total", 0), "import_total", ""))
    stats_html = f'<div class="imp-stats">{"".join(badges)}</div>'

    head = (f'<th class="num">{t("import_col_row", lang)}</th>'
            + "".join((f'<th class="num">{escape(c)}</th>' if c in _IMP_NUM
                       else f'<th>{escape(c)}</th>') for c in _IMP_COLS)
            + f'<th>{t("import_col_status", lang)}</th>')
    trs = []
    for r in rows:
        status = r.get("status", "ok")
        rcls = (" row-dup" if status == "duplicate"
                else " row-err" if status == "error" else "")
        tds = [f'<td class="num">{escape(str(r.get("row_num", "")))}</td>']
        for c in _IMP_COLS:
            cls = ' class="num"' if c in _IMP_NUM else ""
            tds.append(f'<td{cls}>{escape(str(r.get(c, "") or "—"))}</td>')
        label = t(_IMP_STATUS_LABEL.get(r.get("status_label", ""), "import_status_ok"), lang)
        tds.append(f'<td><span class="st-pill {escape(status)}">{escape(label)}</span></td>')
        trs.append(f'<tr class="{rcls.strip()}">{"".join(tds)}</tr>')
    body = "".join(trs) or (
        f'<tr><td class="tt-td-empty" colspan="{len(_IMP_COLS) + 2}">—</td></tr>')

    table = (f'<div class="tt-table-wrap" style="--tt-table-h:360px">'
             f'<table class="tt-data"><thead><tr>{head}</tr></thead>'
             f'<tbody>{body}</tbody></table></div>')
    return detect_html + stats_html + table


def _block_html(a: dict, is_start: bool) -> str:
    color = block_color(a)
    is_lab = "lab" in str(a.get("block_kind", "")).lower()
    klass = "tt-blk" + (" lab" if is_lab else "") + ("" if is_start else " cont")
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
    return (f'<div class="tt-wrap"><div class="tt-scroll">'
            f'<table class="tt"><thead><tr>{head}</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
            f'</div></div>')
