"""
Base Results Dialog

This module provides an abstract base class for all agent results dialogs
(Medication, Diagnostic, Workflow, Data Extraction). It encapsulates common
patterns for:
- Dialog window creation and layout
- Results text display with formatting
- Action buttons (Copy, Export, Add to Document, Close)
- Clipboard and PDF export functionality

Usage:
    class MyResultsDialog(BaseResultsDialog):
        def _get_dialog_title(self) -> str:
            return "My Results"

        def _format_results(self, results: Any) -> str:
            return str(results)

        def _get_pdf_filename(self) -> str:
            return "my_results.pdf"
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT
from tkinter import messagebox, filedialog
import pyperclip
import os
import platform
import subprocess
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List, Tuple

from ui.scaling_utils import ui_scaler
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext


class BaseResultsDialog(ABC):
    """Abstract base class for agent results dialogs.

    This class provides common functionality for displaying AI agent results:
    - Dialog window with customizable title and size
    - Formatted text display area with scrollbar
    - Action buttons: Copy, Export PDF, Add to Document, Close
    - Text formatting with configurable tags
    - Clipboard and PDF export support

    Subclasses must implement:
    - _get_dialog_title(): Return the dialog window title
    - _format_results(): Format the results for display
    - _get_pdf_filename(): Return default PDF filename

    Optional overrides:
    - _get_type_titles(): Return mapping of result types to display titles
    - _configure_text_tags(): Configure additional text formatting tags
    - _display_formatted_results(): Custom result display logic
    - _export_to_pdf(): Custom PDF export logic

    Attributes:
        parent: Parent window
        dialog: The Toplevel dialog window (created on show)
        result_text: Text widget for displaying results
        results: The raw results data
        results_text: The formatted results text
        result_type: Type of results being displayed
        source: Source of the results
        metadata: Additional metadata about the results
    """

    def __init__(self, parent):
        """Initialize the base results dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.dialog: Optional[tk.Toplevel] = None
        self.result_text: Optional[tk.Text] = None
        self.results: Any = None
        self.results_text: str = ""
        self.result_type: str = ""
        self.source: str = ""
        self.metadata: Dict[str, Any] = {}
        self.logger = get_logger(self.__class__.__module__)
        self._status_label: Optional[ttk.Label] = None
        self._status_after_id: Optional[str] = None

    @abstractmethod
    def _get_dialog_title(self) -> str:
        """Return the dialog window title.

        Returns:
            Title string for the dialog window
        """
        pass

    @abstractmethod
    def _format_results(self, results: Any, result_type: str) -> str:
        """Format the results for display.

        Args:
            results: Raw results data
            result_type: Type of results

        Returns:
            Formatted text string for display
        """
        pass

    @abstractmethod
    def _get_pdf_filename(self) -> str:
        """Return the default PDF filename.

        Returns:
            Default filename for PDF export
        """
        pass

    def _get_dialog_size(self) -> Tuple[int, int]:
        """Return the dialog window size.

        Override this to customize dialog dimensions.

        Returns:
            Tuple of (width, height) in pixels
        """
        return (950, 750)

    def _get_min_size(self) -> Tuple[int, int]:
        """Return the minimum dialog window size.

        Override this to customize minimum dimensions.

        Returns:
            Tuple of (min_width, min_height) in pixels
        """
        return (900, 700)

    def _get_type_titles(self) -> Dict[str, str]:
        """Return mapping of result types to display titles.

        Override this to provide custom type-to-title mapping.

        Returns:
            Dictionary mapping result_type to display title
        """
        return {}

    def show_results(self, results: Any, result_type: str, source: str,
                     metadata: Optional[Dict[str, Any]] = None) -> None:
        """Show the results in a dialog window.

        Args:
            results: The results data (dict or string)
            result_type: Type of results being displayed
            source: Source of the results
            metadata: Optional additional metadata
        """
        # Store data
        self.results = results if isinstance(results, dict) else {"results": results}
        self.result_type = result_type
        self.source = source
        self.metadata = metadata or {}

        # Format results
        if isinstance(results, dict):
            self.results_text = self._format_results(results, result_type)
        else:
            self.results_text = str(results)

        # Create dialog window
        self._create_dialog()

        # Create UI components
        self._create_header()
        self._create_text_area()
        self._create_buttons()

        # Display results
        self._display_formatted_results(self.results_text)

        # Focus on dialog
        self.dialog.focus_set()

    def _create_dialog(self) -> None:
        """Create the dialog window."""
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title(self._get_dialog_title())

        # Set size
        width, height = self._get_dialog_size()
        dialog_width, dialog_height = ui_scaler.get_dialog_size(width, height)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")

        # Set minimum size
        min_width, min_height = self._get_min_size()
        self.dialog.minsize(min_width, min_height)

        # Make dialog modal
        self.dialog.transient(self.parent)

        # Center dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Create main frame
        self.main_frame = ttk.Frame(self.dialog, padding=20)
        self.main_frame.pack(fill=BOTH, expand=True)

    def _create_header(self) -> None:
        """Create the dialog header with title and metadata."""
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=X, pady=(0, 15))

        # Title
        type_titles = self._get_type_titles()
        title = type_titles.get(self.result_type, self._get_dialog_title())

        title_label = ttk.Label(
            header_frame,
            text=title,
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(side=LEFT)

        # Metadata info
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side=RIGHT)

        if self.source:
            ttk.Label(
                info_frame,
                text=f"Source: {self.source}",
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 15))

        # Add custom metadata display
        self._add_metadata_display(info_frame)

    def _add_metadata_display(self, info_frame: ttk.Frame) -> None:
        """Add custom metadata display to the header.

        Override this to display custom metadata in the header.

        Args:
            info_frame: Frame to add metadata widgets to
        """
        pass

    def _create_text_area(self) -> None:
        """Create the text display area with scrollbar."""
        text_frame = ttk.Frame(self.main_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 15))

        # Create text widget
        self.result_text = tk.Text(
            text_frame,
            wrap=WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10
        )
        self.result_text.pack(side=LEFT, fill=BOTH, expand=True)

        # Create scrollbar
        scrollbar = ttk.Scrollbar(
            text_frame,
            orient=VERTICAL,
            command=self.result_text.yview
        )
        scrollbar.pack(side=RIGHT, fill=Y)
        self.result_text.config(yscrollcommand=scrollbar.set)

        # Configure text tags
        self._configure_text_tags()

    def _configure_text_tags(self) -> None:
        """Configure text formatting tags.

        Override this to add custom text tags. Call super() to keep default tags.
        """
        self.result_text.tag_configure("heading", font=("Segoe UI", 12, "bold"), spacing3=5)
        self.result_text.tag_configure("subheading", font=("Segoe UI", 11, "bold"), spacing3=3)
        self.result_text.tag_configure("warning", foreground="orange", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("error", foreground="red", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("success", foreground="green", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("item", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("detail", foreground="gray", font=("Segoe UI", 10))
        self.result_text.tag_configure("code", font=("Consolas", 10), background="#f0f0f0")

    def _display_formatted_results(self, text: str) -> None:
        """Display formatted results in the text widget.

        Override this for custom formatting logic.

        Args:
            text: Formatted results text
        """
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        # Parse and format lines
        lines = text.split('\n')
        for line in lines:
            self._format_line(line)

        self.result_text.config(state=tk.DISABLED)

    def _format_line(self, line: str) -> None:
        """Format and insert a single line into the text widget.

        Override this for custom line formatting.

        Args:
            line: Line of text to format and insert
        """
        # Check for heading (ALL CAPS ending with :)
        if line.upper() == line and line.endswith(':') and line.strip():
            self.result_text.insert(tk.END, line + '\n', "heading")
        # Warning indicators
        elif line.startswith('⚠') or line.startswith('[WARNING]'):
            self.result_text.insert(tk.END, line + '\n', "warning")
        # Error indicators
        elif line.startswith('❌') or line.startswith('[ERROR]'):
            self.result_text.insert(tk.END, line + '\n', "error")
        # Success indicators
        elif line.startswith('✓') or line.startswith('[OK]'):
            self.result_text.insert(tk.END, line + '\n', "success")
        # Bullet points
        elif line.startswith('•') or line.startswith('-'):
            parts = line.split(' ', 1)
            self.result_text.insert(tk.END, parts[0] + ' ')
            if len(parts) > 1:
                self.result_text.insert(tk.END, parts[1], "item")
            self.result_text.insert(tk.END, '\n')
        # Indented details
        elif line.startswith('  '):
            self.result_text.insert(tk.END, line + '\n', "detail")
        # Normal text
        else:
            self.result_text.insert(tk.END, line + '\n')

    def _create_buttons(self) -> None:
        """Create the action buttons."""
        button_frame = ttk.Frame(self.main_frame)
        button_frame.pack(fill=X)

        # Copy button
        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=self._copy_to_clipboard,
            bootstyle="info",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        # Export PDF button
        ttk.Button(
            button_frame,
            text="Export to PDF",
            command=self._export_to_pdf,
            bootstyle="warning",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        # Add to SOAP button
        ttk.Button(
            button_frame,
            text="Add to SOAP Note",
            command=lambda: self._add_to_document("soap"),
            bootstyle="success",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        # Add to Letter button
        ttk.Button(
            button_frame,
            text="Add to Letter",
            command=lambda: self._add_to_document("letter"),
            bootstyle="primary",
            width=18
        ).pack(side=LEFT)

        # Status label for brief feedback messages
        self._status_label = ttk.Label(
            button_frame,
            text="",
            font=("Segoe UI", 10),
            foreground="green"
        )
        self._status_label.pack(side=LEFT, padx=(15, 0))

        # Close button
        ttk.Button(
            button_frame,
            text="Close",
            command=self.dialog.destroy,
            width=15
        ).pack(side=RIGHT)

    def _show_brief_feedback(self, message: str, duration_ms: int = 2000, error: bool = False) -> None:
        """Show a brief feedback message that auto-dismisses.

        Args:
            message: The message to display
            duration_ms: How long to show the message (default: 2 seconds)
            error: If True, show in red color for errors
        """
        if not self._status_label:
            return

        # Cancel any pending clear
        if self._status_after_id:
            try:
                self.dialog.after_cancel(self._status_after_id)
            except (tk.TclError, AttributeError):
                pass

        # Show the message
        color = "red" if error else "green"
        self._status_label.config(text=message, foreground=color)

        # Schedule clear
        def clear_message():
            try:
                if self._status_label and self._status_label.winfo_exists():
                    self._status_label.config(text="")
            except (tk.TclError, AttributeError):
                pass

        self._status_after_id = self.dialog.after(duration_ms, clear_message)

    def _copy_to_clipboard(self) -> None:
        """Copy the results to clipboard."""
        try:
            pyperclip.copy(self.results_text)
            self._show_brief_feedback("Copied to clipboard!")
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Copying to clipboard",
                exception=e,
                input_summary=f"text_length={len(self.results_text)}"
            )
            self.logger.error(ctx.to_log_string())
            self._show_brief_feedback("Copy failed", error=True)

    def _add_to_document(self, doc_type: str) -> None:
        """Add the results to a document (SOAP note or letter).

        Args:
            doc_type: Type of document ('soap' or 'letter')
        """
        try:
            if doc_type == "soap":
                target_widget = self.parent.soap_text
                doc_name = "SOAP Note"
            else:
                target_widget = self.parent.letter_text
                doc_name = "Letter"

            # Get current content
            current_content = target_widget.get("1.0", "end").strip()

            # Create section header
            section_title = self._get_dialog_title().replace(" Results", " Analysis")

            # Add results with separator
            if current_content:
                new_content = f"{current_content}\n\n--- {section_title} ---\n\n{self.results_text}"
            else:
                new_content = f"--- {section_title} ---\n\n{self.results_text}"

            # Update the text widget
            target_widget.delete("1.0", tk.END)
            target_widget.insert("1.0", new_content)

            # Switch to the appropriate tab
            if doc_type == "soap":
                self.parent.notebook.select(1)  # SOAP tab
            else:
                self.parent.notebook.select(3)  # Letter tab

            messagebox.showinfo(
                "Added",
                f"Results added to {doc_name}!",
                parent=self.dialog
            )

        except AttributeError as e:
            ctx = ErrorContext.capture(
                operation=f"Adding to {doc_type}",
                exception=e,
                input_summary="Parent missing expected document widgets"
            )
            self.logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Error",
                "Could not access document. Please try again.",
                parent=self.dialog
            )
        except Exception as e:
            ctx = ErrorContext.capture(
                operation=f"Adding to {doc_type}",
                exception=e,
                input_summary=f"doc_type={doc_type}"
            )
            self.logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Error",
                ctx.user_message,
                parent=self.dialog
            )

    def _export_to_pdf(self) -> None:
        """Export the results to PDF.

        Override this for custom PDF export logic.
        """
        try:
            from utils.pdf_exporter import PDFExporter

            # Get save location
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=self._get_pdf_filename(),
                title="Save Report as PDF"
            )

            if not file_path:
                return

            # Create PDF exporter
            pdf_exporter = PDFExporter()

            # Prepare data for PDF
            report_data = self._prepare_pdf_data()

            # Generate PDF
            success = self._generate_pdf(pdf_exporter, report_data, file_path)

            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Report exported to:\n{file_path}",
                    parent=self.dialog
                )

                # Offer to open the PDF
                if messagebox.askyesno(
                    "Open PDF",
                    "Would you like to open the PDF now?",
                    parent=self.dialog
                ):
                    self._open_file(file_path)
            else:
                messagebox.showerror(
                    "Export Failed",
                    "Failed to export PDF. Check logs for details.",
                    parent=self.dialog
                )

        except ImportError as e:
            ctx = ErrorContext.capture(
                operation="PDF export",
                exception=e,
                input_summary="PDF exporter module not available"
            )
            self.logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Export Error",
                "PDF export is not available. Please install required dependencies.",
                parent=self.dialog
            )
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="PDF export",
                exception=e,
                input_summary=f"result_type={self.result_type}"
            )
            self.logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Export Error",
                ctx.user_message,
                parent=self.dialog
            )

    def _prepare_pdf_data(self) -> Dict[str, Any]:
        """Prepare data for PDF export.

        Override this for custom PDF data preparation.

        Returns:
            Dictionary with data for PDF generation
        """
        data = {
            "title": self._get_dialog_title(),
            "result_type": self.result_type,
            "source": self.source,
            "content": self.results_text,
            **self.metadata
        }
        if isinstance(self.results, dict):
            data.update(self.results)
        return data

    def _generate_pdf(self, pdf_exporter, report_data: Dict[str, Any],
                      file_path: str) -> bool:
        """Generate the PDF file.

        Override this to use a specific PDF generation method.

        Args:
            pdf_exporter: PDFExporter instance
            report_data: Data for the report
            file_path: Path to save the PDF

        Returns:
            True if successful, False otherwise
        """
        # Default implementation tries generic report generation
        if hasattr(pdf_exporter, 'generate_report_pdf'):
            return pdf_exporter.generate_report_pdf(report_data, file_path)

        # Fallback: generate simple text PDF
        return self._generate_simple_pdf(file_path)

    def _generate_simple_pdf(self, file_path: str) -> bool:
        """Generate a simple text-based PDF.

        Args:
            file_path: Path to save the PDF

        Returns:
            True if successful, False otherwise
        """
        try:
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas

            c = canvas.Canvas(file_path, pagesize=letter)
            width, height = letter

            # Title
            c.setFont("Helvetica-Bold", 16)
            c.drawString(72, height - 72, self._get_dialog_title())

            # Content
            c.setFont("Helvetica", 10)
            y = height - 108

            for line in self.results_text.split('\n'):
                if y < 72:
                    c.showPage()
                    c.setFont("Helvetica", 10)
                    y = height - 72
                c.drawString(72, y, line[:100])  # Truncate long lines
                y -= 14

            c.save()
            return True
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generating simple PDF",
                exception=e,
                input_summary=f"file_path={file_path}"
            )
            self.logger.error(ctx.to_log_string())
            return False

    def _open_file(self, file_path: str) -> None:
        """Open a file with the default application.

        Args:
            file_path: Path to the file to open
        """
        try:
            if platform.system() == 'Darwin':
                subprocess.call(('open', file_path))
            elif platform.system() == 'Windows':
                os.startfile(file_path)
            else:
                subprocess.call(('xdg-open', file_path))
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Opening file",
                exception=e,
                input_summary=f"file_path={file_path}, platform={platform.system()}"
            )
            self.logger.error(ctx.to_log_string())
