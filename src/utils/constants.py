"""
Application Constants Module

This module provides centralized definitions for all constant values used
throughout the application, including provider names, status values, and
other magic strings that were previously scattered across the codebase.

Usage:
    from utils.constants import AIProvider, STTProvider, TTSProvider

    # Use enum values
    if provider == AIProvider.OPENAI:
        ...

    # Use string value when needed
    provider_name = AIProvider.OPENAI.value  # "openai"

    # Check if a string is a valid provider
    if AIProvider.is_valid("openai"):
        ...

    # Get provider from string
    provider = AIProvider.from_string("openai")
"""

from enum import Enum
from typing import Optional, List, Type, TypeVar

T = TypeVar('T', bound='BaseProvider')


class BaseProvider(Enum):
    """Base class for provider enums with common functionality."""

    @classmethod
    def values(cls) -> List[str]:
        """Get all provider values as strings.

        Returns:
            List of provider string values
        """
        return [member.value for member in cls]

    @classmethod
    def names(cls) -> List[str]:
        """Get all provider names (enum names).

        Returns:
            List of provider names
        """
        return [member.name for member in cls]

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string is a valid provider value.

        Args:
            value: String to check

        Returns:
            True if valid provider value
        """
        return value.lower() in [v.lower() for v in cls.values()]

    @classmethod
    def from_string(cls: Type[T], value: str) -> Optional[T]:
        """Get provider enum from string value.

        Args:
            value: Provider string value

        Returns:
            Provider enum member or None if not found
        """
        value_lower = value.lower()
        for member in cls:
            if member.value.lower() == value_lower:
                return member
        return None

    def __str__(self) -> str:
        """Return the string value of the provider."""
        return self.value


class AIProvider(BaseProvider):
    """AI/LLM provider identifiers.

    These are used for:
    - API key storage and retrieval
    - Model selection and routing
    - Rate limiting
    - Error handling and logging
    """
    OPENAI = "openai"
    ANTHROPIC = "anthropic"
    OLLAMA = "ollama"
    GEMINI = "gemini"

    @classmethod
    def get_display_name(cls, provider: 'AIProvider') -> str:
        """Get human-readable display name for provider.

        Args:
            provider: Provider enum member

        Returns:
            Display name string
        """
        display_names = {
            cls.OPENAI: "OpenAI",
            cls.ANTHROPIC: "Anthropic (Claude)",
            cls.OLLAMA: "Ollama (Local)",
            cls.GEMINI: "Google Gemini",
        }
        return display_names.get(provider, provider.value.title())


class STTProvider(BaseProvider):
    """Speech-to-Text provider identifiers.

    These are used for:
    - Transcription service selection
    - API key management
    - Audio processing routing
    """
    DEEPGRAM = "deepgram"
    GROQ = "groq"
    ELEVENLABS = "elevenlabs"
    WHISPER = "whisper"
    OPENAI = "openai"  # OpenAI Whisper API

    @classmethod
    def get_display_name(cls, provider: 'STTProvider') -> str:
        """Get human-readable display name for provider."""
        display_names = {
            cls.DEEPGRAM: "Deepgram",
            cls.GROQ: "Groq (Whisper)",
            cls.ELEVENLABS: "ElevenLabs",
            cls.WHISPER: "Whisper (Local)",
            cls.OPENAI: "OpenAI Whisper",
        }
        return display_names.get(provider, provider.value.title())


class TTSProvider(BaseProvider):
    """Text-to-Speech provider identifiers.

    These are used for:
    - Voice synthesis service selection
    - API key management
    - Audio output generation
    """
    ELEVENLABS = "elevenlabs"
    OPENAI = "openai"
    SYSTEM = "system"  # System TTS (pyttsx3, etc.)

    @classmethod
    def get_display_name(cls, provider: 'TTSProvider') -> str:
        """Get human-readable display name for provider."""
        display_names = {
            cls.ELEVENLABS: "ElevenLabs",
            cls.OPENAI: "OpenAI TTS",
            cls.SYSTEM: "System Voice",
        }
        return display_names.get(provider, provider.value.title())


class ProcessingStatus(BaseProvider):
    """Recording processing status values.

    These are used in the database to track processing state.
    """
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

    @classmethod
    def get_display_icon(cls, status: 'ProcessingStatus') -> str:
        """Get display icon for status."""
        icons = {
            cls.PENDING: "—",
            cls.PROCESSING: "🔄",
            cls.COMPLETED: "✓",
            cls.FAILED: "❌",
            cls.CANCELLED: "⊘",
        }
        return icons.get(status, "?")


class QueueStatus(BaseProvider):
    """Processing queue status values."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"


class TaskType(BaseProvider):
    """Processing task type identifiers."""
    TRANSCRIPTION = "transcription"
    SOAP_NOTE = "soap_note"
    REFERRAL = "referral"
    LETTER = "letter"
    FULL_PROCESS = "full_process"


