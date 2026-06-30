"""Tests for the pure PDF export helpers (Streamlit-free)."""
from pathlib import Path
import re
import subprocess

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


def test_build_grid_pdf_includes_room_label(tmp_path):
    from timetabling.pdf_export import build_grid_pdf
    if subprocess.run(["which", "pdftotext"], capture_output=True).returncode != 0:
        pytest.skip("pdftotext is not installed")
    pdf_path = tmp_path / "schedule.pdf"
    pdf_path.write_bytes(build_grid_pdf(_sample_schedule(), "Öğretim elemanı: Şükrü Çağ", "tr"))
    text = subprocess.check_output(["pdftotext", str(pdf_path), "-"], text=True)
    assert "A101" in text


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


def test_build_pdf_bundle_multi_entity_returns_single_merged_pdf():
    from timetabling.pdf_export import build_pdf_bundle
    data, fname, mime = build_pdf_bundle(
        _sample_schedule(), "instructor_name",
        ["Şükrü Çağ", "Ayşe Yılmaz"], "Öğretim elemanı", "tr")
    assert mime == "application/pdf"
    assert re.fullmatch(r"schedule_instructor_name_\d{8}_\d{6}\.pdf", fname)
    assert bytes(data[:4]) == b"%PDF"
    # Two entities → two pages in the merged PDF.
    assert data.count(b"/Type /Page\n") + data.count(b"/Type/Page\n") + \
           data.count(b"/Type /Page<") >= 2 or data.count(b"/Type /Page") >= 2


def test_build_pdf_bundle_sorts_entities_naturally():
    """EE-2 must come before EE-10 — alphabetic sort puts '10' before '2'."""
    from timetabling.pdf_export import _natsort_key
    ents = ["EE-10", "EE-2", "EE-1", "EE-11"]
    assert sorted(ents, key=_natsort_key) == ["EE-1", "EE-2", "EE-10", "EE-11"]


def test_build_pdf_bundle_sanitizes_filename():
    from timetabling.pdf_export import _sanitize_filename
    assert _sanitize_filename("Ahmet Acar") == "Ahmet_Acar"
    assert _sanitize_filename("A/B:C*?") == "A_B_C"
    assert _sanitize_filename("Şükrü Çağ") == "Şükrü_Çağ"


def test_dense_pdf_views_are_paginated_for_readability():
    from timetabling.pdf_export import _assignment_hours, _paginate_for_readability

    sched = {"assignments": [
        {"section_id": f"ELT 40{i}_01", "day": "Mo", "start": 9, "end": 11,
         "room": f"A10{i}", "instructor_name": f"Instructor {i}",
         "department": "English Language Education"}
        for i in range(3)
    ]}
    pages = _paginate_for_readability(sched)

    assert len(pages) == 2
    assert sum(len(p["assignments"]) for p in pages) == 3
    for page in pages:
        slot_counts = {}
        for assignment in page["assignments"]:
            for slot in _assignment_hours(assignment):
                slot_counts[slot] = slot_counts.get(slot, 0) + 1
        assert max(slot_counts.values()) <= 2


def test_pdf_i18n_keys_exist():
    from timetabling.i18n import t
    assert t("res_dl_pdf", "tr") == "PDF indir"
    assert t("res_dl_pdf", "en") == "Download PDF"
