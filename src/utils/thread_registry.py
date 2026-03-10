"""
Thread Registry - Tracks I/O threads for graceful shutdown.

Lightweight singleton that registers background threads doing I/O
(DB writes, file ops, API calls) so they can be joined on shutdown.
Uses WeakSet so threads are auto-removed when garbage collected.
"""

import threading
import weakref
from typing import Dict

from utils.structured_logging import get_logger

logger = get_logger(__name__)


class ThreadRegistry:
    """Registry for tracking background I/O threads."""

    _instance = None
    _init_lock = threading.Lock()

    def __init__(self):
        self._threads: weakref.WeakSet[threading.Thread] = weakref.WeakSet()
        self._names: weakref.WeakValueDictionary[str, threading.Thread] = (
            weakref.WeakValueDictionary()
        )
        self._lock = threading.Lock()

    @classmethod
    def instance(cls) -> "ThreadRegistry":
        """Get or create the singleton instance."""
        if cls._instance is None:
            with cls._init_lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, thread: threading.Thread) -> None:
        """Register a thread for tracking.

        Args:
            name: Descriptive name for logging
            thread: The thread to track
        """
        with self._lock:
            self._threads.add(thread)
            self._names[name] = thread
        logger.debug(f"Registered thread: {name}")

    def get_active_threads(self) -> list[tuple[str, threading.Thread]]:
        """Return list of (name, thread) for alive threads."""
        with self._lock:
            return [
                (name, thread)
                for name, thread in list(self._names.items())
                if thread.is_alive()
            ]

    def shutdown(self, timeout: float = 10.0) -> Dict[str, bool]:
        """Join all active threads with timeout.

        Args:
            timeout: Maximum seconds to wait for all threads combined

        Returns:
            Dict mapping thread name to whether it completed
        """
        active = self.get_active_threads()
        if not active:
            logger.info("ThreadRegistry: no active threads to wait for")
            return {}

        logger.info(f"ThreadRegistry: waiting for {len(active)} thread(s) to complete")

        results = {}
        remaining = timeout
        for name, thread in active:
            if remaining <= 0:
                results[name] = False
                continue

            import time
            start = time.monotonic()
            thread.join(timeout=remaining)
            elapsed = time.monotonic() - start
            remaining -= elapsed

            completed = not thread.is_alive()
            results[name] = completed
            if not completed:
                logger.warning(f"Thread '{name}' did not complete within timeout")

        completed_count = sum(1 for v in results.values() if v)
        timed_out = sum(1 for v in results.values() if not v)
        if timed_out:
            logger.warning(
                f"ThreadRegistry shutdown: {completed_count} completed, {timed_out} timed out"
            )
        else:
            logger.info(f"ThreadRegistry: all {completed_count} thread(s) completed")

        return results
