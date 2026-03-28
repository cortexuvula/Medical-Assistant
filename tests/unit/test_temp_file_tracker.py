"""Tests for utils.temp_file_tracker — TempFileTracker singleton."""

import os
import pytest
import threading
from pathlib import Path


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset TempFileTracker singleton before each test."""
    import utils.temp_file_tracker as mod
    mod.TempFileTracker._instance = None
    yield
    mod.TempFileTracker._instance = None


# ── Singleton ─────────────────────────────────────────────────────────────────

class TestTempFileTrackerSingleton:
    def test_instance_returns_same_object(self):
        from utils.temp_file_tracker import TempFileTracker
        a = TempFileTracker.instance()
        b = TempFileTracker.instance()
        assert a is b

    def test_instance_is_temp_file_tracker(self):
        from utils.temp_file_tracker import TempFileTracker
        assert isinstance(TempFileTracker.instance(), TempFileTracker)


# ── register / unregister ─────────────────────────────────────────────────────

class TestRegisterUnregister:
    def test_register_adds_path(self):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/phi_test_file.tmp")
        assert "/tmp/phi_test_file.tmp" in tracker._files

    def test_unregister_removes_path(self):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/phi_test_file.tmp")
        tracker.unregister("/tmp/phi_test_file.tmp")
        assert "/tmp/phi_test_file.tmp" not in tracker._files

    def test_unregister_nonexistent_path_safe(self):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        tracker.unregister("/nonexistent/path.tmp")  # Should not raise

    def test_register_multiple_paths(self):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        tracker.register("/tmp/a.tmp")
        tracker.register("/tmp/b.tmp")
        assert len(tracker._files) == 2


# ── cleanup_all ───────────────────────────────────────────────────────────────

class TestCleanupAll:
    def test_deletes_existing_file(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()

        f = tmp_path / "phi_data.tmp"
        f.write_text("sensitive data")
        tracker.register(str(f))

        count = tracker.cleanup_all()
        assert count == 1
        assert not f.exists()

    def test_returns_count_of_deleted(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()

        for i in range(3):
            f = tmp_path / f"file_{i}.tmp"
            f.write_text("data")
            tracker.register(str(f))

        count = tracker.cleanup_all()
        assert count == 3

    def test_clears_registry_after_cleanup(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()

        f = tmp_path / "phi.tmp"
        f.write_text("data")
        tracker.register(str(f))
        tracker.cleanup_all()

        assert len(tracker._files) == 0

    def test_already_deleted_file_not_counted(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()

        f = tmp_path / "ghost.tmp"
        # Register path but don't create the file
        tracker.register(str(f))

        count = tracker.cleanup_all()
        assert count == 0  # FileNotFoundError is silently handled

    def test_returns_zero_when_no_files(self):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        count = tracker.cleanup_all()
        assert count == 0

    def test_partial_cleanup_when_some_missing(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()

        f_exists = tmp_path / "exists.tmp"
        f_exists.write_text("data")
        tracker.register(str(f_exists))
        tracker.register("/nonexistent/ghost.tmp")

        count = tracker.cleanup_all()
        assert count == 1
        assert not f_exists.exists()


# ── thread-safety ─────────────────────────────────────────────────────────────

class TestThreadSafety:
    def test_concurrent_register_safe(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        errors = []

        def register_many():
            try:
                for i in range(20):
                    tracker.register(f"/tmp/thread_test_{i}.tmp")
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=register_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []

    def test_concurrent_cleanup_safe(self, tmp_path):
        from utils.temp_file_tracker import TempFileTracker
        tracker = TempFileTracker.instance()
        errors = []

        # Create some files to delete
        files = []
        for i in range(5):
            f = tmp_path / f"concurrent_{i}.tmp"
            f.write_text("data")
            tracker.register(str(f))
            files.append(f)

        def do_cleanup():
            try:
                tracker.cleanup_all()
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=do_cleanup) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == []
