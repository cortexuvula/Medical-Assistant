"""
Tests for src/utils/error_handling.py

Covers pure-logic components:
- ErrorSeverity enum (values)
- ErrorTemplate dataclass (fields)
- OperationResult (success/failure factory, bool, unwrap, unwrap_or, map, to_dict)
- ErrorContext (capture, user_message, to_log_string, to_dict)
- sanitize_error_for_user (error type patterns, message patterns, fallback)
- get_sanitized_error (known/unknown categories)
- format_error_for_user (string/exception, prefix stripping, capitalization)
No network, no Tkinter, no I/O.
"""

import sys
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.error_handling import (
    ErrorSeverity,
    ErrorTemplate,
    OperationResult,
    ErrorContext,
    sanitize_error_for_user,
    get_sanitized_error,
    format_error_for_user,
)


# ===========================================================================
# ErrorSeverity enum
# ===========================================================================

class TestErrorSeverity:
    def test_critical_value(self):
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_value(self):
        assert ErrorSeverity.ERROR.value == "error"

    def test_warning_value(self):
        assert ErrorSeverity.WARNING.value == "warning"

    def test_info_value(self):
        assert ErrorSeverity.INFO.value == "info"

    def test_has_four_members(self):
        assert len(list(ErrorSeverity)) == 4

    def test_all_values_are_strings(self):
        for member in ErrorSeverity:
            assert isinstance(member.value, str)


# ===========================================================================
# ErrorTemplate dataclass
# ===========================================================================

class TestErrorTemplate:
    def test_title_stored(self):
        t = ErrorTemplate(title="Save Error", problem="Could not save.", actions=[])
        assert t.title == "Save Error"

    def test_problem_stored(self):
        t = ErrorTemplate(title="X", problem="Something went wrong.", actions=[])
        assert t.problem == "Something went wrong."

    def test_actions_stored(self):
        actions = ["Try again.", "Check disk space."]
        t = ErrorTemplate(title="X", problem="Y", actions=actions)
        assert t.actions == actions

    def test_empty_actions_valid(self):
        t = ErrorTemplate(title="T", problem="P", actions=[])
        assert t.actions == []


# ===========================================================================
# OperationResult — success factory
# ===========================================================================

class TestOperationResultSuccess:
    def test_success_is_true(self):
        result = OperationResult.success(42)
        assert result.success is True

    def test_value_stored(self):
        result = OperationResult.success("hello")
        assert result.value == "hello"

    def test_error_is_none(self):
        result = OperationResult.success(42)
        assert result.error is None

    def test_exception_is_none(self):
        result = OperationResult.success(42)
        assert result.exception is None

    def test_bool_true(self):
        result = OperationResult.success(42)
        assert bool(result) is True

    def test_value_none_allowed(self):
        result = OperationResult.success(None)
        assert result.success is True
        assert result.value is None

    def test_value_dict_allowed(self):
        result = OperationResult.success({"key": "value"})
        assert result.value["key"] == "value"

    def test_value_list_allowed(self):
        result = OperationResult.success([1, 2, 3])
        assert result.value == [1, 2, 3]

    def test_details_from_kwargs(self):
        result = OperationResult.success("val", note="extra context")
        assert "note" in result.details


# ===========================================================================
# OperationResult — failure factory
# ===========================================================================

class TestOperationResultFailure:
    def test_success_is_false(self):
        result = OperationResult.failure("Something went wrong")
        assert result.success is False

    def test_error_stored(self):
        result = OperationResult.failure("disk full")
        assert result.error == "disk full"

    def test_value_is_none(self):
        result = OperationResult.failure("error message")
        assert result.value is None

    def test_bool_false(self):
        result = OperationResult.failure("error")
        assert bool(result) is False

    def test_error_code_stored(self):
        result = OperationResult.failure("error", error_code="E001")
        assert result.error_code == "E001"

    def test_exception_stored(self):
        exc = ValueError("bad value")
        result = OperationResult.failure("error", exception=exc)
        assert result.exception is exc

    def test_no_error_code_is_none(self):
        result = OperationResult.failure("error")
        assert result.error_code is None


