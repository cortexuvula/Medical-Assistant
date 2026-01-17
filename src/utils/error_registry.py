"""
Error Registry Module

Unified error code definitions, user-friendly message mapping, and error display utilities.
This module consolidates error handling infrastructure for the Medical Assistant application.

Merged from:
- error_codes.py (error code definitions and formatting)
- error_messages.py (user-friendly message mapping)
"""

from typing import Dict, Optional, Tuple

from utils.structured_logging import get_logger

logger = get_logger(__name__)

# =============================================================================
# ERROR CODE DEFINITIONS
# =============================================================================

# Error code format: CATEGORY_SPECIFIC_ERROR
# Categories: API, CONN (Connection), AUTH (Authentication), CFG (Configuration), SYS (System)

ERROR_CODES: Dict[str, Tuple[str, str]] = {
    # API Errors
    "API_KEY_MISSING": (
        "API key not configured",
        "Please add your API key in Settings → API Keys or set it in the .env file."
    ),
    "API_KEY_INVALID": (
        "Invalid API key",
        "The API key appears to be invalid. Please check your API key in Settings → API Keys."
    ),
    "API_RATE_LIMIT": (
        "API rate limit exceeded",
        "You've exceeded the API rate limit. Please wait a moment before trying again."
    ),
    "API_QUOTA_EXCEEDED": (
        "API quota exceeded",
        "You've exceeded your API quota. Please check your account billing or upgrade your plan."
    ),
    "API_MODEL_NOT_FOUND": (
        "Model not available",
        "The requested model is not available. Try selecting a different model in Settings."
    ),

    # Connection Errors
    "CONN_TIMEOUT": (
        "Connection timeout",
        "The request timed out. This might be due to slow internet or an overloaded model. Try again or use a smaller model."
    ),
    "CONN_NO_INTERNET": (
        "No internet connection",
        "Please check your internet connection and try again."
    ),
    "CONN_SERVICE_DOWN": (
        "Service unavailable",
        "The service is currently unavailable. Please try again later or check the service status."
    ),
    "CONN_OLLAMA_NOT_RUNNING": (
        "Ollama not running",
        "Ollama service is not running. Please start Ollama with 'ollama serve' in your terminal."
    ),

    # Configuration Errors
    "CFG_MODEL_NOT_INSTALLED": (
        "Model not installed",
        "The model is not installed locally. Run 'ollama pull {model_name}' to install it."
    ),
    "CFG_INVALID_SETTINGS": (
        "Invalid settings",
        "Some settings are invalid. Please check your configuration in Settings."
    ),

    # System Errors
    "SYS_AUDIO_DEVICE": (
        "Audio device error",
        "Could not access the audio device. Please check your microphone permissions and settings."
    ),
    "SYS_FILE_ACCESS": (
        "File access error",
        "Could not access the file. Please check file permissions and try again."
    ),
    "SYS_MEMORY": (
        "Memory error",
        "Not enough memory to complete the operation. Try closing other applications."
    ),

    # Generic fallback
    "UNKNOWN_ERROR": (
        "Unexpected error occurred",
        "An unexpected error occurred. Please try again or contact support if the issue persists."
    )
}


# =============================================================================
# ERROR CODE FUNCTIONS
# =============================================================================

def get_error_message(error_code: str, details: str = "", model_name: str = "") -> Tuple[str, str]:
    """Get formatted error title and message with troubleshooting hints.

    Args:
        error_code: The error code from ERROR_CODES
        details: Additional error details
        model_name: Model name for model-specific errors

    Returns:
        Tuple of (title, message) for the error dialog
    """
    if error_code not in ERROR_CODES:
        error_code = "UNKNOWN_ERROR"

    title, hint = ERROR_CODES[error_code]

    # Customize message based on error code
    if error_code == "CFG_MODEL_NOT_INSTALLED" and model_name:
        hint = hint.format(model_name=model_name)

    # Build full message
    message_parts = [hint]

    if details:
        message_parts.append(f"\nDetails: {details}")

    if error_code != "UNKNOWN_ERROR":
        message_parts.append(f"\nError code: {error_code}")

    return title, "\n".join(message_parts)


