"""
Medication Analysis Dialog

Provides a dialog for users to select the type of medication analysis
and the source of content to analyze.
"""

import tkinter as tk
from ui.scaling_utils import ui_scaler
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Optional, Dict


class MedicationAnalysisDialog:
    """Dialog for configuring medication analysis options."""
    
    def __init__(self, parent):
        """Initialize the medication analysis dialog.
        
        Args:
            parent: Parent window
        """
        self.parent = parent
        self.result = None
        self.has_transcript = False
        self.has_soap = False
        self.has_context = False
        
    def set_available_content(self, has_transcript: bool, has_soap: bool, has_context: bool = False):
        """Set what content is available for analysis.
        
        Args:
            has_transcript: Whether transcript content is available
            has_soap: Whether SOAP note content is available
            has_context: Whether context content is available
        """
        self.has_transcript = has_transcript
        self.has_soap = has_soap
        self.has_context = has_context
        
    def show(self) -> Optional[Dict]:
        """Show the dialog and return user selection.
        
        Returns:
            Dictionary with 'analysis_type', 'source' and optional 'custom_medications', or None if cancelled
        """
        # Create dialog window
        self.dialog = tk.Toplevel(self.parent)
        self.dialog.title("Medication Analysis Options")
        
        # Get screen dimensions
        screen_width = self.dialog.winfo_screenwidth()
        screen_height = self.dialog.winfo_screenheight()
        
        # Set dialog size to fit screen better
        dialog_width = min(900, int(screen_width * 0.8))
        dialog_height = min(700, int(screen_height * 0.85))
        
        self.dialog.geometry(f"{dialog_width}x{dialog_height}")
        self.dialog.minsize(800, 500)
        self.dialog.transient(self.parent)

        # Center the dialog
        self.dialog.update_idletasks()
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.dialog.geometry(f"{dialog_width}x{dialog_height}+{x}+{y}")

        # Grab focus after window is visible
        self.dialog.deiconify()
        try:
            self.dialog.grab_set()
        except tk.TclError:
            pass  # Window not viewable yet, will still work without grab
        
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
        # Get theme colors for canvas
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
        
        # Use scrollable_frame as the main frame
        main_frame = scrollable_frame
        
        # Title
        title_label = ttk.Label(
            main_frame, 
            text="Configure Medication Analysis",
            font=("Segoe UI", 14, "bold")
        )
        title_label.pack(pady=(0, 10))
        
        # Analysis type selection
        type_frame = ttk.Labelframe(main_frame, text="Analysis Type", padding=10)
        type_frame.pack(fill=X, pady=(0, 10))
        
        self.analysis_type_var = tk.StringVar(value="comprehensive")
        
        # Analysis type options
        analysis_types = [
            ("comprehensive", "Comprehensive Analysis", "Full medication review including extraction, interactions, and recommendations"),
            ("extract", "Extract Medications", "Extract all medications mentioned in the text"),
            ("interactions", "Check Interactions", "Check for drug-drug interactions"),
            ("dosing", "Validate Dosing", "Validate medication dosing for patient"),
            ("alternatives", "Suggest Alternatives", "Suggest alternative medications"),
            ("prescription", "Generate Prescription", "Generate prescription format")
        ]
        
        for value, text, description in analysis_types:
            frame = ttk.Frame(type_frame)
            frame.pack(fill=X, pady=2)
            
            ttk.Radiobutton(
                frame,
                text=text,
                variable=self.analysis_type_var,
                value=value
            ).pack(anchor=W)
            
            ttk.Label(
                frame,
                text=f"    {description}",
                foreground="gray",
                font=("Segoe UI", 9)
            ).pack(anchor=W, padx=(20, 0))
        
        # Source selection
        source_frame = ttk.Labelframe(main_frame, text="Content Source", padding=10)
        source_frame.pack(fill=X, pady=(0, 10))
        
        # Set default source based on availability
        if self.has_transcript:
            default_source = "transcript"
        elif self.has_soap:
            default_source = "soap"
        elif self.has_context:
            default_source = "context"
        else:
            default_source = "custom"
        self.source_var = tk.StringVar(value=default_source)
        
        # Transcript option
        transcript_radio = ttk.Radiobutton(
            source_frame,
            text="Use current transcript",
            variable=self.source_var,
            value="transcript",
            state=NORMAL if self.has_transcript else DISABLED
        )
        transcript_radio.pack(anchor=W, pady=5)
        
        if not self.has_transcript:
            ttk.Label(
                source_frame,
                text="    (No transcript available)",
                foreground="gray"
            ).pack(anchor=W)
        
        # SOAP note option
        soap_radio = ttk.Radiobutton(
            source_frame,
            text="Use current SOAP note",
            variable=self.source_var,
            value="soap",
            state=NORMAL if self.has_soap else DISABLED
        )
        soap_radio.pack(anchor=W, pady=5)
        
        if not self.has_soap:
            ttk.Label(
                source_frame,
                text="    (No SOAP note available)",
                foreground="gray"
            ).pack(anchor=W)
        
        # Context option
        context_radio = ttk.Radiobutton(
            source_frame,
            text="Use context information",
            variable=self.source_var,
            value="context",
            state=NORMAL if self.has_context else DISABLED
        )
        context_radio.pack(anchor=W, pady=5)
        
        if not self.has_context:
            ttk.Label(
                source_frame,
                text="    (No context information available)",
                foreground="gray"
            ).pack(anchor=W)
        
        # Custom input option
        custom_radio = ttk.Radiobutton(
            source_frame,
            text="Enter custom medications or text",
            variable=self.source_var,
            value="custom"
        )
        custom_radio.pack(anchor=W, pady=5)

        # Patient context section
        patient_frame = ttk.Labelframe(main_frame, text="Patient Context (Optional - Improves Analysis)", padding=10)
        patient_frame.pack(fill=X, pady=(0, 10))

        context_note = ttk.Label(
            patient_frame,
            text="Providing patient details improves dosing validation and safety checks",
            foreground="gray",
            font=("Segoe UI", 9, "italic")
        )
        context_note.pack(anchor=W, pady=(0, 10))

        # Create a grid for patient context fields
        fields_frame = ttk.Frame(patient_frame)
        fields_frame.pack(fill=X)

        # Row 1: Age and Weight
        row1 = ttk.Frame(fields_frame)
        row1.pack(fill=X, pady=2)

        # Age
        age_frame = ttk.Frame(row1)
        age_frame.pack(side=LEFT, padx=(0, 20))
        ttk.Label(age_frame, text="Age:").pack(side=LEFT)
        self.age_var = tk.StringVar()
        age_entry = ttk.Entry(age_frame, textvariable=self.age_var, width=8)
        age_entry.pack(side=LEFT, padx=(5, 0))
        ttk.Label(age_frame, text="years", foreground="gray").pack(side=LEFT, padx=(3, 0))

        # Weight
        weight_frame = ttk.Frame(row1)
        weight_frame.pack(side=LEFT, padx=(0, 20))
        ttk.Label(weight_frame, text="Weight:").pack(side=LEFT)
        self.weight_var = tk.StringVar()
        weight_entry = ttk.Entry(weight_frame, textvariable=self.weight_var, width=8)
        weight_entry.pack(side=LEFT, padx=(5, 0))
        ttk.Label(weight_frame, text="kg", foreground="gray").pack(side=LEFT, padx=(3, 0))

        # Row 2: eGFR and Hepatic Function
        row2 = ttk.Frame(fields_frame)
        row2.pack(fill=X, pady=2)

        # eGFR (renal function)
        egfr_frame = ttk.Frame(row2)
        egfr_frame.pack(side=LEFT, padx=(0, 20))
        ttk.Label(egfr_frame, text="eGFR:").pack(side=LEFT)
        self.egfr_var = tk.StringVar()
        egfr_entry = ttk.Entry(egfr_frame, textvariable=self.egfr_var, width=8)
        egfr_entry.pack(side=LEFT, padx=(5, 0))
        ttk.Label(egfr_frame, text="mL/min", foreground="gray").pack(side=LEFT, padx=(3, 0))

        # Hepatic function
        hepatic_frame = ttk.Frame(row2)
        hepatic_frame.pack(side=LEFT, padx=(0, 20))
        ttk.Label(hepatic_frame, text="Hepatic:").pack(side=LEFT)
        self.hepatic_var = tk.StringVar(value="normal")
        hepatic_combo = ttk.Combobox(
            hepatic_frame,
            textvariable=self.hepatic_var,
            values=["normal", "Child-Pugh A (mild)", "Child-Pugh B (moderate)", "Child-Pugh C (severe)"],
            state="readonly",
            width=20
        )
        hepatic_combo.pack(side=LEFT, padx=(5, 0))

        # Row 3: Allergies
        row3 = ttk.Frame(fields_frame)
        row3.pack(fill=X, pady=(5, 0))

        ttk.Label(row3, text="Known Drug Allergies:").pack(anchor=W)
        self.allergies_var = tk.StringVar()
        allergies_entry = ttk.Entry(row3, textvariable=self.allergies_var)
        allergies_entry.pack(fill=X, pady=(3, 0))
        ttk.Label(
            row3,
            text="Separate multiple allergies with commas (e.g., Penicillin, Sulfa, NSAIDs)",
            foreground="gray",
            font=("Segoe UI", 9)
        ).pack(anchor=W)

        # Custom medications input
        custom_frame = ttk.Labelframe(main_frame, text="Custom Input (Optional)", padding=10)
        custom_frame.pack(fill=BOTH, expand=True, pady=(0, 10))
        
        # Instructions
        instructions = ttk.Label(
            custom_frame,
            text="Enter medications or clinical text below (one per line for medication lists):",
            foreground="gray"
        )
        instructions.pack(anchor=W, pady=(0, 10))
        
        # Text input with scrollbar
        text_frame = ttk.Frame(custom_frame)
        text_frame.pack(fill=BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        self.custom_text = tk.Text(
            text_frame,
            height=3,
            wrap=WORD,
            yscrollcommand=scrollbar.set
        )
        self.custom_text.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.config(command=self.custom_text.yview)
        
        # Example text
        example_text = ttk.Label(
            custom_frame,
            text="Example: Aspirin 81mg daily, Metformin 500mg BID, Lisinopril 10mg daily",
            foreground="gray",
            font=("Segoe UI", 9, "italic")
        )
        example_text.pack(anchor=W, pady=(10, 0))
        
        # Add buttons to the button frame created earlier
        ttk.Button(
            button_frame,
            text="Cancel",
            command=self._cancel,
            style="secondary.TButton"
        ).pack(side=RIGHT, padx=(5, 0))
        
        ttk.Button(
            button_frame,
            text="Analyze",
            command=self._analyze,
            style="primary.TButton"
        ).pack(side=RIGHT)
        
        # Focus on custom text if that's selected
        if self.source_var.get() == "custom":
            self.custom_text.focus_set()
        
        # Wait for dialog to close
        self.dialog.wait_window()
        
        return self.result
    
    def _analyze(self):
        """Handle analyze button click."""
        analysis_type = self.analysis_type_var.get()
        source = self.source_var.get()
        custom_medications = self.custom_text.get("1.0", "end").strip()

        # Validate custom input if selected
        if source == "custom" and not custom_medications:
            tk.messagebox.showwarning(
                "No Input",
                "Please enter medications or clinical text to analyze.",
                parent=self.dialog
            )
            return

        # Collect patient context
        patient_context = {}

        # Age (validate if provided)
        age = self.age_var.get().strip()
        if age:
            try:
                age_val = int(age)
                if 0 < age_val < 150:
                    patient_context["age"] = age_val
            except ValueError:
                pass  # Invalid age, ignore

        # Weight (validate if provided)
        weight = self.weight_var.get().strip()
        if weight:
            try:
                weight_val = float(weight)
                if 0 < weight_val < 500:
                    patient_context["weight_kg"] = weight_val
            except ValueError:
                pass  # Invalid weight, ignore

        # eGFR (validate if provided)
        egfr = self.egfr_var.get().strip()
        if egfr:
            try:
                egfr_val = float(egfr)
                if 0 <= egfr_val <= 200:
                    patient_context["egfr"] = egfr_val
            except ValueError:
                pass  # Invalid eGFR, ignore

        # Hepatic function
        hepatic = self.hepatic_var.get()
        if hepatic and hepatic != "normal":
            patient_context["hepatic_function"] = hepatic

        # Allergies
        allergies = self.allergies_var.get().strip()
        if allergies:
            # Parse comma-separated list and clean up
            allergy_list = [a.strip() for a in allergies.split(",") if a.strip()]
            if allergy_list:
                patient_context["allergies"] = allergy_list

        self.result = {
            "analysis_type": analysis_type,
            "source": source,
            "custom_medications": custom_medications if source == "custom" else "",
            "patient_context": patient_context if patient_context else None
        }
        self.dialog.destroy()
    
    def _cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()