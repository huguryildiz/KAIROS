from timetabling.textnorm import normalize_staff_id, normalize_name, parse_int, normalize_staff_ids


def test_normalize_staff_id_strips_s_suffix():
    assert normalize_staff_id("00005657 (S)") == "00005657"
    assert normalize_staff_id(" 00006729 ") == "00006729"
    assert normalize_staff_id("") == ""


def test_normalize_name():
    assert normalize_name("Mustafa Kerem Yüksel (S)") == "Mustafa Kerem Yüksel"
    assert normalize_name("  Orhan   Gencel ") == "Orhan Gencel"


def test_parse_int():
    assert parse_int("24") == 24
    assert parse_int("", default=0) == 0
    assert parse_int("3,70", default=-1) == -1   # comma-decimal is not an int


def test_normalize_staff_ids_splits_and_cleans():
    assert normalize_staff_ids("00003893,00002022") == ["00003893", "00002022"]
    assert normalize_staff_ids("00005657 (S)") == ["00005657"]
    assert normalize_staff_ids(" 00006729 , 00007000 (S) ") == ["00006729", "00007000"]
    assert normalize_staff_ids("") == []
    assert normalize_staff_ids(None) == []