# =============================================================================
# Legacy String Constants (for backward compatibility)
# =============================================================================
# These provide direct string access for code that expects strings

# AI Providers
PROVIDER_OPENAI = AIProvider.OPENAI.value
PROVIDER_ANTHROPIC = AIProvider.ANTHROPIC.value
PROVIDER_OLLAMA = AIProvider.OLLAMA.value
PROVIDER_GEMINI = AIProvider.GEMINI.value

# STT Providers
STT_DEEPGRAM = STTProvider.DEEPGRAM.value
STT_GROQ = STTProvider.GROQ.value
STT_ELEVENLABS = STTProvider.ELEVENLABS.value
STT_WHISPER = STTProvider.WHISPER.value

# TTS Providers
TTS_ELEVENLABS = TTSProvider.ELEVENLABS.value
TTS_OPENAI = TTSProvider.OPENAI.value
TTS_SYSTEM = TTSProvider.SYSTEM.value

# Processing Status
STATUS_PENDING = ProcessingStatus.PENDING.value
STATUS_PROCESSING = ProcessingStatus.PROCESSING.value
STATUS_COMPLETED = ProcessingStatus.COMPLETED.value
STATUS_FAILED = ProcessingStatus.FAILED.value

# All provider values (for validation)
ALL_AI_PROVIDERS = AIProvider.values()
ALL_STT_PROVIDERS = STTProvider.values()
ALL_TTS_PROVIDERS = TTSProvider.values()


# =============================================================================
# Provider Lists for UI Dropdowns
# =============================================================================

def get_ai_provider_choices() -> List[tuple]:
    """Get AI provider choices for UI dropdowns.

    Returns:
        List of (value, display_name) tuples
    """
    return [(p.value, AIProvider.get_display_name(p)) for p in AIProvider]


def get_stt_provider_choices() -> List[tuple]:
    """Get STT provider choices for UI dropdowns.

    Returns:
        List of (value, display_name) tuples
    """
    return [(p.value, STTProvider.get_display_name(p)) for p in STTProvider]


def get_tts_provider_choices() -> List[tuple]:
    """Get TTS provider choices for UI dropdowns.

    Returns:
        List of (value, display_name) tuples
    """
    return [(p.value, TTSProvider.get_display_name(p)) for p in TTSProvider]


# =============================================================================
# Error Message Templates
# =============================================================================
# Standardized error messages for consistent user feedback

class ErrorMessages:
    """Standardized error message templates.

    Usage:
        from utils.constants import ErrorMessages

        # Use directly
        raise ValueError(ErrorMessages.API_KEY_MISSING.format(provider="OpenAI"))

        # Or via helper method
        raise ValueError(ErrorMessages.format_api_error("OpenAI", "rate limit"))
    """

    # API Errors
    API_KEY_MISSING = "API key not configured for {provider}"
    API_KEY_INVALID = "Invalid API key for {provider}"
    API_RATE_LIMITED = "{provider} API rate limit exceeded. Please try again later."
    API_SERVICE_UNAVAILABLE = "{provider} service is temporarily unavailable"
    API_TIMEOUT = "{provider} request timed out after {timeout}s"
    API_AUTHENTICATION_FAILED = "Authentication failed for {provider}"

    # Database Errors
    DB_CONNECTION_FAILED = "Failed to connect to database: {error}"
    DB_QUERY_FAILED = "Database query failed: {error}"
    DB_RECORD_NOT_FOUND = "Record with ID {id} not found"
    DB_SAVE_FAILED = "Failed to save {item_type}: {error}"
    DB_DELETE_FAILED = "Failed to delete {item_type}: {error}"

    # File Errors
    FILE_NOT_FOUND = "File not found: {path}"
    FILE_READ_FAILED = "Failed to read file: {error}"
    FILE_WRITE_FAILED = "Failed to write file: {error}"
    FILE_DELETE_FAILED = "Failed to delete file: {error}"
    FILE_PERMISSION_DENIED = "Permission denied: {path}"

    # Audio Errors
    AUDIO_DEVICE_NOT_FOUND = "Audio device not found: {device}"
    AUDIO_DEVICE_DISCONNECTED = "Audio device disconnected during recording"
    AUDIO_RECORDING_FAILED = "Recording failed: {error}"
    AUDIO_TRANSCRIPTION_FAILED = "Transcription failed: {error}"

    # Processing Errors
    PROCESSING_FAILED = "Processing failed: {error}"
    PROCESSING_TIMEOUT = "Processing timed out after {timeout}s"
    PROCESSING_CANCELLED = "Processing was cancelled"

    # Validation Errors
    VALIDATION_REQUIRED = "{field} is required"
    VALIDATION_INVALID = "Invalid {field}: {reason}"
    VALIDATION_TOO_LONG = "{field} exceeds maximum length of {max_length}"
    VALIDATION_TOO_SHORT = "{field} must be at least {min_length} characters"

    # Generic Errors
    OPERATION_FAILED = "Operation failed: {error}"
    UNEXPECTED_ERROR = "An unexpected error occurred: {error}"
    NOT_CONFIGURED = "{component} is not configured"
    NOT_AVAILABLE = "{feature} is not available"

    @classmethod
    def format_api_error(cls, provider: str, error: str) -> str:
        """Format an API error message."""
        return f"{provider} API error: {error}"

    @classmethod
    def format_db_error(cls, operation: str, error: str) -> str:
        """Format a database error message."""
        return f"Database {operation} failed: {error}"

    @classmethod
    def format_file_error(cls, operation: str, path: str, error: str) -> str:
        """Format a file operation error message."""
        return f"Failed to {operation} file '{path}': {error}"


