"""
Clinical Workflow Options Dialog

Provides options for selecting and configuring clinical workflows.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any
from ui.scaling_utils import ui_scaler


class WorkflowDialog:
    """Dialog for clinical workflow options."""
    
    def __init__(self, parent):
        """Initialize the workflow dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        
        # Create dialog
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Clinical Workflow Options")
        self.dialog_width, self.dialog_height = ui_scaler.get_dialog_size(800, 700)
        self.dialog.geometry(f"{self.dialog_width}x{self.dialog_height}")
        self.dialog.transient(parent)
        self.dialog.grab_set()
        
        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")
        
        self._create_widgets()
        
        # Bind escape key to cancel
        self.dialog.bind('<Escape>', lambda e: self.cancel())
        
    def _create_widgets(self):
        """Create dialog widgets."""
        # Main frame with padding
        main_frame = ttk.Frame(self.dialog, padding="20")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text="Manage Clinical Workflow",
            font=("Segoe UI", 16, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Workflow type selection
        type_frame = ttk.LabelFrame(main_frame, text="Select Workflow Type", padding="15")
        type_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.workflow_type_var = tk.StringVar(value="patient_intake")
        
        workflow_types = [
            ("patient_intake", "Patient Intake", "Complete patient registration and initial assessment"),
            ("diagnostic_workup", "Diagnostic Workup", "Systematic approach to diagnosis with test ordering"),
            ("treatment_protocol", "Treatment Protocol", "Structured treatment plan with monitoring"),
            ("follow_up_care", "Follow-up Care", "Post-treatment monitoring and care coordination"),
            ("general", "Custom Workflow", "Create a custom clinical workflow")
        ]
        
        for value, text, description in workflow_types:
            frame = ttk.Frame(type_frame)
            frame.pack(fill=tk.X, pady=5)
            
            radio = ttk.Radiobutton(
                frame,
                text=text,
                variable=self.workflow_type_var,
                value=value
            )
            radio.pack(side=tk.LEFT)
            
            desc_label = ttk.Label(
                frame,
                text=f" - {description}",
                font=("Segoe UI", 9),
                foreground="gray"
            )
            desc_label.pack(side=tk.LEFT, padx=(10, 0))
        
        # Patient/Clinical context
        context_frame = ttk.LabelFrame(main_frame, text="Clinical Context", padding="15")
        context_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Patient info fields
        info_frame = ttk.Frame(context_frame)
        info_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Two columns for patient info
        left_col = ttk.Frame(info_frame)
        left_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10))
        
        right_col = ttk.Frame(info_frame)
        right_col.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # Left column fields
        ttk.Label(left_col, text="Patient Type:").pack(anchor=tk.W)
        self.patient_type_var = tk.StringVar(value="New Patient")
        patient_type_combo = ttk.Combobox(
            left_col,
            textvariable=self.patient_type_var,
            values=["New Patient", "Established Patient", "Emergency", "Referral"],
            state="readonly",
            width=25
        )
        patient_type_combo.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(left_col, text="Age (optional):").pack(anchor=tk.W)
        self.age_entry = ttk.Entry(left_col, width=25)
        self.age_entry.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(left_col, text="Primary Concern:").pack(anchor=tk.W)
        self.concern_entry = ttk.Entry(left_col, width=25)
        self.concern_entry.pack(fill=tk.X)
        
        # Right column fields
        ttk.Label(right_col, text="Visit Type:").pack(anchor=tk.W)
        self.visit_type_var = tk.StringVar(value="Office Visit")
        visit_type_combo = ttk.Combobox(
            right_col,
            textvariable=self.visit_type_var,
            values=["Office Visit", "Telehealth", "Hospital", "Home Visit"],
            state="readonly",
            width=25
        )
        visit_type_combo.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(right_col, text="Urgency:").pack(anchor=tk.W)
        self.urgency_var = tk.StringVar(value="Routine")
        urgency_combo = ttk.Combobox(
            right_col,
            textvariable=self.urgency_var,
            values=["Routine", "Urgent", "Emergency"],
            state="readonly",
            width=25
        )
        urgency_combo.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(right_col, text="Specialty (if applicable):").pack(anchor=tk.W)
        self.specialty_entry = ttk.Entry(right_col, width=25)
        self.specialty_entry.pack(fill=tk.X)
        
        # Clinical details text area
        ttk.Label(context_frame, text="Additional Clinical Details:").pack(anchor=tk.W, pady=(10, 5))
        
        text_frame = ttk.Frame(context_frame)
        text_frame.pack(fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.clinical_text = tk.Text(
            text_frame,
            height=8,
            wrap=tk.WORD,
            yscrollcommand=scrollbar.set
        )
        self.clinical_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.clinical_text.yview)
        
        # Workflow options
        options_frame = ttk.LabelFrame(main_frame, text="Workflow Options", padding="15")
        options_frame.pack(fill=tk.X, pady=(0, 15))
        
        self.include_forms_var = tk.BooleanVar(value=True)
        forms_check = ttk.Checkbutton(
            options_frame,
            text="Include required forms and documentation",
            variable=self.include_forms_var
        )
        forms_check.pack(anchor=tk.W, pady=2)
        
        self.include_timeframes_var = tk.BooleanVar(value=True)
        timeframes_check = ttk.Checkbutton(
            options_frame,
            text="Include estimated timeframes for each step",
            variable=self.include_timeframes_var
        )
        timeframes_check.pack(anchor=tk.W, pady=2)
        
        self.include_alternatives_var = tk.BooleanVar(value=True)
        alternatives_check = ttk.Checkbutton(
            options_frame,
            text="Include alternative pathways and contingencies",
            variable=self.include_alternatives_var
        )
        alternatives_check.pack(anchor=tk.W, pady=2)
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Cancel button
        cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            width=20
        )
        cancel_btn.pack(side=tk.LEFT, padx=(0, 10))
        
        # Generate button
        self.generate_btn = ttk.Button(
            button_frame,
            text="Generate Workflow",
            command=self.generate,
            width=20,
            style="Accent.TButton"
        )
        self.generate_btn.pack(side=tk.RIGHT)
        
        # Focus on generate button
        self.generate_btn.focus_set()
        
    def generate(self):
        """Handle generate button click."""
        # Validate inputs
        primary_concern = self.concern_entry.get().strip()
        if self.workflow_type_var.get() in ["diagnostic_workup", "treatment_protocol"] and not primary_concern:
            messagebox.showwarning(
                "Missing Information",
                "Please enter the primary concern for this workflow type.",
                parent=self.dialog
            )
            self.concern_entry.focus_set()
            return
        
        # Collect all inputs
        self.result = {
            "workflow_type": self.workflow_type_var.get(),
            "patient_info": {
                "type": self.patient_type_var.get(),
                "visit_type": self.visit_type_var.get(),
                "age": self.age_entry.get().strip(),
                "urgency": self.urgency_var.get(),
                "specialty": self.specialty_entry.get().strip(),
                "primary_concern": primary_concern
            },
            "clinical_context": self.clinical_text.get("1.0", tk.END).strip(),
            "options": {
                "include_forms": self.include_forms_var.get(),
                "include_timeframes": self.include_timeframes_var.get(),
                "include_alternatives": self.include_alternatives_var.get()
            }
        }
        
        self.dialog.destroy()
        
    def cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
        
    def show(self) -> Optional[Dict[str, Any]]:
        """Show the dialog and return the result.
        
        Returns:
            Dictionary with workflow configuration or None if cancelled
        """
        # Wait for dialog to close
        self.dialog.wait_window()
        return self.result