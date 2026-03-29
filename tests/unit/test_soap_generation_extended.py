"""Extended tests for soap_generation.py critical paths.

Covers _prepare_soap_generation(), _postprocess_soap_result(),
_validate_soap_output() warning branches, create_soap_note_streaming(),
and create_soap_note_with_openai() using mocked AI dependencies.
"""

import pytest
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_ai_result(text: str = "SOAP note output"):
    """Return a mock AIResult-like object."""
    result = MagicMock()
    result.text = text
    return result


def _make_settings(model="gpt-4", icd_version="ICD-10", temperature=0.4,
                   system_message="", provider="openai", **soap_overrides):
    soap = {
        "model": model,
        "icd_code_version": icd_version,
        "temperature": temperature,
        "system_message": system_message,
    }
    soap.update(soap_overrides)
    return {"soap_note": soap, "ai_provider": provider}


# ── _prepare_soap_generation ──────────────────────────────────────────────────

class TestPrepareSoapGeneration:
    """Tests for _prepare_soap_generation() parameter preparation."""

    @patch("ai.soap_generation.settings_manager")
    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="System message")
    def test_returns_four_tuple(self, mock_sys_msg, mock_sanitize, mock_settings):
        mock_settings.get_all.return_value = _make_settings()
        from ai.soap_generation import _prepare_soap_generation
        result = _prepare_soap_generation("Transcript text", "")
        assert len(result) == 4

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_uses_model_from_settings(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings(model="claude-3-opus")
        from ai.soap_generation import _prepare_soap_generation
        model, _, _, _ = _prepare_soap_generation("Text", "", settings=settings)
        assert model == "claude-3-opus"

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Dynamic sys")
    def test_custom_system_message_overrides_default(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings(system_message="My custom system")
        from ai.soap_generation import _prepare_soap_generation
        _, system_message, _, _ = _prepare_soap_generation("Text", "", settings=settings)
        assert system_message == "My custom system"

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Dynamic sys")
    def test_empty_custom_message_uses_dynamic(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings(system_message="")
        from ai.soap_generation import _prepare_soap_generation
        _, system_message, _, _ = _prepare_soap_generation("Text", "", settings=settings)
        assert system_message == "Dynamic sys"

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_temperature_from_settings(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings(temperature=0.7)
        from ai.soap_generation import _prepare_soap_generation
        _, _, _, temperature = _prepare_soap_generation("Text", "", settings=settings)
        assert temperature == 0.7

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_prompt_includes_transcript(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings()
        from ai.soap_generation import _prepare_soap_generation
        _, _, full_prompt, _ = _prepare_soap_generation("Patient reports chest pain", "", settings=settings)
        assert "Patient reports chest pain" in full_prompt

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_context_included_in_prompt(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings()
        from ai.soap_generation import _prepare_soap_generation
        _, _, full_prompt, _ = _prepare_soap_generation("Transcript", "Previous visit notes", settings=settings)
        assert "Previous visit notes" in full_prompt

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_long_context_truncated(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings()
        long_context = "A" * 10000  # Over the 8000 char limit
        from ai.soap_generation import _prepare_soap_generation
        _, _, full_prompt, _ = _prepare_soap_generation("Transcript", long_context, settings=settings)
        assert "...[truncated]" in full_prompt

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_emotion_context_included(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings()
        from ai.soap_generation import _prepare_soap_generation
        _, _, full_prompt, _ = _prepare_soap_generation(
            "Transcript", "", emotion_context="Patient sounded anxious", settings=settings
        )
        assert "Patient sounded anxious" in full_prompt

    @patch("ai.soap_generation.settings_manager")
    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_uses_global_settings_when_none_provided(self, mock_sys_msg, mock_sanitize, mock_settings):
        mock_settings.get_all.return_value = _make_settings()
        from ai.soap_generation import _prepare_soap_generation
        result = _prepare_soap_generation("Text", "")  # No settings argument
        assert len(result) == 4
        mock_settings.get_all.assert_called()

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_provider_specific_system_message(self, mock_sys_msg, mock_sanitize):
        """Provider-specific message takes precedence over generic."""
        settings = _make_settings()
        settings["soap_note"]["openai_system_message"] = "OpenAI-specific system"
        from ai.soap_generation import _prepare_soap_generation
        _, system_message, _, _ = _prepare_soap_generation("Text", "", settings=settings)
        assert system_message == "OpenAI-specific system"

    @patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x)
    @patch("ai.soap_generation.get_soap_system_message", return_value="Sys")
    def test_sanitize_called_on_text_and_context(self, mock_sys_msg, mock_sanitize):
        settings = _make_settings()
        from ai.soap_generation import _prepare_soap_generation
        _prepare_soap_generation("My transcript", "context data", settings=settings)
        mock_sanitize.assert_called()


# ── _postprocess_soap_result ──────────────────────────────────────────────────

class TestPostprocessSoapResult:
    """Tests for _postprocess_soap_result() cleaning and synopsis logic."""

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_returns_string(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.return_value = ""
        from ai.soap_generation import _postprocess_soap_result
        result = _postprocess_soap_result("SOAP text", "")
        assert isinstance(result, str)

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_synopsis_appended_when_missing(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.return_value = "Patient hypertension summary"
        from ai.soap_generation import _postprocess_soap_result
        result = _postprocess_soap_result("Subjective: Pain\nObjective: BP 140/90", "")
        assert "Patient hypertension summary" in result

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_synopsis_not_added_when_already_present(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.return_value = "Extra synopsis"
        from ai.soap_generation import _postprocess_soap_result
        soap_with_synopsis = "Subjective: Pain\nClinical Synopsis:\n- BP controlled"
        _postprocess_soap_result(soap_with_synopsis, "")
        mock_am.generate_synopsis.assert_not_called()

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_on_chunk_callback_called_with_synopsis(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.return_value = "Synopsis text"
        chunks = []
        from ai.soap_generation import _postprocess_soap_result
        _postprocess_soap_result("SOAP body", "", on_chunk=chunks.append)
        assert any("Synopsis text" in c for c in chunks)

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_synopsis_exception_handled_gracefully(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.side_effect = Exception("Agent unavailable")
        from ai.soap_generation import _postprocess_soap_result
        result = _postprocess_soap_result("SOAP body", "")
        assert isinstance(result, str)

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_empty_synopsis_not_appended(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.return_value = ""
        from ai.soap_generation import _postprocess_soap_result
        result = _postprocess_soap_result("SOAP body without synopsis", "")
        assert "Clinical Synopsis:" not in result

    @patch("ai.soap_generation.clean_text", side_effect=lambda x: x)
    @patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x)
    @patch("managers.agent_manager.agent_manager")
    def test_clean_text_called(self, mock_am, mock_format, mock_clean):
        mock_am.generate_synopsis.return_value = ""
        from ai.soap_generation import _postprocess_soap_result
        _postprocess_soap_result("Raw SOAP text", "")
        mock_clean.assert_called_once_with("Raw SOAP text")


# ── _validate_soap_output — warning branches ──────────────────────────────────

class TestValidateSoapOutputWarnings:
    """Tests for ICD code warning paths in _validate_soap_output()."""

    def test_returns_tuple(self):
        from ai.soap_generation import _validate_soap_output
        soap, warnings = _validate_soap_output("No ICD codes here")
        assert isinstance(soap, str)
        assert isinstance(warnings, list)

    def test_empty_text_returns_no_warnings(self):
        from ai.soap_generation import _validate_soap_output
        soap, warnings = _validate_soap_output("")
        assert warnings == []

    @patch("ai.soap_generation.extract_icd_codes", return_value=["INVALID"])
    @patch("ai.soap_generation.validate_code")
    def test_invalid_icd_code_produces_warning(self, mock_validate, mock_extract):
        result_mock = MagicMock()
        result_mock.is_valid = False
        result_mock.warning = "bad format"
        result_mock.description = None
        mock_validate.return_value = result_mock
        from ai.soap_generation import _validate_soap_output
        _, warnings = _validate_soap_output("Assessment: ICD INVALID")
        assert len(warnings) == 1
        assert "INVALID" in warnings[0]

    @patch("ai.soap_generation.extract_icd_codes", return_value=["Z99.9"])
    @patch("ai.soap_generation.validate_code")
    def test_valid_format_but_no_description_produces_warning(self, mock_validate, mock_extract):
        result_mock = MagicMock()
        result_mock.is_valid = True
        result_mock.warning = None
        result_mock.description = None  # No description → warning
        mock_validate.return_value = result_mock
        from ai.soap_generation import _validate_soap_output
        _, warnings = _validate_soap_output("Assessment: Z99.9")
        assert len(warnings) == 1
        assert "verify" in warnings[0].lower()

    @patch("ai.soap_generation.extract_icd_codes", return_value=["I10"])
    @patch("ai.soap_generation.validate_code")
    def test_valid_code_with_description_no_warning(self, mock_validate, mock_extract):
        result_mock = MagicMock()
        result_mock.is_valid = True
        result_mock.warning = None
        result_mock.description = "Essential hypertension"
        mock_validate.return_value = result_mock
        from ai.soap_generation import _validate_soap_output
        _, warnings = _validate_soap_output("Assessment: I10 Essential hypertension")
        assert warnings == []

    def test_soap_text_unchanged(self):
        from ai.soap_generation import _validate_soap_output
        original = "Subjective: Patient reports pain"
        returned_soap, _ = _validate_soap_output(original)
        assert returned_soap == original

    @patch("ai.soap_generation.extract_icd_codes", return_value=["INVALID"])
    @patch("ai.soap_generation.validate_code")
    def test_invalid_code_warning_contains_code_name(self, mock_validate, mock_extract):
        result_mock = MagicMock()
        result_mock.is_valid = False
        result_mock.warning = None
        result_mock.description = None
        mock_validate.return_value = result_mock
        from ai.soap_generation import _validate_soap_output
        _, warnings = _validate_soap_output("INVALID code text")
        assert "INVALID" in warnings[0]


# ── create_soap_note_streaming ────────────────────────────────────────────────

class TestCreateSoapNoteStreaming:
    """Tests for the streaming SOAP note generation entrypoint."""

    def _patches(self):
        return [
            patch("ai.soap_generation.settings_manager"),
            patch("ai.soap_generation.call_ai_streaming"),
            patch("ai.soap_generation.call_ai"),
            patch("ai.soap_generation.clean_text", side_effect=lambda x: x),
            patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x),
            patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x),
            patch("ai.soap_generation.get_soap_system_message", return_value="Sys"),
            patch("managers.agent_manager.agent_manager"),
            patch("ai.soap_generation.extract_icd_codes", return_value=[]),
        ]

    def test_returns_tuple(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai_streaming") as mock_stream, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_stream.return_value = _make_ai_result("SOAP streaming output")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_streaming
            result = create_soap_note_streaming("Transcript", on_chunk=lambda c: None)
            assert len(result) == 2  # (soap_text, icd_warnings)

    def test_uses_streaming_when_callback_provided(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai_streaming") as mock_stream, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_stream.return_value = _make_ai_result("Streaming result")
            mock_am.generate_synopsis.return_value = ""
            chunks = []
            from ai.soap_generation import create_soap_note_streaming
            create_soap_note_streaming("Text", on_chunk=chunks.append)
            mock_stream.assert_called_once()
            mock_call_ai.assert_not_called()

    def test_falls_back_to_non_streaming_when_no_callback(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai_streaming") as mock_stream, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_call_ai.return_value = _make_ai_result("Non-streaming result")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_streaming
            create_soap_note_streaming("Text")  # No on_chunk
            mock_call_ai.assert_called_once()
            mock_stream.assert_not_called()

    def test_result_text_from_ai_result(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai_streaming") as mock_stream, \
             patch("ai.soap_generation.call_ai"), \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_stream.return_value = _make_ai_result("Extracted SOAP text")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_streaming
            soap_text, _ = create_soap_note_streaming("Text", on_chunk=lambda c: None)
            assert "Extracted SOAP text" in soap_text


# ── create_soap_note_with_openai ──────────────────────────────────────────────

class TestCreateSoapNoteWithOpenAI:
    """Tests for the non-streaming SOAP note generation entrypoint."""

    def test_returns_tuple(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_call_ai.return_value = _make_ai_result("SOAP output")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_with_openai
            result = create_soap_note_with_openai("Transcript")
            assert len(result) == 2  # (soap_text, warnings)

    def test_calls_call_ai(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_call_ai.return_value = _make_ai_result("Output")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_with_openai
            create_soap_note_with_openai("Transcript")
            mock_call_ai.assert_called_once()

    def test_soap_text_in_result(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_call_ai.return_value = _make_ai_result("Hypertension SOAP note")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_with_openai
            soap_text, _ = create_soap_note_with_openai("Patient with hypertension")
            assert "Hypertension SOAP note" in soap_text

    def test_icd_warnings_returned(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_call_ai.return_value = _make_ai_result("SOAP text")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_with_openai
            _, icd_warnings = create_soap_note_with_openai("Transcript")
            assert isinstance(icd_warnings, list)

    def test_with_emotion_context(self):
        with patch("ai.soap_generation.settings_manager") as mock_sm, \
             patch("ai.soap_generation.call_ai") as mock_call_ai, \
             patch("ai.soap_generation.clean_text", side_effect=lambda x: x), \
             patch("ai.soap_generation.format_soap_paragraphs", side_effect=lambda x: x), \
             patch("ai.soap_generation.sanitize_prompt", side_effect=lambda x: x), \
             patch("ai.soap_generation.get_soap_system_message", return_value="Sys"), \
             patch("managers.agent_manager.agent_manager") as mock_am, \
             patch("ai.soap_generation.extract_icd_codes", return_value=[]):
            mock_sm.get_all.return_value = _make_settings()
            mock_call_ai.return_value = _make_ai_result("SOAP")
            mock_am.generate_synopsis.return_value = ""
            from ai.soap_generation import create_soap_note_with_openai
            result = create_soap_note_with_openai("Transcript", emotion_context="Anxious")
            assert len(result) == 2
