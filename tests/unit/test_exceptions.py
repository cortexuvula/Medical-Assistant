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
    AudioError, RecordingError, PlaybackError, AudioSaveError,
    ProcessingError, TranscriptionError, TranslationError,
    APIError, RateLimitError, AuthenticationError, ServiceUnavailableError,
    QuotaExceededError, InvalidRequestError, APITimeoutError,
    ConfigurationError, DatabaseError, ExportError,
    ValidationError, DeviceDisconnectedError,
    DocumentGenerationError, AIResult,
)


# ===========================================================================
# Mixin classes
# ===========================================================================

class TestRetryableError:
    def test_is_not_base_exception(self):
        assert not issubclass(RetryableError, Exception)

    def test_instantiable(self):
        obj = RetryableError()
        assert isinstance(obj, RetryableError)

    def test_rate_limit_is_retryable(self):
        assert isinstance(RateLimitError("msg"), RetryableError)

    def test_service_unavailable_is_retryable(self):
        assert isinstance(ServiceUnavailableError("msg"), RetryableError)

    def test_api_timeout_is_retryable(self):
        assert isinstance(APITimeoutError("msg"), RetryableError)


class TestPermanentError:
    def test_is_not_base_exception(self):
        assert not issubclass(PermanentError, Exception)

    def test_instantiable(self):
        obj = PermanentError()
        assert isinstance(obj, PermanentError)

    def test_authentication_is_permanent(self):
        assert isinstance(AuthenticationError("msg"), PermanentError)

    def test_quota_exceeded_is_permanent(self):
        assert isinstance(QuotaExceededError("msg"), PermanentError)

    def test_invalid_request_is_permanent(self):
        assert isinstance(InvalidRequestError("msg"), PermanentError)

    def test_configuration_is_permanent(self):
        assert isinstance(ConfigurationError("msg"), PermanentError)

    def test_validation_is_permanent(self):
        assert isinstance(ValidationError("msg"), PermanentError)


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

    def test_details_none_becomes_empty_dict(self):
        e = MedicalAssistantError("msg", details=None)
        assert e.details == {}

    def test_can_raise_and_catch(self):
        with pytest.raises(MedicalAssistantError):
            raise MedicalAssistantError("test")

    def test_catchable_as_exception(self):
        with pytest.raises(Exception):
            raise MedicalAssistantError("catch as Exception")


# ===========================================================================
# Audio exception hierarchy
# ===========================================================================

class TestAudioError:
    def test_is_medical_assistant_error(self):
        assert issubclass(AudioError, MedicalAssistantError)

    def test_instantiation(self):
        e = AudioError("audio problem")
        assert e.message == "audio problem"

    def test_inherits_details_default(self):
        e = AudioError("msg")
        assert e.details == {}


class TestRecordingError:
    def test_is_audio_error(self):
        assert issubclass(RecordingError, AudioError)

    def test_is_medical_assistant_error(self):
        assert issubclass(RecordingError, MedicalAssistantError)

    def test_message_stored(self):
        e = RecordingError("mic failed")
        assert e.message == "mic failed"

    def test_caught_as_audio_error(self):
        with pytest.raises(AudioError):
            raise RecordingError("mic failed")

    def test_caught_as_exception(self):
        with pytest.raises(Exception):
            raise RecordingError("mic failed")


class TestPlaybackError:
    def test_is_audio_error(self):
        assert issubclass(PlaybackError, AudioError)

    def test_message_stored(self):
        e = PlaybackError("speaker error")
        assert e.message == "speaker error"

    def test_caught_as_audio_error(self):
        with pytest.raises(AudioError):
            raise PlaybackError("speaker error")


class TestAudioSaveError:
    def test_is_processing_error(self):
        assert issubclass(AudioSaveError, ProcessingError)

    def test_is_medical_assistant_error(self):
        assert issubclass(AudioSaveError, MedicalAssistantError)

    def test_message_stored(self):
        e = AudioSaveError("save failed")
        assert e.message == "save failed"


# ===========================================================================
# Processing exceptions
# ===========================================================================

class TestProcessingError:
    def test_is_medical_assistant_error(self):
        assert issubclass(ProcessingError, MedicalAssistantError)

    def test_message_stored(self):
        e = ProcessingError("processing failed")
        assert e.message == "processing failed"


class TestTranscriptionError:
    def test_is_processing_error(self):
        assert issubclass(TranscriptionError, ProcessingError)

    def test_is_medical_assistant_error(self):
        assert issubclass(TranscriptionError, MedicalAssistantError)

    def test_message_stored(self):
        e = TranscriptionError("STT failed")
        assert e.message == "STT failed"

    def test_caught_as_processing_error(self):
        with pytest.raises(ProcessingError):
            raise TranscriptionError("STT error")

    def test_caught_as_medical(self):
        with pytest.raises(MedicalAssistantError):
            raise TranscriptionError("STT failed")


class TestTranslationError:
    def test_is_medical_assistant_error(self):
        assert issubclass(TranslationError, MedicalAssistantError)

    def test_not_processing_error(self):
        assert not issubclass(TranslationError, ProcessingError)

    def test_message_stored(self):
        e = TranslationError("translation failed")
        assert e.message == "translation failed"


class TestDocumentGenerationError:
    def test_is_processing_error(self):
        assert issubclass(DocumentGenerationError, ProcessingError)

    def test_is_medical_assistant_error(self):
        assert issubclass(DocumentGenerationError, MedicalAssistantError)

    def test_message_stored(self):
        e = DocumentGenerationError("SOAP generation failed")
        assert e.message == "SOAP generation failed"


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

    def test_details_forwarded(self):
        e = APIError("api error", details={"url": "/v1/chat"})
        assert e.details == {"url": "/v1/chat"}

    def test_raisable(self):
        with pytest.raises(APIError):
            raise APIError("boom")


# ===========================================================================
# RateLimitError
# ===========================================================================

class TestRateLimitError:
    def test_is_api_error(self):
        assert issubclass(RateLimitError, APIError)

    def test_is_retryable_subclass(self):
        assert issubclass(RateLimitError, RetryableError)

    def test_is_not_permanent_subclass(self):
        assert not issubclass(RateLimitError, PermanentError)

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

    def test_message_stored(self):
        e = RateLimitError("too many requests")
        assert e.message == "too many requests"

    def test_error_code_passthrough(self):
        e = RateLimitError("rate limited", error_code="RATE_LIMIT")
        assert e.error_code == "RATE_LIMIT"


# ===========================================================================
# AuthenticationError
# ===========================================================================

class TestAuthenticationError:
    def test_is_api_error(self):
        assert issubclass(AuthenticationError, APIError)

    def test_is_permanent_subclass(self):
        assert issubclass(AuthenticationError, PermanentError)

    def test_is_not_retryable_subclass(self):
        assert not issubclass(AuthenticationError, RetryableError)

    def test_status_code_is_401(self):
        e = AuthenticationError("invalid key")
        assert e.status_code == 401

    def test_isinstance_permanent(self):
        e = AuthenticationError("bad key")
        assert isinstance(e, PermanentError)

    def test_message_stored(self):
        e = AuthenticationError("invalid API key")
        assert e.message == "invalid API key"

    def test_caught_as_api_error(self):
        with pytest.raises(APIError):
            raise AuthenticationError("invalid key")


# ===========================================================================
# ServiceUnavailableError
# ===========================================================================

class TestServiceUnavailableError:
    def test_is_api_error(self):
        assert issubclass(ServiceUnavailableError, APIError)

    def test_is_retryable(self):
        assert issubclass(ServiceUnavailableError, RetryableError)

    def test_is_not_permanent(self):
        assert not issubclass(ServiceUnavailableError, PermanentError)

    def test_status_code_503(self):
        e = ServiceUnavailableError("down")
        assert e.status_code == 503

    def test_message_stored(self):
        e = ServiceUnavailableError("OpenAI is down")
        assert e.message == "OpenAI is down"

    def test_error_code_passthrough(self):
        e = ServiceUnavailableError("down", error_code="SVC_DOWN")
        assert e.error_code == "SVC_DOWN"


