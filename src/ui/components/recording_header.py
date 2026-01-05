"""
Recording Header Component for Medical Assistant
Provides a prominent recording control area with waveform visualization
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Dict, Callable, Optional, List
import logging
import math

from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler
from settings.settings import SETTINGS


class RecordingHeader:
    """Creates a prominent recording header with button, waveform, and device selector."""

    # Colors for buttons (these are explicit and don't change with theme)
    COLORS = {
        "button_bg": "#2196F3",    # Blue button
        "button_fg": "#ffffff",    # White text
        "button_recording": "#f44336",  # Red when recording
        "button_paused": "#FF9800",     # Orange when paused
        "waveform_idle": "#90CAF9",     # Light blue dots
        "waveform_active": "#2196F3",   # Blue waveform
    }

    def __init__(self, parent_ui):
        """Initialize the RecordingHeader component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components

        # Waveform state
        self._waveform_canvas = None
        self._waveform_data: List[float] = []
        self._is_recording = False
        self._animation_id = None

        # Recording controls state
        self._controls_frame = None
        self._pause_btn = None
        self._cancel_btn = None
        self._timer_label = None
        self._timer_running = False
        self._timer_start_time = None
        self._timer_paused_time = 0
        self._timer_id = None

    def create_recording_header(self, command_map: Dict[str, Callable], parent=None) -> ttk.Frame:
        """Create the recording header component.

        Args:
            command_map: Dictionary mapping command names to functions
            parent: Optional parent widget. If None, uses self.parent

        Returns:
            ttk.Frame: The recording header frame
        """
        # Main container - use provided parent or default
        target_parent = parent if parent else self.parent
        header_frame = ttk.Frame(target_parent)

        # Inner frame - use ttk.Frame for theme support
        self._header_bg = ttk.Frame(header_frame)
        self._header_bg.pack(fill=tk.X, padx=10, pady=(5, 0))

        # Content container - ttk.Frame follows theme
        content = ttk.Frame(self._header_bg)
        content.pack(fill=tk.X, padx=15, pady=12)

        # Left section: Contains button, controls, and advanced analysis
        left_section = ttk.Frame(content)
        left_section.pack(side=tk.LEFT)

        # Recording button
        self._record_btn = tk.Button(
            left_section,
            text="▶  Start Recording",
            font=("Segoe UI", 12, "bold"),
            bg=self.COLORS["button_bg"],
            fg=self.COLORS["button_fg"],
            activebackground="#1976D2",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=25,
            pady=8,
            cursor="hand2",
            command=command_map.get("toggle_soap_recording")
        )
        self._record_btn.pack(side=tk.LEFT)
        ToolTip(self._record_btn, "Start/Stop Recording (Ctrl+Shift+S)")

        # Store reference
        self.components['header_record_button'] = self._record_btn

        # Controls frame (Pause, Cancel, Timer) - shown when recording
        self._controls_frame = ttk.Frame(left_section)
        # Don't pack yet - will be shown when recording starts

        # Pause button
        self._pause_btn = tk.Button(
            self._controls_frame,
            text="⏸ Pause",
            font=("Segoe UI", 10),
            bg="#FF9800",  # Orange
            fg="#ffffff",
            activebackground="#F57C00",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=command_map.get("toggle_soap_pause")
        )
        self._pause_btn.pack(side=tk.LEFT, padx=(15, 5))

        # Cancel button
        self._cancel_btn = tk.Button(
            self._controls_frame,
            text="✕ Cancel",
            font=("Segoe UI", 10),
            bg="#f44336",  # Red
            fg="#ffffff",
            activebackground="#D32F2F",
            activeforeground="#ffffff",
            relief=tk.FLAT,
            padx=12,
            pady=5,
            cursor="hand2",
            command=command_map.get("cancel_soap_recording")
        )
        self._cancel_btn.pack(side=tk.LEFT, padx=5)

        # Timer label - use ttk.Label for theme support
        self._timer_label = ttk.Label(
            self._controls_frame,
            text="00:00",
            font=("Segoe UI", 12, "bold"),
            foreground="#e53935"  # Red color for timer
        )
        self._timer_label.pack(side=tk.LEFT, padx=(10, 0))

        # Store references
        self.components['header_pause_button'] = self._pause_btn
        self.components['header_cancel_button'] = self._cancel_btn
        self.components['header_timer_label'] = self._timer_label

        # Advanced Analysis checkbox (always visible)
        self._advanced_frame = ttk.Frame(left_section)
        self._advanced_frame.pack(side=tk.LEFT, padx=(20, 0))

        self.advanced_analysis_var = tk.BooleanVar(value=False)
        self._advanced_checkbox = ttk.Checkbutton(
            self._advanced_frame,
            text="Advanced Analysis",
            variable=self.advanced_analysis_var,
            bootstyle="primary"
        )
        self._advanced_checkbox.pack(side=tk.LEFT)
        ToolTip(self._advanced_checkbox, "Enable real-time differential diagnosis during recording")

        # Interval selector
        self.analysis_interval_var = tk.StringVar(value="2 min")
        self._interval_combo = ttk.Combobox(
            self._advanced_frame,
            textvariable=self.analysis_interval_var,
            values=["1 min", "2 min", "5 min"],
            width=6,
            state="readonly"
        )
        self._interval_combo.pack(side=tk.LEFT, padx=(5, 0))
        ToolTip(self._interval_combo, "Analysis interval")

        # Store references
        self.components['header_advanced_checkbox'] = self._advanced_checkbox
        self.components['header_interval_combo'] = self._interval_combo

        # Center: Waveform visualization
        waveform_frame = ttk.Frame(content)
        waveform_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=15)

        # Canvas needs explicit background - will be updated to match theme
        self._waveform_canvas = tk.Canvas(
            waveform_frame,
            height=40,
            highlightthickness=0
        )
        self._waveform_canvas.pack(fill=tk.X, expand=True)
        # Update canvas background to match theme after window is displayed
        self._waveform_canvas.bind("<Map>", self._update_canvas_theme)

        # Draw initial idle waveform (dotted line)
        self._draw_idle_waveform()

        # Bind resize event
        self._waveform_canvas.bind("<Configure>", self._on_canvas_resize)

        # Right: Device selector
        device_frame = ttk.Frame(content)
        device_frame.pack(side=tk.RIGHT)

        device_label = ttk.Label(
            device_frame,
            text="Device",
            font=("Segoe UI", 9)
        )
        device_label.pack(side=tk.LEFT, padx=(0, 5))

        # Get microphones
        from utils.utils import get_valid_microphones
        mic_names = get_valid_microphones() or ["No microphone found"]

        self._device_combo = ttk.Combobox(
            device_frame,
            values=mic_names,
            state="readonly",
            width=30
        )
        self._device_combo.pack(side=tk.LEFT)

        # Set initial selection
        if mic_names:
            saved_mic = SETTINGS.get("selected_microphone", "")
            if saved_mic and saved_mic in mic_names:
                self._device_combo.set(saved_mic)
            else:
                self._device_combo.current(0)

        self._device_combo.bind("<<ComboboxSelected>>", self._on_device_change)
        self.components['header_device_combo'] = self._device_combo

        return header_frame

    def _draw_idle_waveform(self):
        """Draw the idle waveform (dotted horizontal line)."""
        if not self._waveform_canvas:
            return

        self._waveform_canvas.delete("all")
        width = self._waveform_canvas.winfo_width() or 400
        height = self._waveform_canvas.winfo_height() or 40
        mid_y = height // 2

        # Draw dotted line pattern
        dot_spacing = 8
        dot_radius = 2

        for x in range(0, width, dot_spacing):
            # Vary the y position slightly for visual interest
            variance = math.sin(x * 0.1) * 3
            y = mid_y + variance

            self._waveform_canvas.create_oval(
                x - dot_radius, y - dot_radius,
                x + dot_radius, y + dot_radius,
                fill=self.COLORS["waveform_idle"],
                outline=""
            )

    def _draw_active_waveform(self, audio_data: Optional[List[float]] = None):
        """Draw the active waveform during recording.

        Args:
            audio_data: Audio amplitude data to visualize
        """
        if not self._waveform_canvas:
            return

        self._waveform_canvas.delete("all")
        width = self._waveform_canvas.winfo_width() or 400
        height = self._waveform_canvas.winfo_height() or 40
        mid_y = height // 2

        if audio_data and len(audio_data) > 0:
            # Draw actual waveform
            points = []
            step = max(1, len(audio_data) // width)

            for i in range(0, min(len(audio_data), width)):
                idx = min(i * step, len(audio_data) - 1)
                amplitude = audio_data[idx]
                y = mid_y - (amplitude * (height // 2 - 2))
                points.extend([i, y])

            if len(points) >= 4:
                self._waveform_canvas.create_line(
                    points,
                    fill=self.COLORS["waveform_active"],
                    width=2,
                    smooth=True
                )
        else:
            # Draw animated placeholder waveform
            import time
            t = time.time()
            points = []

            for x in range(0, width, 3):
                amplitude = math.sin(x * 0.05 + t * 5) * 0.3 + math.sin(x * 0.02 + t * 3) * 0.2
                y = mid_y - (amplitude * (height // 2 - 5))
                points.extend([x, y])

            if len(points) >= 4:
                self._waveform_canvas.create_line(
                    points,
                    fill=self.COLORS["waveform_active"],
                    width=2,
                    smooth=True
                )

    def _on_canvas_resize(self, event):
        """Handle canvas resize."""
        if self._is_recording:
            self._draw_active_waveform(self._waveform_data)
        else:
            self._draw_idle_waveform()

    def _on_device_change(self, event):
        """Handle device selection change."""
        selected = self._device_combo.get()
        SETTINGS["selected_microphone"] = selected

        try:
            from settings.settings import save_settings
            save_settings(SETTINGS)
        except Exception as e:
            logging.error(f"Error saving microphone setting: {e}")

        # Notify parent if it has a handler
        if hasattr(self.parent, '_on_microphone_change'):
            self.parent._on_microphone_change(event)

    def _update_canvas_theme(self, event=None):
        """Update canvas background to match the current theme."""
        try:
            # Get the background color from the parent frame
            style = ttk.Style()
            bg_color = style.lookup('TFrame', 'background')
            if bg_color:
                self._waveform_canvas.config(bg=bg_color)
        except Exception as e:
            logging.debug(f"Could not update canvas theme: {e}")

    def set_recording_state(self, is_recording: bool, is_paused: bool = False):
        """Update the header state for recording.

        Args:
            is_recording: Whether recording is active
            is_paused: Whether recording is paused
        """
        self._is_recording = is_recording

        if is_recording:
            # Show controls frame (pack after record button, before advanced frame)
            self._controls_frame.pack(side=tk.LEFT, after=self._record_btn)

            # Update button appearance based on paused state
            if is_paused:
                # Main button stays as Stop Recording
                self._record_btn.config(
                    text="⏹  Stop Recording",
                    bg=self.COLORS["button_recording"]
                )
                # Only pause button changes to Resume
                self._pause_btn.config(text="▶ Resume", bg="#28a745")  # Green
                self._pause_timer()
            else:
                self._record_btn.config(
                    text="⏹  Stop Recording",
                    bg=self.COLORS["button_recording"]
                )
                self._pause_btn.config(text="⏸ Pause", bg="#FF9800")  # Orange
                if not self._timer_running:
                    self._start_timer()
                else:
                    self._resume_timer()

            # Start waveform animation
            self._start_waveform_animation()
        else:
            # Hide controls frame
            self._controls_frame.pack_forget()

            # Reset button to idle state
            self._record_btn.config(
                text="▶  Start Recording",
                bg=self.COLORS["button_bg"]
            )

            # Stop timer
            self._stop_timer()

            # Stop animation and show idle waveform
            self._stop_waveform_animation()
            self._draw_idle_waveform()

    def _start_waveform_animation(self):
        """Start the waveform animation."""
        if self._animation_id:
            return

        def animate():
            if self._is_recording:
                self._draw_active_waveform(self._waveform_data)
                self._animation_id = self._waveform_canvas.after(50, animate)

        animate()

    def _stop_waveform_animation(self):
        """Stop the waveform animation."""
        if self._animation_id:
            try:
                self._waveform_canvas.after_cancel(self._animation_id)
            except Exception:
                pass
            self._animation_id = None

    def update_waveform(self, audio_data: List[float]):
        """Update the waveform with new audio data.

        Args:
            audio_data: List of audio amplitude values
        """
        self._waveform_data = audio_data

    def refresh_devices(self):
        """Refresh the device list."""
        from utils.utils import get_valid_microphones
        mic_names = get_valid_microphones() or ["No microphone found"]
        self._device_combo.config(values=mic_names)

    # =========================================================================
    # TIMER METHODS
    # =========================================================================

    def _start_timer(self):
        """Start the recording timer."""
        import time
        self._timer_running = True
        self._timer_start_time = time.time()
        self._timer_paused_time = 0
        self._update_timer_display()

    def _pause_timer(self):
        """Pause the recording timer."""
        import time
        if self._timer_running:
            self._timer_paused_time += time.time() - self._timer_start_time
            self._timer_running = False
            if self._timer_id:
                try:
                    self._timer_label.after_cancel(self._timer_id)
                except Exception:
                    pass
                self._timer_id = None

    def _resume_timer(self):
        """Resume the recording timer."""
        import time
        self._timer_running = True
        self._timer_start_time = time.time()
        self._update_timer_display()

    def _stop_timer(self):
        """Stop and reset the recording timer."""
        self._timer_running = False
        self._timer_start_time = None
        self._timer_paused_time = 0
        if self._timer_id:
            try:
                self._timer_label.after_cancel(self._timer_id)
            except Exception:
                pass
            self._timer_id = None
        if self._timer_label:
            self._timer_label.config(text="00:00")

    def _update_timer_display(self):
        """Update the timer display every second."""
        if not self._timer_running or not self._timer_label:
            return

        import time
        elapsed = self._timer_paused_time + (time.time() - self._timer_start_time)
        minutes = int(elapsed // 60)
        seconds = int(elapsed % 60)
        self._timer_label.config(text=f"{minutes:02d}:{seconds:02d}")

        self._timer_id = self._timer_label.after(1000, self._update_timer_display)
