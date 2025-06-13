"""
Medication Results Dialog

Displays the results of medication analysis in a formatted, user-friendly dialog.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox
import pyperclip
import logging
from typing import Dict, Any
import json


class MedicationResultsDialog:
    """Dialog for displaying medication analysis results."""
    
    def __init__(self, parent):
        """Initialize the medication results dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.analysis_text = ""
        self.result_text = None
        
    def show_results(self, analysis: Any, analysis_type: str, source: str, metadata: Dict):
        """Show the medication analysis results.
        
        Args:
            analysis: The medication analysis results (dict or string)
            analysis_type: Type of analysis performed
            source: Source of the analysis (Transcript, SOAP Note, Custom Input)
            metadata: Additional metadata from the analysis
        """
        # Convert analysis to string if it's a dict
        if isinstance(analysis, dict):
            self.analysis_text = self._format_analysis_dict(analysis, analysis_type)
        else:
            self.analysis_text = str(analysis)
        
        # Create dialog window
        dialog = tk.Toplevel(self.parent)
        dialog.title("Medication Analysis Results")
        dialog.geometry("950x750")
        dialog.minsize(900, 700)  # Set minimum size
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
        
        # Analysis type titles
        type_titles = {
            "extract": "Medication Extraction",
            "interactions": "Drug Interaction Check",
            "dosing": "Dosing Validation",
            "alternatives": "Alternative Medications",
            "prescription": "Prescription Generation",
            "comprehensive": "Comprehensive Medication Analysis"
        }
        
        title_label = ttk.Label(
            header_frame, 
            text=type_titles.get(analysis_type, "Medication Analysis"),
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
        
        med_count = metadata.get('medication_count', 0)
        if med_count > 0:
            ttk.Label(
                info_frame,
                text=f"Medications: {med_count}",
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 15))
        
        interaction_count = metadata.get('interaction_count', 0)
        if interaction_count > 0:
            interaction_label = ttk.Label(
                info_frame,
                text=f"⚠ Interactions: {interaction_count}",
                font=("Segoe UI", 10, "bold"),
                foreground="orange"
            )
            interaction_label.pack(side=LEFT, padx=(0, 15))
        
        if metadata.get('has_warnings', False):
            warning_label = ttk.Label(
                info_frame,
                text="⚠ WARNINGS",
                font=("Segoe UI", 10, "bold"),
                foreground="red"
            )
            warning_label.pack(side=LEFT)
        
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
        self._display_formatted_analysis(self.analysis_text)
        
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
        
        # Focus on the dialog
        dialog.focus_set()
    
    def _format_analysis_dict(self, analysis: Dict, analysis_type: str) -> str:
        """Format analysis dictionary into readable text.
        
        Args:
            analysis: Analysis results dictionary
            analysis_type: Type of analysis performed
            
        Returns:
            Formatted text string
        """
        formatted = []
        
        if analysis_type == "extract":
            if "medications" in analysis:
                formatted.append("EXTRACTED MEDICATIONS:\n")
                for med in analysis["medications"]:
                    if isinstance(med, dict):
                        name = med.get("name", "Unknown")
                        dose = med.get("dose", "")
                        route = med.get("route", "")
                        frequency = med.get("frequency", "")
                        formatted.append(f"• {name}")
                        if dose: formatted.append(f"  - Dose: {dose}")
                        if route: formatted.append(f"  - Route: {route}")
                        if frequency: formatted.append(f"  - Frequency: {frequency}")
                        formatted.append("")
                    else:
                        formatted.append(f"• {med}\n")
        
        elif analysis_type == "interactions":
            if "interactions" in analysis:
                formatted.append("DRUG INTERACTIONS:\n")
                for interaction in analysis["interactions"]:
                    if isinstance(interaction, dict):
                        drugs = interaction.get("drugs", [])
                        severity = interaction.get("severity", "Unknown")
                        description = interaction.get("description", "")
                        formatted.append(f"⚠ {' + '.join(drugs)}")
                        formatted.append(f"  Severity: {severity}")
                        if description:
                            formatted.append(f"  {description}")
                        formatted.append("")
                    else:
                        formatted.append(f"• {interaction}\n")
        
        elif analysis_type == "prescription":
            if "prescription" in analysis:
                formatted.append("PRESCRIPTION:\n")
                formatted.append(analysis["prescription"])
        
        else:
            # For comprehensive or other analysis types, format as JSON
            formatted.append(json.dumps(analysis, indent=2))
        
        return "\n".join(formatted)
    
    def _display_formatted_analysis(self, text: str):
        """Display formatted analysis in the text widget.
        
        Args:
            text: Formatted analysis text
        """
        self.result_text.config(state=NORMAL)
        self.result_text.delete("1.0", END)
        
        # Configure tags for formatting
        self.result_text.tag_configure("heading", font=("Segoe UI", 12, "bold"), spacing3=5)
        self.result_text.tag_configure("warning", foreground="orange", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("error", foreground="red", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("medication", font=("Segoe UI", 11, "bold"))
        self.result_text.tag_configure("detail", foreground="gray", font=("Segoe UI", 10))
        
        # Parse and format the text
        lines = text.split('\n')
        for line in lines:
            if line.upper() == line and line.endswith(':') and line.strip():
                # Heading
                self.result_text.insert(END, line + '\n', "heading")
            elif line.startswith('⚠'):
                # Warning
                self.result_text.insert(END, line + '\n', "warning")
            elif line.startswith('❌'):
                # Error
                self.result_text.insert(END, line + '\n', "error")
            elif line.startswith('•'):
                # Medication or bullet point
                parts = line.split(' ', 1)
                self.result_text.insert(END, parts[0] + ' ')
                if len(parts) > 1:
                    self.result_text.insert(END, parts[1], "medication")
                self.result_text.insert(END, '\n')
            elif line.startswith('  -') or line.startswith('  '):
                # Detail
                self.result_text.insert(END, line + '\n', "detail")
            else:
                # Normal text
                self.result_text.insert(END, line + '\n')
        
        self.result_text.config(state=DISABLED)
    
    def _copy_to_clipboard(self):
        """Copy the analysis to clipboard."""
        try:
            pyperclip.copy(self.analysis_text)
            messagebox.showinfo(
                "Copied",
                "Analysis copied to clipboard!",
                parent=self.parent
            )
        except Exception as e:
            logging.error(f"Error copying to clipboard: {str(e)}")
            messagebox.showerror(
                "Error",
                f"Failed to copy to clipboard: {str(e)}",
                parent=self.parent
            )
    
    def _add_to_document(self, doc_type: str):
        """Add the analysis to a document (SOAP note or letter).
        
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
                new_content = f"{current_content}\n\n--- Medication Analysis ---\n\n{self.analysis_text}"
            else:
                new_content = f"--- Medication Analysis ---\n\n{self.analysis_text}"
            
            # Update the text widget
            target_widget.delete("1.0", END)
            target_widget.insert("1.0", new_content)
            
            # Switch to the appropriate tab
            if doc_type == "soap":
                self.parent.notebook.select(1)  # SOAP tab
            else:
                self.parent.notebook.select(3)  # Letter tab
            
            messagebox.showinfo(
                "Added",
                f"Analysis added to {doc_name}!",
                parent=self.parent
            )
            
        except Exception as e:
            logging.error(f"Error adding to document: {str(e)}")
            messagebox.showerror(
                "Error",
                f"Failed to add to document: {str(e)}",
                parent=self.parent
            )