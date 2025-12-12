"""
Base setup class for initialization components.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class BaseSetup(ABC):
    """Abstract base class for setup components.

    Each setup component handles a specific aspect of application
    initialization. Subclasses must implement the initialize() method.

    Attributes:
        app: Reference to the main application instance
        logger: Logger for this setup component
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the setup component.

        Args:
            app: The main application instance
        """
        self.app = app
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def initialize(self) -> None:
        """Perform initialization for this component.

        Raises:
            Exception: If initialization fails
        """
        pass

    @abstractmethod
    def cleanup(self) -> None:
        """Clean up resources created during initialization.

        Called during application shutdown.
        """
        pass

    def _log_start(self, task: str) -> None:
        """Log the start of an initialization task."""
        self.logger.debug(f"Starting: {task}")

    def _log_complete(self, task: str) -> None:
        """Log the completion of an initialization task."""
        self.logger.debug(f"Completed: {task}")

    def _log_error(self, task: str, error: Exception) -> None:
        """Log an error during initialization."""
        self.logger.error(f"Failed: {task} - {error}", exc_info=True)
