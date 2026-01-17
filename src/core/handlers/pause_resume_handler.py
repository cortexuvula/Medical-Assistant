"""
Pause/Resume Handler

Provides pause and resume state machine for recording sessions.
Extracted from RecordingController for better separation of concerns.
"""

import threading
from typing import TYPE_CHECKING, Optional, Callable

from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = get_logger(__name__)


class PauseResumeHandler:
    """Handles recording pause/resume state transitions.

    This handler manages:
    - Pause/resume toggle logic
    - State machine for recording pause states
    - Audio handler coordination during pause/resume
    - Advanced analysis toggle during recording
    """

    def __init__(self, app: 'MedicalDictationApp', state_lock: threading.Lock):
        """Initialize the pause/resume handler.

        Args:
            app: Reference to the main application instance
            state_lock: Shared lock for thread-safe state transitions
        """
        self.app = app
        self._state_lock = state_lock
        # Reference to stop listening function (managed by parent controller)
        self._soap_stop_listening_function: Optional[Callable] = None

    def set_stop_function(self, stop_func: Optional[Callable]) -> None:
        """Set the stop listening function reference.

        Args:
            stop_func: The function to stop background listening
        """
        self._soap_stop_listening_function = stop_func

    def get_stop_function(self) -> Optional[Callable]:
        """Get the current stop listening function.

        Returns:
            The stop listening function or None
        """
        return self._soap_stop_listening_function

    def clear_stop_function(self) -> None:
        """Clear the stop listening function reference."""
        self._soap_stop_listening_function = None

    # ========================================
    # Pause/Resume Operations
    # ========================================

    def toggle_pause(self) -> None:
        """Toggle pause state for SOAP recording.

        Thread-safe: Uses lock to prevent race conditions during state transitions.
        """
        with self._state_lock:
            # Check for both recording and paused states
            # (is_recording returns False when paused, so we need to check both)
            is_recording = self.app.recording_manager.is_recording
            is_paused = self.app.recording_manager.is_paused

            if is_recording or is_paused:
                if self._soap_stop_listening_function:
                    self._pause_internal()
                else:
                    self._resume_internal()

    def pause(self) -> None:
        """Pause the current SOAP recording.

        Thread-safe wrapper for external calls.
        """
        with self._state_lock:
            self._pause_internal()

    def _pause_internal(self) -> None:
        """Internal pause implementation (must be called with lock held)."""
        if not self._soap_stop_listening_function:
            return

        self.app.play_recording_sound(start=False)
        self.app.recording_manager.pause_recording()

        # Stop the current recording
        self._soap_stop_listening_function()
        self._soap_stop_listening_function = None

        # Update UI
        self.app.ui_state_manager.set_recording_state(
            recording=True, paused=True, caller="pause"
        )
        self.app.update_status("SOAP recording paused. Press Resume to continue.", "info")

    def resume(self) -> None:
        """Resume SOAP recording after pause.

        Thread-safe wrapper for external calls.
        """
        with self._state_lock:
            self._resume_internal()

    def _resume_internal(self) -> None:
        """Internal resume implementation (must be called with lock held)."""
        try:
            self.app.play_recording_sound(start=True)
            self.app.recording_manager.resume_recording()

            # Get selected microphone
            selected_device = self.app.mic_combobox.get()

            from utils.utils import get_device_index_from_name
            device_index = get_device_index_from_name(selected_device)
            logger.info(f"Resuming SOAP recording with device: {selected_device} (index {device_index})")

            # Start new recording session
            self._soap_stop_listening_function = self.app.audio_handler.listen_in_background(
                mic_name=selected_device,
                callback=self._get_soap_callback(),
                phrase_time_limit=3
            )

            # Update UI
            self.app.ui_state_manager.set_recording_state(
                recording=True, paused=False, caller="resume"
            )
            self.app.update_status("SOAP recording resumed.", "info")

        except Exception as e:
            logger.error("Error resuming SOAP recording", exc_info=True)
            self.app.update_status(f"Error resuming SOAP recording: {str(e)}", "error")

    def _get_soap_callback(self) -> Callable:
        """Get the SOAP callback function from the app.

        Returns:
            The SOAP callback function
        """
        # Access the callback through the recording controller
        if hasattr(self.app, 'recording_controller'):
            return self.app.recording_controller._soap_callback
        # Fallback to soap_audio_processor
        return self.app.soap_audio_processor.process_soap_callback

    # ========================================
    # Advanced Analysis Toggle
    # ========================================

    def on_advanced_analysis_toggled(self, enabled: bool) -> None:
        """Handle advanced analysis checkbox toggle during recording.

        Allows starting/stopping periodic analysis mid-recording when the user
        toggles the Advanced Analysis checkbox.

        Args:
            enabled: Whether the checkbox is now checked
        """
        # Only act if recording is active
        if not self.app.recording_manager.is_recording:
            return

        if enabled:
            # Start periodic analysis mid-recording
            if hasattr(self.app, 'recording_controller'):
                self.app.recording_controller.start_periodic_analysis()
            # Show the analysis panel
            if hasattr(self.app.ui, 'shared_panel_manager') and self.app.ui.shared_panel_manager:
                from ui.components.shared_panel_manager import SharedPanelManager
                self.app.ui.shared_panel_manager.show_panel(SharedPanelManager.PANEL_ANALYSIS)
            logger.info("Started periodic analysis mid-recording")
        else:
            # Stop periodic analysis mid-recording
            if hasattr(self.app, 'recording_controller'):
                self.app.recording_controller.stop_periodic_analysis()
            logger.info("Stopped periodic analysis mid-recording")


__all__ = ["PauseResumeHandler"]
