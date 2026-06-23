"""Step 5 — Solve: fixed time budget, run the pipeline. Upload-gated."""
from html import escape

import streamlit as st
import streamlit.components.v1 as _cmp

from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                  build_instructors_from_courselist, build_rooms_from_ui,
                                  courselist_is_valid)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline, AUTO_REPAIR_THRESHOLD
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

    # Display countdown scaled to expected solve time.
    # Mirrors the runtime cap: 0.5s/section proxy (course rows ≈ 0.6× block count),
    # floor 60s, brackets at 150/400 to match the runtime cap thresholds.
    _n = len(courses)
    if _n <= 150:
        _display_seconds = max(60, int(_n * 0.8))   # e.g. 100 courses → 80s display
    elif _n <= 400:
        _display_seconds = 600
    else:
        _display_seconds = _SOLVE_SECONDS

    # Client-side solve watcher. Delivered via a height:0 iframe component so the JS
    # actually runs — inline <script> in st.markdown stays in the DOM but is never
    # executed (React dangerouslySetInnerHTML), so it is inert (see app.py). The
    # watcher polls the parent doc every second for .solve-running (present while a
    # solve is in progress) and, while it is there, (a) arms window.onbeforeunload on
    # the parent so navigating away prompts the browser's "Leave site?" dialog, and
    # (b) live-updates the .solve-eta span with elapsed + approx remaining time
    # (counted down from _display_seconds); it clears the guard once the page rerenders.
    # The wrapping container is display:none (ui_style .st-key-solve_watch) so the
    # 0-height iframe contributes no vertical gap between the caption and the button.
    with st.container(key="solve_watch"):
        _cmp.html(
            f'<script>(function(){{'
            f'var D=window.parent.document,W=window.parent;'
            f'var B={_display_seconds},t0=null;'
            f'function tick(){{'
            f'var el=D.querySelector(".solve-running");'
            f'if(el){{'
            f'W.onbeforeunload=function(e){{e.preventDefault();e.returnValue="";}};'
            f'if(!t0)t0=Date.now();'
            f'var es=Math.round((Date.now()-t0)/1000);'
            f'var pf=D.querySelector(".solve-progress-fill");'
            f'if(pf)pf.style.width=Math.min(100,Math.round(es/B*100))+"%";'
            f'}}else{{W.onbeforeunload=null;t0=null;}}'
            f'setTimeout(tick,1000);}}'
            f'tick();'
            f'}})();</script>',
            height=0,
        )
    # Gate solving on a validated courselist: disable the button while the upload
    # has blocking validation errors (missing required columns / no rows).
    valid = courselist_is_valid(courses)
    ph = st.empty()
    if not valid:
        st.caption(t("solve_blocked", lang))
    if ph.button(t("solve_button", lang), type="primary", key="solve_btn",
                 disabled=not valid):
        cfg = build_config(st.session_state["settings"],
                           st.session_state["availability"], _SOLVE_SECONDS)
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
        _days = ["Pzt","Sal","Çar","Per","Cum"] if lang == "tr" else ["Mon","Tue","Wed","Thu","Fri"]
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
        ph.markdown(
            f'<div class="solve-running">'
            f'<div class="solve-mini-grid" aria-hidden="true">'
            f'<div class="smg-days">{_days_html}</div>'
            f'<div class="smg-board">'
            f'<div class="smg-cells">{_cells_html}</div>'
            f'<div class="smg-blocks">{_blks_html}</div>'
            f'<div class="smg-sweep"></div>'
            f'</div>'
            f'</div>'
            f'<div class="solve-label">'
            f'<span class="solve-gear"></span>'
            f'{escape(t("solve_spinner", lang, n=len(secs)))}'
            f'</div>'
            f'<div class="solve-progress-track">'
            f'<div class="solve-progress-fill"></div>'
            f'</div>'
            f'</div>',
            unsafe_allow_html=True,
        )
        res = run_pipeline(_PERIOD, secs, rooms, instr, cfg, solver="auto")
        st.session_state["result"] = res
        st.success(t("solve_done", lang, a=len(res.assignments),
                     v=len(res.violations), u=len(res.unschedulable)))
        st.rerun()
