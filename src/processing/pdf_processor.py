"""
PDF Processor for RSVP Reader

Extracts text from PDF files with OCR fallback for scanned documents.
Uses pdfplumber for text-based PDFs and pytesseract for OCR.
"""

import shutil
from typing import Callable, Optional, Tuple
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class PDFProcessor:
    """Handles PDF text extraction with OCR fallback."""

    # Minimum characters per page to consider PDF as text-based
    MIN_CHARS_PER_PAGE = 50

    def __init__(self):
        """Initialize the PDF processor."""
        self._pdfplumber_available = None
        self._pytesseract_available = None
        self._tesseract_path = None

    @property
    def pdfplumber_available(self) -> bool:
        """Check if pdfplumber is available."""
        if self._pdfplumber_available is None:
            try:
                import pdfplumber
                self._pdfplumber_available = True
            except ImportError:
                self._pdfplumber_available = False
                logger.warning("pdfplumber not available")
        return self._pdfplumber_available

    @property
    def tesseract_available(self) -> bool:
        """Check if Tesseract OCR is installed and available."""
        if self._pytesseract_available is None:
            try:
                import pytesseract
                # Try to find tesseract executable
                tesseract_path = shutil.which("tesseract")
                if tesseract_path:
                    self._tesseract_path = tesseract_path
                    self._pytesseract_available = True
                else:
                    # Try common installation paths
                    import platform
                    system = platform.system()
                    if system == "Windows":
                        common_paths = [
                            r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                            r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                        ]
                    elif system == "Darwin":  # macOS
                        common_paths = [
                            "/usr/local/bin/tesseract",
                            "/opt/homebrew/bin/tesseract",
                        ]
                    else:  # Linux
                        common_paths = [
                            "/usr/bin/tesseract",
                            "/usr/local/bin/tesseract",
                        ]

                    import os
                    for path in common_paths:
                        if os.path.exists(path):
                            self._tesseract_path = path
                            pytesseract.pytesseract.tesseract_cmd = path
                            self._pytesseract_available = True
                            break
                    else:
                        self._pytesseract_available = False
            except ImportError:
                self._pytesseract_available = False
                logger.warning("pytesseract not available")
        return self._pytesseract_available

    def get_tesseract_install_instructions(self) -> str:
        """Get platform-specific Tesseract installation instructions."""
        import platform
        system = platform.system()

        if system == "Windows":
            return (
                "Tesseract OCR is required for scanned PDF support.\n\n"
                "Installation:\n"
                "1. Download installer from:\n"
                "   https://github.com/UB-Mannheim/tesseract/wiki\n"
                "2. Run the installer\n"
                "3. Restart the application"
            )
        elif system == "Darwin":  # macOS
            return (
                "Tesseract OCR is required for scanned PDF support.\n\n"
                "Installation:\n"
                "  brew install tesseract\n\n"
                "Then restart the application."
            )
        else:  # Linux
            return (
                "Tesseract OCR is required for scanned PDF support.\n\n"
                "Installation:\n"
                "  Ubuntu/Debian: sudo apt-get install tesseract-ocr\n"
                "  Fedora: sudo dnf install tesseract\n"
                "  Arch: sudo pacman -S tesseract\n\n"
                "Then restart the application."
            )

    def extract_text(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[str, bool]:
        """Extract text from a PDF file.

        Tries pdfplumber first. If the extracted text is sparse (< 50 chars/page),
        falls back to OCR using pytesseract.

        Args:
            file_path: Path to the PDF file
            progress_callback: Optional callback for progress updates (message: str)

        Returns:
            Tuple of (extracted_text, used_ocr)
            - extracted_text: The extracted text content
            - used_ocr: True if OCR was used, False if text extraction worked

        Raises:
            Exception: If PDF extraction fails
        """
        if not self.pdfplumber_available:
            raise ImportError(
                "pdfplumber is required for PDF processing.\n"
                "Install with: pip install pdfplumber"
            )

        # Try text-based extraction first
        if progress_callback:
            progress_callback("Extracting text from PDF...")

        text, page_count = self._extract_with_pdfplumber(file_path, progress_callback)

        # Check if we got enough text
        if self._needs_ocr(text, page_count):
            if progress_callback:
                progress_callback("PDF appears to be scanned, attempting OCR...")

            if not self.tesseract_available:
                # Return what we have with a warning
                logger.warning("Tesseract not available for OCR fallback")
                if text.strip():
                    return text, False
                raise RuntimeError(
                    "This PDF appears to be scanned but Tesseract OCR is not installed.\n\n"
                    + self.get_tesseract_install_instructions()
                )

            # Use OCR
            ocr_text = self._extract_with_ocr(file_path, progress_callback)
            return ocr_text, True

        return text, False

    def _extract_with_pdfplumber(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> Tuple[str, int]:
        """Extract text using pdfplumber.

        Args:
            file_path: Path to the PDF file
            progress_callback: Optional progress callback

        Returns:
            Tuple of (extracted_text, page_count)
        """
        import pdfplumber

        text_parts = []
        page_count = 0

        with pdfplumber.open(file_path) as pdf:
            page_count = len(pdf.pages)

            for i, page in enumerate(pdf.pages):
                if progress_callback:
                    progress_callback(f"Processing page {i + 1} of {page_count}...")

                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        return "\n\n".join(text_parts), page_count

    def _extract_with_ocr(
        self,
        file_path: str,
        progress_callback: Optional[Callable[[str], None]] = None
    ) -> str:
        """Extract text using OCR (pytesseract + pdf2image).

        Args:
            file_path: Path to the PDF file
            progress_callback: Optional progress callback

        Returns:
            Extracted text from OCR
        """
        try:
            import pytesseract
            from pdf2image import convert_from_path
        except ImportError as e:
            raise ImportError(
                f"OCR dependencies not available: {e}\n"
                "Install with: pip install pytesseract pdf2image"
            )

        # Configure tesseract path if we found it
        if self._tesseract_path:
            pytesseract.pytesseract.tesseract_cmd = self._tesseract_path

        if progress_callback:
            progress_callback("Converting PDF to images for OCR...")

        # Convert PDF to images
        try:
            images = convert_from_path(file_path)
        except Exception as e:
            raise RuntimeError(
                f"Failed to convert PDF to images: {e}\n\n"
                "This may require poppler-utils to be installed:\n"
                "  Ubuntu/Debian: sudo apt-get install poppler-utils\n"
                "  macOS: brew install poppler\n"
                "  Windows: Download from https://github.com/oschwartz10612/poppler-windows"
            )

        text_parts = []
        total_pages = len(images)

        for i, image in enumerate(images):
            if progress_callback:
                progress_callback(f"Running OCR on page {i + 1} of {total_pages}...")

            # Run OCR on the image
            page_text = pytesseract.image_to_string(image)
            if page_text.strip():
                text_parts.append(page_text.strip())

        return "\n\n".join(text_parts)

    def _needs_ocr(self, text: str, page_count: int) -> bool:
        """Determine if OCR is needed based on extracted text density.

        Args:
            text: Extracted text from pdfplumber
            page_count: Number of pages in the PDF

        Returns:
            True if OCR should be attempted
        """
        if page_count == 0:
            return True

        # Calculate average characters per page
        text_length = len(text.strip())
        avg_chars_per_page = text_length / page_count

        return avg_chars_per_page < self.MIN_CHARS_PER_PAGE


# Singleton instance
_pdf_processor = None


def get_pdf_processor() -> PDFProcessor:
    """Get the singleton PDF processor instance."""
    global _pdf_processor
    if _pdf_processor is None:
        _pdf_processor = PDFProcessor()
    return _pdf_processor


__all__ = ["PDFProcessor", "get_pdf_processor"]