# ===========================================================================
# QuotaExceededError
# ===========================================================================

class TestQuotaExceededError:
    def test_is_api_error(self):
        assert issubclass(QuotaExceededError, APIError)

    def test_is_permanent(self):
        assert issubclass(QuotaExceededError, PermanentError)

    def test_is_not_retryable(self):
        assert not issubclass(QuotaExceededError, RetryableError)

    def test_status_code_403(self):
        e = QuotaExceededError("quota hit")
        assert e.status_code == 403

    def test_message_stored(self):
        e = QuotaExceededError("monthly limit reached")
        assert e.message == "monthly limit reached"


# ===========================================================================
# InvalidRequestError
# ===========================================================================

class TestInvalidRequestError:
    def test_is_api_error(self):
        assert issubclass(InvalidRequestError, APIError)

    def test_is_permanent(self):
        assert issubclass(InvalidRequestError, PermanentError)

    def test_is_not_retryable(self):
        assert not issubclass(InvalidRequestError, RetryableError)

    def test_status_code_400(self):
        e = InvalidRequestError("bad payload")
        assert e.status_code == 400

    def test_message_stored(self):
        e = InvalidRequestError("malformed JSON")
        assert e.message == "malformed JSON"


# ===========================================================================
# APITimeoutError
# ===========================================================================

class TestAPITimeoutError:
    def test_is_api_error(self):
        assert issubclass(APITimeoutError, APIError)

    def test_is_retryable(self):
        assert issubclass(APITimeoutError, RetryableError)

    def test_is_not_permanent(self):
        assert not issubclass(APITimeoutError, PermanentError)

    def test_status_code_408(self):
        e = APITimeoutError("timed out")
        assert e.status_code == 408

    def test_timeout_seconds_stored(self):
        e = APITimeoutError("slow", timeout_seconds=30.0)
        assert e.timeout_seconds == 30.0

    def test_timeout_seconds_default_none(self):
        e = APITimeoutError("slow")
        assert e.timeout_seconds is None

    def test_service_stored(self):
        e = APITimeoutError("slow", service="openai")
        assert e.service == "openai"

    def test_service_default_none(self):
        e = APITimeoutError("slow")
        assert e.service is None

    def test_message_stored(self):
        e = APITimeoutError("connection timed out")
        assert e.message == "connection timed out"

    def test_all_attributes_together(self):
        e = APITimeoutError("timeout", timeout_seconds=10.5, service="anthropic",
                            error_code="TIMEOUT")
        assert e.status_code == 408
        assert e.timeout_seconds == 10.5
        assert e.service == "anthropic"
        assert e.error_code == "TIMEOUT"

    def test_timeout_error_alias(self):
        from utils.exceptions import TimeoutError as TE
        assert TE is APITimeoutError

    def test_caught_as_api_error(self):
        with pytest.raises(APIError):
            raise APITimeoutError("timed out")


# ===========================================================================
# ConfigurationError, DatabaseError, ExportError
# ===========================================================================

class TestConfigurationError:
    def test_is_medical_assistant_error(self):
        assert issubclass(ConfigurationError, MedicalAssistantError)

    def test_is_permanent(self):
        assert issubclass(ConfigurationError, PermanentError)

    def test_is_not_retryable(self):
        assert not issubclass(ConfigurationError, RetryableError)

    def test_message_stored(self):
        e = ConfigurationError("missing API key")
        assert e.message == "missing API key"

    def test_error_code_stored(self):
        e = ConfigurationError("bad config", error_code="CFG_ERR")
        assert e.error_code == "CFG_ERR"


