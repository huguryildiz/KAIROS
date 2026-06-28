# app.py (repo root) — run with: PYTHONPATH=src streamlit run app.py
# Single-page premium flow: app bar + step indicator + hero, then the five
# section renderers shown progressively (Solve/Results gated on prerequisites).
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import streamlit as st
from timetabling.settings import default_settings
from timetabling.ui_style import (brand_css, appbar_html, stepper_html,
                                  hero_html, footer_html, dropzone_drag_js,
                                  eyebrow_html)
from timetabling.ui_app import (get_lang, get_theme, theme_toggle,
                                lang_selector_bar, hero_chips)
from timetabling.i18n import t
from views import upload, review, classrooms, settings, solve, results

_ICON = os.path.join(os.path.dirname(__file__), "assets", "icon.svg")
st.set_page_config(
    page_title="KAIROS | Ders Programı Optimizasyonu / Timetable Optimization",
    page_icon=_ICON,
    layout="wide",
)

# Session defaults
st.session_state.setdefault("courses", [])
st.session_state.setdefault("classrooms", [])
st.session_state.setdefault("result", None)
st.session_state.setdefault("lang", "en")
st.session_state.setdefault("theme", "light")
st.session_state.setdefault("settings", default_settings())
st.session_state.setdefault("availability", {})

st.markdown(brand_css(get_theme()), unsafe_allow_html=True)

has_courses = bool(st.session_state["courses"])
has_result = st.session_state["result"] is not None

# --- Sticky glass header: brand + controls + step indicator in one frosted bar
#     (the .st-key-topbar wrapper is made sticky + backdrop-blurred in ui_style).
def _solve_status() -> str:
    if not has_courses:
        return "locked"
    return "done" if has_result else "active"

lang = get_lang()

# Streamlit's file-uploader widget hardcodes English strings in its React bundle.
# When the UI language is TR, inject a tiny MutationObserver that rewrites those
# strings in the parent DOM as soon as they appear (and whenever Streamlit re-renders).
if lang == "tr":
    import streamlit.components.v1 as _cmp
    _cmp.html(
        """<script>
(function(){
  var TR={
    "Drag and drop file here":"Dosyayı buraya bırakın",
    "Browse files":"Dosya seç"
  };
  var LIM=/^Limit \\d+MB per file/;
  function run(){
    try{
      window.parent.document
        .querySelectorAll('[data-testid="stFileUploaderDropzone"]')
        .forEach(function(dz){
          dz.querySelectorAll('p,span,small,button').forEach(function(el){
            if(el.children.length)return;
            var s=el.innerText.trim();
            if(TR[s]){el.innerText=TR[s];return;}
            if(LIM.test(s)){el.innerText="Maks. 200 MB · Yalnızca CSV";}
          });
        });
    }catch(e){}
  }
  run();
  new MutationObserver(function(){setTimeout(run,60);})
    .observe(window.parent.document.body,{childList:true,subtree:true});
})();
</script>""",
        height=0,
    )

# Drag-over highlight for the upload cards (Step 1 + Classrooms). Delivered via an
# iframe component so the JS actually runs — inline <script> in st.markdown is
# stripped by Streamlit's sanitizer. See ui_style.dropzone_drag_js for details.
import streamlit.components.v1 as _cmp
_cmp.html(dropzone_drag_js(), height=0)

with st.container(key="topbar"):
    bar = st.columns([7, 2], vertical_alignment="center")
    with bar[0]:
        st.markdown(appbar_html(lang), unsafe_allow_html=True)
    with bar[1]:
        # Theme + language controls on one tight, right-aligned flex row
        # (the container is flipped to flex-direction:row in ui_style).
        with st.container(key="topctrls"):
            theme_toggle()
            lang = lang_selector_bar()

    steps = [
        {"key": "data", "label": t("step_data", lang),
         "status": "done" if has_courses else "active"},
        {"key": "settings", "label": t("step_settings", lang),
         "status": "active" if has_courses else "locked"},
        {"key": "solve", "label": t("step_solve", lang), "status": _solve_status()},
        {"key": "results", "label": t("step_results", lang),
         "status": "active" if has_result else "locked"},
    ]
    st.markdown(stepper_html(steps, lang), unsafe_allow_html=True)

# --- Hero (chips track the workflow state: proof → dataset → real outcome)
st.markdown(hero_html(lang, hero_chips(lang)), unsafe_allow_html=True)


def _anchor(name: str) -> None:
    st.markdown(f'<div id="s-{name}"></div>', unsafe_allow_html=True)


# --- Sections (progressive disclosure)
# Step 1 — Data: one numbered step grouping the course upload, the validation
# review, and the classroom inventory (each rendered as a number-less sub-header).
_anchor("data")
st.markdown(eyebrow_html(1, t("step_data", lang), "data"), unsafe_allow_html=True)
_anchor("upload")
upload.render(lang)

if has_courses:
    _anchor("review")
    review.render(lang)
    _anchor("classrooms")
    classrooms.render(lang)
    st.divider()
    _anchor("settings")
    settings.render(lang)
    st.divider()
    _anchor("solve")
    solve.render(lang)

if has_result:
    st.divider()
    _anchor("results")
    results.render(lang)


# --- Auto-advance: after a fresh upload / sample-load, smooth-scroll the page to
# the Review step so the next action is in view (set by views.upload._set_courses).
# --- Footer (attribution) — always last, after every section.
st.markdown(footer_html(lang), unsafe_allow_html=True)

_scroll_target = st.session_state.pop("scroll_to", None)
if _scroll_target:
    import streamlit.components.v1 as components
    components.html(
        f"""
        <script>
          const doc = window.parent.document;
          const el = doc.getElementById("s-{_scroll_target}");
          if (el) el.scrollIntoView({{behavior: "smooth", block: "start"}});
        </script>
        """,
        height=0,
    )
