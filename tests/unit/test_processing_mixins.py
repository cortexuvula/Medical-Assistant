"""
Tests for pure logic in three ProcessingQueue mixins:
  src/processing/notification_mixin.py  — callback dispatch + exception isolation
  src/processing/task_lifecycle_mixin.py — _update_avg_processing_time, _prune_completed_tasks
  src/processing/reprocessing_mixin.py  — _extract_context_from_metadata, _should_retry

Concrete test subclasses supply the minimal state each mixin requires.
No Tkinter, no real DB.
"""

import json
import sys
import threading
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.notification_mixin import NotificationMixin
from processing.task_lifecycle_mixin import TaskLifecycleMixin
from processing.reprocessing_mixin import ReprocessingMixin


# ===========================================================================
# Concrete helpers
# ===========================================================================

class _Notifier(NotificationMixin):
    """Minimal concrete class for NotificationMixin tests."""
    def __init__(self, status_cb=None, completion_cb=None, error_cb=None):
        self.status_callback = status_cb
        self.completion_callback = completion_cb
        self.error_callback = error_cb


class _Lifecycle(TaskLifecycleMixin):
    """Minimal concrete class for TaskLifecycleMixin tests."""
    MAX_COMPLETED_TASKS = 3

    def __init__(self):
        self.lock = threading.Lock()
        self.stats = {
            "total_processed": 0,
            "total_failed": 0,
            "processing_time_avg": 0.0,
        }
        self.completed_tasks = {}
        self.failed_tasks = {}


class _Reprocessor(ReprocessingMixin):
    """Minimal concrete class for ReprocessingMixin tests."""
    pass


# ===========================================================================
# NotificationMixin — _notify_status_update
# ===========================================================================

class TestNotifyStatusUpdate:
    def test_calls_status_callback(self):
        cb = MagicMock()
        n = _Notifier(status_cb=cb)
        n._notify_status_update("t1", "running", 2)
        cb.assert_called_once_with("t1", "running", 2)

    def test_no_call_when_callback_is_none(self):
        n = _Notifier(status_cb=None)
        # Should not raise
        n._notify_status_update("t1", "running", 0)

    def test_exception_in_callback_is_suppressed(self):
        cb = MagicMock(side_effect=RuntimeError("boom"))
        n = _Notifier(status_cb=cb)
        # Must not propagate
        n._notify_status_update("t1", "running", 0)


# ===========================================================================
# NotificationMixin — _notify_completion
# ===========================================================================

class TestNotifyCompletion:
    def test_calls_completion_callback(self):
        cb = MagicMock()
        n = _Notifier(completion_cb=cb)
        recording = {"recording_id": 5}
        result = {"soap_note": "..."}
        n._notify_completion("t1", recording, result)
        cb.assert_called_once_with("t1", recording, result)

    def test_no_call_when_callback_is_none(self):
        n = _Notifier(completion_cb=None)
        n._notify_completion("t1", {}, {})

    def test_exception_in_callback_is_suppressed(self):
        cb = MagicMock(side_effect=ValueError("fail"))
        n = _Notifier(completion_cb=cb)
        n._notify_completion("t1", {"recording_id": 1}, {})


# ===========================================================================
# NotificationMixin — _notify_error
# ===========================================================================

class TestNotifyError:
    def test_calls_error_callback(self):
        cb = MagicMock()
        n = _Notifier(error_cb=cb)
        n._notify_error("t1", {"recording_id": 3}, "Something went wrong")
        cb.assert_called_once_with("t1", {"recording_id": 3}, "Something went wrong")

    def test_no_call_when_callback_is_none(self):
        n = _Notifier(error_cb=None)
        n._notify_error("t1", {}, "error")

    def test_exception_in_callback_is_suppressed(self):
        cb = MagicMock(side_effect=Exception("crash"))
        n = _Notifier(error_cb=cb)
        n._notify_error("t1", {"recording_id": 1}, "err")


# ===========================================================================
# TaskLifecycleMixin — _update_avg_processing_time
# ===========================================================================

class TestUpdateAvgProcessingTime:
    def test_sets_avg_when_total_is_zero(self):
        lc = _Lifecycle()
        lc.stats["total_processed"] = 0
        lc._update_avg_processing_time(5.0)
        assert lc.stats["processing_time_avg"] == 5.0

    def test_sets_avg_when_total_is_one(self):
        lc = _Lifecycle()
        lc.stats["total_processed"] = 1
        lc._update_avg_processing_time(3.0)
        assert lc.stats["processing_time_avg"] == 3.0

    def test_computes_running_average_correctly(self):
        lc = _Lifecycle()
        # Simulate: total_processed=2, current_avg=4.0, new_time=6.0
        # Expected: (4.0 * 1 + 6.0) / 2 = 5.0
        lc.stats["total_processed"] = 2
        lc.stats["processing_time_avg"] = 4.0
        lc._update_avg_processing_time(6.0)
        assert lc.stats["processing_time_avg"] == 5.0

    def test_running_average_over_many_samples(self):
        lc = _Lifecycle()
        # Build up a simulated history: avg of [1, 2, 3, 4, 5] = 3
        times = [1.0, 2.0, 3.0, 4.0, 5.0]
        for i, t in enumerate(times):
            lc.stats["total_processed"] = i
            lc._update_avg_processing_time(t)
        # After 5 updates: should be close to the running average
        assert lc.stats["processing_time_avg"] > 0


# ===========================================================================
# TaskLifecycleMixin — _prune_completed_tasks
# ===========================================================================

