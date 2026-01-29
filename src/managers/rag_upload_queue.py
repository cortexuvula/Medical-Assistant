"""
RAG Upload Queue Manager.

Manages async document uploads with queue management and cancellation support.
Allows non-blocking document uploads with progress tracking.
"""

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional

from rag.cancellation import CancellationError, CancellationToken
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class UploadTaskStatus(Enum):
    """Status of an upload task."""
    QUEUED = "queued"
    EXTRACTING = "extracting"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    SYNCING = "syncing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class UploadTask:
    """A single document upload task.

    Attributes:
        task_id: Unique task identifier
        session_id: Session this task belongs to
        file_path: Path to the file being uploaded
        status: Current task status
        progress_percent: Upload progress (0-100)
        error_message: Error message if failed
        document_id: ID of created document (if completed)
        created_at: When the task was created
        started_at: When processing started
        completed_at: When processing completed
    """
    task_id: str
    session_id: str
    file_path: str
    status: UploadTaskStatus = UploadTaskStatus.QUEUED
    progress_percent: float = 0.0
    error_message: Optional[str] = None
    document_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    options: dict = field(default_factory=dict)


@dataclass
class UploadSession:
    """A batch upload session containing multiple tasks.

    Attributes:
        session_id: Unique session identifier
        tasks: List of tasks in this session
        options: Upload options for all tasks
        created_at: When the session was created
        cancellation_token: Token for cancelling this session
    """
    session_id: str
    tasks: list[UploadTask] = field(default_factory=list)
    options: dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    cancellation_token: CancellationToken = field(default_factory=CancellationToken)

    @property
    def total_tasks(self) -> int:
        """Total number of tasks in session."""
        return len(self.tasks)

    @property
    def completed_tasks(self) -> int:
        """Number of completed tasks."""
        return sum(1 for t in self.tasks if t.status == UploadTaskStatus.COMPLETED)

    @property
    def failed_tasks(self) -> int:
        """Number of failed tasks."""
        return sum(1 for t in self.tasks if t.status == UploadTaskStatus.FAILED)

    @property
    def cancelled_tasks(self) -> int:
        """Number of cancelled tasks."""
        return sum(1 for t in self.tasks if t.status == UploadTaskStatus.CANCELLED)

    @property
    def progress_percent(self) -> float:
        """Overall session progress."""
        if not self.tasks:
            return 0.0
        return sum(t.progress_percent for t in self.tasks) / len(self.tasks)

    @property
    def is_complete(self) -> bool:
        """Check if all tasks are done (completed, failed, or cancelled)."""
        terminal_statuses = {
            UploadTaskStatus.COMPLETED,
            UploadTaskStatus.FAILED,
            UploadTaskStatus.CANCELLED,
        }
        return all(t.status in terminal_statuses for t in self.tasks)


@dataclass
class UploadProgressUpdate:
    """Progress update for UI callback.

    Attributes:
        session_id: Session this update belongs to
        task_id: Task this update is for
        file_path: File being processed
        status: Current status
        progress_percent: Progress (0-100)
        message: Human-readable status message
        error: Error message if any
    """
    session_id: str
    task_id: str
    file_path: str
    status: UploadTaskStatus
    progress_percent: float
    message: str = ""
    error: Optional[str] = None


# Type alias for progress callbacks
ProgressCallback = Callable[[UploadProgressUpdate], None]


