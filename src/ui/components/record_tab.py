"""
Record Tab Component for Medical Assistant
Handles the recording workflow UI elements
"""

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import BOTH, X, Y, LEFT, RIGHT
import logging
from datetime import datetime
from typing import Dict, Callable, Optional
from ui.tooltip import ToolTip
from ui.scaling_utils import ui_scaler


class RecordTab:
    """Manages the Record workflow tab UI components.

    Note: Recording controls (buttons, timer, waveform) are now in RecordingHeader.
    This tab now primarily displays the Advanced Analysis Results.
    """

    def __init__(self, parent_ui):
        """Initialize the RecordTab component.

        Args:
            parent_ui: Reference to the parent WorkflowUI instance
        """
        self.parent_ui = parent_ui
        self.parent = parent_ui.parent
        self.components = parent_ui.components
        
    def create_record_tab(self, command_map: Dict[str, Callable]) -> ttk.Frame:
        """Create the Record workflow tab (legacy - for backwards compatibility).

        Args:
            command_map: Dictionary of commands

        Returns:
            ttk.Frame: The record tab frame
        """
        # For backwards compatibility, delegate to create_analysis_panel
        return self.create_analysis_panel(self.parent, command_map)

    def create_analysis_panel(self, parent, command_map: Optional[Dict[str, Callable]] = None) -> ttk.Frame:
        """Create the Advanced Analysis Results panel.

        This is the main panel that shows analysis results during recording.
        It takes full width in the shared panel area.

        Args:
            parent: Parent widget for the panel
            command_map: Optional dictionary of commands

        Returns:
            ttk.Frame: The analysis panel frame
        """
        # Store command map for later use
        if command_map:
            self._command_map = command_map

        analysis_frame = ttk.Frame(parent)

        # Create placeholder components for backwards compatibility
        self._create_placeholder_components()

        # Main content frame with padding
        content_frame = ttk.Frame(analysis_frame)
        content_frame.pack(fill=BOTH, expand=True, padx=10, pady=5)

        # Create text area
        text_frame = ttk.Labelframe(content_frame, text="Advanced Analysis Results", padding=10)
        text_frame.pack(fill=BOTH, expand=True)

        # Create header frame with countdown and buttons
        header_frame = ttk.Frame(text_frame)
        header_frame.pack(fill=X, pady=(0, 5))

        # Countdown label on the left
        self.countdown_label = ttk.Label(header_frame, text="", width=14, anchor="w")
        self.countdown_label.pack(side=LEFT)
        self.components['countdown_label'] = self.countdown_label

        # Button row on the right
        button_frame = ttk.Frame(header_frame)
        button_frame.pack(side=RIGHT)

        copy_btn = ttk.Button(
            button_frame,
            text="Copy",
            command=self._copy_analysis,
            bootstyle="secondary-outline",
            width=6
        )
        copy_btn.pack(side=LEFT, padx=2)
        ToolTip(copy_btn, "Copy analysis to clipboard")
        self.components['copy_analysis_button'] = copy_btn

        soap_btn = ttk.Button(
            button_frame,
            text="→ SOAP",
            command=self._add_analysis_to_soap,
            bootstyle="info-outline",
            width=7
        )
        soap_btn.pack(side=LEFT, padx=2)
        ToolTip(soap_btn, "Add analysis to SOAP note")
        self.components['soap_analysis_button'] = soap_btn

        clear_btn = ttk.Button(
            button_frame,
            text="Clear",
            command=self._clear_analysis,
            bootstyle="secondary-outline",
            width=6
        )
        clear_btn.pack(side=LEFT, padx=2)
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

        # Add empty state hint
        self._show_empty_state_hint()

        return analysis_frame

    def _create_placeholder_components(self):
        """Create placeholder component references for backwards compatibility.

        The actual recording controls are now in the header. This method sets up
        references so that code expecting record tab components still works.
        """
        # These will be redirected to header controls after header is created
        # For now, set to None - they'll be updated by _link_to_header_controls
        self.components['main_record_button'] = None
        self.components['pause_button'] = None
        self.components['cancel_button'] = None
        self.components['timer_label'] = None

    def link_to_header_controls(self):
        """Link component references to header controls.

        Called after the recording header is created to redirect
        component references to the header controls.
        """
        # Get header components
        header_record = self.components.get('header_record_button')
        header_pause = self.components.get('header_pause_button')
        header_cancel = self.components.get('header_cancel_button')
        header_timer = self.components.get('header_timer_label')

        # Update main component references to point to header controls
        if header_record:
            self.components['main_record_button'] = header_record
        if header_pause:
            self.components['pause_button'] = header_pause
        if header_cancel:
            self.components['cancel_button'] = header_cancel
        if header_timer:
            self.components['timer_label'] = header_timer

        # Link advanced analysis vars from header
        if hasattr(self.parent_ui, 'recording_header') and self.parent_ui.recording_header:
            header = self.parent_ui.recording_header
            if hasattr(header, 'advanced_analysis_var'):
                self.parent_ui.advanced_analysis_var = header.advanced_analysis_var
            if hasattr(header, 'analysis_interval_var'):
                self.parent_ui.analysis_interval_var = header.analysis_interval_var

    def _initialize_recording_ui_state(self):
        """Initialize the recording UI to its default state.

        Most controls are now in the header, so this is simplified.
        """
        pass  # Recording controls are now in the header
    
    def set_recording_state(self, recording: bool, paused: bool = False):
        """Update UI elements based on recording state.

        Recording controls are now in the header. This method handles
        any Record tab-specific state changes.

        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        logging.info(f"RecordTab.set_recording_state called: recording={recording}, paused={paused}")

        if recording and not paused:
            # Clear the analysis display when starting a new recording
            text_widget = self.components.get('record_notes_text')
            if text_widget:
                current = text_widget.get("1.0", "end-1c")
                # Only clear if there's actual content (not just the hint)
                if current.strip() and "will appear here" not in current:
                    # Keep existing analysis - don't clear during recording
                    pass
        elif not recording:
            # Recording stopped - optionally clear for next session
            # (Analysis results are kept until explicitly cleared)
            pass
    
    # Note: Timer and animation methods removed - now handled by RecordingHeader

    # ==================== Advanced Analysis Methods ====================

    def _show_empty_state_hint(self):
        """Show the empty state hint in the analysis text area."""
        text_widget = self.components.get('record_notes_text')
        if text_widget:
            text_widget.delete("1.0", tk.END)
            hint_text = (
                "Advanced Analysis results will appear here during recording.\n\n"
                "To enable:\n"
                "1. Check 'Advanced Analysis' in the header above\n"
                "2. Select the analysis interval (1, 2, or 5 minutes)\n"
                "3. Click 'Start Recording'\n\n"
                "Real-time differential diagnosis suggestions will appear here\n"
                "with timestamps as you record."
            )
            text_widget.insert("1.0", hint_text)
            text_widget.config(foreground="gray")

    def _copy_analysis(self):
        """Copy analysis results to clipboard."""
        text_widget = self.components.get('record_notes_text')
        if not text_widget:
            return

        text = text_widget.get("1.0", "end-1c").strip()

        # Don't copy the empty state hint
        if not text or "will appear here" in text:
            self._show_feedback("Nothing to copy")
            return

        try:
            self.parent.clipboard_clear()
            self.parent.clipboard_append(text)
            self._show_feedback("Copied to clipboard")
        except Exception as e:
            logging.error(f"Error copying analysis: {e}")
            self._show_feedback("Copy failed")

    def _add_analysis_to_soap(self):
        """Add analysis results to SOAP note."""
        text_widget = self.components.get('record_notes_text')
        if not text_widget:
            return

        text = text_widget.get("1.0", "end-1c").strip()

        # Don't add the empty state hint
        if not text or "will appear here" in text:
            self._show_feedback("No analysis to add")
            return

        try:
            # Find the SOAP text widget in parent
            soap_text = None
            if hasattr(self.parent_ui, 'parent') and hasattr(self.parent_ui.parent, 'ui'):
                ui = self.parent_ui.parent.ui
                if hasattr(ui, 'components') and 'soap_text' in ui.components:
                    soap_text = ui.components['soap_text']

            if soap_text:
                # Append to SOAP note with separator
                soap_text.insert(tk.END, f"\n\n{'─' * 40}\nAdvanced Analysis:\n{'─' * 40}\n{text}")
                soap_text.see(tk.END)
                self._show_feedback("Added to SOAP note")
            else:
                self._show_feedback("SOAP note not available")
        except Exception as e:
            logging.error(f"Error adding to SOAP: {e}")
            self._show_feedback("Failed to add")

    def _clear_analysis(self):
        """Clear the analysis text and show empty state."""
        self._show_empty_state_hint()
        self.update_countdown(0, clear=True)
        self._show_feedback("Cleared")

    def _show_feedback(self, message: str):
        """Show brief feedback in the countdown label."""
        if hasattr(self, 'countdown_label'):
            original_text = self.countdown_label.cget('text')
            self.countdown_label.config(text=message)
            # Restore after 2 seconds
            self.parent.after(2000, lambda: self.countdown_label.config(text=original_text))

    def update_countdown(self, seconds: int, clear: bool = False):
        """Update the countdown display.

        Args:
            seconds: Seconds remaining until next analysis
            clear: If True, clear the countdown display
        """
        if not hasattr(self, 'countdown_label'):
            return

        if clear:
            self.countdown_label.config(text="")
        elif seconds <= 0:
            self.countdown_label.config(text="Analyzing...")
        else:
            mins, secs = divmod(seconds, 60)
            self.countdown_label.config(text=f"Next: {mins}:{secs:02d}")

    def update_analysis_display(self, text: str):
        """Update analysis display with accumulated results.

        Args:
            text: New analysis text to append
        """
        text_widget = self.components.get('record_notes_text')
        if not text_widget:
            return

        try:
            # Get current content
            current = text_widget.get("1.0", "end-1c")

            # Clear empty state hint if present
            if "will appear here" in current:
                text_widget.delete("1.0", tk.END)
                text_widget.config(foreground="")  # Reset to default color
                current = ""

            # Add separator if not first entry
            if current.strip():
                text_widget.insert(tk.END, "\n\n" + "─" * 50 + "\n\n")

            # Add timestamped entry
            timestamp = datetime.now().strftime("%H:%M:%S")
            text_widget.insert(tk.END, f"[{timestamp}]\n{text}")
            text_widget.see(tk.END)

        except Exception as e:
            logging.error(f"Error updating analysis display: {e}")

    def get_analysis_interval_seconds(self) -> int:
        """Get the current analysis interval in seconds.

        Returns:
            Interval in seconds (60, 120, or 300)
        """
        try:
            # Get interval from parent_ui (set from header)
            if hasattr(self.parent_ui, 'analysis_interval_var') and self.parent_ui.analysis_interval_var:
                interval_str = self.parent_ui.analysis_interval_var.get()
            elif hasattr(self.parent_ui, 'recording_header') and self.parent_ui.recording_header:
                interval_str = self.parent_ui.recording_header.analysis_interval_var.get()
            else:
                return 120  # Default to 2 minutes

            minutes = int(interval_str.split()[0])
            return minutes * 60
        except (ValueError, IndexError, AttributeError):
            return 120  # Default to 2 minutes