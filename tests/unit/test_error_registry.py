"""
Tests for src/utils/error_registry.py

Covers:
- ERROR_CODES dict (structure, known codes, tuple values)
- get_error_message (known codes, unknown fallback, details, model_name)
- format_api_error (key/auth errors, rate limit, quota, model, timeout, connection, unknown)
- ErrorMessageMapper.get_user_message (API/audio/db/file/network/processing matches, exception types, fallback)
- ErrorMessageMapper._format_message (with/without context)
- ErrorMessageMapper.get_retry_suggestion (rate limit, timeout, db locked, memory, permission, unknown)
- get_user_friendly_error convenience
- format_error_with_retry (with and without retry suggestion)
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.error_registry import (
    ERROR_CODES,
    get_error_message,
    format_api_error,
    ErrorMessageMapper,
    get_user_friendly_error,
    format_error_with_retry,
)


# ===========================================================================
# ERROR_CODES dict
# ===========================================================================

class TestErrorCodes:
    def test_is_dict(self):
        assert isinstance(ERROR_CODES, dict)

    def test_not_empty(self):
        assert len(ERROR_CODES) > 0

    def test_known_api_key_missing(self):
        assert "API_KEY_MISSING" in ERROR_CODES

    def test_known_api_key_invalid(self):
        assert "API_KEY_INVALID" in ERROR_CODES

    def test_known_api_rate_limit(self):
        assert "API_RATE_LIMIT" in ERROR_CODES

    def test_known_conn_timeout(self):
        assert "CONN_TIMEOUT" in ERROR_CODES

    def test_known_conn_no_internet(self):
        assert "CONN_NO_INTERNET" in ERROR_CODES

    def test_known_cfg_model_not_installed(self):
        assert "CFG_MODEL_NOT_INSTALLED" in ERROR_CODES

    def test_known_sys_audio_device(self):
        assert "SYS_AUDIO_DEVICE" in ERROR_CODES

    def test_known_unknown_error(self):
        assert "UNKNOWN_ERROR" in ERROR_CODES

    def test_all_values_are_tuples(self):
        for code, value in ERROR_CODES.items():
            assert isinstance(value, tuple), f"{code} value should be a tuple"

    def test_all_tuples_have_two_strings(self):
        for code, (title, hint) in ERROR_CODES.items():
            assert isinstance(title, str)
            assert isinstance(hint, str)

    def test_titles_are_non_empty(self):
        for code, (title, _) in ERROR_CODES.items():
            assert len(title) > 0

    def test_hints_are_non_empty(self):
        for code, (_, hint) in ERROR_CODES.items():
            assert len(hint) > 0


# ===========================================================================
# get_error_message
# ===========================================================================

class TestGetErrorMessage:
    def test_returns_tuple(self):
        result = get_error_message("API_KEY_MISSING")
        assert isinstance(result, tuple)

    def test_returns_two_strings(self):
        title, message = get_error_message("API_KEY_MISSING")
        assert isinstance(title, str)
        assert isinstance(message, str)

    def test_known_code_title(self):
        title, _ = get_error_message("API_KEY_MISSING")
        assert title == ERROR_CODES["API_KEY_MISSING"][0]

    def test_unknown_code_uses_fallback(self):
        title, message = get_error_message("NONEXISTENT_CODE")
        expected_title = ERROR_CODES["UNKNOWN_ERROR"][0]
        assert title == expected_title

    def test_details_appended(self):
        _, message = get_error_message("API_KEY_MISSING", details="extra info")
        assert "extra info" in message

    def test_error_code_appended_for_known(self):
        _, message = get_error_message("API_KEY_MISSING")
        assert "API_KEY_MISSING" in message

    def test_error_code_not_appended_for_unknown(self):
        _, message = get_error_message("NONEXISTENT_CODE")
        assert "NONEXISTENT_CODE" not in message

    def test_model_name_interpolated_for_cfg(self):
        _, message = get_error_message("CFG_MODEL_NOT_INSTALLED", model_name="llama3")
        assert "llama3" in message

    def test_model_name_not_required_for_other_codes(self):
        title, message = get_error_message("API_KEY_MISSING", model_name="")
        assert isinstance(title, str)

    def test_empty_details_no_details_line(self):
        _, message = get_error_message("API_KEY_MISSING", details="")
        assert "Details:" not in message

    def test_conn_timeout_title(self):
        title, _ = get_error_message("CONN_TIMEOUT")
        assert title == "Connection timeout"

    def test_sys_memory_title(self):
        title, _ = get_error_message("SYS_MEMORY")
        assert title == "Memory error"


# ===========================================================================
# format_api_error
# ===========================================================================

class TestFormatApiError:
    def test_returns_tuple(self):
        result = format_api_error("openai", Exception("some error"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_authentication_error(self):
        code, _ = format_api_error("openai", Exception("authentication failed"))
        assert code == "API_KEY_INVALID"

    def test_api_key_in_message(self):
        code, _ = format_api_error("openai", Exception("Invalid api key"))
        assert code == "API_KEY_INVALID"

    def test_unauthorized_error(self):
        code, _ = format_api_error("anthropic", Exception("unauthorized access"))
        assert code == "API_KEY_INVALID"

    def test_rate_limit_error(self):
        code, _ = format_api_error("openai", Exception("rate limit exceeded"))
        assert code == "API_RATE_LIMIT"

    def test_quota_error(self):
        code, _ = format_api_error("openai", Exception("quota exceeded"))
        assert code == "API_QUOTA_EXCEEDED"

    def test_insufficient_quota_error(self):
        code, _ = format_api_error("openai", Exception("insufficient_quota"))
        assert code == "API_QUOTA_EXCEEDED"

    def test_model_not_found_error(self):
        code, _ = format_api_error("openai", Exception("model gpt-99 not found"))
        assert code == "API_MODEL_NOT_FOUND"

    def test_timeout_error(self):
        code, _ = format_api_error("openai", Exception("request timeout"))
        assert code == "CONN_TIMEOUT"

    def test_connection_error(self):
        code, _ = format_api_error("openai", Exception("connection refused"))
        assert code == "CONN_NO_INTERNET"

    def test_network_error(self):
        code, _ = format_api_error("openai", Exception("network failure"))
        assert code == "CONN_NO_INTERNET"

    def test_unknown_error(self):
        code, _ = format_api_error("openai", Exception("bizarre problem xyz987"))
        assert code == "UNKNOWN_ERROR"

    def test_details_contain_provider(self):
        _, details = format_api_error("anthropic", Exception("authentication failed"))
        assert "Anthropic" in details

    def test_details_is_string(self):
        _, details = format_api_error("openai", Exception("rate limit exceeded"))
        assert isinstance(details, str)


# ===========================================================================
# ErrorMessageMapper.get_user_message
# ===========================================================================

class TestErrorMessageMapperGetUserMessage:
    def test_returns_tuple(self):
        result = ErrorMessageMapper.get_user_message(Exception("some error"))
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_api_key_pattern(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("Invalid API key provided"))
        assert isinstance(msg, str)
        assert len(msg) > 0

    def test_rate_limit_pattern(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("Rate limit exceeded for the API"))
        assert isinstance(msg, str)

    def test_audio_microphone_pattern(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("No microphone found on this system"))
        assert isinstance(msg, str)

    def test_database_locked_pattern(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("Database locked by another process"))
        assert isinstance(msg, str)

    def test_disk_full_pattern(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("Disk full, cannot write"))
        assert isinstance(msg, str)

    def test_file_not_found_pattern(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("File not found: /path/to/file"))
        assert isinstance(msg, str)

    def test_timeout_in_message(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("Timeout waiting for response"))
        assert isinstance(msg, str)

    def test_out_of_memory(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("Out of memory"))
        assert isinstance(msg, str)

    def test_generic_fallback(self):
        msg, _ = ErrorMessageMapper.get_user_message(Exception("something truly bizarre xyz999"))
        assert len(msg) > 0

    def test_generic_fallback_with_context(self):
        msg, _ = ErrorMessageMapper.get_user_message(
            Exception("bizarre xyz999"), context="saving file"
        )
        assert len(msg) > 0

    def test_technical_details_is_error_string(self):
        e = Exception("specific detail")
        _, technical = ErrorMessageMapper.get_user_message(e)
        assert technical == str(e)

    def test_connection_error_type(self):
        class MyConnectionError(Exception):
            pass
        e = MyConnectionError("network issue")
        msg, _ = ErrorMessageMapper.get_user_message(e)
        assert isinstance(msg, str)

    def test_permission_error_type(self):
        class MyPermissionError(Exception):
            pass
        e = MyPermissionError("denied")
        msg, _ = ErrorMessageMapper.get_user_message(e)
        assert isinstance(msg, str)


# ===========================================================================
# ErrorMessageMapper._format_message
# ===========================================================================

class TestFormatMessage:
    def test_without_context(self):
        result = ErrorMessageMapper._format_message("Check settings.")
        assert result == "Check settings."

    def test_with_context(self):
        result = ErrorMessageMapper._format_message("Check settings.", context="saving file")
        assert "saving file" in result
        assert "Check settings." in result

    def test_with_context_includes_both(self):
        result = ErrorMessageMapper._format_message("Try again.", context="uploading data")
        assert "uploading data" in result
        assert "Try again." in result


# ===========================================================================
# ErrorMessageMapper.get_retry_suggestion
# ===========================================================================

class TestGetRetrySuggestion:
    def test_rate_limit_suggestion(self):
        e = Exception("rate limit exceeded")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is not None

    def test_timeout_suggestion(self):
        e = Exception("request timeout occurred")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is not None

    def test_connection_suggestion(self):
        e = Exception("connection refused")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is not None

    def test_database_locked_suggestion(self):
        e = Exception("database locked by process")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is not None

    def test_memory_suggestion(self):
        e = Exception("out of memory error")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is not None

    def test_permission_suggestion(self):
        e = Exception("permission denied to file")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is not None

    def test_unknown_error_no_suggestion(self):
        e = Exception("completely unrelated bizarre error xyz123abc")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert result is None

    def test_returns_string_when_found(self):
        e = Exception("rate limit")
        result = ErrorMessageMapper.get_retry_suggestion(e)
        assert isinstance(result, str)


# ===========================================================================
# get_user_friendly_error
# ===========================================================================

class TestGetUserFriendlyError:
    def test_returns_string(self):
        result = get_user_friendly_error(Exception("test error"))
        assert isinstance(result, str)

    def test_returns_non_empty(self):
        result = get_user_friendly_error(Exception("test error"))
        assert len(result) > 0

    def test_with_context(self):
        result = get_user_friendly_error(Exception("some error"), context="uploading data")
        assert isinstance(result, str)

    def test_api_key_error_friendly(self):
        result = get_user_friendly_error(Exception("Invalid API key"))
        assert isinstance(result, str)


# ===========================================================================
# format_error_with_retry
# ===========================================================================

class TestFormatErrorWithRetry:
    def test_returns_string(self):
        result = format_error_with_retry(Exception("test error"))
        assert isinstance(result, str)

    def test_with_retry_suggestion_nonempty(self):
        e = Exception("rate limit exceeded")
        result = format_error_with_retry(e)
        assert len(result) > 0

    def test_without_retry_suggestion_returns_message(self):
        e = Exception("completely bizarre xyz987abc")
        result = format_error_with_retry(e)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_with_context(self):
        result = format_error_with_retry(Exception("some error"), context="processing")
        assert isinstance(result, str)
