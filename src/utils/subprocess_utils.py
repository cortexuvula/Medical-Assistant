"""
Subprocess Utilities Module

Provides wrapper functions for subprocess operations with proper output capture,
logging, and platform-specific handling for improved debugging.

Usage:
    from utils.subprocess_utils import run_subprocess, open_file_with_default_app

    # Run a command with output capture
    result = run_subprocess(['ffmpeg', '-version'], timeout=30)
    if result.success:
        print(result.stdout)
    else:
        print(f"Error: {result.stderr}")

    # Open a file with system default application
    open_file_with_default_app('/path/to/file.pdf')
"""

import logging
import subprocess
import platform
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Union, Dict, Any

logger = logging.getLogger(__name__)


@dataclass
class SubprocessResult:
    """Result from a subprocess execution."""
    success: bool
    returncode: int
    stdout: str
    stderr: str
    command: List[str]

    @property
    def output(self) -> str:
        """Combined stdout and stderr for convenience."""
        parts = []
        if self.stdout:
            parts.append(self.stdout)
        if self.stderr:
            parts.append(self.stderr)
        return '\n'.join(parts)


def _get_windows_subprocess_kwargs() -> Dict[str, Any]:
    """Get kwargs to suppress console windows on Windows."""
    kwargs = {}
    if platform.system() == 'Windows':
        kwargs['creationflags'] = subprocess.CREATE_NO_WINDOW
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = subprocess.SW_HIDE
        kwargs['startupinfo'] = si
    return kwargs


def run_subprocess(
    command: List[str],
    timeout: Optional[float] = 60.0,
    capture_output: bool = True,
    log_on_error: bool = True,
    log_command: bool = False,
    cwd: Optional[Union[str, Path]] = None,
    env: Optional[Dict[str, str]] = None,
    input_data: Optional[str] = None,
    suppress_console: bool = True
) -> SubprocessResult:
    """Run a subprocess with proper output capture and error handling.

    Args:
        command: Command and arguments as a list
        timeout: Timeout in seconds (None for no timeout)
        capture_output: Whether to capture stdout/stderr
        log_on_error: Whether to log command and output on non-zero exit
        log_command: Whether to log the command before running
        cwd: Working directory for the command
        env: Environment variables (None uses current environment)
        input_data: Data to send to stdin
        suppress_console: Whether to suppress console window on Windows

    Returns:
        SubprocessResult with success status, output, and return code

    Example:
        >>> result = run_subprocess(['git', 'status'])
        >>> if result.success:
        ...     print("Git status:", result.stdout)
    """
    if log_command:
        logger.debug(f"Running command: {' '.join(command)}")

    kwargs = {
        'stdout': subprocess.PIPE if capture_output else None,
        'stderr': subprocess.PIPE if capture_output else None,
        'text': True,
        'timeout': timeout,
    }

    if cwd:
        kwargs['cwd'] = str(cwd)
    if env:
        kwargs['env'] = env
    if input_data:
        kwargs['input'] = input_data

    # Add Windows-specific kwargs to suppress console
    if suppress_console:
        kwargs.update(_get_windows_subprocess_kwargs())

    try:
        result = subprocess.run(command, **kwargs)

        stdout = result.stdout or ''
        stderr = result.stderr or ''
        success = result.returncode == 0

        if not success and log_on_error:
            logger.warning(
                f"Subprocess failed with return code {result.returncode}\n"
                f"Command: {' '.join(command)}\n"
                f"Stdout: {stdout[:500] if stdout else '(empty)'}\n"
                f"Stderr: {stderr[:500] if stderr else '(empty)'}"
            )

        return SubprocessResult(
            success=success,
            returncode=result.returncode,
            stdout=stdout,
            stderr=stderr,
            command=command
        )

    except subprocess.TimeoutExpired as e:
        logger.error(f"Subprocess timed out after {timeout}s: {' '.join(command)}")
        return SubprocessResult(
            success=False,
            returncode=-1,
            stdout=e.stdout or '' if hasattr(e, 'stdout') else '',
            stderr=f"Process timed out after {timeout} seconds",
            command=command
        )

    except FileNotFoundError:
        logger.error(f"Command not found: {command[0]}")
        return SubprocessResult(
            success=False,
            returncode=-1,
            stdout='',
            stderr=f"Command not found: {command[0]}",
            command=command
        )

    except PermissionError:
        logger.error(f"Permission denied running: {' '.join(command)}")
        return SubprocessResult(
            success=False,
            returncode=-1,
            stdout='',
            stderr=f"Permission denied: {command[0]}",
            command=command
        )

    except Exception as e:
        logger.error(f"Unexpected error running subprocess: {e}")
        return SubprocessResult(
            success=False,
            returncode=-1,
            stdout='',
            stderr=str(e),
            command=command
        )


def open_file_with_default_app(file_path: Union[str, Path]) -> SubprocessResult:
    """Open a file with the system's default application.

    Args:
        file_path: Path to the file to open

    Returns:
        SubprocessResult indicating success/failure

    Example:
        >>> result = open_file_with_default_app('/path/to/document.pdf')
        >>> if not result.success:
        ...     print(f"Failed to open file: {result.stderr}")
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return SubprocessResult(
            success=False,
            returncode=-1,
            stdout='',
            stderr=f"File not found: {file_path}",
            command=['open', str(file_path)]
        )

    system = platform.system()

    if system == 'Darwin':
        command = ['open', str(file_path)]
    elif system == 'Windows':
        command = ['start', '', str(file_path)]
        # Windows 'start' requires shell=True, use os.startfile instead
        try:
            import os
            os.startfile(str(file_path))
            return SubprocessResult(
                success=True,
                returncode=0,
                stdout='',
                stderr='',
                command=['os.startfile', str(file_path)]
            )
        except Exception as e:
            return SubprocessResult(
                success=False,
                returncode=-1,
                stdout='',
                stderr=str(e),
                command=['os.startfile', str(file_path)]
            )
    else:  # Linux and others
        command = ['xdg-open', str(file_path)]

    return run_subprocess(command, timeout=10, log_on_error=True)


def print_file(file_path: Union[str, Path]) -> SubprocessResult:
    """Print a file using the system's default printer.

    Args:
        file_path: Path to the file to print

    Returns:
        SubprocessResult indicating success/failure
    """
    file_path = Path(file_path)

    if not file_path.exists():
        return SubprocessResult(
            success=False,
            returncode=-1,
            stdout='',
            stderr=f"File not found: {file_path}",
            command=['lpr', str(file_path)]
        )

    system = platform.system()

    if system == 'Darwin':
        command = ['lpr', str(file_path)]
    elif system == 'Windows':
        # Windows printing via PowerShell
        command = ['powershell', '-Command', f'Start-Process -FilePath "{file_path}" -Verb Print']
    else:  # Linux
        command = ['lpr', str(file_path)]

    return run_subprocess(command, timeout=30, log_on_error=True)


def check_command_exists(command: str) -> bool:
    """Check if a command exists in the system PATH.

    Args:
        command: Name of the command to check

    Returns:
        True if command exists and is executable
    """
    system = platform.system()

    if system == 'Windows':
        check_cmd = ['where', command]
    else:
        check_cmd = ['which', command]

    result = run_subprocess(check_cmd, timeout=5, log_on_error=False)
    return result.success
