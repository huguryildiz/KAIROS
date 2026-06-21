"""Step 4 — School Settings: institutional policy, preference weights, instructor
availability, and a downloadable school profile. Thin Streamlit over the pure
timetabling.settings module; every value lives in st.session_state until solve time
(timetabling.settings.build_config turns it into a Config). Mobile-portrait: single
column, collapsible expanders, pick-one-edit forms (mirrors views/classrooms.py)."""
from html import escape

import streamlit as st

from timetabling.ui_style import eyebrow_html
from timetabling.i18n import t, DAY_LABELS
from timetabling.settings import profile_to_json, profile_from_json

_LEVELS = ("off", "normal", "strong")
_MIDDAY = 13  # hardcoded AM/PM boundary; no longer a user-facing setting
_WEIGHT_KNOBS = ("evening", "cohort_gap", "room_count", "instr_days")


def _emails(courses) -> list:
    """Unique instructor emails from the uploaded course list (availability is keyed by email)."""
    seen = []
    for r in courses:
        for e in str(r.get("Instructor Email", "")).split(","):
            e = e.strip()
            if e and e not in seen:
                seen.append(e)
    return sorted(seen)


def _email_labels(courses) -> tuple[list[str], dict[str, str]]:
    """Return (display_labels, label→email map) for the instructor selectbox.

    Display format: "Name (email)" when a name is available, else just "email".
    Availability is keyed by email, so the map lets callers recover the email from
    the selected label without parsing.
    """
    email_to_name: dict[str, str] = {}
    for r in courses:
        emails = [e.strip() for e in str(r.get("Instructor Email", "")).split(",") if e.strip()]
        names = [n.strip() for n in str(r.get("Instructor Name", "")).split(",")]
        for i, email in enumerate(emails):
            if email not in email_to_name:
                name = names[i] if i < len(names) else ""
                email_to_name[email] = name

    labels: list[str] = []
    label_to_email: dict[str, str] = {}
    for email in sorted(email_to_name):
        name = email_to_name[email]
        label = f"{name} ({email})" if name else email
        labels.append(label)
        label_to_email[label] = email
    return labels, label_to_email


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
    # School-profile import/export is disabled: an out-of-spec JSON upload can crash
    # profile_from_json, and the feature has no clear use yet. Re-enable once the
    # upload path validates the schema defensively. Keep _profile() for that.
    # _profile(lang)


