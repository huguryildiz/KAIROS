import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st
from timetabling.ui_input import validate_courselist

st.header("📤 Upload courses")
st.caption("CSV columns: Course Code, Course Name, Section No, T, P, L, "
           "Lecturer Name, Lecturer Email, ~Students")

up = st.file_uploader("Course list (CSV)", type=["csv"])
if up is not None:
    df = pd.read_csv(up, dtype=str).fillna("")
    rows = df.to_dict("records")
    st.session_state["courses"] = rows
    st.success(f"Loaded {len(rows)} rows.")
    for w in validate_courselist(rows):
        st.warning(w)
    st.dataframe(df, use_container_width=True, height=320)
elif st.session_state["courses"]:
    st.info(f"{len(st.session_state['courses'])} rows currently loaded.")
    st.dataframe(pd.DataFrame(st.session_state["courses"]), use_container_width=True)
