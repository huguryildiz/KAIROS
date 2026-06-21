"""Streamlit-aware UI helpers (kept out of i18n/ui_style so those stay pure)."""
from __future__ import annotations
import streamlit as st

from .i18n import LANGS, DEFAULT_LANG, t
from .ui_input import cohort_from_code, parse_emails

_LANG_LABELS = {"tr": "🇹🇷", "en": "🇬🇧"}


def _fmt_duration(secs, lang: str) -> str:
    """Compact solve-time label: '47s' under 90s, else whole minutes ('5 dk')."""
    s = int(round(secs or 0))
    return f"{s}s" if s < 90 else f"{round(s / 60)} {t('hero_dur_min', lang)}"


def hero_chips(lang: str):
    """Live hero stat chips that track the workflow state, returning a list of
    ``(value, label, tone)`` for ui_style.hero_html — or None for the static
    proof chips when no data is loaded yet.

    no data → proof · loaded → {sections, depts, rooms, instructors} ·
    solved → {sections, conflicts, placement%, solve time}."""
    courses = st.session_state.get("courses", [])
    result = st.session_state.get("result")

    if result is not None:                                  # solved → real outcome
        total = len(result.assignments) + sum(s.get("n_blocks", len(s.get("issues", []))) for s in result.unschedulable)
        placed = (len(result.assignments) / total * 100) if total else 0
        conflicts = len(result.violations)
        return [
            (str(len(courses)), t("kpi_sections", lang), ""),
            (str(conflicts), t("hero_stat_conflicts", lang),
             "good" if conflicts == 0 else "bad"),
            (f"{placed:.0f}%", t("hero_stat_placed", lang),
             "good" if placed >= 99 else ""),
            (_fmt_duration(result.stats.get("wall_time"), lang),
             t("hero_stat_speed", lang), ""),
        ]

    if courses:                                             # loaded → dataset shape
        depts = {cohort_from_code(r.get("Course Code", ""))[0]
                 for r in courses if r.get("Course Code")}
        instr = set()
        for r in courses:
            instr.update(parse_emails(r.get("Instructor Email", "")))
        rooms = st.session_state.get("classrooms", [])
        return [
            (str(len(courses)), t("kpi_sections", lang), ""),
            (str(len(depts)), t("kpi_depts", lang), ""),
            (str(len(rooms)), t("kpi_rooms", lang), ""),
            (str(len(instr)), t("kpi_instructors", lang), ""),
        ]

    return None                                             # no data → proof chips


def get_lang() -> str:
    return st.session_state.get("lang", DEFAULT_LANG)


def get_theme() -> str:
    return st.session_state.get("theme", "light")


def theme_toggle() -> None:
    """Render the ☀️/🌙 toggle. Flips session_state['theme'] and reruns so the
    next pass emits the other token set via ui_style.brand_css(theme)."""
    st.session_state.setdefault("theme", "light")
    dark = get_theme() == "dark"
    if st.button("☀️" if dark else "🌙", key="theme_btn"):
        st.session_state["theme"] = "light" if dark else "dark"
        st.rerun()


def lang_selector_bar() -> str:
    """App-bar language switch: button shows the CURRENT language flag.

    Clicking switches to the other language — same pattern as theme_toggle."""
    st.session_state.setdefault("lang", DEFAULT_LANG)
    current = get_lang()
    other = next(c for c in LANGS if c != current)
    if st.button(_LANG_LABELS[current], key="lang_btn"):
        st.session_state["lang"] = other
        st.rerun()
    return get_lang()


def lang_selector() -> str:
    """Deprecated sidebar variant — kept until app.py drops st.navigation."""
    st.session_state.setdefault("lang", DEFAULT_LANG)
    return st.sidebar.radio(
        t("lang_label", get_lang()), list(LANGS), key="lang",
        format_func=lambda code: _LANG_LABELS.get(code, code), horizontal=True,
    )
