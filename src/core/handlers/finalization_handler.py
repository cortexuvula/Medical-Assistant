"""
Finalization Handler

Provides post-recording cleanup and processing coordination.
Extracted from RecordingController for better separation of concerns.
"""

import logging
from typing import TYPE_CHECKING, Dict, Any

from settings import settings_manager

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class FinalizationHandler:
    """Handles post-recording finalization and processing.

    This handler manages:
    - Recording completion processing
    - Quick continue mode vs immediate processing
    - Recording data validation
    - Post-recording event generation
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the finalization handler.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    # ========================================
    # Finalization
    # ========================================

    def finalize_recording(self, recording_data: Dict[str, Any]) -> None:
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
        if settings_manager.get_quick_continue_mode():
            # Queue for background processing
            self.app._queue_recording_for_processing(recording_data)
            # Reset UI immediately
            self.app._reset_ui_for_next_patient()
            self.app.status_manager.info("Recording queued - Ready for next patient")
        else:
            # Process immediately
            self.app.process_soap_recording()
            self.app.after(0, lambda: self.app.ui_state_manager.set_recording_state(
                recording=False, caller="finalize_delayed"
            ))

        # Trigger recording complete event for auto-save
        self.app.event_generate("<<RecordingComplete>>", when="tail")

    # ========================================
    # Callback
    # ========================================

    def soap_callback(self, audio_data: Any) -> None:
        """Callback for SOAP note recording.

        Args:
            audio_data: Audio data from the recording
        """
        self.app.soap_audio_processor.process_soap_callback(audio_data)


__all__ = ["FinalizationHandler"]
