"""
Workflow-Oriented UI Components for Medical Assistant

This module provides a task-based UI organization with three main workflows:
Record, Process, and Generate.
"""

import tkinter as tk
import tkinter.messagebox
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Dict, Callable, Tuple, Optional
from ui.tooltip import ToolTip
import logging
import time
import threading
import numpy as np
import os
from datetime import datetime
from settings.settings import SETTINGS


class WorkflowUI:
    """Manages the workflow-oriented user interface."""
    
    def __init__(self, parent):
        """Initialize the WorkflowUI.
        
        Args:
            parent: The parent widget (main application window)
        """
        self.parent = parent
        self.components = {}
        self.current_workflow = "record"
        
        # Timer functionality
        self.timer_start_time = None
        self.timer_paused_time = 0
        self.timer_thread = None
        self.timer_running = False
        
        
        # Recording status animation
        self.recording_pulse_state = 0
        self.pulse_animation_id = None
        self.status_indicator = None
        self.animation_active = False
        
        
    def create_workflow_tabs(self, command_map: Dict[str, Callable]) -> ttk.Notebook:
        """Create the main workflow tabs (Record, Process, Generate).
        
        Args:
            command_map: Dictionary mapping button names to their command functions
            
        Returns:
            ttk.Notebook: The workflow notebook widget
        """
        # Create main workflow notebook
        workflow_notebook = ttk.Notebook(self.parent, style="Workflow.TNotebook")
        
        # Create Record tab
        record_frame = self._create_record_tab(command_map)
        workflow_notebook.add(record_frame, text="Record")
        
        # Create Process tab
        process_frame = self._create_process_tab(command_map)
        workflow_notebook.add(process_frame, text="Process")
        
        # Create Generate tab
        generate_frame = self._create_generate_tab(command_map)
        workflow_notebook.add(generate_frame, text="Generate")
        
        # Create Recordings tab
        recordings_frame = self._create_recordings_tab(command_map)
        workflow_notebook.add(recordings_frame, text="Recordings")
        
        # Bind tab change event
        workflow_notebook.bind("<<NotebookTabChanged>>", self._on_workflow_tab_changed)
        
        self.components['workflow_notebook'] = workflow_notebook
        return workflow_notebook
    
    def _create_record_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Record workflow tab.
        
        Args:
            command_map: Dictionary of commands
            
        Returns:
            ttk.Frame: The record tab frame
        """
        record_frame = ttk.Frame(self.parent)
        
        # Main recording controls container (no longer using paned window)
        center_frame = ttk.Frame(record_frame)
        center_frame.pack(expand=True, fill=BOTH, padx=10, pady=5)
        
        # Recording status frame (for visual feedback)
        status_frame = ttk.Frame(center_frame)
        status_frame.pack(pady=(0, 5))
        
        # Status label
        self.components['recording_status'] = ttk.Label(
            status_frame, 
            text="", 
            font=("Segoe UI", 12)
        )
        self.components['recording_status'].pack()
        
        # Recording status indicator and main button
        record_button_frame = ttk.Frame(center_frame)
        record_button_frame.pack(pady=0)
        
        # Status indicator (animated when recording)
        status_frame = ttk.Frame(record_button_frame)
        status_frame.pack(pady=(0, 2))
        
        self.status_indicator = ttk.Label(
            status_frame,
            text="Ready",
            font=("Segoe UI", 10, "bold"),
            foreground="#27ae60"
        )
        self.status_indicator.pack()
        self.components['status_indicator'] = self.status_indicator
        
        self.components['main_record_button'] = ttk.Button(
            record_button_frame,
            text="Start Recording",
            command=command_map.get("toggle_soap_recording"),
            bootstyle="success",
            width=20,
            style="Large.TButton"
        )
        self.components['main_record_button'].pack()
        ToolTip(self.components['main_record_button'], "Click to start/stop recording (Ctrl+Shift+S)")
        
        # Fixed-height container for recording controls to prevent resize
        controls_container = ttk.Frame(center_frame, height=35)
        controls_container.pack(pady=1, fill=X)
        controls_container.pack_propagate(False)  # Maintain fixed height
        
        # Recording controls frame inside the container
        recording_controls = ttk.Frame(controls_container)
        recording_controls.pack(expand=True)
        self.components['recording_controls'] = recording_controls
        self.components['controls_container'] = controls_container
        
        self.components['pause_button'] = ttk.Button(
            recording_controls,
            text="Pause",
            command=command_map.get("toggle_soap_pause"),
            bootstyle="warning",
            width=10,
            state=DISABLED
        )
        self.components['pause_button'].pack(side=LEFT, padx=5)
        self.components['pause_button'].pack_forget()  # Initially hidden
        ToolTip(self.components['pause_button'], "Pause/Resume recording (Space)")
        
        self.components['cancel_button'] = ttk.Button(
            recording_controls,
            text="Cancel",
            command=command_map.get("cancel_soap_recording"),
            bootstyle="danger",
            width=10,
            state=DISABLED
        )
        self.components['cancel_button'].pack(side=LEFT, padx=5)
        self.components['cancel_button'].pack_forget()  # Initially hidden
        ToolTip(self.components['cancel_button'], "Cancel recording and discard audio (Esc)")
        
        # Fixed-height container for timer to prevent resize
        timer_container = ttk.Frame(center_frame, height=35)
        timer_container.pack(pady=2, fill=X)
        timer_container.pack_propagate(False)  # Maintain fixed height
        
        # Timer display inside the container
        self.components['timer_label'] = ttk.Label(
            timer_container,
            text="00:00",
            font=("Segoe UI", 20, "bold")
        )
        self.components['timer_label'].pack(expand=True)
        self.components['timer_container'] = timer_container
        
        # Fixed-height container for audio visualization to prevent resize
        audio_viz_container = ttk.Frame(center_frame, height=50)
        audio_viz_container.pack(pady=(0, 3), fill=X)
        audio_viz_container.pack_propagate(False)  # Maintain fixed height
        
        # Audio visualization panel inside the container
        audio_viz_frame = ttk.Frame(audio_viz_container)
        audio_viz_frame.pack(fill=BOTH, expand=True)
        self.components['audio_viz_frame'] = audio_viz_frame
        self.components['audio_viz_container'] = audio_viz_container
        
        
        
        # Recording session info panel
        info_frame = ttk.Frame(audio_viz_frame)
        info_frame.pack(fill=X, padx=5, pady=(2, 0))
        
        # Session info labels
        self.session_info_frame = ttk.Frame(info_frame)
        self.session_info_frame.pack(fill=X)
        
        info_left = ttk.Frame(self.session_info_frame)
        info_left.pack(side=LEFT, fill=X, expand=True)
        
        self.quality_label = ttk.Label(info_left, text="Quality: 44.1kHz • 16-bit", font=("Segoe UI", 8), foreground="gray")
        self.quality_label.pack(side=LEFT)
        
        info_right = ttk.Frame(self.session_info_frame)
        info_right.pack(side=RIGHT)
        
        self.file_size_label = ttk.Label(info_right, text="Size: 0 KB", font=("Segoe UI", 8), foreground="gray")
        self.file_size_label.pack(side=RIGHT, padx=(5, 0))
        
        self.duration_label = ttk.Label(info_right, text="Duration: 00:00", font=("Segoe UI", 8), foreground="gray")
        self.duration_label.pack(side=RIGHT, padx=(5, 0))
        
        self.components['session_info'] = {
            'quality': self.quality_label,
            'file_size': self.file_size_label,
            'duration': self.duration_label
        }
        
        # Quick actions (appear after recording)
        quick_actions = ttk.Frame(center_frame)
        # Initially hidden
        
        self.components['quick_actions'] = quick_actions
        
        # Initialize UI state - hide controls initially
        self._initialize_recording_ui_state()
        
        return record_frame
    
    def _create_process_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Process workflow tab.
        
        Args:
            command_map: Dictionary of commands
            
        Returns:
            ttk.Frame: The process tab frame
        """
        process_frame = ttk.Frame(self.parent)
        
        # Text processing tools
        tools_frame = ttk.LabelFrame(process_frame, text="Text Processing Tools", padding=15)
        tools_frame.pack(fill=X, padx=20, pady=20)
        
        # Create tool buttons in a grid
        tools = [
            {
                "name": "refine",
                "text": "Refine Text",
                "tooltip": "Clean up punctuation and capitalization",
                "command": command_map.get("refine_text"),
                "row": 0,
                "column": 0
            },
            {
                "name": "improve",
                "text": "Improve Text",
                "tooltip": "Enhance clarity and readability",
                "command": command_map.get("improve_text"),
                "row": 0,
                "column": 1
            },
            {
                "name": "undo",
                "text": "Undo",
                "tooltip": "Undo last change (Ctrl+Z)",
                "command": command_map.get("undo_text"),
                "row": 1,
                "column": 0
            },
            {
                "name": "redo",
                "text": "Redo",
                "tooltip": "Redo last change (Ctrl+Y)",
                "command": command_map.get("redo_text"),
                "row": 1,
                "column": 1
            }
        ]
        
        for tool in tools:
            btn = ttk.Button(
                tools_frame,
                text=tool["text"],
                command=tool["command"],
                bootstyle="info",
                width=20
            )
            btn.grid(row=tool["row"], column=tool["column"], padx=10, pady=10, sticky="ew")
            ToolTip(btn, tool["tooltip"])
            self.components[f"process_{tool['name']}_button"] = btn
        
        # Configure grid weights
        tools_frame.columnconfigure(0, weight=1)
        tools_frame.columnconfigure(1, weight=1)
        
        # File operations
        file_frame = ttk.LabelFrame(process_frame, text="File Operations", padding=15)
        file_frame.pack(fill=X, padx=20, pady=(0, 20))
        
        file_ops = [
            {
                "name": "save",
                "text": "Save",
                "tooltip": "Save transcript and audio",
                "command": command_map.get("save_text"),
                "column": 0
            },
            {
                "name": "load",
                "text": "Load Audio",
                "tooltip": "Load and transcribe audio file",
                "command": command_map.get("load_audio_file"),
                "column": 1
            },
            {
                "name": "new_session",
                "text": "New Session",
                "tooltip": "Start a new session (Ctrl+N)",
                "command": command_map.get("new_session"),
                "column": 2
            }
        ]
        
        for op in file_ops:
            btn = ttk.Button(
                file_frame,
                text=op["text"],
                command=op["command"],
                bootstyle="primary",
                width=15
            )
            btn.grid(row=0, column=op["column"], padx=10, pady=10, sticky="ew")
            ToolTip(btn, op["tooltip"])
            self.components[f"file_{op['name']}_button"] = btn
        
        # Configure grid weights
        for i in range(3):
            file_frame.columnconfigure(i, weight=1)
        
        return process_frame
    
    def _create_generate_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
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
        gen_frame = ttk.LabelFrame(scrollable_frame, text="Generate Documents", padding=15)
        gen_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)
        
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
        
        # Use a more compact layout with smaller padding
        for i, doc in enumerate(documents):
            # Create a frame for each document type
            doc_frame = ttk.Frame(gen_frame)
            doc_frame.grid(row=i, column=0, sticky="ew", padx=10, pady=5)
            gen_frame.columnconfigure(0, weight=1)
            
            # Large button with responsive width
            btn = ttk.Button(
                doc_frame,
                text=doc["text"],
                command=doc["command"],
                bootstyle=doc["bootstyle"],
                width=20,  # Slightly smaller width
                style="Large.TButton"
            )
            btn.pack(side=LEFT, padx=(0, 10))
            self.components[f"generate_{doc['name']}_button"] = btn
            
            # Description with wrapping
            desc_label = ttk.Label(
                doc_frame,
                text=doc["description"],
                font=("Segoe UI", 9),  # Slightly smaller font
                wraplength=300  # Enable text wrapping
            )
            desc_label.pack(side=LEFT, fill=X, expand=True)
            
            ToolTip(btn, doc["description"])
        
        # Smart suggestions frame (initially hidden)
        suggestions_frame = ttk.LabelFrame(scrollable_frame, text="Suggestions", padding=10)
        self.components['suggestions_frame'] = suggestions_frame
        
        return generate_frame
    
    def _create_recordings_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Recordings workflow tab.
        
        Args:
            command_map: Dictionary mapping button names to their command functions
            
        Returns:
            ttk.Frame: The recordings tab frame
        """
        recordings_frame = ttk.Frame(self.parent)
        
        # Create the recordings panel that fills the entire tab
        recordings_panel = self._create_recordings_panel(recordings_frame)
        recordings_panel.pack(fill=BOTH, expand=True, padx=10, pady=10)
        self.components['recordings_panel'] = recordings_panel
        
        return recordings_frame
    
    def _on_workflow_tab_changed(self, event):
        """Handle workflow tab change event."""
        notebook = event.widget
        tab_index = notebook.index("current")
        tab_names = ["record", "process", "generate", "recordings"]
        
        if 0 <= tab_index < len(tab_names):
            self.current_workflow = tab_names[tab_index]
            logging.debug(f"Switched to {self.current_workflow} workflow")
            
            # Refresh recordings list when switching to Recordings tab
            if self.current_workflow == "recordings":
                self._refresh_recordings_list()
            
            # Trigger any workflow-specific updates
            if hasattr(self.parent, 'on_workflow_changed'):
                self.parent.on_workflow_changed(self.current_workflow)
    
    def create_context_panel(self) -> ttk.Frame:
        """Create the persistent context side panel.
        
        Returns:
            ttk.Frame: The context panel frame
        """
        # Create a collapsible side panel
        context_panel = ttk.Frame(self.parent)
        
        # Header with collapse button
        header_frame = ttk.Frame(context_panel)
        header_frame.pack(fill=X, padx=5, pady=5)
        
        self.components['context_collapse_btn'] = ttk.Button(
            header_frame,
            text="<",
            width=3,
            command=self._toggle_context_panel
        )
        self.components['context_collapse_btn'].pack(side=LEFT)
        
        ttk.Label(
            header_frame, 
            text="Context", 
            font=("Segoe UI", 12, "bold")
        ).pack(side=LEFT, padx=10)
        
        # Context content frame
        content_frame = ttk.Frame(context_panel)
        content_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)
        self.components['context_content_frame'] = content_frame
        
        # Quick templates
        self.templates_frame = ttk.LabelFrame(content_frame, text="Quick Templates", padding=10)
        self.templates_frame.pack(fill=X, pady=(0, 10))
        
        # Create initial templates
        self._create_template_buttons()
        
        # Context text area
        text_frame = ttk.LabelFrame(content_frame, text="Context Information", padding=10)
        text_frame.pack(fill=BOTH, expand=True)
        
        # Create text widget with scrollbar
        text_scroll = ttk.Scrollbar(text_frame)
        text_scroll.pack(side=RIGHT, fill=Y)
        
        self.components['context_text'] = tk.Text(
            text_frame,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set,
            height=10,
            width=30
        )
        self.components['context_text'].pack(fill=BOTH, expand=True)
        text_scroll.config(command=self.components['context_text'].yview)
        
        # Context actions
        actions_frame = ttk.Frame(content_frame)
        actions_frame.pack(fill=X, pady=5)
        
        ttk.Button(
            actions_frame,
            text="Save Template",
            bootstyle="info",
            command=self._save_context_template
        ).pack(side=LEFT, padx=2)
        
        ttk.Button(
            actions_frame,
            text="Clear",
            bootstyle="secondary",
            command=self._clear_context
        ).pack(side=LEFT, padx=2)
        
        self.components['context_panel'] = context_panel
        self._context_collapsed = False
        
        return context_panel
    
    def _toggle_context_panel(self):
        """Toggle the context panel visibility."""
        if self._context_collapsed:
            # Expand
            self.components['context_content_frame'].pack(fill=BOTH, expand=True, padx=10, pady=5)
            self.components['context_collapse_btn'].config(text="<")
            self._context_collapsed = False
        else:
            # Collapse
            self.components['context_content_frame'].pack_forget()
            self.components['context_collapse_btn'].config(text=">")
            self._context_collapsed = True
    
    def _apply_context_template(self, template: str):
        """Apply a context template."""
        template_texts = {
            "Follow-up visit": "Follow-up visit for ongoing condition.",
            "New patient": "New patient consultation. No previous medical history available.",
            "Telehealth consultation": "Telehealth consultation via video call.",
            "Annual checkup": "Annual health checkup and preventive care visit.",
            "Urgent care visit": "Urgent care visit for acute symptoms."
        }
        
        if template in template_texts:
            self.components['context_text'].delete("1.0", tk.END)
            self.components['context_text'].insert("1.0", template_texts[template])
    
    def _save_context_template(self):
        """Save current context as a template."""
        # Get current context text
        context_text = self.components['context_text'].get("1.0", tk.END).strip()
        
        if not context_text:
            tkinter.messagebox.showwarning("No Content", "Please enter some context text before saving as a template.")
            return
        
        # Create dialog to get template name
        dialog = tk.Toplevel(self.parent)
        dialog.title("Save Context Template")
        dialog.geometry("400x200")
        dialog.resizable(False, False)
        dialog.transient(self.parent)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - (dialog.winfo_width() // 2)
        y = (dialog.winfo_screenheight() // 2) - (dialog.winfo_height() // 2)
        dialog.geometry(f"+{x}+{y}")
        
        # Dialog content
        ttk.Label(dialog, text="Template Name:", font=("Segoe UI", 11)).pack(pady=10)
        
        name_var = tk.StringVar()
        name_entry = ttk.Entry(dialog, textvariable=name_var, width=40, font=("Segoe UI", 10))
        name_entry.pack(pady=5)
        name_entry.focus()
        
        # Preview of content
        ttk.Label(dialog, text="Content Preview:", font=("Segoe UI", 10)).pack(pady=(15, 5))
        preview_text = context_text[:100] + "..." if len(context_text) > 100 else context_text
        preview_label = ttk.Label(dialog, text=preview_text, font=("Segoe UI", 9), foreground="gray")
        preview_label.pack(pady=5, padx=20)
        
        result = {"saved": False}
        
        def save_template():
            template_name = name_var.get().strip()
            if not template_name:
                tkinter.messagebox.showwarning("Invalid Name", "Please enter a template name.")
                return
            
            # Save to settings
            try:
                custom_templates = SETTINGS.get("custom_context_templates", {})
                custom_templates[template_name] = context_text
                SETTINGS["custom_context_templates"] = custom_templates
                
                # Save settings
                from settings.settings import save_settings
                save_settings(SETTINGS)
                
                # Refresh template buttons
                self._refresh_template_buttons()
                
                result["saved"] = True
                dialog.destroy()
                
                tkinter.messagebox.showinfo("Template Saved", f"Template '{template_name}' has been saved successfully!")
                
            except Exception as e:
                logging.error(f"Error saving context template: {e}")
                tkinter.messagebox.showerror("Error", f"Failed to save template: {str(e)}")
        
        def cancel():
            dialog.destroy()
        
        # Buttons
        button_frame = ttk.Frame(dialog)
        button_frame.pack(pady=20)
        
        ttk.Button(button_frame, text="Save", command=save_template, bootstyle="success").pack(side=LEFT, padx=5)
        ttk.Button(button_frame, text="Cancel", command=cancel, bootstyle="secondary").pack(side=LEFT, padx=5)
        
        # Bind Enter key to save
        name_entry.bind("<Return>", lambda e: save_template())
        dialog.bind("<Escape>", lambda e: cancel())
        
        # Wait for dialog to close
        dialog.wait_window()
    
    def _create_template_buttons(self):
        """Create template buttons including built-in and custom templates."""
        # Built-in templates
        builtin_templates = [
            "Follow-up visit",
            "New patient", 
            "Telehealth consultation",
            "Annual checkup",
            "Urgent care visit"
        ]
        
        # Clear existing buttons
        for widget in self.templates_frame.winfo_children():
            widget.destroy()
        
        # Add built-in templates
        for template in builtin_templates:
            btn = ttk.Button(
                self.templates_frame,
                text=template,
                bootstyle="outline",
                command=lambda t=template: self._apply_context_template(t)
            )
            btn.pack(pady=3, padx=5, fill=X)
        
        # Add custom templates
        custom_templates = SETTINGS.get("custom_context_templates", {})
        if custom_templates:
            # Add separator
            separator = ttk.Separator(self.templates_frame, orient="horizontal")
            separator.pack(fill=X, pady=5)
            
            # Add custom template buttons
            for template_name, template_text in custom_templates.items():
                btn_frame = ttk.Frame(self.templates_frame)
                btn_frame.pack(fill=X, pady=3, padx=5)
                
                # Template button
                btn = ttk.Button(
                    btn_frame,
                    text=template_name,
                    bootstyle="info-outline",
                    command=lambda t=template_text: self._apply_custom_template(t)
                )
                btn.pack(side=LEFT, fill=X, expand=True, padx=(0, 3))
                
                # Delete button
                del_btn = ttk.Button(
                    btn_frame,
                    text="X",
                    bootstyle="danger-outline",
                    width=3,
                    command=lambda name=template_name: self._delete_custom_template(name)
                )
                del_btn.pack(side=RIGHT, padx=(2, 0))
                ToolTip(del_btn, f"Delete template '{template_name}'")
    
    def _refresh_template_buttons(self):
        """Refresh the template buttons to show updated custom templates."""
        self._create_template_buttons()
    
    def _apply_custom_template(self, template_text: str):
        """Apply a custom template."""
        self.components['context_text'].delete("1.0", tk.END)
        self.components['context_text'].insert("1.0", template_text)
    
    def _delete_custom_template(self, template_name: str):
        """Delete a custom template."""
        result = tkinter.messagebox.askyesno(
            "Delete Template",
            f"Are you sure you want to delete the template '{template_name}'?",
            icon="warning"
        )
        
        if result:
            try:
                custom_templates = SETTINGS.get("custom_context_templates", {})
                if template_name in custom_templates:
                    del custom_templates[template_name]
                    SETTINGS["custom_context_templates"] = custom_templates
                    
                    # Save settings
                    from settings.settings import save_settings
                    save_settings(SETTINGS)
                    
                    # Refresh template buttons
                    self._refresh_template_buttons()
                    
                    tkinter.messagebox.showinfo("Template Deleted", f"Template '{template_name}' has been deleted.")
                    
            except Exception as e:
                logging.error(f"Error deleting custom template: {e}")
                tkinter.messagebox.showerror("Error", f"Failed to delete template: {str(e)}")
    
    def _clear_context(self):
        """Clear the context text."""
        self.components['context_text'].delete("1.0", tk.END)
    
    def show_quick_actions(self, actions: list):
        """Show quick action buttons after recording.
        
        Args:
            actions: List of action dictionaries with 'text', 'command', and 'style'
        """
        # Clear existing actions
        for widget in self.components['quick_actions'].winfo_children():
            widget.destroy()
        
        # Create new action buttons
        for action in actions:
            btn = ttk.Button(
                self.components['quick_actions'],
                text=action['text'],
                command=action['command'],
                bootstyle=action.get('style', 'primary'),
                width=15
            )
            btn.pack(side=LEFT, padx=5)
        
        # Show the quick actions frame
        self.components['quick_actions'].pack(pady=20)
    
    def hide_quick_actions(self):
        """Hide the quick actions frame."""
        self.components['quick_actions'].pack_forget()
    
    def update_recording_status(self, status: str, style: str = "default"):
        """Update the recording status display.
        
        Args:
            status: Status text to display
            style: Style to apply (default, recording, paused, processing)
        """
        status_label = self.components.get('recording_status')
        if status_label:
            status_label.config(text=status)
            
            # Apply style-specific formatting
            if style == "recording":
                status_label.config(foreground="red")
            elif style == "paused":
                status_label.config(foreground="orange")
            elif style == "processing":
                status_label.config(foreground="blue")
            else:
                status_label.config(foreground="")
    
    def update_timer(self, time_str: str):
        """Update the timer display.
        
        Args:
            time_str: Time string to display (e.g., "01:23")
        """
        timer_label = self.components.get('timer_label')
        if timer_label:
            timer_label.config(text=time_str)
        
        # Update session duration info
        session_info = self.components.get('session_info')
        if session_info and 'duration' in session_info:
            session_info['duration'].config(text=f"Duration: {time_str}")
        
        # Estimate file size (rough calculation: 44.1kHz * 2 bytes * time)
        try:
            parts = time_str.split(':')
            if len(parts) == 2:
                minutes = int(parts[0])
                seconds = int(parts[1])
                total_seconds = minutes * 60 + seconds
                
                # Rough estimate: 44100 Hz * 2 bytes/sample * 1 channel * seconds
                estimated_bytes = total_seconds * 44100 * 2
                
                if estimated_bytes < 1024:
                    size_str = f"{estimated_bytes} B"
                elif estimated_bytes < 1024 * 1024:
                    size_str = f"{estimated_bytes // 1024} KB"
                else:
                    size_str = f"{estimated_bytes // (1024 * 1024)} MB"
                
                if session_info and 'file_size' in session_info:
                    session_info['file_size'].config(text=f"Size: ~{size_str}")
        except:
            pass  # Ignore errors in size calculation
    
    def set_recording_state(self, recording: bool, paused: bool = False):
        """Update UI elements based on recording state.
        
        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        logging.info(f"WorkflowUI.set_recording_state called: recording={recording}, paused={paused}")
        
        main_record_btn = self.components.get('main_record_button')
        pause_btn = self.components.get('pause_button')
        cancel_btn = self.components.get('cancel_button')
        recording_controls = self.components.get('recording_controls')
        timer_label = self.components.get('timer_label')
        
        logging.info(f"Button components found: main_record={main_record_btn is not None}, pause={pause_btn is not None}, cancel={cancel_btn is not None}")
        
        # Debug: Check current button text
        if main_record_btn:
            current_text = main_record_btn.cget('text')
            logging.info(f"Current main record button text: '{current_text}'")
        
        if recording:
            # Update main record button
            if main_record_btn:
                main_record_btn.config(text="Stop Recording", bootstyle="danger")
                logging.info("Main record button updated to 'Stop Recording'")
                # Force immediate UI update
                main_record_btn.update_idletasks()
                main_record_btn.update()
                # Verify the change took effect
                new_text = main_record_btn.cget('text')
                logging.info(f"Main record button text after update: '{new_text}'")
            
            # Show the recording controls buttons
            if pause_btn:
                pause_btn.pack(side=LEFT, padx=10)
            if cancel_btn:
                cancel_btn.pack(side=LEFT, padx=10)
            logging.info("Recording controls visible")
            
            # Enable and configure pause button
            if pause_btn:
                pause_btn.config(state=tk.NORMAL)
                if paused:
                    pause_btn.config(text="Resume", bootstyle="success")
                    # Pause timer
                    self.pause_timer()
                else:
                    pause_btn.config(text="Pause", bootstyle="warning")
                    # Start or resume timer
                    if not self.timer_running and self.timer_start_time is None:
                        self.start_timer()
                    elif not self.timer_running:
                        self.resume_timer()
                logging.info(f"Pause button enabled: {pause_btn['state']}")
                
            # Enable cancel button
            if cancel_btn:
                cancel_btn.config(state=tk.NORMAL)
                logging.info(f"Cancel button enabled: {cancel_btn['state']}")
            
            # Show timer label with current time
            if timer_label:
                if self.timer_paused_time > 0:
                    # We have paused time, so show it
                    minutes = int(self.timer_paused_time // 60)
                    seconds = int(self.timer_paused_time % 60)
                    time_str = f"{minutes:02d}:{seconds:02d}"
                    timer_label.config(text=time_str)
                else:
                    # Fresh start
                    timer_label.config(text="00:00")
            
            # Show audio visualization content
            audio_viz_frame = self.components.get('audio_viz_frame')
            if audio_viz_frame:
                # Re-pack the info frame if needed
                for child in audio_viz_frame.winfo_children():
                    child.pack(fill=X, padx=10, pady=(5, 0))
            
            self._start_pulse_animation()
                
            # Force a UI update to ensure changes are visible
            if self.parent:
                self.parent.update_idletasks()
                self.parent.update()  # Additional update to ensure UI refresh
        else:
            # Not recording - reset everything
            if main_record_btn:
                main_record_btn.config(text="Start Recording", bootstyle="success", state=tk.NORMAL)
                logging.info("Main record button updated to 'Start Recording'")
                # Force immediate UI update
                main_record_btn.update_idletasks()
                main_record_btn.update()
                # Verify the change took effect
                new_text = main_record_btn.cget('text')
                logging.info(f"Main record button text after reset: '{new_text}'")
                
            # Disable pause button
            if pause_btn:
                pause_btn.config(state=tk.DISABLED, text="Pause", bootstyle="warning")
                
            # Disable cancel button  
            if cancel_btn:
                cancel_btn.config(state=tk.DISABLED)
            
            # Stop and reset timer
            self.stop_timer()
            
            # Hide the recording control buttons
            if pause_btn:
                pause_btn.pack_forget()
            if cancel_btn:
                cancel_btn.pack_forget()
            
            # Hide timer label (but keep container)
            if timer_label:
                timer_label.config(text="")  # Empty text
            
            # Hide audio viz content (but keep container)
            audio_viz_frame = self.components.get('audio_viz_frame')
            if audio_viz_frame:
                for child in audio_viz_frame.winfo_children():
                    child.pack_forget()
            
            self._stop_pulse_animation()
            
            # Force UI update for stop recording state
            if self.parent:
                self.parent.update_idletasks()
                self.parent.update()  # Additional update to ensure UI refresh
    
    def update_recording_progress(self, progress_text: str):
        """Update recording progress/status text.
        
        Args:
            progress_text: Status text to display
        """
        status_label = self.components.get('recording_status')
        if status_label:
            status_label.config(text=progress_text)
    
    def start_timer(self):
        """Start the recording timer."""
        # Stop any existing timer first
        self._reset_timer_state()
        
        # Reset timer state
        self.timer_start_time = time.time()
        self.timer_paused_time = 0
        self.timer_running = True
        
        # Start new timer thread
        self.timer_thread = threading.Thread(target=self._update_timer_loop, daemon=True)
        self.timer_thread.start()
        logging.info("Timer started (fresh)")
    
    def pause_timer(self):
        """Pause the recording timer."""
        if self.timer_running and self.timer_start_time:
            # Calculate and save the current elapsed time
            current_elapsed = time.time() - self.timer_start_time
            self.timer_paused_time += current_elapsed
            self.timer_running = False
            
            # Keep displaying the paused time
            total_elapsed = self.timer_paused_time
            minutes = int(total_elapsed // 60)
            seconds = int(total_elapsed % 60)
            time_str = f"{minutes:02d}:{seconds:02d}"
            self.update_timer(time_str)
            
            logging.info(f"Timer paused at {time_str}")
    
    def resume_timer(self):
        """Resume the recording timer."""
        if not self.timer_running:
            self.timer_start_time = time.time()
            self.timer_running = True
            
            # Restart timer thread if it's not running
            if self.timer_thread is None or not self.timer_thread.is_alive():
                self.timer_thread = threading.Thread(target=self._update_timer_loop, daemon=True)
                self.timer_thread.start()
            
            logging.info("Timer resumed")
    
    def _reset_timer_state(self):
        """Internal method to reset timer state without UI updates."""
        self.timer_running = False
        self.timer_start_time = None
        self.timer_paused_time = 0
        # Note: thread will stop itself when timer_running becomes False
    
    def stop_timer(self):
        """Stop and reset the recording timer."""
        self._reset_timer_state()
        
        # Update display to 00:00
        timer_label = self.components.get('timer_label')
        if timer_label:
            timer_label.config(text="00:00")
        logging.info("Timer stopped and reset")
    
    def _update_timer_loop(self):
        """Timer update loop (runs in background thread)."""
        while True:
            try:
                # Check if we should exit the loop (only when timer is fully stopped/reset)
                if self.timer_start_time is None and self.timer_paused_time == 0:
                    break
                    
                if self.timer_running and self.timer_start_time is not None:
                    # Timer is running - calculate elapsed time
                    current_elapsed = time.time() - self.timer_start_time
                    total_elapsed = self.timer_paused_time + current_elapsed
                    
                    # Format time as MM:SS
                    minutes = int(total_elapsed // 60)
                    seconds = int(total_elapsed % 60)
                    time_str = f"{minutes:02d}:{seconds:02d}"
                    
                    # Update timer display on main thread
                    if self.parent:
                        def update_display(time_text=time_str):
                            self.update_timer(time_text)
                        self.parent.after(0, update_display)
                
                # Update every second
                time.sleep(1)
            except Exception as e:
                logging.error(f"Timer update error: {e}")
                break
    
    def _start_pulse_animation(self):
        """Start the recording status pulse animation."""
        if self.status_indicator:
            self.animation_active = True
            self._animate_pulse()
    
    def _stop_pulse_animation(self):
        """Stop the recording status pulse animation."""
        logging.info("Stopping pulse animation")
        self.animation_active = False
        if self.pulse_animation_id:
            self.parent.after_cancel(self.pulse_animation_id)
            self.pulse_animation_id = None
            logging.info("Pulse animation cancelled")
        
        # Reset status indicator
        if self.status_indicator:
            self.status_indicator.config(text="Ready", foreground="#27ae60")
            # Force immediate UI update
            self.status_indicator.update_idletasks()
            self.status_indicator.update()
            logging.info("Status indicator reset to Ready")
    
    def _animate_pulse(self):
        """Animate the recording status indicator."""
        if not self.status_indicator or not self.animation_active:
            return
            
        try:
            # Pulse animation cycle
            self.recording_pulse_state = (self.recording_pulse_state + 1) % 60
            
            # Calculate opacity/color intensity
            pulse_intensity = (np.sin(self.recording_pulse_state * 0.2) + 1) / 2  # 0 to 1
            
            # Interpolate between dark and bright red
            intensity = int(128 + (127 * pulse_intensity))
            color = f"#{intensity:02x}3030"
            
            # Update status text and color
            if self.recording_pulse_state < 30:
                text = "Recording"
            else:
                text = "Recording"
                
            self.status_indicator.config(text=text, foreground=color)
            
            # Schedule next frame only if still active
            if self.animation_active:
                self.pulse_animation_id = self.parent.after(50, self._animate_pulse)
            
        except Exception as e:
            logging.error(f"Error in pulse animation: {e}")
    
    def create_status_bar(self) -> tuple:
        """Create the status bar at the bottom of the application.
        
        Returns:
            tuple: (status_frame, status_icon_label, status_label, provider_indicator, progress_bar)
        """
        status_frame = ttk.Frame(self.parent, padding=(10, 5))
        
        # Configure for responsive layout
        status_frame.columnconfigure(1, weight=1)  # Status label should expand
        
        # Status icon
        status_icon_label = ttk.Label(status_frame, text="", font=("Segoe UI", 16), foreground="gray")
        status_icon_label.pack(side=LEFT, padx=(5, 0))
        
        # Status text
        status_label = ttk.Label(
            status_frame, 
            text="Status: Idle", 
            anchor="w",
            font=("Segoe UI", 10)
        )
        status_label.pack(side=LEFT, fill=tk.X, expand=True, padx=(5, 0))
        
        # Provider indicator
        provider = SETTINGS.get("ai_provider", "openai").capitalize()
        stt_provider = SETTINGS.get("stt_provider", "groq").upper()
        provider_indicator = ttk.Label(
            status_frame, 
            text=f"AI: {provider} | STT: {stt_provider}",
            anchor="e",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        provider_indicator.pack(side=LEFT, padx=(0, 10))
        
        # Queue status indicator
        queue_status_label = ttk.Label(
            status_frame,
            text="",  # Empty initially
            anchor="e",
            font=("Segoe UI", 9, "bold"),
            foreground="gray"
        )
        queue_status_label.pack(side=LEFT, padx=(0, 10))
        
        # Store reference for later use
        self.components['queue_status_label'] = queue_status_label
        
        # Progress bar
        progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        progress_bar.pack(side=RIGHT, padx=10)
        progress_bar.stop()
        progress_bar.pack_forget()
        
        # Update status manager with queue label after it's created
        if hasattr(self.parent, 'status_manager') and self.parent.status_manager:
            self.parent.status_manager.set_queue_status_label(queue_status_label)
        
        return status_frame, status_icon_label, status_label, provider_indicator, progress_bar
    
    def create_notebook(self) -> tuple:
        """Create the notebook with tabs for transcript, soap note, referral, letter, and chat.
        
        Returns:
            tuple: (notebook, transcript_text, soap_text, referral_text, letter_text, chat_text, context_text)
        """
        notebook = ttk.Notebook(self.parent, style="Green.TNotebook")
        
        # Create tabs
        tabs = [
            ("Transcript", "transcript"),
            ("SOAP Note", "soap"),
            ("Referral", "referral"),
            ("Letter", "letter"),
            ("Chat", "chat")
        ]
        
        text_widgets = {}
        
        for tab_name, widget_key in tabs:
            # Create frame for each tab
            frame = ttk.Frame(notebook)
            notebook.add(frame, text=tab_name)
            
            # Create text widget with scrollbar
            text_scroll = ttk.Scrollbar(frame)
            text_scroll.pack(side=RIGHT, fill=Y)
            
            text_widget = tk.Text(
                frame,
                wrap=tk.WORD,
                yscrollcommand=text_scroll.set,
                undo=True,
                autoseparators=True
            )
            text_widget.pack(fill=BOTH, expand=True)
            text_scroll.config(command=text_widget.yview)
            
            # Store reference
            text_widgets[widget_key] = text_widget
            
            # Add welcome message to chat tab
            if widget_key == "chat":
                text_widget.insert("1.0", "Welcome to the Medical Assistant Chat!\n\n")
                text_widget.insert("end", "This is your ChatGPT-style interface where you can:\n")
                text_widget.insert("end", "• Ask medical questions\n")
                text_widget.insert("end", "• Get explanations about medical terms\n")
                text_widget.insert("end", "• Have conversations about healthcare topics\n")
                text_widget.insert("end", "• Clear the chat with 'clear chat' command\n\n")
                text_widget.insert("end", "Type your message in the AI Assistant chat box below to start chatting with the AI!\n")
                text_widget.insert("end", "="*50 + "\n\n")
                
                # Configure initial styling
                text_widget.tag_config("welcome", foreground="gray", font=("Arial", 10, "italic"))
                text_widget.tag_add("welcome", "1.0", "end")
                
                # Make text widget read-only but still selectable
                text_widget.bind("<Key>", lambda e: "break" if e.keysym not in ["Up", "Down", "Left", "Right", "Prior", "Next", "Home", "End"] else None)
        
        # Return in expected order
        return (
            notebook,
            text_widgets["transcript"],
            text_widgets["soap"],
            text_widgets["referral"],
            text_widgets["letter"],
            text_widgets["chat"],
            None  # No context text in notebook for workflow UI
        )
    
    def _initialize_recording_ui_state(self):
        """Initialize the recording UI to its default state."""
        # Hide timer label initially (but keep container visible)
        timer_label = self.components.get('timer_label')
        if timer_label:
            timer_label.config(text="")  # Empty text instead of invisible
            
        # Hide audio viz content initially (but keep container visible)
        audio_viz_frame = self.components.get('audio_viz_frame')
        if audio_viz_frame:
            for child in audio_viz_frame.winfo_children():
                child.pack_forget()
                
        # Ensure pause and cancel buttons start in disabled state
        pause_btn = self.components.get('pause_button')
        cancel_btn = self.components.get('cancel_button')
        if pause_btn:
            pause_btn.config(state=tk.DISABLED)
        if cancel_btn:
            cancel_btn.config(state=tk.DISABLED)
    
    def _create_recordings_panel(self, parent_frame: ttk.Frame) -> ttk.LabelFrame:
        """Create a panel showing recent recordings.
        
        Args:
            parent_frame: Parent frame to place the panel in
            
        Returns:
            ttk.LabelFrame: The recordings panel
        """
        # Create the labeled frame
        recordings_frame = ttk.LabelFrame(parent_frame, text="Recent Recordings", padding=5)
        
        # Create controls frame at the top
        controls_frame = ttk.Frame(recordings_frame)
        controls_frame.pack(fill=X, pady=(0, 5))
        
        # Search box
        search_frame = ttk.Frame(controls_frame)
        search_frame.pack(side=LEFT, fill=X, expand=True)
        
        ttk.Label(search_frame, text="Search:", font=("Segoe UI", 9)).pack(side=LEFT, padx=(0, 5))
        self.recordings_search_var = tk.StringVar()
        search_entry = ttk.Entry(search_frame, textvariable=self.recordings_search_var, width=30)
        search_entry.pack(side=LEFT, fill=X, expand=True)
        search_entry.bind("<KeyRelease>", lambda e: self._filter_recordings())
        
        # Refresh button
        refresh_btn = ttk.Button(controls_frame, text="⟳", width=3, 
                                command=self._refresh_recordings_list)
        refresh_btn.pack(side=RIGHT, padx=(5, 0))
        ToolTip(refresh_btn, "Refresh recordings list")
        
        # Create treeview with scrollbar
        tree_container = ttk.Frame(recordings_frame)
        tree_container.pack(fill=BOTH, expand=True)
        
        # Scrollbar
        scrollbar = ttk.Scrollbar(tree_container)
        scrollbar.pack(side=RIGHT, fill=Y)
        
        # Create compact treeview
        columns = ("date", "time", "transcription", "soap", "referral", "letter")
        self.recordings_tree = ttk.Treeview(
            tree_container,
            columns=columns,
            show="tree headings",
            height=7,  # Show 7 rows for better visibility
            selectmode="browse",
            yscrollcommand=scrollbar.set
        )
        scrollbar.config(command=self.recordings_tree.yview)
        self.recordings_tree.pack(side=LEFT, fill=BOTH, expand=True)
        
        # Configure columns
        self.recordings_tree.heading("#0", text="ID", anchor=tk.W)
        self.recordings_tree.heading("date", text="Date", anchor=tk.W)
        self.recordings_tree.heading("time", text="Time", anchor=tk.W)
        self.recordings_tree.heading("transcription", text="Transcription", anchor=tk.CENTER)
        self.recordings_tree.heading("soap", text="SOAP Note", anchor=tk.CENTER)
        self.recordings_tree.heading("referral", text="Referral", anchor=tk.CENTER)
        self.recordings_tree.heading("letter", text="Letter", anchor=tk.CENTER)
        
        # Set column widths with anchor for centering
        self.recordings_tree.column("#0", width=50, minwidth=40, stretch=False, anchor=tk.W)
        self.recordings_tree.column("date", width=100, minwidth=80, anchor=tk.W)
        self.recordings_tree.column("time", width=80, minwidth=60, anchor=tk.W)
        self.recordings_tree.column("transcription", width=90, minwidth=70, anchor=tk.CENTER)
        self.recordings_tree.column("soap", width=90, minwidth=70, anchor=tk.CENTER)
        self.recordings_tree.column("referral", width=80, minwidth=60, anchor=tk.CENTER)
        self.recordings_tree.column("letter", width=80, minwidth=60, anchor=tk.CENTER)
        
        # Configure tags for styling
        self.recordings_tree.tag_configure("complete", foreground="#27ae60")
        self.recordings_tree.tag_configure("processing", foreground="#f39c12")
        self.recordings_tree.tag_configure("partial", foreground="#3498db")
        self.recordings_tree.tag_configure("failed", foreground="#e74c3c")
        
        # Configure column-specific styling
        self.recordings_tree.tag_configure("has_content", foreground="#27ae60")  # Green for checkmarks
        self.recordings_tree.tag_configure("no_content", foreground="#888888")   # Gray for dashes
        self.recordings_tree.tag_configure("processing_content", foreground="#f39c12")  # Orange for processing
        self.recordings_tree.tag_configure("failed_content", foreground="#e74c3c")  # Red for failed
        
        # Action buttons - split into two rows for better layout
        actions_frame = ttk.Frame(recordings_frame)
        actions_frame.pack(fill=X, pady=(5, 0))
        
        # First row of buttons
        row1_frame = ttk.Frame(actions_frame)
        row1_frame.pack(fill=X)
        
        # Load button
        load_btn = ttk.Button(
            row1_frame,
            text="Load",
            command=self._load_selected_recording,
            bootstyle="primary-outline",
            width=10
        )
        load_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(load_btn, "Load selected recording")
        
        # Delete button
        delete_btn = ttk.Button(
            row1_frame,
            text="Delete",
            command=self._delete_selected_recording,
            bootstyle="danger-outline",
            width=10
        )
        delete_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(delete_btn, "Delete selected recording")
        
        # Export button
        export_btn = ttk.Button(
            row1_frame,
            text="Export",
            command=self._export_selected_recording,
            bootstyle="info-outline",
            width=10
        )
        export_btn.pack(side=LEFT, padx=(0, 5))
        ToolTip(export_btn, "Export selected recording")
        
        # Clear All button
        clear_all_btn = ttk.Button(
            row1_frame,
            text="Clear All",
            command=self._clear_all_recordings,
            bootstyle="danger-outline",
            width=10
        )
        clear_all_btn.pack(side=LEFT)
        ToolTip(clear_all_btn, "Clear all recordings from database")
        
        # Recording count label - place in second row
        row2_frame = ttk.Frame(actions_frame)
        row2_frame.pack(fill=X, pady=(5, 0))
        
        self.recording_count_label = ttk.Label(
            row2_frame,
            text="0 recordings",
            font=("Segoe UI", 9),
            foreground="gray"
        )
        self.recording_count_label.pack(side=LEFT)
        
        # Bind double-click to load
        self.recordings_tree.bind("<Double-Button-1>", lambda e: self._load_selected_recording())
        
        # Load initial recordings
        self._refresh_recordings_list()
        
        return recordings_frame
    
    def _refresh_recordings_list(self):
        """Refresh the recordings list from database."""
        def task():
            try:
                # Get recent recordings from database
                recordings = self.parent.db.get_all_recordings()
                # Update UI on main thread
                self.parent.after(0, lambda: self._populate_recordings_tree(recordings))
            except Exception as e:
                logging.error(f"Error loading recordings: {e}")
                self.parent.after(0, lambda: self.recording_count_label.config(text="Error loading recordings"))
        
        # Run in background thread
        threading.Thread(target=task, daemon=True).start()
    
    def _populate_recordings_tree(self, recordings: list):
        """Populate the recordings tree with data."""
        # Clear existing items
        for item in self.recordings_tree.get_children():
            self.recordings_tree.delete(item)
        
        # Add recordings
        for recording in recordings:
            try:
                rec_id = recording['id']
                
                # Parse timestamp
                timestamp = recording.get('timestamp', '')
                if timestamp:
                    try:
                        dt_obj = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        date_str = dt_obj.strftime("%Y-%m-%d")
                        time_str = dt_obj.strftime("%H:%M")
                    except:
                        date_str = timestamp.split()[0] if ' ' in timestamp else timestamp
                        time_str = timestamp.split()[1] if ' ' in timestamp else ""
                else:
                    date_str = "Unknown"
                    time_str = ""
                
                # Determine completion status for each type
                has_transcript = bool(recording.get('transcript'))
                has_soap = bool(recording.get('soap_note'))
                has_referral = bool(recording.get('referral'))
                has_letter = bool(recording.get('letter'))
                processing_status = recording.get('processing_status', '')
                
                # Status indicators with standard checkmarks
                if processing_status == 'processing':
                    transcript_status = "🔄" if not has_transcript else "✓"
                    soap_status = "🔄" if not has_soap else "✓"
                    referral_status = "🔄" if not has_referral else "✓"
                    letter_status = "🔄" if not has_letter else "✓"
                    tag = "processing"
                elif processing_status == 'failed':
                    transcript_status = "❌" if not has_transcript else "✓"
                    soap_status = "❌" if not has_soap else "✓"
                    referral_status = "❌" if not has_referral else "✓"
                    letter_status = "❌" if not has_letter else "✓"
                    tag = "failed"
                else:
                    transcript_status = "✓" if has_transcript else "—"
                    soap_status = "✓" if has_soap else "—"
                    referral_status = "✓" if has_referral else "—"
                    letter_status = "✓" if has_letter else "—"
                    
                    # Determine overall tag based on what content exists
                    content_count = sum([has_transcript, has_soap, has_referral, has_letter])
                    if content_count == 4:
                        tag = "complete"  # All green
                    elif content_count >= 2:
                        tag = "partial"   # Mixed green/gray
                    elif content_count == 1:
                        tag = "has_content"  # Some green
                    else:
                        tag = "no_content"   # All gray
                
                # Insert into tree with appropriate tag for coloring
                self.recordings_tree.insert(
                    "", "end",
                    text=str(rec_id),
                    values=(date_str, time_str, transcript_status, soap_status, referral_status, letter_status),
                    tags=(tag,)
                )
            except Exception as e:
                logging.error(f"Error adding recording to tree: {e}")
        
        # Update count
        count = len(self.recordings_tree.get_children())
        self.recording_count_label.config(text=f"{count} recording{'s' if count != 1 else ''}")
    
    def _filter_recordings(self):
        """Filter recordings based on search text."""
        search_text = self.recordings_search_var.get().lower()
        
        if not search_text:
            # Show all items
            for item in self.recordings_tree.get_children():
                self.recordings_tree.reattach(item, '', 'end')
        else:
            # Hide non-matching items
            for item in self.recordings_tree.get_children():
                values = self.recordings_tree.item(item, 'values')
                # Search in date, time, and completion status columns
                # Also search in the ID (text field)
                id_text = self.recordings_tree.item(item, 'text')
                searchable_values = list(values) + [id_text]
                if any(search_text in str(v).lower() for v in searchable_values):
                    self.recordings_tree.reattach(item, '', 'end')
                else:
                    self.recordings_tree.detach(item)
    
    def _load_selected_recording(self):
        """Load the selected recording into the main application."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to load.")
            return
        
        # Get recording ID
        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))
        
        try:
            # Get full recording data
            recording = self.parent.db.get_recording(rec_id)
            if not recording:
                tk.messagebox.showerror("Error", "Recording not found in database.")
                return
            
            # Clear existing content
            from utils.cleanup_utils import clear_all_content
            clear_all_content(self.parent)
            
            # Load data into UI
            if recording.get('transcript'):
                self.parent.transcript_text.insert("1.0", recording['transcript'])
                self.parent.notebook.select(0)  # Switch to transcript tab
            
            if recording.get('soap_note'):
                self.parent.soap_text.insert("1.0", recording['soap_note'])
                if not recording.get('transcript'):
                    self.parent.notebook.select(1)  # Switch to SOAP tab
            
            if recording.get('referral'):
                self.parent.referral_text.insert("1.0", recording['referral'])
            
            if recording.get('letter'):
                self.parent.letter_text.insert("1.0", recording['letter'])
            
            # Load chat content if available
            if hasattr(self.parent, 'chat_text') and recording.get('chat'):
                self.parent.chat_text.insert("1.0", recording['chat'])
            
            # Update status
            self.parent.status_manager.success(f"Loaded recording #{rec_id}")
            
            # Update current recording ID
            self.parent.current_recording_id = rec_id
            
        except Exception as e:
            logging.error(f"Error loading recording: {e}")
            tk.messagebox.showerror("Load Error", f"Failed to load recording: {str(e)}")
    
    def _delete_selected_recording(self):
        """Delete the selected recording."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to delete.")
            return
        
        # Confirm deletion
        if not tk.messagebox.askyesno("Confirm Delete", "Are you sure you want to delete this recording?"):
            return
        
        # Get recording ID
        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))
        
        try:
            # Delete from database
            self.parent.db.delete_recording(rec_id)
            
            # Remove from tree
            self.recordings_tree.delete(item)
            
            # Update count
            count = len(self.recordings_tree.get_children())
            self.recording_count_label.config(text=f"{count} recording{'s' if count != 1 else ''}")
            
            # Update status
            self.parent.status_manager.success("Recording deleted")
            
        except Exception as e:
            logging.error(f"Error deleting recording: {e}")
            tk.messagebox.showerror("Delete Error", f"Failed to delete recording: {str(e)}")
    
    def _export_selected_recording(self):
        """Export the selected recording."""
        selection = self.recordings_tree.selection()
        if not selection:
            tk.messagebox.showwarning("No Selection", "Please select a recording to export.")
            return
        
        # Get recording ID
        item = selection[0]
        rec_id = int(self.recordings_tree.item(item, 'text'))
        
        try:
            # Get full recording data
            recording = self.parent.db.get_recording(rec_id)
            if not recording:
                tk.messagebox.showerror("Error", "Recording not found in database.")
                return
            
            # Ask for export format
            from tkinter import filedialog
            file_path = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[
                    ("Text files", "*.txt"),
                    ("All files", "*.*")
                ],
                title="Export Recording"
            )
            
            if not file_path:
                return
            
            # Create export content
            content = []
            content.append(f"Medical Recording Export - ID: {rec_id}")
            content.append(f"Date: {recording.get('timestamp', 'Unknown')}")
            content.append(f"Patient: {recording.get('patient_name', 'Unknown')}")
            content.append("=" * 50)
            
            if recording.get('transcript'):
                content.append("\nTRANSCRIPT:")
                content.append(recording['transcript'])
            
            if recording.get('soap_note'):
                content.append("\n\nSOAP NOTE:")
                content.append(recording['soap_note'])
            
            if recording.get('referral'):
                content.append("\n\nREFERRAL:")
                content.append(recording['referral'])
            
            if recording.get('letter'):
                content.append("\n\nLETTER:")
                content.append(recording['letter'])
            
            # Write to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(content))
            
            self.parent.status_manager.success(f"Recording exported to {os.path.basename(file_path)}")
            
        except Exception as e:
            logging.error(f"Error exporting recording: {e}")
            tk.messagebox.showerror("Export Error", f"Failed to export recording: {str(e)}")
    
    def _clear_all_recordings(self):
        """Clear all recordings from the database."""
        # Confirm deletion with a strong warning
        result = tkinter.messagebox.askyesno(
            "Clear All Recordings",
            "WARNING: This will permanently delete ALL recordings from the database.\n\n"
            "This action cannot be undone!\n\n"
            "Are you absolutely sure you want to continue?",
            icon="warning"
        )
        
        if not result:
            return
        
        # Double confirmation for safety
        result2 = tkinter.messagebox.askyesno(
            "Final Confirmation",
            "This is your last chance to cancel.\n\n"
            "Delete ALL recordings permanently?",
            icon="warning"
        )
        
        if not result2:
            return
        
        try:
            # Clear all recordings from database
            success = self.parent.db.clear_all_recordings()
            
            if success:
                # Clear the tree view
                for item in self.recordings_tree.get_children():
                    self.recordings_tree.delete(item)
                
                # Update count
                self.recording_count_label.config(text="0 recordings")
                
                # Clear any currently loaded content
                from utils.cleanup_utils import clear_all_content
                clear_all_content(self.parent)
                
                # Reset current recording ID
                self.parent.current_recording_id = None
                
                # Update status
                self.parent.status_manager.success("All recordings cleared from database")
                
                tkinter.messagebox.showinfo(
                    "Success",
                    "All recordings have been cleared from the database."
                )
            else:
                tkinter.messagebox.showerror(
                    "Error",
                    "Failed to clear recordings from database."
                )
                
        except Exception as e:
            logging.error(f"Error clearing all recordings: {e}")
            tkinter.messagebox.showerror(
                "Clear Error",
                f"Failed to clear recordings: {str(e)}"
            )