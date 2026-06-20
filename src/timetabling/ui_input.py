from __future__ import annotations
import re
from typing import List, Dict, Tuple

from .config import Config
from .model import Section, Room, Instructor
from .derive import course_level, blocks_from_tpl
from .textnorm import parse_int

_CODE = re.compile(r"\s*([A-Za-z]+)\D*(\d)")


def cohort_from_code(code: str) -> Tuple[str, str, str]:
    m = _CODE.match(str(code or ""))
    if not m:
        return ("UNK", "0", "UNK-0")
    dept, year = m.group(1).upper(), m.group(2)
    return (dept, year, f"{dept}-{year}")


def is_part_time(lecturer_name: str) -> bool:
    return "(S)" in (lecturer_name or "")


def parse_emails(s: str) -> List[str]:
    return [e.strip() for e in str(s or "").split(",") if e.strip()]
