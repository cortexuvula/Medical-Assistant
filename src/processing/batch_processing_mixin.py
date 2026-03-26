"""
Batch Processing Mixin for ProcessingQueue.

Handles batch operations including:
- Adding multiple recordings to the queue as a batch
- Tracking batch progress and completion
- Canceling batch operations
- Batch status reporting

This mixin is designed to be used with ProcessingQueue to keep the main
class focused on core queue operations.
"""

from concurrent.futures import Future
from typing import Dict, Optional, Callable, Any, List
from datetime import datetime
import uuid

from utils.error_handling import ErrorContext
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class BatchProcessingMixin:
    """Mixin providing batch processing capabilities for ProcessingQueue."""

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
            if task_id is not None:
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
                batch["tracking_errors"] = batch.get("tracking_errors", 0) + 1
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
                    batch["tracking_errors"] = batch.get("tracking_errors", 0) + 1
                    logger.warning("Failed to mark batch as completed in database", batch_id=batch_id, error=str(e))

            # Log tracking error summary if any occurred
            tracking_errors = batch.get("tracking_errors", 0)
            if tracking_errors > 0:
                logger.warning(
                    "Batch had database tracking errors",
                    batch_id=batch_id,
                    tracking_errors=tracking_errors,
                    completed=completed,
                    failed=failed,
                    total=total
                )

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
