"""
Tests for src/processing/guidelines_processing_mixin.py

Covers GuidelinesProcessingMixin: _prune_old_batches, add_guideline_batch
(validation + batch init), add_guideline_upload, cancel_guideline_batch,
get_guideline_batch_status, set_guideline_progress_callback,
_complete_guideline_batch, and _mark_guideline_task_complete.
Uses a minimal concrete subclass — no Tkinter, no RAG/DB.
"""

import sys
import threading
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.guidelines_processing_mixin import GuidelinesProcessingMixin


# ---------------------------------------------------------------------------
# Minimal concrete subclass
# ---------------------------------------------------------------------------

class _Guide(GuidelinesProcessingMixin):
    MAX_BATCH_SIZE = 5

    def __init__(self):
        self.lock = threading.Lock()
        self.guideline_batches: dict = {}
        self.active_tasks: dict = {}
        self.completed_tasks: dict = {}
        self.failed_tasks: dict = {}
        self.app = None                 # Skip Tkinter .after() calls
        self.queue = MagicMock()        # absorb queue.put()


def _files(n):
    return [f"/tmp/file_{i}.pdf" for i in range(1, n + 1)]


def _make_batch(g, n=2):
    """Helper: add a batch to g and return batch_id."""
    return g.add_guideline_batch(_files(n), {})


# ===========================================================================
# _prune_old_batches
# ===========================================================================

class TestPruneOldBatches:
    def test_no_op_when_no_attribute(self):
        g = _Guide()
        del g.guideline_batches          # Remove the attribute
        g._prune_old_batches()           # Should not raise

    def test_no_pruning_when_no_completed_batches(self):
        g = _Guide()
        g.guideline_batches = {
            "b1": {"status": "processing", "completed_at": None}
        }
        g._prune_old_batches()
        assert "b1" in g.guideline_batches

    def test_prunes_old_completed_batch(self):
        g = _Guide()
        old_time = datetime.now() - timedelta(hours=3)
        g.guideline_batches = {
            "old": {"status": "completed", "completed_at": old_time}
        }
        g._prune_old_batches(max_age_hours=2.0)
        assert "old" not in g.guideline_batches

    def test_prunes_old_cancelled_batch(self):
        g = _Guide()
        old_time = datetime.now() - timedelta(hours=5)
        g.guideline_batches = {
            "b": {"status": "cancelled", "completed_at": old_time}
        }
        g._prune_old_batches(max_age_hours=2.0)
        assert "b" not in g.guideline_batches

    def test_keeps_recent_completed_batch(self):
        g = _Guide()
        recent = datetime.now() - timedelta(minutes=30)
        g.guideline_batches = {
            "new": {"status": "completed", "completed_at": recent}
        }
        g._prune_old_batches(max_age_hours=2.0)
        assert "new" in g.guideline_batches

    def test_prunes_old_but_keeps_recent(self):
        g = _Guide()
        old_time = datetime.now() - timedelta(hours=4)
        recent = datetime.now() - timedelta(minutes=10)
        g.guideline_batches = {
            "old": {"status": "completed", "completed_at": old_time},
            "new": {"status": "completed", "completed_at": recent},
        }
        g._prune_old_batches(max_age_hours=2.0)
        assert "old" not in g.guideline_batches
        assert "new" in g.guideline_batches


# ===========================================================================
# add_guideline_batch — validation
# ===========================================================================

class TestAddGuidelineBatchValidation:
    def test_raises_when_files_is_empty(self):
        g = _Guide()
        with pytest.raises(ValueError, match="empty"):
            g.add_guideline_batch([], {})

    def test_raises_when_batch_too_large(self):
        g = _Guide()
        with pytest.raises(ValueError, match="exceeds maximum"):
            g.add_guideline_batch(_files(6), {})

    def test_accepts_exactly_max_batch_size(self):
        g = _Guide()
        batch_id = g.add_guideline_batch(_files(5), {})
        assert batch_id is not None

    def test_accepts_single_file(self):
        g = _Guide()
        batch_id = g.add_guideline_batch(_files(1), {})
        assert batch_id is not None


# ===========================================================================
# add_guideline_batch — batch init
# ===========================================================================

