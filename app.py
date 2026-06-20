# app.py  (repo root) — run with: PYTHONPATH=src streamlit run app.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_style import BRAND_CSS, logo_img_html

st.set_page_config(page_title="Course Timetabling", page_icon="📅", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)

# default session state
st.session_state.setdefault("courses", [])
st.session_state.setdefault("classrooms", [dict(r) for r in DEFAULT_CLASSROOMS])
st.session_state.setdefault("result", None)

st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)

st.markdown(
    """
    <div class="tt-hero">
      <div class="eyebrow">University course timetabling</div>
      <h1>Every section, placed on a <em>conflict-free</em> weekly grid.</h1>
      <p>Upload your course list, set your rooms, and let the CP-SAT solver assign a
         day, time, and room to each section — no double-booked rooms, instructors, or labs.</p>
      <div class="tt-steps">
        <span class="tt-step"><b>1</b>Upload courses</span>
        <span class="tt-step"><b>2</b>Classrooms</span>
        <span class="tt-step"><b>3</b>Solve</span>
        <span class="tt-step"><b>4</b>Results</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption("Start from the sidebar → **Upload courses**.")