class TestDatabaseError:
    def test_is_medical_assistant_error(self):
        assert issubclass(DatabaseError, MedicalAssistantError)

    def test_is_not_permanent(self):
        assert not issubclass(DatabaseError, PermanentError)

    def test_message_stored(self):
        e = DatabaseError("connection failed")
        assert e.message == "connection failed"

    def test_details_stored(self):
        e = DatabaseError("db error", details={"table": "recordings"})
        assert e.details == {"table": "recordings"}


class TestExportError:
    def test_is_medical_assistant_error(self):
        assert issubclass(ExportError, MedicalAssistantError)

    def test_message_stored(self):
        e = ExportError("export failed")
        assert e.message == "export failed"


# ===========================================================================
# ValidationError
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

    def test_message_stored(self):
        e = ValidationError("value out of range")
        assert e.message == "value out of range"

    def test_error_code_passthrough(self):
        e = ValidationError("bad value", error_code="VAL_ERR", field="dob")
        assert e.error_code == "VAL_ERR"
        assert e.field == "dob"


# ===========================================================================
# DeviceDisconnectedError
# ===========================================================================

class TestDeviceDisconnectedError:
    def test_is_audio_error(self):
        assert issubclass(DeviceDisconnectedError, AudioError)

    def test_is_medical_assistant_error(self):
        assert issubclass(DeviceDisconnectedError, MedicalAssistantError)

    def test_device_name_stored(self):
        e = DeviceDisconnectedError("device gone", device_name="Mic XYZ")
        assert e.device_name == "Mic XYZ"

    def test_device_name_default_none(self):
        e = DeviceDisconnectedError("device gone")
        assert e.device_name is None

    def test_message_stored(self):
        e = DeviceDisconnectedError("microphone disconnected")
        assert e.message == "microphone disconnected"

    def test_caught_as_audio_error(self):
        with pytest.raises(AudioError):
            raise DeviceDisconnectedError("device lost")


# ===========================================================================
# AIResult — success factory
# ===========================================================================

class TestAIResultSuccess:
    def test_is_success_true(self):
        r = AIResult.success("generated text")
        assert r.is_success is True

    def test_is_error_false(self):
        r = AIResult.success("text")
        assert r.is_error is False

    def test_text_returned(self):
        r = AIResult.success("hello world")
        assert r.text == "hello world"

    def test_error_is_none(self):
        r = AIResult.success("text")
        assert r.error is None

    def test_error_code_is_none(self):
        r = AIResult.success("text")
        assert r.error_code is None

    def test_exception_is_none(self):
        r = AIResult.success("text")
        assert r.exception is None

    def test_str_returns_text(self):
        r = AIResult.success("my text")
        assert str(r) == "my text"

    def test_bool_is_true(self):
        r = AIResult.success("text")
        assert bool(r) is True

    def test_unwrap_returns_text(self):
        r = AIResult.success("the text")
        assert r.unwrap() == "the text"

    def test_unwrap_or_returns_text(self):
        r = AIResult.success("real")
        assert r.unwrap_or("default") == "real"

    def test_usage_stored(self):
        r = AIResult.success("text", usage={"total_tokens": 100})
        assert r.usage == {"total_tokens": 100}

    def test_usage_default_empty(self):
        r = AIResult.success("text")
        assert r.usage == {}

    def test_context_from_kwargs(self):
        r = AIResult.success("text", provider="openai", model="gpt-4")
        assert r.context["provider"] == "openai"
        assert r.context["model"] == "gpt-4"

    def test_context_empty_when_no_kwargs(self):
        r = AIResult.success("text")
        assert r.context == {}

    def test_str_empty_text(self):
        r = AIResult.success("")
        assert str(r) == ""


# ===========================================================================
# AIResult — failure factory
# ===========================================================================

