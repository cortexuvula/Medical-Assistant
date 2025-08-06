"""
Status Bar Component for Medical Assistant
Handles the application status bar UI
"""

import tkinter as tk
import ttkbootstrap as ttk
from ui.scaling_utils import ui_scaler
from settings.settings import SETTINGS


class StatusBar:
    """Manages the status bar UI components."""
    
    def __init__(self, parent_ui):
        """Initialize the StatusBar component.
        
        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
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
        status_icon_label.pack(side=tk.LEFT, padx=(5, 0))
        
        # Status text
        status_label = ttk.Label(
            status_frame, 
            text="Status: Idle", 
            anchor="w",
            font=("Segoe UI", ui_scaler.scale_font_size(10))
        )
        status_label.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(ui_scaler.get_padding(5), 0))
        
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
        provider_indicator.pack(side=tk.LEFT, padx=(0, 10))
        
        # Queue status indicator
        queue_status_label = ttk.Label(
            status_frame,
            text="",  # Empty initially
            anchor="e",
            font=("Segoe UI", ui_scaler.scale_font_size(9), "bold"),
            foreground="gray"
        )
        queue_status_label.pack(side=tk.LEFT, padx=(0, ui_scaler.get_padding(10)))
        
        # Store reference for later use
        self.components['queue_status_label'] = queue_status_label
        
        # Progress bar
        progress_bar = ttk.Progressbar(status_frame, mode="indeterminate")
        progress_bar.pack(side=tk.RIGHT, padx=10)
        progress_bar.stop()
        progress_bar.pack_forget()
        
        # Update status manager with queue label after it's created
        if hasattr(self.parent, 'status_manager') and self.parent.status_manager:
            self.parent.status_manager.set_queue_status_label(queue_status_label)
        
        return status_frame, status_icon_label, status_label, provider_indicator, progress_bar