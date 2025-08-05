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
        type_frame = ttk.LabelFrame(main_frame, text="Analysis Type", padding=10)
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
        source_frame = ttk.LabelFrame(main_frame, text="Content Source", padding=10)
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
        
        # Custom medications input
        custom_frame = ttk.LabelFrame(main_frame, text="Custom Input (Optional)", padding=10)
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
        
        self.result = {
            "analysis_type": analysis_type,
            "source": source,
            "custom_medications": custom_medications if source == "custom" else ""
        }
        self.dialog.destroy()
    
    def _cancel(self):
        """Handle cancel button click."""
        self.result = None
        self.dialog.destroy()