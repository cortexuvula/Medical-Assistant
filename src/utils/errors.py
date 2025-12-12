"""
Custom exception classes for Medical Assistant.

This module provides a standardized exception hierarchy that enables:
- Consistent error handling across the application
- Clear distinction between retryable and non-retryable errors
- Actionable error messages for users
- Structured error information for logging

Usage:
    try:
        result = transcribe_audio(audio_data)
    except TranscriptionError as e:
        if e.retryable:
            # Schedule retry
            pass
        else:
            # Show error to user
            display_error(e.user_message)
"""

from typing import Optional, List, Dict, Any


class MedicalAssistantError(Exception):
    """Base exception for all Medical Assistant errors.

    Attributes:
        message: Technical error message for logging
        user_message: User-friendly message for display
        retryable: Whether the operation can be retried
        error_code: Unique error identifier for tracking
    """

    def __init__(
        self,
        message: str,
        user_message: Optional[str] = None,
        retryable: bool = False,
        error_code: Optional[str] = None
    ):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or message
        self.retryable = retryable
        self.error_code = error_code or self.__class__.__name__

    def __str__(self) -> str:
        return self.message

    def to_dict(self) -> Dict[str, Any]:
        """Convert exception to dictionary for logging/serialization."""
        return {
            'error_type': self.__class__.__name__,
            'error_code': self.error_code,
            'message': self.message,
            'user_message': self.user_message,
            'retryable': self.retryable
        }


# ============================================================================
# Audio Errors
# ============================================================================

class AudioError(MedicalAssistantError):
    """Base class for audio-related errors."""
    pass


class AudioDeviceError(AudioError):
    """Error accessing or using an audio device."""

    def __init__(
        self,
        message: str,
        device_name: Optional[str] = None,
        available_devices: Optional[List[str]] = None
    ):
        super().__init__(
            message=message,
            user_message=f"Audio device error: {message}. Please check your microphone settings.",
            retryable=True,
            error_code="AUDIO_DEVICE_ERROR"
        )
        self.device_name = device_name
        self.available_devices = available_devices


class AudioFormatError(AudioError):
    """Unsupported or invalid audio format."""

    SUPPORTED_FORMATS = ['mp3', 'wav', 'ogg', 'flac', 'm4a']

    def __init__(self, message: str, format_received: Optional[str] = None):
        super().__init__(
            message=message,
            user_message=f"Unsupported audio format. Supported formats: {', '.join(self.SUPPORTED_FORMATS)}",
            retryable=False,
            error_code="AUDIO_FORMAT_ERROR"
        )
        self.format_received = format_received
        self.supported_formats = self.SUPPORTED_FORMATS


class AudioProcessingError(AudioError):
    """Error during audio processing (conversion, normalization, etc.)."""

    def __init__(self, message: str, stage: Optional[str] = None):
        super().__init__(
            message=message,
            user_message="Error processing audio. Please try again.",
            retryable=True,
            error_code="AUDIO_PROCESSING_ERROR"
        )
        self.stage = stage


# ============================================================================
# Transcription Errors
# ============================================================================

class TranscriptionError(AudioError):
    """Error during speech-to-text transcription."""

    def __init__(
        self,
        message: str,
        provider: Optional[str] = None,
        retryable: bool = True
    ):
        super().__init__(
            message=message,
            user_message="Transcription failed. Please try again.",
            retryable=retryable,
            error_code="TRANSCRIPTION_ERROR"
        )
        self.provider = provider


class TranscriptionAPIError(TranscriptionError):
    """API error from transcription service."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None
    ):
        super().__init__(
            message=message,
            provider=provider,
            retryable=status_code is None or status_code >= 500
        )
        self.status_code = status_code
        self.error_code = "TRANSCRIPTION_API_ERROR"


class TranscriptionEmptyResultError(TranscriptionError):
    """Transcription returned no text (silent audio or unrecognized speech)."""

    def __init__(self, provider: Optional[str] = None):
        super().__init__(
            message="Transcription returned empty result",
            provider=provider,
            retryable=False
        )
        self.user_message = "Could not detect speech in the audio. Please speak clearly and try again."
        self.error_code = "TRANSCRIPTION_EMPTY"


# ============================================================================
# AI/Processing Errors
# ============================================================================

class AIError(MedicalAssistantError):
    """Base class for AI-related errors."""
    pass


class AIProviderError(AIError):
    """Error from AI provider (OpenAI, Anthropic, etc.)."""

    def __init__(
        self,
        message: str,
        provider: str,
        status_code: Optional[int] = None,
        rate_limited: bool = False
    ):
        retryable = rate_limited or (status_code is not None and status_code >= 500)
        super().__init__(
            message=message,
            user_message="AI processing failed. Please try again.",
            retryable=retryable,
            error_code="AI_PROVIDER_ERROR"
        )
        self.provider = provider
        self.status_code = status_code
        self.rate_limited = rate_limited

        if rate_limited:
            self.user_message = "AI service is busy. Please wait a moment and try again."


class AIConfigurationError(AIError):
    """Invalid AI configuration (missing API key, invalid model, etc.)."""

    def __init__(self, message: str, provider: Optional[str] = None):
        super().__init__(
            message=message,
            user_message="AI service not configured. Please check your API key settings.",
            retryable=False,
            error_code="AI_CONFIG_ERROR"
        )
        self.provider = provider


# ============================================================================
# Database Errors
# ============================================================================

class DatabaseError(MedicalAssistantError):
    """Base class for database errors."""
    pass


class DatabaseConnectionError(DatabaseError):
    """Error connecting to database."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            user_message="Database connection error. Please restart the application.",
            retryable=True,
            error_code="DB_CONNECTION_ERROR"
        )


