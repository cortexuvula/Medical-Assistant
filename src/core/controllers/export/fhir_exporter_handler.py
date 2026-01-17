"""
FHIR Exporter Handler

Handles FHIR R4 JSON export operations for EHR/EMR integration.
Extracted from ProcessingController for better separation of concerns.
"""

from tkinter import messagebox
from pathlib import Path
from typing import TYPE_CHECKING

from core.controllers.export.document_constants import get_document_display_name
from core.controllers.export.export_helpers import (
    get_active_document_info,
    get_export_file_path,
    validate_export_content,
    create_fhir_config
)
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = get_logger(__name__)


class FHIRExporterHandler:
    """Handles FHIR R4 JSON export operations.

    This handler manages:
    - FHIR JSON file export
    - FHIR JSON clipboard copy
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the FHIR exporter handler.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def export_as_fhir(self) -> None:
        """Export current document as FHIR R4 JSON for EHR/EMR import."""
        try:
            from exporters.fhir_exporter import FHIRExporter

            doc_type, content, _ = get_active_document_info(self.app)

            if doc_type is None:
                messagebox.showwarning("Export Error", "Invalid document tab selected.")
                return

            is_valid, error_msg = validate_export_content(doc_type, content)
            if not is_valid:
                messagebox.showwarning("Export Error", error_msg)
                return

            file_path = get_export_file_path(
                doc_type, ".json",
                title=f"Export {get_document_display_name(doc_type)} as FHIR",
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
            if not file_path:
                return

            config = create_fhir_config()
            fhir_exporter = FHIRExporter(config)

            export_content = self._prepare_fhir_content(doc_type, content)
            success = fhir_exporter.export(export_content, Path(file_path))

            if success:
                display_name = get_document_display_name(doc_type)
                self.app.status_manager.success(f"{display_name} exported as FHIR successfully")
                self._offer_open_file(file_path)
            else:
                error_msg = fhir_exporter.last_error or "Unknown error"
                messagebox.showerror("Export Failed", f"Failed to export FHIR: {error_msg}")

        except Exception as e:
            logger.error(f"Error exporting as FHIR: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export FHIR: {str(e)}")

    def copy_fhir_to_clipboard(self) -> None:
        """Copy current document as FHIR JSON to clipboard."""
        try:
            from exporters.fhir_exporter import FHIRExporter

            doc_type, content, _ = get_active_document_info(self.app)

            if doc_type is None:
                messagebox.showwarning("Export Error", "Invalid document tab selected.")
                return

            is_valid, error_msg = validate_export_content(doc_type, content)
            if not is_valid:
                messagebox.showwarning("Export Error", error_msg)
                return

            config = create_fhir_config()
            fhir_exporter = FHIRExporter(config)

            export_content = self._prepare_fhir_content(doc_type, content)
            success = fhir_exporter.export_to_clipboard(export_content)

            if success:
                self.app.status_manager.success("FHIR JSON copied to clipboard")
                messagebox.showinfo(
                    "Success",
                    "FHIR JSON has been copied to clipboard.\n\n"
                    "You can now paste it into your EHR/EMR import field."
                )
            else:
                error_msg = fhir_exporter.last_error or "Unknown error"
                messagebox.showerror("Export Failed", f"Failed to copy FHIR to clipboard: {error_msg}")

        except Exception as e:
            logger.error(f"Error copying FHIR to clipboard: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to copy FHIR: {str(e)}")

    def _prepare_fhir_content(self, doc_type: str, content: str) -> dict:
        """Prepare content dictionary for FHIR export.

        Args:
            doc_type: Document type
            content: Document content

        Returns:
            Dictionary with FHIR export parameters
        """
        display_name = get_document_display_name(doc_type)

        return {
            "soap_data": content,
            "title": display_name,
            "export_type": "bundle" if doc_type == "soap_note" else "document_reference",
            "document_type": doc_type
        }

    def _offer_open_file(self, file_path: str) -> None:
        """Offer to open exported file."""
        if messagebox.askyesno("Open File", "Would you like to open the FHIR JSON file now?"):
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(file_path, operation="open")
            if not success:
                logger.error(f"Failed to open FHIR file: {error}")
                messagebox.showerror("Error", f"Could not open file: {error}")


__all__ = ["FHIRExporterHandler"]
