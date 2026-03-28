"""Tests for utils.subprocess_utils — subprocess wrapper utilities."""

import subprocess
import os
import pytest
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from utils.subprocess_utils import (
    SubprocessResult,
    run_subprocess,
    open_file_with_default_app,
    print_file,
    check_command_exists,
    _get_windows_subprocess_kwargs,
)


class TestSubprocessResult:
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


class TestRunSubprocess:
    @patch("utils.subprocess_utils.subprocess.run")
    def test_successful_command(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="ok", stderr="")
        result = run_subprocess(["echo", "hello"])
        assert result.success is True
        assert result.returncode == 0
        assert result.stdout == "ok"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_failed_command(self, mock_run):
        mock_run.return_value = Mock(returncode=1, stdout="", stderr="fail")
        result = run_subprocess(["false"])
        assert result.success is False
        assert result.returncode == 1

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
    def test_file_not_found(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        result = run_subprocess(["nonexistent"])
        assert result.success is False
        assert result.returncode == -1
        assert "not found" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_permission_error(self, mock_run):
        mock_run.side_effect = PermissionError()
        result = run_subprocess(["restricted"])
        assert result.success is False
        assert "Permission denied" in result.stderr or "permission" in result.stderr.lower()

    @patch("utils.subprocess_utils.subprocess.run")
    def test_generic_exception(self, mock_run):
        mock_run.side_effect = Exception("unexpected")
        result = run_subprocess(["boom"])
        assert result.success is False
        assert "unexpected" in result.stderr

    @patch("utils.subprocess_utils.subprocess.run")
    def test_cwd_passed_through(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        run_subprocess(["ls"], cwd="/tmp")
        kwargs = mock_run.call_args[1]
        assert kwargs["cwd"] == "/tmp"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_env_passed_through(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        custom_env = {"MY_VAR": "1"}
        run_subprocess(["cmd"], env=custom_env)
        kwargs = mock_run.call_args[1]
        assert kwargs["env"] == custom_env

    @patch("utils.subprocess_utils.subprocess.run")
    def test_input_data_passed_through(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        run_subprocess(["cat"], input_data="hello")
        kwargs = mock_run.call_args[1]
        assert kwargs["input"] == "hello"

    @patch("utils.subprocess_utils.subprocess.run")
    def test_command_stored_in_result(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
        result = run_subprocess(["git", "status"])
        assert result.command == ["git", "status"]

    @patch("utils.subprocess_utils.subprocess.run")
    def test_none_stdout_stderr_coerced_to_empty(self, mock_run):
        mock_run.return_value = Mock(returncode=0, stdout=None, stderr=None)
        result = run_subprocess(["cmd"])
        assert result.stdout == ""
        assert result.stderr == ""


class TestGetWindowsSubprocessKwargs:
    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_non_windows_returns_empty(self, mock_system):
        assert _get_windows_subprocess_kwargs() == {}

    @patch("utils.subprocess_utils.platform.system", return_value="Darwin")
    def test_macos_returns_empty(self, mock_system):
        assert _get_windows_subprocess_kwargs() == {}


class TestOpenFileWithDefaultApp:
    def test_nonexistent_file_returns_failure(self, tmp_path):
        result = open_file_with_default_app(tmp_path / "nope.txt")
        assert result.success is False
        assert "not found" in result.stderr.lower()

    @patch("utils.subprocess_utils.run_subprocess")
    @patch("utils.subprocess_utils.platform.system", return_value="Linux")
    def test_linux_uses_xdg_open(self, mock_system, mock_run, tmp_path):
        f = tmp_path / "doc.pdf"
        f.write_text("data")
        mock_run.return_value = SubprocessResult(
            success=True, returncode=0, stdout="", stderr="",
            command=["xdg-open", str(f)],
        )
        result = open_file_with_default_app(f)
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
        result = open_file_with_default_app(f)
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


class TestPrintFile:
    def test_nonexistent_file_returns_failure(self, tmp_path):
        result = print_file(tmp_path / "nope.txt")
        assert result.success is False
        assert "not found" in result.stderr.lower()

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


class TestCheckCommandExists:
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
