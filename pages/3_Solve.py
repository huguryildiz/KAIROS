import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import streamlit as st
from timetabling.config import Config
from timetabling.ui_input import (build_sections_from_courselist,
                                  build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
from timetabling.ui_style import BRAND_CSS, logo_img_html

st.set_page_config(page_title="Solve · Course Timetabling", page_icon="▶", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)

st.header("Solve")
courses = st.session_state.get("courses", [])
if not courses:
    st.warning("Upload a course list first (Upload page).")
    st.stop()

st.caption(f"{len(courses)} course rows · {len(st.session_state['classrooms'])} rooms ready.")
c1, c2 = st.columns(2)
period = c1.selectbox("Period", ["001", "002"], help="001 = Fall, 002 = Spring")
time_limit = c2.slider("Time limit (seconds)", 10, 600, 60, step=10)

if st.button("Solve timetable", type="primary"):
    cfg = Config(solve_time_limit_s=float(time_limit))
    secs, rep = build_sections_from_courselist(courses, period, cfg)
    instr = build_instructors_from_courselist(courses)
    rooms = build_rooms_from_ui(st.session_state["classrooms"], cfg)
    mark_virtual(secs, rooms, cfg)
    with st.spinner(f"Solving {len(secs)} sections…"):
        res = run_pipeline(period, secs, rooms, instr, cfg, solver="auto")
    st.session_state["result"] = res
    st.session_state["period"] = period
    st.success(f"Placed {len(res.assignments)} blocks · {len(res.violations)} hard conflicts · "
               f"{len(res.unschedulable)} unschedulable.")
    st.page_link("pages/4_Results.py", label="See results →")
