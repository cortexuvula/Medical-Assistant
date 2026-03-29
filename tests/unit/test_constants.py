"""
Tests for src/utils/constants.py

Covers BaseProvider (values, names, is_valid, from_string, __str__),
AIProvider/STTProvider/TTSProvider/ProcessingStatus/QueueStatus/TaskType enums,
legacy string constants, get_ollama_url/get_neo4j_uri (env var priority),
and provider choice list generators.
Pure logic — no external dependencies.
"""

import sys
import os
import pytest
from pathlib import Path
from unittest.mock import patch

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.constants import (
    BaseProvider,
    AIProvider, STTProvider, TTSProvider,
    ProcessingStatus, QueueStatus, TaskType,
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
    STT_DEEPGRAM, STT_GROQ, STT_ELEVENLABS, STT_WHISPER, STT_MODULATE,
    TTS_ELEVENLABS, TTS_OPENAI, TTS_SYSTEM,
    STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED,
    ALL_AI_PROVIDERS, ALL_STT_PROVIDERS, ALL_TTS_PROVIDERS,
    DEFAULT_OLLAMA_URL, DEFAULT_NEO4J_BOLT_URL,
    get_ollama_url, get_neo4j_uri,
    get_ai_provider_choices, get_stt_provider_choices, get_tts_provider_choices,
)


# ===========================================================================
# BaseProvider.values()
# ===========================================================================

class TestBaseProviderValues:
    def test_returns_list(self):
        assert isinstance(AIProvider.values(), list)

    def test_values_are_strings(self):
        for v in AIProvider.values():
            assert isinstance(v, str)

    def test_contains_all_members(self):
        vals = AIProvider.values()
        for member in AIProvider:
            assert member.value in vals

    def test_length_matches_member_count(self):
        assert len(AIProvider.values()) == len(list(AIProvider))


# ===========================================================================
# BaseProvider.names()
# ===========================================================================

class TestBaseProviderNames:
    def test_returns_list(self):
        assert isinstance(AIProvider.names(), list)

    def test_names_match_enum_names(self):
        names = AIProvider.names()
        for member in AIProvider:
            assert member.name in names

    def test_names_are_uppercase(self):
        for name in AIProvider.names():
            assert name == name.upper()


# ===========================================================================
# BaseProvider.is_valid()
# ===========================================================================

class TestBaseProviderIsValid:
    def test_valid_value_returns_true(self):
        assert AIProvider.is_valid("openai") is True

    def test_invalid_value_returns_false(self):
        assert AIProvider.is_valid("unknown_provider") is False

    def test_case_insensitive_upper(self):
        assert AIProvider.is_valid("OPENAI") is True

    def test_case_insensitive_mixed(self):
        assert AIProvider.is_valid("OpenAi") is True

    def test_empty_string_returns_false(self):
        assert AIProvider.is_valid("") is False

    def test_all_members_valid(self):
        for member in AIProvider:
            assert AIProvider.is_valid(member.value) is True


# ===========================================================================
# BaseProvider.from_string()
# ===========================================================================

class TestBaseProviderFromString:
    def test_returns_enum_member_for_valid_value(self):
        result = AIProvider.from_string("openai")
        assert result is AIProvider.OPENAI

    def test_returns_none_for_invalid_value(self):
        result = AIProvider.from_string("nonexistent")
        assert result is None

    def test_case_insensitive_lookup(self):
        assert AIProvider.from_string("ANTHROPIC") is AIProvider.ANTHROPIC
        assert AIProvider.from_string("Anthropic") is AIProvider.ANTHROPIC

    def test_all_members_retrievable(self):
        for member in AIProvider:
            assert AIProvider.from_string(member.value) is member

    def test_stt_provider_lookup(self):
        assert STTProvider.from_string("deepgram") is STTProvider.DEEPGRAM

    def test_tts_provider_lookup(self):
        assert TTSProvider.from_string("elevenlabs") is TTSProvider.ELEVENLABS


# ===========================================================================
# BaseProvider.__str__()
# ===========================================================================

class TestBaseProviderStr:
    def test_str_returns_value(self):
        assert str(AIProvider.OPENAI) == "openai"
        assert str(AIProvider.ANTHROPIC) == "anthropic"

    def test_str_for_stt(self):
        assert str(STTProvider.DEEPGRAM) == "deepgram"

    def test_str_for_processing_status(self):
        assert str(ProcessingStatus.COMPLETED) == "completed"


