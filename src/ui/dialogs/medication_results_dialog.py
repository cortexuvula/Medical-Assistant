"""
Medication Results Dialog

Displays the results of medication analysis in a formatted, user-friendly dialog.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT, NORMAL, DISABLED, WORD, END
from tkinter import messagebox, filedialog
import pyperclip
import logging
from typing import Dict, Any, Optional
import json
import os
from utils.pdf_exporter import PDFExporter
from database.database import Database


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
        self.analysis_data = None
        self.analysis_type = ""
        self.source = ""
        self.metadata = {}
        self.recording_id: Optional[int] = None
        self.patient_context: Optional[Dict[str, Any]] = None
        self.source_text: str = ""
        self.dialog: Optional[tk.Toplevel] = None
        self._db: Optional[Database] = None
        
    def show_results(
        self,
        analysis: Any,
        analysis_type: str,
        source: str,
        metadata: Dict,
        recording_id: Optional[int] = None,
        patient_context: Optional[Dict[str, Any]] = None,
        source_text: str = ""
    ):
        """Show the medication analysis results.

        Args:
            analysis: The medication analysis results (dict or string)
            analysis_type: Type of analysis performed
            source: Source of the analysis (Transcript, SOAP Note, Custom Input)
            metadata: Additional metadata from the analysis
            recording_id: Optional recording ID to link analysis to
            patient_context: Optional patient context used for analysis
            source_text: Original text that was analyzed
        """
        # Store additional context for saving
        self.recording_id = recording_id
        self.patient_context = patient_context
        self.source_text = source_text
        # Store data for potential export
        self.analysis_data = analysis if isinstance(analysis, dict) else {"analysis": analysis}
        self.analysis_type = analysis_type
        self.source = source
        self.metadata = metadata
        
        # Convert analysis to string if it's a dict
        if isinstance(analysis, dict):
            self.analysis_text = self._format_analysis_dict(analysis, analysis_type)
        else:
            self.analysis_text = str(analysis)
        
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        dialog = self.dialog
        dialog.title("Medication Analysis Results")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(950, 750)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        dialog.minsize(900, 700)  # Set minimum size
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
            text="Add to Letter",
            command=lambda: self._add_to_document("letter"),
            bootstyle="primary",
            width=18
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
        """Display formatted analysis in the text widget with severity highlighting.

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

        # Severity color tags for drug interactions
        self.result_text.tag_configure(
            "severity_contraindicated",
            foreground="white",
            background="#dc3545",  # Red
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "severity_major",
            foreground="black",
            background="#fd7e14",  # Orange
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "severity_moderate",
            foreground="black",
            background="#ffc107",  # Yellow
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "severity_minor",
            foreground="white",
            background="#28a745",  # Green
            font=("Segoe UI", 11)
        )
        self.result_text.tag_configure(
            "allergy_warning",
            foreground="white",
            background="#dc3545",  # Red
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "renal_warning",
            foreground="black",
            background="#17a2b8",  # Teal/Info
            font=("Segoe UI", 11, "bold")
        )
        self.result_text.tag_configure(
            "hepatic_warning",
            foreground="white",
            background="#6f42c1",  # Purple
            font=("Segoe UI", 11, "bold")
        )

        # Parse and format the text
        lines = text.split('\n')
        for line in lines:
            line_lower = line.lower()

            # Check for severity indicators in the line
            severity_tag = self._detect_severity_tag(line_lower)

            if line.upper() == line and line.endswith(':') and line.strip():
                # Heading
                self.result_text.insert(END, line + '\n', "heading")
            elif severity_tag:
                # Line contains severity indicator - apply colored tag
                self.result_text.insert(END, line + '\n', severity_tag)
            elif line.startswith('⚠') or "warning" in line_lower:
                # Warning
                self.result_text.insert(END, line + '\n', "warning")
            elif line.startswith('❌') or "contraindicated" in line_lower:
                # Error/Contraindicated
                self.result_text.insert(END, line + '\n', "severity_contraindicated")
            elif "allergy" in line_lower or "allergic" in line_lower:
                # Allergy warning
                self.result_text.insert(END, line + '\n', "allergy_warning")
            elif "renal" in line_lower or "kidney" in line_lower or "egfr" in line_lower:
                # Renal-related
                self.result_text.insert(END, line + '\n', "renal_warning")
            elif "hepatic" in line_lower or "liver" in line_lower or "child-pugh" in line_lower:
                # Hepatic-related
                self.result_text.insert(END, line + '\n', "hepatic_warning")
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

    def _detect_severity_tag(self, line: str) -> str:
        """
        Detect severity level in a line and return appropriate tag.

        Args:
            line: Lowercase line text

        Returns:
            Tag name for severity coloring, or empty string if none detected
        """
        # Severity keywords in order of precedence
        if "contraindicated" in line or "do not use" in line:
            return "severity_contraindicated"
        elif "major" in line and ("interaction" in line or "severity" in line):
            return "severity_major"
        elif "serious" in line and "interaction" in line:
            return "severity_major"
        elif "moderate" in line and ("interaction" in line or "severity" in line):
            return "severity_moderate"
        elif "minor" in line and ("interaction" in line or "severity" in line):
            return "severity_minor"
        elif "severity:" in line:
            # Check what follows "severity:"
            if "contraindicated" in line:
                return "severity_contraindicated"
            elif "major" in line or "serious" in line:
                return "severity_major"
            elif "moderate" in line:
                return "severity_moderate"
            elif "minor" in line or "minimal" in line:
                return "severity_minor"
        return ""
    
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
    
    def _export_to_pdf(self):
        """Export the medication analysis to PDF."""
        try:
            # Get default filename
            default_filename = f"medication_{self.analysis_type}_report.pdf"
            
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.parent,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Medication Report as PDF"
            )
            
            if not file_path:
                return
            
            # Create PDF exporter
            pdf_exporter = PDFExporter()
            
            # Prepare medication data for PDF
            medication_data = {
                "medications": [],
                "interactions": [],
                "warnings": [],
                "recommendations": ""
            }
            
            # Extract data based on analysis type and structure
            if isinstance(self.analysis_data, dict):
                # Extract medications
                if "medications" in self.analysis_data:
                    medication_data["medications"] = self.analysis_data["medications"]
                elif "extracted_medications" in self.analysis_data:
                    medication_data["medications"] = self.analysis_data["extracted_medications"]
                
                # Extract interactions
                if "interactions" in self.analysis_data:
                    medication_data["interactions"] = self.analysis_data["interactions"]
                elif "drug_interactions" in self.analysis_data:
                    medication_data["interactions"] = self.analysis_data["drug_interactions"]
                
                # Extract warnings
                if "warnings" in self.analysis_data:
                    medication_data["warnings"] = self.analysis_data["warnings"]
                elif "alerts" in self.analysis_data:
                    medication_data["warnings"] = self.analysis_data["alerts"]
                
                # Extract recommendations
                if "recommendations" in self.analysis_data:
                    medication_data["recommendations"] = self.analysis_data["recommendations"]
                elif "suggestions" in self.analysis_data:
                    medication_data["recommendations"] = self.analysis_data["suggestions"]
            
            # If data is not properly structured, use the formatted text
            if not any(medication_data.values()):
                medication_data["recommendations"] = self.analysis_text
            
            # Add metadata to the data
            medication_data.update(self.metadata)
            
            # Generate PDF
            success = pdf_exporter.generate_medication_report_pdf(
                medication_data,
                file_path,
                self.analysis_type
            )
            
            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Medication report exported to:\n{file_path}",
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
            logging.error(f"Error exporting to PDF: {str(e)}")
            messagebox.showerror(
                "Export Error",
                f"Failed to export PDF: {str(e)}",
                parent=self.parent
            )

    def _get_database(self) -> Database:
        """Get or create database connection."""
        if self._db is None:
            self._db = Database()
        return self._db

    def _save_to_database(self):
        """Save the medication analysis to the database."""
        try:
            db = self._get_database()

            # Prepare result JSON
            result_json = None
            if isinstance(self.analysis_data, dict):
                result_json = json.dumps(self.analysis_data)

            # Prepare metadata JSON
            metadata_json = json.dumps(self.metadata) if self.metadata else None

            # Prepare patient context JSON
            patient_context_json = None
            if self.patient_context:
                patient_context_json = json.dumps(self.patient_context)

            # Save to database
            analysis_id = db.save_analysis_result(
                analysis_type="medication",
                result_text=self.analysis_text,
                recording_id=self.recording_id,
                analysis_subtype=self.analysis_type,
                result_json=result_json,
                metadata_json=metadata_json,
                patient_context_json=patient_context_json,
                source_type=self.source,
                source_text=self.source_text[:5000] if self.source_text else None  # Limit source text
            )

            if analysis_id:
                # Build info message
                info_parts = [f"Medication analysis saved (ID: {analysis_id})"]
                if self.recording_id:
                    info_parts.append(f"Linked to recording #{self.recording_id}")

                messagebox.showinfo(
                    "Saved",
                    "\n".join(info_parts),
                    parent=self.dialog if self.dialog else self.parent
                )
            else:
                messagebox.showerror(
                    "Save Failed",
                    "Failed to save analysis to database.",
                    parent=self.dialog if self.dialog else self.parent
                )

        except Exception as e:
            logging.error(f"Error saving to database: {str(e)}")
            messagebox.showerror(
                "Save Error",
                f"Failed to save to database: {str(e)}",
                parent=self.dialog if self.dialog else self.parent
            )