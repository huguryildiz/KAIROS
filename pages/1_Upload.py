import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st
from timetabling.ui_input import validate_courselist
from timetabling.ui_style import BRAND_CSS, logo_img_html
from timetabling.ui_app import lang_selector
from timetabling.i18n import t

st.set_page_config(page_title="Upload · Course Timetabling", page_icon="📤", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)
lang = lang_selector()

st.header(t("upload_header", lang))
st.caption(t("upload_caption", lang))

up = st.file_uploader(t("upload_uploader", lang), type=["csv"])
if up is not None:
    df = pd.read_csv(up, dtype=str).fillna("")
    rows = df.to_dict("records")
    st.session_state["courses"] = rows
    st.success(t("upload_loaded", lang, n=len(rows)))
    for code, kw in validate_courselist(rows):
        msg = t(code, lang, **kw)
        (st.info if code == "info_part_time" else st.warning)(msg)
    st.dataframe(df, use_container_width=True, height=340)
elif st.session_state["courses"]:
    st.info(t("upload_current", lang, n=len(st.session_state["courses"])))
    st.dataframe(pd.DataFrame(st.session_state["courses"]), use_container_width=True)
else:
    st.info(t("upload_none", lang))
