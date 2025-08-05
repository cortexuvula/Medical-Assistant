"""
Data Extraction Results Dialog

Displays extracted clinical data with export options.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui.scaling_utils import ui_scaler
import json
import logging
from typing import Dict, Any
import os
from utils.pdf_exporter import PDFExporter


logger = logging.getLogger(__name__)


class DataExtractionResultsDialog:
    """Dialog for displaying data extraction results."""
    
    def __init__(self, parent):
        """Initialize the results dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.extracted_data = ""
        self.output_format = "structured_text"
        self.metadata = {}
        self.extraction_type = ""
        self.source = ""
        
    def show_results(self, extracted_data: str, extraction_type: str, 
                     source: str, output_format: str, metadata: Dict[str, Any]):
        """Show the extraction results in a dialog.
        
        Args:
            extracted_data: The extracted data
            extraction_type: Type of extraction performed
            source: Source of the data
            output_format: Format of the extracted data
            metadata: Additional metadata including counts
        """
        self.extracted_data = extracted_data
        self.output_format = output_format
        self.metadata = metadata
        self.extraction_type = extraction_type
        self.source = source
        
        # Create dialog
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Data Extraction Results")
        self.dialog_width, dialog_height = ui_scaler.get_dialog_size(900, 700)
        dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 900) // 2
        y = (self.dialog.winfo_screenheight() - 700) // 2
        self.dialog.geometry(f"900x700+{x}+{y}")
        
        self._create_widgets(extraction_type, source)
        
        # Bind escape key to close
        self.dialog.bind('<Escape>', lambda e: self.close())
        
    def _create_widgets(self, extraction_type: str, source: str):
        """Create dialog widgets."""
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title and info
        title_frame = ttk.Frame(main_frame)
        title_frame.pack(fill=tk.X, pady=(0, 15))
        
        title_label = ttk.Label(
            title_frame,
            text="Extracted Clinical Data",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        # Export buttons on the right
        export_frame = ttk.Frame(title_frame)
        export_frame.pack(side=tk.RIGHT)
        
        copy_btn = ttk.Button(
            export_frame,
            text="Copy to Clipboard",
            command=self.copy_to_clipboard,
            width=15
        )
        copy_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        export_btn = ttk.Button(
            export_frame,
            text="Export to File",
            command=self.export_to_file,
            width=15
        )
        export_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        pdf_btn = ttk.Button(
            export_frame,
            text="Export to PDF",
            command=self._export_to_pdf,
            width=15
        )
        pdf_btn.pack(side=tk.LEFT)
        
        # Info labels
        info_frame = ttk.Frame(main_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        source_label = ttk.Label(
            info_frame,
            text=f"Source: {source}",
            font=("Segoe UI", 10)
        )
        source_label.pack(side=tk.LEFT, padx=(0, 20))
        
        type_text = extraction_type.replace('_', ' ').title()
        type_label = ttk.Label(
            info_frame,
            text=f"Type: {type_text}",
            font=("Segoe UI", 10)
        )
        type_label.pack(side=tk.LEFT, padx=(0, 20))
        
        format_text = self.output_format.replace('_', ' ').title()
        format_label = ttk.Label(
            info_frame,
            text=f"Format: {format_text}",
            font=("Segoe UI", 10)
        )
        format_label.pack(side=tk.LEFT)
        
        # Summary statistics
        if 'counts' in self.metadata:
            counts = self.metadata['counts']
            summary_frame = ttk.LabelFrame(main_frame, text="Summary", padding="10")
            summary_frame.pack(fill=tk.X, pady=(0, 15))
            
            summary_text = []
            if counts.get('vital_signs', 0) > 0:
                summary_text.append(f"Vital Signs: {counts['vital_signs']}")
            if counts.get('laboratory_values', 0) > 0:
                summary_text.append(f"Lab Values: {counts['laboratory_values']}")
            if counts.get('medications', 0) > 0:
                summary_text.append(f"Medications: {counts['medications']}")
            if counts.get('diagnoses', 0) > 0:
                summary_text.append(f"Diagnoses: {counts['diagnoses']}")
            if counts.get('procedures', 0) > 0:
                summary_text.append(f"Procedures: {counts['procedures']}")
            
            if summary_text:
                summary_label = ttk.Label(
                    summary_frame,
                    text=" | ".join(summary_text),
                    font=("Segoe UI", 10)
                )
                summary_label.pack()
            
            # Check for abnormal values
            if self.metadata.get('has_abnormal'):
                warning_label = ttk.Label(
                    summary_frame,
                    text="⚠ Abnormal values detected",
                    font=("Segoe UI", 10, "bold"),
                    foreground="red"
                )
                warning_label.pack(pady=(5, 0))
        
        # Results text area with scrollbar
        text_frame = ttk.Frame(main_frame)
        text_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Create text widget with scrollbar
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Consolas", 10) if self.output_format in ["json", "csv"] else ("Segoe UI", 10),
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10
        )
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)
        
        # Insert extracted data
        self.text_widget.insert(tk.END, self.extracted_data)
        
        # Make text read-only but selectable
        self.text_widget.config(state=tk.DISABLED)
        
        # Add syntax highlighting for JSON
        if self.output_format == "json":
            self._highlight_json()
        
        # Close button
        close_btn = ttk.Button(
            main_frame,
            text="Close",
            command=self.close,
            width=20
        )
        close_btn.pack(pady=(0, 0))
        
    def _highlight_json(self):
        """Add syntax highlighting for JSON format."""
        try:
            # Define tags for different JSON elements
            self.text_widget.tag_configure("key", foreground="#0066cc")
            self.text_widget.tag_configure("string", foreground="#008000")
            self.text_widget.tag_configure("number", foreground="#ff6600")
            self.text_widget.tag_configure("boolean", foreground="#cc0066")
            self.text_widget.tag_configure("null", foreground="#666666")
            
            # Simple JSON syntax highlighting
            content = self.text_widget.get("1.0", tk.END)
            
            # This is a simplified approach - in production, use a proper JSON parser
            import re
            
            # Highlight strings (quoted text)
            for match in re.finditer(r'"([^"\\]|\\.)*"', content):
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                
                # Check if it's a key (followed by colon)
                if match.end() < len(content) and content[match.end():match.end()+1].strip().startswith(':'):
                    self.text_widget.tag_add("key", start_idx, end_idx)
                else:
                    self.text_widget.tag_add("string", start_idx, end_idx)
            
            # Highlight numbers
            for match in re.finditer(r'\b\d+\.?\d*\b', content):
                start_idx = f"1.0 + {match.start()} chars"
                end_idx = f"1.0 + {match.end()} chars"
                self.text_widget.tag_add("number", start_idx, end_idx)
            
            # Highlight booleans and null
            for keyword in ['true', 'false', 'null']:
                for match in re.finditer(r'\b' + keyword + r'\b', content):
                    start_idx = f"1.0 + {match.start()} chars"
                    end_idx = f"1.0 + {match.end()} chars"
                    tag = "boolean" if keyword in ['true', 'false'] else "null"
                    self.text_widget.tag_add(tag, start_idx, end_idx)
                    
        except Exception as e:
            logger.error(f"Error highlighting JSON: {e}")
    
    def copy_to_clipboard(self):
        """Copy extracted data to clipboard."""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(self.extracted_data)
        self.dialog.update()
        
        # Show confirmation
        messagebox.showinfo(
            "Copied",
            "Extracted data copied to clipboard!",
            parent=self.dialog
        )
    
    def export_to_file(self):
        """Export extracted data to file."""
        # Determine file extension based on format
        if self.output_format == "json":
            default_ext = ".json"
            filetypes = [("JSON files", "*.json"), ("All files", "*.*")]
        elif self.output_format == "csv":
            default_ext = ".csv"
            filetypes = [("CSV files", "*.csv"), ("All files", "*.*")]
        else:
            default_ext = ".txt"
            filetypes = [("Text files", "*.txt"), ("All files", "*.*")]
        
        # Ask for file location
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Extracted Data",
            defaultextension=default_ext,
            filetypes=filetypes
        )
        
        if filename:
            try:
                with open(filename, 'w', encoding='utf-8') as f:
                    f.write(self.extracted_data)
                
                messagebox.showinfo(
                    "Export Successful",
                    f"Data exported successfully to:\n{filename}",
                    parent=self.dialog
                )
            except Exception as e:
                logger.error(f"Error exporting data: {e}")
                messagebox.showerror(
                    "Export Error",
                    f"Failed to export data:\n{str(e)}",
                    parent=self.dialog
                )
    
    def _export_to_pdf(self):
        """Export the extracted data to PDF."""
        try:
            # Get default filename
            default_filename = f"data_extraction_{self.extraction_type}_report.pdf"
            
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Data Extraction Report as PDF"
            )
            
            if not file_path:
                return
            
            # Create PDF exporter
            pdf_exporter = PDFExporter()
            
            # Prepare extraction data for PDF
            extraction_data = self._parse_extraction_data()
            
            # Add metadata
            extraction_data.update({
                "source": self.source,
                "extraction_type": self.extraction_type,
                "format": self.output_format
            })
            
            # Generate PDF
            success = pdf_exporter.generate_data_extraction_report_pdf(
                extraction_data,
                file_path,
                self.output_format
            )
            
            if success:
                messagebox.showinfo(
                    "Export Successful",
                    f"Data extraction report exported to:\n{file_path}",
                    parent=self.dialog
                )
                
                # Optionally open the PDF
                if messagebox.askyesno(
                    "Open PDF",
                    "Would you like to open the PDF now?",
                    parent=self.dialog
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
                    parent=self.dialog
                )
                
        except Exception as e:
            logger.error(f"Error exporting to PDF: {str(e)}")
            messagebox.showerror(
                "Export Error",
                f"Failed to export PDF: {str(e)}",
                parent=self.dialog
            )
    
    def _parse_extraction_data(self) -> Dict[str, Any]:
        """Parse the extracted data based on format.
        
        Returns:
            Dictionary with structured extraction data
        """
        data = {
            "vitals": [],
            "labs": [],
            "diagnoses": [],
            "medications": [],
            "procedures": []
        }
        
        try:
            if self.output_format == "json":
                # Parse JSON data
                json_data = json.loads(self.extracted_data)
                
                # Map JSON fields to expected structure
                if isinstance(json_data, dict):
                    data["vitals"] = json_data.get("vital_signs", [])
                    data["labs"] = json_data.get("laboratory_values", [])
                    data["diagnoses"] = json_data.get("diagnoses", [])
                    data["medications"] = json_data.get("medications", [])
                    data["procedures"] = json_data.get("procedures", [])
                    
            elif self.output_format == "csv":
                # Parse CSV data
                import csv
                import io
                
                reader = csv.DictReader(io.StringIO(self.extracted_data))
                for row in reader:
                    # Categorize based on type field or infer from content
                    if row.get("type") == "vital" or "blood pressure" in str(row).lower():
                        data["vitals"].append(row)
                    elif row.get("type") == "lab" or any(term in str(row).lower() for term in ["glucose", "hemoglobin", "wbc"]):
                        data["labs"].append(row)
                    elif row.get("type") == "diagnosis" or "icd" in str(row).lower():
                        data["diagnoses"].append(row)
                    elif row.get("type") == "medication" or any(term in str(row).lower() for term in ["mg", "dose", "tablet"]):
                        data["medications"].append(row)
                    elif row.get("type") == "procedure":
                        data["procedures"].append(row)
                        
            else:
                # For structured text, use the raw data
                # The PDF exporter will handle it as generic content
                data["raw_content"] = self.extracted_data
                
            # Add counts from metadata if available
            if "counts" in self.metadata:
                data.update(self.metadata)
                
        except Exception as e:
            logger.error(f"Error parsing extraction data: {str(e)}")
            # Fallback to raw content
            data["raw_content"] = self.extracted_data
            
        return data
    
    def close(self):
        """Close the dialog."""
        self.dialog.destroy()