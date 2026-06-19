from timetabling import join


def test_build_section_frame_001():
    df = join.build_section_frame("001")
    assert len(df) == 841                       # one row per Grades section
    row = df[df["section_id"] == "ADA 403_01"].iloc[0]
    assert row["staff_id"] == "00005657"        # (S) stripped
    assert row["dept_code"] == "ADA" and row["year_level"] == "4"
    assert row["plan_schedule"] == "Fr 13 - 16"  # LEFT join into Plan
    assert int(row["T"]) == 3


def test_enrollment_join_coverage():
    df = join.build_section_frame("001")
    matched = (df["dept_code"] != "").sum()
    assert matched / len(df) > 0.85             # most sections find a cohort
