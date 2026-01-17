"""
AI Caller Interface Module

Provides a dependency injection interface for AI calls, eliminating circular imports
between the agent system and the AI module.

This module defines:
1. AICallerProtocol - Abstract interface for AI calls
2. DefaultAICaller - Standard implementation using the ai module
3. get_default_ai_caller() - Factory function for creating callers

Usage:
    # In agent initialization (dependency injection)
    caller = get_default_ai_caller()
    agent = SomeAgent(config, ai_caller=caller)

    # In agent's _call_ai method
    response = self.ai_caller.call(model, system_message, prompt, temperature)
"""

from abc import ABC, abstractmethod
from typing import Optional, Callable, Dict, Any, Protocol, runtime_checkable

from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA, PROVIDER_GEMINI
)
from utils.structured_logging import get_logger

logger = get_logger(__name__)


@runtime_checkable
class AICallerProtocol(Protocol):
    """Protocol defining the interface for AI callers.

    This protocol allows for dependency injection of AI calling functionality,
    making agents testable and avoiding circular imports.
    """

    def call(
        self,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7,
        provider: Optional[str] = None
    ) -> str:
        """Make an AI call and return the response.

        Args:
            model: The model identifier to use
            system_message: System message/context for the AI
            prompt: The user prompt
            temperature: Sampling temperature (0.0-1.0)
            provider: Optional provider override (openai, anthropic, etc.)

        Returns:
            The AI response text

        Raises:
            Exception: If the AI call fails
        """
        ...

    def call_with_provider(
        self,
        provider: str,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7
    ) -> str:
        """Make an AI call to a specific provider.

        Args:
            provider: The provider to use (openai, anthropic, ollama, gemini)
            model: The model identifier to use
            system_message: System message/context for the AI
            prompt: The user prompt
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            The AI response text

        Raises:
            Exception: If the AI call fails
        """
        ...


class BaseAICaller(ABC):
    """Abstract base class for AI callers."""

    @abstractmethod
    def call(
        self,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7,
        provider: Optional[str] = None
    ) -> str:
        """Make an AI call and return the response."""
        pass

    @abstractmethod
    def call_with_provider(
        self,
        provider: str,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7
    ) -> str:
        """Make an AI call to a specific provider."""
        pass


class DefaultAICaller(BaseAICaller):
    """Default AI caller implementation using the ai module.

    This class lazily imports from the ai module to avoid circular imports
    at module load time. Imports only happen when methods are called.
    """

    def __init__(self):
        """Initialize the AI caller."""
        self._call_ai = None
        self._call_openai = None
        self._call_anthropic = None
        self._call_ollama = None
        self._call_gemini = None
        self._initialized = False

    def _ensure_initialized(self) -> None:
        """Lazily initialize AI function references.

        This defers the import of the ai module until actually needed,
        avoiding circular import issues at module load time.
        """
        if self._initialized:
            return

        # Import here to avoid circular imports at module load time
        from ai.ai import (
            call_ai,
            call_openai,
            call_anthropic,
            call_ollama,
            call_gemini
        )

        self._call_ai = call_ai
        self._call_openai = call_openai
        self._call_anthropic = call_anthropic
        self._call_ollama = call_ollama
        self._call_gemini = call_gemini
        self._initialized = True

    def call(
        self,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7,
        provider: Optional[str] = None
    ) -> str:
        """Make an AI call using the default routing.

        Args:
            model: The model identifier to use
            system_message: System message/context for the AI
            prompt: The user prompt
            temperature: Sampling temperature (0.0-1.0)
            provider: Optional provider override

        Returns:
            The AI response text
        """
        self._ensure_initialized()

        if provider:
            return self.call_with_provider(provider, model, system_message, prompt, temperature)

        return self._call_ai(model, system_message, prompt, temperature)

    def call_with_provider(
        self,
        provider: str,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7
    ) -> str:
        """Make an AI call to a specific provider.

        Args:
            provider: The provider to use
            model: The model identifier to use
            system_message: System message/context for the AI
            prompt: The user prompt
            temperature: Sampling temperature (0.0-1.0)

        Returns:
            The AI response text
        """
        self._ensure_initialized()

        provider_lower = provider.lower()

        if provider_lower == PROVIDER_OPENAI:
            return self._call_openai(model, system_message, prompt, temperature)
        elif provider_lower == PROVIDER_ANTHROPIC:
            return self._call_anthropic(model, system_message, prompt, temperature)
        elif provider_lower == PROVIDER_OLLAMA:
            return self._call_ollama(system_message, prompt, temperature)
        elif provider_lower == PROVIDER_GEMINI:
            return self._call_gemini(model, system_message, prompt, temperature)
        else:
            # Fallback to generic call_ai
            logger.warning(f"Unknown provider '{provider}', falling back to default routing")
            return self._call_ai(model, system_message, prompt, temperature)


class MockAICaller(BaseAICaller):
    """Mock AI caller for testing.

    This can be used in unit tests to avoid making actual AI calls.
    """

    def __init__(self, default_response: str = "Mock response"):
        """Initialize the mock caller.

        Args:
            default_response: Default response to return
        """
        self.default_response = default_response
        self.call_history: list = []

    def call(
        self,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7,
        provider: Optional[str] = None
    ) -> str:
        """Record the call and return a mock response."""
        self.call_history.append({
            "model": model,
            "system_message": system_message,
            "prompt": prompt,
            "temperature": temperature,
            "provider": provider
        })
        return self.default_response

    def call_with_provider(
        self,
        provider: str,
        model: str,
        system_message: str,
        prompt: str,
        temperature: float = 0.7
    ) -> str:
        """Record the call and return a mock response."""
        return self.call(model, system_message, prompt, temperature, provider)

    def reset(self) -> None:
        """Reset call history."""
        self.call_history.clear()


# Singleton instance for the default AI caller
_default_ai_caller: Optional[DefaultAICaller] = None


def get_default_ai_caller() -> DefaultAICaller:
    """Get the default AI caller singleton.

    Returns:
        The default AI caller instance
    """
    global _default_ai_caller
    if _default_ai_caller is None:
        _default_ai_caller = DefaultAICaller()
    return _default_ai_caller


def create_mock_ai_caller(default_response: str = "Mock response") -> MockAICaller:
    """Create a mock AI caller for testing.

    Args:
        default_response: Default response to return

    Returns:
        A new MockAICaller instance
    """
    return MockAICaller(default_response)
