"""
Tests for src/utils/exceptions.py

Covers the full exception hierarchy and AIResult wrapper class.
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

from utils.exceptions import (
    MedicalAssistantError,
    AudioError, RecordingError, PlaybackError,
    ProcessingError, TranscriptionError,
    TranslationError,
    APIError, RateLimitError, AuthenticationError,
    ServiceUnavailableError, QuotaExceededError,
    InvalidRequestError, APITimeoutError, TimeoutError,
    ConfigurationError,
    DatabaseError, ExportError, ValidationError,
    DeviceDisconnectedError,
    AudioSaveError, DocumentGenerationError,
    RetryableError, PermanentError,
    AIResult,
)


# ===========================================================================
# Base exception
# ===========================================================================

class TestMedicalAssistantError:
    def test_basic_message(self):
        err = MedicalAssistantError("something went wrong")
        assert str(err) == "something went wrong"
        assert err.message == "something went wrong"
        assert err.error_code is None
        assert err.details == {}

    def test_with_error_code(self):
        err = MedicalAssistantError("msg", error_code="E001")
        assert err.error_code == "E001"

    def test_with_details(self):
        err = MedicalAssistantError("msg", details={"key": "val"})
        assert err.details == {"key": "val"}

    def test_empty_details_defaults_to_dict(self):
        err = MedicalAssistantError("msg", details=None)
        assert err.details == {}

    def test_is_exception(self):
        with pytest.raises(MedicalAssistantError):
            raise MedicalAssistantError("boom")


# ===========================================================================
# Audio exceptions
# ===========================================================================

class TestAudioErrors:
    def test_audio_error_inherits_base(self):
        err = AudioError("audio fail")
        assert isinstance(err, MedicalAssistantError)
        assert isinstance(err, Exception)

    def test_recording_error(self):
        err = RecordingError("mic failed")
        assert isinstance(err, AudioError)
        assert isinstance(err, MedicalAssistantError)
        assert str(err) == "mic failed"

    def test_playback_error(self):
        err = PlaybackError("speaker failed")
        assert isinstance(err, AudioError)

    def test_device_disconnected_error_default(self):
        err = DeviceDisconnectedError("device gone")
        assert isinstance(err, AudioError)
        assert err.device_name is None

    def test_device_disconnected_error_with_name(self):
        err = DeviceDisconnectedError("device gone", device_name="USB Mic")
        assert err.device_name == "USB Mic"

    def test_device_disconnected_inherits_audio(self):
        err = DeviceDisconnectedError("gone")
        assert isinstance(err, AudioError)
        assert isinstance(err, MedicalAssistantError)


# ===========================================================================
# Processing exceptions
# ===========================================================================

class TestProcessingErrors:
    def test_processing_error_inherits_base(self):
        err = ProcessingError("process fail")
        assert isinstance(err, MedicalAssistantError)

    def test_transcription_error(self):
        err = TranscriptionError("stt failed")
        assert isinstance(err, ProcessingError)
        assert isinstance(err, MedicalAssistantError)

    def test_audio_save_error(self):
        err = AudioSaveError("write failed")
        assert isinstance(err, ProcessingError)

    def test_document_generation_error(self):
        err = DocumentGenerationError("soap gen failed")
        assert isinstance(err, ProcessingError)


# ===========================================================================
# Translation exceptions
# ===========================================================================

class TestTranslationError:
    def test_translation_error(self):
        err = TranslationError("translate fail")
        assert isinstance(err, MedicalAssistantError)
        assert str(err) == "translate fail"


# ===========================================================================
# API exceptions
# ===========================================================================

class TestAPIError:
    def test_basic_api_error(self):
        err = APIError("bad request")
        assert isinstance(err, MedicalAssistantError)
        assert err.status_code is None
        assert str(err) == "bad request"

    def test_api_error_with_status_code(self):
        err = APIError("not found", status_code=404)
        assert err.status_code == 404

    def test_api_error_with_error_code(self):
        err = APIError("forbidden", status_code=403, error_code="QUOTA")
        assert err.error_code == "QUOTA"

    def test_rate_limit_error(self):
        err = RateLimitError("too many requests")
        assert isinstance(err, APIError)
        assert isinstance(err, RetryableError)
        assert err.status_code == 429
        assert err.retry_after is None

    def test_rate_limit_error_with_retry_after(self):
        err = RateLimitError("slow down", retry_after=30)
        assert err.retry_after == 30

    def test_authentication_error(self):
        err = AuthenticationError("invalid key")
        assert isinstance(err, APIError)
        assert isinstance(err, PermanentError)
        assert err.status_code == 401

    def test_service_unavailable_error(self):
        err = ServiceUnavailableError("down")
        assert isinstance(err, APIError)
        assert isinstance(err, RetryableError)
        assert err.status_code == 503

    def test_quota_exceeded_error(self):
        err = QuotaExceededError("quota hit")
        assert isinstance(err, APIError)
        assert isinstance(err, PermanentError)
        assert err.status_code == 403

    def test_invalid_request_error(self):
        err = InvalidRequestError("bad param")
        assert isinstance(err, APIError)
        assert isinstance(err, PermanentError)
        assert err.status_code == 400

    def test_api_timeout_error_defaults(self):
        err = APITimeoutError("timed out")
        assert isinstance(err, APIError)
        assert isinstance(err, RetryableError)
        assert err.status_code == 408
        assert err.timeout_seconds is None
        assert err.service is None

    def test_api_timeout_error_with_attrs(self):
        err = APITimeoutError("timed out", timeout_seconds=30.0, service="openai")
        assert err.timeout_seconds == 30.0
        assert err.service == "openai"

    def test_timeout_error_alias(self):
        # TimeoutError is an alias for APITimeoutError
        err = TimeoutError("alias test")
        assert isinstance(err, APITimeoutError)


# ===========================================================================
# Storage / Config / Export exceptions
# ===========================================================================

class TestOtherErrors:
    def test_configuration_error(self):
        err = ConfigurationError("bad config")
        assert isinstance(err, MedicalAssistantError)
        assert isinstance(err, PermanentError)

    def test_database_error(self):
        err = DatabaseError("db fail")
        assert isinstance(err, MedicalAssistantError)

    def test_export_error(self):
        err = ExportError("export fail")
        assert isinstance(err, MedicalAssistantError)

    def test_validation_error_defaults(self):
        err = ValidationError("invalid input")
        assert isinstance(err, MedicalAssistantError)
        assert isinstance(err, PermanentError)
        assert err.field is None

    def test_validation_error_with_field(self):
        err = ValidationError("too long", field="patient_name")
        assert err.field == "patient_name"


# ===========================================================================
# Mixin classes
# ===========================================================================

class TestMixins:
    def test_retryable_error_is_base(self):
        assert issubclass(RateLimitError, RetryableError)
        assert issubclass(ServiceUnavailableError, RetryableError)
        assert issubclass(APITimeoutError, RetryableError)

    def test_permanent_error_is_base(self):
        assert issubclass(AuthenticationError, PermanentError)
        assert issubclass(QuotaExceededError, PermanentError)
        assert issubclass(InvalidRequestError, PermanentError)
        assert issubclass(ConfigurationError, PermanentError)
        assert issubclass(ValidationError, PermanentError)


# ===========================================================================
# AIResult wrapper
# ===========================================================================

class TestAIResultSuccess:
    def test_success_factory(self):
        result = AIResult.success("Hello world")
        assert result.is_success is True
        assert result.is_error is False
        assert result.text == "Hello world"
        assert result.error is None
        assert result.error_code is None

    def test_success_str(self):
        result = AIResult.success("some output")
        assert str(result) == "some output"

    def test_success_bool(self):
        result = AIResult.success("text")
        assert bool(result) is True

    def test_success_with_usage(self):
        usage = {"prompt_tokens": 10, "completion_tokens": 20, "total_tokens": 30}
        result = AIResult.success("text", usage=usage)
        assert result.usage == usage

    def test_success_with_context(self):
        result = AIResult.success("text", model="gpt-4", latency=0.5)
        assert result.context["model"] == "gpt-4"
        assert result.context["latency"] == 0.5

    def test_success_unwrap(self):
        result = AIResult.success("the text")
        assert result.unwrap() == "the text"

    def test_success_unwrap_or(self):
        result = AIResult.success("the text")
        assert result.unwrap_or("default") == "the text"

    def test_success_empty_text(self):
        result = AIResult.success("")
        assert result.text == ""
        assert str(result) == ""


class TestAIResultFailure:
    def test_failure_factory(self):
        result = AIResult.failure("something broke")
        assert result.is_success is False
        assert result.is_error is True
        assert result.text == ""
        assert result.error == "something broke"

    def test_failure_str_with_code(self):
        result = AIResult.failure("bad error", error_code="E_FAIL")
        assert "E_FAIL" in str(result)
        assert "bad error" in str(result)

    def test_failure_str_no_code(self):
        result = AIResult.failure("bad error")
        assert "AI_ERROR" in str(result)
        assert "bad error" in str(result)

    def test_failure_bool(self):
        result = AIResult.failure("error")
        assert bool(result) is False

    def test_failure_unwrap_raises_api_error(self):
        result = AIResult.failure("failed", error_code="BOOM")
        with pytest.raises(APIError):
            result.unwrap()

    def test_failure_unwrap_raises_original_exception(self):
        exc = ValueError("original")
        result = AIResult.failure("failed", exception=exc)
        with pytest.raises(ValueError):
            result.unwrap()

    def test_failure_unwrap_or(self):
        result = AIResult.failure("error")
        assert result.unwrap_or("fallback") == "fallback"

    def test_failure_with_context(self):
        result = AIResult.failure("err", provider="openai", attempt=3)
        assert result.context["provider"] == "openai"
        assert result.context["attempt"] == 3

    def test_failure_exception_property(self):
        exc = RuntimeError("cause")
        result = AIResult.failure("msg", exception=exc)
        assert result.exception is exc

    def test_failure_no_exception_property(self):
        result = AIResult.failure("msg")
        assert result.exception is None


class TestAIResultDefaults:
    def test_default_text_is_empty_string(self):
        result = AIResult()
        assert result.text == ""

    def test_default_usage_is_empty_dict(self):
        result = AIResult()
        assert result.usage == {}

    def test_default_context_is_empty_dict(self):
        result = AIResult()
        assert result.context == {}

    def test_none_text_returns_empty(self):
        result = AIResult(text=None)
        assert result.text == ""

    def test_success_result_has_empty_usage_by_default(self):
        result = AIResult.success("text")
        assert result.usage == {}
