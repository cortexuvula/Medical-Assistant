"""
Extended tests for src/utils/structured_logging.py

Covers:
- _sanitize_value() with SENSITIVE_FIELDS redaction
- _format_context() formatting of key-value pairs
- get_logger() returning correct logger types
- StructuredLogger log methods, context management
- JsonStructuredLogger JSON output
- timed() decorator measuring execution time
- log_operation() context manager
- RequestLogger with correlation IDs
- MAX_VALUE_LENGTH truncation
- get_log_level_from_string()
- configure_logging()
"""

import logging
import json
import time
import unittest
from unittest.mock import patch, MagicMock

from utils.structured_logging import (
    _sanitize_value,
    _format_context,
    get_logger,
    StructuredLogger,
    JsonStructuredLogger,
    timed,
    log_operation,
    RequestLogger,
    SENSITIVE_FIELDS,
    MAX_VALUE_LENGTH,
    get_log_level_from_string,
    configure_logging,
    _loggers,
    _loggers_lock,
)


class TestSanitizeValue(unittest.TestCase):
    """Tests for _sanitize_value()."""

    def test_redacts_sensitive_field_patient_name(self):
        result = _sanitize_value("patient_name", "John Doe")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_transcript(self):
        result = _sanitize_value("transcript", "Patient presents with headache...")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_api_key(self):
        result = _sanitize_value("api_key", "sk-abc123")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_password(self):
        result = _sanitize_value("password", "supersecret")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_soap_note(self):
        result = _sanitize_value("soap_note", "S: Patient reports...")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_diagnosis(self):
        result = _sanitize_value("diagnosis", "Hypertension")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_medication(self):
        result = _sanitize_value("medication", "Lisinopril 10mg")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_case_insensitive(self):
        """Key comparison should be case-insensitive."""
        result = _sanitize_value("Patient_Name", "Jane Doe")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_ssn(self):
        result = _sanitize_value("ssn", "123-45-6789")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_sensitive_field_dob(self):
        result = _sanitize_value("dob", "1985-03-15")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_phi_fields(self):
        """Verify several PHI-specific fields are redacted."""
        phi_fields = [
            "subjective", "objective", "plan", "assessment",
            "referral", "referral_letter", "discharge_summary",
            "vital_signs", "lab_result", "medical_history",
        ]
        for field_name in phi_fields:
            with self.subTest(field=field_name):
                result = _sanitize_value(field_name, "some PHI data")
                self.assertEqual(result, "[REDACTED]", f"Field '{field_name}' was not redacted")

    def test_non_sensitive_field_passes_through(self):
        result = _sanitize_value("recording_id", 42)
        self.assertEqual(result, 42)

    def test_non_sensitive_string_passes_through(self):
        result = _sanitize_value("status", "completed")
        self.assertEqual(result, "completed")

    def test_truncates_long_string(self):
        long_value = "x" * (MAX_VALUE_LENGTH + 100)
        result = _sanitize_value("description", long_value)
        self.assertEqual(len(result), MAX_VALUE_LENGTH + len("...[truncated]"))
        self.assertTrue(result.endswith("...[truncated]"))
        self.assertEqual(result[:MAX_VALUE_LENGTH], "x" * MAX_VALUE_LENGTH)

    def test_does_not_truncate_short_string(self):
        short_value = "x" * 10
        result = _sanitize_value("description", short_value)
        self.assertEqual(result, short_value)

    def test_string_exactly_at_max_length_not_truncated(self):
        exact_value = "a" * MAX_VALUE_LENGTH
        result = _sanitize_value("description", exact_value)
        self.assertEqual(result, exact_value)

    def test_redacts_value_containing_api_key_pattern(self):
        """Values containing 'api_key=' should be redacted regardless of key name."""
        result = _sanitize_value("debug_info", "connection api_key=sk-abc123 established")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_value_containing_password_pattern(self):
        result = _sanitize_value("log_line", "password=secret123")
        self.assertEqual(result, "[REDACTED]")

    def test_redacts_value_containing_token_pattern(self):
        result = _sanitize_value("message", "set token=xyz789abc")
        self.assertEqual(result, "[REDACTED]")

    def test_non_string_value_passes_through(self):
        result = _sanitize_value("count", 42)
        self.assertEqual(result, 42)

    def test_list_value_passes_through(self):
        result = _sanitize_value("items", [1, 2, 3])
        self.assertEqual(result, [1, 2, 3])

    def test_dict_value_passes_through(self):
        result = _sanitize_value("metadata", {"key": "value"})
        self.assertEqual(result, {"key": "value"})

    def test_none_value_passes_through(self):
        result = _sanitize_value("optional_field", None)
        self.assertIsNone(result)

    def test_sensitive_field_with_non_string_value_still_redacted(self):
        """Even numeric values should be redacted for sensitive fields."""
        result = _sanitize_value("patient_id", 12345)
        self.assertEqual(result, "[REDACTED]")


