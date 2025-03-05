import tkinter as tk
from ttkbootstrap.constants import *
import logging

class StatusManager:
    """Manages status updates, progress indicators, and provider information display."""
    
    def __init__(self, parent, status_icon_label, status_label, provider_indicator, progress_bar):
        """Initialize the status manager with UI components.
        
        Args:
            parent: The parent window/widget that will handle after() calls
            status_icon_label: The label showing the status icon/dot
            status_label: The label showing the status text
            provider_indicator: The label showing the current AI/STT providers
            progress_bar: The progress indicator for long-running operations
        """
        self.parent = parent  # The parent window/widget that will handle after() calls
        self.status_icon_label = status_icon_label
        self.status_label = status_label
        self.provider_indicator = provider_indicator
        self.progress_bar = progress_bar
        
        # Track timers
        self.status_timer = None
        self.status_timers = []
        
        # Status colors
        self.status_colors = {
            "success": "#28a745",  # Green
            "info": "#17a2b8",     # Blue
            "warning": "#ffc107",  # Yellow
            "error": "#dc3545",    # Red
            "idle": "gray"         # Gray for idle state
        }
    
    def update_status(self, message, status_type="info"):
        """Update the status bar with a message and specific status type.
        
        Args:
            message: The status message to display
            status_type: Type of status ('info', 'error', 'warning', 'success', 'progress')
        """
        # Cancel any pending status timer
        self.cancel_scheduled_updates()
        
        # Update status text
        self.status_label.config(text=f"Status: {message}")
        
        # Color-code the status indicator
        self.status_icon_label.config(
            foreground=self.status_colors.get(status_type, self.status_colors["info"])
        )
        
        # Make status message more prominent for important messages
        if status_type in ["error", "warning"]:
            self.status_label.config(font=("Segoe UI", 10, "bold"))
        else:
            self.status_label.config(font=("Segoe UI", 10))
        
        # Update provider indicator info
        self.update_provider_info()
        
        # For non-error/progress messages, set a timer to clear status after a delay
        if status_type != "error" and status_type != "progress":
            # Clear status after 8 seconds unless it's an error or progress indicator
            self.status_timer = self.parent.after(8000, self.reset_status)
    
    def update_provider_info(self):
        """Update the provider indicator with current AI and STT providers."""
        try:
            from settings import SETTINGS
            provider = SETTINGS.get("ai_provider", "openai").capitalize()
            stt_provider = SETTINGS.get("stt_provider", "deepgram").capitalize()
            self.provider_indicator.config(text=f"Using: {provider} | STT: {stt_provider}")
        except Exception as e:
            logging.error(f"Error updating provider info: {e}", exc_info=True)
    
    def reset_status(self):
        """Reset status to idle state after timeout."""
        self.status_label.config(text="Status: Idle", font=("Segoe UI", 10))
        self.status_icon_label.config(foreground=self.status_colors["idle"])
        self.status_timer = None
    
    def cancel_scheduled_updates(self):
        """Cancel all scheduled status updates."""
        if self.status_timer:
            self.parent.after_cancel(self.status_timer)
            self.status_timer = None
        
        for timer_id in self.status_timers:
            if timer_id:
                try:
                    self.parent.after_cancel(timer_id)
                except Exception:
                    pass
        self.status_timers = []
    
    def schedule_status_update(self, delay_ms, message, status_type="info"):
        """Schedule a status update to occur after a delay.
        
        Args:
            delay_ms: Delay in milliseconds before showing the status
            message: Status message to display
            status_type: Type of status
            
        Returns:
            Timer ID for the scheduled update
        """
        timer_id = self.parent.after(delay_ms, lambda: self.update_status(message, status_type))
        self.status_timers.append(timer_id)
        return timer_id
    
    def show_progress(self, show=True):
        """Show or hide the progress bar.
        
        Args:
            show: True to show and start progress bar, False to hide it
        """
        if show:
            self.progress_bar.pack(side=RIGHT, padx=10)
            self.progress_bar.start()
        else:
            self.progress_bar.stop()
            self.progress_bar.pack_forget()
    
    # Convenience methods for specific status types
    def info(self, message):
        """Display an informational status message."""
        self.update_status(message, "info")
        
    def error(self, message):
        """Display an error status message."""
        self.update_status(message, "error")
        
    def warning(self, message):
        """Display a warning status message."""
        self.update_status(message, "warning")
        
    def success(self, message):
        """Display a success status message."""
        self.update_status(message, "success")
        
    def progress(self, message, show_bar=True):
        """Display a progress status message and optionally show progress bar.
        
        Args:
            message: Status message to display
            show_bar: Whether to show the progress bar
        """
        self.update_status(message, "progress")
        if show_bar:
            self.show_progress(True)
