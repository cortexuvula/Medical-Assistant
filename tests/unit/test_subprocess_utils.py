"""
Comprehensive pytest unit tests for src/utils/subprocess_utils.py.

All tests are pure-logic — no real subprocess calls are made.
"""

import sys
import pytest
import platform
import subprocess
from pathlib import Path
from unittest.mock import patch, MagicMock, call

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.subprocess_utils import (
    SubprocessResult,
    run_subprocess,
    open_file_with_default_app,
    print_file,
    check_command_exists,
    _get_windows_subprocess_kwargs,
)


# ---------------------------------------------------------------------------
# SubprocessResult – dataclass field construction
# ---------------------------------------------------------------------------

class TestSubprocessResultFields:
    """Tests for SubprocessResult dataclass field construction."""

    def test_success_true_stored(self):
        r = SubprocessResult(success=True, returncode=0, stdout="out", stderr="", command=["cmd"])
        assert r.success is True

    def test_success_false_stored(self):
        r = SubprocessResult(success=False, returncode=1, stdout="", stderr="err", command=["cmd"])
        assert r.success is False

    def test_returncode_zero_stored(self):
        r = SubprocessResult(success=True, returncode=0, stdout="", stderr="", command=["cmd"])
        assert r.returncode == 0

    def test_nonzero_returncode_stored(self):
        r = SubprocessResult(success=False, returncode=2, stdout="", stderr="", command=["cmd"])
        assert r.returncode == 2

    def test_negative_returncode_stored(self):
        r = SubprocessResult(success=False, returncode=-1, stdout="", stderr="", command=["cmd"])
        assert r.returncode == -1

    def test_stdout_stored(self):
        r = SubprocessResult(success=True, returncode=0, stdout="hello", stderr="", command=["cmd"])
        assert r.stdout == "hello"

    def test_stderr_stored(self):
        r = SubprocessResult(success=False, returncode=1, stdout="", stderr="bad", command=["cmd"])
        assert r.stderr == "bad"

    def test_command_stored(self):
        cmd = ["git", "status"]
        r = SubprocessResult(success=True, returncode=0, stdout="", stderr="", command=cmd)
        assert r.command == ["git", "status"]

    def test_command_is_list(self):
        r = SubprocessResult(success=True, returncode=0, stdout="", stderr="", command=["a", "b"])
        assert isinstance(r.command, list)

    def test_empty_stdout_and_stderr(self):
        r = SubprocessResult(success=True, returncode=0, stdout="", stderr="", command=["cmd"])
        assert r.stdout == ""
        assert r.stderr == ""


# ---------------------------------------------------------------------------
# SubprocessResult.output property
# ---------------------------------------------------------------------------

class TestSubprocessResultOutput:
    """Tests for the output property (combined stdout+stderr)."""

    def test_output_combines_stdout_and_stderr(self):
        r = SubprocessResult(
            success=True, returncode=0,
            stdout="out line", stderr="err line",
            command=["test"],
        )
        assert "out line" in r.output
        assert "err line" in r.output

    def test_output_stdout_only(self):
        r = SubprocessResult(
            success=True, returncode=0,
            stdout="only out", stderr="",
            command=["test"],
        )
        assert r.output == "only out"

    def test_output_stderr_only(self):
        r = SubprocessResult(
            success=False, returncode=1,
            stdout="", stderr="only err",
            command=["test"],
        )
        assert r.output == "only err"

    def test_output_both_empty(self):
        r = SubprocessResult(
            success=True, returncode=0,
            stdout="", stderr="",
            command=["cmd"],
        )
        assert r.output == ""

    def test_both_combined_with_newline(self):
        r = SubprocessResult(success=True, returncode=0, stdout="out", stderr="err", command=["cmd"])
        assert r.output == "out\nerr"

    def test_output_newline_separator(self):
        r = SubprocessResult(success=True, returncode=0, stdout="line1", stderr="line2", command=["cmd"])
        assert "\n" in r.output

    def test_stdout_appears_first(self):
        r = SubprocessResult(success=True, returncode=0, stdout="FIRST", stderr="SECOND", command=["cmd"])
        assert r.output.startswith("FIRST")

    def test_stderr_appears_second(self):
        r = SubprocessResult(success=True, returncode=0, stdout="FIRST", stderr="SECOND", command=["cmd"])
        assert r.output.endswith("SECOND")

    def test_multiline_stdout_only(self):
        r = SubprocessResult(success=True, returncode=0, stdout="a\nb", stderr="", command=["cmd"])
        assert r.output == "a\nb"

    def test_multiline_stderr_only(self):
        r = SubprocessResult(success=False, returncode=1, stdout="", stderr="x\ny", command=["cmd"])
        assert r.output == "x\ny"

    def test_multiline_both(self):
        r = SubprocessResult(success=True, returncode=0, stdout="a\nb", stderr="c\nd", command=["cmd"])
        assert r.output == "a\nb\nc\nd"

    def test_output_property_is_string(self):
        r = SubprocessResult(success=True, returncode=0, stdout="x", stderr="y", command=["cmd"])
        assert isinstance(r.output, str)


