"""
Unit tests for src/utils/error_handling.py

Tests cover:
- sanitize_error_for_user: user-friendly error message mapping
- ErrorTemplate / show_error_dialog / get_sanitized_error: error template system
- ErrorSeverity enum
- OperationResult: success/failure, to_dict, bool, unwrap, unwrap_or, map
- handle_errors decorator: severity levels, return types
- ui_error_context: context manager for UI operations
- AsyncUIErrorHandler: async UI error handling
- safe_execute: safe function execution wrapper
- format_error_for_user: error message formatting
- log_and_raise: log-then-raise helper
- ErrorContext: error context capture and formatting
- safe_ui_update / SafeUIUpdater: thread-safe UI update wrappers
- run_in_thread: background thread execution with callbacks
"""

import logging
import threading
import time
import unittest
from dataclasses import dataclass
from unittest.mock import Mock, MagicMock, patch, call

from utils.error_handling import (
    sanitize_error_for_user,
    _USER_FRIENDLY_ERRORS,
    _ERROR_TEMPLATES,
    ErrorTemplate,
    show_error_dialog,
    get_sanitized_error,
    ErrorSeverity,
    OperationResult,
    handle_errors,
    ui_error_context,
    AsyncUIErrorHandler,
    safe_execute,
    format_error_for_user,
    log_and_raise,
    ErrorContext,
    safe_ui_update,
    SafeUIUpdater,
    run_in_thread,
)


# ---------------------------------------------------------------------------
# sanitize_error_for_user
# ---------------------------------------------------------------------------

class TestSanitizeErrorForUser(unittest.TestCase):
    """Tests for sanitize_error_for_user()."""

    def test_known_error_type_authentication(self):
        """Should match AuthenticationError by type name."""
        class AuthenticationError(Exception):
            pass
        result = sanitize_error_for_user(AuthenticationError("bad key"))
        self.assertEqual(result, "API authentication failed. Please check your API key.")

    def test_known_error_type_rate_limit(self):
        class RateLimitError(Exception):
            pass
        result = sanitize_error_for_user(RateLimitError("too many"))
        self.assertEqual(result, "API rate limit exceeded. Please wait and try again.")

    def test_known_error_type_api_connection(self):
        class APIConnectionError(Exception):
            pass
        result = sanitize_error_for_user(APIConnectionError("no net"))
        self.assertEqual(result, "Could not connect to the AI service. Please check your internet connection.")

    def test_known_error_type_timeout(self):
        class TimeoutError(Exception):
            pass
        result = sanitize_error_for_user(TimeoutError("took too long"))
        self.assertEqual(result, "The request timed out. Please try again.")

    def test_known_error_type_invalid_request(self):
        class InvalidRequestError(Exception):
            pass
        result = sanitize_error_for_user(InvalidRequestError("bad input"))
        self.assertEqual(result, "The request was invalid. Please check your input.")

    def test_known_error_type_service_unavailable(self):
        class ServiceUnavailableError(Exception):
            pass
        result = sanitize_error_for_user(ServiceUnavailableError("down"))
        self.assertEqual(result, "The AI service is temporarily unavailable. Please try again later.")

    def test_message_pattern_timeout(self):
        """Should fall through type check and match message pattern."""
        err = Exception("Request timeout after 30s")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "The request timed out. Please try again.")

    def test_message_pattern_connection(self):
        err = Exception("connection refused by server")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Could not connect to the service. Please check your internet connection.")

    def test_message_pattern_connect(self):
        err = Exception("failed to connect")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Could not connect to the service. Please check your internet connection.")

    def test_message_pattern_rate_limit(self):
        err = Exception("rate limit exceeded")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Rate limit exceeded. Please wait and try again.")

    def test_message_pattern_quota(self):
        err = Exception("quota exceeded for today")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Rate limit exceeded. Please wait and try again.")

    def test_message_pattern_unauthorized(self):
        err = Exception("unauthorized access")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Authentication failed. Please verify your API key is correct.")

    def test_message_pattern_authentication(self):
        err = Exception("authentication failed for user")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Authentication failed. Please verify your API key is correct.")

    def test_message_pattern_api_key(self):
        err = Exception("api key is invalid")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Authentication failed. Please verify your API key is correct.")

    def test_message_pattern_invalid(self):
        err = Exception("invalid parameter supplied")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "Invalid request. Please check your input and try again.")

    def test_generic_fallback(self):
        """Unknown errors should return generic message."""
        err = Exception("some obscure internal error xyz_12345")
        result = sanitize_error_for_user(err)
        self.assertEqual(result, "An error occurred while processing your request. Please try again.")


# ---------------------------------------------------------------------------
# ErrorTemplate / show_error_dialog / get_sanitized_error
# ---------------------------------------------------------------------------