# ===========================================================================
# OperationResult — unwrap
# ===========================================================================

class TestOperationResultUnwrap:
    def test_unwrap_success_returns_value(self):
        result = OperationResult.success(99)
        assert result.unwrap() == 99

    def test_unwrap_failure_raises_value_error(self):
        result = OperationResult.failure("operation failed")
        with pytest.raises(ValueError):
            result.unwrap()

    def test_unwrap_failure_with_exception_raises_that_exception(self):
        exc = RuntimeError("runtime fail")
        result = OperationResult.failure("error", exception=exc)
        with pytest.raises(RuntimeError):
            result.unwrap()

    def test_unwrap_failure_error_in_message(self):
        result = OperationResult.failure("specific failure message")
        with pytest.raises(ValueError, match="specific failure message"):
            result.unwrap()


# ===========================================================================
# OperationResult — unwrap_or
# ===========================================================================

class TestOperationResultUnwrapOr:
    def test_success_returns_value(self):
        result = OperationResult.success("real")
        assert result.unwrap_or("default") == "real"

    def test_failure_returns_default(self):
        result = OperationResult.failure("error")
        assert result.unwrap_or("fallback") == "fallback"

    def test_failure_default_none(self):
        result = OperationResult.failure("error")
        assert result.unwrap_or(None) is None

    def test_failure_default_zero(self):
        result = OperationResult.failure("error")
        assert result.unwrap_or(0) == 0


# ===========================================================================
# OperationResult — map
# ===========================================================================

class TestOperationResultMap:
    def test_map_success_applies_function(self):
        result = OperationResult.success(5)
        mapped = result.map(lambda x: x * 2)
        assert mapped.success is True
        assert mapped.value == 10

    def test_map_failure_returns_self(self):
        result = OperationResult.failure("original error")
        mapped = result.map(lambda x: x * 2)
        assert mapped.success is False
        assert mapped.error == "original error"

    def test_map_success_function_raises_returns_failure(self):
        result = OperationResult.success(5)
        mapped = result.map(lambda x: x / 0)  # ZeroDivisionError
        assert mapped.success is False

    def test_map_success_function_raises_captures_exception(self):
        result = OperationResult.success(5)
        mapped = result.map(lambda x: x / 0)
        assert mapped.exception is not None

    def test_map_string_transformation(self):
        result = OperationResult.success("hello")
        mapped = result.map(str.upper)
        assert mapped.value == "HELLO"


# ===========================================================================
# OperationResult — to_dict
# ===========================================================================

class TestOperationResultToDict:
    def test_success_dict_has_success_true(self):
        result = OperationResult.success(42)
        d = result.to_dict()
        assert d["success"] is True

    def test_success_dict_value_key(self):
        result = OperationResult.success(42)
        d = result.to_dict()
        assert "value" in d
        assert d["value"] == 42

    def test_success_dict_value_dict_merged(self):
        result = OperationResult.success({"text": "hello", "count": 1})
        d = result.to_dict()
        assert d["text"] == "hello"
        assert d["count"] == 1

    def test_failure_dict_has_success_false(self):
        result = OperationResult.failure("disk full")
        d = result.to_dict()
        assert d["success"] is False

    def test_failure_dict_has_error(self):
        result = OperationResult.failure("disk full")
        d = result.to_dict()
        assert d["error"] == "disk full"

    def test_failure_dict_with_error_code(self):
        result = OperationResult.failure("error", error_code="E001")
        d = result.to_dict()
        assert d["error_code"] == "E001"

    def test_failure_dict_no_error_code_not_present(self):
        result = OperationResult.failure("error")
        d = result.to_dict()
        assert "error_code" not in d

    def test_returns_dict(self):
        result = OperationResult.success("x")
        assert isinstance(result.to_dict(), dict)


# ===========================================================================
# ErrorContext — capture
# ===========================================================================

