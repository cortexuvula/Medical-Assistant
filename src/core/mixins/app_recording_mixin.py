"""
App Recording Mixin

Provides recording control methods for the MedicalDictationApp.
These are legacy fallback implementations for when recording_controller is not available.
Extracted from app.py for better separation of concerns.
"""

import time
import threading
import tkinter as tk
from tkinter import messagebox
from typing import TYPE_CHECKING, Optional

from settings.settings import SETTINGS
from utils.cleanup_utils import clear_content_except_context
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from audio.recording_manager import RecordingManager
    from audio.audio import AudioHandler

logger = get_logger(__name__)


class AppRecordingMixin:
    """Mixin providing recording control methods for MedicalDictationApp.

    This mixin expects the following attributes on the class:
    - recording_controller: RecordingController instance (primary)
    - recording_manager: RecordingManager instance (legacy fallback)
    - audio_handler: AudioHandler instance
    - mic_combobox: Microphone selection combobox
    - soap_recording: Boolean flag
    - soap_stop_listening_function: Callable or None
    - status_manager: StatusManager instance
    - ui_state_manager: UIStateManager instance
    - ui: WorkflowUI instance
    """

    def _finalize_soap_recording(self, recording_data: dict = None) -> None:
        """Complete the SOAP recording process with recording data from RecordingManager."""
        # Recording data should come from RecordingManager which uses AudioStateManager
        if not recording_data or not recording_data.get('audio'):
            self.status_manager.error("No audio data available")
            self._update_recording_ui_state(recording=False, caller="finalize_no_audio")
            return

        # Check if quick continue mode is enabled
        if SETTINGS.get("quick_continue_mode", True):
            # Queue for background processing
            self._queue_recording_for_processing(recording_data)
            # Reset UI immediately
            self._reset_ui_for_next_patient()
            # Show status
            self.status_manager.info("Recording queued - Ready for next patient")

            # Trigger recording complete event for auto-save (also when queued)
            self.event_generate("<<RecordingComplete>>", when="tail")
        else:
            # Current behavior - process immediately
            self.process_soap_recording()
            # Reset all button states after processing is complete
            self.after(0, lambda: self._update_recording_ui_state(recording=False, caller="finalize_delayed"))

            # Trigger recording complete event for auto-save
            self.event_generate("<<RecordingComplete>>", when="tail")

    def pause_soap_recording(self) -> None:
        """Pause SOAP recording.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.pause()
            return

        # Legacy implementation (fallback)
        if self.soap_stop_listening_function:
            # Play pause sound (quick beep)
            self.play_recording_sound(start=False)

            # Pause the recording manager
            self.recording_manager.pause_recording()

            # Stop the current recording
            self.soap_stop_listening_function()
            self.soap_stop_listening_function = None

            # Update UI
            self._update_recording_ui_state(recording=True, paused=True, caller="pause")
            self.update_status("SOAP recording paused. Press Resume to continue.", "info")

    def resume_soap_recording(self) -> None:
        """Resume SOAP recording after pause using the selected microphone.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.resume()
            return

        # Legacy implementation (fallback)
        try:
            # Play resume sound
            self.play_recording_sound(start=True)

            # Resume the recording manager
            self.recording_manager.resume_recording()

            # Get selected microphone name
            selected_device = self.mic_combobox.get()

            # Get the actual device index if using the new naming format
            from utils.utils import get_device_index_from_name
            device_index = get_device_index_from_name(selected_device)

            # Log the selected device information
            logger.info(f"Resuming SOAP recording with device: {selected_device} (index {device_index})")

            # Start new recording session
            self.soap_stop_listening_function = self.audio_handler.listen_in_background(
                mic_name=selected_device,
                callback=self.soap_callback,
                phrase_time_limit=3  # Use 3 seconds for more frequent processing
            )

            # Update UI
            self._update_recording_ui_state(recording=True, paused=False, caller="resume")
            self.update_status("SOAP recording resumed.", "info")

        except Exception as e:
            logger.error("Error resuming SOAP recording", exc_info=True)
            self.update_status(f"Error resuming SOAP recording: {str(e)}", "error")

    def cancel_soap_recording(self) -> None:
        """Cancel the current SOAP note recording without processing.

        This method delegates to the RecordingController for centralized recording management.
        """
        # Delegate to recording controller if available
        if hasattr(self, 'recording_controller') and self.recording_controller:
            self.recording_controller.cancel()
            return

        # Legacy implementation (fallback)
        if not self.soap_recording:
            return

        # Show confirmation dialog before canceling
        # Force focus to ensure keyboard shortcuts work
        self.focus_force()
        self.update()

        if not messagebox.askyesno("Cancel Recording",
                                  "Are you sure you want to cancel the current recording?\n\n"
                                  "All recorded audio will be discarded.",
                                  icon="warning",
                                  parent=self):
            return  # User clicked "No", abort cancellation

        self.update_status("Cancelling recording...")

        def cancel_task():
            # Stop listening with wait_for_stop=True to ensure clean shutdown
            if self.soap_stop_listening_function:
                self.soap_stop_listening_function(True)

            # Wait a small additional time to ensure processing completes
            time.sleep(0.5)

            # Update UI on main thread
            self.after(0, lambda: [
                self._cancel_soap_recording_finalize()
            ])

        # Run the cancellation process in a separate thread to avoid freezing the UI
        threading.Thread(target=cancel_task, daemon=True).start()

        # Update status immediately
        self.update_status("Cancelling SOAP recording...", "info")
        # Disable main record button during cancellation
        main_record_btn = self.ui.components.get('main_record_button')
        if main_record_btn:
            main_record_btn.config(state=tk.DISABLED)

    def _cancel_soap_recording_finalize(self) -> None:
        """Finalize the cancellation of SOAP recording."""
        # Stop periodic analysis if running
        self._stop_periodic_analysis()

        # Clear content except context when cancelling
        clear_content_except_context(self)

        # Reset state variables
        self.soap_recording = False

        # Reset UI buttons
        self._update_recording_ui_state(recording=False, caller="cancel_finalize")

        # Update status
        self.status_manager.warning("SOAP note recording cancelled.")

    def play_recording_sound(self, start: bool = True) -> None:
        """Play a sound to indicate recording start/stop."""
        # Sound disabled - just log the event
        logger.debug(f"Recording {'started' if start else 'stopped'}")


__all__ = ["AppRecordingMixin"]
