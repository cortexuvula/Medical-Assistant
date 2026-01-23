"""
Single Instance Manager

Ensures only one instance of the application runs at a time.
Uses socket-based locking which is more reliable than file locks,
especially on macOS where file locks can have issues with App bundles.
"""

import socket
import sys
import os
import atexit
from pathlib import Path
from utils.structured_logging import get_logger

logger = get_logger(__name__)

# Use a fixed port for the socket lock
# Port in the dynamic/private range (49152-65535)
LOCK_PORT = 59847
LOCK_HOST = '127.0.0.1'


class SingleInstanceManager:
    """Manages single-instance enforcement using a socket lock."""

    _instance = None
    _socket = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._socket = None
        self._lock_file = None

    def acquire_lock(self) -> bool:
        """
        Try to acquire the single-instance lock.

        Returns:
            True if lock acquired (we're the first instance)
            False if another instance is already running
        """
        try:
            # Create a socket and try to bind to our port
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)

            # Try to bind - will fail if another instance has it
            self._socket.bind((LOCK_HOST, LOCK_PORT))
            self._socket.listen(1)

            # Register cleanup
            atexit.register(self.release_lock)

            logger.info("Single-instance lock acquired")
            return True

        except socket.error as e:
            # Port already in use - another instance is running
            logger.info(f"Another instance is already running (socket error: {e})")
            if self._socket:
                try:
                    self._socket.close()
                except Exception:
                    pass
                self._socket = None
            return False
        except Exception as e:
            # Unexpected error - log but allow app to start
            logger.warning(f"Single-instance check error (allowing start): {e}")
            return True

    def release_lock(self):
        """Release the single-instance lock."""
        if self._socket:
            try:
                self._socket.close()
                logger.debug("Single-instance lock released")
            except Exception as e:
                logger.debug(f"Error releasing lock: {e}")
            finally:
                self._socket = None

    def is_another_instance_running(self) -> bool:
        """
        Check if another instance is running without acquiring the lock.

        Returns:
            True if another instance is running
            False if no other instance detected
        """
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
            test_socket.settimeout(1)

            # Try to connect to the lock port
            result = test_socket.connect_ex((LOCK_HOST, LOCK_PORT))
            test_socket.close()

            # If connect succeeds (result == 0), another instance has the port
            return result == 0

        except Exception:
            return False


def get_single_instance_manager() -> SingleInstanceManager:
    """Get the singleton instance manager."""
    return SingleInstanceManager()


def ensure_single_instance() -> bool:
    """
    Ensure only one instance of the application is running.

    Returns:
        True if this is the only instance (safe to continue)
        False if another instance is already running (should exit)
    """
    manager = get_single_instance_manager()
    return manager.acquire_lock()


def show_already_running_message():
    """Show a message that another instance is already running."""
    try:
        # Try to use tkinter messagebox if available
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
