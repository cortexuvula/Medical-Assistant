"""
Tests for src/utils/error_registry.py
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


# =============================================================================
# TestErrorCodes
# =============================================================================

class TestErrorCodes:
    """Tests for the ERROR_CODES dict structure and contents."""

    EXPECTED_KEYS = {
        "API_KEY_MISSING",
        "API_KEY_INVALID",
        "API_RATE_LIMIT",
        "API_QUOTA_EXCEEDED",
        "API_MODEL_NOT_FOUND",
        "CONN_TIMEOUT",
        "CONN_NO_INTERNET",
        "CONN_SERVICE_DOWN",
        "CONN_OLLAMA_NOT_RUNNING",
        "CFG_MODEL_NOT_INSTALLED",
        "CFG_INVALID_SETTINGS",
        "SYS_AUDIO_DEVICE",
        "SYS_FILE_ACCESS",
        "SYS_MEMORY",
        "UNKNOWN_ERROR",
    }

    def test_error_codes_is_dict(self):
        assert isinstance(ERROR_CODES, dict)

    def test_error_codes_has_15_keys(self):
        assert len(ERROR_CODES) == 15

    def test_error_codes_contains_all_expected_keys(self):
        assert set(ERROR_CODES.keys()) == self.EXPECTED_KEYS

    def test_api_key_missing_present(self):
        assert "API_KEY_MISSING" in ERROR_CODES

    def test_api_key_invalid_present(self):
        assert "API_KEY_INVALID" in ERROR_CODES

    def test_api_rate_limit_present(self):
        assert "API_RATE_LIMIT" in ERROR_CODES

    def test_api_quota_exceeded_present(self):
        assert "API_QUOTA_EXCEEDED" in ERROR_CODES

    def test_api_model_not_found_present(self):
        assert "API_MODEL_NOT_FOUND" in ERROR_CODES

    def test_conn_timeout_present(self):
        assert "CONN_TIMEOUT" in ERROR_CODES

    def test_conn_no_internet_present(self):
        assert "CONN_NO_INTERNET" in ERROR_CODES

    def test_conn_service_down_present(self):
        assert "CONN_SERVICE_DOWN" in ERROR_CODES

    def test_conn_ollama_not_running_present(self):
        assert "CONN_OLLAMA_NOT_RUNNING" in ERROR_CODES

    def test_cfg_model_not_installed_present(self):
        assert "CFG_MODEL_NOT_INSTALLED" in ERROR_CODES

    def test_cfg_invalid_settings_present(self):
        assert "CFG_INVALID_SETTINGS" in ERROR_CODES

    def test_sys_audio_device_present(self):
        assert "SYS_AUDIO_DEVICE" in ERROR_CODES

    def test_sys_file_access_present(self):
        assert "SYS_FILE_ACCESS" in ERROR_CODES

    def test_sys_memory_present(self):
        assert "SYS_MEMORY" in ERROR_CODES

    def test_unknown_error_present(self):
        assert "UNKNOWN_ERROR" in ERROR_CODES

    def test_all_values_are_tuples(self):
        for key, value in ERROR_CODES.items():
            assert isinstance(value, tuple), f"{key} value is not a tuple"

    def test_all_values_have_length_2(self):
        for key, value in ERROR_CODES.items():
            assert len(value) == 2, f"{key} tuple does not have length 2"

    def test_all_titles_are_strings(self):
        for key, (title, hint) in ERROR_CODES.items():
            assert isinstance(title, str), f"{key} title is not a string"

    def test_all_hints_are_strings(self):
        for key, (title, hint) in ERROR_CODES.items():
            assert isinstance(hint, str), f"{key} hint is not a string"

    def test_all_titles_non_empty(self):
        for key, (title, hint) in ERROR_CODES.items():
            assert title.strip() != "", f"{key} has empty title"

    def test_all_hints_non_empty(self):
        for key, (title, hint) in ERROR_CODES.items():
            assert hint.strip() != "", f"{key} has empty hint"


# =============================================================================
# TestGetErrorMessage
# =============================================================================

class TestGetErrorMessage:
    """Tests for get_error_message()."""

    def test_known_code_returns_tuple(self):
        result = get_error_message("API_KEY_MISSING")
        assert isinstance(result, tuple)

    def test_known_code_returns_2_tuple(self):
        result = get_error_message("API_KEY_MISSING")
        assert len(result) == 2

    def test_title_matches_error_codes(self):
        for code in ERROR_CODES:
            title, _ = get_error_message(code)
            assert title == ERROR_CODES[code][0], f"Title mismatch for {code}"

    def test_unknown_code_falls_back_to_unknown_error(self):
        title, _ = get_error_message("NONEXISTENT_CODE_XYZ")
        assert title == ERROR_CODES["UNKNOWN_ERROR"][0]

    def test_unknown_code_uses_unknown_hint(self):
        _, message = get_error_message("NONEXISTENT_CODE_XYZ")
        assert ERROR_CODES["UNKNOWN_ERROR"][1] in message

    def test_empty_string_code_falls_back(self):
        title, _ = get_error_message("")
        assert title == ERROR_CODES["UNKNOWN_ERROR"][0]

    def test_details_appended_to_message(self):
        _, message = get_error_message("API_KEY_MISSING", details="some extra info")
        assert "Details: some extra info" in message

    def test_error_code_appended_when_details_given(self):
        _, message = get_error_message("API_KEY_MISSING", details="some extra info")
        assert "Error code: API_KEY_MISSING" in message

    def test_error_code_appended_even_without_details(self):
        # error code line appears whenever code is not UNKNOWN_ERROR
        _, message = get_error_message("API_KEY_MISSING")
        assert "Error code: API_KEY_MISSING" in message

    def test_error_code_not_appended_for_unknown_error(self):
        _, message = get_error_message("UNKNOWN_ERROR", details="some details")
        assert "Error code: UNKNOWN_ERROR" not in message

    def test_no_details_means_no_details_line(self):
        _, message = get_error_message("API_KEY_MISSING")
        assert "Details:" not in message

    def test_model_name_formatted_into_cfg_model_not_installed(self):
        _, message = get_error_message("CFG_MODEL_NOT_INSTALLED", model_name="llama2")
        assert "llama2" in message

    def test_cfg_model_not_installed_without_model_name_has_placeholder(self):
        _, message = get_error_message("CFG_MODEL_NOT_INSTALLED")
        # Without a model_name the {model_name} placeholder is left as-is
        assert "{model_name}" in message

    def test_model_name_has_no_effect_on_other_codes(self):
        title, message = get_error_message("API_KEY_MISSING", model_name="llama2")
        assert "llama2" not in message
        assert "llama2" not in title

    def test_details_present_for_all_known_non_unknown_codes(self):
        for code in ERROR_CODES:
            if code == "UNKNOWN_ERROR":
                continue
            _, message = get_error_message(code, details="test_detail")
            assert "Details: test_detail" in message, f"Details missing for {code}"
            assert f"Error code: {code}" in message, f"Error code missing for {code}"

    def test_returns_strings(self):
        title, message = get_error_message("CONN_TIMEOUT")
        assert isinstance(title, str)
        assert isinstance(message, str)

    def test_conn_timeout_title(self):
        title, _ = get_error_message("CONN_TIMEOUT")
        assert title == "Connection timeout"

    def test_sys_memory_title(self):
        title, _ = get_error_message("SYS_MEMORY")
        assert title == "Memory error"

    def test_api_key_invalid_title(self):
        title, _ = get_error_message("API_KEY_INVALID")
        assert title == "Invalid API key"

    def test_unknown_error_no_error_code_line_even_with_details(self):
        _, message = get_error_message("UNKNOWN_ERROR", details="oops")
        assert "Error code:" not in message


# =============================================================================
# TestFormatApiError
# =============================================================================

class TestFormatApiError:
    """Tests for format_api_error()."""

    def test_returns_2_tuple(self):
        result = format_api_error("openai", ValueError("some error"))
        assert isinstance(result, tuple) and len(result) == 2

    def test_first_element_is_string(self):
        code, _ = format_api_error("openai", ValueError("some error"))
        assert isinstance(code, str)

    def test_second_element_is_string(self):
        _, details = format_api_error("openai", ValueError("some error"))
        assert isinstance(details, str)

    def test_api_key_pattern_returns_api_key_invalid(self):
        code, _ = format_api_error("openai", ValueError("Invalid api key provided"))
        assert code == "API_KEY_INVALID"

    def test_authentication_pattern_returns_api_key_invalid(self):
        code, _ = format_api_error("openai", ValueError("authentication failed"))
        assert code == "API_KEY_INVALID"

    def test_unauthorized_pattern_returns_api_key_invalid(self):
        code, _ = format_api_error("openai", ValueError("unauthorized access"))
        assert code == "API_KEY_INVALID"

    def test_api_key_invalid_details_contains_provider(self):
        _, details = format_api_error("openai", ValueError("api key invalid"))
        assert "Openai" in details

    def test_rate_limit_pattern_returns_api_rate_limit(self):
        code, _ = format_api_error("anthropic", ValueError("rate limit exceeded"))
        assert code == "API_RATE_LIMIT"

    def test_rate_limit_details_contains_provider(self):
        _, details = format_api_error("anthropic", ValueError("rate limit exceeded"))
        assert "Anthropic" in details

    def test_quota_pattern_returns_api_quota_exceeded(self):
        code, _ = format_api_error("openai", ValueError("quota exceeded"))
        assert code == "API_QUOTA_EXCEEDED"

    def test_insufficient_quota_pattern_returns_api_quota_exceeded(self):
        code, _ = format_api_error("openai", ValueError("insufficient_quota error"))
        assert code == "API_QUOTA_EXCEEDED"

    def test_quota_details_contains_provider(self):
        _, details = format_api_error("openai", ValueError("quota exceeded"))
        assert "Openai" in details

    def test_model_not_found_pattern_returns_api_model_not_found(self):
        code, _ = format_api_error("openai", ValueError("model gpt-5 not found"))
        assert code == "API_MODEL_NOT_FOUND"

    def test_model_not_found_details_is_error_string(self):
        error = ValueError("model gpt-5 not found")
        _, details = format_api_error("openai", error)
        assert details == str(error)

    def test_timeout_pattern_returns_conn_timeout(self):
        code, _ = format_api_error("openai", ValueError("request timeout"))
        assert code == "CONN_TIMEOUT"

    def test_timeout_details_contains_provider(self):
        _, details = format_api_error("openai", ValueError("timeout occurred"))
        assert "Openai" in details

    def test_connection_pattern_returns_conn_no_internet(self):
        code, _ = format_api_error("openai", ValueError("connection refused"))
        assert code == "CONN_NO_INTERNET"

    def test_network_pattern_returns_conn_no_internet(self):
        code, _ = format_api_error("openai", ValueError("network error"))
        assert code == "CONN_NO_INTERNET"

    def test_connection_details_contains_provider(self):
        _, details = format_api_error("openai", ValueError("connection error"))
        assert "Openai" in details

    def test_unknown_pattern_returns_unknown_error(self):
        code, _ = format_api_error("openai", ValueError("something completely different"))
        assert code == "UNKNOWN_ERROR"

    def test_unknown_error_details_is_error_string(self):
        error = ValueError("something completely different")
        _, details = format_api_error("openai", error)
        assert details == str(error)

    def test_provider_name_is_title_cased_in_details(self):
        _, details = format_api_error("openai", ValueError("api key error"))
        assert "Openai" in details

    def test_exception_type_does_not_affect_pattern_matching(self):
        code, _ = format_api_error("openai", RuntimeError("rate limit hit"))
        assert code == "API_RATE_LIMIT"

    def test_model_only_without_not_found_returns_non_model_code(self):
        code, _ = format_api_error("openai", ValueError("model is loading"))
        assert code != "API_MODEL_NOT_FOUND"

    def test_not_found_only_without_model_returns_non_model_code(self):
        code, _ = format_api_error("openai", ValueError("resource not found"))
        assert code != "API_MODEL_NOT_FOUND"

    def test_case_insensitive_api_key_match(self):
        code, _ = format_api_error("openai", ValueError("API KEY is wrong"))
        assert code == "API_KEY_INVALID"

    def test_case_insensitive_rate_limit_match(self):
        code, _ = format_api_error("openai", ValueError("Rate Limit exceeded"))
        assert code == "API_RATE_LIMIT"


# =============================================================================
# TestErrorMessageMapper
# =============================================================================

class TestErrorMessageMapper:
    """Tests for ErrorMessageMapper class attributes and methods."""

    # --- Class attribute structure ---

    def test_api_errors_is_dict(self):
        assert isinstance(ErrorMessageMapper.API_ERRORS, dict)

    def test_audio_errors_is_dict(self):
        assert isinstance(ErrorMessageMapper.AUDIO_ERRORS, dict)

    def test_database_errors_is_dict(self):
        assert isinstance(ErrorMessageMapper.DATABASE_ERRORS, dict)

    def test_file_errors_is_dict(self):
        assert isinstance(ErrorMessageMapper.FILE_ERRORS, dict)

    def test_network_errors_is_dict(self):
        assert isinstance(ErrorMessageMapper.NETWORK_ERRORS, dict)

    def test_processing_errors_is_dict(self):
        assert isinstance(ErrorMessageMapper.PROCESSING_ERRORS, dict)

    def test_api_errors_non_empty(self):
        assert len(ErrorMessageMapper.API_ERRORS) > 0

    def test_audio_errors_non_empty(self):
        assert len(ErrorMessageMapper.AUDIO_ERRORS) > 0

    def test_database_errors_non_empty(self):
        assert len(ErrorMessageMapper.DATABASE_ERRORS) > 0

    def test_file_errors_non_empty(self):
        assert len(ErrorMessageMapper.FILE_ERRORS) > 0

    def test_network_errors_non_empty(self):
        assert len(ErrorMessageMapper.NETWORK_ERRORS) > 0

    def test_processing_errors_non_empty(self):
        assert len(ErrorMessageMapper.PROCESSING_ERRORS) > 0

    # --- get_user_message return types ---

    def test_get_user_message_returns_tuple(self):
        result = ErrorMessageMapper.get_user_message(ValueError("some error"))
        assert isinstance(result, tuple)

    def test_get_user_message_returns_2_tuple(self):
        result = ErrorMessageMapper.get_user_message(ValueError("some error"))
        assert len(result) == 2

    def test_get_user_message_first_element_string(self):
        msg, _ = ErrorMessageMapper.get_user_message(ValueError("some error"))
        assert isinstance(msg, str)

    def test_get_user_message_second_element_string(self):
        _, details = ErrorMessageMapper.get_user_message(ValueError("some error"))
        assert isinstance(details, str)

    def test_second_element_is_str_of_error(self):
        error = ValueError("original error text")
        _, details = ErrorMessageMapper.get_user_message(error)
        assert details == str(error)

    # --- API_ERRORS key matching ---

    def test_matches_invalid_api_key_in_api_errors(self):
        error = ValueError("Invalid API key detected")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.API_ERRORS["Invalid API key"]

    def test_matches_rate_limit_exceeded_in_api_errors(self):
        error = ValueError("Rate limit exceeded by provider")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.API_ERRORS["Rate limit exceeded"]

    def test_matches_model_not_found_in_api_errors(self):
        error = ValueError("Model not found in registry")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.API_ERRORS["Model not found"]

    def test_matches_connection_timeout_in_api_errors(self):
        error = ValueError("connection timeout occurred")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.API_ERRORS["Connection timeout"]

    # --- AUDIO_ERRORS key matching ---

    def test_matches_no_microphone_in_audio_errors(self):
        error = ValueError("No microphone found on this device")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.AUDIO_ERRORS["No microphone"]

    def test_matches_recording_failed_in_audio_errors(self):
        error = ValueError("recording failed to start")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.AUDIO_ERRORS["Recording failed"]

    def test_matches_audio_device_busy(self):
        error = ValueError("audio device busy right now")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.AUDIO_ERRORS["Audio device busy"]

    # --- DATABASE_ERRORS key matching ---

    def test_matches_database_locked(self):
        error = ValueError("database locked by another process")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.DATABASE_ERRORS["Database locked"]

    def test_matches_database_corrupt(self):
        error = ValueError("database corrupt, cannot read")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.DATABASE_ERRORS["Database corrupt"]

    def test_matches_disk_full_database_category_first(self):
        # "Disk full" appears in DATABASE_ERRORS and FILE_ERRORS;
        # DATABASE_ERRORS is iterated first so it wins
        error = ValueError("disk full, cannot write")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert msg == ErrorMessageMapper.DATABASE_ERRORS["Disk full"]

    # --- Exception type name fallbacks ---

    def test_connectionerror_type_returns_connection_message(self):
        error = ConnectionError("failed to connect")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert "connection" in msg.lower()

    def test_timeouterror_type_returns_timeout_message(self):
        error = TimeoutError("operation timed out")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert "timed out" in msg.lower() or "timeout" in msg.lower()

    def test_permissionerror_type_returns_permission_message(self):
        error = PermissionError("access denied")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert "permission" in msg.lower()

    def test_filenotfounderror_type_returns_file_message(self):
        error = FileNotFoundError("no such file")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert "file" in msg.lower() or "not found" in msg.lower()

    def test_memoryerror_type_returns_memory_message(self):
        error = MemoryError("cannot allocate")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert "memory" in msg.lower()

    # --- Generic fallback ---

    def test_unknown_error_returns_generic_message(self):
        error = ValueError("xyzzy_totally_unrecognised_string_42")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert "unexpected error" in msg.lower() or "error occurred" in msg.lower()

    def test_unknown_error_with_context_mentions_context(self):
        error = ValueError("xyzzy_totally_unrecognised_string_42")
        msg, _ = ErrorMessageMapper.get_user_message(error, context="processing audio")
        assert "processing audio" in msg

    # --- Context prepending ---

    def test_context_prepended_with_error_while(self):
        error = ValueError("Invalid API key check")
        msg, _ = ErrorMessageMapper.get_user_message(error, context="calling API")
        assert msg.startswith("Error while calling API:")

    def test_no_context_no_error_while_prefix(self):
        error = ValueError("Invalid API key check")
        msg, _ = ErrorMessageMapper.get_user_message(error)
        assert not msg.startswith("Error while")

    # --- _format_message ---

    def test_format_message_without_context_returns_message_unchanged(self):
        result = ErrorMessageMapper._format_message("Something went wrong.")
        assert result == "Something went wrong."

    def test_format_message_with_context_prepends_error_while(self):
        result = ErrorMessageMapper._format_message("Something went wrong.", context="saving file")
        assert result == "Error while saving file: Something went wrong."

    def test_format_message_context_none_same_as_omitted(self):
        result = ErrorMessageMapper._format_message("Oops.", context=None)
        assert result == "Oops."

    def test_format_message_empty_message_with_context(self):
        result = ErrorMessageMapper._format_message("", context="doing something")
        assert result == "Error while doing something: "

    # --- get_retry_suggestion ---

    def test_retry_suggestion_rate_limit_is_not_none(self):
        error = ValueError("rate limit exceeded")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None

    def test_retry_suggestion_rate_limit_mentions_wait(self):
        error = ValueError("rate limit exceeded")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert "60" in suggestion or "wait" in suggestion.lower()

    def test_retry_suggestion_timeout_is_not_none(self):
        error = ValueError("request timeout")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None

    def test_retry_suggestion_timeout_mentions_internet(self):
        error = ValueError("request timeout")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert "internet" in suggestion.lower() or "try again" in suggestion.lower()

    def test_retry_suggestion_connection_is_not_none(self):
        error = ValueError("connection failed")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None

    def test_retry_suggestion_database_locked_is_not_none(self):
        error = ValueError("database locked by process")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None

    def test_retry_suggestion_database_locked_mentions_wait(self):
        error = ValueError("database locked by process")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert "wait" in suggestion.lower() or "seconds" in suggestion.lower()

    def test_retry_suggestion_out_of_memory_is_not_none(self):
        error = MemoryError("out of memory")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None

    def test_retry_suggestion_out_of_memory_mentions_applications(self):
        error = MemoryError("out of memory")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert "close" in suggestion.lower() or "application" in suggestion.lower()

    def test_retry_suggestion_permission_is_not_none(self):
        error = PermissionError("permission denied")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None

    def test_retry_suggestion_permission_mentions_permissions(self):
        error = PermissionError("permission denied")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert "permission" in suggestion.lower()

    def test_retry_suggestion_unknown_returns_none(self):
        error = ValueError("xyzzy_totally_unrecognised_string_99")
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is None

    def test_retry_suggestion_returns_string_or_none(self):
        for error in [
            ValueError("rate limit hit"),
            ValueError("some unrelated error"),
            TimeoutError("timed out"),
        ]:
            result = ErrorMessageMapper.get_retry_suggestion(error)
            assert result is None or isinstance(result, str)


# =============================================================================
# TestGetUserFriendlyError
# =============================================================================

class TestGetUserFriendlyError:
    """Tests for get_user_friendly_error()."""

    def test_returns_string(self):
        result = get_user_friendly_error(ValueError("some error"))
        assert isinstance(result, str)

    def test_returns_non_empty_string(self):
        result = get_user_friendly_error(ValueError("some error"))
        assert result.strip() != ""

    def test_with_context_includes_context(self):
        result = get_user_friendly_error(
            ValueError("xyzzy_totally_unknown_error"),
            context="processing audio"
        )
        assert "processing audio" in result

    def test_without_context_is_string(self):
        result = get_user_friendly_error(ValueError("xyzzy_totally_unknown_error"))
        assert isinstance(result, str)

    def test_delegates_to_error_message_mapper(self):
        error = ValueError("Invalid API key supplied")
        result = get_user_friendly_error(error)
        expected, _ = ErrorMessageMapper.get_user_message(error)
        assert result == expected

    def test_known_api_error_recognized(self):
        error = ValueError("rate limit exceeded on API")
        result = get_user_friendly_error(error)
        assert "rate limit" in result.lower() or "wait" in result.lower()

    def test_known_audio_error_recognized(self):
        error = ValueError("no microphone detected")
        result = get_user_friendly_error(error)
        assert "microphone" in result.lower()

    def test_connection_error_type_recognized(self):
        result = get_user_friendly_error(ConnectionError("cannot connect"))
        assert "connection" in result.lower()


# =============================================================================
# TestFormatErrorWithRetry
# =============================================================================

class TestFormatErrorWithRetry:
    """Tests for format_error_with_retry()."""

    def test_returns_string(self):
        result = format_error_with_retry(ValueError("some error"))
        assert isinstance(result, str)

    def test_returns_non_empty_string(self):
        result = format_error_with_retry(ValueError("some error"))
        assert result.strip() != ""

    def test_rate_limit_error_adds_retry_suggestion(self):
        error = ValueError("rate limit exceeded")
        result = format_error_with_retry(error)
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert suggestion is not None
        assert suggestion in result

    def test_rate_limit_result_has_double_newline_separator(self):
        error = ValueError("rate limit exceeded")
        result = format_error_with_retry(error)
        assert "\n\n" in result

    def test_both_message_and_suggestion_present_for_rate_limit(self):
        error = ValueError("rate limit exceeded")
        result = format_error_with_retry(error)
        user_message = get_user_friendly_error(error)
        suggestion = ErrorMessageMapper.get_retry_suggestion(error)
        assert user_message in result
        assert suggestion in result

    def test_unknown_error_no_double_newline_separator(self):
        error = ValueError("xyzzy_totally_unrecognised_string_77")
        result = format_error_with_retry(error)
        assert "\n\n" not in result

    def test_unknown_error_result_equals_user_friendly_message(self):
        error = ValueError("xyzzy_totally_unrecognised_string_77")
        result = format_error_with_retry(error)
        user_message = get_user_friendly_error(error)
        assert result == user_message

    def test_timeout_error_adds_retry_suggestion(self):
        error = ValueError("request timeout")
        result = format_error_with_retry(error)
        assert "\n\n" in result

    def test_with_context_includes_context_in_message(self):
        error = ValueError("xyzzy_totally_unrecognised_string_55")
        result = format_error_with_retry(error, context="saving the file")
        assert "saving the file" in result

    def test_connection_error_adds_retry_suggestion(self):
        error = ValueError("connection refused")
        result = format_error_with_retry(error)
        assert "\n\n" in result

    def test_database_locked_adds_retry_suggestion(self):
        error = ValueError("database locked by process")
        result = format_error_with_retry(error)
        assert "\n\n" in result
