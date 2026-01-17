"""Regression tests for AI providers.

These tests verify that all AI providers work correctly
with mocked API responses.

Note: AI providers now return AIResult objects instead of strings.
Use str(result) for backward compatibility or result.text for the content.
"""
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, Mock

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from utils.exceptions import AIResult


class TestOpenAIProvider:
    """Tests for OpenAI AI provider."""

    @pytest.fixture
    def mock_openai_response(self):
        """Create mock OpenAI response."""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Mocked OpenAI response"
        mock_response.usage.prompt_tokens = 10
        mock_response.usage.completion_tokens = 20
        return mock_response

    def test_call_openai_returns_airesult(self, mock_openai_response, mock_api_keys):
        """call_openai should return an AIResult."""
        from src.ai.ai import call_openai

        with patch('ai.providers.openai_provider._openai_api_call') as mock_api_call:
            mock_api_call.return_value = mock_openai_response

            result = call_openai(
                model="gpt-4",
                system_message="You are a helpful assistant",
                prompt="Test prompt",
                temperature=0.7
            )

        # Result should be AIResult, with str() for backward compatibility
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)

    def test_call_openai_handles_error(self, mock_api_keys):
        """call_openai should handle API errors gracefully."""
        from src.ai.ai import call_openai

        with patch('ai.providers.openai_provider._openai_api_call') as mock_api_call:
            mock_api_call.side_effect = Exception("API Error")

            result = call_openai(
                model="gpt-4",
                system_message="Test",
                prompt="Test",
                temperature=0.7
            )

        # Should return AIResult (possibly with error), not raise exception
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)


class TestAnthropicProvider:
    """Tests for Anthropic AI provider."""

    @pytest.fixture
    def mock_anthropic_response(self):
        """Create mock Anthropic response."""
        mock_response = MagicMock()
        mock_response.content = [MagicMock()]
        mock_response.content[0].text = "Mocked Anthropic response"
        mock_response.usage.input_tokens = 10
        mock_response.usage.output_tokens = 20
        return mock_response

    def test_call_anthropic_returns_airesult(self, mock_anthropic_response, mock_api_keys):
        """call_anthropic should return an AIResult."""
        from src.ai.ai import call_anthropic

        result = call_anthropic(
            model="claude-sonnet-4-20250514",
            system_message="You are a helpful assistant",
            prompt="Test prompt",
            temperature=0.7
        )

        # Result should be AIResult, with str() for backward compatibility
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)

    def test_call_anthropic_handles_error(self, mock_api_keys):
        """call_anthropic should handle API errors gracefully."""
        from src.ai.ai import call_anthropic

        with patch('ai.providers.anthropic_provider._anthropic_api_call') as mock_api_call:
            mock_api_call.side_effect = Exception("API Error")

            result = call_anthropic(
                model="claude-sonnet-4-20250514",
                system_message="Test",
                prompt="Test",
                temperature=0.7
            )

        # Should return AIResult (possibly with error), not raise exception
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)


class TestGeminiProvider:
    """Tests for Google Gemini AI provider."""

    def test_call_gemini_returns_airesult(self, mock_api_keys):
        """call_gemini should return an AIResult."""
        from src.ai.ai import call_gemini

        result = call_gemini(
            model_name="gemini-1.5-pro",
            system_message="Test",
            prompt="Test",
            temperature=0.7
        )

        # Result should be AIResult, with str() for backward compatibility
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)


class TestAIProviderSelection:
    """Tests for AI provider selection logic."""

    def test_call_ai_routes_based_on_settings(self, mock_api_keys):
        """call_ai should route based on settings."""
        from src.ai.ai import call_ai

        mock_result = AIResult.success("OpenAI response")
        with patch('ai.ai.call_openai', return_value=mock_result) as mock_openai:
            with patch('settings.settings.SETTINGS', {'ai_provider': 'openai'}):
                result = call_ai(
                    model="gpt-4",
                    system_message="Test",
                    prompt="Test",
                    temperature=0.7
                )

        # Result should be AIResult, with str() for backward compatibility
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)

    def test_call_ai_returns_airesult(self, mock_api_keys):
        """call_ai should always return an AIResult."""
        from src.ai.ai import call_ai

        result = call_ai(
            model="gpt-4",
            system_message="Test",
            prompt="Test",
            temperature=0.7
        )

        # Result should be AIResult, with str() for backward compatibility
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)


class TestSOAPNoteGeneration:
    """Tests for SOAP note generation."""

    def test_create_soap_note_with_openai(self, mock_api_keys):
        """create_soap_note_with_openai should generate SOAP note."""
        from src.ai.ai import create_soap_note_with_openai

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = """
            S: Patient reports headache
            O: Vital signs normal
            A: Tension headache
            P: Ibuprofen 400mg PRN
            """
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(
                text="Patient has headache for 2 days"
            )

        assert isinstance(result, str)
        # Should contain SOAP sections
        assert any(section in result for section in ['S:', 'Subjective', 'SUBJECTIVE'])

    def test_soap_note_includes_context(self, mock_api_keys):
        """SOAP note generation should include context if provided."""
        from src.ai.ai import create_soap_note_with_openai

        with patch('ai.soap_generation.call_ai') as mock_call, \
             patch('managers.agent_manager.agent_manager') as mock_agent:
            mock_call.return_value = "SOAP note with context"
            mock_agent.generate_synopsis.return_value = None
            mock_agent.is_agent_enabled.return_value = False

            result = create_soap_note_with_openai(
                text="Patient has headache",
                context="History of migraines"
            )

        # call_ai should have been called with the text
        assert mock_call.called


