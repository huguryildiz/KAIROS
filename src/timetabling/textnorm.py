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
