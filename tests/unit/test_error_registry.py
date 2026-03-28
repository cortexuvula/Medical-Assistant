"""Unit tests for utils.error_registry — error codes + user-friendly message mapping."""

import unittest

from utils.error_registry import (
    ERROR_CODES,
    get_error_message,
    format_api_error,
    ErrorMessageMapper,
    get_user_friendly_error,
    format_error_with_retry,
)


class TestErrorCodes(unittest.TestCase):

    def test_error_codes_is_dict(self):
        assert isinstance(ERROR_CODES, dict)

    def test_all_entries_are_tuples(self):
        for code, value in ERROR_CODES.items():
            assert isinstance(value, tuple), f"{code} is not a tuple"
            assert len(value) == 2, f"{code} does not have 2 elements"

    def test_unknown_error_exists(self):
        assert "UNKNOWN_ERROR" in ERROR_CODES

    def test_api_key_missing_exists(self):
        assert "API_KEY_MISSING" in ERROR_CODES


class TestGetErrorMessage(unittest.TestCase):

    def test_known_error_code(self):
        title, message = get_error_message("API_KEY_MISSING")
        assert title == "API key not configured"
        assert "API key" in message

    def test_unknown_code_falls_back(self):
        title, message = get_error_message("TOTALLY_FAKE_CODE")
        assert title == "Unexpected error occurred"

    def test_details_appended(self):
        _, message = get_error_message("API_KEY_MISSING", details="extra info")
        assert "extra info" in message

    def test_error_code_appended(self):
        _, message = get_error_message("API_KEY_MISSING")
        assert "API_KEY_MISSING" in message

    def test_unknown_error_no_code_appended(self):
        _, message = get_error_message("UNKNOWN_ERROR")
        assert "UNKNOWN_ERROR" not in message

    def test_model_not_installed_uses_model_name(self):
        _, message = get_error_message(
            "CFG_MODEL_NOT_INSTALLED", model_name="llama3"
        )
        assert "llama3" in message

    def test_model_not_installed_without_model_name(self):
        _, message = get_error_message("CFG_MODEL_NOT_INSTALLED")
        assert "{model_name}" in message


class TestFormatApiError(unittest.TestCase):

    def test_api_key_error(self):
        code, details = format_api_error("openai", Exception("Invalid API key"))
        assert code == "API_KEY_INVALID"

    def test_authentication_error(self):
        code, _ = format_api_error("anthropic", Exception("authentication failed"))
        assert code == "API_KEY_INVALID"

    def test_rate_limit_error(self):
        code, _ = format_api_error("openai", Exception("rate limit exceeded"))
        assert code == "API_RATE_LIMIT"

    def test_quota_error(self):
        code, _ = format_api_error("openai", Exception("insufficient_quota"))
        assert code == "API_QUOTA_EXCEEDED"

    def test_model_not_found(self):
        code, _ = format_api_error("openai", Exception("model gpt-5 not found"))
        assert code == "API_MODEL_NOT_FOUND"

    def test_timeout_error(self):
        code, _ = format_api_error("openai", Exception("request timeout"))
        assert code == "CONN_TIMEOUT"

    def test_connection_error(self):
        code, _ = format_api_error("openai", Exception("connection refused"))
        assert code == "CONN_NO_INTERNET"

    def test_network_error(self):
        code, _ = format_api_error("openai", Exception("network unreachable"))
        assert code == "CONN_NO_INTERNET"

    def test_unknown_error(self):
        code, _ = format_api_error("openai", Exception("something weird"))
        assert code == "UNKNOWN_ERROR"

    def test_provider_title_in_details(self):
        _, details = format_api_error("openai", Exception("rate limit exceeded"))
        assert "Openai" in details


class TestErrorMessageMapper(unittest.TestCase):

    def test_api_error_matched(self):
        err = Exception("Invalid API key provided")
        msg, tech = ErrorMessageMapper.get_user_message(err)
        assert "API key" in msg

    def test_audio_error_matched(self):
        err = Exception("No microphone detected in system")
        msg, _ = ErrorMessageMapper.get_user_message(err)
        assert "microphone" in msg.lower()

    def test_database_error_matched(self):
        err = Exception("Database locked by another process")
        msg, _ = ErrorMessageMapper.get_user_message(err)
        assert "busy" in msg.lower() or "database" in msg.lower()

    def test_context_included(self):
        err = Exception("Invalid API key")
        msg, _ = ErrorMessageMapper.get_user_message(err, context="processing audio")
        assert "processing audio" in msg

    def test_fallback_for_unknown_error(self):
        err = Exception("completely unknown error type xyzzy")
        msg, tech = ErrorMessageMapper.get_user_message(err)
        assert "unexpected" in msg.lower() or "error" in msg.lower()

    def test_exception_type_connectionerror(self):
        err = ConnectionError("failed to connect")
        msg, _ = ErrorMessageMapper.get_user_message(err)
        assert "connection" in msg.lower()

    def test_exception_type_timeout(self):
        err = TimeoutError("timed out")
        msg, _ = ErrorMessageMapper.get_user_message(err)
        assert "timed out" in msg.lower() or "timeout" in msg.lower()


class TestGetRetrySuggestion(unittest.TestCase):

    def test_rate_limit_suggestion(self):
        suggestion = ErrorMessageMapper.get_retry_suggestion(Exception("rate limit hit"))
        assert suggestion is not None
        assert "wait" in suggestion.lower() or "60" in suggestion

    def test_timeout_suggestion(self):
        suggestion = ErrorMessageMapper.get_retry_suggestion(Exception("connection timeout"))
        assert suggestion is not None

    def test_database_locked_suggestion(self):
        suggestion = ErrorMessageMapper.get_retry_suggestion(Exception("database locked"))
        assert suggestion is not None

    def test_no_suggestion_for_unknown(self):
        suggestion = ErrorMessageMapper.get_retry_suggestion(Exception("xyzzy"))
        assert suggestion is None


class TestConvenienceFunctions(unittest.TestCase):

    def test_get_user_friendly_error(self):
        msg = get_user_friendly_error(Exception("rate limit exceeded"))
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_get_user_friendly_error_with_context(self):
        msg = get_user_friendly_error(
            Exception("connection timeout"), context="saving file"
        )
        assert "saving file" in msg

    def test_format_error_with_retry_includes_suggestion(self):
        msg = format_error_with_retry(Exception("rate limit exceeded"))
        assert "wait" in msg.lower() or "60" in msg.lower()

    def test_format_error_with_retry_no_suggestion(self):
        msg = format_error_with_retry(Exception("xyzzy unknown error"))
        assert isinstance(msg, str)
        assert len(msg) > 0


if __name__ == "__main__":
    unittest.main()
