"""Pure-logic tests for the classrooms add/edit/remove upsert (the form glue in
views/classrooms.py is Streamlit-coupled; the room-list mutation isn't)."""
from views.classrooms import _upsert_room


def _rooms():
    return [{"Room": "A216", "Cap": "25", "Lab": ""},
            {"Room": "A211-PC-L", "Cap": "99", "Lab": "x"}]


def test_upsert_edits_picked_room_in_place():
    rooms = _rooms()
    out = _upsert_room(rooms, "A216", {"Room": "A216", "Cap": "30", "Lab": ""})
    assert out is rooms                              # mutates in place
    assert out[0] == {"Room": "A216", "Cap": "30", "Lab": ""}
    assert len(out) == 2                             # no new row


def test_upsert_rename_keeps_position_no_duplicate():
    rooms = _rooms()
    _upsert_room(rooms, "A216", {"Room": "A220", "Cap": "25", "Lab": ""})
    assert [r["Room"] for r in rooms] == ["A220", "A211-PC-L"]


def test_upsert_new_room_appends():
    rooms = _rooms()
    _upsert_room(rooms, "+ New room", {"Room": "B101", "Cap": "40", "Lab": "x"})
    assert len(rooms) == 3 and rooms[-1]["Room"] == "B101"


def test_upsert_new_name_collision_updates_existing():
    # Adding a "new" room whose name already exists updates that row, never dups.
    rooms = _rooms()
    _upsert_room(rooms, "+ New room", {"Room": "A216", "Cap": "12", "Lab": "x"})
    assert len(rooms) == 2
    assert rooms[0] == {"Room": "A216", "Cap": "12", "Lab": "x"}
