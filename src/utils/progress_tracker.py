"""
Progress tracking utilities for long-running operations.

This module provides a callback-based progress tracking system that can be used
to update UI elements during long operations.
"""

import time
import logging
import tkinter as tk
from typing import Callable, Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ProgressInfo:
    """Information about operation progress."""
    current: int
    total: int
    percentage: float
    message: str
    time_elapsed: float
    estimated_remaining: Optional[float] = None
    
    def __str__(self) -> str:
        """String representation of progress."""
        if self.estimated_remaining:
            return f"{self.message} ({self.percentage:.0f}% - {self.estimated_remaining:.0f}s remaining)"
        return f"{self.message} ({self.percentage:.0f}%)"


class ProgressTracker:
    """Tracks progress of long-running operations."""
    
    def __init__(self, 
                 total_steps: int, 
                 callback: Optional[Callable[[ProgressInfo], None]] = None,
                 initial_message: str = "Processing..."):
        """
        Initialize progress tracker.
        
        Args:
            total_steps: Total number of steps in the operation
            callback: Function to call with progress updates
            initial_message: Initial progress message
        """
        self.total_steps = total_steps
        self.current_step = 0
        self.callback = callback
        self.start_time = time.time()
        self.step_times = []
        self.current_message = initial_message
        
        # Send initial progress
        self._send_progress()
    
    def update(self, message: Optional[str] = None, increment: int = 1) -> None:
        """
        Update progress.
        
        Args:
            message: Optional message to display
            increment: Number of steps to increment
        """
        self.current_step = min(self.current_step + increment, self.total_steps)
        if message:
            self.current_message = message
            
        # Track step timing for estimation
        current_time = time.time()
        if self.current_step > 0:
            self.step_times.append(current_time - self.start_time)
            
        self._send_progress()
    
    def set_progress(self, step: int, message: Optional[str] = None) -> None:
        """
        Set progress to specific step.
        
        Args:
            step: Step number to set
            message: Optional message to display
        """
        self.current_step = min(step, self.total_steps)
        if message:
            self.current_message = message
        self._send_progress()
    
    def complete(self, message: str = "Complete") -> None:
        """Mark operation as complete."""
        self.current_step = self.total_steps
        self.current_message = message
        self._send_progress()
    
    def _send_progress(self) -> None:
        """Send progress update via callback."""
        if not self.callback:
            return
            
        percentage = (self.current_step / self.total_steps * 100) if self.total_steps > 0 else 0
        time_elapsed = time.time() - self.start_time
        
        # Estimate remaining time
        estimated_remaining = None
        if self.current_step > 0 and self.current_step < self.total_steps:
            avg_time_per_step = time_elapsed / self.current_step
            remaining_steps = self.total_steps - self.current_step
            estimated_remaining = avg_time_per_step * remaining_steps
        
        progress_info = ProgressInfo(
            current=self.current_step,
            total=self.total_steps,
            percentage=percentage,
            message=self.current_message,
            time_elapsed=time_elapsed,
            estimated_remaining=estimated_remaining
        )
        
        try:
            self.callback(progress_info)
        except Exception as e:
            logging.error(f"Error in progress callback: {e}")


class DocumentGenerationProgress:
    """Specialized progress tracking for document generation."""
    
    # Step definitions for different document types
    SOAP_STEPS = [
        (0.1, "Preparing transcript..."),
        (0.2, "Extracting context..."),
        (0.4, "Generating SOAP sections..."),
        (0.7, "Formatting output..."),
        (0.9, "Finalizing document..."),
        (1.0, "Complete")
    ]
    
    REFERRAL_STEPS = [
        (0.15, "Analyzing patient information..."),
        (0.3, "Identifying conditions..."),
        (0.6, "Generating referral content..."),
        (0.85, "Formatting letter..."),
        (1.0, "Complete")
    ]
    
    DIAGNOSTIC_STEPS = [
        (0.1, "Extracting symptoms..."),
        (0.3, "Analyzing clinical data..."),
        (0.5, "Generating differential diagnosis..."),
        (0.7, "Looking up ICD codes..."),
        (0.9, "Compiling recommendations..."),
        (1.0, "Complete")
    ]
    
    @classmethod
    def create_soap_tracker(cls, callback: Callable[[ProgressInfo], None]) -> ProgressTracker:
        """Create progress tracker for SOAP note generation."""
        tracker = ProgressTracker(
            total_steps=len(cls.SOAP_STEPS),
            callback=callback,
            initial_message="Starting SOAP note generation..."
        )
        return tracker
    
    @classmethod
    def create_referral_tracker(cls, callback: Callable[[ProgressInfo], None]) -> ProgressTracker:
        """Create progress tracker for referral generation."""
        tracker = ProgressTracker(
            total_steps=len(cls.REFERRAL_STEPS),
            callback=callback,
            initial_message="Starting referral generation..."
        )
        return tracker
    
    @classmethod
    def create_diagnostic_tracker(cls, callback: Callable[[ProgressInfo], None]) -> ProgressTracker:
        """Create progress tracker for diagnostic analysis."""
        tracker = ProgressTracker(
            total_steps=len(cls.DIAGNOSTIC_STEPS),
            callback=callback,
            initial_message="Starting diagnostic analysis..."
        )
        return tracker


def create_progress_callback(status_manager, progress_bar=None) -> Callable[[ProgressInfo], None]:
    """
    Create a progress callback for UI updates.
    
    Args:
        status_manager: Application status manager
        progress_bar: Optional progress bar widget
        
    Returns:
        Callback function for progress updates
    """
    def callback(progress: ProgressInfo):
        """Update UI with progress information."""
        # Update status message
        status_manager.progress(str(progress))
        
        # Update progress bar if available
        if progress_bar and hasattr(progress_bar, 'config'):
            try:
                # For determinate progress bar
                progress_bar.config(value=progress.percentage)
            except (tk.TclError, AttributeError):
                # Fallback for indeterminate progress bar or widget destroyed
                pass
                
        # Log progress
        logging.debug(f"Progress: {progress.current}/{progress.total} - {progress.message}")
    
    return callback