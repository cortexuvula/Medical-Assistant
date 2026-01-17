"""
Base Provider Manager

This module provides an abstract base class for all provider managers
(TTS, Translation, STT). It encapsulates common patterns for:
- Provider registration and instantiation
- Provider caching and lazy initialization
- Settings-based provider selection
- Thread-safe singleton patterns
- OperationResult-based error handling

Usage:
    class MyManager(ProviderManager[MyProvider]):
        def _get_providers(self) -> Dict[str, Type[MyProvider]]:
            return {"provider1": Provider1, "provider2": Provider2}

        def _create_provider_instance(self, provider_class, name):
            return provider_class(api_key=self._get_api_key(name))

        def _get_settings_key(self) -> str:
            return "my_provider"
"""

import threading
from utils.structured_logging import get_logger
from abc import ABC, abstractmethod
from typing import Dict, Type, Optional, TypeVar, Generic, Any

from utils.error_handling import OperationResult
from utils.security import get_security_manager

logger = get_logger(__name__)

# Generic type for the provider
T = TypeVar('T')


class ProviderManager(ABC, Generic[T]):
    """Abstract base class for all provider managers.

    This class provides common functionality for managing provider instances:
    - Provider registration via _get_providers()
    - Lazy provider instantiation with caching
    - Settings-based provider selection
    - API key retrieval via security manager
    - OperationResult-based error handling methods

    Subclasses must implement:
    - _get_providers(): Return mapping of provider names to classes
    - _create_provider_instance(): Create and configure a provider instance
    - _get_settings_key(): Return the settings key for this manager

    Attributes:
        providers: Mapping of provider names to provider classes
        security_manager: Security manager for API key retrieval
    """

    def __init__(self):
        """Initialize the provider manager."""
        # Using module-level logger
        self._current_provider: Optional[str] = None
        self._provider_instance: Optional[T] = None
        self.security_manager = get_security_manager()
        self.providers: Dict[str, Type[T]] = self._get_providers()

    @abstractmethod
    def _get_providers(self) -> Dict[str, Type[T]]:
        """Return mapping of provider names to provider classes.

        Subclasses must implement this to register their available providers.

        Returns:
            Dictionary mapping provider names to their class types

        Example:
            def _get_providers(self):
                return {
                    "google": GoogleProvider,
                    "amazon": AmazonProvider,
                    "local": LocalProvider,
                }
        """
        pass

    @abstractmethod
    def _create_provider_instance(self, provider_class: Type[T], provider_name: str) -> T:
        """Create and configure a provider instance.

        Subclasses must implement this to handle provider-specific initialization.

        Args:
            provider_class: The provider class to instantiate
            provider_name: Name of the provider being created

        Returns:
            Configured provider instance

        Example:
            def _create_provider_instance(self, provider_class, provider_name):
                api_key = self._get_api_key(provider_name)
                return provider_class(api_key=api_key, timeout=30)
        """
        pass

    @abstractmethod
    def _get_settings_key(self) -> str:
        """Return the settings key for this manager.

        This is used to retrieve provider settings from SETTINGS.

        Returns:
            Settings key string (e.g., "tts", "translation", "stt")
        """
        pass

    def _get_provider_name_from_settings(self) -> str:
        """Get the current provider name from settings.

        Override this method if your manager uses a different settings structure.

        Returns:
            Provider name from settings, or default if not set
        """
        from settings.settings import SETTINGS
        settings = SETTINGS.get(self._get_settings_key(), {})
        return settings.get("provider", self._get_default_provider())

    def _get_default_provider(self) -> str:
        """Get the default provider name.

        Override this if your manager has a specific default provider.

        Returns:
            Name of the default provider
        """
        # Return first registered provider as default
        providers = list(self.providers.keys())
        return providers[0] if providers else ""

    def _get_api_key(self, provider_name: str) -> str:
        """Get API key for a provider from security manager.

        Args:
            provider_name: Name of the provider

        Returns:
            API key string, or empty string if not found
        """
        try:
            key = self.security_manager.get_api_key(provider_name)
            return key or ""
        except Exception as e:
            logger.warning(f"Failed to get API key for {provider_name}: {e}")
            return ""

    def _get_cache_key(self) -> str:
        """Generate a cache key for the current provider configuration.

        Override this if your manager needs more complex cache invalidation.

        Returns:
            Cache key string
        """
        return self._get_provider_name_from_settings()

    def get_provider(self) -> T:
        """Get the current provider instance, creating it if necessary.

        This method implements lazy initialization with caching. The provider
        is only created when first requested, and subsequent calls return
        the cached instance unless settings have changed.

        Returns:
            Provider instance

        Raises:
            ValueError: If no valid provider can be created
        """
        cache_key = self._get_cache_key()

        if self._current_provider != cache_key or self._provider_instance is None:
            self._create_provider(self._get_provider_name_from_settings())
            self._current_provider = cache_key

        return self._provider_instance

    def get_provider_safe(self) -> OperationResult[T]:
        """Get provider instance with OperationResult return type.

        Returns:
            OperationResult containing provider on success, or error details on failure
        """
        try:
            provider = self.get_provider()
            return OperationResult.success(provider)
        except Exception as e:
            return OperationResult.failure(
                f"Failed to get provider: {str(e)}",
                error_code="PROVIDER_ERROR",
                exception=e
            )

    def _create_provider(self, provider_name: str) -> None:
        """Create a new provider instance.

        Args:
            provider_name: Name of the provider to create

        Raises:
            ValueError: If provider name is not registered
        """
        if provider_name not in self.providers:
            available = ", ".join(self.providers.keys())
            raise ValueError(
                f"Unknown provider: {provider_name}. "
                f"Available providers: {available}"
            )

        provider_class = self.providers[provider_name]
        self._provider_instance = self._create_provider_instance(provider_class, provider_name)
        logger.info(f"Created {provider_name} provider")

    def clear_provider_cache(self) -> None:
        """Clear the cached provider instance.

        Call this when settings change to force provider recreation
        on the next get_provider() call.
        """
        self._current_provider = None
        self._provider_instance = None
        logger.debug("Provider cache cleared")

    def get_available_providers(self) -> list:
        """Get list of available provider names.

        Returns:
            List of registered provider names
        """
        return list(self.providers.keys())

    def is_provider_available(self, provider_name: str) -> bool:
        """Check if a provider is registered.

        Args:
            provider_name: Name of the provider to check

        Returns:
            True if provider is registered, False otherwise
        """
        return provider_name in self.providers

    def test_connection(self) -> bool:
        """Test connection to the current provider.

        Override this if your provider has a specific connection test.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            provider = self.get_provider()
            if hasattr(provider, 'test_connection'):
                return provider.test_connection()
            return True
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False

    def test_connection_safe(self) -> OperationResult[bool]:
        """Test connection with OperationResult return type.

        Returns:
            OperationResult containing True on success, or error details on failure
        """
        try:
            result = self.test_connection()
            if result:
                return OperationResult.success(True)
            else:
                return OperationResult.failure(
                    "Connection test failed",
                    error_code="CONNECTION_FAILED"
                )
        except Exception as e:
            return OperationResult.failure(
                f"Connection test error: {str(e)}",
                error_code="CONNECTION_ERROR",
                exception=e
            )


def create_thread_safe_singleton(manager_class: Type[ProviderManager]) -> callable:
    """Factory function to create a thread-safe singleton getter.

    This function generates a get_*_manager() function that implements
    the double-checked locking pattern for thread-safe singleton access.

    Args:
        manager_class: The manager class to create singleton for

    Returns:
        A function that returns the singleton instance

    Example:
        get_tts_manager = create_thread_safe_singleton(TTSManager)

        # Usage:
        manager = get_tts_manager()  # Thread-safe singleton access
    """
    _instance = None
    _lock = threading.Lock()

    def get_manager() -> ProviderManager:
        nonlocal _instance
        if _instance is None:
            with _lock:
                if _instance is None:
                    _instance = manager_class()
        return _instance

    return get_manager
