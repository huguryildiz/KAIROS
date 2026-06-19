from timetabling.config import Config, DAYS
from timetabling.model import Room, Section, Block


def test_config_defaults():
    cfg = Config()
    assert DAYS == ["Mo", "Tu", "We", "Th", "Fr"]
    assert cfg.undergrad_end == 18
    assert cfg.days() == ["Mo", "Tu", "We", "Th", "Fr"]
    cfg2 = Config(saturday_enabled=True)
    assert "Sa" in cfg2.days()


def test_model_dataclasses():
    r = Room("A216", 25, False, True)
    assert r.cap == 25 and not r.is_lab
    s = Section("X_01", "001", "X 101", "n", 1, "X", "Fac", "X-1", ["id"], 30,
                3, 0, 0, 3, "Course")
    assert s.blocks == []
