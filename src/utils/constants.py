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
    PERPLEXITY = "perplexity"
    GROK = "grok"
    OLLAMA = "ollama"

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
            cls.PERPLEXITY: "Perplexity",
            cls.GROK: "Grok (X.AI)",
            cls.OLLAMA: "Ollama (Local)",
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
PROVIDER_PERPLEXITY = AIProvider.PERPLEXITY.value
PROVIDER_GROK = AIProvider.GROK.value
PROVIDER_OLLAMA = AIProvider.OLLAMA.value

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
