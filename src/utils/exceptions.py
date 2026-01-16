"""
Custom exception hierarchy for Medical Assistant application.
"""

class MedicalAssistantError(Exception):
    """Base exception class for Medical Assistant."""
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}


class AudioError(MedicalAssistantError):
    """Exceptions related to audio processing."""
    pass


class RecordingError(AudioError):
    """Raised when audio recording fails."""
    pass


class PlaybackError(AudioError):
    """Raised when audio playback fails."""
    pass


class TranscriptionError(MedicalAssistantError):
    """Exceptions related to speech-to-text transcription."""
    pass


class TranslationError(MedicalAssistantError):
    """Exceptions related to text translation."""
    pass


class APIError(MedicalAssistantError):
    """Base class for API-related errors."""
    def __init__(self, message: str, status_code: int = None, error_code: str = None, details: dict = None):
        super().__init__(message, error_code, details)
        self.status_code = status_code


class RateLimitError(APIError):
    """Raised when API rate limit is exceeded."""
    def __init__(self, message: str, retry_after: int = None, **kwargs):
        super().__init__(message, status_code=429, **kwargs)
        self.retry_after = retry_after


class AuthenticationError(APIError):
    """Raised when API authentication fails."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=401, **kwargs)


class ServiceUnavailableError(APIError):
    """Raised when external service is unavailable."""
    def __init__(self, message: str, **kwargs):
        super().__init__(message, status_code=503, **kwargs)


class APITimeoutError(APIError):
    """Raised when an API call times out.

    Note: Named APITimeoutError to avoid shadowing Python's built-in TimeoutError.

    Attributes:
        timeout_seconds: The timeout value that was exceeded
        service: The service that timed out (e.g., 'openai', 'anthropic')
    """
    def __init__(self, message: str, timeout_seconds: float = None, service: str = None, **kwargs):
        super().__init__(message, status_code=408, **kwargs)
        self.timeout_seconds = timeout_seconds
        self.service = service


# Alias for backward compatibility (deprecated - use APITimeoutError directly)
TimeoutError = APITimeoutError


class ConfigurationError(MedicalAssistantError):
    """Raised when configuration is invalid or missing."""
    pass


class DatabaseError(MedicalAssistantError):
    """Exceptions related to database operations."""
    pass


class ExportError(MedicalAssistantError):
    """Raised when export operations fail."""
    pass


class ValidationError(MedicalAssistantError):
    """Raised when input validation fails."""
    def __init__(self, message: str, field: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.field = field


class DeviceDisconnectedError(AudioError):
    """Raised when an audio device is disconnected during operation."""
    def __init__(self, message: str, device_name: str = None, **kwargs):
        super().__init__(message, **kwargs)
        self.device_name = device_name


# =============================================================================
# Processing Queue Exceptions
# =============================================================================

class ProcessingError(MedicalAssistantError):
    """Base exception for processing queue errors."""
    pass


class AudioSaveError(ProcessingError):
    """Raised when saving audio to file fails."""
    pass


class DocumentGenerationError(ProcessingError):
    """Raised when document generation (SOAP, referral, letter) fails."""
    pass


# =============================================================================
# Result Wrapper Classes
# =============================================================================

class AIResult:
    """
    Result wrapper for AI operations providing consistent error handling.

    This class wraps AI responses to distinguish between successful results
    and errors, replacing the pattern of returning error strings that could
    be mistaken for valid responses.

    Usage:
        result = AIResult.success("Generated text here")
        if result.is_success:
            use_text(result.text)
        else:
            handle_error(result.error, result.error_code)

    For backward compatibility, str(result) returns the text or error message.
    """

    def __init__(self, text: str = None, error: str = None, error_code: str = None,
                 exception: Exception = None, context: dict = None):
        self._text = text
        self._error = error
        self._error_code = error_code
        self._exception = exception
        self._context = context or {}

    @classmethod
    def success(cls, text: str, **context) -> 'AIResult':
        """Create a successful result with generated text."""
        return cls(text=text, context=context)

    @classmethod
    def failure(cls, error: str, error_code: str = None,
                exception: Exception = None, **context) -> 'AIResult':
        """Create a failed result with error information."""
        return cls(error=error, error_code=error_code,
                   exception=exception, context=context)

    @property
    def is_success(self) -> bool:
        """Check if the operation succeeded."""
        return self._error is None

    @property
    def is_error(self) -> bool:
        """Check if the operation failed."""
        return self._error is not None

    @property
    def text(self) -> str:
        """Get the generated text (empty string if failed)."""
        return self._text or ""

    @property
    def error(self) -> str:
        """Get the error message (None if successful)."""
        return self._error

    @property
    def error_code(self) -> str:
        """Get the error code (None if successful)."""
        return self._error_code

    @property
    def exception(self) -> Exception:
        """Get the original exception (None if successful or no exception)."""
        return self._exception

    @property
    def context(self) -> dict:
        """Get additional context information."""
        return self._context

    def __str__(self) -> str:
        """Return text for successful results, error message for failures.

        This provides backward compatibility with code expecting strings.
        """
        if self.is_success:
            return self._text or ""
        else:
            return f"[Error: {self._error_code or 'AI_ERROR'}] {self._error}"

    def __bool__(self) -> bool:
        """Allow using result in boolean context (True if successful)."""
        return self.is_success

    def unwrap(self) -> str:
        """Get the text or raise an exception if failed.

        Raises:
            APIError: If the operation failed
        """
        if self.is_success:
            return self._text
        if self._exception:
            raise self._exception
        raise APIError(self._error, error_code=self._error_code)

    def unwrap_or(self, default: str) -> str:
        """Get the text or return a default value if failed."""
        return self._text if self.is_success else default