"""
Typed Configuration Dataclasses

This module provides strongly-typed configuration objects to replace
Dict[str, Any] patterns throughout the codebase. Using dataclasses
provides IDE autocomplete, type checking, and validation.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, List, Dict, Any
from enum import Enum


class Priority(str, Enum):
    """Processing priority levels."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"


class RetryStrategy(str, Enum):
    """Retry strategy options for agent execution."""
    EXPONENTIAL = "exponential"
    LINEAR = "linear"
    FIXED = "fixed"
    NONE = "none"


class DocumentType(str, Enum):
    """Types of documents that can be generated."""
    SOAP = "soap"
    REFERRAL = "referral"
    LETTER = "letter"


@dataclass
class BatchProcessingOptions:
    """Options for batch processing of multiple recordings.

    Attributes:
        generate_soap: Whether to generate SOAP notes
        generate_referral: Whether to generate referral letters
        generate_letter: Whether to generate generic letters
        skip_existing: Skip recordings that already have generated content
        continue_on_error: Continue processing if one recording fails
        priority: Processing priority level
        max_concurrent: Maximum concurrent processing tasks
    """
    generate_soap: bool = True
    generate_referral: bool = False
    generate_letter: bool = False
    skip_existing: bool = True
    continue_on_error: bool = True
    priority: Priority = Priority.NORMAL
    max_concurrent: int = 3

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "generate_soap": self.generate_soap,
            "generate_referral": self.generate_referral,
            "generate_letter": self.generate_letter,
            "skip_existing": self.skip_existing,
            "continue_on_error": self.continue_on_error,
            "priority": self.priority.value,
            "max_concurrent": self.max_concurrent,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BatchProcessingOptions":
        """Create from dictionary."""
        priority = data.get("priority", "normal")
        if isinstance(priority, str):
            priority = Priority(priority)
        return cls(
            generate_soap=data.get("generate_soap", True),
            generate_referral=data.get("generate_referral", False),
            generate_letter=data.get("generate_letter", False),
            skip_existing=data.get("skip_existing", True),
            continue_on_error=data.get("continue_on_error", True),
            priority=priority,
            max_concurrent=data.get("max_concurrent", 3),
        )


@dataclass
class AgentExecutionOptions:
    """Options for AI agent task execution.

    Attributes:
        timeout: Maximum execution time in seconds
        max_retries: Maximum number of retry attempts
        retry_strategy: Strategy for calculating retry delays
        retry_delay: Base delay between retries in seconds
        temperature: AI model temperature (0.0-2.0)
        max_tokens: Maximum tokens in response
    """
    timeout: int = 60
    max_retries: int = 3
    retry_strategy: RetryStrategy = RetryStrategy.EXPONENTIAL
    retry_delay: float = 1.0
    temperature: float = 0.7
    max_tokens: int = 4000

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "timeout": self.timeout,
            "max_retries": self.max_retries,
            "retry_strategy": self.retry_strategy.value,
            "retry_delay": self.retry_delay,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AgentExecutionOptions":
        """Create from dictionary."""
        strategy = data.get("retry_strategy", "exponential")
        if isinstance(strategy, str):
            strategy = RetryStrategy(strategy)
        return cls(
            timeout=data.get("timeout", 60),
            max_retries=data.get("max_retries", 3),
            retry_strategy=strategy,
            retry_delay=data.get("retry_delay", 1.0),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("max_tokens", 4000),
        )


@dataclass
class TranscriptionOptions:
    """Options for speech-to-text transcription.

    Attributes:
        language: Language code (e.g., 'en-US', 'es-ES')
        diarize: Enable speaker diarization
        num_speakers: Expected number of speakers (for diarization)
        model: STT model to use (provider-specific)
        smart_formatting: Enable smart formatting (punctuation, numbers)
        profanity_filter: Filter profane words
    """
    language: str = "en-US"
    diarize: bool = False
    num_speakers: Optional[int] = None
    model: Optional[str] = None
    smart_formatting: bool = True
    profanity_filter: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "language": self.language,
            "diarize": self.diarize,
            "num_speakers": self.num_speakers,
            "model": self.model,
            "smart_formatting": self.smart_formatting,
            "profanity_filter": self.profanity_filter,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranscriptionOptions":
        """Create from dictionary."""
        return cls(
            language=data.get("language", "en-US"),
            diarize=data.get("diarize", False),
            num_speakers=data.get("num_speakers"),
            model=data.get("model"),
            smart_formatting=data.get("smart_formatting", True),
            profanity_filter=data.get("profanity_filter", False),
        )


