"""
Pydantic Settings Validation Models

This module provides runtime validation for application settings using Pydantic.
It catches configuration errors early (typos, invalid values) and provides
clear error messages.

Usage:
    from settings.settings_models import validate_settings

    settings_dict = load_raw_settings()
    validated, result = validate_settings(settings_dict)
    for warning in result.warnings:
        logger.warning(f"Settings: {warning}")
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Literal
from enum import Enum

try:
    from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
    PYDANTIC_AVAILABLE = True
except ImportError:
    PYDANTIC_AVAILABLE = False
    # Stub classes when Pydantic not available
    class BaseModel:
        pass

    def Field(*args, **kwargs):
        return None

    def field_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator

    def model_validator(*args, **kwargs):
        def decorator(func):
            return func
        return decorator


# =============================================================================
# Validation Result
# =============================================================================

@dataclass
class ValidationResult:
    """Result of settings validation."""
    is_valid: bool = True
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    unknown_keys: List[str] = field(default_factory=list)


# =============================================================================
# Pydantic Models for Settings Sections
# =============================================================================

if PYDANTIC_AVAILABLE:

    class LoggingSettings(BaseModel):
        """Logging configuration settings."""
        model_config = ConfigDict(extra="allow")

        level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
        file_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG"
        console_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
        max_file_size_kb: int = Field(default=200, ge=10, le=10000)
        backup_count: int = Field(default=2, ge=0, le=20)

    class RAGResilienceSettings(BaseModel):
        """RAG resilience and circuit breaker settings."""
        model_config = ConfigDict(extra="allow")

        neo4j_failure_threshold: int = Field(default=3, ge=1, le=20)
        neo4j_recovery_timeout: int = Field(default=30, ge=5, le=600)
        neon_failure_threshold: int = Field(default=5, ge=1, le=20)
        neon_recovery_timeout: int = Field(default=30, ge=5, le=600)
        embedding_failure_threshold: int = Field(default=5, ge=1, le=20)
        embedding_recovery_timeout: int = Field(default=60, ge=5, le=600)
        health_check_cache_ttl: int = Field(default=30, ge=5, le=300)

    class RAGSearchQualitySettings(BaseModel):
        """RAG search quality enhancement settings."""
        model_config = ConfigDict(extra="allow")

        enable_adaptive_threshold: bool = True
        min_threshold: float = Field(default=0.2, ge=0.0, le=1.0)
        max_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
        target_result_count: int = Field(default=5, ge=1, le=50)
        enable_query_expansion: bool = True
        expand_abbreviations: bool = True
        expand_synonyms: bool = True
        max_expansion_terms: int = Field(default=3, ge=1, le=10)
        enable_bm25: bool = True
        vector_weight: float = Field(default=0.5, ge=0.0, le=1.0)
        bm25_weight: float = Field(default=0.3, ge=0.0, le=1.0)
        graph_weight: float = Field(default=0.2, ge=0.0, le=1.0)
        enable_mmr: bool = True
        mmr_lambda: float = Field(default=0.7, ge=0.0, le=1.0)

        @model_validator(mode="after")
        def validate_weights_sum(self):
            """Validate that weights sum to approximately 1.0."""
            total = self.vector_weight + self.bm25_weight + self.graph_weight
            if not (0.9 <= total <= 1.1):
                # Just warn, don't fail
                pass
            return self

    class SOAPNoteSettings(BaseModel):
        """SOAP note generation settings."""
        model_config = ConfigDict(extra="allow")

        model: str = "gpt-3.5-turbo"
        ollama_model: str = "llama3"
        anthropic_model: str = "claude-sonnet-4-20250514"
        gemini_model: str = "gemini-2.0-flash"
        temperature: float = Field(default=0.4, ge=0.0, le=2.0)
        openai_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
        ollama_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
        anthropic_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
        gemini_temperature: float = Field(default=0.4, ge=0.0, le=2.0)
        icd_code_version: Literal["ICD-9", "ICD-10", "both"] = "ICD-9"
        system_message: str = ""
        openai_system_message: str = ""
        anthropic_system_message: str = ""
        ollama_system_message: str = ""
        gemini_system_message: str = ""

    class AgentSettings(BaseModel):
        """Settings for an individual agent."""
        model_config = ConfigDict(extra="allow")

        enabled: bool = False
        provider: str = "openai"
        model: str = "gpt-4"
        temperature: float = Field(default=0.3, ge=0.0, le=2.0)
        max_tokens: int = Field(default=500, ge=50, le=16000)
        system_prompt: str = ""

    class AgentConfigSettings(BaseModel):
        """Collection of agent configurations."""
        model_config = ConfigDict(extra="allow")

        synopsis: Optional[AgentSettings] = None
        diagnostic: Optional[AgentSettings] = None
        medication: Optional[AgentSettings] = None
        referral: Optional[AgentSettings] = None
        data_extraction: Optional[AgentSettings] = None
        workflow: Optional[AgentSettings] = None

    class TranslationSettings(BaseModel):
        """Translation feature settings."""
        model_config = ConfigDict(extra="allow")

        provider: str = "deep_translator"
        sub_provider: str = "google"
        patient_language: str = "es"
        doctor_language: str = "en"
        auto_detect: bool = True
        input_device: str = ""
        output_device: str = ""
        llm_refinement_enabled: bool = False
        refinement_provider: str = "openai"
        refinement_model: str = "gpt-3.5-turbo"
        refinement_temperature: float = Field(default=0.1, ge=0.0, le=2.0)

    class TTSSettings(BaseModel):
        """Text-to-speech settings."""
        model_config = ConfigDict(extra="allow")

        provider: str = "pyttsx3"
        voice: str = "default"
        rate: int = Field(default=150, ge=50, le=400)
        volume: float = Field(default=1.0, ge=0.0, le=1.0)
        language: str = "en"
        elevenlabs_model: str = "eleven_turbo_v2_5"

    class ChatInterfaceSettings(BaseModel):
        """Chat interface settings."""
        model_config = ConfigDict(extra="allow")

        enabled: bool = True
        max_input_length: int = Field(default=2000, ge=100, le=50000)
        max_context_length: int = Field(default=8000, ge=1000, le=128000)
        max_history_items: int = Field(default=10, ge=1, le=100)
        show_suggestions: bool = True
        auto_apply_changes: bool = True
        temperature: float = Field(default=0.3, ge=0.0, le=2.0)

    class RSVPSettings(BaseModel):
        """RSVP reader settings."""
        model_config = ConfigDict(extra="allow")

        wpm: int = Field(default=300, ge=50, le=2000)
        font_size: int = Field(default=48, ge=12, le=200)
        chunk_size: int = Field(default=1, ge=1, le=5)
        auto_start: bool = False
        dark_theme: bool = True
        audio_cue: bool = False
        show_context: bool = False

    class AllSettings(BaseModel):
        """
        Complete settings model with validation.

        This is the top-level model that validates all settings sections.
        Uses extra="allow" to permit forward compatibility with new settings.
        """
        model_config = ConfigDict(extra="allow")

        # Core settings
        ai_provider: str = "openai"
        stt_provider: str = "groq"
        theme: str = "flatly"
        storage_folder: str = ""
        default_folder: str = ""
        default_storage_folder: str = ""

        # Feature flags
        quick_continue_mode: bool = True
        max_background_workers: int = Field(default=2, ge=1, le=10)
        max_guideline_workers: int = Field(default=4, ge=1, le=16)
        show_processing_notifications: bool = True
        auto_retry_failed: bool = True
        auto_update_ui_on_completion: bool = True
        max_retry_attempts: int = Field(default=3, ge=1, le=10)
        autosave_enabled: bool = True
        autosave_interval: int = Field(default=300, ge=30, le=3600)
        recording_autosave_enabled: bool = True
        recording_autosave_interval: int = Field(default=60, ge=10, le=600)
        notification_style: str = "toast"

        # Window state
        window_width: int = Field(default=1200, ge=400, le=10000)
        window_height: int = Field(default=800, ge=300, le=10000)

        # UI collapse states
        sidebar_collapsed: bool = False
        sidebar_file_expanded: bool = True
        sidebar_generate_expanded: bool = True
        sidebar_tools_expanded: bool = True
        advanced_analysis_collapsed: bool = True
        analysis_panel_collapsed: bool = True
        bottom_section_collapsed: bool = False

        # Global temperature
        temperature: float = Field(default=0.4, ge=0.0, le=2.0)

        # Prompt/text settings (allow any dict structure)
        refine_text: Optional[Dict[str, Any]] = None
        improve_text: Optional[Dict[str, Any]] = None
        referral: Optional[Dict[str, Any]] = None
        advanced_analysis: Optional[Dict[str, Any]] = None

        # STT provider settings
        deepgram: Optional[Dict[str, Any]] = None
        elevenlabs: Optional[Dict[str, Any]] = None
        groq: Optional[Dict[str, Any]] = None

        # Custom data
        custom_vocabulary: Optional[Dict[str, Any]] = None
        custom_chat_suggestions: Optional[Dict[str, Any]] = None
        custom_context_templates: Optional[Dict[str, Any]] = None
        context_template_favorites: Optional[List[str]] = None
        translation_canned_responses: Optional[Dict[str, Any]] = None

        # Nested settings
        logging: Optional[LoggingSettings] = None
        rag_resilience: Optional[RAGResilienceSettings] = None
        rag_search_quality: Optional[RAGSearchQualitySettings] = None
        soap_note: Optional[SOAPNoteSettings] = None
        agent_config: Optional[AgentConfigSettings] = None
        ai_config: Optional[Dict[str, Any]] = None  # Legacy/alternative agent config
        translation: Optional[TranslationSettings] = None
        tts: Optional[TTSSettings] = None
        chat_interface: Optional[ChatInterfaceSettings] = None
        rsvp: Optional[RSVPSettings] = None
        rsvp_reader: Optional[RSVPSettings] = None  # Alternative key for RSVP

        @field_validator("ai_provider")
        @classmethod
        def validate_ai_provider(cls, v):
            """Validate AI provider is a known value."""
            known_providers = {"openai", "anthropic", "ollama", "gemini", "grok", "deepseek"}
            if v.lower() not in known_providers:
                # Warning but don't fail - might be a new provider
                pass
            return v

        @field_validator("stt_provider")
        @classmethod
        def validate_stt_provider(cls, v):
            """Validate STT provider is a known value."""
            known_providers = {"groq", "deepgram", "elevenlabs", "whisper", "google"}
            if v.lower() not in known_providers:
                pass
            return v


# =============================================================================
# Validation Functions
# =============================================================================

def validate_settings(settings_dict: Dict[str, Any]) -> tuple:
    """
    Validate settings dictionary against Pydantic models.

    Args:
        settings_dict: Raw settings dictionary

    Returns:
        Tuple of (validated_settings or original dict, ValidationResult)
    """
    result = ValidationResult()

    if not PYDANTIC_AVAILABLE:
        result.warnings.append("Pydantic not available - skipping validation")
        return settings_dict, result

    try:
        # Validate using the top-level model
        validated = AllSettings(**settings_dict)

        # Collect warnings for unknown top-level keys
        known_keys = set(AllSettings.model_fields.keys())
        for key in settings_dict.keys():
            if key not in known_keys and not key.startswith("_"):
                result.unknown_keys.append(key)

        if result.unknown_keys:
            result.warnings.append(
                f"Unknown settings keys (may be typos): {', '.join(result.unknown_keys[:5])}"
                + (f" (+{len(result.unknown_keys) - 5} more)" if len(result.unknown_keys) > 5 else "")
            )

        # Check for common typos
        _check_common_typos(settings_dict, result)

        # Validate weight sums if RAG search quality is present
        if "rag_search_quality" in settings_dict:
            rsq = settings_dict["rag_search_quality"]
            total = rsq.get("vector_weight", 0.5) + rsq.get("bm25_weight", 0.3) + rsq.get("graph_weight", 0.2)
            if not (0.9 <= total <= 1.1):
                result.warnings.append(
                    f"RAG search weights sum to {total:.2f} (expected ~1.0)"
                )

        return validated.model_dump(), result

    except Exception as e:
        result.is_valid = False
        result.errors.append(f"Validation failed: {str(e)}")
        # Return original settings if validation fails
        return settings_dict, result


def _check_common_typos(settings_dict: Dict[str, Any], result: ValidationResult) -> None:
    """Check for common typos in settings keys."""
    typo_suggestions = {
        # Top level
        "ai_provder": "ai_provider",
        "stt_provder": "stt_provider",
        "quick_continu_mode": "quick_continue_mode",
        "autosave_enbled": "autosave_enabled",
        "loging": "logging",

        # SOAP note
        "temperture": "temperature",
        "icd_code_verion": "icd_code_version",
        "system_mesage": "system_message",

        # RAG
        "rag_search_qualtiy": "rag_search_quality",
        "rag_resilence": "rag_resilience",
        "vector_wieght": "vector_weight",
        "mmr_lamda": "mmr_lambda",

        # Agents
        "agent_confg": "agent_config",
        "system_promt": "system_prompt",
        "max_tokns": "max_tokens",

        # Other
        "transltion": "translation",
        "chat_interfce": "chat_interface",
    }

    def check_dict_keys(d: Dict, path: str = ""):
        """Recursively check for typos in dict keys."""
        if not isinstance(d, dict):
            return

        for key, value in d.items():
            full_key = f"{path}.{key}" if path else key

            if key in typo_suggestions:
                result.warnings.append(
                    f"Possible typo: '{full_key}' - did you mean '{typo_suggestions[key]}'?"
                )

            if isinstance(value, dict):
                check_dict_keys(value, full_key)

    check_dict_keys(settings_dict)


def validate_setting_value(key: str, value: Any, section: str = None) -> ValidationResult:
    """
    Validate a single setting value.

    Args:
        key: The setting key
        value: The value to validate
        section: Optional section name for context

    Returns:
        ValidationResult with any errors/warnings
    """
    result = ValidationResult()

    # Temperature validation
    if "temperature" in key:
        if not isinstance(value, (int, float)):
            result.errors.append(f"{key}: must be a number, got {type(value).__name__}")
        elif not (0.0 <= value <= 2.0):
            result.warnings.append(f"{key}: {value} is outside typical range (0.0-2.0)")

    # Max tokens validation
    if "max_tokens" in key:
        if not isinstance(value, int):
            result.errors.append(f"{key}: must be an integer")
        elif value < 50:
            result.warnings.append(f"{key}: {value} is very low, may truncate responses")
        elif value > 16000:
            result.warnings.append(f"{key}: {value} exceeds most model limits")

    # Boolean validation
    bool_keys = {"enabled", "auto_start", "dark_theme", "audio_cue", "show_context",
                 "diarize", "smart_format", "auto_detect"}
    if key in bool_keys:
        if not isinstance(value, bool):
            result.warnings.append(f"{key}: expected boolean, got {type(value).__name__}")

    return result


# =============================================================================
# Helper Functions
# =============================================================================

def get_settings_schema() -> Dict[str, Any]:
    """
    Get JSON schema for settings validation.

    Useful for documentation or external validation tools.

    Returns:
        JSON schema dictionary
    """
    if not PYDANTIC_AVAILABLE:
        return {"error": "Pydantic not available"}

    return AllSettings.model_json_schema()


def is_pydantic_available() -> bool:
    """Check if Pydantic is available for validation."""
    return PYDANTIC_AVAILABLE
