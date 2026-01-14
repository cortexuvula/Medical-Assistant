"""
Diagnostic Results Export Module

Provides export functionality for PDF, FHIR, and clipboard operations.
"""

import os
import json
import logging
import base64
from datetime import datetime
from tkinter import messagebox, filedialog
from tkinter.constants import NORMAL
import pyperclip
from typing import Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    import tkinter as tk


class ExportMixin:
    """Mixin for export operations on diagnostic results."""

    parent: "tk.Tk"
    dialog: Optional["tk.Toplevel"]
    analysis_text: str
    source: str
    metadata: Dict
    result_text: "tk.Text"

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
            from utils.pdf_exporter import PDFExporter

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
        return base64.b64encode(text.encode('utf-8')).decode('utf-8')


__all__ = ["ExportMixin"]