class TestFormatContext(unittest.TestCase):
    """Tests for _format_context()."""

    def test_empty_context_returns_empty_string(self):
        result = _format_context({})
        self.assertEqual(result, "")

    def test_none_like_empty_dict(self):
        """Empty dict should return empty string."""
        result = _format_context({})
        self.assertEqual(result, "")

    def test_single_key_value(self):
        result = _format_context({"status": "ok"})
        self.assertEqual(result, " | status=ok")

    def test_string_with_spaces_gets_quoted(self):
        result = _format_context({"message": "hello world"})
        self.assertEqual(result, ' | message="hello world"')

    def test_string_with_quotes_gets_quoted(self):
        result = _format_context({"name": 'say "hi"'})
        self.assertIn('name="say "hi""', result)

    def test_numeric_value(self):
        result = _format_context({"count": 42})
        self.assertEqual(result, " | count=42")

    def test_list_value_json_encoded(self):
        result = _format_context({"items": [1, 2, 3]})
        self.assertIn("items=[1, 2, 3]", result)

    def test_dict_value_json_encoded(self):
        result = _format_context({"meta": {"a": 1}})
        self.assertIn('meta=', result)

    def test_multiple_key_values(self):
        result = _format_context({"a": 1, "b": 2})
        self.assertIn("a=1", result)
        self.assertIn("b=2", result)
        self.assertTrue(result.startswith(" | "))

    def test_sensitive_field_redacted_in_context(self):
        result = _format_context({"patient_name": "John Doe"})
        self.assertIn("[REDACTED]", result)
        self.assertNotIn("John Doe", result)

    def test_long_string_truncated_in_context(self):
        long_val = "x" * (MAX_VALUE_LENGTH + 50)
        result = _format_context({"data": long_val})
        self.assertIn("...[truncated]", result)


class TestGetLogger(unittest.TestCase):
    """Tests for get_logger()."""

    def setUp(self):
        """Clear the logger cache before each test."""
        with _loggers_lock:
            # Remove test-specific loggers to avoid cross-test pollution
            keys_to_remove = [k for k in _loggers if k.startswith("test.")]
            for k in keys_to_remove:
                del _loggers[k]

    def test_returns_structured_logger(self):
        logger = get_logger("test.module1")
        self.assertIsInstance(logger, StructuredLogger)

    def test_returns_json_logger_when_requested(self):
        logger = get_logger("test.json_module", json_format=True)
        self.assertIsInstance(logger, JsonStructuredLogger)

    def test_caches_logger_instance(self):
        logger1 = get_logger("test.cached")
        logger2 = get_logger("test.cached")
        self.assertIs(logger1, logger2)

    def test_different_names_return_different_loggers(self):
        logger1 = get_logger("test.module_a")
        logger2 = get_logger("test.module_b")
        self.assertIsNot(logger1, logger2)

    def test_logger_has_correct_name(self):
        logger = get_logger("test.named_module")
        self.assertEqual(logger.name, "test.named_module")