class TestErrorTemplateSystem(unittest.TestCase):
    """Tests for the error template system."""

    def test_error_templates_keys_exist(self):
        expected_keys = {
            "save_file", "load_file", "export_pdf", "export_word",
            "export_fhir", "print_document", "save_settings", "api_keys",
            "import_prompts", "export_prompts", "upload_document",
            "load_recording", "reprocess", "chat_error", "open_dialog",
            "generic",
        }
        self.assertTrue(expected_keys.issubset(set(_ERROR_TEMPLATES.keys())))

    def test_error_template_has_required_fields(self):
        for key, tmpl in _ERROR_TEMPLATES.items():
            self.assertIsInstance(tmpl, ErrorTemplate, f"Template '{key}' not ErrorTemplate")
            self.assertTrue(tmpl.title, f"Template '{key}' missing title")
            self.assertTrue(tmpl.problem, f"Template '{key}' missing problem")
            self.assertIsInstance(tmpl.actions, list, f"Template '{key}' actions not a list")
            self.assertTrue(len(tmpl.actions) > 0, f"Template '{key}' has no actions")

    @patch("utils.error_handling.logger")
    def test_show_error_dialog_known_category(self, mock_logger):
        with patch("tkinter.messagebox.showerror") as mock_showerror:
            err = ValueError("test error")
            show_error_dialog("save_file", err, parent=None)

            mock_showerror.assert_called_once()
            args = mock_showerror.call_args
            self.assertEqual(args[0][0], "Save Error")
            self.assertIn("could not be saved", args[0][1])
            self.assertIn("What to try:", args[0][1])

    @patch("utils.error_handling.logger")
    def test_show_error_dialog_unknown_category_uses_generic(self, mock_logger):
        with patch("tkinter.messagebox.showerror") as mock_showerror:
            err = RuntimeError("oops")
            show_error_dialog("nonexistent_category_xyz", err)

            mock_showerror.assert_called_once()
            args = mock_showerror.call_args
            self.assertEqual(args[0][0], "Error")  # generic title
            self.assertIn("unexpected error", args[0][1])

    @patch("utils.error_handling.logger")
    def test_show_error_dialog_with_detail(self, mock_logger):
        with patch("tkinter.messagebox.showerror") as mock_showerror:
            show_error_dialog("save_file", ValueError("x"), detail="Disk full")

            msg = mock_showerror.call_args[0][1]
            self.assertIn("Disk full", msg)

    def test_get_sanitized_error_known_category(self):
        result = get_sanitized_error("save_file", ValueError("x"))
        self.assertEqual(result, "The file could not be saved.")

    def test_get_sanitized_error_unknown_category(self):
        result = get_sanitized_error("nonexistent", ValueError("x"))
        self.assertEqual(result, "An unexpected error occurred.")


# ---------------------------------------------------------------------------
# ErrorSeverity
# ---------------------------------------------------------------------------

class TestErrorSeverity(unittest.TestCase):

    def test_values(self):
        self.assertEqual(ErrorSeverity.CRITICAL.value, "critical")
        self.assertEqual(ErrorSeverity.ERROR.value, "error")
        self.assertEqual(ErrorSeverity.WARNING.value, "warning")
        self.assertEqual(ErrorSeverity.INFO.value, "info")

    def test_members(self):
        self.assertEqual(len(ErrorSeverity), 4)


# ---------------------------------------------------------------------------
# OperationResult
# ---------------------------------------------------------------------------

