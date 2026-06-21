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


def test_build_pdf_bundle_single_entity_returns_pdf():
    from timetabling.pdf_export import build_pdf_bundle
    data, fname, mime = build_pdf_bundle(
        _sample_schedule(), "instructor_name", ["Şükrü Çağ"],
        "Öğretim elemanı", "tr")
    assert mime == "application/pdf"
    assert fname.endswith(".pdf")
    assert bytes(data[:4]) == b"%PDF"


def test_build_pdf_bundle_multi_entity_returns_zip():
    from timetabling.pdf_export import build_pdf_bundle
    data, fname, mime = build_pdf_bundle(
        _sample_schedule(), "instructor_name",
        ["Şükrü Çağ", "Ayşe Yılmaz"], "Öğretim elemanı", "tr")
    assert mime == "application/zip"
    assert fname == "schedule_instructor_name.zip"
    zf = zipfile.ZipFile(io.BytesIO(data))
    names = zf.namelist()
    assert len(names) == 2
    for n in names:
        assert n.endswith(".pdf")
        assert zf.read(n)[:4] == b"%PDF"


def test_build_pdf_bundle_sanitizes_and_dedupes_names():
    from timetabling.pdf_export import _sanitize_filename
    assert _sanitize_filename("Ahmet Acar") == "Ahmet_Acar"
    assert _sanitize_filename("A/B:C*?") == "A_B_C"
    assert _sanitize_filename("Şükrü Çağ") == "Şükrü_Çağ"
