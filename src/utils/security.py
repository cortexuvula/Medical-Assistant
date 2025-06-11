"""
Comprehensive security module for Medical Assistant.
Provides encryption, rate limiting, and enhanced validation.
"""

import os
import json
import time
import hashlib
import logging
import secrets
from pathlib import Path
from typing import Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
import base64
from threading import Lock
from collections import defaultdict, deque

from core.config import get_config
from utils.exceptions import ConfigurationError, APIError


class SecureKeyStorage:
    """Secure storage for API keys with encryption at rest."""
    
    def __init__(self, key_file: Optional[Path] = None):
        """Initialize secure key storage.
        
        Args:
            key_file: Path to encrypted key file (default: config/keys.enc)
        """
        self.logger = logging.getLogger(__name__)
        self.config = get_config()
        
        if key_file is None:
            key_file = Path(self.config.storage.base_folder) / ".keys" / "keys.enc"
        
        self.key_file = key_file
        self.key_file.parent.mkdir(parents=True, exist_ok=True)
        
        # Lock for thread safety
        self._lock = Lock()
        
        # Initialize encryption
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption key from master password or environment."""
        # Try to get master key from environment
        master_key = os.getenv("MEDICAL_ASSISTANT_MASTER_KEY")
        
        if not master_key:
            # Generate from machine-specific data
            machine_id = self._get_machine_id()
            master_key = machine_id
        
        # Derive encryption key from master key
        self._cipher_suite = self._create_cipher(master_key)
    
    def _get_machine_id(self) -> str:
        """Get a unique machine identifier for key derivation."""
        # Combine multiple sources for uniqueness
        sources = []
        
        # Username
        sources.append(os.getenv("USER", "default"))
        
        # Home directory
        sources.append(str(Path.home()))
        
        # Platform-specific ID
        try:
            if os.name == 'posix':
                # Try to get MAC address on Unix-like systems
                import uuid
                sources.append(str(uuid.getnode()))
            elif os.name == 'nt':
                # Windows machine GUID
                import subprocess
                result = subprocess.run(
                    ['wmic', 'csproduct', 'get', 'UUID'],
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    sources.append(result.stdout.strip())
        except:
            pass
        
        # Combine sources
        combined = "|".join(sources)
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _create_cipher(self, password: str) -> Fernet:
        """Create a cipher suite from a password.
        
        Args:
            password: Password to derive key from
            
        Returns:
            Fernet cipher suite
        """
        # Use PBKDF2 to derive a key from the password
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=b'medical_assistant_salt_v1',  # Static salt for this application
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def store_key(self, provider: str, api_key: str):
        """Store an encrypted API key.
        
        Args:
            provider: API provider name
            api_key: API key to store
        """
        with self._lock:
            # Load existing keys
            keys = self._load_keys()
            
            # Encrypt and store the new key
            encrypted_key = self._cipher_suite.encrypt(api_key.encode())
            keys[provider] = {
                "encrypted_key": base64.b64encode(encrypted_key).decode(),
                "stored_at": datetime.now().isoformat(),
                "key_hash": hashlib.sha256(api_key.encode()).hexdigest()[:8]  # For verification
            }
            
            # Save keys
            self._save_keys(keys)
            self.logger.info(f"Securely stored API key for {provider}")
    
    def get_key(self, provider: str) -> Optional[str]:
        """Retrieve and decrypt an API key.
        
        Args:
            provider: API provider name
            
        Returns:
            Decrypted API key or None if not found
        """
        with self._lock:
            keys = self._load_keys()
            
            if provider not in keys:
                return None
            
            try:
                encrypted_key = base64.b64decode(keys[provider]["encrypted_key"])
                decrypted_key = self._cipher_suite.decrypt(encrypted_key).decode()
                return decrypted_key
            except Exception as e:
                self.logger.error(f"Failed to decrypt key for {provider}: {e}")
                return None
    
    def remove_key(self, provider: str) -> bool:
        """Remove a stored API key.
        
        Args:
            provider: API provider name
            
        Returns:
            True if removed, False if not found
        """
        with self._lock:
            keys = self._load_keys()
            
            if provider in keys:
                del keys[provider]
                self._save_keys(keys)
                self.logger.info(f"Removed API key for {provider}")
                return True
            
            return False
    
    def list_providers(self) -> Dict[str, Dict[str, str]]:
        """List stored providers with metadata (not the actual keys).
        
        Returns:
            Dictionary of provider metadata
        """
        with self._lock:
            keys = self._load_keys()
            
            # Return metadata only, not the encrypted keys
            return {
                provider: {
                    "stored_at": data["stored_at"],
                    "key_hash": data["key_hash"]
                }
                for provider, data in keys.items()
            }
    
    def _load_keys(self) -> Dict[str, Any]:
        """Load encrypted keys from file."""
        if not self.key_file.exists():
            return {}
        
        try:
            with open(self.key_file, 'r') as f:
                return json.load(f)
        except Exception as e:
            self.logger.error(f"Failed to load keys: {e}")
            return {}
    
    def _save_keys(self, keys: Dict[str, Any]):
        """Save encrypted keys to file."""
        try:
            # Set restrictive permissions (owner read/write only)
            with open(self.key_file, 'w') as f:
                json.dump(keys, f, indent=2)
            
            # Set file permissions (Unix-like systems)
            if os.name == 'posix':
                os.chmod(self.key_file, 0o600)
                
        except Exception as e:
            self.logger.error(f"Failed to save keys: {e}")
            raise ConfigurationError(f"Failed to save encrypted keys: {e}")


class RateLimiter:
    """Rate limiter for API calls."""
    
    def __init__(self):
        """Initialize rate limiter."""
        self.logger = logging.getLogger(__name__)
        self._limits = defaultdict(lambda: {"calls": deque(), "lock": Lock()})
        
        # Default rate limits per provider (calls per minute)
        self.default_limits = {
            "openai": 60,
            "perplexity": 50,
            "groq": 30,
            "deepgram": 100,
            "elevenlabs": 50,
            "ollama": 1000  # Local, so higher limit
        }
    
    def check_rate_limit(self, provider: str, identifier: Optional[str] = None) -> Tuple[bool, Optional[float]]:
        """Check if a request is within rate limits.
        
        Args:
            provider: API provider name
            identifier: Optional identifier for more granular limiting
            
        Returns:
            Tuple of (is_allowed, wait_time_seconds)
        """
        key = f"{provider}:{identifier}" if identifier else provider
        limit_data = self._limits[key]
        
        with limit_data["lock"]:
            now = time.time()
            calls = limit_data["calls"]
            
            # Get rate limit for provider
            rate_limit = self.default_limits.get(provider, 60)
            
            # Remove calls older than 1 minute
            while calls and calls[0] < now - 60:
                calls.popleft()
            
            # Check if we're at the limit
            if len(calls) >= rate_limit:
                # Calculate wait time
                oldest_call = calls[0]
                wait_time = 60 - (now - oldest_call)
                return False, wait_time
            
            # Record this call
            calls.append(now)
            return True, None
    
    def set_limit(self, provider: str, calls_per_minute: int):
        """Set custom rate limit for a provider.
        
        Args:
            provider: API provider name
            calls_per_minute: Maximum calls per minute
        """
        self.default_limits[provider] = calls_per_minute
        self.logger.info(f"Set rate limit for {provider}: {calls_per_minute} calls/minute")
    
    def get_usage_stats(self, provider: str) -> Dict[str, Any]:
        """Get usage statistics for a provider.
        
        Args:
            provider: API provider name
            
        Returns:
            Usage statistics
        """
        limit_data = self._limits[provider]
        
        with limit_data["lock"]:
            now = time.time()
            calls = limit_data["calls"]
            
            # Remove old calls
            while calls and calls[0] < now - 60:
                calls.popleft()
            
            rate_limit = self.default_limits.get(provider, 60)
            
            return {
                "provider": provider,
                "calls_last_minute": len(calls),
                "rate_limit": rate_limit,
                "available": rate_limit - len(calls),
                "utilization": len(calls) / rate_limit if rate_limit > 0 else 0
            }


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
        self.logger = logging.getLogger(__name__)
        self.key_storage = SecureKeyStorage()
        self.rate_limiter = RateLimiter()
        self.config = get_config()
        
        # Enhanced validation patterns
        self.api_key_validators = {
            "openai": self._validate_openai_key,
            "deepgram": self._validate_deepgram_key,
            "elevenlabs": self._validate_elevenlabs_key,
            "groq": self._validate_groq_key,
            "perplexity": self._validate_perplexity_key,
        }
    
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
        if not api_key:
            return False, "API key cannot be empty"
        
        # Basic validation from validation.py
        from utils.validation import validate_api_key as basic_validate
        is_valid, error = basic_validate(provider, api_key)
        if not is_valid:
            return False, error
        
        # Provider-specific validation
        if provider in self.api_key_validators:
            return self.api_key_validators[provider](api_key)
        
        return True, None
    
    def _validate_openai_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate OpenAI API key format."""
        if not api_key.startswith("sk-"):
            return False, "OpenAI API keys should start with 'sk-'"
        
        # OpenAI keys can have varying lengths now (sk-proj-*, etc.)
        if len(api_key) < 20:  # Minimum reasonable length
            return False, "OpenAI API key is too short"
        
        if len(api_key) > 200:  # Maximum reasonable length
            return False, "OpenAI API key is too long"
        
        return True, None
    
    def _validate_groq_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Groq API key format."""
        if not api_key.startswith("gsk_"):
            return False, "Groq API keys should start with 'gsk_'"
        
        if len(api_key) != 56:  # gsk_ + 52 characters
            return False, "Invalid Groq API key length"
        
        return True, None
    
    def _validate_deepgram_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Deepgram API key format."""
        # Deepgram keys are typically 40+ character alphanumeric strings
        if len(api_key) < 32:
            return False, "Deepgram API key is too short"
        
        if len(api_key) > 100:
            return False, "Deepgram API key is too long"
        
        # Allow alphanumeric characters
        if not api_key.isalnum():
            return False, "Deepgram API key should contain only letters and numbers"
        
        return True, None
    
    def _validate_elevenlabs_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate ElevenLabs API key format."""
        if len(api_key) != 32:
            return False, "Invalid ElevenLabs API key length"
        
        try:
            int(api_key, 16)  # Should be hexadecimal
        except ValueError:
            return False, "ElevenLabs API key should be hexadecimal"
        
        return True, None
    
    def _validate_perplexity_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Perplexity API key format."""
        if not api_key.startswith("pplx-"):
            return False, "Perplexity API keys should start with 'pplx-'"
        
        if len(api_key) != 53:  # pplx- + 48 characters
            return False, "Invalid Perplexity API key length"
        
        return True, None
    
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
        if not input_text:
            return ""
        
        # Use validation.py sanitization as base
        from utils.validation import sanitize_prompt, safe_filename
        
        if input_type == "prompt":
            sanitized = sanitize_prompt(input_text)
            
            # Additional security checks
            # Remove potential prompt injection attempts
            injection_patterns = [
                r'ignore previous instructions',
                r'disregard all prior',
                r'forget everything',
                r'system:',
                r'assistant:',
                r'user:',
            ]
            
            for pattern in injection_patterns:
                if pattern.lower() in sanitized.lower():
                    self.logger.warning(f"Potential prompt injection detected: {pattern}")
                    sanitized = sanitized.replace(pattern, "")
            
            return sanitized
        
        elif input_type == "filename":
            return safe_filename(input_text)
        
        else:
            # Generic sanitization
            # Remove control characters
            sanitized = ''.join(char for char in input_text if ord(char) >= 32 or char in '\n\t')
            
            # Limit length
            max_length = 10000
            if len(sanitized) > max_length:
                sanitized = sanitized[:max_length]
            
            return sanitized.strip()
    
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