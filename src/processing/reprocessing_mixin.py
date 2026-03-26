"""
Reprocessing Mixin for ProcessingQueue.

Handles reprocessing operations including:
- Reprocessing failed recordings
- Retry logic with exponential backoff
- Multiple recording reprocessing

This mixin is designed to be used with ProcessingQueue to keep the main
class focused on core queue operations.
"""

import json
import os
import time
import threading
from typing import Any, Dict, Optional, List

from settings.settings_manager import settings_manager
from utils.error_handling import ErrorContext
from utils.exceptions import DatabaseError
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ReprocessingMixin:
    """Mixin providing reprocessing capabilities for ProcessingQueue."""

    @staticmethod
    def _extract_context_from_metadata(metadata: Any) -> str:
        """Extract context from recording metadata, handling both dict and JSON string."""
        if not metadata:
            return ""
        if isinstance(metadata, str):
            try:
                metadata = json.loads(metadata)
            except (json.JSONDecodeError, TypeError):
                return ""
        if isinstance(metadata, dict):
            return metadata.get("context", "")
        return ""

    def reprocess_failed_recording(self, recording_id: int) -> Optional[str]:
        """Reprocess a failed recording by re-adding it to the queue.

        Args:
            recording_id: ID of the failed recording to reprocess

        Returns:
            Task ID if successfully queued, None if failed
        """
        try:
            # Get recording from database
            if not self.app or not hasattr(self.app, 'db'):
                logger.error("No app context available for reprocessing", recording_id=recording_id)
                return None

            recording = self.app.db.get_recording(recording_id)
            if not recording:
                logger.error("Recording not found", recording_id=recording_id)
                return None

            # Check if it's actually failed
            if recording.get('processing_status') != 'failed':
                logger.warning(
                    "Recording is not in failed status",
                    recording_id=recording_id,
                    current_status=recording.get('processing_status')
                )
                return None

            # Load audio from file if available
            audio_path = recording.get('audio_path')
            audio_data = None

            if audio_path and os.path.exists(audio_path):
                # Validate file size before loading into memory
                from audio.audio import AudioHandler
                is_valid, size_mb, max_mb = AudioHandler.validate_audio_file_size(audio_path)
                if not is_valid:
                    logger.warning(
                        "Audio file too large for reprocessing, using existing transcript",
                        audio_path=audio_path,
                        size_mb=size_mb,
                        max_mb=max_mb,
                        recording_id=recording_id,
                    )
                else:
                    try:
                        from pydub import AudioSegment
                        audio_data = AudioSegment.from_mp3(audio_path)
                        logger.info("Loaded audio for reprocessing", audio_path=audio_path, recording_id=recording_id)
                    except Exception as e:
                        logger.error(
                            "Failed to load audio for reprocessing",
                            audio_path=audio_path,
                            recording_id=recording_id,
                            error=str(e)
                        )
                        # Continue without audio - transcript might be available

            # Reset processing fields
            self.app.db.update_recording(
                recording_id,
                processing_status='pending',
                error_message=None,
                retry_count=0,
                processing_started_at=None,
                processing_completed_at=None
            )

            # Prepare task data
            task_data = {
                'recording_id': recording_id,
                'audio_data': audio_data,
                'transcript': recording.get('transcript', ''),  # Use existing transcript if available
                'patient_name': recording.get('patient_name', 'Patient'),
                'context': recording.get('metadata', {}).get('context', '') if isinstance(recording.get('metadata'), dict) else '',
                'process_options': {
                    'generate_soap': not bool(recording.get('soap_note')),
                    'generate_referral': not bool(recording.get('referral')),
                    'generate_letter': not bool(recording.get('letter'))
                },
                'is_reprocess': True,
                'priority': 3  # Higher priority for manual reprocess
            }

            # Add to queue
            task_id = self.add_recording(task_data)

            logger.info("Recording queued for reprocessing", recording_id=recording_id, task_id=task_id)
            return task_id

        except DatabaseError as e:
            ctx = ErrorContext.capture(
                operation="Reprocess failed recording",
                exception=e,
                error_code="REPROCESS_DB_ERROR",
                recording_id=recording_id
            )
            ctx.log()
            return None
        except (OSError, IOError) as e:
            ctx = ErrorContext.capture(
                operation="Load audio for reprocessing",
                exception=e,
                error_code="REPROCESS_FILE_ERROR",
                recording_id=recording_id,
                audio_path=audio_path if 'audio_path' in locals() else None
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Reprocess failed recording",
                exception=e,
                error_code="REPROCESS_UNEXPECTED_ERROR",
                recording_id=recording_id
            )
            ctx.log()
            return None

    def reprocess_multiple_failed_recordings(self, recording_ids: List[int]) -> Dict[int, Optional[str]]:
        """Reprocess multiple failed recordings.

        Args:
            recording_ids: List of recording IDs to reprocess

        Returns:
            Dictionary mapping recording_id to task_id (or None if failed)
        """
        results = {}
        for recording_id in recording_ids:
            task_id = self.reprocess_failed_recording(recording_id)
            results[recording_id] = task_id
        return results

    def _should_retry(self, recording_data: Dict) -> bool:
        """Check if a task should be retried.

        Args:
            recording_data: The recording data dict

        Returns:
            True if retry should be attempted
        """
        if not settings_manager.get("auto_retry_failed", True):
            return False

        max_retries = settings_manager.get("max_retry_attempts", 3)
        return recording_data.get("retry_count", 0) < max_retries

    def _retry_task(self, task_id: str, recording_data: Dict, error_msg: str):
        """Retry a failed task with exponential backoff.

        Args:
            task_id: The task identifier
            recording_data: The recording data dict
            error_msg: The error message from the failure
        """
        retry_count = recording_data.get("retry_count", 0) + 1
        recording_data["retry_count"] = retry_count
        recording_data["last_error"] = error_msg

        # Calculate backoff delay - faster recovery for better UX
        # 0.5s, 1s, 2s, 4s... up to 30s (instead of 2s, 4s, 8s... up to 5 min)
        delay = min(30, 0.5 * (2 ** retry_count))

        with self.lock:
            self.stats["total_retried"] += 1

        logger.info("Retrying task", task_id=task_id, attempt=retry_count, delay_seconds=delay)

        # Schedule retry
        def delayed_retry():
            time.sleep(delay)
            if not self.shutdown_event.is_set():
                self.queue.put((recording_data["priority"] - 1, task_id, recording_data))

        threading.Thread(target=delayed_retry, daemon=True).start()
