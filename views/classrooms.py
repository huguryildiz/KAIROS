"""Step 3 — Classrooms: KPI chips + CSV upload + inventory preview (capacity, lab)."""
import os

import streamlit as st

from timetabling.csv_import import ok_rooms, parse_classrooms, read_raw
from timetabling.defaults import DEFAULT_CLASSROOMS
from timetabling.ui_style import (
    data_table_html, detected_columns_html, eyebrow_html, import_stats_html,
    kpi_chips_html, success_banner_html, upload_cta_html, upload_error_html,
)
from timetabling.textnorm import parse_int
from timetabling.i18n import t

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_classrooms.csv")


def render(lang: str) -> None:
    st.markdown(eyebrow_html(None, t("step_classrooms", lang), "classrooms", sub=True),
                unsafe_allow_html=True)
    st.caption(t("cr_caption", lang))

    rooms = st.session_state["classrooms"]
    caps = [parse_int(r.get("Capacity") or r.get("Cap"), 0) for r in rooms]
    labs = sum(1 for r in rooms
               if str(r.get("Type", "")).strip().lower() not in ("", "normal"))
    st.markdown(kpi_chips_html([
        (t("kpi_rooms", lang), str(len(rooms)), ""),
        (t("kpi_labs", lang), str(labs), ""),
        (t("kpi_maxcap", lang), str(max(caps) if caps else 0), ""),
        (t("kpi_online", lang), "∞", "good"),
    ]), unsafe_allow_html=True)

    source = st.session_state.get("cr_source")

    # Upload card — same dropzone look as Step 1. Once a list is loaded (sample or
    # CSV) the card shows a green "loaded" banner with a button to load a different
    # list; until then it shows the dropzone + "Try with sample dataset" button.
    with st.container(key="cr_card"):
        if source:
            st.markdown(success_banner_html(t("cr_loaded", lang, n=len(rooms)), source),
                        unsafe_allow_html=True)
            # Center the "load a different list" button below the success banner.
            # Its keyed container (.st-key-cr_change) is a flex item that sizes to
            # its label and sits left, so it must be forced full-width + flex-center
            # while the inner stButton + button are pinned back to content width so
            # the button hugs its label (see the button-centering rule in CLAUDE.md).
            st.markdown(
                "<style>"
                ".st-key-cr_change{display:flex!important;justify-content:center!important;width:100%!important;}"
                ".st-key-cr_change [data-testid='stButton']{width:auto!important;flex:0 0 auto!important;}"
                ".st-key-cr_change button{width:auto!important;}"
                "</style>",
                unsafe_allow_html=True)
            if st.button(t("cr_change_btn", lang), key="cr_change",
                         icon=":material/upload_file:"):
                st.session_state.pop("cr_source", None)
                st.session_state.pop("cr_report", None)
                st.rerun()
        else:
            # Empty state: same two-button row as Step 1 — left = "Upload CSV" CTA
            # (a visual primary button with an invisible file-uploader overlaid on
            # top, so it opens the file picker and still accepts drag-drop); right =
            # the native "sample dataset" secondary button. Columns stack on mobile.
            c_up, c_sample = st.columns(2, vertical_alignment="center")
            with c_up:
                with st.container(key="cr_up_btn"):
                    st.markdown(upload_cta_html(lang), unsafe_allow_html=True)
                    up = st.file_uploader("Upload CSV", type=["csv"], key="cr_upload",
                                          label_visibility="collapsed")
            with c_sample:
                load_sample = st.button(
                    t("cr_sample", lang),
                    key="cr_sample",
                    type="secondary",
                    icon=":material/dataset:",
                )

            if up is not None:
                try:
                    report = parse_classrooms(read_raw(up))
                except Exception as exc:
                    st.markdown(upload_error_html(up.name, exc, lang), unsafe_allow_html=True)
                    report = None
                if report is not None and not ok_rooms(report):
                    st.markdown(upload_error_html(up.name, t("cr_upload_error", lang), lang),
                                unsafe_allow_html=True)
                elif report is not None:
                    st.session_state["classrooms"] = ok_rooms(report)
                    st.session_state["cr_report"] = report
                    st.session_state["cr_source"] = up.name
                    st.rerun()

            if load_sample:
                report = parse_classrooms(read_raw(_SAMPLE))
                st.session_state["classrooms"] = ok_rooms(report) or [dict(r) for r in DEFAULT_CLASSROOMS]
                st.session_state["cr_report"] = report
                st.session_state["cr_source"] = t("cr_sample_name", lang)
                st.rerun()

            # Format hint + expected-columns example (empty state only; once a list
            # is loaded the success state shows the actual detected columns instead).
            st.caption(t("cr_upload_hint", lang))
            _cr = [t("tbl_room", lang), t("tbl_cap", lang), t("tbl_type", lang)]
            st.markdown(
                data_table_html(
                    _cr,
                    [["A216", "25", "normal"], ["A211-PC-L", "99", "pc"]],
                    max_height=160, numeric=(_cr[1],)),
                unsafe_allow_html=True)

    # Detected-column chips + valid/total badges + inventory preview — shown below
    # the card (not inside it) so the dashed border wraps only the banner + button,
    # matching the course upload module's success-state layout.
    if source:
        report = st.session_state.get("cr_report")
        if report:
            st.markdown(detected_columns_html(report["detected_columns"], lang),
                        unsafe_allow_html=True)
            st.markdown(import_stats_html(report["stats"], lang),
                        unsafe_allow_html=True)
        _cr = [t("tbl_room", lang), t("tbl_cap", lang), t("tbl_type", lang)]
        st.markdown(
            data_table_html(
                _cr,
                [[r.get("Room", ""), r.get("Capacity", r.get("Cap", "")),
                  r.get("Type", "")] for r in rooms],
                max_height=300, numeric=(_cr[1],)),
            unsafe_allow_html=True)