class TestAIResultFailure:
    def test_is_error_true(self):
        r = AIResult.failure("something broke")
        assert r.is_error is True

    def test_is_success_false(self):
        r = AIResult.failure("err")
        assert r.is_success is False

    def test_error_message_stored(self):
        r = AIResult.failure("API error")
        assert r.error == "API error"

    def test_error_code_stored(self):
        r = AIResult.failure("err", error_code="E500")
        assert r.error_code == "E500"

    def test_error_code_default_none(self):
        r = AIResult.failure("err")
        assert r.error_code is None

    def test_text_is_empty_string(self):
        r = AIResult.failure("err")
        assert r.text == ""

    def test_bool_is_false(self):
        r = AIResult.failure("err")
        assert bool(r) is False

    def test_exception_stored(self):
        exc = RuntimeError("boom")
        r = AIResult.failure("err", exception=exc)
        assert r.exception is exc

    def test_exception_default_none(self):
        r = AIResult.failure("err")
        assert r.exception is None

    def test_unwrap_raises_api_error(self):
        r = AIResult.failure("failed")
        with pytest.raises(APIError):
            r.unwrap()

    def test_unwrap_raises_stored_exception(self):
        orig_exc = ValueError("original")
        r = AIResult.failure("err", exception=orig_exc)
        with pytest.raises(ValueError):
            r.unwrap()

    def test_unwrap_or_returns_default(self):
        r = AIResult.failure("err")
        assert r.unwrap_or("fallback") == "fallback"

    def test_unwrap_or_returns_empty_string_default(self):
        r = AIResult.failure("err")
        assert r.unwrap_or("") == ""

    def test_context_from_kwargs(self):
        r = AIResult.failure("err", retry_count=3)
        assert r.context["retry_count"] == 3

    def test_context_empty_when_no_kwargs(self):
        r = AIResult.failure("err")
        assert r.context == {}


# ===========================================================================
# AIResult.__str__
# ===========================================================================

class TestAIResultStr:
    def test_success_str_is_text(self):
        r = AIResult.success("The SOAP note text.")
        assert str(r) == "The SOAP note text."

    def test_failure_str_with_error_code(self):
        r = AIResult.failure("bad request", error_code="INVALID_REQ")
        result = str(r)
        assert "INVALID_REQ" in result
        assert "bad request" in result

    def test_failure_str_without_error_code_uses_default(self):
        r = AIResult.failure("something failed")
        result = str(r)
        assert "AI_ERROR" in result
        assert "something failed" in result

    def test_failure_str_exact_format_with_code(self):
        r = AIResult.failure("the error message", error_code="CODE")
        assert str(r) == "[Error: CODE] the error message"

    def test_failure_str_exact_format_no_code(self):
        r = AIResult.failure("the error message")
        assert str(r) == "[Error: AI_ERROR] the error message"


# ===========================================================================
# AIResult.unwrap
# ===========================================================================

class TestAIResultUnwrap:
    def test_success_returns_text(self):
        r = AIResult.success("the text")
        assert r.unwrap() == "the text"

    def test_failure_raises_api_error(self):
        r = AIResult.failure("failed")
        with pytest.raises(APIError):
            r.unwrap()

    def test_failure_with_exception_re_raises_original(self):
        original = AuthenticationError("auth failed")
        r = AIResult.failure("wrapped", exception=original)
        with pytest.raises(AuthenticationError):
            r.unwrap()

    def test_failure_api_error_carries_error_code(self):
        r = AIResult.failure("call failed", error_code="NET_ERR")
        with pytest.raises(APIError) as exc_info:
            r.unwrap()
        assert exc_info.value.error_code == "NET_ERR"


# ===========================================================================
# AIResult.unwrap_or
# ===========================================================================

class TestAIResultUnwrapOr:
    def test_success_returns_text(self):
        r = AIResult.success("actual text")
        assert r.unwrap_or("default") == "actual text"

    def test_failure_returns_default(self):
        r = AIResult.failure("error")
        assert r.unwrap_or("fallback text") == "fallback text"

    def test_failure_empty_string_default(self):
        r = AIResult.failure("error")
        assert r.unwrap_or("") == ""

    def test_success_ignores_default(self):
        r = AIResult.success("real text")
        assert r.unwrap_or("should not appear") == "real text"


# ===========================================================================
# AIResult.context and .usage
# ===========================================================================

