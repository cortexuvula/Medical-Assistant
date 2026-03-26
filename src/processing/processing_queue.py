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
from processing.guidelines_processing_mixin import GuidelinesProcessingMixin
from processing.task_executor_mixin import TaskExecutorMixin
from processing.task_lifecycle_mixin import TaskLifecycleMixin
from processing.notification_mixin import NotificationMixin


class ProcessingQueue(
    BatchProcessingMixin,
    DocumentGenerationMixin,
    ReprocessingMixin,
    GuidelinesProcessingMixin,
    TaskExecutorMixin,
    TaskLifecycleMixin,
    NotificationMixin,
):
    """Manages background processing of medical recordings.

    This class uses mixins to organize functionality:
    - BatchProcessingMixin: Batch operations (add_batch_recordings, cancel_batch, etc.)
    - DocumentGenerationMixin: Document generation (_generate_soap_note, etc.)
    - ReprocessingMixin: Retry and reprocess operations
    - GuidelinesProcessingMixin: Background guideline upload operations
    - TaskExecutorMixin: Recording processing logic (_process_recording)
    - TaskLifecycleMixin: Task state transitions (_mark_completed, _mark_failed, etc.)
    - NotificationMixin: Callback notifications (_notify_status_update, etc.)

    Deduplication:
        The queue tracks active recordings by their recording_id to prevent
        duplicate processing. A recording that is already pending or processing
        will not be queued again until it completes or fails.
    """

    # Maximum batch size to prevent resource exhaustion
    # Increased from 100 to support large guideline batches with parallel processing
    MAX_BATCH_SIZE = 1000

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

        # Separate executor for guideline uploads (I/O-bound tasks)
        default_guideline_workers = min(os.cpu_count(), 8) if os.cpu_count() else 4
        self.max_guideline_workers = settings_manager.get("max_guideline_workers", default_guideline_workers)

        # Core components
        self.queue = Queue()
        self.executor = ThreadPoolExecutor(max_workers=self.max_workers)

        # Dedicated executor for guidelines to prevent blocking recordings
        self.guideline_executor = ThreadPoolExecutor(
            max_workers=self.max_guideline_workers,
            thread_name_prefix="guideline-worker"
        )
        self.active_tasks: Dict[str, Dict] = {}
        self.completed_tasks: Dict[str, Dict] = {}
        self.failed_tasks: Dict[str, Dict] = {}
        self.batch_tasks: Dict[str, Dict] = {}  # Track batch processing

        # Memory management: limit completed/failed task history
        self.MAX_COMPLETED_TASKS = 1000
        # Age-based eviction: tasks older than this (seconds) are auto-failed
        self.TASK_MAX_AGE_SECONDS = 3600  # 1 hour
        self._last_eviction_check = time.time()

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

        # Guidelines processing (from GuidelinesProcessingMixin)
        self.guideline_batches: Dict[str, Dict] = {}
        self.guideline_progress_callback: Optional[Callable] = None

        # Start the queue processor
        self.processor_thread = Thread(target=self._process_queue, daemon=True)
        self.processor_thread.start()

        logger.info(
            "ProcessingQueue initialized",
            recording_workers=self.max_workers,
            guideline_workers=self.max_guideline_workers
        )

    def recover_orphaned_tasks(self) -> int:
        """Recover tasks that were interrupted by a previous crash/shutdown.

        Checks the processing_queue DB table for tasks stuck in 'queued' or
        'processing' state and marks them as failed (re-queuing is not possible
        without the in-memory audio data).

        Returns:
            Number of tasks recovered
        """
        if not self.app or not hasattr(self.app, 'db') or not self.app.db:
            return 0

        recovered = 0
        try:
            # Use the Database's connection context manager for thread-safe access
            with self.app.db.connection() as (conn, cursor):
                cursor.execute(
                    "SELECT task_id, recording_id, status "
                    "FROM processing_queue WHERE status IN ('queued', 'processing')"
                )
                rows = cursor.fetchall()

            if not rows:
                return 0

            for row in rows:
                task_id = row[0]
                recording_id = row[1]
                status = row[2]

                error_msg = (
                    "Interrupted by application shutdown"
                    if status == 'processing'
                    else "Interrupted by application shutdown - please reprocess"
                )

                try:
                    self.app.db.update_queue_status(
                        task_id, "failed",
                        last_error=error_msg
                    )
                    logger.info(
                        f"Marked orphaned {status} task as failed",
                        task_id=task_id,
                        recording_id=recording_id
                    )
                    recovered += 1
                except Exception as e:
                    logger.warning(f"Failed to recover task {task_id}: {e}")

            if recovered:
                logger.info(f"Recovered {recovered} orphaned task(s) from previous session")
        except Exception as e:
            logger.error(f"Error recovering orphaned tasks: {e}", exc_info=True)

        return recovered

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
                        "tracking_errors": 0,
                        "task_ids": []
                    }
                self.batch_tasks[batch_id]["total"] += 1
                self.batch_tasks[batch_id]["task_ids"].append(task_id)

        # DB FIRST: persist task to survive crashes
        try:
            if self.app and hasattr(self.app, 'db') and self.app.db and recording_id is not None:
                self.app.db.add_to_processing_queue(
                    recording_id, task_id, recording_data["priority"]
                )
        except Exception as e:
            logger.warning(f"Failed to persist task to DB (continuing in-memory): {e}")

        # Add to queue (outside lock - queue is thread-safe)
        self.queue.put((recording_data["priority"], task_id, recording_data))

        # Notify status update
        self._notify_status_update(task_id, "queued", len(self.active_tasks))

        logger.info("Recording added to queue", recording_id=recording_id, task_id=task_id)

        return task_id

    def _process_queue(self):
        """Main queue processing loop - runs in separate thread."""
        logger.info("Processing queue started")

        while not self.shutdown_event.is_set():
            try:
                # Wait for items with timeout
                priority, task_id, recording_data = self.queue.get(timeout=1.0)

                # Route to appropriate executor based on task type
                task_type = recording_data.get("task_type", "recording")
                if task_type == "guideline_upload":
                    executor = self.guideline_executor
                    logger.debug("Submitting to guideline executor", task_id=task_id)
                else:
                    executor = self.executor
                    logger.debug("Submitting to recording executor", task_id=task_id)

                # Submit to appropriate executor
                future = executor.submit(self._process_recording, task_id, recording_data)

                # Track the future
                with self.lock:
                    if task_id in self.active_tasks:
                        self.active_tasks[task_id]["future"] = future
                        self.active_tasks[task_id]["status"] = "processing"
                        self.active_tasks[task_id]["executor_type"] = task_type  # Track which executor

                # Update DB status to 'processing'
                try:
                    if self.app and hasattr(self.app, 'db') and self.app.db:
                        self.app.db.update_queue_status(
                            task_id, "processing",
                            started_at=datetime.now().isoformat()
                        )
                except Exception as e:
                    logger.warning("Failed to update queue status to 'processing'", task_id=task_id, error=str(e))

                # Mark queue task as done
                self.queue.task_done()

            except Empty:
                # No items in queue — periodically evict stale active tasks
                now = time.time()
                if now - self._last_eviction_check > 60:  # Check every 60s
                    self._last_eviction_check = now
                    self._evict_stale_tasks()
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

    def get_status(self) -> Dict[str, Any]:
        """Get current queue status and statistics."""
        with self.lock:
            # Count active tasks by type
            recording_tasks = sum(
                1 for t in self.active_tasks.values()
                if t.get("task_type", "recording") == "recording"
            )
            guideline_tasks = sum(
                1 for t in self.active_tasks.values()
                if t.get("task_type") == "guideline_upload"
            )

            return {
                "queue_size": self.queue.qsize(),
                "active_tasks": len(self.active_tasks),
                "active_recording_tasks": recording_tasks,
                "active_guideline_tasks": guideline_tasks,
                "completed_tasks": len(self.completed_tasks),
                "failed_tasks": len(self.failed_tasks),
                "stats": self.stats.copy(),
                "workers": self.max_workers,
                "guideline_workers": self.max_guideline_workers
            }

    def _evict_stale_tasks(self):
        """Evict active tasks that have been running longer than TASK_MAX_AGE_SECONDS.

        Prevents unbounded growth of active_tasks dict when tasks hang or never complete.
        """
        now = time.time()
        stale_tasks = []

        with self.lock:
            for task_id, task_data in self.active_tasks.items():
                queued_at = task_data.get("queued_at")
                if queued_at:
                    try:
                        task_time = datetime.fromisoformat(queued_at).timestamp()
                        if now - task_time > self.TASK_MAX_AGE_SECONDS:
                            stale_tasks.append(task_id)
                    except (ValueError, TypeError):
                        pass

        for task_id in stale_tasks:
            logger.warning(
                "Evicting stale task (exceeded max age)",
                task_id=task_id,
                max_age_seconds=self.TASK_MAX_AGE_SECONDS
            )
            with self.lock:
                task_data = self.active_tasks.get(task_id, {})
            self._mark_failed(task_id, task_data, f"Task timed out after {self.TASK_MAX_AGE_SECONDS}s")

        if stale_tasks:
            logger.info(f"Evicted {len(stale_tasks)} stale task(s)")

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

    def shutdown(self, wait: bool = True):
        """Shutdown the processing queue gracefully."""
        logger.info("Shutting down processing queue", wait=wait)

        # Signal shutdown
        self.shutdown_event.set()

        # Wait for processor thread
        if wait:
            self.processor_thread.join(timeout=5)

        # Shutdown both executors
        logger.info("Shutting down recording executor", max_workers=self.max_workers)
        self.executor.shutdown(wait=wait)

        # Shutdown guideline executor
        logger.info("Shutting down guideline executor", max_workers=self.max_guideline_workers)
        self.guideline_executor.shutdown(wait=wait)

        logger.info("Processing queue shutdown complete")

    # NOTE: _generate_soap_note, _generate_referral, and _generate_letter
    # are inherited from DocumentGenerationMixin — do not redefine here.

    # NOTE: _process_recording and _transcribe_audio are inherited from
    # TaskExecutorMixin — do not redefine here.

    # NOTE: _mark_completed, _mark_failed, _prune_completed_tasks, and
    # _update_avg_processing_time are inherited from TaskLifecycleMixin —
    # do not redefine here.

    # NOTE: _notify_status_update, _notify_completion, and _notify_error
    # are inherited from NotificationMixin — do not redefine here.

    # NOTE: _should_retry and _retry_task are inherited from
    # ReprocessingMixin — do not redefine here.

    # NOTE: cancel_batch, get_batch_status, set_batch_callback,
    # _check_batch_completion, and add_batch_recordings are inherited from
    # BatchProcessingMixin — do not redefine here.

    # NOTE: reprocess_failed_recording and reprocess_multiple_failed_recordings
    # are inherited from ReprocessingMixin — do not redefine here.
