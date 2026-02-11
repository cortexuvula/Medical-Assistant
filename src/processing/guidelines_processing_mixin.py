"""
Guidelines Processing Mixin for ProcessingQueue.

Handles batch guideline upload operations including:
- Adding multiple guideline files to the queue as a batch
- Tracking batch progress and completion
- Parallel processing of guideline uploads
- Canceling batch operations
- Progress callbacks to UI

This mixin extends ProcessingQueue to handle guideline uploads in the background,
allowing the UI to remain responsive during long-running bulk uploads.
"""

from typing import Dict, Optional, Callable, Any, List
from datetime import datetime
import uuid
import os
from threading import Event

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class GuidelinesProcessingMixin:
    """Mixin providing background guideline upload capabilities for ProcessingQueue."""

    def _prune_old_batches(self, max_age_hours: float = 2.0):
        """Remove completed/cancelled batch records older than max_age_hours.

        Must be called INSIDE self.lock.
        """
        if not hasattr(self, 'guideline_batches'):
            return

        cutoff = datetime.now() - __import__('datetime').timedelta(hours=max_age_hours)
        to_remove = [
            bid for bid, batch in self.guideline_batches.items()
            if batch.get("status") in ("completed", "cancelled")
            and batch.get("completed_at") is not None
            and batch["completed_at"] < cutoff
        ]
        for bid in to_remove:
            del self.guideline_batches[bid]

        if to_remove:
            logger.debug(f"Pruned {len(to_remove)} old guideline batches")

    def add_guideline_batch(
        self,
        files: List[str],
        options: Dict[str, Any]
    ) -> str:
        """Add multiple guideline files as a batch for processing.

        Args:
            files: List of file paths to upload
            options: Upload options:
                - specialty: Optional[str]
                - source: Optional[str]
                - version: Optional[str]
                - effective_date: Optional[date]
                - document_type: Optional[str]
                - title: Optional[str]
                - extract_recommendations: bool (default True)
                - enable_graph: bool (default True)
                - enable_ocr: bool (default True)
                - continue_on_error: bool (default True)

        Returns:
            batch_id: Unique identifier for the batch

        Raises:
            ValueError: If files list is empty or exceeds MAX_BATCH_SIZE
        """
        if not files:
            raise ValueError("Cannot add empty guideline batch")

        if len(files) > self.MAX_BATCH_SIZE:
            raise ValueError(
                f"Batch size {len(files)} exceeds maximum {self.MAX_BATCH_SIZE}"
            )

        batch_id = str(uuid.uuid4())

        with self.lock:
            # Initialize batch tracking
            if not hasattr(self, 'guideline_batches'):
                self.guideline_batches: Dict[str, Dict] = {}

            # Prune old completed batches to prevent memory growth (Fix 17)
            self._prune_old_batches()

            self.guideline_batches[batch_id] = {
                "batch_id": batch_id,
                "total_files": len(files),
                "processed": 0,
                "successful": 0,
                "failed": 0,
                "skipped": 0,  # Duplicates skipped
                "status": "queued",  # queued, processing, completed, cancelled
                "task_ids": [],
                "file_paths": files.copy(),
                "options": options,
                "created_at": datetime.now(),
                "completed_at": None,
                "errors": [],  # List[Dict[str, str]] with file_path and error_message
                "skipped_files": [],  # List[str] with filenames of skipped duplicates
            }

        logger.info(
            "Guideline batch queued",
            batch_id=batch_id,
            total_files=len(files),
            options=options
        )

        # Queue individual files
        for file_path in files:
            task_id = self.add_guideline_upload(file_path, options, batch_id)
            if task_id:
                with self.lock:
                    self.guideline_batches[batch_id]["task_ids"].append(task_id)

        # Mark batch as processing
        with self.lock:
            if batch_id in self.guideline_batches:
                self.guideline_batches[batch_id]["status"] = "processing"

        return batch_id

    def add_guideline_upload(
        self,
        file_path: str,
        options: Dict[str, Any],
        batch_id: Optional[str] = None
    ) -> Optional[str]:
        """Add a single guideline file to the processing queue.

        Args:
            file_path: Path to guideline file
            options: Upload options
            batch_id: Optional batch identifier

        Returns:
            task_id: Unique identifier for tracking this task
        """
        task_id = str(uuid.uuid4())
        filename = os.path.basename(file_path)

        # Create task data
        task_data = {
            "task_id": task_id,
            "task_type": "guideline_upload",
            "batch_id": batch_id,
            "file_path": file_path,
            "filename": filename,
            "options": options,
            "status": "queued",
            "progress_status": None,
            "progress_percent": 0.0,
            "queued_at": datetime.now(),
            "started_at": None,
            "completed_at": None,
            "error_message": None,
        }

        with self.lock:
            self.active_tasks[task_id] = task_data

        # Add to queue
        priority = options.get("priority", 5)
        self.queue.put((priority, task_id, task_data))

        logger.debug(
            "Guideline upload queued",
            task_id=task_id,
            filename=filename,
            batch_id=batch_id
        )

        return task_id

    def cancel_guideline_batch(self, batch_id: str) -> int:
        """Cancel all pending tasks in a guideline batch.

        Only tasks that haven't started yet can be cancelled.
        Tasks currently being processed will complete.

        Args:
            batch_id: The batch identifier

        Returns:
            Number of tasks cancelled
        """
        cancelled_count = 0

        with self.lock:
            if batch_id not in self.guideline_batches:
                logger.warning("Batch not found for cancellation", batch_id=batch_id)
                return 0

            batch = self.guideline_batches[batch_id]
            task_ids = batch.get("task_ids", [])

            for task_id in task_ids:
                if task_id in self.active_tasks:
                    task = self.active_tasks[task_id]

                    # Can only cancel if not started yet
                    if task.get("status") == "queued":
                        task["status"] = "cancelled"
                        task["error_message"] = "Cancelled by user"
                        cancelled_count += 1

                        # Move to failed tasks
                        self.failed_tasks[task_id] = task
                        del self.active_tasks[task_id]

            # Update batch status
            if cancelled_count > 0:
                batch["status"] = "cancelled"
                batch["failed"] += cancelled_count
                batch["processed"] += cancelled_count

        logger.info(
            "Guideline batch cancellation",
            batch_id=batch_id,
            cancelled=cancelled_count
        )

        return cancelled_count

    def get_guideline_batch_status(self, batch_id: str) -> Optional[Dict]:
        """Get current status of a guideline batch.

        Args:
            batch_id: The batch identifier

        Returns:
            Dictionary with batch status or None if not found
        """
        with self.lock:
            if not hasattr(self, 'guideline_batches'):
                return None

            if batch_id not in self.guideline_batches:
                return None

            # Return a copy to avoid external modification
            return self.guideline_batches[batch_id].copy()

    def set_guideline_progress_callback(self, callback: Optional[Callable]):
        """Register callback for guideline upload progress updates.

        Callback signature: callback(task_id, status, percent, error)

        Args:
            callback: Function to call on progress updates
        """
        self.guideline_progress_callback = callback
        logger.debug("Guideline progress callback registered")

    def _process_guideline_upload(self, task_id: str, task_data: Dict):
        """Process a single guideline upload (runs in worker thread).

        Args:
            task_id: Task identifier
            task_data: Task data dictionary
        """
        from rag.guidelines_upload_manager import get_guidelines_upload_manager
        from rag.guidelines_models import GuidelineUploadStatus

        file_path = task_data["file_path"]
        filename = task_data["filename"]
        options = task_data["options"]
        batch_id = task_data.get("batch_id")

        # Check if cancelled
        with self.lock:
            if task_id in self.active_tasks:
                if self.active_tasks[task_id].get("status") == "cancelled":
                    logger.info("Task cancelled, skipping", task_id=task_id)
                    return
            else:
                # Task was removed (cancelled)
                logger.info("Task not found, skipping", task_id=task_id)
                return

        # Update task status
        with self.lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["status"] = "processing"
                self.active_tasks[task_id]["started_at"] = datetime.now()

        logger.info(
            "Starting guideline upload",
            task_id=task_id,
            filename=filename,
            batch_id=batch_id
        )

        # Define progress callback
        def progress_callback(status: GuidelineUploadStatus, percent: float, error=None):
            """Called by upload manager with progress updates."""
            self._update_guideline_progress(task_id, status, percent, error)

        try:
            manager = get_guidelines_upload_manager()

            # Call upload_guideline with progress callback
            guideline_id = manager.upload_guideline(
                file_path=file_path,
                specialty=options.get("specialty"),
                source=options.get("source"),
                version=options.get("version"),
                effective_date=options.get("effective_date"),
                document_type=options.get("document_type"),
                title=options.get("title"),
                extract_recommendations=options.get("extract_recommendations", True),
                enable_graph=options.get("enable_graph", True),
                enable_ocr=options.get("enable_ocr", True),
                skip_duplicates=options.get("skip_duplicates", True),
                progress_callback=progress_callback,
            )

            # Check if skipped as duplicate
            if guideline_id is None:
                # Skipped duplicate
                self._mark_guideline_task_complete(task_id, batch_id, success=True, skipped=True)
                logger.info(
                    "Guideline skipped (duplicate)",
                    task_id=task_id,
                    filename=filename
                )
            else:
                # Successfully uploaded
                self._mark_guideline_task_complete(task_id, batch_id, success=True)
                logger.info(
                    "Guideline upload completed",
                    task_id=task_id,
                    filename=filename,
                    guideline_id=guideline_id
                )

        except Exception as e:
            logger.error(
                f"Guideline upload failed: {e}",
                task_id=task_id,
                filename=filename,
                exc_info=True
            )
            self._mark_guideline_task_complete(
                task_id,
                batch_id,
                success=False,
                error=str(e)
            )

    def _update_guideline_progress(
        self,
        task_id: str,
        status,
        percent: float,
        error: Optional[str] = None
    ):
        """Update guideline task progress (thread-safe).

        Args:
            task_id: Task identifier
            status: GuidelineUploadStatus enum value
            percent: Progress percentage (0-100)
            error: Optional error message
        """
        # Update task state inside lock
        with self.lock:
            if task_id in self.active_tasks:
                self.active_tasks[task_id]["progress_status"] = status
                self.active_tasks[task_id]["progress_percent"] = percent
                if error:
                    self.active_tasks[task_id]["error_message"] = error

        # Call callback OUTSIDE lock to prevent deadlocks
        if hasattr(self, 'guideline_progress_callback') and self.guideline_progress_callback:
            try:
                # Schedule callback on main thread
                # self.app IS the root ttk.Window, so call .after() on it directly
                if self.app:
                    self.app.after(
                        0,
                        lambda: self.guideline_progress_callback(task_id, status, percent, error)
                    )
            except Exception as e:
                logger.error(f"Error calling guideline progress callback: {e}")

    def _mark_guideline_task_complete(
        self,
        task_id: str,
        batch_id: Optional[str],
        success: bool,
        error: Optional[str] = None,
        skipped: bool = False
    ):
        """Mark a guideline task as complete and update batch status.

        Args:
            task_id: Task identifier
            batch_id: Optional batch identifier
            success: Whether upload succeeded
            error: Optional error message
            skipped: Whether file was skipped as duplicate
        """
        # Store batch info for callback outside lock
        batch_info_for_callback = None
        batch_id_for_callback = None

        with self.lock:
            # Update task status
            if task_id in self.active_tasks:
                task = self.active_tasks[task_id]
                task["status"] = "completed" if success else "failed"
                task["completed_at"] = datetime.now()
                task["skipped"] = skipped

                if error:
                    task["error_message"] = error

                # Move to appropriate collection
                if success:
                    self.completed_tasks[task_id] = task
                else:
                    self.failed_tasks[task_id] = task

                del self.active_tasks[task_id]

            # Update batch if this task belongs to one
            if batch_id and hasattr(self, 'guideline_batches'):
                if batch_id in self.guideline_batches:
                    batch = self.guideline_batches[batch_id]
                    batch["processed"] += 1

                    if success:
                        if skipped:
                            batch["skipped"] += 1
                            # Track skipped filename
                            if task_id in self.completed_tasks:
                                completed_task = self.completed_tasks[task_id]
                                batch["skipped_files"].append(
                                    completed_task.get("filename", "unknown")
                                )
                        else:
                            batch["successful"] += 1
                    else:
                        batch["failed"] += 1

                        # Track error
                        if task_id in self.failed_tasks:
                            failed_task = self.failed_tasks[task_id]
                            batch["errors"].append({
                                "file_path": failed_task.get("file_path", "unknown"),
                                "filename": failed_task.get("filename", "unknown"),
                                "error_message": error or "Unknown error"
                            })

                    # Store batch info copy for callback (inside lock)
                    batch_info_for_callback = batch.copy()
                    batch_id_for_callback = batch_id

                    # Check if batch is complete
                    if batch["processed"] >= batch["total_files"]:
                        self._complete_guideline_batch(batch_id)

        # Call batch progress callback OUTSIDE lock to prevent deadlocks
        if batch_info_for_callback and batch_id_for_callback:
            if hasattr(self, 'batch_callback') and self.batch_callback:
                try:
                    # Schedule callback on main thread
                    # self.app IS the root ttk.Window, so call .after() on it directly
                    if self.app:
                        self.app.after(
                            0,
                            lambda: self.batch_callback(batch_id_for_callback, batch_info_for_callback)
                        )
                except Exception as e:
                    logger.error(f"Error calling batch progress callback: {e}")

    def _complete_guideline_batch(self, batch_id: str):
        """Mark a guideline batch as complete (must be called inside lock).

        Args:
            batch_id: Batch identifier
        """
        # This method should be called while lock is held
        if batch_id not in self.guideline_batches:
            return

        batch = self.guideline_batches[batch_id]

        # Only mark complete if not already cancelled
        if batch["status"] != "cancelled":
            batch["status"] = "completed"

        batch["completed_at"] = datetime.now()

        logger.info(
            "Guideline batch completed",
            batch_id=batch_id,
            successful=batch["successful"],
            failed=batch["failed"],
            total=batch["total_files"]
        )

        # Call batch completion callback if registered
        # Pre-copy batch info while lock is held (this method runs inside lock)
        # to avoid the lambda reading stale data when it executes on the main thread
        if hasattr(self, 'batch_callback') and self.batch_callback:
            batch_info_copy = batch.copy()
            try:
                # self.app IS the root ttk.Window, so call .after() on it directly
                if self.app:
                    self.app.after(
                        0,
                        lambda: self.batch_callback(batch_id, batch_info_copy)
                    )
            except Exception as e:
                logger.error(f"Error calling batch completion callback: {e}")
