"""
Tests for src/utils/constants.py

Covers:
- BaseProvider enum helpers (values, names, choices, is_valid, from_string, __str__)
- AIProvider, STTProvider, TTSProvider, ProcessingStatus, QueueStatus, TaskType enums
- Legacy string constants
- ALL_* provider lists
- Default URL constants and URL-lookup functions
- get_*_provider_choices() helpers
- ErrorMessages static templates and class methods
- AppConfig numeric constants
- FeatureFlags boolean constants
- TimingConstants numeric constants
"""

import sys
import os
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.constants import (
    BaseProvider, AIProvider, STTProvider, TTSProvider,
    ProcessingStatus, QueueStatus, TaskType,
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
    STT_DEEPGRAM, STT_GROQ, STT_ELEVENLABS,
    TTS_ELEVENLABS, TTS_OPENAI, TTS_SYSTEM,
    STATUS_PENDING, STATUS_PROCESSING, STATUS_COMPLETED, STATUS_FAILED,
    ALL_AI_PROVIDERS, ALL_STT_PROVIDERS, ALL_TTS_PROVIDERS,
    DEFAULT_OLLAMA_URL,
    get_ollama_url, get_ai_provider_choices, get_stt_provider_choices, get_tts_provider_choices,
    ErrorMessages, AppConfig, FeatureFlags, TimingConstants,
)


# =============================================================================
# AIProvider enum
# =============================================================================

class TestAIProvider:
    """Tests for the AIProvider enum."""

    def test_has_openai(self):
        assert AIProvider.OPENAI is not None

    def test_has_anthropic(self):
        assert AIProvider.ANTHROPIC is not None

    def test_has_ollama(self):
        assert AIProvider.OLLAMA is not None

    def test_has_gemini(self):
        assert AIProvider.GEMINI is not None

    def test_has_groq(self):
        assert AIProvider.GROQ is not None

    def test_has_cerebras(self):
        assert AIProvider.CEREBRAS is not None

    def test_exactly_six_members(self):
        assert len(list(AIProvider)) == 6

    def test_openai_value_is_string(self):
        assert isinstance(AIProvider.OPENAI.value, str)

    def test_anthropic_value_is_string(self):
        assert isinstance(AIProvider.ANTHROPIC.value, str)

    def test_ollama_value_string(self):
        assert isinstance(AIProvider.OLLAMA.value, str)

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

    def test_all_members_have_name(self):
        for member in AIProvider:
            assert isinstance(member.name, str)
            assert len(member.name) > 0

    def test_str_returns_value(self):
        assert str(AIProvider.OPENAI) == "openai"
        assert str(AIProvider.ANTHROPIC) == "anthropic"

    def test_get_display_name_openai(self):
        name = AIProvider.get_display_name(AIProvider.OPENAI)
        assert isinstance(name, str)
        assert len(name) > 0

    def test_get_display_name_all_members(self):
        for member in AIProvider:
            name = AIProvider.get_display_name(member)
            assert isinstance(name, str)


# =============================================================================
# BaseProvider helpers
# =============================================================================

class TestBaseProviderValues:
    """Tests for BaseProvider.values() classmethod."""

    def test_returns_list(self):
        assert isinstance(AIProvider.values(), list)

    def test_non_empty(self):
        assert len(AIProvider.values()) > 0

    def test_contains_openai(self):
        assert "openai" in AIProvider.values()

    def test_contains_anthropic(self):
        assert "anthropic" in AIProvider.values()

    def test_all_items_are_strings(self):
        for v in AIProvider.values():
            assert isinstance(v, str)

    def test_length_matches_member_count(self):
        assert len(AIProvider.values()) == len(list(AIProvider))

    def test_stt_values_returns_list(self):
        assert isinstance(STTProvider.values(), list)

    def test_tts_values_returns_list(self):
        assert isinstance(TTSProvider.values(), list)


