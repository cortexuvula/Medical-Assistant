"""
Background Processing Queue Module

Manages asynchronous processing of recordings to allow immediate
continuation with next patient consultation.

Error Handling:
    - Raises ProcessingError: For task execution failures
    - Raises TranscriptionError: For STT provider failures
    - Raises DocumentGenerationError: For SOAP/referral/letter generation failures
    - Uses ErrorContext for capturing detailed error context
    - Failed tasks are tracked in failed_tasks dict with full error details
    - Retry logic with exponential backoff for transient failures
    - Batch processing supports continue_on_error for resilience

Logging:
    - Uses structured logging with context for better debugging
    - Key context fields: task_id, recording_id, batch_id, duration_ms
    - Thread exceptions captured via global exception hook

Thread Safety:
    - Uses ThreadPoolExecutor for concurrent task processing
    - RLock for thread-safe access to shared state
    - Queue-based task distribution for reliable ordering
    - Daemon threads prevent blocking on shutdown

Deduplication:
    - Tracks recording_id -> task_id mapping to prevent duplicate processing
    - Active recordings cannot be re-queued until completion or failure
"""

import uuid
import time
import os
from queue import Queue, Empty
from concurrent.futures import ThreadPoolExecutor, Future
from threading import Thread, RLock, Event
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime
import traceback

from database.database import Database
from settings.settings_manager import settings_manager
from utils.error_handling import ErrorContext, OperationResult
from utils.exceptions import (
    MedicalAssistantError,
    ProcessingError,
    TranscriptionError,
    AudioSaveError,
    DocumentGenerationError,
    APIError,
    APITimeoutError,
    DatabaseError,
)
from utils.structured_logging import get_logger

# Module-level structured logger
logger = get_logger(__name__)


def _thread_exception_hook(args):
    """Global exception hook for thread exceptions.

    This captures unhandled exceptions in threads that would otherwise be silent.
    """
    logger.error(
        "Unhandled exception in thread",
        thread_name=args.thread.name,
        exception_type=args.exc_type.__name__,
        exception_value=str(args.exc_value),
        exc_info=(args.exc_type, args.exc_value, args.exc_traceback)
    )


# Install global thread exception hook
import threading
if hasattr(threading, 'excepthook'):
    # Python 3.8+
    threading.excepthook = _thread_exception_hook


from processing.batch_processing_mixin import BatchProcessingMixin
from processing.document_generation_mixin import DocumentGenerationMixin
from processing.reprocessing_mixin import ReprocessingMixin


