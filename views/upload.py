"""Step 1 — Upload: CSV dropzone + Load-sample. Writes session_state['courses']."""
import os

import pandas as pd
import streamlit as st

from timetabling.i18n import t

_SAMPLE = os.path.join(os.path.dirname(__file__), "..", "assets", "sample_courses.csv")


def _set_courses(df: pd.DataFrame) -> None:
    st.session_state["courses"] = df.fillna("").to_dict("records")


def render(lang: str) -> None:
    st.markdown(
        f'<div class="eyebrow"><span class="n">1</span>{t("step_upload", lang)}</div>',
        unsafe_allow_html=True)
    st.subheader(t("upload_header", lang))
    st.caption(t("upload_caption", lang))

    up = st.file_uploader(t("upload_uploader", lang), type=["csv"])
    if up is not None:
        _set_courses(pd.read_csv(up, dtype=str))
        st.success(t("upload_loaded", lang, n=len(st.session_state["courses"])))

    st.caption(t("upload_sample_caption", lang))
    if st.button(t("upload_sample_btn", lang), key="load_sample"):
        _set_courses(pd.read_csv(_SAMPLE, dtype=str))
        st.rerun()