class TestStructuredLogger(unittest.TestCase):
    """Tests for the StructuredLogger class."""

    def setUp(self):
        self.logger = StructuredLogger("test.structured")
        self.logger.logger = MagicMock()

    def test_info_logs_message(self):
        self.logger.info("Hello")
        self.logger.logger.log.assert_called_once()
        args = self.logger.logger.log.call_args
        self.assertEqual(args[0][0], logging.INFO)
        self.assertIn("Hello", args[0][1])

    def test_debug_logs_at_debug_level(self):
        self.logger.debug("Debug msg")
        self.logger.logger.log.assert_called_once()
        self.assertEqual(self.logger.logger.log.call_args[0][0], logging.DEBUG)

    def test_warning_logs_at_warning_level(self):
        self.logger.warning("Warn msg")
        self.logger.logger.log.assert_called_once()
        self.assertEqual(self.logger.logger.log.call_args[0][0], logging.WARNING)

    def test_critical_logs_at_critical_level(self):
        self.logger.critical("Critical msg")
        self.logger.logger.log.assert_called_once()
        self.assertEqual(self.logger.logger.log.call_args[0][0], logging.CRITICAL)

    def test_error_logs_message(self):
        self.logger.error("Error msg")
        self.logger.logger.error.assert_called_once()
        self.assertIn("Error msg", self.logger.logger.error.call_args[0][0])

    def test_error_with_exc_info(self):
        self.logger.error("Error", exc_info=True)
        self.logger.logger.error.assert_called_once()
        self.assertTrue(self.logger.logger.error.call_args[1]["exc_info"])

    def test_exception_logs_with_exc_info(self):
        self.logger.exception("Oops")
        self.logger.logger.error.assert_called_once()
        self.assertTrue(self.logger.logger.error.call_args[1]["exc_info"])

    def test_log_with_context_kwargs(self):
        self.logger.info("Processing", recording_id=42, status="ok")
        msg = self.logger.logger.log.call_args[0][1]
        self.assertIn("recording_id=42", msg)
        self.assertIn("status=ok", msg)

    def test_set_context_persists(self):
        # session_id is in SENSITIVE_FIELDS so it gets redacted
        self.logger.set_context(request_count="5")
        self.logger.info("Test")
        msg = self.logger.logger.log.call_args[0][1]
        self.assertIn("request_count=5", msg)

    def test_clear_context(self):
        self.logger.set_context(session_id="abc")
        self.logger.clear_context()
        self.logger.info("Test")
        msg = self.logger.logger.log.call_args[0][1]
        self.assertNotIn("session_id", msg)

    def test_context_manager(self):
        self.logger.info("Before")
        msg_before = self.logger.logger.log.call_args[0][1]
        self.assertNotIn("request_id", msg_before)

        with self.logger.context(request_id="req-1"):
            self.logger.info("During")
            msg_during = self.logger.logger.log.call_args[0][1]
            self.assertIn("request_id=req-1", msg_during)

        self.logger.info("After")
        msg_after = self.logger.logger.log.call_args[0][1]
        self.assertNotIn("request_id", msg_after)

    def test_log_method_delegates_to_internal_log(self):
        self.logger.log(logging.WARNING, "Custom level")
        self.logger.logger.log.assert_called_once()
        self.assertEqual(self.logger.logger.log.call_args[0][0], logging.WARNING)

    def test_isEnabledFor_delegates(self):
        self.logger.logger.isEnabledFor.return_value = True
        self.assertTrue(self.logger.isEnabledFor(logging.DEBUG))
        self.logger.logger.isEnabledFor.assert_called_with(logging.DEBUG)

    def test_kwargs_override_context(self):
        """Call-specific kwargs should override persistent context."""
        self.logger.set_context(status="pending")
        self.logger.info("Test", status="done")
        msg = self.logger.logger.log.call_args[0][1]
        self.assertIn("status=done", msg)


