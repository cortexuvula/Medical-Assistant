"""
AI Pipeline Tests

Tests for provider fallback chain and token tracking.
"""

import pytest
from unittest.mock import patch, MagicMock


class TestAIResultUsage:
    """Verify AIResult token usage field."""

    def test_usage_with_data(self):
        from utils.exceptions import AIResult
        r = AIResult.success("text", usage={"prompt_tokens": 50, "completion_tokens": 100, "total_tokens": 150})
        assert r.usage["total_tokens"] == 150
        assert r.usage["prompt_tokens"] == 50

    def test_usage_empty_by_default(self):
        from utils.exceptions import AIResult
        r = AIResult.success("text")
        assert r.usage == {}

    def test_usage_on_failure(self):
        from utils.exceptions import AIResult
        r = AIResult.failure("error")
        assert r.usage == {}

    def test_backward_compatible(self):
        from utils.exceptions import AIResult
        # Existing code that doesn't pass usage should still work
        r = AIResult.success("hello", model="gpt-4", provider="openai")
        assert r.is_success
        assert r.text == "hello"
        assert r.usage == {}


class TestProviderFallbackChain:
    """Verify provider fallback logic in router."""

    def test_fallback_chain_defined(self):
        from ai.providers.router import FALLBACK_CHAIN
        assert "openai" in FALLBACK_CHAIN
        assert "anthropic" in FALLBACK_CHAIN
        assert "groq" in FALLBACK_CHAIN
        assert "cerebras" in FALLBACK_CHAIN
        # Ollama and Gemini excluded
        assert "ollama" not in FALLBACK_CHAIN
        assert "gemini" not in FALLBACK_CHAIN

    @patch('ai.providers.router._call_provider')
    def test_primary_success_no_fallback(self, mock_call):
        """When primary provider succeeds, no fallback is attempted."""
        import sys
        from ai.providers.router import call_ai
        from utils.exceptions import AIResult

        sm_mod = sys.modules['settings.settings_manager']
        mock_mgr = MagicMock()
        mock_mgr.get_all.return_value = {"ai_provider": "openai"}
        mock_call.return_value = AIResult.success("response text")

        with patch.object(sm_mod, 'settings_manager', mock_mgr):
            result = call_ai("gpt-4", "system", "prompt", 0.5)

        assert result.is_success
        assert mock_call.call_count == 1  # Only primary, no fallback

    @patch('utils.security.get_security_manager')
    @patch('ai.providers.router._call_provider')
    def test_fallback_on_primary_failure(self, mock_call, mock_security):
        """When primary fails, fallback providers are tried."""
        import sys
        from ai.providers.router import call_ai
        from utils.exceptions import AIResult

        sm_mod = sys.modules['settings.settings_manager']
        mock_mgr = MagicMock()
        mock_mgr.get_all.return_value = {"ai_provider": "openai"}

        # Primary fails, first fallback (openai again) skipped, anthropic succeeds
        mock_call.side_effect = [
            AIResult.failure("OpenAI down"),  # Primary
            AIResult.success("Anthropic response"),  # Fallback to anthropic
        ]

        # Mock security manager to say anthropic has API key
        mock_sec = MagicMock()
        mock_sec.get_api_key.return_value = "sk-ant-test"
        mock_security.return_value = mock_sec

        with patch.object(sm_mod, 'settings_manager', mock_mgr):
            result = call_ai("gpt-4", "system", "prompt", 0.5)

        assert result.is_success
        assert result.text == "Anthropic response"
        assert mock_call.call_count == 2

    @patch('ai.providers.router._call_provider')
    def test_explicit_provider_no_fallback(self, mock_call):
        """When provider is explicitly set, no fallback even on failure."""
        import sys
        from ai.providers.router import call_ai
        from utils.exceptions import AIResult

        sm_mod = sys.modules['settings.settings_manager']
        mock_mgr = MagicMock()
        mock_mgr.get_all.return_value = {"ai_provider": "openai"}
        mock_call.return_value = AIResult.failure("Anthropic down")

        with patch.object(sm_mod, 'settings_manager', mock_mgr):
            result = call_ai("claude-3", "system", "prompt", 0.5, provider="anthropic")

        assert result.is_error
        assert mock_call.call_count == 1  # No fallback


class TestLogUsage:
    """Verify usage logging helper."""

    def test_log_usage_passes_through(self):
        from ai.providers.router import _log_usage
        from utils.exceptions import AIResult

        result = AIResult.success("text", usage={"total_tokens": 100})
        logged = _log_usage(result, "openai", "gpt-4")
        assert logged is result  # Same object returned

    def test_log_usage_handles_no_usage(self):
        from ai.providers.router import _log_usage
        from utils.exceptions import AIResult

        result = AIResult.success("text")
        logged = _log_usage(result, "openai", "gpt-4")
        assert logged is result
