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
import re
from html import escape
from typing import List, Tuple

from .ui_grid import build_week_grid, DAYS_ORDER
from .i18n import DAY_LABELS, DAY_LABELS_FULL, DEFAULT_LANG, field_label, t

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
    "--primary": "#7B82D4", "--primary-700": "#5C64C7",
    "--primary-50": "#EEEFFE", "--primary-100": "#DCDDF8",
    "--canvas": "#F4F6FA", "--surface": "#FFFFFF", "--surface-2": "#FAFBFD",
    "--card": "#FFFFFF", "--card-bd": "#E5E9F1",
    "--ink": "#131722", "--ink-2": "#39414F", "--muted": "#5B6472", "--faint": "#9AA3B2",
    "--border": "#E5E9F1", "--border-2": "#EEF1F6",
    "--good": "#0F766E", "--good-bg": "#ECFDF6", "--good-bd": "#A7E3D4", "--good-mid": "#34D399",
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
    "--cta-bg": "rgba(43,58,140,.85)", "--cta-bd": "rgba(255,255,255,.25)", "--cta-sh": "rgba(43,58,140,.42)",
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
    "--good": "#34D6AA", "--good-bg": "rgba(52,214,170,.13)", "--good-bd": "rgba(52,214,170,.36)", "--good-mid": "#34D6AA",
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
    "--cta-bg": "rgba(55,72,165,.80)", "--cta-bd": "rgba(255,255,255,.18)", "--cta-sh": "rgba(55,72,165,.52)",
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
/* Streamlit collapses the brand markdown wrapper to a ~12px line box, so the
   taller brand row top-aligns and its mid-line lands ~8px below the control
   buttons (which sit on the true row centre). Nudge the brand up to match — a
   transform, so it shifts visually without reflowing the collapsed wrappers.
   Offset is line-box-driven (constant for both the 28px and 40px glyph), not
   glyph-height-driven, so a single value holds across breakpoints. */
.tt-appbar{display:flex;align-items:center;gap:14px;transform:translateY(-8px);}
.tt-brand{display:flex;align-items:center;gap:11px;font-weight:700;}
.tt-brand .glyph{width:32px;height:32px;border-radius:8px;flex:none;overflow:hidden;box-shadow:var(--sh-1);}
.tt-brand .glyph img{width:100%;height:100%;display:block;border-radius:inherit;}
.tt-brand .name{font-family:var(--serif);font-weight:600;font-size:1.3rem;letter-spacing:-.005em;background:linear-gradient(95deg,var(--head-1) 0%,var(--head-2) 100%);-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;}
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
/* Sub-header: a smaller, number-less section header for the sub-sections grouped
   under one numbered step (e.g. course list / review / classrooms under Data). */
