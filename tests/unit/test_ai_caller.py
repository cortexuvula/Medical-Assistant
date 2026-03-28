"""Tests for ai.agents.ai_caller — MockAICaller, DefaultAICaller, factory functions."""

import pytest
from unittest.mock import MagicMock, patch

from ai.agents.ai_caller import (
    MockAICaller,
    DefaultAICaller,
    BaseAICaller,
    AICallerProtocol,
    get_default_ai_caller,
    create_mock_ai_caller,
)


# ── MockAICaller ──────────────────────────────────────────────────────────────

class TestMockAICaller:
    def test_init_default_response(self):
        caller = MockAICaller()
        assert caller.default_response == "Mock response"

    def test_init_custom_response(self):
        caller = MockAICaller("Custom reply")
        assert caller.default_response == "Custom reply"

    def test_call_returns_default_response(self):
        caller = MockAICaller("Hello!")
        result = caller.call("gpt-4", "sys", "prompt")
        assert result == "Hello!"

    def test_call_records_history(self):
        caller = MockAICaller()
        caller.call("gpt-4", "sys", "my prompt", 0.5)
        assert len(caller.call_history) == 1
        entry = caller.call_history[0]
        assert entry["model"] == "gpt-4"
        assert entry["system_message"] == "sys"
        assert entry["prompt"] == "my prompt"
        assert entry["temperature"] == 0.5

    def test_call_records_provider(self):
        caller = MockAICaller()
        caller.call("gpt-4", "sys", "prompt", provider="openai")
        assert caller.call_history[0]["provider"] == "openai"

    def test_multiple_calls_accumulate_history(self):
        caller = MockAICaller()
        caller.call("gpt-4", "sys", "p1")
        caller.call("gpt-4", "sys", "p2")
        assert len(caller.call_history) == 2

    def test_reset_clears_history(self):
        caller = MockAICaller()
        caller.call("gpt-4", "sys", "prompt")
        caller.reset()
        assert len(caller.call_history) == 0

    def test_call_with_provider_delegates_to_call(self):
        caller = MockAICaller("Provider reply")
        result = caller.call_with_provider("openai", "gpt-4", "sys", "prompt", 0.7)
        assert result == "Provider reply"
        assert len(caller.call_history) == 1
        assert caller.call_history[0]["provider"] == "openai"

    def test_implements_protocol(self):
        caller = MockAICaller()
        assert isinstance(caller, AICallerProtocol)

    def test_is_base_ai_caller(self):
        caller = MockAICaller()
        assert isinstance(caller, BaseAICaller)


# ── DefaultAICaller ───────────────────────────────────────────────────────────

