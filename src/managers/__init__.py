"""
Managers package for Medical Assistant.

This package provides various manager classes for handling application state,
resources, and services. Managers follow a consistent singleton pattern using
the SingletonManager base class.

Singleton Pattern:
    Managers that need single instances should inherit from SingletonManager:

    class MyManager(SingletonManager):
        def _initialize(self):
            # One-time initialization code
            self.data = {}

    # Access singleton via class method
    manager = MyManager.get_instance()

Lazy Initialization Pattern:
    For managers that should be lazily initialized (created on first access):

    _my_manager: Optional[MyManager] = None

    def get_my_manager() -> MyManager:
        global _my_manager
        if _my_manager is None:
            _my_manager = MyManager.get_instance()
        return _my_manager
"""

import logging
import threading
from abc import ABC
from typing import TypeVar, Type, Optional

logger = logging.getLogger(__name__)

T = TypeVar('T', bound='SingletonManager')


class SingletonManager(ABC):
    """Base class for singleton managers.

    This class provides a thread-safe singleton pattern for manager classes.
    Subclasses should override `_initialize()` to perform one-time setup.

    The singleton pattern ensures:
    1. Only one instance exists per class
    2. Thread-safe initialization
    3. Lazy initialization (instance created on first access)
    4. Clear initialization separation from construction

    Example:
        class DataManager(SingletonManager):
            def _initialize(self):
                self.cache = {}
                self.load_data()

        # Get the singleton instance
        manager = DataManager.get_instance()

    Note:
        Avoid using __init__ for initialization logic as it may be called
        multiple times. Use _initialize() instead.
    """

    _instances: dict = {}
    _lock = threading.Lock()

    def __new__(cls: Type[T], *args, **kwargs) -> T:
        """Create or return the singleton instance.

        Thread-safe implementation using double-checked locking.
        """
        if cls not in cls._instances:
            with cls._lock:
                # Double-check after acquiring lock
                if cls not in cls._instances:
                    instance = super().__new__(cls)
                    instance._initialized = False
                    cls._instances[cls] = instance
        return cls._instances[cls]

    def __init__(self):
        """Initialize the manager.

        Note: __init__ may be called multiple times on the same instance.
        Use _initialize() for one-time setup logic.
        """
        if not self._initialized:
            with self._lock:
                if not self._initialized:
                    self._initialize()
                    self._initialized = True
                    logger.debug(f"{self.__class__.__name__} initialized")

    def _initialize(self) -> None:
        """Perform one-time initialization.

        Override this method in subclasses for setup logic.
        This is guaranteed to be called only once per singleton instance.
        """
        pass

    @classmethod
    def get_instance(cls: Type[T]) -> T:
        """Get the singleton instance.

        This is the preferred way to access the singleton.

        Returns:
            The singleton instance of this manager class.
        """
        return cls()

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (mainly for testing).

        Warning: This should only be used in tests. Resetting a manager
        in production code can lead to inconsistent state.
        """
        with cls._lock:
            if cls in cls._instances:
                instance = cls._instances.pop(cls)
                if hasattr(instance, '_cleanup'):
                    try:
                        instance._cleanup()
                    except Exception as e:
                        logger.warning(f"Error during {cls.__name__} cleanup: {e}")

    def _cleanup(self) -> None:
        """Clean up resources before instance reset.

        Override this method in subclasses to release resources.
        Called by reset_instance() before the instance is discarded.
        """
        pass


class ManagerRegistry:
    """Registry for tracking and managing all singleton managers.

    This class provides centralized management of manager instances,
    useful for application shutdown and testing.

    Example:
        # Register managers during app initialization
        registry = ManagerRegistry()
        registry.register(DataManager)
        registry.register(CacheManager)

        # Clean up all managers during shutdown
        registry.cleanup_all()
    """

    def __init__(self):
        """Initialize the registry."""
        self._manager_classes: list = []
        self._lock = threading.Lock()

    def register(self, manager_class: Type[SingletonManager]) -> None:
        """Register a manager class for tracking.

        Args:
            manager_class: The manager class to register
        """
        with self._lock:
            if manager_class not in self._manager_classes:
                self._manager_classes.append(manager_class)

    def cleanup_all(self) -> None:
        """Clean up all registered managers.

        Calls reset_instance() on each registered manager in reverse
        registration order (LIFO).
        """
        with self._lock:
            for manager_class in reversed(self._manager_classes):
                try:
                    manager_class.reset_instance()
                except Exception as e:
                    logger.error(f"Error cleaning up {manager_class.__name__}: {e}")

    def get_registered(self) -> list:
        """Get list of registered manager classes."""
        with self._lock:
            return list(self._manager_classes)


# Global registry for manager cleanup
_manager_registry = ManagerRegistry()


def get_manager_registry() -> ManagerRegistry:
    """Get the global manager registry."""
    return _manager_registry
