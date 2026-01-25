"""
Base class for OCR (Optical Character Recognition) providers.

This module defines the interface that all OCR providers must implement,
ensuring consistent behavior across different OCR services like
Azure Document Intelligence.

Error Handling:
    - OCRResult.success indicates operation success/failure
    - OCRResult.error contains error message on failure
    - Providers should catch provider-specific exceptions and return error results
    - test_connection() returns bool, never raises exceptions

Logging:
    - Each provider uses get_logger(self.__class__.__name__)
    - Logs include image dimensions, processing time, and confidence metrics
    - API keys and image data are not logged

Usage:
    provider = AzureDocumentProvider()
    result = provider.extract_from_image("/path/to/image.png")
    if result.success:
        text = result.text
        tables = result.tables
    else:
        handle_error(result.error)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pathlib import Path

from utils.structured_logging import get_logger


@dataclass
class OCRResult:
    """Structured result from an OCR operation.

    This class provides a consistent format for OCR results
    across all providers, including metadata and error information.
    """

    text: str
    """The extracted text from the document/image."""

    success: bool = True
    """Whether the OCR operation was successful."""

    error: Optional[str] = None
    """Error message if OCR failed."""

    confidence: Optional[float] = None
    """Overall confidence score (0.0-1.0) if available from provider."""

    tables: List[Dict[str, Any]] = field(default_factory=list)
    """Extracted table data as list of dicts with rows/columns."""

    layout_info: Dict[str, Any] = field(default_factory=dict)
    """Layout information (paragraphs, headers, etc.) if available."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional provider-specific metadata."""

    @classmethod
    def success_result(cls, text: str, **kwargs) -> 'OCRResult':
        """Create a successful OCR result.

        Args:
            text: The extracted text
            **kwargs: Additional fields (confidence, tables, etc.)

        Returns:
            OCRResult with success=True
        """
        return cls(text=text, success=True, **kwargs)

    @classmethod
    def failure_result(cls, error: str, **kwargs) -> 'OCRResult':
        """Create a failed OCR result.

        Args:
            error: Error message describing the failure
            **kwargs: Additional fields

        Returns:
            OCRResult with success=False and error message
        """
        return cls(text="", success=False, error=error, **kwargs)


class BaseOCRProvider(ABC):
    """Base class that all OCR providers must implement.

    This abstract base class defines the interface for OCR providers.
    Subclasses must implement the abstract methods to provide OCR
    functionality.

    Attributes:
        language: Language code for OCR (e.g., "eng", "fra")
        logger: Logger instance for this provider

    Example:
        class MyProvider(BaseOCRProvider):
            @property
            def provider_name(self) -> str:
                return "my_provider"

            def extract_from_image(self, file_path: str) -> OCRResult:
                # Implementation here
                pass

            def test_connection(self) -> bool:
                # Validate connection
                pass
    """

    def __init__(self, language: str = "eng"):
        """Initialize the provider with language settings.

        Args:
            language: Language code for OCR (e.g., 'eng', 'fra', 'deu')
        """
        self.language = language
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique identifier for this provider.

        Returns:
            A lowercase string identifier (e.g., "azure_document_intelligence")
        """
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Check if the provider is properly configured.

        Returns:
            True if the provider has all required configuration
        """
        pass

    @abstractmethod
    def extract_from_image(self, file_path: str) -> OCRResult:
        """Extract text from an image file.

        Args:
            file_path: Path to the image file (PNG, JPG, TIFF, BMP)

        Returns:
            OCRResult with extracted text or error information
        """
        pass

    @abstractmethod
    def extract_from_pdf_page(self, pil_image) -> OCRResult:
        """Extract text from a PDF page rendered as PIL Image.

        Args:
            pil_image: PIL Image object of the rendered PDF page

        Returns:
            OCRResult with extracted text or error information
        """
        pass

    @abstractmethod
    def extract_from_bytes(self, image_bytes: bytes, file_type: str = "png") -> OCRResult:
        """Extract text from raw image bytes.

        Args:
            image_bytes: Raw bytes of the image
            file_type: File type/extension hint (e.g., "png", "jpg", "pdf")

        Returns:
            OCRResult with extracted text or error information
        """
        pass

    @abstractmethod
    def test_connection(self) -> bool:
        """Test if the provider is properly configured and accessible.

        This method validates that:
        1. Required API key/credentials are present (if needed)
        2. The service is reachable (for cloud providers)
        3. Authentication is valid (for cloud providers)

        Returns:
            True if connection test passes, False otherwise
        """
        pass

    def _validate_file_path(self, file_path: str) -> Optional[str]:
        """Validate that a file path exists and is readable.

        Args:
            file_path: Path to validate

        Returns:
            Error message if invalid, None if valid
        """
        path = Path(file_path)
        if not path.exists():
            return f"File not found: {file_path}"
        if not path.is_file():
            return f"Path is not a file: {file_path}"
        return None

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        configured = "configured" if self.is_configured else "not configured"
        return f"<{self.__class__.__name__}({self.provider_name}, {configured})>"
