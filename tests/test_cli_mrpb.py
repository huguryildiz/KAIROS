import sys
from timetabling import __main__ as m


def test_mrpb_flag_parses(monkeypatch):
    # Build the parser the same way main() does is internal; instead test the Config override logic.
    from timetabling.config import Config
    # default path
    assert Config(solve_time_limit_s=60).max_rooms_per_block == 12
    # override path
    assert Config(solve_time_limit_s=60, max_rooms_per_block=6).max_rooms_per_block == 6
