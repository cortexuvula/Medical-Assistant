"""
Unit tests for src/utils/error_handling.py — pure logic only, no Tkinter.

Covers:
- sanitize_error_for_user
- get_sanitized_error
- ErrorSeverity enum
- OperationResult (success/failure, to_dict, bool, unwrap, unwrap_or, map)
- format_error_for_user
- ErrorContext (capture, user_message, to_log_string, to_dict)
- handle_errors decorator
- safe_execute
- _USER_FRIENDLY_ERRORS and _ERROR_TEMPLATES data integrity
"""

import logging
import pytest
import sys

sys.path.insert(0, "src")

from utils.error_handling import (
    sanitize_error_for_user,
    get_sanitized_error,
    format_error_for_user,
    ErrorSeverity,
    OperationResult,
    ErrorContext,
    handle_errors,
    safe_execute,
    log_and_raise,
    _USER_FRIENDLY_ERRORS,
    _ERROR_TEMPLATES,
)


# ---------------------------------------------------------------------------
# Custom exception types used throughout tests
# ---------------------------------------------------------------------------

class AuthenticationError(Exception):
    """Simulates an API AuthenticationError."""


class RateLimitError(Exception):
    """Simulates an API RateLimitError."""


class APIConnectionError(Exception):
    """Simulates an API connection error."""


class TimeoutError(Exception):  # noqa: A001
    """Simulates a Timeout error (type name contains 'Timeout')."""


class InvalidRequestError(Exception):
    """Simulates an InvalidRequestError."""


class APIError(Exception):
    """Simulates a generic APIError."""


class ServiceUnavailableError(Exception):
    """Simulates a ServiceUnavailableError."""


# ===========================================================================
# 1. sanitize_error_for_user
# ===========================================================================

class TestSanitizeErrorForUserTypeNameMatching:
    """Type-name pattern matching via _USER_FRIENDLY_ERRORS dict."""

    def test_authentication_error_returns_api_auth_message(self):
        result = sanitize_error_for_user(AuthenticationError("sk-secret"))
        assert result == _USER_FRIENDLY_ERRORS["AuthenticationError"]

    def test_authentication_error_does_not_expose_api_key(self):
        result = sanitize_error_for_user(AuthenticationError("sk-secret-key-12345"))
        assert "sk-secret-key-12345" not in result

    def test_rate_limit_error_returns_rate_limit_message(self):
        result = sanitize_error_for_user(RateLimitError("throttled"))
        assert result == _USER_FRIENDLY_ERRORS["RateLimitError"]

    def test_api_connection_error_returns_connection_message(self):
        result = sanitize_error_for_user(APIConnectionError("host unreachable"))
        assert result == _USER_FRIENDLY_ERRORS["APIConnectionError"]

    def test_timeout_error_type_name_matched(self):
        result = sanitize_error_for_user(TimeoutError("30s exceeded"))
        assert result == _USER_FRIENDLY_ERRORS["Timeout"]

    def test_invalid_request_error_returns_invalid_message(self):
        result = sanitize_error_for_user(InvalidRequestError("bad JSON body"))
        assert result == _USER_FRIENDLY_ERRORS["InvalidRequestError"]

    def test_api_error_returns_api_error_message(self):
        result = sanitize_error_for_user(APIError("500 internal"))
        assert result == _USER_FRIENDLY_ERRORS["APIError"]

    def test_service_unavailable_error_matched(self):
        result = sanitize_error_for_user(ServiceUnavailableError("down"))
        assert result == _USER_FRIENDLY_ERRORS["ServiceUnavailableError"]

    def test_type_name_match_is_case_insensitive(self):
        class MyAuthenticationError(Exception):
            pass
        result = sanitize_error_for_user(MyAuthenticationError("oops"))
        assert result == _USER_FRIENDLY_ERRORS["AuthenticationError"]

    def test_type_name_match_takes_precedence_over_message_keywords(self):
        # AuthenticationError class name matches before "connection" in message
        result = sanitize_error_for_user(AuthenticationError("connection refused"))
        assert result == _USER_FRIENDLY_ERRORS["AuthenticationError"]

    def test_result_is_always_a_string(self):
        assert isinstance(sanitize_error_for_user(ValueError("x")), str)


