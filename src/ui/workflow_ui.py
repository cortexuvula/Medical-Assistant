"""
Workflow-Oriented UI Components for Medical Assistant

This module provides a task-based UI organization with three main workflows:
Record, Process, and Generate.
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Dict, Callable
import logging

# Import UI components
from ui.components.record_tab import RecordTab
from ui.components.process_tab import ProcessTab
from ui.components.generate_tab import GenerateTab
from ui.components.recordings_tab import RecordingsTab
from ui.components.context_panel import ContextPanel
from ui.components.status_bar import StatusBar
from ui.components.notebook_tabs import NotebookTabs


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
        
        # Initialize component handlers
        self.record_tab = RecordTab(self)
        self.process_tab = ProcessTab(self)
        self.generate_tab = GenerateTab(self)
        self.recordings_tab = RecordingsTab(self)
        self.context_panel = ContextPanel(self)
        self.status_bar = StatusBar(self)
        self.notebook_tabs = NotebookTabs(self)
        
        # Advanced analysis variable (will be set by RecordTab)
        self.advanced_analysis_var = None
        
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
        record_frame = self.record_tab.create_record_tab(command_map)
        workflow_notebook.add(record_frame, text="Record")
        
        # Create Process tab
        process_frame = self.process_tab.create_process_tab(command_map)
        workflow_notebook.add(process_frame, text="Process")
        
        # Create Generate tab
        generate_frame = self.generate_tab.create_generate_tab(command_map)
        workflow_notebook.add(generate_frame, text="Generate")
        
        # Create Recordings tab
        recordings_frame = self.recordings_tab.create_recordings_tab(command_map)
        workflow_notebook.add(recordings_frame, text="Recordings")
        
        # Bind tab change event
        workflow_notebook.bind("<<NotebookTabChanged>>", self._on_workflow_tab_changed)
        
        self.components['workflow_notebook'] = workflow_notebook
        return workflow_notebook
    
    def _on_workflow_tab_changed(self, event):
        """Handle workflow tab change event."""
        try:
            notebook = event.widget
            tab_index = notebook.index("current")
            tab_names = ["record", "process", "generate", "recordings"]
            
            if 0 <= tab_index < len(tab_names):
                self.current_workflow = tab_names[tab_index]
                logging.debug(f"Switched to {self.current_workflow} workflow")
                
                # Refresh recordings list when switching to Recordings tab
                if self.current_workflow == "recordings":
                    self.recordings_tab._refresh_recordings_list()
                
                # Trigger any workflow-specific updates
                if hasattr(self.parent, 'on_workflow_changed'):
                    self.parent.on_workflow_changed(self.current_workflow)
        except Exception as e:
            # Ignore errors during shutdown
            logging.debug(f"Tab change error (likely during shutdown): {e}")
    
    def create_context_panel(self) -> ttk.Frame:
        """Create the persistent context side panel.
        
        Returns:
            ttk.Frame: The context panel frame
        """
        return self.context_panel.create_context_panel()
    
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
            btn.pack(side=tk.LEFT, padx=5)
        
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
        self.record_tab.update_timer(time_str)
    
    def set_recording_state(self, recording: bool, paused: bool = False):
        """Update UI elements based on recording state.
        
        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        self.record_tab.set_recording_state(recording, paused)
    
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
        self.record_tab.start_timer()
    
    def pause_timer(self):
        """Pause the recording timer."""
        self.record_tab.pause_timer()
    
    def resume_timer(self):
        """Resume the recording timer."""
        self.record_tab.resume_timer()
    
    def stop_timer(self):
        """Stop and reset the recording timer."""
        self.record_tab.stop_timer()
    
    def create_status_bar(self) -> tuple:
        """Create the status bar at the bottom of the application.
        
        Returns:
            tuple: (status_frame, status_icon_label, status_label, provider_indicator, progress_bar)
        """
        return self.status_bar.create_status_bar()
    
    def create_notebook(self) -> tuple:
        """Create the notebook with tabs for transcript, soap note, referral, letter, chat, and RAG.
        
        Returns:
            tuple: (notebook, transcript_text, soap_text, referral_text, letter_text, chat_text, rag_text, context_text)
        """
        return self.notebook_tabs.create_notebook()
    
    # Expose component methods for backwards compatibility
    def _refresh_recordings_list(self):
        """Refresh the recordings list from database."""
        self.recordings_tab._refresh_recordings_list()
    
    def _clear_chat_history(self):
        """Clear the chat conversation history."""
        self.notebook_tabs._clear_chat_history()
    
    def _clear_rag_history(self):
        """Clear the RAG conversation history."""
        self.notebook_tabs._clear_rag_history()