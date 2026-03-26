"""Type definitions for the processing queue system."""
from __future__ import annotations

from typing import TypedDict, Optional, Any, List


class ProcessingTask(TypedDict, total=False):
    """Typed structure for a task in the processing queue."""
    task_id: str
    recording_id: int
    audio_data: Any
    patient_name: str
    context: str
    priority: str
    batch_id: Optional[str]
    queued_at: float
    retry_count: int
    status: str
    future: Any
    executor_type: str
    task_type: str


class BatchTaskStatus(TypedDict):
    """Typed structure for batch processing status tracking."""
    total: int
    completed: int
    failed: int
    tracking_errors: int
    task_ids: List[str]


class ProcessingStats(TypedDict):
    """Typed structure for processing queue statistics."""
    total_processed: int
    total_failed: int
    total_retried: int
    avg_processing_time: float
    last_processing_time: float
    uptime: float


class QueueStatus(TypedDict):
    """Typed structure for overall queue status information."""
    queue_size: int
    active_tasks: int
    active_recording_tasks: int
    active_guideline_tasks: int
    completed_tasks: int
    failed_tasks: int
    stats: ProcessingStats
    workers: int
    guideline_workers: int
