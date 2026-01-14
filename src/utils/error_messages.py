"""
Error Messages - Re-export Facade

DEPRECATED: Import directly from utils.error_registry instead.

This module re-exports user-friendly error message functionality from the
consolidated error_registry for backward compatibility.
"""

from utils.error_registry import (
    ErrorMessageMapper,
    get_user_friendly_error,
    format_error_with_retry,
)

__all__ = [
    "ErrorMessageMapper",
    "get_user_friendly_error",
    "format_error_with_retry",
]
