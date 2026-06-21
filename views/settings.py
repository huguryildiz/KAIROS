"""Step 4 — School Settings: institutional policy, preference weights, instructor
availability, and a downloadable school profile. Thin Streamlit over the pure
timetabling.settings module; every value lives in st.session_state until solve time
(timetabling.settings.build_config turns it into a Config). Mobile-portrait: single
column, collapsible expanders, pick-one-edit forms (mirrors views/classrooms.py)."""
import streamlit as st

from timetabling.ui_style import eyebrow_html
from timetabling.i18n import t, DAY_LABELS
from timetabling.settings import profile_to_json, profile_from_json

_LEVELS = ("off", "normal", "strong")
_WEIGHT_KNOBS = ("evening", "cohort_gap", "room_count", "instr_days")


def _emails(courses) -> list:
    """Unique lecturer emails from the uploaded course list (availability is keyed by email)."""
    seen = []
    for r in courses:
        for e in str(r.get("Lecturer Email", "")).split(","):
            e = e.strip()
            if e and e not in seen:
                seen.append(e)
    return sorted(seen)


def _bump() -> None:
    st.session_state["set_rev"] = st.session_state.get("set_rev", 0) + 1


def _work_days(s) -> list:
    return ["Mo", "Tu", "We", "Th", "Fr"] + (["Sa"] if s.get("saturday") else [])


def render(lang: str) -> None:
    st.markdown(eyebrow_html(4, t("step_settings", lang), "settings"),
                unsafe_allow_html=True)
    st.caption(t("set_caption", lang))
    s = st.session_state["settings"]
    _policy(lang, s)
    _availability(lang)
    _profile(lang)


def _policy(lang: str, s: dict) -> None:
    with st.expander(t("set_policy_header", lang), expanded=True, icon=":material/tune:"):
        c1, c2, c3 = st.columns(3)
        s["day_start"] = c1.number_input(t("set_day_start", lang), min_value=6, max_value=12,
                                         value=int(s["day_start"]), step=1, key="set_day_start")
        s["day_end"] = c2.number_input(t("set_day_end", lang), min_value=13, max_value=21,
                                       value=int(s["day_end"]), step=1, key="set_day_end")
        s["midday_split"] = c3.number_input(t("set_midday", lang), min_value=10, max_value=16,
                                            value=int(s["midday_split"]), step=1, key="set_midday")
        c4, c5, c6 = st.columns(3)
        s["max_theory_session"] = c4.number_input(t("set_max_theory", lang), min_value=1,
                                                  max_value=6, value=int(s["max_theory_session"]),
                                                  step=1, key="set_maxtheory")
        s["max_block_len"] = c5.number_input(t("set_max_block", lang), min_value=1, max_value=8,
                                             value=int(s["max_block_len"]), step=1, key="set_maxblock")
        s["daily_hours_cap"] = c6.number_input(t("set_daily_cap", lang), min_value=0, max_value=12,
                                               value=int(s["daily_hours_cap"]), step=1,
                                               help=t("set_daily_cap_help", lang), key="set_dailycap")
        c7, c8 = st.columns(2)
        s["saturday"] = c7.checkbox(t("set_saturday", lang), value=bool(s["saturday"]), key="set_sat")
        s["include_grad"] = c8.checkbox(t("set_include_grad", lang),
                                        value=bool(s["include_grad"]), key="set_grad")

        st.divider()
        st.markdown(f"**{t('set_weights_header', lang)}**")
        disp = [t(f"set_w_{lv}", lang) for lv in _LEVELS]
        wc = st.columns(2)
        for i, knob in enumerate(_WEIGHT_KNOBS):
            cur = s["weights"].get(knob, "normal")
            idx = _LEVELS.index(cur) if cur in _LEVELS else 1
            chosen = wc[i % 2].selectbox(t(f"set_w_{knob}", lang), disp, index=idx,
                                         key=f"set_w_{knob}")
            s["weights"][knob] = _LEVELS[disp.index(chosen)]

        st.divider()
        _blackouts(lang, s)