def _policy(lang: str, s: dict) -> None:
    with st.expander(t("set_policy_header", lang), expanded=True, icon=":material/tune:"):
        c1, c2, c3 = st.columns(3)
        s["day_start"] = c1.number_input(t("set_day_start", lang), min_value=6, max_value=12,
                                         value=int(s["day_start"]), step=1,
                                         help=t("set_day_start_help", lang), key="set_day_start")
        s["day_end"] = c2.number_input(t("set_day_end", lang), min_value=13, max_value=21,
                                       value=int(s["day_end"]), step=1,
                                       help=t("set_day_end_help", lang), key="set_day_end")
        s["max_theory_session"] = c3.number_input(t("set_max_theory", lang), min_value=1,
                                                  max_value=6, value=int(s["max_theory_session"]),
                                                  step=1, help=t("set_max_theory_help", lang),
                                                  key="set_maxtheory")
        c4, c5, c6 = st.columns(3)
        s["max_block_len"] = c4.number_input(t("set_max_block", lang), min_value=1, max_value=8,
                                             value=int(s["max_block_len"]), step=1,
                                             help=t("set_max_block_help", lang), key="set_maxblock")
        s["daily_hours_cap"] = c5.number_input(t("set_daily_cap", lang), min_value=0, max_value=12,
                                               value=int(s["daily_hours_cap"]), step=1,
                                               help=t("set_daily_cap_help", lang), key="set_dailycap")
        s["instr_days_cap"] = c6.number_input(t("set_days_cap", lang), min_value=0, max_value=6,
                                              value=int(s.get("instr_days_cap", 0)), step=1,
                                              help=t("set_days_cap_help", lang), key="set_dayscap")
        c7, c8 = st.columns(2)
        s["saturday"] = c7.toggle(t("set_saturday", lang), value=bool(s["saturday"]),
                                  help=t("set_saturday_help", lang), key="set_sat")
        s["include_grad"] = c8.toggle(t("set_include_grad", lang),
                                      value=bool(s["include_grad"]), key="set_grad")
        if s["include_grad"]:
            _gc1, gc2 = st.columns(2)
            s["grad_start"] = gc2.number_input(
                t("set_grad_start", lang), min_value=6, max_value=20,
                value=int(s.get("grad_start", 18)), step=1,
                help=t("set_grad_start_help", lang), key="set_grad_start")

        s["lunch_enabled"] = st.toggle(t("set_lunch", lang),
                                       value=bool(s.get("lunch_enabled", False)),
                                       help=t("set_lunch_help", lang), key="set_lunch")
        if s["lunch_enabled"]:
            lc1, lc2, _ = st.columns([1, 1, 2])
            s["lunch_start"] = lc1.number_input(t("set_lunch_start", lang), min_value=9,
                                                max_value=16, value=int(s.get("lunch_start", 12)),
                                                step=1, key="set_lunch_start")
            s["lunch_end"] = lc2.number_input(t("set_lunch_end", lang), min_value=10,
                                              max_value=17, value=int(s.get("lunch_end", 13)),
                                              step=1, key="set_lunch_end")

        st.divider()
        st.markdown(f"**{t('set_weights_header', lang)}**")
        disp = [t(f"set_w_{lv}", lang) for lv in _LEVELS]
        wc = st.columns(2)
        for i, knob in enumerate(_WEIGHT_KNOBS):
            cur = s["weights"].get(knob, "normal")
            idx = _LEVELS.index(cur) if cur in _LEVELS else 1
            chosen = wc[i % 2].segmented_control(t(f"set_w_{knob}", lang), disp,
                                                 default=disp[idx], key=f"set_w_{knob}",
                                                 help=t(f"set_w_{knob}_help", lang))
            if chosen is not None:
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
            day_label = dl.get(day, day)
            staff_html = (f'<span class="bl-st"> · {t("set_scope_staff", lang)}</span>'
                          if staff else "")
            cc = st.columns([6, 1], vertical_alignment="center")
            cc[0].markdown(
                f'<span class="bl-chip"><span class="bl-ic">⊘</span>'
                f'{day_label} {hour:02d}:00{staff_html}</span>',
                unsafe_allow_html=True,
            )
            if cc[1].button("✕", key=f"bl_rm_{i}"):
                bl.pop(i)
                _bump()
                st.rerun()
    else:
        st.caption(t("set_blackout_none", lang))

    rev = st.session_state.get("set_rev", 0)
    scope_opts = [t("set_scope_all", lang), t("set_scope_staff", lang)]
    a1, a2, a3, a4 = st.columns([2, 1.2, 2.2, 0.9], vertical_alignment="bottom")
    nd = a1.selectbox(t("set_blackout_day", lang), _work_days(s),
                      format_func=lambda d: dl.get(d, d), key=f"bl_day_{rev}")
    nh = a2.number_input(t("set_blackout_hour", lang), min_value=6, max_value=21,
                         value=12, step=1, key=f"bl_hour_{rev}")
    nscope = a3.segmented_control(t("set_blackout_scope", lang), scope_opts,
                                  default=scope_opts[0], key=f"bl_scope_{rev}")
    if a4.button(t("set_blackout_add", lang), icon=":material/add:", key=f"bl_add_{rev}", type="primary"):
        nst = nscope == scope_opts[1]
        bl.append([nd, int(nh), bool(nst)])
        _bump()
        st.rerun()


def _win(s) -> tuple[int, int]:
    """(day_start, day_end) from settings, as ints with sane fallbacks."""
    def g(k, d):
        try:
            return int(s.get(k, d))
        except (TypeError, ValueError):
            return d
    return g("day_start", 9), g("day_end", 18)


def _slots_to_hours(slots, day_start, day_end, midday) -> dict:
    """Group an availability list ([[day, hour|"AM"|"PM"], ...]) into {day: set(hours)}.
    Legacy half-day codes are expanded against the current window so old data still shows."""
    by_day: dict = {}
    for entry in slots or []:
        try:
            d, val = entry[0], entry[1]
        except (TypeError, IndexError):
            continue
        code = str(val).upper()
        if code == "AM":
            hrs = range(day_start, midday)
        elif code == "PM":
            hrs = range(midday, day_end)
        else:
            try:
                hrs = (int(val),)
            except (TypeError, ValueError):
                continue
        by_day.setdefault(d, set()).update(hrs)
    return by_day


