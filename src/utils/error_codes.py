"""
Error Codes - Re-export Facade

DEPRECATED: Import directly from utils.error_registry instead.

This module re-exports error code functionality from the consolidated error_registry
for backward compatibility.
"""

from utils.error_registry import (
    ERROR_CODES,
    get_error_message,
    show_error_dialog,
    format_api_error,
)

__all__ = [
    "ERROR_CODES",
    "get_error_message",
    "show_error_dialog",
    "format_api_error",
]
