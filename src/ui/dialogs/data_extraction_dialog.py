"""
Data Extraction Options Dialog

Provides options for selecting data extraction source, type, and output format.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any


class DataExtractionDialog:
    """Dialog for data extraction options."""
    
    def __init__(self, parent):
        """Initialize the data extraction dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        self.available_sources = []
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Data Extraction Options")
        
        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # Set dialog size to fit screen better
        dialog_width = min(700, int(screen_width * 0.7))
        dialog_height = min(650, int(screen_height * 0.85))
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(600, 500)
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")
        
        self._create_widgets()
        
        # Bind escape key to cancel
        self.dialog.bind('<Escape>', lambda e: self.cancel())
        
    def _create_widgets(self):
        """Create dialog widgets."""
        # Main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Create button frame first (at bottom)
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=tk.X, side=tk.BOTTOM, pady=(10, 0))
        
        # Create frame for scrollable content
        scroll_container = ttk.Frame(main_container)
        scroll_container.pack(fill=tk.BOTH, expand=True)
        
        # Create scrollable frame
        canvas = tk.Canvas(scroll_container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Main frame with padding inside scrollable area
        main_frame = ttk.Frame(scrollable_frame, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Extract Clinical Data",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Source selection frame
        source_frame = ttk.LabelFrame(main_frame, text="Select Source", padding="15")
        source_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.source_var = tk.StringVar(value="transcript")
        
        self.transcript_radio = ttk.Radiobutton(
            source_frame,
            text="Transcript",
            variable=self.source_var,
            value="transcript",
            state=tk.DISABLED
        )
        self.transcript_radio.pack(anchor=tk.W, pady=5)
        
        self.soap_radio = ttk.Radiobutton(
            source_frame,
            text="SOAP Note",
            variable=self.source_var,
            value="soap",
            state=tk.DISABLED
        )
        self.soap_radio.pack(anchor=tk.W, pady=5)
        
        self.context_radio = ttk.Radiobutton(
            source_frame,
            text="Context Information",
            variable=self.source_var,
            value="context",
            state=tk.DISABLED
        )
        self.context_radio.pack(anchor=tk.W, pady=5)
        
        # Extraction type frame
        type_frame = ttk.LabelFrame(main_frame, text="Data Type to Extract", padding="15")
        type_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.extraction_type_var = tk.StringVar(value="comprehensive")
        
        extraction_types = [
            ("comprehensive", "All Clinical Data (Comprehensive)"),
            ("vitals", "Vital Signs Only"),
            ("labs", "Laboratory Values Only"),
            ("medications", "Medications Only"),
            ("diagnoses", "Diagnoses with ICD Codes"),
            ("procedures", "Procedures and Interventions")
        ]
        
        for value, text in extraction_types:
            ttk.Radiobutton(
                type_frame,
                text=text,
                variable=self.extraction_type_var,
                value=value
            ).pack(anchor=tk.W, pady=5)
        
        # Output format frame
        format_frame = ttk.LabelFrame(main_frame, text="Output Format", padding="15")
        format_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.output_format_var = tk.StringVar(value="structured_text")
        
        output_formats = [
            ("structured_text", "Structured Text (Human-readable)"),
            ("json", "JSON (Machine-readable)"),
            ("csv", "CSV (Spreadsheet-compatible)")
        ]
        
        for value, text in output_formats:
            ttk.Radiobutton(
                format_frame,
                text=text,
                variable=self.output_format_var,
                value=value
            ).pack(anchor=tk.W, pady=5)
        
        # Info label
        info_label = ttk.Label(
            main_frame,
            text="The extracted data will be displayed in a results window with export options.",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        info_label.pack(pady=10)
        
        # Add buttons to the button_frame created at the top
        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            width=20
        )
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Extract button
        self.extract_btn = ttk.Button(
            button_frame,
            text="Extract Data",
            command=self.extract,
            width=20,
            style="Accent.TButton"
        )
        self.extract_btn.pack(side=tk.RIGHT)
        
        # Focus on extract button
        self.extract_btn.focus_set()
        
    def set_available_content(self, has_transcript: bool, has_soap: bool, has_context: bool = False):
        """Set which content sources are available.
        
        Args:
            has_transcript: Whether transcript is available
            has_soap: Whether SOAP note is available
            has_context: Whether context information is available
        """
        self.available_sources = []
        
        if has_transcript:
            self.transcript_radio.config(state=tk.NORMAL)
            self.available_sources.append("transcript")
        
        if has_soap:
            self.soap_radio.config(state=tk.NORMAL)
            self.available_sources.append("soap")
        
        if has_context:
            self.context_radio.config(state=tk.NORMAL)
            self.available_sources.append("context")
        
        # Set default selection to first available source
        if self.available_sources:
            self.source_var.set(self.available_sources[0])
        
    def extract(self):
        """Handle extract button click."""
        if not self.available_sources:
            messagebox.showerror(
                "No Content Available",
                "No content is available for data extraction.",
                parent=self.dialog
            )
            return
        
        # Collect selected options
        self.result = {
            "source": self.source_var.get(),
            "extraction_type": self.extraction_type_var.get(),
            "output_format": self.output_format_var.get()
        }
        
        self.dialog.destroy()
        
    def cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
        
    def show(self) -> Optional[Dict[str, Any]]:
        """Show the dialog and return the result.
        
        Returns:
            Dictionary with selected options or None if cancelled
        """
        # Wait for dialog to close
        self.dialog.wait_window()
        return self.result