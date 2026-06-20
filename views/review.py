"""Step 2 — Review uploaded data: KPI chips + validation alerts + table."""
import pandas as pd
import streamlit as st

from timetabling.ui_input import (validate_courselist, cohort_from_code,
                                  parse_emails)
from timetabling.ui_style import kpi_chips_html
from timetabling.i18n import t


def render(lang: str) -> None:
    rows = st.session_state.get("courses", [])
    st.markdown(
        f'<div class="eyebrow"><span class="n">2</span>{t("step_review", lang)}</div>',
        unsafe_allow_html=True)
    st.subheader(t("review_header", lang))
    st.caption(t("review_caption", lang))

    n_courses = len({str(r.get("Course Code", "")).strip()
                     for r in rows if r.get("Course Code")})
    depts = {cohort_from_code(r.get("Course Code", ""))[0]
             for r in rows if r.get("Course Code")}
    instr = set()
    for r in rows:
        instr.update(parse_emails(r.get("Lecturer Email", "")))
    st.markdown(kpi_chips_html([
        (t("kpi_sections", lang), str(len(rows)), ""),
        (t("kpi_courses", lang), str(n_courses), ""),
        (t("kpi_depts", lang), str(len(depts)), ""),
        (t("kpi_instructors", lang), str(len(instr)), ""),
    ]), unsafe_allow_html=True)

    for code, kw in validate_courselist(rows):
        msg = t(code, lang, **kw)
        (st.info if code == "info_part_time" else st.warning)(msg)

    st.dataframe(pd.DataFrame(rows), use_container_width=True, height=340)
