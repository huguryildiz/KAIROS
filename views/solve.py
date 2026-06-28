"""Step 5 — Solve: fixed time budget, run the pipeline. Upload-gated."""
from html import escape
import queue as _queue
import threading
import time as _time
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as _cmp

from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                  build_instructors_from_courselist, build_rooms_from_ui,
                                  classrooms_is_valid, courselist_is_valid)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline, AUTO_REPAIR_THRESHOLD
from timetabling.export import write_schedule_outputs
from timetabling.cloud_storage import upload_outputs_if_configured
from timetabling.i18n import t
from timetabling.ui_style import eyebrow_html

# Fixed solve budget (seconds). The largest real period (~800 sections) converges in
# ~5–10.5 min via the repair solver (README benchmark); 50 min is a hard upper bound with
# ~5x headroom for larger inputs, kept under Cloud Run's --timeout 3600 (~10 min margin for
# container startup + response streaming). Wired into both the CP-SAT and repair paths as a deadline.
# period is a label only (tags the schedule dict); the uploaded courselist defines what
# gets scheduled, so it is fixed here rather than chosen in the UI.
_SOLVE_SECONDS = 3000
_PERIOD = "001"


def render(lang: str) -> None:
    st.markdown(eyebrow_html(3, t("step_solve", lang), "solve"),
                unsafe_allow_html=True)

    courses = st.session_state.get("courses", [])
    st.caption(t("solve_ready", lang, c=len(courses),
                 r=len(st.session_state["classrooms"])))

    # Client-side watcher: arms window.onbeforeunload while .solve-running is present so
    # navigating away shows the browser's "Leave site?" dialog. The 0-height iframe runs
    # actual JS (inline <script> in st.markdown is inert under React). The wrapping
    # container is display:none (ui_style .st-key-solve_watch) so it adds no vertical gap.
    _warn_text = ("⚠ Çözüm devam ediyor — lütfen sayfadan ayrılmayın" if lang == "tr"
                  else "⚠ Solving in progress — please don't leave the page")
    with st.container(key="solve_watch"):
        _cmp.html(
            '<script>(function(){'
            'var D=window.parent.document,W=window.parent;'
            'function ensureBanner(){'
            'if(!D.getElementById("sp-warn-banner")){'
            'var b=D.createElement("div");b.id="sp-warn-banner";'
            f'b.textContent="{_warn_text}";'
            'D.body.appendChild(b);}}'
            'function removeBanner(){var b=D.getElementById("sp-warn-banner");if(b)b.remove();}'
            'function tick(){'
            'if(D.querySelector(".solve-running")){'
            'W.onbeforeunload=function(e){e.preventDefault();e.returnValue="";};'
            'ensureBanner();'
            '}else{W.onbeforeunload=null;removeBanner();}'
            'setTimeout(tick,800);}'
            'tick();'
            '})();</script>',
            height=0,
        )

    # Gate solving on both a validated courselist and an explicitly loaded classroom
    # inventory. session_state["classrooms"] starts empty, so cr_source being set
    # is the reliable signal that the user actually loaded classroom data.
    valid_courses = courselist_is_valid(courses)
    valid_rooms = bool(st.session_state.get("cr_source")) and classrooms_is_valid(
        st.session_state["classrooms"]
    )
    valid = valid_courses and valid_rooms

    if not valid_courses:
        st.warning(t("solve_blocked_courses", lang), icon="⚠️")
        if st.button(t("solve_go_to_data", lang), key="go_to_data",
                     type="secondary", icon=":material/arrow_upward:"):
            st.session_state["scroll_to"] = "upload"
            st.rerun()
    if not valid_rooms:
        st.warning(t("solve_blocked_classrooms", lang), icon="⚠️")
        if st.button(t("solve_go_to_classrooms", lang), key="go_to_classrooms",
                     type="secondary", icon=":material/arrow_upward:"):
            st.session_state["scroll_to"] = "classrooms"
            st.rerun()

    ph = st.empty()
    if ph.button(t("solve_button", lang), type="primary", key="solve_btn",
                 disabled=not valid):
        cfg = build_config(st.session_state["settings"],
                           st.session_state["availability"], _SOLVE_SECONDS,
                           availability_avoid=st.session_state.get("availability_avoid", {}),
                           availability_prefer=st.session_state.get("availability_prefer", {}))
        secs, _ = build_sections_from_courselist(courses, _PERIOD, cfg)
        instr = build_instructors_from_courselist(courses)
        rooms = build_rooms_from_ui(st.session_state["classrooms"], cfg)
        mark_virtual(secs, rooms, cfg)
        # For small inputs, cap the solver time so repair soft-polish and CP-SAT
        # don't run their full 50-min budget. Formula: 0.5s/block, floor 60s.
        if len(secs) <= 300:
            _cap = max(60.0, len(secs) * 0.5)
            cfg.solve_time_limit_s = min(cfg.solve_time_limit_s, _cap)
            cfg.repair_time_limit_s = min(cfg.repair_time_limit_s, _cap)

        # --- step progress bar helpers --------------------------------------
        # 5 phases map to indexed steps; each event drives the active dot.
        _STEP_KEYS = ["gen_candidates", "construct", "repair_sweep", "soft_polish", "validate"]
        _STEP_IDX  = {k: i for i, k in enumerate(_STEP_KEYS)}
        _STEPS_TR  = ["Adaylar", "Taslak", "Onarım", "Kalite", "Kontrol"]
        _STEPS_EN  = ["Slots",   "Build",  "Repair", "Polish", "Check"]

        def _fmt_detail(evt):
            key, *args = evt
            if lang == "tr":
                m = {
                    "gen_candidates": lambda n: f"{n} blok işleniyor...",
                    "construct":      lambda _: "İlk taslak oluşturuluyor...",
                    "repair_sweep":   lambda sw, n: f"Tur {sw} · {n} blok kaldı",
                    "soft_polish":    lambda _: "Program kalitesi iyileştiriliyor...",
                    "validate":       lambda _: "Kontroller yapılıyor...",
                }
            else:
                m = {
                    "gen_candidates": lambda n: f"Processing {n} blocks...",
                    "construct":      lambda _: "Building initial schedule...",
                    "repair_sweep":   lambda sw, n: f"Round {sw} · {n} remaining",
                    "soft_polish":    lambda _: "Optimizing schedule quality...",
                    "validate":       lambda _: "Validating schedule...",
                }
            fn = m.get(key)
            return fn(*args) if fn else ""

        # --- mini-grid animation card ---------------------------------------
        _days = ["Pzt", "Sal", "Çar", "Per", "Cum"] if lang == "tr" else ["Mon", "Tue", "Wed", "Thu", "Fri"]
        _days_html = "".join(f"<span>{d}</span>" for d in _days)
        _cells_html = "<i></i>" * 25
        _BLOCKS = [
            # (col, row_start, row_span, color, delay)
            (1, 1, 2, "#8E9BF2", "0.0s"),
            (1, 4, 1, "#E87CC4", "1.3s"),
            (2, 2, 2, "#6BC87A", "0.7s"),
            (2, 5, 1, "#B8A9F2", "2.1s"),
            (3, 1, 1, "#F29E4C", "0.4s"),
            (3, 3, 2, "#F2C84C", "1.6s"),
            (4, 2, 2, "#E87C7C", "1.0s"),
            (4, 5, 1, "#7EC8E3", "2.4s"),
            (5, 1, 2, "#82C98C", "1.8s"),
            (5, 4, 2, "#7BBEF2", "0.2s"),
        ]
        _blks_html = "".join(
            f'<div class="smg-blk" style="grid-column:{c};grid-row:{r}/span {s};--c:{col};--d:{d}"></div>'
            for c, r, s, col, d in _BLOCKS
        )
        _grid_html = (
            f'<div class="solve-mini-grid" aria-hidden="true">'
            f'<div class="smg-days">{_days_html}</div>'
            f'<div class="smg-board">'
            f'<div class="smg-cells">{_cells_html}</div>'
            f'<div class="smg-blocks">{_blks_html}</div>'
            f'<div class="smg-sweep"></div>'
            f'</div>'
            f'</div>'
        )

        def _render_card(step_idx, detail="", elapsed_s=0.0):
            labels = _STEPS_TR if lang == "tr" else _STEPS_EN
            fill_w = step_idx * 20  # dot centers at 10/30/50/70/90% → fill 0/20/40/60/80%
            nodes_html = ""
            for i, lbl in enumerate(labels):
                if i < step_idx:
                    cls = "sp-done"
                    dot = f'<div class="sp-dot" style="animation-delay:{i * 0.07:.2f}s">&#10003;</div>'
                elif i == step_idx:
                    cls = "sp-active"
                    dot = f'<div class="sp-dot">{i + 1}</div>'
                else:
                    cls = ""
                    dot = f'<div class="sp-dot">{i + 1}</div>'
                nodes_html += (
                    f'<div class="sp-node {cls}">'
                    f'{dot}'
                    f'<span class="sp-lbl">{lbl}</span>'
                    f'</div>'
                )
            m, s = divmod(int(elapsed_s), 60)
            elapsed_html = f'{m:02d}:{s:02d}'
            ph.markdown(
                f'<div class="solve-running">'
                f'{_grid_html}'
                f'<div class="sp-wrap">'
                f'<div class="sp-line-bg"></div>'
                f'<div class="sp-line-fill" style="--sp-fw:{fill_w}%"></div>'
                f'<div class="sp-nodes">{nodes_html}</div>'
                f'</div>'
                f'<div class="sp-detail">{escape(detail)}</div>'
                f'<div class="sp-elapsed">{elapsed_html}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

        # Render initial card before solver starts
        _init_detail = (f"{len(secs)} blok işleniyor..." if lang == "tr"
                        else f"Processing {len(secs)} blocks...")
        _render_card(0, _init_detail, 0.0)

        # --- run solver in background thread, poll progress queue -----------
        _q = _queue.Queue()
        _result = [None]
        _error = [None]
        _done = threading.Event()

        def _run():
            try:
                _result[0] = run_pipeline(_PERIOD, secs, rooms, instr, cfg,
                                          solver="auto", progress_cb=_q.put)
            except Exception as exc:
                _error[0] = exc
            finally:
                _done.set()

        threading.Thread(target=_run, daemon=True).start()

        _t_start = _time.perf_counter()
        _cur_step = 0
        _cur_detail = _init_detail
        while not _done.is_set():
            elapsed = _time.perf_counter() - _t_start
            try:
                evt = _q.get(timeout=1)
                _cur_step = _STEP_IDX.get(evt[0], _cur_step)
                _cur_detail = _fmt_detail(evt)
            except _queue.Empty:
                pass
            _render_card(_cur_step, _cur_detail, elapsed)

        if _error[0]:
            raise _error[0]

        res = _result[0]
        written = write_schedule_outputs(
            Path("out"), res.schedule, period=_PERIOD, include_period=False
        )
        try:
            upload_outputs_if_configured(written)
        except Exception as exc:
            st.warning(f"Cloud Storage upload failed: {exc}")
        st.session_state["result"] = res
        st.success(t("solve_done", lang, a=len(res.assignments),
                     v=len(res.violations), u=len(res.unschedulable)))
        st.rerun()
