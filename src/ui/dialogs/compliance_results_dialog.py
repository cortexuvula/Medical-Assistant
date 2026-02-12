"""
Compliance Results Dialog

Displays the results of clinical guidelines compliance analysis in a
condition-organized view with disclaimer banner, verification indicators,
and collapsible condition sections.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT, TOP, BOTTOM
from tkinter import messagebox, filedialog
import pyperclip
from typing import Dict, Any, Optional, List
import os
from utils.structured_logging import get_logger
from utils.error_handling import ErrorContext

logger = get_logger(__name__)


class ComplianceResultsDialog:
    """Dialog for displaying clinical guidelines compliance analysis results."""

    # Status colors
    STATUS_COLORS = {
        'ALIGNED': {'bg': '#28a745', 'fg': 'white'},
        'GAP': {'bg': '#dc3545', 'fg': 'white'},
        'REVIEW': {'bg': '#17a2b8', 'fg': 'white'},
    }

    STATUS_ICONS = {
        'ALIGNED': '\u2713',
        'GAP': '\u2717',
        'REVIEW': '?',
    }

    def __init__(self, parent):
        """Initialize the compliance results dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.analysis_text = ""
        self.metadata = {}
        self.recording_id: Optional[int] = None
        self.dialog: Optional[tk.Toplevel] = None
        self._condition_frames = {}

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
                - has_sufficient_data: bool
                - conditions: list of condition dicts
                - conditions_count: int
                - disclaimer: str
                - compliant_count: int
                - gap_count: int
                - warning_count: int
                - guidelines_checked: int
            recording_id: Optional recording ID to link analysis to
        """
        self.recording_id = recording_id
        self.analysis_text = analysis
        self.metadata = metadata or {}

        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        dialog = self.dialog
        dialog.title("Clinical Guidelines Compliance")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(950, 800)
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
        main_frame = ttk.Frame(dialog, padding=15)
        main_frame.pack(fill=BOTH, expand=True)

        # Disclaimer banner at top
        self._create_disclaimer_banner(main_frame)

        # Header with title and score
        self._create_header(main_frame)

        # Summary bar
        self._create_summary_bar(main_frame)

        # Check for insufficient data
        has_sufficient = self.metadata.get('has_sufficient_data', True)
        if not has_sufficient:
            self._create_insufficient_data_view(main_frame)
        else:
            # Scrollable condition sections
            self._create_conditions_view(main_frame)

        # Button frame
        self._create_buttons(main_frame)

        # Focus on the dialog
        dialog.focus_set()

    def _create_disclaimer_banner(self, parent: ttk.Frame) -> None:
        """Create the disclaimer banner at the top."""
        disclaimer = self.metadata.get(
            'disclaimer',
            'AI-assisted analysis for clinical decision support. '
            'Verify findings against current clinical guidelines.'
        )

        banner_frame = ttk.Frame(parent)
        banner_frame.pack(fill=X, pady=(0, 10))

        # Use a canvas for colored background
        banner_canvas = tk.Canvas(
            banner_frame, height=32, highlightthickness=0,
            bg='#fff3cd'  # Amber/yellow background
        )
        banner_canvas.pack(fill=X)

        banner_canvas.create_text(
            10, 16,
            text=f"\u26A0  {disclaimer}",
            anchor='w',
            font=("Segoe UI", 9, "italic"),
            fill='#856404',
        )

    def _create_header(self, parent: ttk.Frame) -> None:
        """Create the header with title and score badge."""
        header_frame = ttk.Frame(parent)
        header_frame.pack(fill=X, pady=(0, 10))

        title_label = ttk.Label(
            header_frame,
            text="Clinical Guidelines Compliance Analysis",
            font=("Segoe UI", 15, "bold")
        )
        title_label.pack(side=LEFT)

        # Score badge
        has_sufficient = self.metadata.get('has_sufficient_data', True)
        score = self.metadata.get('overall_score', 0.0)
        score_pct = int(score * 100)

        if has_sufficient and score_pct > 0:
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
                text="Alignment:",
                font=("Segoe UI", 11)
            )
            score_text_label.pack(side=RIGHT)
        elif not has_sufficient:
            ttk.Label(
                header_frame,
                text="N/A",
                font=("Segoe UI", 14, "bold"),
                foreground="#6c757d"
            ).pack(side=RIGHT, padx=10)

    def _create_summary_bar(self, parent: ttk.Frame) -> None:
        """Create the summary metrics bar."""
        summary_frame = ttk.Frame(parent)
        summary_frame.pack(fill=X, pady=(0, 10))

        conditions_count = self.metadata.get('conditions_count', 0)
        guidelines_checked = self.metadata.get('guidelines_checked', 0)
        aligned_count = self.metadata.get('compliant_count', 0)
        gap_count = self.metadata.get('gap_count', 0)
        review_count = self.metadata.get('warning_count', 0)

        # Conditions analyzed
        if conditions_count > 0:
            ttk.Label(
                summary_frame,
                text=f"Conditions: {conditions_count}",
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 15))

        # Guidelines searched
        if guidelines_checked > 0:
            ttk.Label(
                summary_frame,
                text=f"Guidelines: {guidelines_checked}",
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 15))

        # Aligned count
        if aligned_count > 0:
            ttk.Label(
                summary_frame,
                text=f"\u2713 Aligned: {aligned_count}",
                font=("Segoe UI", 10),
                foreground="#28a745"
            ).pack(side=LEFT, padx=(0, 15))

        # Gap count
        if gap_count > 0:
            ttk.Label(
                summary_frame,
                text=f"\u2717 Gaps: {gap_count}",
                font=("Segoe UI", 10, "bold"),
                foreground="#dc3545"
            ).pack(side=LEFT, padx=(0, 15))

        # Review count
        if review_count > 0:
            ttk.Label(
                summary_frame,
                text=f"? Review: {review_count}",
                font=("Segoe UI", 10),
                foreground="#17a2b8"
            ).pack(side=LEFT)

        # Score progress bar
        has_sufficient = self.metadata.get('has_sufficient_data', True)
        if has_sufficient:
            score = self.metadata.get('overall_score', 0.0)
            score_pct = int(score * 100)
            bar_frame = ttk.Frame(parent)
            bar_frame.pack(fill=X, pady=(0, 10))
            score_bar = ttk.Progressbar(
                bar_frame,
                mode='determinate',
                value=score_pct,
                bootstyle=self._get_progressbar_style(score_pct)
            )
            score_bar.pack(fill=X)

    def _create_insufficient_data_view(self, parent: ttk.Frame) -> None:
        """Create the insufficient data message view."""
        msg_frame = ttk.Frame(parent, padding=30)
        msg_frame.pack(fill=BOTH, expand=True, pady=10)

        ttk.Label(
            msg_frame,
            text="Insufficient Data",
            font=("Segoe UI", 14, "bold"),
            foreground="#6c757d"
        ).pack(pady=(0, 15))

        msg_text = (
            self.analysis_text or
            "Not enough clinical guidelines or SOAP note data available to "
            "perform a meaningful compliance analysis."
        )

        text_widget = tk.Text(
            msg_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 11),
            height=8,
            padx=15,
            pady=15,
        )
        text_widget.pack(fill=BOTH, expand=True)
        text_widget.insert("1.0", msg_text)
        text_widget.config(state=tk.DISABLED)

    def _create_conditions_view(self, parent: ttk.Frame) -> None:
        """Create the scrollable condition-organized results view."""
        conditions = self.metadata.get('conditions', [])

        # Create scrollable canvas
        canvas_frame = ttk.Frame(parent)
        canvas_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            canvas_frame, orient=VERTICAL, command=canvas.yview
        )
        scrollable = ttk.Frame(canvas)

        scrollable.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mousewheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        canvas.bind_all("<MouseWheel>", _on_mousewheel)
        # Clean up mousewheel binding when dialog closes
        if self.dialog:
            self.dialog.bind(
                "<Destroy>",
                lambda e: canvas.unbind_all("<MouseWheel>")
            )

        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        # Bind canvas width to scrollable frame
        def _on_canvas_configure(event):
            canvas.itemconfig(
                canvas.find_all()[0], width=event.width
            )
        canvas.bind("<Configure>", _on_canvas_configure)

        if not conditions:
            # Show the raw text if no structured conditions
            self._create_raw_text_view(scrollable)
            return

        # Create a section for each condition
        for i, cond in enumerate(conditions):
            self._create_condition_section(scrollable, cond, i)

    def _create_condition_section(
        self, parent: ttk.Frame, cond: dict, index: int
    ) -> None:
        """Create a collapsible section for one condition.

        Args:
            parent: Parent frame
            cond: Condition dict with 'condition', 'status', 'score', 'findings'
            index: Condition index
        """
        cond_name = cond.get('condition', 'Unknown')
        status = cond.get('status', 'REVIEW')
        score = cond.get('score', 0.0)
        guidelines_matched = cond.get('guidelines_matched', 0)
        findings = cond.get('findings', [])

        colors = self.STATUS_COLORS.get(status, self.STATUS_COLORS['REVIEW'])
        icon = self.STATUS_ICONS.get(status, '?')

        # Condition frame with border
        section_frame = ttk.LabelFrame(
            parent,
            text="",
            padding=10,
        )
        section_frame.pack(fill=X, padx=5, pady=(0, 8))

        # Header row with condition name and status badge
        header_frame = ttk.Frame(section_frame)
        header_frame.pack(fill=X, pady=(0, 5))

        # Status badge
        badge_canvas = tk.Canvas(
            header_frame, width=90, height=24,
            highlightthickness=0, bg=colors['bg']
        )
        badge_canvas.pack(side=LEFT, padx=(0, 10))
        badge_canvas.create_text(
            45, 12,
            text=f"{icon} {status}",
            fill=colors['fg'],
            font=("Segoe UI", 9, "bold"),
        )

        # Condition name
        ttk.Label(
            header_frame,
            text=cond_name,
            font=("Segoe UI", 12, "bold")
        ).pack(side=LEFT)

        # Score on right
        score_pct = int(score * 100)
        score_color = self._get_score_color(score_pct)
        ttk.Label(
            header_frame,
            text=f"{score_pct}%",
            font=("Segoe UI", 11, "bold"),
            foreground=score_color
        ).pack(side=RIGHT, padx=(10, 0))

        ttk.Label(
            header_frame,
            text=f"Guidelines: {guidelines_matched}",
            font=("Segoe UI", 9),
            foreground="#6c757d"
        ).pack(side=RIGHT)

        # Separator
        ttk.Separator(section_frame, orient='horizontal').pack(
            fill=X, pady=5
        )

        # Findings list
        for finding in findings:
            self._create_finding_row(section_frame, finding)

    def _create_finding_row(self, parent: ttk.Frame, finding: dict) -> None:
        """Create a row for a single finding.

        Args:
            parent: Parent frame
            finding: Finding dict
        """
        status = finding.get('status', 'REVIEW')
        finding_text = finding.get('finding', '')
        guideline_ref = finding.get('guideline_reference', '')
        recommendation = finding.get('recommendation', '')
        citation_verified = finding.get('citation_verified', False)

        colors = self.STATUS_COLORS.get(status, self.STATUS_COLORS['REVIEW'])
        icon = self.STATUS_ICONS.get(status, '?')

        row_frame = ttk.Frame(parent)
        row_frame.pack(fill=X, padx=5, pady=2)

        # Status indicator
        status_label = tk.Label(
            row_frame,
            text=f" {icon} ",
            bg=colors['bg'],
            fg=colors['fg'],
            font=("Segoe UI", 9, "bold"),
            padx=4,
            pady=1,
        )
        status_label.pack(side=LEFT, padx=(0, 8))

        # Finding content
        content_frame = ttk.Frame(row_frame)
        content_frame.pack(side=LEFT, fill=X, expand=True)

        # Finding text
        ttk.Label(
            content_frame,
            text=finding_text,
            font=("Segoe UI", 10),
            wraplength=700,
        ).pack(anchor='w')

        # Guideline reference with verification indicator
        if guideline_ref:
            verify_mark = '\u2713 verified' if citation_verified else '? unverified'
            verify_color = '#28a745' if citation_verified else '#6c757d'

            ref_frame = ttk.Frame(content_frame)
            ref_frame.pack(anchor='w', pady=(2, 0))

            ttk.Label(
                ref_frame,
                text=f"Guideline: {guideline_ref}",
                font=("Segoe UI", 9, "italic"),
                foreground="#0066cc",
                wraplength=650,
            ).pack(side=LEFT)

            ttk.Label(
                ref_frame,
                text=f"  [{verify_mark}]",
                font=("Segoe UI", 8),
                foreground=verify_color,
            ).pack(side=LEFT)

        # Recommendation
        if recommendation:
            ttk.Label(
                content_frame,
                text=f"Recommendation: {recommendation}",
                font=("Segoe UI", 9),
                foreground="#2d6a4f",
                wraplength=700,
            ).pack(anchor='w', pady=(2, 0))

    def _create_raw_text_view(self, parent: ttk.Frame) -> None:
        """Create a raw text view fallback when no structured conditions."""
        text_widget = tk.Text(
            parent,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            padx=10,
            pady=10,
        )
        text_widget.pack(fill=BOTH, expand=True)
        text_widget.insert("1.0", self.analysis_text)
        text_widget.config(state=tk.DISABLED)

    def _create_buttons(self, parent: ttk.Frame) -> None:
        """Create the action buttons at the bottom."""
        button_frame = ttk.Frame(parent)
        button_frame.pack(fill=X, pady=(5, 0))

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
            command=self.dialog.destroy,
            width=15
        ).pack(side=RIGHT)

    def _get_score_color(self, score_pct: int) -> str:
        """Get color based on compliance score percentage."""
        if score_pct >= 80:
            return "#28a745"
        elif score_pct >= 60:
            return "#fd7e14"
        else:
            return "#dc3545"

    def _get_progressbar_style(self, score_pct: int) -> str:
        """Get progressbar style based on compliance score percentage."""
        if score_pct >= 80:
            return "success"
        elif score_pct >= 60:
            return "warning"
        else:
            return "danger"

    def _copy_to_clipboard(self):
        """Copy the analysis to clipboard."""
        try:
            pyperclip.copy(self.analysis_text)
            messagebox.showinfo(
                "Copied",
                "Compliance analysis copied to clipboard!",
                parent=self.dialog
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
                parent=self.dialog
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
                new_content = (
                    f"{current_content}\n\n"
                    f"--- Clinical Guidelines Compliance ---\n\n"
                    f"{self.analysis_text}"
                )
            else:
                new_content = (
                    f"--- Clinical Guidelines Compliance ---\n\n"
                    f"{self.analysis_text}"
                )

            # Update the text widget
            target_widget.delete("1.0", tk.END)
            target_widget.insert("1.0", new_content)

            # Switch to the appropriate tab
            if doc_type == "soap":
                self.parent.notebook.select(1)  # SOAP tab

            messagebox.showinfo(
                "Added",
                f"Compliance analysis added to {doc_name}!",
                parent=self.dialog
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
                parent=self.dialog
            )

    def _export_to_pdf(self):
        """Export the compliance analysis to PDF."""
        try:
            from utils.pdf_exporter import PDFExporter

            # Get default filename
            default_filename = "compliance_report.pdf"

            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog,
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
                "conditions_count": self.metadata.get('conditions_count', 0),
                "has_sufficient_data": self.metadata.get('has_sufficient_data', True),
                "disclaimer": self.metadata.get('disclaimer', ''),
                "analysis_text": self.analysis_text,
                "conditions": self.metadata.get('conditions', []),
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
                    parent=self.dialog
                )

                # Optionally open the PDF
                if messagebox.askyesno(
                    "Open PDF",
                    "Would you like to open the PDF now?",
                    parent=self.dialog
                ):
                    import subprocess
                    import platform

                    if platform.system() == 'Darwin':
                        subprocess.call(('open', file_path))
                    elif platform.system() == 'Windows':
                        os.startfile(file_path)
                    else:
                        subprocess.call(('xdg-open', file_path))
            else:
                messagebox.showerror(
                    "Export Failed",
                    "Failed to export PDF. Check logs for details.",
                    parent=self.dialog
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
                parent=self.dialog
            )

    def _open_guidelines_upload(self):
        """Open the guidelines upload dialog."""
        try:
            from ui.dialogs.guidelines_upload_dialog import GuidelinesUploadDialog

            def on_upload(files: list, options: dict):
                """Handle upload start."""
                logger.info(f"Uploading {len(files)} guideline(s)")

            dialog = GuidelinesUploadDialog(self.parent, on_upload=on_upload)
            dialog.wait_window()

        except ImportError:
            messagebox.showinfo(
                "Upload Guidelines",
                "Use the 'Upload Guidelines' button in the Clinical Guidelines tab "
                "to add clinical guidelines to your database.",
                parent=self.dialog
            )
        except Exception as e:
            logger.error(f"Error opening guidelines upload: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to open guidelines upload: {e}",
                parent=self.dialog
            )