class TestOperationResult(unittest.TestCase):

    # --- factory methods ---
    def test_success_factory(self):
        r = OperationResult.success(42)
        self.assertTrue(r.success)
        self.assertEqual(r.value, 42)
        self.assertIsNone(r.error)

    def test_success_factory_with_details(self):
        r = OperationResult.success("ok", foo="bar")
        self.assertEqual(r.details, {"foo": "bar"})

    def test_failure_factory(self):
        r = OperationResult.failure("bad things")
        self.assertFalse(r.success)
        self.assertEqual(r.error, "bad things")
        self.assertIsNone(r.value)

    def test_failure_factory_with_exception(self):
        exc = ValueError("val err")
        r = OperationResult.failure("msg", error_code="E001", exception=exc, extra="data")
        self.assertEqual(r.error_code, "E001")
        self.assertIs(r.exception, exc)
        self.assertEqual(r.details, {"extra": "data"})

    # --- to_dict ---
    def test_to_dict_success_with_dict_value(self):
        r = OperationResult.success({"text": "hello"})
        d = r.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["text"], "hello")

    def test_to_dict_success_with_non_dict_value(self):
        r = OperationResult.success(99)
        d = r.to_dict()
        self.assertTrue(d["success"])
        self.assertEqual(d["value"], 99)

    def test_to_dict_success_with_none_value(self):
        r = OperationResult.success(None)
        d = r.to_dict()
        self.assertTrue(d["success"])
        self.assertNotIn("value", d)

    def test_to_dict_failure(self):
        r = OperationResult.failure("oops")
        d = r.to_dict()
        self.assertFalse(d["success"])
        self.assertEqual(d["error"], "oops")

    def test_to_dict_failure_with_error_code(self):
        r = OperationResult.failure("oops", error_code="E42")
        d = r.to_dict()
        self.assertEqual(d["error_code"], "E42")

    def test_to_dict_failure_no_error_message(self):
        r = OperationResult(success=False)
        d = r.to_dict()
        self.assertEqual(d["error"], "Unknown error")

    # --- bool ---
    def test_bool_true(self):
        self.assertTrue(bool(OperationResult.success(1)))

    def test_bool_false(self):
        self.assertFalse(bool(OperationResult.failure("err")))

    # --- unwrap ---
    def test_unwrap_success(self):
        r = OperationResult.success("hello")
        self.assertEqual(r.unwrap(), "hello")

    def test_unwrap_failure_raises_original_exception(self):
        exc = RuntimeError("boom")
        r = OperationResult.failure("msg", exception=exc)
        with self.assertRaises(RuntimeError):
            r.unwrap()

    def test_unwrap_failure_raises_value_error(self):
        r = OperationResult.failure("msg")
        with self.assertRaises(ValueError) as ctx:
            r.unwrap()
        self.assertIn("msg", str(ctx.exception))

    def test_unwrap_failure_no_message(self):
        r = OperationResult(success=False)
        with self.assertRaises(ValueError) as ctx:
            r.unwrap()
        self.assertIn("Operation failed", str(ctx.exception))

    # --- unwrap_or ---
    def test_unwrap_or_success(self):
        r = OperationResult.success(10)
        self.assertEqual(r.unwrap_or(0), 10)

    def test_unwrap_or_failure(self):
        r = OperationResult.failure("err")
        self.assertEqual(r.unwrap_or(0), 0)

    # --- map ---
    def test_map_success(self):
        r = OperationResult.success(5)
        r2 = r.map(lambda x: x * 2)
        self.assertTrue(r2.success)
        self.assertEqual(r2.value, 10)

    def test_map_failure_passthrough(self):
        r = OperationResult.failure("err")
        r2 = r.map(lambda x: x * 2)
        self.assertFalse(r2.success)
        self.assertIs(r2, r)

    def test_map_exception_in_func(self):
        r = OperationResult.success(5)
        r2 = r.map(lambda x: 1 / 0)
        self.assertFalse(r2.success)
        self.assertIn("division by zero", r2.error)
        self.assertIsInstance(r2.exception, ZeroDivisionError)


# ---------------------------------------------------------------------------
# handle_errors decorator
# ---------------------------------------------------------------------------

class TestHandleErrors(unittest.TestCase):

    @patch("utils.error_handling.logger")
    def test_no_error_returns_normally(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR)
        def good():
            return OperationResult.success(42)

        r = good()
        self.assertTrue(r.success)
        self.assertEqual(r.value, 42)

    @patch("utils.error_handling.logger")
    def test_critical_reraises(self, mock_logger):
        @handle_errors(ErrorSeverity.CRITICAL)
        def boom():
            raise RuntimeError("critical!")

        with self.assertRaises(RuntimeError):
            boom()
        mock_logger.error.assert_called()

    @patch("utils.error_handling.logger")
    def test_error_returns_operation_result(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR)
        def fail():
            raise ValueError("bad")

        r = fail()
        self.assertFalse(r.success)
        self.assertIsInstance(r, OperationResult)
        mock_logger.error.assert_called()

    @patch("utils.error_handling.logger")
    def test_warning_logs_warning(self, mock_logger):
        @handle_errors(ErrorSeverity.WARNING, return_type="none")
        def warn():
            raise ValueError("hmm")

        result = warn()
        self.assertIsNone(result)
        mock_logger.warning.assert_called()

    @patch("utils.error_handling.logger")
    def test_info_logs_info(self, mock_logger):
        @handle_errors(ErrorSeverity.INFO, return_type="none")
        def info_op():
            raise ValueError("fyi")

        result = info_op()
        self.assertIsNone(result)
        mock_logger.info.assert_called()

    @patch("utils.error_handling.logger")
    def test_return_type_dict(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR, return_type="dict")
        def fail():
            raise ValueError("d")

        r = fail()
        self.assertIsInstance(r, dict)
        self.assertFalse(r["success"])
        self.assertIn("error", r)

    @patch("utils.error_handling.logger")
    def test_return_type_bool(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR, return_type="bool")
        def fail():
            raise ValueError("b")

        self.assertFalse(fail())

    @patch("utils.error_handling.logger")
    def test_return_type_none(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR, return_type="none")
        def fail():
            raise ValueError("n")

        self.assertIsNone(fail())

    @patch("utils.error_handling.logger")
    def test_custom_error_message(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR, error_message="Custom prefix")
        def fail():
            raise ValueError("details")

        r = fail()
        self.assertIn("Custom prefix", r.error)

    @patch("utils.error_handling.logger")
    def test_preserves_function_name(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR)
        def my_function():
            pass

        self.assertEqual(my_function.__name__, "my_function")


