"""Input validation utilities for the Medical Assistant application."""

import os
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, List
from error_codes import get_error_message

# API key patterns for basic validation
API_KEY_PATTERNS = {
    # OpenAI now uses various formats including sk-proj-*, sk-*, etc.
    "openai": re.compile(r'^sk-[a-zA-Z0-9\-_]{20,}$'),
    # Deepgram keys can be various formats, often 40+ character alphanumeric
    "deepgram": re.compile(r'^[a-zA-Z0-9]{32,}$'),
    # ElevenLabs keys start with sk_ followed by alphanumeric characters
    "elevenlabs": re.compile(r'^sk_[a-zA-Z0-9]{40,}$'),
    "groq": re.compile(r'^gsk_[a-zA-Z0-9]{52}$'),
    "perplexity": re.compile(r'^pplx-[a-f0-9]{48}$'),
    "grok": re.compile(r'^xai-[a-zA-Z0-9]+$'),
    # Anthropic keys start with sk-ant- followed by alphanumeric characters
    "anthropic": re.compile(r'^sk-ant-[a-zA-Z0-9\-_]{95,}$'),
}

# Maximum lengths for input validation
MAX_PROMPT_LENGTH = 10000  # Maximum characters for user prompts
MAX_FILE_PATH_LENGTH = 260  # Windows MAX_PATH limitation
MAX_API_KEY_LENGTH = 200  # Reasonable maximum for API keys

# Dangerous patterns to sanitize from prompts
DANGEROUS_PATTERNS = [
    # Injection attempts
    # Updated pattern to match various script tag formats including malformed ones
    re.compile(r'<script[^>]*>.*?</script[^>]*>', re.IGNORECASE | re.DOTALL),
    re.compile(r'javascript:', re.IGNORECASE),
    re.compile(r'on\w+\s*=', re.IGNORECASE),  # Event handlers
    # System commands
    re.compile(r';\s*(rm|del|format|shutdown|reboot)', re.IGNORECASE),
    re.compile(r'\$\(.*?\)'),  # Command substitution
    re.compile(r'`.*?`'),  # Backtick command execution
]

