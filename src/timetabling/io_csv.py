from __future__ import annotations
from pathlib import Path
import pandas as pd

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

_PERIOD_FILE = {"001": "2025-01", "002": "2025-02"}


def _read(name: str) -> pd.DataFrame:
    return pd.read_csv(DATA_DIR / name, dtype=str).fillna("")


def load_grades(period: str) -> pd.DataFrame:
    return _read(f"{_PERIOD_FILE[period]}-Grades.csv")


def load_plan(period: str) -> pd.DataFrame:
    df = _read(f"{_PERIOD_FILE[period]}-Plan.csv").copy()
    df["period"] = period
    return df


def load_enrollment() -> pd.DataFrame:
    return _read("enrollment_by_section.csv")


def load_classrooms() -> pd.DataFrame:
    return _read("classrooms.csv")


def load_lecturers() -> pd.DataFrame:
    return _read("lecturers.csv")
