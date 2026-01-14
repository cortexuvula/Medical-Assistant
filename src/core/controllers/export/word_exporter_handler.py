"""
Word Exporter Handler

Handles Word document (.docx) export operations.
Extracted from ProcessingController for better separation of concerns.
"""

import logging
from tkinter import messagebox
from pathlib import Path
from typing import TYPE_CHECKING

from core.controllers.export.document_constants import get_document_display_name
from core.controllers.export.export_helpers import (
    get_active_document_info,
    get_export_file_path,
    validate_export_content
)
from settings import settings_manager

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class WordExporterHandler:
    """Handles Word document export operations.

    This handler manages:
    - Single document Word export
    - Optional letterhead inclusion
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the Word exporter handler.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def export_as_word(self) -> None:
        """Export current document as Word document (.docx)."""
        try:
            from exporters.docx_exporter import DocxExporter

            doc_type, content, _ = get_active_document_info(self.app)

            if doc_type is None:
                messagebox.showwarning("Export Error", "Invalid document tab selected.")
                return

            is_valid, error_msg = validate_export_content(doc_type, content)
            if not is_valid:
                messagebox.showwarning("Export Error", error_msg)
                return

            file_path = get_export_file_path(
                doc_type, ".docx",
                filetypes=[("Word documents", "*.docx"), ("All files", "*.*")]
            )
            if not file_path:
                return

            clinic_name = settings_manager.get("clinic_name", "")
            doctor_name = settings_manager.get("doctor_name", "")

            docx_exporter = DocxExporter(clinic_name=clinic_name, doctor_name=doctor_name)

            export_content = {
                "document_type": "soap" if doc_type == "soap_note" else "generic",
                "content": content,
                "title": get_document_display_name(doc_type),
                "include_letterhead": bool(clinic_name or doctor_name)
            }

            success = docx_exporter.export(export_content, Path(file_path))

            if success:
                display_name = get_document_display_name(doc_type)
                self.app.status_manager.success(f"{display_name} exported to Word successfully")
                self._offer_open_file(file_path)
            else:
                error_msg = docx_exporter.last_error or "Unknown error"
                messagebox.showerror("Export Failed", f"Failed to export Word document: {error_msg}")

        except Exception as e:
            logger.error(f"Error exporting to Word: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export Word document: {str(e)}")

    def _offer_open_file(self, file_path: str) -> None:
        """Offer to open exported file."""
        if messagebox.askyesno("Open Document", "Would you like to open the Word document now?"):
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(file_path, operation="open")
            if not success:
                logger.error(f"Failed to open Word document: {error}")
                messagebox.showerror("Error", f"Could not open Word document: {error}")


__all__ = ["WordExporterHandler"]
