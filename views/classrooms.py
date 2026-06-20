import pandas as pd
import streamlit as st
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_app import get_lang
from timetabling.i18n import t

lang = get_lang()

st.header(t("cr_header", lang))
st.caption(t("cr_caption", lang))

if st.button(t("cr_reset", lang)):
    st.session_state["classrooms"] = [dict(r) for r in DEFAULT_CLASSROOMS]
    st.rerun()

df = pd.DataFrame(st.session_state["classrooms"])
edited = st.data_editor(
    df,
    num_rows="dynamic",
    use_container_width=True,
    column_config={
        "Room": st.column_config.TextColumn(t("cr_col_room", lang), width="medium"),
        "Cap": st.column_config.NumberColumn(t("cr_col_cap", lang), min_value=0, step=1),
        "Lab": st.column_config.CheckboxColumn(t("cr_col_lab", lang)),
    },
)

edited["Lab"] = edited["Lab"].apply(lambda v: "x" if v and str(v) not in ("", "False", "0") else "")
st.session_state["classrooms"] = edited.fillna("").to_dict("records")

st.caption(t("cr_count", lang, n=len(st.session_state["classrooms"])))
