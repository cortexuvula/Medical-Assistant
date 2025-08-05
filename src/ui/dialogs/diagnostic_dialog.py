"""
Diagnostic Analysis Dialog

Provides a dialog for users to select the source of clinical findings
and optionally input custom findings for diagnostic analysis.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Optional, Dict


class DiagnosticAnalysisDialog:
    """Dialog for configuring diagnostic analysis input."""
    
    def __init__(self, parent):
        """Initialize the diagnostic analysis dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        self.has_transcript = False
        self.has_soap = False
        
    def set_available_content(self, has_transcript: bool, has_soap: bool):
        """Set what content is available for analysis.
        
        Args:
            has_transcript: Whether transcript content is available
            has_soap: Whether SOAP note content is available
        """
        self.has_transcript = has_transcript
        self.has_soap = has_soap
        
    def show(self) -> Optional[Dict]:
        """Show the dialog and return user selection.
        
        Returns:
            Dictionary with 'source' and optional 'custom_findings', or None if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Diagnostic Analysis Options")
        self.dialog_width, dialog_height = ui_scaler.get_dialog_size(800, 700)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(750, 650)  # Set minimum size
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        # Main container
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="Select Source for Diagnostic Analysis",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Source selection
        source_frame = ttk.LabelFrame(main_frame, text="Analysis Source", padding=15)
        source_frame.pack(fill=X, pady=(0, 20))
        
        self.source_var = tk.StringVar(value="transcript" if self.has_transcript else "custom")
        
        # Transcript option
        transcript_radio = ttk.Radiobutton(
            source_frame,
            text="Use current transcript",
            variable=self.source_var,
            value="transcript",
            state=NORMAL if self.has_transcript else DISABLED
        )
        transcript_radio.pack(anchor=W, pady=5)
        
        if not self.has_transcript:
            ttk.Label(
                source_frame,
                text="    (No transcript available)",
                foreground="gray"
            ).pack(anchor=W)
        
        # SOAP note option
        soap_radio = ttk.Radiobutton(
            source_frame,
            text="Use current SOAP note",
            variable=self.source_var,
            value="soap",
            state=NORMAL if self.has_soap else DISABLED
        )
        soap_radio.pack(anchor=W, pady=5)
        
        if not self.has_soap:
            ttk.Label(
                source_frame,
                text="    (No SOAP note available)",
                foreground="gray"
            ).pack(anchor=W)
        
        # Custom input option
        custom_radio = ttk.Radiobutton(
            source_frame,
            text="Enter custom clinical findings",
            variable=self.source_var,
            value="custom"
        )
        custom_radio.pack(anchor=W, pady=5)
        
        # Custom findings input
        custom_frame = ttk.LabelFrame(main_frame, text="Custom Clinical Findings", padding=15)
        custom_frame.pack(fill=BOTH, expand=True, pady=(0, 20))
        
        # Instructions
        ttk.Label(
            custom_frame,
            text="Enter symptoms, examination findings, lab results, etc.:",
            font=("Segoe UI", 10)
        ).pack(anchor=W, pady=(0, 10))
        
        # Text area with scrollbar
        text_frame = ttk.Frame(custom_frame)
        text_frame.pack(fill=BOTH, expand=True)
        
        self.custom_text = tk.Text(
            text_frame,
            wrap=WORD,
            height=10,
            font=("Segoe UI", 11)
        )
        self.custom_text.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=self.custom_text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.custom_text.config(yscrollcommand=scrollbar.set)
        
        # Example text
        example_text = """Example:
- Severe headache for 2 weeks, right-sided
- Associated nausea and photophobia
- BP 130/85, HR 78, Temp 37.0°C
- Neurological exam normal
- Family history of migraines"""
        
        self.custom_text.insert("1.0", example_text)
        self.custom_text.tag_add("example", "1.0", "end")
        self.custom_text.tag_config("example", foreground="gray")
        
        # Clear example text on first click
        def clear_example(event=None):
            if self.custom_text.tag_ranges("example"):
                self.custom_text.delete("1.0", "end")
                self.custom_text.tag_remove("example", "1.0", "end")
                self.custom_text.unbind("<FocusIn>")
        
        self.custom_text.bind("<FocusIn>", clear_example)
        
        # Enable/disable custom text based on selection
        def on_source_change():
            if self.source_var.get() == "custom":
                self.custom_text.config(state=NORMAL)
                clear_example()
            else:
                self.custom_text.config(state=DISABLED)
        
        self.source_var.trace('w', lambda *args: on_source_change())
        on_source_change()
        
        # Buttons
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X)
        
        ttk.Button(
            button_frame,
            text="Analyze",
            command=self._on_analyze,
            bootstyle="primary",
            width=15
        ).pack(side=RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15
        ).pack(side=RIGHT)
        
        # Focus and bindings
        self.dialog.bind("<Return>", lambda e: self._on_analyze())
        self.dialog.bind("<Escape>", lambda e: self._on_cancel())
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
        return self.result
    
    def _on_analyze(self):
        """Handle analyze button click."""
        source = self.source_var.get()
        
        if source == "custom":
            custom_findings = self.custom_text.get("1.0", "end").strip()
            # Check if it's still the example text
            if custom_findings.startswith("Example:") or not custom_findings:
                tk.messagebox.showwarning(
                    "No Custom Findings",
                    "Please enter clinical findings or select a different source.",
                    parent=self.dialog
                )
                return
        else:
            custom_findings = ""
        
        self.result = {
            "source": source,
            "custom_findings": custom_findings
        }
        
        self.dialog.destroy()
    
    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()