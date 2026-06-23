"""Step 4 — School Settings: institutional policy, preference weights, instructor
availability, and a downloadable school profile. Thin Streamlit over the pure
timetabling.settings module; every value lives in st.session_state until solve time
(timetabling.settings.build_config turns it into a Config). Mobile-portrait: single
column, collapsible expanders, pick-one-edit forms (mirrors views/classrooms.py)."""
from html import escape

import streamlit as st

from timetabling.ui_style import eyebrow_html
from timetabling.i18n import t, DAY_LABELS, DAY_LABELS_FULL
from timetabling.settings import profile_to_json, profile_from_json, _LEGACY_LEVEL
from timetabling.ui_input import normalize_name, grad_dept_codes

_LEVELS = ("low", "medium", "high")
_MIDDAY = 13  # hardcoded AM/PM boundary; no longer a user-facing setting
_WEIGHT_KNOBS = ("maxrun", "instr_days", "room_stable")


def _hour_select(col, label: str, lo: int, hi: int, cur, key: str, help: str = "") -> int:
    """Native HH:00 selectbox over [lo, hi]. Returns the chosen hour as int.
    (st.number_input rejects a ':00' literal in format=, so we list the hours.)"""
    opts = [f"{h:02d}:00" for h in range(lo, hi + 1)]
    cur_s = f"{int(cur):02d}:00"
    raw = col.selectbox(label, opts,
                        index=opts.index(cur_s) if cur_s in opts else 0,
                        key=key, help=help or None)
    return int(raw.split(":")[0])


def _emails(courses) -> list:
    """Unique instructor emails from the uploaded course list (availability is keyed by email)."""
    seen = []
    for r in courses:
        for e in str(r.get("Instructor Email", "")).split(","):
            e = e.strip()
            if e and e not in seen:
                seen.append(e)
    return sorted(seen)


def _email_labels(courses) -> tuple[list[str], dict[str, str], dict[str, str]]:
    """Return (display_labels, label→email map, email→name map) for the instructor selectbox.

    Display format: "Name (email)" when a name is available, else just "email".
    Availability is keyed by email, so the map lets callers recover the email from
    the selected label without parsing.
    """
    # Identity key = email when present, else the normalized display name — the
    # same key build_sections uses for instructor_ids, so availability matches.
    id_to_name: dict[str, str] = {}
    for r in courses:
        emails = [e.strip() for e in str(r.get("Instructor Email", "")).split(",") if e.strip()]
        names = [n.strip() for n in str(r.get("Instructor Name", "")).split(",")]
        if emails:
            for i, email in enumerate(emails):
                id_to_name.setdefault(email, names[i] if i < len(names) else "")
        else:
            for n in names:
                if n.strip():
                    id_to_name.setdefault(normalize_name(n), n.strip())

    labels: list[str] = []
    label_to_email: dict[str, str] = {}
    for key in sorted(id_to_name):
        name = id_to_name[key]
        label = f"{name} ({key})" if (name and name.lower() != key) else (name or key)
        labels.append(label)
        label_to_email[label] = key
    return labels, label_to_email, id_to_name


def _bump() -> None:
    st.session_state["set_rev"] = st.session_state.get("set_rev", 0) + 1


def _work_days(s) -> list:
    return ["Mo", "Tu", "We", "Th", "Fr"] + (["Sa"] if s.get("saturday") else [])