def validate_api_key(provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
    """Validate an API key for a specific provider.
    
    Args:
        provider: The API provider name (openai, deepgram, etc.)
        api_key: The API key to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not api_key:
        return False, "API key cannot be empty"
    
    # Check length
    if len(api_key) > MAX_API_KEY_LENGTH:
        return False, f"API key is too long (max {MAX_API_KEY_LENGTH} characters)"
    
    # Remove whitespace
    api_key = api_key.strip()
    
    # Basic format validation for known providers
    if provider.lower() in API_KEY_PATTERNS:
        pattern = API_KEY_PATTERNS[provider.lower()]
        if not pattern.match(api_key):
            return False, f"Invalid {provider} API key format"
    
    # Check for common mistakes
    if api_key.startswith('"') or api_key.endswith('"'):
        return False, "API key should not include quotes"
    
    if ' ' in api_key:
        return False, "API key should not contain spaces"
    
    if api_key == f"<YOUR_{provider.upper()}_API_KEY>" or api_key.startswith("<") or api_key.endswith(">"):
        return False, "Please replace the placeholder with your actual API key"
    
    return True, None

def sanitize_prompt(prompt: str) -> str:
    """Sanitize user prompt before sending to API.
    
    Args:
        prompt: The user's input prompt
        
    Returns:
        Sanitized prompt safe for API calls
    """
    if not prompt:
        return ""
    
    # Truncate if too long
    if len(prompt) > MAX_PROMPT_LENGTH:
        logging.warning(f"Prompt truncated from {len(prompt)} to {MAX_PROMPT_LENGTH} characters")
        prompt = prompt[:MAX_PROMPT_LENGTH] + "..."
    
    # Remove dangerous patterns
    original_prompt = prompt
    for pattern in DANGEROUS_PATTERNS:
        prompt = pattern.sub('', prompt)
    
    if prompt != original_prompt:
        logging.warning("Potentially dangerous content removed from prompt")
    
    # Remove excessive whitespace
    prompt = ' '.join(prompt.split())
    
    # Remove null bytes and other problematic characters
    prompt = prompt.replace('\x00', '').replace('\r', '\n')
    
    # Ensure the prompt is valid UTF-8
    try:
        prompt.encode('utf-8')
    except UnicodeEncodeError:
        # Remove non-UTF-8 characters
        prompt = prompt.encode('utf-8', 'ignore').decode('utf-8')
        logging.warning("Non-UTF-8 characters removed from prompt")
    
    return prompt.strip()

def validate_file_path(file_path: str, must_exist: bool = False, 
                      must_be_writable: bool = False) -> Tuple[bool, Optional[str]]:
    """Validate a file path for safety and accessibility.
    
    Args:
        file_path: The file path to validate
        must_exist: Whether the file must already exist
        must_be_writable: Whether we need write access to the file/directory
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not file_path:
        return False, "File path cannot be empty"
    
    # Check length
    if len(file_path) > MAX_FILE_PATH_LENGTH:
        return False, f"File path too long (max {MAX_FILE_PATH_LENGTH} characters)"
    
    try:
        path = Path(file_path).resolve()
        
        # Security check: ensure path doesn't escape intended directories
        # This is a basic check - adjust based on your security requirements
        if ".." in file_path:
            return False, "File path cannot contain '..' for security reasons"
        
        # Check if path exists when required
        if must_exist and not path.exists():
            return False, f"File does not exist: {file_path}"
        
        # Check write permissions
        if must_be_writable:
            if path.exists():
                if not os.access(path, os.W_OK):
                    return False, f"No write permission for: {file_path}"
            else:
                # Check parent directory for write permission
                parent = path.parent
                if not parent.exists():
                    return False, f"Parent directory does not exist: {parent}"
                if not os.access(parent, os.W_OK):
                    return False, f"No write permission in directory: {parent}"
        
        # Check for dangerous file names (Windows)
        dangerous_names = ['CON', 'PRN', 'AUX', 'NUL', 'COM1', 'COM2', 'COM3', 'COM4',
                          'COM5', 'COM6', 'COM7', 'COM8', 'COM9', 'LPT1', 'LPT2', 
                          'LPT3', 'LPT4', 'LPT5', 'LPT6', 'LPT7', 'LPT8', 'LPT9']
        
        base_name = path.stem.upper()
        if base_name in dangerous_names:
            return False, f"Reserved file name not allowed: {path.stem}"
        
        return True, None
        
    except Exception as e:
        return False, f"Invalid file path: {str(e)}"

def validate_audio_file(file_path: str) -> Tuple[bool, Optional[str]]:
    """Validate an audio file path.
    
    Args:
        file_path: Path to the audio file
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    # First do general file validation
    is_valid, error = validate_file_path(file_path, must_exist=True)
    if not is_valid:
        return False, error
    
    # Check file extension
    valid_extensions = {'.wav', '.mp3', '.m4a', '.flac', '.ogg', '.opus', '.webm'}
    path = Path(file_path)
    if path.suffix.lower() not in valid_extensions:
        return False, f"Unsupported audio format: {path.suffix}"
    
    # Check file size (limit to 100MB for safety)
    max_size = 100 * 1024 * 1024  # 100MB
    if path.stat().st_size > max_size:
        return False, f"Audio file too large (max 100MB)"
    
    return True, None

def validate_model_name(model_name: str, provider: str) -> Tuple[bool, Optional[str]]:
    """Validate a model name for a specific provider.
    
    Args:
        model_name: The model name to validate
        provider: The API provider
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not model_name:
        return False, "Model name cannot be empty"
    
    # Basic validation
    if len(model_name) > 100:
        return False, "Model name too long"
    
    # Provider-specific validation
    if provider.lower() == "openai":
        valid_prefixes = ['gpt-3.5', 'gpt-4', 'text-', 'davinci', 'curie', 'babbage', 'ada']
        if not any(model_name.startswith(prefix) for prefix in valid_prefixes):
            logging.warning(f"Unusual OpenAI model name: {model_name}")
    
    elif provider.lower() == "ollama":
        # Ollama models should not contain special characters
        if not re.match(r'^[a-zA-Z0-9_\-:\.]+$', model_name):
            return False, "Invalid Ollama model name format"
    
    return True, None

def validate_temperature(temperature: float) -> Tuple[bool, Optional[str]]:
    """Validate temperature parameter for AI models.
    
    Args:
        temperature: The temperature value
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        temp = float(temperature)
        if temp < 0.0 or temp > 2.0:
            return False, "Temperature must be between 0.0 and 2.0"
        return True, None
    except (ValueError, TypeError):
        return False, "Temperature must be a number"

def validate_export_path(directory: str) -> Tuple[bool, Optional[str]]:
    """Validate a directory path for exporting files.
    
    Args:
        directory: The directory path to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    is_valid, error = validate_file_path(directory, must_exist=True, must_be_writable=True)
    if not is_valid:
        return False, error
    
    path = Path(directory)
    if not path.is_dir():
        return False, "Path must be a directory, not a file"
    
    return True, None

def safe_filename(filename: str, max_length: int = 255) -> str:
    """Convert a string into a safe filename.
    
    Args:
        filename: The desired filename
        max_length: Maximum length for the filename
        
    Returns:
        A sanitized filename safe for the filesystem
    """
    # Remove invalid characters
    safe_chars = re.sub(r'[<>:"/\\|?*]', '_', filename)
    
    # Remove control characters
    safe_chars = ''.join(char for char in safe_chars if ord(char) >= 32)
    
    # Remove leading/trailing dots and spaces
    safe_chars = safe_chars.strip('. ')
    
    # Ensure it's not empty
    if not safe_chars:
        safe_chars = "unnamed"
    
    # Truncate if too long
    if len(safe_chars) > max_length:
        safe_chars = safe_chars[:max_length]
    
    return safe_chars