"""Tests for the pure PDF export helpers (Streamlit-free)."""
import io
import zipfile
from pathlib import Path

import pytest


def test_fpdf2_importable_and_fonts_present():
    import fpdf  # noqa: F401  -- fpdf2 imports as `fpdf`
    fonts = Path("src/timetabling/assets/fonts")
    assert (fonts / "DejaVuSans.ttf").stat().st_size > 100_000
    assert (fonts / "DejaVuSans-Bold.ttf").stat().st_size > 100_000


def _sample_schedule():
    return {
        "assignments": [
            {"section_id": "CMPE201_01", "course_code": "CMPE201",
             "day": "Mo", "start": 9, "end": 11, "room": "A101",
             "instructor_name": "Şükrü Çağ", "instructor_id": "scag@uni.edu",
             "cohort": "CMPE-2", "dept": "CMPE"},
            {"section_id": "CMPE305_01", "course_code": "CMPE305",
             "day": "We", "start": 13, "end": 15, "room": "A203",
             "instructor_name": "Ayşe Yılmaz", "instructor_id": "ayilmaz@uni.edu",
             "cohort": "CMPE-3", "dept": "CMPE"},
        ]
    }


def test_build_grid_pdf_returns_pdf_bytes():
    from timetabling.pdf_export import build_grid_pdf
    data = build_grid_pdf(_sample_schedule(), "Öğretim elemanı: Şükrü Çağ", "tr")
    assert isinstance(data, (bytes, bytearray))
    assert bytes(data[:4]) == b"%PDF"
    assert len(data) > 500


def test_build_grid_pdf_handles_turkish_and_empty():
    from timetabling.pdf_export import build_grid_pdf
    # Turkish glyphs in title + empty assignment list must not raise.
    data = build_grid_pdf({"assignments": []}, "Boş çizelge — İçğöşü", "tr")
    assert bytes(data[:4]) == b"%PDF"
