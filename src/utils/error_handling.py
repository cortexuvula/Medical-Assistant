"""
Standardized error handling utilities for Medical Assistant.

This module provides consistent error handling patterns across the application:

1. OperationResult - Standard return type for operations that can fail
2. ErrorSeverity - Classification of error severity for handling
3. handle_errors decorator - Automatic error handling based on severity
4. UIErrorHandler - Context manager for UI operations with progress/cleanup
5. safe_execute - Wrapper for safe execution with logging

Usage Examples:

    # Using OperationResult for functions that can fail
    def process_document(content: str) -> OperationResult:
        if not content:
            return OperationResult.failure("Content cannot be empty")
        try:
            result = do_processing(content)
            return OperationResult.success(result)
        except Exception as e:
            return OperationResult.failure(str(e), exception=e)

    # Using the decorator for automatic handling
    @handle_errors(ErrorSeverity.ERROR)
    def analyze_text(text: str) -> dict:
        return {"analysis": "result"}

    # Using UIErrorHandler for UI operations
    with UIErrorHandler(app, button, "Processing"):
        result = long_running_operation()
        display_result(result)
"""

import logging
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, Union
from functools import wraps
from contextlib import contextmanager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ErrorSeverity(Enum):
    """Classification of error severity for handling decisions."""

    CRITICAL = "critical"
    """Critical errors that should raise exceptions and halt execution."""

    ERROR = "error"
    """Errors that should be reported but allow graceful recovery."""

    WARNING = "warning"
    """Warnings that should be logged but don't prevent operation."""

    INFO = "info"
    """Informational issues that are silently logged."""


