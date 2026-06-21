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
    # Downloads — JSON, CSV and PDF on one row. The button row is rendered into a
    # container placed ABOVE the entity chips, but filled AFTER the multiselect so
    # the PDF button reflects the current chip selection.
    dim_label = t(VIEW_KEY[view_field], lang)
    btn_row = st.container()
    pdf_entities = st.multiselect(
        t("res_pdf_pick", lang, dim=dim_label),
        entities, default=[entity], format_func=fmt or str,
        key="pdf_entities")
    with btn_row:
        c3, c4, c5 = st.columns(3)
        c3.download_button(t("res_dl_json", lang),
                           json.dumps(sched, ensure_ascii=False, indent=2),
                           file_name="schedule.json",
                           key="dl_json")
        c4.download_button(t("res_dl_csv", lang),
                           pd.DataFrame(sched["assignments"]).to_csv(index=False),
                           file_name="schedule.csv",
                           key="dl_csv")
        if pdf_entities:
            n = len(pdf_entities)
            pdf_data, pdf_name, pdf_mime = build_pdf_bundle(
                sched, view_field, pdf_entities, dim_label, lang)
            label = t("res_dl_pdf", lang) + (f" ({n})" if n > 1 else "")
            c5.download_button(label, pdf_data, file_name=pdf_name,
                               mime=pdf_mime, key="dl_pdf")
        else:
            c5.download_button(t("res_dl_pdf", lang), b"",
                               file_name="schedule.pdf", key="dl_pdf",
                               disabled=True)

    if res.unschedulable:
        with st.expander(t("res_unsched_title", lang, n=len(res.unschedulable))):
            st.markdown(unschedulable_html(res.unschedulable, lang),
                        unsafe_allow_html=True)
