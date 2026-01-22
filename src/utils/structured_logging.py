"""
Structured Logging Utilities

This module provides structured logging capabilities for the Medical Assistant
application. Structured logging adds context to log messages in a consistent
format, making logs easier to search, filter, and analyze.

Features:
- Key-value context in log messages
- JSON output format option
- Performance timing helpers
- Request/operation tracking
- Sanitization of sensitive data

Usage:
    from utils.structured_logging import StructuredLogger, get_logger, timed

    # Get a structured logger
    logger = get_logger(__name__)

    # Log with context
    logger.info("Processing recording", recording_id=123, patient="John Doe")

    # Output: 2024-01-15 10:30:45 - INFO - Processing recording | recording_id=123 patient="John Doe"

    # Use timing decorator
    @timed("processing")
    def process_data(data):
        return transform(data)
"""

import logging
import json
import time
import os
import functools
import threading
from typing import Any, Dict, Optional, Callable, TypeVar
from datetime import datetime
from contextlib import contextmanager

T = TypeVar('T')

# Log level mapping for string-to-int conversion
_LOG_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}


def _get_configured_log_level(level_key: str = "level") -> int:
    """Get log level from environment or settings.

    Priority:
    1. Environment variable MEDICAL_ASSISTANT_LOG_LEVEL
    2. Settings file (logging.{level_key})
    3. Default to INFO

    Args:
        level_key: Which setting to read (level, file_level, console_level)

    Returns:
        Logging level as int
    """
    # Environment variable takes precedence
    env_level = os.environ.get("MEDICAL_ASSISTANT_LOG_LEVEL", "").upper()
    if env_level in _LOG_LEVEL_MAP:
        return _LOG_LEVEL_MAP[env_level]

    # Try settings file
    try:
        # Import here to avoid circular imports (settings imports structured_logging)
        # Use a direct file read to avoid the circular dependency
        import json as json_module
        from pathlib import Path

        # Try to find settings file
        settings_paths = [
            Path.home() / "AppData" / "Local" / "MedicalAssistant" / "settings.json",
            Path.home() / ".config" / "MedicalAssistant" / "settings.json",
            Path.home() / "Library" / "Application Support" / "MedicalAssistant" / "settings.json",
        ]

        for settings_path in settings_paths:
            if settings_path.exists():
                with open(settings_path, "r", encoding="utf-8") as f:
                    settings = json_module.load(f)
                    level_str = settings.get("logging", {}).get(level_key, "INFO").upper()
                    return _LOG_LEVEL_MAP.get(level_str, logging.INFO)
    except Exception:
        pass  # Fall through to default

    return logging.INFO


def get_log_level_from_string(level_str: str) -> int:
    """Convert a log level string to logging level int.

    Args:
        level_str: Log level name (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Logging level constant
    """
    return _LOG_LEVEL_MAP.get(level_str.upper(), logging.INFO)

# Sensitive field names that should be redacted
SENSITIVE_FIELDS = frozenset([
    'api_key', 'apikey', 'password', 'secret', 'token', 'auth',
    'authorization', 'credential', 'private_key', 'access_token',
    'refresh_token', 'ssn', 'social_security', 'credit_card', 'cc_number'
])

# Maximum length for string values in logs
MAX_VALUE_LENGTH = 500


def _sanitize_value(key: str, value: Any) -> Any:
    """Sanitize a value for logging.

    Args:
        key: The key/field name
        value: The value to sanitize

    Returns:
        Sanitized value safe for logging
    """
    # Redact sensitive fields
    if key.lower() in SENSITIVE_FIELDS:
        return "[REDACTED]"

    # Truncate long strings
    if isinstance(value, str) and len(value) > MAX_VALUE_LENGTH:
        return value[:MAX_VALUE_LENGTH] + "...[truncated]"

    # Redact sensitive-looking values
    if isinstance(value, str):
        lower_value = value.lower()
        if any(pattern in lower_value for pattern in ['api_key=', 'password=', 'token=']):
            return "[REDACTED]"

    return value


def _format_context(context: Dict[str, Any]) -> str:
    """Format context dictionary for log output.

    Args:
        context: Dictionary of context key-value pairs

    Returns:
        Formatted string for log message
    """
    if not context:
        return ""

    parts = []
    for key, value in context.items():
        sanitized = _sanitize_value(key, value)

        # Format the value
        if isinstance(sanitized, str):
            if ' ' in sanitized or '"' in sanitized:
                parts.append(f'{key}="{sanitized}"')
            else:
                parts.append(f'{key}={sanitized}')
        elif isinstance(sanitized, (list, dict)):
            parts.append(f'{key}={json.dumps(sanitized)}')
        else:
            parts.append(f'{key}={sanitized}')

    return " | " + " ".join(parts)