class TestDefaultAICaller:
    def test_creates_instance(self):
        caller = DefaultAICaller()
        assert caller is not None

    def test_not_initialized_at_creation(self):
        caller = DefaultAICaller()
        assert not caller._initialized

    def test_call_routes_through_provider_when_given(self):
        caller = DefaultAICaller()
        mock_ai = MagicMock(return_value="routed")
        caller._call_ai = mock_ai
        caller._call_openai = MagicMock(return_value="openai_result")
        caller._initialized = True

        result = caller.call("gpt-4", "sys", "prompt", provider="openai")
        assert result == "openai_result"
        caller._call_openai.assert_called_once()

    def test_call_without_provider_uses_call_ai(self):
        caller = DefaultAICaller()
        caller._call_ai = MagicMock(return_value="generic_result")
        caller._initialized = True

        result = caller.call("gpt-4", "sys", "prompt")
        assert result == "generic_result"

    def test_call_extracts_text_from_ai_result(self):
        caller = DefaultAICaller()
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.text = "extracted text"
        caller._call_ai = MagicMock(return_value=mock_result)
        caller._initialized = True

        result = caller.call("gpt-4", "sys", "prompt")
        assert result == "extracted text"

    def test_call_raises_on_failed_ai_result(self):
        caller = DefaultAICaller()
        mock_result = MagicMock()
        mock_result.is_success = False
        mock_result.error = "rate limit exceeded"
        caller._call_ai = MagicMock(return_value=mock_result)
        caller._initialized = True

        with pytest.raises(Exception, match="rate limit exceeded"):
            caller.call("gpt-4", "sys", "prompt")

    def test_call_raises_on_failed_ai_result_no_error_msg(self):
        caller = DefaultAICaller()
        mock_result = MagicMock()
        mock_result.is_success = False
        mock_result.error = None
        caller._call_ai = MagicMock(return_value=mock_result)
        caller._initialized = True

        with pytest.raises(Exception, match="AI call failed"):
            caller.call("gpt-4", "sys", "prompt")

    def test_call_with_provider_anthropic(self):
        caller = DefaultAICaller()
        caller._call_anthropic = MagicMock(return_value="anthropic_result")
        caller._initialized = True

        result = caller.call_with_provider("anthropic", "claude-3", "sys", "prompt")
        assert result == "anthropic_result"

    def test_call_with_provider_ollama(self):
        caller = DefaultAICaller()
        caller._call_ollama = MagicMock(return_value="ollama_result")
        caller._initialized = True

        result = caller.call_with_provider("ollama", "llama3", "sys", "prompt")
        assert result == "ollama_result"

    def test_call_with_provider_gemini(self):
        caller = DefaultAICaller()
        caller._call_gemini = MagicMock(return_value="gemini_result")
        caller._initialized = True

        result = caller.call_with_provider("gemini", "gemini-pro", "sys", "prompt")
        assert result == "gemini_result"

    def test_call_with_provider_groq(self):
        caller = DefaultAICaller()
        caller._call_groq = MagicMock(return_value="groq_result")
        caller._initialized = True

        result = caller.call_with_provider("groq", "mixtral", "sys", "prompt")
        assert result == "groq_result"

    def test_call_with_provider_cerebras(self):
        caller = DefaultAICaller()
        caller._call_cerebras = MagicMock(return_value="cerebras_result")
        caller._initialized = True

        result = caller.call_with_provider("cerebras", "model", "sys", "prompt")
        assert result == "cerebras_result"

    def test_call_with_unknown_provider_falls_back_to_call_ai(self):
        caller = DefaultAICaller()
        caller._call_ai = MagicMock(return_value="fallback_result")
        caller._initialized = True

        result = caller.call_with_provider("unknown_provider", "model", "sys", "prompt")
        assert result == "fallback_result"

    def test_call_with_provider_extracts_ai_result_text(self):
        caller = DefaultAICaller()
        mock_result = MagicMock()
        mock_result.is_success = True
        mock_result.text = "provider text"
        caller._call_openai = MagicMock(return_value=mock_result)
        caller._initialized = True

        result = caller.call_with_provider("openai", "gpt-4", "sys", "prompt")
        assert result == "provider text"


# ── Factory Functions ─────────────────────────────────────────────────────────

class TestGetDefaultAICaller:
    def setup_method(self):
        import ai.agents.ai_caller as mod
        mod._default_ai_caller = None

    def test_returns_default_ai_caller(self):
        caller = get_default_ai_caller()
        assert isinstance(caller, DefaultAICaller)

    def test_returns_singleton(self):
        a = get_default_ai_caller()
        b = get_default_ai_caller()
        assert a is b

    def teardown_method(self):
        import ai.agents.ai_caller as mod
        mod._default_ai_caller = None


class TestCreateMockAICaller:
    def test_returns_mock_ai_caller(self):
        caller = create_mock_ai_caller()
        assert isinstance(caller, MockAICaller)

    def test_custom_response_passed_through(self):
        caller = create_mock_ai_caller("Custom response")
        assert caller.default_response == "Custom response"

    def test_default_response_is_mock_response(self):
        caller = create_mock_ai_caller()
        assert caller.default_response == "Mock response"

    def test_each_call_returns_new_instance(self):
        a = create_mock_ai_caller()
        b = create_mock_ai_caller()
        assert a is not b