class TestJsonStructuredLogger(unittest.TestCase):
    """Tests for JsonStructuredLogger JSON output."""

    def setUp(self):
        self.logger = JsonStructuredLogger("test.json")
        self.logger.logger = MagicMock()

    def test_logs_json_format(self):
        self.logger.info("Test message", count=5)
        msg = self.logger.logger.log.call_args[0][1]
        parsed = json.loads(msg)
        self.assertEqual(parsed["message"], "Test message")
        self.assertEqual(parsed["count"], 5)
        self.assertEqual(parsed["level"], "INFO")
        self.assertEqual(parsed["logger"], "test.json")
        self.assertIn("timestamp", parsed)

    def test_json_sanitizes_sensitive_fields(self):
        self.logger.info("Processing", patient_name="Jane")
        msg = self.logger.logger.log.call_args[0][1]
        parsed = json.loads(msg)
        self.assertEqual(parsed["patient_name"], "[REDACTED]")

    def test_json_includes_persistent_context(self):
        self.logger.set_context(module="auth")
        self.logger.info("Login")
        msg = self.logger.logger.log.call_args[0][1]
        parsed = json.loads(msg)
        self.assertEqual(parsed["module"], "auth")


class TestTimedDecorator(unittest.TestCase):
    """Tests for the timed() decorator."""

    def test_measures_execution_time(self):
        mock_logger = MagicMock(spec=StructuredLogger)

        @timed("test_op", logger=mock_logger)
        def fast_func():
            return "result"

        result = fast_func()
        self.assertEqual(result, "result")

        # Should have logged "Starting" and "Completed"
        self.assertEqual(mock_logger.debug.call_count, 1)
        self.assertIn("Starting test_op", mock_logger.debug.call_args[0][0])
        mock_logger.log.assert_called_once()
        completed_msg = mock_logger.log.call_args[0][1]
        self.assertIn("Completed test_op", completed_msg)

    def test_logs_error_on_exception(self):
        mock_logger = MagicMock(spec=StructuredLogger)

        @timed("failing_op", logger=mock_logger)
        def failing_func():
            raise ValueError("test error")

        with self.assertRaises(ValueError):
            failing_func()

        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        self.assertIn("Failed failing_op", error_msg)

    def test_uses_function_name_as_default_operation(self):
        mock_logger = MagicMock(spec=StructuredLogger)

        @timed(logger=mock_logger)
        def my_special_function():
            return 42

        my_special_function()
        self.assertIn("my_special_function", mock_logger.debug.call_args[0][0])

    def test_preserves_function_name_and_docstring(self):
        @timed("op")
        def documented_func():
            """This is a documented function."""
            pass

        self.assertEqual(documented_func.__name__, "documented_func")
        self.assertEqual(documented_func.__doc__, "This is a documented function.")

    def test_duration_is_positive(self):
        mock_logger = MagicMock(spec=StructuredLogger)

        @timed("op", logger=mock_logger)
        def sleepy():
            time.sleep(0.01)

        sleepy()
        kwargs = mock_logger.log.call_args[1]
        self.assertGreater(kwargs["duration_ms"], 0)


class TestLogOperation(unittest.TestCase):
    """Tests for log_operation() context manager."""

    def test_logs_start_and_completion(self):
        mock_logger = MagicMock(spec=StructuredLogger)

        with log_operation(mock_logger, "db_query", table="recordings"):
            pass

        # Should have 2 info calls: starting + completed
        self.assertEqual(mock_logger.info.call_count, 2)
        start_msg = mock_logger.info.call_args_list[0][0][0]
        self.assertIn("Starting db_query", start_msg)
        complete_msg = mock_logger.info.call_args_list[1][0][0]
        self.assertIn("Completed db_query", complete_msg)

    def test_logs_error_on_exception(self):
        mock_logger = MagicMock(spec=StructuredLogger)

        with self.assertRaises(RuntimeError):
            with log_operation(mock_logger, "bad_op"):
                raise RuntimeError("fail")

        mock_logger.error.assert_called_once()
        error_msg = mock_logger.error.call_args[0][0]
        self.assertIn("Failed bad_op", error_msg)