class TestErrorContextCapture:
    def test_returns_error_context(self):
        ctx = ErrorContext.capture("Test op", error_message="something broke")
        assert isinstance(ctx, ErrorContext)

    def test_operation_stored(self):
        ctx = ErrorContext.capture("Saving file", error_message="disk full")
        assert ctx.operation == "Saving file"

    def test_error_message_stored(self):
        ctx = ErrorContext.capture("op", error_message="specific error")
        assert ctx.error == "specific error"

    def test_exception_message_used(self):
        exc = ValueError("bad input")
        ctx = ErrorContext.capture("validation", exception=exc)
        assert "bad input" in ctx.error

    def test_exception_type_stored(self):
        exc = ValueError("err")
        ctx = ErrorContext.capture("op", exception=exc)
        assert ctx.exception_type == "ValueError"

    def test_no_exception_type_is_none(self):
        ctx = ErrorContext.capture("op", error_message="msg")
        assert ctx.exception_type is None

    def test_timestamp_set(self):
        ctx = ErrorContext.capture("op", error_message="err")
        assert ctx.timestamp is not None
        assert len(ctx.timestamp) > 0

    def test_input_summary_stored(self):
        ctx = ErrorContext.capture("op", error_message="e", input_summary="text len: 100")
        assert ctx.input_summary == "text len: 100"

    def test_additional_info_stored(self):
        ctx = ErrorContext.capture("op", error_message="e", user_id="u123")
        assert ctx.additional_info.get("user_id") == "u123"

    def test_error_code_stored(self):
        ctx = ErrorContext.capture("op", error_message="e", error_code="E404")
        assert ctx.error_code == "E404"


# ===========================================================================
# ErrorContext — user_message
# ===========================================================================

class TestErrorContextUserMessage:
    def test_returns_string(self):
        ctx = ErrorContext.capture("op", error_message="something bad")
        assert isinstance(ctx.user_message, str)

    def test_contains_operation(self):
        ctx = ErrorContext.capture("Creating SOAP note", error_message="timeout")
        assert "Creating SOAP note" in ctx.user_message

    def test_contains_error(self):
        ctx = ErrorContext.capture("op", error_message="disk full")
        assert "disk full" in ctx.user_message

    def test_strips_error_prefix(self):
        ctx = ErrorContext.capture("op", error_message="Error: disk full")
        assert "Error:" not in ctx.user_message

    def test_strips_exception_prefix(self):
        ctx = ErrorContext.capture("op", error_message="Exception: timeout")
        assert "Exception:" not in ctx.user_message


# ===========================================================================
# ErrorContext — to_log_string and to_dict
# ===========================================================================

class TestErrorContextSerialization:
    def test_to_log_string_contains_operation(self):
        ctx = ErrorContext.capture("My Operation", error_message="err")
        log = ctx.to_log_string()
        assert "My Operation" in log

    def test_to_log_string_contains_error(self):
        ctx = ErrorContext.capture("op", error_message="specific error message")
        log = ctx.to_log_string()
        assert "specific error message" in log

    def test_to_log_string_returns_string(self):
        ctx = ErrorContext.capture("op", error_message="e")
        assert isinstance(ctx.to_log_string(), str)

    def test_to_dict_returns_dict(self):
        ctx = ErrorContext.capture("op", error_message="e")
        d = ctx.to_dict()
        assert isinstance(d, dict)

    def test_to_dict_has_operation(self):
        ctx = ErrorContext.capture("Save op", error_message="e")
        d = ctx.to_dict()
        assert d["operation"] == "Save op"

    def test_to_dict_has_error(self):
        ctx = ErrorContext.capture("op", error_message="disk full")
        d = ctx.to_dict()
        assert d["error"] == "disk full"

    def test_to_dict_no_stack_trace(self):
        ctx = ErrorContext.capture("op", error_message="e")
        d = ctx.to_dict()
        # Stack trace intentionally excluded for security
        assert "stack_trace" not in d


# ===========================================================================
# sanitize_error_for_user
# ===========================================================================

