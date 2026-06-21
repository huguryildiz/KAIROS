"""Step 5 — Solve: fixed time budget, run the pipeline. Upload-gated."""
from html import escape

import streamlit as st

from timetabling.settings import build_config
from timetabling.ui_input import (build_sections_from_courselist,
                                  build_instructors_from_courselist, build_rooms_from_ui)
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
    st.markdown(eyebrow_html(5, t("step_solve", lang), "solve"),
                unsafe_allow_html=True)

    courses = st.session_state.get("courses", [])
    st.caption(t("solve_ready", lang, c=len(courses),
                 r=len(st.session_state["classrooms"])))

    # JS: on pointerdown → restart wand animation + burst confetti particles.
    # pointerdown fires for both mouse and touch before Streamlit rerenders.
    st.markdown(
        '<script>(function(){'
        'var C=["#FFD700","#FF6B6B","#4ECDC4","#7E90EE","#FFA07A","#C7B8EA","#FF9F43","#54A0FF"];'
        'function burst(btn){'
        'var r=btn.getBoundingClientRect(),cx=r.left+r.width/2,cy=r.top+r.height/2;'
        'for(var i=0;i<38;i++){(function(){'
        'var el=document.createElement("div"),sz=5+Math.random()*8,'
        'col=C[0|Math.random()*C.length],circ=Math.random()>.4;'
        'el.style.position="fixed";el.style.left=cx+"px";el.style.top=cy+"px";'
        'el.style.width=sz+"px";el.style.height=sz+"px";el.style.background=col;'
        'el.style.borderRadius=circ?"50%":"3px";el.style.pointerEvents="none";el.style.zIndex="9999";'
        'document.body.appendChild(el);'
        'var a=Math.random()*Math.PI*2,sp=4+Math.random()*11,'
        'vx=Math.cos(a)*sp,vy=Math.sin(a)*sp-7,g=.38,x=0,y=0,f=0,mf=62;'
        'function step(){'
        'f++;vy+=g;x+=vx;y+=vy;'
        'el.style.transform="translate("+x+"px,"+y+"px) rotate("+(f*9)+"deg)";'
        'el.style.opacity=1-f/mf;'
        'if(f<mf)requestAnimationFrame(step);else el.remove();}'
        'setTimeout(function(){requestAnimationFrame(step);},Math.random()*110);'
        '})();}'
        '}'
        'function attach(){'
        'var b=document.querySelector(".st-key-solve_btn button");'
        'if(!b){setTimeout(attach,150);return;}'
        'b.addEventListener("pointerdown",function(){'
        'b.classList.remove("wand-casting");void b.offsetWidth;b.classList.add("wand-casting");'
        'burst(b);});}'
        'attach();'
        '})();</script>',
        unsafe_allow_html=True,
    )
    # JS: beforeunload guard + elapsed/remaining timer.
    # Polls for .solve-running every second; sets window.onbeforeunload while it
    # is present (solve in progress) and clears it once the page rerenders.
    # A window.__kw flag prevents duplicate loops when Streamlit reruns the script.
    _lbl_elapsed = "geçti · kalan ~" if lang == "tr" else "elapsed · ~"
    _lbl_min = "dk" if lang == "tr" else "min"
    _lbl_sec = "sn" if lang == "tr" else "s"
    st.markdown(
        f'<script>(function(){{'
        f'if(window.__kw)return;window.__kw=true;'
        f'var B={_SOLVE_SECONDS},t0=null;'
        f'function f(s){{return s<60?s+\' {_lbl_sec}\':Math.floor(s/60)+\' {_lbl_min} \'+(s%60)+\' {_lbl_sec}\';}}  '
        f'function tick(){{'
        f'var el=document.querySelector(".solve-running");'
        f'if(el){{'
        f'window.onbeforeunload=function(e){{e.preventDefault();e.returnValue="";}};'
        f'if(!t0)t0=Date.now();'
        f'var es=Math.round((Date.now()-t0)/1000),rm=Math.max(0,B-es);'
        f'var sp=el.querySelector(".solve-eta");'
        f'if(sp)sp.textContent="· "+f(es)+" {_lbl_elapsed} "+f(rm);'
        f'}}else{{window.onbeforeunload=null;t0=null;}}'
        f'setTimeout(tick,1000);}}'
        f'tick();'
        f'}})();</script>',
        unsafe_allow_html=True,
    )
    _, _col, _ = st.columns([1.5, 3, 1.5])
    ph = _col.empty()
    if ph.button(t("solve_button", lang), type="primary", key="solve_btn"):
        cfg = build_config(st.session_state["settings"],
                           st.session_state["availability"], _SOLVE_SECONDS)
        secs, _ = build_sections_from_courselist(courses, _PERIOD, cfg)
        instr = build_instructors_from_courselist(courses)
        rooms = build_rooms_from_ui(st.session_state["classrooms"], cfg)
        mark_virtual(secs, rooms, cfg)
        ph.markdown(
            f'<div class="solve-running">'
            f'<span class="solve-spin"></span>'
            f'{escape(t("solve_spinner", lang, n=len(secs)))}'
            f'<span class="solve-eta"></span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        res = run_pipeline(_PERIOD, secs, rooms, instr, cfg, solver="auto")
        st.session_state["result"] = res
        st.success(t("solve_done", lang, a=len(res.assignments),
                     v=len(res.violations), u=len(res.unschedulable)))
        st.rerun()
