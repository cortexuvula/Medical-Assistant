"""
Single Instance Manager

Ensures only one instance of the application runs at a time.
Uses a PID-based lock file which is more reliable than sockets on macOS,
as it doesn't suffer from TIME_WAIT issues after crashes.
"""

import os
import sys
import atexit
import platform
from pathlib import Path
from utils.structured_logging import get_logger

logger = get_logger(__name__)


def _get_lock_file_path() -> Path:
    """Get the path for the lock file."""
    if platform.system() == 'Darwin':
        # macOS: Use ~/Library/Application Support
        lock_dir = Path.home() / "Library" / "Application Support" / "MedicalAssistant"
    elif platform.system() == 'Windows':
        # Windows: Use %LOCALAPPDATA%
        lock_dir = Path(os.environ.get('LOCALAPPDATA', Path.home())) / "MedicalAssistant"
    else:
        # Linux: Use ~/.local/share
        lock_dir = Path.home() / ".local" / "share" / "MedicalAssistant"

    lock_dir.mkdir(parents=True, exist_ok=True)
    return lock_dir / "app.lock"


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    if platform.system() == 'Windows':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        except Exception:
            return False
    else:
        # Unix-like (macOS, Linux)
        try:
            os.kill(pid, 0)  # Signal 0 doesn't kill, just checks if process exists
            return True
        except OSError:
            return False


def _read_lock_file(lock_file: Path) -> int | None:
    """Read PID from lock file. Returns None if file doesn't exist or is invalid."""
    try:
        if lock_file.exists():
            content = lock_file.read_text().strip()
            return int(content)
    except (ValueError, OSError) as e:
        logger.debug(f"Error reading lock file: {e}")
    return None


def _write_lock_file(lock_file: Path, pid: int) -> bool:
    """Write PID to lock file."""
    try:
        lock_file.write_text(str(pid))
        return True
    except OSError as e:
        logger.error(f"Failed to write lock file: {e}")
        return False


def _remove_lock_file(lock_file: Path) -> None:
    """Remove the lock file."""
    try:
        if lock_file.exists():
            lock_file.unlink()
            logger.debug("Lock file removed")
    except OSError as e:
        logger.debug(f"Error removing lock file: {e}")


def ensure_single_instance() -> bool:
    """
    Ensure only one instance of the application is running.

    Returns:
        True if this is the only instance (safe to continue)
        False if another instance is already running (should exit)
    """
    lock_file = _get_lock_file_path()
    current_pid = os.getpid()

    # Check if lock file exists
    existing_pid = _read_lock_file(lock_file)

    if existing_pid is not None:
        # Lock file exists - check if the process is still running
        if existing_pid == current_pid:
            # Same process, probably a restart within the same process
            logger.debug("Lock file contains our own PID")
            return True

        if _is_process_running(existing_pid):
            # Another instance is running
            logger.info(f"Another instance is running (PID: {existing_pid})")
            return False
        else:
            # Stale lock file - process no longer exists
            logger.info(f"Removing stale lock file (PID {existing_pid} not running)")
            _remove_lock_file(lock_file)

    # Create lock file with our PID
    if _write_lock_file(lock_file, current_pid):
        # Register cleanup on exit
        atexit.register(_remove_lock_file, lock_file)
        logger.info(f"Single-instance lock acquired (PID: {current_pid})")
        return True

    # Failed to write lock file - allow app to start anyway
    logger.warning("Could not write lock file, allowing start")
    return True


def show_already_running_message():
    """Show a message that another instance is already running."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        # Create a hidden root window
        root = tk.Tk()
        root.withdraw()

        messagebox.showinfo(
            "Medical Assistant",
            "Medical Assistant is already running.\n\n"
            "Please check your taskbar/dock for the existing window."
        )

        root.destroy()

    except Exception as e:
        # Fallback to console message
        print("Medical Assistant is already running.")
        print("Please check your taskbar/dock for the existing window.")
        logger.info(f"Could not show GUI message: {e}")
