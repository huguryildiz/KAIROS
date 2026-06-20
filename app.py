# app.py  (repo root) — run with: PYTHONPATH=src streamlit run app.py
# Navigation controller: renders the shared sidebar (logo + language selector),
# then dispatches to a localized page from views/ via st.navigation.
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

pages = [
    st.Page("views/home.py", title=t("nav_home", lang), icon="🏠", default=True),
    st.Page("views/upload.py", title=t("step_upload", lang), icon="📤"),
    st.Page("views/classrooms.py", title=t("step_classrooms", lang), icon="🏫"),
    st.Page("views/solve.py", title=t("step_solve", lang), icon="▶"),
    st.Page("views/results.py", title=t("step_results", lang), icon="📊"),
]
st.navigation(pages).run()
