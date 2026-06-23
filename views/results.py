"""Step 6 — Results: metric cards, weekly grid (view/selection), downloads."""
import json

import pandas as pd
import streamlit as st

from timetabling.ui_grid import filter_assignments, distinct_values
from timetabling.ui_style import metric_cards_html, week_grid_html, eyebrow_html, unschedulable_html
from timetabling.pdf_export import build_pdf_bundle
from timetabling.i18n import t

# View dimension -> i18n label key for the "view by" selector.
VIEW_KEY = {"cohort": "res_view_cohort", "room": "res_view_room",
            "instructor_name": "res_view_instructor", "dept": "res_view_dept",
            "course_code": "res_view_course"}


# Rendering a merged PDF (dozens of pages) takes seconds — cache so non-PDF
# reruns (selectbox changes, etc.) don't redo the work. Cache key includes the
# schedule's content via Streamlit's auto-hashing; max_entries bounds memory.
@st.cache_data(show_spinner=False, max_entries=8)
def _bundle(sched: dict, view_field: str, entities: tuple,
            dim_label: str, lang: str):
    return build_pdf_bundle(sched, view_field, list(entities), dim_label, lang)


def render(lang: str) -> None:
    res = st.session_state.get("result")
    if res is None:
        return
    st.markdown(eyebrow_html(4, t("step_results", lang), "results"),
                unsafe_allow_html=True)

    sched = res.schedule
    total_blocks = len(res.assignments) + sum(s.get("n_blocks", len(s.get("issues", []))) for s in res.unschedulable)
    placed_pct = (len(res.assignments) / total_blocks * 100) if total_blocks else 0
    conflicts = len(res.violations)
    elapsed = res.stats.get("total_elapsed_s", 0)
    elapsed_str = f"{elapsed:.0f} s" if elapsed < 60 else f"{elapsed/60:.1f} dk"
    st.markdown(metric_cards_html([
        (t("res_m_placed", lang), f"{placed_pct:.0f}%", "good" if placed_pct >= 99 else "brand"),
        (t("res_m_conflicts", lang), str(conflicts), "good" if conflicts == 0 else "bad"),
        (t("res_m_rooms", lang), str(len({a['room'] for a in sched['assignments']})), ""),
        (t("res_m_unsched", lang), str(len(res.unschedulable)), "" if not res.unschedulable else "bad"),
        (t("res_m_solve_time", lang), elapsed_str, ""),
    ]), unsafe_allow_html=True)

    c1, c2 = st.columns([1, 2])
    view_field = c1.selectbox(t("res_view_by", lang), list(VIEW_KEY),
                              format_func=lambda f: t(VIEW_KEY[f], lang))
    entities = distinct_values(sched, view_field)
    if not entities:
        st.info(t("res_no_assign", lang))
        return
    # For the instructor view build a name→email map so the dropdown shows "Name (email)".
    name_to_email = {}
    if view_field == "instructor_name":
        for a in sched.get("assignments", []):
            name = str(a.get("instructor_name", ""))
            email = str(a.get("instructor_id", ""))
            if name and email and name not in name_to_email:
                name_to_email[name] = email
    fmt = (lambda n: f"{n} ({name_to_email[n]})" if n in name_to_email and "@" in name_to_email[n] else n) \
          if view_field == "instructor_name" else None
    entity = c2.selectbox(t(VIEW_KEY[view_field], lang), entities, format_func=fmt or str)
    view = filter_assignments(sched, view_field, entity)
    st.markdown(week_grid_html(view, lang=lang), unsafe_allow_html=True)


    st.write("")
    # Downloads — JSON / CSV / PDF on one row. The PDF merges every entity of
    # the current view dimension (e.g. all cohorts) into one multi-page file,
    # sorted naturally (EE-1, EE-2, …, EE-10) so it reads in order.
    dim_label = t(VIEW_KEY[view_field], lang)
    pdf_data, pdf_name, pdf_mime = _bundle(
        sched, view_field, tuple(entities), dim_label, lang)
    with st.container(horizontal=True, horizontal_alignment="center",
                      gap="small"):
        st.download_button(t("res_dl_json", lang),
                           json.dumps(sched, ensure_ascii=False, indent=2),
                           file_name="schedule.json",
                           key="dl_json")
        st.download_button(t("res_dl_csv", lang),
                           pd.DataFrame(sched["assignments"]).to_csv(index=False),
                           file_name="schedule.csv",
                           key="dl_csv")
        st.download_button(t("res_dl_pdf", lang), pdf_data,
                           file_name=pdf_name, mime=pdf_mime, key="dl_pdf")

    if res.unschedulable:
        with st.expander(t("res_unsched_title", lang, n=len(res.unschedulable))):
            st.markdown(unschedulable_html(res.unschedulable, lang),
                        unsafe_allow_html=True)
