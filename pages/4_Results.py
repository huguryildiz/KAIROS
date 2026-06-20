import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st
from timetabling.ui_grid import filter_assignments, distinct_values
from timetabling.ui_style import BRAND_CSS, metric_cards_html, week_grid_html, logo_img_html

st.set_page_config(page_title="Results · Course Timetabling", page_icon="📊", layout="wide")
st.markdown(BRAND_CSS, unsafe_allow_html=True)
st.sidebar.markdown(logo_img_html(), unsafe_allow_html=True)

st.header("Results")
res = st.session_state.get("result")
if res is None:
    st.warning("No solution yet — run a solve first (Solve page).")
    st.stop()

sched = res.schedule
total_blocks = len(res.assignments) + sum(len(s.blocks) for s in res.unschedulable)
placed_pct = (len(res.assignments) / total_blocks * 100) if total_blocks else 0
conflicts = len(res.violations)
st.markdown(metric_cards_html([
    ("Placed", f"{placed_pct:.0f}%", "good" if placed_pct >= 99 else "brand"),
    ("Hard conflicts", str(conflicts), "good" if conflicts == 0 else "bad"),
    ("Rooms used", str(len({a['room'] for a in sched['assignments']})), ""),
    ("Unschedulable", str(len(res.unschedulable)), "" if not res.unschedulable else "bad"),
]), unsafe_allow_html=True)

# Two-level "view + selection" filter (ported from out/timetable_001.html):
# pick a dimension to view by, then one entity within it; the grid shows just
# that entity's week so cells stay readable.
VIEWS = {"Cohort": "cohort", "Room": "room", "Instructor": "instructor_name",
         "Department": "dept"}
META_FOR = {"cohort": "room", "room": "cohort", "instructor_name": "room", "dept": "room"}

c1, c2 = st.columns([1, 2])
view_label = c1.selectbox("View by", list(VIEWS))
view_field = VIEWS[view_label]
entities = distinct_values(sched, view_field)
if not entities:
    st.info("No assignments to display.")
    st.stop()
entity = c2.selectbox(view_label, entities)
view = filter_assignments(sched, view_field, entity)
st.markdown(week_grid_html(view, meta_field=META_FOR[view_field]), unsafe_allow_html=True)
st.caption(f"{len(view['assignments'])} blocks · solid bar = theory · dashed bar = lab · "
           f"color = department · hover a block for details.")

st.write("")
c3, c4 = st.columns(2)
c3.download_button("Download schedule.json",
                   json.dumps(sched, ensure_ascii=False, indent=2),
                   file_name=f"schedule_{st.session_state.get('period','')}.json",
                   use_container_width=True)
c4.download_button("Download assignments.csv",
                   pd.DataFrame(sched["assignments"]).to_csv(index=False),
                   file_name=f"schedule_{st.session_state.get('period','')}.csv",
                   use_container_width=True)

if res.unschedulable:
    with st.expander(f"Unschedulable sections ({len(res.unschedulable)})"):
        st.write([s.section_id for s in res.unschedulable])
