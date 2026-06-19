from timetabling.schedule_parse import parse_schedule, ParsedSession


def test_single_unit():
    sessions, errors = parse_schedule("Fr 13 - 16")
    assert errors == []
    assert sessions == [ParsedSession("Fr", 13, 16)]


def test_chained_sessions():
    sessions, errors = parse_schedule("Th 09 - 12 Th 13 - 16")
    assert errors == []
    assert sessions == [ParsedSession("Th", 9, 12), ParsedSession("Th", 13, 16)]


def test_multiday_slash():
    sessions, errors = parse_schedule("Tu/Fr 09 - 12")
    assert errors == []
    assert sessions == [ParsedSession("Tu", 9, 12), ParsedSession("Fr", 9, 12)]


def test_empty_is_empty_no_error():
    assert parse_schedule("") == ([], [])
    assert parse_schedule("   ") == ([], [])


def test_dirty_value_flagged_not_repaired():
    sessions, errors = parse_schedule("Işıl Sevilay Yılmaz")
    assert sessions == []
    assert len(errors) == 1 and "does not start with a valid day" in errors[0]


def test_dirty_room_code_flagged():
    sessions, errors = parse_schedule("D232")
    assert sessions == []
    assert len(errors) == 1
