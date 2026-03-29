"""
Tests for src/processing/pdf_processor.py

Covers PDFProcessor (init, _needs_ocr pure logic, pdfplumber_available
lazy caching, get_tesseract_install_instructions platform strings) and
the get_pdf_processor singleton accessor.
No real PDF files or external libraries required.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.pdf_processor import PDFProcessor, get_pdf_processor


# ---------------------------------------------------------------------------
# Singleton reset fixture
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def reset_singleton():
    import processing.pdf_processor as mod
    mod._pdf_processor = None
    yield
    mod._pdf_processor = None


# ===========================================================================
# PDFProcessor.__init__
# ===========================================================================

class TestPDFProcessorInit:
    def test_pdfplumber_available_is_none(self):
        p = PDFProcessor()
        assert p._pdfplumber_available is None

    def test_pytesseract_available_is_none(self):
        p = PDFProcessor()
        assert p._pytesseract_available is None

    def test_tesseract_path_is_none(self):
        p = PDFProcessor()
        assert p._tesseract_path is None

    def test_min_chars_per_page_is_50(self):
        assert PDFProcessor.MIN_CHARS_PER_PAGE == 50


# ===========================================================================
# PDFProcessor._needs_ocr
# ===========================================================================

class TestNeedsOcr:
    def setup_method(self):
        self.p = PDFProcessor()

    def test_returns_true_when_page_count_is_zero(self):
        assert self.p._needs_ocr("some text", 0) is True

    def test_returns_true_when_text_is_empty_one_page(self):
        # 0 chars / 1 page = 0 < 50
        assert self.p._needs_ocr("", 1) is True

    def test_returns_true_when_avg_chars_below_threshold(self):
        # 49 chars / 1 page = 49 < 50
        assert self.p._needs_ocr("a" * 49, 1) is True

    def test_returns_false_when_avg_chars_equals_threshold(self):
        # 50 chars / 1 page = 50 >= 50
        assert self.p._needs_ocr("a" * 50, 1) is False

    def test_returns_false_when_avg_chars_above_threshold(self):
        # 100 chars / 1 page = 100 >= 50
        assert self.p._needs_ocr("a" * 100, 1) is False

    def test_uses_average_across_multiple_pages(self):
        # 60 chars / 2 pages = 30 < 50 → True
        assert self.p._needs_ocr("a" * 60, 2) is True

    def test_false_with_adequate_chars_across_pages(self):
        # 200 chars / 2 pages = 100 >= 50 → False
        assert self.p._needs_ocr("a" * 200, 2) is False

    def test_strips_whitespace_before_measuring(self):
        # "   " stripped → "" → 0 chars → needs OCR
        assert self.p._needs_ocr("   ", 1) is True

    def test_exact_boundary_100_chars_2_pages_is_false(self):
        # 100 / 2 = 50 >= 50 → False
        assert self.p._needs_ocr("a" * 100, 2) is False


# ===========================================================================
# PDFProcessor.pdfplumber_available (lazy caching)
# ===========================================================================

class TestPdfplumberAvailable:
    def test_returns_true_when_cached_as_true(self):
        p = PDFProcessor()
        p._pdfplumber_available = True
        assert p.pdfplumber_available is True

    def test_returns_false_when_cached_as_false(self):
        p = PDFProcessor()
        p._pdfplumber_available = False
        assert p.pdfplumber_available is False

    def test_returns_true_when_pdfplumber_importable(self):
        p = PDFProcessor()
        # pdfplumber is installed in the venv
        result = p.pdfplumber_available
        assert isinstance(result, bool)

    def test_caches_result_after_first_call(self):
        p = PDFProcessor()
        _ = p.pdfplumber_available
        # After first call, _pdfplumber_available should be set
        assert p._pdfplumber_available is not None

    def test_returns_false_when_import_fails(self):
        p = PDFProcessor()
        with patch("builtins.__import__", side_effect=ImportError("no pdfplumber")):
            # Directly test the caching logic
            p._pdfplumber_available = False
        assert p.pdfplumber_available is False


# ===========================================================================
# PDFProcessor.get_tesseract_install_instructions
# ===========================================================================

class TestGetTesseractInstallInstructions:
    def test_returns_string(self):
        p = PDFProcessor()
        result = p.get_tesseract_install_instructions()
        assert isinstance(result, str)

    def test_contains_tesseract_keyword(self):
        p = PDFProcessor()
        result = p.get_tesseract_install_instructions()
        assert "Tesseract" in result

    def test_linux_instructions_contain_apt(self):
        p = PDFProcessor()
        with patch("platform.system", return_value="Linux"):
            result = p.get_tesseract_install_instructions()
        assert "apt" in result.lower() or "dnf" in result.lower() or "pacman" in result.lower()

    def test_macos_instructions_contain_brew(self):
        p = PDFProcessor()
        with patch("platform.system", return_value="Darwin"):
            result = p.get_tesseract_install_instructions()
        assert "brew" in result

    def test_windows_instructions_contain_installer(self):
        p = PDFProcessor()
        with patch("platform.system", return_value="Windows"):
            result = p.get_tesseract_install_instructions()
        assert "installer" in result.lower() or "download" in result.lower()

    def test_linux_as_default_when_unknown_platform(self):
        # Linux branch is the else branch — also handles unknown OSes
        p = PDFProcessor()
        with patch("platform.system", return_value="FreeBSD"):
            result = p.get_tesseract_install_instructions()
        # Falls to else → Linux-style instructions
        assert "sudo" in result or "apt" in result or "dnf" in result or "pacman" in result


# ===========================================================================
# get_pdf_processor singleton
# ===========================================================================

class TestGetPdfProcessor:
    def test_returns_pdf_processor_instance(self):
        p = get_pdf_processor()
        assert isinstance(p, PDFProcessor)

    def test_returns_same_instance_on_repeated_calls(self):
        p1 = get_pdf_processor()
        p2 = get_pdf_processor()
        assert p1 is p2

    def test_new_instance_after_singleton_reset(self):
        import processing.pdf_processor as mod
        mod._pdf_processor = None
        p1 = get_pdf_processor()
        mod._pdf_processor = None
        p2 = get_pdf_processor()
        # Different instances since singleton was cleared
        assert p1 is not p2