class TestSanitizeErrorForUserMessageKeywords:
    """Keyword-in-message fallback path."""

    def test_timeout_in_message_returns_timeout_text(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("Request timeout after 10s"))
        assert "timed out" in result.lower()

    def test_connection_keyword_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("connection refused"))
        assert "connect" in result.lower()

    def test_connect_keyword_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("failed to connect"))
        assert "connect" in result.lower()

    def test_rate_limit_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("you exceeded the rate limit"))
        assert "rate limit" in result.lower() or "wait" in result.lower()

    def test_quota_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("quota exceeded for today"))
        assert "rate limit" in result.lower() or "quota" in result.lower() or "wait" in result.lower()

    def test_unauthorized_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("401 unauthorized"))
        assert "authentication" in result.lower() or "api key" in result.lower()

    def test_api_key_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("invalid api key supplied"))
        assert "authentication" in result.lower() or "api key" in result.lower()

    def test_invalid_in_message(self):
        class GenericError(Exception):
            pass
        result = sanitize_error_for_user(GenericError("invalid parameter value"))
        assert "invalid" in result.lower()

    def test_generic_fallback_for_unknown_error(self):
        class WeirdObscureError(Exception):
            pass
        result = sanitize_error_for_user(WeirdObscureError("xyzzy-completely-unknown-abc123"))
        assert result == "An error occurred while processing your request. Please try again."


# ===========================================================================
# 2. get_sanitized_error
# ===========================================================================

class TestGetSanitizedError:
    """Tests for get_sanitized_error()."""

    def test_save_file_returns_correct_problem(self):
        assert get_sanitized_error("save_file", ValueError("x")) == "The file could not be saved."

    def test_load_file_returns_correct_problem(self):
        assert get_sanitized_error("load_file", FileNotFoundError("missing")) == "The file could not be loaded."

    def test_generic_returns_unexpected_error(self):
        assert get_sanitized_error("generic", Exception()) == "An unexpected error occurred."

    def test_unknown_category_falls_back_to_generic(self):
        assert get_sanitized_error("nonexistent_xyz", Exception()) == "An unexpected error occurred."

    def test_export_pdf_category(self):
        assert get_sanitized_error("export_pdf", Exception()) == "The PDF could not be exported."

    def test_export_word_category(self):
        assert get_sanitized_error("export_word", Exception()) == "The Word document could not be exported."

    def test_chat_error_category(self):
        assert get_sanitized_error("chat_error", Exception()) == "An error occurred in the chat interface."

    def test_return_type_is_string(self):
        assert isinstance(get_sanitized_error("save_file", Exception()), str)

    def test_error_argument_not_exposed_in_output(self):
        secret = "top-secret-trace-abc123"
        result = get_sanitized_error("save_file", Exception(secret))
        assert secret not in result

    def test_print_document_category(self):
        assert get_sanitized_error("print_document", Exception()) == "The document could not be printed."

    def test_save_settings_category(self):
        assert get_sanitized_error("save_settings", Exception()) == "Settings could not be saved."


# ===========================================================================
# 3. ErrorSeverity enum
# ===========================================================================

class TestErrorSeverity:
    """Tests for the ErrorSeverity enum."""

    def test_critical_value(self):
        assert ErrorSeverity.CRITICAL.value == "critical"

    def test_error_value(self):
        assert ErrorSeverity.ERROR.value == "error"

    def test_warning_value(self):
        assert ErrorSeverity.WARNING.value == "warning"

    def test_info_value(self):
        assert ErrorSeverity.INFO.value == "info"

    def test_four_members(self):
        assert len(list(ErrorSeverity)) == 4

    def test_members_are_distinct(self):
        members = list(ErrorSeverity)
        assert len(members) == len(set(m.value for m in members))

    def test_critical_is_enum_member(self):
        assert isinstance(ErrorSeverity.CRITICAL, ErrorSeverity)

    def test_error_is_enum_member(self):
        assert isinstance(ErrorSeverity.ERROR, ErrorSeverity)