class RAGUploadQueueManager:
    """Manages async document uploads with queue management.

    Features:
    - Non-blocking uploads using ThreadPoolExecutor
    - Session-based grouping of uploads
    - Per-session cancellation support
    - Progress callbacks for UI updates
    - Automatic cleanup of completed sessions
    """

    # Maximum concurrent uploads
    MAX_CONCURRENT_UPLOADS = 3

    # Session cleanup age (hours)
    SESSION_MAX_AGE_HOURS = 24

    def __init__(self):
        """Initialize the upload queue manager."""
        self._executor = ThreadPoolExecutor(
            max_workers=self.MAX_CONCURRENT_UPLOADS,
            thread_name_prefix="rag_upload_"
        )
        self._sessions: dict[str, UploadSession] = {}
        self._futures: dict[str, Future] = {}
        self._callbacks: dict[str, ProgressCallback] = {}
        self._lock = threading.Lock()

    def queue_upload(
        self,
        files: list[str],
        options: Optional[dict] = None,
        callback: Optional[ProgressCallback] = None,
    ) -> str:
        """Queue files for upload.

        Args:
            files: List of file paths to upload
            options: Upload options (enable_ocr, enable_graph, etc.)
            callback: Optional progress callback

        Returns:
            Session ID for tracking this upload batch
        """
        session_id = str(uuid.uuid4())
        options = options or {}

        # Create session
        session = UploadSession(
            session_id=session_id,
            options=options,
        )

        # Create tasks for each file
        for file_path in files:
            task = UploadTask(
                task_id=str(uuid.uuid4()),
                session_id=session_id,
                file_path=file_path,
                options=options,
            )
            session.tasks.append(task)

        with self._lock:
            self._sessions[session_id] = session
            if callback:
                self._callbacks[session_id] = callback

        # Start processing tasks
        for task in session.tasks:
            future = self._executor.submit(
                self._process_task,
                task,
                session.cancellation_token,
            )
            self._futures[task.task_id] = future

        logger.info(f"Queued {len(files)} files for upload in session {session_id}")
        return session_id

    def cancel_session(self, session_id: str) -> int:
        """Cancel all pending tasks in a session.

        Args:
            session_id: Session to cancel

        Returns:
            Number of tasks that were cancelled
        """
        with self._lock:
            session = self._sessions.get(session_id)
            if not session:
                logger.warning(f"Session {session_id} not found")
                return 0

            # Request cancellation
            session.cancellation_token.cancel("User cancelled upload")

            cancelled_count = 0
            for task in session.tasks:
                if task.status == UploadTaskStatus.QUEUED:
                    task.status = UploadTaskStatus.CANCELLED
                    cancelled_count += 1

                    # Cancel the future if it exists
                    future = self._futures.get(task.task_id)
                    if future:
                        future.cancel()

            logger.info(f"Cancelled {cancelled_count} tasks in session {session_id}")
            return cancelled_count

    def get_session(self, session_id: str) -> Optional[UploadSession]:
        """Get a session by ID.

        Args:
            session_id: Session ID

        Returns:
            UploadSession or None if not found
        """
        with self._lock:
            return self._sessions.get(session_id)

    def get_session_status(self, session_id: str) -> dict:
        """Get status summary for a session.

        Args:
            session_id: Session ID

        Returns:
            Dict with status summary
        """
        session = self.get_session(session_id)
        if not session:
            return {"error": "Session not found"}

        return {
            "session_id": session_id,
            "total_tasks": session.total_tasks,
            "completed_tasks": session.completed_tasks,
            "failed_tasks": session.failed_tasks,
            "cancelled_tasks": session.cancelled_tasks,
            "progress_percent": session.progress_percent,
            "is_complete": session.is_complete,
        }

    def _process_task(
        self,
        task: UploadTask,
        cancellation_token: CancellationToken,
    ) -> None:
        """Process a single upload task.

        Args:
            task: Task to process
            cancellation_token: Cancellation token
        """
        try:
            task.started_at = datetime.now()
            self._emit_progress(task, "Starting upload...")

            # Check for cancellation
            cancellation_token.raise_if_cancelled()

            # Get the document manager
            from managers.rag_document_manager import get_rag_document_manager
            manager = get_rag_document_manager()

            # Upload with async support
            task.status = UploadTaskStatus.EXTRACTING
            task.progress_percent = 10.0
            self._emit_progress(task, "Extracting text...")

            cancellation_token.raise_if_cancelled()

            # Create progress callback for detailed updates
            def upload_progress(status: str, progress: float):
                task.progress_percent = progress
                if "chunking" in status.lower():
                    task.status = UploadTaskStatus.CHUNKING
                elif "embedding" in status.lower():
                    task.status = UploadTaskStatus.EMBEDDING
                elif "sync" in status.lower():
                    task.status = UploadTaskStatus.SYNCING
                self._emit_progress(task, status)
                cancellation_token.raise_if_cancelled()

            # Call the async upload method
            result = manager.upload_document_async(
                task.file_path,
                options=task.options,
                progress_callback=upload_progress,
                cancellation_token=cancellation_token,
            )

            # Mark as completed
            task.status = UploadTaskStatus.COMPLETED
            task.progress_percent = 100.0
            task.document_id = result.get("document_id") if result else None
            task.completed_at = datetime.now()
            self._emit_progress(task, "Upload complete")

            logger.info(f"Task {task.task_id} completed: {task.file_path}")

        except CancellationError as e:
            task.status = UploadTaskStatus.CANCELLED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self._emit_progress(task, "Upload cancelled")
            logger.info(f"Task {task.task_id} cancelled")

        except Exception as e:
            task.status = UploadTaskStatus.FAILED
            task.error_message = str(e)
            task.completed_at = datetime.now()
            self._emit_progress(task, f"Upload failed: {e}")
            logger.error(f"Task {task.task_id} failed: {e}")

    def _emit_progress(self, task: UploadTask, message: str) -> None:
        """Emit progress update for a task.

        Args:
            task: Task being updated
            message: Progress message
        """
        callback = self._callbacks.get(task.session_id)
        if callback:
            try:
                update = UploadProgressUpdate(
                    session_id=task.session_id,
                    task_id=task.task_id,
                    file_path=task.file_path,
                    status=task.status,
                    progress_percent=task.progress_percent,
                    message=message,
                    error=task.error_message,
                )
                callback(update)
            except Exception as e:
                logger.warning(f"Error in progress callback: {e}")

    def cleanup_old_sessions(self) -> int:
        """Remove completed sessions older than SESSION_MAX_AGE_HOURS.

        Returns:
            Number of sessions removed
        """
        from datetime import timedelta

        cutoff = datetime.now() - timedelta(hours=self.SESSION_MAX_AGE_HOURS)
        removed = 0

        with self._lock:
            to_remove = []
            for session_id, session in self._sessions.items():
                if session.is_complete and session.created_at < cutoff:
                    to_remove.append(session_id)

            for session_id in to_remove:
                del self._sessions[session_id]
                self._callbacks.pop(session_id, None)
                removed += 1

        if removed:
            logger.info(f"Cleaned up {removed} old upload sessions")

        return removed

    def shutdown(self):
        """Shutdown the executor and cancel pending tasks."""
        # Cancel all sessions
        with self._lock:
            for session_id in list(self._sessions.keys()):
                session = self._sessions[session_id]
                session.cancellation_token.cancel("Shutdown requested")

        # Shutdown executor
        self._executor.shutdown(wait=False)
        logger.info("RAG upload queue manager shutdown")


# Singleton instance
_upload_queue_manager: Optional[RAGUploadQueueManager] = None


def get_rag_upload_queue_manager() -> RAGUploadQueueManager:
    """Get the global RAG upload queue manager.

    Returns:
        RAGUploadQueueManager instance
    """
    global _upload_queue_manager
    if _upload_queue_manager is None:
        _upload_queue_manager = RAGUploadQueueManager()
    return _upload_queue_manager


def reset_rag_upload_queue_manager():
    """Reset the global RAG upload queue manager."""
    global _upload_queue_manager
    if _upload_queue_manager:
        _upload_queue_manager.shutdown()
        _upload_queue_manager = None