.eyebrow.sub{font-size:1.12rem;font-weight:600;margin:18px 0 8px;gap:8px;}

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
.chip-stat.good .v{color:var(--good-mid);}.chip-stat.good .l{color:var(--good-bd);}
.chip-stat.bad{background:rgba(248,113,113,.14);border-color:rgba(248,113,113,.34);}
.chip-stat.bad .v{color:#FCA5A5;}

/* Hero animation — a mini week grid that "solves" itself: course blocks slide
   into empty cells forming a conflict-free schedule, then gently re-solves on an
   ~8s loop. Decorative (aria-hidden), lives behind the text on the right. The
   hero gradient is theme-fixed navy, so this reads identically in light + dark.
   Day labels are localized in `hero_html` (DAY_LABELS[lang]). */
.tt-hero h1,.tt-hero>p,.tt-hero>.row{position:relative;z-index:1;}
.tt-hero-anim{position:absolute;z-index:0;right:30px;top:50%;transform:translateY(-50%);width:286px;pointer-events:none;}
.tt-hero-anim::before{content:"";position:absolute;inset:-26px -22px;border-radius:30px;background:radial-gradient(60% 60% at 50% 42%, rgba(150,166,240,.22), rgba(150,166,240,0) 72%);}
.tt-hero-anim .days{display:grid;grid-template-columns:repeat(5,1fr);gap:6px;margin:0 0 7px;}
.tt-hero-anim .days span{font:600 .56rem/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:rgba(190,200,240,.62);text-align:center;}
.tt-hero-anim .board{position:relative;}
.tt-hero-anim .cells{display:grid;grid-template-columns:repeat(5,1fr);grid-template-rows:repeat(5,26px);gap:6px;}
.tt-hero-anim .cells i{border-radius:6px;background:rgba(255,255,255,.045);box-shadow:inset 0 0 0 1px rgba(255,255,255,.06);}
.tt-hero-anim .blocks{position:absolute;inset:0;display:grid;grid-template-columns:repeat(5,1fr);grid-template-rows:repeat(5,26px);gap:6px;}
.tt-hero-anim .blk{position:relative;border-radius:6px;--c:#8E9BF2;background:linear-gradient(158deg, color-mix(in srgb,var(--c) 78%, #ffffff) 0%, var(--c) 60%);box-shadow:0 5px 16px -6px var(--c),inset 0 1px 0 rgba(255,255,255,.4);opacity:0;transform:translateY(-12px) scale(.92);animation:solveIn 8s var(--d,0s) cubic-bezier(.34,1.32,.5,1) infinite;}
.tt-hero-anim .blk::after{content:"";position:absolute;left:7px;right:7px;top:6px;height:3px;border-radius:3px;background:rgba(255,255,255,.5);}
.tt-hero-anim .sweep{position:absolute;inset:0;border-radius:8px;overflow:hidden;pointer-events:none;}
.tt-hero-anim .sweep::after{content:"";position:absolute;top:-20%;bottom:-20%;left:-40%;width:34%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.16),transparent);transform:skewX(-14deg);animation:gridSweep 8s 1.9s ease-in-out infinite;}
@keyframes solveIn{0%{opacity:0;transform:translateY(-12px) scale(.92);}6%{opacity:1;transform:translateY(2px) scale(1.03);}11%{opacity:1;transform:translateY(0) scale(1);}78%{opacity:1;transform:none;}87%{opacity:0;transform:translateY(-8px) scale(.96);}100%{opacity:0;transform:translateY(-12px) scale(.92);}}
@keyframes gridSweep{0%,18%{transform:translateX(0) skewX(-14deg);opacity:0;}24%{opacity:1;}46%{transform:translateX(900%) skewX(-14deg);opacity:0;}100%{transform:translateX(900%) skewX(-14deg);opacity:0;}}
/* Hide below 980px so the grid never crowds the headline / on mobile portrait. */
@media (max-width:980px){.tt-hero-anim{display:none;}}
@media (prefers-reduced-motion:reduce){.tt-hero-anim .blk{animation:none;opacity:1;transform:none;}.tt-hero-anim .sweep{display:none;}}

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
table.tt th{background:var(--surface-2);color:var(--muted);font:600 .68rem/1 var(--mono);text-transform:uppercase;letter-spacing:.07em;padding:12px 8px;border-bottom:1px solid var(--border);text-align:center;vertical-align:middle;}
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
.tt-blk .tag.prat{color:var(--warn,#b45309);border-color:currentColor;}
.tt-empty{color:var(--faint);font:500 .9rem/1 var(--font);padding:24px;text-align:center;}

/* Read-only data table (uploaded courselist / room inventory previews). Our own
   HTML/CSS so it follows the in-app light/dark theme — st.dataframe's glide grid
   paints its canvas from Streamlit's *native* (light) theme and can't be
   re-themed via CSS. Header sticks; the wrapper scrolls internally (both axes)
   so a wide table stays contained on a phone in portrait. */
.tt-table-wrap{border:1px solid var(--border);border-radius:var(--r-lg);overflow:auto;width:fit-content;max-width:100%;max-height:var(--tt-table-h,340px);background:var(--surface);box-shadow:var(--sh-1);-webkit-overflow-scrolling:touch;}
table.tt-data{border-collapse:collapse;width:auto;min-width:280px;margin:0 auto;font:500 .82rem/1.45 var(--font);color:var(--ink-2);}
table.tt-data thead th{position:sticky;top:0;z-index:1;background:var(--surface-2);color:var(--muted);font:600 .66rem/1 var(--mono);text-transform:uppercase;letter-spacing:.06em;text-align:left;padding:7px 10px;border-bottom:1px solid var(--border);white-space:nowrap;}
table.tt-data tbody td{padding:5px 10px;border-bottom:1px solid var(--border-2);white-space:nowrap;text-align:left;}
table.tt-data th.num,table.tt-data td.num{text-align:center;font-variant-numeric:tabular-nums;}
table.tt-data tbody tr:nth-child(even){background:var(--surface-2);}
table.tt-data tbody tr:hover{background:var(--primary-50);}
table.tt-data tbody tr:last-child td{border-bottom:none;}
td.tt-td-empty{color:var(--faint);text-align:center;padding:20px;}
.cr-edit-head{font:600 .92rem/1.3 var(--font);color:var(--ink-2);margin:20px 0 8px;}

/* CSV import preview (VERA-style): detected-column chips, stat badges, status pills */
.imp-detect-card{background:var(--card);border:1px solid var(--card-bd);border-radius:var(--r);padding:14px 16px 0;box-shadow:var(--sh-1);margin:6px 0 14px;overflow:hidden;}
.imp-req-row{display:flex;align-items:center;gap:10px;margin:12px -16px 0;padding:10px 16px;}
.imp-req-row.met{background:var(--good-bg);border-top:1px solid var(--good-bd);}
.imp-req-row.unmet{background:var(--error-bg);border-top:1px solid var(--error-bd);}
.imp-req-row.warn{background:var(--warn-bg);border-top:1px solid var(--warn-bd);}
.imp-req-icon{width:15px;height:15px;flex:none;vertical-align:middle;}
.imp-req-row.met .imp-req-icon{color:var(--good);}
.imp-req-row.unmet .imp-req-icon{color:var(--error);}
.imp-req-row.warn .imp-req-icon{color:var(--warn);}
.imp-req-lbl{font:700 .62rem/1 var(--mono);text-transform:uppercase;letter-spacing:.12em;flex:none;}
.imp-req-row.met .imp-req-lbl{color:var(--good);}
.imp-req-row.unmet .imp-req-lbl{color:var(--error);}
.imp-req-row.warn .imp-req-lbl{color:var(--warn);}
.imp-req-val{font:600 .8rem/1 var(--font);display:flex;align-items:center;gap:8px;}
.imp-req-val.met{color:var(--good);}
.imp-req-val.unmet{color:var(--error);}
.imp-req-val.warn{color:var(--warn);}
.imp-req-fields{font:500 .7rem/1 var(--mono);opacity:.65;color:inherit;}
.imp-req-met{font:600 .8rem/1 var(--font);color:var(--good);flex:none;}
.imp-detect{margin:0 0 4px;}
.imp-detect-head{display:flex;align-items:center;gap:9px;margin-bottom:11px;}
.imp-detect-head .lbl{font:700 .64rem/1 var(--mono);color:var(--muted);text-transform:uppercase;letter-spacing:.13em;}
.imp-detect-head .imp-detect-count{font:700 .6rem/1 var(--mono);color:var(--primary);background:var(--primary-50);border:1px solid var(--primary-100);border-radius:999px;padding:3px 8px;font-variant-numeric:tabular-nums;}
.imp-cols{display:flex;flex-wrap:wrap;gap:7px;}
.imp-cols .col{display:inline-flex;align-items:center;gap:7px;background:var(--good-bg);border:1px solid var(--good-bd);border-radius:10px;padding:6px 11px 6px 10px;box-shadow:var(--sh-1);transition:border-color .18s ease,box-shadow .18s ease,transform .18s ease;}
.imp-cols .col:hover{transform:translateY(-1px);border-color:var(--good);box-shadow:var(--sh-2);}
.imp-cols .col .dot{width:6px;height:6px;border-radius:50%;flex:none;background:var(--good);box-shadow:0 0 0 3px var(--good-bg);}
.imp-cols .col b{font:600 .74rem/1 var(--font);color:var(--ink);letter-spacing:-.01em;}
.imp-cols .col .arw{font:600 .74rem/1 var(--font);color:var(--faint);}
.imp-cols .col em{font:500 .72rem/1 var(--mono);font-style:normal;color:var(--muted);}
.imp-cols .col.pos{border-style:dashed;background:var(--warn-bg);border-color:var(--warn-bd);box-shadow:none;}
.imp-cols .col.pos .dot{background:var(--warn);box-shadow:0 0 0 3px var(--warn-bg);}
.imp-cols .col.pos b{color:var(--ink-2);}
.imp-cols .col.pos em{color:var(--faint);}
.imp-cols .col .tag{margin-left:1px;font:700 .53rem/1 var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--warn);background:var(--warn-bg);border:1px solid var(--warn-bd);border-radius:5px;padding:3px 5px;}
.imp-stats{display:flex;flex-wrap:wrap;gap:8px;margin-bottom:10px;}
.imp-badge{display:inline-flex;align-items:baseline;gap:5px;border-radius:8px;padding:5px 11px;font:600 .72rem/1 var(--font);border:1px solid var(--border);background:var(--surface-2);color:var(--ink-2);}
.imp-badge .n{font:800 .9rem/1 var(--font);font-variant-numeric:tabular-nums;color:var(--ink);}
.imp-badge.good .n{color:var(--good);}
.imp-badge.good{background:var(--good-bg);border-color:var(--good-bd);color:var(--good);}
.imp-badge.warn{background:var(--warn-bg);border-color:var(--warn-bd);color:var(--warn);}
.imp-badge.bad{background:var(--error-bg);border-color:var(--error-bd);color:var(--error);}
.tt-data tr.row-dup{background:var(--warn-bg);}
.tt-data tr.row-err{background:var(--error-bg);}
.st-pill{display:inline-block;font:600 .64rem/1 var(--mono);padding:4px 8px;border-radius:6px;border:1px solid var(--border);background:var(--surface-2);color:var(--muted);white-space:nowrap;}
.st-pill.ok{background:var(--good-bg);border-color:var(--good-bd);color:var(--good);}
.st-pill.duplicate{background:var(--warn-bg);border-color:var(--warn-bd);color:var(--warn);}
.st-pill.error{background:var(--error-bg);border-color:var(--error-bd);color:var(--error);}

/* Solve card — replaces the button while the solver runs; shows animated grid + progress */
.solve-running{display:flex;flex-direction:column;gap:14px;padding:20px 22px;max-width:480px;margin:0 auto;
  border-radius:14px;cursor:wait;color:#fff;
  background:radial-gradient(ellipse at 85% -15%,#5C6CC6 0%,rgba(92,108,198,0) 56%),
             linear-gradient(135deg,#233178 0%,#2B3A8C 50%,#1C2766 100%);
  box-shadow:0 1px 2px rgba(31,43,103,.3),0 10px 36px -10px rgba(31,43,103,.55);}
/* Mini timetable grid inside the card */
.smg-days{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin-bottom:6px;}
.smg-days span{font:600 .55rem/1 var(--mono);letter-spacing:.06em;text-transform:uppercase;color:rgba(190,200,240,.6);text-align:center;}
.smg-board{position:relative;}
.smg-cells,.smg-blocks{display:grid;grid-template-columns:repeat(5,1fr);grid-template-rows:repeat(5,20px);gap:5px;}
.smg-blocks{position:absolute;inset:0;}
.smg-cells i{border-radius:4px;background:rgba(255,255,255,.045);box-shadow:inset 0 0 0 1px rgba(255,255,255,.06);}
.smg-blk{position:relative;border-radius:4px;--c:#8E9BF2;background:linear-gradient(158deg,color-mix(in srgb,var(--c) 78%,#fff) 0%,var(--c) 60%);box-shadow:0 4px 12px -4px var(--c),inset 0 1px 0 rgba(255,255,255,.35);opacity:0;transform:translateY(-10px) scale(.93);animation:solveIn 8s var(--d,0s) cubic-bezier(.34,1.32,.5,1) infinite;}
.smg-blk::after{content:"";position:absolute;left:5px;right:5px;top:5px;height:2px;border-radius:2px;background:rgba(255,255,255,.45);}
.smg-sweep{position:absolute;inset:0;border-radius:6px;overflow:hidden;pointer-events:none;}
.smg-sweep::after{content:"";position:absolute;top:-20%;bottom:-20%;left:-40%;width:30%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.12),transparent);transform:skewX(-14deg);animation:gridSweep 8s 1.9s ease-in-out infinite;}
/* Label row — !important needed; Streamlit's div{color:var(--ink)} overrides inherited white */
.solve-label{display:flex;align-items:center;gap:9px;font:700 .95rem/1 var(--font);color:#fff!important;}
/* Progress bar */
.solve-progress-track{height:5px;border-radius:99px;background:rgba(255,255,255,.13);overflow:hidden;}
.solve-progress-fill{height:100%;border-radius:99px;background:linear-gradient(90deg,#8E9BF2,#B8C4F5);width:0%;transition:width .9s linear;}
/* In-progress spinner gear */
.solve-gear{width:18px;height:18px;flex:none;
  background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='white' d='M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z'/%3E%3C/svg%3E") center/contain no-repeat;
  animation:solveSpin .9s linear infinite;}
@keyframes solveSpin{to{transform:rotate(360deg);}}
/* Solve button — LEFT-aligned, auto-width, shimmer on load; CSS SVG gear nudges on click
   (the continuous gear rotation appears in the .solve-gear loading state while solving).
   transform-origin centred so the gear spins about its own hub. */
.st-key-solve_btn{display:flex;justify-content:flex-start;}
.st-key-solve_btn button{position:relative;overflow:hidden;padding:12px 40px!important;display:inline-flex!important;align-items:center;justify-content:center;gap:7px;}
.st-key-solve_btn button::before{content:"";display:inline-block;flex:none;width:20px;height:20px;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24'%3E%3Cpath fill='white' d='M19.14 12.94c.04-.3.06-.61.06-.94 0-.32-.02-.64-.07-.94l2.03-1.58c.18-.14.23-.41.12-.61l-1.92-3.32c-.12-.22-.37-.29-.59-.22l-2.39.96c-.5-.38-1.03-.7-1.62-.94l-.36-2.54c-.04-.24-.24-.41-.48-.41h-3.84c-.24 0-.43.17-.47.41l-.36 2.54c-.59.24-1.13.57-1.62.94l-2.39-.96c-.22-.08-.47 0-.59.22L2.74 8.87c-.12.21-.08.47.12.61l2.03 1.58c-.05.3-.09.63-.09.94s.02.64.07.94l-2.03 1.58c-.18.14-.23.41-.12.61l1.92 3.32c.12.22.37.29.59.22l2.39-.96c.5.38 1.03.7 1.62.94l.36 2.54c.05.24.24.41.48.41h3.84c.24 0 .44-.17.47-.41l.36-2.54c.59-.24 1.13-.56 1.62-.94l2.39.96c.22.08.47 0 .59-.22l1.92-3.32c.12-.22.07-.47-.12-.61l-2.01-1.58zM12 15.6c-1.98 0-3.6-1.62-3.6-3.6s1.62-3.6 3.6-3.6 3.6 1.62 3.6 3.6-1.62 3.6-3.6 3.6z'/%3E%3C/svg%3E") center/contain no-repeat;transform-origin:50% 50%;}
.st-key-solve_btn button::after{content:"";position:absolute;top:-50%;left:-80%;width:45%;height:200%;background:linear-gradient(90deg,transparent,rgba(255,255,255,.26),transparent);transform:skewX(-12deg);animation:wandShimmer 1.6s ease-in-out 0.1s 3;}
.st-key-solve_btn button.wand-casting::before{animation:wandCast 0.5s ease-in-out;}
@keyframes wandShimmer{0%{left:-80%}100%{left:140%}}
@keyframes wandCast{0%{transform:rotate(0deg)}20%{transform:rotate(-22deg)}55%{transform:rotate(15deg)}80%{transform:rotate(-5deg)}100%{transform:rotate(0deg)}}
/* Solve watcher iframe (views/solve.py) — a height:0 components.html iframe whose JS
   arms the "Leave site?" guard + live ETA countdown. Collapse its container so the
   0-height iframe leaves no flex-gap row between the caption and the button. A
   display:none iframe still loads and runs its script, so the watcher keeps polling. */
.st-key-solve_watch{display:none!important;}

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

/* Widget help (?) icon — keep it at default DOM order (after the label text)
   so ? sits immediately to the RIGHT of the label text. */
[data-testid="stWidgetLabel"] > div:has([data-testid="stTooltipIcon"]){
  flex:0 0 auto!important;justify-content:flex-start!important;
  margin:0 0 0 5px!important;}
[data-testid="stWidgetLabel"] [data-testid="stTooltipIcon"] [data-testid="stTooltipHoverTarget"],
[data-testid="stWidgetLabel"] [data-testid="stTooltipIcon"] label{margin:0!important;}
/* The ? glyph stroke defaults to a very faint tone that vanishes in dark mode;
   force a visible muted colour that brightens to primary on hover. */
[data-testid="stTooltipIcon"] svg{stroke:var(--muted)!important;color:var(--muted)!important;}
[data-testid="stTooltipIcon"]:hover svg{stroke:var(--primary)!important;color:var(--primary)!important;}

/* Help (?) tooltip popover — render as ONE flat floating bubble, NEVER a card
   nested inside the settings card. The outer popover layer paints nothing; the
   single visible bubble (inner div) is ONE solid colour. No contrasting border:
   a filled surface PLUS a 1px grey border reads as two stacked layers (a card
   inside a frame) — exactly the nested-card look. The bubble floats on its soft
   even shadow alone, so the whole edge stays a single colour. */
[data-baseweb="popover"]:has([data-testid="stTooltipContent"]){
  background:transparent!important;border:none!important;box-shadow:none!important;}
[data-baseweb="popover"]:has([data-testid="stTooltipContent"]) > div{
  background:var(--surface-2)!important;border:none!important;
  border-radius:var(--r-sm)!important;
  box-shadow:0 6px 24px rgba(20,24,38,.16),0 1px 3px rgba(20,24,38,.10)!important;}
[data-testid="stTooltipContent"]{text-align:justify!important;text-justify:inter-word;}
[data-testid="stTooltipContent"],
[data-testid="stTooltipContent"] *{color:var(--ink-2)!important;background:transparent!important;}

/* ── CTA (primary) button — glassmorphism ─────────────────────────────────── */
/* Dark-navy glass fill via --cta-bg token. backdrop-blur gives the frosted
   glass look; white-highlight border (--cta-bd) separates it from background.
   min-height 44px = WCAG mobile tap target. Hover: brightness lift + y-translate
   — no border/size change so no layout reflow. Tokens live in _LIGHT_TOKENS /
   _DARK_TOKENS; change there to restyle all CTAs at once. */
.stButton>button[kind="primary"],
.stButton>button[data-testid="stBaseButton-primary"]{
  background:var(--cta-bg)!important;
  backdrop-filter:blur(16px) saturate(1.4)!important;
  -webkit-backdrop-filter:blur(16px) saturate(1.4)!important;
  color:#fff!important;-webkit-text-fill-color:#fff!important;
  border:1px solid var(--cta-bd)!important;border-radius:16px;font-weight:700;font-size:1rem;
  min-height:44px;padding:.75rem 1.5rem!important;
  box-shadow:0 2px 12px var(--cta-sh),inset 0 1px 0 rgba(255,255,255,.18)!important;
  transition:filter .18s ease,box-shadow .18s ease,transform .18s ease;}
.stButton>button[kind="primary"] p,
.stButton>button[data-testid="stBaseButton-primary"] p{
  color:#fff!important;-webkit-text-fill-color:#fff!important;font-weight:700;}
.stButton>button[kind="primary"]:hover,
.stButton>button[data-testid="stBaseButton-primary"]:hover{
  filter:brightness(1.12);transform:translateY(-1px);
  box-shadow:0 6px 20px var(--cta-sh),inset 0 1px 0 rgba(255,255,255,.22)!important;
  color:#fff!important;-webkit-text-fill-color:#fff!important;}
.stButton>button[kind="primary"]:hover p,
.stButton>button[data-testid="stBaseButton-primary"]:hover p{
  color:#fff!important;-webkit-text-fill-color:#fff!important;}
.stButton>button[kind="primary"]:active,
.stButton>button[data-testid="stBaseButton-primary"]:active{
  transform:translateY(0)!important;filter:brightness(.88)!important;
  box-shadow:0 1px 4px var(--cta-sh),inset 0 1px 0 rgba(255,255,255,.14)!important;}
.stButton>button[kind="primary"]:focus-visible,
.stButton>button[data-testid="stBaseButton-primary"]:focus-visible{
  outline:2px solid var(--primary)!important;outline-offset:3px!important;}
/* ── Secondary button ─────────────────────────────────────────────────────── */
/* Surface card look. Hover uses inset box-shadow (no border width change →
   no layout shift). :active sinks back to rest level. */
.stButton>button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]),
.stDownloadButton>button{
  background:var(--surface)!important;color:var(--ink)!important;
  border:1px solid var(--border)!important;border-radius:10px;font-weight:500;
  min-height:44px;padding:.6rem 1.25rem!important;
  box-shadow:var(--sh-1)!important;
  transition:background .18s ease,color .18s ease,box-shadow .18s ease,transform .18s ease;}
.stDownloadButton>button p{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
.stButton>button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):hover,
.stDownloadButton>button:hover{
  background:var(--primary-50)!important;color:var(--primary)!important;
  box-shadow:inset 0 0 0 1.5px var(--primary),var(--sh-1)!important;
  transform:translateY(-1px);}
.stButton>button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):active,
.stDownloadButton>button:active{
  transform:translateY(0)!important;background:var(--primary-100)!important;
  box-shadow:inset 0 0 0 1.5px var(--primary)!important;}
.stButton>button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):focus-visible,
.stDownloadButton>button:focus-visible{
  outline:2px solid var(--primary)!important;outline-offset:3px!important;}
/* ── Button icon hover animations ───────────────────────────────────────── */
/* Streamlit material icons sit in [data-testid="stIconMaterial"] inside each
   button. On hover the icon springs with an elastic overshoot (cubic-bezier
   mimics a physical bounce) — scale-up + slight tilt — giving every icon
   button a tactile, alive feel without touching the button's own transform.
   :active snaps back below 1× so the press registers visually.
   Covers st.button and st.download_button in both primary and secondary kinds.
   The wand ::before on .st-key-solve_btn uses a separate wandCast keyframe and
   is unaffected by these rules. */
.stButton button [data-testid="stIconMaterial"],
.stDownloadButton button [data-testid="stIconMaterial"]{
  display:inline-flex;align-items:center;justify-content:center;
  transition:transform .3s cubic-bezier(.34,1.56,.64,1);
  will-change:transform;}
.stButton button:hover [data-testid="stIconMaterial"],
.stDownloadButton button:hover [data-testid="stIconMaterial"]{
  transform:scale(1.22) rotate(-8deg);}
.stButton button:active [data-testid="stIconMaterial"],
.stDownloadButton button:active [data-testid="stIconMaterial"]{
  transform:scale(.9) rotate(0deg);
  transition:transform .1s ease;}
@media (prefers-reduced-motion:reduce){
  .stButton button [data-testid="stIconMaterial"],
  .stDownloadButton button [data-testid="stIconMaterial"]{transition:none;}
  .stButton button:hover [data-testid="stIconMaterial"],
  .stDownloadButton button:hover [data-testid="stIconMaterial"]{transform:none;}}
/* Premium download buttons — JSON (indigo) + CSV (emerald) + PDF (red).
   st-key-* lives on the PARENT of stDownloadButton, so selectors use the ancestor pattern:
   .st-key-X [data-testid="stDownloadButton"] button — specificity (0,3,1) > generic (0,2,1). */
.st-key-dl_json [data-testid="stDownloadButton"] button,
.st-key-dl_json [data-testid="stBaseButton-secondary"]{background:linear-gradient(135deg,#3A4EA0 0%,#2F42A0 46%,#233178 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #2B3A8C!important;border-radius:12px!important;font-weight:600!important;letter-spacing:.01em;padding:12px 20px!important;box-shadow:0 1px 3px rgba(31,43,103,.35),0 6px 18px -8px rgba(31,43,103,.55)!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button p,
.st-key-dl_json [data-testid="stBaseButton-secondary"] p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button:hover{background:linear-gradient(135deg,#4A5EB0 0%,#3F52B0 46%,#334188 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #2B3A8C!important;box-shadow:0 4px 14px -4px rgba(31,43,103,.6)!important;transform:translateY(-1px)!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button:hover p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_json [data-testid="stDownloadButton"] button::before{content:"";display:inline-block;width:18px;height:18px;margin-right:8px;vertical-align:middle;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='16 18 22 12 16 6'/%3E%3Cpolyline points='8 6 2 12 8 18'/%3E%3C/svg%3E") center/contain no-repeat;}
.st-key-dl_csv [data-testid="stDownloadButton"] button,
.st-key-dl_csv [data-testid="stBaseButton-secondary"]{background:linear-gradient(135deg,#1A7A42 0%,#186C3A 46%,#115530 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #166235!important;border-radius:12px!important;font-weight:600!important;letter-spacing:.01em;padding:12px 20px!important;box-shadow:0 1px 3px rgba(17,85,48,.35),0 6px 18px -8px rgba(17,85,48,.55)!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button p,
.st-key-dl_csv [data-testid="stBaseButton-secondary"] p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button:hover{background:linear-gradient(135deg,#2A8A52 0%,#267C4A 46%,#195C38 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #166235!important;box-shadow:0 4px 14px -4px rgba(17,85,48,.6)!important;transform:translateY(-1px)!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button:hover p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_csv [data-testid="stDownloadButton"] button::before{content:"";display:inline-block;width:18px;height:18px;margin-right:8px;vertical-align:middle;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='3' width='18' height='18' rx='2'/%3E%3Cline x1='3' y1='9' x2='21' y2='9'/%3E%3Cline x1='3' y1='15' x2='21' y2='15'/%3E%3Cline x1='9' y1='3' x2='9' y2='21'/%3E%3C/svg%3E") center/contain no-repeat;}
.st-key-dl_pdf [data-testid="stDownloadButton"] button,
.st-key-dl_pdf [data-testid="stBaseButton-secondary"]{background:linear-gradient(135deg,#C0392B 0%,#A93226 46%,#922B21 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #922B21!important;border-radius:12px!important;font-weight:600!important;letter-spacing:.01em;padding:12px 20px!important;box-shadow:0 1px 3px rgba(146,43,33,.35),0 6px 18px -8px rgba(146,43,33,.55)!important;}
.st-key-dl_pdf [data-testid="stDownloadButton"] button p,
.st-key-dl_pdf [data-testid="stBaseButton-secondary"] p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_pdf [data-testid="stDownloadButton"] button:hover{background:linear-gradient(135deg,#D04437 0%,#B93A2E 46%,#A23529 100%)!important;color:#fff!important;-webkit-text-fill-color:#fff!important;border:1px solid #922B21!important;box-shadow:0 4px 14px -4px rgba(146,43,33,.6)!important;transform:translateY(-1px)!important;}
.st-key-dl_pdf [data-testid="stDownloadButton"] button:hover p{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.st-key-dl_pdf [data-testid="stDownloadButton"] button::before{content:"";display:inline-block;width:18px;height:18px;margin-right:8px;vertical-align:middle;background:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='white' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z'/%3E%3Cpolyline points='14 2 14 8 20 8'/%3E%3C/svg%3E") center/contain no-repeat;}
/* Theme toggle (☀️/🌙) — circular icon button; detailed sizing rules live below with lang_btn */
.st-key-theme_btn button{background:var(--surface-2)!important;border:1px solid var(--border)!important;color:var(--ink)!important;border-radius:50%!important;padding:0!important;width:32px!important;height:32px!important;}
.st-key-theme_btn button:hover{background:var(--surface)!important;border-color:var(--primary)!important;}
/* ── Upload dropzone card ── premium animated dropzone.
   Rest: dashed border + soft shadow, a glow breathing behind the icon, the
   upload arrow rising out of its tray. Hover/drag (the moment that matters):
   the card lifts and a gradient comet sweeps the perimeter to say "drop here". */
@property --dz-ang{syntax:"<angle>";initial-value:0deg;inherits:false;}
:is(.st-key-upload_card,.st-key-cr_card){position:relative;border:1.8px dashed var(--primary);border-radius:var(--r-xl);background:var(--surface);text-align:center;padding-bottom:28px;margin:4px 0 6px;box-shadow:var(--sh-1);transition:transform .3s ease,box-shadow .3s ease,border-color .3s ease,background .25s ease;animation:dzEnter .55s cubic-bezier(.22,1,.36,1) both;}
:is(.st-key-upload_card,.st-key-cr_card)>[data-testid="stVerticalBlock"]{gap:0!important;position:relative;z-index:1;}
/* Gradient comet ring — masked to a 2px outline, revealed + spun on hover. */
:is(.st-key-upload_card,.st-key-cr_card)::after{content:"";position:absolute;inset:-2px;border-radius:inherit;padding:2px;pointer-events:none;opacity:0;transition:opacity .35s ease;
  background:conic-gradient(from var(--dz-ang),transparent 0deg,var(--primary) 55deg,var(--head-2) 110deg,transparent 175deg,transparent 360deg);
  -webkit-mask:linear-gradient(#000 0 0) content-box,linear-gradient(#000 0 0);-webkit-mask-composite:xor;mask-composite:exclude;
  animation:dzSpin 3.4s linear infinite;}
:is(.st-key-upload_card,.st-key-cr_card):hover{transform:translateY(-2px);box-shadow:var(--sh-2);border-color:var(--primary-700);}
:is(.st-key-upload_card,.st-key-cr_card):hover::after{opacity:1;}
/* JS-toggled drag-over state — more intense than hover */
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active{border-color:var(--primary)!important;border-style:solid!important;background:var(--primary-50)!important;transform:translateY(-3px)!important;box-shadow:var(--sh-2)!important;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active::after{opacity:1!important;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active .dz-icon{background:var(--primary)!important;border-color:var(--primary)!important;color:#fff!important;transform:scale(1.12) translateY(-4px)!important;box-shadow:var(--sh-3)!important;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active .dz-icon svg{color:#fff!important;stroke:#fff!important;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active .dz-glow{animation:none!important;opacity:1!important;transform:scale(1.5)!important;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active .dz-sub{opacity:0;}
/* Dual title: idle shown by default, drag title hidden; swap on drag-active */
.dz-title-drag{display:none;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active .dz-title-idle{display:none!important;}
:is(.st-key-upload_card,.st-key-cr_card).dz-drag-active .dz-title-drag{display:block!important;color:var(--primary)!important;}
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
:is(.st-key-upload_card,.st-key-cr_card):hover .dz-icon{transform:scale(1.08) translateY(-2px);border-color:var(--primary);box-shadow:var(--sh-2);}
.dz-title{font:700 1.08rem/1.2 var(--font);color:var(--ink);margin:0;transition:color .3s ease;}
:is(.st-key-upload_card,.st-key-cr_card):hover .dz-title{color:var(--primary);}
.dz-sub{font:500 .85rem/1.4 var(--font);color:var(--muted);margin:0;}
@keyframes dzEnter{from{opacity:0;transform:translateY(12px);}to{opacity:1;transform:none;}}
@keyframes dzSpin{to{--dz-ang:360deg;}}
@keyframes dzPulse{0%,100%{transform:scale(.8);opacity:.5;}50%{transform:scale(1.15);opacity:.9;}}
@keyframes dzArrow{0%,100%{transform:translateY(2px);opacity:.45;}50%{transform:translateY(-3px);opacity:1;}}
@media (prefers-reduced-motion:reduce){
  :is(.st-key-upload_card,.st-key-cr_card),.dz-glow,.dz-icon .dz-arrow{animation:none;}
  :is(.st-key-upload_card,.st-key-cr_card)::after{animation:none;}
}
/* Overlay the dz-header with a transparent clickable file input.
   The uploader is absolute, but Streamlit makes every stElementContainer
   position:relative — so without this the uploader anchors to its OWN
   container (which sits BELOW the dz-header) instead of the card, leaving
   the cloud icon with no dropzone behind it (clicks + file drops miss). Force
   the uploader's container static so the card becomes the offset parent and
   the overlay lands on top of the icon. */
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stElementContainer"]:has([data-testid="stFileUploader"]){position:static!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploader"]{position:absolute;top:0;left:0;right:0;height:175px;z-index:5;padding:0!important;margin:0!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDropzone"]{position:absolute;inset:0;background:transparent!important;border:none!important;box-shadow:none!important;padding:0!important;cursor:pointer;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDropzone"] *:not(button){visibility:hidden!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDropzone"] button{display:block!important;position:absolute!important;inset:0!important;width:100%!important;height:100%!important;opacity:0!important;cursor:pointer!important;border:none!important;background:transparent!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderFile"]{display:none!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stHorizontalBlock"]{padding:0 20px!important;justify-content:center!important;}
:is(.st-key-upload_card,.st-key-cr_card) :is([data-testid="stColumn"],[data-testid="column"]){padding:0!important;}
/* Step-1 empty state: two-button row. Left = "Upload CSV" CTA (.up-cta, visual
   only) with the invisible file_uploader overlaid inside .st-key-up_btn; right =
   the native sample button. The CTA container is the uploader's offset parent, so
   the overlay covers ONLY the CTA — the sample button stays clickable. Columns
   stack vertically on mobile portrait, each overlay following its own column. */
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stHorizontalBlock"]:has(:is(.st-key-up_btn,.st-key-cr_up_btn)){padding:22px 20px 6px!important;align-items:center!important;justify-content:center!important;gap:14px!important;flex-wrap:wrap!important;}
/* Shrink both columns to their button so the pair sits together (centered),
   not split across two half-width columns. Wraps on narrow phones. */
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stHorizontalBlock"]:has(:is(.st-key-up_btn,.st-key-cr_up_btn)) :is([data-testid="stColumn"],[data-testid="column"]){flex:0 0 auto!important;width:auto!important;min-width:0!important;display:flex!important;flex-direction:column!important;justify-content:center!important;}
/* Pin the CTA container to the button height so its column (which ALSO holds the
   invisible file-uploader element) is exactly 48px — same as the sample column —
   otherwise the uploader's residual height makes the CTA sit lower than the sample. */
:is(.st-key-up_btn,.st-key-cr_up_btn){position:relative;gap:0!important;width:fit-content;max-width:100%;height:48px!important;min-height:48px!important;display:flex;flex-direction:column;justify-content:center;}
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stElementContainer"]{margin:0!important;}
/* The CTA's own element container otherwise collapses to ~32px (Streamlit's emotion
   class wins on source-order tie), so the 48px .up-cta overflows downward and sits
   ~8px lower than the sample button. Pin it to 48px so the CTA fits exactly — both
   buttons then share one vertical center under the row's align-items:center. The
   uploader's element container (no .up-cta) stays 0-height as the absolute overlay. */
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stElementContainer"]:has(.up-cta){height:48px!important;display:flex;align-items:center;}
/* Streamlit gives stMarkdownContainer a default margin-bottom:-16px, which shrinks
   the stMarkdown flex item to 32px; align-items:center then offsets the 48px CTA 8px
   down. Zero the margin and let stMarkdown fill so the CTA sits flush at the top. */
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stMarkdownContainer"]{margin-bottom:0!important;}
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stMarkdown"]{height:48px!important;display:flex;align-items:center;}
.up-cta{display:flex;align-items:center;justify-content:center;gap:9px;
  height:48px;padding:0 22px;border-radius:16px;
  background:var(--cta-bg);border:1px solid var(--cta-bd);color:#fff;
  backdrop-filter:blur(16px) saturate(1.4);-webkit-backdrop-filter:blur(16px) saturate(1.4);
  font:700 1rem/1.2 var(--font);
  box-shadow:0 2px 12px var(--cta-sh),inset 0 1px 0 rgba(255,255,255,.18);
  user-select:none;pointer-events:none;transition:transform .2s ease,box-shadow .2s ease,filter .2s ease;}
/* Force white text on the dark-navy glass — markdown's -webkit-text-fill-color
   (ink) otherwise wins over plain color, so "CSV Yükle" rendered dark in light mode. */
.up-cta,.up-cta *{color:#fff!important;-webkit-text-fill-color:#fff!important;}
.up-cta svg{stroke:#fff!important;}
/* Hide the file_uploader's widget label leaking the "Upload CSV" string into the box. */
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stWidgetLabel"],:is(.st-key-up_btn,.st-key-cr_up_btn) label{display:none!important;}
.up-cta-ic{position:relative;width:20px;height:20px;display:grid;place-items:center;flex:0 0 auto;}
.up-cta-ic>svg,.up-cta-arrow{grid-area:1/1;}
.up-cta-ic>svg{width:20px;height:20px;}
.up-cta-arrow{display:grid;place-items:center;}
.up-cta-arrow>svg{width:20px;height:20px;}
:is(.st-key-up_btn,.st-key-cr_up_btn):hover .up-cta{filter:brightness(1.12);transform:translateY(-1px);box-shadow:0 6px 20px var(--cta-sh),inset 0 1px 0 rgba(255,255,255,.22);}
:is(.st-key-up_btn,.st-key-cr_up_btn):hover .up-cta-arrow{animation:ctaArrow .9s ease-in-out infinite;}
@keyframes ctaArrow{0%,100%{transform:translateY(1px);}50%{transform:translateY(-2px);}}
@media (prefers-reduced-motion:reduce){:is(.st-key-up_btn,.st-key-cr_up_btn):hover .up-cta-arrow{animation:none;}}
/* Scope the overlay to the CTA box (inset:0); more specific than the whole-card
   uploader rules above, so it wins regardless of source order. */
:is(.st-key-upload_card,.st-key-cr_card) :is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploader"]{position:absolute!important;inset:0!important;height:100%!important;width:100%!important;z-index:5;padding:0!important;margin:0!important;}
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderDropzone"]{position:absolute!important;inset:0!important;min-height:0!important;background:transparent!important;border:none!important;box-shadow:none!important;padding:0!important;cursor:pointer;}
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderDropzone"] *:not(button){visibility:hidden!important;}
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderDropzone"] button{display:block!important;position:absolute!important;inset:0!important;width:100%!important;height:100%!important;opacity:0!important;cursor:pointer!important;border:none!important;background:transparent!important;}
:is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderFile"]{display:none!important;}
/* Sample button keeps its global auto-width (sizes to its label), centered by the
   .st-key-load_sample flex wrapper — content-width per the button-width rule.
   Pin it to the CTA's height (48px) so the two buttons align as a matched pair. */
:is(.st-key-upload_card,.st-key-cr_card) :is(.st-key-load_sample,.st-key-cr_sample) button{height:48px!important;min-height:48px!important;padding-top:0!important;padding-bottom:0!important;}
/* Upload success / error state */
@keyframes uploadPop{0%{opacity:0;transform:scale(.6);}65%{transform:scale(1.12);}100%{opacity:1;transform:scale(1);}}
@keyframes uploadRise{0%{opacity:0;transform:translateY(10px);}100%{opacity:1;transform:translateY(0);}}
.upload-ok{display:flex;flex-direction:column;align-items:center;gap:6px;padding:20px 0 8px;}
.upload-ok .chk{width:52px;height:52px;border-radius:50%;background:var(--good-bg);border:2px solid var(--good-bd);display:grid;place-items:center;color:var(--good);animation:uploadPop .45s cubic-bezier(.34,1.56,.64,1) both;}
.upload-ok .chk svg{width:26px;height:26px;}
.upload-ok .ok-title{font:700 .98rem/1.2 var(--font);color:var(--good);margin:0;animation:uploadRise .3s .25s ease both;}
.upload-ok .ok-sub{font:500 .8rem/1.4 var(--font);color:var(--muted);margin:0;animation:uploadRise .3s .35s ease both;}
.upload-ok .ok-sub .ok-fname{font:500 .8rem/1.4 var(--mono);color:var(--muted);background:none;padding:0;border:none;border-radius:0;}
.upload-err{display:flex;flex-direction:column;align-items:center;gap:6px;padding:20px 16px 14px;background:var(--error-bg);border:1px solid var(--error-bd);border-radius:var(--r);margin:8px 0;}
.upload-err .err-icon{width:52px;height:52px;border-radius:50%;background:var(--error-bg);border:2px solid var(--error-bd);display:grid;place-items:center;color:var(--error);animation:uploadPop .45s cubic-bezier(.34,1.56,.64,1) both;}
.upload-err .err-icon svg{width:26px;height:26px;}
.upload-err .err-title{font:700 .98rem/1.2 var(--font);color:var(--error);margin:0;text-align:center;animation:uploadRise .3s .25s ease both;}
.upload-err .err-detail{font:400 .78rem/1.5 var(--mono);color:var(--error);background:var(--error-bd);border-radius:var(--r-sm);padding:6px 12px;margin:4px 0 0;max-width:100%;word-break:break-all;text-align:center;animation:uploadRise .3s .3s ease both;}
.upload-err .err-hint{font:400 .8rem/1.4 var(--font);color:var(--muted);margin:0;text-align:center;animation:uploadRise .3s .38s ease both;}
/* Invalid file type: red icon + text for the rejected-file row. Exclude the
   dropzone itself (it is ALSO a <section>) so the empty zone stays transparent
   — otherwise the error bg out-specifies the dropzone rule and paints it red. */
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploader"] section:not([data-testid="stFileUploaderDropzone"]){background:var(--error-bg)!important;border:1px solid var(--error-bd)!important;border-radius:var(--r-sm)!important;margin:4px 12px!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploader"] section:not([data-testid="stFileUploaderDropzone"]) svg{color:var(--error)!important;fill:var(--error)!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploader"] section:not([data-testid="stFileUploaderDropzone"]) small{color:var(--error)!important;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDeleteBtn"]{color:var(--error)!important;opacity:.75;}
:is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDeleteBtn"]:hover{opacity:1;}
/* "Try with sample dataset" — auto-width (fits its label), centered in the card;
   the primary gradient already applies. A light sheen sweeps across on hover so
   the call-to-action feels alive. */
:is(.st-key-load_sample,.st-key-cr_sample),:is(.st-key-load_sample,.st-key-cr_sample) .stButton{display:flex;justify-content:center;width:100%;}
:is(.st-key-load_sample,.st-key-cr_sample){position:relative;z-index:20;}
:is(.st-key-load_sample,.st-key-cr_sample) button{position:relative;overflow:hidden;width:auto!important;padding:12px 40px!important;}
:is(.st-key-load_sample,.st-key-cr_sample) button::after{content:"";position:absolute;top:0;left:-130%;width:60%;height:100%;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.28),transparent);transform:skewX(-18deg);transition:left .6s ease;}
:is(.st-key-load_sample,.st-key-cr_sample) button:hover::after{left:150%;}
@media (prefers-reduced-motion:reduce){:is(.st-key-load_sample,.st-key-cr_sample) button::after{transition:none;}}
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
/* Only the OUTER baseweb wrapper carries a border; the inner base-input stays
   transparent. Painting both (the old rule) drew a box-inside-a-box — the seam
   that made the stepper read as cheap. One soft --border hairline, not the heavy
   --faint mid-gray. */
[data-testid="stTextInput"] [data-baseweb="input"],
[data-testid="stNumberInput"] [data-baseweb="input"]{
  background:var(--surface)!important;border:1px solid var(--border)!important;border-radius:12px!important;
  overflow:hidden!important;box-shadow:0 1px 2px rgba(16,24,40,.05)!important;
  transition:border-color .18s ease,box-shadow .18s ease;}
[data-testid="stTextInput"] [data-baseweb="base-input"],
[data-testid="stNumberInput"] [data-baseweb="base-input"]{
  background:transparent!important;border:none!important;border-radius:0!important;}
[data-testid="stTextInput"] input,[data-testid="stNumberInput"] input{
  background:transparent!important;color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-testid="stTextInput"] input::placeholder,[data-testid="stNumberInput"] input::placeholder{color:var(--faint)!important;}
[data-testid="stTextInput"] [data-baseweb="input"]:focus-within{
  border-color:var(--primary)!important;box-shadow:0 0 0 3px var(--primary-50)!important;}
[data-testid="stNumberInput"] label{white-space:nowrap!important;}

/* ── Quantity selector — premium rounded pill (st.number_input) ───────────────
   The native ± steppers ship in a sibling group div AFTER [data-baseweb="input"]
   (step-down then step-up). We promote stNumberInputContainer to the one rounded
   pill surface and re-order its children into  −  ·  value  ·  +  : step-down on
   the left, the centred field in the middle, step-up on the right — a true
   quantity stepper, not an input with side buttons. Targeted by the STABLE
   data-testids (stNumberInputContainer / StepDown / StepUp), never the churny
   emotion classes; the step-button wrapper is reached via :has() so a class
   rename can't break the layout. */
[data-testid="stNumberInputContainer"]{
  display:flex!important;align-items:stretch!important;gap:0!important;
  max-width:170px!important;background:var(--surface)!important;
  border:1px solid var(--border)!important;border-radius:999px!important;
  box-shadow:var(--sh-1)!important;overflow:hidden!important;
  transition:border-color .18s ease,box-shadow .18s ease;}
[data-testid="stNumberInputContainer"]:hover{
  border-color:var(--primary-100)!important;box-shadow:var(--sh-2)!important;}
[data-testid="stNumberInputContainer"]:focus-within{
  border-color:var(--primary)!important;
  box-shadow:0 0 0 3px var(--primary-50),var(--sh-1)!important;}
/* inner field wrapper: shed the shared text-input chrome (border/shadow/cap) and
   take the centre slot; neutralise the shared :focus-within ring so the pill — not
   the bare field inside it — shows focus. */
[data-testid="stNumberInput"] [data-baseweb="input"]{
  background:transparent!important;border:none!important;border-radius:0!important;
  box-shadow:none!important;max-width:none!important;min-width:0!important;
  flex:1 1 auto!important;order:1!important;}
[data-testid="stNumberInput"] [data-baseweb="input"]:focus-within{
  border-color:transparent!important;box-shadow:none!important;}
[data-testid="stNumberInput"] input{
  text-align:center!important;font:700 1.06rem/1 var(--font)!important;
  color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;
  letter-spacing:-.01em;padding:0 2px!important;}
/* dissolve the step-button wrapper so both buttons become direct flex children
   of the pill (display:contents), then place one on each end via order. */
[data-testid="stNumberInputContainer"]>div:has(>[data-testid="stNumberInputStepDown"]){
  display:contents!important;}
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepDown"],
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepUp"]{
  background:transparent!important;border:none!important;border-radius:0!important;
  box-shadow:none!important;color:var(--muted)!important;
  width:44px!important;min-width:44px!important;flex:0 0 44px!important;
  align-self:stretch!important;display:grid!important;place-items:center!important;
  cursor:pointer!important;opacity:.8;
  transition:background .16s ease,color .16s ease,opacity .16s ease,transform .12s ease;}
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepDown"]{order:0!important;}
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepUp"]{order:2!important;}
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepDown"]:hover,
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepUp"]:hover{
  background:var(--primary-50)!important;color:var(--primary)!important;opacity:1;}
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepDown"]:active,
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepUp"]:active{
  background:var(--primary-100)!important;color:var(--primary)!important;transform:scale(.9);}
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepDown"]:disabled,
[data-testid="stNumberInput"] button[data-testid="stNumberInputStepUp"]:disabled{
  opacity:.3!important;cursor:not-allowed!important;background:transparent!important;color:var(--muted)!important;}
[data-testid="stNumberInput"] button svg{width:13px!important;height:13px!important;}
@media (prefers-reduced-motion:reduce){
  [data-testid="stNumberInputContainer"],
  [data-testid="stNumberInput"] button{transition:none!important;}}
/* Selectbox closed control + its caret. */
[data-testid="stSelectbox"] [data-baseweb="select"]>div:first-child{
  background:var(--surface)!important;border:1.5px solid var(--faint)!important;border-radius:10px!important;color:var(--ink)!important;}
[data-testid="stSelectbox"] [data-baseweb="select"] [data-baseweb="select-value-container"] *{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-testid="stSelectbox"] [data-baseweb="select"] svg{fill:var(--muted)!important;}
/* Multiselect control — same border/surface as selectbox. */
[data-testid="stMultiSelect"] [data-baseweb="select"]>div:first-child{
  background:var(--surface)!important;border:1.5px solid var(--faint)!important;border-radius:10px!important;}
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="select-value-container"] *{color:var(--ink)!important;-webkit-text-fill-color:var(--ink)!important;}
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"]{
  background:var(--cta-bg)!important;border:none!important;border-radius:999px!important;
  color:#fff!important;-webkit-text-fill-color:#fff!important;}
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] *{color:#fff!important;-webkit-text-fill-color:#fff!important;}
[data-testid="stMultiSelect"] [data-baseweb="select"] [data-baseweb="tag"] svg{fill:#fff!important;}
[data-testid="stMultiSelect"] [data-baseweb="select"] svg{fill:var(--muted)!important;}
/* Selectbox open menu — themed in brand_css() via _popover_css() with literal
   token values so the portal dropdown is always readable in dark mode. */
/* Checkbox label + box border follow the theme; the tick uses the brand primary. */
[data-testid="stCheckbox"] label,[data-testid="stCheckbox"] label *{color:var(--ink)!important;}
[data-testid="stCheckbox"] [data-baseweb="checkbox"]>span:first-of-type{border-color:var(--border)!important;}

/* st.toggle — track + thumb themed to follow light/dark tokens.
   Streamlit renders st.toggle as stCheckbox but with a div (not span) as the
   first child of label[data-baseweb="checkbox"] — regular checkboxes use span,
   so `> div:first-child` targets only toggle tracks without touching checkboxes.
   aria-checked on the input reflects the on-state; :has() propagates it to track. */
[data-testid="stCheckbox"] label[data-baseweb="checkbox"]>div:first-child{
  background:var(--faint)!important;border-radius:999px!important;
  transition:background .2s ease,box-shadow .2s ease;}
[data-testid="stCheckbox"] label[data-baseweb="checkbox"]:has(input[aria-checked="true"])>div:first-child{
  background:var(--primary)!important;
  box-shadow:0 0 0 3px var(--primary-50)!important;}
[data-testid="stCheckbox"] label[data-baseweb="checkbox"]>div:first-child>div{
  background:#fff!important;box-shadow:0 1px 4px rgba(0,0,0,.35)!important;}

/* ── Instructor availability heatmap ── when2meet-style hourly grid: time rows ×
   day columns, tap a cell to block that hour for the instructor. Mirrors the result
   timetable's hour×day shape so the picker and the schedule read in one language.
   Each cell is a Streamlit checkbox restyled into a flat tile that fills amber when
   blocked (:has(input:checked)); the native box + label are hidden — the tile colour
   is the only signal. Scoped to .st-key-av_hm. Columns are forced nowrap + min-width:0
   so the grid never stacks on a phone (the cells just shrink to fit). */
.st-key-av_hm{background:var(--card);border:1px solid var(--card-bd);
  border-radius:var(--r-lg);box-shadow:var(--sh-1);padding:12px 12px 9px;margin:2px 0 6px;overflow:hidden;}
.st-key-av_hm [data-testid="stVerticalBlock"]{gap:4px!important;}
.st-key-av_hm [data-testid="stHorizontalBlock"]{flex-wrap:nowrap!important;gap:4px!important;align-items:stretch;}
.st-key-av_hm [data-testid="stColumn"],.st-key-av_hm [data-testid="column"]{min-width:0!important;flex:1 1 0!important;}
/* a column's element wrapper is content-sized by default — stretch it so the cell
   (checkbox) fills the column rather than collapsing to the hidden box's 16px. */
.st-key-av_hm [data-testid="stElementContainer"]{width:100%!important;}
/* first column of every row is the narrow time gutter */
.st-key-av_hm [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:first-child,
.st-key-av_hm [data-testid="stHorizontalBlock"]>[data-testid="column"]:first-child{flex:0 0 46px!important;}
.hm-dh{text-align:center;font:700 .72rem/1 var(--font);color:var(--ink-2);padding:2px 0 5px;}
.hm-tl{font:600 .64rem/1 var(--mono);color:var(--faint);text-align:right;padding-right:7px;
  height:30px;display:flex;align-items:center;justify-content:flex-end;white-space:nowrap;}
.hm-mid{height:1px;background:var(--warn-bd);opacity:.7;margin:2px 0;border-radius:1px;}
/* cell = restyled checkbox tile */
.st-key-av_hm [data-testid="stCheckbox"]{width:100%;}
.st-key-av_hm [data-testid="stCheckbox"] label{
  display:flex!important;width:100%;height:30px;border-radius:7px;cursor:pointer;
  background:var(--surface-2);border:1px solid var(--border);
  transition:background .13s ease,border-color .13s ease;}
.st-key-av_hm [data-testid="stCheckbox"] label:hover{border-color:var(--primary-100);background:var(--surface);}
.st-key-av_hm [data-testid="stCheckbox"] label:focus-within{outline:2px solid var(--primary);outline-offset:1px;}
/* hide the native box + label text */
.st-key-av_hm [data-baseweb="checkbox"]>span:first-of-type{display:none!important;}
.st-key-av_hm [data-testid="stCheckbox"] [data-testid="stWidgetLabel"]{display:none!important;}
/* blocked = solid amber tile */
.st-key-av_hm [data-testid="stCheckbox"] label:has(input:checked){
  background:var(--warn);border-color:var(--warn);box-shadow:0 2px 7px -2px var(--warn);}
.st-key-av_hm [data-testid="stCheckbox"] label:has(input:checked):hover{background:var(--warn);border-color:var(--warn-bd);}
@media (prefers-reduced-motion:reduce){.st-key-av_hm [data-testid="stCheckbox"] label{transition:none;}}
.st-key-av_hm .stButton{margin-top:10px;}
/* Legend + count line under the grid */
.hm-leg{display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center;font:500 .74rem/1 var(--font);
  color:var(--muted);margin:2px 2px 11px;}
.hm-leg span{display:inline-flex;align-items:center;}
.hm-leg i{width:13px;height:13px;border-radius:4px;display:inline-block;margin-right:6px;}
.hm-leg .av{background:var(--surface-2);border:1px solid var(--border);}
.hm-leg .bl{background:var(--warn);}
.hm-leg b{color:var(--warn);font-weight:700;}
/* Blocked-slots overview — one warm-chipped row per restricted instructor */
.av-sum-who{font:600 .78rem/1.3 var(--font);color:var(--ink-2);margin-right:2px;word-break:break-word;}
/* Interactive chip-buttons (replace static .av-chip spans) */
[class*="st-key-av_row_"]>[data-testid="stVerticalBlock"]{display:flex!important;flex-wrap:wrap!important;align-items:center!important;gap:7px!important;padding:9px 12px!important;background:var(--surface-2)!important;border:1px solid var(--border-2)!important;border-radius:10px!important;margin-bottom:8px!important;}
[class*="st-key-av_row_"] [data-testid="stMarkdownContainer"]{flex:0 0 auto!important;margin:0!important;}
[class*="st-key-av_row_"] [data-testid="stMarkdownContainer"] p{margin:0!important;}
[class*="st-key-av_rm_"],[class*="st-key-av_rm_"]>[data-testid="stButton"]{display:inline-flex!important;flex:0 0 auto!important;}
[class*="st-key-av_rm_"] [data-testid="stButton"]>button{font:600 .62rem/1 var(--mono)!important;padding:4px 8px!important;border-radius:6px!important;background:var(--warn-bg)!important;border:1px solid var(--warn-bd)!important;color:var(--warn)!important;white-space:nowrap!important;height:auto!important;min-height:0!important;line-height:1!important;transition:background .15s,color .15s,border-color .15s!important;}
[class*="st-key-av_rm_"] [data-testid="stButton"]>button:hover{background:rgba(239,68,68,.12)!important;border-color:#ef4444!important;color:#b91c1c!important;cursor:pointer!important;}
[class*="st-key-av_rm_"] [data-testid="stButton"]>button{display:flex!important;align-items:center!important;justify-content:space-between!important;gap:8px!important;}
[class*="st-key-av_rm_"] [data-testid="stButton"]>button::after{content:"✕";font-size:1rem;font-weight:900;line-height:1;margin-left:auto;color:transparent;transition:color .15s;}
[class*="st-key-av_rm_"] [data-testid="stButton"]>button:hover::after{color:#ef4444!important;}

/* Misc Streamlit chrome that should follow the theme */
hr{border-color:var(--border) !important;}
[data-testid="stWidgetLabel"] p,[data-testid="stCaptionContainer"],.stRadio label{color:var(--ink);}
[data-testid="stCaptionContainer"] code{font:600 .9rem/1.55 var(--mono);color:var(--ink-2);background:none;padding:0;}
[data-baseweb="slider"] [role="slider"]{background:var(--primary) !important;}
[data-testid="stAlert"]{border-radius:var(--r);}

/* ── Default segmented control: readable text pills (e.g. preference weights) ── */
[data-testid="stButtonGroup"]>div{display:inline-flex;flex-wrap:wrap;align-items:center;gap:6px;}
[data-testid="stBaseButton-segmented_control"],
[data-testid="stBaseButton-segmented_controlActive"]{
  border:1px solid var(--border)!important;background:var(--surface-2)!important;
  box-shadow:var(--sh-1)!important;border-radius:999px!important;
  padding:6px 16px!important;width:auto!important;min-width:0!important;
  white-space:nowrap;display:inline-flex!important;align-items:center;justify-content:center;
  font:600 .84rem/1 var(--font)!important;color:var(--muted)!important;
  transition:background .16s,color .16s,box-shadow .16s,transform .16s;}
[data-testid="stBaseButton-segmented_control"] p,
[data-testid="stBaseButton-segmented_controlActive"] p{
  font:inherit!important;color:inherit!important;letter-spacing:-.005em;}
[data-testid="stBaseButton-segmented_control"]:hover{
  background:var(--surface)!important;color:var(--primary)!important;
  border-color:var(--primary)!important;box-shadow:var(--sh-2)!important;
  transform:translateY(-1px);}
[data-testid="stBaseButton-segmented_controlActive"]{
  background:linear-gradient(135deg,var(--primary) 0%,#4456B5 100%)!important;
  color:#fff!important;border-color:transparent!important;
  box-shadow:0 1px 2px rgba(31,43,103,.28),0 4px 12px -6px rgba(31,43,103,.5),
    inset 0 1px 0 rgba(255,255,255,.22)!important;}
[data-testid="stBaseButton-segmented_controlActive"] p{color:#fff!important;}
[data-testid="stBaseButton-segmented_controlActive"]:hover{filter:brightness(1.05);}

/* ── Premium language switch (st.segmented_control: 🇹🇷 TR | 🇬🇧 EN) ── */
/* Scoped to the top-bar control group so it never touches other segmented controls. */
/* Track: frameless — just hosts the two round flag buttons, like the theme toggle. */
.st-key-topctrls [data-testid="stButtonGroup"]{
  display:inline-flex;width:auto;align-items:center;
  gap:8px;padding:0;border:0;background:transparent;box-shadow:none;}
.st-key-topctrls [data-testid="stButtonGroup"]>div{display:inline-flex;flex-wrap:nowrap;align-items:center;gap:4px;}
/* Segments: round 32px buttons matching the theme toggle; flag emoji is the label. */
.st-key-topctrls [data-testid="stBaseButton-segmented_control"],
.st-key-topctrls [data-testid="stBaseButton-segmented_controlActive"]{
  border:1px solid var(--border)!important;background:var(--surface-2)!important;
  box-shadow:var(--sh-1)!important;
  border-radius:50%!important;width:32px!important;height:32px!important;
  min-width:32px!important;min-height:32px!important;padding:0!important;flex:none;
  display:inline-flex!important;align-items:center;justify-content:center;
  font:600 1rem/1 var(--font)!important;color:var(--muted)!important;
  transition:background .16s,color .16s,box-shadow .16s,transform .16s;}
.st-key-topctrls [data-testid="stBaseButton-segmented_control"] p,
.st-key-topctrls [data-testid="stBaseButton-segmented_controlActive"] p{
  font:inherit!important;color:inherit!important;letter-spacing:-.005em;}
/* Inactive hover — lift toward the surface without committing. */
.st-key-topctrls [data-testid="stBaseButton-segmented_control"]:hover{
  background:var(--surface)!important;color:var(--primary)!important;
  border-color:var(--primary)!important;box-shadow:var(--sh-2)!important;
  transform:translateY(-1px);}
/* Active segment — primary gradient, white text, soft lift. */
.st-key-topctrls [data-testid="stBaseButton-segmented_controlActive"]{
  background:linear-gradient(135deg,var(--primary) 0%,#4456B5 100%)!important;
  color:#fff!important;border-color:transparent!important;
  box-shadow:0 1px 2px rgba(31,43,103,.28),0 4px 12px -6px rgba(31,43,103,.5),
    inset 0 1px 0 rgba(255,255,255,.22)!important;}
.st-key-topctrls [data-testid="stBaseButton-segmented_controlActive"]:hover{filter:brightness(1.05);}

/* ── Right control group: theme button + lang switch on one tight row ──
   Flip the container's vertical block to a centered horizontal flex.
   Cover both self and descendant stVerticalBlock targets. Strip all default
   Streamlit padding/margin so controls sit flush. */
.st-key-topctrls,
.st-key-topctrls[data-testid="stVerticalBlock"],
.st-key-topctrls [data-testid="stVerticalBlock"]{
  flex-direction:row!important;align-items:center!important;
  justify-content:center!important;gap:8px!important;
  padding:0!important;margin:0!important;}
/* Let flex align-items:center on the column do the vertical centring; no manual
   nudge, so the 32px control buttons line up with the 40px-logo brand row. */
.st-key-topctrls{margin-top:0!important;}
.st-key-topctrls [data-testid="stElementContainer"]{
  width:auto!important;flex:none!important;padding:0!important;margin:0!important;}
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
  flex:1 1 auto!important;display:flex!important;align-items:center!important;}
.st-key-topbar [data-testid="stHorizontalBlock"]>[data-testid="stColumn"]:last-child{
  flex:0 0 auto!important;display:flex!important;align-items:center!important;
  justify-content:center!important;}

/* Desktop-only: nudge right controls down to balance the brand's -8px nudge up. */
@media (min-width:641px){
  .st-key-topctrls{transform:translateY(4px);}
}

/* Theme + language toggles — identical premium round icon buttons. Both are
   st.button (the lang switch shows the CURRENT language's flag; clicking toggles
   to the other). Streamlit's own rule has specificity 0031 (!important); we need
   to match or exceed it. Prefixing with .st-key-topctrls gives us 0031 too, and
   since our <style> is injected after Streamlit's own sheet, last wins on ties. */
.st-key-topctrls .st-key-theme_btn button[data-testid],
.st-key-topctrls .st-key-lang_btn button[data-testid]{
  width:32px!important;height:32px!important;min-width:32px!important;min-height:32px!important;
  padding:0!important;border-radius:50%!important;flex:none;
  display:inline-flex!important;align-items:center!important;justify-content:center!important;
  font-size:1.1rem!important;line-height:1!important;
  background:var(--surface-2)!important;border:1px solid var(--border)!important;
  color:var(--ink-2)!important;box-shadow:var(--sh-1)!important;
  transition:border-color .16s,color .16s,box-shadow .16s,transform .16s;}
/* Inner markdown div must not add size — collapse to point. */
.st-key-topctrls .st-key-theme_btn button[data-testid]>div,
.st-key-topctrls .st-key-lang_btn button[data-testid]>div{display:contents!important;padding:0!important;margin:0!important;}
.st-key-topctrls .st-key-theme_btn button[data-testid] p,
.st-key-topctrls .st-key-lang_btn button[data-testid] p{font-size:1.1rem!important;line-height:1!important;margin:0!important;padding:0!important;}
.st-key-topctrls .st-key-theme_btn button[data-testid]:hover,
.st-key-topctrls .st-key-lang_btn button[data-testid]:hover{
  border-color:var(--primary)!important;color:var(--primary)!important;
  box-shadow:var(--sh-2)!important;transform:translateY(-1px);}
/* Lang button shows the active language — subtle active ring. */
.st-key-topctrls .st-key-lang_btn button[data-testid]{
  border-color:var(--primary-100)!important;
  box-shadow:0 0 0 2px var(--primary-50),var(--sh-1)!important;}

/* Tooltips (hover + help "?") — ONE flat bubble, never a nested card. The help
   "?" tooltip is a [data-baseweb=tooltip] (NOT a popover). Its single visible
   surface is the `>div`; stTooltipContent is ONLY the inner text wrapper and
   must paint NOTHING. Giving the content its own box-shadow/border-radius draws
   a second rounded rect inset inside the bubble — a transparent node still casts
   its drop shadow — which is exactly the card-in-card look. So the bubble carries
   the lone background + soft even shadow, and the content is zeroed out. */
[data-baseweb="tooltip"]>div{
  background:var(--tt-bg)!important;color:var(--tt-ink)!important;
  border:none!important;border-radius:var(--r-sm)!important;
  box-shadow:0 6px 22px rgba(20,24,38,.16),0 1px 4px rgba(20,24,38,.10)!important;
  font:500 .78rem/1.35 var(--font)!important;padding:8px 12px!important;
  max-width:240px!important;}
[data-baseweb="tooltip"] [data-testid="stTooltipContent"],
[data-baseweb="tooltip"] [data-testid="stTooltipContent"] *{
  color:var(--tt-ink)!important;background:transparent!important;
  border:none!important;border-radius:0!important;box-shadow:none!important;}
[data-baseweb="tooltip"] [data-testid="stTooltipContent"]{padding:0!important;}
/* Widget labels: ? icon sits immediately after the label text.
   Streamlit renders .stTooltipIcon before <label> in the DOM → reorder.
   justify-content:flex-start prevents the icon drifting to the far right. */
[data-testid="stWidgetLabel"]{
  display:flex!important;flex-direction:row!important;
  align-items:center!important;gap:3px!important;flex-wrap:nowrap!important;
  justify-content:flex-start!important;}
[data-testid="stWidgetLabel"] label{order:0;flex:0 1 auto;}
[data-testid="stWidgetLabel"] .stTooltipIcon{order:1;flex:none;}

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
  .tt-brand .name{font-size:1.15rem;}
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
  :is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploader"]{
    position:static!important;height:auto!important;}
  :is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDropzone"]{
    position:relative!important;inset:auto!important;}
  :is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDropzone"] *:not(button){
    display:revert!important;visibility:visible!important;}
  :is(.st-key-upload_card,.st-key-cr_card) [data-testid="stFileUploaderDropzone"] button{
    position:static!important;inset:auto!important;
    width:auto!important;height:auto!important;opacity:1!important;}
  :is(.st-key-upload_card,.st-key-cr_card) .dz-header{padding:20px 16px 8px;}
  :is(.st-key-upload_card,.st-key-cr_card) .dz-title,:is(.st-key-upload_card,.st-key-cr_card) .dz-sub{display:none!important;}
  /* EXCEPTION to the flow-layout reset above: both cards' two-button CTA
     (.st-key-up_btn / .st-key-cr_up_btn) is a COMPACT overlay (not a full dz-header
     dropzone), so the "opaque dropzone blocks the cloud icon" concern doesn't
     apply. Re-pin its absolute overlay + hide the native dropzone text on mobile,
     or Streamlit's "Drop file here / Browse files" text leaks over the CTA and the
     sample button. Scoped under the card + the CTA container (0,4,0) so it
     out-specifies the :is(...) reset (0,2,0) and stays later in source order. */
  :is(.st-key-upload_card,.st-key-cr_card) :is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploader"]{
    position:absolute!important;inset:0!important;height:100%!important;width:100%!important;}
  :is(.st-key-upload_card,.st-key-cr_card) :is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderDropzone"]{
    position:absolute!important;inset:0!important;min-height:0!important;}
  :is(.st-key-upload_card,.st-key-cr_card) :is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderDropzone"] *:not(button){
    visibility:hidden!important;}
  :is(.st-key-upload_card,.st-key-cr_card) :is(.st-key-up_btn,.st-key-cr_up_btn) [data-testid="stFileUploaderDropzone"] button{
    position:absolute!important;inset:0!important;width:100%!important;height:100%!important;opacity:0!important;}
}

/* Blackout slot chips — warm amber "blocked time" tag */
.bl-chip{display:inline-flex;align-items:center;gap:7px;background:var(--warn-bg);border:1px solid var(--warn-bd);color:var(--warn);border-radius:999px;padding:5px 13px 5px 10px;font:600 .82rem/1 var(--font);white-space:nowrap;}
.bl-chip .bl-ic{flex:none;font-size:.78em;opacity:.75;letter-spacing:0;}
.bl-chip .bl-st{font:500 .7rem/1 var(--mono);opacity:.82;margin-left:2px;}
.bl-row{display:flex;align-items:center;gap:0;padding:3px 0;}
/* Blackout row: collapse columns so delete button sits right next to chip */
[data-testid="stHorizontalBlock"]:has(.bl-chip)>[data-testid="stColumn"]{flex:0 0 auto!important;width:auto!important;min-width:0!important;}
/* Red delete button in blackout rows */
[data-testid="stHorizontalBlock"]:has(.bl-chip) [data-testid="stColumn"]:last-child button{background:transparent!important;border:none!important;box-shadow:none!important;min-height:28px!important;height:28px!important;padding:0 6px!important;font-size:.9rem!important;font-weight:700!important;line-height:1!important;}
[data-testid="stHorizontalBlock"]:has(.bl-chip) [data-testid="stColumn"]:last-child button,
[data-testid="stHorizontalBlock"]:has(.bl-chip) [data-testid="stColumn"]:last-child button p,
[data-testid="stHorizontalBlock"]:has(.bl-chip) [data-testid="stColumn"]:last-child button span{color:var(--error)!important;}
[data-testid="stHorizontalBlock"]:has(.bl-chip) [data-testid="stColumn"]:last-child button:hover{background:transparent!important;box-shadow:none!important;opacity:.65!important;}

/* Footer: quiet attribution, centered, mono — sits flush at the page bottom. */
.tt-footer{margin-top:32px;padding:16px 12px 4px;border-top:1px solid var(--border);
  text-align:center;font:500 .74rem/1.5 var(--mono);color:var(--muted);}
.tt-footer a{color:var(--good);font-weight:600;text-decoration:none;}
.tt-footer a:hover{text-decoration:underline;text-underline-offset:3px;}

/* Unschedulable section cards (results view). */
.uns-list{display:flex;flex-direction:column;gap:8px;padding:4px 0;}
.uns-card{background:var(--error-bg);border:1px solid var(--error-bd);border-radius:12px;
  padding:12px 16px;display:flex;gap:12px;align-items:flex-start;}
.uns-dot{width:7px;height:7px;border-radius:50%;background:var(--error);flex:none;margin-top:5px;}
.uns-body{flex:1;min-width:0;}
.uns-head{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-bottom:5px;}
.uns-id{font:700 .84rem/1 var(--mono);color:var(--ink);}
.uns-iss{font:500 .74rem/1.45 var(--font);color:var(--muted);display:block;
  padding-left:10px;position:relative;}
.uns-iss::before{content:"·";position:absolute;left:1px;color:var(--error);font-weight:700;}
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


def success_banner_html(title: str, subtitle: str) -> str:
    """Animated green success banner (check + title + subtitle) shown inside an
    upload/dropzone card once data has been loaded."""
    return (
        f'<div class="upload-ok">'
        f'<div class="chk">{_CHECK_SVG}</div>'
        f'<p class="ok-title">{escape(title)}</p>'
        f'<p class="ok-sub"><code class="ok-fname">{escape(subtitle)}</code></p>'
        f'</div>'
    )


def upload_success_html(filename: str, n_rows: int, lang: str = DEFAULT_LANG) -> str:
    """Animated success banner shown inside the upload card after a file is loaded."""
    return success_banner_html(t("upload_loaded", lang, n=n_rows), filename)


def dropzone_html(lang: str = DEFAULT_LANG) -> str:
    """Custom upload card header: icon + title + subtitle. Rendered above the
    native st.file_uploader inside a :is(.st-key-upload_card,.st-key-cr_card) container; CSS strips
    the uploader's native chrome so the two read as one unified card."""
    title = escape(t("upload_dropzone_title", lang))
    drag_title = escape(t("upload_dropzone_drag", lang))
    sub = escape(t("upload_dropzone_sub", lang))
    return (
        f'<div class="dz-header">'
        f'<div class="dz-iconwrap"><span class="dz-glow"></span>'
        f'<div class="dz-icon">{_UPLOAD_TRAY_SVG}'
        f'<span class="dz-arrow">{_UPLOAD_ARROW_SVG}</span></div></div>'
        f'<p class="dz-title dz-title-idle">{title}</p>'
        f'<p class="dz-title dz-title-drag">{drag_title}</p>'
        f'<p class="dz-sub">{sub}</p>'
        f'</div>'
    )


def upload_cta_html(lang: str = DEFAULT_LANG) -> str:
    """Visual-only primary CTA ("Upload CSV") shown in the left half of the upload
    card's two-button row. It is purely decorative (``pointer-events:none``): the
    real click/drag target is the invisible ``st.file_uploader`` overlaid on top of
    it inside the ``.st-key-up_btn`` container, so clicking the CTA opens the file
    picker. The right half is the native "sample dataset" st.button."""
    label = escape(t("upload_cta_btn", lang))
    return (
        f'<div class="up-cta">'
        f'<span class="up-cta-ic">{_UPLOAD_TRAY_SVG}'
        f'<span class="up-cta-arrow">{_UPLOAD_ARROW_SVG}</span></span>'
        f'<span>{label}</span></div>'
    )


def dropzone_drag_js() -> str:
    """JS that lights up an upload card while a file is dragged over it — swaps the
    title to "release to upload" and tints the background (the visuals live in the
    ``.dz-drag-active`` CSS rules; this only toggles the class).

    Must be delivered via ``components.html`` (an iframe), NOT ``st.markdown``:
    Streamlit's DOMPurify strips inline ``<script>`` from markdown, so it would
    never run. From the iframe it reaches the app through ``window.parent`` and
    binds capture-phase listeners on the parent document; they re-query the cards
    on every event, so they keep working across reruns. The iframe is recreated on
    each rerun, so we first detach the previous run's now-stale handlers (stashed
    on ``window.parent.__dzHandlers``). Only cards that actually contain an active
    file-uploader dropzone light up — the post-upload success card is skipped."""
    return (
        '<script>(function(){'
        'var P=window.parent,D=P.document;'
        'if(P.__dzHandlers){'
        'D.removeEventListener("dragenter",P.__dzHandlers.on,true);'
        'D.removeEventListener("dragover",P.__dzHandlers.on,true);'
        'D.removeEventListener("dragleave",P.__dzHandlers.leave,true);'
        'D.removeEventListener("drop",P.__dzHandlers.end,true);'
        'D.removeEventListener("dragend",P.__dzHandlers.end,true);}'
        'function cards(){return D.querySelectorAll(".st-key-upload_card,.st-key-cr_card");}'
        'function isFile(e){var t=e.dataTransfer&&e.dataTransfer.types;'
        'return !!t&&Array.prototype.indexOf.call(t,"Files")>-1;}'
        # Highlight only when over the real (droppable) uploader zone, so the
        # "release to upload" invite never appears over the non-droppable
        # example table / sample button below it.
        'function zone(t){return t&&t.closest?t.closest(\'[data-testid="stFileUploaderDropzone"]\'):null;}'
        'function on(e){if(!isFile(e))return;var z=zone(e.target);if(!z)return;'
        'var c=z.closest(".st-key-upload_card,.st-key-cr_card");if(c)c.classList.add("dz-drag-active");}'
        'function leave(e){if(zone(e.relatedTarget))return;'
        'cards().forEach(function(c){c.classList.remove("dz-drag-active");});}'
        'function end(){cards().forEach(function(c){c.classList.remove("dz-drag-active");});}'
        'D.addEventListener("dragenter",on,true);'
        'D.addEventListener("dragover",on,true);'
        'D.addEventListener("dragleave",leave,true);'
        'D.addEventListener("drop",end,true);'
        'D.addEventListener("dragend",end,true);'
        'P.__dzHandlers={on:on,leave:leave,end:end};'
        '})();</script>'
    )


def eyebrow_html(n, label: str, key: str, sub: bool = False) -> str:
    """Section header: badge + gradient label + a permalink anchor that targets the
    section's ``#s-<key>`` scroll anchor (rendered by app._anchor). With ``sub=True``
    it renders a smaller, number-less sub-header (used for the sub-sections grouped
    under a single numbered step, e.g. the unified Data step)."""
    if sub:
        return (
            f'<div class="eyebrow sub"><span class="lbl">{escape(label)}</span>'
            f'<a class="anchor" href="#s-{escape(key)}" title="{escape(label)}" '
            f'aria-label="{escape(label)}">{_LINK_SVG}</a></div>'
        )
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
        f'<div class="glyph">{logo_img_html(32, _ICON_PATH)}</div>'
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


# Decorative hero animation blocks — (grid-column, grid-row, color, delay). A
# fixed, conflict-free tiling of the 5×5 mini grid; the CSS animates each block
# sliding into place. Cool indigo/violet to match the hero gradient, with two
# mint blocks echoing the "0 hard conflicts" promise (never red = conflict).
_HERO_ANIM_BLOCKS = (
    ("1", "1/3", "#8E9BF2", "0s"), ("2", "1", "#A78BF0", ".10s"),
    ("4", "1/3", "#6E78D8", ".20s"), ("3", "2/4", "#34D6AA", ".30s"),
    ("5", "2", "#B6A4F4", ".40s"), ("2", "3/5", "#7C89E8", ".50s"),
    ("1", "4", "#34D6AA", ".60s"), ("4", "4/6", "#9A8CF2", ".70s"),
    ("5", "5", "#7C89E8", ".80s"),
)


def hero_anim_html(lang: str = DEFAULT_LANG) -> str:
    """Decorative self-solving mini-timetable for the hero (see the
    ``.tt-hero-anim`` CSS). ``aria-hidden``; day labels follow ``lang`` so the
    grid header is localized (TR ``Pzt Sal…`` / EN ``Mon Tue…``)."""
    labels = DAY_LABELS.get(lang, DAY_LABELS[DEFAULT_LANG])
    days = "".join(f"<span>{escape(labels.get(d, d))}</span>" for d in DAYS_ORDER)
    blocks = "".join(
        f'<div class="blk" style="grid-column:{c};grid-row:{r};--c:{col};--d:{d}"></div>'
        for (c, r, col, d) in _HERO_ANIM_BLOCKS)
    return (
        f'<div class="tt-hero-anim" aria-hidden="true">'
        f'<div class="days">{days}</div>'
        f'<div class="board"><div class="cells">{"<i></i>" * 25}</div>'
        f'<div class="blocks">{blocks}</div>'
        f'<div class="sweep"></div></div></div>'
    )


def hero_html(lang: str = DEFAULT_LANG, chips=None) -> str:
    """Hero banner. ``chips`` is a list of ``(value, label, tone)`` (tone in
    {'', 'good', 'bad'}); when None the static proof chips are shown — so the
    hero turns into a live dashboard as data is loaded and solved (see
    ``ui_app.hero_chips``)."""
    if chips is None:
        chips = [
            (t("feat_input_v", lang), t("feat_input_label", lang), ""),
            (t("feat_conflict_v", lang), t("feat_conflict_label", lang), ""),
            (t("feat_pref_v", lang), t("feat_pref_label", lang), ""),
            (t("feat_export_v", lang), t("feat_export_label", lang), ""),
        ]
    cells = "".join(
        f'<div class="chip-stat {escape(tone)}"><span class="v">{escape(str(v))}</span>'
        f'<span class="l">{escape(label)}</span></div>'
        for (v, label, tone) in chips)
    return (
        f'<div class="tt-hero">'
        f'{hero_anim_html(lang)}'
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
                    numeric: Tuple[str, ...] = (),
                    pill_cols: Tuple[str, ...] = (),
                    pill_labels: dict = None) -> str:
    """Read-only themed table for tabular previews (uploaded courselist, room
    inventory). Rendered as our own HTML/CSS so it follows the in-app light/dark
    theme — unlike ``st.dataframe``, whose glide-grid canvas is painted from
    Streamlit's *native* (light) theme and cannot be re-themed from CSS.

    ``columns`` are header labels; ``rows`` are row sequences aligned to them.
    ``numeric`` lists column labels to right-align with tabular figures.
    ``pill_cols`` lists column labels whose cell values are CSS class names rendered
    as colored status pills; ``pill_labels`` maps class name → display text.
    The wrapper scrolls internally (both axes), capped at ``max_height`` px."""
    num = set(numeric)
    pills = set(pill_cols)
    _labels = pill_labels or {}
    head = "".join(
        f'<th class="num">{escape(str(c))}</th>' if c in num else f'<th>{escape(str(c))}</th>'
        for c in columns)
    if not rows:
        body = f'<tr><td class="tt-td-empty" colspan="{max(len(columns), 1)}">—</td></tr>'
    else:
        trs = []
        for r in rows:
            tds_parts = []
            for i, v in enumerate(r):
                col = columns[i] if i < len(columns) else ""
                v_str = "" if v is None else str(v)
                if col in pills:
                    label = _labels.get(v_str, v_str)
                    tds_parts.append(
                        f'<td><span class="st-pill {escape(v_str)}">{escape(label)}</span></td>')
                elif col in num:
                    tds_parts.append(f'<td class="num">{escape(v_str)}</td>')
                else:
                    tds_parts.append(f'<td>{escape(v_str)}</td>')
            trs.append(f'<tr>{"".join(tds_parts)}</tr>')
        body = "".join(trs)
    return (f'<div style="display:flex;justify-content:center">'
            f'<div class="tt-table-wrap" style="--tt-table-h:{int(max_height)}px">'
            f'<table class="tt-data"><thead><tr>{head}</tr></thead>'
            f'<tbody>{body}</tbody></table></div></div>')


_IMP_STATUS_LABEL = {
    "ok": "import_status_ok", "dup": "import_status_dup",
    "dup_file": "import_status_dup_file", "err_code": "import_status_err_code",
    "err_hours": "import_status_err_hours",
}
# Columns shown in the import preview (canonical field -> i18n-free short header).
_IMP_COLS = ("Course Code", "Course Name", "Section No", "T", "P", "L",
             "Instructor Name", "Instructor Email", "~Students",
             "Section Capacity", "Year", "Part-time", "Room Type", "Fixed", "Dept")
_IMP_NUM = {"T", "P", "L", "~Students", "Section Capacity", "Year"}


_REQUIRED_COURSE_FIELDS = (
    "Course Code", "Course Name", "Dept",
    "Section No", "Instructor Name",
    "T", "P", "L",
    "Section Capacity",
)


def detected_columns_html(detected: list, lang: str = DEFAULT_LANG,
                          required: tuple | None = None) -> str:
    """The "detected columns" chip row inside a card, with a minimum-requirements
    banner. Green chips = header-matched; dashed-orange = positional fallback.
    ``detected`` = ``[{field, label, source}]`` from ``csv_import.map_columns``."""
    if not detected:
        return ""

    if required is None:
        required = _REQUIRED_COURSE_FIELDS

    def _chip(d):
        is_pos = d["source"] != "header"
        tag = (f'<span class="tag">{t("import_positional", lang)}</span>'
               if is_pos else "")
        field_display = escape(field_label(str(d["field"]), lang))
        return (f'<span class="col{" pos" if is_pos else ""}">'
                f'<i class="dot"></i>'
                f'<b>{field_display}</b>'
                f'<span class="arw">→</span>'
                f'<em>{escape(str(d["label"]))}</em>{tag}</span>')

    chips = "".join(_chip(d) for d in detected)
    n_match = sum(1 for d in detected if d["source"] == "header")
    count = f'<span class="imp-detect-count">{n_match}/{len(detected)}</span>'

    detected_by_field = {d["field"]: d for d in detected}
    # A header row exists if at least one column matched by name. Positional
    # fallback is the *expected* path for a header-less file, but on a file that
    # does have a header it means we could not recognize a required column's
    # name and guessed by position — a low-confidence mapping worth flagging.
    has_header = any(d["source"] == "header" for d in detected)
    missing_req = [f for f in required if f not in detected_by_field]
    guessed_req = [] if missing_req else [
        f for f in required
        if has_header and detected_by_field[f]["source"] != "header"]
    _icon_met = ('<svg class="imp-req-icon" viewBox="0 0 16 16" fill="none" '
                 'xmlns="http://www.w3.org/2000/svg">'
                 '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>'
                 '<path d="M4.5 8.5l2.5 2.5 4-5" stroke="currentColor" '
                 'stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>'
                 '</svg>')
    _icon_unmet = ('<svg class="imp-req-icon" viewBox="0 0 16 16" fill="none" '
                   'xmlns="http://www.w3.org/2000/svg">'
                   '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>'
                   '<path d="M5.5 5.5l5 5M10.5 5.5l-5 5" stroke="currentColor" '
                   'stroke-width="1.5" stroke-linecap="round"/>'
                   '</svg>')
    # Soft "i" glyph: this state is a "please verify", not an error.
    _icon_warn = ('<svg class="imp-req-icon" viewBox="0 0 16 16" fill="none" '
                  'xmlns="http://www.w3.org/2000/svg">'
                  '<circle cx="8" cy="8" r="7" stroke="currentColor" stroke-width="1.5"/>'
                  '<path d="M8 7.3v4" stroke="currentColor" stroke-width="1.5" '
                  'stroke-linecap="round"/>'
                  '<path d="M8 4.6v.1" stroke="currentColor" stroke-width="1.7" '
                  'stroke-linecap="round"/>'
                  '</svg>')
    req_fields_str = escape(" · ".join(field_label(f, lang) for f in required))
    if missing_req:
        tone, icon = "unmet", _icon_unmet
        cols = escape(", ".join(field_label(f, lang) for f in missing_req))
        msg = t("import_min_unmet", lang, cols=cols)
    elif guessed_req:
        # Show the guessed column number so the user can verify at a glance
        # ("is column 10 really Section Capacity?") without scrolling the table.
        tone, icon = "warn", _icon_warn
        def _gcol(f):
            m = re.search(r"(\d+)", str(detected_by_field[f]["label"]))
            col = (t("import_col_n", lang, n=m.group(1)) if m
                   else str(detected_by_field[f]["label"]))
            return f"{field_label(f, lang)} → {col}"
        cols = escape(", ".join(_gcol(f) for f in guessed_req))
        msg = t("import_min_warn", lang, cols=cols)
    else:
        tone, icon = "met", _icon_met
        msg = t("import_min_met", lang)
    if tone == "met":
        met_badge = f'<span class="imp-req-met">{msg}</span>'
        req_val = (f'<span class="imp-req-val {tone}">'
                   f'<span class="imp-req-fields">{req_fields_str}</span>'
                   f'</span>')
    else:
        met_badge = ""
        req_val = (f'<span class="imp-req-val {tone}">'
                   f'<span class="imp-req-fields">{req_fields_str}</span>'
                   f'{msg}</span>')

    req_row = (f'<div class="imp-req-row {tone}">'
               f'{icon}'
               f'{met_badge}'
               f'<span class="imp-req-lbl">{t("import_min_req", lang)}</span>'
               f'{req_val}</div>')

    return (f'<div class="imp-detect-card">'
            f'<div class="imp-detect"><div class="imp-detect-head">'
            f'<span class="lbl">{t("import_detected", lang)}</span>'
            f'{count}</div><div class="imp-cols">{chips}</div></div>'
            f'{req_row}'
            f'</div>')


def import_stats_html(stats: dict, lang: str = DEFAULT_LANG) -> str:
    """Valid / duplicate / error / total badge row. Shared by the course import
    preview and the Classrooms step."""
    def _badge(n, key, tone):
        return (f'<span class="imp-badge {tone}"><span class="n">{n}</span>'
                f'{t(key, lang)}</span>')
    badges = [_badge(stats.get("valid", 0), "import_valid", "good")]
    if stats.get("duplicate", 0):
        badges.append(_badge(stats["duplicate"], "import_duplicate", "warn"))
    if stats.get("error", 0):
        badges.append(_badge(stats["error"], "import_error", "bad"))
    badges.append(_badge(stats.get("total", 0), "import_total", ""))
    return f'<div class="imp-stats">{"".join(badges)}</div>'


def import_preview_html(report: dict, lang: str = DEFAULT_LANG) -> str:
    """Render the VERA-style import preview: detected-column chips, stat badges
    and a per-row preview table with colored status pills. ``report`` is the dict
    from ``csv_import.parse_courselist``."""
    rows = report.get("rows", [])
    detected = report.get("detected_columns", [])
    detect_html = detected_columns_html(detected, lang)
    stats_html = import_stats_html(report.get("stats", {}), lang)

    # Only preview columns that were actually mapped from the file. With a header,
    # unmatched canonical fields are absent from ``detected_columns`` — showing
    # them as all-"—" columns is noise. Fall back to the full set if detection is
    # empty (defensive; shouldn't happen for a parsed report).
    detected_fields = {d["field"] for d in detected}
    cols = tuple(c for c in _IMP_COLS if c in detected_fields) or _IMP_COLS

    head = (f'<th class="num">{t("import_col_row", lang)}</th>'
            + "".join((f'<th class="num">{escape(field_label(c, lang))}</th>'
                       if c in _IMP_NUM
                       else f'<th>{escape(field_label(c, lang))}</th>')
                      for c in cols)
            + f'<th>{t("import_col_status", lang)}</th>')
    trs = []
    for r in rows:
        status = r.get("status", "ok")
        rcls = (" row-dup" if status == "duplicate"
                else " row-err" if status == "error" else "")
        tds = [f'<td class="num">{escape(str(r.get("row_num", "")))}</td>']
        for c in cols:
            cls = ' class="num"' if c in _IMP_NUM else ""
            tds.append(f'<td{cls}>{escape(str(r.get(c, "") or "—"))}</td>')
        label = t(_IMP_STATUS_LABEL.get(r.get("status_label", ""), "import_status_ok"), lang)
        tds.append(f'<td><span class="st-pill {escape(status)}">{escape(label)}</span></td>')
        trs.append(f'<tr class="{rcls.strip()}">{"".join(tds)}</tr>')
    body = "".join(trs) or (
        f'<tr><td class="tt-td-empty" colspan="{len(cols) + 2}">—</td></tr>')

    table = (f'<div class="tt-table-wrap" style="--tt-table-h:360px">'
             f'<table class="tt-data"><thead><tr>{head}</tr></thead>'
             f'<tbody>{body}</tbody></table></div>')
    return detect_html + stats_html + table


def _block_html(a: dict, is_start: bool) -> str:
    color = block_color(a)
    is_lab = "lab" in str(a.get("block_kind", "")).lower()
    is_prat = not is_lab and (a.get("section_p") or 0) > 0
    klass = "tt-blk" + (" lab" if is_lab else "") + ("" if is_start else " cont")
    if is_lab:
        tag = '<span class="tag">LAB</span>'
    elif is_prat:
        tag = '<span class="tag prat">PRAT</span>'
    else:
        tag = ""
    section = escape(str(a.get("section_id") or a.get("course_code", "")))
    instr_name = str(a.get("instructor_name", ""))
    instr_id = str(a.get("instructor_id", ""))
    # Show "Name (email)" when both are present and email looks like an address
    if instr_name and instr_id and "@" in instr_id:
        instructor = escape(f"{instr_name} ({instr_id})")
    else:
        instructor = escape(instr_name or instr_id)
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


_UNSCHED_REASON = {
    "tr": {
        "no room with sufficient capacity": "Yeterli kapasiteli derslik bulunamadı",
        "block longer than daily time window": "Blok süresi günlük zaman penceresini aşıyor",
    },
    "en": {
        "no room with sufficient capacity": "No room with sufficient capacity",
        "block longer than daily time window": "Block longer than daily time window",
    },
}


def unschedulable_html(items: list, lang: str = DEFAULT_LANG) -> str:
    """Premium card list for sections that could not be scheduled."""
    reasons = _UNSCHED_REASON.get(lang, _UNSCHED_REASON["en"])
    students_label = "öğrenci" if lang == "tr" else "students"
    cards = []
    for s in items:
        sid = escape(str(s.get("section_id", "")))
        students = s.get("students", 0)
        issues = s.get("issues", [])
        seen_reasons: set = set()
        unique_issues = [(blk, r) for blk, r in issues if not (r in seen_reasons or seen_reasons.add(r))]
        iss_html = "".join(
            f'<span class="uns-iss">{escape(reasons.get(reason, reason))}</span>'
            for _, reason in unique_issues
        )
        cards.append(
            f'<div class="uns-card">'
            f'<div class="uns-dot"></div>'
            f'<div class="uns-body">'
            f'<div class="uns-head">'
            f'<span class="uns-id">{sid}</span>'
            f'<span class="pill">{students} {students_label}</span>'
            f'</div>'
            f'{iss_html}'
            f'</div></div>'
        )
    return f'<div class="uns-list">{"".join(cards)}</div>'


def week_grid_html(schedule: dict, hour_lo: int = 9, hour_hi: int = 21,
                   lang: str = DEFAULT_LANG) -> str:
    grid = build_week_grid(schedule, hour_lo, hour_hi)
    if not schedule.get("assignments"):
        return (f'<div class="tt-wrap"><div class="tt-empty">'
                f'{t("grid_empty", lang)}</div></div>')
    days = DAY_LABELS_FULL.get(lang, DAY_LABELS_FULL[DEFAULT_LANG])
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
