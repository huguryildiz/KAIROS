"""Step 1 — Upload: CSV dropzone + Load-sample. Writes session_state['courses']."""
import os

import streamlit as st

from timetabling.csv_import import ok_rows, parse_courselist, read_raw
from timetabling.i18n import t
from timetabling.ui_style import eyebrow_html, upload_cta_html, upload_error_html, upload_success_html

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
    st.markdown(eyebrow_html(None, t("step_upload", lang), "upload", sub=True),
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
            # Center the "upload a different file" button horizontally, directly
            # below the success message. The button's keyed container
            # (Streamlit adds .st-key-change_file when key="change_file") is a
            # flex *item* that sizes to its content (~206px) and sits left, so
            # flex-centering it alone does nothing — it must first be forced to
            # full width. Then center its content while pinning the inner stButton
            # + button back to content width so the button hugs its label (per the
            # button-width rule) instead of stretching edge-to-edge.
            st.markdown(
                "<style>"
                ".st-key-change_file{display:flex!important;justify-content:center!important;width:100%!important;}"
                ".st-key-change_file [data-testid='stButton']{width:auto!important;flex:0 0 auto!important;}"
                ".st-key-change_file button{width:auto!important;}"
                "</style>",
                unsafe_allow_html=True,
            )
            clicked = st.button(t("upload_change_btn", lang), key="change_file",
                                icon=":material/upload_file:")
            if clicked:
                for key in ("courses", "import_report", "upload_filename") + _DOWNSTREAM_KEYS:
                    st.session_state.pop(key, None)
                st.rerun()
        else:
            # Empty state: two side-by-side buttons. Left = "Upload CSV" CTA (a
            # visual primary button with an invisible file-uploader overlaid on top,
            # so it opens the file picker and still accepts drag-drop). Right = the
            # native "sample dataset" button. Columns stack on mobile portrait.
            c_up, c_sample = st.columns(2, vertical_alignment="center")
            with c_up:
                with st.container(key="up_btn"):
                    st.markdown(upload_cta_html(lang), unsafe_allow_html=True)
                    up = st.file_uploader("Upload CSV", type=["csv"],
                                          label_visibility="collapsed")
            with c_sample:
                load_sample = st.button(
                    t("upload_sample_btn", lang),
                    key="load_sample",
                    type="secondary",
                    icon=":material/dataset:",
                )

            if up is not None:
                try:
                    _ingest(up)
                    st.rerun()
                except Exception as exc:
                    st.markdown(upload_error_html(up.name, exc, lang), unsafe_allow_html=True)
            if load_sample:
                _ingest(_SAMPLE)
                st.rerun()

        st.caption(t("upload_format_label", lang))
        _h = {k: t(k, lang) for k in (
            "tbl_course_code", "tbl_course_name", "tbl_dept", "tbl_section_no",
            "tbl_lecturer_name", "tbl_lecturer_email", "tbl_capacity", "tbl_room_type",
            "sample_course_name_1", "sample_dept_1", "sample_course_name_2", "sample_dept_2",
        )}
        st.markdown(
            '<div style="display:flex;justify-content:center">'
            '<div class="tt-table-wrap" style="--tt-table-h:120px">'
            '<table class="tt-data"><thead><tr>'
            f'<th>{_h["tbl_course_code"]}</th>'
            f'<th>{_h["tbl_course_name"]}</th>'
            f'<th>{_h["tbl_dept"]}</th>'
            f'<th>{_h["tbl_section_no"]}</th>'
            f'<th>{_h["tbl_lecturer_name"]}</th>'
            f'<th>{_h["tbl_lecturer_email"]}</th>'
            '<th class="num">T</th><th class="num">P</th><th class="num">L</th>'
            f'<th class="num">{_h["tbl_capacity"]}</th>'
            f'<th>{_h["tbl_room_type"]}</th>'
            '</tr></thead><tbody>'
            f'<tr><td>CMPE 113</td><td>{_h["sample_course_name_1"]}</td>'
            f'<td>{_h["sample_dept_1"]}</td><td>CMPE 113_01</td>'
            '<td>Ahmet Yılmaz</td><td>ayilmaz@uni.edu</td>'
            '<td class="num">3</td><td class="num">0</td><td class="num">2</td>'
            '<td class="num">50</td><td>pc</td></tr>'
            f'<tr><td>MATH 101</td><td>{_h["sample_course_name_2"]}</td>'
            f'<td>{_h["sample_dept_2"]}</td><td>MATH 101_01</td>'
            '<td>Burak Demir</td><td>bdemir@uni.edu</td>'
            '<td class="num">4</td><td class="num">0</td><td class="num">0</td>'
            '<td class="num">60</td><td></td></tr>'
            '</tbody></table></div></div>',
            unsafe_allow_html=True,
        )
        st.caption(t("upload_format_tpl", lang))
