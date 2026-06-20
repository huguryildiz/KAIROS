import streamlit as st
from timetabling.config import Config
from timetabling.ui_input import (build_sections_from_courselist,
                                  build_instructors_from_courselist, build_rooms_from_ui)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
from timetabling.ui_app import get_lang
from timetabling.i18n import t

lang = get_lang()

st.header(t("solve_header", lang))
courses = st.session_state.get("courses", [])
if not courses:
    st.warning(t("solve_need_upload", lang))
    st.stop()

st.caption(t("solve_ready", lang, c=len(courses), r=len(st.session_state["classrooms"])))
c1, c2 = st.columns(2)
period = c1.selectbox(t("solve_period", lang), ["001", "002"], help=t("solve_period_help", lang))
time_limit = c2.slider(t("solve_timelimit", lang), 10, 600, 60, step=10)

if st.button(t("solve_button", lang), type="primary"):
    cfg = Config(solve_time_limit_s=float(time_limit))
    secs, rep = build_sections_from_courselist(courses, period, cfg)
    instr = build_instructors_from_courselist(courses)
    rooms = build_rooms_from_ui(st.session_state["classrooms"], cfg)
    mark_virtual(secs, rooms, cfg)
    with st.spinner(t("solve_spinner", lang, n=len(secs))):
        res = run_pipeline(period, secs, rooms, instr, cfg, solver="auto")
    st.session_state["result"] = res
    st.session_state["period"] = period
    st.success(t("solve_done", lang, a=len(res.assignments),
                 v=len(res.violations), u=len(res.unschedulable)))
    st.page_link("views/results.py", label=t("solve_see_results", lang))
