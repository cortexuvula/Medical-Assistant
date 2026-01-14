"""
Secure Key Storage Module

Provides encrypted storage for API keys using Fernet encryption.
"""

import os
import json
import hashlib
import logging
import secrets
import subprocess
import base64
from pathlib import Path
from typing import Dict, Optional, Any, List
from datetime import datetime
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.backends import default_backend
from threading import Lock

from core.config import get_config
from utils.exceptions import ConfigurationError


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


__all__ = ["SecureKeyStorage"]
