"""
Tests for src/utils/security_decorators.py

Covers rate_limited, sanitize_inputs, require_api_key, log_api_call,
and secure_api_call decorators — all pure logic with mocked security manager.
"""

import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.security_decorators import (
    rate_limited,
    sanitize_inputs,
    require_api_key,
    log_api_call,
    secure_api_call,
)
from utils.exceptions import APIError, RateLimitError


# ---------------------------------------------------------------------------
# Mock security manager factory
# ---------------------------------------------------------------------------

def _mock_security(
    rate_limit_allowed=True,
    wait_time=0.0,
    api_key="sk-test",
    key_valid=True,
    key_error="",
    sanitized=None,
    token="abc123"
):
    """Build a mock security manager."""
    mock = MagicMock()
    mock.check_rate_limit.return_value = (rate_limit_allowed, wait_time)
    mock.get_api_key.return_value = api_key
    mock.validate_api_key.return_value = (key_valid, key_error)
    mock.sanitize_input.side_effect = lambda val, *a, **kw: sanitized if sanitized is not None else val
    mock.generate_secure_token.return_value = token
    return mock


# ===========================================================================
# rate_limited
# ===========================================================================

class TestRateLimited:
    def test_calls_function_when_allowed(self):
        mock_sec = _mock_security(rate_limit_allowed=True)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai")
            def my_func():
                return "ok"

            result = my_func()
        assert result == "ok"

    def test_raises_rate_limit_error_when_not_allowed(self):
        mock_sec = _mock_security(rate_limit_allowed=False, wait_time=5.0)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai")
            def my_func():
                return "ok"

            with pytest.raises(RateLimitError):
                my_func()

    def test_rate_limit_error_contains_wait_time(self):
        mock_sec = _mock_security(rate_limit_allowed=False, wait_time=10.5)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai")
            def my_func():
                pass

            with pytest.raises(RateLimitError) as exc_info:
                my_func()
        assert "10.5" in str(exc_info.value)

    def test_rate_limit_error_contains_provider(self):
        mock_sec = _mock_security(rate_limit_allowed=False, wait_time=1.0)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("deepgram")
            def my_func():
                pass

            with pytest.raises(RateLimitError) as exc_info:
                my_func()
        assert "deepgram" in str(exc_info.value)

    def test_calls_check_rate_limit_with_provider(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("anthropic")
            def my_func():
                return True

            my_func()
        mock_sec.check_rate_limit.assert_called_once_with("anthropic", None)

    def test_uses_identifier_arg_from_kwargs(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai", identifier_arg="user_id")
            def my_func(prompt, user_id=None):
                return True

            my_func(prompt="hello", user_id="user-42")
        mock_sec.check_rate_limit.assert_called_once_with("openai", "user-42")

    def test_identifier_is_none_when_arg_not_in_kwargs(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai", identifier_arg="user_id")
            def my_func(prompt):
                return True

            my_func("hello")
        mock_sec.check_rate_limit.assert_called_once_with("openai", None)

    def test_function_args_passed_through(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai")
            def my_func(a, b):
                return a + b

            result = my_func(2, 3)
        assert result == 5

    def test_preserves_function_name(self):
        @rate_limited("openai")
        def original_function():
            pass

        assert original_function.__name__ == "original_function"

    def test_returns_function_result(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @rate_limited("openai")
            def my_func():
                return {"response": "text"}

            result = my_func()
        assert result == {"response": "text"}


# ===========================================================================
# sanitize_inputs
# ===========================================================================

class TestSanitizeInputs:
    def test_sanitizes_named_arg(self):
        mock_sec = _mock_security(sanitized="clean text")
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @sanitize_inputs("prompt")
            def process(prompt):
                return prompt

            result = process(prompt="<script>bad</script>")
        assert result == "clean text"

    def test_non_string_arg_not_sanitized(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @sanitize_inputs("count")
            def process(count):
                return count

            result = process(count=42)
        assert result == 42
        mock_sec.sanitize_input.assert_not_called()

    def test_unlisted_arg_not_sanitized(self):
        mock_sec = _mock_security()
        calls = []
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @sanitize_inputs("prompt")
            def process(prompt, other):
                calls.append(other)
                return prompt

            process(prompt="hello", other="untouched")
        # sanitize_input called only for "prompt"
        assert mock_sec.sanitize_input.call_count == 1

    def test_sanitizes_multiple_args(self):
        results = []
        mock_sec = MagicMock()
        mock_sec.sanitize_input.side_effect = lambda v, *a: v.upper()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @sanitize_inputs("a", "b")
            def process(a, b):
                results.append((a, b))

            process(a="hello", b="world")
        assert results[0] == ("HELLO", "WORLD")

    def test_logs_warning_when_sanitized_differs(self):
        mock_sec = MagicMock()
        mock_sec.sanitize_input.return_value = "clean"
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec), \
             patch("utils.security_decorators.logger") as mock_logger:
            @sanitize_inputs("prompt")
            def process(prompt):
                return prompt

            process(prompt="dirty input")
        mock_logger.warning.assert_called_once()

    def test_no_warning_when_sanitization_unchanged(self):
        mock_sec = MagicMock()
        mock_sec.sanitize_input.return_value = "same"
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec), \
             patch("utils.security_decorators.logger") as mock_logger:
            @sanitize_inputs("prompt")
            def process(prompt):
                return prompt

            process(prompt="same")
        mock_logger.warning.assert_not_called()

    def test_preserves_function_name(self):
        @sanitize_inputs("prompt")
        def my_processor(prompt):
            pass

        assert my_processor.__name__ == "my_processor"

    def test_input_type_passed_to_sanitize(self):
        mock_sec = MagicMock()
        mock_sec.sanitize_input.return_value = "text"
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @sanitize_inputs("data", input_type="html")
            def process(data):
                return data

            process(data="text")
        mock_sec.sanitize_input.assert_called_once_with("text", "html")


# ===========================================================================
# require_api_key
# ===========================================================================

class TestRequireApiKey:
    def test_calls_function_when_key_valid(self):
        mock_sec = _mock_security(api_key="sk-valid", key_valid=True)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("openai")
            def my_func():
                return "success"

            result = my_func()
        assert result == "success"

    def test_raises_api_error_when_no_key(self):
        mock_sec = _mock_security(api_key=None)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("openai")
            def my_func():
                return "success"

            with pytest.raises(APIError):
                my_func()

    def test_raises_api_error_when_empty_key(self):
        mock_sec = _mock_security(api_key="")
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("openai")
            def my_func():
                return "ok"

            with pytest.raises(APIError):
                my_func()

    def test_raises_api_error_when_key_invalid(self):
        mock_sec = _mock_security(api_key="bad-key", key_valid=False, key_error="malformed key")
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("openai")
            def my_func():
                return "ok"

            with pytest.raises(APIError, match="malformed key"):
                my_func()

    def test_error_contains_provider_name(self):
        mock_sec = _mock_security(api_key=None)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("deepgram")
            def my_func():
                pass

            with pytest.raises(APIError) as exc_info:
                my_func()
        assert "deepgram" in str(exc_info.value)

    def test_validates_key_with_correct_provider(self):
        mock_sec = _mock_security(api_key="sk-test", key_valid=True)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("anthropic")
            def my_func():
                return True

            my_func()
        mock_sec.validate_api_key.assert_called_once_with("anthropic", "sk-test")

    def test_preserves_function_name(self):
        @require_api_key("openai")
        def my_api_call():
            pass

        assert my_api_call.__name__ == "my_api_call"

    def test_passes_through_return_value(self):
        mock_sec = _mock_security(api_key="sk-valid", key_valid=True)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("openai")
            def my_func():
                return {"data": [1, 2, 3]}

            result = my_func()
        assert result == {"data": [1, 2, 3]}

    def test_does_not_call_function_when_key_missing(self):
        mock_sec = _mock_security(api_key="")
        called = []
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @require_api_key("openai")
            def my_func():
                called.append(True)

            with pytest.raises(APIError):
                my_func()
        assert not called


# ===========================================================================
# log_api_call
# ===========================================================================

class TestLogApiCall:
    def test_calls_wrapped_function(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func():
                return "result"

            result = my_func()
        assert result == "result"

    def test_re_raises_exception_from_function(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func():
                raise ValueError("API timeout")

            with pytest.raises(ValueError, match="API timeout"):
                my_func()

    def test_generates_call_id_token(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func():
                return True

            my_func()
        mock_sec.generate_secure_token.assert_called_once_with(16)

    def test_preserves_function_name(self):
        @log_api_call("openai")
        def api_wrapper():
            pass

        assert api_wrapper.__name__ == "api_wrapper"

    def test_logs_success_on_successful_call(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func():
                return "ok"

            with patch("utils.security_decorators.get_logger") as mock_get_logger:
                mock_audit_logger = MagicMock()
                mock_get_logger.return_value = mock_audit_logger
                my_func()
            # info should be called for start and success
            assert mock_audit_logger.info.call_count >= 1

    def test_logs_error_on_failure(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func():
                raise RuntimeError("network error")

            with patch("utils.security_decorators.get_logger") as mock_get_logger:
                mock_audit_logger = MagicMock()
                mock_get_logger.return_value = mock_audit_logger
                with pytest.raises(RuntimeError):
                    my_func()
            mock_audit_logger.error.assert_called_once()

    def test_passes_args_and_kwargs(self):
        mock_sec = _mock_security()
        received = []
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func(a, b, c=3):
                received.append((a, b, c))

            my_func(1, 2, c=99)
        assert received[0] == (1, 2, 99)

    def test_log_response_false_by_default(self):
        mock_sec = _mock_security()
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @log_api_call("openai")
            def my_func():
                return "SECRET RESPONSE"

            with patch("utils.security_decorators.get_logger") as mock_get_logger:
                mock_audit_logger = MagicMock()
                mock_get_logger.return_value = mock_audit_logger
                my_func()
            # debug should NOT be called with response preview
            for debug_call in mock_audit_logger.debug.call_args_list:
                assert "SECRET RESPONSE" not in str(debug_call)


# ===========================================================================
# secure_api_call (combined)
# ===========================================================================

class TestSecureApiCall:
    def test_calls_function_when_all_checks_pass(self):
        mock_sec = _mock_security(
            api_key="sk-valid",
            key_valid=True,
            rate_limit_allowed=True
        )
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai")
            def my_func(prompt):
                return f"processed: {prompt}"

            result = my_func(prompt="hello")
        assert "processed" in result

    def test_raises_api_error_when_no_key(self):
        mock_sec = _mock_security(api_key="")
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai")
            def my_func(prompt):
                return prompt

            with pytest.raises(APIError):
                my_func(prompt="hello")

    def test_raises_rate_limit_error_when_throttled(self):
        mock_sec = _mock_security(
            api_key="sk-valid",
            key_valid=True,
            rate_limit_allowed=False,
            wait_time=3.0
        )
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai", sanitize=False)
            def my_func(prompt):
                return prompt

            with pytest.raises(RateLimitError):
                my_func(prompt="hello")

    def test_rate_limit_disabled_skips_check(self):
        mock_sec = _mock_security(api_key="sk-valid", key_valid=True)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai", rate_limit=False, sanitize=False)
            def my_func():
                return "ok"

            my_func()
        mock_sec.check_rate_limit.assert_not_called()

    def test_sanitize_disabled_skips_sanitization(self):
        mock_sec = _mock_security(api_key="sk-valid", key_valid=True)
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai", rate_limit=False, sanitize=False)
            def my_func(prompt):
                return prompt

            my_func(prompt="hello")
        mock_sec.sanitize_input.assert_not_called()

    def test_sanitize_enabled_for_prompt_args(self):
        mock_sec = MagicMock()
        mock_sec.get_api_key.return_value = "sk-valid"
        mock_sec.validate_api_key.return_value = (True, "")
        mock_sec.check_rate_limit.return_value = (True, 0.0)
        mock_sec.generate_secure_token.return_value = "token"
        mock_sec.sanitize_input.return_value = "sanitized"
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai", rate_limit=False, sanitize=True)
            def my_func(prompt):
                return prompt

            my_func(prompt="raw input")
        mock_sec.sanitize_input.assert_called_once()

    def test_non_prompt_args_not_auto_sanitized(self):
        mock_sec = MagicMock()
        mock_sec.get_api_key.return_value = "sk-valid"
        mock_sec.validate_api_key.return_value = (True, "")
        mock_sec.check_rate_limit.return_value = (True, 0.0)
        mock_sec.generate_secure_token.return_value = "token"
        mock_sec.sanitize_input.return_value = "value"
        with patch("utils.security_decorators.get_security_manager", return_value=mock_sec):
            @secure_api_call("openai", rate_limit=False, sanitize=True)
            def my_func(model, temperature):
                return (model, temperature)

            my_func(model="gpt-4", temperature=0.7)
        # No prompt-like args → sanitize_input not called
        mock_sec.sanitize_input.assert_not_called()
