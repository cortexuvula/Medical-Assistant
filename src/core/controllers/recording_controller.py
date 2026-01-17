"""
Recording Controller Module (Consolidated)

This module consolidates recording-related controllers:
- Recording operations (start/stop, pause/resume, cancellation)
- Periodic analysis during recording (differential diagnosis)
- Recording recovery and auto-save

This is the single source of truth for all recording state and operations.
The actual logic is delegated to specialized handlers for better separation of concerns.

Migration Guide:
    # Old imports (deprecated)
    from core.recording_controller import RecordingController
    from core.periodic_analysis_controller import PeriodicAnalysisController
    from core.recording_recovery_controller import RecordingRecoveryController

    # New import
    from core.controllers.recording_controller import RecordingController
"""

import threading
import tkinter as tk
from tkinter import messagebox
from typing import Optional, Callable, Any, Dict, List, TYPE_CHECKING

from core.handlers.recovery_handler import RecoveryHandler
from core.handlers.pause_resume_handler import PauseResumeHandler
from core.handlers.periodic_analysis_handler import PeriodicAnalysisHandler
from core.handlers.finalization_handler import FinalizationHandler
from utils.structured_logging import get_logger

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = get_logger(__name__)


class RecordingController:
    """Consolidated controller for recording operations, periodic analysis, and recovery.

    This class coordinates:
    - SOAP recording start/stop, pause/resume, and cancellation
    - Audio callback handling
    - Periodic analysis during recording (differential diagnosis)
    - Recording auto-save and crash recovery
    - Post-recording processing coordination

    The actual logic is delegated to specialized handlers:
    - RecoveryHandler: Crash recovery and auto-save
    - PauseResumeHandler: Pause/resume state machine
    - PeriodicAnalysisHandler: Real-time analysis during recording
    - FinalizationHandler: Post-recording cleanup and queuing

    Thread Safety:
        All recording state changes are protected by _state_lock to prevent race conditions.
        The recording_manager.is_recording property is the single source of truth
        for recording state.
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the recording controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

        # ========================================
        # Shared State
        # ========================================
        self._state_lock = threading.Lock()
        self._soap_stop_listening_function: Optional[Callable] = None

        # ========================================
        # Initialize Handlers
        # ========================================
        self._recovery_handler = RecoveryHandler(app)
        self._pause_resume_handler = PauseResumeHandler(app, self._state_lock)
        self._periodic_analysis_handler = PeriodicAnalysisHandler(app)
        self._finalization_handler = FinalizationHandler(app)

    # ========================================
    # Recording Properties
    # ========================================

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

    # ========================================
    # Handler Properties (for backward compatibility)
    # ========================================

    @property
    def patient_context(self) -> str:
        """Get patient context from periodic analysis handler."""
        return self._periodic_analysis_handler.patient_context

    @patient_context.setter
    def patient_context(self, value: str) -> None:
        """Set patient context in periodic analysis handler."""
        self._periodic_analysis_handler.patient_context = value

    @property
    def differential_tracker(self):
        """Get differential tracker from periodic analysis handler."""
        return self._periodic_analysis_handler.differential_tracker

    @property
    def autosave_manager(self):
        """Get autosave manager from recovery handler."""
        return self._recovery_handler.autosave_manager

    # ========================================
    # Recording Operations
    # ========================================

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
        from ui.components.shared_panel_manager import SharedPanelManager

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
            # Sync with pause/resume handler
            self._pause_resume_handler.set_stop_function(self._soap_stop_listening_function)

            logger.info("SOAP recording started successfully")

            # Start recording auto-save for crash recovery
            patient_context = self.app.context_text.get("1.0", "end-1c").strip() if hasattr(self.app, 'context_text') else ""
            self.start_autosave({
                "patient_context": patient_context,
                "device_name": selected_device
            })

            # Clear and initialize analysis display
            self._periodic_analysis_handler.initialize_analysis_display()

            # Start periodic analysis if enabled
            if hasattr(self.app.ui, 'advanced_analysis_var') and self.app.ui.advanced_analysis_var.get():
                self.start_periodic_analysis()
                # Expand the bottom section if it's collapsed
                if hasattr(self.app, '_bottom_collapsed') and self.app._bottom_collapsed:
                    if hasattr(self.app, '_toggle_bottom_section'):
                        self.app._toggle_bottom_section()
                # Show the analysis panel in the shared panel area
                if hasattr(self.app.ui, 'shared_panel_manager') and self.app.ui.shared_panel_manager:
                    self.app.ui.shared_panel_manager.show_panel(SharedPanelManager.PANEL_ANALYSIS)
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
            self._pause_resume_handler.clear_stop_function()

        # Stop periodic analysis if running
        self.stop_periodic_analysis()

        # Reset audio handler settings
        self.app.audio_handler.soap_mode = False
        self.app.audio_handler.silence_threshold = 0.001

        # Stop recording auto-save (completed successfully)
        self.stop_autosave(completed_successfully=True)

        # Stop and get recording data - recording_manager handles state transition
        recording_data = self.app.recording_manager.stop_recording()
        if recording_data:
            self.app.play_recording_sound(start=False)
            self._finalization_handler.finalize_recording(recording_data)
        else:
            self.app.status_manager.error("No recording data available")
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="recording_controller_stop_no_data"
            )

    # ========================================
    # Pause/Resume Operations (delegated)
    # ========================================

    def toggle_pause(self) -> None:
        """Toggle pause state for SOAP recording."""
        self._pause_resume_handler.toggle_pause()
        # Sync stop function state
        self._soap_stop_listening_function = self._pause_resume_handler.get_stop_function()

    def pause(self) -> None:
        """Pause the current SOAP recording."""
        self._pause_resume_handler.pause()
        self._soap_stop_listening_function = self._pause_resume_handler.get_stop_function()

    def resume(self) -> None:
        """Resume SOAP recording after pause."""
        self._pause_resume_handler.resume()
        self._soap_stop_listening_function = self._pause_resume_handler.get_stop_function()

    def on_advanced_analysis_toggled(self, enabled: bool) -> None:
        """Handle advanced analysis checkbox toggle during recording."""
        self._pause_resume_handler.on_advanced_analysis_toggled(enabled)

    # ========================================
    # Cancel Operation
    # ========================================

    def cancel(self) -> None:
        """Cancel the current SOAP recording without processing.

        Thread-safe: Uses lock to prevent race conditions during state transitions.
        """
        # Check state before showing dialog (don't hold lock during dialog)
        if not (self.is_recording or self.is_paused):
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
        """
        try:
            # Stop the background listening
            if self._soap_stop_listening_function:
                self._soap_stop_listening_function()
                self._soap_stop_listening_function = None
                self._pause_resume_handler.clear_stop_function()

            # Stop periodic analysis if running
            self.stop_periodic_analysis()

            # Reset audio handler settings
            self.app.audio_handler.soap_mode = False
            self.app.audio_handler.silence_threshold = 0.001

            # Stop recording auto-save (not completed - cancelled)
            self.stop_autosave(completed_successfully=False)

            # Cancel the recording in RecordingManager
            self.app.recording_manager.cancel_recording()

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
            self.app.ui_state_manager.set_recording_state(
                recording=False, caller="cancel_error"
            )

    # ========================================
    # Recording Callbacks
    # ========================================

    def _soap_callback(self, audio_data: Any) -> None:
        """Callback for SOAP note recording."""
        self._finalization_handler.soap_callback(audio_data)

    # ========================================
    # Periodic Analysis Operations (delegated)
    # ========================================

    def set_recording_id(self, recording_id: Optional[int]) -> None:
        """Set the current recording ID for linking periodic analyses."""
        self._periodic_analysis_handler.set_recording_id(recording_id)

    def get_last_session_id(self) -> Optional[int]:
        """Get the last saved periodic analysis session ID."""
        return self._periodic_analysis_handler.get_last_session_id()

    def start_periodic_analysis(self) -> None:
        """Start periodic analysis during recording."""
        self._periodic_analysis_handler.start_periodic_analysis()

    def stop_periodic_analysis(self, save_to_database: bool = True) -> Optional[int]:
        """Stop periodic analysis and optionally save history to database."""
        return self._periodic_analysis_handler.stop_periodic_analysis(save_to_database)

    def perform_periodic_analysis(self, analysis_count: int, elapsed_time: float) -> None:
        """Perform periodic analysis callback."""
        self._periodic_analysis_handler.perform_periodic_analysis(analysis_count, elapsed_time)

    def update_analysis_display(self, analysis_text: str) -> None:
        """Update the analysis display in the UI."""
        self._periodic_analysis_handler.update_analysis_display(analysis_text)

    def clear_advanced_analysis_text(self) -> None:
        """Clear the Advanced Analysis Results text area."""
        self._periodic_analysis_handler.clear_advanced_analysis_text()

    def get_analysis_history(self) -> dict:
        """Get the analysis history summary."""
        return self._periodic_analysis_handler.get_analysis_history()

    def get_combined_analysis_text(self) -> str:
        """Get all analysis results combined as text."""
        return self._periodic_analysis_handler.get_combined_analysis_text()

    def get_periodic_session(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Retrieve a saved periodic analysis session."""
        return self._periodic_analysis_handler.get_periodic_session(session_id)

    def get_linked_periodic_analyses(self, recording_id: int) -> List[Dict[str, Any]]:
        """Get all periodic analyses linked to a recording."""
        return self._periodic_analysis_handler.get_linked_periodic_analyses(recording_id)

    # ========================================
    # Recovery Operations (delegated)
    # ========================================

    def check_for_incomplete_recording(self) -> None:
        """Check for incomplete recording on startup."""
        self._recovery_handler.check_for_incomplete_recording()

    def discard_recovery(self) -> None:
        """User declined recovery - clean up files."""
        self._recovery_handler.discard_recovery()

    def start_autosave(self, metadata: Optional[dict] = None) -> None:
        """Start auto-save for a new recording."""
        self._recovery_handler.start_autosave(metadata)

    def stop_autosave(self, completed_successfully: bool = False) -> None:
        """Stop auto-save for current recording."""
        self._recovery_handler.stop_autosave(completed_successfully)

    def is_autosave_running(self) -> bool:
        """Check if auto-save is currently active."""
        return self._recovery_handler.is_autosave_running()

    # ========================================
    # Cleanup
    # ========================================

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
                self._pause_resume_handler.clear_stop_function()

            # Stop recording auto-save if running (mark as incomplete for potential recovery)
            try:
                self.stop_autosave(completed_successfully=False)
            except Exception as e:
                logger.warning(f"Error stopping recording auto-save during cleanup: {e}")


# ========================================
# Backward Compatibility Aliases
# ========================================

# These aliases allow old code to work with the consolidated controller
PeriodicAnalysisController = RecordingController
RecordingRecoveryController = RecordingController
