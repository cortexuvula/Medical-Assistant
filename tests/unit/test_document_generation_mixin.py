"""
Tests for src/processing/document_generation_mixin.py

Covers DocumentGenerationMixin: _generate_soap_note, _generate_referral,
and _generate_letter — focuses on exception isolation (each method returns
None on any error and never propagates).
All AI/agent calls are mocked.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from processing.document_generation_mixin import DocumentGenerationMixin
from utils.exceptions import APIError, APITimeoutError


# ---------------------------------------------------------------------------
# Minimal concrete subclass
# ---------------------------------------------------------------------------

class _DocGen(DocumentGenerationMixin):
    pass


# ===========================================================================
# _generate_soap_note
# ===========================================================================

class TestGenerateSoapNote:
    def _make(self):
        return _DocGen()

    def _patch_soap(self, return_value=("SOAP text", []), side_effect=None):
        """Patch create_soap_note_with_openai and settings_manager."""
        return patch.multiple(
            "processing.document_generation_mixin",
            settings_manager=MagicMock(
                get_ai_provider=MagicMock(return_value="openai"),
                get_nested=MagicMock(return_value="gpt-4"),
            ),
        )

    def test_returns_soap_note_on_success(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", return_value=("SOAP", [])):
            result = g._generate_soap_note("transcript")
        assert result == "SOAP"

    def test_returns_none_on_api_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", side_effect=APIError("fail")):
            result = g._generate_soap_note("transcript")
        assert result is None

    def test_returns_none_on_api_timeout_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", side_effect=APITimeoutError("timeout")):
            result = g._generate_soap_note("transcript")
        assert result is None

    def test_returns_none_on_connection_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", side_effect=ConnectionError("no net")):
            result = g._generate_soap_note("transcript")
        assert result is None

    def test_returns_none_on_generic_exception(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", side_effect=RuntimeError("oops")):
            result = g._generate_soap_note("transcript")
        assert result is None

    def test_returns_none_on_timeout_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", side_effect=TimeoutError("timed out")):
            result = g._generate_soap_note("transcript")
        assert result is None

    def test_passes_context_to_soap_generator(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        mock_fn = MagicMock(return_value=("note", []))
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_soap_note_with_openai", mock_fn):
            g._generate_soap_note("transcript", context="annual visit")
        mock_fn.assert_called_once_with("transcript", "annual visit")


# ===========================================================================
# _generate_referral
# ===========================================================================

class TestGenerateReferral:
    def _make(self):
        return _DocGen()

    def _make_response(self, success=True, result="Referral text", error=None):
        resp = MagicMock()
        resp.success = success
        resp.result = result
        resp.error = error
        return resp

    def test_returns_referral_on_success(self):
        g = self._make()
        response = self._make_response(success=True, result="Refer to cardiologist")
        mock_am = MagicMock()
        mock_am.execute_agent_task.return_value = response
        with patch("managers.agent_manager.agent_manager", mock_am):
            result = g._generate_referral("SOAP note text")
        assert result == "Refer to cardiologist"

    def test_returns_none_when_response_is_none(self):
        g = self._make()
        mock_am = MagicMock()
        mock_am.execute_agent_task.return_value = None
        with patch("managers.agent_manager.agent_manager", mock_am):
            result = g._generate_referral("SOAP note")
        assert result is None

    def test_returns_none_when_success_is_false(self):
        g = self._make()
        response = self._make_response(success=False, result=None, error="Agent failed")
        mock_am = MagicMock()
        mock_am.execute_agent_task.return_value = response
        with patch("managers.agent_manager.agent_manager", mock_am):
            result = g._generate_referral("SOAP note")
        assert result is None

    def test_returns_none_when_result_is_none(self):
        g = self._make()
        response = self._make_response(success=True, result=None)
        mock_am = MagicMock()
        mock_am.execute_agent_task.return_value = response
        with patch("managers.agent_manager.agent_manager", mock_am):
            result = g._generate_referral("SOAP note")
        assert result is None

    def test_returns_none_on_exception(self):
        g = self._make()
        mock_am = MagicMock()
        mock_am.execute_agent_task.side_effect = RuntimeError("crash")
        with patch("managers.agent_manager.agent_manager", mock_am):
            result = g._generate_referral("SOAP note")
        assert result is None


# ===========================================================================
# _generate_letter
# ===========================================================================

class TestGenerateLetter:
    def _make(self):
        return _DocGen()

    def test_returns_letter_on_success(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", return_value="Dear Dr. Smith..."):
            result = g._generate_letter("content", "specialist")
        assert result == "Dear Dr. Smith..."

    def test_returns_none_on_api_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", side_effect=APIError("fail")):
            result = g._generate_letter("content")
        assert result is None

    def test_returns_none_on_api_timeout_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", side_effect=APITimeoutError("timeout")):
            result = g._generate_letter("content")
        assert result is None

    def test_returns_none_on_connection_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", side_effect=ConnectionError("no net")):
            result = g._generate_letter("content")
        assert result is None

    def test_returns_none_on_generic_exception(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", side_effect=ValueError("unexpected")):
            result = g._generate_letter("content")
        assert result is None

    def test_returns_none_on_timeout_error(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", side_effect=TimeoutError("timed out")):
            result = g._generate_letter("content")
        assert result is None

    def test_passes_recipient_type_and_specs(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        mock_fn = MagicMock(return_value="letter")
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", mock_fn):
            g._generate_letter("content", "insurance", "be brief")
        mock_fn.assert_called_once_with("content", "insurance", "be brief")

    def test_default_recipient_type_is_other(self):
        g = self._make()
        sm = MagicMock(
            get_ai_provider=MagicMock(return_value="openai"),
            get_nested=MagicMock(return_value="gpt-4"),
        )
        mock_fn = MagicMock(return_value="letter")
        with patch("processing.document_generation_mixin.settings_manager", sm), \
             patch("ai.ai.create_letter_with_ai", mock_fn):
            g._generate_letter("content")
        args = mock_fn.call_args[0]
        assert args[1] == "other"