@dataclass
class OperationResult(Generic[T]):
    """
    Standard result type for operations that can fail.

    This provides a consistent interface for returning either success
    with a value or failure with an error message, replacing the
    inconsistent {"success": bool, "error": str} pattern.

    Attributes:
        success: Whether the operation succeeded
        value: The result value (only valid if success=True)
        error: Error message (only valid if success=False)
        error_code: Optional error code for programmatic handling
        exception: The original exception if one was caught
        details: Additional error details for debugging

    Example:
        result = OperationResult.success({"text": "processed"})
        if result.success:
            use_value(result.value)
        else:
            show_error(result.error)
    """

    success: bool
    value: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    exception: Optional[Exception] = None
    details: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def success(cls, value: T, **details) -> 'OperationResult[T]':
        """Create a successful result with a value."""
        return cls(success=True, value=value, details=details)

    @classmethod
    def failure(
        cls,
        error: str,
        error_code: Optional[str] = None,
        exception: Optional[Exception] = None,
        **details
    ) -> 'OperationResult[T]':
        """Create a failed result with an error message."""
        return cls(
            success=False,
            error=error,
            error_code=error_code,
            exception=exception,
            details=details
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert to dictionary for backward compatibility.

        This maintains compatibility with existing code that expects
        {"success": bool, "text": str} or {"success": bool, "error": str}
        """
        if self.success:
            result = {"success": True}
            if self.value is not None:
                if isinstance(self.value, dict):
                    result.update(self.value)
                else:
                    result["value"] = self.value
            return result
        else:
            return {
                "success": False,
                "error": self.error or "Unknown error",
                **({"error_code": self.error_code} if self.error_code else {})
            }

    def __bool__(self) -> bool:
        """Allow using result in boolean context."""
        return self.success

    def unwrap(self) -> T:
        """
        Get the value or raise an exception if failed.

        Raises:
            ValueError: If the operation failed
        """
        if not self.success:
            if self.exception:
                raise self.exception
            raise ValueError(self.error or "Operation failed")
        return self.value

    def unwrap_or(self, default: T) -> T:
        """Get the value or return a default if failed."""
        return self.value if self.success else default

    def map(self, func: Callable[[T], Any]) -> 'OperationResult':
        """Apply a function to the value if successful."""
        if self.success:
            try:
                return OperationResult.success(func(self.value))
            except Exception as e:
                return OperationResult.failure(str(e), exception=e)
        return self


def handle_errors(
    severity: ErrorSeverity = ErrorSeverity.ERROR,
    error_message: Optional[str] = None,
    log_traceback: bool = True,
    return_type: str = "result"
):
    """
    Decorator to standardize error handling based on severity.

    Args:
        severity: How to handle errors (CRITICAL raises, ERROR returns, etc.)
        error_message: Custom error message prefix
        log_traceback: Whether to log full traceback
        return_type: What to return on error - "result", "none", "dict", or "bool"

    Example:
        @handle_errors(ErrorSeverity.ERROR)
        def process_data(data: str) -> OperationResult:
            # If this raises, it returns OperationResult.failure()
            return OperationResult.success(parse(data))

        @handle_errors(ErrorSeverity.WARNING, return_type="none")
        def optional_enhancement(data: str) -> Optional[str]:
            # If this raises, it logs warning and returns None
            return enhance(data)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Build error message
                msg_prefix = error_message or f"Error in {func.__name__}"
                full_message = f"{msg_prefix}: {str(e)}"

                # Log based on severity
                if severity == ErrorSeverity.CRITICAL:
                    logger.error(full_message, exc_info=log_traceback)
                    raise
                elif severity == ErrorSeverity.ERROR:
                    logger.error(full_message, exc_info=log_traceback)
                elif severity == ErrorSeverity.WARNING:
                    logger.warning(full_message, exc_info=log_traceback)
                else:  # INFO
                    logger.info(full_message)

                # Return based on return_type
                if return_type == "result":
                    return OperationResult.failure(full_message, exception=e)
                elif return_type == "dict":
                    return {"success": False, "error": full_message}
                elif return_type == "bool":
                    return False
                else:  # "none"
                    return None

        return wrapper
    return decorator


@contextmanager
def ui_error_context(
    status_manager,
    button=None,
    progress_bar=None,
    operation_name: str = "Operation",
    show_success: bool = True
):
    """
    Context manager for UI operations with automatic progress and error handling.

    Args:
        status_manager: The app's status manager for showing messages
        button: Optional button to disable during operation
        progress_bar: Optional progress bar to show/hide
        operation_name: Name of operation for status messages
        show_success: Whether to show success message on completion

    Example:
        with ui_error_context(app.status_manager, app.generate_btn,
                             app.progress_bar, "Generating SOAP note"):
            result = generate_soap_note(content)
            app.soap_text.insert("1.0", result)
    """
    import tkinter as tk

    # Store original button state
    original_button_state = None
    if button:
        try:
            original_button_state = button.cget('state')
            button.config(state=tk.DISABLED)
        except tk.TclError:
            pass

    # Show progress
    if progress_bar:
        try:
            progress_bar.pack(side=tk.RIGHT, padx=10)
            progress_bar.start()
        except tk.TclError:
            pass

    status_manager.progress(f"{operation_name}...")

    try:
        yield
        if show_success:
            status_manager.success(f"{operation_name} completed")
    except Exception as e:
        error_msg = f"{operation_name} failed: {str(e)}"
        logger.error(error_msg, exc_info=True)
        status_manager.error(error_msg)
        raise
    finally:
        # Restore button state
        if button and original_button_state is not None:
            try:
                button.config(state=original_button_state)
            except tk.TclError:
                pass

        # Hide progress bar
        if progress_bar:
            try:
                progress_bar.stop()
                progress_bar.pack_forget()
            except tk.TclError:
                pass


class AsyncUIErrorHandler:
    """
    Handler for async UI operations with thread-safe error handling.

    This is used for operations that run in a background thread but
    need to update the UI and handle errors on the main thread.

    Example:
        handler = AsyncUIErrorHandler(app, button, progress_bar, "Processing")
        handler.start()

        def background_task():
            try:
                result = long_operation()
                handler.complete(lambda: update_ui(result))
            except Exception as e:
                handler.fail(e)

        executor.submit(background_task)
    """

    def __init__(
        self,
        app,
        button=None,
        progress_bar=None,
        operation_name: str = "Operation"
    ):
        self.app = app
        self.button = button
        self.progress_bar = progress_bar
        self.operation_name = operation_name
        self._started = False

    def start(self):
        """Start the operation - disable UI and show progress."""
        import tkinter as tk

        if self._started:
            return

        self._started = True

        def _start_ui():
            try:
                if self.button:
                    self.button.config(state=tk.DISABLED)
                if self.progress_bar:
                    self.progress_bar.pack(side=tk.RIGHT, padx=10)
                    self.progress_bar.start()
                if hasattr(self.app, 'status_manager'):
                    self.app.status_manager.progress(f"{self.operation_name}...")
            except tk.TclError:
                pass  # Window may be closing

        self.app.after(0, _start_ui)

    def complete(self, callback: Callable = None, success_message: str = None):
        """Complete the operation successfully."""
        import tkinter as tk

        def _complete_ui():
            try:
                self._restore_ui()
                if hasattr(self.app, 'status_manager'):
                    msg = success_message or f"{self.operation_name} completed"
                    self.app.status_manager.success(msg)
                if callback:
                    callback()
            except tk.TclError:
                pass

        self.app.after(0, _complete_ui)

    def fail(self, error: Union[str, Exception], callback: Callable = None):
        """Fail the operation with an error."""
        import tkinter as tk

        error_msg = str(error) if isinstance(error, Exception) else error
        full_msg = f"{self.operation_name} failed: {error_msg}"

        if isinstance(error, Exception):
            logger.error(full_msg, exc_info=True)
        else:
            logger.error(full_msg)

        def _fail_ui():
            try:
                self._restore_ui()
                if hasattr(self.app, 'status_manager'):
                    self.app.status_manager.error(full_msg)
                if callback:
                    callback()
            except tk.TclError:
                pass

        self.app.after(0, _fail_ui)

    def _restore_ui(self):
        """Restore UI elements to their original state."""
        import tkinter as tk

        try:
            if self.button:
                self.button.config(state=tk.NORMAL)
            if self.progress_bar:
                self.progress_bar.stop()
                self.progress_bar.pack_forget()
        except tk.TclError:
            pass


def safe_execute(
    func: Callable,
    *args,
    error_handler: Callable[[Exception], None] = None,
    default: Any = None,
    log_errors: bool = True,
    **kwargs
) -> Any:
    """
    Execute a function safely with error handling.

    Args:
        func: Function to execute
        *args: Positional arguments to pass to func
        error_handler: Optional callback for errors
        default: Value to return on error
        log_errors: Whether to log errors
        **kwargs: Keyword arguments to pass to func

    Returns:
        Function result or default on error

    Example:
        result = safe_execute(parse_json, data, default={})
    """
    try:
        return func(*args, **kwargs)
    except Exception as e:
        if log_errors:
            logger.warning(f"Error in {func.__name__}: {e}")
        if error_handler:
            error_handler(e)
        return default


def format_error_for_user(error: Union[str, Exception]) -> str:
    """
    Format an error message for display to users.

    This strips technical details and provides a user-friendly message.
    """
    if isinstance(error, Exception):
        error_msg = str(error)
    else:
        error_msg = error

    # Remove common technical prefixes
    prefixes_to_strip = [
        "Error: ",
        "Exception: ",
        "Failed: ",
    ]
    for prefix in prefixes_to_strip:
        if error_msg.startswith(prefix):
            error_msg = error_msg[len(prefix):]

    # Capitalize first letter
    if error_msg:
        error_msg = error_msg[0].upper() + error_msg[1:]

    return error_msg


def log_and_raise(
    error: Exception,
    message: str = None,
    log_level: int = logging.ERROR,
    include_traceback: bool = True
):
    """
    Log an error and re-raise it.

    Useful for catch-log-reraise patterns where you want consistent logging.

    Args:
        error: The exception to log and raise
        message: Optional message prefix
        log_level: Logging level to use
        include_traceback: Whether to include traceback in log

    Example:
        try:
            risky_operation()
        except ValueError as e:
            log_and_raise(e, "Failed to process data")
    """
    full_message = f"{message}: {error}" if message else str(error)
    logger.log(log_level, full_message, exc_info=include_traceback)
    raise
