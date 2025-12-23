"""
Referral Options Dialog

Provides a dialog for users to configure referral generation options including:
- Source selection (transcript, SOAP, context)
- Recipient type (specialist, GP back-referral, hospital, diagnostic)
- Saved recipients for quick reuse
- Urgency level
- Condition selection
- Specialty selection
"""

import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Optional, Dict, List, Any


# Common medical specialties for dropdown
MEDICAL_SPECIALTIES = [
    "Cardiology",
    "Dermatology",
    "Endocrinology",
    "Gastroenterology",
    "Hematology",
    "Nephrology",
    "Neurology",
    "Oncology",
    "Ophthalmology",
    "Orthopedics",
    "Otolaryngology (ENT)",
    "Psychiatry",
    "Pulmonology",
    "Rheumatology",
    "Urology",
    "General Surgery",
    "Obstetrics/Gynecology",
    "Pediatrics",
    "Radiology",
    "Other"
]


class ReferralOptionsDialog:
    """Dialog for configuring referral generation options."""

    def __init__(self, parent):
        """Initialize the referral options dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        self.has_transcript = False
        self.has_soap = False
        self.has_context = False
        self.conditions_list: List[str] = []
        self.inferred_specialty: str = ""
        self.saved_recipients: List[Dict[str, Any]] = []
        self.condition_vars: Dict[str, tk.BooleanVar] = {}

    def set_available_content(self, has_transcript: bool, has_soap: bool, has_context: bool = False):
        """Set what content is available for referral generation.

        Args:
            has_transcript: Whether transcript content is available
            has_soap: Whether SOAP note content is available
            has_context: Whether context content is available
        """
        self.has_transcript = has_transcript
        self.has_soap = has_soap
        self.has_context = has_context

    def set_conditions(self, conditions: List[str], inferred_specialty: str = ""):
        """Set the conditions extracted from the source text.

        Args:
            conditions: List of condition strings
            inferred_specialty: Auto-inferred specialty based on conditions
        """
        self.conditions_list = conditions
        self.inferred_specialty = inferred_specialty

    def set_saved_recipients(self, recipients: List[Dict[str, Any]]):
        """Set the list of saved recipients for quick selection.

        Args:
            recipients: List of saved recipient dictionaries
        """
        self.saved_recipients = recipients

    def show(self) -> Optional[Dict]:
        """Show the dialog and return user selection.

        Returns:
            Dictionary with referral options, or None if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Referral Options")

        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()

        # Set dialog size
        dialog_width = min(800, int(screen_width * 0.7))
        dialog_height = min(700, int(screen_height * 0.8))

        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(700, 500)
        self.dialog.transient(self.parent)
        self.dialog.grab_set()

        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Create main container
        main_container = ttk.Frame(self.dialog)
        main_container.pack(fill=BOTH, expand=True, padx=10, pady=10)

        # Create button frame first (at bottom)
        button_frame = ttk.Frame(main_container)
        button_frame.pack(fill=X, side=BOTTOM, pady=(10, 0))

        # Create frame for scrollable content
        scroll_container = ttk.Frame(main_container)
        scroll_container.pack(fill=BOTH, expand=True)

        # Create scrollable frame
        style = ttk.Style()
        bg_color = style.lookup('TFrame', 'background')

        canvas = tk.Canvas(scroll_container, bg=bg_color if bg_color else 'white', highlightthickness=0)
        scrollbar = ttk.Scrollbar(scroll_container, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Pack canvas and scrollbar
        canvas.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y)

        main_frame = scrollable_frame

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Configure Referral Generation",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 15))

        # Row 1: Source and Recipient Type (side by side)
        row1_frame = ttk.Frame(main_frame)
        row1_frame.pack(fill=X, pady=(0, 10))

        # Source selection (left side)
        source_frame = ttk.LabelFrame(row1_frame, text="Content Source", padding=10)
        source_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        # Set default source
        if self.has_soap:
            default_source = "soap"
        elif self.has_transcript:
            default_source = "transcript"
        elif self.has_context:
            default_source = "context"
        else:
            default_source = "transcript"
        self.source_var = tk.StringVar(value=default_source)

        sources = [
            ("soap", "SOAP Note", self.has_soap),
            ("transcript", "Transcript", self.has_transcript),
            ("context", "Context", self.has_context)
        ]

        for value, text, available in sources:
            radio = ttk.Radiobutton(
                source_frame,
                text=text,
                variable=self.source_var,
                value=value,
                state=NORMAL if available else DISABLED
            )
            radio.pack(anchor=W, pady=2)

        # Recipient Type (right side)
        recipient_type_frame = ttk.LabelFrame(row1_frame, text="Recipient Type", padding=10)
        recipient_type_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0))

        self.recipient_type_var = tk.StringVar(value="specialist")

        recipient_types = [
            ("specialist", "Specialist Consultation"),
            ("gp_backreferral", "GP Back-Referral"),
            ("hospital", "Hospital/ER Admission"),
            ("diagnostic", "Diagnostic Services")
        ]

        for value, text in recipient_types:
            ttk.Radiobutton(
                recipient_type_frame,
                text=text,
                variable=self.recipient_type_var,
                value=value,
                command=self._on_recipient_type_change
            ).pack(anchor=W, pady=2)

        # Row 2: Urgency and Specialty (side by side)
        row2_frame = ttk.Frame(main_frame)
        row2_frame.pack(fill=X, pady=(0, 10))

        # Urgency selection (left side)
        urgency_frame = ttk.LabelFrame(row2_frame, text="Urgency Level", padding=10)
        urgency_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(0, 5))

        self.urgency_var = tk.StringVar(value="routine")

        urgency_levels = [
            ("routine", "Routine (elective)"),
            ("soon", "Soon (2-4 weeks)"),
            ("urgent", "Urgent (48-72 hours)"),
            ("emergency", "Emergency (same day)")
        ]

        for value, text in urgency_levels:
            ttk.Radiobutton(
                urgency_frame,
                text=text,
                variable=self.urgency_var,
                value=value
            ).pack(anchor=W, pady=2)

        # Specialty selection (right side)
        specialty_frame = ttk.LabelFrame(row2_frame, text="Target Specialty", padding=10)
        specialty_frame.pack(side=LEFT, fill=BOTH, expand=True, padx=(5, 0))

        ttk.Label(specialty_frame, text="Select specialty:").pack(anchor=W)

        self.specialty_var = tk.StringVar(value=self.inferred_specialty or "")
        self.specialty_combo = ttk.Combobox(
            specialty_frame,
            textvariable=self.specialty_var,
            values=MEDICAL_SPECIALTIES,
            state="normal",  # Allow custom entry
            width=25
        )
        self.specialty_combo.pack(fill=X, pady=(5, 0))

        if self.inferred_specialty:
            ttk.Label(
                specialty_frame,
                text=f"(Auto-inferred: {self.inferred_specialty})",
                foreground="gray",
                font=("Segoe UI", 9, "italic")
            ).pack(anchor=W, pady=(2, 0))

        # Row 3: Conditions selection
        conditions_frame = ttk.LabelFrame(main_frame, text="Conditions to Include", padding=10)
        conditions_frame.pack(fill=X, pady=(0, 10))

        if self.conditions_list:
            ttk.Label(
                conditions_frame,
                text="Select conditions to focus on:",
                foreground="gray"
            ).pack(anchor=W, pady=(0, 5))

            # Create checkboxes for each condition
            conditions_grid = ttk.Frame(conditions_frame)
            conditions_grid.pack(fill=X)

            for i, condition in enumerate(self.conditions_list):
                var = tk.BooleanVar(value=True)  # Default all selected
                self.condition_vars[condition] = var

                cb = ttk.Checkbutton(
                    conditions_grid,
                    text=condition,
                    variable=var
                )
                # Arrange in 2 columns
                row = i // 2
                col = i % 2
                cb.grid(row=row, column=col, sticky=W, padx=(0, 20), pady=2)
        else:
            ttk.Label(
                conditions_frame,
                text="No conditions detected. The referral will include all relevant clinical information.",
                foreground="gray",
                font=("Segoe UI", 9, "italic")
            ).pack(anchor=W)

        # Row 4: Saved Recipients
        recipients_frame = ttk.LabelFrame(main_frame, text="Recipient Details (Optional)", padding=10)
        recipients_frame.pack(fill=X, pady=(0, 10))

        # Saved recipients dropdown
        saved_row = ttk.Frame(recipients_frame)
        saved_row.pack(fill=X, pady=(0, 10))

        ttk.Label(saved_row, text="Saved Recipients:").pack(side=LEFT, padx=(0, 10))

        recipient_names = ["(New recipient)"] + [r.get("name", "Unknown") for r in self.saved_recipients]
        self.saved_recipient_var = tk.StringVar(value="(New recipient)")
        self.saved_recipient_combo = ttk.Combobox(
            saved_row,
            textvariable=self.saved_recipient_var,
            values=recipient_names,
            state="readonly",
            width=30
        )
        self.saved_recipient_combo.pack(side=LEFT, fill=X, expand=True)
        self.saved_recipient_combo.bind("<<ComboboxSelected>>", self._on_saved_recipient_selected)

        # Manual recipient details
        details_grid = ttk.Frame(recipients_frame)
        details_grid.pack(fill=X)

        # Name
        ttk.Label(details_grid, text="Recipient Name:").grid(row=0, column=0, sticky=W, pady=2)
        self.recipient_name_var = tk.StringVar()
        ttk.Entry(details_grid, textvariable=self.recipient_name_var, width=35).grid(row=0, column=1, sticky=W, padx=(10, 0), pady=2)

        # Facility
        ttk.Label(details_grid, text="Facility:").grid(row=1, column=0, sticky=W, pady=2)
        self.recipient_facility_var = tk.StringVar()
        ttk.Entry(details_grid, textvariable=self.recipient_facility_var, width=35).grid(row=1, column=1, sticky=W, padx=(10, 0), pady=2)

        # Fax
        ttk.Label(details_grid, text="Fax:").grid(row=2, column=0, sticky=W, pady=2)
        self.recipient_fax_var = tk.StringVar()
        ttk.Entry(details_grid, textvariable=self.recipient_fax_var, width=35).grid(row=2, column=1, sticky=W, padx=(10, 0), pady=2)

        # Save checkbox
        self.save_recipient_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            recipients_frame,
            text="Save this recipient for future use",
            variable=self.save_recipient_var
        ).pack(anchor=W, pady=(10, 0))

        # Buttons
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            style="secondary.TButton"
        ).pack(side=RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Generate Referral",
            command=self._generate,
            style="primary.TButton"
        ).pack(side=RIGHT)

        # Wait for dialog to close
        self.dialog.wait_window()

        return self.result

    def _on_recipient_type_change(self):
        """Handle recipient type selection change."""
        recipient_type = self.recipient_type_var.get()

        # Enable/disable specialty based on recipient type
        if recipient_type in ("specialist", "hospital"):
            self.specialty_combo.config(state="normal")
        else:
            self.specialty_combo.config(state="disabled")
            if recipient_type == "gp_backreferral":
                self.specialty_var.set("General Practice")
            elif recipient_type == "diagnostic":
                self.specialty_var.set("Radiology")

    def _on_saved_recipient_selected(self, event=None):
        """Handle saved recipient selection."""
        selected = self.saved_recipient_var.get()

        if selected == "(New recipient)":
            # Clear fields
            self.recipient_name_var.set("")
            self.recipient_facility_var.set("")
            self.recipient_fax_var.set("")
            self.save_recipient_var.set(False)
        else:
            # Find the selected recipient
            for recipient in self.saved_recipients:
                if recipient.get("name") == selected:
                    self.recipient_name_var.set(recipient.get("name", ""))
                    self.recipient_facility_var.set(recipient.get("facility", ""))
                    self.recipient_fax_var.set(recipient.get("fax", ""))
                    if recipient.get("specialty"):
                        self.specialty_var.set(recipient.get("specialty"))
                    if recipient.get("recipient_type"):
                        self.recipient_type_var.set(recipient.get("recipient_type"))
                    break

    def _generate(self):
        """Handle generate button click."""
        # Collect selected conditions
        selected_conditions = [
            cond for cond, var in self.condition_vars.items() if var.get()
        ]

        # Validate
        if not selected_conditions and self.conditions_list:
            if not messagebox.askyesno(
                "No Conditions Selected",
                "No conditions are selected. The referral will include all clinical information.\n\nDo you want to continue?",
                parent=self.dialog
            ):
                return

        # Build result
        self.result = {
            "source": self.source_var.get(),
            "recipient_type": self.recipient_type_var.get(),
            "urgency": self.urgency_var.get(),
            "specialty": self.specialty_var.get(),
            "conditions": selected_conditions,
            "conditions_text": ", ".join(selected_conditions) if selected_conditions else "",
            "recipient_details": {
                "name": self.recipient_name_var.get().strip(),
                "facility": self.recipient_facility_var.get().strip(),
                "fax": self.recipient_fax_var.get().strip()
            },
            "save_recipient": self.save_recipient_var.get()
        }

        self.dialog.destroy()

    def _cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()
