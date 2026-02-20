"""
Security Validators Module

Provides input sanitization and API key validation.
"""

import re
from typing import Dict, Optional, Tuple, Callable
from utils.structured_logging import get_logger

from utils.constants import (
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_CEREBRAS,
    STT_DEEPGRAM, STT_GROQ, STT_ELEVENLABS
)

logger = get_logger(__name__)


class APIKeyValidator:
    """Validates API key formats for various providers."""

    def __init__(self):
        """Initialize the API key validator."""
        # Using module-level logger

        # Configurable API key format rules
        # Format: (prefix, min_length, max_length, allowed_chars_pattern)
        # Use None for fields that shouldn't be checked
        # allowed_chars_pattern: 'alnum' for alphanumeric, 'alnum_dash' for alphanumeric + dash/underscore, or None
        self.api_key_formats: Dict[str, Dict] = {
            PROVIDER_OPENAI: {"prefix": "sk-", "min_length": 20, "max_length": 200, "chars": "alnum_dash"},
            STT_GROQ: {"prefix": "gsk_", "min_length": 40, "max_length": 100, "chars": "alnum"},
            STT_DEEPGRAM: {"prefix": None, "min_length": 32, "max_length": 100, "chars": "alnum"},
            STT_ELEVENLABS: {"prefix": "sk_", "min_length": 30, "max_length": 100, "chars": "alnum"},
            PROVIDER_ANTHROPIC: {"prefix": "sk-ant-", "min_length": 90, "max_length": 200, "chars": "alnum_dash"},
            PROVIDER_CEREBRAS: {"prefix": "csk-", "min_length": 20, "max_length": 100, "chars": "alnum_dash"},
        }

        # Provider-specific validators
        self.validators: Dict[str, Callable[[str], Tuple[bool, Optional[str]]]] = {
            PROVIDER_OPENAI: self._validate_openai_key,
            STT_DEEPGRAM: self._validate_deepgram_key,
            STT_ELEVENLABS: self._validate_elevenlabs_key,
            STT_GROQ: self._validate_groq_key,
            PROVIDER_ANTHROPIC: self._validate_anthropic_key,
            PROVIDER_CEREBRAS: self._validate_cerebras_key,
        }

    def validate(self, provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate an API key for a provider.

        Args:
            provider: API provider name
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not api_key:
            return False, "API key cannot be empty"

        # Basic validation from validation.py
        from utils.validation import validate_api_key as basic_validate
        is_valid, error = basic_validate(provider, api_key)
        if not is_valid:
            return False, error

        # Provider-specific validation
        if provider in self.validators:
            return self.validators[provider](api_key)

        return True, None

    def _validate_key_format(self, api_key: str, provider: str) -> Tuple[bool, Optional[str]]:
        """Generic API key format validation using configurable rules.

        Args:
            api_key: The API key to validate
            provider: The provider name (used to look up format rules)

        Returns:
            Tuple of (is_valid, error_message)
        """
        if provider not in self.api_key_formats:
            # No specific format rules, accept any reasonable key
            if len(api_key) < 10:
                return False, f"{provider} API key is too short"
            if len(api_key) > 500:
                return False, f"{provider} API key is too long"
            return True, None

        rules = self.api_key_formats[provider]
        provider_name = provider.capitalize()

        # Check prefix if specified
        prefix = rules.get("prefix")
        if prefix and not api_key.startswith(prefix):
            return False, f"{provider_name} API keys should start with '{prefix}'"

        # Check minimum length
        min_length = rules.get("min_length", 10)
        if len(api_key) < min_length:
            return False, f"{provider_name} API key is too short (minimum {min_length} characters)"

        # Check maximum length
        max_length = rules.get("max_length", 500)
        if len(api_key) > max_length:
            return False, f"{provider_name} API key is too long (maximum {max_length} characters)"

        # Check character set if specified
        chars = rules.get("chars")
        if chars:
            # Get the part after prefix (if any) for character validation
            check_part = api_key[len(prefix):] if prefix else api_key

            if chars == "alnum":
                if not check_part.isalnum():
                    return False, f"{provider_name} API key should contain only letters and numbers after the prefix"
            elif chars == "alnum_dash":
                # Allow alphanumeric plus dash and underscore
                if not re.match(r'^[a-zA-Z0-9_-]+$', check_part):
                    return False, f"{provider_name} API key contains invalid characters"

        return True, None

    def _validate_openai_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate OpenAI API key format."""
        return self._validate_key_format(api_key, PROVIDER_OPENAI)

    def _validate_groq_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Groq API key format."""
        return self._validate_key_format(api_key, STT_GROQ)

    def _validate_deepgram_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Deepgram API key format."""
        return self._validate_key_format(api_key, STT_DEEPGRAM)

    def _validate_elevenlabs_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate ElevenLabs API key format."""
        return self._validate_key_format(api_key, STT_ELEVENLABS)

    def _validate_anthropic_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Anthropic API key format."""
        return self._validate_key_format(api_key, PROVIDER_ANTHROPIC)

    def _validate_cerebras_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Cerebras API key format."""
        return self._validate_key_format(api_key, PROVIDER_CEREBRAS)

    def update_format(self, provider: str, prefix: Optional[str] = None,
                      min_length: Optional[int] = None, max_length: Optional[int] = None,
                      chars: Optional[str] = None) -> None:
        """Update API key format rules for a provider at runtime.

        This allows adapting to API key format changes without code modifications.

        Args:
            provider: The provider name
            prefix: Expected prefix (e.g., 'sk-', 'gsk_'), or None to not check prefix
            min_length: Minimum key length, or None to keep existing
            max_length: Maximum key length, or None to keep existing
            chars: Character set ('alnum', 'alnum_dash'), or None to not validate chars
        """
        if provider not in self.api_key_formats:
            self.api_key_formats[provider] = {}

        rules = self.api_key_formats[provider]

        if prefix is not None:
            rules["prefix"] = prefix
        if min_length is not None:
            rules["min_length"] = min_length
        if max_length is not None:
            rules["max_length"] = max_length
        if chars is not None:
            rules["chars"] = chars

        logger.info(f"Updated API key format rules for {provider}: {rules}")


class InputSanitizer:
    """Sanitizes user input for security."""

    def __init__(self):
        """Initialize the input sanitizer."""
        # Using module-level logger

        # Prompt injection patterns - specific to avoid false positives with medical text
        # (e.g., "cardiovascular system:" is legitimate medical documentation)
        self.injection_patterns = [
            r'ignore previous instructions',
            r'disregard all prior',
            r'forget everything',
            r'you are now',
            r'new instructions:',
            r'override:',
        ]

    def sanitize(self, input_text: str, input_type: str = "prompt") -> str:
        """Sanitize input based on type.

        Args:
            input_text: Text to sanitize
            input_type: Type of input (prompt, filename, etc.)

        Returns:
            Sanitized text
        """
        if not input_text:
            return ""

        if input_type == "prompt":
            return self._sanitize_prompt(input_text)
        elif input_type == "filename":
            return self._sanitize_filename(input_text)
        else:
            return self._sanitize_generic(input_text)

    def _sanitize_prompt(self, text: str) -> str:
        """Sanitize prompt input.

        Args:
            text: Prompt text to sanitize

        Returns:
            Sanitized prompt
        """
        # Use validation.py sanitization as base
        from utils.validation import sanitize_prompt

        sanitized = sanitize_prompt(text)

        # Additional security checks - remove potential prompt injection attempts
        for pattern in self.injection_patterns:
            if pattern.lower() in sanitized.lower():
                logger.warning(f"Potential prompt injection detected: {pattern}")
                sanitized = sanitized.replace(pattern, "")

        return sanitized

    def _sanitize_filename(self, text: str) -> str:
        """Sanitize filename input.

        Args:
            text: Filename to sanitize

        Returns:
            Sanitized filename
        """
        from utils.validation import safe_filename
        return safe_filename(text)

    def _sanitize_generic(self, text: str) -> str:
        """Generic sanitization for other input types.

        Args:
            text: Text to sanitize

        Returns:
            Sanitized text
        """
        # Remove control characters
        sanitized = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')

        # Limit length
        max_length = 10000
        if len(sanitized) > max_length:
            sanitized = sanitized[:max_length]

        return sanitized.strip()


__all__ = ["APIKeyValidator", "InputSanitizer"]