class StructuredLogger:
    """A logger wrapper that supports structured context in log messages.

    This class wraps a standard Python logger and adds support for
    key-value context in log messages.

    Attributes:
        name: The logger name
        logger: The underlying Python logger
    """

    def __init__(self, name: str, level: int = logging.DEBUG):
        """Initialize the structured logger.

        Args:
            name: Logger name (usually __name__ of the module)
            level: Logging level (default: DEBUG)
        """
        self.name = name
        self.logger = logging.getLogger(name)
        self._context: Dict[str, Any] = {}
        self._context_lock = threading.Lock()

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal logging method.

        Args:
            level: Logging level
            message: Log message
            **kwargs: Context key-value pairs
        """
        # Merge instance context with call-specific context
        with self._context_lock:
            full_context = {**self._context, **kwargs}

        # Format the message with context
        context_str = _format_context(full_context)
        full_message = f"{message}{context_str}"

        self.logger.log(level, full_message)

    def debug(self, message: str, **kwargs) -> None:
        """Log a debug message with context."""
        self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs) -> None:
        """Log an info message with context."""
        self._log(logging.INFO, message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log a warning message with context."""
        self._log(logging.WARNING, message, **kwargs)

    def error(self, message: str, exc_info: bool = False, **kwargs) -> None:
        """Log an error message with context.

        Args:
            message: Error message
            exc_info: If True, include exception info
            **kwargs: Context key-value pairs
        """
        with self._context_lock:
            full_context = {**self._context, **kwargs}

        context_str = _format_context(full_context)
        full_message = f"{message}{context_str}"

        self.logger.error(full_message, exc_info=exc_info)

    def exception(self, message: str, **kwargs) -> None:
        """Log an exception with context.

        Automatically includes exception traceback.
        """
        self.error(message, exc_info=True, **kwargs)

    def critical(self, message: str, **kwargs) -> None:
        """Log a critical message with context."""
        self._log(logging.CRITICAL, message, **kwargs)

    def log(self, level: int, message: str, **kwargs) -> None:
        """Log a message at the specified level with context.

        Args:
            level: Logging level (e.g., logging.ERROR, logging.INFO)
            message: Log message
            **kwargs: Context key-value pairs
        """
        self._log(level, message, **kwargs)

    def isEnabledFor(self, level: int) -> bool:
        """Check if the logger is enabled for the specified level.

        Args:
            level: Logging level to check

        Returns:
            True if the logger would process a message at this level
        """
        return self.logger.isEnabledFor(level)

    def set_context(self, **kwargs) -> None:
        """Set persistent context that will be included in all log messages.

        Args:
            **kwargs: Context key-value pairs to persist
        """
        with self._context_lock:
            self._context.update(kwargs)

    def clear_context(self) -> None:
        """Clear all persistent context."""
        with self._context_lock:
            self._context.clear()

    @contextmanager
    def context(self, **kwargs):
        """Context manager for temporary log context.

        Args:
            **kwargs: Context key-value pairs

        Example:
            with logger.context(request_id="abc123"):
                logger.info("Processing request")
                # All logs in this block include request_id
        """
        with self._context_lock:
            old_context = self._context.copy()
            self._context.update(kwargs)

        try:
            yield self
        finally:
            with self._context_lock:
                self._context = old_context


class JsonStructuredLogger(StructuredLogger):
    """A structured logger that outputs JSON-formatted logs.

    Useful for log aggregation systems that parse JSON logs.
    """

    def _log(self, level: int, message: str, **kwargs) -> None:
        """Internal logging method with JSON output.

        Args:
            level: Logging level
            message: Log message
            **kwargs: Context key-value pairs
        """
        with self._context_lock:
            full_context = {**self._context, **kwargs}

        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": logging.getLevelName(level),
            "logger": self.name,
            "message": message,
            **{k: _sanitize_value(k, v) for k, v in full_context.items()}
        }

        self.logger.log(level, json.dumps(log_entry))


# Logger cache
_loggers: Dict[str, StructuredLogger] = {}
_loggers_lock = threading.Lock()


