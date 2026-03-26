"""
Notification Mixin for ProcessingQueue.

Handles callback notifications including:
- Status update notifications
- Completion notifications
- Error notifications

This mixin is designed to be used with ProcessingQueue to keep the main
class focused on core queue operations.
"""

from typing import Dict

from utils.error_handling import ErrorContext
from utils.structured_logging import get_logger

logger = get_logger(__name__)


class NotificationMixin:
    """Mixin providing notification capabilities for ProcessingQueue."""

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
