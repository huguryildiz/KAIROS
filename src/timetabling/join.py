from __future__ import annotations
import pandas as pd

from . import io_csv
from .textnorm import normalize_staff_id, normalize_name


def build_section_frame(period: str, include_plan_only: bool = False) -> pd.DataFrame:
    grades = io_csv.load_grades(period).copy()
    enroll = io_csv.load_enrollment().copy()
    plan = io_csv.load_plan(period).copy()

    g = pd.DataFrame({
        "section_id": grades["Section"].str.strip(),
        "period": grades["Period"].str.strip(),
        "code": grades["Code"].str.strip(),
        "name": grades["Name"].str.strip(),
        "department": grades["Dept."].str.strip(),
        "T": grades["T"], "P": grades["P"], "L": grades["L"], "Cr": grades["Cr"],
        "category": grades["Category"].str.strip(),
        "staff_id": grades["Staff ID"].map(normalize_staff_id),
        "grades_students": grades["# of Students"],
        "lecturer_name": grades["Lecturer"].map(normalize_name),
    })

    e = enroll[enroll["Period"].str.strip() == period][
        ["Section", "Dept_Code", "Year_Level", "Students"]
    ].rename(columns={"Section": "section_id", "Dept_Code": "dept_code",
                      "Year_Level": "year_level", "Students": "enroll_students"})
    e["section_id"] = e["section_id"].str.strip()
    e = e.drop_duplicates("section_id")

    p = plan[["SECTION", "SECT_CAP", "ROOM", "SCHEDULE"]].rename(columns={
        "SECTION": "section_id", "SECT_CAP": "plan_sect_cap",
        "ROOM": "plan_room", "SCHEDULE": "plan_schedule"})
    p["section_id"] = p["section_id"].str.strip()
    p = p.drop_duplicates("section_id")

    df = g.merge(e, on="section_id", how="left").merge(p, on="section_id", how="left")
    df = df.fillna("")

    if include_plan_only:
        extra = p[~p["section_id"].isin(df["section_id"])].copy()
        extra["period"] = period
        df = pd.concat([df, extra], ignore_index=True).fillna("")
    return df
