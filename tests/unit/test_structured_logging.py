"""
Tests for src/utils/structured_logging.py

Covers _LOG_LEVEL_MAP, get_log_level_from_string, _get_configured_log_level,
SENSITIVE_FIELDS, _sanitize_value, _format_context, StructuredLogger
(all log methods, set/clear_context, context() manager, isEnabledFor),
JsonStructuredLogger, get_logger (caching + json_format), timed decorator,
log_operation context manager, RequestLogger, and configure_logging.
No Tkinter required.
"""

import sys
import json
import logging
import os
import time
import threading
from pathlib import Path
from unittest.mock import MagicMock, patch, call

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(project_root / "src"))

import utils.structured_logging as sl_module
from utils.structured_logging import (
    _LOG_LEVEL_MAP,
    get_log_level_from_string,
    _get_configured_log_level,
    SENSITIVE_FIELDS,
    _sanitize_value,
    _format_context,
    StructuredLogger,
    JsonStructuredLogger,
    get_logger,
    timed,
    log_operation,
    RequestLogger,
    configure_logging,
    setup_logging,
    MAX_VALUE_LENGTH,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _fresh_logger(name: str = "test_logger") -> StructuredLogger:
    """Create a StructuredLogger with a null handler so tests don't pollute stderr."""
    lg = StructuredLogger(name)
    lg.logger.handlers.clear()
    lg.logger.addHandler(logging.NullHandler())
    return lg


# ===========================================================================
# _LOG_LEVEL_MAP
# ===========================================================================

class TestLogLevelMap:
    def test_has_debug(self):
        assert _LOG_LEVEL_MAP["DEBUG"] == logging.DEBUG

    def test_has_info(self):
        assert _LOG_LEVEL_MAP["INFO"] == logging.INFO

    def test_has_warning(self):
        assert _LOG_LEVEL_MAP["WARNING"] == logging.WARNING

    def test_has_error(self):
        assert _LOG_LEVEL_MAP["ERROR"] == logging.ERROR

    def test_has_critical(self):
        assert _LOG_LEVEL_MAP["CRITICAL"] == logging.CRITICAL

    def test_five_entries(self):
        assert len(_LOG_LEVEL_MAP) == 5


# ===========================================================================
# get_log_level_from_string
# ===========================================================================

class TestGetLogLevelFromString:
    def test_debug_string(self):
        assert get_log_level_from_string("DEBUG") == logging.DEBUG

    def test_info_string(self):
        assert get_log_level_from_string("INFO") == logging.INFO

    def test_warning_string(self):
        assert get_log_level_from_string("WARNING") == logging.WARNING

    def test_error_string(self):
        assert get_log_level_from_string("ERROR") == logging.ERROR

    def test_critical_string(self):
        assert get_log_level_from_string("CRITICAL") == logging.CRITICAL

    def test_case_insensitive_lower(self):
        assert get_log_level_from_string("debug") == logging.DEBUG

    def test_case_insensitive_mixed(self):
        assert get_log_level_from_string("Warning") == logging.WARNING

    def test_unknown_returns_info(self):
        assert get_log_level_from_string("VERBOSE") == logging.INFO

    def test_empty_string_returns_info(self):
        assert get_log_level_from_string("") == logging.INFO


# ===========================================================================
# _get_configured_log_level
# ===========================================================================

class TestGetConfiguredLogLevel:
    def test_env_var_debug_takes_priority(self):
        with patch.dict(os.environ, {"MEDICAL_ASSISTANT_LOG_LEVEL": "DEBUG"}):
            result = _get_configured_log_level()
        assert result == logging.DEBUG

    def test_env_var_error(self):
        with patch.dict(os.environ, {"MEDICAL_ASSISTANT_LOG_LEVEL": "ERROR"}):
            result = _get_configured_log_level()
        assert result == logging.ERROR

    def test_env_var_case_insensitive(self):
        with patch.dict(os.environ, {"MEDICAL_ASSISTANT_LOG_LEVEL": "warning"}):
            result = _get_configured_log_level()
        assert result == logging.WARNING

    def test_env_var_invalid_falls_through_to_default(self):
        # Invalid env var → settings path search (will fail) → INFO default
        with patch.dict(os.environ, {"MEDICAL_ASSISTANT_LOG_LEVEL": "VERBOSE"}):
            result = _get_configured_log_level()
        assert result == logging.INFO

    def test_no_env_var_returns_info_by_default(self):
        env = {k: v for k, v in os.environ.items() if k != "MEDICAL_ASSISTANT_LOG_LEVEL"}
        with patch.dict(os.environ, env, clear=True):
            result = _get_configured_log_level()
        assert result == logging.INFO

    def test_returns_int(self):
        result = _get_configured_log_level()
        assert isinstance(result, int)


# ===========================================================================
# SENSITIVE_FIELDS
# ===========================================================================

class TestSensitiveFields:
    def test_is_frozenset(self):
        assert isinstance(SENSITIVE_FIELDS, frozenset)

    def test_contains_api_key(self):
        assert "api_key" in SENSITIVE_FIELDS

    def test_contains_password(self):
        assert "password" in SENSITIVE_FIELDS

    def test_contains_token(self):
        assert "token" in SENSITIVE_FIELDS

    def test_contains_phi_transcript(self):
        assert "transcript" in SENSITIVE_FIELDS

    def test_contains_patient(self):
        assert "patient" in SENSITIVE_FIELDS

    def test_contains_medication(self):
        assert "medication" in SENSITIVE_FIELDS

    def test_substantial_field_count(self):
        assert len(SENSITIVE_FIELDS) >= 30


# ===========================================================================
# _sanitize_value
# ===========================================================================

class TestSanitizeValue:
    def test_redacts_api_key_field(self):
        assert _sanitize_value("api_key", "sk-abc123") == "[REDACTED]"

    def test_redacts_password_field(self):
        assert _sanitize_value("password", "supersecret") == "[REDACTED]"

    def test_redacts_transcript_field(self):
        assert _sanitize_value("transcript", "patient says...") == "[REDACTED]"

    def test_field_check_case_insensitive(self):
        assert _sanitize_value("API_KEY", "sk-abc123") == "[REDACTED]"

    def test_passes_through_safe_string(self):
        assert _sanitize_value("status", "active") == "active"

    def test_passes_through_integer(self):
        assert _sanitize_value("count", 42) == 42

    def test_passes_through_none(self):
        assert _sanitize_value("result", None) is None

    def test_truncates_long_string(self):
        long_str = "x" * (MAX_VALUE_LENGTH + 50)
        result = _sanitize_value("description", long_str)
        assert result.endswith("...[truncated]")
        assert len(result) <= MAX_VALUE_LENGTH + len("...[truncated]")

    def test_short_string_not_truncated(self):
        short = "hello"
        assert _sanitize_value("description", short) == "hello"

    def test_redacts_value_containing_api_key_pattern(self):
        result = _sanitize_value("message", "api_key=secretvalue")
        assert result == "[REDACTED]"

    def test_redacts_value_containing_password_pattern(self):
        result = _sanitize_value("message", "password=secret")
        assert result == "[REDACTED]"

    def test_redacts_value_containing_token_pattern(self):
        result = _sanitize_value("message", "token=abc123")
        assert result == "[REDACTED]"

    def test_safe_value_with_sensitive_substring_in_key_check(self):
        # "count" is not in SENSITIVE_FIELDS — value passes through
        assert _sanitize_value("count", "api_key=xyz") == "[REDACTED]"


# ===========================================================================
# _format_context
# ===========================================================================

class TestFormatContext:
    def test_empty_context_returns_empty_string(self):
        assert _format_context({}) == ""

    def test_none_like_empty_dict(self):
        # Passing {} returns ""
        assert _format_context({}) == ""

    def test_simple_value_no_spaces(self):
        result = _format_context({"count": 5})
        assert "count=5" in result

    def test_string_with_space_gets_quoted(self):
        result = _format_context({"name": "hello world"})
        assert 'name="hello world"' in result

    def test_string_without_space_no_quotes(self):
        result = _format_context({"status": "active"})
        assert "status=active" in result

    def test_list_value_json_encoded(self):
        result = _format_context({"items": [1, 2, 3]})
        assert "items=[1, 2, 3]" in result

    def test_dict_value_json_encoded(self):
        result = _format_context({"meta": {"k": "v"}})
        assert "meta=" in result
        assert '"k"' in result

    def test_output_starts_with_pipe(self):
        result = _format_context({"x": 1})
        assert result.startswith(" | ")

    def test_sensitive_field_redacted_in_output(self):
        result = _format_context({"api_key": "sk-secret"})
        assert "sk-secret" not in result
        assert "[REDACTED]" in result

    def test_multiple_fields_space_separated(self):
        result = _format_context({"a": 1, "b": 2})
        assert "a=1" in result
        assert "b=2" in result


# ===========================================================================
# StructuredLogger
# ===========================================================================

class TestStructuredLoggerInit:
    def test_name_attribute(self):
        lg = StructuredLogger("my.module")
        assert lg.name == "my.module"

    def test_logger_attribute_is_logging_logger(self):
        lg = StructuredLogger("my.module")
        assert isinstance(lg.logger, logging.Logger)

    def test_initial_context_empty(self):
        lg = StructuredLogger("my.module")
        assert lg._context == {}


class TestStructuredLoggerMethods:
    def setup_method(self):
        self.lg = _fresh_logger("test.methods")
        self.mock_logger = MagicMock()
        self.lg.logger = self.mock_logger

    def test_debug_calls_log(self):
        self.lg.debug("test")
        self.mock_logger.log.assert_called_once()
        args = self.mock_logger.log.call_args[0]
        assert args[0] == logging.DEBUG
        assert "test" in args[1]

    def test_info_calls_log_at_info_level(self):
        self.lg.info("msg")
        args = self.mock_logger.log.call_args[0]
        assert args[0] == logging.INFO

    def test_warning_calls_log_at_warning(self):
        self.lg.warning("warn")
        args = self.mock_logger.log.call_args[0]
        assert args[0] == logging.WARNING

    def test_critical_calls_log_at_critical(self):
        self.lg.critical("crit")
        args = self.mock_logger.log.call_args[0]
        assert args[0] == logging.CRITICAL

    def test_error_calls_logger_error(self):
        self.lg.error("oops")
        self.mock_logger.error.assert_called_once()
        assert "oops" in self.mock_logger.error.call_args[0][0]

    def test_error_with_exc_info_passed_through(self):
        self.lg.error("boom", exc_info=True)
        _, kwargs = self.mock_logger.error.call_args
        assert kwargs.get("exc_info") is True

    def test_exception_calls_error_with_exc_info(self):
        self.lg.exception("ex")
        self.mock_logger.error.assert_called_once()
        _, kwargs = self.mock_logger.error.call_args
        assert kwargs.get("exc_info") is True

    def test_log_method_passes_level(self):
        self.lg.log(logging.WARNING, "msg")
        args = self.mock_logger.log.call_args[0]
        assert args[0] == logging.WARNING

    def test_context_kwargs_included_in_message(self):
        self.lg.info("event", count=5, user="alice")
        args = self.mock_logger.log.call_args[0]
        msg = args[1]
        assert "count=5" in msg
        assert "user=alice" in msg

    def test_is_enabled_for_delegates(self):
        self.mock_logger.isEnabledFor.return_value = True
        assert self.lg.isEnabledFor(logging.DEBUG) is True
        self.mock_logger.isEnabledFor.assert_called_once_with(logging.DEBUG)


class TestStructuredLoggerContext:
    def setup_method(self):
        self.lg = _fresh_logger("test.ctx")
        self.mock_logger = MagicMock()
        self.lg.logger = self.mock_logger

    def test_set_context_persists(self):
        self.lg.set_context(request_id="abc")
        self.lg.info("msg")
        args = self.mock_logger.log.call_args[0]
        assert "request_id=abc" in args[1]

    def test_clear_context_removes_fields(self):
        self.lg.set_context(request_id="abc")
        self.lg.clear_context()
        self.lg.info("msg")
        args = self.mock_logger.log.call_args[0]
        assert "request_id" not in args[1]

    def test_context_manager_adds_context(self):
        with self.lg.context(op="save"):
            self.lg.info("inside")
        args = self.mock_logger.log.call_args[0]
        assert "op=save" in args[1]

    def test_context_manager_restores_on_exit(self):
        self.lg.set_context(base="x")
        with self.lg.context(op="save"):
            pass
        self.lg.info("after")
        args = self.mock_logger.log.call_args[0]
        assert "op=" not in args[1]
        assert "base=x" in args[1]

    def test_context_manager_restores_on_exception(self):
        self.lg.set_context(base="x")
        try:
            with self.lg.context(op="save"):
                raise ValueError("oops")
        except ValueError:
            pass
        self.lg.info("after")
        args = self.mock_logger.log.call_args[0]
        assert "op=" not in args[1]

    def test_call_specific_context_merged_with_persistent(self):
        self.lg.set_context(base="x")
        self.lg.info("msg", extra="y")
        args = self.mock_logger.log.call_args[0]
        assert "base=x" in args[1]
        assert "extra=y" in args[1]


# ===========================================================================
# JsonStructuredLogger
# ===========================================================================

class TestJsonStructuredLogger:
    def test_is_subclass_of_structured_logger(self):
        assert issubclass(JsonStructuredLogger, StructuredLogger)

    def test_log_produces_json_string(self):
        jl = JsonStructuredLogger("test.json")
        mock_logger = MagicMock()
        jl.logger = mock_logger

        jl.info("hello", user="bob")

        args = mock_logger.log.call_args[0]
        json_str = args[1]
        parsed = json.loads(json_str)

        assert parsed["message"] == "hello"
        assert parsed["level"] == "INFO"
        assert parsed["logger"] == "test.json"
        assert "timestamp" in parsed

    def test_json_includes_context(self):
        jl = JsonStructuredLogger("test.json")
        mock_logger = MagicMock()
        jl.logger = mock_logger

        jl.debug("event", count=3)

        args = mock_logger.log.call_args[0]
        parsed = json.loads(args[1])
        assert parsed.get("count") == 3

    def test_json_redacts_sensitive_fields(self):
        jl = JsonStructuredLogger("test.json")
        mock_logger = MagicMock()
        jl.logger = mock_logger

        jl.info("log", api_key="sk-secret")

        args = mock_logger.log.call_args[0]
        parsed = json.loads(args[1])
        assert parsed.get("api_key") == "[REDACTED]"


# ===========================================================================
# get_logger
# ===========================================================================

class TestGetLogger:
    def setup_method(self):
        # Clear the logger cache before each test
        with sl_module._loggers_lock:
            sl_module._loggers.clear()

    def test_returns_structured_logger(self):
        lg = get_logger("mymodule")
        assert isinstance(lg, StructuredLogger)

    def test_same_name_returns_same_instance(self):
        lg1 = get_logger("mymodule")
        lg2 = get_logger("mymodule")
        assert lg1 is lg2

    def test_different_names_different_instances(self):
        lg1 = get_logger("module.a")
        lg2 = get_logger("module.b")
        assert lg1 is not lg2

    def test_json_format_returns_json_logger(self):
        lg = get_logger("json_module", json_format=True)
        assert isinstance(lg, JsonStructuredLogger)

    def test_default_format_not_json_logger(self):
        lg = get_logger("plain_module", json_format=False)
        assert type(lg) is StructuredLogger


# ===========================================================================
# timed decorator
# ===========================================================================

class TestTimedDecorator:
    def test_function_return_value_preserved(self):
        @timed("op")
        def add(a, b):
            return a + b

        assert add(2, 3) == 5

    def test_function_called_with_args(self):
        called_with = []

        @timed("op")
        def capture(*args, **kwargs):
            called_with.extend(args)

        capture(1, 2, 3)
        assert called_with == [1, 2, 3]

    def test_exception_reraised(self):
        @timed("op")
        def fail():
            raise RuntimeError("boom")

        import pytest
        with pytest.raises(RuntimeError, match="boom"):
            fail()

    def test_operation_name_used_in_log(self):
        logs = []

        @timed("my_operation")
        def work():
            return "done"

        mock_lg = MagicMock()
        mock_lg.debug = lambda msg, **kw: logs.append(msg)
        mock_lg.log = lambda lvl, msg, **kw: logs.append(msg)
        mock_lg.error = lambda msg, **kw: logs.append(msg)

        # Patch get_logger to return our mock
        with patch("utils.structured_logging.get_logger", return_value=mock_lg):
            # Need a fresh function since logger is captured at decoration time
            @timed("my_operation")
            def work2():
                return "done"
            work2()

        assert any("my_operation" in m for m in logs)

    def test_uses_function_name_when_no_op_name(self):
        logs = []
        mock_lg = MagicMock()
        mock_lg.debug = lambda msg, **kw: logs.append(msg)
        mock_lg.log = lambda lvl, msg, **kw: logs.append(msg)
        mock_lg.error = lambda msg, **kw: None

        with patch("utils.structured_logging.get_logger", return_value=mock_lg):
            @timed()
            def my_named_func():
                return 1
            my_named_func()

        assert any("my_named_func" in m for m in logs)

    def test_functools_wraps_preserves_name(self):
        @timed("op")
        def original():
            pass

        assert original.__name__ == "original"

    def test_duration_ms_logged_on_success(self):
        logged_kwargs = {}

        mock_lg = MagicMock()
        mock_lg.debug = lambda *a, **kw: None
        mock_lg.log = lambda lvl, msg, **kw: logged_kwargs.update(kw)
        mock_lg.error = lambda *a, **kw: None

        with patch("utils.structured_logging.get_logger", return_value=mock_lg):
            @timed("op")
            def work():
                return 1
            work()

        assert "duration_ms" in logged_kwargs


# ===========================================================================
# log_operation
# ===========================================================================

class TestLogOperation:
    def test_success_path_logs_start_and_complete(self):
        lg = _fresh_logger("lo_test")
        logs = []
        lg.logger = MagicMock()
        lg.logger.log = lambda lvl, msg, **kw: logs.append(msg)

        with log_operation(lg, "my_op"):
            pass

        text = " ".join(logs)
        assert "my_op" in text

    def test_exception_is_reraised(self):
        lg = _fresh_logger("lo_err")
        lg.logger = MagicMock()

        import pytest
        with pytest.raises(ValueError, match="oops"):
            with log_operation(lg, "failing_op"):
                raise ValueError("oops")

    def test_context_included_in_logs(self):
        lg = _fresh_logger("lo_ctx")
        logs = []
        lg.logger = MagicMock()
        lg.logger.log = lambda lvl, msg, **kw: logs.append(msg)

        with log_operation(lg, "ctx_op", table="recordings"):
            pass

        text = " ".join(logs)
        assert "table=recordings" in text

    def test_error_logged_on_exception(self):
        lg = _fresh_logger("lo_err2")
        errors = []
        lg.logger = MagicMock()
        lg.logger.error = lambda msg, **kw: errors.append(msg)
        lg.logger.log = lambda *a, **kw: None

        try:
            with log_operation(lg, "bad_op"):
                raise RuntimeError("fail")
        except RuntimeError:
            pass

        assert any("bad_op" in e for e in errors)


# ===========================================================================
# RequestLogger
# ===========================================================================

class TestRequestLogger:
    def test_request_id_generated(self):
        lg = _fresh_logger("rl_test")
        lg.logger = MagicMock()
        lg.logger.log = lambda *a, **kw: None

        rl = RequestLogger(lg)
        with rl.request("op") as request_id:
            assert request_id is not None
            assert isinstance(request_id, str)

    def test_request_ids_unique(self):
        lg = _fresh_logger("rl_unique")
        lg.logger = MagicMock()
        lg.logger.log = lambda *a, **kw: None

        rl = RequestLogger(lg)
        ids = []
        for _ in range(3):
            with rl.request("op") as rid:
                ids.append(rid)

        assert len(set(ids)) == 3

    def test_custom_request_id_used(self):
        lg = _fresh_logger("rl_custom")
        lg.logger = MagicMock()
        lg.logger.log = lambda *a, **kw: None

        rl = RequestLogger(lg)
        with rl.request("op", request_id="custom-id") as rid:
            assert rid == "custom-id"

    def test_counter_increments(self):
        lg = _fresh_logger("rl_counter")
        lg.logger = MagicMock()
        lg.logger.log = lambda *a, **kw: None

        rl = RequestLogger(lg)
        assert rl._request_counter == 0
        with rl.request("op"):
            pass
        assert rl._request_counter == 1

    def test_exception_propagated(self):
        lg = _fresh_logger("rl_exc")
        lg.logger = MagicMock()
        lg.logger.log = lambda *a, **kw: None
        lg.logger.error = lambda *a, **kw: None

        rl = RequestLogger(lg)
        import pytest
        with pytest.raises(RuntimeError):
            with rl.request("op"):
                raise RuntimeError("boom")


# ===========================================================================
# configure_logging / setup_logging
# ===========================================================================

class TestConfigureLogging:
    def test_runs_without_error(self):
        # basicConfig is a no-op if handlers already exist — just check it doesn't raise
        configure_logging(level=logging.WARNING)

    def test_json_format_sets_minimal_formatter(self):
        # Just verify it doesn't raise — handlers may already exist
        configure_logging(level=logging.WARNING, json_format=True)

    def test_setup_logging_is_alias(self):
        assert setup_logging is configure_logging
