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
from tooltip import ToolTip
import logging
from settings import SETTINGS


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
        workflow_notebook.add(record_frame, text="📝 Record")
        
        # Create Process tab
        process_frame = self._create_process_tab(command_map)
        workflow_notebook.add(process_frame, text="✨ Process")
        
        # Create Generate tab
        generate_frame = self._create_generate_tab(command_map)
        workflow_notebook.add(generate_frame, text="📄 Generate")
        
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
        
        # Center the main recording controls
        center_frame = ttk.Frame(record_frame)
        center_frame.pack(expand=True, fill=BOTH, padx=20, pady=20)
        
        # Recording status frame (for visual feedback)
        status_frame = ttk.Frame(center_frame)
        status_frame.pack(pady=(0, 20))
        
        # Status label
        self.components['recording_status'] = ttk.Label(
            status_frame, 
            text="Ready to Record", 
            font=("Segoe UI", 14)
        )
        self.components['recording_status'].pack()
        
        # Waveform visualization placeholder
        waveform_frame = ttk.Frame(center_frame, height=100)
        waveform_frame.pack(fill=X, pady=10)
        
        # Canvas for waveform (placeholder for now)
        self.components['waveform_canvas'] = tk.Canvas(
            waveform_frame, 
            height=100, 
            bg='#2b2b2b',
            highlightthickness=0
        )
        self.components['waveform_canvas'].pack(fill=X)
        
        # Main record button - large and centered
        record_button_frame = ttk.Frame(center_frame)
        record_button_frame.pack(pady=20)
        
        self.components['main_record_button'] = ttk.Button(
            record_button_frame,
            text="🎤 Start Recording",
            command=command_map.get("toggle_soap_recording"),
            bootstyle="success",
            width=20,
            style="Large.TButton"
        )
        self.components['main_record_button'].pack()
        ToolTip(self.components['main_record_button'], "Click to start/stop recording (Ctrl+Shift+S)")
        
        # Recording controls (appear during recording)
        recording_controls = ttk.Frame(center_frame)
        recording_controls.pack(pady=10)
        
        self.components['pause_button'] = ttk.Button(
            recording_controls,
            text="⏸️ Pause",
            command=command_map.get("toggle_soap_pause"),
            bootstyle="warning",
            width=10,
            state=DISABLED
        )
        self.components['pause_button'].pack(side=LEFT, padx=5)
        
        self.components['cancel_button'] = ttk.Button(
            recording_controls,
            text="❌ Cancel",
            command=command_map.get("cancel_soap_recording"),
            bootstyle="danger",
            width=10,
            state=DISABLED
        )
        self.components['cancel_button'].pack(side=LEFT, padx=5)
        
        # Timer display
        self.components['timer_label'] = ttk.Label(
            center_frame,
            text="00:00",
            font=("Segoe UI", 24, "bold")
        )
        self.components['timer_label'].pack(pady=10)
        
        # Quick actions (appear after recording)
        quick_actions = ttk.Frame(center_frame)
        # Initially hidden
        
        self.components['quick_actions'] = quick_actions
        
        # Microphone selection at bottom
        mic_frame = ttk.LabelFrame(record_frame, text="Audio Settings", padding=10)
        mic_frame.pack(side=BOTTOM, fill=X, padx=20, pady=(0, 20))
        
        # Copy microphone selection from existing UI
        ttk.Label(mic_frame, text="Microphone:").pack(side=LEFT, padx=(0, 5))
        
        # Store reference for microphone dropdown (will be connected later)
        self.components['mic_frame'] = mic_frame
        
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
                "text": "🔧 Refine Text",
                "tooltip": "Clean up punctuation and capitalization",
                "command": command_map.get("refine_text"),
                "row": 0,
                "column": 0
            },
            {
                "name": "improve",
                "text": "✨ Improve Text",
                "tooltip": "Enhance clarity and readability",
                "command": command_map.get("improve_text"),
                "row": 0,
                "column": 1
            },
            {
                "name": "undo",
                "text": "↩️ Undo",
                "tooltip": "Undo last change (Ctrl+Z)",
                "command": command_map.get("undo_text"),
                "row": 1,
                "column": 0
            },
            {
                "name": "redo",
                "text": "↪️ Redo",
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
                "text": "💾 Save",
                "tooltip": "Save transcript and audio",
                "command": command_map.get("save_text"),
                "column": 0
            },
            {
                "name": "load",
                "text": "📁 Load Audio",
                "tooltip": "Load and transcribe audio file",
                "command": command_map.get("load_audio_file"),
                "column": 1
            },
            {
                "name": "new_session",
                "text": "🆕 New Session",
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
        
        # Document generation options
        gen_frame = ttk.LabelFrame(generate_frame, text="Generate Documents", padding=15)
        gen_frame.pack(fill=BOTH, expand=True, padx=20, pady=20)
        
        # Create large buttons for each document type
        documents = [
            {
                "name": "soap",
                "text": "📋 SOAP Note",
                "description": "Generate a structured SOAP note from the transcript",
                "command": command_map.get("create_soap_note"),
                "bootstyle": "success"
            },
            {
                "name": "referral",
                "text": "🏥 Referral",
                "description": "Create a professional referral letter",
                "command": command_map.get("create_referral"),
                "bootstyle": "info"
            },
            {
                "name": "letter",
                "text": "✉️ Letter",
                "description": "Generate a formal medical letter",
                "command": command_map.get("create_letter"),
                "bootstyle": "primary"
            }
        ]
        
        for i, doc in enumerate(documents):
            # Create a frame for each document type
            doc_frame = ttk.Frame(gen_frame)
            doc_frame.grid(row=i, column=0, sticky="ew", padx=20, pady=10)
            gen_frame.columnconfigure(0, weight=1)
            
            # Large button
            btn = ttk.Button(
                doc_frame,
                text=doc["text"],
                command=doc["command"],
                bootstyle=doc["bootstyle"],
                width=25,
                style="Large.TButton"
            )
            btn.pack(side=LEFT, padx=(0, 15))
            self.components[f"generate_{doc['name']}_button"] = btn
            
            # Description
            desc_label = ttk.Label(
                doc_frame,
                text=doc["description"],
                font=("Segoe UI", 10)
            )
            desc_label.pack(side=LEFT, fill=X, expand=True)
            
            ToolTip(btn, doc["description"])
        
        # Smart suggestions frame (initially hidden)
        suggestions_frame = ttk.LabelFrame(generate_frame, text="Suggestions", padding=10)
        self.components['suggestions_frame'] = suggestions_frame
        
        return generate_frame
    
    def _on_workflow_tab_changed(self, event):
        """Handle workflow tab change event."""
        notebook = event.widget
        tab_index = notebook.index("current")
        tab_names = ["record", "process", "generate"]
        
        if 0 <= tab_index < len(tab_names):
            self.current_workflow = tab_names[tab_index]
            logging.info(f"Switched to {self.current_workflow} workflow")
            
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
            text="◀",
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
        self.templates_frame = ttk.LabelFrame(content_frame, text="Quick Templates", padding=5)
        self.templates_frame.pack(fill=X, pady=(0, 10))
        
        # Create initial templates
        self._create_template_buttons()
        
        # Context text area
        text_frame = ttk.LabelFrame(content_frame, text="Context Information", padding=5)
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
            self.components['context_collapse_btn'].config(text="◀")
            self._context_collapsed = False
        else:
            # Collapse
            self.components['context_content_frame'].pack_forget()
            self.components['context_collapse_btn'].config(text="▶")
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
            tk.messagebox.showwarning("No Content", "Please enter some context text before saving as a template.")
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
                tk.messagebox.showwarning("Invalid Name", "Please enter a template name.")
                return
            
            # Save to settings
            try:
                custom_templates = SETTINGS.get("custom_context_templates", {})
                custom_templates[template_name] = context_text
                SETTINGS["custom_context_templates"] = custom_templates
                
                # Save settings
                from settings import save_settings
                save_settings(SETTINGS)
                
                # Refresh template buttons
                self._refresh_template_buttons()
                
                result["saved"] = True
                dialog.destroy()
                
                tk.messagebox.showinfo("Template Saved", f"Template '{template_name}' has been saved successfully!")
                
            except Exception as e:
                logging.error(f"Error saving context template: {e}")
                tk.messagebox.showerror("Error", f"Failed to save template: {str(e)}")
        
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
                width=20,
                command=lambda t=template: self._apply_context_template(t)
            )
            btn.pack(pady=2, fill=X)
        
        # Add custom templates
        custom_templates = SETTINGS.get("custom_context_templates", {})
        if custom_templates:
            # Add separator
            separator = ttk.Separator(self.templates_frame, orient="horizontal")
            separator.pack(fill=X, pady=5)
            
            # Add custom template buttons
            for template_name, template_text in custom_templates.items():
                btn_frame = ttk.Frame(self.templates_frame)
                btn_frame.pack(fill=X, pady=1)
                
                # Template button
                btn = ttk.Button(
                    btn_frame,
                    text=template_name,
                    bootstyle="info-outline",
                    command=lambda t=template_text: self._apply_custom_template(t)
                )
                btn.pack(side=LEFT, fill=X, expand=True)
                
                # Delete button
                del_btn = ttk.Button(
                    btn_frame,
                    text="×",
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
        result = tk.messagebox.askyesno(
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
                    from settings import save_settings
                    save_settings(SETTINGS)
                    
                    # Refresh template buttons
                    self._refresh_template_buttons()
                    
                    tk.messagebox.showinfo("Template Deleted", f"Template '{template_name}' has been deleted.")
                    
            except Exception as e:
                logging.error(f"Error deleting custom template: {e}")
                tk.messagebox.showerror("Error", f"Failed to delete template: {str(e)}")
    
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
    
    def set_recording_state(self, recording: bool, paused: bool = False):
        """Update UI elements based on recording state.
        
        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        main_record_btn = self.components.get('main_record_button')
        pause_btn = self.components.get('pause_button')
        cancel_btn = self.components.get('cancel_button')
        
        if recording:
            if main_record_btn:
                main_record_btn.config(text="🛑 Stop Recording", bootstyle="danger")
            if pause_btn:
                pause_btn.config(state=tk.NORMAL)
                if paused:
                    pause_btn.config(text="▶️ Resume", bootstyle="success")
                else:
                    pause_btn.config(text="⏸️ Pause", bootstyle="warning")
            if cancel_btn:
                cancel_btn.config(state=tk.NORMAL)
        else:
            # Not recording
            if main_record_btn:
                main_record_btn.config(text="🎤 Start Recording", bootstyle="success")
            if pause_btn:
                pause_btn.config(state=tk.DISABLED, text="⏸️ Pause", bootstyle="warning")
            if cancel_btn:
                cancel_btn.config(state=tk.DISABLED)
    
    def update_recording_progress(self, progress_text: str):
        """Update recording progress/status text.
        
        Args:
            progress_text: Status text to display
        """
        status_label = self.components.get('recording_status')
        if status_label:
            status_label.config(text=progress_text)
    
    def create_status_bar(self) -> tuple:
        """Create the status bar at the bottom of the application.
        
        Returns:
            tuple: (status_frame, status_icon_label, status_label, provider_indicator, progress_bar)
        """
        status_frame = ttk.Frame(self.parent, padding=(10, 5))
        
        # Configure for responsive layout
        status_frame.columnconfigure(1, weight=1)  # Status label should expand
        
        # Status icon
        status_icon_label = ttk.Label(status_frame, text="•", font=("Segoe UI", 16), foreground="gray")
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
        
        # Progress bar
        progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        progress_bar.pack(side=RIGHT, padx=10)
        progress_bar.stop()
        progress_bar.pack_forget()
        
        return status_frame, status_icon_label, status_label, provider_indicator, progress_bar
    
    def create_notebook(self) -> tuple:
        """Create the notebook with tabs for transcript, soap note, referral, and letter.
        
        Returns:
            tuple: (notebook, transcript_text, soap_text, referral_text, letter_text, context_text)
        """
        notebook = ttk.Notebook(self.parent, style="Green.TNotebook")
        
        # Create tabs
        tabs = [
            ("Transcript", "transcript"),
            ("SOAP Note", "soap"),
            ("Referral", "referral"),
            ("Letter", "letter")
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
        
        # Return in expected order
        return (
            notebook,
            text_widgets["transcript"],
            text_widgets["soap"],
            text_widgets["referral"],
            text_widgets["letter"],
            None  # No context text in notebook for workflow UI
        )