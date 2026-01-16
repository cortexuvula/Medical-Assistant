"""
Diagnostic Analysis Dialog

Provides a dialog for users to select the source of clinical findings,
patient context, specialty focus, and optionally input custom findings
for diagnostic analysis.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, VERTICAL, LEFT, RIGHT, W
from tkinter import messagebox, filedialog
from typing import Optional, Dict, List
import json
import os
import logging
from datetime import datetime


# Specialty options for focused analysis
SPECIALTY_OPTIONS = [
    ("General/Primary Care", "general", "Common conditions first, broad differential"),
    ("Emergency Medicine", "emergency", "Red flags prioritized, life-threatening conditions first"),
    ("Internal Medicine", "internal", "Comprehensive workup, multisystem considerations"),
    ("Pediatrics", "pediatric", "Age-appropriate differentials, developmental considerations"),
    ("Cardiology", "cardiology", "Cardiovascular-focused differential"),
    ("Pulmonology", "pulmonology", "Respiratory-focused differential"),
    ("Gastroenterology", "gi", "GI-focused differential"),
    ("Neurology", "neurology", "Neurological-focused differential"),
    ("Psychiatry", "psychiatry", "Mental health focus, biopsychosocial approach"),
    ("Orthopedics", "orthopedic", "Musculoskeletal-focused differential"),
    ("Oncology", "oncology", "Malignancy considerations prioritized"),
    ("Geriatrics", "geriatric", "Age-related conditions, polypharmacy considerations"),
]


class DiagnosticAnalysisDialog:
    """Dialog for configuring diagnostic analysis input."""

    # Templates directory
    TEMPLATES_DIR = os.path.join(os.path.expanduser("~"), ".medical_assistant", "context_templates")

    def __init__(self, parent):
        """Initialize the diagnostic analysis dialog.

        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        self.has_transcript = False
        self.has_soap = False

        # Ensure templates directory exists
        os.makedirs(self.TEMPLATES_DIR, exist_ok=True)

    def set_available_content(self, has_transcript: bool, has_soap: bool):
        """Set what content is available for analysis.

        Args:
            has_transcript: Whether transcript content is available
            has_soap: Whether SOAP note content is available
        """
        self.has_transcript = has_transcript
        self.has_soap = has_soap

    def show(self) -> Optional[Dict]:
        """Show the dialog and return user selection.

        Returns:
            Dictionary with 'source', 'custom_findings', 'patient_context',
            and 'specialty', or None if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Diagnostic Analysis Options")
        dialog_width, dialog_height = ui_scaler.get_dialog_size(950, 950)
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(900, 900)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() - self.dialog.winfo_width()) // 2
        y = (self.dialog.winfo_screenheight() - self.dialog.winfo_height()) // 2
        self.dialog.geometry(f"+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass

        # Create scrollable main frame
        canvas = tk.Canvas(self.dialog)
        scrollbar = ttk.Scrollbar(self.dialog, orient=VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas, padding=20)

        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )

        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        # Mouse wheel scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        scrollbar.pack(side=RIGHT, fill=Y)
        canvas.pack(side=LEFT, fill=BOTH, expand=True)

        main_frame = scrollable_frame

        # Title
        title_label = ttk.Label(
            main_frame,
            text="Configure Diagnostic Analysis",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 15))

        # ==================== SOURCE SELECTION ====================
        source_frame = ttk.Labelframe(main_frame, text="Analysis Source", padding=15)
        source_frame.pack(fill=X, pady=(0, 15))

        self.source_var = tk.StringVar(value="transcript" if self.has_transcript else "custom")

        # Transcript option
        transcript_radio = ttk.Radiobutton(
            source_frame,
            text="Use current transcript",
            variable=self.source_var,
            value="transcript",
            state=tk.NORMAL if self.has_transcript else DISABLED
        )
        transcript_radio.pack(anchor=W, pady=3)

        if not self.has_transcript:
            ttk.Label(
                source_frame,
                text="    (No transcript available)",
                foreground="gray"
            ).pack(anchor=W)

        # SOAP note option
        soap_radio = ttk.Radiobutton(
            source_frame,
            text="Use current SOAP note (recommended - more structured)",
            variable=self.source_var,
            value="soap",
            state=tk.NORMAL if self.has_soap else DISABLED
        )
        soap_radio.pack(anchor=W, pady=3)

        if not self.has_soap:
            ttk.Label(
                source_frame,
                text="    (No SOAP note available)",
                foreground="gray"
            ).pack(anchor=W)

        # Custom input option
        custom_radio = ttk.Radiobutton(
            source_frame,
            text="Enter custom clinical findings",
            variable=self.source_var,
            value="custom"
        )
        custom_radio.pack(anchor=W, pady=3)

        # ==================== PATIENT CONTEXT ====================
        context_frame = ttk.Labelframe(main_frame, text="Patient Context (Optional - Improves Accuracy)", padding=15)
        context_frame.pack(fill=X, pady=(0, 15))

        # Template management row
        template_frame = ttk.Frame(context_frame)
        template_frame.pack(fill=X, pady=(0, 10))

        ttk.Label(
            template_frame,
            text="Templates:",
            font=("Segoe UI", 9)
        ).pack(side=LEFT, padx=(0, 5))

        # Template dropdown
        self.template_var = tk.StringVar(value="")
        self.template_combo = ttk.Combobox(
            template_frame,
            textvariable=self.template_var,
            width=30,
            state="readonly"
        )
        self.template_combo.pack(side=LEFT, padx=(0, 5))
        self._refresh_template_list()

        ttk.Button(
            template_frame,
            text="Load",
            command=self._load_template,
            bootstyle="info-outline",
            width=8
        ).pack(side=LEFT, padx=(0, 3))

        ttk.Button(
            template_frame,
            text="Save As...",
            command=self._save_template,
            bootstyle="success-outline",
            width=10
        ).pack(side=LEFT, padx=(0, 3))

        ttk.Button(
            template_frame,
            text="Delete",
            command=self._delete_template,
            bootstyle="danger-outline",
            width=8
        ).pack(side=LEFT, padx=(0, 3))

        ttk.Button(
            template_frame,
            text="Clear All",
            command=self._clear_context,
            bootstyle="secondary-outline",
            width=10
        ).pack(side=LEFT)

        # Demographics row
        demo_frame = ttk.Frame(context_frame)
        demo_frame.pack(fill=X, pady=(0, 10))

        # Age
        ttk.Label(demo_frame, text="Age:").pack(side=LEFT)
        self.age_var = tk.StringVar()
        age_entry = ttk.Entry(demo_frame, textvariable=self.age_var, width=8)
        age_entry.pack(side=LEFT, padx=(5, 15))

        # Sex
        ttk.Label(demo_frame, text="Sex:").pack(side=LEFT)
        self.sex_var = tk.StringVar()
        sex_combo = ttk.Combobox(
            demo_frame,
            textvariable=self.sex_var,
            values=["", "Male", "Female", "Other"],
            width=10,
            state="readonly"
        )
        sex_combo.pack(side=LEFT, padx=(5, 15))

        # Pregnancy status (for females)
        self.pregnant_var = tk.BooleanVar()
        self.pregnant_check = ttk.Checkbutton(
            demo_frame,
            text="Pregnant",
            variable=self.pregnant_var,
            state=tk.DISABLED
        )
        self.pregnant_check.pack(side=LEFT, padx=(5, 0))

        # Enable pregnancy checkbox for females
        def on_sex_change(*args):
            if self.sex_var.get() == "Female":
                self.pregnant_check.config(state=tk.NORMAL)
            else:
                self.pregnant_check.config(state=tk.DISABLED)
                self.pregnant_var.set(False)
        self.sex_var.trace('w', on_sex_change)

        # Past Medical History
        pmh_frame = ttk.Frame(context_frame)
        pmh_frame.pack(fill=X, pady=(5, 5))

        ttk.Label(pmh_frame, text="Past Medical History:").pack(anchor=W)
        self.pmh_text = tk.Text(pmh_frame, height=2, wrap=tk.WORD, font=("Segoe UI", 10))
        self.pmh_text.pack(fill=X, pady=(3, 0))
        self.pmh_text.insert("1.0", "e.g., HTN, DM2, asthma...")
        self.pmh_text.tag_add("hint", "1.0", "end")
        self.pmh_text.tag_config("hint", foreground="gray")

        def clear_pmh_hint(event=None):
            if self.pmh_text.tag_ranges("hint"):
                self.pmh_text.delete("1.0", "end")
                self.pmh_text.tag_remove("hint", "1.0", "end")
        self.pmh_text.bind("<FocusIn>", clear_pmh_hint)

        # Current Medications
        meds_frame = ttk.Frame(context_frame)
        meds_frame.pack(fill=X, pady=(5, 5))

        ttk.Label(meds_frame, text="Current Medications:").pack(anchor=W)
        self.meds_text = tk.Text(meds_frame, height=2, wrap=tk.WORD, font=("Segoe UI", 10))
        self.meds_text.pack(fill=X, pady=(3, 0))
        self.meds_text.insert("1.0", "e.g., metformin 500mg BID, lisinopril 10mg daily...")
        self.meds_text.tag_add("hint", "1.0", "end")
        self.meds_text.tag_config("hint", foreground="gray")

        def clear_meds_hint(event=None):
            if self.meds_text.tag_ranges("hint"):
                self.meds_text.delete("1.0", "end")
                self.meds_text.tag_remove("hint", "1.0", "end")
        self.meds_text.bind("<FocusIn>", clear_meds_hint)

        # Allergies
        allergy_frame = ttk.Frame(context_frame)
        allergy_frame.pack(fill=X, pady=(5, 5))

        ttk.Label(allergy_frame, text="Allergies:").pack(side=LEFT)
        self.allergies_var = tk.StringVar()
        allergy_entry = ttk.Entry(allergy_frame, textvariable=self.allergies_var, width=50)
        allergy_entry.pack(side=LEFT, padx=(5, 0), fill=X, expand=True)

        # Past Surgical History
        psh_frame = ttk.Frame(context_frame)
        psh_frame.pack(fill=X, pady=(5, 5))

        ttk.Label(psh_frame, text="Past Surgical History:").pack(anchor=W)
        self.psh_text = tk.Text(psh_frame, height=2, wrap=tk.WORD, font=("Segoe UI", 10))
        self.psh_text.pack(fill=X, pady=(3, 0))
        self.psh_text.insert("1.0", "e.g., appendectomy 2015, cholecystectomy 2018...")
        self.psh_text.tag_add("hint", "1.0", "end")
        self.psh_text.tag_config("hint", foreground="gray")

        def clear_psh_hint(event=None):
            if self.psh_text.tag_ranges("hint"):
                self.psh_text.delete("1.0", "end")
                self.psh_text.tag_remove("hint", "1.0", "end")
        self.psh_text.bind("<FocusIn>", clear_psh_hint)

        # Family History
        fhx_frame = ttk.Frame(context_frame)
        fhx_frame.pack(fill=X, pady=(5, 5))

        ttk.Label(fhx_frame, text="Family History:").pack(anchor=W)
        self.fhx_text = tk.Text(fhx_frame, height=2, wrap=tk.WORD, font=("Segoe UI", 10))
        self.fhx_text.pack(fill=X, pady=(3, 0))
        self.fhx_text.insert("1.0", "e.g., Father: MI at 55, Mother: DM2, breast cancer...")
        self.fhx_text.tag_add("hint", "1.0", "end")
        self.fhx_text.tag_config("hint", foreground="gray")

        def clear_fhx_hint(event=None):
            if self.fhx_text.tag_ranges("hint"):
                self.fhx_text.delete("1.0", "end")
                self.fhx_text.tag_remove("hint", "1.0", "end")
        self.fhx_text.bind("<FocusIn>", clear_fhx_hint)

        # Social History
        shx_frame = ttk.Frame(context_frame)
        shx_frame.pack(fill=X, pady=(5, 5))

        ttk.Label(shx_frame, text="Social History:").pack(anchor=W)
        self.shx_text = tk.Text(shx_frame, height=2, wrap=tk.WORD, font=("Segoe UI", 10))
        self.shx_text.pack(fill=X, pady=(3, 0))
        self.shx_text.insert("1.0", "e.g., Smoker 20 pack-years, quit 2020; 2 drinks/week; retired teacher...")
        self.shx_text.tag_add("hint", "1.0", "end")
        self.shx_text.tag_config("hint", foreground="gray")

        def clear_shx_hint(event=None):
            if self.shx_text.tag_ranges("hint"):
                self.shx_text.delete("1.0", "end")
                self.shx_text.tag_remove("hint", "1.0", "end")
        self.shx_text.bind("<FocusIn>", clear_shx_hint)

        # Review of Systems (expandable)
        ros_frame = ttk.Labelframe(context_frame, text="Review of Systems (Click to expand)", padding=5)
        ros_frame.pack(fill=X, pady=(10, 0))

        self.ros_expanded = tk.BooleanVar(value=False)
        self.ros_content_frame = ttk.Frame(ros_frame)

        def toggle_ros():
            if self.ros_expanded.get():
                self.ros_content_frame.pack(fill=X, pady=(5, 0))
                ros_toggle_btn.config(text="▼ Hide Review of Systems")
            else:
                self.ros_content_frame.pack_forget()
                ros_toggle_btn.config(text="▶ Show Review of Systems")

        ros_toggle_btn = ttk.Button(
            ros_frame,
            text="▶ Show Review of Systems",
            command=lambda: [self.ros_expanded.set(not self.ros_expanded.get()), toggle_ros()],
            bootstyle="link"
        )
        ros_toggle_btn.pack(anchor=W)

        # ROS checkboxes in a grid
        self.ros_vars = {}
        ros_systems = [
            ("Constitutional", "constitutional", "Fever, fatigue, weight loss"),
            ("HEENT", "heent", "Headache, vision changes, hearing loss"),
            ("Cardiovascular", "cardiovascular", "Chest pain, palpitations, edema"),
            ("Respiratory", "respiratory", "Cough, SOB, wheezing"),
            ("GI", "gi", "Nausea, vomiting, abdominal pain, diarrhea"),
            ("GU", "gu", "Dysuria, frequency, hematuria"),
            ("Musculoskeletal", "musculoskeletal", "Joint pain, swelling, stiffness"),
            ("Neurological", "neurological", "Weakness, numbness, dizziness"),
            ("Psychiatric", "psychiatric", "Anxiety, depression, sleep issues"),
            ("Skin", "skin", "Rash, itching, lesions"),
            ("Endocrine", "endocrine", "Polydipsia, polyuria, heat/cold intolerance"),
            ("Heme/Lymph", "heme_lymph", "Easy bruising, lymphadenopathy"),
        ]

        for i, (label, key, tooltip) in enumerate(ros_systems):
            row = i // 3
            col = i % 3

            frame = ttk.Frame(self.ros_content_frame)
            frame.grid(row=row, column=col, sticky=W, padx=5, pady=2)

            self.ros_vars[key] = tk.StringVar(value="")
            cb = ttk.Checkbutton(
                frame,
                text=label,
                variable=self.ros_vars[key],
                onvalue=f"{label}: positive",
                offvalue=""
            )
            cb.pack(side=LEFT)

            # Add entry for notes
            entry = ttk.Entry(frame, width=15)
            entry.pack(side=LEFT, padx=(5, 0))
            entry.insert(0, "details...")
            entry.config(foreground="gray")

            def on_entry_focus_in(e, ent=entry):
                if ent.get() == "details...":
                    ent.delete(0, "end")
                    ent.config(foreground="black")

            def on_entry_focus_out(e, ent=entry, k=key):
                if not ent.get():
                    ent.insert(0, "details...")
                    ent.config(foreground="gray")
                else:
                    # Update the ROS var with details
                    if self.ros_vars[k].get():
                        self.ros_vars[k].set(f"{label}: {ent.get()}")

            entry.bind("<FocusIn>", on_entry_focus_in)
            entry.bind("<FocusOut>", on_entry_focus_out)

        # Configure grid columns
        for col in range(3):
            self.ros_content_frame.columnconfigure(col, weight=1)

        # ==================== SPECIALTY FOCUS ====================
        specialty_frame = ttk.Labelframe(main_frame, text="Specialty Focus", padding=15)
        specialty_frame.pack(fill=X, pady=(0, 15))

        ttk.Label(
            specialty_frame,
            text="Select a specialty lens for the differential diagnosis:",
            font=("Segoe UI", 10)
        ).pack(anchor=W, pady=(0, 10))

        self.specialty_var = tk.StringVar(value="general")

        # Create specialty options in a grid layout (2 columns)
        specialty_grid = ttk.Frame(specialty_frame)
        specialty_grid.pack(fill=X)

        for i, (label, value, description) in enumerate(SPECIALTY_OPTIONS):
            row = i // 2
            col = i % 2

            frame = ttk.Frame(specialty_grid)
            frame.grid(row=row, column=col, sticky=W, padx=5, pady=3)

            radio = ttk.Radiobutton(
                frame,
                text=label,
                variable=self.specialty_var,
                value=value
            )
            radio.pack(anchor=W)

            # Small description label
            desc_label = ttk.Label(
                frame,
                text=f"  {description}",
                font=("Segoe UI", 8),
                foreground="gray"
            )
            desc_label.pack(anchor=W)

        # Configure grid columns to expand equally
        specialty_grid.columnconfigure(0, weight=1)
        specialty_grid.columnconfigure(1, weight=1)

        # ==================== CUSTOM FINDINGS ====================
        custom_frame = ttk.Labelframe(main_frame, text="Custom Clinical Findings", padding=15)
        custom_frame.pack(fill=BOTH, expand=True, pady=(0, 15))

        ttk.Label(
            custom_frame,
            text="Enter symptoms, examination findings, lab results, etc.:",
            font=("Segoe UI", 10)
        ).pack(anchor=W, pady=(0, 10))

        text_frame = ttk.Frame(custom_frame)
        text_frame.pack(fill=BOTH, expand=True)

        self.custom_text = tk.Text(
            text_frame,
            wrap=tk.WORD,
            height=8,
            font=("Segoe UI", 11)
        )
        self.custom_text.pack(side=LEFT, fill=BOTH, expand=True)

        text_scrollbar = ttk.Scrollbar(text_frame, orient=VERTICAL, command=self.custom_text.yview)
        text_scrollbar.pack(side=RIGHT, fill=Y)
        self.custom_text.config(yscrollcommand=text_scrollbar.set)

        example_text = """Example:
