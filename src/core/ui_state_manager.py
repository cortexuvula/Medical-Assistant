"""
UI State Manager Module

Manages UI state transitions including recording states, button states,
progress indicators, and other UI element coordination.

This controller extracts UI state management logic from the main App class
to improve maintainability and separation of concerns.
"""

import tkinter as tk
from tkinter import NORMAL, DISABLED
from typing import Optional, Dict, Any, TYPE_CHECKING

from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = get_logger(__name__)


class UIStateManager:
    """Manager for UI state transitions and coordination.

    This class handles:
    - Recording UI state (buttons, indicators)
    - Progress indicators
    - Button state management
    - Theme-aware state updates
    - Coordinated multi-widget state changes
    """

    # Recording button states
    RECORD_BUTTON_IDLE = "🎙️ Record"
    RECORD_BUTTON_RECORDING = "⏹️ Stop"
    RECORD_BUTTON_PAUSED = "⏹️ Stop"

    PAUSE_BUTTON_IDLE = "⏸️ Pause"
    PAUSE_BUTTON_PAUSED = "▶️ Resume"

    # Colors for different states
    RECORDING_COLOR = "#dc3545"  # Red
    PAUSED_COLOR = "#ffc107"  # Yellow/Orange
    IDLE_COLOR = None  # Use theme default

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the UI state manager.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self._current_state = "idle"
        self._state_history: list = []

    @property
    def current_state(self) -> str:
        """Get the current UI state."""
        return self._current_state

    def set_recording_state(self, recording: bool, paused: bool = False, caller: str = "unknown") -> None:
        """Update UI elements to reflect the current recording state.

        Args:
            recording: Whether recording is active
            paused: Whether recording is paused (only relevant if recording=True)
            caller: Identifier for debugging state transitions
        """
        logger.debug(f"UI state update: recording={recording}, paused={paused}, caller={caller}")

        # Update state tracking
        previous_state = self._current_state
        if not recording:
            self._current_state = "idle"
        elif paused:
            self._current_state = "paused"
        else:
            self._current_state = "recording"

        self._state_history.append({
            "from": previous_state,
            "to": self._current_state,
            "caller": caller
        })

        # Limit history size
        if len(self._state_history) > 100:
            self._state_history = self._state_history[-50:]

        # Update buttons
        self._update_record_button(recording, paused)
        self._update_pause_button(recording, paused)
        self._update_cancel_button(recording)

        # Update other UI elements
        self._update_mic_selector(recording)
        self._update_provider_selectors(recording)

        # Update record tab UI (timer, pulse animation, etc.)
        self._update_record_tab_state(recording, paused)

    def _update_record_button(self, recording: bool, paused: bool) -> None:
        """Update the main record button state."""
        main_record_btn = self.app.ui.components.get('main_record_button')
        if not main_record_btn:
            return

        try:
            if recording:
                main_record_btn.config(
                    text=self.RECORD_BUTTON_RECORDING,
                    state=NORMAL
                )
                # Apply recording color if supported by theme
                self._apply_button_style(main_record_btn, "recording" if not paused else "paused")
            else:
                main_record_btn.config(
                    text=self.RECORD_BUTTON_IDLE,
                    state=NORMAL
                )
                self._apply_button_style(main_record_btn, "idle")
        except tk.TclError as e:
            logger.warning(f"Error updating record button: {e}")

    def _update_pause_button(self, recording: bool, paused: bool) -> None:
        """Update the pause/resume button state."""
        pause_btn = self.app.ui.components.get('pause_button')
        if not pause_btn:
            return

        try:
            if recording:
                pause_btn.config(
                    text=self.PAUSE_BUTTON_PAUSED if paused else self.PAUSE_BUTTON_IDLE,
                    state=NORMAL
                )
            else:
                pause_btn.config(
                    text=self.PAUSE_BUTTON_IDLE,
                    state=DISABLED
                )
        except tk.TclError as e:
            logger.warning(f"Error updating pause button: {e}")

    def _update_cancel_button(self, recording: bool) -> None:
        """Update the cancel button state."""
        cancel_btn = self.app.ui.components.get('cancel_button')
        if not cancel_btn:
            return

        try:
            cancel_btn.config(state=NORMAL if recording else DISABLED)
        except tk.TclError as e:
            logger.warning(f"Error updating cancel button: {e}")

    def _update_mic_selector(self, recording: bool) -> None:
        """Update microphone selector state during recording."""
        try:
            if hasattr(self.app, 'mic_combobox'):
                self.app.mic_combobox.config(state=DISABLED if recording else "readonly")
        except tk.TclError as e:
            logger.warning(f"Error updating mic selector: {e}")

    def _update_provider_selectors(self, recording: bool) -> None:
        """Update provider selector states during recording."""
        try:
            if hasattr(self.app, 'stt_combobox'):
                self.app.stt_combobox.config(state=DISABLED if recording else "readonly")
            if hasattr(self.app, 'provider_combobox'):
                self.app.provider_combobox.config(state=DISABLED if recording else "readonly")
        except tk.TclError as e:
            logger.warning(f"Error updating provider selectors: {e}")

    def _update_record_tab_state(self, recording: bool, paused: bool) -> None:
        """Update record tab UI elements (timer, pulse animation, etc.).

        Args:
            recording: Whether recording is active
            paused: Whether recording is paused
        """
        try:
            # Delegate to workflow UI's record tab for timer and visual updates
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'set_recording_state'):
                self.app.ui.set_recording_state(recording, paused)

            # Update recording header controls (Pause, Cancel, Timer)
            if hasattr(self.app, 'ui') and hasattr(self.app.ui, 'recording_header'):
                self.app.ui.recording_header.set_recording_state(recording, paused)
        except tk.TclError as e:
            logger.warning(f"Error updating record tab state: {e}")

    def _apply_button_style(self, button: tk.Widget, state: str) -> None:
        """Apply visual style to a button based on state.

        Args:
            button: The button widget to style
            state: One of 'idle', 'recording', 'paused'
        """
        # This can be extended to apply ttkbootstrap styles
        # For now, we rely on the button text changes
        pass

    def set_processing_state(self, processing: bool, operation: str = "") -> None:
        """Update UI to indicate processing state.

        Args:
            processing: Whether processing is active
            operation: Description of the operation being performed
        """
        # Update generation buttons
        self._set_generation_buttons_enabled(not processing)

        # Update progress bar
        if hasattr(self.app, 'progress_bar'):
            try:
                if processing:
                    self.app.progress_bar.pack(side=tk.RIGHT, padx=10)
                    self.app.progress_bar.start()
                else:
                    self.app.progress_bar.stop()
                    self.app.progress_bar.pack_forget()
            except tk.TclError:
                pass

    def _set_generation_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable document generation buttons.

        Args:
            enabled: Whether buttons should be enabled
        """
        state = NORMAL if enabled else DISABLED
        buttons = ['refine_button', 'improve_button', 'soap_button']

        for btn_name in buttons:
            if hasattr(self.app, btn_name):
                try:
                    getattr(self.app, btn_name).config(state=state)
                except tk.TclError:
                    pass

    def show_status_indicator(self, indicator_type: str, message: str = "") -> None:
        """Show a status indicator in the UI.

        Args:
            indicator_type: Type of indicator ('recording', 'processing', 'error', 'success')
            message: Optional message to display
        """
        # This could be extended to show visual indicators in the status bar
        pass

    def reset_to_idle(self) -> None:
        """Reset all UI elements to idle state."""
        self.set_recording_state(recording=False, caller="reset_to_idle")
        self.set_processing_state(processing=False)
        self._current_state = "idle"

    def get_state_history(self, limit: int = 10) -> list:
        """Get recent state transition history for debugging.

        Args:
            limit: Maximum number of entries to return

        Returns:
            List of state transition records
        """
        return self._state_history[-limit:]

    def enable_api_dependent_buttons(self, has_api_key: bool) -> None:
        """Enable or disable buttons that require API keys.

        Args:
            has_api_key: Whether a valid API key is configured
        """
        state = NORMAL if has_api_key else DISABLED

        api_buttons = ['refine_button', 'improve_button', 'soap_button']
        for btn_name in api_buttons:
            if hasattr(self.app, btn_name):
                try:
                    getattr(self.app, btn_name).config(state=state)
                except tk.TclError:
                    pass

    def update_restore_button_visibility(self, has_autosave: bool) -> None:
        """Update visibility of the autosave restore button.

        Args:
            has_autosave: Whether there is autosave data available
        """
        restore_btn = self.app.ui.components.get('restore_autosave_btn')
        if not restore_btn:
            return

        try:
            if has_autosave:
                restore_btn.pack(side=tk.RIGHT, padx=5)
            else:
                restore_btn.pack_forget()
        except tk.TclError:
            pass

    def flash_button(self, button_name: str, times: int = 3, interval: int = 200) -> None:
        """Flash a button to draw attention to it.

        Args:
            button_name: Name of the button in ui.components
            times: Number of times to flash
            interval: Milliseconds between flashes
        """
        button = self.app.ui.components.get(button_name)
        if not button:
            return

        original_state = button.cget('state')

        def do_flash(remaining: int, show: bool):
            if remaining <= 0:
                try:
                    button.config(state=original_state)
                except tk.TclError:
                    pass
                return

            try:
                # Toggle visibility or style
                button.config(state=NORMAL if show else DISABLED)
                self.app.after(interval, lambda: do_flash(remaining - 1, not show))
            except tk.TclError:
                pass

        do_flash(times * 2, False)
