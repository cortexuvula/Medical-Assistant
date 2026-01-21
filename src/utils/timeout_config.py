"""
Timeout Configuration Module

Provides centralized, configurable timeout settings for all external API calls.
This ensures consistent timeout handling across the application and prevents
hung operations from blocking the application indefinitely.

Usage:
    from utils.timeout_config import get_timeout, TimeoutConfig

    # Get timeout for a specific service
    timeout = get_timeout("openai")

    # Get timeout with custom default
    timeout = get_timeout("custom_service", default=45.0)

    # Update timeouts at runtime
    TimeoutConfig.update_timeout("openai", 120.0)
"""

from typing import Dict, Optional
from settings.settings import SETTINGS
from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA, PROVIDER_GEMINI
)
from utils.structured_logging import get_logger

logger = get_logger(__name__)


# Default timeout values in seconds
DEFAULT_TIMEOUTS: Dict[str, float] = {
    # AI Provider timeouts (using constants)
    PROVIDER_OPENAI: 60.0,       # OpenAI API calls
    PROVIDER_ANTHROPIC: 90.0,    # Anthropic/Claude API calls (can be slower)
    PROVIDER_OLLAMA: 180.0,      # Ollama (local, can be very slow depending on model)
    PROVIDER_GEMINI: 90.0,       # Google Gemini API calls

    # STT Provider timeouts (for transcription)
    "deepgram": 120.0,        # Deepgram STT (long audio files)
    "groq": 60.0,             # Groq Whisper STT (fast)
    "elevenlabs": 90.0,       # ElevenLabs STT

    # Neo4j/Knowledge Graph timeouts
    "neo4j": 30.0,            # Neo4j operations (reduced from 300s)
    "neo4j_connect": 5.0,     # Neo4j connection timeout
    "graphiti": 30.0,         # Graphiti knowledge graph operations

    # Embedding API timeouts
    "embedding": 60.0,        # Embedding generation
    "embedding_batch": 120.0, # Large batch embedding

    # Other service timeouts
    "rag": 30.0,              # RAG/N8N webhook calls
    "stt": 120.0,             # Generic speech-to-text transcription
    "tts": 30.0,              # Text-to-speech synthesis
    "health_check": 5.0,      # Service health checks

    # Generic defaults
    "default": 60.0,          # Default for unspecified services
    "short": 10.0,            # Quick operations
    "long": 300.0,            # Long-running operations
}

# Connection timeout (time to establish connection) vs read timeout (time to receive response)
DEFAULT_CONNECT_TIMEOUT: float = 10.0


class TimeoutConfig:
    """Centralized timeout configuration manager.

    This class provides:
    - Configurable timeout values for different services
    - Runtime updates to timeout settings
    - Integration with application settings
    - Tuple timeouts for connect/read separation
    """

    _instance: Optional['TimeoutConfig'] = None
    _timeouts: Dict[str, float]
    _connect_timeout: float

    def __new__(cls) -> 'TimeoutConfig':
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super(TimeoutConfig, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """Initialize the timeout configuration."""
        if self._initialized:
            return

        self._timeouts = DEFAULT_TIMEOUTS.copy()
        self._connect_timeout = DEFAULT_CONNECT_TIMEOUT
        self._load_from_settings()
        self._initialized = True

    def _load_from_settings(self) -> None:
        """Load timeout settings from application settings if available."""
        try:
            timeout_settings = SETTINGS.get("timeouts", {})

            # Load service-specific timeouts
            for service, timeout in timeout_settings.items():
                if service == "connect":
                    self._connect_timeout = float(timeout)
                elif isinstance(timeout, (int, float)) and timeout > 0:
                    self._timeouts[service] = float(timeout)
                    logger.debug(f"Loaded timeout for {service}: {timeout}s")

        except Exception as e:
            logger.warning(f"Error loading timeout settings: {e}. Using defaults.")

    def get_timeout(self, service: str, default: Optional[float] = None) -> float:
        """Get the timeout value for a specific service.

        Args:
            service: Service name (e.g., 'openai', 'anthropic', 'rag')
            default: Default value if service not found

        Returns:
            Timeout value in seconds
        """
        if default is not None:
            return self._timeouts.get(service, default)
        return self._timeouts.get(service, self._timeouts["default"])

    def get_timeout_tuple(self, service: str) -> tuple:
        """Get a (connect_timeout, read_timeout) tuple for requests library.

        Args:
            service: Service name

        Returns:
            Tuple of (connect_timeout, read_timeout) in seconds
        """
        read_timeout = self.get_timeout(service)
        return (self._connect_timeout, read_timeout)

    def update_timeout(self, service: str, timeout: float) -> None:
        """Update the timeout for a specific service at runtime.

        Args:
            service: Service name
            timeout: New timeout value in seconds
        """
        if timeout <= 0:
            logger.warning(f"Invalid timeout value {timeout} for {service}. Must be positive.")
            return

        self._timeouts[service] = timeout
        logger.info(f"Updated timeout for {service} to {timeout}s")

    def update_connect_timeout(self, timeout: float) -> None:
        """Update the connection timeout.

        Args:
            timeout: New connect timeout value in seconds
        """
        if timeout <= 0:
            logger.warning(f"Invalid connect timeout value {timeout}. Must be positive.")
            return

        self._connect_timeout = timeout
        logger.info(f"Updated connect timeout to {timeout}s")

    @property
    def connect_timeout(self) -> float:
        """Get the connection timeout value."""
        return self._connect_timeout

    def get_all_timeouts(self) -> Dict[str, float]:
        """Get all configured timeout values.

        Returns:
            Dictionary of service names to timeout values
        """
        return self._timeouts.copy()

    def reset_to_defaults(self) -> None:
        """Reset all timeouts to default values."""
        self._timeouts = DEFAULT_TIMEOUTS.copy()
        self._connect_timeout = DEFAULT_CONNECT_TIMEOUT
        logger.info("Reset all timeouts to defaults")


# Module-level singleton instance
_timeout_config: Optional[TimeoutConfig] = None


def get_timeout_config() -> TimeoutConfig:
    """Get the singleton timeout configuration instance.

    Returns:
        TimeoutConfig instance
    """
    global _timeout_config
    if _timeout_config is None:
        _timeout_config = TimeoutConfig()
    return _timeout_config


def get_timeout(service: str, default: Optional[float] = None) -> float:
    """Convenience function to get timeout for a service.

    Args:
        service: Service name (e.g., 'openai', 'anthropic', 'rag')
        default: Default value if service not found

    Returns:
        Timeout value in seconds
    """
    return get_timeout_config().get_timeout(service, default)


def get_timeout_tuple(service: str) -> tuple:
    """Convenience function to get timeout tuple for requests.

    Args:
        service: Service name

    Returns:
        Tuple of (connect_timeout, read_timeout) in seconds
    """
    return get_timeout_config().get_timeout_tuple(service)