def show_error_dialog(parent, error_code: str, details: str = "", model_name: str = "") -> None:
    """Show an error dialog with troubleshooting hints.

    Args:
        parent: Parent window for the dialog
        error_code: The error code from ERROR_CODES
        details: Additional error details
        model_name: Model name for model-specific errors
    """
    from tkinter import messagebox

    title, message = get_error_message(error_code, details, model_name)
    messagebox.showerror(title, message, parent=parent)


def format_api_error(provider: str, error: Exception) -> Tuple[str, str]:
    """Format API-specific errors based on the provider and error type.

    Args:
        provider: The API provider (openai, anthropic, etc.)
        error: The exception that occurred

    Returns:
        Tuple of (error_code, details) for get_error_message
    """
    error_str = str(error).lower()

    # Check for common API error patterns
    if "api key" in error_str or "authentication" in error_str or "unauthorized" in error_str:
        return "API_KEY_INVALID", f"{provider.title()} API authentication failed"
    elif "rate limit" in error_str:
        return "API_RATE_LIMIT", f"{provider.title()} rate limit reached"
    elif "quota" in error_str or "insufficient_quota" in error_str:
        return "API_QUOTA_EXCEEDED", f"{provider.title()} quota exceeded"
    elif "model" in error_str and "not found" in error_str:
        return "API_MODEL_NOT_FOUND", str(error)
    elif "timeout" in error_str:
        return "CONN_TIMEOUT", f"Request to {provider.title()} timed out"
    elif "connection" in error_str or "network" in error_str:
        return "CONN_NO_INTERNET", f"Could not connect to {provider.title()}"
    else:
        return "UNKNOWN_ERROR", str(error)


# =============================================================================
# USER-FRIENDLY MESSAGE MAPPER
# =============================================================================