# ===========================================================================
# 4. OperationResult
# ===========================================================================

class TestOperationResultSuccessFactory:
    """OperationResult.success() factory and truthy/value access."""

    def test_success_flag_is_true(self):
        assert OperationResult.success("x").success is True

    def test_value_stored(self):
        assert OperationResult.success(42).value == 42

    def test_none_value_accepted(self):
        assert OperationResult.success(None).success is True

    def test_dict_value_stored(self):
        assert OperationResult.success({"k": "v"}).value == {"k": "v"}

    def test_extra_details_stored(self):
        r = OperationResult.success("ok", count=5, label="test")
        assert r.details["count"] == 5
        assert r.details["label"] == "test"

    def test_error_is_none(self):
        assert OperationResult.success("x").error is None

    def test_exception_is_none(self):
        assert OperationResult.success("x").exception is None

    def test_bool_is_true(self):
        assert bool(OperationResult.success("x")) is True


class TestOperationResultFailureFactory:
    """OperationResult.failure() factory and falsy/error access."""

    def test_success_flag_is_false(self):
        assert OperationResult.failure("oops").success is False

    def test_error_message_stored(self):
        assert OperationResult.failure("disk full").error == "disk full"

    def test_value_is_none(self):
        assert OperationResult.failure("oops").value is None

    def test_error_code_stored(self):
        assert OperationResult.failure("oops", error_code="ERR_001").error_code == "ERR_001"

    def test_error_code_none_when_omitted(self):
        assert OperationResult.failure("oops").error_code is None

    def test_exception_stored(self):
        exc = ValueError("bad")
        assert OperationResult.failure("oops", exception=exc).exception is exc

    def test_exception_none_when_omitted(self):
        assert OperationResult.failure("oops").exception is None

    def test_bool_is_false(self):
        assert bool(OperationResult.failure("oops")) is False

    def test_extra_details_stored(self):
        r = OperationResult.failure("err", context="unit test")
        assert r.details["context"] == "unit test"


class TestOperationResultToDict:
    """OperationResult.to_dict() serialisation."""

    def test_success_with_dict_value_merges_keys(self):
        d = OperationResult.success({"text": "hello", "count": 1}).to_dict()
        assert d["success"] is True
        assert d["text"] == "hello"
        assert d["count"] == 1

    def test_success_with_non_dict_value_uses_value_key(self):
        d = OperationResult.success("plain").to_dict()
        assert d["success"] is True
        assert d["value"] == "plain"

    def test_success_with_none_value_no_value_key(self):
        d = OperationResult.success(None).to_dict()
        assert d == {"success": True}

    def test_failure_has_success_false(self):
        assert OperationResult.failure("bad").to_dict()["success"] is False

    def test_failure_has_error_key(self):
        assert OperationResult.failure("bad").to_dict()["error"] == "bad"

    def test_failure_with_error_code_includes_it(self):
        d = OperationResult.failure("oops", error_code="E42").to_dict()
        assert d["error_code"] == "E42"

    def test_failure_without_error_code_omits_key(self):
        assert "error_code" not in OperationResult.failure("oops").to_dict()

    def test_failure_without_error_message_uses_unknown_error(self):
        d = OperationResult(success=False).to_dict()
        assert d["error"] == "Unknown error"


