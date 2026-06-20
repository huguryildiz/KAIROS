"""Streamlit-aware UI helpers (kept out of i18n/ui_style so those stay pure)."""
from __future__ import annotations
import streamlit as st

from .i18n import LANGS, DEFAULT_LANG, t

_LANG_LABELS = {"tr": "🇹🇷 TR", "en": "🇬🇧 EN"}


def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def get_theme() -> str:
    return st.session_state.get("theme", "light")


def theme_toggle() -> None:
    """Render the ☀️/🌙 toggle. Flips session_state['theme'] and reruns so the
    next pass emits the other token set via ui_style.brand_css(theme)."""
    st.session_state.setdefault("theme", "light")
    dark = get_theme() == "dark"
    if st.button("☀️" if dark else "🌙", key="theme_btn",
                 help=t("theme_toggle", get_lang())):
        st.session_state["theme"] = "light" if dark else "dark"
        st.rerun()


def lang_selector_bar() -> str:
    """App-bar language selector (replaces the old sidebar radio). Bound to
    session_state['lang']; always exactly one language selected."""
    st.session_state.setdefault("lang", DEFAULT_LANG)
    st.radio(
        t("lang_label", get_lang()), list(LANGS), key="lang",
        format_func=lambda code: _LANG_LABELS.get(code, code),
        horizontal=True, label_visibility="collapsed",
    )
    return get_lang()


def lang_selector() -> str:
    """Deprecated sidebar variant — kept until app.py drops st.navigation."""
    st.session_state.setdefault("lang", DEFAULT_LANG)
    return st.sidebar.radio(
        t("lang_label", get_lang()), list(LANGS), key="lang",
        format_func=lambda code: _LANG_LABELS.get(code, code), horizontal=True,
    )
