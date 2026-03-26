"""Unit tests for ai.letter_generation module."""

import sys
import pytest
from unittest.mock import Mock, patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ai_result(text: str):
    """Create a mock AIResult with the given text."""
    result = Mock()
    result.text = text
    result.is_success = True
    return result


# ===========================================================================
# create_referral_with_openai
# ===========================================================================

class TestCreateReferralWithOpenai:
    """Tests for create_referral_with_openai."""

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_happy_path_no_conditions(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_referral_with_openai

        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("Referral letter text")

        result = create_referral_with_openai("SOAP note here")

        assert result == "Referral letter text"
        mock_call_ai.assert_called_once()
        args = mock_call_ai.call_args
        assert "SOAP Note given to you" in args[0][2]
        assert args[0][1] == "You are a physician writing referral letters to other physicians. Be concise but thorough."
        assert args[0][3] == 0.7

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_happy_path_with_conditions(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_referral_with_openai

        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("Focused referral")

        result = create_referral_with_openai("note text", conditions="diabetes, HTN")

        assert result == "Focused referral"
        prompt_arg = mock_call_ai.call_args[0][2]
        assert "diabetes, HTN" in prompt_arg
        assert "focusing specifically on these conditions" in prompt_arg

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_uses_configured_model(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_referral_with_openai

        mock_sm.get_nested.return_value = "claude-3-opus"
        mock_call_ai.return_value = _make_ai_result("text")

        create_referral_with_openai("note")

        assert mock_call_ai.call_args[0][0] == "claude-3-opus"

    @patch("ai.letter_generation.call_ai", side_effect=Exception("API timeout"))
    @patch("ai.letter_generation.settings_manager")
    def test_error_returns_error_string(self, mock_sm, mock_call_ai):
        from ai.letter_generation import create_referral_with_openai

        mock_sm.get_nested.return_value = "gpt-4"

        result = create_referral_with_openai("note")

        assert "[Error:" in result
        assert "API timeout" in result or "Failed to create referral" in result

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_empty_text_input(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_referral_with_openai

        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("")

        result = create_referral_with_openai("")
        assert result == ""

    @patch("ai.letter_generation.clean_text")
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_clean_text_called_without_remove_citations(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_referral_with_openai

        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("raw text")
        mock_clean.return_value = "cleaned"

        result = create_referral_with_openai("note")

        mock_clean.assert_called_once_with("raw text", remove_citations=False)
        assert result == "cleaned"


# ===========================================================================
# get_possible_conditions
# ===========================================================================

class TestGetPossibleConditions:
    """Tests for get_possible_conditions."""

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_happy_path(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import get_possible_conditions

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("Diabetes, Hypertension, COPD")

        result = get_possible_conditions("Patient has diabetes and high blood pressure")

        assert "Diabetes" in result
        assert "Hypertension" in result
        mock_call_ai.assert_called_once()

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    def test_uses_configured_provider_model(self, mock_call_ai, mock_clean):
        from ai.letter_generation import get_possible_conditions
        sm_mod = sys.modules['settings.settings_manager']

        mock_sm = Mock()
        mock_sm.get_ai_provider.return_value = "anthropic"
        mock_sm.get_nested.return_value = "claude-3-opus"
        mock_call_ai.return_value = _make_ai_result("Condition A")

        with patch.object(sm_mod, 'settings_manager', mock_sm):
            get_possible_conditions("text")

        assert mock_call_ai.call_args[0][0] == "claude-3-opus"
        mock_sm.get_nested.assert_called_with("anthropic.model", "gpt-4")

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_prompt_includes_source_text(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import get_possible_conditions

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("Condition")

        get_possible_conditions("My specific clinical text")

        prompt = mock_call_ai.call_args[0][2]
        assert "My specific clinical text" in prompt
        assert "comma-separated" in prompt

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_empty_text(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import get_possible_conditions

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.return_value = "gpt-4"
        mock_call_ai.return_value = _make_ai_result("")

        result = get_possible_conditions("")
        assert result == ""

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai", side_effect=Exception("Network error"))
    @patch("ai.letter_generation.settings_manager")
    def test_exception_propagates(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import get_possible_conditions

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.return_value = "gpt-4"

        with pytest.raises(Exception, match="Network error"):
            get_possible_conditions("text")


# ===========================================================================
# _get_recipient_guidance
# ===========================================================================

class TestGetRecipientGuidance:
    """Tests for _get_recipient_guidance."""

    def test_known_recipient_types(self):
        from ai.letter_generation import _get_recipient_guidance

        known_types = ["insurance", "employer", "specialist", "patient",
                       "school", "legal", "government", "other"]

        for rtype in known_types:
            guidance = _get_recipient_guidance(rtype)
            assert "focus" in guidance
            assert "exclude" in guidance
            assert "tone" in guidance
            assert "format" in guidance
            assert isinstance(guidance["focus"], list)
            assert isinstance(guidance["exclude"], list)
            assert len(guidance["focus"]) > 0

    def test_unknown_type_falls_back_to_other(self):
        from ai.letter_generation import _get_recipient_guidance

        guidance = _get_recipient_guidance("unknown_type")
        other_guidance = _get_recipient_guidance("other")
        assert guidance == other_guidance

    def test_insurance_has_medical_necessity(self):
        from ai.letter_generation import _get_recipient_guidance

        guidance = _get_recipient_guidance("insurance")
        focus_text = " ".join(guidance["focus"])
        assert "medical necessity" in focus_text.lower() or "Medical necessity" in focus_text

    def test_employer_excludes_detailed_diagnosis(self):
        from ai.letter_generation import _get_recipient_guidance

        guidance = _get_recipient_guidance("employer")
        exclude_text = " ".join(guidance["exclude"])
        assert "diagnosis" in exclude_text.lower()

    def test_patient_tone_is_warm(self):
        from ai.letter_generation import _get_recipient_guidance

        guidance = _get_recipient_guidance("patient")
        assert "warm" in guidance["tone"].lower() or "Warm" in guidance["tone"]

    def test_legal_tone_is_objective(self):
        from ai.letter_generation import _get_recipient_guidance

        guidance = _get_recipient_guidance("legal")
        assert "objective" in guidance["tone"].lower()


# ===========================================================================
# _build_letter_prompt
# ===========================================================================

class TestBuildLetterPrompt:
    """Tests for _build_letter_prompt."""

    def test_includes_clinical_text(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("Patient has diabetes", "other", "")
        assert "Patient has diabetes" in prompt

    def test_includes_recipient_display_name(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("text", "insurance", "")
        assert "Insurance Company" in prompt

    def test_includes_specs_when_provided(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("text", "other", "Include ICD codes")
        assert "Include ICD codes" in prompt
        assert "ADDITIONAL INSTRUCTIONS" in prompt

    def test_excludes_specs_section_when_empty(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("text", "other", "")
        assert "ADDITIONAL INSTRUCTIONS" not in prompt

    def test_excludes_specs_section_when_whitespace(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("text", "other", "   ")
        assert "ADDITIONAL INSTRUCTIONS" not in prompt

    def test_includes_guidance_focus_items(self):
        from ai.letter_generation import _build_letter_prompt, _get_recipient_guidance

        guidance = _get_recipient_guidance("specialist")
        prompt = _build_letter_prompt("text", "specialist", "")
        for item in guidance["focus"]:
            assert item in prompt

    def test_includes_guidance_exclude_items(self):
        from ai.letter_generation import _build_letter_prompt, _get_recipient_guidance

        guidance = _get_recipient_guidance("specialist")
        prompt = _build_letter_prompt("text", "specialist", "")
        for item in guidance["exclude"]:
            assert item in prompt

    def test_includes_tone_and_format(self):
        from ai.letter_generation import _build_letter_prompt, _get_recipient_guidance

        guidance = _get_recipient_guidance("patient")
        prompt = _build_letter_prompt("text", "patient", "")
        assert guidance["tone"] in prompt
        assert guidance["format"] in prompt

    def test_unknown_recipient_type_uses_other_display(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("text", "alien", "")
        assert "the recipient" in prompt

    def test_all_known_recipient_display_names(self):
        from ai.letter_generation import _build_letter_prompt

        expected = {
            "insurance": "Insurance Company",
            "employer": "Employer/Workplace",
            "specialist": "Specialist Colleague",
            "patient": "the Patient",
            "school": "School/Educational Institution",
            "legal": "Legal Counsel/Attorney",
            "government": "Government Agency",
        }
        for rtype, display_fragment in expected.items():
            prompt = _build_letter_prompt("text", rtype, "")
            assert display_fragment in prompt, f"Missing '{display_fragment}' for type '{rtype}'"

    def test_formatting_instructions_present(self):
        from ai.letter_generation import _build_letter_prompt

        prompt = _build_letter_prompt("text", "other", "")
        assert "date" in prompt.lower()
        assert "signature" in prompt.lower()


# ===========================================================================
# _get_letter_system_message
# ===========================================================================

class TestGetLetterSystemMessage:
    """Tests for _get_letter_system_message."""

    def test_base_message_always_present(self):
        from ai.letter_generation import _get_letter_system_message

        for rtype in ["insurance", "employer", "specialist", "patient",
                      "school", "legal", "government", "other", "unknown"]:
            msg = _get_letter_system_message(rtype)
            assert "expert medical professional" in msg
            assert "RECIPIENT-FOCUSED CONTENT" in msg

    def test_insurance_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("insurance")
        assert "INSURANCE" in msg
        assert "medical necessity" in msg.lower()

    def test_employer_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("employer")
        assert "EMPLOYER" in msg
        assert "functional capacity" in msg.lower()

    def test_specialist_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("specialist")
        assert "SPECIALIST" in msg

    def test_patient_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("patient")
        assert "PATIENT" in msg
        assert "simple language" in msg.lower() or "jargon" in msg.lower()

    def test_school_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("school")
        assert "SCHOOL" in msg
        assert "educational" in msg.lower()

    def test_legal_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("legal")
        assert "LEGAL" in msg
        assert "objective" in msg.lower()

    def test_government_specific_content(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("government")
        assert "GOVERNMENT" in msg or "DISABILITY" in msg

    def test_unknown_type_gets_generic_message(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("unknown")
        assert "Tailor content appropriately" in msg

    def test_other_type_gets_generic_message(self):
        from ai.letter_generation import _get_letter_system_message

        msg = _get_letter_system_message("other")
        assert "Tailor content appropriately" in msg


# ===========================================================================
# create_letter_with_ai
# ===========================================================================

class TestCreateLetterWithAi:
    """Tests for create_letter_with_ai."""

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_happy_path(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_with_ai

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: {
            "openai.model": "gpt-4",
            "letter.temperature": 0.7,
        }.get(key, default)
        mock_call_ai.return_value = _make_ai_result("Dear Doctor, ...")

        result = create_letter_with_ai("SOAP note", "specialist", "Be brief")

        assert result == "Dear Doctor, ..."
        mock_call_ai.assert_called_once()

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    def test_uses_configured_model_and_temperature(self, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_with_ai
        sm_mod = sys.modules['settings.settings_manager']

        mock_sm = Mock()
        mock_sm.get_ai_provider.return_value = "anthropic"
        mock_sm.get_nested.side_effect = lambda key, default: {
            "anthropic.model": "claude-3-sonnet",
            "letter.temperature": 0.5,
        }.get(key, default)
        mock_call_ai.return_value = _make_ai_result("letter")

        with patch.object(sm_mod, 'settings_manager', mock_sm):
            create_letter_with_ai("text")

        call_args = mock_call_ai.call_args[0]
        assert call_args[0] == "claude-3-sonnet"
        assert call_args[3] == 0.5

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_default_recipient_type_is_other(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_with_ai

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_ai.return_value = _make_ai_result("letter")

        create_letter_with_ai("text")

        # The system message should use the "other" type
        system_msg = mock_call_ai.call_args[0][1]
        assert "Tailor content appropriately" in system_msg

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_passes_recipient_type_to_prompt_and_system_msg(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_with_ai

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_ai.return_value = _make_ai_result("letter")

        create_letter_with_ai("text", "insurance", "Urgent")

        system_msg = mock_call_ai.call_args[0][1]
        prompt = mock_call_ai.call_args[0][2]
        assert "INSURANCE" in system_msg
        assert "Insurance Company" in prompt
        assert "Urgent" in prompt

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai", side_effect=Exception("Timeout"))
    @patch("ai.letter_generation.settings_manager")
    def test_exception_propagates(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_with_ai

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default

        with pytest.raises(Exception, match="Timeout"):
            create_letter_with_ai("text")


# ===========================================================================
# create_letter_streaming
# ===========================================================================

class TestCreateLetterStreaming:
    """Tests for create_letter_streaming."""

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai_streaming")
    @patch("ai.letter_generation.settings_manager")
    def test_with_on_chunk_callback(self, mock_sm, mock_call_streaming, mock_clean):
        from ai.letter_generation import create_letter_streaming

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_streaming.return_value = _make_ai_result("Streamed letter")

        callback = Mock()
        result = create_letter_streaming("text", "patient", "specs", on_chunk=callback)

        assert result == "Streamed letter"
        mock_call_streaming.assert_called_once()
        # Verify callback was passed to call_ai_streaming
        assert mock_call_streaming.call_args[0][4] is callback

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_without_on_chunk_uses_non_streaming(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_streaming

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_ai.return_value = _make_ai_result("Non-streamed letter")

        result = create_letter_streaming("text", "specialist")

        assert result == "Non-streamed letter"
        mock_call_ai.assert_called_once()

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai")
    @patch("ai.letter_generation.settings_manager")
    def test_none_callback_uses_non_streaming(self, mock_sm, mock_call_ai, mock_clean):
        from ai.letter_generation import create_letter_streaming

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_ai.return_value = _make_ai_result("letter")

        result = create_letter_streaming("text", on_chunk=None)

        assert result == "letter"
        mock_call_ai.assert_called_once()

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai_streaming")
    def test_uses_configured_model_and_temperature(self, mock_call_streaming, mock_clean):
        from ai.letter_generation import create_letter_streaming
        sm_mod = sys.modules['settings.settings_manager']

        mock_sm = Mock()
        mock_sm.get_ai_provider.return_value = "anthropic"
        mock_sm.get_nested.side_effect = lambda key, default: {
            "anthropic.model": "claude-3-haiku",
            "letter.temperature": 0.3,
        }.get(key, default)
        mock_call_streaming.return_value = _make_ai_result("letter")

        with patch.object(sm_mod, 'settings_manager', mock_sm):
            create_letter_streaming("text", on_chunk=Mock())

        call_args = mock_call_streaming.call_args[0]
        assert call_args[0] == "claude-3-haiku"
        assert call_args[3] == 0.3

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai_streaming")
    @patch("ai.letter_generation.settings_manager")
    def test_recipient_type_and_specs_passed_through(self, mock_sm, mock_call_streaming, mock_clean):
        from ai.letter_generation import create_letter_streaming

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_streaming.return_value = _make_ai_result("letter")

        create_letter_streaming("text", "legal", "Include timeline", on_chunk=Mock())

        system_msg = mock_call_streaming.call_args[0][1]
        prompt = mock_call_streaming.call_args[0][2]
        assert "LEGAL" in system_msg
        assert "Legal Counsel" in prompt
        assert "Include timeline" in prompt

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai_streaming", side_effect=Exception("Stream error"))
    @patch("ai.letter_generation.settings_manager")
    def test_exception_propagates(self, mock_sm, mock_call_streaming, mock_clean):
        from ai.letter_generation import create_letter_streaming

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default

        with pytest.raises(Exception, match="Stream error"):
            create_letter_streaming("text", on_chunk=Mock())

    @patch("ai.letter_generation.clean_text", side_effect=lambda t, **kw: t)
    @patch("ai.letter_generation.call_ai_streaming")
    @patch("ai.letter_generation.settings_manager")
    def test_default_params(self, mock_sm, mock_call_streaming, mock_clean):
        """Test that defaults for recipient_type and specs work correctly."""
        from ai.letter_generation import create_letter_streaming

        mock_sm.get_ai_provider.return_value = "openai"
        mock_sm.get_nested.side_effect = lambda key, default: default
        mock_call_streaming.return_value = _make_ai_result("letter")

        callback = Mock()
        create_letter_streaming("text", on_chunk=callback)

        system_msg = mock_call_streaming.call_args[0][1]
        prompt = mock_call_streaming.call_args[0][2]
        assert "Tailor content appropriately" in system_msg
        assert "ADDITIONAL INSTRUCTIONS" not in prompt
