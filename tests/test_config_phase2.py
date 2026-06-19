from timetabling.config import Config

def test_phase2_defaults():
    c = Config()
    assert c.max_block_len == 4
    assert c.max_theory_session == 2
    assert c.extra_rooms == ()
    assert c.compact_cohort_years == (2, 3, 4)
    assert c.w_cohort_gap == 3
    assert c.w_order == 1
    assert c.w_englab == 1
    assert c.eng_lab_days == ("Th", "Fr")
    assert c.eng_faculty_match == "Engineering"
    assert c.w_nonadjacent == 0

def test_phase2_overridable():
    c = Config(max_block_len=3, w_cohort_gap=0)
    assert c.max_block_len == 3 and c.w_cohort_gap == 0
