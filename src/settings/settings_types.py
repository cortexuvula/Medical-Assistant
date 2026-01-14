"""
Type definitions for Medical Assistant settings.

This module provides TypedDict definitions for all settings structures,
enabling type checking and IDE autocomplete for settings access.
"""

from typing import TypedDict, Optional, List, Dict, Any


class ModelConfig(TypedDict, total=False):
    """Configuration for AI model settings."""
    model: str
    ollama_model: str
    anthropic_model: str
    gemini_model: str
    temperature: float
    openai_temperature: float
    ollama_temperature: float
    anthropic_temperature: float
    gemini_temperature: float
    prompt: str
    system_message: str


class AgentConfig(TypedDict, total=False):
    """Configuration for an AI agent."""
    enabled: bool
    provider: str
    model: str
    temperature: float
    max_tokens: int
    system_prompt: str
    auto_run_after_soap: bool


class SOAPNoteConfig(TypedDict, total=False):
    """Configuration for SOAP note generation."""
    model: str
    ollama_model: str
    anthropic_model: str
    gemini_model: str
    temperature: float
    openai_temperature: float
    ollama_temperature: float
    anthropic_temperature: float
    gemini_temperature: float
    system_message: str
    openai_system_message: str
    anthropic_system_message: str
    ollama_system_message: str
    gemini_system_message: str
    icd_code_version: str


class TranslationSettings(TypedDict, total=False):
    """Configuration for translation features."""
    patient_language: str
    doctor_language: str
    provider: str
    llm_refinement_enabled: bool
    llm_refinement_provider: str
    canned_responses: List[Dict[str, str]]


class TTSSettings(TypedDict, total=False):
    """Configuration for text-to-speech."""
    provider: str
    voice_id: str
    model: str
    rate: float


class ElevenLabsSettings(TypedDict, total=False):
    """Configuration for ElevenLabs STT/TTS."""
    api_key: str
    diarize: bool
    tag_audio_events: bool
    timestamps: bool
    model: str


class DeepgramSettings(TypedDict, total=False):
    """Configuration for Deepgram STT."""
    api_key: str
    model: str
    smart_format: bool
    diarize: bool
    punctuate: bool
    profanity_filter: bool
    redact: bool
    paragraphs: bool


class GroqSettings(TypedDict, total=False):
    """Configuration for Groq STT."""
    api_key: str
    model: str
    language: str


class AdvancedAnalysisSettings(TypedDict, total=False):
    """Configuration for advanced/periodic analysis."""
    provider: str
    model: str
    temperature: float
    openai_temperature: float
    anthropic_temperature: float
    ollama_temperature: float
    gemini_temperature: float
    prompt: str
    system_message: str


class ChatInterfaceSettings(TypedDict, total=False):
    """Configuration for chat interface."""
    enable_tools: bool
    show_suggestions: bool


class CustomVocabularySettings(TypedDict, total=False):
    """Configuration for custom vocabulary."""
    enabled: bool
    words: List[str]


class WindowSettings(TypedDict, total=False):
    """Window state settings."""
    width: int
    height: int
    sidebar_collapsed: bool


class AllSettings(TypedDict, total=False):
    """Complete settings dictionary type."""
    # Core providers
    ai_provider: str
    stt_provider: str
    theme: str

    # Model configurations
    soap_note: SOAPNoteConfig
    refine_text: ModelConfig
    improve_text: ModelConfig
    referral: ModelConfig

    # Agent configurations
    agent_config: Dict[str, AgentConfig]

    # Advanced analysis
    advanced_analysis: AdvancedAnalysisSettings

    # STT providers
    elevenlabs: ElevenLabsSettings
    deepgram: DeepgramSettings
    groq: GroqSettings

    # Translation & TTS
    translation: TranslationSettings
    tts: TTSSettings

    # Chat
    chat_interface: ChatInterfaceSettings

    # Vocabulary
    custom_vocabulary: CustomVocabularySettings

    # UI state
    window_width: int
    window_height: int
    sidebar_collapsed: bool

    # Feature flags
    quick_continue_mode: bool
    autosave_enabled: bool
    show_processing_notifications: bool

    # Storage
    storage_folder: str