class TestBaseProviderChoices:
    """Tests for the get_*_provider_choices() helpers (value + display name tuples).

    NOTE: The source module does not define a choices() classmethod on
    BaseProvider; the task description mentions it but it is absent from the
    actual source.  The closest equivalent is get_*_provider_choices(), which
    returns (value, display_name) tuples.  These tests target those helpers.
    """

    def test_ai_choices_is_list(self):
        assert isinstance(get_ai_provider_choices(), list)

    def test_ai_choices_non_empty(self):
        assert len(get_ai_provider_choices()) > 0

    def test_ai_choices_are_tuples(self):
        for item in get_ai_provider_choices():
            assert isinstance(item, tuple)

    def test_ai_choices_are_2_tuples(self):
        for item in get_ai_provider_choices():
            assert len(item) == 2

    def test_ai_choices_first_element_is_string(self):
        for value, _ in get_ai_provider_choices():
            assert isinstance(value, str)

    def test_ai_choices_second_element_is_string(self):
        for _, display in get_ai_provider_choices():
            assert isinstance(display, str)

    def test_stt_choices_are_2_tuples(self):
        for item in get_stt_provider_choices():
            assert len(item) == 2

    def test_tts_choices_are_2_tuples(self):
        for item in get_tts_provider_choices():
            assert len(item) == 2


class TestBaseProviderIsValid:
    """Tests for BaseProvider.is_valid() classmethod."""

    def test_valid_value_returns_true(self):
        assert AIProvider.is_valid("openai") is True

    def test_valid_uppercase_returns_true(self):
        assert AIProvider.is_valid("OPENAI") is True

    def test_invalid_value_returns_false(self):
        assert AIProvider.is_valid("nonexistent") is False

    def test_empty_string_returns_false(self):
        assert AIProvider.is_valid("") is False


class TestBaseProviderFromString:
    """Tests for BaseProvider.from_string() classmethod."""

    def test_returns_correct_member(self):
        assert AIProvider.from_string("openai") is AIProvider.OPENAI

    def test_case_insensitive(self):
        assert AIProvider.from_string("OPENAI") is AIProvider.OPENAI

    def test_unknown_returns_none(self):
        assert AIProvider.from_string("unknown_provider") is None

    def test_empty_string_returns_none(self):
        assert AIProvider.from_string("") is None


class TestBaseProviderNames:
    """Tests for BaseProvider.names() classmethod."""

    def test_returns_list(self):
        assert isinstance(AIProvider.names(), list)

    def test_contains_openai_name(self):
        assert "OPENAI" in AIProvider.names()

    def test_all_items_are_strings(self):
        for n in AIProvider.names():
            assert isinstance(n, str)


# =============================================================================
# STTProvider enum
# =============================================================================

class TestSTTProvider:
    """Tests for the STTProvider enum."""

    def test_has_deepgram(self):
        assert STTProvider.DEEPGRAM is not None

    def test_has_groq(self):
        assert STTProvider.GROQ is not None

    def test_has_elevenlabs(self):
        assert STTProvider.ELEVENLABS is not None

    def test_has_whisper(self):
        assert STTProvider.WHISPER is not None

    def test_has_openai(self):
        assert STTProvider.OPENAI is not None

    def test_has_modulate(self):
        assert STTProvider.MODULATE is not None

    def test_deepgram_value(self):
        assert STTProvider.DEEPGRAM.value == "deepgram"

    def test_groq_value(self):
        assert STTProvider.GROQ.value == "groq"

    def test_elevenlabs_value(self):
        assert STTProvider.ELEVENLABS.value == "elevenlabs"

    def test_all_members_have_string_value(self):
        for member in STTProvider:
            assert isinstance(member.value, str)


# =============================================================================
# TTSProvider enum
# =============================================================================

class TestTTSProvider:
    """Tests for the TTSProvider enum."""

    def test_has_elevenlabs(self):
        assert TTSProvider.ELEVENLABS is not None

    def test_has_openai(self):
        assert TTSProvider.OPENAI is not None

    def test_has_system(self):
        assert TTSProvider.SYSTEM is not None

    def test_elevenlabs_value(self):
        assert TTSProvider.ELEVENLABS.value == "elevenlabs"

    def test_openai_value(self):
        assert TTSProvider.OPENAI.value == "openai"

    def test_system_value(self):
        assert TTSProvider.SYSTEM.value == "system"

    def test_exactly_three_members(self):
        assert len(list(TTSProvider)) == 3


