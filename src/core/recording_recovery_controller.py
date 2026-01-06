"""
Recording Recovery Controller Module

Handles startup check for incomplete recordings and the recovery process.
This controller manages the RecordingAutoSaveManager and coordinates
with the UI to prompt users about recovering incomplete recordings.
"""

import logging
from typing import TYPE_CHECKING, Optional

from audio.recording_autosave_manager import RecordingAutoSaveManager
from pydub import AudioSegment

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class RecordingRecoveryController:
    """Controller for managing recording auto-save and recovery.

    This class coordinates:
    - Recording auto-save initialization
    - Startup check for incomplete recordings
    - Recovery dialog presentation
    - Audio recovery and processing
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the recording recovery controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app
        self.autosave_manager = RecordingAutoSaveManager()
        self._recovery_pending = False

    def check_for_incomplete_recording(self) -> None:
        """Check for incomplete recording on startup.

        This should be called after the UI is fully initialized.
        Uses app.after() to show dialog after a short delay.
        """
        try:
            if self.autosave_manager.has_incomplete_recording():
                # Schedule dialog to show after UI is ready
                self.app.after(500, self._show_recovery_dialog)
                logger.info("Found incomplete recording - will prompt for recovery")
            else:
                logger.debug("No incomplete recording found")
        except Exception as e:
            logger.error(f"Error checking for incomplete recording: {e}")

    def _show_recovery_dialog(self) -> None:
        """Show the recovery prompt dialog."""
        try:
            recovery_info = self.autosave_manager.get_recovery_info()
            if not recovery_info:
                logger.warning("Recovery info not available")
                return

            # Import dialog here to avoid circular imports
            from ui.dialogs.recording_recovery_dialog import show_recording_recovery_dialog

            result = show_recording_recovery_dialog(self.app, recovery_info)

            if result:
                # User wants to recover
                self._perform_recovery(recovery_info)
            else:
                # User declined - clean up files
                self.discard_recovery()

        except ImportError as e:
            logger.error(f"Could not import recovery dialog: {e}")
            # Fall back to simple messagebox
            self._show_fallback_dialog()
        except Exception as e:
            logger.error(f"Error showing recovery dialog: {e}", exc_info=True)

    def _show_fallback_dialog(self) -> None:
        """Show a simple fallback dialog if the custom dialog fails."""
        from tkinter import messagebox

        recovery_info = self.autosave_manager.get_recovery_info()
        if not recovery_info:
            return

        duration = recovery_info.get("estimated_duration_seconds", 0)
        duration_str = f"{duration / 60:.1f} minutes" if duration >= 60 else f"{duration:.0f} seconds"

        result = messagebox.askyesno(
            "Recover Incomplete Recording?",
            f"An incomplete recording was found:\n\n"
            f"Duration: ~{duration_str}\n"
            f"Last saved: {recovery_info.get('last_save_time', 'Unknown')}\n\n"
            f"Would you like to recover this recording?",
            parent=self.app
        )

        if result:
            self._perform_recovery(recovery_info)
        else:
            self.discard_recovery()

    def _perform_recovery(self, recovery_info: dict) -> None:
        """Perform the actual recovery of audio.

        Args:
            recovery_info: Dictionary with recovery session info
        """
        try:
            # Recover the audio
            recovered_audio = self.autosave_manager.recover_recording()

            if recovered_audio is None:
                if hasattr(self.app, 'status_manager'):
                    self.app.status_manager.error("Failed to recover recording - no audio data")
                return

            # Process the recovered audio
            self._process_recovered_audio(recovered_audio, recovery_info)

            # Clean up recovery files after successful recovery
            self.autosave_manager.cleanup_recovery_files()

            if hasattr(self.app, 'status_manager'):
                duration = len(recovered_audio) / 1000.0
                self.app.status_manager.success(f"Recovered {duration:.1f} seconds of audio")

        except Exception as e:
            logger.error(f"Error during recovery: {e}", exc_info=True)
            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.error(f"Recovery failed: {str(e)}")

    def _process_recovered_audio(self, audio: AudioSegment, recovery_info: dict) -> None:
        """Process recovered audio through the normal transcription pipeline.

        Args:
            audio: Recovered AudioSegment
            recovery_info: Recovery session metadata
        """
        try:
            # Restore patient context if available
            patient_context = recovery_info.get("patient_context", "")
            if patient_context and hasattr(self.app, 'context_text'):
                self.app.context_text.delete("1.0", "end")
                self.app.context_text.insert("1.0", patient_context)

            # Use the SOAP processor to handle the recovered audio
            if hasattr(self.app, 'soap_processor'):
                # Queue the audio for processing
                self.app.soap_processor.process_recovered_audio(audio)
            else:
                # Fallback: save audio and transcribe directly
                self._fallback_process_audio(audio)

        except Exception as e:
            logger.error(f"Error processing recovered audio: {e}", exc_info=True)
            raise

    def _fallback_process_audio(self, audio: AudioSegment) -> None:
        """Fallback method to process audio if soap_processor is not available.

        Args:
            audio: AudioSegment to process
        """
        try:
            import os
            from datetime import datetime
            from settings.settings import SETTINGS

            # Save audio to file
            storage_folder = SETTINGS.get("storage_folder", "")
            if not storage_folder:
                storage_folder = os.path.expanduser("~/Documents/Medical-Dictation/Storage")
                os.makedirs(storage_folder, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"recovered_recording_{timestamp}.mp3"
            filepath = os.path.join(storage_folder, filename)

            # Export audio
            audio.export(filepath, format="mp3")
            logger.info(f"Saved recovered audio to: {filepath}")

            # Attempt transcription
            if hasattr(self.app, 'audio_handler') and hasattr(self.app.audio_handler, 'transcribe_audio'):
                transcript = self.app.audio_handler.transcribe_audio(audio)

                if transcript and hasattr(self.app, 'transcript_text'):
                    self.app.transcript_text.delete("1.0", "end")
                    self.app.transcript_text.insert("1.0", transcript)

                    if hasattr(self.app, 'status_manager'):
                        self.app.status_manager.success("Recording recovered and transcribed")

        except Exception as e:
            logger.error(f"Fallback processing failed: {e}")
            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.error("Failed to process recovered audio")

    def discard_recovery(self) -> None:
        """User declined recovery - clean up files."""
        try:
            self.autosave_manager.cleanup_recovery_files()
            logger.info("User declined recovery - files cleaned up")

            if hasattr(self.app, 'status_manager'):
                self.app.status_manager.info("Incomplete recording discarded")

        except Exception as e:
            logger.error(f"Error cleaning up recovery files: {e}")

    def start_autosave(self, metadata: Optional[dict] = None) -> None:
        """Start auto-save for a new recording.

        Called by RecordingController when recording starts.

        Args:
            metadata: Optional recording metadata
        """
        if hasattr(self.app, 'audio_state_manager'):
            self.autosave_manager.start(self.app.audio_state_manager, metadata)

    def stop_autosave(self, completed_successfully: bool = False) -> None:
        """Stop auto-save for current recording.

        Called by RecordingController when recording stops or is cancelled.

        Args:
            completed_successfully: True if recording completed normally
        """
        self.autosave_manager.stop(completed_successfully=completed_successfully)

    def is_autosave_running(self) -> bool:
        """Check if auto-save is currently active."""
        return self.autosave_manager.is_running
