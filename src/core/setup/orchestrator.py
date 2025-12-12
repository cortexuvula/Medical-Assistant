"""
Setup orchestrator for Medical Assistant.

Coordinates initialization of all setup components in the correct order.
"""

import logging
from typing import List, TYPE_CHECKING

from .base import BaseSetup
from .threading_setup import ThreadingSetup
from .security_setup import SecuritySetup
from .database_setup import DatabaseSetup

if TYPE_CHECKING:
    from core.app import MedicalDictationApp


class SetupOrchestrator:
    """Orchestrates application initialization.

    This class coordinates the initialization of all setup components
    in the correct dependency order. It also provides cleanup functionality
    for graceful shutdown.

    Example usage:
        orchestrator = SetupOrchestrator(app)
        try:
            orchestrator.initialize_all()
        except Exception:
            orchestrator.cleanup_all()
            raise
    """

    def __init__(self, app: 'MedicalDictationApp'):
        """Initialize the orchestrator.

        Args:
            app: The main application instance
        """
        self.app = app
        self.logger = logging.getLogger(__name__)
        self._setup_components: List[BaseSetup] = []
        self._initialized_components: List[BaseSetup] = []

        # Register setup components in dependency order
        self._register_components()

    def _register_components(self) -> None:
        """Register setup components in dependency order.

        Components are initialized in the order they are registered.
        Later components may depend on earlier ones.
        """
        # Order matters:
        # 1. Threading - needed by most other components
        # 2. Security - API keys needed before API calls
        # 3. Database - needed for data storage
        self._setup_components = [
            ThreadingSetup(self.app),
            SecuritySetup(self.app),
            DatabaseSetup(self.app),
        ]

    def initialize_all(self) -> None:
        """Initialize all registered components.

        Components are initialized in registration order.
        If any component fails, previously initialized components
        are cleaned up.

        Raises:
            Exception: If any initialization fails
        """
        self.logger.info("Starting application initialization")

        for component in self._setup_components:
            component_name = component.__class__.__name__
            try:
                self.logger.debug(f"Initializing {component_name}")
                component.initialize()
                self._initialized_components.append(component)
                self.logger.debug(f"Initialized {component_name}")
            except Exception as e:
                self.logger.error(f"Failed to initialize {component_name}: {e}")
                # Clean up already-initialized components
                self.cleanup_all()
                raise

        self.logger.info("Application initialization complete")

    def cleanup_all(self) -> None:
        """Clean up all initialized components.

        Components are cleaned up in reverse initialization order.
        All cleanup errors are logged but don't stop the process.
        """
        self.logger.info("Starting application cleanup")

        # Clean up in reverse order
        for component in reversed(self._initialized_components):
            component_name = component.__class__.__name__
            try:
                self.logger.debug(f"Cleaning up {component_name}")
                component.cleanup()
                self.logger.debug(f"Cleaned up {component_name}")
            except Exception as e:
                self.logger.error(f"Error cleaning up {component_name}: {e}")

        self._initialized_components.clear()
        self.logger.info("Application cleanup complete")

    def initialize_component(self, component_class: type) -> None:
        """Initialize a specific component.

        Useful for lazy initialization or re-initialization.

        Args:
            component_class: The class of the component to initialize

        Raises:
            ValueError: If component class is not registered
            Exception: If initialization fails
        """
        for component in self._setup_components:
            if isinstance(component, component_class):
                if component not in self._initialized_components:
                    component.initialize()
                    self._initialized_components.append(component)
                return

        raise ValueError(f"Component {component_class.__name__} not registered")

    def cleanup_component(self, component_class: type) -> None:
        """Clean up a specific component.

        Args:
            component_class: The class of the component to clean up
        """
        for component in self._initialized_components:
            if isinstance(component, component_class):
                component.cleanup()
                self._initialized_components.remove(component)
                return
