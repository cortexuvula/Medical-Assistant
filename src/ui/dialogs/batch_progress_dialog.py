"""
Batch Progress Dialog

Displays real-time progress of batch processing operations.
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Optional, Callable
import logging
import threading
from datetime import datetime

from ttkbootstrap.tooltip import ToolTip


class BatchProgressDialog:
    """Dialog for displaying batch processing progress."""
    
    def __init__(self, parent: tk.Tk, batch_id: str, total_count: int):
        """Initialize the batch progress dialog.
        
        Args:
            parent: Parent window
            batch_id: Batch identifier
            total_count: Total number of recordings in batch
        """
        self.parent = parent
        self.batch_id = batch_id
        self.total_count = total_count
        self.completed_count = 0
        self.failed_count = 0
        self.cancelled = False
        self.on_cancel_callback: Optional[Callable] = None
        
        # Create dialog window
        self.dialog = tk.Toplevel(parent)
        self.dialog.title("Batch Processing Progress")
        self.dialog.geometry("800x600")
        self.dialog.resizable(True, True)
        self.dialog.minsize(700, 500)
        
        # Center the dialog
        self.dialog.transient(parent)
        self.dialog.update_idletasks()
        x = (self.dialog.winfo_screenwidth() // 2) - (800 // 2)
        y = (self.dialog.winfo_screenheight() // 2) - (600 // 2)
        self.dialog.geometry(f"+{x}+{y}")
        
        # Make modal
        self.dialog.grab_set()
        
        # Start time tracking (must be before _create_ui which calls _update_timer)
        self.start_time = datetime.now()
        
        # Create UI
        self._create_ui()
        
        # Prevent closing while processing
        self.dialog.protocol("WM_DELETE_WINDOW", self._on_close)
        
    def _create_ui(self):
        """Create the dialog UI."""
        # Main container
        main_frame = ttk.Frame(self.dialog, padding=20)
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Title
        title_label = ttk.Label(
            main_frame,
            text=f"Processing {self.total_count} Recordings",
            font=("", 12, "bold")
        )
        title_label.pack(pady=(0, 20))
        
        # Progress section
        progress_frame = ttk.LabelFrame(main_frame, text="Overall Progress", padding=15)
        progress_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Progress bar
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            mode='determinate',
            maximum=self.total_count,
            value=0,
            length=700
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        # Progress text
        self.progress_label = ttk.Label(
            progress_frame,
            text=f"0 of {self.total_count} completed (0%)",
            font=("", 10)
        )
        self.progress_label.pack()
        
        # Statistics frame
        stats_frame = ttk.LabelFrame(main_frame, text="Statistics", padding=15)
        stats_frame.pack(fill=tk.X, pady=(0, 15))
        
        # Create grid for statistics
        stats_grid = ttk.Frame(stats_frame)
        stats_grid.pack(fill=tk.X)
        
        # Statistics labels
        ttk.Label(stats_grid, text="Completed:", font=("", 9, "bold")).grid(row=0, column=0, sticky=tk.W, padx=(0, 10))
        self.completed_label = ttk.Label(stats_grid, text="0", foreground="#27ae60")
        self.completed_label.grid(row=0, column=1, sticky=tk.W, padx=(0, 30))
        
        ttk.Label(stats_grid, text="Failed:", font=("", 9, "bold")).grid(row=0, column=2, sticky=tk.W, padx=(0, 10))
        self.failed_label = ttk.Label(stats_grid, text="0", foreground="#e74c3c")
        self.failed_label.grid(row=0, column=3, sticky=tk.W, padx=(0, 30))
        
        ttk.Label(stats_grid, text="Remaining:", font=("", 9, "bold")).grid(row=0, column=4, sticky=tk.W, padx=(0, 10))
        self.remaining_label = ttk.Label(stats_grid, text=str(self.total_count), foreground="#3498db")
        self.remaining_label.grid(row=0, column=5, sticky=tk.W)
        
        ttk.Label(stats_grid, text="Elapsed Time:", font=("", 9, "bold")).grid(row=1, column=0, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.elapsed_label = ttk.Label(stats_grid, text="00:00:00")
        self.elapsed_label.grid(row=1, column=1, sticky=tk.W, padx=(0, 30), pady=(10, 0))
        
        ttk.Label(stats_grid, text="Estimated Time:", font=("", 9, "bold")).grid(row=1, column=2, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.eta_label = ttk.Label(stats_grid, text="Calculating...")
        self.eta_label.grid(row=1, column=3, sticky=tk.W, padx=(0, 30), pady=(10, 0))
        
        ttk.Label(stats_grid, text="Speed:", font=("", 9, "bold")).grid(row=1, column=4, sticky=tk.W, padx=(0, 10), pady=(10, 0))
        self.speed_label = ttk.Label(stats_grid, text="0 rec/min")
        self.speed_label.grid(row=1, column=5, sticky=tk.W, pady=(10, 0))
        
        # Details frame with scrollable text
        details_frame = ttk.LabelFrame(main_frame, text="Processing Details", padding=10)
        details_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 15))
        
        # Scrollable text area for details
        text_scroll = ttk.Scrollbar(details_frame)
        text_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        self.details_text = tk.Text(
            details_frame,
            height=12,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set,
            font=("Courier", 9)
        )
        self.details_text.pack(fill=tk.BOTH, expand=True)
        text_scroll.config(command=self.details_text.yview)
        
        # Configure tags for colored text
        self.details_text.tag_config("success", foreground="#27ae60")
        self.details_text.tag_config("error", foreground="#e74c3c")
        self.details_text.tag_config("info", foreground="#3498db")
        
        # Button frame
        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X)
        
        # Cancel button
        self.cancel_btn = ttk.Button(
            button_frame,
            text="Cancel",
            command=self._on_cancel,
            bootstyle="danger",
            width=15
        )
        self.cancel_btn.pack(side=tk.RIGHT)
        ToolTip(self.cancel_btn, "Cancel remaining batch processing")
        
        # Close button (initially disabled)
        self.close_btn = ttk.Button(
            button_frame,
            text="Close",
            command=self._on_close,
            bootstyle="secondary",
            width=15,
            state=tk.DISABLED
        )
        self.close_btn.pack(side=tk.RIGHT, padx=(0, 10))
        
        # Start update timer
        self._update_timer()
        
    def update_progress(self, completed: int, failed: int, message: str = None):
        """Update the progress display.
        
        Args:
            completed: Number of completed recordings
            failed: Number of failed recordings
            message: Optional status message
        """
        self.completed_count = completed
        self.failed_count = failed
        total_processed = completed + failed
        remaining = self.total_count - total_processed
        
        # Update progress bar
        self.progress_bar['value'] = total_processed
        
        # Update progress label
        percentage = int((total_processed / self.total_count) * 100)
        self.progress_label.config(
            text=f"{total_processed} of {self.total_count} completed ({percentage}%)"
        )
        
        # Update statistics
        self.completed_label.config(text=str(completed))
        self.failed_label.config(text=str(failed))
        self.remaining_label.config(text=str(remaining))
        
        # Add message to details if provided
        if message:
            self.add_detail(message, "info")
        
        # Check if complete
        if total_processed >= self.total_count:
            self._on_complete()
    
    def add_detail(self, message: str, tag: str = "info"):
        """Add a detail message to the text area.
        
        Args:
            message: Message to add
            tag: Text tag for coloring (success, error, info)
        """
        self.details_text.insert(tk.END, f"{datetime.now().strftime('%H:%M:%S')} - {message}\n", tag)
        self.details_text.see(tk.END)
    
    def _update_timer(self):
        """Update elapsed time and estimates."""
        if not self.cancelled and self.progress_bar['value'] < self.total_count:
            elapsed = datetime.now() - self.start_time
            elapsed_str = str(elapsed).split('.')[0]
            self.elapsed_label.config(text=elapsed_str)
            
            # Calculate speed and ETA
            total_processed = self.completed_count + self.failed_count
            if total_processed > 0:
                seconds_elapsed = elapsed.total_seconds()
                speed = (total_processed / seconds_elapsed) * 60  # records per minute
                self.speed_label.config(text=f"{speed:.1f} rec/min")
                
                # Estimate remaining time
                remaining = self.total_count - total_processed
                if speed > 0:
                    eta_seconds = (remaining / speed) * 60
                    eta_hours = int(eta_seconds // 3600)
                    eta_minutes = int((eta_seconds % 3600) // 60)
                    eta_seconds = int(eta_seconds % 60)
                    self.eta_label.config(text=f"{eta_hours:02d}:{eta_minutes:02d}:{eta_seconds:02d}")
                else:
                    self.eta_label.config(text="Calculating...")
            
            # Schedule next update
            self.dialog.after(1000, self._update_timer)
    
    def _on_cancel(self):
        """Handle cancel button click."""
        if messagebox.askyesno("Cancel Batch Processing", 
                              "Are you sure you want to cancel the remaining batch processing?",
                              parent=self.dialog):
            self.cancelled = True
            self.cancel_btn.config(state=tk.DISABLED)
            self.add_detail("Batch processing cancelled by user", "error")
            
            # Call cancel callback if set
            if self.on_cancel_callback:
                self.on_cancel_callback(self.batch_id)
    
    def _on_complete(self):
        """Handle batch completion."""
        self.cancel_btn.config(state=tk.DISABLED)
        self.close_btn.config(state=tk.NORMAL)
        
        # Show completion summary
        if self.failed_count == 0:
            self.add_detail(f"Batch processing completed successfully! All {self.completed_count} recordings processed.", "success")
        else:
            self.add_detail(f"Batch processing completed with errors. {self.completed_count} succeeded, {self.failed_count} failed.", "error")
    
    def _on_close(self):
        """Handle close button click or window close."""
        if self.progress_bar['value'] < self.total_count and not self.cancelled:
            messagebox.showwarning("Processing in Progress",
                                 "Batch processing is still in progress. Please wait or cancel first.",
                                 parent=self.dialog)
            return
        
        self.dialog.destroy()
    
    def set_cancel_callback(self, callback: Callable):
        """Set the callback function for cancel action.
        
        Args:
            callback: Function to call when cancel is clicked
        """
        self.on_cancel_callback = callback