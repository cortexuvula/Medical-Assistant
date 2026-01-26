"""
Compliance Results Dialog

Displays the results of clinical guidelines compliance analysis in a formatted dialog.
Shows compliance score, gaps, warnings, and recommendations with guideline citations.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT
from tkinter import messagebox, filedialog
import pyperclip
from typing import Dict, Any, Optional, List
import json
import os
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)


class ComplianceResultsDialog:
    """Dialog for displaying clinical guidelines compliance analysis results."""

    def __init__(self, parent):
        """Initialize the compliance results dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.analysis_text = ""
        self.result_text = None
        self.metadata = {}
        self.recording_id: Optional[int] = None
        self.dialog: Optional[tk.Toplevel] = None

    def show_results(
        self,
        analysis: str,
        metadata: Dict,
        recording_id: Optional[int] = None
    ):
        """Show the compliance analysis results.

        Args:
            analysis: The compliance analysis results text
            metadata: Additional metadata from the analysis including:
                - overall_score: float (0-1)
                - compliant_count: int
                - gap_count: int
                - warning_count: int
                - guidelines_checked: int
                - compliance_items: list of compliance item dicts
            recording_id: Optional recording ID to link analysis to
        """
        self.recording_id = recording_id
        self.analysis_text = analysis
        self.metadata = metadata or {}

        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        dialog = self.dialog
        dialog.title("Clinical Guidelines Compliance")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(950, 750)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.minsize(900, 700)
        dialog.transient(self.parent)

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # Grab focus
        dialog.deiconify()
        try:
            dialog.grab_set()
        except tk.TclError:
            pass

        # Main container
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=BOTH, expand=True)

        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 15))

        title_label = ttk.Label(
            header_frame,
            text="Clinical Guidelines Compliance Analysis",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(side=LEFT)

        # Score badge
        score = self.metadata.get('overall_score', 0.0)
        score_pct = int(score * 100)
        score_color = self._get_score_color(score_pct)
        score_label = ttk.Label(
            header_frame,
            text=f"{score_pct}%",
            font=("Segoe UI", 18, "bold"),
            foreground=score_color
        )
        score_label.pack(side=RIGHT, padx=10)

        score_text_label = ttk.Label(
            header_frame,
            text="Compliance Score:",
            font=("Segoe UI", 11)
        )
        score_text_label.pack(side=RIGHT)

        # Summary bar
        summary_frame = ttk.Frame(main_frame)
        summary_frame.pack(fill=X, pady=(0, 15))

        # Guidelines checked
        guidelines_checked = self.metadata.get('guidelines_checked', 0)
        ttk.Label(
            summary_frame,
            text=f"Guidelines Checked: {guidelines_checked}",
            font=("Segoe UI", 10)
        ).pack(side=LEFT, padx=(0, 20))

        # Compliant count
        compliant_count = self.metadata.get('compliant_count', 0)
        if compliant_count > 0:
            ttk.Label(
                summary_frame,
                text=f"✓ Compliant: {compliant_count}",
                font=("Segoe UI", 10),
                foreground="green"
            ).pack(side=LEFT, padx=(0, 20))

        # Gap count
        gap_count = self.metadata.get('gap_count', 0)
        if gap_count > 0:
            ttk.Label(
                summary_frame,
                text=f"✗ Gaps: {gap_count}",
                font=("Segoe UI", 10, "bold"),
                foreground="red"
            ).pack(side=LEFT, padx=(0, 20))

        # Warning count
        warning_count = self.metadata.get('warning_count', 0)
        if warning_count > 0:
            ttk.Label(
                summary_frame,
                text=f"⚠ Warnings: {warning_count}",
                font=("Segoe UI", 10),
                foreground="orange"
            ).pack(side=LEFT)

        # Score progress bar
        score_bar_frame = ttk.Frame(main_frame)
        score_bar_frame.pack(fill=X, pady=(0, 15))

        score_bar = ttk.Progressbar(
            score_bar_frame,
            mode='determinate',
            value=score_pct,
            bootstyle=self._get_progressbar_style(score_pct)
        )
        score_bar.pack(fill=X)

        # Results text area
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 15))

        # Create text widget with scrollbar
        self.result_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10
        )
        self.result_text.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=self.result_text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.result_text.config(yscrollcommand=scrollbar.set)

        # Insert and format the analysis
        self._display_formatted_analysis(self.analysis_text)

        # Make text read-only
        self.result_text.config(state=tk.DISABLED)

        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X)

        # Action buttons
        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=self._copy_to_clipboard,
            bootstyle="info",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Export to PDF",
            command=self._export_to_pdf,
            bootstyle="warning",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Add to SOAP Note",
            command=lambda: self._add_to_document("soap"),
            bootstyle="success",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Upload Guidelines",
            command=self._open_guidelines_upload,
            bootstyle="primary",
            width=18
        ).pack(side=LEFT)

        ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
            width=15
        ).pack(side=RIGHT)

        # Focus on the dialog
        dialog.focus_set()

    def _get_score_color(self, score_pct: int) -> str:
        """Get color based on compliance score percentage."""
        if score_pct >= 80:
            return "green"
        elif score_pct >= 60:
            return "orange"
        else:
            return "red"

    def _get_progressbar_style(self, score_pct: int) -> str:
        """Get progressbar style based on compliance score percentage."""
        if score_pct >= 80:
            return "success"
        elif score_pct >= 60:
            return "warning"
        else:
            return "danger"

    def _display_formatted_analysis(self, text: str):
        """Display formatted compliance analysis in the text widget.

        Args:
            text: The compliance analysis text to display
        """
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete("1.0", tk.END)

        # Configure tags for formatting
        self.result_text.tag_configure("heading", font=("Segoe UI", 12, "bold"), spacing3=5)
        self.result_text.tag_configure("subheading", font=("Segoe UI", 11, "bold"), spacing3=3)

        # Status tags
        self.result_text.tag_configure(
            "compliant",
            foreground="green",
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "gap",
            foreground="white",
            background="#dc3545",  # Red
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "warning",
            foreground="black",
            background="#ffc107",  # Yellow
            font=("Segoe UI", 11, "bold")
        )

        # Evidence level tags
        self.result_text.tag_configure(
            "class_i",
            foreground="white",
            background="#28a745",  # Green
            font=("Segoe UI", 10, "bold")
        )
        self.result_text.tag_configure(
            "class_iia",
            foreground="black",
            background="#17a2b8",  # Teal
            font=("Segoe UI", 10, "bold")
        )
        self.result_text.tag_configure(
            "class_iib",
            foreground="black",
            background="#ffc107",  # Yellow
            font=("Segoe UI", 10)
        )
        self.result_text.tag_configure(
            "class_iii",
            foreground="white",
            background="#dc3545",  # Red
            font=("Segoe UI", 10, "bold")
        )

        self.result_text.tag_configure(
            "level_a",
            foreground="white",
            background="#28a745",
            font=("Segoe UI", 9, "bold")
        )
        self.result_text.tag_configure(
            "level_b",
            foreground="black",
            background="#17a2b8",
            font=("Segoe UI", 9)
        )
        self.result_text.tag_configure(
            "level_c",
            foreground="black",
            background="#ffc107",
            font=("Segoe UI", 9)
        )

        # Guideline citation tag
        self.result_text.tag_configure(
            "guideline_source",
            font=("Segoe UI", 10, "italic"),
            foreground="#0066cc"
        )

        # Recommendation tag
        self.result_text.tag_configure(
            "recommendation",
            font=("Segoe UI", 10),
            foreground="#2d6a4f",
            lmargin1=15,
            lmargin2=30
        )

        # Detail tag
        self.result_text.tag_configure(
            "detail",
            foreground="gray",
            font=("Segoe UI", 10),
            lmargin1=15
        )

        # Parse and format the text
        lines = text.split('\n')

        for line in lines:
            line_lower = line.lower()
            stripped_line = line.strip()

            # Check for status markers
            if stripped_line.startswith('[COMPLIANT]'):
                self.result_text.insert(tk.END, "[COMPLIANT] ", "compliant")
                rest = stripped_line[11:].strip()
                self.result_text.insert(tk.END, rest + '\n')
                continue
            elif stripped_line.startswith('[GAP]'):
                self.result_text.insert(tk.END, "[GAP] ", "gap")
                rest = stripped_line[5:].strip()
                self.result_text.insert(tk.END, rest + '\n')
                continue
            elif stripped_line.startswith('[WARNING]'):
                self.result_text.insert(tk.END, "[WARNING] ", "warning")
                rest = stripped_line[9:].strip()
                self.result_text.insert(tk.END, rest + '\n')
                continue

            # Check for section headings
            if line.startswith('##') or line.startswith('#'):
                clean_line = line.lstrip('#').strip()
                self.result_text.insert(tk.END, clean_line + '\n', "heading")
                continue

            if line.upper() == line and line.endswith(':') and stripped_line:
                # All caps heading
                self.result_text.insert(tk.END, line + '\n', "heading")
                continue

            if any(heading in line_lower for heading in ['compliance summary', 'detailed findings', 'improvement']):
                self.result_text.insert(tk.END, line + '\n', "subheading")
                continue

            # Check for evidence class markers
            if 'class i,' in line_lower or 'class i ' in line_lower:
                if 'class iii' in line_lower:
                    self.result_text.insert(tk.END, line + '\n', "class_iii")
                elif 'class iib' in line_lower:
                    self.result_text.insert(tk.END, line + '\n', "class_iib")
                elif 'class iia' in line_lower:
                    self.result_text.insert(tk.END, line + '\n', "class_iia")
                else:
                    self.result_text.insert(tk.END, line + '\n', "class_i")
                continue

            # Check for level markers
            if 'level a' in line_lower:
                self.result_text.insert(tk.END, line + '\n', "level_a")
                continue
            elif 'level b' in line_lower:
                self.result_text.insert(tk.END, line + '\n', "level_b")
                continue
            elif 'level c' in line_lower:
                self.result_text.insert(tk.END, line + '\n', "level_c")
                continue

            # Check for guideline sources
            if any(source in line for source in ['AHA', 'ACC', 'ADA', 'GOLD', 'NICE', 'IDSA', 'CHEST']):
                if 'per ' in line_lower or 'source:' in line_lower or 'guideline' in line_lower:
                    self.result_text.insert(tk.END, line + '\n', "guideline_source")
                    continue

            # Check for recommendations
            if 'recommendation:' in line_lower:
                self.result_text.insert(tk.END, line + '\n', "recommendation")
                continue

            # Check for notes/details
            if line.startswith('  -') or line.startswith('  •') or 'note:' in line_lower:
                self.result_text.insert(tk.END, line + '\n', "detail")
                continue

            # Default formatting
            self.result_text.insert(tk.END, line + '\n')

        self.result_text.config(state=tk.DISABLED)

    def _copy_to_clipboard(self):
        """Copy the analysis to clipboard."""
        try:
            pyperclip.copy(self.analysis_text)
            messagebox.showinfo(
                "Copied",
                "Compliance analysis copied to clipboard!",
                parent=self.parent
            )
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Copying compliance analysis to clipboard",
                exception=e,
                input_summary=f"text_length={len(self.analysis_text)}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Error",
                ctx.user_message,
                parent=self.parent
            )

    def _add_to_document(self, doc_type: str):
        """Add the analysis to a document.

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

            # Add analysis with separator
            if current_content:
                new_content = f"{current_content}\n\n--- Clinical Guidelines Compliance ---\n\n{self.analysis_text}"
            else:
                new_content = f"--- Clinical Guidelines Compliance ---\n\n{self.analysis_text}"

            # Update the text widget
            target_widget.delete("1.0", tk.END)
            target_widget.insert("1.0", new_content)

            # Switch to the appropriate tab
            if doc_type == "soap":
                self.parent.notebook.select(1)  # SOAP tab

            messagebox.showinfo(
                "Added",
                f"Compliance analysis added to {doc_name}!",
                parent=self.parent
            )

        except Exception as e:
            ctx = ErrorContext.capture(
                operation=f"Adding compliance analysis to {doc_type}",
                exception=e,
                input_summary=f"doc_type={doc_type}"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Error",
                ctx.user_message,
                parent=self.parent
            )

    def _export_to_pdf(self):
        """Export the compliance analysis to PDF."""
        try:
            from utils.pdf_exporter import PDFExporter

            # Get default filename
            default_filename = "compliance_report.pdf"

            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.parent,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Compliance Report as PDF"
            )

            if not file_path:
                return

            # Create PDF exporter
            pdf_exporter = PDFExporter()

            # Prepare compliance data for PDF
            compliance_data = {
                "title": "Clinical Guidelines Compliance Report",
                "score": self.metadata.get('overall_score', 0.0),
                "score_percent": int(self.metadata.get('overall_score', 0.0) * 100),
                "guidelines_checked": self.metadata.get('guidelines_checked', 0),
                "compliant_count": self.metadata.get('compliant_count', 0),
                "gap_count": self.metadata.get('gap_count', 0),
                "warning_count": self.metadata.get('warning_count', 0),
                "analysis_text": self.analysis_text,
                "items": self.metadata.get('compliance_items', [])
            }

            # Try to use specialized compliance PDF method if available
            if hasattr(pdf_exporter, 'generate_compliance_report_pdf'):
                success = pdf_exporter.generate_compliance_report_pdf(
                    compliance_data,
                    file_path
                )
            else:
                # Fallback to generic text PDF
                success = pdf_exporter.generate_text_pdf(
                    self.analysis_text,
                    file_path,
                    title="Clinical Guidelines Compliance Report"
                )

            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Compliance report exported to:\n{file_path}",
                    parent=self.parent
                )

                # Optionally open the PDF
                if messagebox.askyesno(
                    "Open PDF",
                    "Would you like to open the PDF now?",
                    parent=self.parent
                ):
                    import subprocess
                    import platform

                    if platform.system() == 'Darwin':       # macOS
                        subprocess.call(('open', file_path))
                    elif platform.system() == 'Windows':    # Windows
                        os.startfile(file_path)
                    else:                                   # Linux
                        subprocess.call(('xdg-open', file_path))
            else:
                messagebox.showerror(
                    "Export Failed",
                    "Failed to export PDF. Check logs for details.",
                    parent=self.parent
                )

        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Exporting compliance analysis to PDF",
                exception=e,
                input_summary="compliance_report"
            )
            logger.error(ctx.to_log_string())
            messagebox.showerror(
                "Export Error",
                ctx.user_message,
                parent=self.parent
            )

    def _open_guidelines_upload(self):
        """Open the guidelines upload dialog."""
        try:
            from ui.dialogs.guidelines_upload_dialog import GuidelinesUploadDialog

            def on_upload(files: list, options: dict):
                """Handle upload start."""
                logger.info(f"Uploading {len(files)} guideline(s)")
                # Would connect to guidelines upload manager here

            dialog = GuidelinesUploadDialog(self.parent, on_upload=on_upload)
            dialog.wait_window()

        except ImportError:
            messagebox.showinfo(
                "Upload Guidelines",
                "Use the 'Upload Guidelines' button in the Clinical Guidelines tab "
                "to add clinical guidelines to your database.",
                parent=self.parent
            )
        except Exception as e:
            logger.error(f"Error opening guidelines upload: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to open guidelines upload: {e}",
                parent=self.parent
            )
