# app.py (repo root) — run with: PYTHONPATH=src streamlit run app.py
# Single-page premium flow: app bar + step indicator + hero, then the five
# section renderers shown progressively (Solve/Results gated on prerequisites).
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_style import brand_css, appbar_html, stepper_html, hero_html
from timetabling.ui_app import get_lang, get_theme, theme_toggle, lang_selector_bar
from timetabling.i18n import t
from views import upload, review, classrooms, solve, results

_ICON = os.path.join(os.path.dirname(__file__), "assets", "icon.svg")
st.set_page_config(page_title="Course Timetabling", page_icon=_ICON, layout="wide")

# Session defaults
st.session_state.setdefault("courses", [])
st.session_state.setdefault("classrooms", [dict(r) for r in DEFAULT_CLASSROOMS])
st.session_state.setdefault("result", None)
st.session_state.setdefault("lang", "tr")
st.session_state.setdefault("theme", "light")

st.markdown(brand_css(get_theme()), unsafe_allow_html=True)

has_courses = bool(st.session_state["courses"])
has_result = st.session_state["result"] is not None

# --- App bar: brand + context (HTML) on the left, controls (widgets) on the right
lang = get_lang()
ctx = (t("appbar_loaded", lang, n=len(st.session_state["courses"]))
       if has_courses else t("appbar_waiting", lang))
bar = st.columns([6, 1, 1.4], vertical_alignment="center")
with bar[0]:
    st.markdown(appbar_html(lang, ctx, live=has_courses), unsafe_allow_html=True)
with bar[1]:
    theme_toggle()
with bar[2]:
    lang = lang_selector_bar()

# --- Step indicator
def _solve_status() -> str:
    if not has_courses:
        return "locked"
    return "done" if has_result else "active"

steps = [
    {"key": "upload", "label": t("step_upload", lang),
     "status": "done" if has_courses else "active"},
    {"key": "review", "label": t("step_review", lang),
     "status": "done" if has_courses else "locked"},
    {"key": "classrooms", "label": t("step_classrooms", lang),
     "status": "done" if has_courses else "locked"},
    {"key": "solve", "label": t("step_solve", lang), "status": _solve_status()},
    {"key": "results", "label": t("step_results", lang),
     "status": "active" if has_result else "locked"},
]
st.markdown(stepper_html(steps, lang), unsafe_allow_html=True)

# --- Hero
st.markdown(hero_html(lang), unsafe_allow_html=True)


def _anchor(name: str) -> None:
    st.markdown(f'<div id="s-{name}"></div>', unsafe_allow_html=True)


# --- Sections (progressive disclosure)
_anchor("upload")
upload.render(lang)

if has_courses:
    st.divider()
    _anchor("review")
    review.render(lang)
    st.divider()
    _anchor("classrooms")
    classrooms.render(lang)
    st.divider()
    _anchor("solve")
    solve.render(lang)

if has_result:
    st.divider()
    _anchor("results")
    results.render(lang)