def get_logger(name: str, json_format: bool = False) -> StructuredLogger:
    """Get or create a structured logger.

    Args:
        name: Logger name (usually __name__)
        json_format: If True, use JSON output format

    Returns:
        StructuredLogger instance
    """
    with _loggers_lock:
        if name not in _loggers:
            if json_format:
                _loggers[name] = JsonStructuredLogger(name)
            else:
                _loggers[name] = StructuredLogger(name)
        return _loggers[name]


def timed(operation_name: str = None, logger: StructuredLogger = None):
    """Decorator to log function execution time.

    Args:
        operation_name: Name for the operation (defaults to function name)
        logger: Logger to use (creates one if not provided)

    Returns:
        Decorator function

    Example:
        @timed("data_processing")
        def process_large_file(filepath):
            # Processing code
            pass
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> T:
            nonlocal logger
            if logger is None:
                logger = get_logger(func.__module__)

            op_name = operation_name or func.__name__
            start_time = time.perf_counter()

            logger.debug(f"Starting {op_name}")

            try:
                result = func(*args, **kwargs)
                elapsed = time.perf_counter() - start_time
                logger.info(
                    f"Completed {op_name}",
                    duration_ms=round(elapsed * 1000, 2),
                    status="success"
                )
                return result

            except Exception as e:
                elapsed = time.perf_counter() - start_time
                logger.error(
                    f"Failed {op_name}",
                    duration_ms=round(elapsed * 1000, 2),
                    status="error",
                    error=str(e)
                )
                raise

        return wrapper
    return decorator


@contextmanager
def log_operation(
    logger: StructuredLogger,
    operation_name: str,
    **context
):
    """Context manager for logging an operation with timing.

    Args:
        logger: Logger to use
        operation_name: Name of the operation
        **context: Additional context to include

    Example:
        with log_operation(logger, "database_query", table="recordings"):
            result = db.query(...)
    """
    start_time = time.perf_counter()
    logger.info(f"Starting {operation_name}", **context)

    try:
        yield
        elapsed = time.perf_counter() - start_time
        logger.info(
            f"Completed {operation_name}",
            duration_ms=round(elapsed * 1000, 2),
            status="success",
            **context
        )
    except Exception as e:
        elapsed = time.perf_counter() - start_time
        logger.error(
            f"Failed {operation_name}",
            duration_ms=round(elapsed * 1000, 2),
            status="error",
            error=str(e),
            **context
        )
        raise


class RequestLogger:
    """Logger for tracking requests/operations with correlation IDs.

    Useful for tracking operations across multiple components.

    Example:
        req_logger = RequestLogger(logger)
        with req_logger.request("process_recording", recording_id=123):
            # All logs in this block include the request_id
            transcribe()
            generate_soap()
    """

    def __init__(self, logger: StructuredLogger):
        """Initialize the request logger.

        Args:
            logger: Base structured logger to use
        """
        self.logger = logger
        self._request_counter = 0
        self._counter_lock = threading.Lock()

    def _generate_request_id(self) -> str:
        """Generate a unique request ID."""
        with self._counter_lock:
            self._request_counter += 1
            timestamp = int(time.time() * 1000)
            return f"{timestamp}-{self._request_counter}"

    @contextmanager
    def request(self, operation_name: str, request_id: str = None, **context):
        """Context manager for a request with correlation ID.

        Args:
            operation_name: Name of the operation
            request_id: Optional request ID (generated if not provided)
            **context: Additional context
        """
        if request_id is None:
            request_id = self._generate_request_id()

        full_context = {"request_id": request_id, **context}

        with log_operation(self.logger, operation_name, **full_context):
            with self.logger.context(**full_context):
                yield request_id


def configure_logging(
    level: int = None,
    format_string: str = None,
    json_format: bool = False
) -> None:
    """Configure the root logger for structured logging.

    Args:
        level: Logging level (if None, reads from settings/environment)
        format_string: Custom format string (ignored if json_format=True)
        json_format: If True, configure for JSON output
    """
    # Get level from settings/environment if not specified
    if level is None:
        level = _get_configured_log_level()

    if format_string is None:
        format_string = "%(asctime)s - %(levelname)s - %(name)s - %(message)s"

    logging.basicConfig(
        level=level,
        format=format_string,
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if json_format:
        # For JSON format, use a minimal formatter since JSON handles structure
        for handler in logging.root.handlers:
            handler.setFormatter(logging.Formatter("%(message)s"))


# Backward compatibility alias
setup_logging = configure_logging
