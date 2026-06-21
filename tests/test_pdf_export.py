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
