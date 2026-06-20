"""Streamlit-aware UI helpers (kept out of i18n/ui_style so those stay pure)."""
from __future__ import annotations
import streamlit as st

from .i18n import LANGS, DEFAULT_LANG, t

_LANG_LABELS = {"tr": "🇹🇷 Türkçe", "en": "🇬🇧 English"}


def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def lang_selector() -> str:
    """Render the sidebar language radio (bound to session_state['lang']) and
    return the active language code."""
    st.session_state.setdefault("lang", DEFAULT_LANG)
    cur = get_lang()
    return st.sidebar.radio(
        t("lang_label", cur), list(LANGS), key="lang",
        format_func=lambda code: _LANG_LABELS.get(code, code),
        horizontal=True,
    )
