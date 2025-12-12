"""
Queue Processing Controller Module

Handles recording queue management, background processing, and quick continue mode
functionality.

This controller extracts queue processing logic from the main App class
to improve maintainability and separation of concerns.
"""

import logging
import tkinter as tk
from datetime import datetime
from typing import TYPE_CHECKING, Optional, List

from settings.settings import SETTINGS, save_settings

if TYPE_CHECKING:
    from core.app import MedicalDictationApp

logger = logging.getLogger(__name__)


class QueueProcessingController:
    """Controller for managing recording queue processing.

    This class coordinates:
    - Queueing recordings for background processing
    - UI reset for next patient
    - Patient name extraction from context
    - Quick continue mode toggling
    - Reprocessing failed recordings
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the queue processing controller.

        Args:
            app: Reference to the main application instance
        """
        self.app = app

    def queue_recording_for_processing(self, recording_data: dict) -> None:
        """Queue recording for background processing.

        Args:
            recording_data: Dictionary containing audio and metadata
        """
        try:
            logging.info("DEBUG: queue_recording_for_processing started")
            # Get patient name - try to extract from context or use default
            logging.info("DEBUG: Getting context text")
            context_text = self.app.context_text.get("1.0", tk.END).strip()
            logging.info("DEBUG: Extracting patient name")
            patient_name = self.extract_patient_name(context_text) or "Patient"

            logging.info("DEBUG: Adding recording to database")
            # Save to database with 'pending' status
            recording_id = self.app.db.add_recording(
                filename=f"queued_{datetime.now().strftime('%Y%m%d_%H%M%S')}.mp3",
                processing_status='pending',
                patient_name=patient_name
            )
            logging.info(f"DEBUG: Database add_recording returned ID: {recording_id}")

            # Get audio data from recording_data if available, otherwise use chunks
            audio_to_process = None
            if recording_data and recording_data.get('audio'):
                audio_to_process = recording_data['audio']
            elif self.app.combined_soap_chunks:
                audio_to_process = self.app.combined_soap_chunks
            else:
                raise ValueError("No audio data available for processing")

            # Prepare task data
            logging.info("DEBUG: Preparing task data")
            task_data = {
                'recording_id': recording_id,
                'audio_data': audio_to_process,
                'patient_name': patient_name,
                'context': context_text,
                'process_options': {
                    'generate_soap': True,
                    'generate_referral': False,
                    'generate_letter': False
                }
            }

            # Add to processing queue
            logging.info("DEBUG: About to call processing_queue.add_recording")
            task_id = self.app.processing_queue.add_recording(task_data)
            logging.info(f"DEBUG: processing_queue.add_recording returned task_id: {task_id}")

            # Update status
            logging.info("DEBUG: About to call status_manager.info")
            self.app.status_manager.info(f"Recording for {patient_name} added to queue")
            logging.info("DEBUG: status_manager.info completed")

            logging.info(f"Queued recording {recording_id} as task {task_id}")

        except Exception as e:
            logging.error(f"Failed to queue recording: {str(e)}", exc_info=True)
            self.app.status_manager.error("Failed to queue recording for processing")
            # Fall back to immediate processing
            self.app.process_soap_recording()

    def reset_ui_for_next_patient(self) -> None:
        """Reset UI for next patient recording."""
        # DON'T clear content here - preserve context and previous recording data
        # Content will only be cleared when starting a new recording

        # Reset recording state
        self.app.soap_recording = False

        # Reset UI buttons
        self.app._update_recording_ui_state(recording=False, caller="reset_for_next")

        # Focus on transcript tab
        self.app.notebook.select(0)

        # Update status
        self.app.status_manager.success("Ready for next patient")

    def extract_patient_name(self, context_text: str) -> Optional[str]:
        """Try to extract patient name from context.

        Args:
            context_text: The context text to parse

        Returns:
            The extracted patient name or None
        """
        # Simple extraction - look for "Patient:" or "Name:" in context
        lines = context_text.split('\n')
        for line in lines:
            if line.startswith(('Patient:', 'Name:', 'Patient Name:')):
                name = line.split(':', 1)[1].strip()
                if name:
                    return name
        return None

    def toggle_quick_continue_mode(self) -> None:
        """Toggle the quick continue mode setting."""
        new_value = self.app.quick_continue_var.get()
        SETTINGS["quick_continue_mode"] = new_value
        save_settings(SETTINGS)

        # Update status
        if new_value:
            self.app.status_manager.success("Quick Continue Mode enabled - recordings will process in background")
        else:
            self.app.status_manager.info("Quick Continue Mode disabled - recordings will process immediately")

        logging.info(f"Quick Continue Mode set to: {new_value}")

    def reprocess_failed_recordings(self, recording_ids: List[int]) -> None:
        """Reprocess failed recordings by re-adding them to the queue.

        Args:
            recording_ids: List of recording IDs to reprocess
        """
        try:
            if not hasattr(self.app, 'processing_queue') or not self.app.processing_queue:
                self.app.status_manager.error("Processing queue not available")
                return

            # Reprocess each recording
            success_count = 0
            failed_count = 0

            for rec_id in recording_ids:
                task_id = self.app.processing_queue.reprocess_failed_recording(rec_id)
                if task_id:
                    success_count += 1
                    logging.info(f"Recording {rec_id} queued for reprocessing as task {task_id}")
                else:
                    failed_count += 1
                    logging.error(f"Failed to reprocess recording {rec_id}")

            # Show status
            if success_count > 0:
                self.app.status_manager.success(
                    f"Queued {success_count} recording{'s' if success_count > 1 else ''} for reprocessing"
                )

            if failed_count > 0:
                self.app.status_manager.warning(
                    f"Failed to reprocess {failed_count} recording{'s' if failed_count > 1 else ''}"
                )

        except Exception as e:
            logging.error(f"Error reprocessing recordings: {str(e)}", exc_info=True)
            self.app.status_manager.error(f"Failed to reprocess recordings: {str(e)}")
