"""
Comprehensive unit tests for src/utils/single_instance.py

Covers:
  - _get_lock_file_path()       (all three platforms + mkdir call)
  - _is_process_running()       (unix signal-0 path, OSError variants)
  - _read_lock_file()           (exists / missing / invalid / whitespace)
  - _write_lock_file()          (success / OSError)
  - _remove_lock_file()         (exists / missing / OSError)
  - ensure_single_instance()    (all decision branches)
"""

import os
import sys
import platform
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

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
    """Tests for _get_lock_file_path()."""

    # -- sanity / type checks -------------------------------------------------

    def test_returns_path_object(self):
        path = _get_lock_file_path()
        assert isinstance(path, Path)

    def test_filename_is_app_lock(self):
        path = _get_lock_file_path()
        assert path.name == "app.lock"

    def test_parent_directory_exists_after_call(self):
        path = _get_lock_file_path()
        assert path.parent.exists()

    def test_medicalassistant_in_path(self):
        path = _get_lock_file_path()
        assert "MedicalAssistant" in str(path)

    # -- Linux ----------------------------------------------------------------

    def test_linux_uses_local_share(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        assert ".local" in str(path)
        assert "share" in str(path)

    def test_linux_exact_structure(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        expected = tmp_path / ".local" / "share" / "MedicalAssistant" / "app.lock"
        assert path == expected

    def test_linux_calls_mkdir_with_parents_exist_ok(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir") as mock_mkdir:
            _get_lock_file_path()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # -- macOS ----------------------------------------------------------------

    def test_darwin_uses_library_application_support(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Darwin"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        assert "Library" in str(path)
        assert "Application Support" in str(path)

    def test_darwin_exact_structure(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Darwin"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        expected = tmp_path / "Library" / "Application Support" / "MedicalAssistant" / "app.lock"
        assert path == expected

    def test_darwin_calls_mkdir(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Darwin"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir") as mock_mkdir:
            _get_lock_file_path()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # -- Windows --------------------------------------------------------------

    def test_windows_uses_localappdata(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Windows"), \
             patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        assert "MedicalAssistant" in str(path)

    def test_windows_exact_structure_with_localappdata(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Windows"), \
             patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        assert path == Path(tmp_path) / "MedicalAssistant" / "app.lock"

    def test_windows_falls_back_to_home_when_no_localappdata(self, tmp_path):
        env_without_local = {k: v for k, v in os.environ.items() if k != "LOCALAPPDATA"}
        with patch("utils.single_instance.platform.system", return_value="Windows"), \
             patch.dict(os.environ, env_without_local, clear=True), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        assert path == tmp_path / "MedicalAssistant" / "app.lock"

    def test_windows_calls_mkdir(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="Windows"), \
             patch.dict(os.environ, {"LOCALAPPDATA": str(tmp_path)}), \
             patch("pathlib.Path.mkdir") as mock_mkdir:
            _get_lock_file_path()
        mock_mkdir.assert_called_once_with(parents=True, exist_ok=True)

    # -- unknown platform falls through to else (Linux path) ------------------

    def test_unknown_platform_uses_linux_branch(self, tmp_path):
        with patch("utils.single_instance.platform.system", return_value="FreeBSD"), \
             patch("pathlib.Path.home", return_value=tmp_path), \
             patch("pathlib.Path.mkdir"):
            path = _get_lock_file_path()
        assert ".local" in str(path)


# ===========================================================================
# _read_lock_file
# ===========================================================================

class TestReadLockFile:
    """Tests for _read_lock_file(lock_file)."""

    def test_returns_pid_from_valid_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("12345")
        assert _read_lock_file(lock) == 12345

    def test_returns_none_when_file_missing(self, tmp_path):
        lock = tmp_path / "missing.lock"
        assert _read_lock_file(lock) is None

    def test_returns_none_for_non_integer_content(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("not_a_pid")
        assert _read_lock_file(lock) is None

    def test_returns_none_for_empty_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("")
        assert _read_lock_file(lock) is None

    def test_strips_whitespace_and_newline(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("  9999  \n")
        assert _read_lock_file(lock) == 9999

    def test_strips_leading_whitespace(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("   42")
        assert _read_lock_file(lock) == 42

    def test_returns_int_type(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("7777")
        result = _read_lock_file(lock)
        assert isinstance(result, int)

    def test_returns_none_type_when_missing(self, tmp_path):
        result = _read_lock_file(tmp_path / "ghost.lock")
        assert result is None

    def test_returns_none_for_float_string(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1.5")
        assert _read_lock_file(lock) is None

    def test_returns_none_for_hex_string(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("0xff")
        assert _read_lock_file(lock) is None

    def test_returns_none_on_oserror_reading(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("123")
        with patch.object(Path, "read_text", side_effect=OSError("read error")):
            assert _read_lock_file(lock) is None

    def test_returns_none_when_exists_but_read_raises(self, tmp_path):
        lock = tmp_path / "app.lock"
        with patch.object(Path, "exists", return_value=True), \
             patch.object(Path, "read_text", side_effect=OSError("io error")):
            assert _read_lock_file(lock) is None

    def test_large_pid_value(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("4194304")
        assert _read_lock_file(lock) == 4194304

    def test_pid_one(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1")
        assert _read_lock_file(lock) == 1

    def test_negative_pid_is_valid_int(self, tmp_path):
        """Negative PIDs don't occur in practice but are valid integers."""
        lock = tmp_path / "app.lock"
        lock.write_text("-1")
        assert _read_lock_file(lock) == -1


# ===========================================================================
# _write_lock_file
# ===========================================================================

class TestWriteLockFile:
    """Tests for _write_lock_file(lock_file, pid)."""

    def test_writes_pid_as_string(self, tmp_path):
        lock = tmp_path / "app.lock"
        _write_lock_file(lock, 42000)
        assert lock.read_text() == "42000"

    def test_returns_true_on_success(self, tmp_path):
        lock = tmp_path / "app.lock"
        assert _write_lock_file(lock, 1) is True

    def test_returns_false_on_oserror(self, tmp_path):
        lock = tmp_path / "app.lock"
        with patch.object(Path, "write_text", side_effect=OSError("permission denied")):
            assert _write_lock_file(lock, 999) is False

    def test_overwrites_existing_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("old_pid")
        _write_lock_file(lock, 12345)
        assert lock.read_text() == "12345"

    def test_file_is_created_when_absent(self, tmp_path):
        lock = tmp_path / "new_lock.lock"
        assert not lock.exists()
        _write_lock_file(lock, 99)
        assert lock.exists()

    def test_write_pid_zero(self, tmp_path):
        lock = tmp_path / "app.lock"
        assert _write_lock_file(lock, 0) is True
        assert lock.read_text() == "0"

    def test_write_large_pid(self, tmp_path):
        lock = tmp_path / "app.lock"
        assert _write_lock_file(lock, 4194304) is True
        assert lock.read_text() == "4194304"

    def test_returns_bool_not_truthy_object(self, tmp_path):
        lock = tmp_path / "app.lock"
        result = _write_lock_file(lock, 1)
        assert result is True  # strict identity, not just truthy


# ===========================================================================
# _remove_lock_file
# ===========================================================================

class TestRemoveLockFile:
    """Tests for _remove_lock_file(lock_file)."""

    def test_removes_existing_file(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1234")
        _remove_lock_file(lock)
        assert not lock.exists()

    def test_no_error_when_file_missing(self, tmp_path):
        lock = tmp_path / "nonexistent.lock"
        _remove_lock_file(lock)  # must not raise

    def test_handles_oserror_on_unlink_gracefully(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1234")
        with patch.object(Path, "unlink", side_effect=OSError("busy")):
            _remove_lock_file(lock)  # must not raise

    def test_returns_none(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1")
        result = _remove_lock_file(lock)
        assert result is None

    def test_calls_unlink_when_file_exists(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1")
        with patch.object(Path, "unlink") as mock_unlink:
            _remove_lock_file(lock)
        mock_unlink.assert_called_once()

    def test_does_not_call_unlink_when_file_missing(self, tmp_path):
        lock = tmp_path / "ghost.lock"
        with patch.object(Path, "unlink") as mock_unlink:
            _remove_lock_file(lock)
        mock_unlink.assert_not_called()

    def test_second_remove_is_safe(self, tmp_path):
        lock = tmp_path / "app.lock"
        lock.write_text("1")
        _remove_lock_file(lock)
        _remove_lock_file(lock)  # second call — file already gone, should not raise


# ===========================================================================
# _is_process_running
# ===========================================================================

class TestIsProcessRunning:
    """Tests for _is_process_running(pid)."""

    # -- current process is always alive --------------------------------------

    def test_current_process_is_running(self):
        # Real call, no mocking needed
        assert _is_process_running(os.getpid()) is True

    # -- Unix: os.kill(pid, 0) path -------------------------------------------

    def test_unix_running_process_kill_no_error_returns_true(self):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill", return_value=None):
            assert _is_process_running(1234) is True

    def test_unix_dead_process_oserror_returns_false(self):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill", side_effect=OSError("no such process")):
            assert _is_process_running(9999) is False

    def test_unix_sends_signal_zero_to_correct_pid(self):
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill") as mock_kill:
            _is_process_running(42)
        mock_kill.assert_called_once_with(42, 0)

    def test_macos_running_process_returns_true(self):
        with patch("utils.single_instance.platform.system", return_value="Darwin"), \
             patch("os.kill", return_value=None):
            assert _is_process_running(100) is True

    def test_macos_dead_process_returns_false(self):
        with patch("utils.single_instance.platform.system", return_value="Darwin"), \
             patch("os.kill", side_effect=OSError):
            assert _is_process_running(100) is False

    def test_unix_permission_error_oserror_returns_false(self):
        """EPERM: process exists but we lack permission — still OSError."""
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill", side_effect=OSError(1, "Operation not permitted")):
            assert _is_process_running(1) is False

    def test_unix_unexpected_exception_propagates(self):
        """The Unix branch only catches OSError; other exceptions propagate."""
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill", side_effect=RuntimeError("unexpected")):
            with pytest.raises(RuntimeError):
                _is_process_running(999)

    def test_unix_process_group_signal_not_sent_for_nonzero_pid(self):
        """Ensure we always pass signal 0 (not something destructive)."""
        with patch("utils.single_instance.platform.system", return_value="Linux"), \
             patch("os.kill") as mock_kill:
            _is_process_running(5678)
        _, sig = mock_kill.call_args[0]
        assert sig == 0

    def test_invalid_very_large_pid_returns_false(self):
        """A PID that almost certainly doesn't exist should return False on Unix."""
        if platform.system() != "Windows":
            assert _is_process_running(4194305) is False


# ===========================================================================
# ensure_single_instance
# ===========================================================================

class TestEnsureSingleInstance:
    """Tests for ensure_single_instance()."""

    def _lock(self, tmp_path):
        return tmp_path / "app.lock"

    # -- no existing lock file ------------------------------------------------

    def test_first_run_returns_true(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            result = ensure_single_instance()
        assert result is True

    def test_first_run_creates_lock_file(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            ensure_single_instance()
        assert lock.exists()

    def test_first_run_writes_current_pid(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock):
            ensure_single_instance()
        assert lock.read_text() == str(os.getpid())

    def test_first_run_registers_atexit(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit") as mock_atexit:
            ensure_single_instance()
        mock_atexit.register.assert_called_once()

    def test_first_run_atexit_passes_remove_and_lock_path(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit") as mock_atexit:
            ensure_single_instance()
        args = mock_atexit.register.call_args[0]
        assert args[0] is _remove_lock_file
        assert args[1] == lock

    # -- own PID already in lock file -----------------------------------------

    def test_own_pid_in_lock_returns_true(self, tmp_path):
        lock = self._lock(tmp_path)
        lock.write_text(str(os.getpid()))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is True

    def test_own_pid_does_not_call_is_process_running(self, tmp_path):
        lock = self._lock(tmp_path)
        lock.write_text(str(os.getpid()))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running") as mock_check, \
             patch("utils.single_instance.atexit"):
            ensure_single_instance()
        mock_check.assert_not_called()

    # -- another live instance ------------------------------------------------

    def test_other_running_instance_returns_false(self, tmp_path):
        lock = self._lock(tmp_path)
        other_pid = os.getpid() + 1000
        lock.write_text(str(other_pid))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=True), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is False

    def test_other_running_instance_does_not_overwrite_lock(self, tmp_path):
        lock = self._lock(tmp_path)
        other_pid = os.getpid() + 1000
        lock.write_text(str(other_pid))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=True), \
             patch("utils.single_instance.atexit"):
            ensure_single_instance()
        assert lock.read_text() == str(other_pid)

    def test_other_running_instance_checks_correct_pid(self, tmp_path):
        lock = self._lock(tmp_path)
        other_pid = os.getpid() + 500
        lock.write_text(str(other_pid))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running",
                   return_value=True) as mock_check, \
             patch("utils.single_instance.atexit"):
            ensure_single_instance()
        mock_check.assert_called_once_with(other_pid)

    # -- stale lock file (dead process) ---------------------------------------

    def test_stale_lock_removed_and_new_lock_written(self, tmp_path):
        lock = self._lock(tmp_path)
        lock.write_text("77777")
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=False), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is True
        assert lock.read_text() == str(os.getpid())

    def test_stale_lock_triggers_remove_then_write(self, tmp_path):
        lock = self._lock(tmp_path)
        lock.write_text("11111")
        remove_calls = []
        write_calls = []

        def fake_remove(path):
            remove_calls.append(path)

        def fake_write(path, pid):
            write_calls.append((path, pid))
            return True

        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=False), \
             patch("utils.single_instance._remove_lock_file", side_effect=fake_remove), \
             patch("utils.single_instance._write_lock_file", side_effect=fake_write), \
             patch("utils.single_instance.atexit"):
            ensure_single_instance()

        assert len(remove_calls) == 1
        assert len(write_calls) == 1
        assert remove_calls[0] == lock
        assert write_calls[0][0] == lock

    # -- lock write failure ---------------------------------------------------

    def test_write_failure_returns_true_anyway(self, tmp_path):
        """App must start even when we can't write the lock file."""
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._write_lock_file", return_value=False), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is True

    def test_write_failure_does_not_register_atexit(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._write_lock_file", return_value=False), \
             patch("utils.single_instance.atexit") as mock_atexit:
            ensure_single_instance()
        mock_atexit.register.assert_not_called()

    # -- invalid lock file content --------------------------------------------

    def test_invalid_lock_file_content_allows_start(self, tmp_path):
        lock = self._lock(tmp_path)
        lock.write_text("garbage")
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is True

    def test_invalid_lock_file_content_writes_current_pid(self, tmp_path):
        lock = self._lock(tmp_path)
        lock.write_text("not-a-pid")
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit"):
            ensure_single_instance()
        assert lock.read_text() == str(os.getpid())

    # -- _read_lock_file returns None (no lock) --------------------------------

    def test_read_returns_none_proceeds_to_write(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._read_lock_file", return_value=None), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is True

    # -- return value is strict bool ------------------------------------------

    def test_returns_true_is_bool(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is True

    def test_returns_false_is_bool(self, tmp_path):
        lock = self._lock(tmp_path)
        other_pid = os.getpid() + 1000
        lock.write_text(str(other_pid))
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance._is_process_running", return_value=True), \
             patch("utils.single_instance.atexit"):
            result = ensure_single_instance()
        assert result is False

    # -- multiple sequential calls (idempotency) ------------------------------

    def test_two_calls_same_process_both_return_true(self, tmp_path):
        lock = self._lock(tmp_path)
        with patch("utils.single_instance._get_lock_file_path", return_value=lock), \
             patch("utils.single_instance.atexit"):
            r1 = ensure_single_instance()
            r2 = ensure_single_instance()
        assert r1 is True
        assert r2 is True


# ===========================================================================
# Integration-style: real file I/O on tmp_path (no mocked I/O)
# ===========================================================================

class TestRealFileIntegration:
    """Light integration tests that use real file I/O."""

    def test_write_then_read_round_trip(self, tmp_path):
        lock = tmp_path / "app.lock"
        _write_lock_file(lock, 42)
        assert _read_lock_file(lock) == 42

    def test_write_then_remove_then_read_returns_none(self, tmp_path):
        lock = tmp_path / "app.lock"
        _write_lock_file(lock, 42)
        _remove_lock_file(lock)
        assert _read_lock_file(lock) is None

    def test_remove_nonexistent_is_safe(self, tmp_path):
        _remove_lock_file(tmp_path / "nonexistent.lock")

    def test_write_returns_true_and_file_created(self, tmp_path):
        lock = tmp_path / "app.lock"
        result = _write_lock_file(lock, os.getpid())
        assert result is True
        assert lock.exists()

    def test_current_pid_is_process_running_unix(self):
        if platform.system() != "Windows":
            assert _is_process_running(os.getpid()) is True

    def test_impossible_pid_is_not_running_unix(self):
        if platform.system() != "Windows":
            assert _is_process_running(4194305) is False
