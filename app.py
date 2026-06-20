# app.py  (repo root) — run with: PYTHONPATH=src streamlit run app.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_style import BRAND_CSS, logo_img_html
from timetabling.ui_app import lang_selector
from timetabling.i18n import t

st.set_page_config(page_title="Course Timetabling", page_icon="📅", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)

# default session state
st.session_state.setdefault("courses", [])
st.session_state.setdefault("classrooms", [dict(r) for r in DEFAULT_CLASSROOMS])
st.session_state.setdefault("result", None)

st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)
lang = lang_selector()

st.markdown(
    f"""
    <div class="tt-hero">
      <div class="eyebrow">{t("hero_eyebrow", lang)}</div>
      <h1>{t("hero_title_html", lang)}</h1>
      <p>{t("hero_body", lang)}</p>
      <div class="tt-steps">
        <span class="tt-step"><b>1</b>{t("step_upload", lang)}</span>
        <span class="tt-step"><b>2</b>{t("step_classrooms", lang)}</span>
        <span class="tt-step"><b>3</b>{t("step_solve", lang)}</span>
        <span class="tt-step"><b>4</b>{t("step_results", lang)}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(t("start_hint", lang))