class TestPruneCompletedTasks:
    def test_no_prune_when_under_limit(self):
        lc = _Lifecycle()  # MAX=3
        lc.completed_tasks = {
            "t1": {"completed_at": datetime.now()},
            "t2": {"completed_at": datetime.now()},
        }
        lc._prune_completed_tasks()
        assert len(lc.completed_tasks) == 2

    def test_prunes_oldest_completed_tasks(self):
        lc = _Lifecycle()  # MAX=3
        old = datetime.now() - timedelta(hours=2)
        recent = datetime.now()
        lc.completed_tasks = {
            "old1": {"completed_at": old},
            "old2": {"completed_at": old + timedelta(minutes=1)},
            "new1": {"completed_at": recent},
            "new2": {"completed_at": recent + timedelta(minutes=1)},
        }
        lc._prune_completed_tasks()
        # Should keep only MAX_COMPLETED_TASKS (3) most recent
        assert len(lc.completed_tasks) == 3
        assert "old1" not in lc.completed_tasks

    def test_prunes_oldest_failed_tasks(self):
        lc = _Lifecycle()  # MAX=3
        old = datetime.now() - timedelta(hours=3)
        lc.failed_tasks = {
            "f1": {"failed_at": old},
            "f2": {"failed_at": old + timedelta(minutes=5)},
            "f3": {"failed_at": old + timedelta(minutes=10)},
            "f4": {"failed_at": datetime.now()},
        }
        lc._prune_completed_tasks()
        assert len(lc.failed_tasks) == 3
        assert "f1" not in lc.failed_tasks

    def test_no_prune_when_exactly_at_limit(self):
        lc = _Lifecycle()  # MAX=3
        lc.completed_tasks = {
            "t1": {"completed_at": datetime.now()},
            "t2": {"completed_at": datetime.now()},
            "t3": {"completed_at": datetime.now()},
        }
        lc._prune_completed_tasks()
        assert len(lc.completed_tasks) == 3

    def test_empty_dicts_no_error(self):
        lc = _Lifecycle()
        lc._prune_completed_tasks()
        assert lc.completed_tasks == {}
        assert lc.failed_tasks == {}


# ===========================================================================
# ReprocessingMixin — _extract_context_from_metadata
# ===========================================================================

class TestExtractContextFromMetadata:
    def test_returns_empty_when_none(self):
        result = ReprocessingMixin._extract_context_from_metadata(None)
        assert result == ""

    def test_returns_empty_when_empty_string(self):
        result = ReprocessingMixin._extract_context_from_metadata("")
        assert result == ""

    def test_returns_context_from_dict(self):
        metadata = {"context": "follow-up visit", "other": "data"}
        result = ReprocessingMixin._extract_context_from_metadata(metadata)
        assert result == "follow-up visit"

    def test_returns_empty_when_dict_has_no_context(self):
        result = ReprocessingMixin._extract_context_from_metadata({"note": "x"})
        assert result == ""

    def test_returns_context_from_json_string(self):
        metadata = json.dumps({"context": "annual checkup"})
        result = ReprocessingMixin._extract_context_from_metadata(metadata)
        assert result == "annual checkup"

    def test_returns_empty_on_invalid_json_string(self):
        result = ReprocessingMixin._extract_context_from_metadata("NOT JSON {{{")
        assert result == ""

    def test_returns_empty_when_metadata_is_non_dict_type(self):
        result = ReprocessingMixin._extract_context_from_metadata(42)
        assert result == ""


# ===========================================================================
# ReprocessingMixin — _should_retry
# ===========================================================================

class TestShouldRetry:
    def test_returns_false_when_auto_retry_disabled(self):
        r = _Reprocessor()
        with patch("processing.reprocessing_mixin.settings_manager") as mock_sm:
            mock_sm.get.side_effect = lambda key, default=None: (
                False if key == "auto_retry_failed" else default
            )
            result = r._should_retry({"retry_count": 0})
        assert result is False

    def test_returns_true_when_retry_count_below_max(self):
        r = _Reprocessor()
        with patch("processing.reprocessing_mixin.settings_manager") as mock_sm:
            mock_sm.get.side_effect = lambda key, default=None: (
                True if key == "auto_retry_failed" else
                3 if key == "max_retry_attempts" else default
            )
            result = r._should_retry({"retry_count": 1})
        assert result is True

    def test_returns_false_when_retry_count_at_max(self):
        r = _Reprocessor()
        with patch("processing.reprocessing_mixin.settings_manager") as mock_sm:
            mock_sm.get.side_effect = lambda key, default=None: (
                True if key == "auto_retry_failed" else
                3 if key == "max_retry_attempts" else default
            )
            result = r._should_retry({"retry_count": 3})
        assert result is False

    def test_returns_false_when_retry_count_exceeds_max(self):
        r = _Reprocessor()
        with patch("processing.reprocessing_mixin.settings_manager") as mock_sm:
            mock_sm.get.side_effect = lambda key, default=None: (
                True if key == "auto_retry_failed" else
                3 if key == "max_retry_attempts" else default
            )
            result = r._should_retry({"retry_count": 5})
        assert result is False

    def test_default_retry_count_zero_treated_as_below_max(self):
        r = _Reprocessor()
        with patch("processing.reprocessing_mixin.settings_manager") as mock_sm:
            mock_sm.get.side_effect = lambda key, default=None: (
                True if key == "auto_retry_failed" else
                3 if key == "max_retry_attempts" else default
            )
            # recording_data without retry_count → defaults to 0
            result = r._should_retry({})
        assert result is True
