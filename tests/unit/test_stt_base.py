"""
Tests for TranscriptionResult and BaseSTTProvider in src/stt_providers/base.py

Covers TranscriptionResult dataclass (defaults, success_result, failure_result,
field values); BaseSTTProvider (default properties: supports_diarization,
requires_api_key, is_configured; _check_api_key, test_connection, __repr__).
Uses a minimal concrete stub to satisfy abstract methods.
No network, no Tkinter, no audio I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from stt_providers.base import TranscriptionResult, BaseSTTProvider


# ---------------------------------------------------------------------------
# Minimal concrete STT stub — only implements required abstract methods
# ---------------------------------------------------------------------------

class _StubSTT(BaseSTTProvider):
    """Concrete stub for testing BaseSTTProvider."""

    def __init__(self, api_key="", language="en-US", transcribe_return="hello"):
        super().__init__(api_key=api_key, language=language)
        self._transcribe_return = transcribe_return

    @property
    def provider_name(self) -> str:
        return "stub"

    def transcribe(self, segment):
        return self._transcribe_return

    def test_connection(self) -> bool:
        return super().test_connection()


class _NoKeySTT(_StubSTT):
    """Stub that reports it doesn't require an API key."""

    @property
    def requires_api_key(self) -> bool:
        return False


# ===========================================================================
# TranscriptionResult
# ===========================================================================

class TestTranscriptionResultDefaults:
    def test_create_with_text(self):
        r = TranscriptionResult(text="hello world")
        assert r.text == "hello world"

    def test_default_success_true(self):
        r = TranscriptionResult(text="hello")
        assert r.success is True

    def test_default_error_none(self):
        r = TranscriptionResult(text="hello")
        assert r.error is None

    def test_default_confidence_none(self):
        r = TranscriptionResult(text="hello")
        assert r.confidence is None

    def test_default_duration_none(self):
        r = TranscriptionResult(text="hello")
        assert r.duration_seconds is None

    def test_default_words_empty_list(self):
        r = TranscriptionResult(text="hello")
        assert r.words == []

    def test_default_metadata_empty_dict(self):
        r = TranscriptionResult(text="hello")
        assert r.metadata == {}


class TestTranscriptionResultSuccessFactory:
    def test_success_result_text(self):
        r = TranscriptionResult.success_result("Patient has diabetes.")
        assert r.text == "Patient has diabetes."

    def test_success_result_success_true(self):
        r = TranscriptionResult.success_result("text")
        assert r.success is True

    def test_success_result_error_none(self):
        r = TranscriptionResult.success_result("text")
        assert r.error is None

    def test_success_result_with_confidence(self):
        r = TranscriptionResult.success_result("text", confidence=0.95)
        assert r.confidence == pytest.approx(0.95)

    def test_success_result_with_duration(self):
        r = TranscriptionResult.success_result("text", duration_seconds=3.5)
        assert r.duration_seconds == pytest.approx(3.5)

    def test_success_result_with_metadata(self):
        r = TranscriptionResult.success_result("text", metadata={"model": "nova"})
        assert r.metadata["model"] == "nova"

    def test_success_result_returns_transcription_result(self):
        assert isinstance(TranscriptionResult.success_result("x"), TranscriptionResult)


class TestTranscriptionResultFailureFactory:
    def test_failure_result_error(self):
        r = TranscriptionResult.failure_result("API error")
        assert r.error == "API error"

    def test_failure_result_success_false(self):
        r = TranscriptionResult.failure_result("error")
        assert r.success is False

    def test_failure_result_text_empty(self):
        r = TranscriptionResult.failure_result("error")
        assert r.text == ""

    def test_failure_result_with_extra_kwargs(self):
        r = TranscriptionResult.failure_result("error", confidence=None)
        assert r.confidence is None

    def test_failure_result_returns_transcription_result(self):
        assert isinstance(TranscriptionResult.failure_result("x"), TranscriptionResult)


# ===========================================================================
# BaseSTTProvider — initialization
# ===========================================================================

class TestBaseSTTProviderInit:
    def test_api_key_stored(self):
        stt = _StubSTT(api_key="key123")
        assert stt.api_key == "key123"

    def test_language_stored(self):
        stt = _StubSTT(language="fr-FR")
        assert stt.language == "fr-FR"

    def test_default_api_key_empty(self):
        stt = _StubSTT()
        assert stt.api_key == ""

    def test_default_language_en_us(self):
        stt = _StubSTT()
        assert stt.language == "en-US"

    def test_provider_name_from_stub(self):
        stt = _StubSTT()
        assert stt.provider_name == "stub"


# ===========================================================================
# Default property values
# ===========================================================================

class TestBaseSTTProviderProperties:
    def test_supports_diarization_false_by_default(self):
        assert _StubSTT().supports_diarization is False

    def test_requires_api_key_true_by_default(self):
        assert _StubSTT().requires_api_key is True

    def test_is_configured_true_when_has_key(self):
        stt = _StubSTT(api_key="sk-abc123")
        assert stt.is_configured is True

    def test_is_configured_false_when_no_key(self):
        stt = _StubSTT(api_key="")
        assert stt.is_configured is False

    def test_no_key_provider_is_configured_without_key(self):
        stt = _NoKeySTT(api_key="")
        assert stt.is_configured is True

    def test_no_key_provider_requires_api_key_false(self):
        stt = _NoKeySTT()
        assert stt.requires_api_key is False


# ===========================================================================
# _check_api_key
# ===========================================================================

class TestCheckApiKey:
    def test_returns_true_with_key(self):
        stt = _StubSTT(api_key="valid_key")
        assert stt._check_api_key() is True

    def test_returns_false_without_key(self):
        stt = _StubSTT(api_key="")
        assert stt._check_api_key() is False

    def test_whitespace_only_key_is_truthy(self):
        stt = _StubSTT(api_key="   ")
        # Non-empty string is truthy in Python
        assert stt._check_api_key() is True


# ===========================================================================
# test_connection (base implementation)
# ===========================================================================

class TestBaseTestConnection:
    def test_returns_true_with_key(self):
        stt = _StubSTT(api_key="some_key")
        assert stt.test_connection() is True

    def test_returns_false_without_key_when_required(self):
        stt = _StubSTT(api_key="")
        assert stt.test_connection() is False

    def test_no_key_provider_returns_true_without_key(self):
        stt = _NoKeySTT(api_key="")
        assert stt.test_connection() is True


# ===========================================================================
# __repr__
# ===========================================================================

class TestBaseRepr:
    def test_returns_string(self):
        stt = _StubSTT(api_key="key")
        assert isinstance(repr(stt), str)

    def test_contains_class_name(self):
        stt = _StubSTT(api_key="key")
        assert "_StubSTT" in repr(stt)

    def test_contains_provider_name(self):
        stt = _StubSTT(api_key="key")
        assert "stub" in repr(stt)

    def test_configured_when_has_key(self):
        stt = _StubSTT(api_key="key")
        assert "configured" in repr(stt)

    def test_not_configured_when_no_key(self):
        stt = _StubSTT(api_key="")
        assert "not configured" in repr(stt)