# ---------------------------------------------------------------------------
# ui_error_context
# ---------------------------------------------------------------------------

class TestUIErrorContext(unittest.TestCase):

    def _make_mocks(self):
        import tkinter as tk
        status_manager = Mock()
        button = Mock()
        button.cget.return_value = tk.NORMAL
        progress_bar = Mock()
        return status_manager, button, progress_bar

    @patch("utils.error_handling.logger")
    def test_success_path(self, mock_logger):
        sm, btn, pb = self._make_mocks()
        with ui_error_context(sm, btn, pb, "TestOp"):
            pass  # no error

        sm.progress.assert_called_once_with("TestOp...")
        sm.success.assert_called_once_with("TestOp completed")
        # Button restored
        self.assertEqual(btn.config.call_count, 2)  # disable + restore
        # Progress bar stopped
        pb.stop.assert_called_once()
        pb.pack_forget.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_success_no_show_success(self, mock_logger):
        sm, btn, pb = self._make_mocks()
        with ui_error_context(sm, btn, pb, "TestOp", show_success=False):
            pass

        sm.success.assert_not_called()

    @patch("utils.error_handling.logger")
    def test_error_path_reraises(self, mock_logger):
        sm, btn, pb = self._make_mocks()
        with self.assertRaises(ValueError):
            with ui_error_context(sm, btn, pb, "TestOp"):
                raise ValueError("fail")

        sm.error.assert_called_once()
        self.assertIn("TestOp failed", sm.error.call_args[0][0])
        # Cleanup still runs
        pb.stop.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_no_button_no_progress(self, mock_logger):
        sm = Mock()
        with ui_error_context(sm, button=None, progress_bar=None, operation_name="Op"):
            pass
        sm.progress.assert_called_once()
        sm.success.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_button_tclerror_handled(self, mock_logger):
        """TclError on button operations should not propagate."""
        import tkinter as tk
        sm = Mock()
        btn = Mock()
        btn.cget.side_effect = tk.TclError("destroyed")
        pb = Mock()
        pb.pack.side_effect = tk.TclError("destroyed")

        with ui_error_context(sm, btn, pb, "Op"):
            pass
        # Should complete without raising


# ---------------------------------------------------------------------------
# AsyncUIErrorHandler
# ---------------------------------------------------------------------------

class TestAsyncUIErrorHandler(unittest.TestCase):

    def _make_handler(self):
        app = Mock()
        # Make app.after execute callback immediately
        app.after = Mock(side_effect=lambda ms, fn: fn())
        button = Mock()
        progress_bar = Mock()
        return AsyncUIErrorHandler(app, button, progress_bar, "TestOp"), app, button, progress_bar

    def test_start_disables_button_and_shows_progress(self):
        handler, app, btn, pb = self._make_handler()
        handler.start()

        self.assertTrue(handler._started)
        btn.config.assert_called()
        pb.start.assert_called_once()

    def test_start_idempotent(self):
        handler, app, btn, pb = self._make_handler()
        handler.start()
        handler.start()  # second call should be no-op

        self.assertEqual(app.after.call_count, 1)

    def test_complete_restores_ui(self):
        handler, app, btn, pb = self._make_handler()
        callback = Mock()
        handler.complete(callback=callback, success_message="Done!")

        callback.assert_called_once()
        pb.stop.assert_called_once()
        pb.pack_forget.assert_called_once()

    def test_complete_default_message(self):
        handler, app, btn, pb = self._make_handler()
        app.status_manager = Mock()
        handler.complete()

        app.status_manager.success.assert_called_once_with("TestOp completed")

    @patch("utils.error_handling.logger")
    def test_fail_with_exception(self, mock_logger):
        handler, app, btn, pb = self._make_handler()
        app.status_manager = Mock()
        callback = Mock()
        handler.fail(ValueError("err"), callback=callback)

        app.status_manager.error.assert_called_once()
        self.assertIn("TestOp failed", app.status_manager.error.call_args[0][0])
        callback.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_fail_with_string(self, mock_logger):
        handler, app, btn, pb = self._make_handler()
        app.status_manager = Mock()
        handler.fail("string error")

        self.assertIn("string error", app.status_manager.error.call_args[0][0])

    def test_restore_ui_handles_tclerror(self):
        """TclError during restore should not propagate."""
        import tkinter as tk
        handler, app, btn, pb = self._make_handler()
        btn.config.side_effect = tk.TclError("gone")
        pb.stop.side_effect = tk.TclError("gone")

        handler._restore_ui()  # Should not raise


