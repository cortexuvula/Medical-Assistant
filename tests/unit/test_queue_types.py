"""
Tests for src/processing/queue_types.py

Covers ProcessingTask (total=False, all optional), BatchTaskStatus,
ProcessingStats, and QueueStatus TypedDicts — structure, required keys,
dict instantiation, and annotation presence.
Pure logic — zero mocking required.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.queue_types import (
    ProcessingTask,
    BatchTaskStatus,
    ProcessingStats,
    QueueStatus,
)


# ===========================================================================
# ProcessingTask (total=False — all keys optional)
# ===========================================================================

class TestProcessingTask:
    def test_is_dict_subclass(self):
        assert issubclass(ProcessingTask, dict)

    def test_no_required_keys(self):
        assert len(ProcessingTask.__required_keys__) == 0

    def test_all_keys_are_optional(self):
        expected = {
            "task_id", "recording_id", "audio_data", "patient_name",
            "context", "priority", "batch_id", "queued_at", "retry_count",
            "status", "future", "executor_type", "task_type",
        }
        assert expected.issubset(ProcessingTask.__optional_keys__)

    def test_can_create_empty(self):
        t: ProcessingTask = {}
        assert isinstance(t, dict)

    def test_can_create_with_subset_of_fields(self):
        t: ProcessingTask = {"task_id": "t1", "status": "queued"}
        assert t["task_id"] == "t1"
        assert t["status"] == "queued"

    def test_can_create_with_all_fields(self):
        t: ProcessingTask = {
            "task_id": "t1",
            "recording_id": 42,
            "audio_data": b"audio",
            "patient_name": "Jane",
            "context": "follow-up",
            "priority": "high",
            "batch_id": None,
            "queued_at": 1234567890.0,
            "retry_count": 0,
            "status": "queued",
            "future": None,
            "executor_type": "thread",
            "task_type": "recording",
        }
        assert t["recording_id"] == 42

    def test_has_task_id_in_optional_keys(self):
        assert "task_id" in ProcessingTask.__optional_keys__

    def test_has_batch_id_in_optional_keys(self):
        assert "batch_id" in ProcessingTask.__optional_keys__


# ===========================================================================
# BatchTaskStatus (all required)
# ===========================================================================

class TestBatchTaskStatus:
    def _make(self, **overrides):
        base = {
            "total": 3,
            "completed": 1,
            "failed": 0,
            "tracking_errors": 0,
            "task_ids": ["t1", "t2", "t3"],
        }
        base.update(overrides)
        return base

    def test_is_dict_subclass(self):
        assert issubclass(BatchTaskStatus, dict)

    def test_required_keys(self):
        required = BatchTaskStatus.__required_keys__
        assert "total" in required
        assert "completed" in required
        assert "failed" in required
        assert "tracking_errors" in required
        assert "task_ids" in required

    def test_no_optional_keys(self):
        assert len(BatchTaskStatus.__optional_keys__) == 0

    def test_create_valid_instance(self):
        b: BatchTaskStatus = self._make()
        assert b["total"] == 3
        assert b["completed"] == 1
        assert isinstance(b["task_ids"], list)

    def test_task_ids_is_list(self):
        b: BatchTaskStatus = self._make(task_ids=["t1"])
        assert isinstance(b["task_ids"], list)

    def test_tracking_errors_present(self):
        b: BatchTaskStatus = self._make(tracking_errors=2)
        assert b["tracking_errors"] == 2


# ===========================================================================
# ProcessingStats (all required)
# ===========================================================================

class TestProcessingStats:
    def _make(self, **overrides):
        base = {
            "total_processed": 10,
            "total_failed": 1,
            "total_retried": 2,
            "avg_processing_time": 1.5,
            "last_processing_time": 1.2,
            "uptime": 3600.0,
        }
        base.update(overrides)
        return base

    def test_is_dict_subclass(self):
        assert issubclass(ProcessingStats, dict)

    def test_required_keys_present(self):
        required = ProcessingStats.__required_keys__
        for key in ("total_processed", "total_failed", "total_retried",
                    "avg_processing_time", "last_processing_time", "uptime"):
            assert key in required

    def test_no_optional_keys(self):
        assert len(ProcessingStats.__optional_keys__) == 0

    def test_create_valid_instance(self):
        s: ProcessingStats = self._make()
        assert s["total_processed"] == 10
        assert s["uptime"] == 3600.0

    def test_all_time_fields_present(self):
        s: ProcessingStats = self._make()
        assert "avg_processing_time" in s
        assert "last_processing_time" in s


# ===========================================================================
# QueueStatus (all required)
# ===========================================================================

class TestQueueStatus:
    def _make_stats(self):
        return {
            "total_processed": 0,
            "total_failed": 0,
            "total_retried": 0,
            "avg_processing_time": 0.0,
            "last_processing_time": 0.0,
            "uptime": 0.0,
        }

    def _make(self, **overrides):
        base = {
            "queue_size": 5,
            "active_tasks": 2,
            "active_recording_tasks": 1,
            "active_guideline_tasks": 1,
            "completed_tasks": 10,
            "failed_tasks": 0,
            "stats": self._make_stats(),
            "workers": 4,
            "guideline_workers": 2,
        }
        base.update(overrides)
        return base

    def test_is_dict_subclass(self):
        assert issubclass(QueueStatus, dict)

    def test_required_keys_present(self):
        required = QueueStatus.__required_keys__
        for key in ("queue_size", "active_tasks", "active_recording_tasks",
                    "active_guideline_tasks", "completed_tasks", "failed_tasks",
                    "stats", "workers", "guideline_workers"):
            assert key in required

    def test_no_optional_keys(self):
        assert len(QueueStatus.__optional_keys__) == 0

    def test_create_valid_instance(self):
        q: QueueStatus = self._make()
        assert q["queue_size"] == 5
        assert isinstance(q["stats"], dict)

    def test_stats_field_is_dict(self):
        q: QueueStatus = self._make()
        assert isinstance(q["stats"], dict)

    def test_worker_counts_present(self):
        q: QueueStatus = self._make(workers=8, guideline_workers=4)
        assert q["workers"] == 8
        assert q["guideline_workers"] == 4
