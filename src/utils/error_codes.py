"""Error codes and messages for the Medical Assistant application."""

from typing import Dict, Tuple

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