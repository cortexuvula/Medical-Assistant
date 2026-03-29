"""
Tests for src/utils/single_instance.py

Covers lock file helpers (_read_lock_file, _write_lock_file, _remove_lock_file),
_get_lock_file_path, _is_process_running, and ensure_single_instance logic.
"""

import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.single_instance import (
    _read_lock_file,
    _write_lock_file,
    _remove_lock_file,
    _get_lock_file_path,
    _is_process_running,
    ensure_single_instance,
)


# ===========================================================================
# _get_lock_file_path
# ===========================================================================

class TestGetLockFilePath:
    def test_returns_path(self):
        path = _get_lock_file_path()
        assert isinstance(path, Path)

    def test_filename_is_app_lock(self):
        path = _get_lock_file_path()
        assert path.name == "app.lock"

    def test_linux_uses_local_share(self):
        with patch("utils.single_instance.platform.system", return_value="Linux"):
            path = _get_lock_file_path()
        assert ".local" in str(path) or "share" in str(path)

    def test_darwin_uses_library(self):
        with patch("utils.single_instance.platform.system", return_value="Darwin"):
            path = _get_lock_file_path()
        assert "Library" in str(path)

    def test_windows_uses_localappdata(self, tmp_path):
        fake_local = str(tmp_path / "localappdata")
        with patch("utils.single_instance.platform.system", return_value="Windows"), \
             patch.dict(os.environ, {"LOCALAPPDATA": fake_local}):
            path = _get_lock_file_path()
        assert "MedicalAssistant" in str(path)

    def test_parent_directory_exists_after_call(self):
        path = _get_lock_file_path()
        assert path.parent.exists()


# ===========================================================================
# _read_lock_file
# ===========================================================================

class TestReadLockFile:
    def test_returns_pid_from_valid_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("12345")
        assert _read_lock_file(lock) == 12345

    def test_returns_none_when_file_missing(self, tmp_path):
        lock = tmp_path / "missing.lock"
        assert _read_lock_file(lock) is None

    def test_returns_none_for_invalid_content(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("not_a_pid")
        assert _read_lock_file(lock) is None

    def test_returns_none_for_empty_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("")
        assert _read_lock_file(lock) is None

    def test_strips_whitespace(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("  9999  \n")
        assert _read_lock_file(lock) == 9999


# ===========================================================================
# _write_lock_file
# ===========================================================================

class TestWriteLockFile:
    def test_writes_pid_to_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        result = _write_lock_file(lock, 42000)
        assert result is True
        assert lock.read_text() == "42000"

    def test_returns_true_on_success(self, tmp_path):
        lock = tmp_path / "app.lock"
        assert _write_lock_file(lock, 1) is True

    def test_returns_false_on_permission_error(self, tmp_path):
        lock = tmp_path / "app.lock"
        with patch.object(Path, "write_text", side_effect=OSError("permission denied")):
            result = _write_lock_file(lock, 999)
        assert result is False

    def test_overwrites_existing_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("old_pid")
        _write_lock_file(lock, 12345)
        assert lock.read_text() == "12345"


# ===========================================================================
# _remove_lock_file
# ===========================================================================

class TestRemoveLockFile:
    def test_removes_existing_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1234")
        _remove_lock_file(lock)
        assert not lock.exists()

    def test_no_error_when_file_missing(self, tmp_path):
        lock = tmp_path / "nonexistent.lock"
        # Should not raise
        _remove_lock_file(lock)

    def test_handles_oserror_gracefully(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1234")
        with patch.object(Path, "unlink", side_effect=OSError("busy")):
            _remove_lock_file(lock)  # Should not raise


# ===========================================================================
# _is_process_running
# ===========================================================================

class TestIsProcessRunning:
    def test_current_process_is_running(self):
        assert _is_process_running(os.getpid()) is True

    def test_invalid_pid_returns_false(self):
        # PID 0 on Unix sends signal to process group; very high PIDs usually invalid
        # Use a PID that definitely doesn't exist
        with patch("os.kill", side_effect=OSError("no such process")):
            result = _is_process_running(9999999)
        assert result is False

    def test_oserror_returns_false_on_unix(self):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill", side_effect=OSError()):
            result = _is_process_running(99999)
        assert result is False


# ===========================================================================
# ensure_single_instance
# ===========================================================================

class TestEnsureSingleInstance:
    def _patched_lock_path(self, tmp_path):
        """Return a lock path inside tmp_path."""
        return tmp_path / "app.lock"

    def test_first_run_returns_true(self, tmp_path):
        lock = self._patched_lock_path(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            result = ensure_single_instance()
        assert result is True
        assert lock.exists()

    def test_creates_lock_file_with_current_pid(self, tmp_path):
        lock = self._patched_lock_path(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            ensure_single_instance()
        assert lock.read_text() == str(os.getpid())

    def test_returns_false_when_another_instance_running(self, tmp_path):
        lock = self._patched_lock_path(tmp_path)
        other_pid = 99998
        lock.write_text(str(other_pid))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=True):
            result = ensure_single_instance()
        assert result is False

    def test_stale_lock_cleaned_and_new_lock_written(self, tmp_path):
        lock = self._patched_lock_path(tmp_path)
        stale_pid = 77777
        lock.write_text(str(stale_pid))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=False):
            result = ensure_single_instance()
        assert result is True
        assert lock.read_text() == str(os.getpid())

    def test_own_pid_in_lock_returns_true(self, tmp_path):
        lock = self._patched_lock_path(tmp_path)
        lock.write_text(str(os.getpid()))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            result = ensure_single_instance()
        assert result is True

    def test_write_failure_returns_true_anyway(self, tmp_path):
        """App should still start even if we can't write the lock file."""
        lock = self._patched_lock_path(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._write_lock_file", return_value=False):
            result = ensure_single_instance()
        assert result is True

    def test_lock_file_no_existing_pid(self, tmp_path):
        """No existing lock file — first run scenario."""
        lock = self._patched_lock_path(tmp_path)
        assert not lock.exists()
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            result = ensure_single_instance()
        assert result is True
        assert lock.exists()
