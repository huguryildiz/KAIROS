from timetabling.ui_input import cohort_from_code, is_part_time, parse_emails


def test_cohort_from_code():
    assert cohort_from_code("CMPE 113") == ("CMPE", "1", "CMPE-1")
    assert cohort_from_code("ADA403") == ("ADA", "4", "ADA-4")
    assert cohort_from_code("???") == ("UNK", "0", "UNK-0")


def test_is_part_time():
    assert is_part_time("B. Demir (S)") is True
    assert is_part_time("A. Yilmaz") is False


def test_parse_emails():
    assert parse_emails("a@x.edu, b@x.edu") == ["a@x.edu", "b@x.edu"]
    assert parse_emails("  ") == []
