import sys
from timetabling import __main__ as m


def test_mrpb_flag_parses(monkeypatch):
    # Build the parser the same way main() does is internal; instead test the Config override logic.
    from timetabling.config import Config
    # default path
    assert Config(solve_time_limit_s=60).max_rooms_per_block == 12
    # override path
    assert Config(solve_time_limit_s=60, max_rooms_per_block=6).max_rooms_per_block == 6


def test_soft_shaping_config_default_and_override():
    from timetabling.config import Config
    assert Config().soft_shaping_in_repair is True
    assert Config(soft_shaping_in_repair=False).soft_shaping_in_repair is False


def test_cli_solves_uploaded_csvs_without_period(tmp_path, monkeypatch):
    courses = tmp_path / "courses.csv"
    courses.write_text(
        "Course Code,Course Name,Dept,Section No,Instructor Name,Instructor Email,T,P,L,Section Capacity\n"
        "CMPE 101,Intro,Engineering,01,Dr A,a@x.edu,2,0,0,20\n",
        encoding="utf-8",
    )
    rooms = tmp_path / "rooms.csv"
    rooms.write_text("Room,Capacity,Type\nA101,40,normal\n", encoding="utf-8")

    monkeypatch.setattr(sys, "argv", [
        "timetabling",
        "--courses", str(courses),
        "--rooms", str(rooms),
        "--mode", "A",
        "--out", str(tmp_path),
        "--time-limit", "5",
    ])

    m.main()

    assert (tmp_path / "schedule.json").exists()
    assert (tmp_path / "schedule.csv").exists()
