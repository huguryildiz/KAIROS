import sys, os, json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import pandas as pd
import streamlit as st
from timetabling.ui_grid import (build_week_grid, filter_assignments,
                                 distinct_values, DAYS_ORDER)

st.header("📊 Results")
res = st.session_state.get("result")
if res is None:
    st.warning("No solution yet — run a solve first (Solve page).")
    st.stop()

sched = res.schedule
m = st.columns(4)
total_blocks = len(res.assignments) + sum(len(s.blocks) for s in res.unschedulable)
placed_pct = (len(res.assignments) / total_blocks * 100) if total_blocks else 0
m[0].metric("Placed", f"{placed_pct:.1f}%")
m[1].metric("Hard conflicts", len(res.violations))
m[2].metric("Rooms used", len({a['room'] for a in sched['assignments']}))
m[3].metric("Unschedulable", len(res.unschedulable))

field = st.selectbox("Filter by", ["(none)", "room", "instructor_name", "cohort", "dept"])
view = sched
if field != "(none)":
    val = st.selectbox(field, [""] + distinct_values(sched, field))
    view = filter_assignments(sched, field, val)

grid = build_week_grid(view)
hours = range(9, 21)
table = {}
for h in hours:
    table[f"{h:02d}:00"] = {
        d: " / ".join(f"{a['course_code']} {a['block_kind'][:1].upper()}"
                      for a in grid.get((d, h), []))
        for d in DAYS_ORDER}
st.dataframe(pd.DataFrame(table).T[DAYS_ORDER], use_container_width=True, height=460)

c1, c2 = st.columns(2)
c1.download_button("⬇ schedule.json",
                   json.dumps(sched, ensure_ascii=False, indent=2),
                   file_name=f"schedule_{st.session_state.get('period','')}.json")
c2.download_button("⬇ assignments.csv",
                   pd.DataFrame(sched["assignments"]).to_csv(index=False),
                   file_name=f"schedule_{st.session_state.get('period','')}.csv")

if res.unschedulable:
    with st.expander(f"Unschedulable sections ({len(res.unschedulable)})"):
        st.write([s.section_id for s in res.unschedulable])
