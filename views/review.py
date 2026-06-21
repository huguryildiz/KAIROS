"""Step 2 — Review uploaded data: KPI chips + validation alerts + table."""
import pandas as pd
import streamlit as st

from timetabling.ui_input import (validate_courselist, cohort_from_code,
                                  parse_emails)
from timetabling.ui_style import (kpi_chips_html, eyebrow_html, data_table_html,
                                  import_preview_html)
from timetabling.i18n import t

# Right-aligned, tabular-figure columns in the courselist preview.
_NUMERIC_COLS = ("T", "P", "L", "~Students")


def render(lang: str) -> None:
    rows = st.session_state.get("courses", [])
    st.markdown(eyebrow_html(None, t("step_review", lang), "review", sub=True),
                unsafe_allow_html=True)
    st.caption(t("review_caption", lang))

    n_courses = len({str(r.get("Course Code", "")).strip()
                     for r in rows if r.get("Course Code")})
    depts = {cohort_from_code(r.get("Course Code", ""))[0]
             for r in rows if r.get("Course Code")}
    instr = set()
    for r in rows:
        instr.update(parse_emails(r.get("Instructor Email", "")))
    st.markdown(kpi_chips_html([
        (t("kpi_sections", lang), str(len(rows)), ""),
        (t("kpi_courses", lang), str(n_courses), ""),
        (t("kpi_depts", lang), str(len(depts)), ""),
        (t("kpi_instructors", lang), str(len(instr)), ""),
    ]), unsafe_allow_html=True)

    _ERROR_CODES = {"warn_missing_cols", "warn_no_rows"}
    for code, kw in validate_courselist(rows):
        msg = t(code, lang, **kw)
        if code in _ERROR_CODES:
            st.error(msg)
        elif code == "info_part_time":
            st.info(msg)
        else:
            st.warning(msg)

    # VERA-style import preview (per-row status + badges) when an import report
    # is available; the plain table is the fallback (e.g. rows set elsewhere).
    report = st.session_state.get("import_report")
    if report:
        if report["stats"].get("duplicate", 0) or report["stats"].get("error", 0):
            st.warning(t("import_skipped_note", lang,
                         skipped=report["stats"]["duplicate"] + report["stats"]["error"],
                         valid=report["stats"]["valid"]))
        st.markdown(import_preview_html(report, lang), unsafe_allow_html=True)
    else:
        df = pd.DataFrame(rows)
        st.markdown(
            data_table_html(list(df.columns), df.astype(str).values.tolist(),
                            max_height=340, numeric=_NUMERIC_COLS),
            unsafe_allow_html=True)