class DatabaseQueryError(DatabaseError):
    """Error executing database query."""

    def __init__(self, message: str, query: Optional[str] = None):
        super().__init__(
            message=message,
            user_message="Database error. Your data may not have been saved.",
            retryable=False,
            error_code="DB_QUERY_ERROR"
        )
        self.query = query


class DatabaseMigrationError(DatabaseError):
    """Error during database migration."""

    def __init__(self, message: str, migration_version: Optional[int] = None):
        super().__init__(
            message=message,
            user_message="Database upgrade failed. Please contact support.",
            retryable=False,
            error_code="DB_MIGRATION_ERROR"
        )
        self.migration_version = migration_version


# ============================================================================
# Configuration Errors
# ============================================================================

class ConfigurationError(MedicalAssistantError):
    """Base class for configuration errors."""

    def __init__(self, message: str, setting_name: Optional[str] = None):
        super().__init__(
            message=message,
            user_message="Configuration error. Please check your settings.",
            retryable=False,
            error_code="CONFIG_ERROR"
        )
        self.setting_name = setting_name


class APIKeyError(ConfigurationError):
    """Missing or invalid API key."""

    def __init__(self, message: str, provider: str):
        super().__init__(
            message=message,
            setting_name=f"{provider}_api_key"
        )
        self.provider = provider
        self.user_message = f"API key for {provider} is missing or invalid. Please configure it in Settings."
        self.error_code = "API_KEY_ERROR"


# ============================================================================
# Processing Queue Errors
# ============================================================================

class ProcessingError(MedicalAssistantError):
    """Base class for processing queue errors."""
    pass


class ProcessingQueueFullError(ProcessingError):
    """Processing queue is at capacity."""

    def __init__(self, queue_size: int):
        super().__init__(
            message=f"Processing queue is full ({queue_size} items)",
            user_message="Processing queue is busy. Please wait for current tasks to complete.",
            retryable=True,
            error_code="QUEUE_FULL"
        )
        self.queue_size = queue_size


class ProcessingTaskError(ProcessingError):
    """Error processing a specific task."""

    def __init__(
        self,
        message: str,
        task_id: str,
        recording_id: Optional[int] = None
    ):
        super().__init__(
            message=message,
            user_message="Task processing failed.",
            retryable=True,
            error_code="TASK_ERROR"
        )
        self.task_id = task_id
        self.recording_id = recording_id


# ============================================================================
# UI Errors
# ============================================================================

class UIError(MedicalAssistantError):
    """Base class for UI-related errors."""

    def __init__(self, message: str):
        super().__init__(
            message=message,
            user_message="An interface error occurred.",
            retryable=False,
            error_code="UI_ERROR"
        )


# ============================================================================
# Helper Functions
# ============================================================================

def is_retryable(exception: Exception) -> bool:
    """Check if an exception indicates a retryable condition.

    Args:
        exception: The exception to check

    Returns:
        True if the operation can be retried
    """
    if isinstance(exception, MedicalAssistantError):
        return exception.retryable
    # Default behavior for unknown exceptions
    return False


def get_user_message(exception: Exception) -> str:
    """Get a user-friendly message from an exception.

    Args:
        exception: The exception to get message from

    Returns:
        User-friendly error message
    """
    if isinstance(exception, MedicalAssistantError):
        return exception.user_message
    return "An unexpected error occurred. Please try again."


def wrap_exception(
    exception: Exception,
    error_class: type = MedicalAssistantError,
    **kwargs
) -> MedicalAssistantError:
    """Wrap a generic exception in a MedicalAssistantError.

    Args:
        exception: The exception to wrap
        error_class: The MedicalAssistantError subclass to use
        **kwargs: Additional arguments for the error class

    Returns:
        A MedicalAssistantError instance
    """
    if isinstance(exception, MedicalAssistantError):
        return exception
    return error_class(str(exception), **kwargs)
