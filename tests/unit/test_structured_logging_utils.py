"""
Tests for src/utils/structured_logging.py

Covers: SENSITIVE_FIELDS, MAX_VALUE_LENGTH, get_log_level_from_string,
_sanitize_value, _format_context, StructuredLogger, get_logger.
"""

import sys
import logging
import pytest
from pathlib import Path

project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

from utils.structured_logging import (
    SENSITIVE_FIELDS,
    MAX_VALUE_LENGTH,
    get_log_level_from_string,
    _sanitize_value,
    _format_context,
    StructuredLogger,
    get_logger,
)


# ---------------------------------------------------------------------------
# SENSITIVE_FIELDS
# ---------------------------------------------------------------------------

class TestSensitiveFields:
    def test_is_frozenset(self):
        assert isinstance(SENSITIVE_FIELDS, frozenset)

    def test_contains_api_key(self):
        assert "api_key" in SENSITIVE_FIELDS

    def test_contains_password(self):
        assert "password" in SENSITIVE_FIELDS

    def test_contains_patient(self):
        assert "patient" in SENSITIVE_FIELDS

    def test_contains_diagnosis(self):
        assert "diagnosis" in SENSITIVE_FIELDS

    def test_contains_token(self):
        assert "token" in SENSITIVE_FIELDS

    def test_contains_ssn(self):
        assert "ssn" in SENSITIVE_FIELDS

    def test_contains_secret(self):
        assert "secret" in SENSITIVE_FIELDS

    def test_contains_authorization(self):
        assert "authorization" in SENSITIVE_FIELDS

    def test_contains_credit_card(self):
        assert "credit_card" in SENSITIVE_FIELDS

    def test_contains_transcript(self):
        assert "transcript" in SENSITIVE_FIELDS

    def test_contains_soap_note(self):
        assert "soap_note" in SENSITIVE_FIELDS

    def test_contains_medication(self):
        assert "medication" in SENSITIVE_FIELDS

    def test_contains_dob(self):
        assert "dob" in SENSITIVE_FIELDS

    def test_contains_email(self):
        assert "email" in SENSITIVE_FIELDS

    def test_contains_phone(self):
        assert "phone" in SENSITIVE_FIELDS

    def test_safe_key_not_present(self):
        assert "recording_id" not in SENSITIVE_FIELDS

    def test_safe_key_status_not_present(self):
        assert "status" not in SENSITIVE_FIELDS

    def test_safe_key_duration_not_present(self):
        assert "duration_ms" not in SENSITIVE_FIELDS

    def test_immutable(self):
        with pytest.raises((AttributeError, TypeError)):
            SENSITIVE_FIELDS.add("newfield")  # type: ignore[attr-defined]

    def test_nonempty(self):
        assert len(SENSITIVE_FIELDS) > 0


# ---------------------------------------------------------------------------
# MAX_VALUE_LENGTH
# ---------------------------------------------------------------------------

class TestMaxValueLength:
    def test_is_integer(self):
        assert isinstance(MAX_VALUE_LENGTH, int)

    def test_equals_500(self):
        assert MAX_VALUE_LENGTH == 500

    def test_positive(self):
        assert MAX_VALUE_LENGTH > 0


# ---------------------------------------------------------------------------
# get_log_level_from_string
# ---------------------------------------------------------------------------

