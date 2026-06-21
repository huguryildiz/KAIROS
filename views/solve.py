"""Step 5 — Solve: fixed time budget, run the pipeline. Upload-gated."""
from html import escape

import streamlit as st
import streamlit.components.v1 as _cmp

from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                  build_instructors_from_courselist, build_rooms_from_ui,
                                  courselist_is_valid)
from timetabling.route import mark_virtual
from timetabling.pipeline import run_pipeline
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

    # Client-side solve watcher. Delivered via a height:0 iframe component so the JS
    # actually runs — inline <script> in st.markdown stays in the DOM but is never
    # executed (React dangerouslySetInnerHTML), so it is inert (see app.py). The
    # watcher polls the parent doc every second for .solve-running (present while a
    # solve is in progress) and, while it is there, (a) arms window.onbeforeunload on
    # the parent so navigating away prompts the browser's "Leave site?" dialog, and
    # (b) live-updates the .solve-eta span with elapsed + approx remaining time
    # (counted down from _SOLVE_SECONDS); it clears the guard once the page rerenders.
    # The wrapping container is display:none (ui_style .st-key-solve_watch) so the
    # 0-height iframe contributes no vertical gap between the caption and the button.
    _lbl_elapsed = "geçti · kalan ~" if lang == "tr" else "elapsed · ~"
    _lbl_min = "dk" if lang == "tr" else "min"
    _lbl_sec = "sn" if lang == "tr" else "s"
    with st.container(key="solve_watch"):
        _cmp.html(
            f'<script>(function(){{'
            f'var D=window.parent.document,W=window.parent;'
            f'var B={_SOLVE_SECONDS},t0=null;'
            f'function f(s){{return s<60?s+\' {_lbl_sec}\':Math.floor(s/60)+\' {_lbl_min} \'+(s%60)+\' {_lbl_sec}\';}}  '
            f'function tick(){{'
            f'var el=D.querySelector(".solve-running");'
            f'if(el){{'
            f'W.onbeforeunload=function(e){{e.preventDefault();e.returnValue="";}};'
            f'if(!t0)t0=Date.now();'
            f'var es=Math.round((Date.now()-t0)/1000),rm=Math.max(0,B-es);'
            f'var sp=D.querySelector(".solve-eta");'
            f'if(sp)sp.textContent=f(es)+" {_lbl_elapsed} "+f(rm);'
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
        ph.markdown(
            f'<div class="solve-running">'
            f'<span class="solve-gear"></span>'
            f'{escape(t("solve_spinner", lang, n=len(secs)))}'
            f'</div>'
            f'<div class="solve-eta"></div>',
            unsafe_allow_html=True,
        )
        res = run_pipeline(_PERIOD, secs, rooms, instr, cfg, solver="auto")
        st.session_state["result"] = res
        st.success(t("solve_done", lang, a=len(res.assignments),
                     v=len(res.violations), u=len(res.unschedulable)))
        st.rerun()
