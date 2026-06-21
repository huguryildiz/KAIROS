from timetabling.config import Config
from timetabling.model import Section, Room, Instructor, Assignment
from timetabling.report import _metrics


def _sec(sid, code, cohort, iid, level=2):
    return Section(sid, "001", code, "x", level, code.split()[0], "F", cohort,
                   [iid], 30, 2, 0, 0, 2, "")


def test_metrics_reports_cohort_gap_and_teaching_days():
    rooms = {"R1": Room("R1", 50, False, True)}
    instr = {"i1": Instructor("i1", "x", True, "D")}
    secs = [_sec("A_01", "ADA 201", "ADA-2", "i1"),
            _sec("B_01", "ADA 202", "ADA-2", "i1")]
    # same cohort, same day Mo: A at 9-11, B at 13-15 -> a 2h idle gap (11,12)
    assigns = [Assignment("A_01#T", "A_01", "theory", "R1", "Mo", 9, 11),
               Assignment("B_01#T", "B_01", "theory", "R1", "Mo", 13, 15)]
    m = _metrics(assigns, secs, rooms, instr, Config(), check_placement=False)
    assert m["cohort_gap"] == 2          # span (15-9=6) - load (4) = 2
    assert m["instr_teaching_days"] == 1  # i1 teaches only Monday