# =============================================================================
# ProcessingStatus enum
# =============================================================================

class TestProcessingStatus:
    """Tests for the ProcessingStatus enum."""

    def test_has_pending(self):
        assert ProcessingStatus.PENDING is not None

    def test_has_processing(self):
        assert ProcessingStatus.PROCESSING is not None

    def test_has_completed(self):
        assert ProcessingStatus.COMPLETED is not None

    def test_has_failed(self):
        assert ProcessingStatus.FAILED is not None

    def test_has_cancelled(self):
        assert ProcessingStatus.CANCELLED is not None

    def test_pending_value(self):
        assert ProcessingStatus.PENDING.value == "pending"

    def test_processing_value(self):
        assert ProcessingStatus.PROCESSING.value == "processing"

    def test_completed_value(self):
        assert ProcessingStatus.COMPLETED.value == "completed"

    def test_failed_value(self):
        assert ProcessingStatus.FAILED.value == "failed"

    def test_all_values_are_strings(self):
        for member in ProcessingStatus:
            assert isinstance(member.value, str)


# =============================================================================
# QueueStatus enum
# =============================================================================

class TestQueueStatus:
    """Tests for the QueueStatus enum."""

    def test_has_pending(self):
        assert QueueStatus.PENDING is not None

    def test_has_in_progress(self):
        assert QueueStatus.IN_PROGRESS is not None

    def test_has_completed(self):
        assert QueueStatus.COMPLETED is not None

    def test_has_failed(self):
        assert QueueStatus.FAILED is not None

    def test_has_retrying(self):
        assert QueueStatus.RETRYING is not None

    def test_in_progress_value(self):
        assert QueueStatus.IN_PROGRESS.value == "in_progress"

    def test_retrying_value(self):
        assert QueueStatus.RETRYING.value == "retrying"


# =============================================================================
# TaskType enum
# =============================================================================

class TestTaskType:
    """Tests for the TaskType enum."""

    def test_has_transcription(self):
        assert TaskType.TRANSCRIPTION is not None

    def test_has_soap_note(self):
        assert TaskType.SOAP_NOTE is not None

    def test_has_referral(self):
        assert TaskType.REFERRAL is not None

    def test_has_letter(self):
        assert TaskType.LETTER is not None

    def test_has_full_process(self):
        assert TaskType.FULL_PROCESS is not None

    def test_transcription_value(self):
        assert TaskType.TRANSCRIPTION.value == "transcription"

    def test_soap_note_value(self):
        assert TaskType.SOAP_NOTE.value == "soap_note"


# =============================================================================
# Legacy string constants
# =============================================================================

class TestLegacyAIProviderConstants:
    """Tests for the module-level AI provider string constants."""

    def test_provider_openai_value(self):
        assert PROVIDER_OPENAI == "openai"

    def test_provider_anthropic_value(self):
        assert PROVIDER_ANTHROPIC == "anthropic"

    def test_provider_ollama_value(self):
        assert PROVIDER_OLLAMA == "ollama"

    def test_provider_gemini_value(self):
        assert PROVIDER_GEMINI == "gemini"

    def test_provider_groq_value(self):
        assert PROVIDER_GROQ == "groq"

    def test_provider_cerebras_value(self):
        assert PROVIDER_CEREBRAS == "cerebras"

    def test_constants_are_strings(self):
        for const in (
            PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
            PROVIDER_GEMINI, PROVIDER_GROQ, PROVIDER_CEREBRAS,
        ):
            assert isinstance(const, str)

    def test_provider_openai_matches_enum(self):
        assert PROVIDER_OPENAI == AIProvider.OPENAI.value

    def test_provider_anthropic_matches_enum(self):
        assert PROVIDER_ANTHROPIC == AIProvider.ANTHROPIC.value


class TestLegacySTTConstants:
    """Tests for the module-level STT string constants."""

    def test_stt_deepgram_value(self):
        assert STT_DEEPGRAM == "deepgram"

    def test_stt_groq_value(self):
        assert STT_GROQ == "groq"

    def test_stt_elevenlabs_value(self):
        assert STT_ELEVENLABS == "elevenlabs"

    def test_stt_deepgram_matches_enum(self):
        assert STT_DEEPGRAM == STTProvider.DEEPGRAM.value

    def test_stt_constants_are_strings(self):
        for const in (STT_DEEPGRAM, STT_GROQ, STT_ELEVENLABS):
            assert isinstance(const, str)


