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
import re
from datetime import datetime
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

        # Display average confidence if available
        avg_confidence = metadata.get('average_confidence')
        if avg_confidence is not None:
            confidence_pct = int(avg_confidence * 100)
            conf_color = "green" if confidence_pct >= 70 else ("orange" if confidence_pct >= 40 else "gray")
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

        # Prominent Red Flags Panel (if red flags present)
        red_flags_list = metadata.get('red_flags_list', [])
        if not red_flags_list:
            # Try to extract from analysis text
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
            if inv.get('investigation_name', '').strip() and len(inv.get('investigation_name', '').strip()) >= 5
        ]

        if valid_investigations:
            self._create_investigations_panel(main_frame, valid_investigations)

        # Periodic Analysis Link (if available)
        periodic_session_id = metadata.get('periodic_session_id')
        if periodic_session_id or (recording_id and self._has_periodic_analyses(recording_id)):
            self._create_periodic_analysis_panel(main_frame, recording_id, periodic_session_id)

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
            text="💡 FHIR export for EHR integration",
            font=("Segoe UI", 9),
            foreground="gray"
        ).pack(side=LEFT, padx=(10, 0))
        
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
        self.result_text.tag_configure("icd_code", foreground="blue", font=("Segoe UI", 10, "italic"))
        self.result_text.tag_configure("confidence_high", foreground="green", font=("Segoe UI", 10, "bold"))
        self.result_text.tag_configure("confidence_medium", foreground="orange", font=("Segoe UI", 10, "bold"))
        self.result_text.tag_configure("confidence_low", foreground="gray", font=("Segoe UI", 10, "bold"))

        # Combined ICD pattern: ICD-10 (e.g., J18.9, K21.0) and ICD-9 (e.g., 486.0, 530.81)
        icd_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b|\b\d{3}\.\d{1,2}\b'
        # Confidence pattern
        confidence_pattern = r'\[(HIGH|MEDIUM|LOW)\]|\b(HIGH|MEDIUM|LOW)\s*(?:confidence|probability)?\b'

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
                # Look for ICD codes (both ICD-10 and ICD-9 formats)
                has_icd = re.search(icd_pattern, line)
                has_confidence = re.search(confidence_pattern, line, re.IGNORECASE)

                if has_icd or has_confidence:
                    # Split line to highlight ICD codes and confidence levels
                    combined_pattern = f'({icd_pattern})|({confidence_pattern})'
                    parts = re.split(combined_pattern, line)
                    for part in parts:
                        if part is None:
                            continue
                        if re.match(icd_pattern, part):
                            self.result_text.insert(END, part, "icd_code")
                        elif re.match(r'\[?HIGH\]?', part, re.IGNORECASE):
                            self.result_text.insert(END, part, "confidence_high")
                        elif re.match(r'\[?MEDIUM\]?', part, re.IGNORECASE):
                            self.result_text.insert(END, part, "confidence_medium")
                        elif re.match(r'\[?LOW\]?', part, re.IGNORECASE):
                            self.result_text.insert(END, part, "confidence_low")
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
                    # Extract diagnosis name and ICD codes (both ICD-10 and ICD-9)
                    # ICD-10 pattern: letter + 2 digits + optional decimal
                    # ICD-9 pattern: 3 digits + decimal
                    icd10_match = re.search(r'\(([A-Z]\d{2}(?:\.\d{1,2})?)\)', line)
                    icd9_match = re.search(r'\((\d{3}\.\d{1,2})\)', line)

                    icd10_code = icd10_match.group(1) if icd10_match else ""
                    icd9_code = icd9_match.group(1) if icd9_match else ""

                    # Extract confidence level
                    confidence_match = re.search(r'\[(HIGH|MEDIUM|LOW)\]', line, re.IGNORECASE)
                    confidence = confidence_match.group(1).upper() if confidence_match else ""

                    # Extract diagnosis name (before any ICD codes or confidence markers)
                    diag_line = line
                    for pattern in [r'\([A-Z]\d{2}(?:\.\d{1,2})?\)', r'\(\d{3}\.\d{1,2}\)', r'\[(HIGH|MEDIUM|LOW)\]']:
                        diag_line = re.sub(pattern, '', diag_line, flags=re.IGNORECASE)
                    diagnosis = diag_line.strip(" -0123456789.:")

                    data["differentials"].append({
                        "diagnosis": diagnosis,
                        "icd10_code": icd10_code,
                        "icd9_code": icd9_code,
                        "icd_code": icd10_code or icd9_code,  # Backward compatibility
                        "confidence": confidence,
                        "probability": confidence,  # Alias for confidence
                        "evidence": [],
                        "tests": []
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
        """Save the diagnostic analysis to the database, including structured data."""
        try:
            db = self._get_database()

            # Parse structured data from analysis
            parsed_data = self._parse_diagnostic_analysis(self.analysis_text)

            # Prepare metadata dict with ICD validation results if available
            metadata_dict = dict(self.metadata) if self.metadata else {}

            # Save to database
            analysis_id = db.save_analysis_result(
                analysis_type="diagnostic",
                result_text=self.analysis_text,
                recording_id=self.recording_id,
                analysis_subtype="differential",
                result_json=parsed_data,  # Pass dict, not JSON string
                metadata=metadata_dict if metadata_dict else None,
                patient_context=None,  # Diagnostic doesn't have patient context yet
                source_type=self.source,
                source_text=self.source_text[:5000] if self.source_text else None
            )

            if analysis_id:
                saved_items = {'differentials': 0, 'investigations': 0, 'pearls': 0}

                # Save structured differentials if available in metadata
                structured_diffs = self.metadata.get('structured_differentials', [])
                if structured_diffs:
                    saved_items['differentials'] = self._save_structured_differentials(
                        db, analysis_id, structured_diffs
                    )

                # Save structured investigations
                structured_invs = self.metadata.get('structured_investigations', [])
                if structured_invs:
                    saved_items['investigations'] = self._save_structured_investigations(
                        db, analysis_id, structured_invs
                    )

                # Save clinical pearls
                structured_pearls = self.metadata.get('structured_clinical_pearls', [])
                if structured_pearls:
                    saved_items['pearls'] = self._save_clinical_pearls(
                        db, analysis_id, structured_pearls
                    )

                # Save extracted clinical data
                extracted_data = self.metadata.get('extracted_clinical_data')
                if extracted_data:
                    self._save_extracted_clinical_data(db, analysis_id, extracted_data)

                # Build info message
                info_parts = [f"Diagnostic analysis saved (ID: {analysis_id})"]
                if self.recording_id:
                    info_parts.append(f"Linked to recording #{self.recording_id}")
                diff_count = self.metadata.get('differential_count', 0)
                if diff_count:
                    info_parts.append(f"Contains {diff_count} differential diagnoses")
                if saved_items['differentials'] > 0:
                    info_parts.append(f"Saved {saved_items['differentials']} structured differentials")
                if saved_items['investigations'] > 0:
                    info_parts.append(f"Saved {saved_items['investigations']} investigations")

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

    def _save_structured_differentials(
        self, db: Database, analysis_id: int, differentials: List[Dict]
    ) -> int:
        """Save structured differential diagnoses to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            differentials: List of structured differential dictionaries

        Returns:
            Number of differentials saved
        """
        saved_count = 0
        try:
            conn = db._get_connection()
            for diff in differentials:
                conn.execute(
                    """
                    INSERT INTO differential_diagnoses (
                        analysis_id, rank, diagnosis_name, icd10_code, icd9_code,
                        confidence_score, confidence_level, reasoning,
                        supporting_findings, against_findings, is_red_flag
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        diff.get('rank', 0),
                        diff.get('diagnosis_name', ''),
                        diff.get('icd10_code'),
                        diff.get('icd9_code'),
                        diff.get('confidence_score'),
                        diff.get('confidence_level'),
                        diff.get('reasoning', ''),
                        json.dumps(diff.get('supporting_findings', [])),
                        json.dumps(diff.get('against_findings', [])),
                        diff.get('is_red_flag', False)
                    )
                )
                saved_count += 1
            conn.commit()
        except Exception as e:
            logging.warning(f"Error saving structured differentials: {e}")
        return saved_count

    def _save_structured_investigations(
        self, db: Database, analysis_id: int, investigations: List[Dict]
    ) -> int:
        """Save recommended investigations to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            investigations: List of investigation dictionaries

        Returns:
            Number of investigations saved
        """
        saved_count = 0
        try:
            conn = db._get_connection()
            for inv in investigations:
                conn.execute(
                    """
                    INSERT INTO recommended_investigations (
                        analysis_id, investigation_name, investigation_type,
                        priority, rationale, status
                    ) VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        analysis_id,
                        inv.get('investigation_name', ''),
                        inv.get('investigation_type', 'other'),
                        inv.get('priority', 'routine'),
                        inv.get('rationale', ''),
                        inv.get('status', 'pending')
                    )
                )
                saved_count += 1
            conn.commit()
        except Exception as e:
            logging.warning(f"Error saving investigations: {e}")
        return saved_count

    def _save_clinical_pearls(
        self, db: Database, analysis_id: int, pearls: List[Dict]
    ) -> int:
        """Save clinical pearls to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            pearls: List of clinical pearl dictionaries

        Returns:
            Number of pearls saved
        """
        saved_count = 0
        try:
            conn = db._get_connection()
            for pearl in pearls:
                conn.execute(
                    """
                    INSERT INTO clinical_pearls (
                        analysis_id, pearl_text, category
                    ) VALUES (?, ?, ?)
                    """,
                    (
                        analysis_id,
                        pearl.get('pearl_text', ''),
                        pearl.get('category', 'diagnostic')
                    )
                )
                saved_count += 1
            conn.commit()
        except Exception as e:
            logging.warning(f"Error saving clinical pearls: {e}")
        return saved_count

    def _save_extracted_clinical_data(
        self, db: Database, analysis_id: int, extracted_data: Dict
    ):
        """Save extracted clinical data to database.

        Args:
            db: Database connection
            analysis_id: ID of the parent analysis
            extracted_data: Dictionary of extracted clinical data
        """
        try:
            conn = db._get_connection()
            for data_type, data in extracted_data.items():
                if data:  # Only save non-empty data
                    conn.execute(
                        """
                        INSERT INTO extracted_clinical_data (
                            analysis_id, data_type, data_json
                        ) VALUES (?, ?, ?)
                        """,
                        (analysis_id, data_type, json.dumps(data))
                    )
            conn.commit()
        except Exception as e:
            logging.warning(f"Error saving extracted clinical data: {e}")

    def _extract_icd_codes(self) -> Dict[str, List[str]]:
        """Extract all ICD codes from the analysis text.

        Returns:
            Dictionary with 'icd10' and 'icd9' lists of codes
        """
        # ICD-10 pattern: letter + 2 digits + optional decimal (e.g., J18.9, K21.0)
        icd10_pattern = r'\b[A-Z]\d{2}(?:\.\d{1,2})?\b'
        # ICD-9 pattern: 3 digits + decimal (e.g., 486.0, 530.81)
        icd9_pattern = r'\b\d{3}\.\d{1,2}\b'

        icd10_codes = list(set(re.findall(icd10_pattern, self.analysis_text)))
        icd9_codes = list(set(re.findall(icd9_pattern, self.analysis_text)))

        return {
            'icd10': sorted(icd10_codes),
            'icd9': sorted(icd9_codes)
        }

    def _copy_icd_codes(self):
        """Copy only the ICD codes to clipboard."""
        try:
            codes = self._extract_icd_codes()
            icd10_codes = codes['icd10']
            icd9_codes = codes['icd9']

            if not icd10_codes and not icd9_codes:
                messagebox.showinfo(
                    "No ICD Codes",
                    "No ICD codes found in the analysis.",
                    parent=self.dialog if self.dialog else self.parent
                )
                return

            # Format the codes for copying
            output_lines = []
            if icd10_codes:
                output_lines.append("ICD-10 Codes:")
                output_lines.extend([f"  {code}" for code in icd10_codes])
            if icd9_codes:
                if output_lines:
                    output_lines.append("")
                output_lines.append("ICD-9 Codes:")
                output_lines.extend([f"  {code}" for code in icd9_codes])

            # Also add a comma-separated list for easy pasting
            output_lines.append("")
            output_lines.append("Combined (comma-separated):")
            all_codes = icd10_codes + icd9_codes
            output_lines.append(", ".join(all_codes))

            output = "\n".join(output_lines)
            pyperclip.copy(output)

            total_count = len(icd10_codes) + len(icd9_codes)
            messagebox.showinfo(
                "Copied",
                f"Copied {total_count} ICD codes to clipboard!\n\n"
                f"ICD-10: {len(icd10_codes)} codes\n"
                f"ICD-9: {len(icd9_codes)} codes",
                parent=self.dialog if self.dialog else self.parent
            )

        except Exception as e:
            logging.error(f"Error copying ICD codes: {str(e)}")
            messagebox.showerror(
                "Error",
                f"Failed to copy ICD codes: {str(e)}",
                parent=self.dialog if self.dialog else self.parent
            )

    def _export_to_fhir(self):
        """Export the diagnostic analysis as a FHIR DiagnosticReport resource."""
        try:
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog if self.dialog else self.parent,
                defaultextension=".json",
                filetypes=[
                    ("FHIR JSON", "*.json"),
                    ("All files", "*.*")
                ],
                initialfile="diagnostic_report_fhir.json",
                title="Export FHIR DiagnosticReport"
            )

            if not file_path:
                return

            # Parse the analysis
            parsed_data = self._parse_diagnostic_analysis(self.analysis_text)
            codes = self._extract_icd_codes()

            # Build FHIR DiagnosticReport resource
            fhir_resource = self._build_fhir_diagnostic_report(parsed_data, codes)

            # Write to file with pretty formatting
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(fhir_resource, f, indent=2, ensure_ascii=False)

            messagebox.showinfo(
                "Export Successful",
                f"FHIR DiagnosticReport exported to:\n{file_path}\n\n"
                f"Resource contains {len(parsed_data.get('differentials', []))} diagnoses.",
                parent=self.dialog if self.dialog else self.parent
            )

            # Optionally open the file
            if messagebox.askyesno(
                "Open File",
                "Would you like to open the exported file?",
                parent=self.dialog if self.dialog else self.parent
            ):
                import subprocess
                import platform

                if platform.system() == 'Darwin':
                    subprocess.call(('open', file_path))
                elif platform.system() == 'Windows':
                    os.startfile(file_path)
                else:
                    subprocess.call(('xdg-open', file_path))

        except Exception as e:
            logging.error(f"Error exporting to FHIR: {str(e)}")
            messagebox.showerror(
                "Export Error",
                f"Failed to export FHIR resource: {str(e)}",
                parent=self.dialog if self.dialog else self.parent
            )

    def _build_fhir_diagnostic_report(self, parsed_data: Dict, codes: Dict) -> Dict:
        """Build a FHIR R4 DiagnosticReport resource.

        Args:
            parsed_data: Parsed diagnostic analysis data
            codes: Extracted ICD codes

        Returns:
            FHIR DiagnosticReport resource as dictionary
        """
        import uuid

        # Generate unique identifier
        report_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        # Build coded diagnoses
        coded_diagnoses = []
        for diff in parsed_data.get('differentials', []):
            coding = []
            if diff.get('icd10_code'):
                coding.append({
                    "system": "http://hl7.org/fhir/sid/icd-10",
                    "code": diff['icd10_code'],
                    "display": diff.get('diagnosis', '')
                })
            if diff.get('icd9_code'):
                coding.append({
                    "system": "http://hl7.org/fhir/sid/icd-9-cm",
                    "code": diff['icd9_code'],
                    "display": diff.get('diagnosis', '')
                })

            if coding:
                coded_diagnoses.append({
                    "code": {
                        "coding": coding,
                        "text": diff.get('diagnosis', '')
                    }
                })

        # Build the FHIR DiagnosticReport resource
        fhir_report = {
            "resourceType": "DiagnosticReport",
            "id": report_id,
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/DiagnosticReport"]
            },
            "identifier": [{
                "system": "urn:medical-assistant:diagnostic-report",
                "value": report_id
            }],
            "status": "final",
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/v2-0074",
                    "code": "OTH",
                    "display": "Other"
                }],
                "text": "Diagnostic Analysis"
            }],
            "code": {
                "coding": [{
                    "system": "http://loinc.org",
                    "code": "51847-2",
                    "display": "Evaluation + Plan note"
                }],
                "text": "Differential Diagnosis Analysis"
            },
            "effectiveDateTime": timestamp,
            "issued": timestamp,
            "conclusion": parsed_data.get('clinical_findings', ''),
            "conclusionCode": coded_diagnoses
        }

        # Add clinical findings as presentedForm (text attachment)
        if self.analysis_text:
            fhir_report["presentedForm"] = [{
                "contentType": "text/plain",
                "data": self._base64_encode(self.analysis_text),
                "title": "Diagnostic Analysis Report"
            }]

        # Add source information as extension
        source_info = {
            "source": self.source,
            "provider": self.metadata.get('provider', ''),
            "model": self.metadata.get('model', ''),
            "specialty": self.metadata.get('specialty', ''),
            "differential_count": self.metadata.get('differential_count', 0),
            "has_red_flags": self.metadata.get('has_red_flags', False)
        }

        fhir_report["extension"] = [{
            "url": "http://medical-assistant.local/fhir/extensions/analysis-metadata",
            "valueString": json.dumps(source_info)
        }]

        # Add red flags as extension if present
        if parsed_data.get('red_flags'):
            fhir_report["extension"].append({
                "url": "http://medical-assistant.local/fhir/extensions/red-flags",
                "valueString": json.dumps(parsed_data['red_flags'])
            })

        # Add recommended investigations as extension
        if parsed_data.get('investigations'):
            fhir_report["extension"].append({
                "url": "http://medical-assistant.local/fhir/extensions/recommended-investigations",
                "valueString": json.dumps(parsed_data['investigations'])
            })

        return fhir_report

    def _base64_encode(self, text: str) -> str:
        """Base64 encode text for FHIR attachment.

        Args:
            text: Text to encode

        Returns:
            Base64 encoded string
        """
        import base64
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')

    def _extract_red_flags_from_text(self, analysis: str) -> List[str]:
        """Extract red flags from analysis text.

        Args:
            analysis: The analysis text

        Returns:
            List of red flag strings
        """
        red_flags = []
        if 'RED FLAGS:' not in analysis:
            return red_flags

        try:
            red_section = analysis.split('RED FLAGS:')[1]
            # Find the end of the section
            for end_marker in ['RECOMMENDED INVESTIGATIONS:', 'CLINICAL PEARLS:',
                               'MEDICATION CONSIDERATIONS:', '\n\n\n']:
                if end_marker in red_section:
                    red_section = red_section.split(end_marker)[0]
                    break

            # Parse each line
            for line in red_section.split('\n'):
                line = line.strip()
                if line and line not in ['None', '-', 'N/A', '']:
                    # Remove bullet points and numbers
                    cleaned = re.sub(r'^[\d\.\-\•\*]+\s*', '', line).strip()
                    if cleaned and len(cleaned) > 3:
                        red_flags.append(cleaned)
        except Exception as e:
            logging.warning(f"Error extracting red flags: {e}")

        return red_flags

    def _extract_investigations_from_text(self, analysis: str) -> List[Dict[str, Any]]:
        """Extract recommended investigations from analysis text.

        Args:
            analysis: The analysis text

        Returns:
            List of investigation dictionaries
        """
        investigations = []
        if 'RECOMMENDED INVESTIGATIONS:' not in analysis:
            return investigations

        try:
            inv_section = analysis.split('RECOMMENDED INVESTIGATIONS:')[1]
            # Find the end of the section
            for end_marker in ['CLINICAL PEARLS:', 'MEDICATION CONSIDERATIONS:', '\n\n\n']:
                if end_marker in inv_section:
                    inv_section = inv_section.split(end_marker)[0]
                    break

            # Parse each line
            for line in inv_section.split('\n'):
                line = line.strip()
                # Skip empty lines and common non-content markers
                if not line or line in ['None', '-', 'N/A', '', 'o', 'O', '•', '*']:
                    continue

                # Remove bullet points, numbers, and common list markers
                # Extended pattern: digits, dots, dashes, bullets, asterisks, 'o'/'O' as bullets
                cleaned = re.sub(r'^[\d\.\-\•\*oO]+[\.\)\:\s]*', '', line).strip()

                # Skip if cleaned text is empty, too short, or just punctuation/whitespace
                if not cleaned or len(cleaned) < 5:
                    continue

                # Skip lines that are just markers or don't contain alphabetic content
                if not any(c.isalpha() for c in cleaned):
                    continue

                # Determine priority based on keywords
                priority = 'routine'
                if any(kw in cleaned.lower() for kw in ['urgent', 'stat', 'immediately', 'emergent']):
                    priority = 'urgent'
                elif any(kw in cleaned.lower() for kw in ['priority', 'soon', 'within 24']):
                    priority = 'high'

                investigations.append({
                    'investigation_name': cleaned,
                    'priority': priority,
                    'status': 'pending',
                    'rationale': ''
                })
        except Exception as e:
            logging.warning(f"Error extracting investigations: {e}")

        return investigations

    def _create_red_flags_panel(self, parent: ttk.Frame, red_flags: List[str]) -> None:
        """Create a prominent red flags panel with visual emphasis.

        Args:
            parent: Parent frame
            red_flags: List of red flag strings
        """
        # Create collapsible red flags panel
        red_frame = ttk.Frame(parent)
        red_frame.pack(fill=X, pady=(0, 10))

        # Header with warning icon and count
        header_frame = ttk.Frame(red_frame)
        header_frame.pack(fill=X)

        # Use a styled label for the header
        style = ttk.Style()
        try:
            style.configure('RedFlag.TLabel', foreground='white', background='#dc3545',
                          font=('Segoe UI', 11, 'bold'))
        except Exception:
            pass

        header_label = ttk.Label(
            header_frame,
            text=f"  ⚠️ RED FLAGS ({len(red_flags)}) - URGENT ATTENTION REQUIRED  ",
            font=("Segoe UI", 11, "bold"),
            foreground="white",
            background="#dc3545"
        )
        header_label.pack(side=LEFT, fill=X, expand=True, ipady=5)

        # Content frame with red border effect
        content_frame = ttk.Frame(red_frame, padding=10)
        content_frame.pack(fill=X)

        # Add each red flag with icon
        for i, flag in enumerate(red_flags[:10], 1):  # Limit to 10 flags
            flag_frame = ttk.Frame(content_frame)
            flag_frame.pack(fill=X, pady=2)

            # Warning icon and text
            ttk.Label(
                flag_frame,
                text="⚠️",
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 5))

            ttk.Label(
                flag_frame,
                text=flag,
                font=("Segoe UI", 10, "bold"),
                foreground="#dc3545",
                wraplength=700
            ).pack(side=LEFT, fill=X, expand=True)

        if len(red_flags) > 10:
            ttk.Label(
                content_frame,
                text=f"... and {len(red_flags) - 10} more red flags",
                font=("Segoe UI", 9, "italic"),
                foreground="gray"
            ).pack(anchor=W, pady=(5, 0))

    def _create_investigations_panel(
        self, parent: ttk.Frame, investigations: List[Dict[str, Any]]
    ) -> None:
        """Create an interactive investigations tracking panel.

        Args:
            parent: Parent frame
            investigations: List of investigation dictionaries
        """
        # Store investigation vars for later access
        self.investigation_vars = {}

        # Create collapsible investigations panel
        inv_frame = ttk.Labelframe(
            parent,
            text=f"📋 Recommended Investigations ({len(investigations)})",
            padding=10
        )
        inv_frame.pack(fill=X, pady=(0, 10))

        # Instructions
        ttk.Label(
            inv_frame,
            text="Check off completed investigations:",
            font=("Segoe UI", 9, "italic"),
            foreground="gray"
        ).pack(anchor=W, pady=(0, 5))

        # Scrollable frame for many investigations
        inv_canvas = tk.Canvas(inv_frame, height=150)
        inv_scrollbar = ttk.Scrollbar(inv_frame, orient=VERTICAL, command=inv_canvas.yview)
        inv_content = ttk.Frame(inv_canvas)

        inv_content.bind(
            "<Configure>",
            lambda e: inv_canvas.configure(scrollregion=inv_canvas.bbox("all"))
        )

        inv_canvas.create_window((0, 0), window=inv_content, anchor="nw")
        inv_canvas.configure(yscrollcommand=inv_scrollbar.set)

        inv_canvas.pack(side=LEFT, fill=BOTH, expand=True)
        inv_scrollbar.pack(side=RIGHT, fill=Y)

        # Priority colors
        priority_colors = {
            'urgent': '#dc3545',
            'high': '#fd7e14',
            'routine': '#6c757d'
        }

        priority_icons = {
            'urgent': '🔴',
            'high': '🟠',
            'routine': '⚪'
        }

        # Filter out investigations with empty or invalid names
        valid_investigations = [
            inv for inv in investigations
            if inv.get('investigation_name', '').strip() and len(inv.get('investigation_name', '').strip()) >= 5
        ]

        # Update the panel title with correct count
        inv_frame.config(text=f"📋 Recommended Investigations ({len(valid_investigations)})")

        # Add each investigation with checkbox
        for i, inv in enumerate(valid_investigations[:20]):  # Limit to 20
            inv_row = ttk.Frame(inv_content)
            inv_row.pack(fill=X, pady=2)

            # Checkbox variable
            var = tk.BooleanVar(value=inv.get('status') == 'completed')
            self.investigation_vars[i] = {
                'var': var,
                'investigation': inv
            }

            # Priority icon
            priority = inv.get('priority', 'routine')
            ttk.Label(
                inv_row,
                text=priority_icons.get(priority, '⚪'),
                font=("Segoe UI", 10)
            ).pack(side=LEFT, padx=(0, 5))

            # Checkbox with investigation name
            cb = ttk.Checkbutton(
                inv_row,
                text=inv.get('investigation_name', 'Unknown'),
                variable=var,
                command=lambda idx=i: self._on_investigation_toggle(idx)
            )
            cb.pack(side=LEFT, fill=X, expand=True)

            # Priority label
            ttk.Label(
                inv_row,
                text=f"[{priority.upper()}]",
                font=("Segoe UI", 8),
                foreground=priority_colors.get(priority, 'gray')
            ).pack(side=RIGHT, padx=5)

        if len(valid_investigations) > 20:
            ttk.Label(
                inv_content,
                text=f"... and {len(valid_investigations) - 20} more investigations",
                font=("Segoe UI", 9, "italic"),
                foreground="gray"
            ).pack(anchor=W, pady=(5, 0))

        # Summary bar
        summary_frame = ttk.Frame(inv_frame)
        summary_frame.pack(fill=X, pady=(10, 0))

        self.inv_summary_label = ttk.Label(
            summary_frame,
            text="0 of {} completed".format(len(valid_investigations)),
            font=("Segoe UI", 9)
        )
        self.inv_summary_label.pack(side=LEFT)

        ttk.Button(
            summary_frame,
            text="Update Status in Database",
            command=self._save_investigation_status,
            bootstyle="info-outline",
            width=25
        ).pack(side=RIGHT)

    def _on_investigation_toggle(self, idx: int) -> None:
        """Handle investigation checkbox toggle.

        Args:
            idx: Investigation index
        """
        # Update summary
        completed = sum(1 for v in self.investigation_vars.values() if v['var'].get())
        total = len(self.investigation_vars)
        self.inv_summary_label.config(text=f"{completed} of {total} completed")

    def _save_investigation_status(self) -> None:
        """Save investigation completion status to database."""
        try:
            db = self._get_database()
            updated = 0

            for idx, data in self.investigation_vars.items():
                inv = data['investigation']
                is_completed = data['var'].get()
                status = 'completed' if is_completed else 'pending'

                # Update if has database ID
                if inv.get('id'):
                    db.update_investigation_status(
                        inv['id'],
                        status=status,
                        result_summary=None
                    )
                    updated += 1

            messagebox.showinfo(
                "Updated",
                f"Investigation status updated for {updated} items.",
                parent=self.dialog if self.dialog else self.parent
            )
        except Exception as e:
            logging.error(f"Error saving investigation status: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to save status: {e}",
                parent=self.dialog if self.dialog else self.parent
            )

    def _has_periodic_analyses(self, recording_id: int) -> bool:
        """Check if there are periodic analyses linked to a recording.

        Args:
            recording_id: The recording ID to check

        Returns:
            True if periodic analyses exist
        """
        try:
            db = self._get_database()
            analyses = db.get_recent_analysis_results(
                analysis_type="periodic",
                limit=100
            )

            return any(a.get('recording_id') == recording_id for a in analyses)
        except Exception:
            return False

    def _create_periodic_analysis_panel(
        self,
        parent: ttk.Frame,
        recording_id: Optional[int],
        session_id: Optional[int]
    ) -> None:
        """Create a panel showing linked periodic analysis evolution.

        Args:
            parent: Parent frame
            recording_id: Recording ID to find linked analyses
            session_id: Specific session ID if known
        """
        # Create collapsible panel
        periodic_frame = ttk.Labelframe(
            parent,
            text="📊 Differential Evolution (Periodic Analysis)",
            padding=10
        )
        periodic_frame.pack(fill=X, pady=(0, 10))

        # Get periodic analyses
        db = self._get_database()
        periodic_analyses = []

        try:
            all_periodic = db.get_recent_analysis_results(
                analysis_type="periodic",
                limit=200
            )

            if recording_id:
                periodic_analyses = [
                    a for a in all_periodic
                    if a.get('recording_id') == recording_id
                    and a.get('analysis_subtype') == 'differential_evolution'
                ]
            elif session_id:
                periodic_analyses = [
                    a for a in all_periodic
                    if a.get('id') == session_id
                ]
        except Exception as e:
            logging.error(f"Error loading periodic analyses: {e}")

        if not periodic_analyses:
            ttk.Label(
                periodic_frame,
                text="No periodic analysis data available for this recording.",
                font=("Segoe UI", 9, "italic"),
                foreground="gray"
            ).pack(anchor=W)
            return

        # Get the most recent session
        session = periodic_analyses[0]
        metadata = {}
        metadata_raw = session.get('metadata_json')
        if metadata_raw:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        # Summary info
        info_frame = ttk.Frame(periodic_frame)
        info_frame.pack(fill=X, pady=(0, 5))

        total_analyses = metadata.get('total_analyses', 0)
        duration = metadata.get('total_duration_seconds', 0)
        duration_str = f"{int(duration // 60)}:{int(duration % 60):02d}"

        ttk.Label(
            info_frame,
            text=f"📈 {total_analyses} periodic analyses over {duration_str}",
            font=("Segoe UI", 10, "bold")
        ).pack(side=LEFT)

        # View full evolution button
        ttk.Button(
            info_frame,
            text="View Full Evolution",
            command=lambda: self._show_periodic_evolution(session),
            bootstyle="info-outline",
            width=18
        ).pack(side=RIGHT)

        # Individual analysis timeline (condensed)
        individual = metadata.get('individual_analyses', [])
        if individual:
            timeline_frame = ttk.Frame(periodic_frame)
            timeline_frame.pack(fill=X, pady=(5, 0))

            for i, analysis in enumerate(individual[:5]):
                elapsed = analysis.get('elapsed_seconds', 0)
                time_str = f"{int(elapsed // 60)}:{int(elapsed % 60):02d}"
                diff_count = analysis.get('differential_count', 0)

                ttk.Label(
                    timeline_frame,
                    text=f"#{analysis.get('analysis_number', i+1)} ({time_str}): {diff_count} differentials",
                    font=("Segoe UI", 9)
                ).pack(anchor=W)

            if len(individual) > 5:
                ttk.Label(
                    timeline_frame,
                    text=f"... and {len(individual) - 5} more snapshots",
                    font=("Segoe UI", 8, "italic"),
                    foreground="gray"
                ).pack(anchor=W)

    def _show_periodic_evolution(self, session: Dict) -> None:
        """Show full periodic analysis evolution in a dialog.

        Args:
            session: The periodic session data
        """
        evolution_dialog = tk.Toplevel(self.dialog or self.parent)
        evolution_dialog.title("Differential Evolution Timeline")
        evolution_dialog.geometry("800x600")
        evolution_dialog.transient(self.dialog or self.parent)

        # Main frame
        main = ttk.Frame(evolution_dialog, padding=15)
        main.pack(fill=BOTH, expand=True)

        # Header
        ttk.Label(
            main,
            text="Differential Diagnosis Evolution Over Time",
            font=("Segoe UI", 14, "bold")
        ).pack(anchor=W, pady=(0, 10))

        # Metadata
        metadata = {}
        metadata_raw = session.get('metadata_json')
        if metadata_raw:
            if isinstance(metadata_raw, dict):
                metadata = metadata_raw
            elif isinstance(metadata_raw, str):
                try:
                    metadata = json.loads(metadata_raw)
                except (json.JSONDecodeError, TypeError):
                    pass

        info_frame = ttk.Frame(main)
        info_frame.pack(fill=X, pady=(0, 10))

        total = metadata.get('total_analyses', 0)
        start = metadata.get('session_start', 'Unknown')[:19] if metadata.get('session_start') else 'Unknown'
        end = metadata.get('session_end', 'Unknown')[:19] if metadata.get('session_end') else 'Unknown'

        ttk.Label(info_frame, text=f"Total Snapshots: {total}").pack(side=LEFT, padx=(0, 20))
        ttk.Label(info_frame, text=f"Start: {start}").pack(side=LEFT, padx=(0, 20))
        ttk.Label(info_frame, text=f"End: {end}").pack(side=LEFT)

        # Content - full evolution text
        text_frame = ttk.Frame(main)
        text_frame.pack(fill=BOTH, expand=True, pady=(0, 10))

        text = tk.Text(
            text_frame,
            wrap=WORD,
            font=("Segoe UI", 10),
            padx=10,
            pady=10
        )
        text.pack(side=LEFT, fill=BOTH, expand=True)

        scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=text.yview)
        scrollbar.pack(side=RIGHT, fill=Y)
        text.config(yscrollcommand=scrollbar.set)

        # Insert the evolution text with formatting
        result_text = session.get('result_text', 'No evolution data available.')

        # Configure tags for formatting
        text.tag_configure("header", font=("Segoe UI", 11, "bold"), foreground="#0d6efd")
        text.tag_configure("new", foreground="green", font=("Segoe UI", 10, "bold"))
        text.tag_configure("removed", foreground="red", font=("Segoe UI", 10))
        text.tag_configure("separator", foreground="gray")

        # Parse and format the text
        for line in result_text.split('\n'):
            if line.startswith('Analysis #') or 'recording time:' in line:
                text.insert(END, line + '\n', "header")
            elif '📈 NEW' in line or '✨ NEW' in line or '🆕' in line:
                text.insert(END, line + '\n', "new")
            elif '❌ REMOVED' in line or '🔻' in line:
                text.insert(END, line + '\n', "removed")
            elif line.strip().startswith('─'):
                text.insert(END, line + '\n', "separator")
            else:
                text.insert(END, line + '\n')

        text.config(state=DISABLED)

        # Buttons
        button_frame = ttk.Frame(main)
        button_frame.pack(fill=X)

        ttk.Button(
            button_frame,
            text="Copy to Clipboard",
            command=lambda: self._copy_evolution_text(result_text),
            bootstyle="info-outline",
            width=18
        ).pack(side=LEFT, padx=(0, 5))

        ttk.Button(
            button_frame,
            text="Close",
            command=evolution_dialog.destroy,
            width=15
        ).pack(side=RIGHT)

    def _copy_evolution_text(self, text: str) -> None:
        """Copy evolution text to clipboard.

        Args:
            text: Text to copy
        """
        try:
            pyperclip.copy(text)
            messagebox.showinfo(
                "Copied",
                "Evolution text copied to clipboard.",
                parent=self.dialog if self.dialog else self.parent
            )
        except Exception as e:
            logging.error(f"Error copying evolution text: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to copy: {e}",
                parent=self.dialog if self.dialog else self.parent
            )