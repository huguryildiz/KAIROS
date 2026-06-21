"""Step 1 — Upload: CSV dropzone + Load-sample. Writes session_state['courses']."""
import os

import pandas as pd
import streamlit as st

from timetabling.csv_import import ok_rows, parse_courselist, read_raw
from timetabling.i18n import t
from timetabling.ui_style import dropzone_html, eyebrow_html, upload_error_html, upload_success_html

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")


def _ingest(file_or_path) -> dict:
    """Parse a CSV (file/path) the VERA way: alias-aware header detection +
    per-row status. Stores only valid rows as ``courses`` and the full report
    (for the Review preview) as ``import_report``."""
    report = parse_courselist(read_raw(file_or_path))
    st.session_state["courses"] = ok_rows(report)
    st.session_state["import_report"] = report
    st.session_state["scroll_to"] = "review"
    return report


def render(lang: str) -> None:
    st.markdown(eyebrow_html(1, t("step_upload", lang), "upload"),
                unsafe_allow_html=True)

    with st.container(key="upload_card"):
        st.markdown(dropzone_html(lang), unsafe_allow_html=True)

        up = st.file_uploader("", type=["csv"], label_visibility="collapsed")
        if up is not None:
            try:
                report = _ingest(up)
                n = report["stats"]["valid"]
                st.markdown(upload_success_html(up.name, n, lang), unsafe_allow_html=True)
            except Exception as exc:
                st.markdown(upload_error_html(up.name, exc, lang), unsafe_allow_html=True)

        st.caption(t("upload_format_label", lang))
        st.dataframe(
            pd.DataFrame([
                {"Course Code": "CMPE 113", "Course Name": "Intro to Programming",
                 "Section No": "01", "T": "3", "P": "0", "L": "2",
                 "Lecturer Name": "A. Yilmaz", "Lecturer Email": "ayilmaz@uni.edu",
                 "~Students": "50"},
                {"Course Code": "MATH 101", "Course Name": "Calculus I",
                 "Section No": "01", "T": "4", "P": "0", "L": "0",
                 "Lecturer Name": "B. Demir", "Lecturer Email": "bdemir@uni.edu",
                 "~Students": "55"},
            ]),
            use_container_width=True,
            hide_index=True,
        )
        st.caption(t("upload_format_tpl", lang))

        if st.button(
            t("upload_sample_btn", lang),
            key="load_sample",
            type="primary",
        ):
            _ingest(_SAMPLE)
            st.rerun()

