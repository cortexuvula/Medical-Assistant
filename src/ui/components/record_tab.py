"""
Record Tab Component for Medical Assistant
Handles the recording workflow UI elements
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
import logging
import time
import threading
import numpy as np
from typing import Dict, Callable, Optional
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from settings.settings import SETTINGS


class RecordTab:
    """Manages the Record workflow tab UI components."""
    
    def __init__(self, parent_ui):
        """Initialize the RecordTab component.
        
        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
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
        
    def create_record_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Record workflow tab.
        
        Args:
            command_map: Dictionary of commands
            
        Returns:
            ttk.Frame: The record tab frame
        """
        record_frame = ttk.Frame(self.parent)
        
        # Create a PanedWindow for two columns with proper sizing
        columns_container = ttk.Panedwindow(record_frame, orient=tk.HORIZONTAL)
        columns_container.pack(expand=True, fill=BOTH, padx=10, pady=5)
        
        # Left column for recording controls (1/3 width)
        left_column = ttk.Frame(columns_container)
        columns_container.add(left_column, weight=1)
        
        # Right column for text area (2/3 width)
        right_column = ttk.Frame(columns_container)
        columns_container.add(right_column, weight=2)
        
        # Main recording controls container in left column
        center_frame = ttk.Frame(left_column)
        center_frame.pack(expand=True, fill=BOTH, padx=(0, 5))
        
        # Recording status frame (for visual feedback)
        status_frame = ttk.Frame(center_frame)
        status_frame.pack(pady=(0, 5))
        
        # Status label
        self.components['recording_status'] = ttk.Label(
            status_frame, 
            text="", 
            font=("Segoe UI", ui_scaler.scale_font_size(12))
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
        
        # Container for timer
        timer_container = ttk.Frame(center_frame)
        timer_container.pack(pady=ui_scaler.get_padding(2), fill=X)
        
        # Timer display inside the container
        self.components['timer_label'] = ttk.Label(
            timer_container,
            text="00:00",
            font=("Segoe UI", ui_scaler.scale_font_size(20), "bold")
        )
        self.components['timer_label'].pack(expand=True)
        self.components['timer_container'] = timer_container
        
        # Container for audio visualization
        audio_viz_container = ttk.Frame(center_frame)
        audio_viz_container.pack(pady=(0, ui_scaler.get_padding(3)), fill=X)
        
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
        
        self.quality_label = ttk.Label(info_left, text="Quality: 44.1kHz • 16-bit", font=("Segoe UI", ui_scaler.scale_font_size(8)), foreground="gray")
        self.quality_label.pack(side=LEFT)
        
        info_right = ttk.Frame(self.session_info_frame)
        info_right.pack(side=RIGHT)
        
        self.file_size_label = ttk.Label(info_right, text="Size: 0 KB", font=("Segoe UI", ui_scaler.scale_font_size(8)), foreground="gray")
        self.file_size_label.pack(side=RIGHT, padx=(5, 0))
        
        self.duration_label = ttk.Label(info_right, text="Duration: 00:00", font=("Segoe UI", ui_scaler.scale_font_size(8)), foreground="gray")
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
        
        # Advanced Analysis checkbox
        analysis_frame = ttk.Frame(center_frame)
        analysis_frame.pack(pady=(10, 5))
        
        self.advanced_analysis_var = tk.BooleanVar(value=False)
        self.components['advanced_analysis_checkbox'] = ttk.Checkbutton(
            analysis_frame,
            text="Advanced Analysis",
            variable=self.advanced_analysis_var,
            bootstyle="primary"
        )
        self.components['advanced_analysis_checkbox'].pack()
        ToolTip(self.components['advanced_analysis_checkbox'], 
                "Enable real-time differential diagnosis during recording (every 2 minutes)")
        
        # Translation Assistant button
        translation_btn = ttk.Button(
            center_frame,
            text="🌐 Translation Assistant",
            command=command_map.get("open_translation"),
            bootstyle="info",
            width=ui_scaler.get_button_width(20)
        )
        translation_btn.pack(pady=(ui_scaler.get_padding(10), 0))
        ToolTip(translation_btn, "Open bidirectional translation for patient communication")
        
        # Initialize UI state - hide controls initially
        self._initialize_recording_ui_state()
        
        # Create text area in right column
        text_frame = ttk.Labelframe(right_column, text="Advanced Analysis Results", padding=10)
        text_frame.pack(fill=BOTH, expand=True)
        
        # Create header frame with clear button
        header_frame = ttk.Frame(text_frame)
        header_frame.pack(fill=X, pady=(0, 5))
        
        # Clear button aligned to the right
        clear_btn = ttk.Button(
            header_frame,
            text="Clear",
            command=command_map.get("clear_advanced_analysis"),
            bootstyle="secondary",
            width=ui_scaler.get_button_width(8)
        )
        clear_btn.pack(side=RIGHT)
        ToolTip(clear_btn, "Clear analysis results")
        self.components['clear_analysis_button'] = clear_btn
        
        # Create text widget with scrollbar
        text_container = ttk.Frame(text_frame)
        text_container.pack(fill=BOTH, expand=True)
        
        text_scroll = ttk.Scrollbar(text_container)
        text_scroll.pack(side=RIGHT, fill=Y)
        
        self.components['record_notes_text'] = tk.Text(
            text_container,
            wrap=tk.WORD,
            yscrollcommand=text_scroll.set
        )
        self.components['record_notes_text'].pack(fill=BOTH, expand=True)
        text_scroll.config(command=self.components['record_notes_text'].yview)
        
        # Store reference to advanced analysis var in parent
        self.parent_ui.advanced_analysis_var = self.advanced_analysis_var
        
        return record_frame
    
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
    
    def set_recording_state(self, recording: bool, paused: bool = False):
        """Update UI elements based on recording state.
        
        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        logging.info(f"RecordTab.set_recording_state called: recording={recording}, paused={paused}")
        
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
        except (tk.TclError, KeyError, TypeError, ZeroDivisionError):
            pass  # Ignore errors in size calculation or widget updates
    
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