class TestOperationResultUnwrap:
    """OperationResult.unwrap() and unwrap_or()."""

    def test_unwrap_success_returns_value(self):
        assert OperationResult.success("payload").unwrap() == "payload"

    def test_unwrap_failure_with_exception_raises_it(self):
        exc = RuntimeError("original")
        r = OperationResult.failure("err", exception=exc)
        with pytest.raises(RuntimeError):
            r.unwrap()

    def test_unwrap_failure_without_exception_raises_value_error(self):
        with pytest.raises(ValueError):
            OperationResult.failure("something went wrong").unwrap()

    def test_unwrap_failure_no_message_raises_value_error(self):
        with pytest.raises(ValueError, match="Operation failed"):
            OperationResult(success=False).unwrap()

    def test_unwrap_or_on_success_returns_value(self):
        assert OperationResult.success("data").unwrap_or("default") == "data"

    def test_unwrap_or_on_failure_returns_default(self):
        assert OperationResult.failure("err").unwrap_or("fallback") == "fallback"

    def test_unwrap_or_on_failure_none_default(self):
        assert OperationResult.failure("err").unwrap_or(None) is None


class TestOperationResultMap:
    """OperationResult.map()."""

    def test_map_on_success_applies_function(self):
        r = OperationResult.success(10).map(lambda x: x * 2)
        assert r.success is True
        assert r.value == 20

    def test_map_returns_new_result(self):
        original = OperationResult.success(10)
        mapped = original.map(lambda x: x + 1)
        assert mapped is not original

    def test_map_on_failure_returns_same_object(self):
        r = OperationResult.failure("err")
        assert r.map(lambda x: x * 2) is r

    def test_map_on_failure_does_not_call_func(self):
        calls = []
        OperationResult.failure("err").map(lambda x: calls.append(x))
        assert calls == []

    def test_map_when_func_raises_returns_failure(self):
        r = OperationResult.success("data").map(lambda x: 1 / 0)
        assert r.success is False

    def test_map_when_func_raises_captures_exception(self):
        r = OperationResult.success("data").map(lambda x: 1 / 0)
        assert isinstance(r.exception, ZeroDivisionError)

    def test_map_when_func_raises_sets_error_message(self):
        r = OperationResult.success("data").map(lambda x: 1 / 0)
        assert r.error is not None


# ===========================================================================
# 5. format_error_for_user
# ===========================================================================

class TestFormatErrorForUser:
    """Tests for format_error_for_user()."""

    def test_strips_error_colon_prefix(self):
        assert format_error_for_user("Error: something bad") == "Something bad"

    def test_strips_exception_colon_prefix(self):
        assert format_error_for_user("Exception: something bad") == "Something bad"

    def test_strips_failed_colon_prefix(self):
        assert format_error_for_user("Failed: could not load") == "Could not load"

    def test_capitalises_first_letter(self):
        assert format_error_for_user("could not connect") == "Could not connect"

    def test_already_capitalised_unchanged(self):
        assert format_error_for_user("Network is unreachable") == "Network is unreachable"

    def test_works_with_string_input(self):
        result = format_error_for_user("plain message")
        assert isinstance(result, str)

    def test_works_with_exception_input(self):
        result = format_error_for_user(ValueError("Error: wrong value"))
        assert result == "Wrong value"

    def test_empty_string_returns_empty_string(self):
        assert format_error_for_user("") == ""

    def test_only_prefix_becomes_empty_string(self):
        result = format_error_for_user("Error: ")
        assert result == ""

    def test_prefix_check_is_case_sensitive_lowercase_not_stripped(self):
        # "error: " (lowercase e) is NOT the recognised prefix "Error: "
        result = format_error_for_user("error: lowercase not stripped")
        assert result[0].isupper()  # first char capitalised but prefix kept

    def test_multiple_sentences_not_truncated(self):
        result = format_error_for_user("Error: First. Second sentence.")
        assert "Second sentence." in result

    def test_exception_with_no_prefix_capitalised(self):
        result = format_error_for_user(ValueError("lowercase message"))
        assert result == "Lowercase message"