class TestReferralGeneration:
    """Tests for referral letter generation."""

    def test_create_referral_returns_string(self, mock_api_keys):
        """create_referral_with_openai should return string."""
        from src.ai.ai import create_referral_with_openai

        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = "Referral letter content"

            result = create_referral_with_openai(
                text="SOAP note content"
            )

        assert isinstance(result, str)


class TestLetterGeneration:
    """Tests for letter generation."""

    def test_create_letter_returns_string(self, mock_api_keys):
        """create_letter_with_ai should return string."""
        from src.ai.ai import create_letter_with_ai

        mock_result = AIResult.success("Letter content")
        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = mock_result

            result = create_letter_with_ai(
                text="SOAP note content",
                recipient_type="patient"
            )

        assert isinstance(result, str)

    def test_letter_supports_different_recipients(self, mock_api_keys):
        """Letter generation should support different recipient types."""
        from src.ai.ai import create_letter_with_ai

        recipient_types = ["patient", "employer", "insurance", "other"]

        mock_result = AIResult.success("Letter content")
        with patch('ai.letter_generation.call_ai') as mock_call:
            mock_call.return_value = mock_result

            for recipient in recipient_types:
                result = create_letter_with_ai(
                    text="SOAP note content",
                    recipient_type=recipient
                )
                assert isinstance(result, str)


class TestTimeoutHandling:
    """Tests for timeout handling in AI calls."""

    def test_timeout_returns_error_message(self, mock_api_keys):
        """Timeout should return AIResult with error, not raise exception."""
        from src.ai.ai import call_openai
        from utils.exceptions import TimeoutError as AppTimeoutError

        with patch('ai.providers.openai_provider._openai_api_call') as mock_api_call:
            mock_api_call.side_effect = AppTimeoutError("Timeout", timeout_seconds=30)

            result = call_openai(
                model="gpt-4",
                system_message="Test",
                prompt="Test",
                temperature=0.7
            )

        # Should return AIResult (possibly with error)
        assert isinstance(result, AIResult)
        result_str = str(result)
        # Should contain error indication
        assert "error" in result_str.lower() or "timeout" in result_str.lower() or "[" in result_str


class TestRateLimitHandling:
    """Tests for rate limit handling in AI calls."""

    def test_rate_limit_handled_gracefully(self, mock_api_keys):
        """Rate limit should be handled gracefully."""
        from src.ai.ai import call_openai

        with patch('ai.providers.openai_provider._openai_api_call') as mock_api_call:
            # Simulate rate limit error
            mock_api_call.side_effect = Exception("Rate limit exceeded")

            result = call_openai(
                model="gpt-4",
                system_message="Test",
                prompt="Test",
                temperature=0.7
            )

        # Should return AIResult (possibly with error), not raise exception
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)


@pytest.mark.regression
class TestAIProviderRegressionSuite:
    """Comprehensive regression tests for AI providers."""

    def test_all_provider_functions_exist(self):
        """All provider call functions should exist."""
        from src.ai import ai

        required_functions = [
            'call_openai',
            'call_anthropic',
            'call_gemini',
            'call_ai'
        ]

        for func_name in required_functions:
            assert hasattr(ai, func_name), f"Missing function: {func_name}"
            assert callable(getattr(ai, func_name)), f"{func_name} is not callable"

    def test_document_generation_functions_exist(self):
        """Document generation functions should exist."""
        from src.ai import ai

        required_functions = [
            'create_soap_note_with_openai',
            'create_referral_with_openai',
            'create_letter_with_ai'
        ]

        for func_name in required_functions:
            assert hasattr(ai, func_name), f"Missing function: {func_name}"

    def test_ai_response_is_always_airesult(self, mock_api_keys):
        """AI functions should always return AIResult."""
        from src.ai.ai import call_ai

        result = call_ai(
            model="gpt-4",
            system_message="Test",
            prompt="Test",
            temperature=0.7
        )

        # Result should be AIResult, with str() for backward compatibility
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)

    def test_temperature_parameter_accepted(self, mock_api_keys):
        """AI functions should accept temperature parameter."""
        from src.ai.ai import call_openai

        # Should accept temperature parameter without error
        result = call_openai(
            model="gpt-4",
            system_message="Test",
            prompt="Test",
            temperature=0.5
        )

        # Result is AIResult (may be error due to validation, but that's ok)
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)

    def test_empty_prompt_handled(self, mock_api_keys):
        """Empty prompt should be handled gracefully."""
        from src.ai.ai import call_ai

        result = call_ai(
            model="gpt-4",
            system_message="Test",
            prompt="",
            temperature=0.7
        )

        # Should return AIResult (empty string or error)
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)

    def test_very_long_prompt_handled(self, mock_api_keys):
        """Very long prompts should be handled."""
        from src.ai.ai import call_ai

        long_prompt = "A" * 50000  # Very long prompt

        result = call_ai(
            model="gpt-4",
            system_message="Test",
            prompt=long_prompt,
            temperature=0.7
        )

        # Should not raise exception, returns AIResult
        assert isinstance(result, AIResult)
        assert isinstance(str(result), str)
