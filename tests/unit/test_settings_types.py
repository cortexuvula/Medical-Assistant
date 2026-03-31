"""
Tests for src/settings/settings_types.py

Covers structural properties of all TypedDicts:
- ModelConfig, AgentConfig, SOAPNoteConfig, TranslationSettings, TTSSettings,
  ElevenLabsSettings, DeepgramSettings, GroqSettings, AdvancedAnalysisSettings,
  ChatInterfaceSettings, CustomVocabularySettings, WindowSettings, AllSettings

TypedDicts don't enforce types at runtime, so tests verify:
- Each class can be instantiated (empty dict with no required keys)
- Expected keys are present in __annotations__
- total=False means no key is required (empty dict is valid)
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from pathlib import Path
from typing import get_type_hints

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from settings.settings_types import (
    ModelConfig,
    AgentConfig,
    SOAPNoteConfig,
    TranslationSettings,
    TTSSettings,
    ElevenLabsSettings,
    DeepgramSettings,
    GroqSettings,
    AdvancedAnalysisSettings,
    ChatInterfaceSettings,
    CustomVocabularySettings,
    WindowSettings,
    AllSettings,
)


# ===========================================================================
# ModelConfig
# ===========================================================================

class TestModelConfig:
    def test_empty_dict_valid(self):
        cfg: ModelConfig = {}
        assert isinstance(cfg, dict)

    def test_has_model_annotation(self):
        assert "model" in ModelConfig.__annotations__

    def test_has_temperature_annotation(self):
        assert "temperature" in ModelConfig.__annotations__

    def test_has_prompt_annotation(self):
        assert "prompt" in ModelConfig.__annotations__

    def test_has_system_message_annotation(self):
        assert "system_message" in ModelConfig.__annotations__

    def test_has_ollama_model(self):
        assert "ollama_model" in ModelConfig.__annotations__

    def test_has_anthropic_model(self):
        assert "anthropic_model" in ModelConfig.__annotations__

    def test_has_gemini_model(self):
        assert "gemini_model" in ModelConfig.__annotations__

    def test_dict_with_values_valid(self):
        cfg: ModelConfig = {"model": "gpt-4o", "temperature": 0.7}
        assert cfg["model"] == "gpt-4o"


# ===========================================================================
# AgentConfig
# ===========================================================================

class TestAgentConfig:
    def test_empty_dict_valid(self):
        cfg: AgentConfig = {}
        assert isinstance(cfg, dict)

    def test_has_enabled_annotation(self):
        assert "enabled" in AgentConfig.__annotations__

    def test_has_provider_annotation(self):
        assert "provider" in AgentConfig.__annotations__

    def test_has_model_annotation(self):
        assert "model" in AgentConfig.__annotations__

    def test_has_temperature_annotation(self):
        assert "temperature" in AgentConfig.__annotations__

    def test_has_max_tokens_annotation(self):
        assert "max_tokens" in AgentConfig.__annotations__

    def test_has_system_prompt_annotation(self):
        assert "system_prompt" in AgentConfig.__annotations__

    def test_has_auto_run_after_soap(self):
        assert "auto_run_after_soap" in AgentConfig.__annotations__


# ===========================================================================
# SOAPNoteConfig
# ===========================================================================

class TestSOAPNoteConfig:
    def test_empty_dict_valid(self):
        cfg: SOAPNoteConfig = {}
        assert isinstance(cfg, dict)

    def test_has_model_annotation(self):
        assert "model" in SOAPNoteConfig.__annotations__

    def test_has_temperature_annotation(self):
        assert "temperature" in SOAPNoteConfig.__annotations__

    def test_has_system_message_annotation(self):
        assert "system_message" in SOAPNoteConfig.__annotations__

    def test_has_icd_code_version_annotation(self):
        assert "icd_code_version" in SOAPNoteConfig.__annotations__

    def test_has_ollama_model(self):
        assert "ollama_model" in SOAPNoteConfig.__annotations__

    def test_has_anthropic_model(self):
        assert "anthropic_model" in SOAPNoteConfig.__annotations__


# ===========================================================================
# TranslationSettings
# ===========================================================================

class TestTranslationSettings:
    def test_empty_dict_valid(self):
        cfg: TranslationSettings = {}
        assert isinstance(cfg, dict)

    def test_has_patient_language(self):
        assert "patient_language" in TranslationSettings.__annotations__

    def test_has_doctor_language(self):
        assert "doctor_language" in TranslationSettings.__annotations__

    def test_has_provider(self):
        assert "provider" in TranslationSettings.__annotations__

    def test_has_llm_refinement_enabled(self):
        assert "llm_refinement_enabled" in TranslationSettings.__annotations__

    def test_has_canned_responses(self):
        assert "canned_responses" in TranslationSettings.__annotations__


# ===========================================================================
# TTSSettings
# ===========================================================================

class TestTTSSettings:
    def test_empty_dict_valid(self):
        cfg: TTSSettings = {}
        assert isinstance(cfg, dict)

    def test_has_provider(self):
        assert "provider" in TTSSettings.__annotations__

    def test_has_voice_id(self):
        assert "voice_id" in TTSSettings.__annotations__

    def test_has_model(self):
        assert "model" in TTSSettings.__annotations__

    def test_has_rate(self):
        assert "rate" in TTSSettings.__annotations__


# ===========================================================================
# ElevenLabsSettings
# ===========================================================================

class TestElevenLabsSettings:
    def test_empty_dict_valid(self):
        cfg: ElevenLabsSettings = {}
        assert isinstance(cfg, dict)

    def test_has_api_key(self):
        assert "api_key" in ElevenLabsSettings.__annotations__

    def test_has_diarize(self):
        assert "diarize" in ElevenLabsSettings.__annotations__

    def test_has_model(self):
        assert "model" in ElevenLabsSettings.__annotations__

    def test_has_timestamps(self):
        assert "timestamps" in ElevenLabsSettings.__annotations__


# ===========================================================================
# DeepgramSettings
# ===========================================================================

class TestDeepgramSettings:
    def test_empty_dict_valid(self):
        cfg: DeepgramSettings = {}
        assert isinstance(cfg, dict)

    def test_has_api_key(self):
        assert "api_key" in DeepgramSettings.__annotations__

    def test_has_model(self):
        assert "model" in DeepgramSettings.__annotations__

    def test_has_smart_format(self):
        assert "smart_format" in DeepgramSettings.__annotations__

    def test_has_diarize(self):
        assert "diarize" in DeepgramSettings.__annotations__

    def test_has_punctuate(self):
        assert "punctuate" in DeepgramSettings.__annotations__

    def test_has_profanity_filter(self):
        assert "profanity_filter" in DeepgramSettings.__annotations__

    def test_has_redact(self):
        assert "redact" in DeepgramSettings.__annotations__

    def test_has_paragraphs(self):
        assert "paragraphs" in DeepgramSettings.__annotations__


# ===========================================================================
# GroqSettings
# ===========================================================================

class TestGroqSettings:
    def test_empty_dict_valid(self):
        cfg: GroqSettings = {}
        assert isinstance(cfg, dict)

    def test_has_api_key(self):
        assert "api_key" in GroqSettings.__annotations__

    def test_has_model(self):
        assert "model" in GroqSettings.__annotations__

    def test_has_language(self):
        assert "language" in GroqSettings.__annotations__


# ===========================================================================
# AdvancedAnalysisSettings
# ===========================================================================

class TestAdvancedAnalysisSettings:
    def test_empty_dict_valid(self):
        cfg: AdvancedAnalysisSettings = {}
        assert isinstance(cfg, dict)

    def test_has_provider(self):
        assert "provider" in AdvancedAnalysisSettings.__annotations__

    def test_has_model(self):
        assert "model" in AdvancedAnalysisSettings.__annotations__

    def test_has_temperature(self):
        assert "temperature" in AdvancedAnalysisSettings.__annotations__

    def test_has_prompt(self):
        assert "prompt" in AdvancedAnalysisSettings.__annotations__

    def test_has_system_message(self):
        assert "system_message" in AdvancedAnalysisSettings.__annotations__


# ===========================================================================
# ChatInterfaceSettings
# ===========================================================================

class TestChatInterfaceSettings:
    def test_empty_dict_valid(self):
        cfg: ChatInterfaceSettings = {}
        assert isinstance(cfg, dict)

    def test_has_enable_tools(self):
        assert "enable_tools" in ChatInterfaceSettings.__annotations__

    def test_has_show_suggestions(self):
        assert "show_suggestions" in ChatInterfaceSettings.__annotations__


# ===========================================================================
# CustomVocabularySettings
# ===========================================================================

class TestCustomVocabularySettings:
    def test_empty_dict_valid(self):
        cfg: CustomVocabularySettings = {}
        assert isinstance(cfg, dict)

    def test_has_enabled(self):
        assert "enabled" in CustomVocabularySettings.__annotations__

    def test_has_words(self):
        assert "words" in CustomVocabularySettings.__annotations__


# ===========================================================================
# WindowSettings
# ===========================================================================

class TestWindowSettings:
    def test_empty_dict_valid(self):
        cfg: WindowSettings = {}
        assert isinstance(cfg, dict)

    def test_has_width(self):
        assert "width" in WindowSettings.__annotations__

    def test_has_height(self):
        assert "height" in WindowSettings.__annotations__

    def test_has_sidebar_collapsed(self):
        assert "sidebar_collapsed" in WindowSettings.__annotations__


# ===========================================================================
# AllSettings
# ===========================================================================

class TestAllSettings:
    def test_empty_dict_valid(self):
        cfg: AllSettings = {}
        assert isinstance(cfg, dict)

    def test_has_ai_provider(self):
        assert "ai_provider" in AllSettings.__annotations__

    def test_has_stt_provider(self):
        assert "stt_provider" in AllSettings.__annotations__

    def test_has_theme(self):
        assert "theme" in AllSettings.__annotations__

    def test_has_soap_note(self):
        assert "soap_note" in AllSettings.__annotations__

    def test_has_refine_text(self):
        assert "refine_text" in AllSettings.__annotations__

    def test_has_improve_text(self):
        assert "improve_text" in AllSettings.__annotations__

    def test_has_referral(self):
        assert "referral" in AllSettings.__annotations__

    def test_has_agent_config(self):
        assert "agent_config" in AllSettings.__annotations__

    def test_has_elevenlabs(self):
        assert "elevenlabs" in AllSettings.__annotations__

    def test_has_deepgram(self):
        assert "deepgram" in AllSettings.__annotations__

    def test_has_groq(self):
        assert "groq" in AllSettings.__annotations__

    def test_has_translation(self):
        assert "translation" in AllSettings.__annotations__

    def test_has_tts(self):
        assert "tts" in AllSettings.__annotations__

    def test_has_window_width(self):
        assert "window_width" in AllSettings.__annotations__

    def test_has_window_height(self):
        assert "window_height" in AllSettings.__annotations__

    def test_has_storage_folder(self):
        assert "storage_folder" in AllSettings.__annotations__

    def test_has_autosave_enabled(self):
        assert "autosave_enabled" in AllSettings.__annotations__

    def test_has_quick_continue_mode(self):
        assert "quick_continue_mode" in AllSettings.__annotations__

    def test_has_sidebar_collapsed(self):
        assert "sidebar_collapsed" in AllSettings.__annotations__

    def test_dict_with_values_valid(self):
        cfg: AllSettings = {"ai_provider": "openai", "theme": "darkly"}
        assert cfg["ai_provider"] == "openai"
