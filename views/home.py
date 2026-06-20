import streamlit as st
from timetabling.ui_app import get_lang
from timetabling.i18n import t

lang = get_lang()

st.markdown(
    f"""
    <div class="tt-hero">
      <div class="eyebrow">{t("hero_eyebrow", lang)}</div>
      <h1>{t("hero_title_html", lang)}</h1>
      <p>{t("hero_body", lang)}</p>
      <div class="tt-steps">
        <span class="tt-step"><b>1</b>{t("step_upload", lang)}</span>
        <span class="tt-step"><b>2</b>{t("step_classrooms", lang)}</span>
        <span class="tt-step"><b>3</b>{t("step_solve", lang)}</span>
        <span class="tt-step"><b>4</b>{t("step_results", lang)}</span>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.caption(t("start_hint", lang))
