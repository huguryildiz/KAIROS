from timetabling.model import Room, Section


def test_room_has_categorical_type_default_normal():
    r = Room(room="A1", cap=30, is_lab=False, is_physical=True)
    assert r.type == "normal"
    r2 = Room(room="L1", cap=20, is_lab=True, is_physical=True, type="pc")
    assert r2.type == "pc" and r2.is_lab is True


def test_section_has_required_room_type_default_blank():
    s = Section(section_id="X_01", period="001", code="X 101", name="X", level=1,
                dept_code="X", faculty="Fac", cohort_key="X-1", instructor_ids=[],
                students=10, T=2, P=0, L=0, Cr=2, category="")
    assert s.required_room_type == ""
