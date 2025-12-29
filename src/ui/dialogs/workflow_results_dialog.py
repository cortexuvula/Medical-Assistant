"""
Clinical Workflow Results Dialog

Displays workflow steps and provides interactive tracking capabilities.
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from ui.scaling_utils import ui_scaler
import json
import logging
from typing import Dict, Any, List
from datetime import datetime
import os
from utils.pdf_exporter import PDFExporter


logger = logging.getLogger(__name__)


class WorkflowResultsDialog:
    """Dialog for displaying and tracking workflow progress."""
    
    def __init__(self, parent):
        """Initialize the workflow results dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.workflow_text = ""
        self.workflow_type = ""
        self.metadata = {}
        self.patient_info = {}
        self.step_checkboxes = []
        self.step_status = {}
        
    def show_results(self, workflow_text: str, workflow_type: str, 
                     patient_info: Dict[str, Any], metadata: Dict[str, Any]):
        """Show the workflow results in a dialog.
        
        Args:
            workflow_text: The generated workflow text
            workflow_type: Type of workflow
            patient_info: Patient information used
            metadata: Additional metadata including steps
        """
        self.workflow_text = workflow_text
        self.workflow_type = workflow_type
        self.metadata = metadata
        self.patient_info = patient_info
        
        # Create dialog
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Clinical Workflow")
        self.dialog_width, self.dialog_height = ui_scaler.get_dialog_size(1000, 800)
        self.dialog.geometry(f"{self.dialog_width}x{self.dialog_height}")
        self.dialog.transient(self.parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - 1000) // 2
        y = (self.dialog.winfo_screenheight() - 800) // 2
        self.dialog.geometry(f"1000x800+{x}+{y}")
        
        self._create_widgets(patient_info)
        
        # Bind escape key to close
        self.dialog.bind('<Escape>', lambda e: self.close())
        
    def _create_widgets(self, patient_info: Dict[str, Any]):
        """Create dialog widgets."""
        # Main container with horizontal split
        paned = ttk.PanedWindow(self.dialog, orient="horizontal")
        paned.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel - Workflow steps and checklist
        left_frame = ttk.Frame(paned)
        paned.add(left_frame, weight=2)
        
        # Right panel - Full workflow text
        right_frame = ttk.Frame(paned)
        paned.add(right_frame, weight=3)
        
        # Left panel content
        self._create_left_panel(left_frame, patient_info)
        
        # Right panel content
        self._create_right_panel(right_frame)
        
        # Bottom buttons
        self._create_bottom_buttons()
        
    def _create_left_panel(self, parent: ttk.Frame, patient_info: Dict[str, Any]):
        """Create the left panel with workflow checklist."""
        # Title and info
        title_frame = ttk.Frame(parent)
        title_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        workflow_title = self.workflow_type.replace('_', ' ').title()
        title_label = ttk.Label(
            title_frame,
            text=f"{workflow_title} Workflow",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(side=tk.LEFT)
        
        # Progress indicator
        self.progress_label = ttk.Label(
            title_frame,
            text="Progress: 0%",
            font=("Segoe UI", 10),
            foreground="gray"
        )
        self.progress_label.pack(side=tk.RIGHT)
        
        # Patient info summary
        info_frame = ttk.Labelframe(parent, text="Patient Information", padding="10")
        info_frame.pack(fill=tk.X, padx=10, pady=5)
        
        info_text = []
        if patient_info.get('type'):
            info_text.append(f"Type: {patient_info['type']}")
        if patient_info.get('visit_type'):
            info_text.append(f"Visit: {patient_info['visit_type']}")
        if patient_info.get('primary_concern'):
            info_text.append(f"Concern: {patient_info['primary_concern']}")
        if patient_info.get('urgency'):
            info_text.append(f"Urgency: {patient_info['urgency']}")
        
        info_label = ttk.Label(
            info_frame,
            text=" | ".join(info_text),
            font=("Segoe UI", 9)
        )
        info_label.pack()
        
        # Workflow metadata
        if self.metadata:
            meta_frame = ttk.Labelframe(parent, text="Workflow Details", padding="10")
            meta_frame.pack(fill=tk.X, padx=10, pady=5)
            
            # Duration
            if 'estimated_duration' in self.metadata:
                duration_label = ttk.Label(
                    meta_frame,
                    text=f"Estimated Duration: {self.metadata['estimated_duration']}",
                    font=("Segoe UI", 9)
                )
                duration_label.pack(anchor=tk.W)
            
            # Step count
            if 'total_steps' in self.metadata:
                steps_label = ttk.Label(
                    meta_frame,
                    text=f"Total Steps: {self.metadata['total_steps']}",
                    font=("Segoe UI", 9)
                )
                steps_label.pack(anchor=tk.W)
        
        # Workflow steps checklist
        checklist_frame = ttk.Labelframe(parent, text="Workflow Steps", padding="10")
        checklist_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        # Create scrollable frame for steps
        canvas = tk.Canvas(checklist_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(checklist_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Create checkboxes for each step
        self._create_step_checkboxes(scrollable_frame)
        
    def _create_step_checkboxes(self, parent: ttk.Frame):
        """Create interactive checkboxes for workflow steps."""
        self.step_checkboxes = []
        self.step_status = {}
        
        # Parse steps from workflow text or metadata
        steps = self._extract_steps()
        
        for i, step in enumerate(steps):
            step_frame = ttk.Frame(parent)
            step_frame.pack(fill=tk.X, pady=5, padx=5)
            
            # Checkbox variable
            var = tk.BooleanVar(value=False)
            self.step_status[i] = var
            
            # Create checkbox
            checkbox = ttk.Checkbutton(
                step_frame,
                text=f"{i+1}. {step['name']}",
                variable=var,
                command=self._update_progress
            )
            checkbox.pack(side=tk.LEFT, fill=tk.X, expand=True)
            
            # Add duration if available
            if step.get('duration'):
                duration_label = ttk.Label(
                    step_frame,
                    text=f"({step['duration']})",
                    font=("Segoe UI", 8),
                    foreground="gray"
                )
                duration_label.pack(side=tk.RIGHT, padx=(5, 0))
            
            self.step_checkboxes.append(checkbox)
            
            # Add description as tooltip if available
            if step.get('description'):
                self._create_tooltip(checkbox, step['description'])
    
    def _extract_steps(self) -> List[Dict[str, str]]:
        """Extract steps from workflow text or metadata."""
        steps = []
        
        # First try metadata
        if 'steps' in self.metadata and self.metadata['steps']:
            return self.metadata['steps']
        
        # Parse from workflow text
        import re
        lines = self.workflow_text.split('\n')
        
        for line in lines:
            # Look for numbered steps
            step_match = re.match(r'^\s*(\d+)\.\s*([^-\n]+)(?:\s*-\s*([^-\n]+))?', line)
            if step_match:
                step_num, step_name, duration = step_match.groups()
                steps.append({
                    'number': int(step_num),
                    'name': step_name.strip(),
                    'duration': duration.strip() if duration else None
                })
        
        # If no numbered steps found, try bullet points
        if not steps:
            for line in lines:
                if line.strip().startswith(('•', '-', '*')) and len(line.strip()) > 2:
                    step_name = line.strip()[1:].strip()
                    steps.append({
                        'number': len(steps) + 1,
                        'name': step_name,
                        'duration': None
                    })
        
        return steps
    
    def _update_progress(self):
        """Update progress indicator based on checked steps."""
        total_steps = len(self.step_status)
        if total_steps == 0:
            return
        
        completed_steps = sum(1 for var in self.step_status.values() if var.get())
        progress = int((completed_steps / total_steps) * 100)
        
        self.progress_label.config(text=f"Progress: {progress}%")
        
        # Update color based on progress
        if progress == 100:
            self.progress_label.config(foreground="green")
        elif progress > 50:
            self.progress_label.config(foreground="blue")
        else:
            self.progress_label.config(foreground="gray")
    
    def _create_right_panel(self, parent: ttk.Frame):
        """Create the right panel with full workflow text."""
        # Title
        title_label = ttk.Label(
            parent,
            text="Complete Workflow",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(padx=10, pady=(10, 5))
        
        # Action buttons
        action_frame = ttk.Frame(parent)
        action_frame.pack(fill=tk.X, padx=10, pady=5)
        
        copy_btn = ttk.Button(
            action_frame,
            text="Copy to Clipboard",
            command=self.copy_to_clipboard,
            width=20
        )
        copy_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        export_btn = ttk.Button(
            action_frame,
            text="Export Workflow",
            command=self.export_workflow,
            width=20
        )
        export_btn.pack(side=tk.LEFT)
        
        # Text area with scrollbar
        text_frame = ttk.Frame(parent)
        text_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.text_widget = tk.Text(
            text_frame,
            wrap=tk.WORD,
            font=("Segoe UI", 10),
            yscrollcommand=scrollbar.set,
            padx=10,
            pady=10
        )
        self.text_widget.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.text_widget.yview)
        
        # Insert workflow text
        self.text_widget.insert(tk.END, self.workflow_text)
        
        # Make text read-only but selectable
        self.text_widget.config(state=tk.DISABLED)
        
        # Apply syntax highlighting
        self._apply_syntax_highlighting()
    
    def _apply_syntax_highlighting(self):
        """Apply syntax highlighting to workflow text."""
        # Define tags
        self.text_widget.tag_configure("heading", font=("Segoe UI", 11, "bold"), foreground="#0066cc")
        self.text_widget.tag_configure("step", font=("Segoe UI", 10, "bold"))
        self.text_widget.tag_configure("checkpoint", foreground="#008000")
        self.text_widget.tag_configure("warning", foreground="#ff6600", font=("Segoe UI", 10, "bold"))
        self.text_widget.tag_configure("duration", foreground="#666666", font=("Segoe UI", 10, "italic"))
        
        # Apply tags
        content = self.text_widget.get("1.0", tk.END)
        
        # Headings (lines with colons)
        import re
        for match in re.finditer(r'^([A-Z][A-Z\s]+):', content, re.MULTILINE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.text_widget.tag_add("heading", start_idx, end_idx)
        
        # Steps (numbered items)
        for match in re.finditer(r'^\s*\d+\.\s*[^\n]+', content, re.MULTILINE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.start() + len(match.group().split('-')[0])} chars"
            self.text_widget.tag_add("step", start_idx, end_idx)
        
        # Checkpoints
        for match in re.finditer(r'✓\s*Checkpoint:[^\n]+', content):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.text_widget.tag_add("checkpoint", start_idx, end_idx)
        
        # Warnings and critical items
        for match in re.finditer(r'(?:WARNING|CRITICAL|IMPORTANT):[^\n]+', content, re.IGNORECASE):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.text_widget.tag_add("warning", start_idx, end_idx)
        
        # Durations
        for match in re.finditer(r'\([^)]*(?:minutes?|hours?|days?)[^)]*\)', content):
            start_idx = f"1.0 + {match.start()} chars"
            end_idx = f"1.0 + {match.end()} chars"
            self.text_widget.tag_add("duration", start_idx, end_idx)
    
    def _create_bottom_buttons(self):
        """Create bottom button bar."""
        button_frame = ttk.Frame(self.dialog)
        button_frame.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # Left side - workflow actions
        left_frame = ttk.Frame(button_frame)
        left_frame.pack(side=tk.LEFT)
        
        save_progress_btn = ttk.Button(
            left_frame,
            text="Save Progress",
            command=self.save_progress,
            width=15
        )
        save_progress_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        export_pdf_btn = ttk.Button(
            left_frame,
            text="Export to PDF",
            command=self._export_to_pdf,
            width=15
        )
        export_pdf_btn.pack(side=tk.LEFT, padx=(0, 5))
        
        print_btn = ttk.Button(
            left_frame,
            text="Print Workflow",
            command=self.print_workflow,
            width=15
        )
        print_btn.pack(side=tk.LEFT)
        
        # Right side - close button
        close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=self.close,
            width=20
        )
        close_btn.pack(side=tk.RIGHT)
    
    def _create_tooltip(self, widget, text):
        """Create a tooltip for a widget."""
        from ui.tooltip import ToolTip
        ToolTip(widget, text)
    
    def copy_to_clipboard(self):
        """Copy workflow text to clipboard."""
        self.dialog.clipboard_clear()
        self.dialog.clipboard_append(self.workflow_text)
        self.dialog.update()
        
        messagebox.showinfo(
            "Copied",
            "Workflow copied to clipboard!",
            parent=self.dialog
        )
    
    def export_workflow(self):
        """Export workflow to file."""
        # Determine filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_name = f"workflow_{self.workflow_type}_{timestamp}"
        
        filename = filedialog.asksaveasfilename(
            parent=self.dialog,
            title="Export Workflow",
            defaultextension=".txt",
            filetypes=[
                ("Text files", "*.txt"),
                ("Markdown files", "*.md"),
                ("JSON files", "*.json"),
                ("All files", "*.*")
            ],
            initialfile=default_name
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    # Export as JSON with metadata
                    export_data = {
                        "workflow_type": self.workflow_type,
                        "generated_at": datetime.now().isoformat(),
                        "workflow_text": self.workflow_text,
                        "metadata": self.metadata,
                        "progress": {
                            f"step_{i}": var.get() 
                            for i, var in self.step_status.items()
                        }
                    }
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(export_data, f, indent=2)
                else:
                    # Export as text
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(self.workflow_text)
                        
                        # Add progress summary if any steps completed
                        if self.step_status:
                            completed = sum(1 for var in self.step_status.values() if var.get())
                            total = len(self.step_status)
                            if completed > 0:
                                f.write(f"\n\n---\nProgress: {completed}/{total} steps completed")
                
                messagebox.showinfo(
                    "Export Successful",
                    f"Workflow exported to:\n{filename}",
                    parent=self.dialog
                )
            except Exception as e:
                logger.error(f"Error exporting workflow: {e}")
                messagebox.showerror(
                    "Export Error",
                    f"Failed to export workflow:\n{str(e)}",
                    parent=self.dialog
                )
    
    def save_progress(self):
        """Save current progress state."""
        # In a real implementation, this would save to database
        completed = sum(1 for var in self.step_status.values() if var.get())
        total = len(self.step_status)
        
        messagebox.showinfo(
            "Progress Saved",
            f"Workflow progress saved: {completed}/{total} steps completed",
            parent=self.dialog
        )
    
    def print_workflow(self):
        """Print the workflow using system print dialog."""
        try:
            # First export to a temporary PDF
            import tempfile
            import subprocess
            import platform
            
            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp_path = tmp.name
            
            # Generate PDF
            if self._export_to_pdf_file(tmp_path):
                # Open system print dialog
                system = platform.system()
                
                if system == 'Windows':
                    # Use Windows print command
                    os.startfile(tmp_path, "print")
                elif system == 'Darwin':  # macOS
                    # Use lpr command on macOS
                    subprocess.run(['lpr', tmp_path])
                else:  # Linux
                    # Use lpr command on Linux
                    subprocess.run(['lpr', tmp_path])
                
                # Clean up temp file after a delay
                self.dialog.after(5000, lambda: os.unlink(tmp_path) if os.path.exists(tmp_path) else None)
                
                messagebox.showinfo(
                    "Print",
                    "Workflow sent to printer.",
                    parent=self.dialog
                )
            else:
                messagebox.showerror(
                    "Print Error",
                    "Failed to prepare document for printing.",
                    parent=self.dialog
                )
                
        except Exception as e:
            logging.error(f"Error printing workflow: {str(e)}")
            messagebox.showerror(
                "Print Error",
                f"Failed to print workflow: {str(e)}",
                parent=self.dialog
            )
    
    def _export_to_pdf(self):
        """Export the workflow to PDF with file dialog."""
        try:
            # Get default filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"workflow_{self.workflow_type}_{timestamp}.pdf"
            
            # Ask user for save location
            file_path = filedialog.asksaveasfilename(
                parent=self.dialog,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=default_filename,
                title="Save Workflow as PDF"
            )
            
            if not file_path:
                return
            
            # Export to PDF
            if self._export_to_pdf_file(file_path):
                messagebox.showinfo(
                    "Export Successful",
                    f"Workflow exported to:\n{file_path}",
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
            logging.error(f"Error exporting to PDF: {str(e)}")
            messagebox.showerror(
                "Export Error",
                f"Failed to export PDF: {str(e)}",
                parent=self.dialog
            )
    
    def _export_to_pdf_file(self, file_path: str) -> bool:
        """Export workflow to PDF file.
        
        Args:
            file_path: Path to save the PDF
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Create PDF exporter
            pdf_exporter = PDFExporter()
            
            # Prepare workflow data
            workflow_data = {
                "workflow_type": self.workflow_type,
                "workflow_text": self.workflow_text,
                "patient_info": self.patient_info,
                "steps": [],
                "notes": ""
            }
            
            # Extract steps with completion status
            steps = self._extract_steps()
            for i, step in enumerate(steps):
                step_data = {
                    "description": step['name'],
                    "time_estimate": step.get('duration', ''),
                    "completed": self.step_status.get(i, tk.BooleanVar()).get() if self.step_status else False
                }
                workflow_data["steps"].append(step_data)
            
            # Add metadata
            if self.metadata:
                workflow_data.update(self.metadata)
            
            # Add progress information
            if self.step_status:
                completed = sum(1 for var in self.step_status.values() if var.get())
                total = len(self.step_status)
                workflow_data["notes"] = f"Progress: {completed}/{total} steps completed"
            
            # Generate PDF
            success = pdf_exporter.generate_workflow_report_pdf(
                workflow_data,
                file_path
            )
            
            return success
            
        except Exception as e:
            logging.error(f"Error generating workflow PDF: {str(e)}")
            return False
    
    def close(self):
        """Close the dialog."""
        # Check if there's unsaved progress
        if self.step_status:
            completed = sum(1 for var in self.step_status.values() if var.get())
            if completed > 0 and completed < len(self.step_status):
                if not messagebox.askyesno(
                    "Unsaved Progress",
                    "You have workflow steps in progress. Close without saving?",
                    parent=self.dialog
                ):
                    return
        
        self.dialog.destroy()