"""
Recording Controller Module

Handles all recording-related operations including SOAP recording,
pause/resume, cancellation, and audio processing coordination.

This controller extracts recording logic from the main App class to
improve maintainability and separation of concerns.
"""

import logging
import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Callable, Any, Dict, TYPE_CHECKING

from settings.settings import SETTINGS

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class RecordingController:
    """Controller for managing recording operations.

    This class coordinates:
    - SOAP recording start/stop
    - Recording pause/resume
    - Recording cancellation
    - Audio callback handling
    - Periodic analysis during recording
    - Post-recording processing coordination

    Thread Safety:
        All state changes are protected by _state_lock to prevent race conditions.
        The recording_manager.is_recording property is the single source of truth
        for recording state.
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the recording controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self._state_lock = threading.Lock()
        self._soap_stop_listening_function: Optional[Callable] = None
        # Note: We use recording_manager.is_recording as the single source of truth
        # _listening_active tracks whether we have an active background listener

    @property
    def is_recording(self) -> bool:
        """Check if SOAP recording is active.

        Uses recording_manager as the single source of truth.
        """
        return self.app.recording_manager.is_recording

    @property
    def is_paused(self) -> bool:
        """Check if recording is paused.

        Uses recording_manager as the single source of truth.
        """
        return self.app.recording_manager.is_paused

    def toggle_recording(self) -> None:
        """Toggle SOAP recording on/off.

        Thread-safe: Uses lock to prevent race conditions during state transitions.
        """
        with self._state_lock:
            if not self.app.recording_manager.is_recording:
                self._start_recording()
            else:
                self._stop_recording()

    def _start_recording(self) -> None:
        """Start a new SOAP recording session.

        Note: Called within _state_lock context from toggle_recording().
        Uses recording_manager as single source of truth for state.
        """
        from utils.cleanup_utils import clear_all_content

        # Switch focus to the SOAP tab
        self.app.notebook.select(1)

        # Clear all text fields and audio segments before starting
        clear_all_content(self.app)

        self.app.status_manager.info("Starting SOAP recording...")

        # Get selected device
        selected_device = self.app.mic_combobox.get()

        # Set up audio handler for SOAP mode
        self.app.audio_handler.soap_mode = True
        self.app.audio_handler.silence_threshold = 0.0001

        # Start recording with callback - recording_manager handles state
        if self.app.recording_manager.start_recording(self._soap_callback):
            # Update UI state after successful start
            self.app.after(0, lambda: self.app.ui_state_manager.set_recording_state(
                recording=True, caller="recording_controller_start"
            ))
            self.app.play_recording_sound(start=True)

            # Store the stop function for pause/cancel functionality
            self._soap_stop_listening_function = self.app.audio_handler.listen_in_background(
                mic_name=selected_device,
                callback=self._soap_callback,
                phrase_time_limit=3
            )
            # Note: No separate _soap_recording flag - recording_manager.is_recording is truth
            logger.info("SOAP recording started successfully")

            # Clear and initialize analysis text area
            self._initialize_analysis_display()

            # Start periodic analysis if enabled
            if hasattr(self.app.ui, 'advanced_analysis_var') and self.app.ui.advanced_analysis_var.get():
                self.app._start_periodic_analysis()
        else:
            self.app.status_manager.error("Failed to start recording")
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="recording_controller_start_failed"
            )

    def _stop_recording(self) -> None:
        """Stop the current SOAP recording.

        Note: Called within _state_lock context from toggle_recording().
        Uses recording_manager as single source of truth for state.
        """
        self.app.status_manager.info("Stopping SOAP recording...")

        # Temporarily disable the record button
        main_record_btn = self.app.ui.components.get('main_record_button')
        if main_record_btn:
            main_record_btn.config(state=tk.DISABLED)

        # Stop the background listening
        if self._soap_stop_listening_function:
            self._soap_stop_listening_function()
            self._soap_stop_listening_function = None

        # Stop periodic analysis if running
        self.app._stop_periodic_analysis()

        # Reset audio handler settings
        self.app.audio_handler.soap_mode = False
        self.app.audio_handler.silence_threshold = 0.001

        # Stop and get recording data - recording_manager handles state transition
        recording_data = self.app.recording_manager.stop_recording()
        if recording_data:
            self.app.play_recording_sound(start=False)
            # Note: No separate _soap_recording flag - recording_manager.is_recording is truth
            self._finalize_recording(recording_data)
        else:
            self.app.status_manager.error("No recording data available")
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="recording_controller_stop_no_data"
            )

    def _finalize_recording(self, recording_data: Dict[str, Any]) -> None:
        """Complete the SOAP recording process.

        Args:
            recording_data: Recording data from RecordingManager
        """
        if not recording_data or not recording_data.get('audio'):
            self.app.status_manager.error("No audio data available")
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="finalize_no_audio"
            )
            return

        # Check if quick continue mode is enabled
        if SETTINGS.get("quick_continue_mode", True):
            # Queue for background processing
            self.app._queue_recording_for_processing(recording_data)
            # Reset UI immediately
            self.app._reset_ui_for_next_patient()
            self.app.status_manager.info("Recording queued • Ready for next patient")
        else:
            # Process immediately
            self.app.process_soap_recording()
            self.app.after(0, lambda: self.app.ui_state_manager.set_recording_state(
                recording=False, caller="finalize_delayed"
            ))

        # Trigger recording complete event for auto-save
        self.app.event_generate("<<RecordingComplete>>", when="tail")

    def toggle_pause(self) -> None:
        """Toggle pause state for SOAP recording.

        Thread-safe: Uses lock to prevent race conditions during state transitions.
        """
        with self._state_lock:
            if self.is_recording:
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
                callback=self._soap_callback,
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

    def cancel(self) -> None:
        """Cancel the current SOAP recording without processing.

        Thread-safe: Uses lock to prevent race conditions during state transitions.
        """
        # Check state before showing dialog (don't hold lock during dialog)
        if not self.is_recording:
            return

        # Show confirmation dialog
        self.app.focus_force()
        self.app.update()

        if not messagebox.askyesno(
            "Cancel Recording",
            "Are you sure you want to cancel the current recording?\n\n"
            "All recorded audio will be discarded.",
            icon="warning",
            parent=self.app
        ):
            return

        self.app.update_status("Cancelling recording...")
        with self._state_lock:
            self._perform_cancellation()

    def _perform_cancellation(self) -> None:
        """Perform the actual recording cancellation.

        Note: Must be called with _state_lock held.
        Uses recording_manager as single source of truth for state.
        """
        try:
            # Stop the background listening
            if self._soap_stop_listening_function:
                self._soap_stop_listening_function()
                self._soap_stop_listening_function = None

            # Stop periodic analysis if running
            self.app._stop_periodic_analysis()

            # Reset audio handler settings
            self.app.audio_handler.soap_mode = False
            self.app.audio_handler.silence_threshold = 0.001

            # Cancel the recording in RecordingManager - handles state transition
            self.app.recording_manager.cancel_recording()
            # Note: No separate _soap_recording flag - recording_manager.is_recording is truth

            # Clear all UI fields
            from utils.cleanup_utils import clear_all_content
            clear_all_content(self.app)

            # Reset UI state
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="cancel"
            )
            self.app.status_manager.info("Recording cancelled")
            logger.info("SOAP recording cancelled by user")

        except Exception as e:
            logger.error(f"Error cancelling recording: {e}", exc_info=True)
            self.app.status_manager.error(f"Error cancelling: {str(e)}")
            # Ensure UI is reset even on error
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="cancel_error"
            )

    def _soap_callback(self, audio_data: Any) -> None:
        """Callback for SOAP note recording.

        Args:
            audio_data: Audio data from the recording
        """
        self.app.soap_audio_processor.process_soap_callback(audio_data)

    def _initialize_analysis_display(self) -> None:
        """Initialize the analysis text area for a new recording."""
        if 'record_notes_text' in self.app.ui.components:
            text_widget = self.app.ui.components['record_notes_text']
            text_widget.delete("1.0", tk.END)

            # Show message if Advanced Analysis is enabled
            if hasattr(self.app.ui, 'advanced_analysis_var') and self.app.ui.advanced_analysis_var.get():
                text_widget.insert(
                    "1.0",
                    "Advanced Analysis enabled. First analysis will appear after 2 minutes...\n\n"
                )

    def cleanup(self) -> None:
        """Clean up resources when the controller is destroyed.

        Thread-safe cleanup of recording resources.
        """
        with self._state_lock:
            if self._soap_stop_listening_function:
                try:
                    self._soap_stop_listening_function()
                except Exception as e:
                    logger.warning(f"Error stopping recording during cleanup: {e}")
                self._soap_stop_listening_function = None
            # Note: No separate _soap_recording flag to clear
            # recording_manager handles its own state cleanup
