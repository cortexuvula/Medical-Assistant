"""
Tests for enums and dataclasses in src/type_definitions/configs.py

Covers Priority, RetryStrategy, DocumentType enum members and str behavior;
and all 8 dataclasses: defaults, to_dict(), from_dict() round-trip,
and from_dict() with string-coerced enum values.
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from type_definitions.configs import (
    Priority, RetryStrategy, DocumentType,
    BatchProcessingOptions, AgentExecutionOptions,
    TranscriptionOptions, DocumentGenerationOptions,
    TTSOptions, TranslationOptions,
    AudioRecordingOptions, ProcessingQueueOptions,
)


# ===========================================================================
# Priority enum
# ===========================================================================

class TestPriority:
    def test_has_low(self):
        assert hasattr(Priority, "LOW")

    def test_has_normal(self):
        assert hasattr(Priority, "NORMAL")

    def test_has_high(self):
        assert hasattr(Priority, "HIGH")

    def test_three_members(self):
        assert len(list(Priority)) == 3

    def test_is_str(self):
        for member in Priority:
            assert isinstance(member.value, str)

    def test_low_str(self):
        assert str(Priority.LOW) == Priority.LOW.value or Priority.LOW == "low"

    def test_normal_str(self):
        assert Priority.NORMAL == "normal" or Priority.NORMAL.value.lower() == "normal"

    def test_high_str(self):
        assert Priority.HIGH == "high" or Priority.HIGH.value.lower() == "high"

    def test_str_enum_usable_as_string(self):
        # str,Enum means the value can be compared to its string value
        assert Priority.LOW == Priority.LOW.value


# ===========================================================================
# RetryStrategy enum
# ===========================================================================

class TestRetryStrategy:
    def test_has_exponential(self):
        assert hasattr(RetryStrategy, "EXPONENTIAL")

    def test_has_linear(self):
        assert hasattr(RetryStrategy, "LINEAR")

    def test_has_fixed(self):
        assert hasattr(RetryStrategy, "FIXED")

    def test_has_none(self):
        assert hasattr(RetryStrategy, "NONE")

    def test_four_members(self):
        assert len(list(RetryStrategy)) == 4

    def test_all_values_are_strings(self):
        for member in RetryStrategy:
            assert isinstance(member.value, str)

    def test_exponential_value(self):
        assert RetryStrategy.EXPONENTIAL == RetryStrategy.EXPONENTIAL.value

    def test_none_value(self):
        assert RetryStrategy.NONE == RetryStrategy.NONE.value


# ===========================================================================
# DocumentType enum
# ===========================================================================

class TestDocumentType:
    def test_has_soap(self):
        assert hasattr(DocumentType, "SOAP")

    def test_has_referral(self):
        assert hasattr(DocumentType, "REFERRAL")

    def test_has_letter(self):
        assert hasattr(DocumentType, "LETTER")

    def test_three_members(self):
        assert len(list(DocumentType)) == 3

    def test_all_values_are_strings(self):
        for member in DocumentType:
            assert isinstance(member.value, str)

    def test_soap_value(self):
        assert DocumentType.SOAP == DocumentType.SOAP.value

    def test_referral_value(self):
        assert DocumentType.REFERRAL == DocumentType.REFERRAL.value

    def test_letter_value(self):
        assert DocumentType.LETTER == DocumentType.LETTER.value


# ===========================================================================
# BatchProcessingOptions
# ===========================================================================

class TestBatchProcessingOptions:
    def test_default_generate_soap_true(self):
        assert BatchProcessingOptions().generate_soap is True

    def test_default_generate_referral_false(self):
        assert BatchProcessingOptions().generate_referral is False

    def test_default_generate_letter_false(self):
        assert BatchProcessingOptions().generate_letter is False

    def test_default_skip_existing_true(self):
        assert BatchProcessingOptions().skip_existing is True

    def test_default_continue_on_error_true(self):
        assert BatchProcessingOptions().continue_on_error is True

    def test_default_priority_normal(self):
        assert BatchProcessingOptions().priority == Priority.NORMAL

    def test_default_max_concurrent_3(self):
        assert BatchProcessingOptions().max_concurrent == 3

    def test_to_dict_returns_dict(self):
        assert isinstance(BatchProcessingOptions().to_dict(), dict)

    def test_to_dict_contains_generate_soap(self):
        d = BatchProcessingOptions().to_dict()
        assert "generate_soap" in d

    def test_to_dict_priority_is_string(self):
        d = BatchProcessingOptions().to_dict()
        assert isinstance(d["priority"], str)

    def test_from_dict_roundtrip(self):
        opts = BatchProcessingOptions(generate_referral=True, max_concurrent=5)
        d = opts.to_dict()
        restored = BatchProcessingOptions.from_dict(d)
        assert restored.generate_referral is True
        assert restored.max_concurrent == 5

    def test_from_dict_priority_from_string(self):
        d = BatchProcessingOptions().to_dict()
        d["priority"] = Priority.HIGH.value
        restored = BatchProcessingOptions.from_dict(d)
        assert restored.priority == Priority.HIGH

    def test_from_dict_empty_uses_defaults(self):
        restored = BatchProcessingOptions.from_dict({})
        assert restored.generate_soap is True

    def test_custom_values_preserved(self):
        opts = BatchProcessingOptions(generate_soap=False, skip_existing=False)
        assert opts.generate_soap is False
        assert opts.skip_existing is False


# ===========================================================================
# AgentExecutionOptions
# ===========================================================================

class TestAgentExecutionOptions:
    def test_default_timeout_60(self):
        assert AgentExecutionOptions().timeout == 60

    def test_default_max_retries_3(self):
        assert AgentExecutionOptions().max_retries == 3

    def test_default_retry_strategy_exponential(self):
        assert AgentExecutionOptions().retry_strategy == RetryStrategy.EXPONENTIAL

    def test_default_retry_delay_1(self):
        assert AgentExecutionOptions().retry_delay == 1.0

    def test_default_temperature_07(self):
        assert AgentExecutionOptions().temperature == pytest.approx(0.7)

    def test_default_max_tokens_4000(self):
        assert AgentExecutionOptions().max_tokens == 4000

    def test_to_dict_returns_dict(self):
        assert isinstance(AgentExecutionOptions().to_dict(), dict)

    def test_to_dict_retry_strategy_is_string(self):
        d = AgentExecutionOptions().to_dict()
        assert isinstance(d["retry_strategy"], str)

    def test_from_dict_roundtrip(self):
        opts = AgentExecutionOptions(timeout=120, max_tokens=8000)
        d = opts.to_dict()
        restored = AgentExecutionOptions.from_dict(d)
        assert restored.timeout == 120
        assert restored.max_tokens == 8000

    def test_from_dict_retry_strategy_from_string(self):
        d = AgentExecutionOptions().to_dict()
        d["retry_strategy"] = RetryStrategy.LINEAR.value
        restored = AgentExecutionOptions.from_dict(d)
        assert restored.retry_strategy == RetryStrategy.LINEAR

    def test_from_dict_empty_uses_defaults(self):
        restored = AgentExecutionOptions.from_dict({})
        assert restored.timeout == 60


# ===========================================================================
# TranscriptionOptions
# ===========================================================================

class TestTranscriptionOptions:
    def test_default_language_en_us(self):
        assert TranscriptionOptions().language == "en-US"

    def test_default_diarize_false(self):
        assert TranscriptionOptions().diarize is False

    def test_default_num_speakers_none(self):
        assert TranscriptionOptions().num_speakers is None

    def test_default_model_none(self):
        assert TranscriptionOptions().model is None

    def test_default_smart_formatting_true(self):
        assert TranscriptionOptions().smart_formatting is True

    def test_default_profanity_filter_false(self):
        assert TranscriptionOptions().profanity_filter is False

    def test_to_dict_returns_dict(self):
        assert isinstance(TranscriptionOptions().to_dict(), dict)

    def test_to_dict_none_values_present(self):
        d = TranscriptionOptions().to_dict()
        assert "num_speakers" in d
        assert d["num_speakers"] is None

    def test_from_dict_roundtrip(self):
        opts = TranscriptionOptions(language="fr-FR", diarize=True, num_speakers=2)
        d = opts.to_dict()
        restored = TranscriptionOptions.from_dict(d)
        assert restored.language == "fr-FR"
        assert restored.diarize is True
        assert restored.num_speakers == 2

    def test_from_dict_empty_uses_defaults(self):
        restored = TranscriptionOptions.from_dict({})
        assert restored.language == "en-US"

    def test_custom_model_set(self):
        opts = TranscriptionOptions(model="whisper-large")
        assert opts.model == "whisper-large"


# ===========================================================================
# DocumentGenerationOptions
# ===========================================================================

class TestDocumentGenerationOptions:
    def test_default_include_context_true(self):
        assert DocumentGenerationOptions().include_context is True

    def test_default_max_tokens_4000(self):
        assert DocumentGenerationOptions().max_tokens == 4000

    def test_default_temperature_07(self):
        assert DocumentGenerationOptions().temperature == pytest.approx(0.7)

    def test_default_provider_none(self):
        assert DocumentGenerationOptions().provider is None

    def test_default_model_none(self):
        assert DocumentGenerationOptions().model is None

    def test_default_system_prompt_none(self):
        assert DocumentGenerationOptions().system_prompt is None

    def test_to_dict_returns_dict(self):
        assert isinstance(DocumentGenerationOptions().to_dict(), dict)

    def test_from_dict_roundtrip(self):
        opts = DocumentGenerationOptions(include_context=False, provider="openai", model="gpt-4")
        d = opts.to_dict()
        restored = DocumentGenerationOptions.from_dict(d)
        assert restored.include_context is False
        assert restored.provider == "openai"
        assert restored.model == "gpt-4"

    def test_from_dict_empty_uses_defaults(self):
        restored = DocumentGenerationOptions.from_dict({})
        assert restored.include_context is True

    def test_system_prompt_can_be_set(self):
        opts = DocumentGenerationOptions(system_prompt="You are a helpful assistant.")
        assert opts.system_prompt == "You are a helpful assistant."


# ===========================================================================
# TTSOptions
# ===========================================================================

class TestTTSOptions:
    def test_default_provider_pyttsx3(self):
        assert TTSOptions().provider == "pyttsx3"

    def test_default_voice_none(self):
        assert TTSOptions().voice is None

    def test_default_language_en(self):
        assert TTSOptions().language == "en"

    def test_default_rate_1(self):
        assert TTSOptions().rate == pytest.approx(1.0)

    def test_default_volume_1(self):
        assert TTSOptions().volume == pytest.approx(1.0)

    def test_default_model_none(self):
        assert TTSOptions().model is None

    def test_to_dict_returns_dict(self):
        assert isinstance(TTSOptions().to_dict(), dict)

    def test_from_dict_roundtrip(self):
        opts = TTSOptions(provider="elevenlabs", language="fr", rate=1.5)
        d = opts.to_dict()
        restored = TTSOptions.from_dict(d)
        assert restored.provider == "elevenlabs"
        assert restored.language == "fr"
        assert restored.rate == pytest.approx(1.5)

    def test_from_dict_empty_uses_defaults(self):
        restored = TTSOptions.from_dict({})
        assert restored.provider == "pyttsx3"

    def test_voice_can_be_set(self):
        opts = TTSOptions(voice="en-US-Wavenet-A")
        assert opts.voice == "en-US-Wavenet-A"


# ===========================================================================
# TranslationOptions
# ===========================================================================

class TestTranslationOptions:
    def test_default_provider_deep_translator(self):
        assert TranslationOptions().provider == "deep_translator"

    def test_default_sub_provider_google(self):
        assert TranslationOptions().sub_provider == "google"

    def test_default_source_language_none(self):
        assert TranslationOptions().source_language is None

    def test_default_target_language_en(self):
        assert TranslationOptions().target_language == "en"

    def test_default_auto_detect_true(self):
        assert TranslationOptions().auto_detect is True

    def test_to_dict_returns_dict(self):
        assert isinstance(TranslationOptions().to_dict(), dict)

    def test_from_dict_roundtrip(self):
        opts = TranslationOptions(target_language="fr", auto_detect=False, source_language="en")
        d = opts.to_dict()
        restored = TranslationOptions.from_dict(d)
        assert restored.target_language == "fr"
        assert restored.auto_detect is False
        assert restored.source_language == "en"

    def test_from_dict_empty_uses_defaults(self):
        restored = TranslationOptions.from_dict({})
        assert restored.target_language == "en"

    def test_source_language_can_be_set(self):
        opts = TranslationOptions(source_language="de")
        assert opts.source_language == "de"


# ===========================================================================
# AudioRecordingOptions
# ===========================================================================

class TestAudioRecordingOptions:
    def test_default_sample_rate_16000(self):
        assert AudioRecordingOptions().sample_rate == 16000

    def test_default_channels_1(self):
        assert AudioRecordingOptions().channels == 1

    def test_default_chunk_size_1024(self):
        assert AudioRecordingOptions().chunk_size == 1024

    def test_default_device_index_none(self):
        assert AudioRecordingOptions().device_index is None

    def test_default_silence_threshold_minus40(self):
        assert AudioRecordingOptions().silence_threshold == pytest.approx(-40.0)

    def test_default_silence_duration_2(self):
        assert AudioRecordingOptions().silence_duration == pytest.approx(2.0)

    def test_to_dict_returns_dict(self):
        assert isinstance(AudioRecordingOptions().to_dict(), dict)

    def test_from_dict_roundtrip(self):
        opts = AudioRecordingOptions(sample_rate=44100, channels=2, device_index=1)
        d = opts.to_dict()
        restored = AudioRecordingOptions.from_dict(d)
        assert restored.sample_rate == 44100
        assert restored.channels == 2
        assert restored.device_index == 1

    def test_from_dict_empty_uses_defaults(self):
        restored = AudioRecordingOptions.from_dict({})
        assert restored.sample_rate == 16000

    def test_silence_threshold_customizable(self):
        opts = AudioRecordingOptions(silence_threshold=-50.0)
        assert opts.silence_threshold == pytest.approx(-50.0)


# ===========================================================================
# ProcessingQueueOptions
# ===========================================================================

class TestProcessingQueueOptions:
    def test_default_max_workers_3(self):
        assert ProcessingQueueOptions().max_workers == 3

    def test_default_retry_failed_true(self):
        assert ProcessingQueueOptions().retry_failed is True

    def test_default_max_retries_2(self):
        assert ProcessingQueueOptions().max_retries == 2

    def test_default_deduplication_true(self):
        assert ProcessingQueueOptions().deduplication is True

    def test_default_batch_size_10(self):
        assert ProcessingQueueOptions().batch_size == 10

    def test_to_dict_returns_dict(self):
        assert isinstance(ProcessingQueueOptions().to_dict(), dict)

    def test_to_dict_contains_all_keys(self):
        d = ProcessingQueueOptions().to_dict()
        for key in ["max_workers", "retry_failed", "max_retries", "deduplication", "batch_size"]:
            assert key in d

    def test_from_dict_roundtrip(self):
        opts = ProcessingQueueOptions(max_workers=8, retry_failed=False, batch_size=20)
        d = opts.to_dict()
        restored = ProcessingQueueOptions.from_dict(d)
        assert restored.max_workers == 8
        assert restored.retry_failed is False
        assert restored.batch_size == 20

    def test_from_dict_empty_uses_defaults(self):
        restored = ProcessingQueueOptions.from_dict({})
        assert restored.max_workers == 3

    def test_deduplication_can_be_disabled(self):
        opts = ProcessingQueueOptions(deduplication=False)
        assert opts.deduplication is False

    def test_max_retries_customizable(self):
        opts = ProcessingQueueOptions(max_retries=5)
        assert opts.max_retries == 5
