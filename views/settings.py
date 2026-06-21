"""Step 4 — School Settings: institutional policy, preference weights, instructor
availability, and a downloadable school profile. Every value lives in st.session_state and
only becomes a Config at solve time (timetabling.settings.build_config). Thin by design —
all logic is in the pure timetabling.settings module."""
import streamlit as st

from timetabling.ui_style import eyebrow_html
from timetabling.i18n import t


def render(lang: str) -> None:
    st.markdown(eyebrow_html(4, t("step_settings", lang), "settings"),
                unsafe_allow_html=True)
    st.caption(t("set_caption", lang))
