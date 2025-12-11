"""
Document Export Controller Module

Handles document export operations including PDF export, batch export,
printing, and SOAP section parsing.

This controller extracts export logic from the main App class to
improve maintainability and separation of concerns.
"""

import logging
import os
import tempfile
import tkinter as tk
from tkinter import messagebox, filedialog
from datetime import datetime
from typing import TYPE_CHECKING, Dict, List, Tuple

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class DocumentExportController:
    """Controller for managing document export operations.

    This class coordinates:
    - PDF export for individual documents
    - Batch PDF export for all documents
    - Document printing via system dialog
    - SOAP section parsing for structured export
    - Save text and audio files
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the document export controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def save_text(self) -> None:
        """Save transcript text and optionally audio using FileManager."""
        text = self.app.transcript_text.get("1.0", tk.END).strip()
        if not text:
            messagebox.showwarning("Save Text", "No text to save.")
            return

        # Save text file
        file_path = self.app.file_manager.save_text_file(text, "Save Transcript")

        if file_path and self.app.audio_segments:
            # Also save audio if available
            audio_data = self.app.audio_handler.combine_audio_segments(self.app.audio_segments)
            if audio_data:
                saved_audio_path = self.app.file_manager.save_audio_file(audio_data, "Save Audio")
                if saved_audio_path:
                    self.app.status_manager.success("Text and audio saved successfully")
                else:
                    self.app.status_manager.warning("Text saved, but audio save was cancelled")
        elif file_path:
            self.app.status_manager.success("Text saved successfully")

    def export_as_pdf(self) -> None:
        """Export current document as PDF."""
        try:
            from utils.pdf_exporter import PDFExporter

            # Get the currently active tab
            selected_tab = self.app.notebook.index('current')

            # Determine document type and get content
            doc_types = ['transcript', 'soap_note', 'referral', 'letter', 'chat']
            if selected_tab >= len(doc_types):
                messagebox.showwarning("Export Error", "Invalid document tab selected.")
                return

            doc_type = doc_types[selected_tab]

            # Get the content from the appropriate text widget
            text_widgets = self._get_text_widgets()
            content = text_widgets[selected_tab].get("1.0", tk.END).strip()

            if not content:
                messagebox.showwarning("Export Error", f"No {doc_type.replace('_', ' ')} content to export.")
                return

            # Generate default filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"{doc_type}_{timestamp}.pdf"

            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=default_filename,
                title=f"Export {doc_type.replace('_', ' ').title()} as PDF"
            )

            if not file_path:
                return

            # Create PDF exporter
            pdf_exporter = PDFExporter()

            # Export based on document type
            success = self._export_document_as_pdf(pdf_exporter, doc_type, content, file_path)

            if success:
                self.app.status_manager.success(f"{doc_type.replace('_', ' ').title()} exported to PDF successfully")

                # Ask if user wants to open the PDF
                if messagebox.askyesno("Open PDF", "Would you like to open the PDF now?"):
                    from utils.validation import open_file_or_folder_safely
                    open_success, error = open_file_or_folder_safely(file_path, operation="open")
                    if not open_success:
                        logging.error(f"Failed to open PDF: {error}")
                        messagebox.showerror("Error", f"Could not open PDF: {error}")
            else:
                messagebox.showerror("Export Failed", "Failed to export PDF. Check logs for details.")

        except Exception as e:
            logging.error(f"Error exporting to PDF: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export PDF: {str(e)}")

    def export_all_as_pdf(self) -> None:
        """Export all documents as separate PDFs."""
        try:
            from utils.pdf_exporter import PDFExporter

            # Ask user for directory
            directory = filedialog.askdirectory(title="Select Directory for PDF Export")
            if not directory:
                return

            pdf_exporter = PDFExporter()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            exported_count = 0

            # Export each document
            documents = [
                ('transcript', self.app.transcript_text, 'Transcript'),
                ('soap_note', self.app.soap_text, 'SOAP Note'),
                ('referral', self.app.referral_text, 'Referral'),
                ('letter', self.app.letter_text, 'Letter')
            ]

            for doc_type, widget, title in documents:
                content = widget.get("1.0", tk.END).strip()
                if content:
                    file_path = os.path.join(directory, f"{doc_type}_{timestamp}.pdf")
                    success = self._export_document_as_pdf(pdf_exporter, doc_type, content, file_path)
                    if success:
                        exported_count += 1

            if exported_count > 0:
                self.app.status_manager.success(f"Exported {exported_count} documents to PDF")

                # Ask if user wants to open the folder
                if messagebox.askyesno("Open Folder", "Would you like to open the export folder?"):
                    from utils.validation import open_file_or_folder_safely
                    success, error = open_file_or_folder_safely(directory, operation="open")
                    if not success:
                        logging.error(f"Failed to open folder: {error}")
                        messagebox.showerror("Error", f"Could not open folder: {error}")
            else:
                messagebox.showinfo("Export Info", "No documents with content to export.")

        except Exception as e:
            logging.error(f"Error exporting all to PDF: {str(e)}")
            messagebox.showerror("Export Error", f"Failed to export PDFs: {str(e)}")

    def print_document(self) -> None:
        """Print current document."""
        try:
            from utils.pdf_exporter import PDFExporter
            from utils.validation import open_file_or_folder_safely

            # Get the currently active tab
            selected_tab = self.app.notebook.index('current')

            # Get content
            text_widgets = self._get_text_widgets()
            content = text_widgets[selected_tab].get("1.0", tk.END).strip()

            if not content:
                messagebox.showwarning("Print Error", "No content to print.")
                return

            # Create temporary PDF
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name

            # Generate PDF
            pdf_exporter = PDFExporter()
            doc_types = ['transcript', 'soap_note', 'referral', 'letter', 'chat']
            doc_type = doc_types[selected_tab]

            success = self._export_document_as_pdf(pdf_exporter, doc_type, content, tmp_path)

            if success:
                # Open system print dialog using safe path handling
                print_success, error = open_file_or_folder_safely(tmp_path, operation="print")

                if print_success:
                    self.app.status_manager.info("Document sent to printer")
                else:
                    logging.error(f"Failed to print: {error}")
                    messagebox.showerror("Print Error", f"Failed to print document: {error}")

                # Clean up temp file after a delay
                self.app.after(5000, lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
            else:
                messagebox.showerror("Print Error", "Failed to prepare document for printing.")
                if os.path.exists(tmp_path):
                    os.unlink(tmp_path)

        except Exception as e:
            logging.error(f"Error printing document: {str(e)}")
            messagebox.showerror("Print Error", f"Failed to print: {str(e)}")

    def _export_document_as_pdf(self, pdf_exporter, doc_type: str, content: str, file_path: str) -> bool:
        """Export a document to PDF based on its type.

        Args:
            pdf_exporter: PDFExporter instance
            doc_type: Type of document (transcript, soap_note, referral, letter, chat)
            content: Document content
            file_path: Output file path

        Returns:
            True if export was successful
        """
        if doc_type == 'soap_note':
            soap_data = self.parse_soap_sections(content)
            return pdf_exporter.generate_soap_note_pdf(soap_data, file_path)
        elif doc_type in ['referral', 'letter']:
            title = 'Medical Referral' if doc_type == 'referral' else 'Medical Correspondence'
            data = {"body": content, "subject": title}
            return pdf_exporter.generate_referral_letter_pdf(data, file_path)
        else:
            # Generic document (transcript, chat)
            title = doc_type.replace('_', ' ').title()
            return pdf_exporter.generate_generic_document_pdf(title, content, file_path)

    def _get_text_widgets(self) -> List[tk.Widget]:
        """Get list of text widgets in tab order.

        Returns:
            List of text widgets
        """
        return [
            self.app.transcript_text,
            self.app.soap_text,
            self.app.referral_text,
            self.app.letter_text,
            self.app.chat_text
        ]

    def parse_soap_sections(self, content: str) -> Dict[str, str]:
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

        # Simple parsing - look for section headers
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

            # Check if this line is a section header
            new_section = None
            for section, headers in section_headers.items():
                if any(line_lower.startswith(header) for header in headers):
                    new_section = section
                    break

            if new_section:
                # Save previous section content
                if current_section and section_content:
                    sections[current_section] = '\n'.join(section_content).strip()

                # Start new section
                current_section = new_section
                section_content = []

                # Add content after the header on the same line
                header_text = line.split(':', 1)
                if len(header_text) > 1 and header_text[1].strip():
                    section_content.append(header_text[1].strip())
            elif current_section:
                # Add line to current section
                section_content.append(line)

        # Save last section
        if current_section and section_content:
            sections[current_section] = '\n'.join(section_content).strip()

        # If no sections found, put all content in subjective
        if not any(sections.values()):
            sections['subjective'] = content

        return sections
