"""
Tests for TaskLifecycleMixin in src/processing/task_lifecycle_mixin.py

Covers _update_avg_processing_time (zero total, single sample, running avg)
and _prune_completed_tasks / _prune_failed_tasks (under limit, over limit,
oldest removed, exactly at limit). Uses a minimal stub with lock, stats,
and task dicts. No network, no Tkinter, no real DB.
"""

import sys
import threading
import pytest
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.task_lifecycle_mixin import TaskLifecycleMixin


# ---------------------------------------------------------------------------
# Minimal stub
# ---------------------------------------------------------------------------

class _Stub(TaskLifecycleMixin):
    def __init__(self, max_completed=5):
        self.lock = threading.Lock()
        self.MAX_COMPLETED_TASKS = max_completed
        self.completed_tasks: dict = {}
        self.failed_tasks: dict = {}
        self.stats = {"total_processed": 0, "processing_time_avg": 0.0}
        self.app = None


def _stub(max_completed=5) -> _Stub:
    return _Stub(max_completed=max_completed)


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day)


# ===========================================================================
# _update_avg_processing_time
# ===========================================================================

class TestUpdateAvgProcessingTime:
    def test_zero_total_sets_avg_to_new_time(self):
        s = _stub()
        s.stats["total_processed"] = 0
        s._update_avg_processing_time(5.0)
        assert s.stats["processing_time_avg"] == pytest.approx(5.0)

    def test_total_one_sets_avg_to_new_time(self):
        s = _stub()
        s.stats["total_processed"] = 1
        s.stats["processing_time_avg"] = 0.0
        s._update_avg_processing_time(7.5)
        assert s.stats["processing_time_avg"] == pytest.approx(7.5)

    def test_running_avg_two_items(self):
        s = _stub()
        s.stats["total_processed"] = 2
        s.stats["processing_time_avg"] = 10.0
        # new avg = (10 * 1 + 4) / 2 = 7.0
        s._update_avg_processing_time(4.0)
        assert s.stats["processing_time_avg"] == pytest.approx(7.0)

    def test_running_avg_three_items(self):
        s = _stub()
        s.stats["total_processed"] = 3
        s.stats["processing_time_avg"] = 10.0
        # new avg = (10 * 2 + 4) / 3 = 8.0
        s._update_avg_processing_time(4.0)
        assert s.stats["processing_time_avg"] == pytest.approx(8.0)

    def test_larger_new_time_increases_avg(self):
        s = _stub()
        s.stats["total_processed"] = 5
        s.stats["processing_time_avg"] = 10.0
        s._update_avg_processing_time(100.0)
        assert s.stats["processing_time_avg"] > 10.0

    def test_smaller_new_time_decreases_avg(self):
        s = _stub()
        s.stats["total_processed"] = 5
        s.stats["processing_time_avg"] = 10.0
        s._update_avg_processing_time(0.0)
        assert s.stats["processing_time_avg"] < 10.0

    def test_result_stored_in_stats(self):
        s = _stub()
        s.stats["total_processed"] = 4
        s.stats["processing_time_avg"] = 6.0
        s._update_avg_processing_time(6.0)
        assert isinstance(s.stats["processing_time_avg"], float)

    def test_equal_new_time_keeps_avg(self):
        s = _stub()
        s.stats["total_processed"] = 10
        s.stats["processing_time_avg"] = 5.0
        s._update_avg_processing_time(5.0)
        assert s.stats["processing_time_avg"] == pytest.approx(5.0)


# ===========================================================================
# _prune_completed_tasks — completed_tasks pruning
# ===========================================================================

class TestPruneCompletedTasks:
    def test_under_limit_no_pruning(self):
        s = _stub(max_completed=10)
        for i in range(5):
            s.completed_tasks[f"t{i}"] = {"completed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert len(s.completed_tasks) == 5

    def test_exactly_at_limit_no_pruning(self):
        s = _stub(max_completed=5)
        for i in range(5):
            s.completed_tasks[f"t{i}"] = {"completed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert len(s.completed_tasks) == 5

    def test_over_limit_prunes_to_max(self):
        s = _stub(max_completed=5)
        for i in range(8):
            s.completed_tasks[f"t{i}"] = {"completed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert len(s.completed_tasks) == 5

    def test_oldest_tasks_removed(self):
        s = _stub(max_completed=3)
        for i in range(6):
            s.completed_tasks[f"t{i}"] = {"completed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        # Oldest 3 (t0, t1, t2) should be removed; t3, t4, t5 remain
        assert "t0" not in s.completed_tasks
        assert "t1" not in s.completed_tasks
        assert "t2" not in s.completed_tasks

    def test_newest_tasks_retained(self):
        s = _stub(max_completed=3)
        for i in range(6):
            s.completed_tasks[f"t{i}"] = {"completed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert "t3" in s.completed_tasks
        assert "t4" in s.completed_tasks
        assert "t5" in s.completed_tasks

    def test_empty_completed_tasks_no_error(self):
        s = _stub(max_completed=5)
        s._prune_completed_tasks()  # Should not raise
        assert len(s.completed_tasks) == 0

    def test_missing_completed_at_handled(self):
        s = _stub(max_completed=2)
        for i in range(4):
            s.completed_tasks[f"t{i}"] = {}  # No completed_at key
        s._prune_completed_tasks()  # Should not raise; uses datetime.min default
        assert len(s.completed_tasks) == 2


# ===========================================================================
# _prune_completed_tasks — failed_tasks pruning
# ===========================================================================

class TestPruneFailedTasks:
    def test_failed_under_limit_no_pruning(self):
        s = _stub(max_completed=10)
        for i in range(5):
            s.failed_tasks[f"f{i}"] = {"failed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert len(s.failed_tasks) == 5

    def test_failed_over_limit_prunes_to_max(self):
        s = _stub(max_completed=3)
        for i in range(6):
            s.failed_tasks[f"f{i}"] = {"failed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert len(s.failed_tasks) == 3

    def test_failed_oldest_removed(self):
        s = _stub(max_completed=2)
        for i in range(5):
            s.failed_tasks[f"f{i}"] = {"failed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert "f0" not in s.failed_tasks
        assert "f1" not in s.failed_tasks
        assert "f2" not in s.failed_tasks

    def test_failed_newest_retained(self):
        s = _stub(max_completed=2)
        for i in range(5):
            s.failed_tasks[f"f{i}"] = {"failed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert "f3" in s.failed_tasks
        assert "f4" in s.failed_tasks

    def test_both_completed_and_failed_pruned_together(self):
        s = _stub(max_completed=3)
        for i in range(6):
            s.completed_tasks[f"c{i}"] = {"completed_at": _dt(i + 1)}
            s.failed_tasks[f"f{i}"] = {"failed_at": _dt(i + 1)}
        s._prune_completed_tasks()
        assert len(s.completed_tasks) == 3
        assert len(s.failed_tasks) == 3