def _fmt_ranges(hours) -> list:
    """Collapse a set of hours into compact range labels, e.g. {9,10,11} → ['09:00–12:00']."""
    hs = sorted(set(hours))
    out, i = [], 0
    while i < len(hs):
        j = i
        while j + 1 < len(hs) and hs[j + 1] == hs[j] + 1:
            j += 1
        out.append(f"{hs[i]:02d}:00–{hs[j] + 1:02d}:00")
        i = j + 1
    return out


def _availability(lang: str) -> None:
    with st.expander(t("set_avail_header", lang), icon=":material/event_available:"):
        labels, label_to_email = _email_labels(st.session_state.get("courses", []))
        if not labels:
            st.caption(t("set_avail_none_instr", lang))
            return
        avail = st.session_state["availability"]
        s = st.session_state["settings"]
        dl = DAY_LABELS.get(lang, DAY_LABELS["en"])
        rev = st.session_state.get("set_rev", 0)
        selected_label = st.selectbox(t("set_avail_pick", lang), labels, key=f"av_who_{rev}")
        who = label_to_email[selected_label]

        days = _work_days(s)
        day_start, day_end = _win(s)
        midday = _MIDDAY
        hours = list(range(day_start, day_end))
        by_day = _slots_to_hours(avail.get(who, []), day_start, day_end, midday)
        cur = {(d, h) for d, hs in by_day.items() for h in hs}

        st.caption(t("set_avail_hint", lang))
        st.markdown(
            "<div class='hm-leg'>"
            f"<span><i class='av'></i>{escape(t('set_avail_free', lang))}</span>"
            f"<span><i class='bl'></i>{escape(t('set_avail_blocked', lang))}</span>"
            f"<span>{escape(t('set_avail_count', lang, n=len(cur)))}</span>"
            "</div>",
            unsafe_allow_html=True,
        )

        picked = []
        ncol = len(days) + 1
        with st.container(key="av_hm"):
            head = st.columns(ncol)
            head[0].markdown("<div class='hm-dh'></div>", unsafe_allow_html=True)
            for i, d in enumerate(days):
                head[i + 1].markdown(f"<div class='hm-dh'>{escape(dl.get(d, d))}</div>",
                                     unsafe_allow_html=True)
            for h in hours:
                if h == midday and day_start < midday < day_end:
                    st.markdown("<div class='hm-mid'></div>", unsafe_allow_html=True)
                row = st.columns(ncol)
                row[0].markdown(f"<div class='hm-tl'>{h:02d}:00</div>", unsafe_allow_html=True)
                for i, d in enumerate(days):
                    on = row[i + 1].checkbox(
                        f"{dl.get(d, d)} {h:02d}:00", value=(d, h) in cur,
                        label_visibility="collapsed", key=f"av_{who}_{d}_{h}_{rev}")
                    if on:
                        picked.append([d, h])

        bcols = st.columns([1, 2, 3])
        if bcols[0].button(t("set_avail_save", lang), type="primary",
                           icon=":material/check_circle:",
                           key=f"av_save_{rev}"):
            if picked:
                avail[who] = picked
            else:
                avail.pop(who, None)
            _bump()
            st.success(t("set_avail_saved", lang, who=who))
            st.rerun()
        if cur and bcols[1].button(t("set_avail_clear", lang), icon=":material/delete_sweep:",
                                   key=f"av_clr_{rev}"):
            avail.pop(who, None)
            _bump()
            st.rerun()

        restricted = {k: v for k, v in avail.items() if v}
        if restricted:
            st.caption(t("set_avail_summary", lang, n=len(restricted)))
            rows_html = []
            for em, slots in restricted.items():
                em_days = _slots_to_hours(slots, day_start, day_end, _MIDDAY)
                chips = "".join(
                    f"<span class='av-chip'>{escape(dl.get(d, d))} {rng}</span>"
                    for d in days if d in em_days
                    for rng in _fmt_ranges(em_days[d])
                )
                rows_html.append(
                    f"<div class='av-sum-row'><span class='av-sum-who'>{escape(em)}</span>{chips}</div>")
            st.markdown(f"<div class='av-sum'>{''.join(rows_html)}</div>", unsafe_allow_html=True)


def _profile(lang: str) -> None:
    with st.expander(t("set_profile_header", lang), icon=":material/badge:"):
        s = st.session_state["settings"]
        a = st.session_state["availability"]
        st.download_button(t("set_profile_download", lang), data=profile_to_json(s, a),
                           file_name="kairos_school_profile.json", mime="application/json",
                           key="prof_dl")
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
