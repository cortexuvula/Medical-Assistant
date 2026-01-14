"""
Settings package for Medical Assistant.

This package provides settings management including:
- SETTINGS dict (legacy, for backward compatibility)
- SettingsManager class (recommended for new code)
- Type definitions for settings structures
"""

from settings.settings import SETTINGS, save_settings, load_settings
from settings.settings_manager import settings_manager, SettingsManager
from settings.settings_types import (
    ModelConfig,
    AgentConfig,
    SOAPNoteConfig,
    TranslationSettings,
    TTSSettings,
)

__all__ = [
    # Legacy exports (backward compatible)
    "SETTINGS",
    "save_settings",
    "load_settings",
    # New exports (recommended)
    "settings_manager",
    "SettingsManager",
    # Type exports
    "ModelConfig",
    "AgentConfig",
    "SOAPNoteConfig",
    "TranslationSettings",
    "TTSSettings",
]
