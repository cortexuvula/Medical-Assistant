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
    
    def __init__(self, parent: tk.Tk, recording_ids: List[int] = None):
        """Initialize the batch processing dialog.
        
        Args:
            parent: Parent window
            recording_ids: List of recording IDs to process (optional)
        """
        self.parent = parent
        self.recording_ids = recording_ids or []
        self.selected_files = []
        self.result = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Batch Processing Options")
        self.dialog.geometry("600x700")
        self.dialog.resizable(True, True)
        self.dialog.minsize(600, 650)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (600 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (700 // 2)
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
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Batch Processing Options",
            font=("", 12, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Source selection frame
        source_frame = ttk.LabelFrame(main_frame, text="Source Selection", padding=15)
        source_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Source type radio buttons
        self.source_var = tk.StringVar(value="database" if self.recording_ids else "files")
        
        database_radio = ttk.Radiobutton(
            source_frame,
            text="Selected Database Recordings",
            variable=self.source_var,
            value="database",
            command=self._update_source_display
        )
        database_radio.pack(anchor=tk.W, pady=5)
        
        files_radio = ttk.Radiobutton(
            source_frame,
            text="Audio Files from Computer",
            variable=self.source_var,
            value="files",
            command=self._update_source_display
        )
        files_radio.pack(anchor=tk.W, pady=5)
        
        # Source info frame
        self.source_info_frame = ttk.Frame(source_frame)
        self.source_info_frame.pack(fill=tk.X, pady=(10, 0))
        
        # Initialize source display
        self._update_source_display()
        
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
        
    def _update_source_display(self):
        """Update the source information display based on selection."""
        # Clear existing widgets
        for widget in self.source_info_frame.winfo_children():
            widget.destroy()
        
        if self.source_var.get() == "database":
            # Show database recordings info
            info_label = ttk.Label(
                self.source_info_frame,
                text=f"Selected recordings from database: {len(self.recording_ids)}",
                foreground="gray"
            )
            info_label.pack(anchor=tk.W)
            
            if not self.recording_ids:
                warning_label = ttk.Label(
                    self.source_info_frame,
                    text="⚠ No recordings selected. Please select recordings first.",
                    foreground="orange"
                )
                warning_label.pack(anchor=tk.W, pady=(5, 0))
        else:
            # Show file selection button
            file_frame = ttk.Frame(self.source_info_frame)
            file_frame.pack(fill=tk.X)
            
            select_btn = ttk.Button(
                file_frame,
                text="Select Audio Files...",
                command=self._select_files,
                bootstyle="info"
            )
            select_btn.pack(side=tk.LEFT, padx=(0, 10))
            
            self.files_label = ttk.Label(
                file_frame,
                text=f"{len(self.selected_files)} files selected",
                foreground="gray"
            )
            self.files_label.pack(side=tk.LEFT)
            
            # Show selected files list if any
            if self.selected_files:
                # Create frame for text and scrollbar
                text_frame = ttk.Frame(self.source_info_frame)
                text_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))
                
                # Create scrollbar
                scrollbar = ttk.Scrollbar(text_frame)
                scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
                
                files_text = tk.Text(
                    text_frame,
                    height=6,
                    width=60,
                    wrap=tk.WORD,
                    font=("Courier", 9),
                    yscrollcommand=scrollbar.set
                )
                files_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
                scrollbar.config(command=files_text.yview)
                
                # Add file names
                for file in self.selected_files:
                    files_text.insert(tk.END, f"• {file}\n")
                
                files_text.config(state=tk.DISABLED)
    
    def _select_files(self):
        """Open file dialog to select audio files."""
        from tkinter import filedialog
        import os
        
        files = filedialog.askopenfilenames(
            parent=self.dialog,
            title="Select Audio Files",
            filetypes=[
                ("Audio Files", "*.mp3 *.wav *.m4a *.flac *.ogg *.opus *.webm *.mp4"),
                ("All Files", "*.*")
            ],
            initialdir=os.path.expanduser("~")
        )
        
        if files:
            self.selected_files = list(files)
            self._update_source_display()
    
    def _on_process(self):
        """Handle process button click."""
        # Validate source selection
        if self.source_var.get() == "database" and not self.recording_ids:
            messagebox.showwarning(
                "No Recordings Selected",
                "Please select recordings from the database first.",
                parent=self.dialog
            )
            return
        elif self.source_var.get() == "files" and not self.selected_files:
            messagebox.showwarning(
                "No Files Selected",
                "Please select audio files to process.",
                parent=self.dialog
            )
            return
        
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
            "source": self.source_var.get(),
            "recording_ids": self.recording_ids if self.source_var.get() == "database" else [],
            "files": self.selected_files if self.source_var.get() == "files" else [],
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