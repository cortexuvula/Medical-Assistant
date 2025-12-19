"""
Generate Tab Component for Medical Assistant
Handles document generation UI
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from ui.hover_effects import ButtonHoverEffect
from ui.ui_constants import Fonts, Spacing, ButtonConfig


class GenerateTab:
    """Manages the Generate workflow tab UI components."""
    
    def __init__(self, parent_ui):
        """Initialize the GenerateTab component.
        
        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
    def create_generate_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Generate workflow tab.
        
        Args:
            command_map: Dictionary of commands
            
        Returns:
            ttk.Frame: The generate tab frame
        """
        generate_frame = ttk.Frame(self.parent)
        
        # Create a canvas and scrollbar for scrolling
        canvas = tk.Canvas(generate_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(generate_frame, orient="vertical", command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)
        
        scrollable_frame.bind(
            "<Configure>",
            lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        # Pack canvas and scrollbar
        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # Bind mouse wheel for scrolling
        def _on_mousewheel(event):
            canvas.yview_scroll(int(-1*(event.delta/120)), "units")
        
        def _bind_mousewheel(event):
            canvas.bind_all("<MouseWheel>", _on_mousewheel)
        
        def _unbind_mousewheel(event):
            canvas.unbind_all("<MouseWheel>")
        
        # Bind/unbind mousewheel when entering/leaving the canvas
        canvas.bind("<Enter>", _bind_mousewheel)
        canvas.bind("<Leave>", _unbind_mousewheel)
        
        # Document generation options
        gen_frame = ttk.LabelFrame(scrollable_frame, text="Generate Documents", padding=Spacing.LG)
        gen_frame.pack(fill=tk.BOTH, expand=True, padx=Spacing.XL, pady=Spacing.XL)
        
        # Create large buttons for each document type
        documents = [
            {
                "name": "soap",
                "text": "SOAP Note",
                "description": "Generate a structured SOAP note from the transcript",
                "command": command_map.get("create_soap_note"),
                "bootstyle": "success"
            },
            {
                "name": "referral",
                "text": "Referral",
                "description": "Create a professional referral letter",
                "command": command_map.get("create_referral"),
                "bootstyle": "info"
            },
            {
                "name": "letter",
                "text": "Letter",
                "description": "Generate a formal medical letter",
                "command": command_map.get("create_letter"),
                "bootstyle": "primary"
            },
            {
                "name": "diagnostic",
                "text": "Diagnostic Analysis",
                "description": "Analyze symptoms and generate differential diagnoses with ICD-9 codes",
                "command": command_map.get("create_diagnostic_analysis"),
                "bootstyle": "warning"
            },
            {
                "name": "medication",
                "text": "Medication Analysis",
                "description": "Extract medications, check interactions, and validate dosing",
                "command": command_map.get("analyze_medications"),
                "bootstyle": "danger"
            },
            {
                "name": "data_extraction",
                "text": "Extract Clinical Data",
                "description": "Extract structured data: vitals, labs, medications, diagnoses",
                "command": command_map.get("extract_clinical_data"),
                "bootstyle": "secondary"
            },
            {
                "name": "workflow",
                "text": "Clinical Workflow",
                "description": "Manage multi-step clinical processes and protocols",
                "command": command_map.get("manage_workflow"),
                "bootstyle": "dark"
            }
        ]
        
        # Create a centered container frame
        center_container = ttk.Frame(gen_frame)
        center_container.pack(expand=True)
        
        # Create buttons in a 2-column layout
        for i, doc in enumerate(documents):
            # Calculate row and column
            row = i // 2
            col = i % 2

            # Create a frame for each document type
            doc_frame = ttk.Frame(center_container)
            doc_frame.grid(row=row, column=col, sticky="ew", padx=Spacing.LG, pady=Spacing.MD)

            # Use outline style for hover effect transition
            bootstyle = f"{doc['bootstyle']}-outline"

            # Large button with consistent width
            btn = ttk.Button(
                doc_frame,
                text=doc["text"],
                command=doc["command"],
                bootstyle=bootstyle,
                width=ButtonConfig.WIDTH_XL,
                style="Large.TButton"
            )
            btn.pack(side=tk.LEFT, padx=(0, Spacing.MD))
            self.components[f"generate_{doc['name']}_button"] = btn

            # Add hover effect - fills in color on hover
            ButtonHoverEffect(btn, hover_bootstyle=doc["bootstyle"])

            # Description with wrapping
            desc_label = ttk.Label(
                doc_frame,
                text=doc["description"],
                font=Fonts.get_font(Fonts.SIZE_SM, scale_func=ui_scaler.scale_font_size),
                wraplength=ui_scaler.scale_dimension(250)
            )
            desc_label.pack(side=tk.LEFT, fill=tk.X, expand=True)

            ToolTip(btn, doc["description"])
        
        # Configure column weights to ensure equal spacing
        center_container.columnconfigure(0, weight=1)
        center_container.columnconfigure(1, weight=1)
        
        # Smart suggestions frame (initially hidden)
        suggestions_frame = ttk.LabelFrame(scrollable_frame, text="Suggestions", padding=Spacing.MD)
        self.components['suggestions_frame'] = suggestions_frame
        
        return generate_frame