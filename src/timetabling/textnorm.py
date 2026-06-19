from __future__ import annotations
import re

_S_SUFFIX = re.compile(r"\(S\)")
_WS = re.compile(r"\s+")


def normalize_staff_id(s: str) -> str:
    if s is None:
        return ""
    s = _S_SUFFIX.sub("", str(s))
    return _WS.sub("", s).strip()


def normalize_name(s: str) -> str:
    if s is None:
        return ""
    s = _S_SUFFIX.sub("", str(s))
    return _WS.sub(" ", s).strip()


def parse_int(s, default=None):
    try:
        return int(str(s).strip())
    except (ValueError, TypeError):
        return default


def normalize_staff_ids(s) -> list:
    """Split a comma-joined Staff ID cell into a list of normalized ids.
    Drops blanks; reuses normalize_staff_id for (S)/whitespace handling."""
    if s is None:
        return []
    out = []
    for part in str(s).split(","):
        sid = normalize_staff_id(part)
        if sid:
            out.append(sid)
    return out