class TestLegacyTTSConstants:
    """Tests for the module-level TTS string constants."""

    def test_tts_elevenlabs_value(self):
        assert TTS_ELEVENLABS == "elevenlabs"

    def test_tts_openai_value(self):
        assert TTS_OPENAI == "openai"

    def test_tts_system_value(self):
        assert TTS_SYSTEM == "system"

    def test_tts_constants_match_enum(self):
        assert TTS_ELEVENLABS == TTSProvider.ELEVENLABS.value
        assert TTS_OPENAI == TTSProvider.OPENAI.value
        assert TTS_SYSTEM == TTSProvider.SYSTEM.value


class TestLegacyStatusConstants:
    """Tests for the module-level STATUS_* string constants."""

    def test_status_pending_value(self):
        assert STATUS_PENDING == "pending"

    def test_status_processing_value(self):
        assert STATUS_PROCESSING == "processing"

    def test_status_completed_value(self):
        assert STATUS_COMPLETED == "completed"

    def test_status_failed_value(self):
        assert STATUS_FAILED == "failed"

    def test_status_constants_match_enum(self):
        assert STATUS_PENDING == ProcessingStatus.PENDING.value
        assert STATUS_PROCESSING == ProcessingStatus.PROCESSING.value
        assert STATUS_COMPLETED == ProcessingStatus.COMPLETED.value
        assert STATUS_FAILED == ProcessingStatus.FAILED.value


# =============================================================================
# ALL_* provider lists
# =============================================================================

class TestAllProviderLists:
    """Tests for the ALL_AI_PROVIDERS, ALL_STT_PROVIDERS, ALL_TTS_PROVIDERS lists."""

    def test_all_ai_providers_is_list(self):
        assert isinstance(ALL_AI_PROVIDERS, list)

    def test_all_ai_providers_non_empty(self):
        assert len(ALL_AI_PROVIDERS) > 0

    def test_all_ai_providers_contains_openai(self):
        assert PROVIDER_OPENAI in ALL_AI_PROVIDERS

    def test_all_ai_providers_contains_anthropic(self):
        assert PROVIDER_ANTHROPIC in ALL_AI_PROVIDERS

    def test_all_ai_providers_all_strings(self):
        for v in ALL_AI_PROVIDERS:
            assert isinstance(v, str)

    def test_all_ai_providers_length(self):
        assert len(ALL_AI_PROVIDERS) == len(list(AIProvider))

    def test_all_stt_providers_is_list(self):
        assert isinstance(ALL_STT_PROVIDERS, list)

    def test_all_stt_providers_non_empty(self):
        assert len(ALL_STT_PROVIDERS) > 0

    def test_all_stt_providers_contains_deepgram(self):
        assert STT_DEEPGRAM in ALL_STT_PROVIDERS

    def test_all_tts_providers_is_list(self):
        assert isinstance(ALL_TTS_PROVIDERS, list)

    def test_all_tts_providers_non_empty(self):
        assert len(ALL_TTS_PROVIDERS) > 0

    def test_all_tts_providers_contains_elevenlabs(self):
        assert TTS_ELEVENLABS in ALL_TTS_PROVIDERS


# =============================================================================
# Default URL constants
# =============================================================================

class TestDefaultURLConstants:
    """Tests for DEFAULT_OLLAMA_URL."""

    def test_default_ollama_url_is_string(self):
        assert isinstance(DEFAULT_OLLAMA_URL, str)

    def test_default_ollama_url_starts_with_http(self):
        assert DEFAULT_OLLAMA_URL.startswith("http://")

    def test_default_ollama_url_contains_localhost(self):
        assert "localhost" in DEFAULT_OLLAMA_URL

    def test_default_ollama_url_contains_port(self):
        assert "11434" in DEFAULT_OLLAMA_URL


# =============================================================================
# get_ollama_url()
# =============================================================================