class TestGetLogLevelFromString:
    def test_debug_returns_10(self):
        assert get_log_level_from_string("DEBUG") == 10

    def test_info_returns_20(self):
        assert get_log_level_from_string("INFO") == 20

    def test_warning_returns_30(self):
        assert get_log_level_from_string("WARNING") == 30

    def test_error_returns_40(self):
        assert get_log_level_from_string("ERROR") == 40

    def test_critical_returns_50(self):
        assert get_log_level_from_string("CRITICAL") == 50

    def test_unknown_returns_info(self):
        assert get_log_level_from_string("UNKNOWN") == 20

    def test_empty_string_returns_info(self):
        assert get_log_level_from_string("") == 20

    def test_case_insensitive_debug(self):
        assert get_log_level_from_string("debug") == 10

    def test_case_insensitive_info(self):
        assert get_log_level_from_string("info") == 20

    def test_case_insensitive_warning(self):
        assert get_log_level_from_string("warning") == 30

    def test_case_insensitive_error(self):
        assert get_log_level_from_string("error") == 40

    def test_case_insensitive_critical(self):
        assert get_log_level_from_string("critical") == 50

    def test_mixed_case_debug(self):
        assert get_log_level_from_string("Debug") == 10

    def test_mixed_case_info(self):
        assert get_log_level_from_string("Info") == 20

    def test_garbage_returns_info(self):
        assert get_log_level_from_string("NOTAREALEVEL") == 20

    def test_returns_int(self):
        assert isinstance(get_log_level_from_string("DEBUG"), int)

    def test_consistent_with_logging_constants_debug(self):
        assert get_log_level_from_string("DEBUG") == logging.DEBUG

    def test_consistent_with_logging_constants_info(self):
        assert get_log_level_from_string("INFO") == logging.INFO

    def test_consistent_with_logging_constants_warning(self):
        assert get_log_level_from_string("WARNING") == logging.WARNING

    def test_consistent_with_logging_constants_error(self):
        assert get_log_level_from_string("ERROR") == logging.ERROR

    def test_consistent_with_logging_constants_critical(self):
        assert get_log_level_from_string("CRITICAL") == logging.CRITICAL


# ---------------------------------------------------------------------------
# _sanitize_value
# ---------------------------------------------------------------------------

class TestSanitizeValue:
    def test_sensitive_key_api_key_redacted(self):
        assert _sanitize_value("api_key", "sk-abc123") == "[REDACTED]"

    def test_sensitive_key_password_redacted(self):
        assert _sanitize_value("password", "hunter2") == "[REDACTED]"

    def test_sensitive_key_token_redacted(self):
        assert _sanitize_value("token", "my-token-value") == "[REDACTED]"

    def test_sensitive_key_ssn_redacted(self):
        assert _sanitize_value("ssn", "123-45-6789") == "[REDACTED]"

    def test_sensitive_key_patient_redacted(self):
        assert _sanitize_value("patient", "John Doe") == "[REDACTED]"

    def test_sensitive_key_diagnosis_redacted(self):
        assert _sanitize_value("diagnosis", "Hypertension") == "[REDACTED]"

    def test_sensitive_key_case_insensitive_upper(self):
        assert _sanitize_value("API_KEY", "value") == "[REDACTED]"

    def test_sensitive_key_case_insensitive_mixed(self):
        assert _sanitize_value("Password", "value") == "[REDACTED]"

    def test_normal_string_unchanged(self):
        assert _sanitize_value("status", "success") == "success"

    def test_normal_key_recording_id_unchanged(self):
        assert _sanitize_value("recording_id", "42") == "42"

    def test_numeric_int_unchanged(self):
        assert _sanitize_value("count", 99) == 99

    def test_numeric_float_unchanged(self):
        assert _sanitize_value("duration_ms", 3.14) == 3.14

    def test_long_string_truncated(self):
        long_str = "x" * 600
        result = _sanitize_value("message", long_str)
        assert result.endswith("...[truncated]")

    def test_long_string_starts_with_original_prefix(self):
        long_str = "a" * 600
        result = _sanitize_value("message", long_str)
        assert result.startswith("a" * 500)

    def test_long_string_total_length(self):
        long_str = "z" * 600
        result = _sanitize_value("message", long_str)
        assert len(result) == 500 + len("...[truncated]")

    def test_string_at_max_length_not_truncated(self):
        exact_str = "b" * 500
        result = _sanitize_value("message", exact_str)
        assert result == exact_str

    def test_string_one_below_max_not_truncated(self):
        short_str = "c" * 499
        result = _sanitize_value("message", short_str)
        assert result == short_str

    def test_value_containing_api_key_pattern_redacted(self):
        result = _sanitize_value("url", "https://api.example.com?api_key=secret123")
        assert result == "[REDACTED]"

    def test_value_containing_password_pattern_redacted(self):
        result = _sanitize_value("query", "password=mysecret")
        assert result == "[REDACTED]"

    def test_value_containing_token_pattern_redacted(self):
        result = _sanitize_value("data", "token=abc.def.ghi")
        assert result == "[REDACTED]"

    def test_none_value_safe_key_returns_none(self):
        result = _sanitize_value("status", None)
        assert result is None

    def test_boolean_value_unchanged(self):
        assert _sanitize_value("active", True) is True

    def test_list_value_unchanged(self):
        lst = [1, 2, 3]
        assert _sanitize_value("items", lst) == lst

    def test_dict_value_unchanged(self):
        d = {"a": 1}
        assert _sanitize_value("extra", d) == d


