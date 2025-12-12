"""
Threading setup for Medical Assistant.

Handles initialization of executors and thread pools.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

from .base import BaseSetup

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class ThreadingSetup(BaseSetup):
    """Setup component for threading and executors.

    Initializes:
    - Background executor for async operations
    - Thread pool configuration
    """

    DEFAULT_MAX_WORKERS = 4

    def initialize(self) -> None:
        """Initialize threading components."""
        self._log_start("Thread executor setup")

        # Create background executor for async operations
        max_workers = self.DEFAULT_MAX_WORKERS
        self.app.executor = ThreadPoolExecutor(
            max_workers=max_workers,
            thread_name_prefix="MedAssist-"
        )

        self._log_complete("Thread executor setup")

    def cleanup(self) -> None:
        """Shutdown thread executor."""
        if hasattr(self.app, 'executor') and self.app.executor:
            self._log_start("Executor shutdown")
            try:
                self.app.executor.shutdown(wait=False)
            except Exception as e:
                self._log_error("Executor shutdown", e)
            self._log_complete("Executor shutdown")