class TestRequestLogger(unittest.TestCase):
    """Tests for RequestLogger with correlation IDs."""

    def test_generates_request_id(self):
        base_logger = MagicMock(spec=StructuredLogger)
        base_logger.context = MagicMock()
        base_logger.context.return_value.__enter__ = MagicMock(return_value=base_logger)
        base_logger.context.return_value.__exit__ = MagicMock(return_value=False)

        req_logger = RequestLogger(base_logger)
        req_id = req_logger._generate_request_id()
        self.assertIsInstance(req_id, str)
        self.assertIn("-", req_id)

    def test_increments_counter(self):
        base_logger = MagicMock(spec=StructuredLogger)
        req_logger = RequestLogger(base_logger)

        id1 = req_logger._generate_request_id()
        id2 = req_logger._generate_request_id()
        # Counter portion should differ
        self.assertNotEqual(id1, id2)


class TestGetLogLevelFromString(unittest.TestCase):
    """Tests for get_log_level_from_string()."""

    def test_debug(self):
        self.assertEqual(get_log_level_from_string("DEBUG"), logging.DEBUG)

    def test_info(self):
        self.assertEqual(get_log_level_from_string("INFO"), logging.INFO)

    def test_warning(self):
        self.assertEqual(get_log_level_from_string("WARNING"), logging.WARNING)

    def test_error(self):
        self.assertEqual(get_log_level_from_string("ERROR"), logging.ERROR)

    def test_critical(self):
        self.assertEqual(get_log_level_from_string("CRITICAL"), logging.CRITICAL)

    def test_case_insensitive(self):
        self.assertEqual(get_log_level_from_string("debug"), logging.DEBUG)

    def test_unknown_level_defaults_to_info(self):
        self.assertEqual(get_log_level_from_string("VERBOSE"), logging.INFO)


class TestConfigureLogging(unittest.TestCase):
    """Tests for configure_logging()."""

    def setUp(self):
        """Save root logger state and clear handlers so basicConfig takes effect."""
        self.root = logging.getLogger()
        self._saved_handlers = self.root.handlers[:]
        self._saved_level = self.root.level
        self.root.handlers.clear()

    def tearDown(self):
        """Restore root logger state."""
        self.root.handlers[:] = self._saved_handlers
        self.root.setLevel(self._saved_level)

    def test_configure_with_explicit_level(self):
        """Should configure root logger to the specified level."""
        configure_logging(level=logging.WARNING)
        self.assertEqual(self.root.level, logging.WARNING)

    def test_configure_json_format(self):
        """JSON format should set minimal formatter on root handlers."""
        configure_logging(level=logging.INFO, json_format=True)
        # At least one handler should have a minimal format
        found_minimal = False
        for handler in self.root.handlers:
            fmt = handler.formatter
            if fmt is not None:
                # Check the format string (access via public format method)
                if fmt.format(logging.LogRecord("n", 0, "", 0, "test", (), None)) == "test":
                    found_minimal = True
                    break
        self.assertTrue(found_minimal, "No handler with minimal '%(message)s' format found")


class TestSensitiveFieldsCoverage(unittest.TestCase):
    """Ensure the SENSITIVE_FIELDS frozenset contains expected entries."""

    def test_contains_security_credentials(self):
        for field in ['api_key', 'password', 'secret', 'token', 'auth', 'jwt']:
            self.assertIn(field, SENSITIVE_FIELDS, f"Missing security field: {field}")

    def test_contains_phi_fields(self):
        for field in ['patient_name', 'diagnosis', 'transcript', 'soap_note',
                       'medication', 'vital_signs', 'lab_result']:
            self.assertIn(field, SENSITIVE_FIELDS, f"Missing PHI field: {field}")

    def test_contains_pii_fields(self):
        for field in ['ssn', 'credit_card', 'bank_account']:
            self.assertIn(field, SENSITIVE_FIELDS, f"Missing PII field: {field}")

    def test_max_value_length_is_reasonable(self):
        self.assertEqual(MAX_VALUE_LENGTH, 500)


if __name__ == "__main__":
    unittest.main()
