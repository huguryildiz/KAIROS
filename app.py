# app.py  (repo root) — run with: PYTHONPATH=src streamlit run app.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st

st.set_page_config(page_title="Course Timetabling", page_icon="📅", layout="wide")

# default session state
st.session_state.setdefault("courses", [])
st.session_state.setdefault("classrooms", [
    {"Room": "A301", "Cap": "60", "Lab": ""},
    {"Room": "A317", "Cap": "30", "Lab": "x"},
])
st.session_state.setdefault("result", None)

logo = os.path.join(os.path.dirname(__file__), "assets", "logo.svg")
if os.path.exists(logo):
    with open(logo, encoding="utf-8") as f:
        st.sidebar.markdown(f.read(), unsafe_allow_html=True)
st.sidebar.markdown("**Course Timetabling**")

st.title("Course Timetabling")
st.write("Use the sidebar: **Upload courses → Classrooms → Solve → Results**.")
st.info("Upload a course-list CSV to begin.")
