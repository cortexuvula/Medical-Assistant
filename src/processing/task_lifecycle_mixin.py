"""
Task Lifecycle Mixin for ProcessingQueue.

Handles task state transitions including:
- Marking tasks as completed
- Marking tasks as failed
- Pruning old completed/failed tasks
- Updating average processing time statistics

This mixin is designed to be used with ProcessingQueue to keep the main
class focused on core queue operations.
"""

from typing import Dict
from datetime import datetime

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class TaskLifecycleMixin:
    """Mixin providing task lifecycle management for ProcessingQueue."""

    def _mark_completed(self, task_id: str, recording_data: Dict, result: Dict, processing_time: float):
        """Mark a task as completed successfully."""
        # DB FIRST: persist completion before updating memory
        try:
            if self.app and hasattr(self.app, 'db') and self.app.db:
                self.app.db.update_recording(
                    recording_data["recording_id"],
                    processing_status="completed",
                    processing_completed_at=datetime.now()
                )
                self.app.db.update_queue_status(
                    task_id, "completed",
                    completed_at=datetime.now().isoformat()
                )
        except Exception as e:
            logger.error(f"Failed to persist task completion to DB: {e}")

        # MEMORY SECOND
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

        # Add processing time to result for notification
        if isinstance(result, dict):
            result['processing_time'] = processing_time

        # Notify completion (read active_tasks count under lock)
        with self.lock:
            active_count = len(self.active_tasks)
        self._notify_completion(task_id, recording_data, result)
        self._notify_status_update(task_id, "completed", active_count)

        logger.info("Task completed", task_id=task_id, processing_time_seconds=round(processing_time, 2))

        # Prune old tasks to prevent memory growth
        self._prune_completed_tasks()

    def _mark_failed(self, task_id: str, recording_data: Dict, error_msg: str):
        """Mark a task as failed."""
        # DB FIRST: persist failure before updating memory
        try:
            if self.app and hasattr(self.app, 'db') and self.app.db:
                self.app.db.update_recording(
                    recording_data["recording_id"],
                    processing_status="failed",
                    error_message=error_msg
                )
                self.app.db.update_queue_status(
                    task_id, "failed",
                    last_error=error_msg
                )
        except Exception as e:
            logger.error(f"Failed to persist task failure to DB: {e}")

        # MEMORY SECOND
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

        # Notify failure (read active_tasks count under lock)
        with self.lock:
            active_count = len(self.active_tasks)
        self._notify_error(task_id, recording_data, error_msg)
        self._notify_status_update(task_id, "failed", active_count)

        logger.error("Task failed", task_id=task_id, error=error_msg)

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