class TestGetOllamaUrl:
    """Tests for get_ollama_url()."""

    def test_returns_string(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_API_URL", raising=False)
        result = get_ollama_url()
        assert isinstance(result, str)

    def test_returns_http_scheme(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_API_URL", raising=False)
        result = get_ollama_url()
        assert result.startswith("http")

    def test_honors_env_var(self, monkeypatch):
        custom_url = "http://myhost:9999"
        monkeypatch.setenv("OLLAMA_API_URL", custom_url)
        assert get_ollama_url() == custom_url

    def test_env_var_overrides_default(self, monkeypatch):
        monkeypatch.setenv("OLLAMA_API_URL", "http://override:1234")
        result = get_ollama_url()
        assert result == "http://override:1234"
        assert result != DEFAULT_OLLAMA_URL

    def test_default_without_env_matches_constant(self, monkeypatch):
        monkeypatch.delenv("OLLAMA_API_URL", raising=False)
        import types
        fake_settings = types.SimpleNamespace(get=lambda key, default="": "")
        fake_module = types.ModuleType("settings.settings_manager")
        fake_module.settings_manager = fake_settings
        monkeypatch.setitem(sys.modules, "settings.settings_manager", fake_module)
        result = get_ollama_url()
        assert result == DEFAULT_OLLAMA_URL

    def test_env_var_value_is_returned_verbatim(self, monkeypatch):
        url = "http://192.168.1.100:11434"
        monkeypatch.setenv("OLLAMA_API_URL", url)
        assert get_ollama_url() == url


# =============================================================================
# get_*_provider_choices()
# =============================================================================

class TestGetProviderChoices:
    """Tests for the get_*_provider_choices() helper functions."""

    def test_ai_choices_returns_list(self):
        result = get_ai_provider_choices()
        assert isinstance(result, list)

    def test_ai_choices_non_empty(self):
        assert len(get_ai_provider_choices()) > 0

    def test_ai_choices_are_2_tuples(self):
        for item in get_ai_provider_choices():
            assert isinstance(item, tuple)
            assert len(item) == 2

    def test_ai_choices_first_element_is_valid_provider(self):
        valid_values = AIProvider.values()
        for value, _ in get_ai_provider_choices():
            assert value in valid_values

    def test_ai_choices_count_matches_enum(self):
        assert len(get_ai_provider_choices()) == len(list(AIProvider))

    def test_stt_choices_returns_list(self):
        assert isinstance(get_stt_provider_choices(), list)

    def test_stt_choices_non_empty(self):
        assert len(get_stt_provider_choices()) > 0

    def test_stt_choices_are_2_tuples(self):
        for item in get_stt_provider_choices():
            assert len(item) == 2

    def test_tts_choices_returns_list(self):
        assert isinstance(get_tts_provider_choices(), list)

    def test_tts_choices_non_empty(self):
        assert len(get_tts_provider_choices()) > 0

    def test_tts_choices_are_2_tuples(self):
        for item in get_tts_provider_choices():
            assert len(item) == 2

    def test_stt_choices_count_matches_enum(self):
        assert len(get_stt_provider_choices()) == len(list(STTProvider))

    def test_tts_choices_count_matches_enum(self):
        assert len(get_tts_provider_choices()) == len(list(TTSProvider))


# =============================================================================
# ErrorMessages
# =============================================================================

class TestErrorMessages:
    """Tests for the ErrorMessages class."""

    def test_api_key_missing_is_string(self):
        assert isinstance(ErrorMessages.API_KEY_MISSING, str)

    def test_api_key_missing_contains_placeholder(self):
        assert "{provider}" in ErrorMessages.API_KEY_MISSING

    def test_api_key_invalid_is_string(self):
        assert isinstance(ErrorMessages.API_KEY_INVALID, str)

    def test_db_connection_failed_is_string(self):
        assert isinstance(ErrorMessages.DB_CONNECTION_FAILED, str)

    def test_file_not_found_is_string(self):
        assert isinstance(ErrorMessages.FILE_NOT_FOUND, str)

    def test_audio_device_not_found_is_string(self):
        assert isinstance(ErrorMessages.AUDIO_DEVICE_NOT_FOUND, str)

    def test_processing_failed_is_string(self):
        assert isinstance(ErrorMessages.PROCESSING_FAILED, str)

    def test_validation_required_is_string(self):
        assert isinstance(ErrorMessages.VALIDATION_REQUIRED, str)

    def test_operation_failed_is_string(self):
        assert isinstance(ErrorMessages.OPERATION_FAILED, str)

    def test_format_api_error_returns_string(self):
        result = ErrorMessages.format_api_error("OpenAI", "rate limit")
        assert isinstance(result, str)

    def test_format_api_error_contains_provider(self):
        result = ErrorMessages.format_api_error("OpenAI", "some error")
        assert "OpenAI" in result

    def test_format_api_error_contains_error_detail(self):
        result = ErrorMessages.format_api_error("Groq", "timeout")
        assert "timeout" in result

    def test_format_db_error_returns_string(self):
        result = ErrorMessages.format_db_error("insert", "constraint violation")
        assert isinstance(result, str)

    def test_format_db_error_contains_operation(self):
        result = ErrorMessages.format_db_error("delete", "FK violation")
        assert "delete" in result

    def test_format_file_error_returns_string(self):
        result = ErrorMessages.format_file_error("read", "/tmp/file.txt", "permission denied")
        assert isinstance(result, str)

    def test_format_file_error_contains_path(self):
        result = ErrorMessages.format_file_error("read", "/tmp/file.txt", "err")
        assert "/tmp/file.txt" in result

    def test_template_format_substitution(self):
        msg = ErrorMessages.API_KEY_MISSING.format(provider="Groq")
        assert "Groq" in msg

    def test_unexpected_error_is_string(self):
        assert isinstance(ErrorMessages.UNEXPECTED_ERROR, str)

    def test_api_rate_limited_contains_provider_placeholder(self):
        assert "{provider}" in ErrorMessages.API_RATE_LIMITED

    def test_processing_timeout_contains_timeout_placeholder(self):
        assert "{timeout}" in ErrorMessages.PROCESSING_TIMEOUT


# =============================================================================
# AppConfig
# =============================================================================

class TestAppConfig:
    """Tests for the AppConfig class constants."""

    def test_default_api_timeout_is_int(self):
        assert isinstance(AppConfig.DEFAULT_API_TIMEOUT, int)

    def test_default_api_timeout_positive(self):
        assert AppConfig.DEFAULT_API_TIMEOUT > 0

    def test_default_transcription_timeout_positive(self):
        assert AppConfig.DEFAULT_TRANSCRIPTION_TIMEOUT > 0

    def test_default_ai_generation_timeout_positive(self):
        assert AppConfig.DEFAULT_AI_GENERATION_TIMEOUT > 0

    def test_default_connection_timeout_positive(self):
        assert AppConfig.DEFAULT_CONNECTION_TIMEOUT > 0

    def test_default_max_retries_is_int(self):
        assert isinstance(AppConfig.DEFAULT_MAX_RETRIES, int)

    def test_default_max_retries_positive(self):
        assert AppConfig.DEFAULT_MAX_RETRIES > 0

    def test_default_retry_delay_is_numeric(self):
        assert isinstance(AppConfig.DEFAULT_RETRY_DELAY, (int, float))

    def test_default_retry_backoff_is_numeric(self):
        assert isinstance(AppConfig.DEFAULT_RETRY_BACKOFF, (int, float))

    def test_cache_ttl_seconds_positive(self):
        assert AppConfig.CACHE_TTL_SECONDS > 0

    def test_cache_max_size_positive(self):
        assert AppConfig.CACHE_MAX_SIZE > 0

    def test_autosave_interval_positive(self):
        assert AppConfig.AUTOSAVE_INTERVAL_SECONDS > 0

    def test_audio_sample_rate_positive(self):
        assert AppConfig.AUDIO_SAMPLE_RATE > 0

    def test_audio_channels_positive(self):
        assert AppConfig.AUDIO_CHANNELS > 0

    def test_audio_chunk_size_positive(self):
        assert AppConfig.AUDIO_CHUNK_SIZE > 0

    def test_queue_max_concurrent_tasks_positive(self):
        assert AppConfig.QUEUE_MAX_CONCURRENT_TASKS > 0

    def test_file_buffer_size_positive(self):
        assert AppConfig.FILE_BUFFER_SIZE > 0

    def test_db_connection_pool_size_positive(self):
        assert AppConfig.DB_CONNECTION_POOL_SIZE > 0

    def test_db_connection_timeout_positive(self):
        assert AppConfig.DB_CONNECTION_TIMEOUT > 0

    def test_ui_status_message_duration_ms_positive(self):
        assert AppConfig.UI_STATUS_MESSAGE_DURATION_MS > 0

    def test_transcription_timeout_gt_api_timeout(self):
        assert AppConfig.DEFAULT_TRANSCRIPTION_TIMEOUT >= AppConfig.DEFAULT_API_TIMEOUT


# =============================================================================
# FeatureFlags
# =============================================================================

class TestFeatureFlags:
    """Tests for the FeatureFlags class constants."""

    def test_enable_diarization_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_DIARIZATION, bool)

    def test_enable_periodic_analysis_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_PERIODIC_ANALYSIS, bool)

    def test_enable_autosave_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_AUTOSAVE, bool)

    def test_enable_quick_continue_mode_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_QUICK_CONTINUE_MODE, bool)

    def test_enable_batch_processing_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_BATCH_PROCESSING, bool)

    def test_enable_rag_tab_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_RAG_TAB, bool)

    def test_enable_chat_tab_is_bool(self):
        assert isinstance(FeatureFlags.ENABLE_CHAT_TAB, bool)


