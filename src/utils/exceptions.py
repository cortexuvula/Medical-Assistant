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