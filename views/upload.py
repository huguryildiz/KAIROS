"""Step 1 — Upload: CSV dropzone + Load-sample. Writes session_state['courses']."""
import os

import pandas as pd
import streamlit as st

from timetabling.csv_import import ok_rows, parse_courselist, read_raw
from timetabling.i18n import t
from timetabling.ui_style import dropzone_html, eyebrow_html, upload_error_html, upload_success_html

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")

# Keys set by solve/review that should be cleared when the file is replaced
_DOWNSTREAM_KEYS = ("schedule", "solve_result", "scroll_to")


def _ingest(file_or_path) -> dict:
    """Parse a CSV (file/path) the VERA way: alias-aware header detection +
    per-row status. Stores only valid rows as ``courses`` and the full report
    (for the Review preview) as ``import_report``."""
    report = parse_courselist(read_raw(file_or_path))
    st.session_state["courses"] = ok_rows(report)
    st.session_state["import_report"] = report
    st.session_state["scroll_to"] = "review"
    # Store display name so success state persists across reruns
    if hasattr(file_or_path, "name"):
        st.session_state["upload_filename"] = file_or_path.name
    else:
        st.session_state["upload_filename"] = os.path.basename(str(file_or_path))
    return report


def render(lang: str) -> None:
    st.markdown(eyebrow_html(1, t("step_upload", lang), "upload"),
                unsafe_allow_html=True)
    st.caption(t("upload_desc", lang))

    has_upload = bool(st.session_state.get("courses"))

    with st.container(key="upload_card"):
        if has_upload:
            # Show only the success state — no upload icon overlay
            report = st.session_state["import_report"]
            n = report["stats"]["valid"]
            filename = st.session_state.get("upload_filename", "")
            st.markdown(upload_success_html(filename, n, lang), unsafe_allow_html=True)
            st.markdown(
                "<style>div[data-testid='stButton']{display:flex;justify-content:center}</style>",
                unsafe_allow_html=True,
            )
            clicked = st.button(t("upload_change_btn", lang), key="change_file",
                                icon=":material/upload_file:")
            if clicked:
                for key in ("courses", "import_report", "upload_filename") + _DOWNSTREAM_KEYS:
                    st.session_state.pop(key, None)
                st.rerun()
        else:
            # Empty state: custom dropzone icon + invisible file-uploader overlay
            st.markdown(dropzone_html(lang), unsafe_allow_html=True)
            up = st.file_uploader("Upload CSV", type=["csv"], label_visibility="collapsed")
            if up is not None:
                try:
                    _ingest(up)
                    st.rerun()
                except Exception as exc:
                    st.markdown(upload_error_html(up.name, exc, lang), unsafe_allow_html=True)

            if st.button(
                t("upload_sample_btn", lang),
                key="load_sample",
                type="primary",
            ):
                _ingest(_SAMPLE)
                st.rerun()

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
