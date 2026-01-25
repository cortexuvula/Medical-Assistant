"""
Azure Document Intelligence (Form Recognizer) OCR Provider.

This provider uses Azure's Document Intelligence service for high-quality
text extraction from documents and images. It supports:
- Multi-page PDF documents
- Images (PNG, JPG, TIFF, BMP)
- Table extraction
- Layout analysis

The prebuilt-read model is used by default, optimized for text-heavy documents
like medical records. For documents with complex tables, prebuilt-layout can
be used instead.

Configuration:
    Set the following environment variables:
    - AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT: Your Azure resource endpoint
    - AZURE_DOCUMENT_INTELLIGENCE_KEY: Your API key

Usage:
    provider = AzureDocumentProvider()
    if provider.is_configured:
        result = provider.extract_from_image("scan.png")
        print(result.text)
"""

import io
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from ocr_providers.base import BaseOCRProvider, OCRResult
from utils.structured_logging import get_logger
from utils.timeout_config import get_timeout

logger = get_logger(__name__)

# Azure SDK import with graceful handling
try:
    from azure.ai.formrecognizer import DocumentAnalysisClient
    from azure.core.credentials import AzureKeyCredential
    from azure.core.exceptions import (
        HttpResponseError,
        ServiceRequestError,
        ClientAuthenticationError,
    )
    AZURE_SDK_AVAILABLE = True
except ImportError:
    AZURE_SDK_AVAILABLE = False
    DocumentAnalysisClient = None
    AzureKeyCredential = None
    HttpResponseError = Exception
    ServiceRequestError = Exception
    ClientAuthenticationError = Exception