class TestAddGuidelineBatchInit:
    def test_returns_string_batch_id(self):
        g = _Guide()
        batch_id = _make_batch(g)
        assert isinstance(batch_id, str) and len(batch_id) > 0

    def test_each_call_returns_unique_id(self):
        g = _Guide()
        id1 = _make_batch(g, 1)
        id2 = _make_batch(g, 1)
        assert id1 != id2

    def test_total_files_correct(self):
        g = _Guide()
        batch_id = _make_batch(g, 3)
        assert g.guideline_batches[batch_id]["total_files"] == 3

    def test_counters_initialized_to_zero(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        b = g.guideline_batches[batch_id]
        assert b["processed"] == 0
        assert b["successful"] == 0
        assert b["failed"] == 0
        assert b["skipped"] == 0

    def test_status_set_to_processing(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        assert g.guideline_batches[batch_id]["status"] == "processing"

    def test_file_paths_stored(self):
        g = _Guide()
        files = _files(2)
        batch_id = g.add_guideline_batch(files, {})
        assert g.guideline_batches[batch_id]["file_paths"] == files

    def test_errors_and_skipped_files_empty(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        b = g.guideline_batches[batch_id]
        assert b["errors"] == []
        assert b["skipped_files"] == []

    def test_options_stored(self):
        g = _Guide()
        opts = {"specialty": "cardiology", "enable_ocr": False}
        batch_id = g.add_guideline_batch(_files(1), opts)
        assert g.guideline_batches[batch_id]["options"] == opts


# ===========================================================================
# add_guideline_upload
# ===========================================================================

class TestAddGuidelineUpload:
    def test_returns_string_task_id(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/file.pdf", {})
        assert isinstance(task_id, str) and len(task_id) > 0

    def test_adds_task_to_active_tasks(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/file.pdf", {})
        assert task_id in g.active_tasks

    def test_task_has_correct_task_type(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/file.pdf", {})
        assert g.active_tasks[task_id]["task_type"] == "guideline_upload"

    def test_task_has_queued_status(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/file.pdf", {})
        assert g.active_tasks[task_id]["status"] == "queued"

    def test_task_filename_extracted_from_path(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/some/deep/path/report.pdf", {})
        assert g.active_tasks[task_id]["filename"] == "report.pdf"

    def test_batch_id_stored_in_task(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/file.pdf", {}, batch_id="batch-123")
        assert g.active_tasks[task_id]["batch_id"] == "batch-123"

    def test_task_progress_starts_at_zero(self):
        g = _Guide()
        task_id = g.add_guideline_upload("/tmp/file.pdf", {})
        assert g.active_tasks[task_id]["progress_percent"] == 0.0

    def test_queue_put_called(self):
        g = _Guide()
        g.add_guideline_upload("/tmp/file.pdf", {})
        g.queue.put.assert_called_once()


# ===========================================================================
# cancel_guideline_batch
# ===========================================================================

class TestCancelGuidelineBatch:
    def test_returns_zero_when_batch_not_found(self):
        g = _Guide()
        assert g.cancel_guideline_batch("nonexistent") == 0

    def test_cancels_queued_tasks(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        # Mark tasks as queued (they already are)
        for tid in list(g.active_tasks):
            if g.active_tasks[tid].get("batch_id") == batch_id:
                g.active_tasks[tid]["status"] = "queued"
        cancelled = g.cancel_guideline_batch(batch_id)
        assert cancelled == 2

    def test_cancelled_tasks_removed_from_active(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        g.cancel_guideline_batch(batch_id)
        # All tasks for this batch should be gone from active_tasks
        remaining = [
            t for t in g.active_tasks.values()
            if t.get("batch_id") == batch_id and t["status"] == "queued"
        ]
        assert len(remaining) == 0

    def test_non_queued_tasks_not_cancelled(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        for tid in list(g.active_tasks):
            g.active_tasks[tid]["status"] = "processing"
        cancelled = g.cancel_guideline_batch(batch_id)
        assert cancelled == 0

    def test_batch_status_set_to_cancelled(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        g.cancel_guideline_batch(batch_id)
        assert g.guideline_batches[batch_id]["status"] == "cancelled"


# ===========================================================================
# get_guideline_batch_status
# ===========================================================================

class TestGetGuidelineBatchStatus:
    def test_returns_none_when_no_attribute(self):
        g = _Guide()
        del g.guideline_batches
        assert g.get_guideline_batch_status("b1") is None

    def test_returns_none_when_batch_not_found(self):
        g = _Guide()
        assert g.get_guideline_batch_status("nonexistent") is None

    def test_returns_dict_for_known_batch(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        result = g.get_guideline_batch_status(batch_id)
        assert isinstance(result, dict)

    def test_returned_dict_has_batch_id(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        result = g.get_guideline_batch_status(batch_id)
        assert result["batch_id"] == batch_id

    def test_returns_copy_not_reference(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        result = g.get_guideline_batch_status(batch_id)
        result["status"] = "MUTATED"
        # Original should be unaffected
        assert g.guideline_batches[batch_id]["status"] != "MUTATED"


# ===========================================================================
# set_guideline_progress_callback
# ===========================================================================

class TestSetGuidelineProgressCallback:
    def test_sets_callback(self):
        g = _Guide()
        cb = MagicMock()
        g.set_guideline_progress_callback(cb)
        assert g.guideline_progress_callback is cb

    def test_replaces_existing_callback(self):
        g = _Guide()
        old_cb = MagicMock()
        new_cb = MagicMock()
        g.set_guideline_progress_callback(old_cb)
        g.set_guideline_progress_callback(new_cb)
        assert g.guideline_progress_callback is new_cb

    def test_accepts_none(self):
        g = _Guide()
        g.set_guideline_progress_callback(None)
        assert g.guideline_progress_callback is None


# ===========================================================================
# _complete_guideline_batch
# ===========================================================================

class TestCompleteGuidelineBatch:
    def test_no_op_when_batch_not_found(self):
        g = _Guide()
        g._complete_guideline_batch("nonexistent")   # Should not raise

    def test_sets_status_to_completed(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        g.guideline_batches[batch_id]["status"] = "processing"
        with g.lock:
            g._complete_guideline_batch(batch_id)
        assert g.guideline_batches[batch_id]["status"] == "completed"

    def test_sets_completed_at(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        with g.lock:
            g._complete_guideline_batch(batch_id)
        assert g.guideline_batches[batch_id]["completed_at"] is not None

    def test_does_not_override_cancelled_status(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        g.guideline_batches[batch_id]["status"] = "cancelled"
        with g.lock:
            g._complete_guideline_batch(batch_id)
        assert g.guideline_batches[batch_id]["status"] == "cancelled"

    def test_completed_at_set_even_for_cancelled(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        g.guideline_batches[batch_id]["status"] = "cancelled"
        with g.lock:
            g._complete_guideline_batch(batch_id)
        assert g.guideline_batches[batch_id]["completed_at"] is not None


# ===========================================================================
# _mark_guideline_task_complete
# ===========================================================================

class TestMarkGuidelineTaskComplete:
    def _setup_task(self, g, batch_id=None):
        """Create a task in active_tasks and return its task_id."""
        task_id = "task-1"
        g.active_tasks[task_id] = {
            "task_id": task_id,
            "status": "processing",
            "file_path": "/tmp/file.pdf",
            "filename": "file.pdf",
            "batch_id": batch_id,
            "error_message": None,
        }
        return task_id

    def test_moves_task_to_completed_on_success(self):
        g = _Guide()
        task_id = self._setup_task(g)
        g._mark_guideline_task_complete(task_id, None, success=True)
        assert task_id in g.completed_tasks
        assert task_id not in g.active_tasks

    def test_moves_task_to_failed_on_failure(self):
        g = _Guide()
        task_id = self._setup_task(g)
        g._mark_guideline_task_complete(task_id, None, success=False)
        assert task_id in g.failed_tasks
        assert task_id not in g.active_tasks

    def test_task_status_set_to_completed(self):
        g = _Guide()
        task_id = self._setup_task(g)
        g._mark_guideline_task_complete(task_id, None, success=True)
        assert g.completed_tasks[task_id]["status"] == "completed"

    def test_task_status_set_to_failed(self):
        g = _Guide()
        task_id = self._setup_task(g)
        g._mark_guideline_task_complete(task_id, None, success=False, error="bad error")
        assert g.failed_tasks[task_id]["status"] == "failed"
        assert g.failed_tasks[task_id]["error_message"] == "bad error"

    def test_increments_batch_successful(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        task_id = self._setup_task(g, batch_id=batch_id)
        g.guideline_batches[batch_id]["task_ids"].append(task_id)
        g.guideline_batches[batch_id]["total_files"] = 3  # not all done yet
        g._mark_guideline_task_complete(task_id, batch_id, success=True)
        assert g.guideline_batches[batch_id]["successful"] == 1

    def test_increments_batch_failed(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        task_id = self._setup_task(g, batch_id=batch_id)
        g.guideline_batches[batch_id]["task_ids"].append(task_id)
        g.guideline_batches[batch_id]["total_files"] = 3  # not all done yet
        g._mark_guideline_task_complete(task_id, batch_id, success=False)
        assert g.guideline_batches[batch_id]["failed"] == 1

    def test_increments_batch_skipped(self):
        g = _Guide()
        batch_id = _make_batch(g, 2)
        task_id = self._setup_task(g, batch_id=batch_id)
        g.guideline_batches[batch_id]["task_ids"].append(task_id)
        g.guideline_batches[batch_id]["total_files"] = 3  # not all done yet
        g._mark_guideline_task_complete(task_id, batch_id, success=True, skipped=True)
        assert g.guideline_batches[batch_id]["skipped"] == 1

    def test_completes_batch_when_all_processed(self):
        g = _Guide()
        batch_id = _make_batch(g, 1)
        task_id = self._setup_task(g, batch_id=batch_id)
        # Set total_files=1 so one completion triggers batch completion
        g.guideline_batches[batch_id]["total_files"] = 1
        g._mark_guideline_task_complete(task_id, batch_id, success=True)
        assert g.guideline_batches[batch_id]["status"] == "completed"

    def test_no_crash_when_task_not_in_active(self):
        g = _Guide()
        # task_id not in active_tasks
        g._mark_guideline_task_complete("ghost-task", None, success=True)
