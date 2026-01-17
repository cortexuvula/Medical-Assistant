"""
Security Package

Provides comprehensive security features for the Medical Assistant application.
Includes encryption, rate limiting, and enhanced validation.
"""

import hashlib
import secrets
from typing import Optional, Tuple
from threading import Lock
from utils.structured_logging import get_logger

from core.config import get_config
from utils.security.key_storage import SecureKeyStorage
from utils.security.rate_limiter import RateLimiter
from utils.security.validators import APIKeyValidator, InputSanitizer

logger = get_logger(__name__)


class SecurityManager:
    """Central security manager for the application."""

    _instance = None
    _lock = Lock()

    def __new__(cls):
        """Singleton pattern."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize security manager."""
        if hasattr(self, '_initialized'):
            return

        self._initialized = True
        # Using module-level logger
        self.key_storage = SecureKeyStorage()
        self.rate_limiter = RateLimiter()
        self.api_key_validator = APIKeyValidator()
        self.input_sanitizer = InputSanitizer()
        self.config = get_config()

        # Expose validators for backward compatibility
        self.api_key_validators = self.api_key_validator.validators
        self.api_key_formats = self.api_key_validator.api_key_formats

    def store_api_key(self, provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate and store an API key securely.

        Args:
            provider: API provider name
            api_key: API key to store

        Returns:
            Tuple of (success, error_message)
        """
        # Validate the key
        is_valid, error = self.validate_api_key(provider, api_key)
        if not is_valid:
            return False, error

        try:
            # Store encrypted
            self.key_storage.store_key(provider, api_key)
            return True, None
        except Exception as e:
            return False, f"Failed to store key: {str(e)}"

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get an API key, checking both environment and secure storage.

        Args:
            provider: API provider name

        Returns:
            API key or None
        """
        # First check environment variable
        env_key = self.config.get_api_key(provider)
        if env_key:
            return env_key

        # Then check secure storage
        return self.key_storage.get_key(provider)

    def validate_api_key(self, provider: str, api_key: str) -> Tuple[bool, Optional[str]]:
        """Enhanced API key validation.

        Args:
            provider: API provider name
            api_key: API key to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return self.api_key_validator.validate(provider, api_key)

    def update_api_key_format(self, provider: str, prefix: Optional[str] = None,
                              min_length: Optional[int] = None, max_length: Optional[int] = None,
                              chars: Optional[str] = None) -> None:
        """Update API key format rules for a provider at runtime.

        Args:
            provider: The provider name
            prefix: Expected prefix (e.g., 'sk-', 'gsk_'), or None to not check prefix
            min_length: Minimum key length, or None to keep existing
            max_length: Maximum key length, or None to keep existing
            chars: Character set ('alnum', 'alnum_dash'), or None to not validate chars
        """
        self.api_key_validator.update_format(provider, prefix, min_length, max_length, chars)

    def check_rate_limit(self, provider: str, identifier: Optional[str] = None) -> Tuple[bool, Optional[float]]:
        """Check if API call is within rate limits.

        Args:
            provider: API provider name
            identifier: Optional identifier for granular limiting

        Returns:
            Tuple of (is_allowed, wait_time_seconds)
        """
        return self.rate_limiter.check_rate_limit(provider, identifier)

    def sanitize_input(self, input_text: str, input_type: str = "prompt") -> str:
        """Enhanced input sanitization.

        Args:
            input_text: Text to sanitize
            input_type: Type of input (prompt, filename, etc.)

        Returns:
            Sanitized text
        """
        return self.input_sanitizer.sanitize(input_text, input_type)

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate a cryptographically secure random token.

        Args:
            length: Token length in bytes

        Returns:
            Hex-encoded secure token
        """
        return secrets.token_hex(length)

    def hash_sensitive_data(self, data: str) -> str:
        """Hash sensitive data for logging or comparison.

        Args:
            data: Sensitive data to hash

        Returns:
            SHA-256 hash of the data
        """
        return hashlib.sha256(data.encode()).hexdigest()


# Global security manager instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance.

    Returns:
        SecurityManager: Global security manager
    """
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


__all__ = [
    "SecureKeyStorage",
    "RateLimiter",
    "APIKeyValidator",
    "InputSanitizer",
    "SecurityManager",
    "get_security_manager",
]
