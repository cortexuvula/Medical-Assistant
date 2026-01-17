"""
Workflow-Oriented UI Components for Medical Assistant

This module provides a task-based UI organization with three main workflows:
Record, Process, and Generate.
"""

import tkinter as tk
import ttkbootstrap as ttk
from typing import Dict, Callable
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Import UI components
from ui.components.record_tab import RecordTab
from ui.components.recordings_tab import RecordingsTab
from ui.components.context_panel import ContextPanel
from ui.components.status_bar import StatusBar
from ui.components.notebook_tabs import NotebookTabs
from ui.components.sidebar_navigation import SidebarNavigation
from ui.components.recording_header import RecordingHeader
from ui.components.shared_panel_manager import SharedPanelManager


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
        self.recordings_tab = RecordingsTab(self)
        self.context_panel = ContextPanel(self)
        self.status_bar = StatusBar(self)
        self.notebook_tabs = NotebookTabs(self)
        self.sidebar_navigation = SidebarNavigation(self)
        self.recording_header = RecordingHeader(self)
        self.shared_panel_manager = None  # Initialized in create_shared_panel()

        # Advanced analysis variable (will be set by RecordTab)
        self.advanced_analysis_var = None
        
    def create_workflow_tabs(self, command_map: Dict[str, Callable]) -> ttk.Notebook:
        """Create the main workflow tabs.

        DEPRECATED: Use create_shared_panel() instead for the new single-panel UI.
        This method is kept for backwards compatibility only.

        Args:
            command_map: Dictionary mapping button names to their command functions

        Returns:
            ttk.Notebook: The workflow notebook widget
        """
        logging.warning("create_workflow_tabs is deprecated. Use create_shared_panel() instead.")

        # Create main workflow notebook with hidden tabs
        style = ttk.Style()
        style.layout("HiddenWorkflow.TNotebook.Tab", [])

        workflow_notebook = ttk.Notebook(self.parent, style="HiddenWorkflow.TNotebook")

        # Create Record tab (index 0) - uses analysis panel
        record_frame = self.record_tab.create_record_tab(command_map)
        workflow_notebook.add(record_frame, text="Record")

        # Create placeholder tabs for backwards compatibility
        placeholder1 = ttk.Frame(workflow_notebook)
        workflow_notebook.add(placeholder1, text="Process")

        placeholder2 = ttk.Frame(workflow_notebook)
        workflow_notebook.add(placeholder2, text="Generate")

        # Create Recordings tab (index 3)
        recordings_frame = self.recordings_tab.create_recordings_tab(command_map)
        workflow_notebook.add(recordings_frame, text="Recordings")

        # Bind tab change event
        workflow_notebook.bind("<<NotebookTabChanged>>", self._on_workflow_tab_changed)

        self.components['workflow_notebook'] = workflow_notebook
        return workflow_notebook
    
    def create_shared_panel(self, command_map: Dict[str, Callable], show_collapse_button: bool = True) -> ttk.Frame:
        """Create the single shared panel area.

        This replaces the old workflow tabs with a single panel that can
        dynamically switch between Analysis and Recordings views.

        Args:
            command_map: Dictionary mapping command names to callable functions
            show_collapse_button: Whether to show individual collapse buttons on panels

        Returns:
            ttk.Frame: The shared panel container
        """
        # Create shared panel manager
        self.shared_panel_manager = SharedPanelManager(self)
        container = self.shared_panel_manager.create_container(self.parent)

        # Create and register panels
        analysis_panel = self.record_tab.create_analysis_panel(container, command_map, show_collapse_button=show_collapse_button)
        recordings_panel = self.recordings_tab.create_recordings_panel(container)

        self.shared_panel_manager.register_panel(
            SharedPanelManager.PANEL_ANALYSIS, analysis_panel
        )
        self.shared_panel_manager.register_panel(
            SharedPanelManager.PANEL_RECORDINGS, recordings_panel
        )

        # Link record tab components to header controls
        self.record_tab.link_to_header_controls()

        # Link advanced analysis variables from header
        if hasattr(self.recording_header, 'advanced_analysis_var'):
            self.advanced_analysis_var = self.recording_header.advanced_analysis_var
        if hasattr(self.recording_header, 'analysis_interval_var'):
            self.analysis_interval_var = self.recording_header.analysis_interval_var

        # Default to analysis panel
        self.shared_panel_manager.show_panel(SharedPanelManager.PANEL_ANALYSIS)

        self.components['shared_panel'] = container
        return container

    def _on_workflow_tab_changed(self, event):
        """Handle workflow tab change event with debouncing.

        Uses 100ms debounce to prevent multiple refreshes during rapid tab switching.
        This improves UI responsiveness by avoiding redundant work.
        """
        # Cancel pending refresh if switching quickly (debounce)
        if hasattr(self, '_pending_tab_refresh'):
            try:
                self.parent.after_cancel(self._pending_tab_refresh)
            except Exception:
                pass

        # Schedule the actual refresh with 100ms debounce
        self._pending_tab_refresh = self.parent.after(100, lambda: self._do_tab_change(event))

    def _do_tab_change(self, event):
        """Perform the actual tab change handling after debounce."""
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
    
    def create_sidebar(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the left sidebar navigation panel.

        Args:
            command_map: Dictionary mapping command names to callable functions

        Returns:
            ttk.Frame: The sidebar frame
        """
        return self.sidebar_navigation.create_sidebar(command_map)

    def create_recording_header(self, command_map: Dict[str, Callable], parent=None) -> ttk.Frame:
        """Create the prominent recording header at the top.

        Args:
            command_map: Dictionary mapping command names to callable functions
            parent: Optional parent widget for the header

        Returns:
            ttk.Frame: The recording header frame
        """
        header = self.recording_header.create_recording_header(command_map, parent)

        # Link record tab components to header controls
        self.record_tab.link_to_header_controls()

        # Link advanced analysis variables from header
        if hasattr(self.recording_header, 'advanced_analysis_var'):
            self.advanced_analysis_var = self.recording_header.advanced_analysis_var
        if hasattr(self.recording_header, 'analysis_interval_var'):
            self.analysis_interval_var = self.recording_header.analysis_interval_var

        return header

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
        # Timer is now in the recording header
        if hasattr(self.recording_header, '_timer_label') and self.recording_header._timer_label:
            self.recording_header._timer_label.config(text=time_str)

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
        # Timer is now managed by the recording header
        if hasattr(self.recording_header, '_start_timer'):
            self.recording_header._start_timer()

    def pause_timer(self):
        """Pause the recording timer."""
        # Timer is now managed by the recording header
        if hasattr(self.recording_header, '_pause_timer'):
            self.recording_header._pause_timer()

    def resume_timer(self):
        """Resume the recording timer."""
        # Timer is now managed by the recording header
        if hasattr(self.recording_header, '_resume_timer'):
            self.recording_header._resume_timer()

    def stop_timer(self):
        """Stop and reset the recording timer."""
        # Timer is now managed by the recording header
        if hasattr(self.recording_header, '_stop_timer'):
            self.recording_header._stop_timer()
    
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