# ===========================================================================
# 6. ErrorContext
# ===========================================================================

class TestErrorContextCapture:
    """ErrorContext.capture() factory."""

    def test_stores_operation(self):
        ctx = ErrorContext.capture(operation="Loading file", exception=ValueError("bad"))
        assert ctx.operation == "Loading file"

    def test_stores_error_from_exception(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("bad value"))
        assert ctx.error == "bad value"

    def test_stores_exception_type(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("x"))
        assert ctx.exception_type == "ValueError"

    def test_with_error_message_param(self):
        ctx = ErrorContext.capture(operation="Op", error_message="custom msg")
        assert ctx.error == "custom msg"

    def test_with_error_message_no_exception_type(self):
        ctx = ErrorContext.capture(operation="Op", error_message="no exc here")
        assert ctx.exception_type is None

    def test_with_input_summary(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("x"), input_summary="len: 42")
        assert ctx.input_summary == "len: 42"

    def test_with_error_code(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("x"), error_code="E_LOAD")
        assert ctx.error_code == "E_LOAD"

    def test_include_stack_trace_false_gives_none(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("x"), include_stack_trace=False)
        assert ctx.stack_trace is None

    def test_timestamp_is_set(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("x"))
        assert ctx.timestamp is not None

    def test_additional_info_stored(self):
        ctx = ErrorContext.capture(operation="Op", exception=ValueError("x"), user_id="u1", sess="s2")
        assert ctx.additional_info["user_id"] == "u1"
        assert ctx.additional_info["sess"] == "s2"

    def test_no_exception_no_message_gives_unknown_error(self):
        ctx = ErrorContext.capture(operation="Op")
        assert ctx.error == "Unknown error"


class TestErrorContextUserMessage:
    """ErrorContext.user_message property."""

    def test_basic_format(self):
        ctx = ErrorContext.capture(operation="Creating SOAP", exception=ValueError("bad"))
        assert ctx.user_message.startswith("Creating SOAP failed")

    def test_strips_error_colon_prefix(self):
        ctx = ErrorContext.capture(operation="Creating SOAP", error_message="Error: bad thing")
        assert ctx.user_message == "Creating SOAP failed: bad thing"

    def test_strips_exception_colon_prefix(self):
        ctx = ErrorContext.capture(operation="Creating SOAP", error_message="Exception: bad thing")
        assert ctx.user_message == "Creating SOAP failed: bad thing"

    def test_empty_error_gives_just_failed_suffix(self):
        ctx = ErrorContext(operation="Op", error="")
        assert ctx.user_message == "Op failed"

    def test_does_not_expose_raw_exception_prefix(self):
        ctx = ErrorContext(operation="Loading", error="Error: file not found")
        assert "Error:" not in ctx.user_message


