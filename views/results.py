"""Step 6 — Results: metric cards, weekly grid (view/selection), downloads."""
import json
import os

import pandas as pd
import streamlit as st
from datetime import timezone as _tz

from timetabling.ui_grid import filter_assignments, distinct_values
from timetabling.ui_style import metric_cards_html, week_grid_html, eyebrow_html, unschedulable_html
from timetabling.pdf_export import build_pdf_bundle
from timetabling.export import CSV_FIELDS
from timetabling.cloud_storage import list_outputs_if_configured
from timetabling.i18n import t

# View dimension -> i18n label key for the "view by" selector.
VIEW_KEY = {"cohort": "res_view_cohort", "room": "res_view_room",
            "instructor_name": "res_view_instructor", "department": "res_view_dept",
            "course_code": "res_view_course"}


# Rendering a merged PDF (dozens of pages) takes seconds — cache so non-PDF
# reruns (selectbox changes, etc.) don't redo the work. Cache key includes the
# schedule's content via Streamlit's auto-hashing; max_entries bounds memory.
@st.cache_data(show_spinner=False, max_entries=8)
def _bundle(sched: dict, view_field: str, entities: tuple,
            dim_label: str, lang: str):
    return build_pdf_bundle(sched, view_field, list(entities), dim_label, lang)


@st.cache_data(show_spinner=False, ttl=60)
def _archive_rows(bucket: str, prefix: str) -> list[dict]:
    return list_outputs_if_configured(
        env={"KAIROS_GCS_BUCKET": bucket, "KAIROS_GCS_PREFIX": prefix}
    )


def _fmt_size(n: int) -> str:
    if n < 1024:
        return f"{n} B"
    if n < 1024 ** 2:
        return f"{n / 1024:.1f} KB"
    return f"{n / 1024 ** 2:.1f} MB"


def _render_archive_log(lang: str) -> None:
    bucket = os.environ.get("KAIROS_GCS_BUCKET", "").strip()
    if not bucket:
        return

    prefix = os.environ.get("KAIROS_GCS_PREFIX", "schedule-outputs")
    with st.expander(t("res_archive_title", lang)):
        try:
            rows = _archive_rows(bucket, prefix)
        except Exception as exc:
            st.warning(t("res_archive_error", lang, error=str(exc)))
        else:
            if rows:
                df = pd.DataFrame(rows)
                df["updated"] = pd.to_datetime(df["updated"], utc=True)
                df["size_str"] = df["size_bytes"].apply(_fmt_size)
                st.dataframe(
                    df,
                    hide_index=True,
                    use_container_width=True,
                    column_order=["updated", "file", "size_str", "download_url"],
                    column_config={
                        "updated": st.column_config.DatetimeColumn(
                            t("res_archive_updated", lang),
                            format="DD/MM/YYYY HH:mm",
                        ),
                        "file": st.column_config.TextColumn(t("res_archive_file", lang)),
                        "size_str": st.column_config.TextColumn(t("res_archive_size", lang)),
                        "download_url": st.column_config.LinkColumn(
                            t("res_archive_dl", lang),
                            display_text="⬇",
                        ),
                    },
                )
            else:
                st.caption(t("res_archive_empty", lang))


def render(lang: str) -> None:
    res = st.session_state.get("result")
    st.markdown(eyebrow_html(4, t("step_results", lang), "results"),
                unsafe_allow_html=True)
    if res is None:
        _render_archive_log(lang)
        return

    sched = res.schedule
    total_blocks = len(res.assignments) + sum(s.get("n_blocks", len(s.get("issues", []))) for s in res.unschedulable)
    placed_pct = (len(res.assignments) / total_blocks * 100) if total_blocks else 0
    conflicts = len(res.violations)
    elapsed = res.stats.get("total_elapsed_s", 0)
    _min = "dk" if lang == "tr" else "min"
    elapsed_str = f"{elapsed:.0f} s" if elapsed < 60 else f"{elapsed/60:.1f} {_min}"
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
                           pd.DataFrame(sched["assignments"], columns=CSV_FIELDS).to_csv(index=False).encode("utf-8-sig"),
                           file_name="schedule.csv",
                           key="dl_csv")
        st.download_button(t("res_dl_pdf", lang), pdf_data,
                           file_name=pdf_name, mime=pdf_mime, key="dl_pdf")

    _render_archive_log(lang)

    if res.unschedulable:
        with st.expander(t("res_unsched_title", lang, n=len(res.unschedulable))):
            st.markdown(unschedulable_html(res.unschedulable, lang),
                        unsafe_allow_html=True)