def _blackouts(lang: str, s: dict) -> None:
    st.markdown(f"**{t('set_blackout_header', lang)}**")
    dl = DAY_LABELS.get(lang, DAY_LABELS["en"])
    bl = s.setdefault("blackouts", [])
    if bl:
        for i, row in enumerate(list(bl)):
            day, hour, staff = row[0], int(row[1]), bool(row[2])
            label = f"{dl.get(day, day)} {hour:02d}:00"
            if staff:
                label += f" · {t('set_blackout_staff', lang)}"
            cc = st.columns([5, 1])
            cc[0].write(label)
            if cc[1].button("✕", key=f"bl_rm_{i}"):
                bl.pop(i)
                _bump()
                st.rerun()
    else:
        st.caption(t("set_blackout_none", lang))

    rev = st.session_state.get("set_rev", 0)
    a1, a2, a3, a4 = st.columns([2, 1.4, 1.8, 1], vertical_alignment="bottom")
    nd = a1.selectbox(t("set_blackout_day", lang), _work_days(s),
                      format_func=lambda d: dl.get(d, d), key=f"bl_day_{rev}")
    nh = a2.number_input(t("set_blackout_hour", lang), min_value=6, max_value=21,
                         value=12, step=1, key=f"bl_hour_{rev}")
    nst = a3.checkbox(t("set_blackout_staff", lang), key=f"bl_staff_{rev}")
    if a4.button(t("set_blackout_add", lang), use_container_width=True, key=f"bl_add_{rev}"):
        bl.append([nd, int(nh), bool(nst)])
        _bump()
        st.rerun()


def _availability(lang: str) -> None:
    with st.expander(t("set_avail_header", lang), icon=":material/event_available:"):
        emails = _emails(st.session_state.get("courses", []))
        if not emails:
            st.caption(t("set_avail_none_instr", lang))
            return
        avail = st.session_state["availability"]
        s = st.session_state["settings"]
        dl = DAY_LABELS.get(lang, DAY_LABELS["en"])
        rev = st.session_state.get("set_rev", 0)
        who = st.selectbox(t("set_avail_pick", lang), emails, key=f"av_who_{rev}")
        cur = {(d, h) for d, h in avail.get(who, [])}
        st.caption(t("set_avail_hint", lang))

        head = st.columns([2, 1, 1])
        head[1].markdown(f"**{t('set_avail_am', lang)}**")
        head[2].markdown(f"**{t('set_avail_pm', lang)}**")
        picked = []
        for d in _work_days(s):
            row = st.columns([2, 1, 1])
            row[0].write(dl.get(d, d))
            am = row[1].checkbox(f"{d} AM", value=(d, "AM") in cur,
                                 label_visibility="collapsed", key=f"av_{who}_{d}_AM_{rev}")
            pm = row[2].checkbox(f"{d} PM", value=(d, "PM") in cur,
                                 label_visibility="collapsed", key=f"av_{who}_{d}_PM_{rev}")
            if am:
                picked.append([d, "AM"])
            if pm:
                picked.append([d, "PM"])
        if st.button(t("set_avail_save", lang), type="primary", key=f"av_save_{rev}"):
            if picked:
                avail[who] = picked
            else:
                avail.pop(who, None)
            _bump()
            st.success(t("set_avail_saved", lang, who=who))
            st.rerun()

        restricted = {k: v for k, v in avail.items() if v}
        if restricted:
            st.caption(t("set_avail_summary", lang, n=len(restricted)))
            for em, slots in restricted.items():
                lab = ", ".join(f"{dl.get(d, d)} {h}" for d, h in slots)
                st.write(f"· {em}: {lab}")


def _profile(lang: str) -> None:
    with st.expander(t("set_profile_header", lang), icon=":material/badge:"):
        s = st.session_state["settings"]
        a = st.session_state["availability"]
        st.download_button(t("set_profile_download", lang), data=profile_to_json(s, a),
                           file_name="kairos_school_profile.json", mime="application/json",
                           use_container_width=True, key="prof_dl")
        up = st.file_uploader(t("set_profile_upload", lang), type=["json"], key="prof_up")
        if up is not None:
            try:
                new_s, new_a = profile_from_json(up.getvalue().decode("utf-8"))
            except Exception:
                st.error(t("set_profile_error", lang))
            else:
                st.session_state["settings"] = new_s
                st.session_state["availability"] = new_a
                _bump()
                st.success(t("set_profile_loaded", lang))
                st.rerun()