class TestErrorContextToLogString:
    """ErrorContext.to_log_string() method."""

    def test_includes_operation(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert "MyOp" in ctx.to_log_string()

    def test_includes_error(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("specific error"))
        assert "specific error" in ctx.to_log_string()

    def test_includes_exception_type(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=TypeError("type err"))
        assert "TypeError" in ctx.to_log_string()

    def test_includes_error_code(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"), error_code="CODE_42")
        assert "CODE_42" in ctx.to_log_string()

    def test_includes_input_summary(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"), input_summary="chars: 500")
        assert "chars: 500" in ctx.to_log_string()

    def test_includes_timestamp(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert ctx.timestamp in ctx.to_log_string()

    def test_omits_error_code_when_absent(self):
        ctx = ErrorContext(operation="Op", error="e")
        assert "Error Code:" not in ctx.to_log_string()

    def test_omits_exception_type_when_absent(self):
        ctx = ErrorContext(operation="Op", error="e")
        assert "Exception Type:" not in ctx.to_log_string()


class TestErrorContextToDict:
    """ErrorContext.to_dict() method."""

    def test_has_operation_key(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert "operation" in ctx.to_dict()

    def test_has_error_key(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert "error" in ctx.to_dict()

    def test_has_exception_type_key(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert "exception_type" in ctx.to_dict()

    def test_has_timestamp_key(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert "timestamp" in ctx.to_dict()

    def test_excludes_stack_trace(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"))
        assert "stack_trace" not in ctx.to_dict()

    def test_input_summary_correct(self):
        ctx = ErrorContext.capture(operation="MyOp", exception=ValueError("e"), input_summary="chars: 100")
        assert ctx.to_dict()["input_summary"] == "chars: 100"

    def test_operation_value_correct(self):
        ctx = ErrorContext.capture(operation="SpecialOp", exception=ValueError("e"))
        assert ctx.to_dict()["operation"] == "SpecialOp"


# ===========================================================================
# 7. handle_errors decorator
# ===========================================================================

class TestHandleErrorsDecorator:
    """Tests for the @handle_errors decorator."""

    def test_no_exception_returns_original_result(self):
        @handle_errors(ErrorSeverity.ERROR)
        def my_func():
            return "original"

        assert my_func() == "original"

    def test_return_type_result_on_exception_returns_operation_failure(self):
        @handle_errors(ErrorSeverity.ERROR, return_type="result")
        def my_func():
            raise ValueError("oops")

        result = my_func()
        assert isinstance(result, OperationResult)
        assert result.success is False

    def test_return_type_result_failure_includes_exception(self):
        @handle_errors(ErrorSeverity.ERROR, return_type="result")
        def my_func():
            raise ValueError("oops")

        result = my_func()
        assert isinstance(result.exception, ValueError)

    def test_return_type_none_returns_none_on_exception(self):
        @handle_errors(ErrorSeverity.ERROR, return_type="none")
        def my_func():
            raise ValueError("oops")

        assert my_func() is None

    def test_return_type_dict_returns_dict_on_exception(self):
        @handle_errors(ErrorSeverity.ERROR, return_type="dict")
        def my_func():
            raise ValueError("oops")

        result = my_func()
        assert isinstance(result, dict)
        assert result["success"] is False

    def test_return_type_dict_has_error_key(self):
        @handle_errors(ErrorSeverity.ERROR, return_type="dict")
        def my_func():
            raise ValueError("oops")

        assert "error" in my_func()

    def test_return_type_bool_returns_false_on_exception(self):
        @handle_errors(ErrorSeverity.ERROR, return_type="bool")
        def my_func():
            raise ValueError("oops")

        assert my_func() is False

    def test_critical_severity_reraises(self):
        @handle_errors(ErrorSeverity.CRITICAL, return_type="result")
        def my_func():
            raise ValueError("critical failure")

        with pytest.raises(ValueError, match="critical failure"):
            my_func()

    def test_warning_severity_returns_none(self):
        @handle_errors(ErrorSeverity.WARNING, return_type="none")
        def my_func():
            raise RuntimeError("warn")

        assert my_func() is None

    def test_info_severity_does_not_reraise(self):
        @handle_errors(ErrorSeverity.INFO, return_type="none")
        def my_func():
            raise ValueError("info-level")

        assert my_func() is None

    def test_custom_error_message_prefix_used(self):
        @handle_errors(ErrorSeverity.ERROR, error_message="Custom prefix", return_type="result")
        def my_func():
            raise ValueError("inner")

        result = my_func()
        assert "Custom prefix" in result.error

    def test_decorated_function_preserves_name(self):
        @handle_errors(ErrorSeverity.ERROR)
        def unique_function_name():
            pass

        assert unique_function_name.__name__ == "unique_function_name"

    def test_decorated_function_passes_args(self):
        @handle_errors(ErrorSeverity.ERROR)
        def add(a, b):
            return a + b

        assert add(3, 4) == 7

    def test_decorated_function_passes_kwargs(self):
        @handle_errors(ErrorSeverity.ERROR)
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        assert greet("Alice", greeting="Hi") == "Hi, Alice"

    def test_default_return_type_is_result(self):
        @handle_errors(ErrorSeverity.ERROR)
        def my_func():
            raise RuntimeError("boom")

        result = my_func()
        assert isinstance(result, OperationResult)


# ===========================================================================
# 8. safe_execute
# ===========================================================================

class TestSafeExecute:
    """Tests for safe_execute()."""

    def test_success_returns_function_result(self):
        assert safe_execute(lambda: 42) == 42

    def test_exception_returns_default_none(self):
        assert safe_execute(lambda: 1 / 0) is None

    def test_exception_returns_custom_default(self):
        assert safe_execute(lambda: 1 / 0, default="fallback") == "fallback"

    def test_exception_returns_dict_default(self):
        result = safe_execute(lambda: (_ for _ in ()).throw(RuntimeError("e")), default={"ok": False})
        assert result == {"ok": False}

    def test_error_handler_called_with_exception(self):
        captured = []
        safe_execute(lambda: 1 / 0, error_handler=lambda e: captured.append(e))
        assert len(captured) == 1
        assert isinstance(captured[0], ZeroDivisionError)

    def test_error_handler_not_called_on_success(self):
        called = []
        safe_execute(lambda: "fine", error_handler=lambda e: called.append(e))
        assert called == []

    def test_passes_positional_args(self):
        def add(a, b):
            return a + b

        assert safe_execute(add, 3, 7) == 10

    def test_passes_keyword_args(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        assert safe_execute(greet, "Alice", greeting="Hi") == "Hi, Alice"

    def test_log_errors_false_still_returns_default(self):
        result = safe_execute(lambda: 1 / 0, default="silent_default", log_errors=False)
        assert result == "silent_default"

    def test_log_errors_false_does_not_emit_warning(self, caplog):
        def failing():
            raise RuntimeError("silent")

        with caplog.at_level(logging.WARNING):
            safe_execute(failing, log_errors=False)

        relevant = [r for r in caplog.records if "failing" in r.message]
        assert relevant == []

    def test_no_error_handler_does_not_raise(self):
        result = safe_execute(lambda: 1 / 0)
        assert result is None

    def test_zero_default_returned_on_error(self):
        assert safe_execute(lambda: 1 / 0, default=0) == 0


# ===========================================================================
# 9. Data integrity: _USER_FRIENDLY_ERRORS and _ERROR_TEMPLATES
# ===========================================================================

class TestInternals:
    """Sanity checks on module-level data structures."""

    def test_user_friendly_errors_is_dict(self):
        assert isinstance(_USER_FRIENDLY_ERRORS, dict)

    def test_user_friendly_errors_not_empty(self):
        assert len(_USER_FRIENDLY_ERRORS) > 0

    def test_user_friendly_errors_all_values_are_strings(self):
        for key, val in _USER_FRIENDLY_ERRORS.items():
            assert isinstance(val, str), f"Value for {key!r} is not a string"

    def test_user_friendly_errors_authentication_key_exists(self):
        assert "AuthenticationError" in _USER_FRIENDLY_ERRORS

    def test_user_friendly_errors_rate_limit_key_exists(self):
        assert "RateLimitError" in _USER_FRIENDLY_ERRORS

    def test_error_templates_is_dict(self):
        assert isinstance(_ERROR_TEMPLATES, dict)

    def test_error_templates_contains_generic(self):
        assert "generic" in _ERROR_TEMPLATES

    def test_error_templates_contains_save_file(self):
        assert "save_file" in _ERROR_TEMPLATES

    def test_error_templates_contains_load_file(self):
        assert "load_file" in _ERROR_TEMPLATES

    def test_generic_problem_is_string(self):
        assert isinstance(_ERROR_TEMPLATES["generic"].problem, str)

    def test_generic_actions_is_list(self):
        assert isinstance(_ERROR_TEMPLATES["generic"].actions, list)

    def test_generic_actions_not_empty(self):
        assert len(_ERROR_TEMPLATES["generic"].actions) > 0

    def test_all_template_titles_are_strings(self):
        for key, tmpl in _ERROR_TEMPLATES.items():
            assert isinstance(tmpl.title, str), f"Title for {key!r} not a string"

    def test_all_template_problems_are_strings(self):
        for key, tmpl in _ERROR_TEMPLATES.items():
            assert isinstance(tmpl.problem, str), f"Problem for {key!r} not a string"

    def test_all_template_actions_are_lists(self):
        for key, tmpl in _ERROR_TEMPLATES.items():
            assert isinstance(tmpl.actions, list), f"Actions for {key!r} not a list"

    def test_all_templates_have_nonempty_actions(self):
        for key, tmpl in _ERROR_TEMPLATES.items():
            assert len(tmpl.actions) > 0, f"Template {key!r} has empty actions"


# ===========================================================================
# 10. log_and_raise
# ===========================================================================

class TestLogAndRaise:
    """Tests for log_and_raise(error, message, log_level, include_traceback).

    Note: log_and_raise uses bare `raise`, so it must be called from within
    an active except block to re-raise the current exception.
    """

    def test_reraises_the_current_exception(self):
        with pytest.raises(ValueError, match="original error"):
            try:
                raise ValueError("original error")
            except ValueError as e:
                log_and_raise(e)

    def test_reraises_runtime_error(self):
        with pytest.raises(RuntimeError, match="boom"):
            try:
                raise RuntimeError("boom")
            except RuntimeError as e:
                log_and_raise(e)

    def test_logs_at_error_level_by_default(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError):
                try:
                    raise ValueError("test msg")
                except ValueError as e:
                    log_and_raise(e)
        assert any("test msg" in r.message for r in caplog.records)

    def test_logs_at_custom_level_warning(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError):
                try:
                    raise ValueError("warn level")
                except ValueError as e:
                    log_and_raise(e, log_level=logging.WARNING)
        warning_records = [r for r in caplog.records if r.levelno == logging.WARNING and "warn level" in r.message]
        assert len(warning_records) >= 1

    def test_message_prefix_included_in_log(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(TypeError):
                try:
                    raise TypeError("bad type")
                except TypeError as e:
                    log_and_raise(e, message="Custom prefix")
        assert any("Custom prefix" in r.message for r in caplog.records)
        assert any("bad type" in r.message for r in caplog.records)

    def test_no_message_prefix_logs_just_error(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError):
                try:
                    raise ValueError("just error")
                except ValueError as e:
                    log_and_raise(e, message=None)
        assert any("just error" in r.message for r in caplog.records)

    def test_include_traceback_true_by_default(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError):
                try:
                    raise ValueError("tb test")
                except ValueError as e:
                    log_and_raise(e)
        # When include_traceback=True, logger.log is called with exc_info=True
        error_records = [r for r in caplog.records if "tb test" in r.message]
        assert len(error_records) >= 1

    def test_include_traceback_false(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(ValueError):
                try:
                    raise ValueError("no tb")
                except ValueError as e:
                    log_and_raise(e, include_traceback=False)
        error_records = [r for r in caplog.records if "no tb" in r.message]
        assert len(error_records) >= 1

    def test_logs_combined_message_with_prefix(self, caplog):
        with caplog.at_level(logging.DEBUG):
            with pytest.raises(OSError):
                try:
                    raise OSError("disk full")
                except OSError as e:
                    log_and_raise(e, message="Save failed")
        assert any("Save failed: disk full" in r.message for r in caplog.records)

    def test_reraises_original_exception_type_not_wrapped(self):
        """Verify that the re-raised exception is the original type, not wrapped."""
        with pytest.raises(KeyError):
            try:
                raise KeyError("missing_key")
            except KeyError as e:
                log_and_raise(e, message="Lookup error")
