"""
PDF Exporter Handler

Handles PDF export operations for medical documents.
Extracted from ProcessingController for better separation of concerns.
"""

import logging
import os
import tempfile
from tkinter import messagebox, filedialog
from typing import TYPE_CHECKING, Dict, Optional

from core.controllers.export.document_constants import (
    SOAP_EXPORT_TYPES,
    CORRESPONDENCE_TYPES,
    get_document_display_name
)
from core.controllers.export.export_helpers import (
    get_active_document_info,
    get_export_file_path,
    validate_export_content
)
from settings import settings_manager

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class PDFExporterHandler:
    """Handles PDF export operations for documents.

    This handler manages:
    - Single document PDF export
    - Batch PDF export
    - PDF with letterhead
    - Print document via PDF
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the PDF exporter handler.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def export_as_pdf(self) -> None:
        """Export current document as PDF."""
        try:
            from utils.pdf_exporter import PDFExporter

            doc_type, content, _ = get_active_document_info(self.app)

            if doc_type is None:
                messagebox.showwarning("Export Error", "Invalid document tab selected.")
                return

            is_valid, error_msg = validate_export_content(doc_type, content)
            if not is_valid:
                messagebox.showwarning("Export Error", error_msg)
                return

            file_path = get_export_file_path(doc_type, ".pdf")
            if not file_path:
                return

            pdf_exporter = PDFExporter()
            success = self._export_document_as_pdf(pdf_exporter, doc_type, content, file_path)

            if success:
                display_name = get_document_display_name(doc_type)
                self.app.status_manager.success(f"{display_name} exported to PDF successfully")
                self._offer_open_file(file_path)
            else:
                messagebox.showerror("Export Failed", "Failed to export PDF. Check logs for details.")

        except Exception as e:
            logger.error(f"Error exporting to PDF: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")

    def export_all_as_pdf(self) -> None:
        """Export all documents as separate PDFs."""
        try:
            from utils.pdf_exporter import PDFExporter

            directory = filedialog.askdirectory(title="Select Directory for PDF Export")
            if not directory:
                return

            pdf_exporter = PDFExporter()
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exported_count = 0

            documents = [
                ('transcript', self.app.transcript_text, 'Transcript'),
                ('soap_note', self.app.soap_text, 'SOAP Note'),
                ('referral', self.app.referral_text, 'Referral'),
                ('letter', self.app.letter_text, 'Letter')
            ]

            for doc_type, widget, _ in documents:
                content = widget.get("1.0", "end").strip()
                if content:
                    file_path = os.path.join(directory, f"{doc_type}_{timestamp}.pdf")
                    success = self._export_document_as_pdf(pdf_exporter, doc_type, content, file_path)
                    if success:
                        exported_count += 1

            if exported_count > 0:
                self.app.status_manager.success(f"Exported {exported_count} documents to PDF")
                self._offer_open_folder(directory)
            else:
                messagebox.showinfo("Export Info", "No documents with content to export.")

        except Exception as e:
            logger.error(f"Error exporting all to PDF: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export PDFs: {str(e)}")

    def export_as_pdf_letterhead(self) -> None:
        """Export current document as PDF with simple letterhead."""
        try:
            from utils.pdf_exporter import PDFExporter

            clinic_name = settings_manager.get("clinic_name", "")
            doctor_name = settings_manager.get("doctor_name", "")

            if not clinic_name and not doctor_name:
                from ui.dialogs.dialogs import show_letterhead_dialog
                result = show_letterhead_dialog(self.app, clinic_name, doctor_name)
                if result is None:
                    return
                clinic_name, doctor_name = result

            doc_type, content, _ = get_active_document_info(self.app)

            if doc_type is None:
                messagebox.showwarning("Export Error", "Invalid document tab selected.")
                return

            is_valid, error_msg = validate_export_content(doc_type, content)
            if not is_valid:
                messagebox.showwarning("Export Error", error_msg)
                return

            file_path = get_export_file_path(
                doc_type, ".pdf",
                title=f"Export {get_document_display_name(doc_type)} as PDF (Letterhead)"
            )
            if not file_path:
                return

            pdf_exporter = PDFExporter()
            pdf_exporter.set_simple_letterhead(clinic_name, doctor_name)

            success = self._export_document_as_pdf(pdf_exporter, doc_type, content, file_path)

            if success:
                display_name = get_document_display_name(doc_type)
                self.app.status_manager.success(f"{display_name} exported to PDF with letterhead")
                self._offer_open_file(file_path)
            else:
                messagebox.showerror("Export Failed", "Failed to export PDF. Check logs for details.")

        except Exception as e:
            logger.error(f"Error exporting to PDF with letterhead: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")

    def print_document(self) -> None:
        """Print current document via system dialog."""
        try:
            from utils.pdf_exporter import PDFExporter
            from utils.validation import open_file_or_folder_safely
            from core.controllers.export.export_helpers import get_text_widgets
            from core.controllers.export.document_constants import DOCUMENT_TYPES

            selected_tab = self.app.notebook.index('current')
            text_widgets = get_text_widgets(self.app)
            content = text_widgets[selected_tab].get("1.0", "end").strip()

            if not content:
                messagebox.showwarning("Print Error", "No content to print.")
                return

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name

            pdf_exporter = PDFExporter()
            doc_type = DOCUMENT_TYPES[selected_tab]

            success = self._export_document_as_pdf(pdf_exporter, doc_type, content, tmp_path)

            if success:
                print_success, error = open_file_or_folder_safely(tmp_path, operation="print")

                if print_success:
                    self.app.status_manager.info("Document sent to printer")
                else:
                    logger.error(f"Failed to print: {error}")
                    messagebox.showerror("Print Error", f"Failed to print document: {error}")

                self.app.after(5000, lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
            else:
                messagebox.showerror("Print Error", "Failed to prepare document for printing.")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except Exception as e:
            logger.error(f"Error printing document: {str(e)}")
            messagebox.showerror("Print Error", f"Failed to print: {str(e)}")

    def _export_document_as_pdf(
        self,
        pdf_exporter,
        doc_type: str,
        content: str,
        file_path: str
    ) -> bool:
        """Export a document to PDF based on its type.

        Args:
            pdf_exporter: PDFExporter instance
            doc_type: Type of document
            content: Document content
            file_path: Output file path

        Returns:
            True if export was successful
        """
        if doc_type in SOAP_EXPORT_TYPES:
            soap_data = self._parse_soap_sections(content)
            return pdf_exporter.generate_soap_note_pdf(soap_data, file_path)
        elif doc_type in CORRESPONDENCE_TYPES:
            title = 'Medical Referral' if doc_type == 'referral' else 'Medical Correspondence'
            data = {"body": content, "subject": title}
            return pdf_exporter.generate_referral_letter_pdf(data, file_path)
        else:
            title = get_document_display_name(doc_type)
            return pdf_exporter.generate_generic_document_pdf(title, content, file_path)

    def _parse_soap_sections(self, content: str) -> Dict[str, str]:
        """Parse SOAP note content into sections.

        Args:
            content: Raw SOAP note text

        Returns:
            Dictionary with subjective, objective, assessment, and plan sections
        """
        sections = {
            'subjective': '',
            'objective': '',
            'assessment': '',
            'plan': ''
        }

        lines = content.split('\n')
        current_section = None
        section_content = []

        section_headers = {
            'subjective': ['subjective:', 's:'],
            'objective': ['objective:', 'o:'],
            'assessment': ['assessment:', 'a:'],
            'plan': ['plan:', 'p:']
        }

        for line in lines:
            line_lower = line.lower().strip()

            new_section = None
            for section, headers in section_headers.items():
                if any(line_lower.startswith(header) for header in headers):
                    new_section = section
                    break

            if new_section:
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content).strip()

                current_section = new_section
                section_content = []

                header_text = line.split(':', 1)
                if len(header_text) > 1 and header_text[1].strip():
                    section_content.append(header_text[1].strip())
            elif current_section:
                section_content.append(line)

        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content).strip()

        if not any(sections.values()):
            sections['subjective'] = content

        return sections

    def _offer_open_file(self, file_path: str) -> None:
        """Offer to open exported file."""
        if messagebox.askyesno("Open PDF", "Would you like to open the PDF now?"):
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(file_path, operation="open")
            if not success:
                logger.error(f"Failed to open PDF: {error}")
                messagebox.showerror("Error", f"Could not open PDF: {error}")

    def _offer_open_folder(self, directory: str) -> None:
        """Offer to open export folder."""
        if messagebox.askyesno("Open Folder", "Would you like to open the export folder?"):
            from utils.validation import open_file_or_folder_safely
            success, error = open_file_or_folder_safely(directory, operation="open")
            if not success:
                logger.error(f"Failed to open folder: {error}")
                messagebox.showerror("Error", f"Could not open folder: {error}")


__all__ = ["PDFExporterHandler"]
