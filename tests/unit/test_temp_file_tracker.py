"""Tests for TempFileTracker."""
import sys, os, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../src'))

import pytest
from unittest.mock import patch

import utils.temp_file_tracker as module
from utils.temp_file_tracker import TempFileTracker


@pytest.fixture(autouse=True)
def reset_singleton():
    module.TempFileTracker._instance = None
    yield
    module.TempFileTracker._instance = None


class TestTempFileTracker:
    """Tests for TempFileTracker singleton lifecycle and behaviour."""

    def test_instance_returns_temp_file_tracker(self):
        tracker = TempFileTracker.instance()
        assert isinstance(tracker, TempFileTracker)

    def test_instance_singleton(self):
        a = TempFileTracker.instance()
        b = TempFileTracker.instance()
        assert a is b

    def test_register_adds_path(self):
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/test_phi.tmp")
        assert "/tmp/test_phi.tmp" in tracker._files

    def test_register_twice_no_duplicate(self):
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/test_phi.tmp")
        tracker.register("/tmp/test_phi.tmp")
        assert len(tracker._files) == 1

    def test_unregister_removes_path(self):
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/test_phi.tmp")
        tracker.unregister("/tmp/test_phi.tmp")
        assert "/tmp/test_phi.tmp" not in tracker._files

    def test_unregister_non_tracked_path_no_error(self):
        tracker = TempFileTracker.instance()
        # Should not raise
        tracker.unregister("/tmp/never_registered.tmp")

    def test_cleanup_all_deletes_existing_file_and_returns_count(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            tracker = TempFileTracker.instance()
            tracker.register(path)
            count = tracker.cleanup_all()
            assert count == 1
            assert not os.path.exists(path)
        finally:
            # Safety net in case cleanup didn't run
            if os.path.exists(path):
                os.unlink(path)

    def test_cleanup_all_empty_tracker_returns_zero(self):
        tracker = TempFileTracker.instance()
        count = tracker.cleanup_all()
        assert count == 0

    def test_cleanup_all_skips_nonexistent_files_gracefully(self):
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/phantom_file_that_does_not_exist_xyz.tmp")
        count = tracker.cleanup_all()
        assert count == 0

    def test_cleanup_all_clears_tracked_set(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            tracker = TempFileTracker.instance()
            tracker.register(path)
            tracker.cleanup_all()
            assert len(tracker._files) == 0
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_tracker_empty_after_cleanup_all(self):
        with tempfile.NamedTemporaryFile(delete=False) as f:
            path = f.name
        try:
            tracker = TempFileTracker.instance()
            tracker.register(path)
            tracker.cleanup_all()
            # Confirm the internal set is empty
            assert tracker._files == set()
        finally:
            if os.path.exists(path):
                os.unlink(path)
