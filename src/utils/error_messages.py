"""
User-friendly error message mapping for Medical Assistant.

This module provides human-readable error messages for various error conditions,
helping to improve the user experience by translating technical errors into
understandable messages.
"""

import logging
from typing import Dict, Optional, Tuple


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
        logging.error(f"Error occurred: {error_type}: {error}", exc_info=True)
        
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