# ===========================================================================
# AIProvider enum
# ===========================================================================

class TestAIProvider:
    def test_has_six_members(self):
        assert len(list(AIProvider)) == 6

    def test_openai_value(self):
        assert AIProvider.OPENAI.value == "openai"

    def test_anthropic_value(self):
        assert AIProvider.ANTHROPIC.value == "anthropic"

    def test_ollama_value(self):
        assert AIProvider.OLLAMA.value == "ollama"

    def test_gemini_value(self):
        assert AIProvider.GEMINI.value == "gemini"

    def test_groq_value(self):
        assert AIProvider.GROQ.value == "groq"

    def test_cerebras_value(self):
        assert AIProvider.CEREBRAS.value == "cerebras"

    def test_get_display_name_openai(self):
        name = AIProvider.get_display_name(AIProvider.OPENAI)
        assert "OpenAI" in name

    def test_get_display_name_anthropic(self):
        name = AIProvider.get_display_name(AIProvider.ANTHROPIC)
        assert "Claude" in name or "Anthropic" in name

    def test_get_display_name_returns_string(self):
        for member in AIProvider:
            assert isinstance(AIProvider.get_display_name(member), str)


# ===========================================================================
# STTProvider enum
# ===========================================================================

class TestSTTProvider:
    def test_has_expected_members(self):
        expected = {"deepgram", "groq", "elevenlabs", "whisper", "openai", "modulate"}
        assert set(STTProvider.values()) == expected

    def test_deepgram_value(self):
        assert STTProvider.DEEPGRAM.value == "deepgram"

    def test_get_display_name_returns_string(self):
        for member in STTProvider:
            assert isinstance(STTProvider.get_display_name(member), str)

    def test_display_name_for_deepgram(self):
        assert "Deepgram" in STTProvider.get_display_name(STTProvider.DEEPGRAM)


# ===========================================================================
# TTSProvider enum
# ===========================================================================

class TestTTSProvider:
    def test_has_three_members(self):
        assert len(list(TTSProvider)) == 3

    def test_elevenlabs_value(self):
        assert TTSProvider.ELEVENLABS.value == "elevenlabs"

    def test_openai_value(self):
        assert TTSProvider.OPENAI.value == "openai"

    def test_system_value(self):
        assert TTSProvider.SYSTEM.value == "system"

    def test_display_names_are_strings(self):
        for member in TTSProvider:
            assert isinstance(TTSProvider.get_display_name(member), str)


# ===========================================================================
# ProcessingStatus enum
# ===========================================================================

class TestProcessingStatus:
    def test_has_five_members(self):
        assert len(list(ProcessingStatus)) == 5

    def test_pending_value(self):
        assert ProcessingStatus.PENDING.value == "pending"

    def test_completed_value(self):
        assert ProcessingStatus.COMPLETED.value == "completed"

    def test_get_display_icon_returns_string(self):
        for member in ProcessingStatus:
            icon = ProcessingStatus.get_display_icon(member)
            assert isinstance(icon, str)

    def test_completed_icon_not_question_mark(self):
        assert ProcessingStatus.get_display_icon(ProcessingStatus.COMPLETED) != "?"


# ===========================================================================
# QueueStatus and TaskType enums
# ===========================================================================

class TestQueueStatusEnum:
    def test_has_expected_values(self):
        assert QueueStatus.PENDING.value == "pending"
        assert QueueStatus.COMPLETED.value == "completed"
        assert QueueStatus.FAILED.value == "failed"

    def test_is_valid_works(self):
        assert QueueStatus.is_valid("pending") is True
        assert QueueStatus.is_valid("nonexistent") is False


class TestTaskType:
    def test_has_expected_values(self):
        assert TaskType.TRANSCRIPTION.value == "transcription"
        assert TaskType.SOAP_NOTE.value == "soap_note"
        assert TaskType.FULL_PROCESS.value == "full_process"

    def test_from_string_works(self):
        assert TaskType.from_string("transcription") is TaskType.TRANSCRIPTION


# ===========================================================================
# Legacy string constants
# ===========================================================================

