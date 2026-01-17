"""
Centralized settings management for Medical Assistant.

This module provides a SettingsManager class that abstracts direct access to the
SETTINGS dictionary, providing type safety, validation, and a consistent API.

Usage:
    from settings.settings_manager import settings_manager

    # Simple access
    provider = settings_manager.get_ai_provider()
    settings_manager.set_ai_provider("anthropic")

    # Nested access
    model = settings_manager.get_nested("soap_note.model")
    settings_manager.set_nested("soap_note.temperature", 0.5)

    # Domain-specific typed access
    config = settings_manager.get_model_config("soap_note")
    agent = settings_manager.get_agent_config("diagnostic")
"""

from typing import Any, Dict, Optional, TypeVar, cast
from utils.structured_logging import get_logger
from settings.settings_types import (
    ModelConfig, AgentConfig, SOAPNoteConfig, TranslationSettings,
    TTSSettings, ElevenLabsSettings, DeepgramSettings, GroqSettings,
    AdvancedAnalysisSettings, ChatInterfaceSettings
)

logger = get_logger(__name__)

T = TypeVar('T')


class SettingsManager:
    """Centralized settings access with type safety and validation.

    This class provides a singleton interface to application settings,
    abstracting direct SETTINGS dict access. It maintains full backward
    compatibility while enabling gradual migration to typed accessors.

    Features:
    - Singleton pattern (thread-safe via module-level instance)
    - Pass-through to existing SETTINGS dict
    - Typed accessors for common settings
    - Nested path access (e.g., "soap_note.model")
    - Auto-save on mutations
    - Validation hooks (future)
    """

    _instance: Optional['SettingsManager'] = None

    def __new__(cls) -> 'SettingsManager':
        """Ensure singleton instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize settings manager."""
        if self._initialized:
            return
        self._initialized = True
        # Lazy import to avoid circular dependencies
        self._settings_module = None
        logger.debug("SettingsManager initialized")

    @property
    def _settings(self) -> Dict[str, Any]:
        """Get the underlying SETTINGS dict (lazy loaded)."""
        if self._settings_module is None:
            from settings.settings import SETTINGS
            self._settings_module = SETTINGS
        return self._settings_module

    def _save(self) -> None:
        """Save settings to disk."""
        from settings.settings import save_settings, SETTINGS
        save_settings(SETTINGS)

    # =========================================================================
    # Basic Access Methods
    # =========================================================================

    def get(self, key: str, default: Any = None) -> Any:
        """Get a top-level setting value.

        Args:
            key: Setting key (e.g., "ai_provider", "theme")
            default: Default value if key not found

        Returns:
            Setting value or default
        """
        return self._settings.get(key, default)

    def get_default(self, key: str, default: Any = None) -> Any:
        """Get the default value for a setting from _DEFAULT_SETTINGS.

        Args:
            key: Setting key (e.g., "translation_canned_responses")
            default: Fallback value if key not found in defaults

        Returns:
            Default setting value or fallback
        """
        from settings.settings import _DEFAULT_SETTINGS
        return _DEFAULT_SETTINGS.get(key, default)

    def get_all(self) -> Dict[str, Any]:
        """Get all settings as a dictionary.

        Returns a reference to the underlying settings dict. Modifications
        to the returned dict will affect the settings directly.

        Returns:
            Dict containing all settings
        """
        return self._settings

    def set(self, key: str, value: Any, auto_save: bool = True) -> None:
        """Set a top-level setting value.

        Args:
            key: Setting key
            value: New value
            auto_save: Whether to save immediately (default: True)
        """
        self._settings[key] = value
        if auto_save:
            self._save()

    def get_nested(self, path: str, default: Any = None) -> Any:
        """Get a nested setting value using dot notation.

        Args:
            path: Dot-separated path (e.g., "soap_note.model", "agent_config.diagnostic.enabled")
            default: Default value if path not found

        Returns:
            Setting value or default

        Example:
            model = settings_manager.get_nested("soap_note.model")
            enabled = settings_manager.get_nested("agent_config.diagnostic.enabled", False)
        """
        keys = path.split('.')
        value = self._settings

        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
                if value is None:
                    return default
            else:
                return default

        return value if value is not None else default

    def set_nested(self, path: str, value: Any, auto_save: bool = True) -> None:
        """Set a nested setting value using dot notation.

        Args:
            path: Dot-separated path (e.g., "soap_note.model")
            value: New value
            auto_save: Whether to save immediately (default: True)

        Example:
            settings_manager.set_nested("soap_note.temperature", 0.5)
            settings_manager.set_nested("agent_config.diagnostic.enabled", True)
        """
        keys = path.split('.')
        target = self._settings

        # Navigate to parent of final key
        for key in keys[:-1]:
            if key not in target:
                target[key] = {}
            target = target[key]

        # Set the value
        target[keys[-1]] = value

        if auto_save:
            self._save()

    # =========================================================================
    # Provider Accessors
    # =========================================================================

    def get_ai_provider(self) -> str:
        """Get the current AI provider."""
        return self.get("ai_provider", "openai")

    def set_ai_provider(self, provider: str) -> None:
        """Set the AI provider."""
        self.set("ai_provider", provider)

    def get_stt_provider(self) -> str:
        """Get the current STT provider."""
        return self.get("stt_provider", "groq")

    def set_stt_provider(self, provider: str) -> None:
        """Set the STT provider."""
        self.set("stt_provider", provider)

    def get_theme(self) -> str:
        """Get the current UI theme."""
        return self.get("theme", "flatly")

    def set_theme(self, theme: str) -> None:
        """Set the UI theme."""
        self.set("theme", theme)

    # =========================================================================
    # Model Configuration Accessors
    # =========================================================================

    def get_model_config(self, domain: str) -> ModelConfig:
        """Get model configuration for a domain.

        Args:
            domain: Config domain (e.g., "soap_note", "refine_text", "improve_text", "referral")

        Returns:
            ModelConfig dict with model, temperature, prompt settings
        """
        config = self._settings.get(domain, {})
        return cast(ModelConfig, config if isinstance(config, dict) else {})

    def set_model_config(self, domain: str, config: ModelConfig) -> None:
        """Set model configuration for a domain.

        Args:
            domain: Config domain
            config: ModelConfig dict
        """
        self._settings[domain] = dict(config)
        self._save()

    def get_soap_config(self) -> SOAPNoteConfig:
        """Get SOAP note configuration."""
        return cast(SOAPNoteConfig, self._settings.get("soap_note", {}))

    def set_soap_config(self, config: SOAPNoteConfig) -> None:
        """Set SOAP note configuration."""
        self._settings["soap_note"] = dict(config)
        self._save()

    # =========================================================================
    # Agent Configuration Accessors
    # =========================================================================

    def get_agent_config(self, agent_name: str) -> AgentConfig:
        """Get configuration for a specific agent.

        Args:
            agent_name: Agent name (e.g., "synopsis", "diagnostic", "medication", "workflow")

        Returns:
            AgentConfig dict
        """
        agent_configs = self._settings.get("agent_config", {})
        return cast(AgentConfig, agent_configs.get(agent_name, {}))

    def set_agent_config(self, agent_name: str, config: AgentConfig) -> None:
        """Set configuration for a specific agent.

        Args:
            agent_name: Agent name
            config: AgentConfig dict
        """
        if "agent_config" not in self._settings:
            self._settings["agent_config"] = {}
        self._settings["agent_config"][agent_name] = dict(config)
        self._save()

    def is_agent_enabled(self, agent_name: str) -> bool:
        """Check if an agent is enabled.

        Args:
            agent_name: Agent name

        Returns:
            True if enabled, False otherwise
        """
        config = self.get_agent_config(agent_name)
        return config.get("enabled", False)

    def set_agent_enabled(self, agent_name: str, enabled: bool) -> None:
        """Enable or disable an agent.

        Args:
            agent_name: Agent name
            enabled: Whether to enable
        """
        self.set_nested(f"agent_config.{agent_name}.enabled", enabled)

    # =========================================================================
    # Translation & TTS Accessors
    # =========================================================================

    def get_translation_settings(self) -> TranslationSettings:
        """Get translation settings."""
        return cast(TranslationSettings, self._settings.get("translation", {}))

    def set_translation_settings(self, settings: TranslationSettings) -> None:
        """Set translation settings."""
        self._settings["translation"] = dict(settings)
        self._save()

    def get_tts_settings(self) -> TTSSettings:
        """Get TTS settings."""
        return cast(TTSSettings, self._settings.get("tts", {}))

    def set_tts_settings(self, settings: TTSSettings) -> None:
        """Set TTS settings."""
        self._settings["tts"] = dict(settings)
        self._save()

    # =========================================================================
    # STT Provider Settings Accessors
    # =========================================================================

    def get_elevenlabs_settings(self) -> ElevenLabsSettings:
        """Get ElevenLabs settings."""
        return cast(ElevenLabsSettings, self._settings.get("elevenlabs", {}))

    def set_elevenlabs_settings(self, settings: ElevenLabsSettings) -> None:
        """Set ElevenLabs settings."""
        self._settings["elevenlabs"] = dict(settings)
        self._save()

    def get_deepgram_settings(self) -> DeepgramSettings:
        """Get Deepgram settings."""
        return cast(DeepgramSettings, self._settings.get("deepgram", {}))

    def set_deepgram_settings(self, settings: DeepgramSettings) -> None:
        """Set Deepgram settings."""
        self._settings["deepgram"] = dict(settings)
        self._save()

    def get_groq_settings(self) -> GroqSettings:
        """Get Groq settings."""
        return cast(GroqSettings, self._settings.get("groq", {}))

    def set_groq_settings(self, settings: GroqSettings) -> None:
        """Set Groq settings."""
        self._settings["groq"] = dict(settings)
        self._save()

    # =========================================================================
    # Advanced Analysis Accessors
    # =========================================================================

    def get_advanced_analysis_settings(self) -> AdvancedAnalysisSettings:
        """Get advanced analysis settings."""
        return cast(AdvancedAnalysisSettings, self._settings.get("advanced_analysis", {}))

    def set_advanced_analysis_settings(self, settings: AdvancedAnalysisSettings) -> None:
        """Set advanced analysis settings."""
        self._settings["advanced_analysis"] = dict(settings)
        self._save()

    # =========================================================================
    # Chat Interface Accessors
    # =========================================================================

    def get_chat_settings(self) -> ChatInterfaceSettings:
        """Get chat interface settings."""
        return cast(ChatInterfaceSettings, self._settings.get("chat_interface", {}))

    def set_chat_settings(self, settings: ChatInterfaceSettings) -> None:
        """Set chat interface settings."""
        self._settings["chat_interface"] = dict(settings)
        self._save()

    # =========================================================================
    # Feature Flag Accessors
    # =========================================================================

    def is_quick_continue_mode(self) -> bool:
        """Check if quick continue mode is enabled."""
        return self.get("quick_continue_mode", True)

    # Alias for compatibility
    def get_quick_continue_mode(self) -> bool:
        """Get quick continue mode status (alias for is_quick_continue_mode)."""
        return self.is_quick_continue_mode()

    def set_quick_continue_mode(self, enabled: bool) -> None:
        """Enable or disable quick continue mode."""
        self.set("quick_continue_mode", enabled)

    def is_autosave_enabled(self) -> bool:
        """Check if autosave is enabled."""
        return self.get("autosave_enabled", True)

    def set_autosave_enabled(self, enabled: bool) -> None:
        """Enable or disable autosave."""
        self.set("autosave_enabled", enabled)

    # =========================================================================
    # Window State Accessors
    # =========================================================================

    def get_window_dimensions(self) -> tuple:
        """Get saved window dimensions.

        Returns:
            Tuple of (width, height) or (0, 0) if not set
        """
        width = self.get("window_width", 0)
        height = self.get("window_height", 0)
        return (width, height)

    def set_window_dimensions(self, width: int, height: int) -> None:
        """Save window dimensions."""
        self._settings["window_width"] = width
        self._settings["window_height"] = height
        self._save()

    def is_sidebar_collapsed(self) -> bool:
        """Check if sidebar is collapsed."""
        return self.get("sidebar_collapsed", False)

    def set_sidebar_collapsed(self, collapsed: bool) -> None:
        """Set sidebar collapsed state."""
        self.set("sidebar_collapsed", collapsed)

    # =========================================================================
    # Persistence Methods
    # =========================================================================

    def save(self) -> None:
        """Explicitly save settings to disk."""
        self._save()

    def reload(self) -> None:
        """Reload settings from disk."""
        from settings.settings import load_settings
        load_settings(force_refresh=True)
        # Reset cached reference
        self._settings_module = None
        logger.debug("Settings reloaded from disk")


# Module-level singleton instance
settings_manager = SettingsManager()