# =============================================================================
# Application Configuration Constants
# =============================================================================
# Default values for application configuration

class AppConfig:
    """Application configuration constants.

    These replace magic numbers scattered throughout the codebase.
    """

    # Timeouts (seconds)
    DEFAULT_API_TIMEOUT = 30
    DEFAULT_TRANSCRIPTION_TIMEOUT = 60
    DEFAULT_AI_GENERATION_TIMEOUT = 120
    DEFAULT_CONNECTION_TIMEOUT = 10

    # Retry Configuration
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0
    DEFAULT_RETRY_BACKOFF = 2.0

    # Cache Configuration
    CACHE_TTL_SECONDS = 3600  # 1 hour
    CACHE_MAX_SIZE = 100

    # Auto-save Configuration
    AUTOSAVE_INTERVAL_SECONDS = 300  # 5 minutes
    AUTOSAVE_MAX_BACKUPS = 3

    # UI Configuration
    UI_STATUS_MESSAGE_DURATION_MS = 5000
    UI_ANIMATION_INTERVAL_MS = 100
    UI_DEBOUNCE_DELAY_MS = 300

    # Audio Configuration
    AUDIO_SAMPLE_RATE = 16000
    AUDIO_CHANNELS = 1
    AUDIO_CHUNK_SIZE = 1024

    # Processing Queue
    QUEUE_MAX_CONCURRENT_TASKS = 3
    QUEUE_RETRY_DELAY_SECONDS = 5
    QUEUE_MAX_RETRY_ATTEMPTS = 3

    # Database
    DB_CONNECTION_POOL_SIZE = 5
    DB_CONNECTION_TIMEOUT = 30

    # Buffer sizes
    FILE_BUFFER_SIZE = 65536  # 64KB


# =============================================================================
# Feature Flags
# =============================================================================
# Boolean flags for enabling/disabling features

class FeatureFlags:
    """Feature flags for conditional functionality.

    These can be overridden via environment variables or settings.
    """

    ENABLE_DIARIZATION = True
    ENABLE_PERIODIC_ANALYSIS = True
    ENABLE_AUTOSAVE = True
    ENABLE_QUICK_CONTINUE_MODE = True
    ENABLE_BATCH_PROCESSING = True
    ENABLE_RAG_TAB = True
    ENABLE_CHAT_TAB = True


# =============================================================================
# Timing Constants
# =============================================================================
# Centralized timing values to avoid magic numbers throughout the codebase

class TimingConstants:
    """Timing constants for various application operations.

    All values in seconds unless otherwise noted.

    Usage:
        from utils.constants import TimingConstants

        interval = TimingConstants.PERIODIC_ANALYSIS_INTERVAL
    """

    # Analysis intervals
    PERIODIC_ANALYSIS_INTERVAL = 120  # 2 minutes - default interval for real-time analysis
    PERIODIC_ANALYSIS_MIN_ELAPSED = 10  # Minimum recording time before immediate analysis

    # Autosave intervals
    AUTOSAVE_INTERVAL = 300  # 5 minutes - default autosave interval

    # Cache TTLs
    SETTINGS_CACHE_TTL = 60  # Settings cache validity
    AGENT_CACHE_TTL = 300  # 5 minutes - agent response cache
    MODEL_CACHE_TTL = 3600  # 1 hour - model/provider info cache

    # API timeouts
    API_TIMEOUT_DEFAULT = 30  # Default API request timeout
    API_TIMEOUT_LONG = 60  # Long-running API operations
    STREAM_TIMEOUT = 60  # Streaming API timeout

    # STT provider failover
    STT_FAILOVER_SKIP_DURATION = 300  # 5 minutes - skip failed provider

    # UI update intervals (milliseconds)
    UI_UPDATE_INTERVAL_MS = 100  # UI refresh rate
    DEBOUNCE_DELAY_MS = 300  # Debounce for rapid events

    # Database
    DB_RETRY_INITIAL_DELAY = 0.1  # Initial delay for retry
    DB_RETRY_MAX_DELAY = 2.0  # Maximum delay between retries

    # Debug
    MAX_DEBUG_FILES = 20  # Maximum debug files to keep