# ---------------------------------------------------------------------------
# safe_execute
# ---------------------------------------------------------------------------

class TestSafeExecute(unittest.TestCase):

    @patch("utils.error_handling.logger")
    def test_success(self, mock_logger):
        result = safe_execute(lambda: 42)
        self.assertEqual(result, 42)

    @patch("utils.error_handling.logger")
    def test_error_returns_default(self, mock_logger):
        result = safe_execute(lambda: 1 / 0, default="fallback")
        self.assertEqual(result, "fallback")

    @patch("utils.error_handling.logger")
    def test_error_calls_handler(self, mock_logger):
        handler = Mock()
        safe_execute(lambda: 1 / 0, error_handler=handler, default=None)
        handler.assert_called_once()
        self.assertIsInstance(handler.call_args[0][0], ZeroDivisionError)

    @patch("utils.error_handling.logger")
    def test_error_no_log(self, mock_logger):
        safe_execute(lambda: 1 / 0, log_errors=False, default=None)
        mock_logger.warning.assert_not_called()

    @patch("utils.error_handling.logger")
    def test_passes_args_and_kwargs(self, mock_logger):
        def fn(a, b, c=10):
            return a + b + c
        result = safe_execute(fn, 1, 2, c=3)
        self.assertEqual(result, 6)

    @patch("utils.error_handling.logger")
    def test_default_is_none(self, mock_logger):
        result = safe_execute(lambda: 1 / 0)
        self.assertIsNone(result)


# ---------------------------------------------------------------------------
# format_error_for_user
# ---------------------------------------------------------------------------

class TestFormatErrorForUser(unittest.TestCase):

    def test_strips_error_prefix(self):
        self.assertEqual(format_error_for_user("Error: something"), "Something")

    def test_strips_exception_prefix(self):
        self.assertEqual(format_error_for_user("Exception: something"), "Something")

    def test_strips_failed_prefix(self):
        self.assertEqual(format_error_for_user("Failed: something"), "Something")

    def test_capitalizes_first_letter(self):
        self.assertEqual(format_error_for_user("lowercase message"), "Lowercase message")

    def test_exception_input(self):
        result = format_error_for_user(ValueError("Error: bad value"))
        self.assertEqual(result, "Bad value")

    def test_empty_string(self):
        self.assertEqual(format_error_for_user(""), "")

    def test_no_prefix(self):
        self.assertEqual(format_error_for_user("already fine"), "Already fine")


# ---------------------------------------------------------------------------
# log_and_raise
# ---------------------------------------------------------------------------

class TestLogAndRaise(unittest.TestCase):

    @patch("utils.error_handling.logger")
    def test_logs_and_raises(self, mock_logger):
        with self.assertRaises(ValueError):
            try:
                raise ValueError("test")
            except ValueError as e:
                log_and_raise(e, "Context message")

        mock_logger.log.assert_called_once()
        args = mock_logger.log.call_args[0]
        self.assertEqual(args[0], logging.ERROR)
        self.assertIn("Context message", args[1])
        self.assertIn("test", args[1])

    @patch("utils.error_handling.logger")
    def test_logs_without_message(self, mock_logger):
        with self.assertRaises(RuntimeError):
            try:
                raise RuntimeError("raw")
            except RuntimeError as e:
                log_and_raise(e)

        logged_msg = mock_logger.log.call_args[0][1]
        self.assertEqual(logged_msg, "raw")

    @patch("utils.error_handling.logger")
    def test_custom_log_level(self, mock_logger):
        with self.assertRaises(ValueError):
            try:
                raise ValueError("x")
            except ValueError as e:
                log_and_raise(e, log_level=logging.WARNING)

        self.assertEqual(mock_logger.log.call_args[0][0], logging.WARNING)


# ---------------------------------------------------------------------------
# ErrorContext
# ---------------------------------------------------------------------------

