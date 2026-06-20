"""Step 5 — Results: metric cards, weekly grid (view/selection), downloads."""
import json

import pandas as pd
import streamlit as st

from timetabling.ui_grid import filter_assignments, distinct_values
from timetabling.ui_style import metric_cards_html, week_grid_html
from timetabling.i18n import t

# View dimension -> i18n label key for the "view by" selector.
VIEW_KEY = {"cohort": "res_view_cohort", "room": "res_view_room",
            "instructor_name": "res_view_instructor", "dept": "res_view_dept"}


def render(lang: str) -> None:
    res = st.session_state.get("result")
    if res is None:
        return
    st.markdown(
        f'<div class="eyebrow"><span class="n">5</span>{t("step_results", lang)}</div>',
        unsafe_allow_html=True)
    st.subheader(t("res_header", lang))

    sched = res.schedule
    total_blocks = len(res.assignments) + sum(len(s.blocks) for s in res.unschedulable)
    placed_pct = (len(res.assignments) / total_blocks * 100) if total_blocks else 0
    conflicts = len(res.violations)
    st.markdown(metric_cards_html([
        (t("res_m_placed", lang), f"{placed_pct:.0f}%", "good" if placed_pct >= 99 else "brand"),
        (t("res_m_conflicts", lang), str(conflicts), "good" if conflicts == 0 else "bad"),
        (t("res_m_rooms", lang), str(len({a['room'] for a in sched['assignments']})), ""),
        (t("res_m_unsched", lang), str(len(res.unschedulable)), "" if not res.unschedulable else "bad"),
    ]), unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])
    view_field = c1.selectbox(t("res_view_by", lang), list(VIEW_KEY),
                              format_func=lambda f: t(VIEW_KEY[f], lang))
    entities = distinct_values(sched, view_field)
    if not entities:
        st.info(t("res_no_assign", lang))
        return
    entity = c2.selectbox(t(VIEW_KEY[view_field], lang), entities)
    view = filter_assignments(sched, view_field, entity)
    st.markdown(week_grid_html(view, lang=lang), unsafe_allow_html=True)
    st.caption(t("res_grid_caption", lang, n=len(view["assignments"])))

    st.write("")
    c3, c4 = st.columns(2)
    c3.download_button(t("res_dl_json", lang),
                       json.dumps(sched, ensure_ascii=False, indent=2),
                       file_name=f"schedule_{st.session_state.get('period','')}.json",
                       use_container_width=True)
    c4.download_button(t("res_dl_csv", lang),
                       pd.DataFrame(sched["assignments"]).to_csv(index=False),
                       file_name=f"schedule_{st.session_state.get('period','')}.csv",
                       use_container_width=True)

    if res.unschedulable:
        with st.expander(t("res_unsched_title", lang, n=len(res.unschedulable))):
            st.write([s.section_id for s in res.unschedulable])
