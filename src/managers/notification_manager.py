"""
Notification Manager Module

Handles system notifications and status updates for background processing.
Provides various notification styles based on user preferences.
"""

import logging
import tkinter as tk
from tkinter import messagebox
import ttkbootstrap as ttk
from typing import Optional, Callable, Dict, Any
from datetime import datetime
import threading
from queue import Queue, Empty
import time

from settings.settings import SETTINGS


class NotificationManager:
    """Manages notifications for background processing events."""
    
    def __init__(self, app):
        """Initialize the notification manager.
        
        Args:
            app: The main application instance
        """
        self.app = app
        self.notification_queue = Queue()
        self.active_toasts = []
        self.notification_history = []
        
        # Start notification processor thread
        self.processor_thread = threading.Thread(target=self._process_notifications, daemon=True)
        self.processor_thread.start()
        
        logging.info("NotificationManager initialized")
    
    def show_completion(self, patient_name: str, recording_id: int, 
                       task_id: str, processing_time: float):
        """Show completion notification.
        
        Args:
            patient_name: Name of the patient
            recording_id: Database ID of the recording
            task_id: Processing task ID
            processing_time: Time taken to process in seconds
        """
        notification = {
            "type": "completion",
            "patient_name": patient_name,
            "recording_id": recording_id,
            "task_id": task_id,
            "processing_time": processing_time,
            "timestamp": datetime.now()
        }
        
        self.notification_queue.put(notification)
        self.notification_history.append(notification)
        
        logging.info(f"Queued completion notification for patient: {patient_name}")
    
    def show_error(self, patient_name: str, error_message: str, 
                  recording_id: int, task_id: str):
        """Show error notification.
        
        Args:
            patient_name: Name of the patient
            error_message: Error description
            recording_id: Database ID of the recording
            task_id: Processing task ID
        """
        notification = {
            "type": "error",
            "patient_name": patient_name,
            "error_message": error_message,
            "recording_id": recording_id,
            "task_id": task_id,
            "timestamp": datetime.now()
        }
        
        self.notification_queue.put(notification)
        self.notification_history.append(notification)
        
        logging.error(f"Queued error notification for patient: {patient_name} - {error_message}")
    
    def show_progress(self, patient_name: str, progress: int, task_id: str):
        """Show progress notification.
        
        Args:
            patient_name: Name of the patient
            progress: Progress percentage (0-100)
            task_id: Processing task ID
        """
        notification = {
            "type": "progress",
            "patient_name": patient_name,
            "progress": progress,
            "task_id": task_id,
            "timestamp": datetime.now()
        }
        
        # Progress updates are lower priority
        if SETTINGS.get("show_progress_notifications", True):
            self.notification_queue.put(notification)
    
    def _process_notifications(self):
        """Process notifications in background thread."""
        while True:
            try:
                # Get notification with timeout
                notification = self.notification_queue.get(timeout=1.0)
                
                # Schedule notification on main thread
                self.app.after(0, lambda n=notification: self._display_notification(n))
                
            except Empty:
                continue
            except Exception as e:
                logging.error(f"Error processing notification: {str(e)}")
    
    def _display_notification(self, notification: Dict[str, Any]):
        """Display notification based on user preferences."""
        style = SETTINGS.get("notification_style", "toast")
        
        if style == "toast":
            self._show_toast_notification(notification)
        elif style == "statusbar":
            self._show_statusbar_notification(notification)
        elif style == "popup":
            self._show_popup_notification(notification)
        else:
            # Default to status bar
            self._show_statusbar_notification(notification)
    
    def _show_toast_notification(self, notification: Dict[str, Any]):
        """Show toast-style notification."""
        # Create toast window
        toast = tk.Toplevel(self.app)
        toast.wm_overrideredirect(True)
        toast.attributes("-topmost", True)
        
        # Style based on notification type
        if notification["type"] == "completion":
            bg_color = "#28a745"  # Green
            title = "✓ Processing Complete"
            message = f"{notification['patient_name']}'s recording processed in {notification['processing_time']:.1f}s"
        elif notification["type"] == "error":
            bg_color = "#dc3545"  # Red
            title = "✗ Processing Failed"
            message = f"{notification['patient_name']}: {notification['error_message']}"
        else:
            bg_color = "#17a2b8"  # Blue
            title = "Processing Update"
            message = f"{notification['patient_name']}: {notification.get('progress', 0)}% complete"
        
        # Create frame
        frame = ttk.Frame(toast, style="dark")
        frame.pack(fill="both", expand=True)
        
        # Add content
        title_label = ttk.Label(frame, text=title, font=("Arial", 10, "bold"))
        title_label.pack(padx=10, pady=(10, 5))
        
        msg_label = ttk.Label(frame, text=message, wraplength=250)
        msg_label.pack(padx=10, pady=(0, 5))
        
        # Add "View" button for completed recordings
        if notification["type"] == "completion":
            view_btn = ttk.Button(
                frame, 
                text="View Results",
                command=lambda: self._view_recording(notification["recording_id"], toast),
                style="success.TButton"
            )
            view_btn.pack(pady=(0, 10))
        else:
            # Add bottom padding for non-completion notifications
            msg_label.pack(padx=10, pady=(0, 10))
        
        # Position toast
        self._position_toast(toast)
        
        # Auto-hide after 5 seconds (8 seconds for completion to give time to click)
        hide_delay = 8000 if notification["type"] == "completion" else 5000
        toast.after(hide_delay, lambda: self._hide_toast(toast))
        
        # Track active toast
        self.active_toasts.append(toast)
    
    def _position_toast(self, toast: tk.Toplevel):
        """Position toast notification on screen."""
        # Update to get dimensions
        toast.update_idletasks()
        
        # Get screen dimensions
        screen_width = toast.winfo_screenwidth()
        screen_height = toast.winfo_screenheight()
        
        # Get toast dimensions
        toast_width = toast.winfo_width()
        toast_height = toast.winfo_height()
        
        # Calculate position (bottom-right corner with offset)
        x = screen_width - toast_width - 20
        
        # Stack toasts if multiple are active
        active_count = len([t for t in self.active_toasts if t.winfo_exists()])
        y = screen_height - (toast_height + 20) * (active_count + 1)
        
        toast.geometry(f"+{x}+{y}")
        
        # Fade in effect
        toast.attributes("-alpha", 0.0)
        self._fade_in(toast)
    
    def _fade_in(self, window: tk.Toplevel, alpha: float = 0.0):
        """Fade in animation for toast."""
        if alpha < 0.9:
            alpha += 0.1
            window.attributes("-alpha", alpha)
            window.after(20, lambda: self._fade_in(window, alpha))
    
    def _hide_toast(self, toast: tk.Toplevel):
        """Hide and destroy toast notification."""
        if toast in self.active_toasts:
            self.active_toasts.remove(toast)
        
        # Fade out
        self._fade_out(toast)
    
    def _fade_out(self, window: tk.Toplevel, alpha: float = 0.9):
        """Fade out animation for toast."""
        if alpha > 0.1:
            alpha -= 0.1
            window.attributes("-alpha", alpha)
            window.after(20, lambda: self._fade_out(window, alpha))
        else:
            window.destroy()
    
    def _show_statusbar_notification(self, notification: Dict[str, Any]):
        """Show notification in status bar."""
        if notification["type"] == "completion":
            message = f"✓ {notification['patient_name']} processed successfully"
            self.app.status_manager.success(message)
        elif notification["type"] == "error":
            message = f"✗ {notification['patient_name']} failed: {notification['error_message']}"
            self.app.status_manager.error(message)
        else:
            message = f"Processing {notification['patient_name']}: {notification.get('progress', 0)}%"
            self.app.status_manager.info(message)
    
    def _show_popup_notification(self, notification: Dict[str, Any]):
        """Show modal popup notification."""
        if notification["type"] == "completion":
            title = "Processing Complete"
            message = f"Successfully processed recording for {notification['patient_name']}.\n\n" \
                     f"Processing time: {notification['processing_time']:.1f} seconds"
            messagebox.showinfo(title, message, parent=self.app)
        elif notification["type"] == "error":
            title = "Processing Failed"
            message = f"Failed to process recording for {notification['patient_name']}.\n\n" \
                     f"Error: {notification['error_message']}"
            messagebox.showerror(title, message, parent=self.app)
    
    def get_notification_history(self, limit: int = 50) -> list:
        """Get recent notification history.
        
        Args:
            limit: Maximum number of notifications to return
            
        Returns:
            List of recent notifications
        """
        return self.notification_history[-limit:]
    
    def clear_notification_history(self):
        """Clear notification history."""
        self.notification_history.clear()
        logging.info("Notification history cleared")
    
    def show_queue_status(self, active_count: int, completed_count: int, failed_count: int):
        """Show queue status summary notification."""
        if active_count > 0:
            message = f"Queue: {active_count} processing"
            if completed_count > 0:
                message += f", {completed_count} completed"
            if failed_count > 0:
                message += f", {failed_count} failed"
            
            # Update status bar
            self.app.status_manager.info(message)
    
    def _view_recording(self, recording_id: int, toast: tk.Toplevel):
        """View a completed recording in the UI."""
        try:
            # Hide the toast
            self._hide_toast(toast)
            
            # Load the recording from database
            recording = self.app.db.get_recording(recording_id)
            if not recording:
                logging.error(f"Recording {recording_id} not found")
                return
            
            # Clear current UI content
            self.app.transcript_text.delete("1.0", "end")
            self.app.soap_text.delete("1.0", "end")
            self.app.referral_text.delete("1.0", "end") 
            self.app.letter_text.delete("1.0", "end")
            
            # Load the content
            if recording.get('transcript'):
                self.app.transcript_text.insert("1.0", recording['transcript'])
            if recording.get('soap_note'):
                self.app.soap_text.insert("1.0", recording['soap_note'])
            if recording.get('referral'):
                self.app.referral_text.insert("1.0", recording['referral'])
            if recording.get('letter'):
                self.app.letter_text.insert("1.0", recording['letter'])
            
            # Switch to SOAP tab if it has content
            if recording.get('soap_note'):
                self.app.notebook.select(1)
            
            # Update current recording ID
            self.app.current_recording_id = recording_id
            
            # Update status
            patient_name = recording.get('patient_name', 'Unknown')
            self.app.status_manager.success(f"Loaded recording for {patient_name}")
            
        except Exception as e:
            logging.error(f"Error viewing recording: {str(e)}", exc_info=True)
    
    def cleanup(self):
        """Clean up notification manager resources."""
        # Clear any remaining toasts
        for toast in self.active_toasts:
            if toast.winfo_exists():
                toast.destroy()
        self.active_toasts.clear()
        
        logging.info("NotificationManager cleaned up")