def render(lang: str) -> None:
    st.markdown(eyebrow_html(2, t("step_settings", lang), "settings"),
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
        st.caption(t("set_policy_desc", lang))
        # Cap the hour dropdowns to the stepper width; responsive (shrinks on
        # narrow viewports, never overflows — see CLAUDE.md mobile-portrait rule).
        st.markdown(
            "<style>.st-key-set_day_start,.st-key-set_day_end,"
            ".st-key-set_grad_start{max-width:260px;}</style>",
            unsafe_allow_html=True,
        )
        # Graduate courses are always scheduled; grad_start sits beside the undergrad
        # end-time as a third time-window control (no toggle).
        s["include_grad"] = True
        c1, c2, c3 = st.columns(3)
        s["day_start"] = _hour_select(c1, t("set_day_start", lang), 6, 12,
                                      s["day_start"], "set_day_start",
                                      help=t("set_day_start_help", lang))
        s["day_end"] = _hour_select(c2, t("set_day_end", lang), 13, 21,
                                    s["day_end"], "set_day_end",
                                    help=t("set_day_end_help", lang))
        s["grad_start"] = _hour_select(c3, t("set_grad_start", lang), 6, 20,
                                       s.get("grad_start", 18), "set_grad_start",
                                       help=t("set_grad_start_help", lang))
        c4, c5, _ = st.columns(3)
        s["max_theory_session"] = c4.number_input(t("set_max_theory", lang), min_value=1,
                                                  max_value=6, value=int(s["max_theory_session"]),
                                                  step=1, help=t("set_max_theory_help", lang),
                                                  key="set_maxtheory")
        s["max_block_len"] = c5.number_input(t("set_max_block", lang), min_value=1, max_value=8,
                                             value=int(s["max_block_len"]), step=1,
                                             help=t("set_max_block_help", lang), key="set_maxblock")
        s["saturday"] = st.toggle(t("set_saturday", lang), value=bool(s["saturday"]),
                                  help=t("set_saturday_help", lang), key="set_sat")
        _grad_by_dept(lang, s)

        # blackouts are a hard constraint -> keep them contiguous with the time-window/grad
        # block, above the preference-weights divider.
        st.divider()
        _blackouts(lang, s)

        st.divider()
        st.markdown(f"**{t('set_weights_header', lang)}**")
        st.caption(t("set_weights_desc", lang))
        disp = [t(f"set_w_{lv}", lang) for lv in _LEVELS]
        wc = st.columns(2)
        for i, knob in enumerate(_WEIGHT_KNOBS):
            cur = _LEGACY_LEVEL.get(s["weights"].get(knob, "medium"), s["weights"].get(knob, "medium"))
            idx = _LEVELS.index(cur) if cur in _LEVELS else 1
            chosen = wc[i % 2].segmented_control(t(f"set_w_{knob}", lang), disp,
                                                 default=disp[idx], key=f"set_w_{knob}",
                                                 help=t(f"set_w_{knob}_help", lang))
            if chosen is not None:
                s["weights"][knob] = _LEVELS[disp.index(chosen)]
        # instr_days target: companion to the "compact instructor days" priority dial above.
        # "No target" keeps the term off (no headroom); ≤4/≤3/≤2 give the dial something to
        # optimize toward. The priority dial is inert until a target is picked (build_config
        # forces w_instr_days=0 at "No target").
        _t_opts = (0, 4, 3, 2)
        t_disp = [t("set_instr_days_no_target", lang) if v == 0
                  else t("set_instr_days_at_most", lang, n=v) for v in _t_opts]
        try:
            cur_t = int(s.get("instr_days_target", 0) or 0)
        except (TypeError, ValueError):
            cur_t = 0
        t_idx = _t_opts.index(cur_t) if cur_t in _t_opts else 0
        chosen_t = wc[1].segmented_control(t("set_instr_days_target", lang), t_disp,
                                           default=t_disp[t_idx], key="set_instr_days_target",
                                           help=t("set_instr_days_target_help", lang))
        if chosen_t is not None:
            s["instr_days_target"] = _t_opts[t_disp.index(chosen_t)]
        # free_day: controlled by which cohort year-levels want a free day (the gate showed a
        # strength slider can't steer it; the year selection IS its on/off control).
        cur_years = [int(y) for y in s.get("free_day_years", []) if str(y).strip().isdigit()]
        picked = st.multiselect(t("set_free_day_years", lang), [1, 2, 3, 4, 5, 6],
                                default=[y for y in cur_years if 1 <= y <= 6],
                                format_func=lambda y: t("set_year_n", lang, n=y),
                                help=t("set_free_day_years_help", lang),
                                key="set_free_day_years")
        s["free_day_years"] = list(picked)


def _grad_by_dept(lang: str, s: dict) -> None:
    """Per-department graduate earliest-start overrides. Lists the graduate dept codes from
    the uploaded course list; for each picked dept, an hour select sets its floor. Writes
    s['grad_start_by_dept'] = {dept: hour} (build_config validates + upper-cases)."""
    courses = st.session_state.get("courses", []) or []
    depts = grad_dept_codes(courses)
    if not depts:
        return
    cur = dict(s.get("grad_start_by_dept", {}) or {})
    rev = st.session_state.get("set_rev", 0)
    picked = st.multiselect(t("set_grad_dept_pick", lang), depts,
                            default=[d for d in depts if d in cur],
                            help=t("set_grad_dept_help", lang), key=f"grad_dept_{rev}")
    new: dict = {}
    if picked:
        gcols = st.columns(min(len(picked), 3))
        for i, d in enumerate(picked):
            h = _hour_select(gcols[i % len(gcols)], d, 6, 20,
                             int(cur.get(d, s.get("grad_start", 18))),
                             f"grad_dept_h_{d}_{rev}")
            new[d] = int(h)
    s["grad_start_by_dept"] = new


def _blackouts(lang: str, s: dict) -> None:
    st.markdown(f"**{t('set_blackout_header', lang)}**")
    st.caption(t("set_blackout_desc", lang))
    dl_full = DAY_LABELS_FULL.get(lang, DAY_LABELS_FULL["en"])
    bl = s.setdefault("blackouts", [])
    # chips: group by (day, scope), collapse consecutive hours into compact range labels
    if bl:
        grouped: dict = {}      # (day, staff) -> set(hours)
        for row in bl:
            grouped.setdefault((row[0], bool(row[2])), set()).add(int(row[1]))
        ci = 0
        for (day, staff), hours in grouped.items():
            staff_html = (f'<span class="bl-st"> · {t("set_scope_staff", lang)}</span>'
                          if staff else "")
            for label in _fmt_ranges(hours):
                start_h, end_h = int(label[:2]), int(label.split("–")[1][:2])
                rng = set(range(start_h, end_h))
                cc = st.columns([6, 1], vertical_alignment="center")
                cc[0].markdown(
                    f'<span class="bl-chip"><span class="bl-ic">⊘</span>'
                    f'{dl_full.get(day, day)} {label}{staff_html}</span>',
                    unsafe_allow_html=True,
                )
                if cc[1].button("✕", key=f"bl_rm_{day}_{staff}_{start_h}_{ci}"):
                    s["blackouts"] = [r for r in bl
                                      if not (r[0] == day and bool(r[2]) == staff
                                              and int(r[1]) in rng)]
                    _bump()
                    st.rerun()
                ci += 1
    else:
        st.markdown(
            f'<div style="padding:6px 0 10px;">'
            f'<span class="bl-chip" style="opacity:.55;background:var(--surface-2)!important;'
            f'border-color:var(--border)!important;color:var(--muted)!important;">'
            f'<span class="bl-ic">—</span>{escape(t("set_blackout_none", lang))}</span>'
            f'</div>',
            unsafe_allow_html=True)

    rev = st.session_state.get("set_rev", 0)
    scope_opts = [t("set_scope_all", lang), t("set_scope_staff", lang)]
    a1, a2, a3, a4 = st.columns([2.4, 1, 1, 0.9], vertical_alignment="bottom")
    nd = a1.multiselect(t("set_blackout_day_scope", lang), _work_days(s),
                        format_func=lambda d: dl_full.get(d, d), key=f"bl_days_{rev}",
                        placeholder=t("set_blackout_day_placeholder", lang))
    nf = _hour_select(a2, t("set_blackout_hour_from", lang), 6, 20, 13, f"bl_from_{rev}")
    nt = _hour_select(a3, t("set_blackout_hour_to", lang), 7, 21, 17, f"bl_to_{rev}")
    add_clicked = a4.button(t("set_blackout_add", lang), icon=":material/add:",
                            key=f"bl_add_{rev}", type="primary")
    nscope = st.segmented_control(t("set_blackout_scope", lang), scope_opts,
                                  default=scope_opts[0], key=f"bl_scope_{rev}")
    if add_clicked:
        staff = nscope == scope_opts[1]
        if nd and nt > nf:
            bl.extend(r for r in _expand_blackout(nd, nf, nt, staff) if r not in bl)
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


def _expand_blackout(days, h_from, h_to, staff):
    """(days, [h_from, h_to)) -> list of [day, hour, staff] triples, de-duped order-preserving."""
    out = []
    for d in days:
        for h in range(int(h_from), int(h_to)):
            row = [d, int(h), bool(staff)]
            if row not in out:
                out.append(row)
    return out


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
        labels, label_to_email, email_to_name = _email_labels(st.session_state.get("courses", []))
        if not labels:
            st.caption(t("set_avail_none_instr", lang))
            return
        avail = st.session_state["availability"]
        s = st.session_state["settings"]
        dl = DAY_LABELS.get(lang, DAY_LABELS["en"])
        rev = st.session_state.get("set_rev", 0)
        st.caption(t("set_avail_hint", lang))
        selected_label = st.selectbox(t("set_avail_pick", lang), labels, key=f"av_who_{rev}")
        who = label_to_email[selected_label]

        days = _work_days(s)
        day_start, day_end = _win(s)
        midday = _MIDDAY
        hours = list(range(day_start, day_end))
        by_day = _slots_to_hours(avail.get(who, []), day_start, day_end, midday)
        cur = {(d, h) for d, hs in by_day.items() for h in hs}
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
            for i_em, (em, slots) in enumerate(restricted.items()):
                em_days = _slots_to_hours(slots, day_start, day_end, _MIDDAY)
                name = email_to_name.get(em, "")
                display = f"{name} ({em})" if (name and name.lower() != em) else em
                with st.container(key=f"av_row_{i_em}_{rev}"):
                    st.markdown(f"<span class='av-sum-who'>{escape(display)}</span>",
                                unsafe_allow_html=True)
                    for d in days:
                        if d not in em_days:
                            continue
                        hs = sorted(em_days[d])
                        ri = 0
                        while ri < len(hs):
                            rj = ri
                            while rj + 1 < len(hs) and hs[rj + 1] == hs[rj] + 1:
                                rj += 1
                            range_hours = set(hs[ri:rj + 1])
                            chip_label = f"{dl.get(d, d)} {hs[ri]:02d}:00–{hs[rj] + 1:02d}:00"
                            if st.button(chip_label, key=f"av_rm_{i_em}_{d}_{hs[ri]}_{rev}"):
                                new_slots = [e for e in (avail.get(em) or [])
                                             if not (e[0] == d and int(e[1]) in range_hours)]
                                if new_slots:
                                    avail[em] = new_slots
                                else:
                                    avail.pop(em, None)
                                _bump()
                                st.rerun()
                            ri = rj + 1


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