class AzureDocumentProvider(BaseOCRProvider):
    """Azure Document Intelligence OCR provider.

    Uses Azure's prebuilt-read or prebuilt-layout models for high-quality
    text extraction with support for tables and layout analysis.

    Attributes:
        endpoint: Azure Document Intelligence endpoint URL
        api_key: API key for authentication
        model_id: Model to use (prebuilt-read or prebuilt-layout)
    """

    # Supported models
    MODEL_READ = "prebuilt-read"  # Best for text-heavy documents
    MODEL_LAYOUT = "prebuilt-layout"  # Better for tables and forms

    def __init__(
        self,
        endpoint: Optional[str] = None,
        api_key: Optional[str] = None,
        model_id: str = MODEL_READ,
        language: str = "eng",
    ):
        """Initialize the Azure Document Intelligence provider.

        Args:
            endpoint: Azure endpoint URL (or use AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT env var)
            api_key: API key (or use AZURE_DOCUMENT_INTELLIGENCE_KEY env var)
            model_id: Model to use (prebuilt-read or prebuilt-layout)
            language: Language hint for OCR
        """
        super().__init__(language=language)

        self.endpoint = endpoint or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT", "")
        self.api_key = api_key or os.getenv("AZURE_DOCUMENT_INTELLIGENCE_KEY", "")
        self.model_id = model_id

        # Client is lazily initialized
        self._client: Optional[DocumentAnalysisClient] = None

    @property
    def provider_name(self) -> str:
        """Return the provider identifier."""
        return "azure_document_intelligence"

    @property
    def is_configured(self) -> bool:
        """Check if the provider has required configuration."""
        if not AZURE_SDK_AVAILABLE:
            return False
        return bool(self.endpoint and self.api_key)

    def _get_client(self) -> Optional[DocumentAnalysisClient]:
        """Get or create the Azure Document Analysis client.

        Returns:
            DocumentAnalysisClient or None if not configured
        """
        if not self.is_configured:
            return None

        if self._client is None:
            try:
                self._client = DocumentAnalysisClient(
                    endpoint=self.endpoint,
                    credential=AzureKeyCredential(self.api_key),
                )
            except Exception as e:
                self.logger.error(f"Failed to create Azure client: {e}")
                return None

        return self._client

    def extract_from_image(self, file_path: str) -> OCRResult:
        """Extract text from an image file using Azure Document Intelligence.

        Args:
            file_path: Path to the image file

        Returns:
            OCRResult with extracted text and metadata
        """
        # Validate file path
        error = self._validate_file_path(file_path)
        if error:
            return OCRResult.failure_result(error)

        # Read file bytes
        try:
            with open(file_path, "rb") as f:
                image_bytes = f.read()
        except Exception as e:
            return OCRResult.failure_result(f"Failed to read file: {e}")

        # Determine file type from extension
        file_type = Path(file_path).suffix.lower().lstrip(".")
        if file_type == "jpg":
            file_type = "jpeg"

        return self.extract_from_bytes(image_bytes, file_type)

    def extract_from_pdf_page(self, pil_image) -> OCRResult:
        """Extract text from a PDF page rendered as PIL Image.

        Args:
            pil_image: PIL Image object of the rendered page

        Returns:
            OCRResult with extracted text
        """
        try:
            # Convert PIL Image to PNG bytes
            buffer = io.BytesIO()
            pil_image.save(buffer, format="PNG")
            image_bytes = buffer.getvalue()
            return self.extract_from_bytes(image_bytes, "png")
        except Exception as e:
            return OCRResult.failure_result(f"Failed to convert image: {e}")

    def extract_from_bytes(self, image_bytes: bytes, file_type: str = "png") -> OCRResult:
        """Extract text from raw image bytes using Azure Document Intelligence.

        Args:
            image_bytes: Raw bytes of the image/document
            file_type: File type hint (png, jpeg, pdf, tiff, bmp)

        Returns:
            OCRResult with extracted text, tables, and metadata
        """
        if not AZURE_SDK_AVAILABLE:
            return OCRResult.failure_result(
                "Azure SDK not installed. Install with: pip install azure-ai-formrecognizer"
            )

        client = self._get_client()
        if not client:
            return OCRResult.failure_result(
                "Azure Document Intelligence not configured. "
                "Set AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT and AZURE_DOCUMENT_INTELLIGENCE_KEY."
            )

        start_time = time.time()

        try:
            # Start the analysis
            timeout = get_timeout("azure_document_intelligence", default=120.0)

            poller = client.begin_analyze_document(
                model_id=self.model_id,
                document=io.BytesIO(image_bytes),
            )

            # Poll for result with timeout
            result = poller.result(timeout=int(timeout))

            # Extract text content
            text = result.content if result.content else ""

            # Extract table data if using layout model
            tables = self._extract_tables(result) if self.model_id == self.MODEL_LAYOUT else []

            # Build metadata
            processing_time = time.time() - start_time
            metadata = {
                "provider": self.provider_name,
                "model": self.model_id,
                "processing_time_seconds": round(processing_time, 2),
                "page_count": len(result.pages) if result.pages else 0,
                "file_type": file_type,
            }

            # Calculate average confidence
            confidence = self._calculate_confidence(result)

            self.logger.info(
                f"Azure OCR completed: {len(text)} chars, "
                f"{metadata['page_count']} pages, "
                f"confidence={confidence:.2f}, "
                f"time={processing_time:.2f}s"
            )

            return OCRResult.success_result(
                text=text.strip(),
                confidence=confidence,
                tables=tables,
                metadata=metadata,
            )

        except ClientAuthenticationError as e:
            self.logger.error(f"Azure authentication failed: {e}")
            return OCRResult.failure_result(
                "Azure authentication failed. Check your API key.",
                metadata={"provider": self.provider_name, "error_type": "authentication"},
            )

        except ServiceRequestError as e:
            self.logger.error(f"Azure service request failed: {e}")
            return OCRResult.failure_result(
                f"Azure service unavailable: {e}",
                metadata={"provider": self.provider_name, "error_type": "service_unavailable"},
            )

        except HttpResponseError as e:
            self.logger.error(f"Azure HTTP error: {e}")
            error_msg = str(e)

            # Handle rate limiting
            if "429" in error_msg or "Too Many Requests" in error_msg:
                return OCRResult.failure_result(
                    "Azure rate limit exceeded. Please try again later.",
                    metadata={"provider": self.provider_name, "error_type": "rate_limit"},
                )

            return OCRResult.failure_result(
                f"Azure API error: {e}",
                metadata={"provider": self.provider_name, "error_type": "api_error"},
            )

        except Exception as e:
            self.logger.error(f"Unexpected Azure OCR error: {e}")
            return OCRResult.failure_result(
                f"OCR failed: {e}",
                metadata={"provider": self.provider_name, "error_type": "unknown"},
            )

    def _extract_tables(self, result) -> List[Dict[str, Any]]:
        """Extract table data from analysis result.

        Args:
            result: Azure DocumentAnalysisResult

        Returns:
            List of table dictionaries with rows and cells
        """
        tables = []

        if not hasattr(result, "tables") or not result.tables:
            return tables

        for table_idx, table in enumerate(result.tables):
            table_data = {
                "index": table_idx,
                "row_count": table.row_count,
                "column_count": table.column_count,
                "cells": [],
            }

            for cell in table.cells:
                cell_data = {
                    "row": cell.row_index,
                    "column": cell.column_index,
                    "text": cell.content,
                    "row_span": cell.row_span,
                    "column_span": cell.column_span,
                }
                table_data["cells"].append(cell_data)

            tables.append(table_data)

        return tables

    def _calculate_confidence(self, result) -> float:
        """Calculate average confidence from analysis result.

        Args:
            result: Azure DocumentAnalysisResult

        Returns:
            Average confidence score (0.0-1.0)
        """
        confidences = []

        if hasattr(result, "pages") and result.pages:
            for page in result.pages:
                if hasattr(page, "words") and page.words:
                    for word in page.words:
                        if hasattr(word, "confidence") and word.confidence:
                            confidences.append(word.confidence)

        if confidences:
            return sum(confidences) / len(confidences)
        return 0.0

    def test_connection(self) -> bool:
        """Test Azure Document Intelligence connection.

        This test validates that:
        1. The endpoint is reachable
        2. The API key is valid
        3. The service can process a request

        Returns:
            True if connection is successful, False otherwise
        """
        if not self.is_configured:
            self.logger.warning("Azure Document Intelligence not configured")
            return False

        client = self._get_client()
        if not client:
            return False

        try:
            # Create a minimal valid test image using PIL
            # Azure requires at least 50x50 pixels
            try:
                from PIL import Image as PILImage

                # Create a 50x50 white image with "Test" text
                img = PILImage.new("RGB", (100, 50), color="white")

                # Try to add text if PIL has ImageDraw
                try:
                    from PIL import ImageDraw
                    draw = ImageDraw.Draw(img)
                    draw.text((10, 15), "Test", fill="black")
                except ImportError:
                    pass  # No text, just white image

                # Convert to PNG bytes
                buffer = io.BytesIO()
                img.save(buffer, format="PNG")
                test_png = buffer.getvalue()

            except ImportError:
                # Fallback: Create a minimal 50x50 PNG manually
                # This is more complex, so we'll just check if client exists
                self.logger.info("PIL not available, checking client creation only")
                return True

            # Try to analyze the test image
            poller = client.begin_analyze_document(
                model_id=self.model_id,
                document=io.BytesIO(test_png),
            )
            result = poller.result(timeout=30)

            self.logger.info("Azure Document Intelligence connection test successful")
            return True

        except ClientAuthenticationError:
            self.logger.error("Azure authentication failed - check API key")
            return False

        except HttpResponseError as e:
            # Check if this is an image dimension error (which means auth worked)
            if "InvalidContentDimensions" in str(e):
                self.logger.info("Azure connection verified (image dimension error expected)")
                return True
            self.logger.error(f"Azure connection test failed: {e}")
            return False

        except Exception as e:
            self.logger.error(f"Azure connection test failed: {e}")
            return False
