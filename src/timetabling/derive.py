from __future__ import annotations
import re
from typing import List, Tuple, Dict

from .config import Config
from .model import Section, Block
from .textnorm import parse_int, normalize_staff_ids

_NUM = re.compile(r"(\d{3})")


def course_level(code: str) -> int:
    m = _NUM.search(str(code))
    if not m:
        return 0
    return int(m.group(1)[0])


def _split_lengths(total: int, max_len: int) -> List[int]:
    if total <= max_len:
        return [total]
    n = (total + max_len - 1) // max_len          # ceil
    base, extra = divmod(total, n)
    return [base + 1] * extra + [base] * (n - extra)


def _make_blocks(section_id, kind, tag, total, max_len, needs_lab) -> List[Block]:
    lens = _split_lengths(total, max_len)
    if len(lens) == 1:
        return [Block(f"{section_id}#{tag}", section_id, kind, lens[0], needs_lab)]
    return [Block(f"{section_id}#{tag}{i+1}", section_id, kind, ln, needs_lab)
            for i, ln in enumerate(lens)]


def blocks_from_tpl(section_id: str, T: int, P: int, L: int, Cr: int,
                    max_block_len: int = 4, max_theory_session: int = 2) -> List[Block]:
    blocks: List[Block] = []
    theory_len = (T or 0) + (P or 0)
    lab_len = L or 0
    if theory_len > 0:
        blocks += _make_blocks(section_id, "theory", "T", theory_len, max_theory_session, False)
    if lab_len > 0:
        blocks += _make_blocks(section_id, "lab", "L", lab_len, max_block_len, True)
    if not blocks:
        default_len = Cr if (Cr and Cr > 0) else 3
        blocks += _make_blocks(section_id, "theory", "T", default_len, max_theory_session, False)
    return blocks


def _students(row) -> int:
    for key in ("enroll_students", "plan_sect_cap", "grades_students"):
        v = parse_int(row.get(key, ""), default=None)
        if v is not None and v > 0:
            return v
    return 1


def build_sections(frame, cfg: Config) -> Tuple[List[Section], Dict]:
    sections: List[Section] = []
    report = {"excluded": 0, "missing_cohort": 0, "missing_hours": 0,
              "hours_rule": "theory = T+P, lab = L (default 3h if all zero)"}
    for _, row in frame.iterrows():
        r = row.to_dict()
        sid = r.get("section_id", "").strip()
        if not sid:
            continue
        category = r.get("category", "").strip()
        if category in cfg.excluded_categories:
            report["excluded"] += 1
            continue
        code = r.get("code", "").strip()
        level = course_level(code)
        if not cfg.include_grad and level > 4:
            report["excluded"] += 1
            continue
        T = parse_int(r.get("T"), 0); P = parse_int(r.get("P"), 0)
        L = parse_int(r.get("L"), 0); Cr = parse_int(r.get("Cr"), 0)
        if (T + P + L) == 0:
            report["missing_hours"] += 1
        dept_code = r.get("dept_code", "").strip()
        year = r.get("year_level", "").strip()
        if dept_code and year:
            cohort = f"{dept_code}-{year}"
        else:
            report["missing_cohort"] += 1
            dept_code = dept_code or (code.split()[0] if code else "UNK")
            cohort = f"{dept_code}-{level}"
        s = Section(
            section_id=sid, period=r.get("period", "").strip(), code=code,
            name=r.get("name", "").strip(), level=level, dept_code=dept_code,
            faculty=r.get("faculty", "").strip(), cohort_key=cohort,
            instructor_ids=normalize_staff_ids(r.get("staff_id", "")), students=_students(r),
            T=T, P=P, L=L, Cr=Cr, category=category,
            blocks=blocks_from_tpl(sid, T, P, L, Cr, cfg.max_block_len, cfg.max_theory_session),
            plan_room=r.get("plan_room", "").strip(),
        )
        sections.append(s)
    return sections, report
