import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st
from timetabling.ui_input import validate_courselist
from timetabling.ui_style import BRAND_CSS, logo_img_html

st.set_page_config(page_title="Upload · Course Timetabling", page_icon="📤", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)

st.header("Upload courses")
st.caption("One row per section. Columns: Course Code, Course Name, Section No, T, P, L, "
           "Lecturer Name, Lecturer Email, ~Students.")

up = st.file_uploader("Course list (CSV)", type=["csv"])
if up is not None:
    df = pd.read_csv(up, dtype=str).fillna("")
    rows = df.to_dict("records")
    st.session_state["courses"] = rows
    st.success(f"Loaded {len(rows)} rows.")
    for w in validate_courselist(rows):
        st.warning(w)
    st.dataframe(df, use_container_width=True, height=340)
elif st.session_state["courses"]:
    st.info(f"{len(st.session_state['courses'])} rows currently loaded — re-upload to replace.")
    st.dataframe(pd.DataFrame(st.session_state["courses"]), use_container_width=True)
else:
    st.info("No file yet. Try the sample at examples/courses_demo.csv.")