class TestErrorContext(unittest.TestCase):

    def test_capture_with_exception(self):
        try:
            raise ValueError("test error")
        except ValueError as e:
            ctx = ErrorContext.capture(
                operation="Processing",
                exception=e,
                input_summary="10 items",
                error_code="E42",
                custom_key="custom_value",
            )

        self.assertEqual(ctx.operation, "Processing")
        self.assertEqual(ctx.error, "test error")
        self.assertEqual(ctx.error_code, "E42")
        self.assertEqual(ctx.exception_type, "ValueError")
        self.assertEqual(ctx.input_summary, "10 items")
        self.assertIsNotNone(ctx.stack_trace)
        self.assertIsNotNone(ctx.timestamp)
        self.assertEqual(ctx.additional_info["custom_key"], "custom_value")

    def test_capture_with_error_message_only(self):
        ctx = ErrorContext.capture(
            operation="Test",
            error_message="manual error"
        )
        self.assertEqual(ctx.error, "manual error")
        self.assertIsNone(ctx.exception_type)
        self.assertIsNone(ctx.stack_trace)

    def test_capture_no_exception_no_message(self):
        ctx = ErrorContext.capture(operation="Test")
        self.assertEqual(ctx.error, "Unknown error")

    def test_capture_no_stack_trace(self):
        try:
            raise ValueError("x")
        except ValueError as e:
            ctx = ErrorContext.capture(
                operation="Test",
                exception=e,
                include_stack_trace=False,
            )
        self.assertIsNone(ctx.stack_trace)

    # --- user_message ---
    def test_user_message_basic(self):
        ctx = ErrorContext(operation="Saving", error="disk full")
        self.assertEqual(ctx.user_message, "Saving failed: disk full")

    def test_user_message_cleans_error_prefix(self):
        ctx = ErrorContext(operation="Loading", error="Error: file not found")
        self.assertIn("Loading failed", ctx.user_message)
        self.assertNotIn("Error:", ctx.user_message)

    def test_user_message_cleans_exception_prefix(self):
        ctx = ErrorContext(operation="Loading", error="Exception: something")
        self.assertNotIn("Exception:", ctx.user_message)

    def test_user_message_no_error(self):
        ctx = ErrorContext(operation="Op", error="")
        self.assertEqual(ctx.user_message, "Op failed")

    # --- to_log_string ---
    def test_to_log_string_basic(self):
        ctx = ErrorContext(
            operation="TestOp",
            error="err msg",
            error_code="E1",
            exception_type="ValueError",
            input_summary="short input",
            timestamp="2026-01-01T00:00:00",
            additional_info={"key": "val"},
        )
        log_str = ctx.to_log_string()
        self.assertIn("Operation: TestOp", log_str)
        self.assertIn("Error: err msg", log_str)
        self.assertIn("Error Code: E1", log_str)
        self.assertIn("Exception Type: ValueError", log_str)
        self.assertIn("Input: short input", log_str)
        self.assertIn("key: val", log_str)
        self.assertIn("Timestamp:", log_str)

    def test_to_log_string_minimal(self):
        ctx = ErrorContext(operation="Op", error="e")
        log_str = ctx.to_log_string()
        self.assertIn("Operation: Op", log_str)
        self.assertNotIn("Error Code:", log_str)
        self.assertNotIn("Exception Type:", log_str)

    # --- to_dict ---
    def test_to_dict(self):
        ctx = ErrorContext(
            operation="Op",
            error="e",
            error_code="E1",
            exception_type="ValueError",
            input_summary="data",
            timestamp="2026-01-01",
            additional_info={"k": "v"},
            stack_trace="traceback...",
        )
        d = ctx.to_dict()
        self.assertEqual(d["operation"], "Op")
        self.assertEqual(d["error"], "e")
        self.assertEqual(d["error_code"], "E1")
        self.assertEqual(d["exception_type"], "ValueError")
        self.assertEqual(d["input_summary"], "data")
        self.assertEqual(d["timestamp"], "2026-01-01")
        self.assertEqual(d["additional_info"], {"k": "v"})
        # Stack trace should NOT be in dict (security)
        self.assertNotIn("stack_trace", d)

    # --- log ---
    @patch("utils.error_handling.logger")
    def test_log_method(self, mock_logger):
        ctx = ErrorContext(
            operation="Op",
            error="e",
            stack_trace="trace lines here",
        )
        ctx.log(level=logging.WARNING, include_trace=True)

        mock_logger.log.assert_called_once()
        self.assertEqual(mock_logger.log.call_args[0][0], logging.WARNING)
        mock_logger.debug.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_log_method_no_trace(self, mock_logger):
        ctx = ErrorContext(operation="Op", error="e", stack_trace="trace")
        ctx.log(include_trace=False)

        mock_logger.log.assert_called_once()
        mock_logger.debug.assert_not_called()

    @patch("utils.error_handling.logger")
    def test_log_method_no_stack_trace_available(self, mock_logger):
        ctx = ErrorContext(operation="Op", error="e")
        ctx.log(include_trace=True)

        mock_logger.log.assert_called_once()
        mock_logger.debug.assert_not_called()


# ---------------------------------------------------------------------------
# safe_ui_update
# ---------------------------------------------------------------------------

