"""
Diagnostic Results Dialog

Displays the results of diagnostic analysis in a formatted, user-friendly dialog.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from tkinter import messagebox, filedialog
import pyperclip
import logging
from typing import Dict, List, Optional, Any
import json
import os
from utils.pdf_exporter import PDFExporter
from database.database import Database


class DiagnosticResultsDialog:
    """Dialog for displaying diagnostic analysis results."""
    
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
        self._db: Optional[Database] = None
        
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
        dialog.minsize(850, 650)  # Set minimum size
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
    
    def _export_to_pdf(self):
        """Export the diagnostic analysis to PDF."""
        try:
            # Get default filename
            default_filename = "diagnostic_analysis_report.pdf"
            
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.result_text.winfo_toplevel(),
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Diagnostic Report as PDF"
            )
            
            if not file_path:
                return
            
            # Create PDF exporter
            pdf_exporter = PDFExporter()
            
            # Parse the analysis text to extract structured data
            diagnostic_data = self._parse_diagnostic_analysis(self.analysis_text)
            
            # Add metadata
            diagnostic_data.update({
                "source": self.source,
                "analysis_date": self.metadata.get("analysis_date", ""),
                "provider": self.metadata.get("provider", "")
            })
            
            # Generate PDF
            success = pdf_exporter.generate_diagnostic_report_pdf(
                diagnostic_data,
                file_path
            )
            
            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Diagnostic report exported to:\n{file_path}",
                    parent=self.result_text.winfo_toplevel()
                )
                
                # Optionally open the PDF
                if messagebox.askyesno(
                    "Open PDF",
                    "Would you like to open the PDF now?",
                    parent=self.result_text.winfo_toplevel()
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
                    parent=self.result_text.winfo_toplevel()
                )
                
        except Exception as e:
            logging.error(f"Error exporting to PDF: {str(e)}")
            messagebox.showerror(
                "Export Error",
                f"Failed to export PDF: {str(e)}",
                parent=self.result_text.winfo_toplevel()
            )
    
    def _parse_diagnostic_analysis(self, analysis_text: str) -> Dict:
        """Parse diagnostic analysis text into structured data.
        
        Args:
            analysis_text: The raw analysis text
            
        Returns:
            Dictionary with structured diagnostic data
        """
        data = {
            "clinical_findings": "",
            "differentials": [],
            "red_flags": [],
            "investigations": [],
            "clinical_pearls": []
        }
        
        # Split into sections
        lines = analysis_text.split('\n')
        current_section = None
        current_content = []
        
        for line in lines:
            line = line.strip()
            
            # Check for section headers
            if "CLINICAL SUMMARY:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "clinical_findings"
                current_content = []
            elif "DIFFERENTIAL DIAGNOSES:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "differentials"
                current_content = []
            elif "RED FLAGS:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "red_flags"
                current_content = []
            elif "RECOMMENDED INVESTIGATIONS:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "investigations"
                current_content = []
            elif "CLINICAL PEARLS:" in line:
                if current_section and current_content:
                    self._save_section_data(data, current_section, current_content)
                current_section = "clinical_pearls"
                current_content = []
            elif line and current_section:
                current_content.append(line)
        
        # Save last section
        if current_section and current_content:
            self._save_section_data(data, current_section, current_content)
        
        return data
    
    def _save_section_data(self, data: Dict, section: str, content: List[str]):
        """Save parsed section data to the data dictionary.
        
        Args:
            data: Data dictionary to update
            section: Section name
            content: List of content lines
        """
        if section == "clinical_findings":
            data["clinical_findings"] = "\n".join(content)
        elif section == "differentials":
            # Parse differentials with their details
            for line in content:
                if line and (line[0].isdigit() or line.startswith("-")):
                    # Extract diagnosis name and any ICD code
                    import re
                    icd_match = re.search(r'\((\d{3}\.\d{1,2})\)', line)
                    if icd_match:
                        diagnosis = line[:icd_match.start()].strip(" -0123456789.")
                        icd_code = icd_match.group(1)
                    else:
                        diagnosis = line.strip(" -0123456789.")
                        icd_code = ""
                    
                    data["differentials"].append({
                        "diagnosis": diagnosis,
                        "icd_code": icd_code,
                        "probability": "",  # Could be extracted if present
                        "evidence": [],     # Could be enhanced with more parsing
                        "tests": []        # Could be enhanced with more parsing
                    })
        elif section == "red_flags":
            data["red_flags"] = [line.strip("- •") for line in content if line.strip()]
        elif section == "investigations":
            data["investigations"] = [line.strip("- •") for line in content if line.strip()]
        elif section == "clinical_pearls":
            data["clinical_pearls"] = [line.strip("- •") for line in content if line.strip()]

    def _get_database(self) -> Database:
        """Get or create database connection."""
        if self._db is None:
            self._db = Database()
        return self._db

    def _save_to_database(self):
        """Save the diagnostic analysis to the database."""
        try:
            db = self._get_database()

            # Parse structured data from analysis
            parsed_data = self._parse_diagnostic_analysis(self.analysis_text)

            # Prepare result JSON
            result_json = json.dumps(parsed_data)

            # Prepare metadata JSON with ICD validation results if available
            metadata_dict = dict(self.metadata) if self.metadata else {}
            if 'icd_validation_results' in metadata_dict:
                # Already included from agent
                pass
            metadata_json = json.dumps(metadata_dict) if metadata_dict else None

            # Save to database
            analysis_id = db.save_analysis_result(
                analysis_type="diagnostic",
                result_text=self.analysis_text,
                recording_id=self.recording_id,
                analysis_subtype="differential",
                result_json=result_json,
                metadata_json=metadata_json,
                patient_context_json=None,  # Diagnostic doesn't have patient context yet
                source_type=self.source,
                source_text=self.source_text[:5000] if self.source_text else None
            )

            if analysis_id:
                # Build info message
                info_parts = [f"Diagnostic analysis saved (ID: {analysis_id})"]
                if self.recording_id:
                    info_parts.append(f"Linked to recording #{self.recording_id}")
                diff_count = self.metadata.get('differential_count', 0)
                if diff_count:
                    info_parts.append(f"Contains {diff_count} differential diagnoses")

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