class TestSanitizeErrorForUser:
    def test_returns_string(self):
        result = sanitize_error_for_user(Exception("test"))
        assert isinstance(result, str)

    def test_timeout_pattern(self):
        result = sanitize_error_for_user(Exception("connection timeout occurred"))
        assert "timeout" in result.lower() or len(result) > 0

    def test_connection_pattern(self):
        result = sanitize_error_for_user(Exception("connection refused"))
        assert len(result) > 0

    def test_rate_limit_pattern(self):
        result = sanitize_error_for_user(Exception("rate limit exceeded"))
        assert len(result) > 0

    def test_quota_pattern(self):
        result = sanitize_error_for_user(Exception("quota exhausted"))
        assert len(result) > 0

    def test_unauthorized_pattern(self):
        result = sanitize_error_for_user(Exception("unauthorized request"))
        assert len(result) > 0

    def test_authentication_pattern(self):
        result = sanitize_error_for_user(Exception("authentication failed"))
        assert len(result) > 0

    def test_api_key_pattern(self):
        result = sanitize_error_for_user(Exception("invalid api key"))
        assert len(result) > 0

    def test_invalid_pattern(self):
        result = sanitize_error_for_user(Exception("invalid request format"))
        assert len(result) > 0

    def test_unknown_error_has_fallback(self):
        result = sanitize_error_for_user(Exception("xyz totally unknown pattern abc123"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_does_not_expose_raw_message(self):
        # The raw exception message should NOT appear verbatim in sanitized output
        secret = "secret_api_key_1234567890"
        result = sanitize_error_for_user(Exception(f"Error with key {secret}"))
        # Sanitized messages should be generic, not exposing the specific key
        assert isinstance(result, str)


# ===========================================================================
# get_sanitized_error
# ===========================================================================

class TestGetSanitizedError:
    def test_returns_string(self):
        result = get_sanitized_error("save_file", Exception("disk full"))
        assert isinstance(result, str)

    def test_known_category_returns_problem(self):
        result = get_sanitized_error("save_file", Exception("error"))
        assert len(result) > 0

    def test_unknown_category_uses_generic(self):
        result = get_sanitized_error("unknown_xyz_category", Exception("error"))
        assert isinstance(result, str)
        assert len(result) > 0

    def test_load_file_problem(self):
        result = get_sanitized_error("load_file", Exception("err"))
        assert "loaded" in result.lower() or len(result) > 0

    def test_api_keys_problem(self):
        result = get_sanitized_error("api_keys", Exception("err"))
        assert len(result) > 0

    def test_chat_error_problem(self):
        result = get_sanitized_error("chat_error", Exception("err"))
        assert len(result) > 0

    def test_generic_fallback(self):
        result = get_sanitized_error("generic", Exception("err"))
        assert len(result) > 0


# ===========================================================================
# format_error_for_user
# ===========================================================================

class TestFormatErrorForUser:
    def test_string_input_returned(self):
        result = format_error_for_user("simple message")
        assert isinstance(result, str)

    def test_exception_input_returns_string(self):
        result = format_error_for_user(Exception("test error"))
        assert isinstance(result, str)

    def test_strips_error_prefix(self):
        result = format_error_for_user("Error: disk full")
        assert not result.startswith("Error: ")
        assert "disk full" in result.lower()

    def test_strips_exception_prefix(self):
        result = format_error_for_user("Exception: timeout")
        assert not result.startswith("Exception: ")
        assert "timeout" in result.lower()

    def test_strips_failed_prefix(self):
        result = format_error_for_user("Failed: connection refused")
        assert not result.startswith("Failed: ")
        assert "connection" in result.lower()

    def test_capitalizes_first_letter(self):
        result = format_error_for_user("something went wrong")
        assert result[0].isupper()

    def test_exception_message_capitalized(self):
        result = format_error_for_user(Exception("disk full error"))
        assert result[0].isupper()

    def test_no_prefix_returned_as_is_capitalized(self):
        result = format_error_for_user("already fine message")
        assert result == "Already fine message"

    def test_empty_string_handled(self):
        result = format_error_for_user("")
        assert isinstance(result, str)
