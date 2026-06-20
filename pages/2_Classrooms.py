import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st

st.header("🏫 Classrooms")
st.caption("Add/edit rooms. Tick 'Lab' for lab rooms. The 'Online' virtual room is added "
           "automatically at solve time.")

df = pd.DataFrame(st.session_state["classrooms"])
edited = st.data_editor(df, num_rows="dynamic", use_container_width=True,
                        column_config={"Room": "Room", "Cap": "Cap", "Lab": "Lab"})
st.session_state["classrooms"] = edited.fillna("").to_dict("records")
st.caption(f"{len(st.session_state['classrooms'])} room(s) defined.")