# =============================================================================
# TimingConstants
# =============================================================================

class TestTimingConstants:
    """Tests for the TimingConstants class constants."""

    def test_periodic_analysis_interval_is_numeric(self):
        assert isinstance(TimingConstants.PERIODIC_ANALYSIS_INTERVAL, (int, float))

    def test_periodic_analysis_interval_positive(self):
        assert TimingConstants.PERIODIC_ANALYSIS_INTERVAL > 0

    def test_periodic_analysis_min_elapsed_positive(self):
        assert TimingConstants.PERIODIC_ANALYSIS_MIN_ELAPSED > 0

    def test_autosave_interval_positive(self):
        assert TimingConstants.AUTOSAVE_INTERVAL > 0

    def test_settings_cache_ttl_positive(self):
        assert TimingConstants.SETTINGS_CACHE_TTL > 0

    def test_agent_cache_ttl_positive(self):
        assert TimingConstants.AGENT_CACHE_TTL > 0

    def test_model_cache_ttl_positive(self):
        assert TimingConstants.MODEL_CACHE_TTL > 0

    def test_api_timeout_default_positive(self):
        assert TimingConstants.API_TIMEOUT_DEFAULT > 0

    def test_api_timeout_long_positive(self):
        assert TimingConstants.API_TIMEOUT_LONG > 0

    def test_stream_timeout_positive(self):
        assert TimingConstants.STREAM_TIMEOUT > 0

    def test_stt_failover_skip_duration_positive(self):
        assert TimingConstants.STT_FAILOVER_SKIP_DURATION > 0

    def test_ui_update_interval_ms_positive(self):
        assert TimingConstants.UI_UPDATE_INTERVAL_MS > 0

    def test_debounce_delay_ms_positive(self):
        assert TimingConstants.DEBOUNCE_DELAY_MS > 0

    def test_db_retry_initial_delay_positive(self):
        assert TimingConstants.DB_RETRY_INITIAL_DELAY > 0

    def test_db_retry_max_delay_positive(self):
        assert TimingConstants.DB_RETRY_MAX_DELAY > 0

    def test_max_debug_files_positive(self):
        assert TimingConstants.MAX_DEBUG_FILES > 0

    def test_long_timeout_exceeds_default(self):
        assert TimingConstants.API_TIMEOUT_LONG >= TimingConstants.API_TIMEOUT_DEFAULT

    def test_db_retry_max_delay_exceeds_initial(self):
        assert TimingConstants.DB_RETRY_MAX_DELAY > TimingConstants.DB_RETRY_INITIAL_DELAY

    def test_model_cache_ttl_exceeds_agent_cache_ttl(self):
        assert TimingConstants.MODEL_CACHE_TTL >= TimingConstants.AGENT_CACHE_TTL
