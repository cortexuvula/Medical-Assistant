"""
Tests for src/processing/batch_processing_mixin.py

Covers BatchProcessingMixin: add_batch_recordings (batch_id, size limit,
tracking init, callback dispatch), cancel_batch, get_batch_status,
set_batch_callback, and _check_batch_completion.
Uses a minimal concrete subclass — no DB, no Tkinter.
"""

import sys
import threading
import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.batch_processing_mixin import BatchProcessingMixin


# ---------------------------------------------------------------------------
# Concrete test class
# ---------------------------------------------------------------------------

class _Batcher(BatchProcessingMixin):
    MAX_BATCH_SIZE = 5

    def __init__(self):
        self.lock = threading.Lock()
        self.batch_tasks: dict = {}
        self.batch_callback = None
        self.app = None
        self.active_tasks: dict = {}
        self._recording_to_task: dict = {}
        self._counter = 0

    def add_recording(self, recording_data):
        """Stub: enqueue and return a deterministic task_id."""
        self._counter += 1
        task_id = f"task_{self._counter}"
        self.active_tasks[task_id] = dict(recording_data)
        return task_id


def _recordings(n):
    return [{"recording_id": i, "audio_data": None} for i in range(1, n + 1)]


# ===========================================================================
# add_batch_recordings
# ===========================================================================

class TestAddBatchRecordings:
    def test_returns_string_batch_id(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(2))
        assert isinstance(batch_id, str)
        assert len(batch_id) > 0

    def test_each_call_generates_unique_batch_id(self):
        b = _Batcher()
        id1 = b.add_batch_recordings(_recordings(1))
        id2 = b.add_batch_recordings(_recordings(1))
        assert id1 != id2

    def test_raises_value_error_when_batch_too_large(self):
        b = _Batcher()  # MAX=5
        with pytest.raises(ValueError, match="exceeds maximum"):
            b.add_batch_recordings(_recordings(6))

    def test_accepts_batch_at_exact_max_size(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(5))
        assert batch_id is not None

    def test_initializes_batch_tracking_total(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(3))
        assert b.batch_tasks[batch_id]["total"] == 3

    def test_initializes_completed_and_failed_to_zero(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(2))
        assert b.batch_tasks[batch_id]["completed"] == 0
        assert b.batch_tasks[batch_id]["failed"] == 0

    def test_injects_batch_id_into_each_recording(self):
        b = _Batcher()
        recs = _recordings(2)
        batch_id = b.add_batch_recordings(recs)
        for rec in recs:
            assert rec["batch_id"] == batch_id

    def test_uses_batch_options_priority(self):
        b = _Batcher()
        recs = _recordings(1)
        b.add_batch_recordings(recs, batch_options={"priority": 9})
        assert recs[0]["priority"] == 9

    def test_calls_batch_callback_on_start(self):
        cb = MagicMock()
        b = _Batcher()
        b.batch_callback = cb
        b.add_batch_recordings(_recordings(2))
        cb.assert_called_once()
        args = cb.call_args[0]
        assert args[0] == "started"

    def test_batch_callback_not_called_when_none(self):
        b = _Batcher()
        b.batch_callback = None
        # Should not raise
        b.add_batch_recordings(_recordings(1))

    def test_batch_callback_exception_is_suppressed(self):
        b = _Batcher()
        b.batch_callback = MagicMock(side_effect=RuntimeError("boom"))
        # Must not propagate
        batch_id = b.add_batch_recordings(_recordings(1))
        assert batch_id is not None


# ===========================================================================
# cancel_batch
# ===========================================================================

class TestCancelBatch:
    def test_returns_zero_when_batch_not_found(self):
        b = _Batcher()
        result = b.cancel_batch("nonexistent")
        assert result == 0

    def test_cancels_queued_tasks(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(2))
        # Mark tasks as queued
        for task_id, task in b.active_tasks.items():
            task["status"] = "queued"
            task["batch_id"] = batch_id
        b.batch_tasks[batch_id]["task_ids"] = list(b.active_tasks.keys())
        cancelled = b.cancel_batch(batch_id)
        assert cancelled == 2

    def test_cancelled_tasks_removed_from_active(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(1))
        for task_id, task in b.active_tasks.items():
            task["status"] = "queued"
            task["batch_id"] = batch_id
        b.batch_tasks[batch_id]["task_ids"] = list(b.active_tasks.keys())
        b.cancel_batch(batch_id)
        assert len(b.active_tasks) == 0

    def test_non_queued_tasks_not_cancelled(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(1))
        # Mark as processing (not queued, no future)
        for task_id, task in b.active_tasks.items():
            task["status"] = "processing"
            task["batch_id"] = batch_id
        b.batch_tasks[batch_id]["task_ids"] = list(b.active_tasks.keys())
        cancelled = b.cancel_batch(batch_id)
        assert cancelled == 0


