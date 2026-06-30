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


def _label_with_detail(value: str, detail: str) -> str:
    value = str(value or "").strip()
    detail = str(detail or "").strip()
    if detail and detail != value:
        return f"{value} · {detail}"
    return value


def _entity_label_func(sched: dict, view_field: str):
    """Return a stable selectbox label function without changing filter values."""
    by_cohort = {}
    by_course = {}
    name_to_email = {}
    for a in sched.get("assignments", []):
        cohort = str(a.get("cohort", "")).strip()
        department = str(a.get("department", "")).strip()
        if cohort and department and cohort not in by_cohort:
            by_cohort[cohort] = department

        course = str(a.get("course_code", "")).strip()
        course_name = str(a.get("course_name", "")).strip()
        if course and course_name and course not in by_course:
            by_course[course] = course_name

        name = str(a.get("instructor_name", "")).strip()
        email = str(a.get("instructor_id", "")).strip()
        if name and email and name not in name_to_email:
            name_to_email[name] = email

    if view_field == "cohort":
        return lambda v: _label_with_detail(v, by_cohort.get(str(v), ""))
    if view_field == "course_code":
        return lambda v: _label_with_detail(v, by_course.get(str(v), ""))
    if view_field == "instructor_name":
        return lambda n: f"{n} ({name_to_email[n]})" if n in name_to_email and "@" in name_to_email[n] else n
    return str


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
    fmt = _entity_label_func(sched, view_field)
    entity = c2.selectbox(t(VIEW_KEY[view_field], lang), entities, format_func=fmt)
    view = filter_assignments(sched, view_field, entity)
    st.markdown(week_grid_html(view, lang=lang), unsafe_allow_html=True)


    st.write("")
    # Downloads — JSON / CSV on one row, then per-dimension PDF buttons.
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

    # Per-dimension PDF downloads — one button per view dimension.
    _PDF_DIMS = [
        ("cohort",          "res_dl_pdf_cohort"),
        ("instructor_name", "res_dl_pdf_instructor"),
        ("room",            "res_dl_pdf_room"),
        ("department",      "res_dl_pdf_dept"),
        ("course_code",     "res_dl_pdf_course"),
    ]
    st.caption(t("res_dl_pdfs_title", lang))
    with st.container(horizontal=True, horizontal_alignment="center",
                      gap="small"):
        for dim_field, label_key in _PDF_DIMS:
            dim_entities = distinct_values(sched, dim_field)
            if not dim_entities:
                continue
            dim_label = t(VIEW_KEY[dim_field], lang)
            pdf_data, pdf_name, pdf_mime = _bundle(
                sched, dim_field, tuple(dim_entities), dim_label, lang)
            st.download_button(
                t(label_key, lang), pdf_data,
                file_name=pdf_name, mime=pdf_mime,
                key=f"dl_pdf_{dim_field}",
                icon=":material/picture_as_pdf:",
            )

    _render_archive_log(lang)

    if res.unschedulable:
        with st.expander(t("res_unsched_title", lang, n=len(res.unschedulable))):
            st.markdown(unschedulable_html(res.unschedulable, lang),
                        unsafe_allow_html=True)
