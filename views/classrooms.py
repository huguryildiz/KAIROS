"""Step 3 — Classrooms: KPI chips + editable inventory (capacity, lab)."""
import pandas as pd
import streamlit as st

from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_input import _truthy
from timetabling.ui_style import kpi_chips_html
from timetabling.textnorm import parse_int
from timetabling.i18n import t


def render(lang: str) -> None:
    st.markdown(
        f'<div class="eyebrow"><span class="n">3</span>{t("step_classrooms", lang)}</div>',
        unsafe_allow_html=True)
    st.subheader(t("cr_header", lang))
    st.caption(t("cr_caption", lang))

    rooms = st.session_state["classrooms"]
    caps = [parse_int(r.get("Cap"), 0) for r in rooms]
    labs = sum(1 for r in rooms if _truthy(r.get("Lab")))
    st.markdown(kpi_chips_html([
        (t("kpi_rooms", lang), str(len(rooms)), ""),
        (t("kpi_labs", lang), str(labs), ""),
        (t("kpi_maxcap", lang), str(max(caps) if caps else 0), ""),
        (t("kpi_online", lang), "∞", "good"),
    ]), unsafe_allow_html=True)

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
    edited["Lab"] = edited["Lab"].apply(
        lambda v: "x" if v and str(v) not in ("", "False", "0") else "")
    st.session_state["classrooms"] = edited.fillna("").to_dict("records")
    st.caption(t("cr_count", lang, n=len(st.session_state["classrooms"])))
