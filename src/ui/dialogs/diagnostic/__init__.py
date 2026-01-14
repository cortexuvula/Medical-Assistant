"""
Diagnostic Results Dialog Package

Displays the results of diagnostic analysis in a formatted, user-friendly dialog.
"""

import tkinter as tk
from tkinter.constants import END, WORD
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT, W, DISABLED
import logging
from typing import Dict, List, Optional

from .formatter import FormatterMixin
from .parser import ParserMixin
from .database import DatabaseMixin
from .export import ExportMixin
from .panels import PanelsMixin
from .periodic import PeriodicMixin


class DiagnosticResultsDialog(
    FormatterMixin,
    ParserMixin,
    DatabaseMixin,
    ExportMixin,
    PanelsMixin,
    PeriodicMixin
):
    """Dialog for displaying diagnostic analysis results.

    This class combines multiple mixins to provide:
    - Text formatting and highlighting (FormatterMixin)
    - Analysis parsing (ParserMixin)
    - Database operations (DatabaseMixin)
    - Export functionality (ExportMixin)
    - Red flags and investigations panels (PanelsMixin)
    - Periodic analysis display (PeriodicMixin)
    """

    def __init__(self, parent):
        """Initialize the diagnostic results dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.analysis_text = ""
        self.source = ""
        self.metadata = {}
        self.dialog: Optional[tk.Toplevel] = None
        self.recording_id: Optional[int] = None
        self.source_text: str = ""
        self._db = None
        self.investigation_vars: Dict = {}
        self.inv_summary_label: Optional[ttk.Label] = None
        self.result_text: Optional[tk.Text] = None

    def show_results(
        self,
        analysis: str,
        source: str,
        metadata: Dict,
        recording_id: Optional[int] = None,
        source_text: str = ""
    ):
        """Show the diagnostic analysis results.

        Args:
            analysis: The diagnostic analysis text
            source: Source of the analysis (Transcript, SOAP Note, Custom Input)
            metadata: Additional metadata from the analysis
            recording_id: Optional recording ID to link analysis to
            source_text: Original text that was analyzed
        """
        self.analysis_text = analysis
        self.source = source
        self.metadata = metadata
        self.recording_id = recording_id
        self.source_text = source_text

        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        dialog = self.dialog
        dialog.title("Diagnostic Analysis Results")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(900, 700)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.minsize(850, 650)
        dialog.transient(self.parent)

        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        dialog.deiconify()
        try:
            dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet

        # Main container
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=BOTH, expand=True)

        # Create header
        self._create_header(main_frame, source, metadata)

        # Create special panels (red flags, investigations, periodic)
        self._create_special_panels(main_frame, analysis, metadata, recording_id)

        # Results text area
        self._create_results_text(main_frame, analysis)

        # Button frames
        self._create_button_frames(main_frame, dialog)

        # Bind keyboard shortcuts
        dialog.bind("<Control-c>", lambda e: self._copy_to_clipboard())
        dialog.bind("<Escape>", lambda e: dialog.destroy())

        # Focus on the dialog
        dialog.focus_set()

    def _create_header(
        self, main_frame: ttk.Frame, source: str, metadata: Dict
    ) -> None:
        """Create the header section with title and metadata.

        Args:
            main_frame: Main container frame
            source: Source of the analysis
            metadata: Analysis metadata
        """
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=X, pady=(0, 15))

        title_label = ttk.Label(
            header_frame,
            text="Diagnostic Analysis",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(side=LEFT)

        # Metadata info
        info_frame = ttk.Frame(header_frame)
        info_frame.pack(side=RIGHT)

        ttk.Label(
            info_frame,
            text=f"Source: {source}",
            font=("Segoe UI", 10)
        ).pack(side=LEFT, padx=(0, 15))

        diff_count = metadata.get('differential_count', 0)
        ttk.Label(
            info_frame,
            text=f"Differentials: {diff_count}",
            font=("Segoe UI", 10)
        ).pack(side=LEFT, padx=(0, 15))

        # Display average confidence if available
        avg_confidence = metadata.get('average_confidence')
        if avg_confidence is not None:
            confidence_pct = int(avg_confidence * 100)
            conf_color = "green" if confidence_pct >= 70 else (
                "orange" if confidence_pct >= 40 else "gray"
            )
            ttk.Label(
                info_frame,
                text=f"Avg Confidence: {confidence_pct}%",
                font=("Segoe UI", 10, "bold"),
                foreground=conf_color
            ).pack(side=LEFT, padx=(0, 15))

        if metadata.get('has_red_flags', False):
            red_flag_label = ttk.Label(
                info_frame,
                text="⚠ RED FLAGS",
                font=("Segoe UI", 10, "bold"),
                foreground="red"
            )
            red_flag_label.pack(side=LEFT)

    def _create_special_panels(
        self,
        main_frame: ttk.Frame,
        analysis: str,
        metadata: Dict,
        recording_id: Optional[int]
    ) -> None:
        """Create special panels for red flags, investigations, and periodic analysis.

        Args:
            main_frame: Main container frame
            analysis: Analysis text
            metadata: Analysis metadata
            recording_id: Optional recording ID
        """
        # Prominent Red Flags Panel (if red flags present)
        red_flags_list = metadata.get('red_flags_list', [])
        if not red_flags_list:
            red_flags_list = self._extract_red_flags_from_text(analysis)

        if red_flags_list:
            self._create_red_flags_panel(main_frame, red_flags_list)

        # Investigation Tracking Panel (if investigations present)
        investigations_list = metadata.get('structured_investigations', [])
        if not investigations_list:
            investigations_list = self._extract_investigations_from_text(analysis)

        # Filter to only valid investigations before creating panel
        valid_investigations = [
            inv for inv in investigations_list
            if inv.get('investigation_name', '').strip()
            and len(inv.get('investigation_name', '').strip()) >= 5
        ]

        if valid_investigations:
            self._create_investigations_panel(main_frame, valid_investigations)

        # Periodic Analysis Link (if available)
        periodic_session_id = metadata.get('periodic_session_id')
        if periodic_session_id or (
            recording_id and self._has_periodic_analyses(recording_id)
        ):
            self._create_periodic_analysis_panel(
                main_frame, recording_id, periodic_session_id
            )

    def _create_results_text(
        self, main_frame: ttk.Frame, analysis: str
    ) -> None:
        """Create the results text area with scrollbar.

        Args:
            main_frame: Main container frame
            analysis: Analysis text to display
        """
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 15))

        # Get current theme colors
        style = ttk.Style()
        bg_color = style.lookup('TFrame', 'background')
        fg_color = style.lookup('TLabel', 'foreground')

        self.result_text = tk.Text(
            text_frame,
            wrap=WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10,
            bg=bg_color if bg_color else 'white',
            fg=fg_color if fg_color else 'black',
            insertbackground=fg_color if fg_color else 'black'
        )
        self.result_text.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(
            text_frame, orient=VERTICAL, command=self.result_text.yview
        )
        scrollbar.pack(side=RIGHT, fill=Y)
        self.result_text.config(yscrollcommand=scrollbar.set)

        # Insert and format the analysis
        self._format_analysis(analysis)

        # Make text read-only
        self.result_text.config(state=DISABLED)

    def _create_button_frames(
        self, main_frame: ttk.Frame, dialog: tk.Toplevel
    ) -> None:
        """Create the button frames with action buttons.

        Args:
            main_frame: Main container frame
            dialog: Dialog window
        """
        # First row of buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X)

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
            width=20
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Add to Letter",
            command=lambda: self._add_to_document("letter"),
            bootstyle="primary",
            width=20
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Save to Database",
            command=self._save_to_database,
            bootstyle="secondary",
            width=18
        ).pack(side=LEFT)

        ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
            width=15
        ).pack(side=RIGHT)

        # Second row of buttons for export features
        button_frame2 = ttk.Frame(main_frame)
        button_frame2.pack(fill=X, pady=(10, 0))

        ttk.Button(
            button_frame2,
            text="Copy ICD Codes",
            command=self._copy_icd_codes,
            bootstyle="info-outline",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame2,
            text="Export to FHIR",
            command=self._export_to_fhir,
            bootstyle="success-outline",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Label(
            button_frame2,
            text="FHIR export for EHR integration",
            font=("Segoe UI", 9),
            foreground="gray"
        ).pack(side=LEFT, padx=(10, 0))


__all__ = ["DiagnosticResultsDialog"]