class ErrorMessageMapper:
    """Maps technical errors to user-friendly messages."""

    # Error category mappings
    API_ERRORS = {
        "Invalid API key": "Your API key appears to be invalid. Please check your API key in Settings.",
        "Rate limit exceeded": "API rate limit reached. Please wait a moment before trying again.",
        "Connection timeout": "Connection timed out. Please check your internet connection.",
        "SSL certificate": "Secure connection failed. Please check your network settings.",
        "API endpoint not found": "Service temporarily unavailable. Please try again later.",
        "Insufficient credits": "API credits exhausted. Please check your account balance.",
        "Model not found": "The selected AI model is not available. Please choose a different model.",
    }

    AUDIO_ERRORS = {
        "No microphone": "No microphone detected. Please connect a microphone and try again.",
        "Microphone access denied": "Microphone access denied. Please grant permission in system settings.",
        "Audio device busy": "Audio device is in use by another application. Please close other audio apps.",
        "Invalid audio format": "Audio format not supported. Please check your audio settings.",
        "Recording failed": "Failed to start recording. Please check your microphone connection.",
    }

    DATABASE_ERRORS = {
        "Database locked": "Database is busy. Please wait a moment and try again.",
        "Database corrupt": "Database error detected. Please restart the application.",
        "Disk full": "Not enough disk space. Please free up some space and try again.",
        "Permission denied": "Cannot access database. Please check file permissions.",
        "Connection failed": "Database connection failed. Please restart the application.",
    }

    FILE_ERRORS = {
        "File not found": "The requested file could not be found.",
        "Permission denied": "Cannot access file. Please check file permissions.",
        "File too large": "File is too large. Please use a smaller file.",
        "Invalid file format": "File format not supported. Please use a supported format.",
        "Disk full": "Not enough disk space to save file.",
    }

    NETWORK_ERRORS = {
        "No internet connection": "No internet connection detected. Please check your network.",
        "DNS resolution failed": "Cannot connect to server. Please check your internet connection.",
        "Proxy error": "Proxy connection failed. Please check your proxy settings.",
        "Timeout": "Request timed out. Please check your internet connection and try again.",
        "Connection refused": "Connection refused. The service may be temporarily unavailable.",
    }

    PROCESSING_ERRORS = {
        "Out of memory": "Not enough memory to complete operation. Please close other applications.",
        "Processing timeout": "Operation took too long. Please try with smaller input.",
        "Invalid input": "Invalid input provided. Please check your data and try again.",
        "Unsupported operation": "This operation is not supported.",
    }

    @classmethod
    def get_user_message(cls, error: Exception, context: Optional[str] = None) -> Tuple[str, str]:
        """
        Get a user-friendly error message for the given exception.

        Args:
            error: The exception that occurred
            context: Optional context about what operation was being performed

        Returns:
            Tuple of (user_message, technical_details)
        """
        error_str = str(error).lower()
        error_type = type(error).__name__

        # Log the technical error
        logger.error(f"Error occurred: {error_type}: {error}", exc_info=True)

        # Check each error category
        for category_errors in [cls.API_ERRORS, cls.AUDIO_ERRORS, cls.DATABASE_ERRORS,
                                cls.FILE_ERRORS, cls.NETWORK_ERRORS, cls.PROCESSING_ERRORS]:
            for key, message in category_errors.items():
                if key.lower() in error_str:
                    return cls._format_message(message, context), str(error)

        # Default messages for common exception types
        if "connectionerror" in error_type.lower():
            return cls._format_message("Connection error. Please check your internet connection.", context), str(error)
        elif "timeout" in error_type.lower():
            return cls._format_message("Operation timed out. Please try again.", context), str(error)
        elif "permissionerror" in error_type.lower():
            return cls._format_message("Permission denied. Please check your access rights.", context), str(error)
        elif "filenotfounderror" in error_type.lower():
            return cls._format_message("File not found. Please check the file path.", context), str(error)
        elif "memoryerror" in error_type.lower():
            return cls._format_message("Out of memory. Please close other applications.", context), str(error)

        # Generic fallback
        generic_message = "An unexpected error occurred. Please try again."
        if context:
            generic_message = f"An error occurred while {context}. Please try again."

        return generic_message, str(error)

    @classmethod
    def _format_message(cls, message: str, context: Optional[str] = None) -> str:
        """Format error message with optional context."""
        if context:
            return f"Error while {context}: {message}"
        return message

    @classmethod
    def get_retry_suggestion(cls, error: Exception) -> Optional[str]:
        """Get a suggestion for whether/how to retry after an error."""
        error_str = str(error).lower()

        if "rate limit" in error_str:
            return "Wait 60 seconds before retrying."
        elif "timeout" in error_str or "connection" in error_str:
            return "Check your internet connection and try again."
        elif "database locked" in error_str:
            return "Wait a few seconds and try again."
        elif "out of memory" in error_str:
            return "Close other applications and try again."
        elif "permission" in error_str:
            return "Check file/folder permissions and try again."

        return None


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

def get_user_friendly_error(error: Exception, context: Optional[str] = None) -> str:
    """
    Convenience function to get user-friendly error message.

    Args:
        error: The exception that occurred
        context: What operation was being performed (e.g., "saving file", "recording audio")

    Returns:
        User-friendly error message
    """
    user_message, _ = ErrorMessageMapper.get_user_message(error, context)
    return user_message


def format_error_with_retry(error: Exception, context: Optional[str] = None) -> str:
    """
    Format error with retry suggestion if applicable.

    Args:
        error: The exception that occurred
        context: What operation was being performed

    Returns:
        Formatted error message with retry suggestion
    """
    user_message = get_user_friendly_error(error, context)
    retry_suggestion = ErrorMessageMapper.get_retry_suggestion(error)

    if retry_suggestion:
        return f"{user_message}\n\n{retry_suggestion}"
    return user_message


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Error codes
    "ERROR_CODES",
    "get_error_message",
    "show_error_dialog",
    "format_api_error",
    # Message mapper
    "ErrorMessageMapper",
    "get_user_friendly_error",
    "format_error_with_retry",
]
