"""
OCR Provider Management Module.

This module provides centralized OCR provider management using
Azure Document Intelligence as the sole OCR provider.

Usage:
    # Get the OCR provider
    from src.ocr_providers import get_ocr_provider
    provider = get_ocr_provider()
    result = provider.extract_from_image("scan.png")

    # Use the manager directly
    from src.ocr_providers import OCRProviderManager
    manager = OCRProviderManager()
    result = manager.extract_from_image("scan.png")
"""

from typing import Optional

from ocr_providers.base import BaseOCRProvider, OCRResult
from ocr_providers.azure_document import AzureDocumentProvider
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Export main classes
__all__ = [
    "BaseOCRProvider",
    "OCRResult",
    "AzureDocumentProvider",
    "OCRProviderManager",
    "get_ocr_provider",
]


class OCRProviderManager:
    """Singleton manager for OCR provider.

    This manager handles Azure Document Intelligence provider initialization.

    Attributes:
        azure_provider: Azure Document Intelligence provider instance
    """

    _instance: Optional['OCRProviderManager'] = None

    def __new__(cls) -> 'OCRProviderManager':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(OCRProviderManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the OCR provider manager."""
        if self._initialized:
            return

        self._azure_provider: Optional[AzureDocumentProvider] = None
        self._initialized = True

        logger.info("OCR Provider Manager initialized")

    @property
    def azure_provider(self) -> AzureDocumentProvider:
        """Get or create the Azure provider instance."""
        if self._azure_provider is None:
            self._azure_provider = AzureDocumentProvider()
        return self._azure_provider

    def get_provider(self) -> AzureDocumentProvider:
        """Get the Azure OCR provider.

        Returns:
            Azure Document Intelligence provider
        """
        return self.azure_provider

    def get_available_providers(self) -> dict[str, bool]:
        """Check which providers are available.

        Returns:
            Dict mapping provider names to their availability status
        """
        return {
            "azure_document_intelligence": self.azure_provider.is_configured,
        }

    def extract_from_image(self, file_path: str) -> OCRResult:
        """Extract text from an image file using Azure.

        Args:
            file_path: Path to the image or document

        Returns:
            OCRResult from Azure or error result
        """
        if not self.azure_provider.is_configured:
            return OCRResult.failure_result(
                "Azure Document Intelligence not configured. "
                "Please set AZURE_DOCUMENT_ENDPOINT and AZURE_DOCUMENT_KEY."
            )

        logger.debug("Performing OCR with Azure Document Intelligence")
        return self.azure_provider.extract_from_image(file_path)

    def extract_from_pil_image(self, pil_image) -> OCRResult:
        """Extract text from a PIL Image using Azure.

        Args:
            pil_image: PIL Image object

        Returns:
            OCRResult from Azure or error result
        """
        if not self.azure_provider.is_configured:
            return OCRResult.failure_result(
                "Azure Document Intelligence not configured. "
                "Please set AZURE_DOCUMENT_ENDPOINT and AZURE_DOCUMENT_KEY."
            )

        logger.debug("Performing OCR with Azure Document Intelligence")
        return self.azure_provider.extract_from_pdf_page(pil_image)

    def test_all_connections(self) -> dict[str, bool]:
        """Test connection to Azure provider.

        Returns:
            Dict mapping provider name to connection test result
        """
        results = {}

        if self.azure_provider.is_configured:
            results["azure_document_intelligence"] = self.azure_provider.test_connection()
        else:
            results["azure_document_intelligence"] = False

        return results


# Module-level singleton instance
_manager: Optional[OCRProviderManager] = None


def get_ocr_manager() -> OCRProviderManager:
    """Get the singleton OCR provider manager.

    Returns:
        OCRProviderManager instance
    """
    global _manager
    if _manager is None:
        _manager = OCRProviderManager()
    return _manager


def get_ocr_provider() -> AzureDocumentProvider:
    """Convenience function to get the Azure OCR provider.

    Returns:
        Azure Document Intelligence provider
    """
    return get_ocr_manager().get_provider()