class TestSafeUIUpdate(unittest.TestCase):

    def test_schedules_callback(self):
        app = Mock()
        cb = Mock()
        result = safe_ui_update(app, cb, delay_ms=10)

        self.assertTrue(result)
        app.after.assert_called_once()
        self.assertEqual(app.after.call_args[0][0], 10)

    def test_app_none_returns_false(self):
        result = safe_ui_update(None, lambda: None)
        self.assertFalse(result)

    def test_attribute_error_returns_false(self):
        app = object()  # no after() method
        result = safe_ui_update(app, lambda: None)
        self.assertFalse(result)

    @patch("utils.error_handling.logger")
    def test_tclerror_on_after_returns_false(self, mock_logger):
        import tkinter as tk
        app = Mock()
        app.after.side_effect = tk.TclError("destroyed")
        result = safe_ui_update(app, lambda: None)
        self.assertFalse(result)

    @patch("utils.error_handling.logger")
    def test_runtime_error_main_thread(self, mock_logger):
        app = Mock()
        app.after.side_effect = RuntimeError("main thread is not in main loop")
        result = safe_ui_update(app, lambda: None)
        self.assertFalse(result)

    @patch("utils.error_handling.logger")
    def test_runtime_error_other(self, mock_logger):
        app = Mock()
        app.after.side_effect = RuntimeError("some other error")
        result = safe_ui_update(app, lambda: None)
        self.assertFalse(result)

    def test_safe_callback_catches_tclerror_destroyed(self):
        """The inner safe_callback should catch TclError for destroyed widgets."""
        import tkinter as tk

        app = Mock()
        captured_cb = None

        def capture_after(ms, fn):
            nonlocal captured_cb
            captured_cb = fn
        app.after = capture_after

        def bad_callback():
            raise tk.TclError("invalid command name")

        safe_ui_update(app, bad_callback)
        # Execute the captured callback - should not raise
        captured_cb()

    @patch("utils.error_handling.logger")
    def test_safe_callback_calls_error_handler_on_tclerror(self, mock_logger):
        """Non-standard TclError should call error_handler."""
        import tkinter as tk

        app = Mock()
        captured_cb = None

        def capture_after(ms, fn):
            nonlocal captured_cb
            captured_cb = fn
        app.after = capture_after

        error_handler = Mock()

        def bad_callback():
            raise tk.TclError("something unusual")

        safe_ui_update(app, bad_callback, error_handler=error_handler)
        captured_cb()
        error_handler.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_safe_callback_calls_error_handler_on_generic_exception(self, mock_logger):
        """Generic exceptions in callback should call error_handler."""
        app = Mock()
        captured_cb = None

        def capture_after(ms, fn):
            nonlocal captured_cb
            captured_cb = fn
        app.after = capture_after

        error_handler = Mock()

        def bad_callback():
            raise RuntimeError("whoops")

        safe_ui_update(app, bad_callback, error_handler=error_handler)
        captured_cb()
        error_handler.assert_called_once()

    @patch("utils.error_handling.logger")
    def test_safe_callback_tclerror_application_destroyed(self, mock_logger):
        """TclError with 'application has been destroyed' should be debug-logged."""
        import tkinter as tk

        app = Mock()
        captured_cb = None

        def capture_after(ms, fn):
            nonlocal captured_cb
            captured_cb = fn
        app.after = capture_after

        def bad_callback():
            raise tk.TclError("application has been destroyed")

        safe_ui_update(app, bad_callback)
        captured_cb()
        # Should have been logged at debug level, no warning
        mock_logger.debug.assert_called()


# ---------------------------------------------------------------------------
# SafeUIUpdater
# ---------------------------------------------------------------------------

class TestSafeUIUpdater(unittest.TestCase):

    def test_update_success(self):
        app = Mock()
        updater = SafeUIUpdater(app)
        result = updater.update(lambda: None)

        self.assertTrue(result)
        self.assertEqual(updater.stats["scheduled"], 1)
        self.assertEqual(updater.stats["failed"], 0)

    def test_update_app_garbage_collected(self):
        """If app is garbage collected, update returns False."""
        updater = SafeUIUpdater(None)
        result = updater.update(lambda: None)

        self.assertFalse(result)
        self.assertEqual(updater.stats["failed"], 1)

    def test_update_failed(self):
        """If safe_ui_update returns False, count as failed."""
        app = Mock()
        app.after.side_effect = AttributeError("no after")
        updater = SafeUIUpdater(app)

        with patch("utils.error_handling.safe_ui_update", return_value=False):
            result = updater.update(lambda: None)

        self.assertFalse(result)
        self.assertEqual(updater.stats["failed"], 1)

    def test_app_property_returns_none_for_none(self):
        updater = SafeUIUpdater(None)
        self.assertIsNone(updater.app)

    def test_app_property_returns_app(self):
        app = Mock()
        updater = SafeUIUpdater(app)
        self.assertIs(updater.app, app)

    def test_error_handler_stored(self):
        handler = Mock()
        updater = SafeUIUpdater(Mock(), error_handler=handler)
        self.assertIs(updater._error_handler, handler)

    def test_stats_accumulate(self):
        app = Mock()
        updater = SafeUIUpdater(app)
        updater.update(lambda: None)
        updater.update(lambda: None)
        self.assertEqual(updater.stats["scheduled"], 2)


