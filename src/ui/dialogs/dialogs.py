"""
Dialogs Module

This module provides dialog functions for the Medical Assistant application.
Functions are organized into submodules for better maintainability:

- model_providers: Functions for fetching AI model lists from providers
- dialog_utils: Common dialog utility functions
- audio_settings: Audio/TTS/STT settings dialogs
- api_key_dialogs: API key prompting and saving
- settings_dialogs: Settings dialog with prompt and model configuration
- api_keys_dialog: Update API keys dialog
- help_dialogs: Shortcuts and about dialogs
- document_dialogs: Letter options and letterhead dialogs

For backward compatibility, all functions are re-exported from this module.
"""

# Import from model_providers submodule
from ui.dialogs.model_providers import (
    clear_model_cache,
    get_openai_models,
    get_fallback_openai_models,
    get_ollama_models,
    get_anthropic_models,
    get_fallback_anthropic_models,
    get_gemini_models,
    get_fallback_gemini_models,
    _model_cache,
    _cache_ttl,
)

# Import from dialog_utils submodule
from ui.dialogs.dialog_utils import (
    create_toplevel_dialog,
    create_model_selector,
    create_model_selection_dialog,
    askstring_min,
    ask_conditions_dialog,
)

# Import from audio_settings submodule
from ui.dialogs.audio_settings import (
    show_elevenlabs_settings_dialog,
    show_deepgram_settings_dialog,
    show_groq_settings_dialog,
    show_translation_settings_dialog,
    show_tts_settings_dialog,
    show_custom_suggestions_dialog,
    test_ollama_connection,
    _fetch_tts_voices,
)

# Import from api_key_dialogs submodule
from ui.dialogs.api_key_dialogs import (
    prompt_for_api_key,
    save_api_key_to_env,
)

# Import from settings_dialogs submodule
from ui.dialogs.settings_dialogs import (
    _create_prompt_tab,
    _create_soap_prompts_tab,
    _create_models_tab,
    _create_temperature_tab,
    show_settings_dialog,
)

# Import from api_keys_dialog submodule
from ui.dialogs.api_keys_dialog import (
    show_api_keys_dialog,
)

# Import from help_dialogs submodule
from ui.dialogs.help_dialogs import (
    show_shortcuts_dialog,
    show_about_dialog,
)

# Import from document_dialogs submodule
from ui.dialogs.document_dialogs import (
    show_letter_options_dialog,
    show_letterhead_dialog,
)


__all__ = [
    # model_providers
    "clear_model_cache",
    "get_openai_models",
    "get_fallback_openai_models",
    "get_ollama_models",
    "get_anthropic_models",
    "get_fallback_anthropic_models",
    "get_gemini_models",
    "get_fallback_gemini_models",
    "_model_cache",
    "_cache_ttl",
    # dialog_utils
    "create_toplevel_dialog",
    "create_model_selector",
    "create_model_selection_dialog",
    "askstring_min",
    "ask_conditions_dialog",
    # audio_settings
    "show_elevenlabs_settings_dialog",
    "show_deepgram_settings_dialog",
    "show_groq_settings_dialog",
    "show_translation_settings_dialog",
    "show_tts_settings_dialog",
    "show_custom_suggestions_dialog",
    "test_ollama_connection",
    "_fetch_tts_voices",
    # api_key_dialogs
    "prompt_for_api_key",
    "save_api_key_to_env",
    # settings_dialogs
    "_create_prompt_tab",
    "_create_soap_prompts_tab",
    "_create_models_tab",
    "_create_temperature_tab",
    "show_settings_dialog",
    # api_keys_dialog
    "show_api_keys_dialog",
    # help_dialogs
    "show_shortcuts_dialog",
    "show_about_dialog",
    # document_dialogs
    "show_letter_options_dialog",
    "show_letterhead_dialog",
]
