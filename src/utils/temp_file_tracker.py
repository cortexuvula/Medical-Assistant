"""
Temp File Tracker - Ensures PHI-containing temp files are cleaned up.

Singleton that tracks temp file paths and provides atexit cleanup
as a safety net for crash/abnormal shutdown scenarios.
"""

import atexit
import os
import threading

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class TempFileTracker:
    """Tracks temporary files and ensures cleanup on exit."""

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self._files: set[str] = set()
        self._files_lock = threading.Lock()
        atexit.register(self.cleanup_all)

    @classmethod
    def instance(cls) -> "TempFileTracker":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, path: str) -> None:
        """Register a temp file for tracking."""
        with self._files_lock:
            self._files.add(path)

    def unregister(self, path: str) -> None:
        """Unregister a temp file (already cleaned up)."""
        with self._files_lock:
            self._files.discard(path)

    def cleanup_all(self) -> int:
        """Delete all tracked temp files. Returns count of files deleted."""
        with self._files_lock:
            paths = list(self._files)
            self._files.clear()

        deleted = 0
        for path in paths:
            try:
                os.unlink(path)
                deleted += 1
                logger.info(f"Cleaned up tracked temp file: {path}")
            except FileNotFoundError:
                pass  # Already cleaned up
            except OSError as e:
                logger.warning(f"Failed to clean up temp file {path}: {e}")

        if deleted:
            logger.info(f"TempFileTracker cleaned up {deleted} file(s)")
        return deleted
