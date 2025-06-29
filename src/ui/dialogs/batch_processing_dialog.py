"""
Batch Processing Dialog

Provides UI for configuring batch processing of multiple recordings.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import List, Dict, Optional
import logging

from ttkbootstrap.tooltip import ToolTip


class BatchProcessingDialog:
    """Dialog for configuring batch processing options."""
    
    def __init__(self, parent: tk.Tk, recording_ids: List[int]):
        """Initialize the batch processing dialog.
        
        Args:
            parent: Parent window
            recording_ids: List of recording IDs to process
        """
        self.parent = parent
        self.recording_ids = recording_ids
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Batch Processing Options")
        self.dialog.geometry("500x400")
        self.dialog.resizable(False, False)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (500 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (400 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        # Make modal
        self.dialog.grab_set()
        
        # Create UI
        self._create_ui()
        
        # Bind Enter and Escape keys
        self.dialog.bind('<Return>', lambda e: self._on_process())
        self.dialog.bind('<Escape>', lambda e: self._on_cancel())
        
    def _create_ui(self):
        """Create the dialog UI."""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and count
        title_label = ttk.Label(
            main_frame,
            text=f"Process {len(self.recording_ids)} Recording{'s' if len(self.recording_ids) > 1 else ''}",
            font=("", 12, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Processing options frame
        options_frame = ttk.LabelFrame(main_frame, text="Processing Options", padding=15)
        options_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 20))
        
        # Processing type checkboxes
        self.process_soap = tk.BooleanVar(value=True)
        self.process_referral = tk.BooleanVar(value=False)
        self.process_letter = tk.BooleanVar(value=False)
        
        soap_check = ttk.Checkbutton(
            options_frame,
            text="Generate SOAP Notes",
            variable=self.process_soap
        )
        soap_check.pack(anchor=tk.W, pady=5)
        ToolTip(soap_check, "Generate SOAP notes from transcripts")
        
        referral_check = ttk.Checkbutton(
            options_frame,
            text="Generate Referrals",
            variable=self.process_referral
        )
        referral_check.pack(anchor=tk.W, pady=5)
        ToolTip(referral_check, "Generate referrals from SOAP notes")
        
        letter_check = ttk.Checkbutton(
            options_frame,
            text="Generate Letters",
            variable=self.process_letter
        )
        letter_check.pack(anchor=tk.W, pady=5)
        ToolTip(letter_check, "Generate letters from available content")
        
        # Priority selection
        priority_frame = ttk.Frame(options_frame)
        priority_frame.pack(fill=tk.X, pady=(20, 0))
        
        ttk.Label(priority_frame, text="Processing Priority:").pack(side=tk.LEFT, padx=(0, 10))
        
        self.priority_var = tk.StringVar(value="normal")
        priority_combo = ttk.Combobox(
            priority_frame,
            textvariable=self.priority_var,
            values=["low", "normal", "high"],
            state="readonly",
            width=15
        )
        priority_combo.pack(side=tk.LEFT)
        ToolTip(priority_combo, "Set priority for batch processing")
        
        # Advanced options
        advanced_frame = ttk.LabelFrame(main_frame, text="Advanced Options", padding=10)
        advanced_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.skip_existing = tk.BooleanVar(value=True)
        skip_check = ttk.Checkbutton(
            advanced_frame,
            text="Skip recordings that already have content",
            variable=self.skip_existing
        )
        skip_check.pack(anchor=tk.W, pady=5)
        ToolTip(skip_check, "Skip processing if the recording already has the requested content")
        
        self.continue_on_error = tk.BooleanVar(value=True)
        continue_check = ttk.Checkbutton(
            advanced_frame,
            text="Continue processing on errors",
            variable=self.continue_on_error
        )
        continue_check.pack(anchor=tk.W, pady=5)
        ToolTip(continue_check, "Continue with remaining recordings if one fails")
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bootstyle="secondary",
            width=15
        )
        cancel_btn.pack(side=tk.RIGHT, padx=(5, 0))
        
        # Process button
        process_btn = ttk.Button(
            button_frame,
            text="Start Processing",
            command=self._on_process,
            bootstyle="primary",
            width=15
        )
        process_btn.pack(side=tk.RIGHT)
        
        # Focus on process button
        process_btn.focus_set()
        
    def _on_process(self):
        """Handle process button click."""
        # Validate at least one processing type is selected
        if not any([self.process_soap.get(), self.process_referral.get(), self.process_letter.get()]):
            messagebox.showwarning(
                "No Processing Selected",
                "Please select at least one processing option.",
                parent=self.dialog
            )
            return
        
        # Build result dictionary
        self.result = {
            "process_soap": self.process_soap.get(),
            "process_referral": self.process_referral.get(),
            "process_letter": self.process_letter.get(),
            "priority": self.priority_var.get(),
            "skip_existing": self.skip_existing.get(),
            "continue_on_error": self.continue_on_error.get()
        }
        
        self.dialog.destroy()
        
    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
        
    def show(self) -> Optional[Dict]:
        """Show the dialog and return the result.
        
        Returns:
            Dictionary with processing options or None if cancelled
        """
        self.dialog.wait_window()
        return self.result