class TestLegacyConstants:
    def test_provider_openai(self):
        assert PROVIDER_OPENAI == "openai"

    def test_provider_anthropic(self):
        assert PROVIDER_ANTHROPIC == "anthropic"

    def test_provider_ollama(self):
        assert PROVIDER_OLLAMA == "ollama"

    def test_provider_gemini(self):
        assert PROVIDER_GEMINI == "gemini"

    def test_provider_groq(self):
        assert PROVIDER_GROQ == "groq"

    def test_provider_cerebras(self):
        assert PROVIDER_CEREBRAS == "cerebras"

    def test_stt_constants(self):
        assert STT_DEEPGRAM == "deepgram"
        assert STT_GROQ == "groq"
        assert STT_ELEVENLABS == "elevenlabs"
        assert STT_WHISPER == "whisper"
        assert STT_MODULATE == "modulate"

    def test_tts_constants(self):
        assert TTS_ELEVENLABS == "elevenlabs"
        assert TTS_OPENAI == "openai"
        assert TTS_SYSTEM == "system"

    def test_status_constants(self):
        assert STATUS_PENDING == "pending"
        assert STATUS_PROCESSING == "processing"
        assert STATUS_COMPLETED == "completed"
        assert STATUS_FAILED == "failed"

    def test_all_ai_providers_is_list(self):
        assert isinstance(ALL_AI_PROVIDERS, list)
        assert "openai" in ALL_AI_PROVIDERS

    def test_all_stt_providers_is_list(self):
        assert isinstance(ALL_STT_PROVIDERS, list)
        assert "deepgram" in ALL_STT_PROVIDERS

    def test_all_tts_providers_is_list(self):
        assert isinstance(ALL_TTS_PROVIDERS, list)
        assert "elevenlabs" in ALL_TTS_PROVIDERS


# ===========================================================================
# get_ollama_url
# ===========================================================================

class TestGetOllamaUrl:
    def test_returns_env_var_when_set(self):
        with patch.dict(os.environ, {"OLLAMA_API_URL": "http://custom:9999"}):
            result = get_ollama_url()
        assert result == "http://custom:9999"

    def test_returns_default_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            # Patch settings_manager to return empty string
            with patch("settings.settings_manager.settings_manager") as mock_sm:
                mock_sm.get.return_value = ""
                result = get_ollama_url()
        assert result == DEFAULT_OLLAMA_URL

    def test_default_is_localhost(self):
        assert "localhost" in DEFAULT_OLLAMA_URL or "127.0.0.1" in DEFAULT_OLLAMA_URL


# ===========================================================================
# get_neo4j_uri
# ===========================================================================

class TestGetNeo4jUri:
    def test_returns_env_var_when_set(self):
        with patch.dict(os.environ, {"NEO4J_URI": "bolt://custom:7688"}):
            result = get_neo4j_uri()
        assert result == "bolt://custom:7688"

    def test_returns_default_when_env_not_set(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("settings.settings_manager.settings_manager") as mock_sm:
                mock_sm.get.return_value = ""
                result = get_neo4j_uri()
        assert result == DEFAULT_NEO4J_BOLT_URL

    def test_default_uses_bolt_protocol(self):
        assert DEFAULT_NEO4J_BOLT_URL.startswith("bolt://")


# ===========================================================================
# Provider choice generators
# ===========================================================================

class TestGetAiProviderChoices:
    def test_returns_list(self):
        assert isinstance(get_ai_provider_choices(), list)

    def test_each_element_is_tuple(self):
        for choice in get_ai_provider_choices():
            assert isinstance(choice, tuple)
            assert len(choice) == 2

    def test_length_matches_provider_count(self):
        assert len(get_ai_provider_choices()) == len(list(AIProvider))

    def test_first_element_is_provider_value(self):
        values = {c[0] for c in get_ai_provider_choices()}
        assert "openai" in values


class TestGetSttProviderChoices:
    def test_returns_list(self):
        assert isinstance(get_stt_provider_choices(), list)

    def test_each_element_is_two_tuple(self):
        for choice in get_stt_provider_choices():
            assert len(choice) == 2

    def test_contains_deepgram(self):
        values = {c[0] for c in get_stt_provider_choices()}
        assert "deepgram" in values


class TestGetTtsProviderChoices:
    def test_returns_list(self):
        assert isinstance(get_tts_provider_choices(), list)

    def test_length_matches_tts_count(self):
        assert len(get_tts_provider_choices()) == len(list(TTSProvider))

    def test_contains_elevenlabs(self):
        values = {c[0] for c in get_tts_provider_choices()}
        assert "elevenlabs" in values
