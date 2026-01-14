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
from typing import Dict, Optional, Any, Tuple, List
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
from utils.constants import (
    AIProvider, STTProvider, TTSProvider,
    PROVIDER_OPENAI, PROVIDER_ANTHROPIC, PROVIDER_OLLAMA,
    STT_DEEPGRAM, STT_GROQ, STT_ELEVENLABS
)


class SecureKeyStorage:
    """Secure storage for API keys with encryption at rest."""

    # Salt length in bytes (256 bits)
    SALT_LENGTH = 32

    # Legacy static salt for backward compatibility during migration
    LEGACY_SALT = b'medical_assistant_salt_v1'

    # Current salt version for tracking migrations
    SALT_VERSION = 2

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
        self.salt_file = key_file.parent / "salt.bin"
        self.key_file.parent.mkdir(parents=True, exist_ok=True)

        # Lock for thread safety
        self._lock = Lock()

        # Initialize encryption with unique salt
        self._init_encryption()
    
    def _init_encryption(self):
        """Initialize encryption key from master password or environment."""
        # Try to get master key from environment
        master_key = os.getenv("MEDICAL_ASSISTANT_MASTER_KEY")

        if not master_key:
            # Generate from machine-specific data
            machine_id = self._get_machine_id()
            master_key = machine_id

        # Get or create unique salt for this installation
        self._salt = self._get_or_create_salt()

        # Derive encryption key from master key with unique salt
        self._cipher_suite = self._create_cipher(master_key, self._salt)

        # Check if migration from legacy salt is needed
        self._migrate_legacy_keys_if_needed(master_key)

    def _get_or_create_salt(self) -> bytes:
        """Get existing salt or create a new one.

        Returns:
            Salt bytes for key derivation
        """
        if self.salt_file.exists():
            try:
                with open(self.salt_file, 'rb') as f:
                    salt_data = f.read()
                    # Validate salt length
                    if len(salt_data) >= self.SALT_LENGTH:
                        return salt_data[:self.SALT_LENGTH]
                    else:
                        self.logger.warning("Invalid salt file, generating new salt")
            except Exception as e:
                self.logger.warning(f"Failed to read salt file: {e}")

        # Generate new cryptographically secure salt
        new_salt = secrets.token_bytes(self.SALT_LENGTH)
        self._save_salt(new_salt)
        return new_salt

    def _save_salt(self, salt: bytes):
        """Save salt to file with secure permissions.

        Args:
            salt: Salt bytes to save
        """
        try:
            with open(self.salt_file, 'wb') as f:
                f.write(salt)

            # Set restrictive permissions (owner read/write only)
            if os.name == 'posix':
                os.chmod(self.salt_file, 0o600)

            self.logger.debug("Salt file saved successfully")
        except Exception as e:
            self.logger.error(f"Failed to save salt file: {e}")
            raise ConfigurationError(f"Failed to save encryption salt: {e}")

    def _migrate_legacy_keys_if_needed(self, master_key: str):
        """Migrate keys from legacy static salt to unique salt.

        Args:
            master_key: Master key for encryption
        """
        keys = self._load_keys()

        # Check if migration is needed
        metadata = keys.get("_metadata", {})
        current_version = metadata.get("salt_version", 1)

        if current_version >= self.SALT_VERSION:
            return  # Already migrated

        if not keys or (len(keys) == 1 and "_metadata" in keys):
            # No keys to migrate, just update version
            self._update_metadata_version(keys)
            return

        self.logger.info("Migrating API keys to new salt format...")
        failed_providers = []  # Track providers that fail migration

        try:
            # Create cipher with legacy salt for decryption
            legacy_cipher = self._create_cipher(master_key, self.LEGACY_SALT)

            # Migrate each key
            migrated_keys = {"_metadata": {"salt_version": self.SALT_VERSION}}

            for provider, data in keys.items():
                if provider == "_metadata":
                    continue

                try:
                    # Decrypt with legacy cipher
                    encrypted_key = base64.b64decode(data["encrypted_key"])
                    decrypted_key = legacy_cipher.decrypt(encrypted_key).decode()

                    # Re-encrypt with new salt
                    new_encrypted = self._cipher_suite.encrypt(decrypted_key.encode())

                    migrated_keys[provider] = {
                        "encrypted_key": base64.b64encode(new_encrypted).decode(),
                        "stored_at": data.get("stored_at", datetime.now().isoformat()),
                        "key_hash": data.get("key_hash", hashlib.sha256(decrypted_key.encode()).hexdigest()[:8])
                    }

                    self.logger.info(f"Migrated key for {provider}")

                except (ValueError, TypeError, KeyError) as e:
                    self.logger.warning(f"Failed to migrate key for {provider}: {e}")
                    # Track failed migrations for user notification
                    failed_providers.append(provider)
                    # Keep the old format - will fail on decrypt but preserves data
                    migrated_keys[provider] = data

            # Save migrated keys
            self._save_keys(migrated_keys)
            self.logger.info("Key migration completed successfully")

            # Notify user about failed migrations
            if failed_providers:
                self._migration_failures = failed_providers
                self.logger.warning(
                    f"Key migration incomplete. The following providers need re-configuration: "
                    f"{', '.join(failed_providers)}. Please re-enter API keys in Settings."
                )

        except (IOError, OSError, json.JSONDecodeError) as e:
            self.logger.error(f"Key migration failed due to file error: {e}")
            self._migration_failures = ["all"]
            # Don't raise - allow app to continue, but track failure for UI notification

    def get_migration_failures(self) -> List[str]:
        """Get list of providers that failed migration.

        Returns:
            List of provider names that failed migration, or empty list if none
        """
        return getattr(self, '_migration_failures', [])

    def _update_metadata_version(self, keys: Dict[str, Any]):
        """Update metadata version without full migration.

        Args:
            keys: Current keys dictionary
        """
        keys["_metadata"] = {"salt_version": self.SALT_VERSION}
        self._save_keys(keys)
    
    def _get_machine_id(self) -> str:
        """Get a unique machine identifier for key derivation.

        Uses multiple sources to create a stable, unique identifier:
        1. Machine-specific hardware identifiers
        2. Filesystem UUIDs (more stable than usernames)
        3. Fallback to user-related identifiers

        Returns:
            SHA-256 hash of combined identifiers
        """
        sources = []

        # Try platform-specific stable identifiers first
        try:
            if os.name == 'posix':
                # Linux: Try machine-id first (most stable)
                machine_id_paths = [
                    '/etc/machine-id',
                    '/var/lib/dbus/machine-id',
                ]
                for path in machine_id_paths:
                    try:
                        with open(path, 'r') as f:
                            machine_id = f.read().strip()
                            if machine_id:
                                sources.append(f"machine_id:{machine_id}")
                                break
                    except (IOError, OSError):
                        continue

                # Also try filesystem UUID of root partition
                try:
                    import subprocess
                    result = subprocess.run(
                        ['findmnt', '-n', '-o', 'UUID', '/'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        sources.append(f"fs_uuid:{result.stdout.strip()}")
                except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                    pass

                # MAC address as additional entropy (may change with VM/container)
                try:
                    import uuid
                    mac = uuid.getnode()
                    # Check if it's a valid MAC (not a random fallback)
                    if mac and (mac >> 40) != 0:
                        sources.append(f"mac:{mac}")
                except (OSError, ValueError, AttributeError):
                    # MAC address retrieval failed
                    pass

            elif os.name == 'nt':
                # Windows: Use multiple stable identifiers
                import subprocess

                # Try machine GUID from registry (most stable)
                try:
                    result = subprocess.run(
                        ['reg', 'query',
                         'HKLM\\SOFTWARE\\Microsoft\\Cryptography',
                         '/v', 'MachineGuid'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        # Parse the output to get the GUID
                        for line in result.stdout.split('\n'):
                            if 'MachineGuid' in line:
                                parts = line.strip().split()
                                if len(parts) >= 3:
                                    sources.append(f"win_guid:{parts[-1]}")
                                    break
                except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                    pass

                # Fallback to product UUID via WMIC
                try:
                    result = subprocess.run(
                        ['wmic', 'csproduct', 'get', 'UUID'],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0:
                        lines = [l.strip() for l in result.stdout.split('\n') if l.strip() and l.strip() != 'UUID']
                        if lines:
                            sources.append(f"product_uuid:{lines[0]}")
                except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
                    pass

        except Exception as e:
            self.logger.warning(f"Error getting platform-specific machine ID: {e}")

        # Fallback identifiers (less stable but always available)
        if not sources:
            self.logger.warning("Using fallback machine identification - encryption keys may not survive reinstall")

            # Username (less stable)
            username = os.getenv("USER") or os.getenv("USERNAME") or "default"
            sources.append(f"user:{username}")

            # Home directory path
            sources.append(f"home:{str(Path.home())}")

            # Python executable path (helps distinguish environments)
            import sys
            sources.append(f"python:{sys.executable}")

        # Add a constant application identifier for additional uniqueness
        sources.append("app:medical_assistant_v2")

        # Combine all sources and hash
        combined = "|".join(sorted(sources))
        return hashlib.sha256(combined.encode()).hexdigest()
    
    def _create_cipher(self, password: str, salt: bytes) -> Fernet:
        """Create a cipher suite from a password and salt.

        Args:
            password: Password to derive key from
            salt: Unique salt for key derivation (should be cryptographically random)

        Returns:
            Fernet cipher suite
        """
        # Use PBKDF2 to derive a key from the password with unique salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        key = base64.urlsafe_b64encode(kdf.derive(password.encode()))
        return Fernet(key)
    
    def store_key(self, provider: str, api_key: str) -> None:
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
            # Filter out internal metadata entries
            return {
                provider: {
                    "stored_at": data.get("stored_at", ""),
                    "key_hash": data.get("key_hash", "")
                }
                for provider, data in keys.items()
                if provider != "_metadata" and isinstance(data, dict)
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
    
    def _save_keys(self, keys: Dict[str, Any]) -> None:
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
    """Persistent rate limiter for API calls with sliding window algorithm.

    This implementation provides:
    - Persistence across application restarts via JSON file storage
    - Sliding window rate limiting with configurable time windows
    - Automatic cleanup of expired entries
    - Thread-safe operations with per-key locking
    - Graceful degradation if persistence fails
    - Memory-bounded lock management with time-based expiry

    The sliding window algorithm uses timestamps to track calls within a
    rolling time window, providing more accurate rate limiting than fixed
    windows.
    """

    # File save interval in seconds (avoid excessive disk writes)
    SAVE_INTERVAL = 30

    # Maximum age of rate limit data to keep (in seconds)
    MAX_DATA_AGE = 3600  # 1 hour

    # Lock management constants
    MAX_LOCKS = 100  # Maximum number of locks to keep
    LOCK_EXPIRY_SECONDS = 3600  # Remove locks unused for 1 hour
    LOCK_CLEANUP_INTERVAL = 300  # Run cleanup every 5 minutes

    def __init__(self, storage_path: Optional[Path] = None):
        """Initialize rate limiter with persistent storage.

        Args:
            storage_path: Path to rate limit data file (default: config/.rate_limits.json)
        """
        self.logger = logging.getLogger(__name__)
        self._global_lock = Lock()
        # Changed from defaultdict to regular dict with timestamps
        # Format: {key: (Lock, last_access_time)}
        self._key_locks: Dict[str, Tuple[Lock, float]] = {}
        self._last_save_time = 0.0
        self._last_lock_cleanup = 0.0

        # In-memory cache of rate limit data
        # Format: {key: {"calls": [timestamp, ...], "window_seconds": int}}
        self._limits: Dict[str, Dict[str, Any]] = {}

        # Set up storage path
        if storage_path is None:
            config = get_config()
            storage_path = Path(config.storage.base_folder) / ".keys" / ".rate_limits.json"
        self.storage_path = storage_path

        # Default rate limits per provider (calls per time window)
        # Format: (calls, window_seconds)
        self.default_limits: Dict[str, Tuple[int, int]] = {
            PROVIDER_OPENAI: (60, 60),       # 60 calls per minute
            STT_GROQ: (30, 60),              # 30 calls per minute
            STT_DEEPGRAM: (100, 60),         # 100 calls per minute
            STT_ELEVENLABS: (50, 60),        # 50 calls per minute
            PROVIDER_ANTHROPIC: (60, 60),    # 60 calls per minute
            PROVIDER_OLLAMA: (1000, 60),     # Local, so higher limit
        }

        # Load persisted data on startup
        self._load_from_disk()

    def _get_key_lock(self, key: str) -> Lock:
        """Get or create a lock for a specific key.

        Thread-safe method that manages lock lifecycle with time-based expiry.

        Args:
            key: The rate limit key

        Returns:
            Lock for the key
        """
        now = time.time()

        with self._global_lock:
            # Run periodic lock cleanup
            if now - self._last_lock_cleanup > self.LOCK_CLEANUP_INTERVAL:
                self._cleanup_expired_locks(now)
                self._last_lock_cleanup = now

            if key in self._key_locks:
                # Update last access time
                lock, _ = self._key_locks[key]
                self._key_locks[key] = (lock, now)
                return lock
            else:
                # Create new lock
                lock = Lock()
                self._key_locks[key] = (lock, now)
                return lock

    def _cleanup_expired_locks(self, now: float) -> None:
        """Remove locks that haven't been used recently.

        Must be called with _global_lock held.

        Args:
            now: Current timestamp
        """
        # Find locks that have expired (not used for LOCK_EXPIRY_SECONDS)
        expired_keys = []
        for key, (lock, last_access) in list(self._key_locks.items()):
            if now - last_access > self.LOCK_EXPIRY_SECONDS:
                # Only remove if the lock is not currently held
                if lock.acquire(blocking=False):
                    lock.release()
                    expired_keys.append(key)

        # Remove expired locks
        for key in expired_keys:
            del self._key_locks[key]

        if expired_keys:
            self.logger.debug(f"Cleaned up {len(expired_keys)} expired locks")

        # Safety limit: if still over MAX_LOCKS, remove oldest
        if len(self._key_locks) > self.MAX_LOCKS:
            # Sort by last access time and remove oldest
            provider_keys = set(self.default_limits.keys())
            sorted_locks = sorted(
                [(k, v[1]) for k, v in self._key_locks.items() if k not in provider_keys],
                key=lambda x: x[1]  # Sort by last access time
            )
            # Remove oldest locks until under limit
            remove_count = len(self._key_locks) - self.MAX_LOCKS
            for key, _ in sorted_locks[:remove_count]:
                if key in self._key_locks:
                    lock, _ = self._key_locks[key]
                    if lock.acquire(blocking=False):
                        lock.release()
                        del self._key_locks[key]

            self.logger.debug(f"Removed {remove_count} locks to stay under MAX_LOCKS")

    def _load_from_disk(self) -> None:
        """Load rate limit data from disk."""
        try:
            if self.storage_path.exists():
                with open(self.storage_path, 'r') as f:
                    data = json.load(f)

                now = time.time()

                # Load and validate data
                for key, limit_data in data.items():
                    if isinstance(limit_data, dict) and "calls" in limit_data:
                        # Filter out expired calls
                        window = limit_data.get("window_seconds", 60)
                        valid_calls = [
                            ts for ts in limit_data["calls"]
                            if now - ts < window
                        ]

                        # Only keep if there are valid calls
                        if valid_calls:
                            self._limits[key] = {
                                "calls": valid_calls,
                                "window_seconds": window
                            }

                self.logger.debug(f"Loaded rate limit data for {len(self._limits)} keys")

        except json.JSONDecodeError as e:
            self.logger.warning(f"Invalid rate limit data file, starting fresh: {e}")
            self._limits = {}
        except Exception as e:
            self.logger.warning(f"Could not load rate limit data: {e}")
            self._limits = {}

    def _save_to_disk(self, force: bool = False) -> None:
        """Save rate limit data to disk asynchronously.

        This method schedules a save operation in a background thread to avoid
        blocking API calls. The save is rate-limited by SAVE_INTERVAL.

        Args:
            force: If True, save immediately; otherwise respect SAVE_INTERVAL
        """
        now = time.time()

        # Respect save interval unless forced
        if not force and now - self._last_save_time < self.SAVE_INTERVAL:
            return

        # Update timestamp immediately to prevent multiple concurrent saves
        self._last_save_time = now

        # Take a snapshot of data for async save (quick operation under lock)
        with self._global_lock:
            data_snapshot = {k: dict(v) for k, v in self._limits.items()}

        # Schedule async save in background thread
        def _do_save():
            try:
                # Ensure directory exists
                self.storage_path.parent.mkdir(parents=True, exist_ok=True)

                # Cleanup old data from snapshot
                cutoff = time.time() - self.MAX_DATA_AGE
                cleaned_data = {}
                for key, limit_data in data_snapshot.items():
                    calls = limit_data.get("calls", [])
                    window = limit_data.get("window_seconds", 60)
                    if calls and max(calls) > cutoff:
                        # Keep only calls within window
                        window_start = time.time() - window
                        limit_data["calls"] = [ts for ts in calls if ts > window_start]
                        cleaned_data[key] = limit_data

                # Write to disk (no lock needed - working with snapshot)
                with open(self.storage_path, 'w') as f:
                    json.dump(cleaned_data, f)

                # Set file permissions (Unix-like systems)
                if os.name == 'posix':
                    os.chmod(self.storage_path, 0o600)

                self.logger.debug(f"Saved rate limit data for {len(cleaned_data)} keys")

            except Exception as e:
                self.logger.warning(f"Could not save rate limit data: {e}")

        # Run save in background thread to avoid blocking
        import threading
        save_thread = threading.Thread(target=_do_save, daemon=True)
        save_thread.start()

    def _cleanup_expired_data(self) -> None:
        """Remove expired entries from rate limit data and stale locks."""
        now = time.time()
        keys_to_remove = []

        for key, limit_data in self._limits.items():
            window = limit_data.get("window_seconds", 60)
            calls = limit_data.get("calls", [])

            # Filter out expired calls
            valid_calls = [ts for ts in calls if now - ts < window]

            if valid_calls:
                limit_data["calls"] = valid_calls
            else:
                keys_to_remove.append(key)

        # Remove empty entries
        for key in keys_to_remove:
            del self._limits[key]

        # Clean up stale locks (locks for keys that no longer have data)
        self._cleanup_stale_locks(keys_to_remove)

    def _cleanup_stale_locks(self, removed_keys: List[str]) -> None:
        """Remove locks for keys that have been removed from rate limit data.

        This is called during data cleanup to remove locks for keys that
        no longer have rate limit data.

        Args:
            removed_keys: List of keys that were removed from rate limit data
        """
        with self._global_lock:
            # Remove locks for explicitly removed keys
            for key in removed_keys:
                if key in self._key_locks:
                    # Only remove if the lock is not currently held
                    lock, _ = self._key_locks[key]
                    if lock.acquire(blocking=False):
                        lock.release()
                        del self._key_locks[key]

            # Also clean up locks for keys without active rate limit data
            active_keys = set(self._limits.keys())
            stale_lock_keys = [
                k for k in list(self._key_locks.keys())
                if k not in active_keys
            ]

            for key in stale_lock_keys:
                if key in self._key_locks:
                    lock, _ = self._key_locks[key]
                    if lock.acquire(blocking=False):
                        lock.release()
                        del self._key_locks[key]

            # Note: MAX_LOCKS enforcement is now handled in _cleanup_expired_locks()

    def check_rate_limit(self, provider: str, identifier: Optional[str] = None) -> Tuple[bool, Optional[float]]:
        """Check if a request is within rate limits using sliding window.

        Args:
            provider: API provider name
            identifier: Optional identifier for more granular limiting

        Returns:
            Tuple of (is_allowed, wait_time_seconds)
        """
        key = f"{provider}:{identifier}" if identifier else provider
        key_lock = self._get_key_lock(key)

        with key_lock:
            now = time.time()

            # Get rate limit configuration for provider
            limit_config = self.default_limits.get(provider, (60, 60))
            max_calls, window_seconds = limit_config

            # Initialize limit data if not exists
            if key not in self._limits:
                self._limits[key] = {
                    "calls": [],
                    "window_seconds": window_seconds
                }

            limit_data = self._limits[key]
            calls = limit_data["calls"]

            # Sliding window: remove calls outside the current window
            window_start = now - window_seconds
            valid_calls = [ts for ts in calls if ts > window_start]
            limit_data["calls"] = valid_calls

            # Check if we're at the limit
            if len(valid_calls) >= max_calls:
                # Calculate wait time until oldest call expires
                if valid_calls:
                    oldest_call = min(valid_calls)
                    wait_time = window_seconds - (now - oldest_call)
                    if wait_time > 0:
                        return False, wait_time

                # All calls have expired, reset
                limit_data["calls"] = []

            # Record this call
            limit_data["calls"].append(now)

            # Trigger async save
            self._save_to_disk()

            return True, None

    def set_limit(self, provider: str, calls_per_window: int, window_seconds: int = 60) -> None:
        """Set custom rate limit for a provider.

        Args:
            provider: API provider name
            calls_per_window: Maximum calls per time window
            window_seconds: Time window in seconds (default: 60)
        """
        self.default_limits[provider] = (calls_per_window, window_seconds)
        self.logger.info(f"Set rate limit for {provider}: {calls_per_window} calls/{window_seconds}s")

    def get_usage_stats(self, provider: str, identifier: Optional[str] = None) -> Dict[str, Any]:
        """Get usage statistics for a provider.

        Args:
            provider: API provider name
            identifier: Optional identifier for more granular stats

        Returns:
            Usage statistics
        """
        key = f"{provider}:{identifier}" if identifier else provider
        key_lock = self._get_key_lock(key)

        with key_lock:
            now = time.time()

            # Get rate limit configuration
            limit_config = self.default_limits.get(provider, (60, 60))
            max_calls, window_seconds = limit_config

            if key not in self._limits:
                return {
                    "provider": provider,
                    "identifier": identifier,
                    "calls_in_window": 0,
                    "rate_limit": max_calls,
                    "window_seconds": window_seconds,
                    "available": max_calls,
                    "utilization": 0.0,
                    "reset_in_seconds": None
                }

            limit_data = self._limits[key]
            calls = limit_data["calls"]

            # Filter to current window
            window_start = now - window_seconds
            valid_calls = [ts for ts in calls if ts > window_start]

            # Calculate reset time
            reset_in = None
            if valid_calls:
                oldest_call = min(valid_calls)
                reset_in = window_seconds - (now - oldest_call)
                if reset_in < 0:
                    reset_in = 0

            return {
                "provider": provider,
                "identifier": identifier,
                "calls_in_window": len(valid_calls),
                "rate_limit": max_calls,
                "window_seconds": window_seconds,
                "available": max(0, max_calls - len(valid_calls)),
                "utilization": len(valid_calls) / max_calls if max_calls > 0 else 0,
                "reset_in_seconds": reset_in
            }

    def reset_provider(self, provider: str, identifier: Optional[str] = None) -> None:
        """Reset rate limit data for a provider.

        Args:
            provider: API provider name
            identifier: Optional identifier for more granular reset
        """
        key = f"{provider}:{identifier}" if identifier else provider
        key_lock = self._get_key_lock(key)

        with key_lock:
            if key in self._limits:
                del self._limits[key]
                self._save_to_disk(force=True)
                self.logger.info(f"Reset rate limit data for {key}")

    def reset_all(self) -> None:
        """Reset all rate limit data."""
        with self._global_lock:
            self._limits = {}
            self._save_to_disk(force=True)
            self.logger.info("Reset all rate limit data")

    def flush(self) -> None:
        """Force save current state to disk."""
        self._save_to_disk(force=True)


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
            PROVIDER_OPENAI: self._validate_openai_key,
            STT_DEEPGRAM: self._validate_deepgram_key,
            STT_ELEVENLABS: self._validate_elevenlabs_key,
            STT_GROQ: self._validate_groq_key,
            PROVIDER_ANTHROPIC: self._validate_anthropic_key,
        }

        # Configurable API key format rules
        # Format: (prefix, min_length, max_length, allowed_chars_pattern)
        # Use None for fields that shouldn't be checked
        # allowed_chars_pattern: 'alnum' for alphanumeric, 'alnum_dash' for alphanumeric + dash/underscore, or None
        self.api_key_formats = {
            PROVIDER_OPENAI: {"prefix": "sk-", "min_length": 20, "max_length": 200, "chars": "alnum_dash"},
            STT_GROQ: {"prefix": "gsk_", "min_length": 40, "max_length": 100, "chars": "alnum"},
            STT_DEEPGRAM: {"prefix": None, "min_length": 32, "max_length": 100, "chars": "alnum"},
            STT_ELEVENLABS: {"prefix": "sk_", "min_length": 30, "max_length": 100, "chars": "alnum"},
            PROVIDER_ANTHROPIC: {"prefix": "sk-ant-", "min_length": 90, "max_length": 200, "chars": "alnum_dash"},
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
                import re
                if not re.match(r'^[a-zA-Z0-9_-]+$', check_part):
                    return False, f"{provider_name} API key contains invalid characters"

        return True, None

    def _validate_openai_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate OpenAI API key format."""
        return self._validate_key_format(api_key, "openai")

    def _validate_groq_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Groq API key format."""
        return self._validate_key_format(api_key, "groq")

    def _validate_deepgram_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Deepgram API key format."""
        return self._validate_key_format(api_key, "deepgram")

    def _validate_elevenlabs_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate ElevenLabs API key format."""
        return self._validate_key_format(api_key, "elevenlabs")

    def _validate_anthropic_key(self, api_key: str) -> Tuple[bool, Optional[str]]:
        """Validate Anthropic API key format."""
        return self._validate_key_format(api_key, "anthropic")

    def update_api_key_format(self, provider: str, prefix: Optional[str] = None,
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

        self.logger.info(f"Updated API key format rules for {provider}: {rules}")
    
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
            # Note: Patterns must be specific to avoid false positives with medical text
            # (e.g., "cardiovascular system:" is legitimate medical documentation)
            injection_patterns = [
                r'ignore previous instructions',
                r'disregard all prior',
                r'forget everything',
                r'you are now',
                r'new instructions:',
                r'override:',
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