import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_style import BRAND_CSS, logo_img_html

st.set_page_config(page_title="Classrooms · Course Timetabling", page_icon="🏫", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)

st.header("Classrooms")
st.caption("Add, remove, or edit rooms. Lab is detected from room name (-L / -PC suffix) "
           "but can be overridden. The Online virtual room is added automatically at solve time.")

if st.button("↺ Reset to defaults"):
    st.session_state["classrooms"] = [dict(r) for r in DEFAULT_CLASSROOMS]
    st.rerun()

df = pd.DataFrame(st.session_state["classrooms"])
edited = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Room": st.column_config.TextColumn("Room", width="medium"),
        "Cap": st.column_config.NumberColumn("Capacity", min_value=0, step=1),
        "Lab": st.column_config.CheckboxColumn("Lab"),
    },
)

edited["Lab"] = edited["Lab"].apply(lambda v: "x" if v and str(v) not in ("", "False", "0") else "")
st.session_state["classrooms"] = edited.fillna("").to_dict("records")

st.caption(f"{len(st.session_state['classrooms'])} room(s) defined.")
