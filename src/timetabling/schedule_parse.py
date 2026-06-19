from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple

VALID_DAYS = frozenset({"Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"})


@dataclass(frozen=True)
class ParsedSession:
    day: str
    start: int
    end: int


def _expand_days(token: str) -> List[str]:
    # "Tu/Fr" -> ["Tu", "Fr"]; "Fr" -> ["Fr"]
    return [d for d in token.split("/") if d]


def parse_schedule(raw: str, valid_days=VALID_DAYS) -> Tuple[List[ParsedSession], List[str]]:
    """Parse a SCHEDULE cell into sessions. Returns (sessions, errors).
    Grammar (repeated): <day[/day...]> <start:int> '-' <end:int>.
    A value whose first token is not a valid day is reported as an error and
    NOT auto-repaired (handles ~11 column-shift rows)."""
    if raw is None:
        return [], []
    text = str(raw).strip()
    if text == "":
        return [], []

    tokens = text.split()
    first_day_token = tokens[0].split("/")[0]
    if first_day_token not in valid_days:
        return [], [f"SCHEDULE value does not start with a valid day token: {text!r}"]

    sessions: List[ParsedSession] = []
    errors: List[str] = []
    i = 0
    n = len(tokens)
    while i < n:
        day_token = tokens[i]
        days = _expand_days(day_token)
        if not days or any(d not in valid_days for d in days):
            errors.append(f"Unexpected token where a day was expected: {day_token!r} in {text!r}")
            break
        # need three more tokens: start, '-', end
        if i + 3 >= n:
            errors.append(f"Incomplete session after {day_token!r} in {text!r}")
            break
        start_tok, dash_tok, end_tok = tokens[i + 1], tokens[i + 2], tokens[i + 3]
        if dash_tok != "-" or not start_tok.isdigit() or not end_tok.isdigit():
            errors.append(f"Malformed session near {day_token!r} in {text!r}")
            break
        start, end = int(start_tok), int(end_tok)
        if not (0 <= start < end <= 24):
            errors.append(f"Bad hour range {start}-{end} in {text!r}")
            break
        for d in days:
            sessions.append(ParsedSession(d, start, end))
        i += 4
    return sessions, errors