# ---------------------------------------------------------------------------
# _format_context
# ---------------------------------------------------------------------------

class TestFormatContext:
    def test_empty_dict_returns_empty_string(self):
        assert _format_context({}) == ""

    def test_nonempty_starts_with_separator(self):
        result = _format_context({"key": "value"})
        assert result.startswith(" | ")

    def test_single_simple_key_value(self):
        result = _format_context({"status": "ok"})
        assert "status=ok" in result

    def test_integer_value_included(self):
        result = _format_context({"count": 42})
        assert "count=42" in result

    def test_float_value_included(self):
        result = _format_context({"ratio": 3.5})
        assert "ratio=3.5" in result

    def test_string_with_spaces_quoted(self):
        result = _format_context({"msg": "hello world"})
        assert 'msg="hello world"' in result

    def test_string_without_spaces_not_quoted(self):
        result = _format_context({"code": "ABC123"})
        assert "code=ABC123" in result
        assert 'code="ABC123"' not in result

    def test_multiple_keys_all_included(self):
        result = _format_context({"a": "x", "b": "y"})
        assert "a=x" in result
        assert "b=y" in result

    def test_list_value_json_formatted(self):
        result = _format_context({"items": [1, 2, 3]})
        assert "items=[1, 2, 3]" in result or "items=[1,2,3]" in result

    def test_dict_value_json_formatted(self):
        result = _format_context({"meta": {"k": "v"}})
        assert "meta=" in result
        assert '"k"' in result
        assert '"v"' in result

    def test_sensitive_key_redacted_in_output(self):
        result = _format_context({"api_key": "secret"})
        assert "secret" not in result
        assert "[REDACTED]" in result

    def test_format_returns_string(self):
        assert isinstance(_format_context({"x": 1}), str)

    def test_long_value_truncated_in_format(self):
        result = _format_context({"msg": "z" * 600})
        assert "[truncated]" in result

    def test_string_with_double_quote_gets_quoted(self):
        result = _format_context({"label": 'say "hi"'})
        assert "label=" in result

    def test_boolean_false_value(self):
        result = _format_context({"active": False})
        assert "active=False" in result


# ---------------------------------------------------------------------------
# StructuredLogger
# ---------------------------------------------------------------------------

