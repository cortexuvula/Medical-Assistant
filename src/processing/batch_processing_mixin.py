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

from typing import Dict, Optional, Callable, Any, List
from datetime import datetime
import uuid

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class BatchProcessingMixin:
    """Mixin providing batch processing capabilities for ProcessingQueue."""

    def add_batch_recordings(self, recordings: List[Dict[str, Any]], batch_options: Dict[str, Any] = None) -> str:
        """Add multiple recordings as a batch for processing.

        Args:
            recordings: List of recording data dictionaries
            batch_options: Optional batch configuration:
                - generate_soap: bool (default True)
                - generate_referral: bool (default False)
                - generate_letter: bool (default False)
                - priority: str (default "normal")
                - skip_existing: bool (default False) - skip if already generated
                - continue_on_error: bool (default True) - continue batch if one fails

        Returns:
            batch_id: Unique identifier for the batch

        Raises:
            ValueError: If recordings list is empty or exceeds MAX_BATCH_SIZE
        """
        if not recordings:
            raise ValueError("Cannot add empty batch")

        if len(recordings) > self.MAX_BATCH_SIZE:
            raise ValueError(f"Batch size {len(recordings)} exceeds maximum {self.MAX_BATCH_SIZE}")

        batch_id = str(uuid.uuid4())
        batch_options = batch_options or {}

        with self.lock:
            self.batch_tasks[batch_id] = {
                "batch_id": batch_id,
                "total": len(recordings),
                "completed": 0,
                "failed": 0,
                "pending": len(recordings),
                "task_ids": [],
                "status": "processing",
                "options": batch_options,
                "created_at": datetime.now().isoformat(),
                "completed_at": None,
                "results": [],
                "errors": []
            }

        logger.info(
            "Batch processing started",
            batch_id=batch_id,
            total_recordings=len(recordings),
            options=batch_options
        )

        # Add individual recordings with batch metadata
        for recording in recordings:
            recording_copy = recording.copy()
            recording_copy["batch_id"] = batch_id
            recording_copy["batch_options"] = batch_options

            task_id = self.add_recording(recording_copy)
            if task_id:
                with self.lock:
                    self.batch_tasks[batch_id]["task_ids"].append(task_id)

        return batch_id

    def cancel_batch(self, batch_id: str) -> int:
        """Cancel all pending tasks in a batch.

        Args:
            batch_id: The batch identifier

        Returns:
            Number of tasks cancelled
        """
        cancelled_count = 0

        with self.lock:
            batch_info = self.batch_tasks.get(batch_id)
            if not batch_info:
                logger.warning("Batch not found for cancellation", batch_id=batch_id)
                return 0

            for task_id in batch_info.get("task_ids", []):
                if self.cancel_task(task_id):
                    cancelled_count += 1

            # Update batch status
            batch_info["status"] = "cancelled"
            batch_info["completed_at"] = datetime.now().isoformat()

        logger.info(
            "Batch cancelled",
            batch_id=batch_id,
            cancelled_count=cancelled_count
        )

        return cancelled_count

    def get_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get the status of a batch.

        Args:
            batch_id: The batch identifier

        Returns:
            Dict with batch status information or None if not found
        """
        with self.lock:
            batch_info = self.batch_tasks.get(batch_id)
            if batch_info:
                return batch_info.copy()
        return None

    def set_batch_callback(self, callback: Callable):
        """Set callback for batch progress updates.

        Args:
            callback: Function called with (batch_id, progress_info) on updates
        """
        self.batch_callback = callback

    def _check_batch_completion(self, batch_id: str):
        """Check if a batch is complete and trigger callbacks.

        Called after each task in a batch completes or fails.

        Args:
            batch_id: The batch identifier to check
        """
        with self.lock:
            batch_info = self.batch_tasks.get(batch_id)
            if not batch_info:
                return

            # Count completed/failed from task statuses
            completed = 0
            failed = 0
            pending = 0

            for task_id in batch_info.get("task_ids", []):
                if task_id in self.completed_tasks:
                    completed += 1
                elif task_id in self.failed_tasks:
                    failed += 1
                elif task_id in self.active_tasks:
                    pending += 1
                else:
                    # Task may be queued but not yet started
                    pending += 1

            # Update batch info
            batch_info["completed"] = completed
            batch_info["failed"] = failed
            batch_info["pending"] = batch_info["total"] - completed - failed

            # Check if batch is complete
            if completed + failed >= batch_info["total"]:
                batch_info["status"] = "completed" if failed == 0 else "completed_with_errors"
                batch_info["completed_at"] = datetime.now().isoformat()

                logger.info(
                    "Batch processing complete",
                    batch_id=batch_id,
                    total=batch_info["total"],
                    completed=completed,
                    failed=failed
                )

            # Create progress info for callback
            progress_info = {
                "batch_id": batch_id,
                "total": batch_info["total"],
                "completed": completed,
                "failed": failed,
                "pending": batch_info["pending"],
                "status": batch_info["status"],
                "progress_percent": (completed + failed) / batch_info["total"] * 100 if batch_info["total"] > 0 else 0
            }

        # Trigger batch callback outside lock to prevent deadlocks
        if self.batch_callback:
            try:
                self.batch_callback(batch_id, progress_info)
            except Exception as e:
                logger.error(
                    "Batch callback error",
                    batch_id=batch_id,
                    error=str(e)
                )

    def _record_batch_result(self, batch_id: str, task_id: str, success: bool, result: Any = None, error: str = None):
        """Record the result of a batch task.

        Args:
            batch_id: The batch identifier
            task_id: The task identifier
            success: Whether the task succeeded
            result: The task result (if successful)
            error: The error message (if failed)
        """
        with self.lock:
            batch_info = self.batch_tasks.get(batch_id)
            if not batch_info:
                return

            if success:
                batch_info["results"].append({
                    "task_id": task_id,
                    "result": result
                })
            else:
                batch_info["errors"].append({
                    "task_id": task_id,
                    "error": error
                })

        # Check if batch is complete
        self._check_batch_completion(batch_id)