class ProcessingQueue(BatchProcessingMixin, DocumentGenerationMixin, ReprocessingMixin):
    """Manages background processing of medical recordings.

    This class uses mixins to organize functionality:
    - BatchProcessingMixin: Batch operations (add_batch_recordings, cancel_batch, etc.)
    - DocumentGenerationMixin: Document generation (_generate_soap_note, etc.)
    - ReprocessingMixin: Retry and reprocess operations

    Deduplication:
        The queue tracks active recordings by their recording_id to prevent
        duplicate processing. A recording that is already pending or processing
        will not be queued again until it completes or fails.
    """

    # Maximum batch size to prevent resource exhaustion
    MAX_BATCH_SIZE = 100

    def __init__(self, app=None, max_workers: int = None):
        """Initialize the processing queue.

        Args:
            app: The main application instance
            max_workers: Maximum number of concurrent processing threads
        """
        self.app = app
        # Dynamic default: use CPU count - 1 (capped at 6) for better throughput
        # This increases concurrent processing from 2 to 4-6 workers typically
        default_workers = min(os.cpu_count() - 1, 6) if os.cpu_count() else 4
        self.max_workers = max_workers or settings_manager.get("max_background_workers", default_workers)

        # Core components
        self.queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)
        self.active_tasks: Dict[str, Dict] = {}
        self.completed_tasks: Dict[str, Dict] = {}
        self.failed_tasks: Dict[str, Dict] = {}
        self.batch_tasks: Dict[str, Dict] = {}  # Track batch processing

        # Memory management: limit completed/failed task history
        self.MAX_COMPLETED_TASKS = 1000

        # Deduplication: track recording_id -> task_id for active recordings
        self._recording_to_task: Dict[int, str] = {}

        # Thread safety - use RLock for reentrant locking (same thread can acquire multiple times)
        self.lock = RLock()
        self.shutdown_event = Event()

        # Callbacks
        self.status_callback: Optional[Callable] = None
        self.completion_callback: Optional[Callable] = None
        self.error_callback: Optional[Callable] = None
        self.batch_callback: Optional[Callable] = None  # For batch progress updates

        # Statistics
        self.stats = {
            "total_queued": 0,
            "total_processed": 0,
            "total_failed": 0,
            "total_retried": 0,
            "total_deduplicated": 0,
            "processing_time_avg": 0
        }

        # Start the queue processor
        self.processor_thread = Thread(target=self._process_queue, daemon=True)
        self.processor_thread.start()

        logger.info("ProcessingQueue initialized", max_workers=self.max_workers)
    
    def add_recording(self, recording_data: Dict[str, Any]) -> Optional[str]:
        """Add a recording to the processing queue.

        Implements deduplication: if a recording is already being processed
        or is pending in the queue, returns None instead of queuing again.

        Args:
            recording_data: Dictionary containing:
                - recording_id: Database ID of the recording
                - audio_data: Raw audio data
                - patient_name: Patient name for notifications
                - context: Any context information
                - priority: Processing priority (0-10, default 5)
                - batch_id: Optional batch identifier

        Returns:
            task_id: Unique identifier for tracking this task, or None if duplicate
        """
        recording_id = recording_data.get("recording_id")
        with self.lock:
            # Check for duplicate - is this recording already being processed?
            if recording_id is not None and recording_id in self._recording_to_task:
                existing_task_id = self._recording_to_task[recording_id]
                # Verify the task is still active
                if existing_task_id in self.active_tasks:
                    existing_status = self.active_tasks[existing_task_id].get("status", "unknown")
                    logger.warning(
                        "Recording already queued, skipping duplicate",
                        recording_id=recording_id,
                        existing_task_id=existing_task_id,
                        existing_status=existing_status
                    )
                    self.stats["total_deduplicated"] += 1
                    return None
                else:
                    # Task completed/failed, remove stale mapping
                    del self._recording_to_task[recording_id]

            # Generate new task ID
            task_id = str(uuid.uuid4())

            # Add timestamp and task ID
            recording_data["task_id"] = task_id
            recording_data["queued_at"] = datetime.now()
            recording_data["priority"] = recording_data.get("priority", 5)
            recording_data["retry_count"] = 0
            recording_data["status"] = "queued"

            # Track in active tasks
            self.active_tasks[task_id] = recording_data
            self.stats["total_queued"] += 1

            # Track recording_id -> task_id for deduplication
            if recording_id is not None:
                self._recording_to_task[recording_id] = task_id

            # Track batch if provided
            batch_id = recording_data.get("batch_id")
            if batch_id:
                if batch_id not in self.batch_tasks:
                    self.batch_tasks[batch_id] = {
                        "total": 0,
                        "completed": 0,
                        "failed": 0,
                        "task_ids": []
                    }
                self.batch_tasks[batch_id]["total"] += 1
                self.batch_tasks[batch_id]["task_ids"].append(task_id)

        # Add to queue (outside lock - queue is thread-safe)
        self.queue.put((recording_data["priority"], task_id, recording_data))

        # Notify status update
        self._notify_status_update(task_id, "queued", len(self.active_tasks))

        logger.info("Recording added to queue", recording_id=recording_id, task_id=task_id)

        return task_id
    
    def add_batch_recordings(self, recordings: List[Dict[str, Any]], batch_options: Dict[str, Any] = None) -> str:
        """Add multiple recordings to the processing queue as a batch.

        Args:
            recordings: List of recording data dictionaries
            batch_options: Optional batch-wide options (priority, etc.)

        Returns:
            batch_id: Unique identifier for the batch

        Raises:
            ValueError: If batch size exceeds MAX_BATCH_SIZE
        """
        # SECURITY: Enforce batch size limit to prevent resource exhaustion
        if len(recordings) > self.MAX_BATCH_SIZE:
            logger.error(
                "Batch size exceeds maximum allowed",
                batch_size=len(recordings),
                max_batch_size=self.MAX_BATCH_SIZE
            )
            raise ValueError(f"Batch size {len(recordings)} exceeds maximum allowed ({self.MAX_BATCH_SIZE})")

        batch_id = str(uuid.uuid4())
        batch_priority = batch_options.get("priority", 5) if batch_options else 5

        logger.info("Adding batch", batch_id=batch_id, recording_count=len(recordings))
        
        # Initialize batch tracking
        with self.lock:
            self.batch_tasks[batch_id] = {
                "total": len(recordings),
                "completed": 0,
                "failed": 0,
                "task_ids": [],
                "started_at": datetime.now(),
                "options": batch_options or {}
            }

        # Persist batch to database for durability
        if self.app and hasattr(self.app, 'db'):
            try:
                import json
                options_json = json.dumps(batch_options) if batch_options else None
                self.app.db.execute_query("""
                    INSERT OR REPLACE INTO batch_processing
                    (batch_id, total_count, completed_count, failed_count, created_at, started_at, options, status)
                    VALUES (?, ?, 0, 0, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, 'processing')
                """, (batch_id, len(recordings), options_json))
                logger.info("Persisted batch to database", batch_id=batch_id)
            except Exception as e:
                logger.warning("Failed to persist batch to database", batch_id=batch_id, error=str(e))
        
        # Add each recording with batch info
        task_ids = []
        for recording_data in recordings:
            # Add batch info to recording data
            recording_data["batch_id"] = batch_id
            recording_data["priority"] = recording_data.get("priority", batch_priority)
            
            # Add batch options
            if batch_options:
                recording_data["batch_options"] = batch_options
            
            task_id = self.add_recording(recording_data)
            task_ids.append(task_id)
        
        # Notify batch start
        if self.batch_callback:
            try:
                self.batch_callback("started", batch_id, 0, len(recordings))
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Batch start callback notification",
                    exception=e,
                    error_code="CALLBACK_BATCH_START_ERROR",
                    batch_id=batch_id,
                    recording_count=len(recordings)
                )
                ctx.log()
        
        return batch_id
    
    def _process_queue(self):
        """Main queue processing loop - runs in separate thread."""
        logger.info("Processing queue started")
        
        while not self.shutdown_event.is_set():
            try:
                # Wait for items with timeout
                priority, task_id, recording_data = self.queue.get(timeout=1.0)
                
                # Submit to executor
                future = self.executor.submit(self._process_recording, task_id, recording_data)

                # Track the future
                with self.lock:
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id]["future"] = future
                        self.active_tasks[task_id]["status"] = "processing"

                # Mark queue task as done
                self.queue.task_done()
                
            except Empty:
                # No items in queue, continue waiting
                continue
            except RuntimeError as e:
                # Thread pool or executor error - may need to exit
                logger.error("Queue processor thread error", error=str(e), exc_info=True)
                if "shutdown" in str(e).lower() or "cannot schedule" in str(e).lower():
                    logger.warning("Executor shutting down, exiting queue processor")
                    break
            except (OSError, IOError) as e:
                # System-level I/O errors
                logger.error("I/O error in queue processor", error=str(e), exc_info=True)
                time.sleep(0.5)  # Back off before retrying
            except Exception as e:
                # Unexpected error - log but don't crash the queue processor
                logger.error(
                    "Unexpected error in queue processor",
                    exception_type=type(e).__name__,
                    error=str(e),
                    exc_info=True
                )
                time.sleep(0.1)  # Brief back-off to prevent tight error loops
    
    def _process_recording(self, task_id: str, recording_data: Dict[str, Any]):
        """Process a single recording - runs in thread pool."""
        start_time = time.time()
        recording_id = recording_data.get("recording_id")
        
        try:
            logger.info("Starting processing for task", task_id=task_id, recording_id=recording_id)
            
            # Update status
            recording_data["status"] = "processing"
            recording_data["started_at"] = datetime.now()
            self._notify_status_update(task_id, "processing", len(self.active_tasks))
            
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
                    logger.info("Transcribing audio for recording", recording_id=recording_id)
                    audio_data = recording_data.get("audio_data")
                    
                    # Save audio file before transcription
                    try:
                        from datetime import datetime as dt
                        import os
                        
                        # Get storage folder
                        storage_folder = settings_manager.get("storage_folder")
                        logger.debug("Storage folder from settings", storage_folder=storage_folder)

                        if not storage_folder:
                            storage_folder = settings_manager.get("default_storage_folder")
                            logger.debug("Using default_storage_folder", storage_folder=storage_folder)

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
                        import tempfile
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
                                else:
                                    logger.error(
                                        "Audio save reported success but file not found",
                                        audio_path=audio_path
                                    )
                            else:
                                logger.error("Failed to save audio", audio_path=audio_path)
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

                    # Use the app's audio handler to transcribe
                    if hasattr(self.app, 'audio_handler'):
                        try:
                            transcript = self.app.audio_handler.transcribe_audio(audio_data)
                            if transcript:
                                # Update the recording data and database
                                recording_data["transcript"] = transcript
                                self.app.db.update_recording(recording_id, transcript=transcript)
                                logger.info(
                                    "Transcription completed",
                                    recording_id=recording_id,
                                    transcript_length=len(transcript)
                                )
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
    
    def _mark_completed(self, task_id: str, recording_data: Dict, result: Dict, processing_time: float):
        """Mark a task as completed successfully."""
        with self.lock:
            # Update task data
            recording_data["status"] = "completed"
            recording_data["completed_at"] = datetime.now()
            recording_data["processing_time"] = processing_time
            recording_data["result"] = result

            # Move to completed
            if task_id in self.active_tasks:
                self.completed_tasks[task_id] = self.active_tasks.pop(task_id)

            # Remove from deduplication tracking
            recording_id = recording_data.get("recording_id")
            if recording_id is not None and recording_id in self._recording_to_task:
                del self._recording_to_task[recording_id]

            # Update stats
            self.stats["total_processed"] += 1
            self._update_avg_processing_time(processing_time)

            # Update batch tracking if part of a batch
            batch_id = recording_data.get("batch_id")
            if batch_id and batch_id in self.batch_tasks:
                self.batch_tasks[batch_id]["completed"] += 1
                self._check_batch_completion(batch_id)
        
        # Update database
        if self.app and hasattr(self.app, 'db'):
            self.app.db.update_recording(
                recording_data["recording_id"],
                processing_status="completed",
                processing_completed_at=datetime.now()
            )
        
        # Add processing time to result for notification
        if isinstance(result, dict):
            result['processing_time'] = processing_time
        
        # Notify completion
        self._notify_completion(task_id, recording_data, result)
        self._notify_status_update(task_id, "completed", len(self.active_tasks))
        
        logger.info("Task completed", task_id=task_id, processing_time_seconds=round(processing_time, 2))

        # Prune old tasks to prevent memory growth
        self._prune_completed_tasks()

    def _prune_completed_tasks(self):
        """Remove oldest completed/failed tasks if over the limit to prevent memory leaks."""
        with self.lock:
            # Prune completed tasks
            if len(self.completed_tasks) > self.MAX_COMPLETED_TASKS:
                # Sort by completed_at time and remove oldest
                sorted_tasks = sorted(
                    self.completed_tasks.items(),
                    key=lambda x: x[1].get("completed_at", datetime.min)
                )
                # Remove oldest tasks (keep most recent MAX_COMPLETED_TASKS)
                tasks_to_remove = len(self.completed_tasks) - self.MAX_COMPLETED_TASKS
                for task_id, _ in sorted_tasks[:tasks_to_remove]:
                    del self.completed_tasks[task_id]
                logger.debug("Pruned old completed tasks", count=tasks_to_remove)

            # Prune failed tasks (use same limit)
            if len(self.failed_tasks) > self.MAX_COMPLETED_TASKS:
                sorted_tasks = sorted(
                    self.failed_tasks.items(),
                    key=lambda x: x[1].get("failed_at", datetime.min)
                )
                tasks_to_remove = len(self.failed_tasks) - self.MAX_COMPLETED_TASKS
                for task_id, _ in sorted_tasks[:tasks_to_remove]:
                    del self.failed_tasks[task_id]
                logger.debug("Pruned old failed tasks", count=tasks_to_remove)

    def _mark_failed(self, task_id: str, recording_data: Dict, error_msg: str):
        """Mark a task as failed."""
        with self.lock:
            # Update task data
            recording_data["status"] = "failed"
            recording_data["failed_at"] = datetime.now()
            recording_data["error_message"] = error_msg

            # Move to failed
            if task_id in self.active_tasks:
                self.failed_tasks[task_id] = self.active_tasks.pop(task_id)

            # Remove from deduplication tracking (allow re-queue after failure)
            recording_id = recording_data.get("recording_id")
            if recording_id is not None and recording_id in self._recording_to_task:
                del self._recording_to_task[recording_id]

            # Update stats
            self.stats["total_failed"] += 1

            # Update batch tracking if part of a batch
            batch_id = recording_data.get("batch_id")
            if batch_id and batch_id in self.batch_tasks:
                self.batch_tasks[batch_id]["failed"] += 1
                self._check_batch_completion(batch_id)
        
        # Update database
        if self.app and hasattr(self.app, 'db'):
            self.app.db.update_recording(
                recording_data["recording_id"],
                processing_status="failed",
                error_message=error_msg
            )
        
        # Notify failure
        self._notify_error(task_id, recording_data, error_msg)
        self._notify_status_update(task_id, "failed", len(self.active_tasks))

        logger.error("Task failed", task_id=task_id, error=error_msg)

        # Prune old tasks to prevent memory growth
        self._prune_completed_tasks()

    def _should_retry(self, recording_data: Dict) -> bool:
        """Check if a task should be retried."""
        if not settings_manager.get("auto_retry_failed", True):
            return False

        max_retries = settings_manager.get("max_retry_attempts", 3)
        return recording_data.get("retry_count", 0) < max_retries
    
    def _retry_task(self, task_id: str, recording_data: Dict, error_msg: str):
        """Retry a failed task with exponential backoff."""
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
        
        Thread(target=delayed_retry, daemon=True).start()
    
    def _update_avg_processing_time(self, new_time: float):
        """Update average processing time statistic.

        Thread-safe: acquires lock before reading/writing shared stats.
        """
        with self.lock:
            total = self.stats["total_processed"]
            if total == 0:
                # Edge case: shouldn't happen but protect against division by zero
                self.stats["processing_time_avg"] = new_time
            elif total == 1:
                self.stats["processing_time_avg"] = new_time
            else:
                # Running average
                current_avg = self.stats["processing_time_avg"]
                self.stats["processing_time_avg"] = ((current_avg * (total - 1)) + new_time) / total
    
    def _notify_status_update(self, task_id: str, status: str, queue_size: int):
        """Notify status callback of queue status change."""
        if self.status_callback:
            try:
                self.status_callback(task_id, status, queue_size)
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Status callback notification",
                    exception=e,
                    error_code="CALLBACK_STATUS_ERROR",
                    task_id=task_id,
                    status=status,
                    queue_size=queue_size
                )
                ctx.log()

    def _notify_completion(self, task_id: str, recording_data: Dict, result: Dict):
        """Notify completion callback."""
        if self.completion_callback:
            try:
                self.completion_callback(task_id, recording_data, result)
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Completion callback notification",
                    exception=e,
                    error_code="CALLBACK_COMPLETION_ERROR",
                    task_id=task_id,
                    recording_id=recording_data.get("recording_id"),
                    result_keys=list(result.keys()) if isinstance(result, dict) else None
                )
                ctx.log()

    def _notify_error(self, task_id: str, recording_data: Dict, error_msg: str):
        """Notify error callback."""
        if self.error_callback:
            try:
                self.error_callback(task_id, recording_data, error_msg)
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Error callback notification",
                    exception=e,
                    error_code="CALLBACK_ERROR_ERROR",
                    task_id=task_id,
                    recording_id=recording_data.get("recording_id"),
                    original_error=error_msg
                )
                ctx.log()
    
    def get_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        with self.lock:
            return {
                "queue_size": self.queue.qsize(),
                "active_tasks": len(self.active_tasks),
                "completed_tasks": len(self.completed_tasks),
                "failed_tasks": len(self.failed_tasks),
                "stats": self.stats.copy(),
                "workers": self.max_workers
            }
    
    def get_task_status(self, task_id: str) -> Optional[Dict]:
        """Get status of a specific task."""
        with self.lock:
            if task_id in self.active_tasks:
                return self.active_tasks[task_id].copy()
            elif task_id in self.completed_tasks:
                return self.completed_tasks[task_id].copy()
            elif task_id in self.failed_tasks:
                return self.failed_tasks[task_id].copy()
        return None
    
    def cancel_task(self, task_id: str) -> bool:
        """Attempt to cancel a queued or processing task."""
        with self.lock:
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                recording_id = task.get("recording_id")

                if task["status"] == "queued":
                    # Remove from queue if still queued
                    task["status"] = "cancelled"
                    self.active_tasks.pop(task_id)
                    # Remove from deduplication tracking
                    if recording_id is not None and recording_id in self._recording_to_task:
                        del self._recording_to_task[recording_id]
                    logger.info("Task cancelled", task_id=task_id, status="queued")
                    return True
                elif "future" in task:
                    # Try to cancel running task
                    future: Future = task["future"]
                    if future.cancel():
                        self.active_tasks.pop(task_id)
                        # Remove from deduplication tracking
                        if recording_id is not None and recording_id in self._recording_to_task:
                            del self._recording_to_task[recording_id]
                        logger.info("Task cancelled", task_id=task_id, status="running")
                        return True
        return False

    def cancel_batch(self, batch_id: str) -> int:
        """Cancel all pending tasks in a batch.

        Args:
            batch_id: The batch identifier

        Returns:
            Number of tasks successfully cancelled
        """
        cancelled_count = 0
        with self.lock:
            batch = self.batch_tasks.get(batch_id)
            if not batch:
                logger.warning("Batch not found for cancellation", batch_id=batch_id)
                return 0

            task_ids = batch.get("task_ids", [])
            logger.info("Attempting to cancel batch", batch_id=batch_id, task_count=len(task_ids))

            for task_id in task_ids:
                # Only cancel if task is still in active_tasks
                if task_id in self.active_tasks:
                    task = self.active_tasks[task_id]
                    if task.get("status") == "queued":
                        # Can cancel queued tasks
                        recording_id = task.get("recording_id")
                        task["status"] = "cancelled"
                        self.active_tasks.pop(task_id)
                        if recording_id is not None and recording_id in self._recording_to_task:
                            del self._recording_to_task[recording_id]
                        cancelled_count += 1
                        logger.debug("Cancelled queued task in batch", task_id=task_id, batch_id=batch_id)
                    elif "future" in task:
                        # Try to cancel running task
                        future: Future = task["future"]
                        if future.cancel():
                            recording_id = task.get("recording_id")
                            self.active_tasks.pop(task_id)
                            if recording_id is not None and recording_id in self._recording_to_task:
                                del self._recording_to_task[recording_id]
                            cancelled_count += 1
                            logger.debug("Cancelled running task in batch", task_id=task_id, batch_id=batch_id)

            logger.info("Batch cancellation complete", batch_id=batch_id, cancelled_count=cancelled_count)

        return cancelled_count

    def shutdown(self, wait: bool = True):
        """Shutdown the processing queue gracefully."""
        logger.info("Shutting down processing queue", wait=wait)

        # Signal shutdown
        self.shutdown_event.set()

        # Wait for processor thread
        if wait:
            self.processor_thread.join(timeout=5)

        # Shutdown executor
        self.executor.shutdown(wait=wait)

        logger.info("Processing queue shutdown complete")
    
    def _check_batch_completion(self, batch_id: str):
        """Check if a batch is complete and notify if so."""
        batch = self.batch_tasks.get(batch_id)
        if not batch:
            return

        total = batch["total"]
        completed = batch["completed"]
        failed = batch["failed"]

        # Update batch progress in database
        if self.app and hasattr(self.app, 'db'):
            try:
                self.app.db.execute_query("""
                    UPDATE batch_processing
                    SET completed_count = ?, failed_count = ?
                    WHERE batch_id = ?
                """, (completed, failed, batch_id))
            except Exception as e:
                logger.warning("Failed to update batch progress in database", batch_id=batch_id, error=str(e))

        # Notify progress
        if self.batch_callback:
            try:
                self.batch_callback("progress", batch_id, completed + failed, total)
            except Exception as e:
                ctx = ErrorContext.capture(
                    operation="Batch progress callback notification",
                    exception=e,
                    error_code="CALLBACK_BATCH_PROGRESS_ERROR",
                    batch_id=batch_id,
                    completed=completed,
                    failed=failed,
                    total=total
                )
                ctx.log()

        # Check if batch is complete
        if completed + failed >= total:
            batch["completed_at"] = datetime.now()

            # Calculate duration
            duration = (batch["completed_at"] - batch["started_at"]).total_seconds()
            batch["duration"] = duration

            # Mark batch as completed in database
            if self.app and hasattr(self.app, 'db'):
                try:
                    self.app.db.execute_query("""
                        UPDATE batch_processing
                        SET completed_count = ?, failed_count = ?, completed_at = CURRENT_TIMESTAMP, status = 'completed'
                        WHERE batch_id = ?
                    """, (completed, failed, batch_id))
                    logger.info("Marked batch as completed in database", batch_id=batch_id)
                except Exception as e:
                    logger.warning("Failed to mark batch as completed in database", batch_id=batch_id, error=str(e))

            # Notify completion
            if self.batch_callback:
                try:
                    self.batch_callback("completed", batch_id, completed, total, failed=failed)
                except Exception as e:
                    ctx = ErrorContext.capture(
                        operation="Batch completion callback notification",
                        exception=e,
                        error_code="CALLBACK_BATCH_COMPLETE_ERROR",
                        batch_id=batch_id,
                        completed=completed,
                        failed=failed,
                        total=total,
                        duration=duration
                    )
                    ctx.log()
            
            logger.info(
                "Batch completed",
                batch_id=batch_id,
                successful=completed,
                failed=failed,
                duration_seconds=round(duration, 2)
            )
    
    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get the status of a batch.
        
        Args:
            batch_id: Batch identifier
            
        Returns:
            Batch status dictionary or None if not found
        """
        with self.lock:
            batch = self.batch_tasks.get(batch_id)
            if batch:
                return {
                    "batch_id": batch_id,
                    "total": batch["total"],
                    "completed": batch["completed"],
                    "failed": batch["failed"],
                    "in_progress": batch["total"] - batch["completed"] - batch["failed"],
                    "started_at": batch.get("started_at"),
                    "completed_at": batch.get("completed_at"),
                    "duration": batch.get("duration"),
                    "options": batch.get("options", {})
                }
        return None
    
    def set_batch_callback(self, callback: Callable):
        """Set the batch progress callback.
        
        Args:
            callback: Function to call with (event, batch_id, current, total, **kwargs)
        """
        self.batch_callback = callback
    
    def _generate_soap_note(self, transcript: str, context: str = "") -> Optional[str]:
        """Generate SOAP note from transcript with optional context.

        Args:
            transcript: The transcript text
            context: Optional context/background information to include

        Returns:
            Generated SOAP note or None if failed

        Note:
            Returns None on failure rather than raising to allow partial
            processing to continue. Errors are logged with full context.
        """
        try:
            from ai.ai import create_soap_note_with_openai

            provider = settings_manager.get_ai_provider()
            model = settings_manager.get_nested(f"{provider}.model", "gpt-4")

            # Generate SOAP note with context if provided
            soap_note = create_soap_note_with_openai(transcript, context)
            return soap_note
        except (APIError, APITimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate SOAP note",
                exception=e,
                error_code=getattr(e, 'error_code', 'SOAP_API_ERROR'),
                transcript_length=len(transcript),
                has_context=bool(context)
            )
            ctx.log()
            return None
        except (ConnectionError, TimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate SOAP note",
                exception=e,
                error_code="SOAP_NETWORK_ERROR",
                transcript_length=len(transcript)
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generate SOAP note",
                exception=e,
                error_code="SOAP_UNEXPECTED_ERROR",
                transcript_length=len(transcript)
            )
            ctx.log()
            return None
    
    def _generate_referral(self, soap_note: str) -> Optional[str]:
        """Generate referral from SOAP note.

        Args:
            soap_note: The SOAP note text

        Returns:
            Generated referral or None if failed

        Note:
            Returns None on failure rather than raising to allow partial
            processing to continue. Errors are logged with full context.
        """
        try:
            from ai.ai import create_referral_with_openai

            provider = settings_manager.get_ai_provider()
            model = settings_manager.get_nested(f"{provider}.model", "gpt-4")

            # For batch processing, use a default condition
            conditions = "Based on the clinical findings in the SOAP note"

            # Generate referral
            referral = create_referral_with_openai(soap_note, conditions)
            return referral
        except (APIError, APITimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate referral",
                exception=e,
                error_code=getattr(e, 'error_code', 'REFERRAL_API_ERROR'),
                soap_note_length=len(soap_note)
            )
            ctx.log()
            return None
        except (ConnectionError, TimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate referral",
                exception=e,
                error_code="REFERRAL_NETWORK_ERROR",
                soap_note_length=len(soap_note)
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generate referral",
                exception=e,
                error_code="REFERRAL_UNEXPECTED_ERROR",
                soap_note_length=len(soap_note)
            )
            ctx.log()
            return None
    
    def _generate_letter(self, content: str, recipient_type: str = "other", specs: str = "") -> Optional[str]:
        """Generate letter from content.

        Args:
            content: The source content (SOAP note or transcript)
            recipient_type: Type of recipient (insurance, employer, specialist, etc.)
            specs: Additional specifications for the letter

        Returns:
            Generated letter or None if failed

        Note:
            Returns None on failure rather than raising to allow partial
            processing to continue. Errors are logged with full context.
        """
        try:
            from ai.ai import create_letter_with_ai

            provider = settings_manager.get_ai_provider()
            model = settings_manager.get_nested(f"{provider}.model", "gpt-4")

            # Generate letter with recipient type and specs
            letter = create_letter_with_ai(content, recipient_type, specs)
            return letter
        except (APIError, APITimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate letter",
                exception=e,
                error_code=getattr(e, 'error_code', 'LETTER_API_ERROR'),
                content_length=len(content),
                recipient_type=recipient_type
            )
            ctx.log()
            return None
        except (ConnectionError, TimeoutError) as e:
            ctx = ErrorContext.capture(
                operation="Generate letter",
                exception=e,
                error_code="LETTER_NETWORK_ERROR",
                content_length=len(content)
            )
            ctx.log()
            return None
        except Exception as e:
            ctx = ErrorContext.capture(
                operation="Generate letter",
                exception=e,
                error_code="LETTER_UNEXPECTED_ERROR",
                content_length=len(content)
            )
            ctx.log()
            return None
    
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