- Severe headache for 2 weeks, right-sided
- Associated nausea and photophobia
- BP 130/85, HR 78, Temp 37.0°C
- Neurological exam normal
- Family history of migraines"""

        self.custom_text.insert("1.0", example_text)
        self.custom_text.tag_add("example", "1.0", "end")
        self.custom_text.tag_config("example", foreground="gray")

        def clear_example(event=None):
            if self.custom_text.tag_ranges("example"):
                self.custom_text.delete("1.0", "end")
                self.custom_text.tag_remove("example", "1.0", "end")
                self.custom_text.unbind("<FocusIn>")

        self.custom_text.bind("<FocusIn>", clear_example)

        # Enable/disable custom text based on selection
        def on_source_change(*args):
            if self.source_var.get() == "custom":
                self.custom_text.config(state=tk.NORMAL)
                clear_example()
            else:
                self.custom_text.config(state=tk.DISABLED)

        self.source_var.trace('w', on_source_change)
        on_source_change()

        # ==================== BUTTONS ====================
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=X, pady=(10, 0))

        ttk.Button(
            button_frame,
            text="Analyze",
            command=self._on_analyze,
            bootstyle="primary",
            width=15
        ).pack(side=RIGHT, padx=(5, 0))

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            width=15
        ).pack(side=RIGHT)

        # Keyboard bindings
        self.dialog.bind("<Return>", lambda e: self._on_analyze())
        self.dialog.bind("<Escape>", lambda e: self._on_cancel())

        # Cleanup mousewheel binding on close
        def on_close():
            canvas.unbind_all("<MouseWheel>")
            self._on_cancel()
        self.dialog.protocol("WM_DELETE_WINDOW", on_close)

        # Wait for dialog to close
        self.dialog.wait_window()

        return self.result

    def _get_patient_context(self) -> Optional[Dict]:
        """Build patient context dictionary from form inputs."""
        context = {}

        # Age
        age = self.age_var.get().strip()
        if age:
            try:
                context['age'] = int(age)
            except ValueError:
                pass  # Skip invalid age

        # Sex
        sex = self.sex_var.get()
        if sex:
            context['sex'] = sex

        # Pregnancy
        if self.pregnant_var.get():
            context['pregnant'] = True

        # Past Medical History
        pmh = self.pmh_text.get("1.0", "end").strip()
        if pmh and not pmh.startswith("e.g.,"):
            context['past_medical_history'] = pmh

        # Medications
        meds = self.meds_text.get("1.0", "end").strip()
        if meds and not meds.startswith("e.g.,"):
            context['current_medications'] = meds

        # Allergies
        allergies = self.allergies_var.get().strip()
        if allergies:
            context['allergies'] = allergies

        # Past Surgical History
        psh = self.psh_text.get("1.0", "end").strip()
        if psh and not psh.startswith("e.g.,"):
            context['past_surgical_history'] = psh

        # Family History
        fhx = self.fhx_text.get("1.0", "end").strip()
        if fhx and not fhx.startswith("e.g.,"):
            context['family_history'] = fhx

        # Social History
        shx = self.shx_text.get("1.0", "end").strip()
        if shx and not shx.startswith("e.g.,"):
            context['social_history'] = shx

        # Review of Systems
        ros_findings = []
        for key, var in self.ros_vars.items():
            value = var.get()
            if value and value != "":
                ros_findings.append(value)
        if ros_findings:
            context['review_of_systems'] = "; ".join(ros_findings)

        return context if context else None

    def _on_analyze(self):
        """Handle analyze button click."""
        source = self.source_var.get()

        if source == "custom":
            custom_findings = self.custom_text.get("1.0", "end").strip()
            if custom_findings.startswith("Example:") or not custom_findings:
                tk.messagebox.showwarning(
                    "No Custom Findings",
                    "Please enter clinical findings or select a different source.",
                    parent=self.dialog
                )
                return
        else:
            custom_findings = ""

        self.result = {
            "source": source,
            "custom_findings": custom_findings,
            "patient_context": self._get_patient_context(),
            "specialty": self.specialty_var.get()
        }

        self.dialog.destroy()

    def _on_cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()

    def _refresh_template_list(self) -> None:
        """Refresh the template dropdown with available templates."""
        templates = []
        if os.path.exists(self.TEMPLATES_DIR):
            for filename in os.listdir(self.TEMPLATES_DIR):
                if filename.endswith('.json'):
                    templates.append(filename[:-5])  # Remove .json extension
        templates.sort()
        self.template_combo['values'] = templates

    def _get_template_path(self, name: str) -> str:
        """Get the full path for a template.

        Args:
            name: Template name (without extension)

        Returns:
            Full path to template file
        """
        return os.path.join(self.TEMPLATES_DIR, f"{name}.json")

    def _save_template(self) -> None:
        """Save current patient context as a template."""
        # Get current context
        context = self._get_patient_context()
        if not context:
            messagebox.showwarning(
                "Empty Context",
                "Please fill in at least one field before saving.",
                parent=self.dialog
            )
            return

        # Ask for template name
        from tkinter import simpledialog
        name = simpledialog.askstring(
            "Save Template",
            "Enter a name for this template:",
            parent=self.dialog
        )

        if not name:
            return

        # Clean name for filename
        safe_name = "".join(c for c in name if c.isalnum() or c in (' ', '-', '_')).strip()
        if not safe_name:
            messagebox.showerror(
                "Invalid Name",
                "Template name must contain alphanumeric characters.",
                parent=self.dialog
            )
            return

        # Check if exists
        path = self._get_template_path(safe_name)
        if os.path.exists(path):
            if not messagebox.askyesno(
                "Overwrite",
                f"Template '{safe_name}' already exists. Overwrite?",
                parent=self.dialog
            ):
                return

        # Save template
        try:
            template_data = {
                'name': safe_name,
                'created': datetime.now().isoformat(),
                'context': context
            }
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(template_data, f, indent=2)

            self._refresh_template_list()
            self.template_var.set(safe_name)

            messagebox.showinfo(
                "Saved",
                f"Template '{safe_name}' saved successfully.",
                parent=self.dialog
            )
        except Exception as e:
            logging.error(f"Error saving template: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to save template: {e}",
                parent=self.dialog
            )

    def _load_template(self) -> None:
        """Load a template into the form."""
        name = self.template_var.get()
        if not name:
            messagebox.showinfo(
                "No Selection",
                "Please select a template to load.",
                parent=self.dialog
            )
            return

        path = self._get_template_path(name)
        if not os.path.exists(path):
            messagebox.showerror(
                "Not Found",
                f"Template '{name}' not found.",
                parent=self.dialog
            )
            return

        try:
            with open(path, 'r', encoding='utf-8') as f:
                template_data = json.load(f)

            context = template_data.get('context', {})
            self._apply_context(context)

            messagebox.showinfo(
                "Loaded",
                f"Template '{name}' loaded successfully.",
                parent=self.dialog
            )
        except Exception as e:
            logging.error(f"Error loading template: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to load template: {e}",
                parent=self.dialog
            )

    def _delete_template(self) -> None:
        """Delete the selected template."""
        name = self.template_var.get()
        if not name:
            messagebox.showinfo(
                "No Selection",
                "Please select a template to delete.",
                parent=self.dialog
            )
            return

        if not messagebox.askyesno(
            "Confirm Delete",
            f"Are you sure you want to delete template '{name}'?",
            parent=self.dialog
        ):
            return

        path = self._get_template_path(name)
        try:
            if os.path.exists(path):
                os.remove(path)
            self._refresh_template_list()
            self.template_var.set("")
            messagebox.showinfo(
                "Deleted",
                f"Template '{name}' deleted.",
                parent=self.dialog
            )
        except Exception as e:
            logging.error(f"Error deleting template: {e}")
            messagebox.showerror(
                "Error",
                f"Failed to delete template: {e}",
                parent=self.dialog
            )

    def _clear_context(self) -> None:
        """Clear all patient context fields."""
        # Demographics
        self.age_var.set("")
        self.sex_var.set("")
        self.pregnant_var.set(False)
        self.allergies_var.set("")

        # Text fields - clear and reset hints
        for text_widget, hint in [
            (self.pmh_text, "e.g., HTN, DM2, asthma..."),
            (self.meds_text, "e.g., metformin 500mg BID, lisinopril 10mg daily..."),
            (self.psh_text, "e.g., appendectomy 2015, cholecystectomy 2018..."),
            (self.fhx_text, "e.g., Father: MI at 55, Mother: DM2, breast cancer..."),
            (self.shx_text, "e.g., Smoker 20 pack-years, quit 2020; 2 drinks/week; retired teacher..."),
        ]:
            text_widget.delete("1.0", "end")
            text_widget.insert("1.0", hint)
            text_widget.tag_add("hint", "1.0", "end")
            text_widget.tag_config("hint", foreground="gray")

        # ROS checkboxes
        for key, var in self.ros_vars.items():
            var.set("")

        self.template_var.set("")

    def _apply_context(self, context: Dict) -> None:
        """Apply context data to form fields.

        Args:
            context: Context dictionary to apply
        """
        # Clear first
        self._clear_context()

        # Demographics
        if 'age' in context:
            self.age_var.set(str(context['age']))
        if 'sex' in context:
            self.sex_var.set(context['sex'])
        if context.get('pregnant'):
            self.pregnant_var.set(True)
        if 'allergies' in context:
            self.allergies_var.set(context['allergies'])

        # Text fields
        text_mappings = [
            ('past_medical_history', self.pmh_text),
            ('current_medications', self.meds_text),
            ('past_surgical_history', self.psh_text),
            ('family_history', self.fhx_text),
            ('social_history', self.shx_text),
        ]

        for key, text_widget in text_mappings:
            if key in context and context[key]:
                text_widget.delete("1.0", "end")
                text_widget.insert("1.0", context[key])
                # Remove hint tag if present
                text_widget.tag_remove("hint", "1.0", "end")

        # ROS - parse from stored string if present
        if 'review_of_systems' in context:
            ros_str = context['review_of_systems']
            for finding in ros_str.split(';'):
                finding = finding.strip()
                if ':' in finding:
                    system, details = finding.split(':', 1)
                    system = system.strip().lower()
                    # Map system name to key
                    system_key_map = {
                        'constitutional': 'constitutional',
                        'heent': 'heent',
                        'cardiovascular': 'cardiovascular',
                        'respiratory': 'respiratory',
                        'gi': 'gi',
                        'gu': 'gu',
                        'musculoskeletal': 'musculoskeletal',
                        'neurological': 'neurological',
                        'psychiatric': 'psychiatric',
                        'skin': 'skin',
                        'endocrine': 'endocrine',
                        'heme/lymph': 'heme_lymph',
                    }
                    for name, key in system_key_map.items():
                        if name in system.lower():
                            if key in self.ros_vars:
                                self.ros_vars[key].set(finding)