# ---------------------------------------------------------------------------
# run_in_thread
# ---------------------------------------------------------------------------

class TestRunInThread(unittest.TestCase):

    @patch("utils.error_handling.logger")
    def test_basic_execution(self, mock_logger):
        result_holder = []

        def task():
            result_holder.append(42)

        t = run_in_thread(task)
        t.join(timeout=5)

        self.assertEqual(result_holder, [42])
        self.assertTrue(t.daemon)

    @patch("utils.error_handling.logger")
    def test_callback_called_without_app(self, mock_logger):
        results = []

        def task():
            return "hello"

        def on_done(result):
            results.append(result)

        t = run_in_thread(task, callback=on_done)
        t.join(timeout=5)

        self.assertEqual(results, ["hello"])

    @patch("utils.error_handling.logger")
    def test_error_callback_called_without_app(self, mock_logger):
        errors = []

        def task():
            raise RuntimeError("boom")

        def on_error(e):
            errors.append(str(e))

        t = run_in_thread(task, error_callback=on_error)
        t.join(timeout=5)

        self.assertEqual(len(errors), 1)
        self.assertIn("boom", errors[0])

    @patch("utils.error_handling.logger")
    def test_callback_with_app_uses_safe_ui_update(self, mock_logger):
        app = Mock()
        results = []

        # Make app.after execute callback immediately
        def mock_after(ms, fn):
            fn()
        app.after = mock_after

        def task():
            return "world"

        def on_done(result):
            results.append(result)

        t = run_in_thread(task, callback=on_done, app=app)
        t.join(timeout=5)

        self.assertEqual(results, ["world"])

    @patch("utils.error_handling.logger")
    def test_error_callback_with_app(self, mock_logger):
        app = Mock()
        errors = []

        def mock_after(ms, fn):
            fn()
        app.after = mock_after

        def task():
            raise ValueError("fail")

        def on_error(e):
            errors.append(str(e))

        t = run_in_thread(task, error_callback=on_error, app=app)
        t.join(timeout=5)

        self.assertEqual(len(errors), 1)
        self.assertIn("fail", errors[0])

    @patch("utils.error_handling.logger")
    def test_non_daemon_thread(self, mock_logger):
        t = run_in_thread(lambda: None, daemon=False)
        t.join(timeout=5)
        self.assertFalse(t.daemon)

    @patch("utils.error_handling.logger")
    def test_callback_exception_triggers_error_callback(self, mock_logger):
        """If the callback itself raises, the error_callback should be called."""
        errors = []

        def task():
            return "ok"

        def bad_callback(result):
            raise RuntimeError("callback failed")

        def on_error(e):
            errors.append(str(e))

        t = run_in_thread(task, callback=bad_callback, error_callback=on_error)
        t.join(timeout=5)

        self.assertEqual(len(errors), 1)
        self.assertIn("callback failed", errors[0])

    @patch("utils.error_handling.logger")
    def test_no_callbacks(self, mock_logger):
        """Should run fine with no callbacks."""
        executed = []

        def task():
            executed.append(True)

        t = run_in_thread(task)
        t.join(timeout=5)
        self.assertTrue(executed)


# ---------------------------------------------------------------------------
# Edge cases and integration-like tests
# ---------------------------------------------------------------------------

class TestEdgeCases(unittest.TestCase):

    def test_operation_result_generic_type(self):
        """OperationResult should work as generic with various types."""
        r_int = OperationResult.success(42)
        r_str = OperationResult.success("hello")
        r_list = OperationResult.success([1, 2, 3])
        r_none = OperationResult.success(None)

        self.assertEqual(r_int.value, 42)
        self.assertEqual(r_str.value, "hello")
        self.assertEqual(r_list.value, [1, 2, 3])
        self.assertIsNone(r_none.value)

    @patch("utils.error_handling.logger")
    def test_handle_errors_with_args_and_kwargs(self, mock_logger):
        @handle_errors(ErrorSeverity.ERROR)
        def add(a, b, c=0):
            return OperationResult.success(a + b + c)

        r = add(1, 2, c=3)
        self.assertTrue(r.success)
        self.assertEqual(r.value, 6)

    def test_error_context_capture_timestamp_format(self):
        ctx = ErrorContext.capture(operation="Test")
        self.assertIsNotNone(ctx.timestamp)
        # Should be ISO format
        self.assertIn("T", ctx.timestamp)

    @patch("utils.error_handling.logger")
    def test_sanitize_error_type_matching_is_case_insensitive(self, mock_logger):
        """Error type matching should be case-insensitive."""
        class apiError(Exception):
            pass
        result = sanitize_error_for_user(apiError("x"))
        self.assertEqual(result, "The AI service encountered an error. Please try again.")


if __name__ == "__main__":
    unittest.main()
