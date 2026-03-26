"""
Task Executor Mixin for ProcessingQueue.

Handles the main recording processing logic including:
- Audio saving and transcription
- SOAP note, referral, and letter generation
- Error handling with retry support

This mixin is designed to be used with ProcessingQueue to keep the main
class focused on core queue operations.
"""

import uuid
import time
from typing import Dict, Any
from datetime import datetime

from settings.settings_manager import settings_manager
from utils.error_handling import ErrorContext
from utils.exceptions import (
    MedicalAssistantError,
    TranscriptionError,
    DocumentGenerationError,
    APIError,
    APITimeoutError,
)
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class TaskExecutorMixin:
    """Mixin providing task execution capabilities for ProcessingQueue."""

    def _process_recording(self, task_id: str, recording_data: Dict[str, Any]):
        """Process a single recording or guideline - runs in thread pool."""
        # Check if this is a guideline upload task
        task_type = recording_data.get("task_type", "recording")

        if task_type == "guideline_upload":
            return self._process_guideline_upload(task_id, recording_data)

        # Normal recording processing
        start_time = time.time()
        recording_id = recording_data.get("recording_id")

        try:
            logger.info("Starting processing for task", task_id=task_id, recording_id=recording_id)

            # Update status
            recording_data["status"] = "processing"
            recording_data["started_at"] = datetime.now()
            with self.lock:
                active_count = len(self.active_tasks)
            self._notify_status_update(task_id, "processing", active_count)

            # Update database status
            if self.app and hasattr(self.app, 'db'):
                self.app.db.update_recording(
                    recording_id,
                    processing_status="processing",
                    processing_started_at=datetime.now()
                )

            # Get the processing function from the app
            if self.app:
                # Process based on options
                process_options = recording_data.get("process_options", {})
                results = {}

                # First, check if we need to transcribe audio
                transcript = recording_data.get("transcript", "")
                if not transcript and recording_data.get("audio_data"):
                    # Transcribe the audio
                    transcript = self._transcribe_audio(task_id, recording_id, recording_data)

                else:
                    if transcript:
                        logger.info(
                            "Using existing transcript",
                            recording_id=recording_id,
                            transcript_length=len(transcript)
                        )
                    else:
                        logger.warning("No transcript or audio data", recording_id=recording_id)

                # Generate SOAP note if requested
                if process_options.get("generate_soap", True):
                    if transcript:
                        logger.info("Generating SOAP note", recording_id=recording_id)
                        # Get context from recording_data (passed from UI)
                        context = recording_data.get("context", "")
                        if context:
                            logger.info("Including context in SOAP generation", context_length=len(context))
                        soap_result = self._generate_soap_note(transcript, context)
                        if soap_result:
                            results["soap_note"] = soap_result
                            # Update database
                            self.app.db.update_recording(recording_id, soap_note=soap_result)
                            logger.info(
                                "SOAP note generated",
                                recording_id=recording_id,
                                soap_note_length=len(soap_result)
                            )
                        else:
                            logger.warning("SOAP generation returned empty result", recording_id=recording_id)
                    else:
                        logger.warning("No transcript available for SOAP generation", recording_id=recording_id)

                # Generate referral if requested
                if process_options.get("generate_referral") and results.get("soap_note"):
                    referral_result = self._generate_referral(results["soap_note"])
                    if referral_result:
                        results["referral"] = referral_result
                        # Update database
                        self.app.db.update_recording(recording_id, referral=referral_result)

                # Generate letter if requested
                if process_options.get("generate_letter"):
                    content = results.get("soap_note") or recording_data.get("transcript", "")
                    if content:
                        letter_result = self._generate_letter(content)
                        if letter_result:
                            results["letter"] = letter_result
                            # Update database
                            self.app.db.update_recording(recording_id, letter=letter_result)

                # Log final results
                logger.info(
                    "Processing results for recording",
                    recording_id=recording_id,
                    generated_documents=list(results.keys())
                )

                # Format results for callback with expected structure
                callback_result = {
                    'success': True,
                    'transcript': recording_data.get("transcript", ""),
                    'soap_note': results.get("soap_note", ""),
                    'referral': results.get("referral", ""),
                    'letter': results.get("letter", ""),
                    'completed_at': datetime.now()
                }

                # Mark as completed
                self._mark_completed(task_id, recording_data, callback_result, time.time() - start_time)

            else:
                logger.error("No app context available for processing", task_id=task_id)
                raise Exception("No app context available")

        except TranscriptionError as e:
            # Transcription-specific failure
            ctx = ErrorContext.capture(
                operation="Transcribe audio",
                exception=e,
                error_code="TRANSCRIPTION_FAILED",
                task_id=task_id,
                recording_id=recording_id
            )
            ctx.log()
            if self._should_retry(recording_data):
                self._retry_task(task_id, recording_data, ctx.user_message)
            else:
                self._mark_failed(task_id, recording_data, ctx.user_message)
        except DocumentGenerationError as e:
            # Document generation failure (SOAP, referral, letter)
            ctx = ErrorContext.capture(
                operation="Generate documents",
                exception=e,
                error_code="DOCUMENT_GENERATION_FAILED",
                task_id=task_id,
                recording_id=recording_id
            )
            ctx.log()
            if self._should_retry(recording_data):
                self._retry_task(task_id, recording_data, ctx.user_message)
            else:
                self._mark_failed(task_id, recording_data, ctx.user_message)
        except (APIError, APITimeoutError) as e:
            # API errors (retryable)
            ctx = ErrorContext.capture(
                operation="API call during processing",
                exception=e,
                error_code=getattr(e, 'error_code', 'API_ERROR'),
                task_id=task_id,
                recording_id=recording_id,
                service=getattr(e, 'service', None)
            )
            ctx.log()
            if self._should_retry(recording_data):
                self._retry_task(task_id, recording_data, ctx.user_message)
            else:
                self._mark_failed(task_id, recording_data, ctx.user_message)
        except (ConnectionError, TimeoutError, OSError) as e:
            # Network/system errors (potentially retryable)
            ctx = ErrorContext.capture(
                operation="Network/system operation",
                exception=e,
                error_code="NETWORK_ERROR",
                task_id=task_id,
                recording_id=recording_id
            )
            ctx.log()
            if self._should_retry(recording_data):
                self._retry_task(task_id, recording_data, ctx.user_message)
            else:
                self._mark_failed(task_id, recording_data, ctx.user_message)
        except MedicalAssistantError as e:
            # Other application-specific errors
            ctx = ErrorContext.capture(
                operation="Processing recording",
                exception=e,
                error_code=getattr(e, 'error_code', 'PROCESSING_ERROR'),
                task_id=task_id,
                recording_id=recording_id
            )
            ctx.log()
            self._mark_failed(task_id, recording_data, ctx.user_message)
        except Exception as e:
            # Unexpected error - log full details and don't retry
            ctx = ErrorContext.capture(
                operation="Processing recording",
                exception=e,
                error_code="UNEXPECTED_PROCESSING_ERROR",
                task_id=task_id,
                recording_id=recording_id
            )
            ctx.log()
            logger.error(
                "Unexpected error processing task",
                task_id=task_id,
                exception_type=type(e).__name__,
                exc_info=True
            )
            self._mark_failed(task_id, recording_data, f"Unexpected error: {type(e).__name__}: {e}")

    def _transcribe_audio(self, task_id: str, recording_id: int, recording_data: Dict[str, Any]) -> str:
        """Transcribe audio data and save the audio file.

        Args:
            task_id: The task identifier
            recording_id: The recording database ID
            recording_data: The full recording data dict (modified in place with transcript)

        Returns:
            The transcript text

        Raises:
            TranscriptionError: If transcription fails
        """
        import os

        logger.info("Transcribing audio for recording", recording_id=recording_id)
        audio_data = recording_data.get("audio_data")

        # Save audio file before transcription
        audio_saved = False
        try:
            from datetime import datetime as dt

            # Get storage folder
            storage_folder = settings_manager.get("storage_folder")
            logger.debug("Storage folder from settings", storage_folder=storage_folder)

            if not storage_folder:
                storage_folder = settings_manager.get("default_storage_folder")
                logger.debug("Using default_storage_folder", storage_folder=storage_folder)

            if not storage_folder:
                storage_folder = settings_manager.get("default_folder")
                logger.debug("Using default_folder", storage_folder=storage_folder)

            if not storage_folder or not os.path.exists(storage_folder):
                logger.warning(
                    "Storage folder not found or not set, using default",
                    configured_folder=storage_folder
                )
                storage_folder = os.path.join(os.path.expanduser("~"), "Documents", "Medical-Dictation", "Storage")
                os.makedirs(storage_folder, exist_ok=True)
                logger.info("Created/using default storage folder", storage_folder=storage_folder)
            else:
                logger.debug("Using configured storage folder", storage_folder=storage_folder)

            # Create filename with patient name using secure approach
            patient_name = recording_data.get('patient_name', 'Patient')
            # Sanitize patient name - only allow safe characters
            safe_patient_name = "".join(c for c in patient_name if c.isalnum() or c in (' ', '-', '_')).rstrip()
            # Limit length to prevent path issues
            safe_patient_name = safe_patient_name[:50] if safe_patient_name else "Patient"
            date_formatted = dt.now().strftime("%d-%m-%y")
            time_formatted = dt.now().strftime("%H-%M-%S")
            # Add unique suffix to prevent collisions/TOCTOU attacks
            unique_suffix = uuid.uuid4().hex[:8]
            final_filename = f"recording_{safe_patient_name}_{date_formatted}_{time_formatted}_{unique_suffix}.mp3"
            audio_path = os.path.join(storage_folder, final_filename)

            # Save audio using audio handler
            logger.info("Attempting to save audio", audio_path=audio_path)
            if hasattr(self.app, 'audio_handler'):
                # Convert audio_data to list if needed
                audio_segments = [audio_data] if not isinstance(audio_data, list) else audio_data
                save_result = self.app.audio_handler.save_audio(audio_segments, audio_path)
                logger.debug("Audio save result", save_result=save_result, audio_path=audio_path)

                if save_result:
                    # Verify file was actually created
                    if os.path.exists(audio_path):
                        file_size = os.path.getsize(audio_path)
                        logger.info(
                            "Audio saved successfully",
                            audio_path=audio_path,
                            file_size_bytes=file_size
                        )
                        audio_saved = True
                    else:
                        logger.error(
                            "Audio save reported success but file not found",
                            audio_path=audio_path
                        )
                        audio_saved = False
                else:
                    logger.error("Failed to save audio", audio_path=audio_path)
                    audio_saved = False
        except (OSError, IOError) as e:
            # File system errors during audio save
            ctx = ErrorContext.capture(
                operation="Save audio file",
                exception=e,
                error_code="AUDIO_SAVE_IO_ERROR",
                audio_path=audio_path if 'audio_path' in locals() else None,
                storage_folder=storage_folder if 'storage_folder' in locals() else None
            )
            ctx.log()
            # Continue with transcription even if audio save fails
        except Exception as e:
            # Unexpected error - log with full context
            ctx = ErrorContext.capture(
                operation="Save audio file",
                exception=e,
                error_code="AUDIO_SAVE_UNEXPECTED",
                audio_path=audio_path if 'audio_path' in locals() else None
            )
            ctx.log()
            # Continue with transcription even if audio save fails

        # Track audio save status in recording data for downstream consumers
        recording_data["audio_saved"] = audio_saved

        # Log comprehensive audio data info for debugging
        if hasattr(audio_data, 'duration_seconds'):
            logger.debug("Audio duration", duration_seconds=audio_data.duration_seconds)
        # Log additional audio parameters to help diagnose truncation issues
        if hasattr(audio_data, 'frame_rate'):
            logger.debug(
                "Audio params before transcription",
                duration_ms=len(audio_data) if hasattr(audio_data, '__len__') else None,
                frame_rate=audio_data.frame_rate,
                channels=audio_data.channels,
                sample_width=audio_data.sample_width
            )

        # Use the app's audio handler to transcribe (with metadata for emotions)
        if hasattr(self.app, 'audio_handler'):
            try:
                result = self.app.audio_handler.transcribe_audio_with_metadata(audio_data)
                transcript = result.text if result.success else ""
                if transcript:
                    # Update the recording data and database
                    recording_data["transcript"] = transcript
                    self.app.db.update_recording(recording_id, transcript=transcript)
                    logger.info(
                        "Transcription completed",
                        recording_id=recording_id,
                        transcript_length=len(transcript)
                    )
                    # Save emotion data if available (Modulate provider)
                    if result.metadata and result.metadata.get("emotion_data"):
                        import json
                        self.app.db.update_recording(
                            recording_id,
                            metadata=json.dumps({"emotion_data": result.metadata["emotion_data"]})
                        )
                        logger.info("Saved emotion data from batch transcription", recording_id=recording_id)
                    return transcript
                else:
                    raise TranscriptionError("Transcription returned empty result")
            except TranscriptionError:
                raise  # Re-raise our custom exception as-is
            except (ConnectionError, TimeoutError) as e:
                # Network errors during transcription
                logger.error(
                    "Network error during transcription",
                    recording_id=recording_id,
                    error=str(e),
                    exc_info=True
                )
                raise TranscriptionError(f"Network error during transcription: {e}")
            except Exception as e:
                # Wrap unexpected errors in TranscriptionError
                logger.error(
                    "Transcription failed",
                    recording_id=recording_id,
                    exception_type=type(e).__name__,
                    error=str(e),
                    exc_info=True
                )
                raise TranscriptionError(f"Transcription failed: {type(e).__name__}: {e}")
        else:
            logger.error("Audio handler not available for transcription")
            raise TranscriptionError("Audio handler not available for transcription")
