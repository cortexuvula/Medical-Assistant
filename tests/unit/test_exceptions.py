"""
Tests for exception hierarchy and AIResult in src/utils/exceptions.py

Covers MedicalAssistantError (message/error_code/details), exception inheritance
chains (AudioError, RecordingError, PlaybackError, TranscriptionError, etc.),
APIError (status_code), RateLimitError (status=429, retry_after, RetryableError mixin),
AuthenticationError (status=401, PermanentError mixin), ServiceUnavailableError,
QuotaExceededError, InvalidRequestError, APITimeoutError (timeout_seconds, service),
ValidationError (field), DeviceDisconnectedError (device_name),
and AIResult (success/failure factories, properties, __str__, __bool__, unwrap).
No network, no Tkinter, no file I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.exceptions import (
    RetryableError, PermanentError, MedicalAssistantError,
    AudioError, RecordingError, PlaybackError,
    ProcessingError, TranscriptionError, TranslationError,
    APIError, RateLimitError, AuthenticationError,
    ServiceUnavailableError, QuotaExceededError, InvalidRequestError,
    APITimeoutError, ConfigurationError, DatabaseError, ExportError,
    ValidationError, DeviceDisconnectedError,
    AudioSaveError, DocumentGenerationError, AIResult,
)


# ===========================================================================
# MedicalAssistantError
# ===========================================================================

class TestMedicalAssistantError:
    def test_is_exception(self):
        assert issubclass(MedicalAssistantError, Exception)

    def test_message_stored(self):
        e = MedicalAssistantError("test message")
        assert e.message == "test message"

    def test_str_message(self):
        e = MedicalAssistantError("something failed")
        assert "something failed" in str(e)

    def test_error_code_stored(self):
        e = MedicalAssistantError("msg", error_code="E001")
        assert e.error_code == "E001"

    def test_error_code_default_none(self):
        e = MedicalAssistantError("msg")
        assert e.error_code is None

    def test_details_stored(self):
        e = MedicalAssistantError("msg", details={"key": "value"})
        assert e.details == {"key": "value"}

    def test_details_default_empty_dict(self):
        e = MedicalAssistantError("msg")
        assert e.details == {}

    def test_can_raise_and_catch(self):
        with pytest.raises(MedicalAssistantError):
            raise MedicalAssistantError("test")


# ===========================================================================
# Audio exception hierarchy
# ===========================================================================

class TestAudioExceptions:
    def test_audio_error_is_medical_assistant_error(self):
        assert issubclass(AudioError, MedicalAssistantError)

    def test_recording_error_is_audio_error(self):
        assert issubclass(RecordingError, AudioError)

    def test_playback_error_is_audio_error(self):
        assert issubclass(PlaybackError, AudioError)

    def test_recording_error_can_raise(self):
        with pytest.raises(AudioError):
            raise RecordingError("mic failed")

    def test_playback_error_message(self):
        e = PlaybackError("speaker error")
        assert e.message == "speaker error"


# ===========================================================================
# Processing exceptions
# ===========================================================================

class TestProcessingExceptions:
    def test_processing_error_is_medical_assistant_error(self):
        assert issubclass(ProcessingError, MedicalAssistantError)

    def test_transcription_error_is_processing_error(self):
        assert issubclass(TranscriptionError, ProcessingError)

    def test_translation_error_is_medical_assistant_error(self):
        assert issubclass(TranslationError, MedicalAssistantError)

    def test_audio_save_error_is_processing_error(self):
        assert issubclass(AudioSaveError, ProcessingError)

    def test_document_generation_error_is_processing_error(self):
        assert issubclass(DocumentGenerationError, ProcessingError)

    def test_transcription_error_caught_as_medical(self):
        with pytest.raises(MedicalAssistantError):
            raise TranscriptionError("STT failed")


# ===========================================================================
# APIError
# ===========================================================================

class TestAPIError:
    def test_is_medical_assistant_error(self):
        assert issubclass(APIError, MedicalAssistantError)

    def test_status_code_stored(self):
        e = APIError("bad request", status_code=400)
        assert e.status_code == 400

    def test_status_code_default_none(self):
        e = APIError("error")
        assert e.status_code is None

    def test_error_code_propagated(self):
        e = APIError("msg", error_code="API_001")
        assert e.error_code == "API_001"

    def test_message_stored(self):
        e = APIError("api failure")
        assert e.message == "api failure"


# ===========================================================================
# RateLimitError
# ===========================================================================

class TestRateLimitError:
    def test_is_api_error(self):
        assert issubclass(RateLimitError, APIError)

    def test_is_retryable(self):
        assert issubclass(RateLimitError, RetryableError)

    def test_status_code_is_429(self):
        e = RateLimitError("too many requests")
        assert e.status_code == 429

    def test_retry_after_stored(self):
        e = RateLimitError("slow down", retry_after=60)
        assert e.retry_after == 60

    def test_retry_after_default_none(self):
        e = RateLimitError("slow down")
        assert e.retry_after is None

    def test_isinstance_retryable(self):
        e = RateLimitError("rate limited")
        assert isinstance(e, RetryableError)

    def test_caught_as_api_error(self):
        with pytest.raises(APIError):
            raise RateLimitError("limit hit")


# ===========================================================================
# AuthenticationError
# ===========================================================================

class TestAuthenticationError:
    def test_is_api_error(self):
        assert issubclass(AuthenticationError, APIError)

    def test_is_permanent(self):
        assert issubclass(AuthenticationError, PermanentError)

    def test_status_code_is_401(self):
        e = AuthenticationError("invalid key")
        assert e.status_code == 401

    def test_isinstance_permanent(self):
        e = AuthenticationError("bad key")
        assert isinstance(e, PermanentError)


# ===========================================================================
# ServiceUnavailableError, QuotaExceededError, InvalidRequestError
# ===========================================================================

class TestOtherAPIErrors:
    def test_service_unavailable_status_503(self):
        e = ServiceUnavailableError("down")
        assert e.status_code == 503

    def test_service_unavailable_is_retryable(self):
        assert issubclass(ServiceUnavailableError, RetryableError)

    def test_quota_exceeded_status_403(self):
        e = QuotaExceededError("quota hit")
        assert e.status_code == 403

    def test_quota_exceeded_is_permanent(self):
        assert issubclass(QuotaExceededError, PermanentError)

    def test_invalid_request_status_400(self):
        e = InvalidRequestError("bad payload")
        assert e.status_code == 400

    def test_invalid_request_is_permanent(self):
        assert issubclass(InvalidRequestError, PermanentError)


# ===========================================================================
# APITimeoutError
# ===========================================================================

class TestAPITimeoutError:
    def test_status_code_408(self):
        e = APITimeoutError("timed out")
        assert e.status_code == 408

    def test_is_retryable(self):
        assert issubclass(APITimeoutError, RetryableError)

    def test_timeout_seconds_stored(self):
        e = APITimeoutError("slow", timeout_seconds=30.0)
        assert e.timeout_seconds == 30.0

    def test_service_stored(self):
        e = APITimeoutError("slow", service="openai")
        assert e.service == "openai"

    def test_timeout_seconds_default_none(self):
        e = APITimeoutError("slow")
        assert e.timeout_seconds is None


# ===========================================================================
# ValidationError, DeviceDisconnectedError
# ===========================================================================

class TestValidationError:
    def test_is_medical_assistant_error(self):
        assert issubclass(ValidationError, MedicalAssistantError)

    def test_is_permanent(self):
        assert issubclass(ValidationError, PermanentError)

    def test_field_stored(self):
        e = ValidationError("bad value", field="username")
        assert e.field == "username"

    def test_field_default_none(self):
        e = ValidationError("bad value")
        assert e.field is None


class TestDeviceDisconnectedError:
    def test_is_audio_error(self):
        assert issubclass(DeviceDisconnectedError, AudioError)

    def test_device_name_stored(self):
        e = DeviceDisconnectedError("device gone", device_name="Mic XYZ")
        assert e.device_name == "Mic XYZ"

    def test_device_name_default_none(self):
        e = DeviceDisconnectedError("device gone")
        assert e.device_name is None


# ===========================================================================
# ConfigurationError, DatabaseError, ExportError
# ===========================================================================

class TestMiscExceptions:
    def test_configuration_error_is_medical(self):
        assert issubclass(ConfigurationError, MedicalAssistantError)

    def test_configuration_error_is_permanent(self):
        assert issubclass(ConfigurationError, PermanentError)

    def test_database_error_is_medical(self):
        assert issubclass(DatabaseError, MedicalAssistantError)

    def test_export_error_is_medical(self):
        assert issubclass(ExportError, MedicalAssistantError)


# ===========================================================================
# AIResult — success factory
# ===========================================================================

class TestAIResultSuccess:
    def test_success_is_success(self):
        r = AIResult.success("generated text")
        assert r.is_success is True

    def test_success_is_not_error(self):
        r = AIResult.success("text")
        assert r.is_error is False

    def test_success_text(self):
        r = AIResult.success("hello world")
        assert r.text == "hello world"

    def test_success_error_is_none(self):
        r = AIResult.success("text")
        assert r.error is None

    def test_success_error_code_is_none(self):
        r = AIResult.success("text")
        assert r.error_code is None

    def test_success_str_returns_text(self):
        r = AIResult.success("my text")
        assert str(r) == "my text"

    def test_success_bool_is_true(self):
        r = AIResult.success("text")
        assert bool(r) is True

    def test_success_unwrap_returns_text(self):
        r = AIResult.success("the text")
        assert r.unwrap() == "the text"

    def test_success_unwrap_or_returns_text(self):
        r = AIResult.success("real")
        assert r.unwrap_or("default") == "real"

    def test_success_usage_stored(self):
        r = AIResult.success("text", usage={"total_tokens": 100})
        assert r.usage == {"total_tokens": 100}

    def test_success_usage_default_empty(self):
        r = AIResult.success("text")
        assert r.usage == {}


# ===========================================================================
# AIResult — failure factory
# ===========================================================================

class TestAIResultFailure:
    def test_failure_is_error(self):
        r = AIResult.failure("something broke")
        assert r.is_error is True

    def test_failure_is_not_success(self):
        r = AIResult.failure("err")
        assert r.is_success is False

    def test_failure_error_message(self):
        r = AIResult.failure("API error")
        assert r.error == "API error"

    def test_failure_error_code(self):
        r = AIResult.failure("err", error_code="E500")
        assert r.error_code == "E500"

    def test_failure_text_is_empty_string(self):
        r = AIResult.failure("err")
        assert r.text == ""

    def test_failure_str_contains_error(self):
        r = AIResult.failure("bad response", error_code="AI_ERR")
        s = str(r)
        assert "bad response" in s
        assert "AI_ERR" in s

    def test_failure_bool_is_false(self):
        r = AIResult.failure("err")
        assert bool(r) is False

    def test_failure_unwrap_raises_api_error(self):
        r = AIResult.failure("failed")
        with pytest.raises(APIError):
            r.unwrap()

    def test_failure_unwrap_raises_stored_exception(self):
        orig_exc = ValueError("original")
        r = AIResult.failure("err", exception=orig_exc)
        with pytest.raises(ValueError):
            r.unwrap()

    def test_failure_unwrap_or_returns_default(self):
        r = AIResult.failure("err")
        assert r.unwrap_or("fallback") == "fallback"

    def test_failure_exception_stored(self):
        exc = RuntimeError("boom")
        r = AIResult.failure("err", exception=exc)
        assert r.exception is exc

    def test_failure_no_exception_is_none(self):
        r = AIResult.failure("err")
        assert r.exception is None


# ===========================================================================
# AIResult — context
# ===========================================================================

class TestAIResultContext:
    def test_context_default_empty(self):
        r = AIResult.success("text")
        assert r.context == {}

    def test_context_passed_via_kwargs(self):
        r = AIResult.success("text", provider="openai", model="gpt-4")
        assert r.context.get("provider") == "openai"
        assert r.context.get("model") == "gpt-4"

    def test_failure_context_via_kwargs(self):
        r = AIResult.failure("err", retry_count=3)
        assert r.context.get("retry_count") == 3