class TestAIResultContextAndUsage:
    def test_context_default_empty_on_direct_construction(self):
        r = AIResult()
        assert r.context == {}

    def test_usage_default_empty_on_direct_construction(self):
        r = AIResult()
        assert r.usage == {}

    def test_context_none_becomes_empty_dict(self):
        r = AIResult(context=None)
        assert r.context == {}

    def test_usage_none_becomes_empty_dict(self):
        r = AIResult(usage=None)
        assert r.usage == {}

    def test_context_stored_on_success(self):
        r = AIResult.success("text", provider="anthropic", model="claude-3")
        assert r.context == {"provider": "anthropic", "model": "claude-3"}

    def test_usage_with_token_counts(self):
        usage = {"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150}
        r = AIResult.success("text", usage=usage)
        assert r.usage["total_tokens"] == 150
        assert r.usage["prompt_tokens"] == 50

    def test_context_stored_on_failure(self):
        r = AIResult.failure("err", attempt=2, provider="openai")
        assert r.context["attempt"] == 2
        assert r.context["provider"] == "openai"


# ===========================================================================
# Cross-hierarchy isinstance checks
# ===========================================================================

class TestCrossHierarchyIsInstance:
    def test_recording_error_full_chain(self):
        e = RecordingError("rec fail")
        assert isinstance(e, RecordingError)
        assert isinstance(e, AudioError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, Exception)

    def test_transcription_error_full_chain(self):
        e = TranscriptionError("stt fail")
        assert isinstance(e, TranscriptionError)
        assert isinstance(e, ProcessingError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, Exception)

    def test_rate_limit_error_full_chain(self):
        e = RateLimitError("rate limited")
        assert isinstance(e, RateLimitError)
        assert isinstance(e, APIError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, RetryableError)
        assert isinstance(e, Exception)

    def test_authentication_error_full_chain(self):
        e = AuthenticationError("unauth")
        assert isinstance(e, AuthenticationError)
        assert isinstance(e, APIError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, PermanentError)
        assert isinstance(e, Exception)

    def test_configuration_error_full_chain(self):
        e = ConfigurationError("bad config")
        assert isinstance(e, ConfigurationError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, PermanentError)
        assert isinstance(e, Exception)

    def test_validation_error_full_chain(self):
        e = ValidationError("bad input")
        assert isinstance(e, ValidationError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, PermanentError)
        assert isinstance(e, Exception)

    def test_device_disconnected_error_full_chain(self):
        e = DeviceDisconnectedError("device lost")
        assert isinstance(e, DeviceDisconnectedError)
        assert isinstance(e, AudioError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, Exception)

    def test_api_timeout_error_full_chain(self):
        e = APITimeoutError("timed out")
        assert isinstance(e, APITimeoutError)
        assert isinstance(e, APIError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, RetryableError)
        assert isinstance(e, Exception)

    def test_document_generation_error_full_chain(self):
        e = DocumentGenerationError("gen failed")
        assert isinstance(e, DocumentGenerationError)
        assert isinstance(e, ProcessingError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, Exception)

    def test_audio_save_error_full_chain(self):
        e = AudioSaveError("save failed")
        assert isinstance(e, AudioSaveError)
        assert isinstance(e, ProcessingError)
        assert isinstance(e, MedicalAssistantError)
        assert isinstance(e, Exception)

    def test_retryable_errors_are_not_permanent(self):
        for cls in (RateLimitError, ServiceUnavailableError, APITimeoutError):
            e = cls("msg")
            assert isinstance(e, RetryableError), f"{cls.__name__} should be RetryableError"
            assert not isinstance(e, PermanentError), f"{cls.__name__} should not be PermanentError"

    def test_permanent_errors_are_not_retryable(self):
        for cls in (AuthenticationError, QuotaExceededError, InvalidRequestError,
                    ConfigurationError, ValidationError):
            e = cls("msg")
            assert isinstance(e, PermanentError), f"{cls.__name__} should be PermanentError"
            assert not isinstance(e, RetryableError), f"{cls.__name__} should not be RetryableError"
