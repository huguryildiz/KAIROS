"""Step 3 — Classrooms: KPI chips + CSV upload + editable inventory (capacity, lab)."""
import pandas as pd
import streamlit as st

from timetabling.defaults import DEFAULT_CLASSROOMS, _lab
from timetabling.ui_input import _truthy
from timetabling.ui_style import kpi_chips_html, eyebrow_html, data_table_html
from timetabling.textnorm import parse_int
from timetabling.i18n import t


def _pick(cols: dict, *names):
    for n in names:
        if n in cols:
            return cols[n]
    return None


def _normalize_rooms(df: pd.DataFrame) -> list[dict]:
    """Map an uploaded CSV to the canonical Room/Cap/Lab records.

    Accepts the editor schema (Room/Cap/Lab) and the raw data format
    (ROOM/ROOM_CAP); column matching is case-insensitive. When no Lab
    column is present the flag is derived from the room name (-L / -PC).
    """
    cols = {str(c).strip().lower(): c for c in df.columns}
    room_c = _pick(cols, "room", "oda", "room_name")
    cap_c = _pick(cols, "cap", "room_cap", "kapasite", "capacity")
    lab_c = _pick(cols, "lab", "is_lab", "laboratuvar")
    if room_c is None:
        return []
    rooms = []
    for _, r in df.iterrows():
        name = str(r.get(room_c, "")).strip()
        if not name or name.lower() == "nan":
            continue
        cap = str(parse_int(r.get(cap_c), 0) or 0) if cap_c is not None else "0"
        lab = ("x" if _truthy(r.get(lab_c)) else "") if lab_c is not None else _lab(name)
        rooms.append({"Room": name, "Cap": cap, "Lab": lab})
    return rooms


def _bump() -> None:
    st.session_state["cr_rev"] = st.session_state.get("cr_rev", 0) + 1


def _upsert_room(rooms: list[dict], sel: str, rec: dict) -> list[dict]:
    """Insert or update ``rec`` in ``rooms`` (mutates and returns it). If ``sel``
    names an existing room, that row is replaced (so a rename works); otherwise a
    row already named ``rec['Room']`` is updated in place, else ``rec`` is
    appended. Keeps room names unique."""
    idx = next((i for i, r in enumerate(rooms) if r["Room"] == sel), None)
    if idx is not None:                              # editing the picked room
        rooms[idx] = rec
        return rooms
    dup = next((i for i, r in enumerate(rooms) if r["Room"] == rec["Room"]), None)
    if dup is not None:                              # new, but name already taken
        rooms[dup] = rec
    else:
        rooms.append(rec)
    return rooms


def render(lang: str) -> None:
    st.markdown(eyebrow_html(3, t("step_classrooms", lang), "classrooms"),
                unsafe_allow_html=True)
    st.caption(t("cr_caption", lang))

    rooms = st.session_state["classrooms"]
    caps = [parse_int(r.get("Cap"), 0) for r in rooms]
    labs = sum(1 for r in rooms if _truthy(r.get("Lab")))
    st.markdown(kpi_chips_html([
        (t("kpi_rooms", lang), str(len(rooms)), ""),
        (t("kpi_labs", lang), str(labs), ""),
        (t("kpi_maxcap", lang), str(max(caps) if caps else 0), ""),
        (t("kpi_online", lang), "∞", "good"),
    ]), unsafe_allow_html=True)

    col_up, col_rst = st.columns([3, 2], vertical_alignment="bottom")
    with col_up:
        with st.expander(t("cr_upload_expander", lang)):
            st.caption(t("cr_upload_hint", lang))
            st.markdown(
                data_table_html(
                    ["Room", "Cap", "Lab"],
                    [["A216", "25", ""], ["A211-PC-L", "99", "x"]],
                    max_height=160, numeric=("Cap",)),
                unsafe_allow_html=True)
            up = st.file_uploader(t("cr_upload_uploader", lang), type=["csv"], key="cr_upload")
            if up is not None:
                parsed = _normalize_rooms(pd.read_csv(up, dtype=str))
                if not parsed:
                    st.error(t("cr_upload_error", lang))
                elif parsed != st.session_state["classrooms"]:
                    st.session_state["classrooms"] = parsed
                    _bump()
                    st.success(t("cr_upload_loaded", lang, n=len(parsed)))
                    st.rerun()
    with col_rst:
        if st.button(t("cr_reset", lang), use_container_width=True):
            st.session_state["classrooms"] = [dict(r) for r in DEFAULT_CLASSROOMS]
            _bump()
            st.rerun()

    # Inventory — read-only themed table (glide's st.data_editor can't follow the
    # in-app dark theme; see ui_style._datagrid_css). Editing happens in the
    # compact form below so the whole step stays dark-correct and mobile-friendly.
    st.markdown(
        data_table_html(
            ["Room", "Cap", "Lab"],
            [[r.get("Room", ""), r.get("Cap", ""),
              "✓" if _truthy(r.get("Lab")) else ""] for r in rooms],
            max_height=320, numeric=("Cap",)),
        unsafe_allow_html=True)
    st.caption(t("cr_count", lang, n=len(rooms)))

    _edit_form(lang, rooms)


def _edit_form(lang: str, rooms: list[dict]) -> None:
    """Single-row add/edit/remove form inside a collapsible expander."""
    rev = st.session_state.get("cr_rev", 0)
    with st.expander(t("cr_edit_header", lang)):
        new_label = t("cr_new_room", lang)
        options = [new_label] + [r["Room"] for r in rooms]

        c_sel, c_name, c_cap, c_lab, c_save, c_del = st.columns(
            [2, 2.5, 1.2, 0.7, 1.2, 1], vertical_alignment="bottom"
        )
        sel = c_sel.selectbox(t("cr_edit_pick", lang), options, key=f"cr_sel_{rev}",
                              label_visibility="collapsed")
        cur = next((r for r in rooms if r["Room"] == sel), None)

        name = c_name.text_input(t("cr_col_room", lang),
                                 value=(cur["Room"] if cur else ""),
                                 placeholder=t("cr_col_room", lang),
                                 key=f"cr_f_room_{rev}_{sel}",
                                 label_visibility="collapsed")
        cap = c_cap.number_input(t("cr_col_cap", lang), min_value=0, step=1,
                                 value=int(parse_int(cur["Cap"], 0)) if cur else 0,
                                 key=f"cr_f_cap_{rev}_{sel}",
                                 label_visibility="collapsed")
        lab = c_lab.checkbox(t("cr_col_lab", lang),
                             value=_truthy(cur["Lab"]) if cur else False,
                             key=f"cr_f_lab_{rev}_{sel}")

        if c_save.button(t("cr_save", lang), type="primary", use_container_width=True):
            name = name.strip()
            if not name:
                st.error(t("cr_need_name", lang))
            else:
                rec = {"Room": name, "Cap": str(int(cap)), "Lab": "x" if lab else ""}
                st.session_state["classrooms"] = _upsert_room(rooms, sel, rec)
                _bump()
                st.success(t("cr_saved", lang, room=name))
                st.rerun()
        if cur and c_del.button(t("cr_remove", lang), use_container_width=True):
            st.session_state["classrooms"] = [r for r in rooms if r["Room"] != sel]
            _bump()
            st.success(t("cr_removed", lang, room=sel))
            st.rerun()
