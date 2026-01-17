"""
Base class for STT (Speech-to-Text) providers.

This module defines the interface that all STT providers must implement,
ensuring consistent behavior across different transcription services.

Error Handling:
    - TranscriptionResult.success indicates operation success/failure
    - TranscriptionResult.error contains error message on failure
    - Providers should catch provider-specific exceptions and return error results
    - test_connection() returns bool, never raises exceptions
    - TranscriptionError raised only for unrecoverable failures

Logging:
    - Each provider uses get_logger(self.__class__.__name__)
    - Logs include audio duration, model used, and timing metrics
    - API keys and audio data are not logged

Usage:
    provider = DeepgramProvider(api_key="...")
    result = provider.transcribe_with_result(audio_segment)
    if result.success:
        text = result.text
    else:
        handle_error(result.error)
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from pydub import AudioSegment

from utils.structured_logging import get_logger


@dataclass
class TranscriptionResult:
    """Structured result from a transcription operation.

    This class provides a consistent format for transcription results
    across all providers, including metadata and error information.
    """

    text: str
    """The transcribed text."""

    success: bool = True
    """Whether the transcription was successful."""

    error: Optional[str] = None
    """Error message if transcription failed."""

    confidence: Optional[float] = None
    """Confidence score (0.0-1.0) if available from provider."""

    duration_seconds: Optional[float] = None
    """Duration of the audio that was transcribed."""

    words: List[Dict[str, Any]] = field(default_factory=list)
    """Word-level transcription data if available (for diarization)."""

    metadata: Dict[str, Any] = field(default_factory=dict)
    """Additional provider-specific metadata."""

    @classmethod
    def success_result(cls, text: str, **kwargs) -> 'TranscriptionResult':
        """Create a successful transcription result."""
        return cls(text=text, success=True, **kwargs)

    @classmethod
    def failure_result(cls, error: str, **kwargs) -> 'TranscriptionResult':
        """Create a failed transcription result."""
        return cls(text="", success=False, error=error, **kwargs)


class BaseSTTProvider(ABC):
    """Base class that all STT providers must implement.

    This abstract base class defines the interface for speech-to-text providers.
    Subclasses must implement the abstract methods to provide transcription
    functionality.

    Attributes:
        api_key: API key for the STT service (may be empty for local providers)
        language: Language code for speech recognition (e.g., "en-US")
        logger: Logger instance for this provider

    Example:
        class MyProvider(BaseSTTProvider):
            @property
            def provider_name(self) -> str:
                return "my_provider"

            def transcribe(self, segment: AudioSegment) -> str:
                # Implementation here
                pass

            def test_connection(self) -> bool:
                # Validate connection
                pass
    """

    def __init__(self, api_key: str = "", language: str = "en-US"):
        """Initialize the provider with API key and language settings.

        Args:
            api_key: API key for the STT service (empty for local providers)
            language: Language code for speech recognition
        """
        self.api_key = api_key
        self.language = language
        self.logger = get_logger(self.__class__.__name__)

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Return the unique identifier for this provider.

        Returns:
            A lowercase string identifier (e.g., "deepgram", "groq", "whisper")
        """
        pass

    @property
    def supports_diarization(self) -> bool:
        """Whether this provider supports speaker diarization.

        Override in subclasses that support diarization.

        Returns:
            True if the provider can identify different speakers
        """
        return False

    @property
    def requires_api_key(self) -> bool:
        """Whether this provider requires an API key.

        Override in subclasses that don't require an API key (e.g., local Whisper).

        Returns:
            True if an API key is required for this provider
        """
        return True

    @property
    def is_configured(self) -> bool:
        """Check if the provider is properly configured.

        Returns:
            True if the provider has all required configuration
        """
        if self.requires_api_key:
            return bool(self.api_key)
        return True

    @abstractmethod
    def transcribe(self, segment: AudioSegment) -> str:
        """Transcribe the provided audio segment.

        Args:
            segment: Audio segment to transcribe

        Returns:
            Transcription text or empty string if failed
        """
        pass

    def transcribe_with_result(self, segment: AudioSegment) -> TranscriptionResult:
        """Transcribe audio and return a structured result.

        This method wraps the basic transcribe() method to provide
        structured error handling and metadata. Override in subclasses
        for provider-specific result handling.

        Args:
            segment: Audio segment to transcribe

        Returns:
            TranscriptionResult with text or error information
        """
        try:
            text = self.transcribe(segment)
            if text:
                return TranscriptionResult.success_result(
                    text=text,
                    duration_seconds=len(segment) / 1000.0
                )
            else:
                return TranscriptionResult.failure_result(
                    error="Transcription returned empty result"
                )
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            return TranscriptionResult.failure_result(error=str(e))

    def test_connection(self) -> bool:
        """Test if the provider is properly configured and accessible.

        This method validates that:
        1. Required API key is present (if needed)
        2. The service is reachable
        3. Authentication is valid

        Override in subclasses to add provider-specific validation.

        Returns:
            True if connection test passes, False otherwise
        """
        if self.requires_api_key and not self.api_key:
            self.logger.warning(f"{self.provider_name}: API key not configured")
            return False
        return True

    def _check_api_key(self) -> bool:
        """Check if the API key is available.

        Returns:
            True if API key is available, False otherwise
        """
        if not self.api_key:
            self.logger.warning(f"{self.__class__.__name__} API key not found")
            return False
        return True

    def __repr__(self) -> str:
        """Return string representation of the provider."""
        configured = "configured" if self.is_configured else "not configured"
        return f"<{self.__class__.__name__}({self.provider_name}, {configured})>"
