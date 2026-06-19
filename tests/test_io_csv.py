from timetabling import io_csv


def test_load_grades_counts_and_columns():
    g = io_csv.load_grades("001")
    assert len(g) == 841
    for col in ["Period", "Code", "Section", "T", "P", "L", "Cr",
                "Category", "Lecturer", "Room", "Schedule", "# of Students", "Staff ID", "Dept."]:
        assert col in g.columns
    assert set(g["Period"].unique()) == {"001"}


def test_load_grades_002():
    assert len(io_csv.load_grades("002")) == 826


def test_load_plan_attaches_period_and_has_no_native_period():
    p = io_csv.load_plan("001")
    assert "period" in p.columns and set(p["period"].unique()) == {"001"}
    assert "SECTION" in p.columns and "SCHEDULE" in p.columns


def test_load_masters():
    assert len(io_csv.load_classrooms()) == 104   # 101 + 3 real lab rooms (A317/A326/DB102-MF-L)
    assert len(io_csv.load_lecturers()) == 340
    assert len(io_csv.load_enrollment()) == 1667
    assert "ROOM_CAP" in io_csv.load_classrooms().columns