# ===========================================================================
# get_batch_status
# ===========================================================================

class TestGetBatchStatus:
    def test_returns_none_when_batch_not_found(self):
        b = _Batcher()
        assert b.get_batch_status("nope") is None

    def test_returns_dict_with_expected_keys(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(3))
        status = b.get_batch_status(batch_id)
        for key in ("batch_id", "total", "completed", "failed", "in_progress"):
            assert key in status

    def test_in_progress_computed_correctly(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(5))
        b.batch_tasks[batch_id]["completed"] = 2
        b.batch_tasks[batch_id]["failed"] = 1
        status = b.get_batch_status(batch_id)
        assert status["in_progress"] == 2  # 5 - 2 - 1

    def test_total_matches_recording_count(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(4))
        status = b.get_batch_status(batch_id)
        assert status["total"] == 4

    def test_batch_id_in_status(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(1))
        status = b.get_batch_status(batch_id)
        assert status["batch_id"] == batch_id


# ===========================================================================
# set_batch_callback
# ===========================================================================

class TestSetBatchCallback:
    def test_sets_batch_callback(self):
        b = _Batcher()
        cb = MagicMock()
        b.set_batch_callback(cb)
        assert b.batch_callback is cb

    def test_replaces_existing_callback(self):
        b = _Batcher()
        old_cb = MagicMock()
        new_cb = MagicMock()
        b.set_batch_callback(old_cb)
        b.set_batch_callback(new_cb)
        assert b.batch_callback is new_cb


# ===========================================================================
# _check_batch_completion
# ===========================================================================

class TestCheckBatchCompletion:
    def test_no_error_when_batch_not_found(self):
        b = _Batcher()
        b._check_batch_completion("nonexistent")  # should not raise

    def test_notifies_progress_callback(self):
        cb = MagicMock()
        b = _Batcher()
        b.batch_callback = cb
        batch_id = b.add_batch_recordings(_recordings(3))
        b.batch_tasks[batch_id]["completed"] = 1
        cb.reset_mock()
        b._check_batch_completion(batch_id)
        # "progress" event should be sent
        progress_calls = [c for c in cb.call_args_list if c.args[0] == "progress"]
        assert len(progress_calls) >= 1

    def test_sets_completed_at_when_batch_done(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(2))
        b.batch_tasks[batch_id]["completed"] = 2
        b.batch_tasks[batch_id]["failed"] = 0
        b._check_batch_completion(batch_id)
        assert "completed_at" in b.batch_tasks[batch_id]

    def test_notifies_completed_callback_when_done(self):
        cb = MagicMock()
        b = _Batcher()
        b.batch_callback = cb
        batch_id = b.add_batch_recordings(_recordings(2))
        b.batch_tasks[batch_id]["completed"] = 2
        cb.reset_mock()
        b._check_batch_completion(batch_id)
        completed_calls = [c for c in cb.call_args_list if c.args[0] == "completed"]
        assert len(completed_calls) == 1

    def test_duration_set_when_batch_completes(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(1))
        b.batch_tasks[batch_id]["completed"] = 1
        b._check_batch_completion(batch_id)
        assert b.batch_tasks[batch_id].get("duration") is not None
        assert b.batch_tasks[batch_id]["duration"] >= 0

    def test_not_completed_when_still_in_progress(self):
        b = _Batcher()
        batch_id = b.add_batch_recordings(_recordings(3))
        b.batch_tasks[batch_id]["completed"] = 1
        b.batch_tasks[batch_id]["failed"] = 0
        b._check_batch_completion(batch_id)
        assert "completed_at" not in b.batch_tasks[batch_id]