class TestStructuredLogger:
    def test_stores_name(self):
        sl = StructuredLogger("my.module")
        assert sl.name == "my.module"

    def test_has_debug_method(self):
        sl = StructuredLogger("test.debug")
        assert callable(sl.debug)

    def test_has_info_method(self):
        sl = StructuredLogger("test.info")
        assert callable(sl.info)

    def test_has_warning_method(self):
        sl = StructuredLogger("test.warning")
        assert callable(sl.warning)

    def test_has_error_method(self):
        sl = StructuredLogger("test.error")
        assert callable(sl.error)

    def test_has_exception_method(self):
        sl = StructuredLogger("test.exception")
        assert callable(sl.exception)

    def test_has_critical_method(self):
        sl = StructuredLogger("test.critical")
        assert callable(sl.critical)

    def test_has_log_method(self):
        sl = StructuredLogger("test.log")
        assert callable(sl.log)

    def test_has_set_context_method(self):
        sl = StructuredLogger("test.set_context")
        assert callable(sl.set_context)

    def test_has_clear_context_method(self):
        sl = StructuredLogger("test.clear_context")
        assert callable(sl.clear_context)

    def test_has_isenabled_for_method(self):
        sl = StructuredLogger("test.isenabled")
        assert callable(sl.isEnabledFor)

    def test_isenabled_for_delegates_to_underlying_logger(self):
        sl = StructuredLogger("test.isenabled.delegate")
        sl.logger.setLevel(logging.WARNING)
        assert not sl.isEnabledFor(logging.DEBUG)
        assert sl.isEnabledFor(logging.ERROR)

    def test_set_context_persists(self):
        sl = StructuredLogger("test.ctx.persist")
        sl.set_context(request_id="req-001")
        assert sl._context.get("request_id") == "req-001"

    def test_clear_context_removes_all(self):
        sl = StructuredLogger("test.ctx.clear")
        sl.set_context(key1="val1", key2="val2")
        sl.clear_context()
        assert sl._context == {}

    def test_debug_does_not_raise(self):
        sl = StructuredLogger("test.no_raise.debug")
        sl.debug("debug message", extra_key="value")

    def test_info_does_not_raise(self):
        sl = StructuredLogger("test.no_raise.info")
        sl.info("info message")

    def test_warning_does_not_raise(self):
        sl = StructuredLogger("test.no_raise.warning")
        sl.warning("warning message", code=404)

    def test_error_does_not_raise(self):
        sl = StructuredLogger("test.no_raise.error")
        sl.error("error message")

    def test_critical_does_not_raise(self):
        sl = StructuredLogger("test.no_raise.critical")
        sl.critical("critical message")

    def test_log_does_not_raise(self):
        sl = StructuredLogger("test.no_raise.log")
        sl.log(logging.INFO, "log message")

    def test_context_manager_restores_context(self):
        sl = StructuredLogger("test.ctx.manager")
        sl.set_context(outer="yes")
        with sl.context(inner="temp"):
            assert sl._context.get("inner") == "temp"
        assert "inner" not in sl._context
        assert sl._context.get("outer") == "yes"

    def test_initial_context_empty(self):
        sl = StructuredLogger("test.ctx.initial")
        assert sl._context == {}

    def test_underlying_logger_is_python_logger(self):
        sl = StructuredLogger("test.underlying")
        assert isinstance(sl.logger, logging.Logger)

    def test_set_context_multiple_calls_accumulate(self):
        sl = StructuredLogger("test.ctx.accumulate")
        sl.set_context(a=1)
        sl.set_context(b=2)
        assert sl._context.get("a") == 1
        assert sl._context.get("b") == 2

    def test_set_context_overwrites_existing_key(self):
        sl = StructuredLogger("test.ctx.overwrite")
        sl.set_context(key="old")
        sl.set_context(key="new")
        assert sl._context.get("key") == "new"


# ---------------------------------------------------------------------------
# get_logger
# ---------------------------------------------------------------------------

class TestGetLogger:
    def test_returns_structured_logger(self):
        lg = get_logger("test.get_logger.a")
        assert isinstance(lg, StructuredLogger)

    def test_same_name_returns_same_instance(self):
        lg1 = get_logger("test.get_logger.same")
        lg2 = get_logger("test.get_logger.same")
        assert lg1 is lg2

    def test_different_names_return_different_instances(self):
        lg1 = get_logger("test.get_logger.diff.one")
        lg2 = get_logger("test.get_logger.diff.two")
        assert lg1 is not lg2

    def test_has_name_attribute(self):
        lg = get_logger("test.get_logger.name_attr")
        assert lg.name == "test.get_logger.name_attr"

    def test_callable_info_method(self):
        lg = get_logger("test.get_logger.callable")
        assert callable(lg.info)