# ---------------------------------------------------------------------------
# _get_windows_subprocess_kwargs
# ---------------------------------------------------------------------------

class TestGetWindowsSubprocessKwargs:
    """Tests for _get_windows_subprocess_kwargs()."""

    def test_returns_dict(self):
        result = _get_windows_subprocess_kwargs()
        assert isinstance(result, dict)

    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_non_windows_returns_empty(self, mock_system):
        assert _get_windows_subprocess_kwargs() == {}

    @patch("utils.subprocess_utils.platform.system", return_value="Darwin")
    def test_macos_returns_empty(self, mock_system):
        assert _get_windows_subprocess_kwargs() == {}

    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_non_windows_no_creationflags(self, mock_system):
        result = _get_windows_subprocess_kwargs()
        assert "creationflags" not in result

    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_non_windows_no_startupinfo(self, mock_system):
        result = _get_windows_subprocess_kwargs()
        assert "startupinfo" not in result

    @patch("utils.subprocess_utils.platform.system", return_value="Windows")
    def test_windows_has_creationflags(self, mock_system):
        mock_si = MagicMock()
        with patch("utils.subprocess_utils.subprocess.STARTUPINFO", return_value=mock_si, create=True), \
             patch("utils.subprocess_utils.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True), \
             patch("utils.subprocess_utils.subprocess.STARTF_USESHOWWINDOW", 0x1, create=True), \
             patch("utils.subprocess_utils.subprocess.SW_HIDE", 0, create=True):
            result = _get_windows_subprocess_kwargs()
        assert "creationflags" in result

    @patch("utils.subprocess_utils.platform.system", return_value="Windows")
    def test_windows_has_startupinfo(self, mock_system):
        mock_si = MagicMock()
        with patch("utils.subprocess_utils.subprocess.STARTUPINFO", return_value=mock_si, create=True), \
             patch("utils.subprocess_utils.subprocess.CREATE_NO_WINDOW", 0x08000000, create=True), \
             patch("utils.subprocess_utils.subprocess.STARTF_USESHOWWINDOW", 0x1, create=True), \
             patch("utils.subprocess_utils.subprocess.SW_HIDE", 0, create=True):
            result = _get_windows_subprocess_kwargs()
        assert "startupinfo" in result


# ---------------------------------------------------------------------------
# run_subprocess – success paths
# ---------------------------------------------------------------------------

class TestRunSubprocessSuccess:
    """Tests for run_subprocess success cases."""

    def _make_proc(self, returncode=0, stdout="output", stderr=""):
        mock_proc = MagicMock()
        mock_proc.returncode = returncode
        mock_proc.stdout = stdout
        mock_proc.stderr = stderr
        return mock_proc

    @patch("utils.subprocess_utils.subprocess.run")
    def test_successful_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        result = run_subprocess(["echo", "hello"])
        assert result.success is True
        assert result.returncode == 0
        assert result.stdout == "ok"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_returns_subprocess_result_type(self, mock_run):
        mock_run.return_value = self._make_proc()
        result = run_subprocess(["echo", "hi"])
        assert isinstance(result, SubprocessResult)

    @patch("utils.subprocess_utils.subprocess.run")
    def test_returncode_zero_success_true(self, mock_run):
        mock_run.return_value = self._make_proc(returncode=0)
        result = run_subprocess(["echo", "hi"])
        assert result.success is True

    @patch("utils.subprocess_utils.subprocess.run")
    def test_returncode_zero_stored(self, mock_run):
        mock_run.return_value = self._make_proc(returncode=0)
        result = run_subprocess(["echo", "hi"])
        assert result.returncode == 0

    @patch("utils.subprocess_utils.subprocess.run")
    def test_stdout_captured(self, mock_run):
        mock_run.return_value = self._make_proc(stdout="hello world")
        result = run_subprocess(["echo", "hello world"])
        assert result.stdout == "hello world"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_stderr_captured(self, mock_run):
        mock_run.return_value = self._make_proc(stderr="warning")
        result = run_subprocess(["cmd"])
        assert result.stderr == "warning"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_command_stored_in_result(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        result = run_subprocess(["git", "status"])
        assert result.command == ["git", "status"]

    @patch("utils.subprocess_utils.subprocess.run")
    def test_none_stdout_becomes_empty_string(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr=None)
        result = run_subprocess(["cmd"])
        assert result.stdout == ""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_none_stderr_becomes_empty_string(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr=None)
        result = run_subprocess(["cmd"])
        assert result.stderr == ""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_none_stdout_stderr_coerced_to_empty(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout=None, stderr=None)
        result = run_subprocess(["cmd"])
        assert result.stdout == ""
        assert result.stderr == ""


# ---------------------------------------------------------------------------
# run_subprocess – failure (non-zero returncode)
# ---------------------------------------------------------------------------

class TestRunSubprocessFailure:
    """Tests for run_subprocess non-zero return-code cases."""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_failed_command(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="fail")
        result = run_subprocess(["false"])
        assert result.success is False
        assert result.returncode == 1

    @patch("utils.subprocess_utils.subprocess.run")
    def test_nonzero_returncode_success_false(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="")
        result = run_subprocess(["cmd"])
        assert result.success is False

    @patch("utils.subprocess_utils.subprocess.run")
    def test_nonzero_returncode_stored(self, mock_run):
        mock_run.return_value = MagicMock(returncode=42, stdout="", stderr="")
        result = run_subprocess(["cmd"])
        assert result.returncode == 42

    @patch("utils.subprocess_utils.subprocess.run")
    def test_large_nonzero_returncode(self, mock_run):
        mock_run.return_value = MagicMock(returncode=255, stdout="", stderr="")
        result = run_subprocess(["cmd"])
        assert result.returncode == 255
        assert result.success is False

    @patch("utils.subprocess_utils.subprocess.run")
    def test_stderr_on_failure(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="bad input")
        result = run_subprocess(["cmd"])
        assert result.stderr == "bad input"


# ---------------------------------------------------------------------------
# run_subprocess – TimeoutExpired exception
# ---------------------------------------------------------------------------

class TestRunSubprocessTimeoutExpired:
    """Tests for TimeoutExpired exception handling."""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_expired(self, mock_run):
        exc = subprocess.TimeoutExpired(cmd=["slow"], timeout=5)
        exc.stdout = ""
        mock_run.side_effect = exc
        result = run_subprocess(["slow"], timeout=5)
        assert result.success is False
        assert result.returncode == -1
        assert "timed out" in result.stderr

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_success_false(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cmd"], timeout=5)
        result = run_subprocess(["cmd"], timeout=5)
        assert result.success is False

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_returncode_minus_one(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cmd"], timeout=5)
        result = run_subprocess(["cmd"], timeout=5)
        assert result.returncode == -1

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_stderr_contains_timed_out(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cmd"], timeout=5)
        result = run_subprocess(["cmd"], timeout=5)
        assert "timed out" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_stderr_contains_timeout_value(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cmd"], timeout=30)
        result = run_subprocess(["cmd"], timeout=30)
        assert "30" in result.stderr

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_command_stored(self, mock_run):
        cmd = ["sleep", "100"]
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=cmd, timeout=1)
        result = run_subprocess(cmd, timeout=1)
        assert result.command == cmd

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_stdout_is_string(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd=["cmd"], timeout=5)
        result = run_subprocess(["cmd"], timeout=5)
        assert isinstance(result.stdout, str)


# ---------------------------------------------------------------------------
# run_subprocess – FileNotFoundError exception
# ---------------------------------------------------------------------------

class TestRunSubprocessFileNotFoundError:
    """Tests for FileNotFoundError exception handling."""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_subprocess(["nonexistent"])
        assert result.success is False
        assert result.returncode == -1
        assert "not found" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_fnf_success_false(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        result = run_subprocess(["nonexistent_cmd"])
        assert result.success is False

    @patch("utils.subprocess_utils.subprocess.run")
    def test_fnf_returncode_minus_one(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        result = run_subprocess(["nonexistent_cmd"])
        assert result.returncode == -1

    @patch("utils.subprocess_utils.subprocess.run")
    def test_fnf_stderr_contains_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        result = run_subprocess(["nonexistent_cmd"])
        assert "not found" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_fnf_stderr_contains_command_name(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        result = run_subprocess(["nonexistent_cmd"])
        assert "nonexistent_cmd" in result.stderr

    @patch("utils.subprocess_utils.subprocess.run")
    def test_fnf_stdout_empty(self, mock_run):
        mock_run.side_effect = FileNotFoundError
        result = run_subprocess(["nonexistent_cmd"])
        assert result.stdout == ""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_fnf_command_stored(self, mock_run):
        cmd = ["missing_binary"]
        mock_run.side_effect = FileNotFoundError
        result = run_subprocess(cmd)
        assert result.command == cmd


# ---------------------------------------------------------------------------
# run_subprocess – PermissionError exception
# ---------------------------------------------------------------------------

class TestRunSubprocessPermissionError:
    """Tests for PermissionError exception handling."""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_permission_error(self, mock_run):
        mock_run.side_effect = PermissionError()
        result = run_subprocess(["restricted"])
        assert result.success is False
        assert "Permission denied" in result.stderr or "permission" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_perm_success_false(self, mock_run):
        mock_run.side_effect = PermissionError
        result = run_subprocess(["/root/secret"])
        assert result.success is False

    @patch("utils.subprocess_utils.subprocess.run")
    def test_perm_returncode_minus_one(self, mock_run):
        mock_run.side_effect = PermissionError
        result = run_subprocess(["/root/secret"])
        assert result.returncode == -1

    @patch("utils.subprocess_utils.subprocess.run")
    def test_perm_stderr_contains_permission_denied(self, mock_run):
        mock_run.side_effect = PermissionError
        result = run_subprocess(["/root/secret"])
        assert "permission denied" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_perm_stdout_empty(self, mock_run):
        mock_run.side_effect = PermissionError
        result = run_subprocess(["/root/secret"])
        assert result.stdout == ""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_perm_command_stored(self, mock_run):
        cmd = ["/root/secret"]
        mock_run.side_effect = PermissionError
        result = run_subprocess(cmd)
        assert result.command == cmd


# ---------------------------------------------------------------------------
# run_subprocess – generic exception
# ---------------------------------------------------------------------------

class TestRunSubprocessGenericException:
    """Tests for generic exception handling."""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exception(self, mock_run):
        mock_run.side_effect = Exception("unexpected")
        result = run_subprocess(["boom"])
        assert result.success is False
        assert "unexpected" in result.stderr

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exc_success_false(self, mock_run):
        mock_run.side_effect = RuntimeError("oops")
        result = run_subprocess(["cmd"])
        assert result.success is False

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exc_returncode_minus_one(self, mock_run):
        mock_run.side_effect = RuntimeError("oops")
        result = run_subprocess(["cmd"])
        assert result.returncode == -1

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exc_message_in_stderr(self, mock_run):
        mock_run.side_effect = RuntimeError("something went wrong")
        result = run_subprocess(["cmd"])
        assert "something went wrong" in result.stderr

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exc_stdout_empty(self, mock_run):
        mock_run.side_effect = ValueError("bad value")
        result = run_subprocess(["cmd"])
        assert result.stdout == ""

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exc_command_stored(self, mock_run):
        cmd = ["broken_cmd"]
        mock_run.side_effect = OSError("io error")
        result = run_subprocess(cmd)
        assert result.command == cmd


# ---------------------------------------------------------------------------
# run_subprocess – kwargs forwarded to subprocess.run
# ---------------------------------------------------------------------------

class TestRunSubprocessKwargs:
    """Tests that optional arguments are forwarded correctly to subprocess.run."""

    def _success_proc(self):
        return MagicMock(returncode=0, stdout="", stderr="")

    @patch("utils.subprocess_utils.subprocess.run")
    def test_capture_output_true_pipes_stdout(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], capture_output=True)
        _, kwargs = mock_run.call_args
        assert kwargs["stdout"] == subprocess.PIPE

    @patch("utils.subprocess_utils.subprocess.run")
    def test_capture_output_true_pipes_stderr(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], capture_output=True)
        _, kwargs = mock_run.call_args
        assert kwargs["stderr"] == subprocess.PIPE

    @patch("utils.subprocess_utils.subprocess.run")
    def test_capture_output_false_stdout_none(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], capture_output=False)
        _, kwargs = mock_run.call_args
        assert kwargs["stdout"] is None

    @patch("utils.subprocess_utils.subprocess.run")
    def test_capture_output_false_stderr_none(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], capture_output=False)
        _, kwargs = mock_run.call_args
        assert kwargs["stderr"] is None

    @patch("utils.subprocess_utils.subprocess.run")
    def test_cwd_passed_through(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["ls"], cwd="/tmp")
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == "/tmp"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_cwd_path_object_converted_to_str(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], cwd=Path("/tmp"))
        _, kwargs = mock_run.call_args
        assert isinstance(kwargs["cwd"], str)

    @patch("utils.subprocess_utils.subprocess.run")
    def test_env_passed_through(self, mock_run):
        mock_run.return_value = self._success_proc()
        custom_env = {"MY_VAR": "1"}
        run_subprocess(["cmd"], env=custom_env)
        kwargs = mock_run.call_args[1]
        assert kwargs["env"] == custom_env

    @patch("utils.subprocess_utils.subprocess.run")
    def test_input_data_passed_as_input_kwarg(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cat"], input_data="hello")
        kwargs = mock_run.call_args[1]
        assert kwargs["input"] == "hello"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_input_data_passed_through(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cat"], input_data="hello")
        kwargs = mock_run.call_args[1]
        assert kwargs["input"] == "hello"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_no_input_data_no_input_kwarg(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"])
        _, kwargs = mock_run.call_args
        assert "input" not in kwargs

    @patch("utils.subprocess_utils.subprocess.run")
    def test_timeout_passed_through(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], timeout=42.0)
        _, kwargs = mock_run.call_args
        assert kwargs["timeout"] == 42.0

    @patch("utils.subprocess_utils.subprocess.run")
    def test_text_mode_always_true(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"])
        _, kwargs = mock_run.call_args
        assert kwargs["text"] is True

    @patch("utils.subprocess_utils.subprocess.run")
    def test_no_cwd_no_cwd_kwarg(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], cwd=None)
        _, kwargs = mock_run.call_args
        assert "cwd" not in kwargs

    @patch("utils.subprocess_utils.subprocess.run")
    def test_no_env_no_env_kwarg(self, mock_run):
        mock_run.return_value = self._success_proc()
        run_subprocess(["cmd"], env=None)
        _, kwargs = mock_run.call_args
        assert "env" not in kwargs


# ---------------------------------------------------------------------------
# open_file_with_default_app
# ---------------------------------------------------------------------------

class TestOpenFileWithDefaultApp:
    """Tests for open_file_with_default_app()."""

    def test_nonexistent_file_returns_failure(self, tmp_path):
        result = open_file_with_default_app(tmp_path / "nope.txt")
        assert result.success is False
        assert "not found" in result.stderr.lower()

    def test_nonexistent_path_returncode_minus_one(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        result = open_file_with_default_app(missing)
        assert result.returncode == -1

    def test_nonexistent_path_no_subprocess_call(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        with patch("subprocess.run") as mock_run:
            open_file_with_default_app(missing)
        mock_run.assert_not_called()

    def test_nonexistent_path_accepts_string(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.txt")
        result = open_file_with_default_app(missing)
        assert result.success is False

    def test_nonexistent_path_returns_subprocess_result(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        result = open_file_with_default_app(missing)
        assert isinstance(result, SubprocessResult)

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_linux_uses_xdg_open(self, mock_system, mock_run, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("data")
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["xdg-open", str(f)],
        )
        open_file_with_default_app(f)
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "xdg-open"

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Darwin")
    def test_macos_uses_open(self, mock_system, mock_run, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("data")
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["open", str(f)],
        )
        open_file_with_default_app(f)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "open"

    @patch("utils.subprocess_utils.platform.system", return_value="Windows")
    def test_windows_uses_startfile(self, mock_system, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("data")
        with patch("os.startfile", create=True) as mock_startfile:
            result = open_file_with_default_app(f)
            mock_startfile.assert_called_once_with(str(f))
            assert result.success is True

    @patch("utils.subprocess_utils.platform.system", return_value="Windows")
    def test_windows_startfile_exception_success_false(self, mock_system, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("data")
        with patch("os.startfile", side_effect=OSError("no app"), create=True):
            result = open_file_with_default_app(f)
        assert result.success is False


# ---------------------------------------------------------------------------
# print_file
# ---------------------------------------------------------------------------

class TestPrintFile:
    """Tests for print_file()."""

    def test_nonexistent_file_returns_failure(self, tmp_path):
        result = print_file(tmp_path / "nope.txt")
        assert result.success is False
        assert "not found" in result.stderr.lower()

    def test_nonexistent_path_returncode_minus_one(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        result = print_file(missing)
        assert result.returncode == -1

    def test_nonexistent_path_no_subprocess_call(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        with patch("subprocess.run") as mock_run:
            print_file(missing)
        mock_run.assert_not_called()

    def test_nonexistent_path_accepts_string(self, tmp_path):
        missing = str(tmp_path / "does_not_exist.txt")
        result = print_file(missing)
        assert result.success is False

    def test_nonexistent_path_returns_subprocess_result(self, tmp_path):
        missing = tmp_path / "does_not_exist.txt"
        result = print_file(missing)
        assert isinstance(result, SubprocessResult)

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_linux_uses_lpr(self, mock_system, mock_run, tmp_path):
        f = tmp_path / "print_me.txt"
        f.write_text("content")
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["lpr", str(f)],
        )
        print_file(f)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "lpr"

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Darwin")
    def test_darwin_uses_lpr(self, mock_system, mock_run, tmp_path):
        f = tmp_path / "doc.txt"
        f.write_text("content")
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["lpr", str(f)],
        )
        print_file(f)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "lpr"

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Windows")
    def test_windows_uses_powershell(self, mock_system, mock_run, tmp_path):
        f = tmp_path / "print_me.txt"
        f.write_text("content")
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["powershell"],
        )
        print_file(f)
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "powershell"


# ---------------------------------------------------------------------------
# check_command_exists
# ---------------------------------------------------------------------------

class TestCheckCommandExists:
    """Tests for check_command_exists()."""

    @patch("utils.subprocess_utils.run_subprocess")
    def test_existing_command_returns_true(self, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0,
            stdout="/usr/bin/python3", stderr="",
            command=["which", "python3"],
        )
        assert check_command_exists("python3") is True

    @patch("utils.subprocess_utils.run_subprocess")
    def test_missing_command_returns_false(self, mock_run):
        mock_run.return_value = SubprocessResult(
            success=False, returncode=1,
            stdout="", stderr="",
            command=["which", "nonexistent"],
        )
        assert check_command_exists("nonexistent") is False

    @patch("utils.subprocess_utils.run_subprocess")
    def test_returns_bool_type(self, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["which", "ls"]
        )
        result = check_command_exists("ls")
        assert isinstance(result, bool)

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_linux_uses_which(self, mock_system, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0,
            stdout="/usr/bin/git", stderr="",
            command=["which", "git"],
        )
        check_command_exists("git")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "which"

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Darwin")
    def test_darwin_uses_which(self, mock_system, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0,
            stdout="/usr/bin/git", stderr="",
            command=["which", "git"],
        )
        check_command_exists("git")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "which"

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Windows")
    def test_windows_uses_where(self, mock_system, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0,
            stdout="C:\\Python\\python.exe", stderr="",
            command=["where", "python"],
        )
        check_command_exists("python")
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "where"

    @patch("utils.subprocess_utils.run_subprocess")
    def test_command_name_passed_to_run_subprocess(self, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["which", "ffmpeg"]
        )
        check_command_exists("ffmpeg")
        args, _ = mock_run.call_args
        assert "ffmpeg" in args[0]

    @patch("utils.subprocess_utils.run_subprocess")
    def test_log_on_error_false_passed(self, mock_run):
        mock_run.return_value = SubprocessResult(
            success=False, returncode=1, stdout="", stderr="",
            command=["which", "missing"]
        )
        check_command_exists("missing")
        _, kwargs = mock_run.call_args
        assert kwargs.get("log_on_error") is False

    @patch("utils.subprocess_utils.run_subprocess")
    def test_timeout_five_seconds(self, mock_run):
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["which", "ls"]
        )
        check_command_exists("ls")
        _, kwargs = mock_run.call_args
        assert kwargs.get("timeout") == 5