@dataclass
class DocumentGenerationOptions:
    """Options for generating medical documents.

    Attributes:
        include_context: Include patient context in generation
        max_tokens: Maximum tokens for AI response
        temperature: AI model temperature
        provider: AI provider to use
        model: AI model to use
        system_prompt: Optional custom system prompt
    """
    include_context: bool = True
    max_tokens: int = 4000
    temperature: float = 0.7
    provider: Optional[str] = None
    model: Optional[str] = None
    system_prompt: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "include_context": self.include_context,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "provider": self.provider,
            "model": self.model,
            "system_prompt": self.system_prompt,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DocumentGenerationOptions":
        """Create from dictionary."""
        return cls(
            include_context=data.get("include_context", True),
            max_tokens=data.get("max_tokens", 4000),
            temperature=data.get("temperature", 0.7),
            provider=data.get("provider"),
            model=data.get("model"),
            system_prompt=data.get("system_prompt"),
        )


@dataclass
class TTSOptions:
    """Options for text-to-speech synthesis.

    Attributes:
        provider: TTS provider (pyttsx3, elevenlabs, google)
        voice: Voice ID or name
        language: Language code
        rate: Speech rate multiplier
        volume: Volume level (0.0-1.0)
        model: Provider-specific model (e.g., elevenlabs model)
    """
    provider: str = "pyttsx3"
    voice: Optional[str] = None
    language: str = "en"
    rate: float = 1.0
    volume: float = 1.0
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "provider": self.provider,
            "voice": self.voice,
            "language": self.language,
            "rate": self.rate,
            "volume": self.volume,
            "model": self.model,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TTSOptions":
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", "pyttsx3"),
            voice=data.get("voice"),
            language=data.get("language", "en"),
            rate=data.get("rate", 1.0),
            volume=data.get("volume", 1.0),
            model=data.get("model"),
        )


@dataclass
class TranslationOptions:
    """Options for translation operations.

    Attributes:
        provider: Translation provider (deep_translator)
        sub_provider: Sub-provider (google, deepl, microsoft)
        source_language: Source language code (auto-detect if None)
        target_language: Target language code
        auto_detect: Enable automatic language detection
    """
    provider: str = "deep_translator"
    sub_provider: str = "google"
    source_language: Optional[str] = None
    target_language: str = "en"
    auto_detect: bool = True

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "provider": self.provider,
            "sub_provider": self.sub_provider,
            "source_language": self.source_language,
            "target_language": self.target_language,
            "auto_detect": self.auto_detect,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TranslationOptions":
        """Create from dictionary."""
        return cls(
            provider=data.get("provider", "deep_translator"),
            sub_provider=data.get("sub_provider", "google"),
            source_language=data.get("source_language"),
            target_language=data.get("target_language", "en"),
            auto_detect=data.get("auto_detect", True),
        )


@dataclass
class AudioRecordingOptions:
    """Options for audio recording.

    Attributes:
        sample_rate: Audio sample rate in Hz
        channels: Number of audio channels (1=mono, 2=stereo)
        chunk_size: Audio chunk size in samples
        device_index: Input device index (None for default)
        silence_threshold: Silence detection threshold (dB)
        silence_duration: Duration of silence to detect (seconds)
    """
    sample_rate: int = 16000
    channels: int = 1
    chunk_size: int = 1024
    device_index: Optional[int] = None
    silence_threshold: float = -40.0
    silence_duration: float = 2.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "sample_rate": self.sample_rate,
            "channels": self.channels,
            "chunk_size": self.chunk_size,
            "device_index": self.device_index,
            "silence_threshold": self.silence_threshold,
            "silence_duration": self.silence_duration,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AudioRecordingOptions":
        """Create from dictionary."""
        return cls(
            sample_rate=data.get("sample_rate", 16000),
            channels=data.get("channels", 1),
            chunk_size=data.get("chunk_size", 1024),
            device_index=data.get("device_index"),
            silence_threshold=data.get("silence_threshold", -40.0),
            silence_duration=data.get("silence_duration", 2.0),
        )


@dataclass
class ProcessingQueueOptions:
    """Options for the processing queue.

    Attributes:
        max_workers: Maximum concurrent worker threads
        retry_failed: Automatically retry failed tasks
        max_retries: Maximum retry attempts for failed tasks
        deduplication: Prevent duplicate tasks for same recording
        batch_size: Number of tasks to process in a batch
    """
    max_workers: int = 3
    retry_failed: bool = True
    max_retries: int = 2
    deduplication: bool = True
    batch_size: int = 10

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for backwards compatibility."""
        return {
            "max_workers": self.max_workers,
            "retry_failed": self.retry_failed,
            "max_retries": self.max_retries,
            "deduplication": self.deduplication,
            "batch_size": self.batch_size,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProcessingQueueOptions":
        """Create from dictionary."""
        return cls(
            max_workers=data.get("max_workers", 3),
            retry_failed=data.get("retry_failed", True),
            max_retries=data.get("max_retries", 2),
            deduplication=data.get("deduplication", True),
            batch_size=data.get("batch_size", 10),
        )
