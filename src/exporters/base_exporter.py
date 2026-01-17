"""
Base Exporter Module

Abstract base class for document exporters providing a common interface
for all export formats (FHIR, Word, PDF, etc.).
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Any, Optional, Union
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class BaseExporter(ABC):
    """Abstract base class for document exporters.

    All export implementations (FHIR, Word, PDF) should inherit from this
    class and implement the required abstract methods.
    """

    def __init__(self):
        """Initialize the base exporter."""
        self._last_error: Optional[str] = None

    @property
    def last_error(self) -> Optional[str]:
        """Get the last error message if export failed."""
        return self._last_error

    @abstractmethod
    def export(
        self,
        content: Dict[str, Any],
        output_path: Path
    ) -> bool:
        """Export content to a file.

        Args:
            content: Dictionary containing the content to export.
                    Structure varies by document type.
            output_path: Path where the exported file should be saved.

        Returns:
            True if export was successful, False otherwise.
            Check last_error property for error details on failure.
        """
        pass

    @abstractmethod
    def export_to_string(self, content: Dict[str, Any]) -> str:
        """Export content and return as string.

        Useful for clipboard operations or preview functionality.

        Args:
            content: Dictionary containing the content to export.

        Returns:
            Exported content as a string (JSON, XML, etc. depending on format).
        """
        pass

    def export_to_clipboard(self, content: Dict[str, Any]) -> bool:
        """Export content to clipboard.

        Args:
            content: Dictionary containing the content to export.

        Returns:
            True if successful, False otherwise.
        """
        try:
            import pyperclip
            export_string = self.export_to_string(content)
            pyperclip.copy(export_string)
            logger.info("Content copied to clipboard")
            return True
        except Exception as e:
            self._last_error = f"Failed to copy to clipboard: {str(e)}"
            logger.error(self._last_error)
            return False

    def _validate_content(self, content: Dict[str, Any], required_keys: list) -> bool:
        """Validate that content contains required keys.

        Args:
            content: Content dictionary to validate.
            required_keys: List of keys that must be present.

        Returns:
            True if all required keys are present, False otherwise.
        """
        missing = [key for key in required_keys if key not in content]
        if missing:
            self._last_error = f"Missing required content keys: {missing}"
            logger.error(self._last_error)
            return False
        return True

    def _ensure_directory(self, path: Path) -> bool:
        """Ensure the directory for the output path exists.

        Args:
            path: Path to check/create directory for.

        Returns:
            True if directory exists or was created, False on error.
        """
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            return True
        except Exception as e:
            self._last_error = f"Failed to create directory: {str(e)}"
            logger.error(self._last_error)
            return False
