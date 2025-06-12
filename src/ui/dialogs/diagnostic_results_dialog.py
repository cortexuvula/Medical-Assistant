"""
Diagnostic Results Dialog

Displays the results of diagnostic analysis in a formatted, user-friendly dialog.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
import pyperclip
import logging
from typing import Dict


class DiagnosticResultsDialog:
    """Dialog for displaying diagnostic analysis results."""
    
    def __init__(self, parent):
        """Initialize the diagnostic results dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.analysis_text = ""
        
    def show_results(self, analysis: str, source: str, metadata: Dict):
        """Show the diagnostic analysis results.
        
        Args:
            analysis: The diagnostic analysis text
            source: Source of the analysis (Transcript, SOAP Note, Custom Input)
            metadata: Additional metadata from the analysis
        """
        self.analysis_text = analysis
        
        # Create dialog window
        dialog = tk.Toplevel(self.parent)
        dialog.title("Diagnostic Analysis Results")
        dialog.geometry("900x700")
        dialog.minsize(850, 650)  # Set minimum size
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() - dialog.winfo_width()) // 2
        y = (dialog.winfo_screenheight() - dialog.winfo_height()) // 2
        dialog.geometry(f"+{x}+{y}")
        
        # Main container
        main_frame = ttk.Frame(dialog, padding=20)
        main_frame.pack(fill=BOTH, expand=True)
        
        # Header
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
        
        if metadata.get('has_red_flags', False):
            red_flag_label = ttk.Label(
                info_frame,
                text="⚠ RED FLAGS",
                font=("Segoe UI", 10, "bold"),
                foreground="red"
            )
            red_flag_label.pack(side=LEFT)
        
        # Results text area
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 15))
        
        # Create text widget with scrollbar
        self.result_text = tk.Text(
            text_frame,
            wrap=WORD,
            font=("Segoe UI", 11),
            padx=10,
            pady=10
        )
        self.result_text.pack(side=LEFT, fill=BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=self.result_text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        self.result_text.config(yscrollcommand=scrollbar.set)
        
        # Insert and format the analysis
        self._format_analysis(analysis)
        
        # Make text read-only
        self.result_text.config(state=DISABLED)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X)
        
        # Action buttons
        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=self._copy_to_clipboard,
            bootstyle="info",
            width=20
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
        ).pack(side=LEFT)
        
        ttk.Button(
            button_frame,
            text="Close",
            command=dialog.destroy,
            width=15
        ).pack(side=RIGHT)
        
        # Bind keyboard shortcuts
        dialog.bind("<Control-c>", lambda e: self._copy_to_clipboard())
        dialog.bind("<Escape>", lambda e: dialog.destroy())
        
        # Focus on the dialog
        dialog.focus_set()
    
    def _format_analysis(self, analysis: str):
        """Format and display the analysis with appropriate styling."""
        # Configure tags for formatting
        self.result_text.tag_configure("section_header", font=("Segoe UI", 12, "bold"), spacing3=10)
        self.result_text.tag_configure("red_flag", foreground="red", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("diagnosis", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("icd9", foreground="blue", font=("Segoe UI", 10, "italic"))
        
        # Insert the analysis
        lines = analysis.split('\n')
        for line in lines:
            line = line.strip()
            if not line:
                self.result_text.insert(END, "\n")
                continue
                
            # Format section headers
            if any(header in line for header in ["CLINICAL SUMMARY:", "DIFFERENTIAL DIAGNOSES:", 
                                                 "RED FLAGS:", "RECOMMENDED INVESTIGATIONS:", 
                                                 "CLINICAL PEARLS:"]):
                self.result_text.insert(END, line + "\n", "section_header")
            # Highlight red flags
            elif "RED FLAGS:" in analysis and self._is_in_section(line, "RED FLAGS:", lines):
                self.result_text.insert(END, line + "\n", "red_flag")
            # Format differential diagnoses
            elif self._is_in_section(line, "DIFFERENTIAL DIAGNOSES:", lines) and (line[0].isdigit() or line.startswith("-")):
                # Look for ICD-9 codes (format: xxx.xx)
                import re
                icd9_pattern = r'\b\d{3}\.\d{1,2}\b'
                if re.search(icd9_pattern, line):
                    # Split line to highlight ICD-9 code
                    parts = re.split(f'({icd9_pattern})', line)
                    for part in parts:
                        if re.match(icd9_pattern, part):
                            self.result_text.insert(END, part, "icd9")
                        else:
                            self.result_text.insert(END, part, "diagnosis")
                    self.result_text.insert(END, "\n")
                else:
                    self.result_text.insert(END, line + "\n", "diagnosis")
            else:
                self.result_text.insert(END, line + "\n")
    
    def _is_in_section(self, line: str, section_header: str, all_lines: list) -> bool:
        """Check if a line belongs to a specific section."""
        # Simple heuristic: check if the section header appears before this line
        # and no other section header appears between them
        section_headers = ["CLINICAL SUMMARY:", "DIFFERENTIAL DIAGNOSES:", 
                          "RED FLAGS:", "RECOMMENDED INVESTIGATIONS:", "CLINICAL PEARLS:"]
        
        in_section = False
        for check_line in all_lines:
            if section_header in check_line:
                in_section = True
            elif any(header in check_line for header in section_headers if header != section_header):
                in_section = False
            elif check_line.strip() == line:
                return in_section
        return False
    
    def _copy_to_clipboard(self):
        """Copy the analysis to clipboard."""
        try:
            pyperclip.copy(self.analysis_text)
            messagebox.showinfo(
                "Success",
                "Diagnostic analysis copied to clipboard!",
                parent=self.result_text.winfo_toplevel()
            )
        except Exception as e:
            logging.error(f"Error copying to clipboard: {e}")
            messagebox.showerror(
                "Error",
                "Failed to copy to clipboard.",
                parent=self.result_text.winfo_toplevel()
            )
    
    def _add_to_document(self, doc_type: str):
        """Add the analysis to a document (SOAP or Letter).
        
        Args:
            doc_type: Either 'soap' or 'letter'
        """
        # Get the appropriate text widget
        if doc_type == "soap":
            text_widget = self.parent.soap_text
            doc_name = "SOAP Note"
            tab_index = 1
        else:
            text_widget = self.parent.letter_text
            doc_name = "Letter"
            tab_index = 3
        
        # Get current content
        current_content = text_widget.get("1.0", "end").strip()
        
        # Prepare the diagnostic section
        diagnostic_section = f"\n\n{'='*50}\nDIAGNOSTIC ANALYSIS\n{'='*50}\n\n{self.analysis_text}"
        
        # Add to document
        text_widget.config(state=NORMAL)
        if current_content:
            text_widget.insert("end", diagnostic_section)
        else:
            text_widget.insert("1.0", self.analysis_text)
        text_widget.config(state=NORMAL)
        
        # Switch to the appropriate tab
        self.parent.notebook.select(tab_index)
        
        # Show confirmation
        messagebox.showinfo(
            "Success",
            f"Diagnostic analysis added to {doc_name}!",
            parent=self.result_text.winfo_toplevel()
        )
        
        # Close the dialog
        self.result_text.winfo_toplevel().destroy()